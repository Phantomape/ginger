"""exp-20260427-021: scarce-slot state-threshold sweep.

This runner changes no production strategy code. It extends the rejected
exp-20260427-021 state-conditioned scarce-slot deferral by asking whether any
market-extension threshold can keep the mid_weak gain without damaging the
late_strong window.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
QUANT_DIR = os.path.join(ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260427-021"
OUT_DIR = os.path.join(ROOT, "data", "experiments", EXPERIMENT_ID)
OUT_JSON = os.path.join(
    OUT_DIR,
    "exp_20260427_021_scarce_slot_state_threshold_sweep_v2.json",
)

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
        "regime": "rotation-heavy bull where strategy makes money but lags indexes",
    },
    {
        "label": "old_thin",
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": os.path.join(ROOT, "data", "ohlcv_snapshot_20241002_20250422.json"),
        "regime": "mixed-to-weak older tape with lower win rate",
    },
]

THRESHOLDS = [None, 0.00, 0.03, 0.05, 0.075, 0.10, 0.125, 0.15]


def compact_metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    scarce = result.get("scarce_slot_attribution") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
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


def run_window(universe: list[str], window: dict, threshold: float | None) -> dict:
    config = {
        "REGIME_AWARE_EXIT": True,
        "DEFER_BREAKOUT_WHEN_SLOTS_LTE": 2,
        "DEFER_BREAKOUT_MAX_MIN_INDEX_PCT_FROM_MA": threshold,
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
        raise RuntimeError(f"{window['label']} threshold={threshold}: {result['error']}")
    return result


def run_default(universe: list[str], window: dict) -> dict:
    engine = BacktestEngine(
        universe,
        start=window["start"],
        end=window["end"],
        config={"REGIME_AWARE_EXIT": True},
        ohlcv_snapshot_path=window["snapshot"],
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(f"{window['label']} default: {result['error']}")
    return result


def delta(after: dict, before: dict, key: str, ndigits: int = 4):
    return round((after.get(key) or 0) - (before.get(key) or 0), ndigits)


def compare(after: dict, before: dict) -> dict:
    return {
        "expected_value_score_delta": delta(after, before, "expected_value_score"),
        "total_pnl_delta": delta(after, before, "total_pnl", 2),
        "sharpe_daily_delta": delta(after, before, "sharpe_daily"),
        "max_drawdown_pct_delta": delta(after, before, "max_drawdown_pct"),
        "win_rate_delta": delta(after, before, "win_rate"),
        "trade_count_delta": (after.get("trade_count") or 0) - (before.get("trade_count") or 0),
        "breakout_deferred_delta": (
            (after.get("breakout_deferred") or 0)
            - (before.get("breakout_deferred") or 0)
        ),
    }


def threshold_key(threshold: float | None) -> str:
    return "unconditional" if threshold is None else f"cap_{threshold:.3f}".replace(".", "_")


def main() -> int:
    universe = get_universe()
    metrics: dict[str, dict] = {}
    comparisons: dict[str, dict] = {}

    for window in WINDOWS:
        label = window["label"]
        default_metrics = compact_metrics(run_default(universe, window))
        metrics[label] = {"current_default_slots_lte_1": default_metrics}
        comparisons[label] = {}
        print(
            f"{label}: default EV={default_metrics['expected_value_score']} "
            f"PnL={default_metrics['total_pnl']}"
        )

        for threshold in THRESHOLDS:
            key = threshold_key(threshold)
            item = compact_metrics(run_window(universe, window, threshold))
            metrics[label][key] = item
            comparisons[label][key] = compare(item, default_metrics)
            print(
                f"  {key}: EV={item['expected_value_score']} "
                f"PnL={item['total_pnl']} deferred={item['breakout_deferred']}"
            )

    aggregate = {}
    for threshold in THRESHOLDS:
        key = threshold_key(threshold)
        rows = {window["label"]: comparisons[window["label"]][key] for window in WINDOWS}
        aggregate[key] = {
            "windows_improved": sum(1 for row in rows.values() if row["expected_value_score_delta"] > 0),
            "windows_regressed": sum(1 for row in rows.values() if row["expected_value_score_delta"] < 0),
            "ev_delta_sum": round(sum(row["expected_value_score_delta"] for row in rows.values()), 4),
            "pnl_delta_sum": round(sum(row["total_pnl_delta"] for row in rows.values()), 2),
            "max_drawdown_delta_max": max(row["max_drawdown_pct_delta"] for row in rows.values()),
            "late_strong_ev_delta": rows["late_strong"]["expected_value_score_delta"],
            "mid_weak_ev_delta": rows["mid_weak"]["expected_value_score_delta"],
            "old_thin_ev_delta": rows["old_thin"]["expected_value_score_delta"],
            "breakout_deferred_delta_sum": sum(row["breakout_deferred_delta"] for row in rows.values()),
        }

    best_key = max(
        aggregate,
        key=lambda key: (
            aggregate[key]["windows_improved"],
            -aggregate[key]["windows_regressed"],
            aggregate[key]["ev_delta_sum"],
        ),
    )
    best = aggregate[best_key]
    decision = (
        "accepted_default_off_research_harness"
        if (
            best["windows_improved"] >= 2
            and best["windows_regressed"] == 0
            and best["ev_delta_sum"] > 0
        )
        else "rejected"
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "hypothesis": (
            "State-conditioned scarce-slot breakout deferral may have a narrow "
            "market-extension threshold that keeps the mid_weak benefit without "
            "damaging late_strong."
        ),
        "single_causal_variable": "scarce-slot breakout deferral market-extension threshold",
        "prior_related_result": {
            "experiment_id": "exp-20260427-021",
            "decision": "rejected",
            "reason": "10% state cap improved mid_weak but materially regressed late_strong.",
        },
        "thresholds": THRESHOLDS,
        "windows": WINDOWS,
        "metrics": metrics,
        "comparisons_vs_current_default": comparisons,
        "aggregate": aggregate,
        "best_threshold_variant": best_key,
        "decision": decision,
        "strategy_behavior_changed": False,
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"Best variant: {best_key} -> {best}")
    print(f"Decision: {decision}")
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

