"""exp-20260428-020 narrow shadow universe definition scout.

Observed-only universe scout. This script does not change production universe
membership, shared strategy code, or portfolio behavior.
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


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from filter import WATCHLIST  # noqa: E402
from risk_engine import SECTOR_MAP  # noqa: E402


EXPERIMENT_ID = "exp-20260428-020"
OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "experiments",
    EXPERIMENT_ID,
    "exp_20260428_020_narrow_shadow_universe_definition.json",
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

FORWARD_HORIZONS = [1, 5, 10, 20]

EXCLUDED_TICKERS = {
    "GLD", "IAU", "IEF", "IWM", "QQQ", "SLV", "SPY", "TLT",
    "UUP", "USO", "XLE", "XLP", "XLU", "XLV",
}

MIN_COVERAGE_FRACTION = 0.95
MIN_MEDIAN_DOLLAR_VOLUME = 40_000_000
MIN_CLOSE = 8.0
HIGH_LOOKBACK_DAYS = 63
MIN_BASE_DAYS_WITHOUT_HIGH = 30
MAX_20D_RETURN_BEFORE_BREAKOUT = 0.18
MIN_VOLUME_RATIO = 1.10
MIN_CLOSE_LOCATION = 0.60
TOP_PER_DAY = 5


def _load_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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


def _expected_days(frames: dict[str, pd.DataFrame], start: str, end: str) -> int:
    spy = frames.get("SPY")
    if spy is None:
        return 0
    return int(len(spy.loc[pd.Timestamp(start):pd.Timestamp(end)]))


def _clean(values):
    return [float(v) for v in values if v is not None and not math.isnan(float(v))]


def _safe_mean(values):
    clean = _clean(values)
    return round(mean(clean), 6) if clean else None


def _safe_median(values):
    clean = _clean(values)
    return round(median(clean), 6) if clean else None


def _quantiles(values):
    clean = sorted(_clean(values))
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
    out = {}
    for horizon in FORWARD_HORIZONS:
        key = f"fwd_{horizon}d"
        values = [row.get(key) for row in rows if row.get(key) is not None]
        positives = [v for v in values if v > 0]
        out[key] = {
            "count": len(values),
            "avg": _safe_mean(values),
            "median": _safe_median(values),
            "win_rate": round(len(positives) / len(values), 4) if values else None,
            **_quantiles(values),
        }
    return out


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


def _load_existing_ab_context() -> tuple[set[tuple[str, str]], set[str], Counter, set[str]]:
    touchpoints: set[tuple[str, str]] = set()
    tickers: set[str] = set()
    by_ticker: Counter = Counter()
    active_days: set[str] = set()
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
            entry_date = str(trade.get("entry_date") or "")[:10]
            if ticker and entry_date:
                ticker = str(ticker).upper()
                touchpoints.add((ticker, entry_date))
                tickers.add(ticker)
                by_ticker[ticker] += 1
                active_days.add(entry_date)

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
                active_days.add(date_key)
    return touchpoints, tickers, by_ticker, active_days


def _ticker_liquidity(
    ticker: str,
    df: pd.DataFrame,
    start: str,
    end: str,
    expected_days: int,
    ab_by_ticker: Counter,
) -> dict:
    window = df.loc[pd.Timestamp(start):pd.Timestamp(end)]
    if window.empty:
        return {
            "ticker": ticker,
            "coverage_days": 0,
            "coverage_fraction": 0.0,
            "median_dollar_volume": None,
            "median_close": None,
            "sector": SECTOR_MAP.get(ticker, "Unknown"),
        }
    dollar_volume = window["Close"].astype(float) * window["Volume"].astype(float)
    return {
        "ticker": ticker,
        "coverage_days": int(len(window)),
        "coverage_fraction": round(len(window) / expected_days, 4) if expected_days else 0.0,
        "median_dollar_volume": round(float(dollar_volume.median()), 2),
        "median_close": round(float(window["Close"].median()), 4),
        "last_close": round(float(window["Close"].iloc[-1]), 4),
        "sector": SECTOR_MAP.get(ticker, "Unknown"),
        "ab_touchpoint_days_all_archives": int(ab_by_ticker[ticker]),
    }


def _passes_liquidity(info: dict) -> bool:
    return (
        info["coverage_fraction"] >= MIN_COVERAGE_FRACTION
        and (info.get("median_dollar_volume") or 0.0) >= MIN_MEDIAN_DOLLAR_VOLUME
        and (info.get("median_close") or 0.0) >= MIN_CLOSE
    )


def _add_features(df: pd.DataFrame, spy: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["high63_prev"] = out["High"].shift(1).rolling(HIGH_LOOKBACK_DAYS).max()
    out["fresh_high63"] = out["Close"] > out["high63_prev"]
    out["days_since_high63"] = 0
    days_since = 10_000
    values = []
    for fresh in out["fresh_high63"].fillna(False):
        days_since = 0 if bool(fresh) else days_since + 1
        values.append(days_since)
    out["days_since_high63"] = pd.Series(values, index=out.index).shift(1)
    out["ret20"] = out["Close"] / out["Close"].shift(20) - 1
    out["ret63"] = out["Close"] / out["Close"].shift(63) - 1
    out["spy_ret20"] = spy["Close"] / spy["Close"].shift(20) - 1
    out["spy_ret63"] = spy["Close"] / spy["Close"].shift(63) - 1
    out["avg_volume20"] = out["Volume"].shift(1).rolling(20).mean()
    out["volume_ratio"] = out["Volume"] / out["avg_volume20"]
    day_range = (out["High"] - out["Low"]).replace(0, pd.NA)
    out["close_location"] = (out["Close"] - out["Low"]) / day_range
    out["dollar_volume"] = out["Close"] * out["Volume"]
    return out


def _forward_returns(df: pd.DataFrame, date_key: str) -> dict:
    asof = pd.Timestamp(date_key)
    if asof not in df.index:
        hist = df.loc[:asof]
        if hist.empty:
            return {f"fwd_{h}d": None for h in FORWARD_HORIZONS}
        asof = hist.index[-1]
    idx = df.index.get_loc(asof)
    entry = float(df.iloc[idx]["Close"])
    out = {}
    for horizon in FORWARD_HORIZONS:
        fwd_idx = idx + horizon
        key = f"fwd_{horizon}d"
        if fwd_idx >= len(df) or entry <= 0:
            out[key] = None
        else:
            out[key] = round(float(df.iloc[fwd_idx]["Close"]) / entry - 1, 6)
    return out


def _candidate(ticker: str, row: pd.Series) -> dict | None:
    required = [
        row.get("fresh_high63"),
        row.get("days_since_high63"),
        row.get("ret20"),
        row.get("ret63"),
        row.get("spy_ret20"),
        row.get("volume_ratio"),
        row.get("close_location"),
    ]
    if any(value is None or pd.isna(value) for value in required):
        return None
    if not bool(row["fresh_high63"]):
        return None
    if float(row["days_since_high63"]) < MIN_BASE_DAYS_WITHOUT_HIGH:
        return None
    if float(row["ret20"]) > MAX_20D_RETURN_BEFORE_BREAKOUT:
        return None
    if float(row["volume_ratio"]) < MIN_VOLUME_RATIO:
        return None
    if float(row["close_location"]) < MIN_CLOSE_LOCATION:
        return None

    rs20 = float(row["ret20"]) - float(row["spy_ret20"])
    rs63 = float(row["ret63"]) - float(row["spy_ret63"])
    score = (
        1.0
        + min(float(row["days_since_high63"]) / 100.0, 1.0) * 0.25
        + min(max(rs20, 0.0), 0.12) * 2.0
        + min(max(rs63, 0.0), 0.25) * 1.0
        + min(float(row["volume_ratio"]) - MIN_VOLUME_RATIO, 2.0) * 0.08
        + min(float(row["close_location"]) - MIN_CLOSE_LOCATION, 0.4) * 0.15
    )
    return {
        "ticker": ticker,
        "date": row.name.strftime("%Y-%m-%d"),
        "shadow_score": round(score, 4),
        "sector": SECTOR_MAP.get(ticker, "Unknown"),
        "close": round(float(row["Close"]), 4),
        "conditions": {
            "days_since_prior_63d_high": int(row["days_since_high63"]),
            "ret20": round(float(row["ret20"]), 6),
            "ret63": round(float(row["ret63"]), 6),
            "spy_ret20": round(float(row["spy_ret20"]), 6),
            "spy_ret63": round(float(row["spy_ret63"]), 6),
            "rs20_vs_spy": round(rs20, 6),
            "rs63_vs_spy": round(rs63, 6),
            "volume_ratio": round(float(row["volume_ratio"]), 4),
            "close_location": round(float(row["close_location"]), 4),
            "dollar_volume": round(float(row["dollar_volume"]), 2),
        },
    }


def _scarce_slot_proxy(rows: list[dict], ab_active_days: set[str]) -> dict:
    by_day: OrderedDict[str, list[dict]] = OrderedDict()
    for row in sorted(rows, key=lambda r: (r["date"], -r["shadow_score"], r["ticker"])):
        by_day.setdefault(row["date"], []).append(row)
    top_rows = []
    for day_rows in by_day.values():
        top_rows.extend(day_rows[:TOP_PER_DAY])
    ab_days = {day for day in by_day if day in ab_active_days}
    return {
        "candidate_days": len(by_day),
        "ab_active_day_count": len(ab_days),
        "ab_active_day_rate": round(len(ab_days) / len(by_day), 4) if by_day else None,
        "top_per_day_limit": TOP_PER_DAY,
        "top_per_day_candidate_count": len(top_rows),
        "top_per_day_forward_returns": _summarize_returns(top_rows),
        "all_candidate_forward_returns": _summarize_returns(rows),
        "note": "Top-per-day returns are only a scarce-slot proxy; no fills, stops, sizing, or slot-aware replay ran.",
    }


def _audit_window(name: str, cfg: dict, production_universe: set[str], ab_context: tuple) -> dict:
    ab_touchpoints, ab_tickers, ab_by_ticker, ab_active_days = ab_context
    frames, metadata = _load_frames(cfg["snapshot"])
    start = cfg["start"]
    end = cfg["end"]
    expected_days = _expected_days(frames, start, end)
    spy = frames["SPY"]

    liquidity = {}
    liquid_tickers = []
    rejections = Counter()
    for ticker, df in frames.items():
        if ticker in EXCLUDED_TICKERS:
            rejections["excluded_etf_or_macro_proxy"] += 1
            continue
        info = _ticker_liquidity(ticker, df, start, end, expected_days, ab_by_ticker)
        liquidity[ticker] = info
        if _passes_liquidity(info):
            liquid_tickers.append(ticker)
        else:
            rejections["failed_liquidity_or_coverage"] += 1

    candidates = []
    for ticker in sorted(liquid_tickers):
        features = _add_features(frames[ticker], spy)
        window = features.loc[pd.Timestamp(start):pd.Timestamp(end)]
        for _, row in window.iterrows():
            signal = _candidate(ticker, row)
            if not signal:
                continue
            signal.update(_forward_returns(frames[ticker], signal["date"]))
            signal["same_day_ab_overlap"] = (ticker, signal["date"]) in ab_touchpoints
            signal["ticker_in_prior_ab_trades_or_signals"] = ticker in ab_tickers
            signal["in_production_universe"] = ticker in production_universe
            signal["median_dollar_volume"] = liquidity[ticker]["median_dollar_volume"]
            signal["coverage_fraction"] = liquidity[ticker]["coverage_fraction"]
            candidates.append(signal)

    candidates = sorted(candidates, key=lambda r: (r["date"], -r["shadow_score"], r["ticker"]))
    same_day_overlap = [row for row in candidates if row["same_day_ab_overlap"]]
    ticker_history_overlap = [row for row in candidates if row["ticker_in_prior_ab_trades_or_signals"]]
    outside_prod = [row for row in candidates if not row["in_production_universe"]]
    by_sector = Counter(row["sector"] for row in candidates)

    return {
        "window": name,
        "start": start,
        "end": end,
        "snapshot": cfg["snapshot"],
        "snapshot_ticker_count": len(frames),
        "snapshot_metadata_ticker_count": metadata.get("ticker_count"),
        "expected_trading_days": expected_days,
        "liquid_shadow_universe_count": len(liquid_tickers),
        "selection_rejections": dict(sorted(rejections.items())),
        "candidate_count": len(candidates),
        "candidate_unique_tickers": len({row["ticker"] for row in candidates}),
        "candidate_tickers": sorted({row["ticker"] for row in candidates}),
        "candidate_count_by_sector": dict(sorted(by_sector.items())),
        "candidate_median_dollar_volume": _safe_median([row["median_dollar_volume"] for row in candidates]),
        "same_day_ab_overlap_count": len(same_day_overlap),
        "same_day_ab_overlap_rate": round(len(same_day_overlap) / len(candidates), 4) if candidates else None,
        "ticker_history_ab_overlap_count": len(ticker_history_overlap),
        "ticker_history_ab_overlap_rate": round(len(ticker_history_overlap) / len(candidates), 4) if candidates else None,
        "outside_production_candidate_count": len(outside_prod),
        "outside_production_unique_tickers": sorted({row["ticker"] for row in outside_prod}),
        "forward_return_distribution": _summarize_returns(candidates),
        "non_same_day_overlap_forward_return_distribution": _summarize_returns(
            [row for row in candidates if not row["same_day_ab_overlap"]]
        ),
        "scarce_slot_proxy": _scarce_slot_proxy(candidates, ab_active_days),
        "top_candidate_tickers": Counter(row["ticker"] for row in candidates).most_common(12),
        "sample_candidates": candidates[:40],
    }


def _weighted_forward(windows: list[dict]) -> dict:
    out = {}
    for horizon in FORWARD_HORIZONS:
        key = f"fwd_{horizon}d"
        count = sum(w["forward_return_distribution"][key]["count"] or 0 for w in windows)
        avg_num = 0.0
        win_num = 0.0
        for window in windows:
            stats = window["forward_return_distribution"][key]
            n = stats["count"] or 0
            if n and stats["avg"] is not None:
                avg_num += n * stats["avg"]
            if n and stats["win_rate"] is not None:
                win_num += n * stats["win_rate"]
        out[key] = {
            "count": count,
            "weighted_avg": round(avg_num / count, 6) if count else None,
            "weighted_win_rate": round(win_num / count, 4) if count else None,
            "note": "Weighted from per-window summary metrics; quantiles remain in window sections.",
        }
    return out


def main() -> None:
    production_universe = _production_universe()
    ab_context = _load_existing_ab_context()
    windows = [
        _audit_window(name, cfg, production_universe, ab_context)
        for name, cfg in WINDOWS.items()
    ]
    total_candidates = sum(w["candidate_count"] for w in windows)
    total_same_day_overlap = sum(w["same_day_ab_overlap_count"] for w in windows)
    total_outside_prod = sum(w["outside_production_candidate_count"] for w in windows)

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "status": "observed_only",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hypothesis": "A narrow shadow universe can surface replayable low-overlap candidates with useful forward returns without adding production tickers.",
        "lane": "universe_scout",
        "change_type": "universe_expansion",
        "single_causal_variable": "narrow shadow universe definition",
        "alpha_hypothesis": {
            "category": "universe_scout",
            "statement": "A fresh 63-day high after a long base may identify delayed institutional accumulation candidates that are lower-overlap than existing A/B entries.",
            "entry_or_allocation_class": "entry universe scout",
            "why_not_production_now": "This is a shadow source audit only; it does not include external constituent history or slot-aware production replay.",
        },
        "shadow_universe_definition": {
            "name": "liquid 63-day base-breakout shadow universe",
            "source": "fixed OHLCV snapshots only; no production universe promotion",
            "liquidity_filters": {
                "min_coverage_fraction": MIN_COVERAGE_FRACTION,
                "min_median_dollar_volume": MIN_MEDIAN_DOLLAR_VOLUME,
                "min_close": MIN_CLOSE,
                "excluded_tickers": sorted(EXCLUDED_TICKERS),
            },
            "candidate_trigger": {
                "fresh_close_above_prior_63d_high": True,
                "min_trading_days_without_prior_63d_high": MIN_BASE_DAYS_WITHOUT_HIGH,
                "max_20d_return_before_breakout": MAX_20D_RETURN_BEFORE_BREAKOUT,
                "volume_ratio_gte": MIN_VOLUME_RATIO,
                "close_location_gte": MIN_CLOSE_LOCATION,
            },
            "forward_return_horizons_trading_days": FORWARD_HORIZONS,
        },
        "bias_risks": [
            "Fixed OHLCV snapshots contain only repository tickers, so true outside-production discovery is structurally capped.",
            "Snapshot membership is survivorship-biased and not a historical constituent universe.",
            "Forward returns are candidate marks, not fills, sizing, stops, news vetos, or scarce-slot portfolio simulation.",
            "This intentionally avoids archived-news/event data because prior event scouts were coverage-limited.",
        ],
        "production_promotion": False,
        "promotion_blockers": [
            "No production ticker add was allowed or attempted.",
            "Outside-production candidate count is structurally limited by current snapshots.",
            "Promotion would require a separate external universe source and Gate 4 slot-aware replay.",
        ],
        "ab_context": {
            "ab_touchpoint_count": len(ab_context[0]),
            "ab_ticker_count": len(ab_context[1]),
            "ab_active_day_count": len(ab_context[3]),
            "ab_by_ticker_top10": dict(ab_context[2].most_common(10)),
        },
        "aggregate": {
            "candidate_count": total_candidates,
            "unique_tickers": sorted({ticker for window in windows for ticker in window["candidate_tickers"]}),
            "same_day_ab_overlap_rate_weighted": round(total_same_day_overlap / total_candidates, 4) if total_candidates else None,
            "outside_production_candidate_count": total_outside_prod,
            "sample_based_forward_returns": _weighted_forward(windows),
        },
        "windows": windows,
        "decision": {
            "status": "observed_only",
            "promotion_ready": False,
            "reason": "Shadow audit only; promotion needs nonzero external/outside-production coverage and stable multi-window forward quality.",
            "what_not_to_repeat": "Do not rerun archived-news event scouts on the same sparse news archive, and do not promote OHLCV base-breakout candidates without an external survivorship-aware universe source.",
        },
    }

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)
        f.write("\n")

    print(json.dumps({
        "artifact": OUT_JSON,
        "candidate_count": total_candidates,
        "same_day_ab_overlap_rate_weighted": artifact["aggregate"]["same_day_ab_overlap_rate_weighted"],
        "outside_production_candidate_count": total_outside_prod,
        "weighted_forward_returns": artifact["aggregate"]["sample_based_forward_returns"],
        "decision": artifact["decision"],
    }, indent=2))


if __name__ == "__main__":
    main()
