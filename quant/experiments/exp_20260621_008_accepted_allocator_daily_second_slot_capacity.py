"""exp-20260621-008: accepted allocator daily second-slot capacity.

Alpha search. Tests one attributable candidate-pool/allocation hypothesis:
keep the current accepted helper source-priority allocator source stack fixed
after exp-20260621-007, and allow at most two default-off paper candidates per
signal date instead of one. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any

import exp_20260611_005_lagged_consensus_shared_allocator_source as base

framework = base.framework
exp008 = base.exp008

REPO_ROOT = framework.REPO_ROOT
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for entry in (str(REPO_ROOT), str(QUANT_ROOT), str(SCRIPTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import accepted_helper_source_priority_allocator_paper_sleeve as allocator_helper  # noqa: E402
from data_layer import get_universe  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260621-008"
OWNER = "alpha-search-automation"
STEM = "accepted_allocator_daily_second_slot_capacity"
TRIAL_FAMILY = "accepted_default_off_helper_source_priority_allocation"
TRIAL_VARIANT_ID = "accepted_allocator_daily_second_slot_capacity_v1"
CHANGED_VARIABLE = TRIAL_VARIANT_ID

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260621_008_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

CURRENT_DAILY_ENTRY_SLOTS = 1
AFTER_DAILY_ENTRY_SLOTS = 2
MIN_ADDED_TRADES = 20
MIN_ADDED_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

CURRENT_SCALARS = OrderedDict(
    (source, float(scalar))
    for source, scalar in allocator_helper.SOURCE_NOTIONAL_SCALARS.items()
)

PREDICTION = {
    "success_probability": 0.14,
    "expected_ev_delta": 0.10,
    "expected_pnl_delta": 2000.0,
    "main_failure_modes": [
        "redundant_second_slot_candidates",
        "drawdown_drift",
        "window_regression",
        "max_concurrent_envelope_skips",
        "allocator_capacity_near_neighbor",
    ],
    "confidence_reason": (
        "The current accepted scalar stack creates more source depth than the "
        "original top-1 allocator, but capacity/position-cap families are "
        "heavily explored and second slots may add correlated or lower-quality "
        "trades."
    ),
    "recorded_at": "2026-06-21T09:13:55+00:00",
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool/allocation: after the accepted source-notional stack, "
        "the shared accepted-helper source-priority allocator may have enough "
        "independent second-choice daily candidates that allowing two "
        "default-off paper entries per signal date improves replacement value "
        "without changing source definitions, rank, hold, cooldown, source "
        "notional scalars, LLM/news, or live/default orders."
    ),
    "2_history_check": {
        "novelty_gate": (
            "experiment.py new warned on allocator near-neighbors and was "
            "recorded with a novelty override. The new evidence axis is the "
            "current exp-20260621-007 accepted source-notional stack: second-slot "
            "replacement value has not been measured under that exact shared "
            "helper/scalar stack."
        ),
        "exp-20260611-005": (
            "Accepted the shared source-priority allocator with daily top-1 "
            "selection and lagged consensus rank 1."
        ),
        "exp-20260612-024": (
            "Allocator activation/envelope context; this run remains default-off "
            "and evaluates the execution envelope before any acceptance."
        ),
        "exp-20260616-016": (
            "Rejected adding SBC as a rank-2 allocator source because it did not "
            "beat accepted allocator comparators and worsened drawdown."
        ),
        "exp-20260620-032": (
            "Accepted source-notional scalars for industry_laggard_repair and "
            "revision_surprise_low_extension."
        ),
        "exp-20260621-001": "Accepted rolling_peer_shock source-notional scalar.",
        "exp-20260621-006": "Accepted turn_of_month source-notional scalar.",
        "exp-20260621-007": "Accepted lagged_cross_source_consensus source-notional scalar.",
    },
    "3_single_causal_variable": (
        "One fixed policy bundle: daily_entry_slots increases from 1 to 2. "
        "Source definitions, source priority, accepted source_notional_scalars, "
        "paper notional base, hold days, same-ticker cooldown, core behavior, "
        "LLM/news, and live/default orders remain fixed."
    ),
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Binding Gate 4 is the "
        "production-consistent execution-envelope comparison of current slots=1 "
        "versus after slots=2: aggregate EV/PnL must improve, no window EV/PnL "
        "regression, survival >=5%, drawdown drift <=0.5pp, added-row sample "
        "must span all three windows with >=20 rows, concentration must pass, "
        "and expanded envelope skips must be zero."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260621_008_accepted_allocator_daily_second_slot_capacity.py"
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _slot_config(daily_entry_slots: int) -> dict[str, Any]:
    return {
        **allocator_helper.DEFAULT_CONFIG,
        "daily_entry_slots": daily_entry_slots,
        "source_notional_scalars": dict(CURRENT_SCALARS),
    }


def _decision_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("decision_id") or ""),
        str(row.get("signal_date") or row.get("date") or "")[:10],
        str(row.get("ticker") or "").upper(),
    )


def _diff_rows(
    current: list[dict[str, Any]],
    expanded: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    current_keys = {_decision_key(row) for row in current}
    expanded_keys = {_decision_key(row) for row in expanded}
    added = [row for row in expanded if _decision_key(row) not in current_keys]
    dropped = [row for row in current if _decision_key(row) not in expanded_keys]
    return added, dropped


def _aggregate_incremental(window_rows: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    before_ev = sum(float(row["before"]["expected_value_score"]) for row in window_rows.values())
    after_ev = sum(float(row["after"]["expected_value_score"]) for row in window_rows.values())
    before_pnl = sum(float(row["before"]["total_pnl"]) for row in window_rows.values())
    after_pnl = sum(float(row["after"]["total_pnl"]) for row in window_rows.values())
    deltas = [row["delta"] for row in window_rows.values()]
    ev_delta = after_ev - before_ev
    pnl_delta = after_pnl - before_pnl
    return {
        "baseline_expected_value_score_sum": round(before_ev, 4),
        "after_expected_value_score_sum": round(after_ev, 4),
        "expected_value_score_delta_sum": round(ev_delta, 4),
        "expected_value_score_delta_pct": round(ev_delta / before_ev, 6) if before_ev else None,
        "baseline_total_pnl_sum": round(before_pnl, 2),
        "after_total_pnl_sum": round(after_pnl, 2),
        "total_pnl_delta_sum": round(pnl_delta, 2),
        "total_pnl_delta_pct": round(pnl_delta / before_pnl, 6) if before_pnl else None,
        "windows_ev_improved": sum(1 for row in deltas if float(row["expected_value_score"]) > 0),
        "windows_ev_regressed": sum(1 for row in deltas if float(row["expected_value_score"]) < 0),
        "windows_pnl_improved": sum(1 for row in deltas if float(row["total_pnl"]) > 0),
        "windows_pnl_regressed": sum(1 for row in deltas if float(row["total_pnl"]) < 0),
        "max_drawdown_delta_max": max(float(row["max_drawdown_pct"]) for row in deltas),
    }


def _target_summary(trades_by_window: OrderedDict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    summary = framework.sleeve._target_trade_summary(trades_by_window)
    positive = summary.get("positive_by_ticker_pnl") or {}
    total = sum(float(value) for value in positive.values())
    if total > 0:
        top5 = sum(sorted((float(value) for value in positive.values()), reverse=True)[:5])
        summary["top5_positive_share"] = round(top5 / total, 6)
    else:
        summary["top5_positive_share"] = None
    summary["source_counts"] = dict(
        Counter(
            str(row.get("source_family") or "unknown")
            for rows in trades_by_window.values()
            for row in rows
        )
    )
    return summary


def _run_comparison() -> dict[str, Any]:
    universe = sorted(get_universe())
    sector_entries = framework._load_sector_entries()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    core_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    current_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    expanded_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    current_enveloped_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    expanded_enveloped_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    window_rows_raw: OrderedDict[str, dict[str, Any]] = OrderedDict()
    window_rows_enveloped: OrderedDict[str, dict[str, Any]] = OrderedDict()
    current_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    expanded_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    current_enveloped_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    expanded_enveloped_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    added_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    dropped_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    helper_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    envelope_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    warehouse_coverage_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] accepted allocator slots {CURRENT_DAILY_ENTRY_SLOTS} vs {AFTER_DAILY_ENTRY_SLOTS}")
        before_result = framework.shadow._run_baseline(universe, cfg)
        core = framework.overlay_helper._metrics(before_result)
        snapshot = exp008._load_window_snapshot_deep(
            cfg=cfg,
            eligible_tickers=set(sector_entries),
        )
        window_sector_entries = {
            ticker: meta for ticker, meta in sector_entries.items() if ticker in snapshot
        }
        candidate_universe = base._candidate_universe_from_sector_entries(
            window_sector_entries
        )
        core_entries = framework.shadow._baseline_entries(before_result)
        calendar_dates = framework.shadow._trading_dates(snapshot)

        current_trades, current_audit = (
            allocator_helper.build_accepted_helper_source_priority_allocator_historical_trades(
                ohlcv_by_ticker=snapshot,
                core_entries_by_date=core_entries,
                windows=OrderedDict([(label, cfg)]),
                candidate_universe=candidate_universe,
                sector_entries=window_sector_entries,
                calendar_dates=calendar_dates,
                config=_slot_config(CURRENT_DAILY_ENTRY_SLOTS),
            )
        )
        expanded_trades, expanded_audit = (
            allocator_helper.build_accepted_helper_source_priority_allocator_historical_trades(
                ohlcv_by_ticker=snapshot,
                core_entries_by_date=core_entries,
                windows=OrderedDict([(label, cfg)]),
                candidate_universe=candidate_universe,
                sector_entries=window_sector_entries,
                calendar_dates=calendar_dates,
                config=_slot_config(AFTER_DAILY_ENTRY_SLOTS),
            )
        )

        current_overlay = framework.sleeve._overlay_from_paper_trades(
            before_result,
            current_trades,
        )
        expanded_overlay = framework.sleeve._overlay_from_paper_trades(
            before_result,
            expanded_trades,
        )
        current_after = framework.overlay_helper._metrics_with_overlay(
            before_result,
            current_overlay,
        )
        expanded_after = framework.overlay_helper._metrics_with_overlay(
            before_result,
            expanded_overlay,
        )

        current_enveloped, current_skipped, current_envelope_audit = (
            allocator_helper.apply_execution_envelope_to_trades(current_trades)
        )
        expanded_enveloped, expanded_skipped, expanded_envelope_audit = (
            allocator_helper.apply_execution_envelope_to_trades(expanded_trades)
        )
        current_enveloped_overlay = framework.sleeve._overlay_from_paper_trades(
            before_result,
            current_enveloped,
        )
        expanded_enveloped_overlay = framework.sleeve._overlay_from_paper_trades(
            before_result,
            expanded_enveloped,
        )
        current_enveloped_after = framework.overlay_helper._metrics_with_overlay(
            before_result,
            current_enveloped_overlay,
        )
        expanded_enveloped_after = framework.overlay_helper._metrics_with_overlay(
            before_result,
            expanded_enveloped_overlay,
        )

        added, dropped = _diff_rows(current_trades, expanded_trades)

        core_metrics[label] = core
        current_metrics[label] = current_after
        expanded_metrics[label] = expanded_after
        current_enveloped_metrics[label] = current_enveloped_after
        expanded_enveloped_metrics[label] = expanded_enveloped_after
        current_trades_by_window[label] = current_trades
        expanded_trades_by_window[label] = expanded_trades
        current_enveloped_trades_by_window[label] = current_enveloped
        expanded_enveloped_trades_by_window[label] = expanded_enveloped
        added_trades_by_window[label] = added
        dropped_trades_by_window[label] = dropped
        helper_audit_by_window[label] = {
            "current_slots": current_audit,
            "expanded_slots": expanded_audit,
        }
        envelope_audit_by_window[label] = {
            "current": current_envelope_audit,
            "expanded": expanded_envelope_audit,
            "current_skipped_count": len(current_skipped),
            "expanded_skipped_count": len(expanded_skipped),
            "current_skip_reasons": current_envelope_audit["skip_reasons"],
            "expanded_skip_reasons": expanded_envelope_audit["skip_reasons"],
        }
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "sector_known_candidate_ticker_count": len(window_sector_entries),
            "snapshot_lookback_calendar_days": exp008.SNAPSHOT_LOOKBACK_CALENDAR_DAYS,
            "source": _repo_rel(framework.WAREHOUSE),
        }
        raw_delta = framework.overlay_helper._delta(expanded_after, current_after)
        enveloped_delta = framework.overlay_helper._delta(
            expanded_enveloped_after,
            current_enveloped_after,
        )
        window_rows_raw[label] = {
            "before": current_after,
            "after": expanded_after,
            "delta": raw_delta,
            "core": core,
            "current_trade_count": len(current_trades),
            "expanded_trade_count": len(expanded_trades),
            "added_trade_count": len(added),
            "dropped_trade_count": len(dropped),
            "current_selected_source_counts": current_audit[
                "selected_source_counts_by_window"
            ][label],
            "expanded_selected_source_counts": expanded_audit[
                "selected_source_counts_by_window"
            ][label],
        }
        window_rows_enveloped[label] = {
            "before": current_enveloped_after,
            "after": expanded_enveloped_after,
            "delta": enveloped_delta,
            "core": core,
            "current_trade_count": len(current_enveloped),
            "expanded_trade_count": len(expanded_enveloped),
            "added_trade_count": len(added),
            "dropped_trade_count": len(dropped),
            "current_envelope_skipped_count": len(current_skipped),
            "expanded_envelope_skipped_count": len(expanded_skipped),
        }

    return {
        "gate2_open_positions": gate2_open_positions,
        "core_metrics": core_metrics,
        "current_metrics": current_metrics,
        "expanded_metrics": expanded_metrics,
        "current_enveloped_metrics": current_enveloped_metrics,
        "expanded_enveloped_metrics": expanded_enveloped_metrics,
        "window_rows_raw": window_rows_raw,
        "window_rows_enveloped": window_rows_enveloped,
        "current_trades_by_window": current_trades_by_window,
        "expanded_trades_by_window": expanded_trades_by_window,
        "current_enveloped_trades_by_window": current_enveloped_trades_by_window,
        "expanded_enveloped_trades_by_window": expanded_enveloped_trades_by_window,
        "added_trades_by_window": added_trades_by_window,
        "dropped_trades_by_window": dropped_trades_by_window,
        "helper_audit_by_window": helper_audit_by_window,
        "envelope_audit_by_window": envelope_audit_by_window,
        "warehouse_coverage_by_window": warehouse_coverage_by_window,
    }


def _binding_gate4(
    *,
    aggregate: dict[str, Any],
    raw_aggregate: dict[str, Any],
    added_summary: dict[str, Any],
    comparison: dict[str, Any],
) -> dict[str, Any]:
    core_metrics = comparison["core_metrics"]
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in core_metrics.values())
    concentration_passed = (
        added_summary["max_single_positive_pnl_share"] is not None
        and added_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and added_summary["positive_pnl_hhi"] is not None
        and added_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    expanded_skip_count = sum(
        int(row["expanded_skipped_count"])
        for row in comparison["envelope_audit_by_window"].values()
    )
    current_skip_count = sum(
        int(row["current_skipped_count"])
        for row in comparison["envelope_audit_by_window"].values()
    )
    dropped_count = sum(len(rows) for rows in comparison["dropped_trades_by_window"].values())
    failed: list[str] = []
    if float(aggregate["expected_value_score_delta_sum"]) <= 0:
        failed.append("enveloped_incremental_ev_not_positive")
    if float(aggregate["total_pnl_delta_sum"]) <= 0:
        failed.append("enveloped_incremental_pnl_not_positive")
    if int(aggregate["windows_ev_regressed"]) > 0:
        failed.append("enveloped_window_ev_regression")
    if int(aggregate["windows_pnl_regressed"]) > 0:
        failed.append("enveloped_window_pnl_regression")
    if float(aggregate["max_drawdown_delta_max"]) > MAX_DRAWDOWN_WORSE:
        failed.append("enveloped_drawdown_drift_too_high")
    if float(raw_aggregate["expected_value_score_delta_sum"]) <= 0:
        failed.append("raw_incremental_ev_not_positive")
    if float(raw_aggregate["total_pnl_delta_sum"]) <= 0:
        failed.append("raw_incremental_pnl_not_positive")
    if int(raw_aggregate["windows_ev_regressed"]) > 0:
        failed.append("raw_window_ev_regression")
    if int(raw_aggregate["windows_pnl_regressed"]) > 0:
        failed.append("raw_window_pnl_regression")
    if int(added_summary["total_trade_count"]) < MIN_ADDED_TRADES:
        failed.append("added_sample_too_small")
    if len(added_summary["windows_with_target_trades"]) < MIN_ADDED_WINDOWS:
        failed.append("added_window_coverage_too_small")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")
    if not concentration_passed:
        failed.append("added_trade_concentration_failed")
    if current_skip_count > 0:
        failed.append("current_allocator_already_violates_execution_envelope")
    if expanded_skip_count > 0:
        failed.append("expanded_allocator_violates_execution_envelope")
    if dropped_count > 0:
        failed.append("second_slot_cooldown_displaced_existing_top1_rows")
    accepted = not failed
    return {
        "passed": accepted,
        "decision": (
            "accepted_allocator_daily_second_slot_capacity"
            if accepted
            else "rejected_allocator_daily_second_slot_capacity"
        ),
        "failed_reasons": failed,
        "binding_metric": "execution_envelope_adjusted_current_slots1_vs_expanded_slots2",
        "aggregate_ev_delta_vs_current_allocator": aggregate[
            "expected_value_score_delta_sum"
        ],
        "aggregate_pnl_delta_vs_current_allocator": aggregate["total_pnl_delta_sum"],
        "raw_aggregate_ev_delta_vs_current_allocator": raw_aggregate[
            "expected_value_score_delta_sum"
        ],
        "raw_aggregate_pnl_delta_vs_current_allocator": raw_aggregate[
            "total_pnl_delta_sum"
        ],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "windows_pnl_improved": aggregate["windows_pnl_improved"],
        "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
        "added_trade_count": added_summary["total_trade_count"],
        "added_trade_count_min": MIN_ADDED_TRADES,
        "added_windows": added_summary["windows_with_target_trades"],
        "added_window_count_min": MIN_ADDED_WINDOWS,
        "dropped_current_top1_trade_count": dropped_count,
        "max_drawdown_worse_vs_current": aggregate["max_drawdown_delta_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "minimum_core_survival_rate": round(min_survival, 6),
        "survival_guard_passed": min_survival >= 0.05,
        "execution_envelope": {
            "passed": current_skip_count == 0 and expanded_skip_count == 0,
            "current_skipped_count": current_skip_count,
            "expanded_skipped_count": expanded_skip_count,
            "by_window": comparison["envelope_audit_by_window"],
        },
        "added_trade_concentration": {
            "passed": concentration_passed,
            "max_single_positive_pnl_share": added_summary[
                "max_single_positive_pnl_share"
            ],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": added_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
            "top5_positive_share": added_summary["top5_positive_share"],
        },
    }


def _production_impact(accepted: bool) -> dict[str, Any]:
    return {
        "trade_enabled": False,
        "alters_orders": False,
        "adapter_status": (
            "shared_default_off_paper_helper" if accepted else "replay_only_no_shared_change"
        ),
        "shared_policy_changed": accepted,
        "backtester_adapter_changed": accepted,
        "run_adapter_changed": accepted,
        "replay_only": not accepted,
        "default_off_paper_only": True,
        "daily_snapshot_exposed": accepted,
        "parity_test_added": accepted,
        "production_signal_path_changed": False,
        "production_orders_changed": False,
        "production_watchlist_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "uses_llm": False,
        "uses_free_ohlcv_only": False,
        "uses_free_non_ohlcv": True,
        "live_realism_evaluated": True,
        "live_ready": False,
        "execution_envelope": allocator_helper.EXECUTION_ENVELOPE,
        "parity_note": (
            "If accepted, historical replay and daily default-off snapshots would "
            "use the same shared accepted-helper allocator daily_entry_slots=2 "
            "config with the current accepted source_notional_scalars. If "
            "rejected, no shared helper, daily snapshot, live/default orders, or "
            "core behavior changes are retained."
        ),
    }


def build_payload() -> dict[str, Any]:
    comparison = _run_comparison()
    raw_aggregate = _aggregate_incremental(comparison["window_rows_raw"])
    enveloped_aggregate = _aggregate_incremental(comparison["window_rows_enveloped"])
    added_summary = _target_summary(comparison["added_trades_by_window"])
    dropped_summary = _target_summary(comparison["dropped_trades_by_window"])
    gate4 = _binding_gate4(
        aggregate=enveloped_aggregate,
        raw_aggregate=raw_aggregate,
        added_summary=added_summary,
        comparison=comparison,
    )
    accepted = gate4["passed"]
    timestamp = framework._utc_now()
    production_impact = _production_impact(accepted)
    status = "accepted_paper_pending_forward" if accepted else "rejected"
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": accepted,
        "actual_success": 1 if accepted else 0,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if accepted else 0.0)) ** 2,
            6,
        ),
    }
    interpretation = (
        "The second daily slot improved production-consistent allocator replacement "
        "value and is retained as shared default-off paper observation only."
        if accepted
        else "The second daily slot failed Gate 4 and is not retained."
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": gate4["decision"],
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "candidate_pool_full_stack",
        "implementation_mode": (
            "shared_paper_first" if accepted else "replay_screen_rejected_before_shared_change"
        ),
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "current_accepted_scalar_stack_second_slot_replacement_value",
        "nearby_prior_experiments": [
            "exp-20260611-005",
            "exp-20260612-024",
            "exp-20260616-016",
            "exp-20260620-032",
            "exp-20260621-001",
            "exp-20260621-006",
            "exp-20260621-007",
        ],
        "prior_trial_count": 7,
        "prediction": PREDICTION,
        "calibration": calibration,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "shared accepted-helper source-priority allocator overlay"
            ),
            "windows": framework.WINDOWS,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Before: current accepted allocator config with daily_entry_slots=1 "
                "and current accepted source_notional_scalars. After: same shared "
                "helper with only daily_entry_slots=2. Binding Gate 4 uses "
                "apply_execution_envelope_to_trades() before overlay metrics so "
                "positive results cannot rely on trades the declared production "
                "envelope would skip."
            ),
        },
        "parameters": {
            "rule_version": allocator_helper.RULE_VERSION,
            "source_rule_version": allocator_helper.SOURCE_RULE_VERSION,
            "source_priority": allocator_helper.SOURCE_PRIORITY,
            "base_paper_notional_usd": allocator_helper.BASE_NOTIONAL_USD,
            "source_notional_scalars": CURRENT_SCALARS,
            "before_daily_entry_slots": CURRENT_DAILY_ENTRY_SLOTS,
            "after_daily_entry_slots": AFTER_DAILY_ENTRY_SLOTS,
            "same_ticker_cooldown_days": allocator_helper.SAME_TICKER_COOLDOWN_DAYS,
        },
        "gate1": {
            "baseline_artifact": (
                "same-run current accepted allocator slots=1 metrics; exp-20260621-007 "
                "artifact supplied the accepted source-scalar before state"
            ),
            "baseline_metrics": comparison["current_enveloped_metrics"],
            "passed": True,
        },
        "gate2": {
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "accepted allocator source row source_family",
                "accepted allocator source row pnl_pct_net/pnl",
                "accepted allocator selected row paper_notional_usd",
                "accepted allocator config daily_entry_slots",
                "daily snapshot candidate source_notional_scalar",
            ],
            "open_positions": comparison["gate2_open_positions"],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_selection_changed": True,
            "minimum_core_survival_rate": gate4["minimum_core_survival_rate"],
            "passed": gate4["survival_guard_passed"],
            "signals_generated": {
                label: row["current_trade_count"]
                for label, row in comparison["window_rows_enveloped"].items()
            },
            "signals_survived": {
                label: row["expanded_trade_count"]
                for label, row in comparison["window_rows_enveloped"].items()
            },
            "note": "Default-off paper allocator capacity only; core signals/survival unchanged.",
        },
        "gate4": gate4,
        "before_metrics": comparison["current_enveloped_metrics"],
        "after_metrics": comparison["expanded_enveloped_metrics"],
        "raw_before_metrics": comparison["current_metrics"],
        "raw_after_metrics": comparison["expanded_metrics"],
        "delta_metrics": {
            "by_window": OrderedDict(
                (label, row["delta"])
                for label, row in comparison["window_rows_enveloped"].items()
            ),
            "aggregate": enveloped_aggregate,
        },
        "raw_delta_metrics": {
            "by_window": OrderedDict(
                (label, row["delta"])
                for label, row in comparison["window_rows_raw"].items()
            ),
            "aggregate": raw_aggregate,
        },
        "core_metrics": comparison["core_metrics"],
        "window_rows": comparison["window_rows_enveloped"],
        "raw_window_rows": comparison["window_rows_raw"],
        "current_trades_by_window": comparison["current_trades_by_window"],
        "expanded_trades_by_window": comparison["expanded_trades_by_window"],
        "added_trades_by_window": comparison["added_trades_by_window"],
        "dropped_trades_by_window": comparison["dropped_trades_by_window"],
        "added_trade_summary": added_summary,
        "dropped_trade_summary": dropped_summary,
        "helper_audit_by_window": comparison["helper_audit_by_window"],
        "execution_envelope_audit_by_window": comparison["envelope_audit_by_window"],
        "warehouse_coverage_by_window": comparison["warehouse_coverage_by_window"],
        "production_impact": production_impact,
        "full_stack_verdict": "accepted_paper_pending_forward" if accepted else "reject",
        "interpretation": interpretation,
        "rejection_reason": None if accepted else "; ".join(gate4["failed_reasons"]),
        "post_run_reflection": {
            "why_result_happened": (
                "The current accepted helper had enough second-slot depth that "
                "additional paper candidates added replacement value without "
                "violating the execution envelope."
                if accepted
                else (
                    "The second slot did not clear a production-consistent "
                    "replacement-value screen. The likely failure mode is that "
                    "the added rows are lower-rank/correlated capacity, or the "
                    "extra entries create execution-envelope pressure that the "
                    "raw historical overlay alone would understate."
                )
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry by sweeping daily_entry_slots, max_active_positions, "
                "source ranks, source thresholds, hold days, cooldown, or source "
                "notional on the same frozen windows."
            ),
            "new_evidence_required": (
                "Closed forward replacement-value rows for rejected second-slot "
                "candidates, or a materially new PIT field that predicts which "
                "second slot should displace idle allocator capacity."
            ),
        },
        "next_retry_requires": [
            "closed forward second-slot replacement-value rows",
            "new PIT field explaining second-slot quality",
            "no frozen-window capacity or rank sweep",
        ],
        "anti_js": "No JavaScript was used.",
        "related_files": _related_files(accepted),
    }


def _related_files(accepted: bool) -> list[str]:
    files = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
        "docs/alpha-optimization-playbook.md",
    ]
    if accepted:
        files.extend(
            [
                "quant/accepted_helper_source_priority_allocator_paper_sleeve.py",
                "quant/test_accepted_helper_source_priority_allocator_paper_sleeve.py",
                "docs/production_backtest_parity_matrix.md",
                "docs/alpha-optimization-playbook.md",
            ]
        )
    return files


def _window_table(payload: dict[str, Any]) -> list[str]:
    rows = [
        "| Window | Current EV | Slot-2 EV | dEV | Current PnL | Slot-2 PnL | dPnL | DD d | Added | Dropped |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {added} | {dropped} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                dd=delta["max_drawdown_pct"],
                added=len(payload["added_trades_by_window"][label]),
                dropped=len(payload["dropped_trades_by_window"][label]),
            )
        )
    return rows


def _build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    raw_aggregate = payload["raw_delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Accepted Allocator Daily Second Slot Capacity",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4: Execution-Envelope Current Slot vs Second Slot",
            "",
            *_window_table(payload),
            "",
            "- Aggregate enveloped EV: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate enveloped PnL: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Aggregate raw EV: `{:+.4f}`".format(
                raw_aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate raw PnL: `${:+,.2f}`".format(
                raw_aggregate["total_pnl_delta_sum"]
            ),
            "- Added trades: `{}` across `{}` windows".format(
                payload["added_trade_summary"]["total_trade_count"],
                len(payload["added_trade_summary"]["windows_with_target_trades"]),
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Production Impact",
            "",
            payload["production_impact"]["parity_note"],
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["gate4"]["passed"],
        "accepted_alpha": payload["gate4"]["passed"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "raw_aggregate_expected_value_delta": payload["raw_delta_metrics"]["aggregate"][
            "expected_value_score_delta_sum"
        ],
        "raw_aggregate_strategy_total_pnl_delta": payload["raw_delta_metrics"][
            "aggregate"
        ]["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_after": payload["after_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "added_trade_count": len(payload["added_trades_by_window"][label]),
                "dropped_trade_count": len(payload["dropped_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON, {})
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "result": {
                "decision": payload["decision"],
                "full_stack_verdict": payload["full_stack_verdict"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "aggregate_expected_value_delta": payload["delta_metrics"]["aggregate"][
                    "expected_value_score_delta_sum"
                ],
                "aggregate_strategy_total_pnl_delta": payload["delta_metrics"][
                    "aggregate"
                ]["total_pnl_delta_sum"],
                "accepted": payload["gate4"]["passed"],
                "calibration": payload["calibration"],
                "production_impact": payload["production_impact"],
            },
        }
    )
    scope = set(ticket.get("allowed_write_scope") or [])
    scope.update(payload["related_files"])
    ticket["allowed_write_scope"] = sorted(scope)
    framework._write_json(TICKET_JSON, ticket)


def _update_registry(payload: dict[str, Any]) -> None:
    result = {
        "decision": payload["decision"],
        "full_stack_verdict": payload["full_stack_verdict"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": payload["delta_metrics"]["aggregate"][
            "expected_value_score_delta_sum"
        ],
        "aggregate_strategy_total_pnl_delta": payload["delta_metrics"]["aggregate"][
            "total_pnl_delta_sum"
        ],
        "accepted": payload["gate4"]["passed"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "completed_at": payload["timestamp"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )


def _write_manifest(payload: dict[str, Any]) -> None:
    paths = [Path(path) for path in payload["related_files"]]
    file_hashes: dict[str, str] = {}
    for path in paths:
        resolved = path if path.is_absolute() else REPO_ROOT / path
        if resolved.exists() and resolved != MANIFEST_JSON:
            file_hashes[_repo_rel(resolved)] = framework._sha256(resolved)
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [_repo_rel(path) for path in paths],
        "file_hashes": file_hashes,
    }
    framework._write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, log_record)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket(payload)
    _update_registry(payload)
    _write_manifest(payload)


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            framework._safe(_build_log_record(payload)),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
