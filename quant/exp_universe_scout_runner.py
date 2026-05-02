"""exp-20260501-013 event-sensitive liquidity-filtered universe scout.

Observed-only shadow evaluation. This does not change the production universe,
signal engine, risk engine, or portfolio engine.
"""

from __future__ import annotations

import json
import math
import os
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from statistics import mean, median

import pandas as pd


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from filter import EVENT_KEYWORDS, WATCHLIST  # noqa: E402
from risk_engine import SECTOR_MAP  # noqa: E402


EXPERIMENT_ID = "exp-20260501-013"
OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "exp_universe_scout_event_sensitive_liquidity.json",
)

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

EVENT_TERMS = sorted(set(EVENT_KEYWORDS + [
    "activist",
    "approval",
    "award",
    "buyback",
    "contract",
    "fda",
    "guidance",
    "launch",
    "order",
    "partnership",
    "probe",
    "sec",
    "settlement",
    "short seller",
    "tariff",
]))

EXCLUDED_TICKERS = {
    "GLD", "IAU", "IEF", "IWM", "QQQ", "SLV", "SPY", "TLT",
    "UUP", "USO", "XLE", "XLP", "XLU", "XLV",
}

FORWARD_HORIZONS = [1, 5, 10, 20]
MIN_MEDIAN_DOLLAR_VOLUME = 25_000_000
MIN_CLOSE = 5.0
MIN_COVERAGE_FRACTION = 0.95


def _load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _date_key_from_path(path: str) -> str | None:
    stem = os.path.basename(path).split(".")[0]
    raw = stem.split("_")[-1]
    if len(raw) != 8 or not raw.isdigit():
        return None
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"


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


def _has_event_term(item: dict) -> bool:
    text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
    return any(term.lower() in text for term in EVENT_TERMS)


def _load_news_events() -> list[dict]:
    events = []
    data_dir = os.path.join(REPO_ROOT, "data")
    for name in sorted(os.listdir(data_dir)):
        if not (name.startswith("clean_news_") or name.startswith("clean_trade_news_")):
            continue
        if not name.endswith(".json"):
            continue
        date_key = _date_key_from_path(name)
        if not date_key:
            continue
        try:
            items = _load_json(os.path.join(data_dir, name))
        except Exception:
            continue
        if not isinstance(items, list):
            continue
        for item in items:
            tickers = [str(t).upper() for t in item.get("tickers", []) if t]
            if not tickers:
                continue
            is_event = item.get("tier") in {"T1", "T2"} or _has_event_term(item)
            if not is_event:
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
        frames[ticker.upper()] = df.set_index("Date").sort_index()
    return frames, payload.get("metadata") or {}


def _expected_trading_days(frames: dict[str, pd.DataFrame], start: str, end: str) -> int:
    spy = frames.get("SPY")
    if spy is not None:
        return int(len(spy.loc[pd.Timestamp(start):pd.Timestamp(end)]))
    return max(
        [len(df.loc[pd.Timestamp(start):pd.Timestamp(end)]) for df in frames.values()],
        default=0,
    )


def _ticker_liquidity(df: pd.DataFrame, start: str, end: str, expected_days: int) -> dict:
    window = df.loc[pd.Timestamp(start):pd.Timestamp(end)]
    if window.empty:
        return {
            "coverage_days": 0,
            "coverage_fraction": 0.0,
            "median_dollar_volume": None,
            "median_close": None,
            "last_close": None,
        }
    dollar_volume = window["Close"].astype(float) * window["Volume"].astype(float)
    coverage = len(window) / expected_days if expected_days else 0.0
    return {
        "coverage_days": int(len(window)),
        "coverage_fraction": round(coverage, 4),
        "median_dollar_volume": round(float(dollar_volume.median()), 2),
        "median_close": round(float(window["Close"].median()), 4),
        "last_close": round(float(window["Close"].iloc[-1]), 4),
    }


def _passes_liquidity(liquidity: dict) -> bool:
    return (
        liquidity["coverage_fraction"] >= MIN_COVERAGE_FRACTION
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


def _load_existing_ab_touchpoints() -> tuple[set[tuple[str, str]], set[str], Counter]:
    touchpoints: set[tuple[str, str]] = set()
    tickers: set[str] = set()
    by_ticker: Counter = Counter()
    data_dir = os.path.join(REPO_ROOT, "data")
    for name in os.listdir(data_dir):
        if not name.startswith("backtest_results_") or not name.endswith(".json"):
            continue
        try:
            payload = _load_json(os.path.join(data_dir, name))
        except Exception:
            continue
        for trade in payload.get("trades") or []:
            if trade.get("strategy") not in {"trend_long", "breakout_long"}:
                continue
            ticker = trade.get("ticker")
            entry_date = trade.get("entry_date")
            if ticker and entry_date:
                ticker = str(ticker).upper()
                touchpoints.add((ticker, str(entry_date)[:10]))
                tickers.add(ticker)
                by_ticker[ticker] += 1

    for name in os.listdir(data_dir):
        if not (name.startswith("quant_signals_") or name.startswith("trend_signals_")):
            continue
        if not name.endswith(".json"):
            continue
        date_key = _date_key_from_path(name)
        if not date_key:
            continue
        try:
            payload = _load_json(os.path.join(data_dir, name))
        except Exception:
            continue
        signals = payload.get("signals") if isinstance(payload, dict) else payload
        if isinstance(signals, dict):
            signals = signals.values()
        for sig in signals or []:
            if not isinstance(sig, dict):
                continue
            if sig.get("strategy") not in {"trend_long", "breakout_long"}:
                continue
            ticker = sig.get("ticker")
            if ticker:
                ticker = str(ticker).upper()
                touchpoints.add((ticker, date_key))
                tickers.add(ticker)
                by_ticker[ticker] += 1
    return touchpoints, tickers, by_ticker


def _safe_mean(values):
    clean = [float(v) for v in values if v is not None and not math.isnan(float(v))]
    return round(mean(clean), 6) if clean else None


def _safe_median(values):
    clean = [float(v) for v in values if v is not None and not math.isnan(float(v))]
    return round(median(clean), 6) if clean else None


def _quantiles(values):
    clean = sorted(float(v) for v in values if v is not None and not math.isnan(float(v)))
    if not clean:
        return {"p10": None, "p25": None, "p50": None, "p75": None, "p90": None}

    def pick(q: float) -> float:
        return round(clean[int(round((len(clean) - 1) * q))], 6)

    return {
        "p10": pick(0.10),
        "p25": pick(0.25),
        "p50": pick(0.50),
        "p75": pick(0.75),
        "p90": pick(0.90),
    }


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


def _scarce_slot_summary(rows: list[dict]) -> dict:
    overlap_rows = [row for row in rows if row["same_day_ab_overlap"]]
    non_overlap_rows = [row for row in rows if not row["same_day_ab_overlap"]]
    same_ticker_rows = [row for row in rows if row["same_ticker_ab_overlap"]]
    return {
        "candidate_days": len({row["date"] for row in rows}),
        "same_day_ab_overlap_count": len(overlap_rows),
        "same_day_ab_overlap_rate": round(len(overlap_rows) / len(rows), 4) if rows else None,
        "same_ticker_ab_overlap_count": len(same_ticker_rows),
        "same_ticker_ab_overlap_rate": round(len(same_ticker_rows) / len(rows), 4) if rows else None,
        "ticker_history_ab_overlap_count": sum(1 for row in rows if row["ticker_in_prior_ab_trades_or_signals"]),
        "ticker_history_ab_overlap_rate": (
            round(sum(1 for row in rows if row["ticker_in_prior_ab_trades_or_signals"]) / len(rows), 4)
            if rows else None
        ),
        "fwd_10d_all": _summarize_returns(rows)["fwd_10d"],
        "fwd_10d_non_same_day_overlap": _summarize_returns(non_overlap_rows)["fwd_10d"],
        "fwd_10d_same_day_overlap": _summarize_returns(overlap_rows)["fwd_10d"],
        "scarce_slot_value_proxy": (
            "Positive if non-overlap 10d average/win-rate exceeds overlap and all-candidate baseline; "
            "still not a production claim without slot-aware replay."
        ),
    }


def _evaluate_window(
    label: str,
    cfg: dict,
    events: list[dict],
    production_universe: set[str],
    ab_touchpoints: set[tuple[str, str]],
    ab_tickers: set[str],
    ab_by_ticker: Counter,
) -> dict:
    frames, metadata = _load_frames(cfg["snapshot"])
    expected_days = _expected_trading_days(frames, cfg["start"], cfg["end"])
    snapshot_tickers = set(frames)
    candidates = _window_events(events, cfg["start"], cfg["end"])

    liquidity_by_ticker = {
        ticker: _ticker_liquidity(df, cfg["start"], cfg["end"], expected_days)
        for ticker, df in frames.items()
    }
    liquid_tickers = {
        ticker
        for ticker, info in liquidity_by_ticker.items()
        if ticker not in EXCLUDED_TICKERS and _passes_liquidity(info)
    }

    rows = []
    skipped = Counter()
    for event in candidates:
        ticker = event["ticker"]
        if ticker in EXCLUDED_TICKERS:
            skipped["excluded_etf_or_macro_proxy"] += 1
            continue
        if ticker not in snapshot_tickers:
            skipped["missing_ohlcv_snapshot"] += 1
            continue
        if ticker not in liquid_tickers:
            skipped["failed_liquidity_or_coverage"] += 1
            continue
        same_day_ab = (ticker, event["date"]) in ab_touchpoints
        row = {
            **event,
            "sector": SECTOR_MAP.get(ticker, "Unknown"),
            "in_production_universe": ticker in production_universe,
            "ticker_in_prior_ab_trades_or_signals": ticker in ab_tickers,
            "same_day_ab_overlap": same_day_ab,
            "same_ticker_ab_overlap": same_day_ab,
            "ab_touchpoint_count_all_archives": int(ab_by_ticker[ticker]),
            "liquidity": liquidity_by_ticker[ticker],
            **_forward_returns(frames[ticker], event["date"]),
        }
        rows.append(row)

    unique_tickers = sorted({row["ticker"] for row in rows})
    outside_production_rows = [row for row in rows if not row["in_production_universe"]]
    by_sector = Counter(row["sector"] for row in rows)
    event_counts = Counter(row["ticker"] for row in rows)
    coverage_values = [row["liquidity"]["coverage_fraction"] for row in rows]
    dollar_volume_values = [row["liquidity"]["median_dollar_volume"] for row in rows]

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
        "candidate_count": len(rows),
        "candidate_unique_tickers": len(unique_tickers),
        "candidate_tickers": unique_tickers,
        "skipped": dict(sorted(skipped.items())),
        "liquidity_filter": {
            "min_median_dollar_volume": MIN_MEDIAN_DOLLAR_VOLUME,
            "min_close": MIN_CLOSE,
            "min_coverage_fraction": MIN_COVERAGE_FRACTION,
            "qualified_liquid_snapshot_tickers": len(liquid_tickers),
            "candidate_median_coverage_fraction": _safe_median(coverage_values),
            "candidate_median_dollar_volume": _safe_median(dollar_volume_values),
        },
        "candidate_count_by_sector": dict(sorted(by_sector.items())),
        "top_event_tickers": event_counts.most_common(12),
        "outside_production_event_count": len(outside_production_rows),
        "outside_production_unique_tickers": sorted({row["ticker"] for row in outside_production_rows}),
        "forward_return_distribution": _summarize_returns(rows),
        "scarce_slot_value": _scarce_slot_summary(rows),
        "sample_candidates": [
            {
                "date": row["date"],
                "ticker": row["ticker"],
                "sector": row["sector"],
                "tier": row["tier"],
                "same_day_ab_overlap": row["same_day_ab_overlap"],
                "ticker_in_prior_ab_trades_or_signals": row["ticker_in_prior_ab_trades_or_signals"],
                "in_production_universe": row["in_production_universe"],
                "coverage_fraction": row["liquidity"]["coverage_fraction"],
                "median_dollar_volume": row["liquidity"]["median_dollar_volume"],
                "fwd_5d": row["fwd_5d"],
                "fwd_10d": row["fwd_10d"],
                "title": row["title"][:180],
            }
            for row in rows[:40]
        ],
    }


def main() -> int:
    production_universe = _production_universe()
    events = _load_news_events()
    ab_touchpoints, ab_tickers, ab_by_ticker = _load_existing_ab_touchpoints()

    windows = []
    for label, cfg in WINDOWS.items():
        summary = _evaluate_window(
            label,
            cfg,
            events,
            production_universe,
            ab_touchpoints,
            ab_tickers,
            ab_by_ticker,
        )
        windows.append(summary)
        fwd10 = summary["forward_return_distribution"]["fwd_10d"]
        scarce = summary["scarce_slot_value"]
        print(
            f"[{label}] raw_events={summary['raw_event_records']} "
            f"candidates={summary['candidate_count']} "
            f"unique={summary['candidate_unique_tickers']} "
            f"overlap={scarce['same_day_ab_overlap_rate']} "
            f"outside_prod={summary['outside_production_event_count']} "
            f"fwd10_avg={fwd10['avg']} fwd10_wr={fwd10['win_rate']}"
        )

    aggregate_rows = []
    for window in windows:
        aggregate_rows.extend(window.get("sample_candidates", []))

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "status": "observed_only",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hypothesis": (
            "An event-sensitive liquidity-filtered shadow universe may identify "
            "scarce external candidates with sufficient data coverage, tradable "
            "liquidity, lower production overlap, and useful forward returns "
            "without adding tickers to production."
        ),
        "single_causal_variable": "event-sensitive liquidity-filtered universe",
        "alpha_hypothesis": {
            "category": "universe_scout",
            "statement": (
                "Ticker-tagged event/news candidates with full OHLCV coverage and "
                "institutional liquidity may offer better scarce-slot candidates "
                "than broad technical-only shadow sources."
            ),
            "why_not_production_now": (
                "This is a shadow-only measurement under survivorship-biased archived "
                "snapshots and does not run through production sizing, exits, or slot competition."
            ),
        },
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
        "survivorship_bias_risk": {
            "level": "high",
            "reason": (
                "OHLCV snapshots only include tickers already archived in this repo. "
                "The scout measures source quality inside available data, not a "
                "survivorship-free external universe."
            ),
        },
        "production_promotion": False,
        "promotion_blockers": [
            "No production universe write was attempted.",
            "Outside-production evidence is limited by archived OHLCV coverage.",
            "Scarce-slot value is measured with forward returns and overlap only; no slot-aware replay was run.",
            "Recent universe expansion logs show repeated ETF/noisy expansion failures; this run is audit-only.",
        ],
        "windows": windows,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
