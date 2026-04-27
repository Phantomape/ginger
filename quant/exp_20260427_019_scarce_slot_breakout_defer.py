"""exp-20260427-019: scarce-slot breakout defer replay.

Single causal variable: when only one entry slot remains, defer new
``breakout_long`` entries so the slot is reserved for ``trend_long`` candidates.
This tests the sleeve-state audit from exp-20260427-016 without changing entry
signals, exits, sizing rules, LLM/news replay, add-on defaults, or global
MAX_POSITIONS.
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


EXPERIMENT_ID = "exp-20260427-019"

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
    scarce = result.get("scarce_slot_attribution") or {}
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
        "breakout_deferred": scarce.get("breakout_deferred", 0),
    }


def run_window(universe: list[str], window: dict, defer_breakouts: bool) -> dict:
    config = {
        "REGIME_AWARE_EXIT": True,
        "DEFER_BREAKOUT_WHEN_SLOTS_LTE": 1 if defer_breakouts else None,
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
        raise RuntimeError(f"{window['label']} defer={defer_breakouts}: {result['error']}")
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

        baseline = run_window(universe, window, defer_breakouts=False)
        variant = run_window(universe, window, defer_breakouts=True)
        raw_results[label]["baseline"] = baseline
        raw_results[label]["scarce_slot_breakout_defer"] = variant
        metrics[label]["baseline"] = compact_metrics(baseline)
        metrics[label]["scarce_slot_breakout_defer"] = compact_metrics(variant)

        before = metrics[label]["baseline"]
        after = metrics[label]["scarce_slot_breakout_defer"]
        comparisons[label] = {
            "expected_value_score_delta": metric_delta(after, before, "expected_value_score"),
            "total_pnl_delta": metric_delta(after, before, "total_pnl", 2),
            "sharpe_daily_delta": metric_delta(after, before, "sharpe_daily"),
            "max_drawdown_pct_delta": metric_delta(after, before, "max_drawdown_pct"),
            "win_rate_delta": metric_delta(after, before, "win_rate"),
            "trade_count_delta": (after.get("trade_count") or 0) - (before.get("trade_count") or 0),
            "breakout_deferred": after.get("breakout_deferred", 0),
        }
        print(
            f"{label}: EV {before['expected_value_score']} -> {after['expected_value_score']} "
            f"PnL {before['total_pnl']} -> {after['total_pnl']} "
            f"DD {before['max_drawdown_pct']} -> {after['max_drawdown_pct']} "
            f"deferred={after.get('breakout_deferred', 0)}"
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
            "When only one entry slot remains, deferring breakout_long entries "
            "may improve sleeve routing by preserving scarce capacity for "
            "trend_long candidates."
        ),
        "single_causal_variable": "DEFER_BREAKOUT_WHEN_SLOTS_LTE=1",
        "windows": WINDOWS,
        "metrics": metrics,
        "comparisons_vs_baseline": comparisons,
        "aggregate": {
            "windows_improved": windows_improved,
            "windows_regressed": windows_regressed,
            "ev_delta_sum": ev_delta_sum,
            "pnl_delta_sum": pnl_delta_sum,
            "max_drawdown_delta_max": max_drawdown_delta_max,
            "total_breakout_deferred": sum(
                item["breakout_deferred"] for item in comparisons.values()
            ),
            "decision": decision,
        },
        "raw_results": raw_results,
    }

    out_path = os.path.join(ROOT, "data", f"{EXPERIMENT_ID}_scarce_slot_breakout_defer.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2, ensure_ascii=False)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
