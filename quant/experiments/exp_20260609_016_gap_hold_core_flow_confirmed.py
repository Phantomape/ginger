"""exp-20260609-016: core-flow confirmed gap-and-hold candidate pool.

Alpha search, replay-only. This keeps the fixed gap-and-hold institutional
demand morphology from exp-20260609-002, then adds one independent displacement
field: the signal date must already have selected core A/B flow, and the
candidate must not be the same ticker as a core entry. The result must beat both
accepted compression and accepted rolling-correlation peer-shock comparators
before it has replacement value.

No production code, shared helper, live/default orders, ranking, sizing, exits,
LLM/news path, watchlist, or run.py behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import exp_20260609_002_gap_and_hold_institutional_demand as prior


framework = prior.framework

EXPERIMENT_ID = "exp-20260609-016"
STEM = "gap_hold_core_flow_confirmed"
TRIAL_FAMILY = "gap_hold_core_flow_confirmed_candidate_pool"
TRIAL_VARIANT_ID = "gap_hold_core_flow_nonoverlap_top1_next_open_10d_v1"
CHANGED_VARIABLE = "gap_hold_core_flow_nonoverlap_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = prior.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260609_016_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

ACCEPTED_COMPRESSION_COMPARATOR = prior.ACCEPTED_COMPRESSION_COMPARATOR
ACCEPTED_ROLLING_CORR_COMPARATOR = {
    "experiment_id": "exp-20260606-025",
    "decision": "accepted_rolling_corr_peer_shock_shared_default_off_adapter",
    "expected_value_score_delta_sum": 0.3845,
    "total_pnl_delta_sum": 6107.66,
    "target_trade_count": 48,
}

PREDICTION = {
    "success_probability": 0.12,
    "expected_ev_delta": 0.20,
    "expected_pnl_delta": 3500.0,
    "main_failure_modes": [
        "sample_too_thin",
        "old_thin_regression",
        "accepted_comparators_not_beaten",
        "core_flow_overfit",
        "gap_momentum_relabel",
    ],
    "confidence_reason": (
        "Gap-hold alone had positive aggregate but failed old_thin/drawdown; "
        "core-flow confirmation has rescued relation sources before, but "
        "playbook treats gap-hold retries as high-risk unless they beat "
        "accepted comparators."
    ),
    "recorded_at": "2026-06-09T14:22:07+00:00",
}

PRODUCTION_IMPACT = {
    **prior.PRODUCTION_IMPACT,
    "parity_note": (
        "Replay-only scout. This experiment changes no production code. A "
        "positive result would require a shared default-off adapter that "
        "computes the same gap-hold morphology, same-day core-flow admission, "
        "same-ticker core-overlap exclusion, next-open paper entry, 10-day "
        "exit, costs, cooldown, comparator, and concentration controls in both "
        "historical replay and daily production before any report queue, paper "
        "ledger, candidate priority, sizing, watchlist, or order surface could "
        "change."
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidates, contexts, scan = prior._candidate_rows_for_window(
        snapshot=snapshot,
        cfg=cfg,
        before_result=before_result,
        sector_entries=sector_entries,
    )
    raw_count = len(candidates)
    same_day_count = sum(1 for row in candidates if row.get("same_day_ab_overlap"))
    same_ticker_count = sum(1 for row in candidates if row.get("same_ticker_ab_overlap"))
    filtered_by_date: dict[str, list[dict[str, Any]]] = {}
    filtered: list[dict[str, Any]] = []
    rejected_missing_core_flow = 0
    rejected_same_ticker = 0
    for row in candidates:
        updated = {
            **row,
            "rule_version": RULE_VERSION,
            "core_flow_confirmation": {
                "required": True,
                "same_day_ab_entry_count": int(row.get("same_day_ab_entry_count") or 0),
                "same_day_ab_overlap": bool(row.get("same_day_ab_overlap")),
                "same_ticker_core_overlap": bool(row.get("same_ticker_ab_overlap")),
                "same_ticker_core_overlap_excluded": True,
                "known_at": "after_signal_day_close_before_next_open_paper_entry",
                "rule_version": RULE_VERSION,
            },
        }
        if not updated["core_flow_confirmation"]["same_day_ab_overlap"]:
            rejected_missing_core_flow += 1
            continue
        if updated["core_flow_confirmation"]["same_ticker_core_overlap"]:
            rejected_same_ticker += 1
            continue
        filtered.append(updated)
        filtered_by_date.setdefault(str(updated["date"]), []).append(updated)

    for context in contexts:
        date_key = str(context.get("date") or "")
        day_rows = filtered_by_date.get(date_key, [])
        context["core_flow_confirmation_required"] = True
        context["same_ticker_core_overlap_excluded"] = True
        context["raw_candidate_count_before_core_flow_filter"] = context.get(
            "raw_candidate_count",
            0,
        )
        context["raw_candidate_count_after_core_flow_filter"] = len(day_rows)
        context["raw_candidate_count"] = len(day_rows)
        if day_rows:
            top = day_rows[0]
            context["top_candidate_after_core_flow"] = top["ticker"]
            context["top_score_after_core_flow"] = top["candidate_score"]

    scan.update(
        {
            "rule_version": RULE_VERSION,
            "base_gap_hold_rule_version": prior.RULE_VERSION,
            "core_flow_confirmation_required": True,
            "same_ticker_core_overlap_excluded": True,
            "raw_gap_hold_candidates_before_core_flow_filter": raw_count,
            "raw_gap_hold_candidates_with_same_day_core_flow": same_day_count,
            "raw_gap_hold_candidates_with_same_ticker_core_overlap": same_ticker_count,
            "raw_gap_hold_candidates_missing_core_flow": rejected_missing_core_flow,
            "raw_gap_hold_candidates_excluded_same_ticker_core_overlap": rejected_same_ticker,
            "raw_gap_hold_candidates_after_core_flow_filter": len(filtered),
            "core_flow_confirmed_dates": len(filtered_by_date),
        }
    )
    return filtered, contexts, scan


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = prior._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    if aggregate["expected_value_score_delta_sum"] <= ACCEPTED_ROLLING_CORR_COMPARATOR[
        "expected_value_score_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_rolling_corr_ev_not_beaten")
    if aggregate["total_pnl_delta_sum"] <= ACCEPTED_ROLLING_CORR_COMPARATOR[
        "total_pnl_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_rolling_corr_pnl_not_beaten")
    gate["accepted_comparators"] = {
        "compression": ACCEPTED_COMPRESSION_COMPARATOR,
        "rolling_corr_peer_shock": ACCEPTED_ROLLING_CORR_COMPARATOR,
    }
    gate["passed"] = not gate.get("failed_reasons")
    gate["decision"] = (
        "positive_replay_lead_not_promoted_gap_hold_core_flow_confirmed"
        if gate["passed"]
        else "rejected_gap_hold_core_flow_confirmed_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = prior.BASE_BUILD_PAYLOAD()
    aggregate = payload["delta_metrics"]["aggregate"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Gap-and-hold liquid stock breakouts may represent stronger "
                "institutional demand when the same date already has selected "
                "core A/B flow, while excluding same-ticker core overlap so "
                "the paper row measures independent replacement value."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_candidate_pool",
            "new_evidence_type": "production_visible_core_flow_displacement_field_on_gap_hold",
            "nearby_prior_experiments": [
                "exp-20260609-002",
                "exp-20260609-003",
                "exp-20260608-013",
                "exp-20260606-025",
            ],
            "prior_trial_count": 4,
            "multiple_testing_risk_bucket": "high",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_comparators": {
                "compression": ACCEPTED_COMPRESSION_COMPARATOR,
                "rolling_corr_peer_shock": ACCEPTED_ROLLING_CORR_COMPARATOR,
            },
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that same-day core flow does "
                "not turn gap-and-hold into independent replacement value; it "
                "either thins the sample or still relabels event-day momentum. "
                "Do not answer by sweeping gap, hold, close-location, volume, "
                "ret5/ret20, top-N, hold-day, cooldown, or paper notional "
                "thresholds on these frozen windows."
            ),
            "next_evidence_needed": (
                "A retry needs materially new PIT event/flow provenance or "
                "forward replacement-value rows. Pure gap-hold or core-flow "
                "threshold retunes should stay frozen."
            ),
        }
    )
    payload.setdefault("parameters", {}).update(
        {
            "single_causal_variable": CHANGED_VARIABLE,
            "core_flow_confirmation_required": True,
            "same_ticker_core_overlap_excluded": True,
            "selection_policy": "gap_hold_top1_after_core_flow_nonoverlap_no_backup_substitution",
            "accepted_comparator_requirement": (
                "Must beat both accepted compression exp-20260608-013 and "
                "accepted rolling-correlation peer-shock exp-20260606-025 "
                "aggregate EV/PnL."
            ),
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "candidate_pool / displacement: gap-and-hold event-day demand is "
            "more likely to be useful when independent core A/B flow confirms "
            "risk appetite on the same date, while same-ticker core overlap is "
            "excluded."
        ),
        "2_history_check": {
            "exp-20260609-002": (
                "Fixed gap-and-hold improved aggregate but failed old_thin and "
                "drawdown; this keeps morphology fixed and only adds core-flow "
                "admission."
            ),
            "exp-20260609-003": (
                "Breadth-confirmed gap-hold still failed; core-flow is a "
                "different production-visible displacement field."
            ),
            "exp-20260608-013": (
                "Accepted compression comparator; must be beaten before any "
                "gap-hold retry has replacement value."
            ),
            "exp-20260606-025": (
                "Accepted rolling-correlation peer-shock comparator; must also "
                "be beaten because it is the stronger relation alpha."
            ),
        },
        "3_single_policy_bundle": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "docs/backtesting.md three canonical windows; positive aggregate "
            "EV/PnL; no EV/PnL-regressed window; sample/concentration/drawdown/"
            "survival guards; and aggregate EV/PnL must beat both accepted "
            "comparators."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260609_016_gap_hold_core_flow_confirmed.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["decision"] = payload["gate4"]["decision"]
    payload["status"] = (
        "positive_replay_lead_not_promoted" if payload["gate4"]["passed"] else "rejected"
    )
    payload["interpretation"] = (
        "The core-flow-confirmed gap-and-hold source cleared strict Gate 4 "
        "and beat accepted comparators, but remains replay-only until a shared "
        "default-off adapter reproduces it."
        if payload["gate4"]["passed"]
        else (
            "The core-flow-confirmed gap-and-hold source did not clear Gate 4 "
            "or did not beat accepted compression/rolling-corr comparators; "
            "do not promote or locally retune this OHLCV gap-hold family on "
            "the frozen windows."
        )
    )
    payload["rejection_reason"] = (
        None if payload["gate4"]["passed"] else "; ".join(payload["gate4"]["failed_reasons"])
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "Same-day core-flow admission can reduce bad market states, but "
            "it may also remove the few independent gap-hold winners and leave "
            "a sample that cannot beat the accepted compression and relation "
            "adapters after next-open costs."
        ),
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping gap, low-vs-prior-close hold, "
            "close-vs-open, close-location, volume, ret5/ret20, core-flow "
            "count, top-N, hold-day, cooldown, or paper-notional thresholds "
            "on these frozen windows."
        ),
        "new_evidence_required": (
            "Need materially new PIT event/flow/catalyst provenance or closed "
            "forward replacement-value rows before revisiting gap-hold "
            "continuation."
        ),
    }
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


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | dPnL | Core-flow days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${dpnl:+,.2f} | {days} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                dpnl=delta.get("total_pnl", 0.0),
                days=scan.get("core_flow_confirmed_dates", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Gap-Hold Core-Flow Confirmed",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target trades: `{}`".format(
                payload["target_trade_summary"]["total_trade_count"]
            ),
            "- Compression comparator EV/PnL: `{}` / `${:,.2f}`".format(
                ACCEPTED_COMPRESSION_COMPARATOR["expected_value_score_delta_sum"],
                ACCEPTED_COMPRESSION_COMPARATOR["total_pnl_delta_sum"],
            ),
            "- Rolling-corr comparator EV/PnL: `{}` / `${:,.2f}`".format(
                ACCEPTED_ROLLING_CORR_COMPARATOR["expected_value_score_delta_sum"],
                ACCEPTED_ROLLING_CORR_COMPARATOR["total_pnl_delta_sum"],
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Production Impact",
            "",
            (
                "Replay-only and default-off paper only. No shared policy, run "
                "adapter, backtester adapter, production watchlist, order path, "
                "core entry, ranking, sizing, or exit behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = prior._build_log_record(payload)
    aggregate = payload["delta_metrics"]["aggregate"]
    record.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "accepted": False,
            "accepted_alpha": False,
            "numeric_gate4_passed": payload["gate4"]["passed"],
            "mechanism_family": "production_visible_free_ohlcv_candidate_pool",
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "hypothesis": payload["hypothesis"],
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
            "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
            "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
            "accepted_comparators": payload["accepted_comparators"],
            "gate4": payload["gate4"],
            "prediction": PREDICTION,
            "calibration": {**payload["calibration"]},
            "production_impact": PRODUCTION_IMPACT,
            "negative_reflection": payload["negative_reflection"],
            "post_run_reflection": payload["post_run_reflection"],
            "anti_js": "No JavaScript was used.",
        }
    )
    for row in record.get("windows") or []:
        label = row.get("label")
        if label in payload["context_scan_by_window"]:
            row["core_flow_confirmed_dates"] = payload["context_scan_by_window"][
                label
            ].get("core_flow_confirmed_dates")
    return record


def _patch_framework() -> None:
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.LOG_JSON = LOG_JSON
    framework.TICKET_JSON = TICKET_JSON
    framework.CARD_MD = CARD_MD
    framework.MANIFEST_JSON = MANIFEST_JSON
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.REGISTRY_JSON = REGISTRY_JSON
    framework.PREDICTION = PREDICTION
    framework.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._gate4 = _gate4
    framework._build_payload = _build_payload
    framework._build_card = _build_card
    framework._build_log_record = _build_log_record


_patch_framework()


def main() -> None:
    framework.main()


if __name__ == "__main__":
    main()
