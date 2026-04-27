"""exp-20260426-013 shadow universe scout.

This is an observed-only universe expansion evaluation. It does not change the
production universe or shared strategy code.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime
from statistics import mean, median

import pandas as pd


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from filter import EVENT_KEYWORDS, WATCHLIST  # noqa: E402
from risk_engine import SECTOR_MAP  # noqa: E402


WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
    }),
])

OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "exp_20260426_013_universe_scout_results.json",
)

EVENT_TERMS = sorted(set(EVENT_KEYWORDS + [
    "contract",
    "partnership",
    "order",
    "launch",
    "approval",
    "fda",
    "sec",
    "probe",
    "settlement",
    "tariff",
    "short seller",
    "activist",
]))

FORWARD_HORIZONS = [1, 5, 10, 20]
MIN_MEDIAN_DOLLAR_VOLUME = 25_000_000
MIN_CLOSE = 5.0
MIN_COVERAGE_FRACTION = 0.95


def _load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _production_universe() -> set[str]:
    universe = {ticker.upper() for ticker in WATCHLIST}
    positions_path = os.path.join(REPO_ROOT, "data", "open_positions.json")
    if os.path.exists(positions_path):
        try:
            payload = _load_json(positions_path)
            for pos in payload.get("positions") or []:
                ticker = pos.get("ticker")
                if ticker:
                    universe.add(str(ticker).upper())
        except Exception:
            pass
    return universe


def _safe_mean(values):
    clean = [float(v) for v in values if v is not None]
    return round(mean(clean), 6) if clean else None


def _safe_median(values):
    clean = [float(v) for v in values if v is not None]
    return round(median(clean), 6) if clean else None


def _quantiles(values):
    clean = sorted(float(v) for v in values if v is not None)
    if not clean:
        return {"p10": None, "p25": None, "p50": None, "p75": None, "p90": None}

    def pick(q):
        idx = int(round((len(clean) - 1) * q))
        return round(clean[idx], 6)

    return {
        "p10": pick(0.10),
        "p25": pick(0.25),
        "p50": pick(0.50),
        "p75": pick(0.75),
        "p90": pick(0.90),
    }


def _date_key_from_path(path: str) -> str | None:
    stem = os.path.basename(path).split(".")[0]
    parts = stem.split("_")
    raw = parts[-1] if parts else ""
    if len(raw) != 8 or not raw.isdigit():
        return None
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"


def _has_event_term(item: dict) -> bool:
    text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
    return any(term.lower() in text for term in EVENT_TERMS)


def _load_news_events() -> list[dict]:
    events = []
    data_dir = os.path.join(REPO_ROOT, "data")
    for name in os.listdir(data_dir):
        if not (name.startswith("clean_news_") or name.startswith("clean_trade_news_")):
            continue
        if not name.endswith(".json"):
            continue
        path = os.path.join(data_dir, name)
        date_key = _date_key_from_path(path)
        if not date_key:
            continue
        try:
            items = _load_json(path)
        except Exception:
            continue
        for item in items if isinstance(items, list) else []:
            tickers = [str(t).upper() for t in item.get("tickers", []) if t]
            if not tickers:
                continue
            if item.get("tier") not in {"T1", "T2"} and not _has_event_term(item):
                continue
            for ticker in tickers:
                events.append({
                    "date": date_key,
                    "ticker": ticker,
                    "source_file": name,
                    "tier": item.get("tier"),
                    "title": item.get("title", ""),
                    "url": item.get("url"),
                })
    return events


def _load_frames(snapshot_path: str) -> tuple[dict[str, pd.DataFrame], dict]:
    payload = _load_json(os.path.join(REPO_ROOT, snapshot_path))
    frames = {}
    for ticker, rows in (payload.get("ohlcv") or {}).items():
        df = pd.DataFrame(rows)
        if df.empty:
            continue
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date").sort_index()
        frames[ticker.upper()] = df
    return frames, payload.get("metadata") or {}


def _expected_trading_days(frames: dict[str, pd.DataFrame], start: str, end: str) -> int:
    spy = frames.get("SPY")
    if spy is not None:
        return int(len(spy.loc[pd.Timestamp(start):pd.Timestamp(end)]))
    return max(
        [len(df.loc[pd.Timestamp(start):pd.Timestamp(end)]) for df in frames.values()],
        default=0,
    )


def _ticker_liquidity(df: pd.DataFrame, start: str, end: str) -> dict:
    window = df.loc[pd.Timestamp(start):pd.Timestamp(end)]
    if window.empty:
        return {
            "coverage_days": 0,
            "median_dollar_volume": None,
            "median_close": None,
            "last_close": None,
        }
    dollar_volume = window["Close"].astype(float) * window["Volume"].astype(float)
    return {
        "coverage_days": int(len(window)),
        "median_dollar_volume": round(float(dollar_volume.median()), 2),
        "median_close": round(float(window["Close"].median()), 4),
        "last_close": round(float(window["Close"].iloc[-1]), 4),
    }


def _passes_liquidity(liquidity: dict, expected_days: int) -> bool:
    coverage_fraction = (
        liquidity["coverage_days"] / expected_days
        if expected_days
        else 0.0
    )
    return (
        coverage_fraction >= MIN_COVERAGE_FRACTION
        and (liquidity.get("median_dollar_volume") or 0.0) >= MIN_MEDIAN_DOLLAR_VOLUME
        and (liquidity.get("median_close") or 0.0) >= MIN_CLOSE
    )


def _forward_returns(df: pd.DataFrame, event_date: str) -> dict[str, float | None]:
    asof = pd.Timestamp(event_date)
    hist = df.loc[:asof]
    if hist.empty:
        return {f"fwd_{h}d": None for h in FORWARD_HORIZONS}
    start_idx = df.index.get_loc(hist.index[-1])
    start_close = float(df["Close"].iloc[start_idx])
    out = {}
    for horizon in FORWARD_HORIZONS:
        target_idx = start_idx + horizon
        if target_idx >= len(df) or start_close <= 0:
            out[f"fwd_{horizon}d"] = None
        else:
            target_close = float(df["Close"].iloc[target_idx])
            out[f"fwd_{horizon}d"] = round((target_close - start_close) / start_close, 6)
    return out


def _load_existing_ab_touchpoints() -> tuple[set[tuple[str, str]], set[str]]:
    touchpoints: set[tuple[str, str]] = set()
    traded_tickers: set[str] = set()
    for name in os.listdir(os.path.join(REPO_ROOT, "data")):
        if not name.startswith("backtest_results_") or not name.endswith(".json"):
            continue
        try:
            data = _load_json(os.path.join(REPO_ROOT, "data", name))
        except Exception:
            continue
        for trade in data.get("trades") or []:
            strategy = trade.get("strategy")
            ticker = trade.get("ticker")
            entry_date = trade.get("entry_date")
            if strategy in {"trend_long", "breakout_long"} and ticker and entry_date:
                touchpoints.add((ticker.upper(), entry_date))
                traded_tickers.add(ticker.upper())

    for name in os.listdir(os.path.join(REPO_ROOT, "data")):
        if not (name.startswith("quant_signals_") or name.startswith("trend_signals_")):
            continue
        if not name.endswith(".json"):
            continue
        date_key = _date_key_from_path(os.path.join(REPO_ROOT, "data", name))
        if not date_key:
            continue
        try:
            data = _load_json(os.path.join(REPO_ROOT, "data", name))
        except Exception:
            continue
        signals = data.get("signals") if isinstance(data, dict) else data
        if isinstance(signals, dict):
            signals = signals.values()
        for sig in signals or []:
            if not isinstance(sig, dict):
                continue
            strategy = sig.get("strategy")
            ticker = sig.get("ticker")
            if strategy in {"trend_long", "breakout_long"} and ticker:
                touchpoints.add((ticker.upper(), date_key))
                traded_tickers.add(ticker.upper())
    return touchpoints, traded_tickers


def _summarize_returns(rows: list[dict]) -> dict:
    summary = {}
    for horizon in FORWARD_HORIZONS:
        key = f"fwd_{horizon}d"
        values = [row.get(key) for row in rows if row.get(key) is not None]
        positives = [v for v in values if v > 0]
        summary[key] = {
            "count": len(values),
            "avg": _safe_mean(values),
            "median": _safe_median(values),
            "win_rate": round(len(positives) / len(values), 4) if values else None,
            **_quantiles(values),
        }
    return summary


def _window_events(events: list[dict], start: str, end: str) -> list[dict]:
    s = pd.Timestamp(start)
    e = pd.Timestamp(end)
    out = []
    seen = set()
    for event in events:
        d = pd.Timestamp(event["date"])
        key = (event["date"], event["ticker"], event.get("title"))
        if s <= d <= e and key not in seen:
            out.append(event)
            seen.add(key)
    return out


def _evaluate_window(
    label: str,
    cfg: dict,
    events: list[dict],
    production_universe: set[str],
    ab_touchpoints: set[tuple[str, str]],
    ab_traded_tickers: set[str],
) -> dict:
    frames, metadata = _load_frames(cfg["snapshot"])
    expected_days = _expected_trading_days(frames, cfg["start"], cfg["end"])
    snapshot_tickers = set(frames)
    candidates = _window_events(events, cfg["start"], cfg["end"])

    liquidity_by_ticker = {
        ticker: _ticker_liquidity(df, cfg["start"], cfg["end"])
        for ticker, df in frames.items()
    }
    liquid_tickers = {
        ticker
        for ticker, info in liquidity_by_ticker.items()
        if _passes_liquidity(info, expected_days)
    }

    rows = []
    skipped = Counter()
    for event in candidates:
        ticker = event["ticker"]
        if ticker not in snapshot_tickers:
            skipped["missing_ohlcv_snapshot"] += 1
            continue
        if ticker not in liquid_tickers:
            skipped["failed_liquidity_or_coverage"] += 1
            continue
        returns = _forward_returns(frames[ticker], event["date"])
        row = {
            **event,
            "sector": SECTOR_MAP.get(ticker, "Unknown"),
            "in_production_universe": ticker in production_universe,
            "ticker_in_prior_ab_trades_or_signals": ticker in ab_traded_tickers,
            "same_day_ab_overlap": (ticker, event["date"]) in ab_touchpoints,
            "liquidity": liquidity_by_ticker[ticker],
            **returns,
        }
        rows.append(row)

    unique_tickers = sorted({row["ticker"] for row in rows})
    non_overlap_rows = [
        row for row in rows
        if not row["same_day_ab_overlap"]
    ]
    outside_production_rows = [
        row for row in rows
        if not row["in_production_universe"]
    ]
    by_sector = Counter(row["sector"] for row in rows)
    event_counts = Counter(row["ticker"] for row in rows)
    same_day_overlaps = sum(1 for row in rows if row["same_day_ab_overlap"])
    ticker_history_overlaps = sum(1 for row in rows if row["ticker_in_prior_ab_trades_or_signals"])

    return {
        "window": label,
        "start": cfg["start"],
        "end": cfg["end"],
        "snapshot": cfg["snapshot"],
        "snapshot_ticker_count": len(snapshot_tickers),
        "snapshot_metadata_ticker_count": len(metadata.get("tickers") or []),
        "expected_trading_days": expected_days,
        "production_universe_count": len(production_universe),
        "raw_event_records": len(candidates),
        "qualified_event_records": len(rows),
        "qualified_unique_tickers": len(unique_tickers),
        "qualified_tickers": unique_tickers,
        "skipped": dict(sorted(skipped.items())),
        "candidate_count_by_sector": dict(sorted(by_sector.items())),
        "top_event_tickers": event_counts.most_common(12),
        "same_day_ab_overlap_count": same_day_overlaps,
        "same_day_ab_overlap_rate": round(same_day_overlaps / len(rows), 4) if rows else None,
        "ticker_history_ab_overlap_count": ticker_history_overlaps,
        "ticker_history_ab_overlap_rate": round(ticker_history_overlaps / len(rows), 4) if rows else None,
        "outside_production_event_count": len(outside_production_rows),
        "outside_production_unique_tickers": sorted({row["ticker"] for row in outside_production_rows}),
        "forward_return_distribution": _summarize_returns(rows),
        "non_same_day_overlap_forward_return_distribution": _summarize_returns(non_overlap_rows),
        "sample_candidates": [
            {
                "date": row["date"],
                "ticker": row["ticker"],
                "sector": row["sector"],
                "same_day_ab_overlap": row["same_day_ab_overlap"],
                "in_production_universe": row["in_production_universe"],
                "median_dollar_volume": row["liquidity"]["median_dollar_volume"],
                "fwd_5d": row["fwd_5d"],
                "fwd_10d": row["fwd_10d"],
                "title": row["title"][:180],
            }
            for row in rows[:25]
        ],
    }


def main() -> int:
    production_universe = _production_universe()
    events = _load_news_events()
    ab_touchpoints, ab_traded_tickers = _load_existing_ab_touchpoints()

    windows = []
    for label, cfg in WINDOWS.items():
        summary = _evaluate_window(
            label,
            cfg,
            events,
            production_universe,
            ab_touchpoints,
            ab_traded_tickers,
        )
        windows.append(summary)
        fwd10 = summary["forward_return_distribution"]["fwd_10d"]
        print(
            f"[{label}] raw_events={summary['raw_event_records']} "
            f"qualified={summary['qualified_event_records']} "
            f"unique={summary['qualified_unique_tickers']} "
            f"same_day_overlap={summary['same_day_ab_overlap_rate']} "
            f"fwd10_avg={fwd10['avg']} fwd10_wr={fwd10['win_rate']}"
        )

    payload = {
        "experiment_id": "exp-20260426-013",
        "status": "observed_only",
        "created_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "hypothesis": (
            "A liquidity-filtered event-sensitive shadow universe can surface "
            "non-overlapping candidates with acceptable data coverage and "
            "forward-return quality outside the current accepted A/B universe."
        ),
        "single_causal_variable": "event-sensitive liquidity-filtered shadow universe definition",
        "shadow_universe_definition": {
            "source": "archived clean_news_* and clean_trade_news_* ticker-tagged event items",
            "event_terms": EVENT_TERMS,
            "liquidity_filters": {
                "min_median_dollar_volume": MIN_MEDIAN_DOLLAR_VOLUME,
                "min_close": MIN_CLOSE,
                "min_coverage_fraction": MIN_COVERAGE_FRACTION,
            },
            "forward_return_horizons_trading_days": FORWARD_HORIZONS,
        },
        "survivorship_bias_risk": (
            "High. Snapshot OHLCV only contains tickers already available in "
            "the repository snapshots, so this evaluates a shadow candidate "
            "source within the current archived data universe rather than a "
            "survivorship-free historical expansion."
        ),
        "production_promotion": False,
        "promotion_blockers": [
            "No production universe write was attempted.",
            "Outside-production ticker evidence is limited by archived OHLCV coverage.",
            "Candidate count alone is not an alpha claim; any promotion needs scarce-slot quality evidence.",
        ],
        "windows": windows,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
