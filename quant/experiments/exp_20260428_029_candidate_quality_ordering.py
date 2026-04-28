"""exp-20260428-029 candidate quality ordering sweep.

Experiment-only alpha search. Recent allocation work showed global cap/heat
changes are either accepted already or too small. This tests one different
capital-allocation variable: when same-day candidates compete for scarce entry
slots, should the entry planner preserve the existing order or sort the full
candidate list by an existing quality score before slot slicing?

Only the entry candidate ordering changes. Signal generation, risk multipliers,
entry/exit rules, gap cancels, add-ons, caps, LLM/news replay, and earnings
remain locked.
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

import backtester as bt  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260428-029"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260428_029_candidate_quality_ordering.json"

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
    ("baseline_native_order", "baseline"),
    ("tqs_desc_order", "tqs_desc"),
    ("confidence_desc_order", "confidence_desc"),
])


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    entry = result.get("entry_execution_attribution") or {}
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


def _ranked(signals: list[dict], ordering: str) -> list[dict]:
    signals = list(signals or [])
    if ordering == "baseline":
        return signals
    if ordering == "tqs_desc":
        return sorted(
            signals,
            key=lambda s: (
                s.get("trade_quality_score")
                if s.get("trade_quality_score") is not None else float("-inf"),
                s.get("confidence_score") or 0,
                (s.get("conditions_met") or {}).get("pct_from_52w_high", float("-inf")),
            ),
            reverse=True,
        )
    if ordering == "confidence_desc":
        return sorted(
            signals,
            key=lambda s: (
                s.get("confidence_score") or 0,
                s.get("trade_quality_score")
                if s.get("trade_quality_score") is not None else float("-inf"),
                (s.get("conditions_met") or {}).get("pct_from_52w_high", float("-inf")),
            ),
            reverse=True,
        )
    raise ValueError(f"Unknown ordering: {ordering}")


def _run_window(universe: list[str], cfg: dict, ordering: str) -> dict:
    original_plan_entry_candidates = bt.plan_entry_candidates

    def ordered_plan_entry_candidates(signals, *args, **kwargs):
        ordered = _ranked(signals, ordering)
        return original_plan_entry_candidates(ordered, *args, **kwargs)

    bt.plan_entry_candidates = ordered_plan_entry_candidates
    try:
        engine = BacktestEngine(
            universe=universe,
            start=cfg["start"],
            end=cfg["end"],
            config={"REGIME_AWARE_EXIT": True},
            replay_llm=False,
            replay_news=False,
            data_dir=str(REPO_ROOT / "data"),
            ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
        )
        result = engine.run()
    finally:
        bt.plan_entry_candidates = original_plan_entry_candidates

    if "error" in result:
        raise RuntimeError(result["error"])
    return {
        "metrics": _metrics(result),
        "trades": result.get("trades", []),
        "entry_execution_attribution": result.get("entry_execution_attribution"),
    }


def run_experiment() -> dict:
    universe = get_universe()
    rows = []
    for label, cfg in WINDOWS.items():
        for variant, ordering in VARIANTS.items():
            result = _run_window(universe, cfg, ordering)
            rows.append({
                "window": label,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "state_note": cfg["state_note"],
                "variant": variant,
                "ordering": ordering,
                **result,
            })
            m = result["metrics"]
            print(
                f"[{label} {variant}] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                f"DD={m['max_drawdown_pct']} WR={m['win_rate']} "
                f"trades={m['trade_count']}"
            )

    baseline_rows = {
        label: next(
            r for r in rows
            if r["window"] == label and r["variant"] == "baseline_native_order"
        )
        for label in WINDOWS
    }

    summary = OrderedDict()
    for variant in ("tqs_desc_order", "confidence_desc_order"):
        by_window = OrderedDict()
        for label in WINDOWS:
            baseline = baseline_rows[label]
            candidate = next(r for r in rows if r["window"] == label and r["variant"] == variant)
            by_window[label] = {
                "before": baseline["metrics"],
                "after": candidate["metrics"],
                "delta": _delta(candidate["metrics"], baseline["metrics"]),
            }
        baseline_total_pnl = round(sum(v["before"]["total_pnl"] for v in by_window.values()), 2)
        total_pnl_delta = round(sum(v["delta"]["total_pnl"] for v in by_window.values()), 2)
        summary[variant] = {
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
            "When same-day candidates compete for scarce entry slots, globally "
            "ranking by existing trade_quality_score may allocate capital to "
            "higher-expectancy candidates without changing entries or risk limits."
        ),
        "change_type": "alpha_search_candidate_quality_ordering",
        "parameters": {
            "single_causal_variable": "entry candidate ordering key before slot slicing",
            "baseline_ordering": "native order after existing breakout-only 52w-high rerank",
            "tested_ordering": ["trade_quality_score descending", "confidence_score descending"],
            "locked_variables": [
                "signal generation",
                "risk multipliers",
                "MAX_POSITION_PCT",
                "MAX_PORTFOLIO_HEAT",
                "MAX_PER_SECTOR",
                "all exits",
                "upside/adverse gap cancels",
                "day-2 add-on trigger and fraction",
                "add-on max position cap",
                "scarce-slot breakout deferral semantics",
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
            **{
                label: best_summary["by_window"][label]["after"]
                for label in WINDOWS
            },
        },
        "delta_metrics": {
            "best_variant": best_variant,
            **{
                label: best_summary["by_window"][label]["delta"]
                for label in WINDOWS
            },
            "aggregate": best_agg,
            "gate4_basis": (
                "Accepted because the best ordering improved all fixed windows and passed Gate 4."
                if accepted else
                "Rejected because no quality-ordering variant passed the fixed-window Gate 4 checks."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft ranking remains sample-limited, so this deterministic "
                "candidate-ordering alpha was tested instead."
            ),
        },
        "rows": rows,
        "summary": summary,
        "rejection_reason": (
            None if accepted else
            "Existing quality/confidence scores did not improve scarce-slot allocation robustly."
        ),
        "next_retry_requires": [
            "Do not retry simple global TQS/confidence ordering without a new discriminator.",
            "A valid retry needs state-specific or event-backed ordering evidence.",
            "Do not combine this with cap, heat, or gap-cancel changes without separate evidence.",
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
        "best_aggregate": payload["delta_metrics"]["aggregate"],
        "artifact": str(OUT_JSON),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
