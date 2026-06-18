"""exp-20260618-022: distribution no-displacement allocator gap scout.

Replay-only alpha search. The single attributable decision hypothesis is that
the accepted distribution-day absorption helper may add value only on signal
dates where the unchanged accepted-helper allocator selects nothing.

This runner deliberately does not change the shared allocator, distribution
helper thresholds, daily production snapshots, live/default orders, ranking,
sizing, or exits. No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from copy import deepcopy
from pathlib import Path
from typing import Any

import exp_20260611_008_distribution_absorption_allocator_source as prior


base = prior.base
framework = prior.framework
allocator_helper = prior.allocator_helper
build_distribution_day_absorption_leadership_historical_trades = (
    prior.build_distribution_day_absorption_leadership_historical_trades
)
persist_self_registered_result = prior.persist_self_registered_result
ORIGINAL_BINDING_GATE4 = prior._binding_gate4
ORIGINAL_BUILD_SOURCE_TRADES = allocator_helper._build_source_trades

EXPERIMENT_ID = "exp-20260618-022"
OWNER = "codex-alpha-search"
STEM = "distribution_gap_fill_allocator"
TRIAL_FAMILY = "accepted_default_off_helper_gap_fill_allocation"
TRIAL_VARIANT_ID = (
    "distribution_day_absorption_no_displacement_gap_fill_allocator_source_v1"
)
CHANGED_VARIABLE = "distribution_day_absorption_no_displacement_empty_allocator_date_source_v1"
DISTRIBUTION_SOURCE_FAMILY = "distribution_day_absorption"

REPO_ROOT = framework.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260618_022_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

ACCEPTED_ALLOCATOR_COMPARATOR = prior.ACCEPTED_ALLOCATOR_COMPARATOR
ACCEPTED_DISTRIBUTION_COMPARATOR = prior.ACCEPTED_DISTRIBUTION_COMPARATOR

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": 0.15,
    "expected_pnl_delta": 3000.0,
    "main_failure_modes": [
        "empty_dates_lower_quality",
        "redundant_with_accepted_allocator",
        "accepted_allocator_comparator_not_beaten",
        "window_regression",
        "target_sample_too_small",
    ],
    "confidence_reason": (
        "Standalone distribution-day absorption is accepted, while rank-3 "
        "allocator insertion failed from likely displacement. Empty-date "
        "admission is a materially different gate shape, but the latest SBC "
        "empty-date scout failed the same broad no-displacement idea."
    ),
    "recorded_at": "2026-06-18T21:10:00+00:00",
}

PRODUCTION_IMPACT = {
    **prior.PRODUCTION_IMPACT,
    "adapter_status": "runner_local_no_displacement_gap_replay",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "shared_policy_tested_and_rolled_back": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "trade_enabled": False,
    "alters_orders": False,
    "uses_llm": False,
    "uses_free_ohlcv_only": True,
    "uses_free_non_ohlcv": False,
    "live_realism_evaluated": True,
    "live_ready": False,
    "parity_note": (
        "Replay-only no-displacement test. The runner keeps the existing "
        "accepted-helper allocator source priority unchanged, computes the "
        "allocator's selected dates first, and admits distribution-day "
        "absorption rows only on dates with no existing accepted allocator "
        "selection. No shared helper, daily snapshot, report queue, watchlist, "
        "order path, ranking, sizing, or exit behavior is retained."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool/allocation: accepted distribution-day absorption rows "
        "may add incremental replacement value only on signal dates where the "
        "unchanged accepted-helper allocator selects no row, because this "
        "removes the displacement channel that made the rank-3 allocator "
        "insertion fail."
    ),
    "2_history_check": {
        "exp-20260611-007": (
            "Accepted shared distribution-day absorption adapter: aggregate EV "
            "+0.5286, PnL +$10,432.91, 113 trades, all windows positive."
        ),
        "exp-20260611-008": (
            "Rejected rank-3 allocator insertion. It tested the same source as "
            "allocator competition, not empty-date admission, and failed the "
            "accepted allocator comparator."
        ),
        "exp-20260612-013": (
            "Rejected distribution as lagged-consensus source; this run does "
            "not use it as source confirmation or alter source priority."
        ),
        "exp-20260618-021": (
            "Rejected SBC no-displacement gap-fill. This run tests a different "
            "accepted source whose prior allocator failure was distribution "
            "displacement, not SBC quality overlap."
        ),
        "exp-20260611-005": (
            "Current binding accepted allocator comparator: aggregate EV "
            "+2.1849 and PnL +$40,397.21 across all three windows."
        ),
        "novelty_gate": (
            "Near-neighbor warning was overridden only for the new evidence "
            "axis: distribution rows are eligible only on dates with no "
            "existing accepted allocator selection; no rank, threshold, top-N, "
            "hold, cooldown, or notional retune is allowed."
        ),
    },
    "3_single_decision_hypothesis": (
        "One fixed policy bundle: accepted distribution-day absorption rows are "
        "eligible only when the unchanged accepted-helper allocator selects no "
        "paper row on that signal date. Existing allocator source priority, "
        "distribution thresholds, top-1/day, paper notional, hold, costs, "
        "cooldown, core behavior, LLM/news, and live/default orders stay fixed."
    ),
    "4_acceptance_standard": (
        "Use docs/backtesting.md three canonical windows. Accept only if "
        "aggregate EV/PnL improve, no EV/PnL window regresses, sample/survival/"
        "drawdown/concentration guards pass, and exp-20260611-005 accepted "
        "allocator plus exp-20260611-007 distribution standalone comparators are "
        "beaten. Replay-only positives are not production-retained without "
        "shared daily parity."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260618_022_distribution_gap_fill_allocator.py"
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _install_replay_variant() -> None:
    original_priority = deepcopy(allocator_helper.SOURCE_PRIORITY)
    proposed_priority = deepcopy(original_priority)
    max_rank = max(int(meta.get("rank") or 0) for meta in proposed_priority.values())
    proposed_priority[DISTRIBUTION_SOURCE_FAMILY] = {
        "rank": max_rank + 1,
        "description": (
            "accepted distribution-day absorption source, eligible only on "
            "dates with no existing accepted allocator selection"
        ),
        "accepted_experiment": "exp-20260611-007",
        "accepted_ev_delta_sum": 0.5286,
        "accepted_pnl_delta_sum": 10432.91,
        "no_displacement_gate": True,
    }
    allocator_helper.SOURCE_PRIORITY.clear()
    allocator_helper.SOURCE_PRIORITY.update(proposed_priority)
    allocator_helper.RULE_VERSION = (
        "accepted_helper_source_priority_no_displacement_distribution_gap_replay_exp_20260618_022"
    )
    allocator_helper.SOURCE_RULE_VERSION = (
        "accepted_helper_source_priority_with_distribution_empty_date_allocation_v1_replay"
    )

    def _build_source_trades_with_distribution_gap(
        *,
        rows_by_ticker: dict[str, list[dict[str, Any]]],
        dates: list[str],
        window_label: str,
        window: dict[str, str],
        core_entries_by_date: dict[str, list[dict[str, Any]]],
        sector_entries: dict[str, dict[str, Any]],
        candidate_universe: dict[str, Any] | list[str] | None,
        calendar_dates: list[str] | None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        allocator_helper.SOURCE_PRIORITY.clear()
        allocator_helper.SOURCE_PRIORITY.update(original_priority)
        source_trades, source_audit = ORIGINAL_BUILD_SOURCE_TRADES(
            rows_by_ticker=rows_by_ticker,
            dates=dates,
            window_label=window_label,
            window=window,
            core_entries_by_date=core_entries_by_date,
            sector_entries=sector_entries,
            candidate_universe=candidate_universe,
            calendar_dates=calendar_dates,
        )
        baseline_selected, _, baseline_priority_audit = (
            allocator_helper.select_accepted_helper_source_priority_rows(
                source_rows=source_trades,
                trading_dates=dates,
                config=None,
                create_trades=False,
            )
        )
        baseline_selected_dates = {
            str(row.get("signal_date") or row.get("date") or "")[:10]
            for row in baseline_selected
        }

        distribution_trades, distribution_audit = (
            build_distribution_day_absorption_leadership_historical_trades(
                ohlcv_by_ticker=rows_by_ticker,
                core_entries_by_date=core_entries_by_date,
                windows=OrderedDict([(window_label, window)]),
                candidate_universe=candidate_universe,
                sector_entries=sector_entries,
            )
        )
        allocator_helper.SOURCE_PRIORITY.clear()
        allocator_helper.SOURCE_PRIORITY.update(proposed_priority)
        normalised: list[dict[str, Any]] = []
        blocked_by_existing_date = 0
        for row in distribution_trades:
            signal_date = str(row.get("signal_date") or row.get("date") or "")[:10]
            if signal_date in baseline_selected_dates:
                blocked_by_existing_date += 1
                continue
            normalised.append(
                {
                    **allocator_helper._normalise_source_row(
                        row,
                        DISTRIBUTION_SOURCE_FAMILY,
                    ),
                    "uses_free_ohlcv_only": True,
                    "uses_free_non_ohlcv": False,
                    "no_displacement_gap_candidate": True,
                }
            )

        source_trades.extend(normalised)
        source_audit["source_priority"] = allocator_helper.SOURCE_PRIORITY
        source_audit["source_trade_counts"][DISTRIBUTION_SOURCE_FAMILY] = len(
            normalised
        )
        source_audit["raw_candidate_counts"][DISTRIBUTION_SOURCE_FAMILY] = (
            distribution_audit.get("raw_candidate_count_by_window", {}).get(
                window_label
            )
        )
        source_audit["source_audits"][DISTRIBUTION_SOURCE_FAMILY] = {
            "rule_version": distribution_audit.get("rule_version"),
            "source_rule_version": distribution_audit.get("source_rule_version"),
            "scan": distribution_audit.get("scan_by_window", {}).get(window_label),
            "baseline_selected_dates": sorted(baseline_selected_dates),
            "baseline_selected_count": len(baseline_selected),
            "baseline_priority_audit": baseline_priority_audit,
            "raw_distribution_trade_count": len(distribution_trades),
            "blocked_by_existing_selected_date": blocked_by_existing_date,
            "eligible_empty_date_distribution_trade_count": len(normalised),
            "source_caveat": (
                "Runner-local replay only. Distribution rows are added only "
                "after removing dates where the unchanged accepted allocator "
                "already selected a row."
            ),
        }
        return source_trades, source_audit

    allocator_helper._build_source_trades = _build_source_trades_with_distribution_gap
    base.RULE_VERSION = allocator_helper.RULE_VERSION
    base.SOURCE_RULE_VERSION = allocator_helper.SOURCE_RULE_VERSION


def _binding_gate4(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = ORIGINAL_BINDING_GATE4(payload)
    numeric_passed = bool(gate4["passed"])
    failed = list(gate4.get("failed_reasons") or [])
    if numeric_passed:
        failed.append("shared_gap_fill_helper_not_implemented")
    gate4.update(
        {
            "numeric_gate4_passed": numeric_passed,
            "passed": False if numeric_passed else gate4["passed"],
            "failed_reasons": failed,
            "decision": (
                "observed_positive_distribution_no_displacement_gap_allocator_blocked_shared_parity"
                if numeric_passed
                else "rejected_distribution_no_displacement_gap_allocator"
            ),
            "shared_adapter_module": "runner_local_no_displacement_gap_replay",
            "daily_snapshot_source": "not_retained_replay_only_gap_variant",
        }
    )
    return gate4


def _configure_prior_module() -> None:
    prior.EXPERIMENT_ID = EXPERIMENT_ID
    prior.OWNER = OWNER
    prior.STEM = STEM
    prior.TRIAL_FAMILY = TRIAL_FAMILY
    prior.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    prior.CHANGED_VARIABLE = CHANGED_VARIABLE
    prior.OUT_DIR = OUT_DIR
    prior.OUT_JSON = OUT_JSON
    prior.LOG_JSON = LOG_JSON
    prior.TICKET_JSON = TICKET_JSON
    prior.CARD_MD = CARD_MD
    prior.MANIFEST_JSON = MANIFEST_JSON
    prior.EXPERIMENT_LOG = EXPERIMENT_LOG
    prior.REGISTRY_JSON = REGISTRY_JSON
    prior.PREDICTION = PREDICTION
    prior.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    prior.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    prior._install_rejected_variant = _install_replay_variant
    prior._binding_gate4 = _binding_gate4
    prior._build_card = _build_card
    prior._build_log_record = _build_log_record
    prior._update_registry = _update_registry
    prior._write_manifest = _write_manifest


def build_payload() -> dict[str, Any]:
    _configure_prior_module()
    payload = prior.build_payload()
    aggregate = payload["delta_metrics"]["aggregate"]
    numeric_passed = bool(payload["gate4"].get("numeric_gate4_passed"))
    for label, row in payload["window_rows"].items():
        source_audits = (
            payload.get("target_audit_by_window", {})
            .get(label, {})
            .get("source_audits_by_window", {})
        )
        distribution_audit = source_audits.get(DISTRIBUTION_SOURCE_FAMILY, {})
        row["baseline_allocator_selected_count"] = distribution_audit.get(
            "baseline_selected_count",
            0,
        )
        row["distribution_blocked_by_existing_selected_date_count"] = (
            distribution_audit.get("blocked_by_existing_selected_date", 0)
        )
        row["distribution_gap_eligible_source_trade_count"] = distribution_audit.get(
            "eligible_empty_date_distribution_trade_count",
            row.get("selected_source_counts", {}).get(DISTRIBUTION_SOURCE_FAMILY, 0),
        )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": (
                "observed_positive_blocked_shared_parity"
                if numeric_passed
                else "rejected"
            ),
            "decision": payload["gate4"]["decision"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "default_off_paper_allocator_gap_fill",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": (
                "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
            ),
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": (
                "new_gate_shape_no_displacement_allocator_admission_for_distribution_source"
            ),
            "nearby_prior_experiments": [
                "exp-20260611-007",
                "exp-20260611-008",
                "exp-20260612-013",
                "exp-20260618-021",
                "exp-20260611-005",
            ],
            "prior_trial_count": 1,
            "prediction": PREDICTION,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "production_impact": PRODUCTION_IMPACT,
            "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
            "total_pnl_delta": aggregate["total_pnl_delta_sum"],
            "numeric_gate4_passed": numeric_passed,
            "full_stack_verdict": (
                "blocked_shared_parity" if numeric_passed else "reject"
            ),
            "interpretation": (
                "Distribution empty-date allocator admission was numerically "
                "positive, but it is not retained because no shared gap-fill "
                "historical/daily helper was implemented."
                if numeric_passed
                else "Distribution empty-date allocator admission failed Gate 4 "
                "and is not retained."
            ),
            "rejection_reason": "; ".join(payload["gate4"]["failed_reasons"]),
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Replay-only runner first computes the unchanged accepted-helper "
        "allocator selections for each canonical window, then adds accepted "
        "distribution-day absorption source rows only on signal dates where "
        "that baseline allocator selected no row. It then uses the existing "
        "allocator selector, next-open entry, 10-trading-day exit, paper "
        "notional, cooldown, costs, and overlay metrics. No shared helper or "
        "production path is retained."
    )
    payload["parameters"].update(
        {
            "rule_version": allocator_helper.RULE_VERSION,
            "source_rule_version": allocator_helper.SOURCE_RULE_VERSION,
            "distribution_source_family": DISTRIBUTION_SOURCE_FAMILY,
            "no_displacement_gate": (
                "Distribution rows are removed on dates where the unchanged "
                "accepted allocator already selected a paper row."
            ),
        }
    )
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_numeric_gate4_passed": numeric_passed,
        "actual_retained_as_alpha": False,
        "failure_modes_observed": payload["gate4"]["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if numeric_passed else 0.0))
            ** 2,
            6,
        ),
    }
    payload["accepted_comparators"] = {
        "accepted_allocator": ACCEPTED_ALLOCATOR_COMPARATOR,
        "accepted_distribution_standalone": ACCEPTED_DISTRIBUTION_COMPARATOR,
    }
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "Distribution rows had enough incremental value on days not already "
            "claimed by the existing allocator, but the experiment stopped short "
            "of acceptance because the gap-fill policy is runner-local and not "
            "a shared daily helper."
            if numeric_passed
            else (
                "Removing displacement was not sufficient. Empty allocator "
                "dates did not supply distribution rows with enough incremental "
                "quality to beat the accepted allocator comparator after costs, "
                "cooldown, and concentration checks."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry distribution allocator variants by changing source "
            "rank, distribution thresholds, pressure lookback, top-N, hold, "
            "cooldown, notional, or another frozen-window empty-date routing "
            "variant."
        ),
        "new_evidence_required": (
            "Retry only with closed forward replacement-value rows, a shared "
            "daily no-displacement helper, or a new PIT flow/catalyst field "
            "that explains why empty-date distribution rows should displace "
            "accepted allocator idle cash."
        ),
    }
    payload["next_retry_requires"] = [
        "closed forward replacement-value rows",
        "shared daily no-displacement helper",
        "orthogonal PIT flow or catalyst field",
    ]
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return payload


def _window_table(payload: dict[str, Any]) -> list[str]:
    rows = [
        "| Window | Before EV | After EV | dEV | Accepted dEV | Before PnL | After PnL | dPnL | Accepted dPnL | DD d | Trades | Distribution selected | Distribution eligible | Distribution blocked |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        row = payload["window_rows"][label]
        comparator = ACCEPTED_ALLOCATOR_COMPARATOR["window_deltas"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | {cev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | ${cpnl:+,.2f} | {dd:+.4f} | {trades} | {selected} | {eligible} | {blocked} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                cev=comparator["ev"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                cpnl=comparator["pnl"],
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=row["target_trade_count"],
                selected=row["selected_source_counts"].get(
                    DISTRIBUTION_SOURCE_FAMILY,
                    0,
                ),
                eligible=row.get("distribution_gap_eligible_source_trade_count", 0),
                blocked=row.get(
                    "distribution_blocked_by_existing_selected_date_count",
                    0,
                ),
            )
        )
    return rows


def _build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Distribution Empty-Date Allocator",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            f"Full-stack verdict: `{payload['full_stack_verdict']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *_window_table(payload),
            "",
            "- Aggregate EV delta: `{:+.4f}` versus accepted allocator `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"],
                ACCEPTED_ALLOCATOR_COMPARATOR["aggregate_ev_delta"],
            ),
            "- Aggregate PnL delta: `${:+,.2f}` versus accepted allocator `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"],
                ACCEPTED_ALLOCATOR_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Numeric Gate 4 passed: `{}`".format(
                payload.get("numeric_gate4_passed"),
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Production Impact",
            "",
            PRODUCTION_IMPACT["parity_note"],
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
    numeric_passed = bool(payload.get("numeric_gate4_passed"))
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": numeric_passed,
        "production_accepted": False,
        "full_stack_verdict": payload["full_stack_verdict"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": payload["gate1"]["baseline_artifact"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate[
            "expected_value_score_delta_pct"
        ],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_comparators": payload["accepted_comparators"],
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
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][
                    label
                ]["total_pnl"],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
                "selected_source_counts": payload["window_rows"][label][
                    "selected_source_counts"
                ],
                "distribution_day_absorption_selected_count": payload["window_rows"][
                    label
                ]["selected_source_counts"].get(DISTRIBUTION_SOURCE_FAMILY, 0),
                "distribution_gap_eligible_source_trade_count": payload["window_rows"][
                    label
                ].get("distribution_gap_eligible_source_trade_count", 0),
                "distribution_blocked_by_existing_selected_date_count": payload[
                    "window_rows"
                ][label].get("distribution_blocked_by_existing_selected_date_count", 0),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _update_registry(payload: dict[str, Any]) -> None:
    result = {
        "decision": payload["decision"],
        "full_stack_verdict": payload["full_stack_verdict"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "accepted": False,
        "numeric_gate4_passed": payload["numeric_gate4_passed"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
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
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
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
    paths = [
        Path(__file__),
        OUT_JSON,
        LOG_JSON,
        TICKET_JSON,
        CARD_MD,
        MANIFEST_JSON,
        REGISTRY_JSON,
        EXPERIMENT_LOG,
    ]
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [_repo_rel(path) for path in paths],
        "file_hashes": {
            _repo_rel(path): framework._sha256(path)
            for path in paths
            if path.exists() and path != MANIFEST_JSON
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def main() -> None:
    _configure_prior_module()
    payload = build_payload()
    prior.persist(payload)
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
