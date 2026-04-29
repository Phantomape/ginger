"""exp-20260428-032: state-gated scarce-slot breakout deferral.

Alpha search. The current production policy defers every breakout_long signal
when only one entry slot remains. This tests whether that deferral should be
state-gated by the weaker of SPY/QQQ distance from its moving average, using
the shared production_parity planner parameter that production can also call.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260428-032"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260428_032_state_gated_breakout_deferral.json"

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
])

VARIANTS = OrderedDict([
    ("baseline_always_defer", None),
    ("defer_when_min_index_le_0pct", 0.00),
    ("defer_when_min_index_le_3pct", 0.03),
    ("defer_when_min_index_le_5pct", 0.05),
    ("defer_when_min_index_le_8pct", 0.08),
])


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    entry = result.get("entry_execution_attribution") or {}
    scarce = result.get("scarce_slot_attribution") or {}
    addon = result.get("addon_attribution") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "tail_loss_share": result.get("tail_loss_share"),
        "addon_executed": addon.get("executed"),
        "breakout_deferred": scarce.get("breakout_deferred"),
        "entry_reason_counts": entry.get("reason_counts", {}),
    }


def _delta(after: dict, before: dict) -> dict:
    out = {}
    for key, before_value in before.items():
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            out[key] = round(after_value - before_value, 6)
        else:
            out[key] = None
    return out


def _run_window(universe: list[str], cfg: dict, threshold: float | None) -> dict:
    config = {
        "REGIME_AWARE_EXIT": True,
        "DEFER_BREAKOUT_MAX_MIN_INDEX_PCT_FROM_MA": threshold,
    }
    engine = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config=config,
        replay_llm=False,
        replay_news=False,
        data_dir=str(REPO_ROOT / "data"),
        ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(result["error"])
    return {
        "metrics": _metrics(result),
        "scarce_slot_attribution": result.get("scarce_slot_attribution"),
        "entry_execution_attribution": result.get("entry_execution_attribution"),
    }


def run_experiment() -> dict:
    universe = get_universe()
    rows = []
    for label, cfg in WINDOWS.items():
        for variant, threshold in VARIANTS.items():
            result = _run_window(universe, cfg, threshold)
            rows.append({
                "window": label,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "state_note": cfg["state_note"],
                "variant": variant,
                "defer_breakout_max_min_index_pct_from_ma": threshold,
                **result,
            })
            m = result["metrics"]
            print(
                f"[{label} {variant}] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                f"DD={m['max_drawdown_pct']} WR={m['win_rate']} "
                f"trades={m['trade_count']} deferred={m['breakout_deferred']}"
            )

    baseline_rows = {
        label: next(
            row for row in rows
            if row["window"] == label and row["variant"] == "baseline_always_defer"
        )
        for label in WINDOWS
    }
    summary = OrderedDict()
    for variant in VARIANTS:
        if variant == "baseline_always_defer":
            continue
        by_window = OrderedDict()
        for label in WINDOWS:
            before = baseline_rows[label]["metrics"]
            after = next(
                row["metrics"] for row in rows
                if row["window"] == label and row["variant"] == variant
            )
            by_window[label] = {
                "before": before,
                "after": after,
                "delta": _delta(after, before),
            }

        baseline_total_pnl = round(sum(v["before"]["total_pnl"] for v in by_window.values()), 2)
        total_pnl_delta = round(sum(v["delta"]["total_pnl"] for v in by_window.values()), 2)
        summary[variant] = {
            "threshold": VARIANTS[variant],
            "by_window": by_window,
            "aggregate": {
                "expected_value_score_delta_sum": round(
                    sum(v["delta"]["expected_value_score"] for v in by_window.values()),
                    6,
                ),
                "total_pnl_delta_sum": total_pnl_delta,
                "baseline_total_pnl_sum": baseline_total_pnl,
                "total_pnl_delta_pct": (
                    round(total_pnl_delta / baseline_total_pnl, 6)
                    if baseline_total_pnl else None
                ),
                "windows_improved": sum(
                    1 for v in by_window.values()
                    if v["delta"]["expected_value_score"] > 0
                ),
                "windows_regressed": sum(
                    1 for v in by_window.values()
                    if v["delta"]["expected_value_score"] < 0
                ),
                "max_drawdown_delta_max": max(
                    v["delta"]["max_drawdown_pct"] for v in by_window.values()
                ),
                "trade_count_delta_sum": sum(v["delta"]["trade_count"] for v in by_window.values()),
                "win_rate_delta_min": min(v["delta"]["win_rate"] for v in by_window.values()),
                "breakout_deferred_delta_sum": sum(
                    v["delta"]["breakout_deferred"] for v in by_window.values()
                ),
            },
        }

    best_variant, best_summary = max(
        summary.items(),
        key=lambda item: (
            item[1]["aggregate"]["windows_improved"],
            -item[1]["aggregate"]["windows_regressed"],
            item[1]["aggregate"]["expected_value_score_delta_sum"],
            item[1]["aggregate"]["total_pnl_delta_sum"],
        ),
    )
    best_agg = best_summary["aggregate"]
    accepted = (
        best_agg["windows_improved"] == 3
        and best_agg["windows_regressed"] == 0
        and (
            best_agg["expected_value_score_delta_sum"] > 0.10
            or best_agg["total_pnl_delta_pct"] > 0.05
            or best_agg["max_drawdown_delta_max"] < -0.01
            or (best_agg["trade_count_delta_sum"] > 0 and best_agg["win_rate_delta_min"] >= 0)
        )
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted" if accepted else "rejected",
        "decision": "accepted" if accepted else "rejected",
        "hypothesis": (
            "Scarce-slot breakout deferral may be more profitable if it only "
            "fires when the weaker of SPY/QQQ is not far above its moving "
            "average, avoiding unnecessary breakout suppression in strong tape."
        ),
        "change_summary": (
            "Tested state-gated values for the existing shared "
            "DEFER_BREAKOUT_MAX_MIN_INDEX_PCT_FROM_MA planner parameter across "
            "the three fixed OHLCV windows. Production defaults are unchanged "
            "unless Gate 4 passes."
        ),
        "change_type": "alpha_search_state_gated_slot_routing",
        "component": (
            "quant/experiments/exp_20260428_032_state_gated_breakout_deferral.py"
        ),
        "parameters": {
            "single_causal_variable": "state-gated scarce-slot breakout deferral",
            "baseline": {
                "DEFER_BREAKOUT_WHEN_SLOTS_LTE": 1,
                "DEFER_BREAKOUT_MAX_MIN_INDEX_PCT_FROM_MA": None,
            },
            "tested_thresholds": {
                name: value for name, value in VARIANTS.items()
                if name != "baseline_always_defer"
            },
            "locked_variables": [
                "signal generation",
                "risk multipliers",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_POSITIONS",
                "MAX_PER_SECTOR",
                "all exits",
                "upside/adverse gap cancels",
                "day-2 add-on trigger and fraction",
                "add-on max position cap",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "date_range": {
            "start": WINDOWS["late_strong"]["start"],
            "end": WINDOWS["late_strong"]["end"],
        },
        "secondary_windows": [
            {"start": WINDOWS["mid_weak"]["start"], "end": WINDOWS["mid_weak"]["end"]},
            {"start": WINDOWS["old_thin"]["start"], "end": WINDOWS["old_thin"]["end"]},
        ],
        "market_regime_summary": {
            label: cfg["state_note"] for label, cfg in WINDOWS.items()
        },
        "before_metrics": {
            label: baseline_rows[label]["metrics"] for label in WINDOWS
        },
        "after_metrics": {
            "best_variant": best_variant,
            "best_threshold": best_summary["threshold"],
            **{
                label: best_summary["by_window"][label]["after"]
                for label in WINDOWS
            },
        },
        "delta_metrics": {
            "best_variant": best_variant,
            "best_threshold": best_summary["threshold"],
            **{
                label: best_summary["by_window"][label]["delta"]
                for label in WINDOWS
            },
            "aggregate": best_agg,
            "gate4_basis": (
                "Accepted because the best state-gated threshold improved all fixed windows and passed Gate 4."
                if accepted else
                "Rejected because no state-gated threshold passed fixed-window Gate 4."
            ),
        },
        "production_impact": {
            "shared_policy_changed": accepted,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft ranking remains sample-limited, so this deterministic "
                "state-routing alpha was tested instead."
            ),
        },
        "rows": rows,
        "summary": summary,
        "rejection_reason": None if accepted else (
            "Index-distance gating of scarce-slot breakout deferral did not "
            "improve allocation robustly enough for promotion."
        ),
        "next_retry_requires": [
            "Do not retry nearby global index-distance thresholds without a new discriminator.",
            "A valid retry needs a more explanatory state source, such as breadth/dispersion or event-backed breakout confirmation.",
            "Keep the current always-on one-slot breakout deferral unchanged unless a future state-routing replay passes all windows.",
        ],
    }


def main() -> int:
    payload = run_experiment()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "best_variant": payload["delta_metrics"]["best_variant"],
        "best_threshold": payload["delta_metrics"]["best_threshold"],
        "best_aggregate": payload["delta_metrics"]["aggregate"],
        "artifact": str(OUT_JSON),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
