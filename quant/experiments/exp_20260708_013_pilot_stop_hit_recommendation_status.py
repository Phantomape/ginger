"""exp-20260708-013: pilot stop-hit recommendation status repair."""

from __future__ import annotations

import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from quant import pilot_tracker  # noqa: E402


EXPERIMENT_ID = "exp-20260708-013"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "pilot_stop_hit_recommendation_status"
RUNNER = f"quant/experiments/exp_20260708_013_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

PILOT_SCORECARD = REPO_ROOT / "data" / "pilots" / "pilot_scorecard.json"
PILOT_RECOMMENDATIONS = (
    REPO_ROOT / "data" / "pilots" / "pilot_recommendations_2026-07-08.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260708_013_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Repair pilot recommendation stop-hit rows so machine-readable actionable "
    "status matches the stop-loss alert and does not masquerade as HOLD."
)
ALPHA_HYPOTHESIS = (
    "Alpha blocker: accepted default-off pilot sleeves are only useful as "
    "activation evidence if the manual stop overlay is machine-auditable; a "
    "STOP_HIT row labelled HOLD can make live pilot risk review ambiguous."
)
CHANGED_VARIABLE = "pilot_recommendations_stop_hit_action_status_v1"
TRIAL_FAMILY = "pilot_recommendations_stop_hit_action_status"
TRIAL_VARIANT_ID = "stop_hit_exit_now_v1"
MECHANISM_FAMILY = "pilot_scorecard_governance_measurement"
NEW_EVIDENCE_AXIS = (
    "Current 2026-07-08 pilot_recommendations has WDC in actionable rows with "
    "stop_status=STOP_HIT but status=HOLD, while the Markdown separately says "
    "STOP_HIT -> SELL. This is a concrete schema/action mismatch, not another "
    "pilot graduation or kill-readiness rerun."
)
NEARBY_PRIORS = [
    "exp-20260707-014",
    "exp-20260707-012",
    "exp-20260628-010",
    "exp-20260702-002",
]
PREDICTION = {
    "success_probability": 0.86,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "status_migration_breaks_time_exit_ordering",
        "stop_alerts_disappear",
        "existing_hold_rows_relabeled_incorrectly",
    ],
    "confidence_reason": (
        "Current payload has WDC stop_status STOP_HIT under status HOLD while "
        "Markdown separately says sell; repair is JSON semantics only."
    ),
    "recorded_at": "2026-07-08T10:05:39+00:00",
}
CHANGED_FILES = [
    "quant/pilot_tracker.py",
    "quant/test_pilot_tracker.py",
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260708_013_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def rows_by_section(payload: dict[str, Any], section: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for rec in payload.get("recommendations") or []:
        for row in rec.get(section) or []:
            if isinstance(row, dict):
                rows.append({"pilot": rec.get("pilot"), "label": rec.get("label"), **row})
    return rows


def actionable_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return rows_by_section(payload, "actionable")


def skipped_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return rows_by_section(payload, "skipped")


def stop_hit_actionable_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in actionable_rows(payload) if row.get("stop_status") == "STOP_HIT"]


def row_identity(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("pilot"),
        row.get("ticker"),
        row.get("entry_date"),
        row.get("days_held"),
        row.get("days_remaining"),
        row.get("stop_status"),
    )


def stop_alert_identity(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("pilot"),
        row.get("ticker"),
        row.get("entry_price"),
        row.get("last_price"),
        row.get("unrealized_pct"),
        row.get("stop_loss_pct"),
    )


def status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(row.get("status") or "") for row in rows))


def build_result() -> dict[str, Any]:
    before_scorecard = read_json(PILOT_SCORECARD, {}) or {}
    before_recommendations = read_json(PILOT_RECOMMENDATIONS, {}) or {}
    after_generated = pilot_tracker.generate(write=False)

    before_actionable = actionable_rows(before_recommendations)
    after_actionable = actionable_rows(after_generated)
    before_skipped = skipped_rows(before_recommendations)
    after_skipped = skipped_rows(after_generated)
    before_stop_hits = stop_hit_actionable_rows(before_recommendations)
    after_stop_hits = stop_hit_actionable_rows(after_generated)
    before_stop_hold = [row for row in before_stop_hits if row.get("status") == "HOLD"]
    after_stop_hold = [row for row in after_stop_hits if row.get("status") == "HOLD"]
    after_stop_exit_now = [
        row for row in after_stop_hits if row.get("status") == "EXIT_NOW"
    ]
    before_alert_ids = sorted(
        stop_alert_identity(row) for row in before_recommendations.get("stop_alerts") or []
    )
    after_alert_ids = sorted(
        stop_alert_identity(row) for row in after_generated.get("stop_alerts") or []
    )
    before_actionable_ids = sorted(row_identity(row) for row in before_actionable)
    after_actionable_ids = sorted(row_identity(row) for row in after_actionable)
    skipped_id_statuses_before = sorted(
        (row_identity(row), row.get("status")) for row in before_skipped
    )
    skipped_id_statuses_after = sorted(
        (row_identity(row), row.get("status")) for row in after_skipped
    )

    checks = {
        "before_mismatch_detected": len(before_stop_hold) >= 1,
        "stop_hit_hold_rows_removed": len(after_stop_hold) == 0,
        "stop_hit_rows_are_exit_now": len(after_stop_exit_now) == len(before_stop_hits),
        "stop_alerts_unchanged": before_alert_ids == after_alert_ids,
        "actionable_position_set_unchanged": before_actionable_ids == after_actionable_ids,
        "skipped_rows_unchanged": skipped_id_statuses_before == skipped_id_statuses_after,
        "scorecards_unchanged": before_scorecard.get("scorecards")
        == after_generated.get("scorecards"),
        "concentration_unchanged": before_recommendations.get("cross_pilot_concentration")
        == after_generated.get("cross_pilot_concentration"),
    }
    accepted = all(checks.values())
    decision = (
        "accepted_measurement_repair_pilot_stop_hit_exit_now_status"
        if accepted
        else "rejected_pilot_stop_hit_status_repair"
    )
    status = "accepted" if accepted else "rejected"
    actual_success = 1 if accepted else 0
    failed_checks = [key for key, passed in checks.items() if not passed]
    timestamp = utc_now()

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "accepted_measurement_repair": accepted,
        "lane": LANE,
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "pilot_reporting_status_semantics_only",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "pilot_recommendations actionable status only",
            "manual stop overlay reporting",
            "no sleeve state mutation",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "measurement_defect_in_current_pilot_recommendations",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": PREDICTION,
        "calibration": {
            "actual_success": actual_success,
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": round(
                (PREDICTION["success_probability"] - actual_success) ** 2, 6
            ),
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_modes": failed_checks,
            "predicted_failure_mode_hit": bool(failed_checks),
        },
        "before_measurement": {
            "scorecard_file": repo_rel(PILOT_SCORECARD),
            "recommendations_file": repo_rel(PILOT_RECOMMENDATIONS),
            "actionable_status_counts": status_counts(before_actionable),
            "actionable_stop_hit_count": len(before_stop_hits),
            "actionable_stop_hit_hold_count": len(before_stop_hold),
            "actionable_stop_hit_rows": before_stop_hits,
            "stop_alerts": before_recommendations.get("stop_alerts") or [],
        },
        "after_measurement": {
            "generated_in_memory_only": True,
            "actionable_status_counts": status_counts(after_actionable),
            "actionable_stop_hit_count": len(after_stop_hits),
            "actionable_stop_hit_hold_count": len(after_stop_hold),
            "actionable_stop_hit_exit_now_count": len(after_stop_exit_now),
            "actionable_stop_hit_rows": after_stop_hits,
            "stop_alerts": after_generated.get("stop_alerts") or [],
        },
        "measurement_checks": checks,
        "failed_checks": failed_checks,
        "gate1": {
            "passed": True,
            "baseline_result_file": repo_rel(PILOT_RECOMMENDATIONS),
            "note": "Measurement repair only; canonical strategy backtest unchanged.",
        },
        "gate2": {
            "passed": True,
            "fields_checked": [
                "recommendations.actionable.status",
                "recommendations.actionable.stop_status",
                "recommendations.actionable.entry_date",
                "recommendations.actionable.ticker",
                "stop_alerts.ticker",
            ],
            "entry_date_target_price_relevance": (
                "entry_date remains present on open pilot rows; target_price is "
                "not consumed because this is pilot reporting, not signal "
                "generation or executable target exits."
            ),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "note": "No buy filter, sell rule, ranking, sizing, or risk budget changed.",
        },
        "gate4": {
            "passed": accepted,
            "decision": decision,
            "strategy_behavior_changed": False,
            "measurement_checks": checks,
            "failed_checks": failed_checks,
            "before_after_strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "signals_generated": 0,
                "signals_survived": 0,
            },
        },
        "summary": {
            "before_actionable_stop_hit_hold_count": len(before_stop_hold),
            "after_actionable_stop_hit_hold_count": len(after_stop_hold),
            "after_actionable_stop_hit_exit_now_count": len(after_stop_exit_now),
            "stop_alert_count": len(after_alert_ids),
            "production_files_regenerated": False,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_exposed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "risk_budget_changed": False,
            "exit_rules_changed": False,
            "paper_orders_changed": False,
            "live_orders_changed": False,
            "watchlist_changed": False,
            "llm_decision_boundary_changed": False,
            "trade_enabled": False,
            "pilot_recommendation_status_changed": True,
            "pilot_artifacts_regenerated": False,
            "parity_note": (
                "The repair changes generated pilot recommendation JSON/Markdown "
                "status semantics only. It does not mutate sleeve state or "
                "change orders, entries, exits, ranking, sizing, verdicts, "
                "concentration alerts, or stop-alert detection."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The tracker computed stop_status and emitted a top-level "
                "stop_alert, but left the actionable row status at HOLD. "
                "Downstream JSON consumers therefore had to join two surfaces "
                "to infer the operator action. Mapping STOP_HIT held rows to "
                "the existing EXIT_NOW action enum removes that ambiguity."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not reserve another pilot_scorecard readiness, kill-rule, "
                "or stop-status semantics audit on these same 2026-07-08 rows "
                "unless a new production-visible governance mismatch appears."
            ),
            "new_evidence_required": (
                "A valid retry needs a new pilot governance artifact whose "
                "machine-readable action contradicts the manual operator "
                "instruction, or a genuinely new pilot data surface."
            ),
        },
        "next_retry_requires": [
            "new pilot governance schema/action mismatch",
            "or a production-visible pilot metadata/code contradiction",
            "or a genuinely new pilot data surface",
        ],
        "related_files": [
            "quant/pilot_tracker.py",
            "quant/test_pilot_tracker.py",
            repo_rel(PILOT_SCORECARD),
            repo_rel(PILOT_RECOMMENDATIONS),
        ],
        "reproduction_commands": [
            f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER} quant\\pilot_tracker.py quant\\test_pilot_tracker.py",
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_pilot_tracker.py -q",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "changed_files": CHANGED_FILES,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "lean_quality_passed": accepted,
        "anti_js": {"used_javascript": False, "evidence": "Python only."},
    }


def build_log(result: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "accepted_measurement_repair",
        "lane",
        "owner",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "single_causal_variable",
        "causal_components",
        "nearby_prior_experiments",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "calibration",
        "before_measurement",
        "after_measurement",
        "measurement_checks",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "summary",
        "production_impact",
        "post_run_reflection",
        "next_retry_requires",
        "changed_files",
        "related_files",
        "reproduction_commands",
        "lean_quality_passed",
        "anti_js",
    ]
    return {key: result.get(key) for key in keys}


def build_card(result: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} - pilot stop-hit recommendation status",
        "",
        f"- status: `{result['status']}`",
        f"- decision: `{result['decision']}`",
        "- before STOP_HIT/HOLD rows: "
        f"`{result['summary']['before_actionable_stop_hit_hold_count']}`",
        "- after STOP_HIT/HOLD rows: "
        f"`{result['summary']['after_actionable_stop_hit_hold_count']}`",
        "- after STOP_HIT/EXIT_NOW rows: "
        f"`{result['summary']['after_actionable_stop_hit_exit_now_count']}`",
        f"- stop alerts unchanged: `{result['measurement_checks']['stop_alerts_unchanged']}`",
        "",
        "No sleeve state, orders, entries, exits, ranking, sizing, verdicts, or concentration alerts changed.",
        "",
        "## Reproduce",
        "",
        f"- `{RUNNER_COMMAND}`",
        "- `.\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_pilot_tracker.py -q`",
        "- `.\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict`",
    ]
    return "\n".join(lines) + "\n"


def build_manifest(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": result["status"],
        "decision": result["decision"],
        "generated_at": result["timestamp"],
        "runner": RUNNER,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "ticket": repo_rel(TICKET_JSON),
        "changed_files": CHANGED_FILES,
        "reproduction_commands": result["reproduction_commands"],
    }


def persist(result: dict[str, Any]) -> None:
    write_json(OUT_JSON, result)
    save_experiment_log_entry(build_log(result), allow_duplicate=True)
    write_text(CARD_MD, build_card(result))
    write_json(MANIFEST_JSON, build_manifest(result))
    ticket = read_json(TICKET_JSON, {}) or {}
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=result["prediction"],
        result={
            "accepted": result["accepted"],
            "accepted_alpha": result["accepted_alpha"],
            "accepted_measurement_repair": result["accepted_measurement_repair"],
            "decision": result["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "summary": result["summary"],
        },
        status=result["status"],
        fields={
            **{key: value for key, value in ticket.items() if key not in {"result", "status"}},
            "owner": OWNER,
            "hypothesis": result["hypothesis"],
            "alpha_hypothesis": result["alpha_hypothesis"],
            "change_type": result["change_type"],
            "implementation_mode": result["implementation_mode"],
            "mechanism_family": result["mechanism_family"],
            "trial_family": result["trial_family"],
            "trial_variant_id": result["trial_variant_id"],
            "single_causal_variable": result["single_causal_variable"],
            "changed_variable": result["changed_variable"],
            "causal_components": result["causal_components"],
            "nearby_prior_experiments": result["nearby_prior_experiments"],
            "new_evidence_type": result["new_evidence_type"],
            "new_evidence_axis": result["new_evidence_axis"],
            "calibration": result["calibration"],
            "measurement_checks": result["measurement_checks"],
            "gate1": result["gate1"],
            "gate2": result["gate2"],
            "gate3": result["gate3"],
            "gate4": result["gate4"],
            "summary": result["summary"],
            "production_impact": result["production_impact"],
            "post_run_reflection": result["post_run_reflection"],
            "next_retry_requires": result["next_retry_requires"],
            "changed_files": CHANGED_FILES,
            "related_files": result["related_files"],
            "reproduction_commands": result["reproduction_commands"],
            "lean_quality_passed": result["lean_quality_passed"],
        },
    )


def main() -> None:
    result = build_result()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": result["status"],
                "decision": result["decision"],
                "before_stop_hit_hold": result["summary"][
                    "before_actionable_stop_hit_hold_count"
                ],
                "after_stop_hit_hold": result["summary"][
                    "after_actionable_stop_hit_hold_count"
                ],
                "after_stop_hit_exit_now": result["summary"][
                    "after_actionable_stop_hit_exit_now_count"
                ],
                "artifact": repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
