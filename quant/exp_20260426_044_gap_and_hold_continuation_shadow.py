"""exp-20260426-044 gap-and-hold continuation shadow audit.

Observed-only alpha discovery. This script does not modify production strategy
logic. With daily OHLCV only, "gap and hold" is defined as an upside gap that
does not fade intraday and closes near the day's high with positive relative
strength versus SPY.
"""

from __future__ import annotations

import json
import math
import os
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from statistics import mean, median


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine  # noqa: E402
from convergence import compute_expected_value_score  # noqa: E402
from data_layer import get_universe  # noqa: E402
from risk_engine import SECTOR_MAP  # noqa: E402


EXPERIMENT_ID = "exp-20260426-044"
OUT_JSON = os.path.join(
    REPO_ROOT,
    "docs",
    "experiments",
    "artifacts",
    "exp_20260426_044_gap_and_hold_continuation_shadow.json",
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

BASE_CONFIG = {"REGIME_AWARE_EXIT": True}
FORWARD_DAYS = (5, 10, 20)
MIN_GAP_UP = 0.015
MIN_CLOSE_VS_PREV_CLOSE = 0.02
MIN_CLOSE_LOCATION = 0.7
MIN_RS_VS_SPY = 0.0
MIN_DOLLAR_VOLUME = 25_000_000
EXCLUDED_TICKERS = {
    "GLD", "IAU", "IEF", "IWM", "QQQ", "SLV", "SPY", "TLT",
    "UUP", "USO", "XLE", "XLP", "XLU", "XLV",
}


def _load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_snapshot(snapshot_path: str) -> dict[str, list[dict]]:
    payload = _load_json(os.path.join(REPO_ROOT, snapshot_path))
    return payload.get("ohlcv", payload)


def _date(row: dict) -> str:
    return str(row.get("Date") or row.get("date"))[:10]


def _value(row: dict, key: str) -> float | None:
    value = row.get(key)
    if isinstance(value, (int, float)) and not math.isnan(float(value)):
        return float(value)
    return None


def _series(snapshot: dict[str, list[dict]], ticker: str) -> list[dict]:
    return sorted(snapshot.get(ticker) or [], key=_date)


def _row_index(rows: list[dict]) -> dict[str, int]:
    return {_date(row): idx for idx, row in enumerate(rows)}


def _return_from_closes(rows: list[dict], start_idx: int, end_idx: int) -> float | None:
    if start_idx < 0 or end_idx >= len(rows):
        return None
    start_close = _value(rows[start_idx], "Close")
    end_close = _value(rows[end_idx], "Close")
    if not start_close or end_close is None:
        return None
    return (end_close / start_close) - 1.0


def _forward_return(rows: list[dict], start_idx: int, horizon: int) -> float | None:
    return _return_from_closes(rows, start_idx, start_idx + horizon)


def _summarize(values: list[float]) -> dict:
    if not values:
        return {
            "count": 0,
            "avg": None,
            "median": None,
            "win_rate": None,
            "p25": None,
            "p75": None,
        }
    ordered = sorted(values)
    return {
        "count": len(values),
        "avg": round(mean(values), 6),
        "median": round(median(values), 6),
        "win_rate": round(sum(1 for value in values if value > 0) / len(values), 4),
        "p25": round(ordered[int((len(ordered) - 1) * 0.25)], 6),
        "p75": round(ordered[int((len(ordered) - 1) * 0.75)], 6),
    }


def _run_baseline(universe: list[str], cfg: dict) -> dict:
    engine = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config=BASE_CONFIG,
        replay_llm=False,
        replay_news=False,
        data_dir=os.path.join(REPO_ROOT, "data"),
        ohlcv_snapshot_path=os.path.join(REPO_ROOT, cfg["snapshot"]),
    )
    result = engine.run()
    result["expected_value_score"] = compute_expected_value_score(result)
    return result


def _metrics(result: dict) -> dict:
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": result.get("benchmarks", {}).get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "trade_count": result.get("total_trades"),
        "win_rate": result.get("win_rate"),
    }


def _baseline_entries(result: dict) -> dict[str, list[dict]]:
    by_date = defaultdict(list)
    for trade in result.get("trades", []):
        if trade.get("strategy") in {"trend_long", "breakout_long"}:
            by_date[str(trade.get("entry_date"))[:10]].append(trade)
    return by_date


def _trading_dates(snapshot: dict[str, list[dict]]) -> list[str]:
    return [_date(row) for row in _series(snapshot, "SPY")]


def _candidate_rows(snapshot: dict[str, list[dict]], ticker: str, dates: list[str]) -> list[dict]:
    rows = _series(snapshot, ticker)
    if len(rows) < 25:
        return []
    idx_by_date = _row_index(rows)
    spy_rows = _series(snapshot, "SPY")
    spy_idx_by_date = _row_index(spy_rows)
    out = []
    for date in dates:
        idx = idx_by_date.get(date)
        spy_idx = spy_idx_by_date.get(date)
        if idx is None or spy_idx is None or idx < 1 or spy_idx < 1:
            continue
        prev = rows[idx - 1]
        cur = rows[idx]
        prev_close = _value(prev, "Close")
        cur_open = _value(cur, "Open")
        cur_high = _value(cur, "High")
        cur_low = _value(cur, "Low")
        cur_close = _value(cur, "Close")
        cur_volume = _value(cur, "Volume")
        if None in (prev_close, cur_open, cur_high, cur_low, cur_close, cur_volume):
            continue
        if not prev_close or cur_high <= cur_low:
            continue
        ticker_ret = _return_from_closes(rows, idx - 1, idx)
        spy_ret = _return_from_closes(spy_rows, spy_idx - 1, spy_idx)
        if ticker_ret is None or spy_ret is None:
            continue
        dollar_volume = cur_close * cur_volume
        gap_up = (cur_open / prev_close) - 1.0
        close_vs_prev_close = (cur_close / prev_close) - 1.0
        close_location = (cur_close - cur_low) / (cur_high - cur_low)
        rs_vs_spy = ticker_ret - spy_ret
        if dollar_volume < MIN_DOLLAR_VOLUME:
            continue
        if gap_up < MIN_GAP_UP:
            continue
        if close_vs_prev_close < MIN_CLOSE_VS_PREV_CLOSE:
            continue
        if cur_close <= cur_open:
            continue
        if close_location < MIN_CLOSE_LOCATION:
            continue
        if rs_vs_spy <= MIN_RS_VS_SPY:
            continue
        forwards = {
            f"fwd_{horizon}d": _forward_return(rows, idx, horizon)
            for horizon in FORWARD_DAYS
        }
        out.append({
            "date": date,
            "ticker": ticker,
            "sector": SECTOR_MAP.get(ticker, "Unknown"),
            "gap_up": round(gap_up, 6),
            "close_vs_prev_close": round(close_vs_prev_close, 6),
            "close_location": round(close_location, 6),
            "ticker_day_return": round(ticker_ret, 6),
            "spy_day_return": round(spy_ret, 6),
            "rs_vs_spy": round(rs_vs_spy, 6),
            "dollar_volume": round(dollar_volume, 2),
            **{
                key: round(value, 6) if isinstance(value, float) else None
                for key, value in forwards.items()
            },
        })
    return out


def _evaluate_window(label: str, cfg: dict, universe: list[str]) -> dict:
    snapshot = _load_snapshot(cfg["snapshot"])
    baseline = _run_baseline(universe, cfg)
    entries_by_date = _baseline_entries(baseline)
    dates = [date for date in _trading_dates(snapshot) if cfg["start"] <= date <= cfg["end"]]

    candidates = []
    for ticker in sorted(set(universe).intersection(snapshot)):
        if ticker in EXCLUDED_TICKERS:
            continue
        candidates.extend(_candidate_rows(snapshot, ticker, dates))

    candidates.sort(
        key=lambda row: (
            row["date"],
            -row["rs_vs_spy"],
            -row["close_location"],
            row["ticker"],
        )
    )
    for row in candidates:
        ab_entries = entries_by_date.get(row["date"], [])
        row["same_day_ab_entry_count"] = len(ab_entries)
        row["same_day_ab_overlap"] = bool(ab_entries)
        row["same_ticker_ab_overlap"] = any(trade.get("ticker") == row["ticker"] for trade in ab_entries)

    forward_summary = {}
    for horizon in FORWARD_DAYS:
        key = f"fwd_{horizon}d"
        forward_summary[key] = _summarize([
            row[key] for row in candidates if isinstance(row.get(key), (int, float))
        ])
    non_overlap = [row for row in candidates if not row["same_day_ab_overlap"]]
    overlap = [row for row in candidates if row["same_day_ab_overlap"]]
    scarce = {
        "candidate_days": len({row["date"] for row in candidates}),
        "candidate_days_with_ab_entries": len({row["date"] for row in overlap}),
        "same_day_ab_overlap_count": len(overlap),
        "same_day_ab_overlap_rate": round(len(overlap) / len(candidates), 4) if candidates else None,
        "same_ticker_ab_overlap_count": sum(1 for row in candidates if row["same_ticker_ab_overlap"]),
        "avg_ab_entries_on_candidate_day": (
            round(mean([row["same_day_ab_entry_count"] for row in candidates]), 4)
            if candidates else None
        ),
        "candidates_on_ab_collision_days": sum(1 for row in candidates if row["same_day_ab_entry_count"] >= 2),
        "fwd_10d_non_overlap": _summarize([
            row["fwd_10d"] for row in non_overlap if isinstance(row.get("fwd_10d"), (int, float))
        ]),
        "fwd_10d_overlap": _summarize([
            row["fwd_10d"] for row in overlap if isinstance(row.get("fwd_10d"), (int, float))
        ]),
    }
    return {
        "window": label,
        "start": cfg["start"],
        "end": cfg["end"],
        "snapshot": cfg["snapshot"],
        "baseline_metrics": _metrics(baseline),
        "candidate_count": len(candidates),
        "candidate_unique_tickers": len({row["ticker"] for row in candidates}),
        "candidate_count_by_sector": dict(sorted(Counter(row["sector"] for row in candidates).items())),
        "top_candidate_tickers": Counter(row["ticker"] for row in candidates).most_common(12),
        "scarce_slot_proxy": scarce,
        "forward_return_distribution": forward_summary,
        "candidates": candidates,
        "sample_candidates": candidates[:40],
    }


def main() -> int:
    universe = get_universe()
    windows = []
    for label, cfg in WINDOWS.items():
        rec = _evaluate_window(label, cfg, universe)
        windows.append(rec)
        fwd10 = rec["forward_return_distribution"]["fwd_10d"]
        print(
            f"[{label}] candidates={rec['candidate_count']} "
            f"tickers={rec['candidate_unique_tickers']} "
            f"overlap={rec['scarce_slot_proxy']['same_day_ab_overlap_rate']} "
            f"fwd10_avg={fwd10['avg']} fwd10_wr={fwd10['win_rate']}"
        )

    aggregate_fwd10 = []
    aggregate_counts = 0
    aggregate_overlap = 0
    for window in windows:
        aggregate_counts += window["candidate_count"]
        aggregate_overlap += window["scarce_slot_proxy"]["same_day_ab_overlap_count"]
        aggregate_fwd10.extend([
            row["fwd_10d"] for row in window["candidates"]
            if isinstance(row.get("fwd_10d"), (int, float))
        ])

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "status": "observed_only",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hypothesis": (
            "A daily gap-and-hold continuation shadow entry may surface institutional "
            "repricing candidates with useful forward returns and limited same-day A/B overlap."
        ),
        "single_causal_variable": "gap-and-hold continuation shadow entry pattern",
        "shadow_entry_definition": {
            "data_granularity": "daily OHLCV; no intraday opening range assumptions",
            "filters": {
                "gap_up_min": MIN_GAP_UP,
                "close_vs_prev_close_min": MIN_CLOSE_VS_PREV_CLOSE,
                "close_must_be_above_open": True,
                "close_location_min": MIN_CLOSE_LOCATION,
                "rs_vs_spy_min": MIN_RS_VS_SPY,
                "min_candidate_day_dollar_volume": MIN_DOLLAR_VOLUME,
            },
            "forward_return_horizons_trading_days": list(FORWARD_DAYS),
        },
        "windows": windows,
        "aggregate_summary": {
            "candidate_count": aggregate_counts,
            "same_day_ab_overlap_count": aggregate_overlap,
            "same_day_ab_overlap_rate": (
                round(aggregate_overlap / aggregate_counts, 4) if aggregate_counts else None
            ),
            "aggregate_fwd10": _summarize(aggregate_fwd10),
        },
        "production_promotion": False,
        "production_promotion_reason": (
            "Shadow-only source audit. Requires stable multi-window forward returns "
            "and then real strategy replay with sizing, slot competition, and exits "
            "before any production change."
        ),
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    print(f"wrote: {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
