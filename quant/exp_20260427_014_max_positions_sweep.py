"""exp-20260427-014: fixed-window MAX_POSITIONS capacity sweep.

This runner tests one capital-allocation variable only: the maximum number of
concurrent positions. It uses the deterministic OHLCV snapshots from
docs/backtesting.md and leaves signal generation, exits, LLM, news replay,
earnings, sizing rules, and add-on defaults unchanged.
"""

import json
import os
import sys
from datetime import datetime, timezone


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from backtester import BacktestEngine, DEFAULT_CONFIG

try:
    from data_layer import get_universe
except Exception:
    from filter import WATCHLIST

    def get_universe():
        return list(WATCHLIST)


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

MAX_POSITIONS_VALUES = [4, 5, 6, 7]
BASELINE_MAX_POSITIONS = DEFAULT_CONFIG["MAX_POSITIONS"]


def compact_metrics(result):
    benchmarks = result.get("benchmarks") or {}
    addon = result.get("addon_attribution") or {}
    capital_efficiency = result.get("capital_efficiency") or {}
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
        "addon_executed": addon.get("executed"),
        "slot_days_used": capital_efficiency.get("slot_days_used"),
        "slot_utilization": capital_efficiency.get("slot_utilization"),
    }


def run_window(universe, window, max_positions):
    config = {
        "REGIME_AWARE_EXIT": True,
        "MAX_POSITIONS": max_positions,
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
        raise RuntimeError(f"{window['label']} MAX_POSITIONS={max_positions}: {result['error']}")
    return result


def main():
    universe = get_universe()
    raw_results = {}
    compact = {}

    for window in WINDOWS:
        raw_results[window["label"]] = {}
        compact[window["label"]] = {}
        for value in MAX_POSITIONS_VALUES:
            result = run_window(universe, window, value)
            raw_results[window["label"]][str(value)] = result
            compact[window["label"]][str(value)] = compact_metrics(result)
            m = compact[window["label"]][str(value)]
            print(
                f"{window['label']} MAX_POSITIONS={value}: "
                f"EV={m['expected_value_score']} PnL={m['total_pnl']} "
                f"SharpeDaily={m['sharpe_daily']} DD={m['max_drawdown_pct']} "
                f"WR={m['win_rate']} trades={m['trade_count']}"
            )

    baseline = {
        label: values[str(BASELINE_MAX_POSITIONS)]
        for label, values in compact.items()
    }
    comparisons = {}
    for value in MAX_POSITIONS_VALUES:
        key = str(value)
        if value == BASELINE_MAX_POSITIONS:
            continue
        windows_improved = 0
        windows_regressed = 0
        ev_delta_sum = 0.0
        pnl_delta_sum = 0.0
        max_drawdown_delta_max = None
        comparisons[key] = {"by_window": {}}
        for label, values in compact.items():
            before = baseline[label]
            after = values[key]
            ev_delta = round(
                (after["expected_value_score"] or 0) - (before["expected_value_score"] or 0),
                4,
            )
            pnl_delta = round((after["total_pnl"] or 0) - (before["total_pnl"] or 0), 2)
            dd_delta = round(
                (after["max_drawdown_pct"] or 0) - (before["max_drawdown_pct"] or 0),
                4,
            )
            if ev_delta > 0:
                windows_improved += 1
            elif ev_delta < 0:
                windows_regressed += 1
            ev_delta_sum += ev_delta
            pnl_delta_sum += pnl_delta
            max_drawdown_delta_max = (
                dd_delta
                if max_drawdown_delta_max is None
                else max(max_drawdown_delta_max, dd_delta)
            )
            comparisons[key]["by_window"][label] = {
                "expected_value_score_delta": ev_delta,
                "total_pnl_delta": pnl_delta,
                "max_drawdown_pct_delta": dd_delta,
                "trade_count_delta": (
                    after["trade_count"] or 0
                ) - (before["trade_count"] or 0),
                "win_rate_delta": round(
                    (after["win_rate"] or 0) - (before["win_rate"] or 0),
                    4,
                ),
            }
        comparisons[key].update({
            "ev_delta_sum": round(ev_delta_sum, 4),
            "pnl_delta_sum": round(pnl_delta_sum, 2),
            "max_drawdown_delta_max": max_drawdown_delta_max,
            "windows_improved": windows_improved,
            "windows_regressed": windows_regressed,
        })

    best_value = max(
        (v for v in MAX_POSITIONS_VALUES if v != BASELINE_MAX_POSITIONS),
        key=lambda v: comparisons[str(v)]["ev_delta_sum"],
    )

    artifact = {
        "experiment_id": "exp-20260427-014",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "hypothesis": (
            "If the accepted A+B+add-on stack is capacity constrained, modestly "
            "changing MAX_POSITIONS should improve capital allocation across "
            "the fixed three windows without changing signal or exit logic."
        ),
        "single_causal_variable": "MAX_POSITIONS",
        "baseline_max_positions": BASELINE_MAX_POSITIONS,
        "tested_values": MAX_POSITIONS_VALUES,
        "windows": WINDOWS,
        "metrics": compact,
        "comparisons_vs_baseline": comparisons,
        "best_non_baseline_value": best_value,
        "raw_results": raw_results,
    }
    out_path = os.path.join(ROOT, "data", "exp_20260427_014_max_positions_sweep.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2, ensure_ascii=False)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
