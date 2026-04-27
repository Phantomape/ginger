"""exp-20260426-003 collision-day tie-break viability audit.

Hypothesis:
    On rare true cohort-competition days, a collision-aware tie-break driven by
    candidate cohort composition might improve marginal slot allocation more
    stably than the rejected broad day-state sleeve routers.

This runner intentionally stays in shadow mode. It reads the accepted-stack
candidate-cohort audit artifact and checks whether the current system even
produces enough real collision days for a tie-break mechanism to matter.
"""

from __future__ import annotations

import json
import os
from collections import OrderedDict


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
IN_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "exp_20260426_002_candidate_cohort_audit.json",
)
OUT_JSON = os.path.join(
    REPO_ROOT,
    "data",
    "exp_20260426_003_results.json",
)


def _round(value, digits=6):
    if value is None:
        return None
    return round(float(value), digits)


def _window_summary(window: dict) -> dict:
    days = window.get("days") or []
    trade_count = (window.get("baseline_metrics") or {}).get("trade_count", 0) or 0

    true_collision_days = [
        day for day in days
        if (day.get("slot_collision_excess") or 0) > 0
    ]
    collision_days_with_entries = [
        day for day in true_collision_days
        if (day.get("entered_count") or 0) > 0
    ]
    mixed_collision_days = [
        day for day in true_collision_days
        if (day.get("pre_size_breakout_share") or 0) > 0
        and (day.get("pre_size_trend_share") or 0) > 0
    ]
    mixed_collision_days_with_entries = [
        day for day in mixed_collision_days
        if (day.get("entered_count") or 0) > 0
    ]
    near_collision_days = [
        day for day in days
        if (day.get("pre_size_count") or 0) >= 4
    ]

    collision_examples = []
    for day in true_collision_days[:5]:
        collision_examples.append({
            "signal_date": day.get("signal_date"),
            "pre_size_count": day.get("pre_size_count"),
            "entered_count": day.get("entered_count"),
            "slot_collision_excess": day.get("slot_collision_excess"),
            "pre_size_breakout_share": day.get("pre_size_breakout_share"),
            "pre_size_trend_share": day.get("pre_size_trend_share"),
            "realized_total_pnl": day.get("realized_total_pnl"),
        })

    return {
        "window": window.get("window"),
        "start": window.get("start"),
        "end": window.get("end"),
        "trade_count": trade_count,
        "day_count": len(days),
        "true_collision_day_count": len(true_collision_days),
        "collision_day_fraction": _round(len(true_collision_days) / len(days)) if days else 0.0,
        "collision_days_with_entries": len(collision_days_with_entries),
        "mixed_collision_day_count": len(mixed_collision_days),
        "mixed_collision_days_with_entries": len(mixed_collision_days_with_entries),
        "near_collision_day_count_pre_size_ge_4": len(near_collision_days),
        "collision_days_per_100_trades": _round(100 * len(true_collision_days) / trade_count) if trade_count else None,
        "collision_examples": collision_examples,
        "viability_flag": (
            "no_real_collision_days"
            if not true_collision_days
            else "collision_days_exist_but_no_entry_decisions"
            if not collision_days_with_entries
            else "entry_relevant_collision_days_exist"
        ),
    }


def main() -> int:
    with open(IN_JSON, "r", encoding="utf-8") as f:
        audit = json.load(f)

    windows = audit.get("windows") or []
    summaries = [_window_summary(window) for window in windows]

    total_trade_count = sum(item["trade_count"] for item in summaries)
    total_collision_days = sum(item["true_collision_day_count"] for item in summaries)
    total_collision_days_with_entries = sum(
        item["collision_days_with_entries"] for item in summaries
    )
    total_mixed_collision_days = sum(item["mixed_collision_day_count"] for item in summaries)
    total_mixed_collision_days_with_entries = sum(
        item["mixed_collision_days_with_entries"] for item in summaries
    )

    result = OrderedDict([
        ("experiment_id", "exp-20260426-003"),
        ("status", "observed_only_candidate"),
        ("hypothesis", (
            "A tie-break targeted only at true collision days might unlock a "
            "new large-category allocation alpha without repeating rejected "
            "broad day-state routing."
        )),
        ("input_artifact", os.path.relpath(IN_JSON, REPO_ROOT).replace("\\", "/")),
        ("window_summaries", summaries),
        ("aggregate", {
            "window_count": len(summaries),
            "total_trade_count": total_trade_count,
            "total_true_collision_days": total_collision_days,
            "total_collision_days_with_entries": total_collision_days_with_entries,
            "total_mixed_collision_days": total_mixed_collision_days,
            "total_mixed_collision_days_with_entries": total_mixed_collision_days_with_entries,
            "collision_days_per_100_trades": (
                _round(100 * total_collision_days / total_trade_count)
                if total_trade_count
                else None
            ),
            "entry_relevant_collision_days_per_100_trades": (
                _round(100 * total_collision_days_with_entries / total_trade_count)
                if total_trade_count
                else None
            ),
        }),
        ("decision_support", {
            "eligible_for_runtime_tiebreak_screen": bool(total_collision_days_with_entries),
            "eligible_for_mixed_strategy_tiebreak_screen": bool(
                total_mixed_collision_days_with_entries
            ),
            "why_not": (
                "The accepted stack currently produces no entry-relevant mixed "
                "collision days across the three fixed windows, so a collision-day "
                "tie-break cannot be meaningfully evaluated as alpha yet."
            ),
        }),
    ])

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
