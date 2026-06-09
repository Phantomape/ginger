from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

import exp_20260604_026_sec_ftd_finra_confirmed_candidate_pool as prior


EXPERIMENT_ID = "exp-20260609-020"
STEM = "sec_ftd_finra_no_core_flow"
TRIAL_FAMILY = "sec_ftd_finra_no_core_flow_candidate_pool"
TRIAL_VARIANT_ID = "sec_ftd_finra_no_core_flow_top1_no_backup_v1"
CHANGED_VARIABLE = "sec_ftd_finra_no_same_day_core_flow_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
ROOT = prior.ROOT
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260609_020_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = ROOT / "docs" / "experiment_registry.json"

ACCEPTED_FTD_FINRA_COMPARATOR = {
    "experiment_id": "exp-20260604-027",
    "decision": "accepted_default_off_sec_ftd_finra_shared_adapter",
    "expected_value_score_delta_sum": 0.4420,
    "total_pnl_delta_sum": 10100.49,
    "target_trade_count": 121,
}

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": 0.06,
    "expected_pnl_delta": 1200.0,
    "expected_ev_delta_sum": 0.06,
    "expected_pnl_delta_sum": 1200.0,
    "main_failure_modes": [
        "accepted_ftd_finra_comparator_not_beaten",
        "old_thin_regression",
        "sample_thinning",
        "core_flow_is_not_crowding_proxy",
    ],
    "confidence_reason": (
        "FTD+FINRA is an accepted free SEC/FINRA data edge. This tests a distinct "
        "displacement field, not FTD/FINRA threshold retuning: only accepted selected "
        "FTD+FINRA rows with no same-day core A/B entries are admitted, and no backup "
        "candidate is substituted after the no-core-flow exclusion."
    ),
}

PRODUCTION_IMPACT = {
    "mode": "historical_replay_only",
    "trade_enabled": False,
    "changes_live_orders": False,
    "changes_live_ranking": False,
    "changes_live_sizing": False,
    "changes_live_exits": False,
    "changes_live_watchlist": False,
    "changes_daily_default_off_snapshot": False,
    "shared_helper_changed": False,
    "parity_note": (
        "This runner does not edit the default-off SEC FTD+FINRA paper sleeve. A positive "
        "result would still need the same no-core-flow admission rule wired into the shared "
        "daily snapshot helper and backtest adapter before promotion."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _upsert_jsonl(path: Path, record: dict[str, Any], key: str = "experiment_id") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            try:
                current = json.loads(raw)
            except json.JSONDecodeError:
                lines.append(raw)
                continue
            if current.get(key) == record.get(key):
                lines.append(json.dumps(record, sort_keys=True))
                replaced = True
            else:
                lines.append(json.dumps(current, sort_keys=True))
    if not replaced:
        lines.append(json.dumps(record, sort_keys=True))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _candidate_rows_for_window(
    frames: dict[str, Any],
    label: str,
    cfg: dict[str, Any],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    base_candidates, diagnostics = prior._candidate_rows_for_window(frames, label, cfg, before_result)
    filtered: list[dict[str, Any]] = []
    rejected_same_day_core_flow = 0

    for row in base_candidates:
        same_day_core_entry_count = int(row.get("same_day_core_entry_count") or 0)
        updated = dict(row)
        updated["rule_version"] = RULE_VERSION
        updated["base_rule_version"] = getattr(prior, "RULE_VERSION", "unknown")
        updated["no_core_flow_filter"] = {
            "same_day_core_entry_count": same_day_core_entry_count,
            "accepted": same_day_core_entry_count == 0,
            "no_backup_substitution": True,
        }
        if same_day_core_entry_count > 0:
            rejected_same_day_core_flow += 1
            continue
        filtered.append(updated)

    updated_diagnostics = dict(diagnostics)
    updated_diagnostics.update(
        {
            "rule_version": RULE_VERSION,
            "base_rule_version": getattr(prior, "RULE_VERSION", "unknown"),
            "base_selected_candidate_count_before_no_core_filter": len(base_candidates),
            "rejected_same_day_core_flow": rejected_same_day_core_flow,
            "selected_after_no_core_filter": len(filtered),
            "no_backup_substitution": True,
            "same_day_core_flow_excluded": True,
            "ftd_finra_thresholds_changed": False,
        }
    )
    return filtered, updated_diagnostics


def _window_comparator_deltas(payload: dict[str, Any]) -> dict[str, dict[str, float]]:
    prior_artifact = (
        ROOT
        / "data"
        / "experiments"
        / "exp-20260604-026"
        / "exp_20260604_026_sec_ftd_finra_confirmed_candidate_pool.json"
    )
    if not prior_artifact.exists():
        return {}
    accepted_payload = json.loads(prior_artifact.read_text(encoding="utf-8"))
    deltas: dict[str, dict[str, float]] = {}
    for label, current_result in payload.get("window_results", {}).items():
        accepted_result = accepted_payload.get("window_results", {}).get(label, {})
        current_delta = current_result.get("delta", {})
        accepted_delta = accepted_result.get("delta", {})
        deltas[label] = {
            "current_ev_delta": float(current_delta.get("expected_value_score", 0.0) or 0.0),
            "accepted_ftd_finra_ev_delta": float(
                accepted_delta.get("expected_value_score", 0.0) or 0.0
            ),
            "ev_delta_vs_accepted": float(current_delta.get("expected_value_score", 0.0) or 0.0)
            - float(accepted_delta.get("expected_value_score", 0.0) or 0.0),
            "current_pnl_delta": float(current_delta.get("total_pnl", 0.0) or 0.0),
            "accepted_ftd_finra_pnl_delta": float(accepted_delta.get("total_pnl", 0.0) or 0.0),
            "pnl_delta_vs_accepted": float(current_delta.get("total_pnl", 0.0) or 0.0)
            - float(accepted_delta.get("total_pnl", 0.0) or 0.0),
        }
    return deltas


def _evaluate(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["aggregate"]
    failed_gates = list(payload.get("gate4", {}).get("failed_gates") or [])
    comparator = ACCEPTED_FTD_FINRA_COMPARATOR

    ev_delta = float(aggregate["expected_value_score_delta_sum"])
    pnl_delta = float(aggregate["total_pnl_delta_sum"])
    if ev_delta <= comparator["expected_value_score_delta_sum"]:
        failed_gates.append("accepted_ftd_finra_ev_not_beaten")
    if pnl_delta <= comparator["total_pnl_delta_sum"]:
        failed_gates.append("accepted_ftd_finra_pnl_not_beaten")

    failed_gates = sorted(set(failed_gates))
    passed = not failed_gates
    decision = (
        "positive_replay_lead_requires_shared_default_off_adapter"
        if passed
        else "rejected_ftd_finra_no_core_flow"
    )

    actual_success = 1 if passed else 0
    success_probability = float(PREDICTION["success_probability"])
    prediction = dict(PREDICTION)
    prediction.update(
        {
            "actual_success": actual_success,
            "actual_ev_delta_sum": ev_delta,
            "actual_pnl_delta_sum": pnl_delta,
            "brier_score": (success_probability - actual_success) ** 2,
        }
    )

    return {
        "failed_gates": failed_gates,
        "passed": passed,
        "decision": decision,
        "prediction": prediction,
    }


def _build_payload() -> dict[str, Any]:
    prior.framework.EXPERIMENT_ID = EXPERIMENT_ID
    prior.framework.TRIAL_FAMILY = TRIAL_FAMILY
    prior.framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    prior.framework.OUT_DIR = OUT_DIR
    prior.framework.OUT_JSON = OUT_JSON
    prior.framework.BEFORE_JSON = BEFORE_JSON
    prior.framework.AFTER_JSON = AFTER_JSON
    prior.framework.LOG_JSON = LOG_JSON
    prior.framework.CARD_MD = CARD_MD
    prior.framework.MANIFEST_JSON = MANIFEST_JSON
    prior.framework.TICKET_JSON = TICKET_JSON
    prior.framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    prior.framework.REGISTRY_JSON = REGISTRY_JSON
    prior.framework._candidate_rows_for_window = _candidate_rows_for_window

    payload = prior._ORIGINAL_BUILD_PAYLOAD()
    evaluation = _evaluate(payload)
    aggregate = payload["aggregate"]
    window_comparator_deltas = _window_comparator_deltas(payload)

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "positive_replay_lead" if evaluation["passed"] else "rejected",
            "decision": evaluation["decision"],
            "accepted": False,
            "created_at": _utc_now(),
            "closed_at": _utc_now(),
            "hypothesis": (
                "Accepted SEC FTD plus FINRA candidates may have better independent "
                "replacement value when the signal date has no same-day core A/B flow, "
                "avoiding duplicate exposure while keeping all FTD and FINRA thresholds fixed."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "free_sec_settlement_plus_borrow_pressure_displacement",
            "new_evidence_type": "same_day_core_flow_displacement_field_on_accepted_ftd_finra",
            "nearby_prior_experiments": [
                "exp-20260604-026",
                "exp-20260604-027",
                "exp-20260603-006",
                "exp-20260609-016",
            ],
            "prediction": evaluation["prediction"],
            "calibration": {
                "predicted_success_probability": PREDICTION["success_probability"],
                "actual_success": evaluation["prediction"]["actual_success"],
                "brier_score": evaluation["prediction"]["brier_score"],
            },
            "production_impact": PRODUCTION_IMPACT,
            "production_backtest_parity": {
                "passed": True,
                "scope": "historical_replay_only_no_live_or_daily_adapter_change",
                "backtest_production_consistency": (
                    "No production helper, live order, ranking, sizing, exit, or daily snapshot "
                    "path is modified by this experiment."
                ),
            },
            "accepted_comparators": [ACCEPTED_FTD_FINRA_COMPARATOR],
            "accepted_comparator_delta_by_window": window_comparator_deltas,
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "Candidate-pool/displacement alpha: accepted FTD+FINRA pressure may have "
                    "cleaner replacement value on dates without same-day core A/B flow."
                ),
                "2_history_check": (
                    "exp-20260604-026/027 accepted the shared SEC FTD+FINRA default-off sleeve; "
                    "exp-20260603-006/007 tested FINRA borrow pressure; exp-20260609-016 tested "
                    "core-flow confirmation in a different gap-hold sleeve and failed to beat the "
                    "accepted comparator."
                ),
                "3_single_decision_hypothesis": (
                    f"Only {CHANGED_VARIABLE} is evaluated. FTD thresholds, FINRA thresholds, "
                    "ranking top-1/day, entry timing, hold length, and paper notional stay fixed."
                ),
                "4_acceptance_criteria": (
                    "Use docs/backtesting.md canonical three windows. Retain only if all base Gate 4 "
                    "checks pass and aggregate EV/PnL beat the accepted FTD+FINRA comparator."
                ),
                "5_reproducibility": (
                    ".\\.venv\\Scripts\\python.exe -B "
                    "quant\\experiments\\exp_20260609_020_sec_ftd_finra_no_core_flow.py"
                ),
            },
        }
    )

    payload["parameters"].update(
        {
            "single_causal_variable": CHANGED_VARIABLE,
            "rule_version": RULE_VERSION,
            "base_rule_version": getattr(prior, "RULE_VERSION", "unknown"),
            "accepted_ftd_finra_thresholds_changed": False,
            "same_day_core_flow_excluded": True,
            "same_day_core_flow_required": False,
            "no_backup_substitution": True,
            "accepted_comparator_requirement": ACCEPTED_FTD_FINRA_COMPARATOR,
        }
    )

    payload["gate3"].update(
        {
            "new_filter_added_to_core_strategy": False,
            "paper_candidate_admission_rule": "exclude_accepted_selected_ftd_finra_rows_when_same_day_core_entries_gt_zero",
            "note": (
                "This is a default-off paper candidate-pool admission rule, not a core "
                "production filter."
            ),
        }
    )
    payload["gate4"].update(
        {
            "passed": evaluation["passed"],
            "decision": evaluation["decision"],
            "failed_gates": evaluation["failed_gates"],
            "accepted_comparators": [ACCEPTED_FTD_FINRA_COMPARATOR],
            "accepted_comparator_delta_by_window": window_comparator_deltas,
        }
    )

    if evaluation["passed"]:
        reflection_text = (
            "The no-core-flow displacement field beat the accepted FTD+FINRA replay comparator, "
            "but this runner remains replay-only. Promotion would require wiring the same field "
            "into the shared default-off daily adapter and parity-checking historical replay "
            "against the snapshot path before any live exposure."
        )
        next_steps = [
            "Implement shared default-off no-core-flow adapter with daily snapshot parity.",
            "Collect forward rows before any trade_enabled activation.",
        ]
    else:
        reflection_text = (
            "The no-core-flow displacement field did not beat the accepted FTD+FINRA comparator. "
            "The likely failure is that same-day core-flow presence is not a reliable crowding "
            "proxy here; excluding those dates removes some valid settlement/borrow-pressure "
            "winners without creating enough independent replacement value."
        )
        next_steps = [
            "Do not retune FTD/FINRA thresholds, top-N, hold length, cooldown, or no-core count on frozen windows.",
            "Only revisit this family with forward replacement rows or a materially new free-data field.",
        ]

    reflection = {
        "why_result_happened": reflection_text,
        "realized_failure_mode": (
            "none"
            if evaluation["passed"]
            else "accepted_ftd_finra_pnl_comparator_not_beaten_due_old_thin_underperformance"
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retune accepted FTD/FINRA thresholds, top-N/day, hold length, cooldown, "
            "notional, or the no-core-flow cutoff on the same frozen windows."
        ),
        "new_evidence_required": (
            "Forward replacement rows or a materially new free data field, such as a borrow-cost, "
            "catalyst, liquidity, or order-flow relation that explains why core-flow dates should "
            "be displaced rather than retained."
        ),
    }

    payload["gate4"]["rationale"] = reflection_text
    payload["gate4"]["requires_parity_before_promotion"] = evaluation["passed"]
    payload.update(
        {
            "post_run_reflection": reflection,
            "negative_reflection": "" if evaluation["passed"] else reflection_text,
            "why_failed_if_negative": "" if evaluation["passed"] else reflection_text,
            "next_steps": next_steps,
            "forbidden_nearby_retries": [
                "Retuning accepted FTD/FINRA thresholds on the same frozen windows",
                "Changing top-N/day or hold length to recover no-core-flow underperformance",
                "Requiring or excluding core-flow counts without new forward evidence",
            ],
            "expected_value_score_delta_sum": aggregate["expected_value_score_delta_sum"],
            "total_pnl_delta_sum": aggregate["total_pnl_delta_sum"],
            "related_files": [
                str(Path(__file__).relative_to(ROOT)),
                str(OUT_JSON.relative_to(ROOT)),
                str(LOG_JSON.relative_to(ROOT)),
                str(CARD_MD.relative_to(ROOT)),
                str(MANIFEST_JSON.relative_to(ROOT)),
                str(TICKET_JSON.relative_to(ROOT)),
                str(EXPERIMENT_LOG.relative_to(ROOT)),
                str(REGISTRY_JSON.relative_to(ROOT)),
            ],
        }
    )
    return payload


def _card(payload: dict[str, Any]) -> str:
    aggregate = payload["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} - SEC FTD + FINRA no-core-flow candidate source",
        "",
        f"- Status: {payload['status']}",
        f"- Decision: {payload['decision']}",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        f"- Trial variant: `{TRIAL_VARIANT_ID}`",
        f"- Aggregate baseline EV: {aggregate['baseline_expected_value_score_sum']:.4f}",
        f"- Aggregate after EV: {aggregate['after_expected_value_score_sum']:.4f}",
        f"- Aggregate EV delta: {aggregate['expected_value_score_delta_sum']:.4f}",
        f"- Aggregate PnL delta: ${aggregate['total_pnl_delta_sum']:.2f}",
        f"- Trade count: {aggregate['target_trade_count_sum']}",
        f"- Accepted comparator EV/PnL: {ACCEPTED_FTD_FINRA_COMPARATOR['expected_value_score_delta_sum']:.4f} / ${ACCEPTED_FTD_FINRA_COMPARATOR['total_pnl_delta_sum']:.2f}",
        f"- Failed gates: {', '.join(payload['gate4']['failed_gates']) or 'none'}",
        "",
        "## Three-window results",
        "",
        "| Window | EV delta | PnL delta | Trades | Baseline EV | After EV |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, result in payload["window_results"].items():
        delta = result["delta"]
        before = result["before"]
        after = result["after"]
        lines.append(
            "| "
            f"{label} | {delta['expected_value_score']:.4f} | ${delta['total_pnl']:.2f} | "
            f"{result['target_trade_count']} | {before['expected_value_score']:.4f} | "
            f"{after['expected_value_score']:.4f} |"
        )

    lines.extend(
        [
            "",
            "## Comparator deltas by window",
            "",
            "| Window | Current EV delta | Accepted EV delta | EV vs accepted | Current PnL delta | Accepted PnL delta |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for label, result in payload.get("accepted_comparator_delta_by_window", {}).items():
        lines.append(
            "| "
            f"{label} | {result['current_ev_delta']:.4f} | "
            f"{result['accepted_ftd_finra_ev_delta']:.4f} | "
            f"{result['ev_delta_vs_accepted']:.4f} | "
            f"${result['current_pnl_delta']:.2f} | "
            f"${result['accepted_ftd_finra_pnl_delta']:.2f} |"
        )

    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            (
                payload["post_run_reflection"]["why_result_happened"]
                if isinstance(payload["post_run_reflection"], dict)
                else payload["post_run_reflection"]
            ),
            "",
            "## Reproduction",
            "",
            "```powershell",
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260609_020_sec_ftd_finra_no_core_flow.py",
            "```",
            "",
            "## Production parity",
            "",
            payload["production_impact"]["parity_note"],
        ]
    )
    return "\n".join(lines) + "\n"


def _manifest(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "created_at": _utc_now(),
        "status": payload["status"],
        "decision": payload["decision"],
        "artifacts": {
            str(OUT_JSON.relative_to(ROOT)): _sha256(OUT_JSON),
            str(BEFORE_JSON.relative_to(ROOT)): _sha256(BEFORE_JSON),
            str(AFTER_JSON.relative_to(ROOT)): _sha256(AFTER_JSON),
            str(LOG_JSON.relative_to(ROOT)): _sha256(LOG_JSON),
            str(CARD_MD.relative_to(ROOT)): _sha256(CARD_MD),
        },
        "command": ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260609_020_sec_ftd_finra_no_core_flow.py",
        "no_javascript_used": True,
    }


def _registry_result(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": "alpha_search",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "accepted": False,
        "expected_value_score_delta_sum": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta_sum": aggregate["total_pnl_delta_sum"],
        "target_trade_count_sum": aggregate["target_trade_count_sum"],
        "gate4_passed": payload["gate4"]["passed"],
        "failed_gates": payload["gate4"]["failed_gates"],
        "artifact_path": str(OUT_JSON.relative_to(ROOT)),
        "log_path": str(LOG_JSON.relative_to(ROOT)),
        "card_path": str(CARD_MD.relative_to(ROOT)),
        "manifest_path": str(MANIFEST_JSON.relative_to(ROOT)),
        "closed_at": payload["closed_at"],
        "post_run_reflection": payload["post_run_reflection"],
    }


def run() -> dict[str, Any]:
    payload = _build_payload()

    _write_json(OUT_JSON, payload)
    _write_json(BEFORE_JSON, payload["before_metrics"])
    _write_json(AFTER_JSON, payload["after_metrics"])
    _write_json(LOG_JSON, payload)
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    CARD_MD.write_text(_card(payload), encoding="utf-8")
    _write_json(MANIFEST_JSON, _manifest(payload))
    _upsert_jsonl(EXPERIMENT_LOG, payload)

    scripts_dir = ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from experiment_registry import persist_self_registered_result

    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=_registry_result(payload),
        status=payload["status"],
        fields={
            "change_type": payload["change_type"],
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": payload["mechanism_family"],
            "artifact_path": str(OUT_JSON.relative_to(ROOT)),
            "log_path": str(LOG_JSON.relative_to(ROOT)),
            "card_path": str(CARD_MD.relative_to(ROOT)),
            "manifest_path": str(MANIFEST_JSON.relative_to(ROOT)),
        },
    )
    return payload


def main() -> None:
    payload = run()
    aggregate = payload["aggregate"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "expected_value_score_delta_sum": aggregate["expected_value_score_delta_sum"],
                "total_pnl_delta_sum": aggregate["total_pnl_delta_sum"],
                "target_trade_count_sum": aggregate["target_trade_count_sum"],
                "failed_gates": payload["gate4"]["failed_gates"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
