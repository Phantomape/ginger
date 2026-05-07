"""exp-20260507-013: core platform exit capture diagnostic.

Observed-only alpha diagnostic. The prior entry-timing replay showed that
waiting for a pullback did not fill any touched core-platform entries. This run
therefore asks whether the same cohort has an exit/capture mismatch: did the
existing path enter correctly, but realize too little of the post-entry move?

No production path, ranking, sizing, LLM/news behavior, entries, exits, or
universe membership is changed by this script.
"""

from __future__ import annotations

import json
import math
import statistics
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260507-013"
STEM = "core_platform_exit_capture_diagnostic"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "docs"
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{STEM}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
BASELINE_LOG = REPO_ROOT / "docs" / "experiments" / "logs" / "exp-20260507-006.json"

TREATMENT_POOL = ("NFLX", "APP", "META", "GOOG", "AMZN", "SPOT", "DIS")
CONTROL_POOL = ("AAPL", "MSFT", "PLTR", "DDOG", "SNOW", "NOW")
FORWARD_HORIZONS = (5, 10, 20, 40)
CAPTURE_HORIZON = 40

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
                "candidate_events": (
                    "data/experiments/exp-20260507-013/"
                    "entry_candidate_events_late_strong.json"
                ),
                "backtest_results": (
                    "data/experiments/exp-20260507-013/"
                    "backtest_results_late_strong.json"
                ),
                "state_note": "slow-melt bull / accepted-stack dominant tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "candidate_events": (
                    "data/experiments/exp-20260507-013/"
                    "entry_candidate_events_mid_weak.json"
                ),
                "backtest_results": (
                    "data/experiments/exp-20260507-013/"
                    "backtest_results_mid_weak.json"
                ),
                "state_note": "rotation-heavy bull where strategy profits but can lag indexes",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "candidate_events": (
                    "data/experiments/exp-20260507-013/"
                    "entry_candidate_events_old_thin.json"
                ),
                "backtest_results": (
                    "data/experiments/exp-20260507-013/"
                    "backtest_results_old_thin.json"
                ),
                "state_note": "mixed-to-weak older tape with lower win rate",
            },
        ),
    ]
)


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return round(value, digits)


def _float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _load_ohlcv(snapshot_path: Path) -> dict[str, list[dict[str, Any]]]:
    payload = _load_json(snapshot_path)
    ohlcv = payload.get("ohlcv")
    if not isinstance(ohlcv, dict):
        raise RuntimeError(f"Unexpected OHLCV snapshot shape: {snapshot_path}")
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in ohlcv.items():
        if not isinstance(rows, list):
            continue
        clean = [row for row in rows if isinstance(row, dict) and row.get("Date")]
        out[str(ticker).upper()] = sorted(clean, key=lambda row: str(row["Date"]))
    return out


def _load_baseline_metrics() -> dict[str, Any]:
    payload = _load_json(BASELINE_LOG)
    metrics = payload.get("baseline_metrics")
    if not isinstance(metrics, dict):
        raise RuntimeError(f"Missing baseline_metrics: {BASELINE_LOG}")
    return metrics


def _close(row: dict[str, Any]) -> float | None:
    return _float(row.get("Close"))


def _high(row: dict[str, Any]) -> float | None:
    return _float(row.get("High"))


def _low(row: dict[str, Any]) -> float | None:
    return _float(row.get("Low"))


def _date_value(row: dict[str, Any]) -> str:
    return str(row.get("Date"))[:10]


def _date_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {_date_value(row): idx for idx, row in enumerate(rows)}


def _idx_for_date(rows: list[dict[str, Any]], date_str: str | None) -> int | None:
    if not date_str:
        return None
    return _date_index(rows).get(str(date_str)[:10])


def _last_idx_on_or_before(rows: list[dict[str, Any]], date_str: str | None) -> int | None:
    if not date_str:
        return None
    target = str(date_str)[:10]
    best = None
    for idx, row in enumerate(rows):
        if _date_value(row) <= target:
            best = idx
        else:
            break
    return best


def _first_idx_on_or_after(rows: list[dict[str, Any]], date_str: str | None) -> int | None:
    if not date_str:
        return None
    target = str(date_str)[:10]
    for idx, row in enumerate(rows):
        if _date_value(row) >= target:
            return idx
    return None


def _signal_entry(event: dict[str, Any]) -> float | None:
    details = event.get("details") if isinstance(event.get("details"), dict) else {}
    snapshot = (
        event.get("signal_snapshot")
        if isinstance(event.get("signal_snapshot"), dict)
        else {}
    )
    return (
        _float(details.get("fill_price"))
        or _float(details.get("signal_entry"))
        or _float(snapshot.get("entry_price"))
    )


def _stats(values: list[float | None], digits: int = 4) -> dict[str, Any]:
    clean = [float(value) for value in values if value is not None and math.isfinite(value)]
    if not clean:
        return {
            "count": 0,
            "avg": None,
            "median": None,
            "p25": None,
            "p75": None,
            "best": None,
            "worst": None,
            "positive_rate": None,
        }
    ordered = sorted(clean)

    def pctile(pct: float) -> float:
        if len(ordered) == 1:
            return ordered[0]
        raw = (len(ordered) - 1) * pct
        lo = math.floor(raw)
        hi = math.ceil(raw)
        if lo == hi:
            return ordered[lo]
        return ordered[lo] + (ordered[hi] - ordered[lo]) * (raw - lo)

    return {
        "count": len(clean),
        "avg": _round(sum(clean) / len(clean), digits),
        "median": _round(statistics.median(clean), digits),
        "p25": _round(pctile(0.25), digits),
        "p75": _round(pctile(0.75), digits),
        "best": _round(max(clean), digits),
        "worst": _round(min(clean), digits),
        "positive_rate": _round(sum(1 for value in clean if value > 0) / len(clean), 4),
    }


def _window_slice(
    rows: list[dict[str, Any]], start_idx: int | None, horizon: int
) -> tuple[int | None, int | None]:
    if start_idx is None or start_idx >= len(rows):
        return None, None
    end_idx = min(len(rows) - 1, start_idx + horizon)
    return start_idx, end_idx


def _forward_return(
    rows: list[dict[str, Any]], start_idx: int | None, entry_price: float | None, horizon: int
) -> float | None:
    start_idx, end_idx = _window_slice(rows, start_idx, horizon)
    if start_idx is None or end_idx is None or entry_price is None or entry_price <= 0:
        return None
    close_value = _close(rows[end_idx])
    if close_value is None:
        return None
    return (close_value - entry_price) / entry_price


def _mfe_mae(
    rows: list[dict[str, Any]], start_idx: int | None, entry_price: float | None, horizon: int
) -> dict[str, Any]:
    start_idx, end_idx = _window_slice(rows, start_idx, horizon)
    if start_idx is None or end_idx is None or entry_price is None or entry_price <= 0:
        return {
            "mfe_pct": None,
            "mae_pct": None,
            "days_to_mfe": None,
            "days_to_mae": None,
            "mfe_date": None,
            "mae_date": None,
        }
    high_points: list[tuple[int, float]] = []
    low_points: list[tuple[int, float]] = []
    for idx in range(start_idx, end_idx + 1):
        high_value = _high(rows[idx])
        low_value = _low(rows[idx])
        if high_value is not None:
            high_points.append((idx, high_value))
        if low_value is not None:
            low_points.append((idx, low_value))
    if not high_points or not low_points:
        return {
            "mfe_pct": None,
            "mae_pct": None,
            "days_to_mfe": None,
            "days_to_mae": None,
            "mfe_date": None,
            "mae_date": None,
        }
    high_idx, high_value = max(high_points, key=lambda item: item[1])
    low_idx, low_value = min(low_points, key=lambda item: item[1])
    return {
        "mfe_pct": (high_value - entry_price) / entry_price,
        "mae_pct": (low_value - entry_price) / entry_price,
        "days_to_mfe": high_idx - start_idx,
        "days_to_mae": low_idx - start_idx,
        "mfe_date": _date_value(rows[high_idx]),
        "mae_date": _date_value(rows[low_idx]),
    }


def _post_exit_mfe(
    rows: list[dict[str, Any]],
    entry_idx: int | None,
    exit_idx: int | None,
    entry_price: float | None,
    horizon: int,
) -> float | None:
    if entry_idx is None or exit_idx is None or entry_price is None or entry_price <= 0:
        return None
    start = exit_idx + 1
    end = min(len(rows) - 1, entry_idx + horizon)
    if start > end:
        return None
    highs = [_high(rows[idx]) for idx in range(start, end + 1)]
    highs = [value for value in highs if value is not None]
    if not highs:
        return None
    return (max(highs) - entry_price) / entry_price


def _cohort_for_ticker(ticker: str) -> str | None:
    ticker = ticker.upper()
    if ticker in TREATMENT_POOL:
        return "treatment"
    if ticker in CONTROL_POOL:
        return "control"
    return None


def _candidate_row(event: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    ticker = str(event.get("ticker", "")).upper()
    cohort = _cohort_for_ticker(ticker)
    if cohort is None:
        return None
    entry = _signal_entry(event)
    idx = _first_idx_on_or_after(rows, event.get("date"))
    forward = {
        f"{horizon}d": _round(_forward_return(rows, idx, entry, horizon), 6)
        for horizon in FORWARD_HORIZONS
    }
    mfe20 = _mfe_mae(rows, idx, entry, 20)
    mfe40 = _mfe_mae(rows, idx, entry, 40)
    return {
        "ticker": ticker,
        "cohort": cohort,
        "strategy": event.get("strategy"),
        "date": str(event.get("date"))[:10],
        "decision": event.get("decision"),
        "candidate_rank": event.get("candidate_rank"),
        "signal_entry": _round(entry, 4),
        "forward_return": forward,
        "mfe_20d_pct": _round(mfe20.get("mfe_pct"), 6),
        "mae_20d_pct": _round(mfe20.get("mae_pct"), 6),
        "mfe_40d_pct": _round(mfe40.get("mfe_pct"), 6),
        "mae_40d_pct": _round(mfe40.get("mae_pct"), 6),
    }


def _trade_row(
    trade: dict[str, Any], rows: list[dict[str, Any]], cohort: str
) -> dict[str, Any] | None:
    ticker = str(trade.get("ticker", "")).upper()
    entry_price = _float(trade.get("entry_price"))
    entry_idx = _idx_for_date(rows, trade.get("entry_date"))
    if entry_idx is None:
        entry_idx = _first_idx_on_or_after(rows, trade.get("entry_date"))
    exit_idx = _idx_for_date(rows, trade.get("exit_date"))
    if exit_idx is None:
        exit_idx = _last_idx_on_or_before(rows, trade.get("exit_date"))
    realized = _float(trade.get("pnl_pct_net"))
    mfe20 = _mfe_mae(rows, entry_idx, entry_price, 20)
    mfe40 = _mfe_mae(rows, entry_idx, entry_price, 40)

    def capture(mfe_pct: Any) -> float | None:
        mfe_value = _float(mfe_pct)
        if mfe_value is None or mfe_value <= 0 or realized is None:
            return None
        return realized / mfe_value

    post_exit_40 = _post_exit_mfe(rows, entry_idx, exit_idx, entry_price, CAPTURE_HORIZON)
    missed_after_exit = None
    if post_exit_40 is not None and realized is not None:
        missed_after_exit = max(0.0, post_exit_40 - max(realized, 0.0))

    return {
        "ticker": ticker,
        "cohort": cohort,
        "strategy": trade.get("strategy"),
        "entry_date": trade.get("entry_date"),
        "exit_date": trade.get("exit_date"),
        "holding_trading_days": (
            exit_idx - entry_idx if entry_idx is not None and exit_idx is not None else None
        ),
        "entry_price": _round(entry_price, 4),
        "exit_price": _round(trade.get("exit_price"), 4),
        "exit_reason": trade.get("exit_reason"),
        "pnl": _round(trade.get("pnl"), 2),
        "pnl_pct_net": _round(realized, 6),
        "shares": trade.get("shares"),
        "target_mult_used": trade.get("target_mult_used"),
        "regime_exit_bucket": trade.get("regime_exit_bucket"),
        "regime_exit_score": _round(trade.get("regime_exit_score"), 6),
        "forward_return": {
            f"{horizon}d": _round(
                _forward_return(rows, entry_idx, entry_price, horizon), 6
            )
            for horizon in FORWARD_HORIZONS
        },
        "mfe_20d_pct": _round(mfe20.get("mfe_pct"), 6),
        "mae_20d_pct": _round(mfe20.get("mae_pct"), 6),
        "mfe_40d_pct": _round(mfe40.get("mfe_pct"), 6),
        "mae_40d_pct": _round(mfe40.get("mae_pct"), 6),
        "days_to_mfe_40d": mfe40.get("days_to_mfe"),
        "mfe_40d_date": mfe40.get("mfe_date"),
        "capture_20d_mfe": _round(capture(mfe20.get("mfe_pct")), 6),
        "capture_40d_mfe": _round(capture(mfe40.get("mfe_pct")), 6),
        "post_exit_mfe_40d_pct": _round(post_exit_40, 6),
        "missed_after_exit_40d_pct": _round(missed_after_exit, 6),
        "exit_before_40d_mfe": (
            exit_idx is not None
            and entry_idx is not None
            and isinstance(mfe40.get("days_to_mfe"), int)
            and exit_idx - entry_idx < int(mfe40["days_to_mfe"])
        ),
        "runner_candidate": _is_runner_candidate(realized, mfe40.get("mfe_pct")),
    }


def _is_runner_candidate(realized: float | None, mfe_pct: Any) -> bool:
    mfe_value = _float(mfe_pct)
    if realized is None or mfe_value is None:
        return False
    return mfe_value >= 0.10 and realized < mfe_value * 0.65


def _summarize_candidates(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["cohort"]].append(row)
        groups[f"ticker:{row['ticker']}"].append(row)
    for key, items in sorted(groups.items()):
        entered = [row for row in items if row.get("decision") == "entered"]
        out[key] = {
            "candidate_count": len(items),
            "entered_count": len(entered),
            "decision_counts": dict(sorted(Counter(row.get("decision") for row in items).items())),
            "strategy_counts": dict(sorted(Counter(row.get("strategy") for row in items).items())),
            "forward_returns": {
                f"{horizon}d": _stats(
                    [
                        _float((row.get("forward_return") or {}).get(f"{horizon}d"))
                        for row in items
                    ],
                    6,
                )
                for horizon in FORWARD_HORIZONS
            },
            "mfe_40d_pct": _stats([_float(row.get("mfe_40d_pct")) for row in items], 6),
            "mae_40d_pct": _stats([_float(row.get("mae_40d_pct")) for row in items], 6),
        }
    return out


def _summarize_trades(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["cohort"]].append(row)
        groups[f"ticker:{row['ticker']}"].append(row)
        groups[f"strategy:{row.get('strategy')}"].append(row)
    for key, items in sorted(groups.items()):
        wins = [row for row in items if (_float(row.get("pnl")) or 0.0) > 0]
        pnl_sum = sum(_float(row.get("pnl")) or 0.0 for row in items)
        runner_candidates = [row for row in items if row.get("runner_candidate")]
        out[key] = {
            "trade_count": len(items),
            "wins": len(wins),
            "win_rate": _round(len(wins) / len(items), 4) if items else None,
            "total_pnl": _round(pnl_sum, 2),
            "avg_pnl": _round(pnl_sum / len(items), 2) if items else None,
            "exit_reason_counts": dict(
                sorted(Counter(row.get("exit_reason") for row in items).items())
            ),
            "strategy_counts": dict(sorted(Counter(row.get("strategy") for row in items).items())),
            "pnl_pct_net": _stats([_float(row.get("pnl_pct_net")) for row in items], 6),
            "mfe_20d_pct": _stats([_float(row.get("mfe_20d_pct")) for row in items], 6),
            "mfe_40d_pct": _stats([_float(row.get("mfe_40d_pct")) for row in items], 6),
            "mae_40d_pct": _stats([_float(row.get("mae_40d_pct")) for row in items], 6),
            "capture_20d_mfe": _stats([_float(row.get("capture_20d_mfe")) for row in items], 6),
            "capture_40d_mfe": _stats([_float(row.get("capture_40d_mfe")) for row in items], 6),
            "missed_after_exit_40d_pct": _stats(
                [_float(row.get("missed_after_exit_40d_pct")) for row in items],
                6,
            ),
            "exit_before_40d_mfe_count": sum(
                1 for row in items if row.get("exit_before_40d_mfe")
            ),
            "runner_candidate_count": len(runner_candidates),
            "sample_runner_candidates": runner_candidates[:8],
        }
    return out


def _window_metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") if isinstance(result.get("benchmarks"), dict) else {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "total_return_pct": _round(benchmarks.get("strategy_total_return_pct"), 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 4),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": _round(result.get("survival_rate"), 4),
    }


def _analyze_window(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    ohlcv = _load_ohlcv(REPO_ROOT / spec["snapshot"])
    candidate_payload = _load_json(REPO_ROOT / spec["candidate_events"])
    result = _load_json(REPO_ROOT / spec["backtest_results"])
    events = candidate_payload.get("candidate_events") or []
    trades = result.get("trades") or []

    candidate_rows: list[dict[str, Any]] = []
    for event in events:
        ticker = str(event.get("ticker", "")).upper()
        ticker_rows = ohlcv.get(ticker)
        if not ticker_rows:
            continue
        row = _candidate_row(event, ticker_rows)
        if row:
            candidate_rows.append(row)

    trade_rows: list[dict[str, Any]] = []
    for trade in trades:
        ticker = str(trade.get("ticker", "")).upper()
        cohort = _cohort_for_ticker(ticker)
        ticker_rows = ohlcv.get(ticker)
        if cohort is None or not ticker_rows:
            continue
        row = _trade_row(trade, ticker_rows, cohort)
        if row:
            trade_rows.append(row)

    return {
        "window": name,
        "window_spec": spec,
        "baseline_metrics": _window_metrics(result),
        "candidate_artifact_validation": {
            "persisted_candidate_events": len(events),
            "entered_candidate_events": sum(
                1 for event in events if event.get("decision") == "entered"
            ),
            "result_total_trades": result.get("total_trades"),
            "entered_matches_result_trades": (
                sum(1 for event in events if event.get("decision") == "entered")
                == result.get("total_trades")
            ),
        },
        "candidate_summary": _summarize_candidates(candidate_rows),
        "trade_capture_summary": _summarize_trades(trade_rows),
        "trade_capture_rows": trade_rows,
    }


def _aggregate(results: dict[str, Any]) -> dict[str, Any]:
    all_trades: list[dict[str, Any]] = []
    all_candidates: list[dict[str, Any]] = []
    official = {
        "expected_value_score_sum": 0.0,
        "total_pnl_sum": 0.0,
        "trade_count_sum": 0,
    }
    for window in results.values():
        metrics = window.get("baseline_metrics") or {}
        official["expected_value_score_sum"] += _float(metrics.get("expected_value_score")) or 0.0
        official["total_pnl_sum"] += _float(metrics.get("total_pnl")) or 0.0
        official["trade_count_sum"] += int(metrics.get("trade_count") or 0)
        all_trades.extend(window.get("trade_capture_rows") or [])
        for cohort in ("treatment", "control"):
            summary = (window.get("candidate_summary") or {}).get(cohort) or {}
            all_candidates.append(
                {
                    "cohort": cohort,
                    "candidate_count": summary.get("candidate_count") or 0,
                    "entered_count": summary.get("entered_count") or 0,
                }
            )

    trade_summary = _summarize_trades(all_trades)
    treatment = trade_summary.get("treatment") or {}
    treatment_trade_count = treatment.get("trade_count") or 0
    runner_count = treatment.get("runner_candidate_count") or 0
    capture_median = (
        (treatment.get("capture_40d_mfe") or {}).get("median")
        if isinstance(treatment.get("capture_40d_mfe"), dict)
        else None
    )
    next_action = "no_runner_exit_replay_yet"
    if treatment_trade_count >= 8 and runner_count >= 3 and (
        capture_median is not None and capture_median < 0.65
    ):
        next_action = "pre_register_core_platform_runner_exit_replay"

    return {
        "official_baseline_metrics": {
            "expected_value_score_sum": _round(official["expected_value_score_sum"], 4),
            "total_pnl_sum": _round(official["total_pnl_sum"], 2),
            "trade_count_sum": official["trade_count_sum"],
        },
        "candidate_counts": {
            "treatment": {
                "candidate_count": sum(
                    row["candidate_count"] for row in all_candidates if row["cohort"] == "treatment"
                ),
                "entered_count": sum(
                    row["entered_count"] for row in all_candidates if row["cohort"] == "treatment"
                ),
            },
            "control": {
                "candidate_count": sum(
                    row["candidate_count"] for row in all_candidates if row["cohort"] == "control"
                ),
                "entered_count": sum(
                    row["entered_count"] for row in all_candidates if row["cohort"] == "control"
                ),
            },
        },
        "trade_capture_summary": trade_summary,
        "diagnostic_read": {
            "next_action": next_action,
            "reason": (
                "Runner-exit replay needs at least 8 treatment trades, at least 3 "
                "runner candidates, and median 40d MFE capture below 0.65."
            ),
            "treatment_trade_count": treatment_trade_count,
            "treatment_runner_candidate_count": runner_count,
            "treatment_capture_40d_mfe_median": capture_median,
        },
    }


def _build_log(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["generated_at"],
        "status": "observed_only",
        "decision": "shadow_only",
        "lane": "alpha_search",
        "change_type": "exit_capture_diagnostic",
        "mechanism_family": "core_platform_exit_capture",
        "alpha_hypothesis_category": "exit",
        "hypothesis": (
            "Core platform entries may not need a cheaper fill; they may need "
            "better upside capture after valid entry."
        ),
        "single_causal_variable": "core_platform_exit_capture_diagnostic",
        "date_range": {
            name: f"{spec['start']} -> {spec['end']}" for name, spec in WINDOWS.items()
        },
        "market_regime_summary": {
            name: spec["state_note"] for name, spec in WINDOWS.items()
        },
        "historical_experiment_check": {
            "exp-20260507-008": (
                "Rejected entry waiting: 0 fills across 11 touched treatment entries. "
                "This run changes the question from entry timing to exit capture."
            ),
            "exp-20260426-051": "Do not retry broad pullback-source logic.",
            "exp-20260506-019": "Do not retry pullback/RS ranking variants.",
            "exp-20260505-011_and_020": (
                "Do not promote consumer-platform universe/gate variants."
            ),
            "mechanism_insight_conflict": (
                "none; this is observed-only exit/capture attribution, not ranking, "
                "entry, or universe expansion."
            ),
        },
        "parameters": {
            "treatment_pool": list(TREATMENT_POOL),
            "control_pool": list(CONTROL_POOL),
            "forward_horizons": list(FORWARD_HORIZONS),
            "capture_horizon": CAPTURE_HORIZON,
            "locked_variables": [
                "universe",
                "signal generation",
                "entry timing",
                "entry filters",
                "candidate ranking",
                "sizing",
                "MAX_POSITIONS",
                "add-ons",
                "exits",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "baseline_metrics": payload["baseline_official_metrics"],
        "observed_metrics": {
            "aggregate": aggregate["official_baseline_metrics"],
            "candidate_counts": aggregate["candidate_counts"],
            "treatment_trade_capture": (
                aggregate["trade_capture_summary"].get("treatment") or {}
            ),
            "control_trade_capture": (
                aggregate["trade_capture_summary"].get("control") or {}
            ),
            "diagnostic_read": aggregate["diagnostic_read"],
        },
        "production_impact": payload["production_impact"],
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM/news replay remains deliberately outside this exit-capture diagnostic."
            ),
        },
        "gate4": {
            "passed": None,
            "basis": (
                "Observed-only diagnostic. No after-metrics exist until a replay "
                "exit variant is pre-registered."
            ),
        },
        "next_action": aggregate["diagnostic_read"]["next_action"],
        "next_retry_requires": [
            "Do not change exits from this diagnostic alone.",
            "A runner-exit replay needs a pre-registered shared-policy treatment and three-window Gate 4.",
            "Any promoted exit policy must be shared by run.py and backtester.py with parity tests.",
        ],
        "related_files": [
            str(OUT_JSON.relative_to(REPO_ROOT)),
            str(LOG_JSON.relative_to(REPO_ROOT)),
            str(TICKET_JSON.relative_to(REPO_ROOT)),
            str(ARTIFACT_MD.relative_to(REPO_ROOT)),
            str(EXPERIMENT_LOG.relative_to(REPO_ROOT)),
        ],
    }


def _artifact(payload: dict[str, Any], log_payload: dict[str, Any]) -> str:
    agg = payload["aggregate"]
    official = agg["official_baseline_metrics"]
    treatment = agg["trade_capture_summary"].get("treatment") or {}
    control = agg["trade_capture_summary"].get("control") or {}
    diag = agg["diagnostic_read"]

    def value(summary: dict[str, Any], key: str, stat: str = "median") -> Any:
        block = summary.get(key)
        if isinstance(block, dict):
            return block.get(stat)
        return None

    lines = [
        "# exp-20260507-009: Core Platform Exit Capture Diagnostic",
        "",
        "Decision: `shadow_only`",
        f"Next action: `{diag['next_action']}`",
        "",
        "## Official Baseline",
        "",
        "| EV sum | PnL sum | Trades |",
        "|---:|---:|---:|",
        (
            f"| {official['expected_value_score_sum']} | "
            f"{official['total_pnl_sum']} | {official['trade_count_sum']} |"
        ),
        "",
        "## Aggregate Capture",
        "",
        (
            "| Cohort | Trades | PnL | Win rate | Median capture 40d MFE | "
            "Runner candidates | Exit before 40d MFE |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|",
        (
            f"| treatment | {treatment.get('trade_count')} | {treatment.get('total_pnl')} | "
            f"{treatment.get('win_rate')} | {value(treatment, 'capture_40d_mfe')} | "
            f"{treatment.get('runner_candidate_count')} | "
            f"{treatment.get('exit_before_40d_mfe_count')} |"
        ),
        (
            f"| control | {control.get('trade_count')} | {control.get('total_pnl')} | "
            f"{control.get('win_rate')} | {value(control, 'capture_40d_mfe')} | "
            f"{control.get('runner_candidate_count')} | "
            f"{control.get('exit_before_40d_mfe_count')} |"
        ),
        "",
        "## Diagnostic Gate",
        "",
        log_payload["observed_metrics"]["diagnostic_read"]["reason"],
        "",
        "## Production Parity",
        "",
        "No production policy changed. This is observed-only attribution.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    baseline_metrics = _load_baseline_metrics()
    by_window = OrderedDict(
        (name, _analyze_window(name, spec)) for name, spec in WINDOWS.items()
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "observed_only",
        "decision": "shadow_only",
        "lane": "alpha_search",
        "change_type": "exit_capture_diagnostic",
        "single_causal_variable": "core_platform_exit_capture_diagnostic",
        "treatment_pool": list(TREATMENT_POOL),
        "control_pool": list(CONTROL_POOL),
        "windows": WINDOWS,
        "baseline_official_metrics": baseline_metrics,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": True,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
        },
        "by_window": by_window,
        "aggregate": _aggregate(by_window),
        "notes": [
            "Observed-only diagnostic; no counterfactual fills or exits are applied.",
            "Entry candidate events are post-filter entry-loop rows, not raw universe signals.",
            "MFE/MAE uses OHLCV snapshot highs/lows after the actual entry date.",
        ],
    }
    log_payload = _build_log(payload)
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": "observed_only",
        "decision": "shadow_only",
        "single_causal_variable": "core_platform_exit_capture_diagnostic",
        "next_action": payload["aggregate"]["diagnostic_read"]["next_action"],
        "artifact": str(OUT_JSON.relative_to(REPO_ROOT)),
    }

    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, log_payload)
    _write_json(TICKET_JSON, ticket)
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text(_artifact(payload, log_payload), encoding="utf-8")
    _append_jsonl(EXPERIMENT_LOG, log_payload)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": "shadow_only",
                "next_action": payload["aggregate"]["diagnostic_read"]["next_action"],
                "diagnostic_read": payload["aggregate"]["diagnostic_read"],
                "out_json": str(OUT_JSON),
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
