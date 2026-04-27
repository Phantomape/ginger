"""exp-20260427-021: state-conditioned scarce-slot breakout defer.

Single causal variable: widen scarce-slot breakout deferral to two slots only
when the broad tape is not extremely extended.  The state guard is
``min(SPY pct_from_ma, QQQ pct_from_ma) <= 10%``.

This tests a market-state discriminator for exp-20260427-020 without changing
entry signals, exits, LLM/news replay, add-on defaults, or global capacity.
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


EXPERIMENT_ID = "exp-20260427-021"

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

VARIANTS = {
    "current_default_slots_lte_1": {
        "REGIME_AWARE_EXIT": True,
        "DEFER_BREAKOUT_WHEN_SLOTS_LTE": 1,
        "DEFER_BREAKOUT_MAX_MIN_INDEX_PCT_FROM_MA": None,
    },
    "unconditional_slots_lte_2": {
        "REGIME_AWARE_EXIT": True,
        "DEFER_BREAKOUT_WHEN_SLOTS_LTE": 2,
        "DEFER_BREAKOUT_MAX_MIN_INDEX_PCT_FROM_MA": None,
    },
    "state_conditioned_slots_lte_2": {
        "REGIME_AWARE_EXIT": True,
        "DEFER_BREAKOUT_WHEN_SLOTS_LTE": 2,
        "DEFER_BREAKOUT_MAX_MIN_INDEX_PCT_FROM_MA": 0.10,
    },
}


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
        "breakout_deferred": scarce.get("breakout_deferred", 0),
        "state_cap": scarce.get("defer_breakout_max_min_index_pct_from_ma"),
    }


def run_window(universe: list[str], window: dict, config: dict) -> dict:
    engine = BacktestEngine(
        universe,
        start=window["start"],
        end=window["end"],
        config=config,
        ohlcv_snapshot_path=window["snapshot"],
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(f"{window['label']} {config}: {result['error']}")
    return result


def metric_delta(after: dict, before: dict, key: str, ndigits: int = 4):
    return round((after.get(key) or 0) - (before.get(key) or 0), ndigits)


def compare(after: dict, before: dict) -> dict:
    return {
        "expected_value_score_delta": metric_delta(after, before, "expected_value_score"),
        "total_pnl_delta": metric_delta(after, before, "total_pnl", 2),
        "sharpe_daily_delta": metric_delta(after, before, "sharpe_daily"),
        "max_drawdown_pct_delta": metric_delta(after, before, "max_drawdown_pct"),
        "win_rate_delta": metric_delta(after, before, "win_rate"),
        "trade_count_delta": (after.get("trade_count") or 0) - (before.get("trade_count") or 0),
        "breakout_deferred_delta": (
            (after.get("breakout_deferred") or 0)
            - (before.get("breakout_deferred") or 0)
        ),
    }


def aggregate(comparisons: dict) -> dict:
    return {
        "windows_improved": sum(
            1 for item in comparisons.values()
            if item["expected_value_score_delta"] > 0
        ),
        "windows_regressed": sum(
            1 for item in comparisons.values()
            if item["expected_value_score_delta"] < 0
        ),
        "ev_delta_sum": round(
            sum(item["expected_value_score_delta"] for item in comparisons.values()),
            4,
        ),
        "pnl_delta_sum": round(
            sum(item["total_pnl_delta"] for item in comparisons.values()),
            2,
        ),
        "max_drawdown_delta_max": max(
            item["max_drawdown_pct_delta"] for item in comparisons.values()
        ),
        "breakout_deferred_delta_sum": sum(
            item["breakout_deferred_delta"] for item in comparisons.values()
        ),
    }


def main() -> None:
    universe = get_universe()
    raw_results = {}
    metrics = {}

    for window in WINDOWS:
        label = window["label"]
        raw_results[label] = {}
        metrics[label] = {}
        for variant_name, config in VARIANTS.items():
            result = run_window(universe, window, config)
            raw_results[label][variant_name] = result
            metrics[label][variant_name] = compact_metrics(result)

        base = metrics[label]["current_default_slots_lte_1"]
        print(
            f"{label}: current EV={base['expected_value_score']} "
            f"PnL={base['total_pnl']} DD={base['max_drawdown_pct']}"
        )
        for variant_name in (
                "unconditional_slots_lte_2",
                "state_conditioned_slots_lte_2"):
            item = metrics[label][variant_name]
            print(
                f"  {variant_name}: EV={item['expected_value_score']} "
                f"PnL={item['total_pnl']} DD={item['max_drawdown_pct']} "
                f"deferred={item['breakout_deferred']}"
            )

    comparisons = {
        variant_name: {
            window["label"]: compare(
                metrics[window["label"]][variant_name],
                metrics[window["label"]]["current_default_slots_lte_1"],
            )
            for window in WINDOWS
        }
        for variant_name in (
            "unconditional_slots_lte_2",
            "state_conditioned_slots_lte_2",
        )
    }
    aggregates = {
        variant_name: aggregate(items)
        for variant_name, items in comparisons.items()
    }

    conditioned = aggregates["state_conditioned_slots_lte_2"]
    decision = (
        "accepted_default_off_research_harness"
        if (
            conditioned["windows_improved"] >= 2
            and conditioned["windows_regressed"] == 0
            and conditioned["ev_delta_sum"] > 0
        )
        else "rejected"
    )

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "hypothesis": (
            "Widening scarce-slot breakout deferral to two remaining slots may "
            "work only when SPY/QQQ are not both extremely extended above their "
            "moving averages."
        ),
        "single_causal_variable": (
            "state-conditioned scarce-slot rule: slots_lte_2 only when "
            "min(SPY pct_from_ma, QQQ pct_from_ma) <= 0.10"
        ),
        "windows": WINDOWS,
        "variants": VARIANTS,
        "metrics": metrics,
        "comparisons_vs_current_default": comparisons,
        "aggregate": aggregates,
        "decision": decision,
        "raw_results": raw_results,
    }

    out_path = os.path.join(
        ROOT,
        "data",
        f"{EXPERIMENT_ID}_state_conditioned_scarce_slot_defer.json",
    )
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2, ensure_ascii=False)
    print(f"Decision: {decision}")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
