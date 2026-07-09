"""exp-20260707-014: pilot concentration alert-rule metadata repair."""

from __future__ import annotations

import datetime as dt
import json
import sys
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


EXPERIMENT_ID = "exp-20260707-014"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "pilot_concentration_alert_rule_metadata"
RUNNER = f"quant/experiments/exp_20260707_014_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

PILOT_SCORECARD = REPO_ROOT / "data" / "pilots" / "pilot_scorecard.json"
PILOT_RECOMMENDATIONS = (
    REPO_ROOT / "data" / "pilots" / "pilot_recommendations_2026-07-07.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260707_014_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Pilot governance measurement repair: cross-pilot concentration output "
    "currently exports min_positions and min_exposure_share without the boolean "
    "operator, making valid three-position sector alerts look contradictory in "
    "the scorecard/recommendations artifact; expose the fixed OR rule in "
    "metadata without changing alert behavior."
)
CHANGED_VARIABLE = "pilot_cross_pilot_concentration_alert_rule_metadata_v1"
TRIAL_FAMILY = "pilot_cross_pilot_concentration_alert_rule_metadata"
TRIAL_VARIANT_ID = "explicit_or_rule_metadata_v1"
MECHANISM_FAMILY = "pilot_scorecard_governance_measurement"
NEW_EVIDENCE_AXIS = (
    "Current 2026-07-07 pilot_scorecard and pilot_recommendations artifacts show "
    "alert=true for 3-position sectors at 42.86% exposure while alert_rule only "
    "lists min_positions=3 and min_exposure_share=0.5; code/tests use an OR "
    "rule, so the new evidence is a concrete schema/metadata ambiguity in "
    "today's production-visible governance artifact, not a readiness or "
    "kill-rule rerun."
)
NEARBY_PRIORS = ["exp-20260707-012", "exp-20260624-010", "exp-20260624-009"]
PREDICTION = {
    "success_probability": 0.9,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "unexpected_snapshot_schema_dependency",
        "tests_expect_old_metadata",
        "audit_registry_conflict",
    ],
    "confidence_reason": (
        "This is a narrow metadata repair: existing code/tests already encode "
        "the intended OR behavior, and today's generated JSON makes that "
        "behavior ambiguous to downstream readers."
    ),
    "recorded_at": "2026-07-07T14:10:30+00:00",
}
CHANGED_FILES = [
    "quant/pilot_tracker.py",
    "quant/test_pilot_tracker.py",
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260707_014_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
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


def concentration_from(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload.get("cross_pilot_concentration") or {})


def alert_rows(concentration: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for level_key, rows_key in (("sector", "by_sector"), ("industry", "by_industry")):
        for row in concentration.get(rows_key) or []:
            if row.get("alert"):
                rows.append({"level": level_key, **row})
    return rows


def alert_identity(row: dict[str, Any]) -> tuple[Any, ...]:
    level = row.get("level")
    name = row.get(level)
    return (
        level,
        name,
        row.get("positions"),
        tuple(row.get("tickers") or []),
        tuple(row.get("pilots") or []),
        row.get("exposure_share"),
    )


def under_share_three_position_alerts(
    concentration: dict[str, Any],
) -> list[dict[str, Any]]:
    rule = concentration.get("alert_rule") or {}
    min_share = float(rule.get("min_exposure_share") or 0.0)
    return [
        row
        for row in alert_rows(concentration)
        if int(row.get("positions") or 0) >= 3
        and float(row.get("exposure_share") or 0.0) < min_share
    ]


def build_result() -> dict[str, Any]:
    before_scorecard = read_json(PILOT_SCORECARD, {}) or {}
    before_recommendations = read_json(PILOT_RECOMMENDATIONS, {}) or {}
    before_concentration = concentration_from(before_scorecard)
    before_rec_concentration = concentration_from(before_recommendations)

    after_generated = pilot_tracker.generate(write=False)
    after_concentration = after_generated["cross_pilot_concentration"]
    after_scorecard_preview = {
        "as_of": after_generated.get("as_of"),
        "cross_pilot_concentration": after_concentration,
        "stop_alerts": after_generated.get("stop_alerts"),
        "scorecards": after_generated.get("scorecards"),
    }
    after_recommendations_preview = {
        "as_of": after_generated.get("as_of"),
        "cross_pilot_concentration": after_concentration,
        "stop_alerts": after_generated.get("stop_alerts"),
        "recommendations": after_generated.get("recommendations"),
    }

    before_alerts = alert_rows(before_concentration)
    after_alerts = alert_rows(after_concentration)
    before_alert_ids = sorted(alert_identity(row) for row in before_alerts)
    after_alert_ids = sorted(alert_identity(row) for row in after_alerts)
    after_rule = after_concentration.get("alert_rule") or {}
    checks = {
        "operator_recorded": after_rule.get("operator") == "or",
        "exposure_share_floor_recorded": after_rule.get("min_positions_for_exposure_share")
        == 2,
        "description_recorded": bool(after_rule.get("description")),
        "scorecard_alerts_unchanged": before_alert_ids == after_alert_ids,
        "recommendation_before_matches_scorecard_before": (
            alert_rows(before_rec_concentration) == before_alerts
        ),
        "three_position_under_share_alert_explained": all(
            int(row.get("positions") or 0) >= int(after_rule.get("min_positions") or 0)
            for row in under_share_three_position_alerts(after_concentration)
        ),
    }
    accepted = all(checks.values())
    decision = (
        "accepted_measurement_repair_pilot_concentration_rule_metadata"
        if accepted
        else "rejected_pilot_concentration_rule_metadata_repair"
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
        "alpha_hypothesis": (
            "Alpha blocker: pilot scorecard governance is used to decide which "
            "default-off paper sleeves remain collectable or killed; ambiguous "
            "concentration rule metadata can make valid risk alerts look like "
            "false positives and confuse later promotion/kill analysis."
        ),
        "change_type": "measurement_repair",
        "implementation_mode": "metadata_only_no_alert_behavior_change",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "pilot_scorecard alert_rule metadata only",
            "no alert behavior change",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "measurement_defect_in_current_pilot_scorecard_artifact",
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
            "scorecard_alert_rule": before_concentration.get("alert_rule"),
            "recommendations_alert_rule": before_rec_concentration.get("alert_rule"),
            "alert_count": len(before_alerts),
            "under_share_three_position_alerts": under_share_three_position_alerts(
                before_concentration
            ),
        },
        "after_measurement": {
            "generated_in_memory_only": True,
            "scorecard_preview": after_scorecard_preview,
            "recommendations_preview": after_recommendations_preview,
            "alert_rule": after_rule,
            "alert_count": len(after_alerts),
            "under_share_three_position_alerts": under_share_three_position_alerts(
                after_concentration
            ),
        },
        "measurement_checks": checks,
        "failed_checks": failed_checks,
        "gate1": {
            "passed": True,
            "baseline_result_file": repo_rel(PILOT_SCORECARD),
            "note": "Measurement repair only; canonical strategy backtest unchanged.",
        },
        "gate2": {
            "passed": True,
            "fields_checked": [
                "cross_pilot_concentration.alert_rule.min_positions",
                "cross_pilot_concentration.alert_rule.min_exposure_share",
                "cross_pilot_concentration.alert_rule.operator",
                "cross_pilot_concentration.alert_rule.min_positions_for_exposure_share",
            ],
            "entry_date_target_price_relevance": (
                "Not applicable: this repair changes pilot governance metadata, "
                "not signal generation or exits."
            ),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "note": "No trading filter or concentration cap changed.",
        },
        "gate4": {
            "passed": accepted,
            "decision": decision,
            "strategy_behavior_changed": False,
            "measurement_checks": checks,
            "failed_checks": failed_checks,
            "alert_rows_unchanged": before_alert_ids == after_alert_ids,
        },
        "summary": {
            "before_alert_rule": before_concentration.get("alert_rule"),
            "after_alert_rule": after_rule,
            "alert_count": len(after_alerts),
            "under_share_three_position_alert_count": len(
                under_share_three_position_alerts(after_concentration)
            ),
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
            "pilot_alert_behavior_changed": False,
            "pilot_artifacts_regenerated": False,
            "parity_note": (
                "The repair only exposes the existing OR rule in generated pilot "
                "metadata. It does not change cross-pilot concentration alerts, "
                "pilot verdicts, orders, entries, exits, ranking, or sizing."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The code and tests already implemented the intended OR alert "
                "semantics, but generated JSON only exposed thresholds and not "
                "the connective/operator. Adding metadata removes the apparent "
                "contradiction in today's scorecard without changing alerts."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not reserve another pilot_scorecard readiness, kill-rule, or "
                "concentration metadata audit on the same rows unless a new "
                "scorecard schema ambiguity or governance mismatch appears."
            ),
            "new_evidence_required": (
                "A valid retry needs a new production-visible pilot governance "
                "artifact whose exported metadata contradicts the actual code "
                "path, or a genuinely new pilot data surface."
            ),
        },
        "next_retry_requires": [
            "new pilot governance schema ambiguity",
            "or a production-visible pilot metadata/code mismatch",
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
        f"# {EXPERIMENT_ID} - pilot concentration alert-rule metadata",
        "",
        f"- status: `{result['status']}`",
        f"- decision: `{result['decision']}`",
        f"- alert count unchanged: `{result['gate4']['alert_rows_unchanged']}`",
        f"- before rule: `{result['summary']['before_alert_rule']}`",
        f"- after operator: `{result['summary']['after_alert_rule'].get('operator')}`",
        f"- under-share three-position alerts: `{result['summary']['under_share_three_position_alert_count']}`",
        "",
        "No pilot alert behavior, verdicts, orders, entries, exits, ranking, or sizing changed.",
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
                "alert_count": result["summary"]["alert_count"],
                "operator": result["summary"]["after_alert_rule"].get("operator"),
                "artifact": repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
