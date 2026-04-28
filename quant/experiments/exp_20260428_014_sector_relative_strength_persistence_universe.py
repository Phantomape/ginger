"""exp-20260428-014 sector relative-strength persistence universe scout.

Observed-only shadow evaluation. This script does not change production
universe membership or shared strategy code.
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


EXPERIMENT_ID = "exp-20260428-014"
OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "experiments",
    EXPERIMENT_ID,
    "exp_20260428_014_sector_relative_strength_persistence_universe.json",
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

EXCLUDED_TICKERS = {
    "GLD", "IAU", "IEF", "IWM", "QQQ", "SLV", "SPY", "TLT",
    "UUP", "USO", "XLE", "XLP", "XLU", "XLV",
}
FORWARD_HORIZONS = [1, 5, 10, 20]

MIN_COVERAGE_FRACTION = 0.95
MIN_MEDIAN_DOLLAR_VOLUME = 50_000_000
MIN_CLOSE = 8.0
MIN_SECTOR_RS_20D = 0.015
MIN_SECTOR_RS_60D = 0.025
MIN_TICKER_RS_VS_SECTOR_20D = 0.0
MIN_VOLUME_RATIO = 0.85
TOP_SECTORS_PER_DAY = 2
TOP_CANDIDATES_PER_DAY = 5


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
    active_days: set[str] = set()
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
            entry_date = str(trade.get("entry_date") or "")[:10]
            if ticker and entry_date:
                ticker = str(ticker).upper()
                touchpoints.add((ticker, entry_date))
                active_days.add(entry_date)
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
                active_days.add(date_key)
                tickers.add(ticker)
                by_ticker[ticker] += 1
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
        "ab_touchpoint_days_all_archives": int(ab_by_ticker[ticker]),
        "sector": SECTOR_MAP.get(ticker, "Unknown"),
    }


def _passes_liquidity(info: dict) -> bool:
    return (
        info["coverage_fraction"] >= MIN_COVERAGE_FRACTION
        and (info.get("median_dollar_volume") or 0.0) >= MIN_MEDIAN_DOLLAR_VOLUME
        and (info.get("median_close") or 0.0) >= MIN_CLOSE
    )


def _add_features(df: pd.DataFrame, spy: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["ret20"] = out["Close"] / out["Close"].shift(20) - 1
    out["ret60"] = out["Close"] / out["Close"].shift(60) - 1
    out["ma50"] = out["Close"].rolling(50).mean()
    out["avg_volume20"] = out["Volume"].shift(1).rolling(20).mean()
    out["volume_ratio"] = out["Volume"] / out["avg_volume20"]
    out["spy_ret20"] = spy["Close"] / spy["Close"].shift(20) - 1
    out["spy_ret60"] = spy["Close"] / spy["Close"].shift(60) - 1
    return out


def _build_sector_series(featured: dict[str, pd.DataFrame], tickers: list[str]) -> dict[str, pd.DataFrame]:
    by_sector: dict[str, list[pd.DataFrame]] = {}
    for ticker in tickers:
        sector = SECTOR_MAP.get(ticker, "Unknown")
        if sector == "Unknown":
            continue
        df = featured[ticker]
        by_sector.setdefault(sector, []).append(df[["ret20", "ret60", "spy_ret20", "spy_ret60"]])

    sector_frames = {}
    for sector, dfs in by_sector.items():
        combined = pd.concat(dfs, keys=range(len(dfs)), names=["component", "Date"])
        grouped = combined.groupby(level="Date").mean(numeric_only=True)
        grouped["sector_rs20"] = grouped["ret20"] - grouped["spy_ret20"]
        grouped["sector_rs60"] = grouped["ret60"] - grouped["spy_ret60"]
        sector_frames[sector] = grouped
    return sector_frames


def _forward_returns(df: pd.DataFrame, date_key: str) -> dict:
    asof = pd.Timestamp(date_key)
    if asof not in df.index:
        hist = df.loc[:asof]
        if hist.empty:
            return {f"fwd_{h}d": None for h in FORWARD_HORIZONS}
        asof = hist.index[-1]
    idx = df.index.get_loc(asof)
    out = {}
    entry = float(df.iloc[idx]["Close"])
    for horizon in FORWARD_HORIZONS:
        fwd_idx = idx + horizon
        if fwd_idx >= len(df):
            out[f"fwd_{horizon}d"] = None
            continue
        out[f"fwd_{horizon}d"] = round(float(df.iloc[fwd_idx]["Close"]) / entry - 1, 6)
    return out


def _candidate_signal(
    ticker: str,
    row: pd.Series,
    sector_row: pd.Series,
) -> dict | None:
    required = [
        row.get("ret20"),
        row.get("ret60"),
        row.get("ma50"),
        row.get("volume_ratio"),
        sector_row.get("sector_rs20"),
        sector_row.get("sector_rs60"),
    ]
    if any(value is None or pd.isna(value) for value in required):
        return None

    sector_rs20 = float(sector_row["sector_rs20"])
    sector_rs60 = float(sector_row["sector_rs60"])
    ticker_vs_sector20 = float(row["ret20"]) - float(sector_row["ret20"])
    above_ma50 = float(row["Close"]) > float(row["ma50"])
    liquid_day = float(row["volume_ratio"]) >= MIN_VOLUME_RATIO
    if not (
        sector_rs20 >= MIN_SECTOR_RS_20D
        and sector_rs60 >= MIN_SECTOR_RS_60D
        and ticker_vs_sector20 >= MIN_TICKER_RS_VS_SECTOR_20D
        and above_ma50
        and liquid_day
    ):
        return None

    score = (
        1.0
        + min(sector_rs20, 0.15) * 3.0
        + min(sector_rs60, 0.25) * 2.0
        + min(ticker_vs_sector20, 0.20) * 2.0
        + min(float(row["volume_ratio"]) - MIN_VOLUME_RATIO, 2.0) * 0.05
    )
    return {
        "ticker": ticker,
        "date": row.name.strftime("%Y-%m-%d"),
        "shadow_score": round(score, 4),
        "sector": SECTOR_MAP.get(ticker, "Unknown"),
        "close": round(float(row["Close"]), 4),
        "conditions": {
            "sector_rs20": round(sector_rs20, 6),
            "sector_rs60": round(sector_rs60, 6),
            "sector_ret20": round(float(sector_row["ret20"]), 6),
            "sector_ret60": round(float(sector_row["ret60"]), 6),
            "ticker_ret20": round(float(row["ret20"]), 6),
            "ticker_ret60": round(float(row["ret60"]), 6),
            "ticker_vs_sector20": round(ticker_vs_sector20, 6),
            "spy_ret20": round(float(row["spy_ret20"]), 6),
            "spy_ret60": round(float(row["spy_ret60"]), 6),
            "volume_ratio": round(float(row["volume_ratio"]), 4),
            "above_ma50": bool(above_ma50),
        },
    }


def _scarce_slot_proxy(rows: list[dict], ab_active_days: set[str]) -> dict:
    by_day: OrderedDict[str, list[dict]] = OrderedDict()
    for row in sorted(rows, key=lambda r: (r["date"], -r["shadow_score"])):
        by_day.setdefault(row["date"], []).append(row)
    top_rows = []
    for day_rows in by_day.values():
        top_rows.extend(day_rows[:TOP_CANDIDATES_PER_DAY])
    ab_days = {day for day in by_day if day in ab_active_days}
    return {
        "candidate_days": len(by_day),
        "ab_active_day_count": len(ab_days),
        "ab_active_day_rate": round(len(ab_days) / len(by_day), 4) if by_day else None,
        "top_per_day_candidate_count": len(top_rows),
        "top_per_day_limit": TOP_CANDIDATES_PER_DAY,
        "top_per_day_forward_returns": _summarize_returns(top_rows),
        "all_candidate_forward_returns": _summarize_returns(rows),
        "scarce_slot_quality_note": "Top-per-day forward returns are only a scarce-slot proxy; no fills, sizing, stops, or slot-aware replay ran.",
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

    featured = {ticker: _add_features(frames[ticker], spy) for ticker in liquid_tickers}
    sector_frames = _build_sector_series(featured, liquid_tickers)

    candidates = []
    for date in spy.loc[pd.Timestamp(start):pd.Timestamp(end)].index:
        sector_scores = []
        for sector, sector_df in sector_frames.items():
            if date not in sector_df.index:
                continue
            sector_row = sector_df.loc[date]
            if pd.isna(sector_row.get("sector_rs20")) or pd.isna(sector_row.get("sector_rs60")):
                continue
            if (
                float(sector_row["sector_rs20"]) >= MIN_SECTOR_RS_20D
                and float(sector_row["sector_rs60"]) >= MIN_SECTOR_RS_60D
            ):
                sector_scores.append((sector, float(sector_row["sector_rs20"]) + float(sector_row["sector_rs60"])))
        allowed_sectors = {
            sector for sector, _ in sorted(sector_scores, key=lambda item: item[1], reverse=True)[:TOP_SECTORS_PER_DAY]
        }
        if not allowed_sectors:
            continue

        for ticker in liquid_tickers:
            sector = SECTOR_MAP.get(ticker, "Unknown")
            if sector not in allowed_sectors:
                continue
            df = featured[ticker]
            if date not in df.index or sector not in sector_frames or date not in sector_frames[sector].index:
                continue
            signal = _candidate_signal(ticker, df.loc[date], sector_frames[sector].loc[date])
            if not signal:
                continue
            signal.update(_forward_returns(frames[ticker], signal["date"]))
            same_day_overlap = (ticker, signal["date"]) in ab_touchpoints
            signal["same_day_ab_overlap"] = bool(same_day_overlap)
            signal["ticker_in_prior_ab_trades_or_signals"] = bool(ticker in ab_tickers)
            signal["in_production_universe"] = bool(ticker in production_universe)
            signal["median_dollar_volume"] = liquidity[ticker]["median_dollar_volume"]
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
        "selection_rejections": dict(rejections),
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
        "sample_candidates": candidates[:20],
    }


def _weighted_forward(windows: list[dict]) -> dict:
    out = {}
    for horizon in FORWARD_HORIZONS:
        key = f"fwd_{horizon}d"
        values = []
        for window in windows:
            values.extend(
                row.get(key)
                for row in window.get("sample_candidates", [])
                if row.get(key) is not None
            )
        # sample_candidates are capped; use window summaries for averages instead.
        count = sum((w["forward_return_distribution"][key]["count"] or 0) for w in windows)
        weighted_avg_num = 0.0
        weighted_win_num = 0.0
        for w in windows:
            summary = w["forward_return_distribution"][key]
            n = summary["count"] or 0
            if n and summary["avg"] is not None:
                weighted_avg_num += n * summary["avg"]
            if n and summary["win_rate"] is not None:
                weighted_win_num += n * summary["win_rate"]
        out[key] = {
            "count": count,
            "weighted_avg": round(weighted_avg_num / count, 6) if count else None,
            "weighted_win_rate": round(weighted_win_num / count, 4) if count else None,
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
    all_tickers = sorted({ticker for window in windows for ticker in window["candidate_tickers"]})
    total_candidates = sum(window["candidate_count"] for window in windows)
    total_overlap = sum(window["same_day_ab_overlap_count"] for window in windows)
    outside_prod = sum(window["outside_production_candidate_count"] for window in windows)

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "status": "observed_only",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hypothesis": "A sector-relative-strength persistence shadow universe can identify replayable low-overlap candidates whose 10-20 day forward returns justify a future external universe source, without adding tickers to production.",
        "lane": "universe_scout",
        "change_type": "universe_expansion",
        "single_causal_variable": "sector relative strength persistence shadow universe",
        "alpha_hypothesis": {
            "category": "universe_scout",
            "statement": "Persistent sector-level relative strength can provide context that pure ticker OHLCV scouts lacked, potentially surfacing candidates where leadership breadth supports continuation.",
            "why_not_production_now": "This is a shadow source audit only. Snapshot membership caps outside-production discovery and there is no slot-aware portfolio replay.",
        },
        "shadow_universe_definition": {
            "source": "fixed OHLCV snapshots plus SECTOR_MAP; no production universe promotion",
            "single_causal_variable": "sector relative strength persistence",
            "liquidity_filters": {
                "min_coverage_fraction": MIN_COVERAGE_FRACTION,
                "min_median_dollar_volume": MIN_MEDIAN_DOLLAR_VOLUME,
                "min_close": MIN_CLOSE,
                "excluded_tickers": sorted(EXCLUDED_TICKERS),
            },
            "sector_persistence_trigger": {
                "top_sectors_per_day": TOP_SECTORS_PER_DAY,
                "sector_equal_weight_20d_return_minus_spy_gte": MIN_SECTOR_RS_20D,
                "sector_equal_weight_60d_return_minus_spy_gte": MIN_SECTOR_RS_60D,
                "ticker_20d_return_minus_sector_20d_gte": MIN_TICKER_RS_VS_SECTOR_20D,
                "close_above_50d_ma": True,
                "volume_ratio_gte": MIN_VOLUME_RATIO,
            },
            "forward_return_horizons_trading_days": FORWARD_HORIZONS,
        },
        "bias_risks": [
            "Fixed OHLCV snapshots contain only archived repository tickers, so outside-production discovery is structurally capped.",
            "Sector labels are static and may not reflect historical business mix changes.",
            "Forward returns are candidate-level marks, not fills, sizing, stops, or scarce-slot portfolio simulation.",
            "This is a context-based shadow universe, not a swept entry threshold or production ranking rule.",
        ],
        "production_promotion": False,
        "promotion_blockers": [
            "No production universe write was allowed or attempted.",
            "Outside-production candidate count is limited by existing fixed snapshots.",
            "Promotion would require an external historical constituent source and Gate 4 slot-aware replay.",
        ],
        "ab_context": {
            "ab_touchpoint_count": len(ab_context[0]),
            "ab_ticker_count": len(ab_context[1]),
            "ab_active_day_count": len(ab_context[3]),
            "ab_by_ticker_top10": dict(ab_context[2].most_common(10)),
        },
        "aggregate": {
            "candidate_count": total_candidates,
            "unique_tickers": all_tickers,
            "same_day_ab_overlap_rate_weighted": round(total_overlap / total_candidates, 4) if total_candidates else None,
            "outside_production_candidate_count": outside_prod,
            "sample_based_forward_returns": _weighted_forward(windows),
        },
        "windows": windows,
        "decision": {
            "status": "observed_only",
            "promotion_ready": False,
            "reason": "Shadow audit only; production promotion is blocked unless multi-window forward returns are stable and an external universe source expands beyond current snapshot membership.",
            "next_retry_rule": "Retry only with a survivorship-aware external universe/sector constituent source or if this same sector-persistence mechanism shows positive 10d and 20d forward returns in all fixed windows with nonzero outside-production candidates.",
        },
    }

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2, sort_keys=False)
        f.write("\n")
    print(json.dumps({
        "artifact": OUT_JSON,
        "candidate_count": total_candidates,
        "same_day_ab_overlap_rate_weighted": artifact["aggregate"]["same_day_ab_overlap_rate_weighted"],
        "outside_production_candidate_count": outside_prod,
        "decision": artifact["decision"],
    }, indent=2))


if __name__ == "__main__":
    main()
