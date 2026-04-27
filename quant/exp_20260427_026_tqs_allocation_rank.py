"""exp-20260427-026: trade-quality-score allocation ranking replay.

Single causal variable: sort same-day entry candidates by enriched
``trade_quality_score`` before slot slicing. This tests whether existing
structured quality fields can route scarce entry slots better without changing
entry rules, exits, sizing, add-ons, LLM/news replay, or global capacity.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from backtester import BacktestEngine

try:
    from data_layer import get_universe
except Exception:
    from filter import WATCHLIST

    def get_universe():
        return list(WATCHLIST)


EXPERIMENT_ID = "exp-20260427-026"

WINDOWS = [
    {
        "label": "late_strong",
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": os.path.join(ROOT, "data", "ohlcv_snapshot_20251023_20260421.json"),
        "regime": "slow-melt bull / accepted-stack dominant tape",
    },
    {
        "label": "mid_weak",
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": os.path.join(ROOT, "data", "ohlcv_snapshot_20250423_20251022.json"),
        "regime": "rotation-heavy bull where accepted stack makes money but lags indexes",
    },
    {
        "label": "old_thin",
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": os.path.join(ROOT, "data", "ohlcv_snapshot_20241002_20250422.json"),
        "regime": "mixed-to-weak older tape with lower win rate",
    },
]


def compact_metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    entry_attr = result.get("entry_execution_attribution") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe": result.get("sharpe"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "spy_buy_hold_return_pct": benchmarks.get("spy_buy_hold_return_pct"),
        "qqq_buy_hold_return_pct": benchmarks.get("qqq_buy_hold_return_pct"),
        "strategy_vs_spy_pct": benchmarks.get("strategy_vs_spy_pct"),
        "strategy_vs_qqq_pct": benchmarks.get("strategy_vs_qqq_pct"),
        "slot_sliced": (entry_attr.get("reason_counts") or {}).get("slot_sliced", 0),
    }


def run_window(universe: list[str], window: dict, rank_by_tqs: bool) -> dict:
    config = {
        "REGIME_AWARE_EXIT": True,
        "RANK_SIGNALS_BY_TQS": rank_by_tqs,
    }
    engine = BacktestEngine(
        universe,
        start=window["start"],
        end=window["end"],
        config=config,
        ohlcv_snapshot_path=window["snapshot"],
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(f"{window['label']} rank_by_tqs={rank_by_tqs}: {result['error']}")
    return result


def metric_delta(after: dict, before: dict, key: str, ndigits: int = 4):
    return round((after.get(key) or 0) - (before.get(key) or 0), ndigits)


def main() -> None:
    universe = get_universe()
    raw_results = {}
    metrics = {}
    comparisons = {}

    for window in WINDOWS:
        label = window["label"]
        raw_results[label] = {}
        metrics[label] = {}

        baseline = run_window(universe, window, rank_by_tqs=False)
        variant = run_window(universe, window, rank_by_tqs=True)
        raw_results[label]["baseline"] = baseline
        raw_results[label]["rank_by_tqs"] = variant
        metrics[label]["baseline"] = compact_metrics(baseline)
        metrics[label]["rank_by_tqs"] = compact_metrics(variant)

        before = metrics[label]["baseline"]
        after = metrics[label]["rank_by_tqs"]
        comparisons[label] = {
            "expected_value_score_delta": metric_delta(after, before, "expected_value_score"),
            "total_pnl_delta": metric_delta(after, before, "total_pnl", 2),
            "sharpe_daily_delta": metric_delta(after, before, "sharpe_daily"),
            "max_drawdown_pct_delta": metric_delta(after, before, "max_drawdown_pct"),
            "win_rate_delta": metric_delta(after, before, "win_rate"),
            "trade_count_delta": (after.get("trade_count") or 0) - (before.get("trade_count") or 0),
            "slot_sliced_delta": (after.get("slot_sliced") or 0) - (before.get("slot_sliced") or 0),
        }
        print(
            f"{label}: EV {before['expected_value_score']} -> {after['expected_value_score']} "
            f"PnL {before['total_pnl']} -> {after['total_pnl']} "
            f"DD {before['max_drawdown_pct']} -> {after['max_drawdown_pct']}"
        )

    windows_improved = sum(
        1 for item in comparisons.values()
        if item["expected_value_score_delta"] > 0
    )
    windows_regressed = sum(
        1 for item in comparisons.values()
        if item["expected_value_score_delta"] < 0
    )
    ev_delta_sum = round(
        sum(item["expected_value_score_delta"] for item in comparisons.values()),
        4,
    )
    pnl_delta_sum = round(
        sum(item["total_pnl_delta"] for item in comparisons.values()),
        2,
    )
    max_drawdown_delta_max = max(
        item["max_drawdown_pct_delta"] for item in comparisons.values()
    )
    decision = (
        "accepted_default_off_research_harness"
        if windows_improved >= 2 and ev_delta_sum > 0
        else "rejected"
    )

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "hypothesis": (
            "Existing enriched trade_quality_score may route scarce same-day entry "
            "slots better than current strategy/native ordering."
        ),
        "single_causal_variable": "RANK_SIGNALS_BY_TQS=True",
        "windows": WINDOWS,
        "metrics": metrics,
        "comparisons_vs_baseline": comparisons,
        "aggregate": {
            "windows_improved": windows_improved,
            "windows_regressed": windows_regressed,
            "ev_delta_sum": ev_delta_sum,
            "pnl_delta_sum": pnl_delta_sum,
            "max_drawdown_delta_max": max_drawdown_delta_max,
            "decision": decision,
        },
        "raw_results": raw_results,
    }

    out_path = os.path.join(ROOT, "data", f"{EXPERIMENT_ID}_tqs_allocation_rank.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2, ensure_ascii=False)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
