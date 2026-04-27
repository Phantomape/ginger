"""exp-20260427-013 gap-down recovery universe scout.

Observed-only shadow evaluation. This does not change the production universe,
signal engine, risk engine, portfolio engine, or backtester.
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


EXPERIMENT_ID = "exp-20260427-013"
OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "experiments",
    EXPERIMENT_ID,
    "exp_20260427_013_liquidity_qualified_gap_down_recovery_shadow_candidate_definition.json",
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

ETF_OR_MACRO_PROXIES = {
    "GLD", "IAU", "IEF", "IWM", "QQQ", "SLV", "SPY", "TLT",
    "UUP", "USO", "XLE", "XLP", "XLU", "XLV",
}

MIN_COVERAGE_FRACTION = 0.95
MIN_MEDIAN_DOLLAR_VOLUME = 25_000_000
MIN_CLOSE = 5.0
MIN_GAP_DOWN_PCT = -0.015
MIN_INTRADAY_RECOVERY_PCT = 0.012
MIN_CLOSE_LOCATION = 0.65
MIN_VOLUME_RATIO = 1.15
MAX_CLOSE_VS_PREV_CLOSE_PCT = 0.015
MIN_ABS_GAP_PCT_FOR_SCORE = 0.015
SCARCE_SLOT_COUNT = 5
FORWARD_HORIZONS = [1, 5, 10, 20]


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


def _expected_days(frames: dict[str, pd.DataFrame], start: str, end: str) -> int:
    spy = frames.get("SPY")
    if spy is not None:
        return int(len(spy.loc[pd.Timestamp(start):pd.Timestamp(end)]))
    return max(
        [len(df.loc[pd.Timestamp(start):pd.Timestamp(end)]) for df in frames.values()],
        default=0,
    )


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


def _date_key_from_path(path: str) -> str | None:
    stem = os.path.basename(path).split(".")[0]
    raw = stem.split("_")[-1]
    if len(raw) != 8 or not raw.isdigit():
        return None
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"


def _load_existing_ab_touchpoints() -> tuple[set[tuple[str, str]], set[str], Counter, Counter]:
    touchpoints: set[tuple[str, str]] = set()
    tickers: set[str] = set()
    by_ticker: Counter = Counter()
    by_date: Counter = Counter()
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
                date_key = str(entry_date)[:10]
                touchpoints.add((ticker, date_key))
                tickers.add(ticker)
                by_ticker[ticker] += 1
                by_date[date_key] += 1

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
                by_date[date_key] += 1
    return touchpoints, tickers, by_ticker, by_date


def _ticker_stats(ticker: str, df: pd.DataFrame, start: str, end: str, expected_days: int) -> dict:
    window = df.loc[pd.Timestamp(start):pd.Timestamp(end)]
    if window.empty:
        return {
            "ticker": ticker,
            "coverage_days": 0,
            "coverage_fraction": 0.0,
            "median_dollar_volume": None,
            "median_close": None,
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
    }


def _liquidity_eligible(stats: dict) -> bool:
    return (
        stats["coverage_fraction"] >= MIN_COVERAGE_FRACTION
        and (stats.get("median_dollar_volume") or 0.0) >= MIN_MEDIAN_DOLLAR_VOLUME
        and (stats.get("median_close") or 0.0) >= MIN_CLOSE
    )


def _forward_returns(df: pd.DataFrame, asof: pd.Timestamp) -> dict:
    hist = df.loc[:asof]
    if hist.empty:
        return {f"fwd_{horizon}d": None for horizon in FORWARD_HORIZONS}
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


def _add_features(df: pd.DataFrame, spy: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["prev_close"] = out["Close"].shift(1)
    out["volume_median_20"] = out["Volume"].rolling(20).median().shift(1)
    out["dollar_volume"] = out["Close"] * out["Volume"]
    out["gap_down_pct"] = (out["Open"] / out["prev_close"]) - 1.0
    out["intraday_recovery_pct"] = (out["Close"] / out["Open"]) - 1.0
    day_range = (out["High"] - out["Low"]).replace(0, pd.NA)
    out["close_location"] = (out["Close"] - out["Low"]) / day_range
    out["close_vs_prev_close_pct"] = (out["Close"] / out["prev_close"]) - 1.0
    out["volume_ratio"] = out["Volume"] / out["volume_median_20"]
    spy_close = spy["Close"].reindex(out.index).ffill()
    out["rs_5d_vs_spy"] = out["Close"].pct_change(5) - spy_close.pct_change(5)
    return out


def _candidate_score(row: pd.Series) -> float:
    gap_component = min(abs(float(row["gap_down_pct"])) / MIN_ABS_GAP_PCT_FOR_SCORE, 3.0)
    recovery_component = min(float(row["intraday_recovery_pct"]) / MIN_INTRADAY_RECOVERY_PCT, 3.0)
    volume_component = min(float(row["volume_ratio"]) / MIN_VOLUME_RATIO, 3.0)
    location_component = min(float(row["close_location"]) / MIN_CLOSE_LOCATION, 1.5)
    rs_component = max(min(float(row.get("rs_5d_vs_spy", 0.0)), 0.10), -0.10)
    return round(gap_component + recovery_component + volume_component + location_component + rs_component, 6)


def _find_candidates(
    ticker: str,
    df: pd.DataFrame,
    spy: pd.DataFrame,
    start: str,
    end: str,
    production_universe: set[str],
    ab_touchpoints: set[tuple[str, str]],
    ab_by_date: Counter,
) -> list[dict]:
    featured = _add_features(df, spy)
    window = featured.loc[pd.Timestamp(start):pd.Timestamp(end)]
    candidates = []
    for asof, row in window.iterrows():
        needed = [
            row.get("prev_close"),
            row.get("volume_median_20"),
            row.get("gap_down_pct"),
            row.get("intraday_recovery_pct"),
            row.get("close_location"),
            row.get("close_vs_prev_close_pct"),
            row.get("volume_ratio"),
        ]
        if any(pd.isna(v) for v in needed):
            continue
        if float(row["gap_down_pct"]) > MIN_GAP_DOWN_PCT:
            continue
        if float(row["intraday_recovery_pct"]) < MIN_INTRADAY_RECOVERY_PCT:
            continue
        if float(row["close_location"]) < MIN_CLOSE_LOCATION:
            continue
        if float(row["volume_ratio"]) < MIN_VOLUME_RATIO:
            continue
        if float(row["close_vs_prev_close_pct"]) > MAX_CLOSE_VS_PREV_CLOSE_PCT:
            continue
        date_key = asof.strftime("%Y-%m-%d")
        fwd = _forward_returns(df, asof)
        candidates.append({
            "date": date_key,
            "ticker": ticker,
            "sector": SECTOR_MAP.get(ticker, "Unknown"),
            "close": round(float(row["Close"]), 4),
            "gap_down_pct": round(float(row["gap_down_pct"]), 6),
            "intraday_recovery_pct": round(float(row["intraday_recovery_pct"]), 6),
            "close_location": round(float(row["close_location"]), 6),
            "close_vs_prev_close_pct": round(float(row["close_vs_prev_close_pct"]), 6),
            "volume_ratio": round(float(row["volume_ratio"]), 6),
            "rs_5d_vs_spy": round(float(row.get("rs_5d_vs_spy", 0.0)), 6),
            "score": _candidate_score(row),
            "in_production_universe": ticker in production_universe,
            "same_ticker_day_ab_overlap": (ticker, date_key) in ab_touchpoints,
            "same_day_ab_activity_count": int(ab_by_date[date_key]),
            **fwd,
        })
    return candidates


def _scarce_slot_summary(candidates: list[dict]) -> dict:
    by_date: dict[str, list[dict]] = {}
    for row in candidates:
        by_date.setdefault(row["date"], []).append(row)

    selected = []
    pressure_days = 0
    for rows in by_date.values():
        rows = sorted(rows, key=lambda r: r["score"], reverse=True)
        if len(rows) > SCARCE_SLOT_COUNT:
            pressure_days += 1
        selected.extend(rows[:SCARCE_SLOT_COUNT])

    all_fwd10 = [r.get("fwd_10d") for r in candidates if r.get("fwd_10d") is not None]
    selected_fwd10 = [r.get("fwd_10d") for r in selected if r.get("fwd_10d") is not None]
    all_avg = _safe_mean(all_fwd10)
    selected_avg = _safe_mean(selected_fwd10)
    return {
        "slot_count_per_day": SCARCE_SLOT_COUNT,
        "candidate_days": len(by_date),
        "slot_pressure_days": pressure_days,
        "slot_pressure_day_rate": round(pressure_days / len(by_date), 4) if by_date else None,
        "top_slot_candidate_count": len(selected),
        "top_slot_fwd_10d_avg": selected_avg,
        "all_candidate_fwd_10d_avg": all_avg,
        "scarce_slot_value_fwd_10d_avg_delta": (
            round(selected_avg - all_avg, 6)
            if selected_avg is not None and all_avg is not None
            else None
        ),
    }


def _window_summary(
    label: str,
    spec: dict,
    production_universe: set[str],
    ab_touchpoints: set[tuple[str, str]],
    ab_by_date: Counter,
) -> tuple[dict, list[dict]]:
    frames, metadata = _load_frames(spec["snapshot"])
    spy = frames.get("SPY")
    if spy is None:
        raise RuntimeError(f"{label} snapshot has no SPY frame")
    expected_days = _expected_days(frames, spec["start"], spec["end"])

    ticker_stats = []
    candidates = []
    for ticker, df in sorted(frames.items()):
        if ticker in ETF_OR_MACRO_PROXIES:
            continue
        stats = _ticker_stats(ticker, df, spec["start"], spec["end"], expected_days)
        ticker_stats.append(stats)
        if not _liquidity_eligible(stats):
            continue
        candidates.extend(
            _find_candidates(
                ticker,
                df,
                spy,
                spec["start"],
                spec["end"],
                production_universe,
                ab_touchpoints,
                ab_by_date,
            )
        )

    eligible = [s for s in ticker_stats if _liquidity_eligible(s)]
    unique_candidate_tickers = sorted({row["ticker"] for row in candidates})
    same_ticker_day_overlap = [row for row in candidates if row["same_ticker_day_ab_overlap"]]
    same_day_ab_activity = [row for row in candidates if row["same_day_ab_activity_count"] > 0]
    outside_production = [row for row in candidates if not row["in_production_universe"]]

    summary = {
        "window": label,
        "start": spec["start"],
        "end": spec["end"],
        "snapshot": spec["snapshot"],
        "snapshot_ticker_count": len(frames),
        "snapshot_metadata_ticker_count": len(metadata.get("tickers") or []),
        "expected_trading_days": expected_days,
        "evaluated_equity_tickers": len(ticker_stats),
        "liquidity_eligible_tickers": len(eligible),
        "avg_coverage_fraction": _safe_mean([s["coverage_fraction"] for s in ticker_stats]),
        "min_coverage_fraction": min([s["coverage_fraction"] for s in ticker_stats], default=None),
        "median_eligible_dollar_volume": _safe_median([s["median_dollar_volume"] for s in eligible]),
        "candidate_count": len(candidates),
        "unique_candidate_tickers": len(unique_candidate_tickers),
        "outside_production_candidate_count": len(outside_production),
        "outside_production_candidate_rate": (
            round(len(outside_production) / len(candidates), 4) if candidates else None
        ),
        "same_ticker_day_ab_overlap_count": len(same_ticker_day_overlap),
        "same_ticker_day_ab_overlap_rate": (
            round(len(same_ticker_day_overlap) / len(candidates), 4) if candidates else None
        ),
        "same_day_ab_activity_count": len(same_day_ab_activity),
        "same_day_ab_activity_rate": (
            round(len(same_day_ab_activity) / len(candidates), 4) if candidates else None
        ),
        "forward_returns": _summarize_returns(candidates),
        "scarce_slot_proxy": _scarce_slot_summary(candidates),
        "top_candidate_examples": sorted(candidates, key=lambda r: r["score"], reverse=True)[:15],
        "candidate_tickers": unique_candidate_tickers,
        "sector_counts": dict(Counter(row["sector"] for row in candidates).most_common()),
    }
    return summary, candidates


def main() -> int:
    production_universe = _production_universe()
    ab_touchpoints, ab_tickers, ab_by_ticker, ab_by_date = _load_existing_ab_touchpoints()
    summaries = OrderedDict()
    all_candidates = []
    for label, spec in WINDOWS.items():
        summary, candidates = _window_summary(
            label,
            spec,
            production_universe,
            ab_touchpoints,
            ab_by_date,
        )
        summaries[label] = summary
        all_candidates.extend({**row, "window": label} for row in candidates)

    aggregate_returns = _summarize_returns(all_candidates)
    aggregate = {
        "candidate_count": len(all_candidates),
        "unique_candidate_tickers": len({row["ticker"] for row in all_candidates}),
        "outside_production_candidate_count": len([
            row for row in all_candidates if not row["in_production_universe"]
        ]),
        "same_ticker_day_ab_overlap_rate": (
            round(
                len([row for row in all_candidates if row["same_ticker_day_ab_overlap"]])
                / len(all_candidates),
                4,
            )
            if all_candidates else None
        ),
        "same_day_ab_activity_rate": (
            round(
                len([row for row in all_candidates if row["same_day_ab_activity_count"] > 0])
                / len(all_candidates),
                4,
            )
            if all_candidates else None
        ),
        "forward_returns": aggregate_returns,
        "scarce_slot_proxy": _scarce_slot_summary(all_candidates),
    }

    promotion_gate = {
        "passes": False,
        "required": [
            "positive 10d average return in all three fixed windows",
            "10d win rate >= 50% in at least two windows",
            "outside-production candidates must be evaluable, or explicitly disclose snapshot limitation",
            "same-ticker-day A/B overlap low enough to be non-duplicative",
            "separate production-path replay before adding any ticker or source",
        ],
        "observed": {
            label: {
                "candidate_count": summary["candidate_count"],
                "fwd_10d_avg": summary["forward_returns"]["fwd_10d"]["avg"],
                "fwd_10d_win_rate": summary["forward_returns"]["fwd_10d"]["win_rate"],
                "outside_production_candidate_count": summary["outside_production_candidate_count"],
                "same_ticker_day_ab_overlap_rate": summary["same_ticker_day_ab_overlap_rate"],
            }
            for label, summary in summaries.items()
        },
        "reason": "Shadow scout only; production promotion requires a separate replay ticket even if source quality is promising.",
    }

    output = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "lane": "universe_scout",
        "change_type": "universe_candidate_source_shadow",
        "single_causal_variable": "liquidity-qualified gap-down recovery shadow candidate definition",
        "parameters": {
            "min_coverage_fraction": MIN_COVERAGE_FRACTION,
            "min_median_dollar_volume": MIN_MEDIAN_DOLLAR_VOLUME,
            "min_close": MIN_CLOSE,
            "min_gap_down_pct": MIN_GAP_DOWN_PCT,
            "min_intraday_recovery_pct": MIN_INTRADAY_RECOVERY_PCT,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio": MIN_VOLUME_RATIO,
            "max_close_vs_prev_close_pct": MAX_CLOSE_VS_PREV_CLOSE_PCT,
            "forward_horizons": FORWARD_HORIZONS,
            "scarce_slot_count": SCARCE_SLOT_COUNT,
        },
        "ab_context": {
            "ab_touchpoint_count": len(ab_touchpoints),
            "ab_ticker_count": len(ab_tickers),
            "ab_by_ticker_top10": dict(ab_by_ticker.most_common(10)),
        },
        "windows": summaries,
        "aggregate": aggregate,
        "promotion_gate": promotion_gate,
        "bias_risks": [
            "Fixed OHLCV snapshots include only archived tickers, so outside-production universe quality cannot be fully measured here.",
            "Ticker set is survivorship-biased to symbols preserved in local snapshots.",
            "No news or LLM event semantics are replayed; gap-down recovery is only a price/volume proxy for event sensitivity.",
            "Forward returns are candidate-level marks, not portfolio fills, sizing, stops, or scarce-slot execution.",
        ],
    }

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, sort_keys=True)

    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "artifact": OUT_JSON,
        "aggregate_candidate_count": aggregate["candidate_count"],
        "aggregate_fwd10_avg": aggregate["forward_returns"]["fwd_10d"]["avg"],
        "aggregate_fwd10_win_rate": aggregate["forward_returns"]["fwd_10d"]["win_rate"],
        "promotion_justified": promotion_gate["passes"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
