"""exp-20260428-030 scarce-slot breakout exception replay.

Experiment-only alpha search. The current accepted scarce-slot policy defers
all breakout_long entries when only one entry slot remains. This tests a
narrower candidate-level exception: allow only the strongest breakout candidates
to compete for that last slot, while keeping signal generation, sizing, exits,
gap cancels, add-ons, and all capital limits unchanged.
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


EXPERIMENT_ID = "exp-20260428-030"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260428_030_scarce_slot_breakout_exception.json"

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
    ("baseline_current_deferral", {"exception": "none", "disable_deferral": False}),
    ("diagnostic_no_deferral", {"exception": "none", "disable_deferral": True}),
    ("high_tqs_breakout_exception", {"exception": "high_tqs", "disable_deferral": False}),
    ("near_high_breakout_exception", {"exception": "near_high", "disable_deferral": False}),
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


def _pct_from_52w_high(sig: dict) -> float | None:
    value = sig.get("pct_from_52w_high")
    if value is None:
        value = (sig.get("conditions_met") or {}).get("pct_from_52w_high")
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _is_exception(sig: dict, exception: str) -> bool:
    if sig.get("strategy") != "breakout_long":
        return False
    if exception == "high_tqs":
        tqs = sig.get("trade_quality_score")
        return tqs is not None and float(tqs) >= 0.95
    if exception == "near_high":
        pct = _pct_from_52w_high(sig)
        return pct is not None and pct >= -0.03
    return False


def _exception_plan_entry_candidates(signals, *args, exception="none", **kwargs):
    original_plan = _exception_plan_entry_candidates.original_plan
    if exception == "none":
        return original_plan(signals, *args, **kwargs)

    input_signals = list(signals or [])
    exempt = [sig for sig in input_signals if _is_exception(sig, exception)]
    if not exempt:
        return original_plan(input_signals, *args, **kwargs)

    placeholder = {
        **kwargs,
        "defer_breakout_when_slots_lte": None,
        "defer_breakout_max_min_index_pct_from_ma": None,
    }
    planned, plan = original_plan(input_signals, *args, **placeholder)
    slots = plan.get("available_slots", 0)
    if slots <= 0:
        return planned, plan

    kept = []
    deferred = []
    for sig in input_signals:
        if sig.get("strategy") == "breakout_long" and not _is_exception(sig, exception):
            deferred.append({
                "ticker": sig.get("ticker"),
                "strategy": sig.get("strategy"),
                "sector": sig.get("sector", "Unknown"),
                "available_slots": slots,
                "trade_quality_score": sig.get("trade_quality_score"),
                "confidence_score": sig.get("confidence_score"),
                "pct_from_52w_high": _pct_from_52w_high(sig),
                "entry_price": sig.get("entry_price"),
                "stop_price": sig.get("stop_price"),
                "target_price": sig.get("target_price"),
                "exception_rule": exception,
            })
        else:
            kept.append(sig)

    slot_sliced = kept[slots:] if slots >= 0 else kept
    planned = kept[:slots]
    plan.update({
        "signals_after_deferral": len(kept),
        "signals_after_entry_plan": len(planned),
        "deferred_breakout_signals": deferred,
        "slot_sliced_signals": slot_sliced,
        "breakout_exception_rule": exception,
    })
    return planned, plan


def _run_window(universe: list[str], cfg: dict, variant: dict) -> dict:
    original_plan_entry_candidates = bt.plan_entry_candidates
    config = {"REGIME_AWARE_EXIT": True}
    if variant["disable_deferral"]:
        config["DEFER_BREAKOUT_WHEN_SLOTS_LTE"] = None
    if variant["exception"] != "none":
        _exception_plan_entry_candidates.original_plan = original_plan_entry_candidates

        def patched(signals, *args, **kwargs):
            return _exception_plan_entry_candidates(
                signals,
                *args,
                exception=variant["exception"],
                **kwargs,
            )

        bt.plan_entry_candidates = patched

    try:
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
    finally:
        bt.plan_entry_candidates = original_plan_entry_candidates

    if "error" in result:
        raise RuntimeError(result["error"])
    return {
        "metrics": _metrics(result),
        "trades": result.get("trades", []),
        "scarce_slot_attribution": result.get("scarce_slot_attribution"),
        "entry_execution_attribution": result.get("entry_execution_attribution"),
    }


def run_experiment() -> dict:
    universe = get_universe()
    rows = []
    for label, cfg in WINDOWS.items():
        for variant_name, variant in VARIANTS.items():
            result = _run_window(universe, cfg, variant)
            rows.append({
                "window": label,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "state_note": cfg["state_note"],
                "variant": variant_name,
                "variant_config": variant,
                **result,
            })
            m = result["metrics"]
            print(
                f"[{label} {variant_name}] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                f"DD={m['max_drawdown_pct']} WR={m['win_rate']} "
                f"trades={m['trade_count']} deferred={m['breakout_deferred']}"
            )

    baseline_rows = {
        label: next(
            r for r in rows
            if r["window"] == label and r["variant"] == "baseline_current_deferral"
        )
        for label in WINDOWS
    }

    summary = OrderedDict()
    for variant_name in VARIANTS:
        if variant_name == "baseline_current_deferral":
            continue
        by_window = OrderedDict()
        for label in WINDOWS:
            baseline = baseline_rows[label]
            candidate = next(r for r in rows if r["window"] == label and r["variant"] == variant_name)
            by_window[label] = {
                "before": baseline["metrics"],
                "after": candidate["metrics"],
                "delta": _delta(candidate["metrics"], baseline["metrics"]),
            }
        baseline_total_pnl = round(sum(v["before"]["total_pnl"] for v in by_window.values()), 2)
        total_pnl_delta = round(sum(v["delta"]["total_pnl"] for v in by_window.values()), 2)
        summary[variant_name] = {
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
            "Candidate-level exceptions to one-slot scarce breakout deferral may "
            "recover high-quality breakout winners without reopening global "
            "candidate ordering, global capacity, or broad breakout de-risking."
        ),
        "change_type": "alpha_search_scarce_slot_breakout_exception",
        "parameters": {
            "single_causal_variable": "candidate-level exception to scarce-slot breakout deferral",
            "baseline": {
                "DEFER_BREAKOUT_WHEN_SLOTS_LTE": 1,
                "DEFER_BREAKOUT_MAX_MIN_INDEX_PCT_FROM_MA": None,
            },
            "tested_variants": {
                "diagnostic_no_deferral": "disable one-slot breakout deferral",
                "high_tqs_breakout_exception": "allow deferred breakout_long if trade_quality_score >= 0.95",
                "near_high_breakout_exception": "allow deferred breakout_long if pct_from_52w_high >= -0.03",
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
                "Accepted because the best exception improved all fixed windows and passed Gate 4."
                if accepted else
                "Rejected because no candidate-level breakout exception passed fixed-window Gate 4."
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
                "candidate-level scarce-slot allocation alpha was tested instead."
            ),
        },
        "rows": rows,
        "summary": summary,
        "rejection_reason": (
            None if accepted else
            "The tested breakout exceptions did not improve scarce-slot allocation robustly."
        ),
        "next_retry_requires": [
            "Do not retry candidate-level scarce-slot breakout exceptions based only on TQS or 52-week proximity.",
            "A valid retry needs a genuinely orthogonal event/state source, not another score-only deferral exception.",
            "Keep the accepted one-slot scarce-slot breakout deferral unchanged unless a future replay passes all three windows.",
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
