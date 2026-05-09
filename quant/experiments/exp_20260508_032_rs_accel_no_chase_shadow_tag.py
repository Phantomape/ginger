"""exp-20260508-032: RS acceleration / no-chase shadow tag audit.

Observed-only alpha discovery. This does not alter production strategy logic,
candidate ranking, sizing, exits, sector caps, add-ons, LLM/news, or orders.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from oracle_diagnostics import (  # noqa: E402
    _as_float,
    _entry_row_index,
    _entry_state_candidate_events,
    _period_return,
    _ticker_rows,
)


EXPERIMENT_ID = "exp-20260508-032"
STEM = "rs_accel_no_chase_shadow_tag"
CORE_STRATEGIES = {"trend_long", "breakout_long"}
NOTIONAL_USD = 10_000.0
HOLD_DAYS = 20

OUT_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / f"exp_20260508_032_{STEM}.json"
)

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

BASELINE = {
    "late_strong": {
        "expected_value_score": 3.7435,
        "sharpe_daily": 4.48,
        "max_drawdown_pct": 0.0539,
        "total_pnl": 83562.53,
        "win_rate": 0.7895,
        "total_trades": 19,
        "survival_rate": 0.8039,
    },
    "mid_weak": {
        "expected_value_score": 1.5478,
        "sharpe_daily": 2.69,
        "max_drawdown_pct": 0.0879,
        "total_pnl": 57542.74,
        "win_rate": 0.5238,
        "total_trades": 21,
        "survival_rate": 0.7925,
    },
    "old_thin": {
        "expected_value_score": 0.3359,
        "sharpe_daily": 1.28,
        "max_drawdown_pct": 0.0905,
        "total_pnl": 26242.68,
        "win_rate": 0.4091,
        "total_trades": 22,
        "survival_rate": 0.9167,
    },
}


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return round(number, digits)


def _median(values: list[float]) -> float | None:
    return round(median(values), 6) if values else None


def _positive_share_by_ticker(rows: list[dict[str, Any]]) -> float | None:
    by_ticker: defaultdict[str, float] = defaultdict(float)
    for row in rows:
        by_ticker[str(row["ticker"])] += float(row["pnl"])
    positives = [value for value in by_ticker.values() if value > 0]
    if not positives:
        return None
    return max(positives) / sum(positives)


def _stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "candidate_count": 0,
            "avg_return_pct": None,
            "median_return_pct": None,
            "total_pnl": 0.0,
            "avg_pnl": None,
            "win_rate": None,
            "decision_counts": {},
            "strategy_counts": {},
            "max_single_ticker_positive_share": None,
            "scarce_slot_rows": 0,
            "avg_vs_same_day_entered_return_pct": None,
        }
    returns = [float(row["return_pct"]) for row in rows]
    pnls = [float(row["pnl"]) for row in rows]
    slot_deltas = [
        float(row["vs_same_day_entered_return_pct"])
        for row in rows
        if row.get("vs_same_day_entered_return_pct") is not None
    ]
    return {
        "candidate_count": len(rows),
        "avg_return_pct": _round(sum(returns) / len(returns), 6),
        "median_return_pct": _median(returns),
        "total_pnl": _round(sum(pnls), 2),
        "avg_pnl": _round(sum(pnls) / len(pnls), 2),
        "win_rate": _round(sum(1 for value in pnls if value > 0) / len(pnls), 4),
        "decision_counts": dict(sorted(Counter(row["decision"] for row in rows).items())),
        "strategy_counts": dict(sorted(Counter(row["strategy"] for row in rows).items())),
        "max_single_ticker_positive_share": _round(_positive_share_by_ticker(rows), 4),
        "scarce_slot_rows": len(slot_deltas),
        "avg_vs_same_day_entered_return_pct": (
            _round(sum(slot_deltas) / len(slot_deltas), 6) if slot_deltas else None
        ),
    }


def _candidate_rows(
    backtest_result: dict[str, Any],
    snapshot: dict[str, Any],
    candidate_events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows_by_ticker = _ticker_rows(snapshot)
    spy_rows = rows_by_ticker.get("SPY")
    spy_index = {
        row.get("Date"): idx for idx, row in enumerate(spy_rows or []) if row.get("Date")
    }
    events = _entry_state_candidate_events(
        backtest_result,
        {"candidate_events": candidate_events},
    )
    out = []
    seen = set()
    for event in events:
        strategy = str(event.get("strategy") or "")
        if strategy not in CORE_STRATEGIES:
            continue
        signal_date = event["signal_date"]
        ticker = str(event["ticker"]).upper()
        key = (
            signal_date,
            ticker,
            strategy,
            event.get("candidate_rank"),
            event.get("decision"),
        )
        if key in seen:
            continue
        seen.add(key)
        rows = rows_by_ticker.get(ticker)
        signal_idx = None
        for idx, row in enumerate(rows or []):
            if row.get("Date") == signal_date:
                signal_idx = idx
                break
        entry_idx = _entry_row_index(rows or [], signal_date, event.get("details"))
        spy_idx = spy_index.get(signal_date)
        if signal_idx is None or entry_idx is None or spy_idx is None:
            continue

        stock_ret_20 = _period_return(rows, signal_idx, 20)
        stock_ret_prev_20 = _period_return(rows, signal_idx - 20, 20)
        spy_ret_20 = _period_return(spy_rows, spy_idx, 20) if spy_rows else None
        spy_ret_prev_20 = _period_return(spy_rows, spy_idx - 20, 20) if spy_rows else None
        if None in (stock_ret_20, stock_ret_prev_20, spy_ret_20, spy_ret_prev_20):
            continue

        row = rows[signal_idx]
        prev_row = rows[signal_idx - 1] if signal_idx > 0 else None
        row_open = _as_float(row.get("Open"))
        prev_close = _as_float(prev_row.get("Close")) if prev_row else None
        gap_pct = (row_open / prev_close) - 1 if row_open is not None and prev_close else None
        rs20 = stock_ret_20 - spy_ret_20
        prev_rs20 = stock_ret_prev_20 - spy_ret_prev_20
        rs_accel = rs20 - prev_rs20
        tag_hit = rs20 > 0 and rs_accel > 0 and (gap_pct is None or gap_pct < 0.03)

        forward = rows[entry_idx : entry_idx + HOLD_DAYS]
        if len(forward) < 2:
            continue
        entry_open = _as_float(forward[0].get("Open"))
        exit_close = _as_float(forward[-1].get("Close"))
        if not entry_open or exit_close is None:
            continue
        shares = int(NOTIONAL_USD // (entry_open * (1 + ROUND_TRIP_COST_PCT)))
        if shares <= 0:
            continue
        entry_price = entry_open * (1 + ROUND_TRIP_COST_PCT)
        exit_price = exit_close * (1 - ROUND_TRIP_COST_PCT)
        pnl = (exit_price - entry_price) * shares
        invested = entry_price * shares
        out.append(
            {
                "signal_date": signal_date,
                "entry_date": forward[0].get("Date"),
                "exit_date": forward[-1].get("Date"),
                "ticker": ticker,
                "strategy": strategy,
                "decision": event.get("decision") or "unknown",
                "candidate_rank": event.get("candidate_rank"),
                "gap_pct": _round(gap_pct, 6),
                "stock_return_20d": _round(stock_ret_20, 6),
                "spy_return_20d": _round(spy_ret_20, 6),
                "rs20": _round(rs20, 6),
                "prev_rs20": _round(prev_rs20, 6),
                "rs20_accel": _round(rs_accel, 6),
                "rs_accel_no_chase": tag_hit,
                "entry_open": _round(entry_open, 4),
                "exit_close": _round(exit_close, 4),
                "shares": shares,
                "pnl": _round(pnl, 2),
                "return_pct": _round(pnl / invested, 6),
            }
        )
    same_day_entered_returns: defaultdict[str, list[float]] = defaultdict(list)
    for row in out:
        if row["decision"] == "entered":
            same_day_entered_returns[row["signal_date"]].append(float(row["return_pct"]))
    for row in out:
        alternatives = same_day_entered_returns.get(row["signal_date"]) or []
        row["same_day_entered_alt_count"] = len(alternatives)
        if row["decision"] != "entered" and alternatives:
            row["vs_same_day_entered_return_pct"] = _round(
                float(row["return_pct"]) - (sum(alternatives) / len(alternatives)),
                6,
            )
        else:
            row["vs_same_day_entered_return_pct"] = None
    return out


def _run_window(name: str, spec: dict[str, Any]) -> dict[str, Any]:
    snapshot = _load_json(REPO_ROOT / spec["snapshot"])
    backtest = _load_json(REPO_ROOT / spec["backtest_results"])
    events_payload = _load_json(REPO_ROOT / spec["candidate_events"])
    rows = _candidate_rows(backtest, snapshot, events_payload.get("candidate_events") or [])
    treatment = [row for row in rows if row["rs_accel_no_chase"]]
    complement = [row for row in rows if not row["rs_accel_no_chase"]]
    missed = [row for row in treatment if row["decision"] != "entered"]
    entered = [row for row in treatment if row["decision"] == "entered"]
    return {
        "window": name,
        "window_spec": spec,
        "candidate_count": len(rows),
        "treatment_count": len(treatment),
        "treatment_overlap_entered_count": len(entered),
        "treatment_missed_count": len(missed),
        "treatment_stats": _stats(treatment),
        "treatment_entered_stats": _stats(entered),
        "treatment_missed_stats": _stats(missed),
        "complement_stats": _stats(complement),
        "treatment_rows": treatment,
    }


def _aggregate(by_window: dict[str, Any]) -> dict[str, Any]:
    treatment = []
    complement = []
    missed = []
    for window_name, window in by_window.items():
        for row in window["treatment_rows"]:
            treatment.append({**row, "window": window_name})
        # Keep aggregate complement compact by recomputing from stats only.
        missed.extend({**row, "window": window_name} for row in window["treatment_rows"] if row["decision"] != "entered")
    treatment_stats = _stats(treatment)
    missed_stats = _stats(missed)
    positive_windows = sum(
        1 for window in by_window.values() if window["treatment_stats"]["total_pnl"] > 0
    )
    windows_with_candidates = sum(1 for window in by_window.values() if window["treatment_count"])
    gate_failures = []
    if treatment_stats["candidate_count"] < 8:
        gate_failures.append("candidate_count_lt_8")
    if positive_windows < 2:
        gate_failures.append("positive_windows_lt_2")
    if (treatment_stats.get("win_rate") or 0) < 0.5:
        gate_failures.append("win_rate_lt_50pct")
    if (treatment_stats.get("avg_return_pct") or 0) <= 0:
        gate_failures.append("avg_return_not_positive")
    if (
        treatment_stats.get("max_single_ticker_positive_share") is not None
        and treatment_stats["max_single_ticker_positive_share"] > 0.5
    ):
        gate_failures.append("single_ticker_positive_share_gt_50pct")
    return {
        "treatment": treatment_stats,
        "missed_treatment": missed_stats,
        "positive_windows": positive_windows,
        "windows_with_candidates": windows_with_candidates,
        "forward_watch_grade": "interesting" if not gate_failures else "not_promotion_grade",
        "gate_failures": gate_failures,
    }


def main() -> None:
    by_window = OrderedDict((name, _run_window(name, spec)) for name, spec in WINDOWS.items())
    aggregate = _aggregate(by_window)
    decision = "observed_only"
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "lane": "alpha_discovery",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "Existing trend_long and breakout_long candidate rows with improving "
            "20-day SPY-relative strength versus the prior 20-day window and no "
            "signal-day 3% gap chase may identify cleaner continuation candidates "
            "with better forward replacement value."
        ),
        "single_causal_variable": "rs_accel_no_chase candidate shadow tag v2",
        "historical_rejected_mechanism_check": {
            "avoids_recent_rejections": [
                "does not retune gap-cancel bypasses",
                "does not promote platform RS20/no-gap missed candidates",
                "does not retune sector caps or sector-risk boosts",
                "does not change add-on heat, ordering, triggers, or volume filters",
                "does not use options, Form 4, 10-K, analyst revisions, or LLM ranking",
            ],
            "why_not_simple_repeat": (
                "This is a candidate-level shadow tag on all existing A/B rows using "
                "RS acceleration versus the prior 20-day excess window plus a no-chase "
                "condition; it is not a hard gate, sector selector, or same-sample "
                "platform-RS20 missed-candidate promotion."
            ),
        },
        "parameters": {
            "core_strategies": sorted(CORE_STRATEGIES),
            "rs20_condition": "stock_20d_return - SPY_20d_return > 0",
            "acceleration_condition": "current_rs20 > prior_20d_rs20",
            "no_chase_condition": "signal_day_gap_pct < 0.03",
            "hold_days": HOLD_DAYS,
            "notional_usd": NOTIONAL_USD,
            "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
        },
        "baseline_metrics": BASELINE,
        "market_regime_summary": {
            name: spec["state_note"] for name, spec in WINDOWS.items()
        },
        "by_window": by_window,
        "aggregate": aggregate,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "why_not_llm": "LLM ranking remains coverage-limited; this is deterministic shadow attribution.",
        },
        "promotion_assessment": (
            "Not justified from this observed-only artifact alone; a later default-off "
            "replay would need Gate 4, multi-window replacement value, and low "
            "single-ticker concentration."
        ),
        "artifact_path": str(OUT_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
    }
    _write_json(OUT_JSON, payload)
    print(json.dumps({"experiment_id": EXPERIMENT_ID, "artifact": payload["artifact_path"], "aggregate": aggregate}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
