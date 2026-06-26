"""exp-20260625-024: moomoo short-volume toxic-Q5 notional down-weight.

This is the materially different gate shape left open after exp-20260625-019:
keep every accepted source-priority allocator row, but cut paper notional on
rows whose point-in-time per-ticker moomoo short_volume_ratio percentile is in
the toxic highest quintile. No live/default orders are changed.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260625_019_moomoo_short_volume_clean_flow_gate as prior_clean_flow  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from short_volume_clean_flow_gate import (  # noqa: E402
    DEFAULT_SHORT_VOLUME_ROWS,
    DEFAULT_TOXIC_QUINTILE_INDEX,
    RULE_VERSION as CLEAN_FLOW_RULE_VERSION,
    annotate_candidate,
    build_short_volume_percentile_index,
    load_short_volume_ratio_history,
)


framework = prior_clean_flow.framework

EXPERIMENT_ID = "exp-20260625-024"
OWNER = "alpha-explore"
SLUG = "moomoo_short_volume_notional_downweight"
RUNNER = f"quant/experiments/exp_20260625_024_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260625_024_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

SCALAR_RULE_VERSION = "short_volume_toxic_q5_notional_downweight_v1"
TOXIC_NOTIONAL_SCALAR = 0.50
MIN_CHANGED_TRADES = 9
MIN_CHANGED_WINDOWS = 2
MIN_EV_IMPROVED_WINDOWS = 2
MAX_EV_REGRESSED_WINDOWS = 0
MAX_DRAWDOWN_WORSE = 0.005
MIN_SCALAR_RETUNE_EV_DELTA_PCT = 0.10
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

HYPOTHESIS = (
    "A PIT Moomoo short-volume toxic-quintile notional down-weight over "
    "accepted allocator rows may preserve winners while reducing informed "
    "short-flow risk better than the rejected hard exclusion."
)
CHANGED_VARIABLE = (
    "moomoo_daily_short_volume_toxic_q5_notional_downweight_over_accepted_allocator_v1"
)
TRIAL_FAMILY = "toxic_q5_notional_downweight"
TRIAL_VARIANT_ID = "scalar_0p50"
NEW_EVIDENCE_AXIS = (
    "Materially different gate shape explicitly left open by the current "
    "playbook: scale toxic-Q5 accepted allocator rows' paper notional instead "
    "of excluding or replacing them; this is not a quintile, lookback, hold, "
    "top-N, source-priority, or threshold retune of the rejected hard-exclusion "
    "policy."
)
PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.25,
    "expected_pnl_delta": 2500.0,
    "main_failure_modes": [
        "toxic rows are net profitable",
        "drawdown not improved",
        "old_thin or mid_weak regression",
        "EV lift below scalar-retune bar",
    ],
    "confidence_reason": (
        "exp-20260625-018 made sign-correct short-volume avoidance plausible, "
        "while exp-20260625-019 showed hard exclusion may destroy replacement "
        "value; down-weighting is a materially different gate shape that keeps "
        "selected rows but reduces toxic-flow exposure."
    ),
    "recorded_at": "2026-06-25T22:07:13+00:00",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(framework.sleeve._safe(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    kept: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if not line.strip():
                continue
            try:
                existing = json.loads(line)
            except json.JSONDecodeError:
                kept.append(line)
                continue
            if existing.get("experiment_id") != record["experiment_id"]:
                kept.append(json.dumps(existing, sort_keys=True))
    kept.append(json.dumps(record, sort_keys=True))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _round(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round(number, digits) if math.isfinite(number) else None


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _counter_dict(counter: Counter[str]) -> dict[str, int]:
    return {key: int(value) for key, value in sorted(counter.items())}


def apply_notional_downweight(
    rows: list[dict[str, Any]],
    percentile_index: dict[str, tuple[list[str], list[float | None]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Preserve all rows and scale paper PnL/notional for toxic-Q5 rows."""

    output: list[dict[str, Any]] = []
    scaled_rows: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()
    quintile_counts: Counter[str] = Counter()
    total_unscaled_toxic_pnl = 0.0
    total_scaled_toxic_pnl = 0.0

    for row in rows:
        annotated = annotate_candidate(row, percentile_index)
        q = annotated.get("short_volume_ratio_quintile")
        toxic = q == DEFAULT_TOXIC_QUINTILE_INDEX
        scalar = TOXIC_NOTIONAL_SCALAR if toxic else 1.0
        reason = "toxic_q5_downweighted" if toxic else "notional_unchanged"
        if q is None:
            quintile_counts["missing"] += 1
        else:
            quintile_counts[f"Q{int(q) + 1}"] += 1
        reason_counts[reason] += 1

        out = dict(annotated)
        out.update(
            {
                "short_volume_notional_scalar_rule_version": SCALAR_RULE_VERSION,
                "short_volume_notional_scalar": scalar,
                "short_volume_notional_scalar_reason": reason,
                "short_volume_notional_scalar_basis": (
                    "entry-date PIT short_volume_ratio quintile is Q5"
                    if toxic
                    else "missing or non-toxic PIT short_volume_ratio quintile"
                ),
            }
        )
        if toxic:
            original_pnl = _float_or_none(out.get("pnl"))
            if original_pnl is not None:
                scaled_pnl = round(original_pnl * scalar, 2)
                out["unscaled_pnl"] = round(original_pnl, 2)
                out["pnl"] = scaled_pnl
                out["short_volume_notional_scaled_pnl_delta"] = round(
                    scaled_pnl - original_pnl,
                    2,
                )
                total_unscaled_toxic_pnl += original_pnl
                total_scaled_toxic_pnl += scaled_pnl
            original_notional = _float_or_none(out.get("paper_notional_usd"))
            if original_notional is not None:
                out["unscaled_paper_notional_usd"] = round(original_notional, 2)
                out["paper_notional_usd"] = round(original_notional * scalar, 2)
            scaled_rows.append(out)
        output.append(out)

    audit = {
        "rule_version": SCALAR_RULE_VERSION,
        "input_count": len(rows),
        "output_count": len(output),
        "scaled_count": len(scaled_rows),
        "unchanged_count": len(output) - len(scaled_rows),
        "toxic_quintile_index": DEFAULT_TOXIC_QUINTILE_INDEX,
        "toxic_quintile_label": f"Q{DEFAULT_TOXIC_QUINTILE_INDEX + 1}",
        "toxic_notional_scalar": TOXIC_NOTIONAL_SCALAR,
        "missing_percentile_scalar": 1.0,
        "reason_counts": _counter_dict(reason_counts),
        "quintile_counts": _counter_dict(quintile_counts),
        "total_unscaled_toxic_pnl": round(total_unscaled_toxic_pnl, 2),
        "total_scaled_toxic_pnl": round(total_scaled_toxic_pnl, 2),
        "total_scalar_pnl_delta": round(
            total_scaled_toxic_pnl - total_unscaled_toxic_pnl,
            2,
        ),
    }
    return output, scaled_rows, audit


def candidate_universe_from_sector_entries(
    sector_entries: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "status": "window_sector_known_universe",
        "tickers": sorted(sector_entries),
        "records": sector_entries,
    }


def gate4(
    *,
    aggregate: dict[str, Any],
    core_aggregate: dict[str, Any],
    scaled_summary: dict[str, Any],
    downweighted_summary: dict[str, Any],
    ungated_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    changed_windows = scaled_summary["windows_with_target_trades"]
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    downweighted_single_share = downweighted_summary["max_single_positive_pnl_share"]
    downweighted_hhi = downweighted_summary["positive_pnl_hhi"]
    ungated_single_share = ungated_summary["max_single_positive_pnl_share"]
    ungated_hhi = ungated_summary["positive_pnl_hhi"]
    ev_delta_pct = aggregate.get("expected_value_score_delta_pct")

    failed: list[str] = []
    if float(aggregate["expected_value_score_delta_sum"] or 0.0) <= 0.0:
        failed.append("notional_scalar_ev_delta_not_positive_vs_ungated_allocator")
    if float(aggregate["total_pnl_delta_sum"] or 0.0) <= 0.0:
        failed.append("notional_scalar_pnl_delta_not_positive_vs_ungated_allocator")
    if ev_delta_pct is None or float(ev_delta_pct) <= MIN_SCALAR_RETUNE_EV_DELTA_PCT:
        failed.append("notional_scalar_ev_lift_below_10pct_retune_bar")
    if int(aggregate["windows_ev_improved"] or 0) < MIN_EV_IMPROVED_WINDOWS:
        failed.append("fewer_than_two_ev_improved_windows_vs_ungated")
    if int(aggregate["windows_ev_regressed"] or 0) > MAX_EV_REGRESSED_WINDOWS:
        failed.append("window_ev_regression_vs_ungated")
    if scaled_summary["total_trade_count"] < MIN_CHANGED_TRADES:
        failed.append("changed_sample_too_small")
    if len(changed_windows) < MIN_CHANGED_WINDOWS:
        failed.append("changed_window_coverage_too_small")
    if float(aggregate["max_drawdown_delta_max"] or 0.0) > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high_vs_ungated")
    if float(core_aggregate["expected_value_score_delta_sum"] or 0.0) <= 0.0:
        failed.append("downweighted_overlay_not_positive_ev_vs_core")
    if float(core_aggregate["total_pnl_delta_sum"] or 0.0) <= 0.0:
        failed.append("downweighted_overlay_not_positive_pnl_vs_core")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")

    concentration_cap_passed = (
        downweighted_single_share is not None
        and downweighted_single_share <= MAX_SINGLE_POSITIVE_SHARE
        and downweighted_hhi is not None
        and downweighted_hhi <= MAX_POSITIVE_HHI
    )
    concentration_not_worse = (
        downweighted_single_share is not None
        and ungated_single_share is not None
        and downweighted_single_share <= ungated_single_share + 1e-12
        and downweighted_hhi is not None
        and ungated_hhi is not None
        and downweighted_hhi <= ungated_hhi + 1e-12
    )
    if not concentration_cap_passed:
        failed.append("downweighted_target_concentration_failed")
    if not concentration_not_worse:
        failed.append("downweighted_target_concentration_worse_than_ungated")

    passed = not failed
    return {
        "passed": passed,
        "decision": (
            "observed_replay_positive_moomoo_short_volume_notional_downweight"
            if passed
            else "rejected_moomoo_short_volume_notional_downweight"
        ),
        "failed_reasons": failed,
        "aggregate_ev_delta_vs_ungated": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta_vs_ungated": aggregate["total_pnl_delta_sum"],
        "aggregate_ev_delta_pct_vs_ungated": ev_delta_pct,
        "aggregate_ev_delta_vs_core": core_aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta_vs_core": core_aggregate["total_pnl_delta_sum"],
        "windows_ev_improved_vs_ungated": aggregate["windows_ev_improved"],
        "windows_ev_regressed_vs_ungated": aggregate["windows_ev_regressed"],
        "windows_pnl_improved_vs_ungated": aggregate["windows_pnl_improved"],
        "windows_pnl_regressed_vs_ungated": aggregate["windows_pnl_regressed"],
        "changed_trade_count": scaled_summary["total_trade_count"],
        "changed_trade_count_min": MIN_CHANGED_TRADES,
        "changed_windows": changed_windows,
        "changed_window_count_min": MIN_CHANGED_WINDOWS,
        "max_drawdown_worse_vs_ungated": aggregate["max_drawdown_delta_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "minimum_core_survival_rate": round(min_survival, 6),
        "survival_guard_passed": min_survival >= 0.05,
        "scalar_retune_ev_delta_pct_guardrail": MIN_SCALAR_RETUNE_EV_DELTA_PCT,
        "target_concentration": {
            "passed": concentration_cap_passed and concentration_not_worse,
            "cap_passed": concentration_cap_passed,
            "not_worse_than_ungated": concentration_not_worse,
            "downweighted_max_single_positive_pnl_share": downweighted_single_share,
            "ungated_max_single_positive_pnl_share": ungated_single_share,
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "downweighted_positive_pnl_hhi": downweighted_hhi,
            "ungated_positive_pnl_hhi": ungated_hhi,
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
        },
        "acceptance_rule": (
            "Binding Gate 4 compares the downweighted allocator against the "
            "current ungated accepted allocator. It must improve aggregate EV "
            "and PnL, clear the >10% EV-lift bar for a notional/capital "
            "allocation scalar trial, improve EV in at least two canonical "
            "windows with zero EV regressions, affect at least nine rows across "
            "at least two windows, keep drawdown drift <=0.5pp, remain positive "
            "versus the core baseline, and not worsen target concentration."
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    short_volume_history, short_volume_audit = load_short_volume_ratio_history()
    percentile_index = build_short_volume_percentile_index(short_volume_history)

    universe = sorted(prior_clean_flow.get_universe())
    sector_entries = framework._load_sector_entries()
    before_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    ungated_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    downweighted_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    delta_vs_ungated_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    delta_vs_core_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    ungated_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    downweighted_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    scaled_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    helper_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    scalar_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    window_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] moomoo short-volume toxic-Q5 notional downweight")
        before_result = framework.shadow._run_baseline(universe, cfg)
        core = framework.overlay_helper._metrics(before_result)
        snapshot = framework._load_window_snapshot(
            cfg=cfg,
            eligible_tickers=set(sector_entries),
        )
        window_sector_entries = {
            ticker: meta for ticker, meta in sector_entries.items() if ticker in snapshot
        }
        candidate_universe = candidate_universe_from_sector_entries(window_sector_entries)
        core_entries = framework.shadow._baseline_entries(before_result)
        ungated_trades, helper_audit = (
            prior_clean_flow.build_accepted_helper_source_priority_allocator_historical_trades(
                ohlcv_by_ticker=snapshot,
                core_entries_by_date=core_entries,
                windows=OrderedDict([(label, cfg)]),
                candidate_universe=candidate_universe,
                sector_entries=window_sector_entries,
                calendar_dates=framework.shadow._trading_dates(snapshot),
            )
        )
        downweighted_trades, scaled_trades, scalar_audit = apply_notional_downweight(
            ungated_trades,
            percentile_index,
        )
        ungated_overlay = framework.sleeve._overlay_from_paper_trades(
            before_result,
            ungated_trades,
        )
        downweighted_overlay = framework.sleeve._overlay_from_paper_trades(
            before_result,
            downweighted_trades,
        )
        ungated = framework.overlay_helper._metrics_with_overlay(before_result, ungated_overlay)
        downweighted = framework.overlay_helper._metrics_with_overlay(
            before_result,
            downweighted_overlay,
        )
        delta_vs_ungated = framework.overlay_helper._delta(downweighted, ungated)
        delta_vs_core = framework.overlay_helper._delta(downweighted, core)

        before_metrics[label] = core
        ungated_metrics[label] = ungated
        downweighted_metrics[label] = downweighted
        delta_vs_ungated_rows[label] = {
            "before": ungated,
            "after": downweighted,
            "delta": delta_vs_ungated,
            "target_trade_count": len(scaled_trades),
        }
        delta_vs_core_rows[label] = {
            "before": core,
            "after": downweighted,
            "delta": delta_vs_core,
            "target_trade_count": len(downweighted_trades),
        }
        ungated_trades_by_window[label] = ungated_trades
        downweighted_trades_by_window[label] = downweighted_trades
        scaled_trades_by_window[label] = scaled_trades
        helper_audit_by_window[label] = helper_audit
        scalar_audit_by_window[label] = scalar_audit
        window_rows[label] = {
            "core_baseline": core,
            "ungated_allocator": ungated,
            "downweighted_allocator": downweighted,
            "delta_vs_ungated": delta_vs_ungated,
            "delta_vs_core": delta_vs_core,
            "ungated_trade_count": len(ungated_trades),
            "downweighted_trade_count": len(downweighted_trades),
            "scaled_toxic_trade_count": len(scaled_trades),
            "scalar_audit": scalar_audit,
            "selected_source_counts": helper_audit["selected_source_counts_by_window"][label],
        }

    aggregate_vs_ungated = framework._aggregate_window_rows(delta_vs_ungated_rows)
    aggregate_vs_core = framework._aggregate_window_rows(delta_vs_core_rows)
    scaled_summary = framework.sleeve._target_trade_summary(scaled_trades_by_window)
    downweighted_summary = framework.sleeve._target_trade_summary(downweighted_trades_by_window)
    ungated_summary = framework.sleeve._target_trade_summary(ungated_trades_by_window)
    gate = gate4(
        aggregate=aggregate_vs_ungated,
        core_aggregate=aggregate_vs_core,
        scaled_summary=scaled_summary,
        downweighted_summary=downweighted_summary,
        ungated_summary=ungated_summary,
        before_metrics=before_metrics,
    )
    status = "accepted_replay_only" if gate["passed"] else "rejected"
    decision = gate["decision"]
    accepted_alpha = False
    production_impact = {
        "shared_policy_changed": False,
        "shared_policy_note": (
            "This run reuses the existing short-volume PIT annotation helper "
            "but does not add or promote a shared sizing policy."
        ),
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "default_off_paper_only": True,
        "daily_snapshot_exposed": False,
        "parity_test_added": False,
        "trade_enabled": False,
        "alters_orders": False,
        "production_orders_changed": False,
        "production_signal_path_changed": False,
        "production_watchlist_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "uses_llm": False,
        "uses_free_non_ohlcv": True,
        "live_realism_evaluated": True,
        "live_ready": False,
        "execution_envelope": {
            "base_notional_usd": prior_clean_flow.BASE_NOTIONAL_USD,
            "toxic_q5_notional_scalar": TOXIC_NOTIONAL_SCALAR,
            "source_notional_scalars": "same as accepted allocator except toxic-Q5 rows",
            "max_concurrent_positions": prior_clean_flow.EXECUTION_ENVELOPE[
                "max_concurrent_positions"
            ],
            "capital_cap": prior_clean_flow.EXECUTION_ENVELOPE["bucket_notional_usd"],
            "min_avg_dollar_volume_20d": prior_clean_flow.EXECUTION_ENVELOPE[
                "min_avg_dollar_volume_20d"
            ],
            "slippage_model": prior_clean_flow.EXECUTION_ENVELOPE["slippage_model"],
            "order_semantics": prior_clean_flow.EXECUTION_ENVELOPE["order_semantics"],
            "kill_switch": prior_clean_flow.EXECUTION_ENVELOPE["kill_switch_drawdown_pct"],
            "portfolio_displacement": prior_clean_flow.EXECUTION_ENVELOPE[
                "core_displacement"
            ],
            "trade_enabled": False,
        },
    }
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_success": 1.0 if gate["passed"] else 0.0,
        "actual_gate4_passed": gate["passed"],
        "failure_modes_observed": gate["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate["passed"] else 0.0)) ** 2,
            6,
        ),
        "surprise_note": (
            "The down-weight preserved enough replacement value to warrant a shared policy test."
            if gate["passed"]
            else "The notional scalar did not create incremental value over the ungated allocator."
        ),
    }
    post_run_reflection = {
        "why_result_happened": (
            "The toxic-Q5 notional scalar improved the accepted allocator in "
            "the replay screen."
            if gate["passed"]
            else (
                "The toxic-Q5 rows were not costly enough in the accepted "
                "allocator replay for a 50% notional haircut to beat the "
                "ungated policy after EV, PnL, window, drawdown, and "
                "concentration checks."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not rescue this by sweeping the scalar, quintile cutoff, "
            "lookback length, allocator source rank, daily slot count, hold "
            "days, or cooldown on these frozen windows."
        ),
        "new_evidence_required": (
            "A retry needs materially more closed forward accepted-allocator "
            "rows tagged with entry-time short_volume_ratio percentile, true "
            "PIT borrow fee/utilization/loan-availability economics, or a "
            "different non-OHLCV flow field."
        ),
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "owner": OWNER,
        "status": status,
        "decision": decision,
        "accepted": gate["passed"],
        "accepted_alpha": accepted_alpha,
        "hypothesis": HYPOTHESIS,
        "change_type": "capital_allocation_private_replay_scout",
        "implementation_mode": "private_replay_notional_scalar_scout",
        "mechanism_family": "moomoo_short_volume_clean_flow",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": [
            "PIT short-volume percentile annotation",
            "toxic-Q5 paper notional scalar",
            "accepted allocator historical replay",
            "Gate 1-4 verdict",
        ],
        "nearby_prior_experiments": [
            "exp-20260625-018",
            "exp-20260625-019",
            "exp-20260625-023",
        ],
        "new_evidence_type": "new_gate_shape",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "multiple_testing_risk_bucket": "high_allocator_near_neighbor_override",
        "prediction": PREDICTION,
        "calibration": calibration,
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": (
                    "experiment.py new warned on allocator near-neighbors; "
                    "override recorded because this is a materially different "
                    "notional down-weight gate shape, not the rejected hard "
                    "exclusion or a threshold/source-priority retune."
                ),
                "exp-20260625-018": "positive observed-only informed-flow avoidance lead",
                "exp-20260625-019": "rejected hard toxic-Q5 exclusion over accepted allocator",
                "exp-20260625-023": "placebo falsification did not lift exp019 blocker",
            },
            "3_single_decision_hypothesis": CHANGED_VARIABLE,
            "4_acceptance_standard": gate["acceptance_rule"],
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "allocator_rule_version": prior_clean_flow.ALLOCATOR_RULE_VERSION,
            "source_rule_version": prior_clean_flow.SOURCE_RULE_VERSION,
            "clean_flow_rule_version": CLEAN_FLOW_RULE_VERSION,
            "scalar_rule_version": SCALAR_RULE_VERSION,
            "short_volume_source": repo_rel(DEFAULT_SHORT_VOLUME_ROWS),
            "toxic_quintile_index": DEFAULT_TOXIC_QUINTILE_INDEX,
            "toxic_quintile_label": f"Q{DEFAULT_TOXIC_QUINTILE_INDEX + 1}",
            "toxic_notional_scalar": TOXIC_NOTIONAL_SCALAR,
            "paper_notional_usd": prior_clean_flow.BASE_NOTIONAL_USD,
            "same_ticker_cooldown_days": prior_clean_flow.SAME_TICKER_COOLDOWN_DAYS,
            "source_priority": prior_clean_flow.SOURCE_PRIORITY,
            "pit_rule": (
                "Historical rows use the latest formed activity percentile "
                "strictly before entry_date. Missing percentiles stay at 1.0 "
                "notional scalar."
            ),
        },
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "accepted allocator overlay with and without toxic-Q5 notional "
                "down-weight."
            ),
            "windows": framework.WINDOWS,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "candidate_ohlcv_source": repo_rel(framework.WAREHOUSE),
            "short_volume_source": repo_rel(DEFAULT_SHORT_VOLUME_ROWS),
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists(),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "core_baseline_metrics": before_metrics,
            "before_policy": "ungated accepted_helper_source_priority_allocator",
            "after_policy": "same allocator with toxic-Q5 paper notional scaled to 50%",
        },
        "gate2": {
            "passed": bool(short_volume_history) and bool(percentile_index) and gate2_open_positions["passed"],
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "entry_date",
                "target_price",
                "allocator candidate ticker/signal_date/entry_date",
                "moomoo activity_date",
                "moomoo short_volume_ratio",
                "PIT expanding per-ticker percentile",
                "paper pnl",
                "paper_notional_usd",
            ],
            "short_volume_audit": short_volume_audit,
        },
        "gate3": {
            "new_core_filter_added": False,
            "strategy_filter_added": False,
            "notional_scalar_added": True,
            "signals_generated": sum(len(rows) for rows in ungated_trades_by_window.values()),
            "signals_survived": sum(len(rows) for rows in downweighted_trades_by_window.values()),
            "survival_rate": _round(
                sum(len(rows) for rows in downweighted_trades_by_window.values())
                / max(1, sum(len(rows) for rows in ungated_trades_by_window.values())),
                6,
            ),
            "minimum_core_survival_rate": gate["minimum_core_survival_rate"],
            "passed": gate["minimum_core_survival_rate"] >= 0.05,
        },
        "gate4": gate,
        "before_metrics": ungated_metrics,
        "after_metrics": downweighted_metrics,
        "core_baseline_metrics": before_metrics,
        "delta_metrics": {
            "by_window_vs_ungated": OrderedDict(
                (label, row["delta"]) for label, row in delta_vs_ungated_rows.items()
            ),
            "aggregate_vs_ungated": aggregate_vs_ungated,
            "by_window_vs_core": OrderedDict(
                (label, row["delta"]) for label, row in delta_vs_core_rows.items()
            ),
            "aggregate_vs_core": aggregate_vs_core,
        },
        "window_rows": window_rows,
        "target_trade_summary": {
            "scaled_toxic_rows": scaled_summary,
            "downweighted_rows": downweighted_summary,
            "ungated_rows": ungated_summary,
        },
        "scalar_audit_by_window": scalar_audit_by_window,
        "helper_audit_by_window": helper_audit_by_window,
        "sample_trades": {
            "scaled_toxic_rows": {
                label: rows[:10] for label, rows in scaled_trades_by_window.items()
            },
            "downweighted_rows": {
                label: rows[:10] for label, rows in downweighted_trades_by_window.items()
            },
        },
        "production_impact": production_impact,
        "post_run_reflection": post_run_reflection,
        "related_files": [
            RUNNER,
            "quant/short_volume_clean_flow_gate.py",
            "quant/accepted_helper_source_priority_allocator_paper_sleeve.py",
            repo_rel(DEFAULT_SHORT_VOLUME_ROWS),
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": "No JavaScript was used.",
    }


def build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    gate = payload["gate4"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "owner": OWNER,
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "numeric_gate4_passed": gate["passed"],
        "hypothesis": HYPOTHESIS,
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "pre_run_questions": payload["pre_run_questions"],
        "backtest_protocol": payload["backtest_protocol"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": gate,
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "aggregate_expected_value_delta": gate["aggregate_ev_delta_vs_ungated"],
        "aggregate_strategy_total_pnl_delta": gate["aggregate_pnl_delta_vs_ungated"],
        "aggregate_ev_delta_vs_core": gate["aggregate_ev_delta_vs_core"],
        "aggregate_pnl_delta_vs_core": gate["aggregate_pnl_delta_vs_core"],
        "target_trade_summary": payload["target_trade_summary"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "changed_files": payload["related_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "anti_js": payload["anti_js"],
    }


def build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Ungated EV | Downweighted EV | dEV | Ungated PnL | Downweighted PnL | dPnL | scaled |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, row in payload["window_rows"].items():
        ungated = row["ungated_allocator"]
        downweighted = row["downweighted_allocator"]
        delta = row["delta_vs_ungated"]
        rows.append(
            "| {label} | {uev:.4f} | {devv:.4f} | {dev:+.4f} | ${upnl:,.2f} | ${dpnl:,.2f} | ${dpnld:+,.2f} | {scaled} |".format(
                label=label,
                uev=ungated["expected_value_score"],
                devv=downweighted["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                upnl=ungated["total_pnl"],
                dpnl=downweighted["total_pnl"],
                dpnld=delta.get("total_pnl", 0.0),
                scaled=row["scaled_toxic_trade_count"],
            )
        )
    gate = payload["gate4"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: moomoo short-volume notional down-weight",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Production orders changed: `false`",
            f"- Runner: `{RUNNER_COMMAND}`",
            "",
            "## Hypothesis",
            "",
            HYPOTHESIS,
            "",
            "## Gate 4: downweighted allocator vs current ungated allocator",
            "",
            *rows,
            "",
            f"- Aggregate EV delta vs ungated: `{gate['aggregate_ev_delta_vs_ungated']:+.4f}`",
            f"- Aggregate EV delta pct vs ungated: `{gate['aggregate_ev_delta_pct_vs_ungated']}`",
            f"- Aggregate PnL delta vs ungated: `${gate['aggregate_pnl_delta_vs_ungated']:+,.2f}`",
            f"- Scaled trades: `{gate['changed_trade_count']}`",
            f"- Failed reasons: `{', '.join(gate['failed_reasons']) or 'none'}`",
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def update_ticket_and_registry(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    result = {
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "aggregate_expected_value_delta": payload["gate4"]["aggregate_ev_delta_vs_ungated"],
        "aggregate_strategy_total_pnl_delta": payload["gate4"]["aggregate_pnl_delta_vs_ungated"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": payload["gate4"][
                "aggregate_ev_delta_vs_ungated"
            ],
            "aggregate_strategy_total_pnl_delta": payload["gate4"][
                "aggregate_pnl_delta_vs_ungated"
            ],
        },
    )
    ticket = {}
    if TICKET_JSON.exists():
        ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8-sig"))
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "updated_at": payload["timestamp"],
            "owner": OWNER,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "decision": payload["decision"],
            "result": result,
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
        }
    )
    write_json(TICKET_JSON, ticket)


def write_manifest(payload: dict[str, Any]) -> None:
    paths = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        TICKET_JSON,
        MANIFEST_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        DEFAULT_SHORT_VOLUME_ROWS,
    ]
    write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "created_at": payload["timestamp"],
            "runner": RUNNER,
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card": repo_rel(CARD_MD),
            "files": {
                repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
                for path in paths
            },
            "reproduction_commands": payload["reproduction_commands"],
            "anti_js": "No JavaScript was used.",
        },
    )


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = build_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)
    update_ticket_and_registry(payload, log_record)
    write_manifest(payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "aggregate_ev_delta_vs_ungated": payload["gate4"][
                    "aggregate_ev_delta_vs_ungated"
                ],
                "aggregate_ev_delta_pct_vs_ungated": payload["gate4"][
                    "aggregate_ev_delta_pct_vs_ungated"
                ],
                "aggregate_pnl_delta_vs_ungated": payload["gate4"][
                    "aggregate_pnl_delta_vs_ungated"
                ],
                "changed_trade_count": payload["gate4"]["changed_trade_count"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
