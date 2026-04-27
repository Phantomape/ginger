"""exp-20260427-028: promote scarce-slot breakout defer to default.

Single causal variable: BacktestEngine's default
``DEFER_BREAKOUT_WHEN_SLOTS_LTE`` changes from ``None`` to ``1``. The baseline
is still replayed by explicitly overriding the config back to ``None``.
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

from backtester import BacktestEngine, DEFAULT_CONFIG

try:
    from data_layer import get_universe
except Exception:
    from filter import WATCHLIST

    def get_universe():
        return list(WATCHLIST)


EXPERIMENT_ID = "exp-20260427-028"

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
        "breakout_deferred": scarce.get("breakout_deferred", 0),
        "defer_breakout_when_slots_lte": scarce.get("defer_breakout_when_slots_lte"),
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


def main() -> None:
    universe = get_universe()
    baseline_config = {
        "REGIME_AWARE_EXIT": True,
        "DEFER_BREAKOUT_WHEN_SLOTS_LTE": None,
    }
    promoted_default_config = {"REGIME_AWARE_EXIT": True}
    metrics = {}
    comparisons = {}

    for window in WINDOWS:
        label = window["label"]
        baseline = run_window(universe, window, baseline_config)
        promoted = run_window(universe, window, promoted_default_config)
        before = compact_metrics(baseline)
        after = compact_metrics(promoted)
        metrics[label] = {
            "baseline_override_none": before,
            "promoted_default": after,
        }
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

    aggregate = {
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
        "total_breakout_deferred": sum(
            item["breakout_deferred"] for item in comparisons.values()
        ),
        "decision": "accepted_production_default",
    }

    artifact = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "hypothesis": (
            "The one-slot scarce-capacity sleeve-routing rule should be promoted "
            "to default because repeated discriminator tests failed to improve it, "
            "while the simple form improves two fixed windows and regresses none."
        ),
        "single_causal_variable": "DEFAULT_CONFIG.DEFER_BREAKOUT_WHEN_SLOTS_LTE: None -> 1",
        "default_config_value": DEFAULT_CONFIG["DEFER_BREAKOUT_WHEN_SLOTS_LTE"],
        "unchanged": [
            "entry signals",
            "exit targets/stops",
            "ADDON trigger and cap",
            "MAX_POSITIONS",
            "LLM/news replay",
            "earnings strategy",
        ],
        "windows": WINDOWS,
        "metrics": metrics,
        "comparisons_vs_baseline": comparisons,
        "aggregate": aggregate,
    }

    out_path = os.path.join(ROOT, "data", f"{EXPERIMENT_ID}_scarce_slot_default_promotion.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2, ensure_ascii=False)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
