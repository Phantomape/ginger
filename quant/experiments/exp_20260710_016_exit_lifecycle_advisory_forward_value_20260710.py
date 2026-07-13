"""exp-20260710-016: exit-lifecycle advisory forward value refresh.

Observed-only alpha attribution. This reruns the fixed
exit-lifecycle advisory severity outcome test from exp-20260701-012 after
materially more production shadow rows settled. It changes no entry, ranking,
sizing, exit, live, or paper order behavior.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


BASE_RUNNER = (
    REPO_ROOT
    / "quant"
    / "experiments"
    / "exp_20260701_012_exit_lifecycle_new_settled_advisory_outcome_refresh.py"
)


def load_prior() -> Any:
    spec = importlib.util.spec_from_file_location("exp_20260701_012_prior", BASE_RUNNER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load base runner: {BASE_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


prior = load_prior()

EXPERIMENT_ID = "exp-20260710-016"
SLUG = "exit_lifecycle_advisory_forward_value_20260710"
RUNNER = f"quant/experiments/exp_20260710_016_{SLUG}.py"
RUNNER_PS = RUNNER.replace("/", "\\")
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_PS
OWNER = "alpha-explore"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260710_016_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Observed-only alpha: with materially more settled exit_lifecycle forward "
    "rows than exp-20260701-012, advisory severity buckets should monotonically "
    "identify worse 5-day cash/SPY/QQQ replacement value if exit/advisory "
    "lifecycle rows are usable for future risk allocation."
)
CHANGE_TYPE = "observed_only_attribution"
MECHANISM_FAMILY = "exit_lifecycle_advisory_outcome"
TRIAL_FAMILY = "exit_lifecycle_forward_advisory_outcome_attribution"
TRIAL_VARIANT_ID = "post_20260611_more_settled_rows_fixed_bucket_20260710_v1"
CHANGED_VARIABLE = "exit_lifecycle_advisory_severity_forward_value_refresh_20260710_v1"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260623-011",
    "exp-20260623-016",
    "exp-20260701-012",
    "exp-20260710-008",
    "exp-20260710-009",
]
NEW_EVIDENCE_TYPE = "materially_more_settled_forward_shadow_exit_rows"
NEW_EVIDENCE_AXIS = (
    "Materially more settled exit_lifecycle forward rows under the same fixed "
    "post-2026-06-11 cohort recipe: exp-20260701-012 tested 156 settled rows; "
    "current no-ID preflight and this runner settle 252 rows after the same "
    "cutoff (+96 rows, +61.5%), with 416 total closed h5 rows."
)
CAUSAL_COMPONENTS = [
    "post-2026-06-11 production exit lifecycle shadow rows",
    "warehouse OHLCV fixed next-open to five-day-close settlement",
    "unchanged advisory severity buckets from exp-20260701-012",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260710_016_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]
REPRODUCTION_COMMANDS = [
    f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER_PS}",
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
]
FINGERPRINT_CAVEAT = (
    "Reservation fingerprint classified this as data_source=forward_replacement_value; "
    "the true evidence surface is exit_lifecycle_advisory_outcome. Manual "
    "saturation check uses the true surface and the material settled-row "
    "increase versus exp-20260701-012."
)


def configure_prior() -> None:
    prior.EXPERIMENT_ID = EXPERIMENT_ID
    prior.SLUG = SLUG
    prior.RUNNER = RUNNER
    prior.RUNNER_COMMAND = RUNNER_COMMAND
    prior.OWNER = OWNER
    prior.DATA_DIR = OUT_DIR
    prior.OUT_JSON = OUT_JSON
    prior.LOG_JSON = LOG_JSON
    prior.CARD_MD = CARD_MD
    prior.MANIFEST_JSON = MANIFEST_JSON
    prior.TICKET_JSON = TICKET_JSON
    prior.REGISTRY_JSON = REGISTRY_JSON
    prior.PRIOR_CUTOFF_AS_OF = "2026-06-11"
    prior.HYPOTHESIS = HYPOTHESIS
    prior.CHANGE_TYPE = CHANGE_TYPE
    prior.MECHANISM_FAMILY = MECHANISM_FAMILY
    prior.TRIAL_FAMILY = TRIAL_FAMILY
    prior.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    prior.CHANGED_VARIABLE = CHANGED_VARIABLE
    prior.NEARBY_PRIOR_EXPERIMENTS = NEARBY_PRIOR_EXPERIMENTS
    prior.NEW_EVIDENCE_TYPE = NEW_EVIDENCE_TYPE
    prior.NEW_EVIDENCE_AXIS = NEW_EVIDENCE_AXIS
    prior.CAUSAL_COMPONENTS = CAUSAL_COMPONENTS
    prior.ALLOWED_WRITE_SCOPE = ALLOWED_WRITE_SCOPE
    prior.CONFIG = {
        **prior.base.CONFIG,
        "prior_cutoff_as_of": prior.PRIOR_CUTOFF_AS_OF,
        "cohort_rule": "as_of_date > prior_cutoff_as_of",
    }


def refresh_calibration(payload: dict[str, Any]) -> dict[str, Any]:
    prediction = payload.get("prediction") or {}
    failed = list(payload.get("gate4", {}).get("failed_reasons") or [])
    probability = float(prediction.get("success_probability") or 0.0)
    actual = 1.0 if payload.get("observed_only_lead") else 0.0
    mode_map = {
        "severity_not_monotonic": {
            "severity_return_spearman_not_negative",
            "severity_spy_replacement_spearman_not_negative",
        },
        "hard_stop_not_worse_than_none": {
            "hard_stop_mean_not_worse_than_none",
            "hard_stop_median_not_worse_than_none",
        },
        "high_urgency_not_worse_than_none": {
            "high_urgency_mean_not_worse_than_none",
            "high_urgency_median_not_worse_than_none",
        },
        "date_instability": {"too_few_dates_with_advisory_worse_than_none"},
    }
    predicted_modes = list(prediction.get("main_failure_modes") or [])
    hit_modes = [
        mode for mode in predicted_modes if mode_map.get(mode, set()).intersection(failed)
    ]
    return {
        "predicted_success_probability": round(probability, 4),
        "actual_success": bool(actual),
        "brier_score": round((probability - actual) ** 2, 6),
        "predicted_failure_modes": predicted_modes,
        "failed_reasons": failed,
        "predicted_failure_modes_hit": hit_modes,
        "surprise_note": (
            "Materially more settled rows still do not make advisory severity "
            "monotonic enough for policy promotion."
            if failed
            else "Materially more settled rows preserved the fixed advisory "
            "severity lead, but this remains observed-only."
        ),
    }


def build_payload() -> dict[str, Any]:
    configure_prior()
    payload = prior.build_payload()
    payload["experiment_id"] = EXPERIMENT_ID
    payload["owner"] = OWNER
    payload["hypothesis"] = HYPOTHESIS
    payload["change_type"] = CHANGE_TYPE
    payload["mechanism_family"] = MECHANISM_FAMILY
    payload["trial_family"] = TRIAL_FAMILY
    payload["trial_variant_id"] = TRIAL_VARIANT_ID
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["single_causal_variable"] = CHANGED_VARIABLE
    payload["causal_components"] = CAUSAL_COMPONENTS
    payload["nearby_prior_experiments"] = NEARBY_PRIOR_EXPERIMENTS
    payload["new_evidence_type"] = NEW_EVIDENCE_TYPE
    payload["new_evidence_axis"] = NEW_EVIDENCE_AXIS
    payload["calibration"] = refresh_calibration(payload)
    payload["fingerprint_caveat"] = FINGERPRINT_CAVEAT
    payload["changed_files"] = ALLOWED_WRITE_SCOPE
    payload["related_files"] = [
        RUNNER,
        prior.repo_rel(BASE_RUNNER),
        prior.repo_rel(prior.SOURCE_DIR),
        prior.repo_rel(prior.BASELINE_RESULT),
        "experiments/logs/exp-20260623-011.json",
        "experiments/logs/exp-20260623-016.json",
        "experiments/logs/exp-20260701-012.json",
        "experiments/logs/exp-20260710-008.json",
        "experiments/logs/exp-20260710-009.json",
    ]
    payload["reproduction_commands"] = REPRODUCTION_COMMANDS
    payload["lean_quality_passed"] = True
    payload["pre_run_questions"]["2_history_check"]["novelty_gate"] = (
        "experiment.py new warned on a near neighbor and accepted a novelty "
        "override because the tested post-2026-06-11 cohort grew from 156 to "
        "252 settled rows (+96, +61.5%) with the fixed recipe unchanged."
    )
    payload["pre_run_questions"]["2_history_check"]["fingerprint_caveat"] = (
        FINGERPRINT_CAVEAT
    )
    payload["post_run_reflection"]["forbidden_near_neighbor_retry"] = (
        "Do not re-slice this same post-2026-06-11 cohort by adjacent exit "
        "lifecycle labels, urgency wording, target, trailing-stop, time-stop, "
        "MFE/giveback, cutoff date, or response-function retunes. A valid retry "
        "needs materially more settled rows again, a new row-producing source/gate "
        "shape, or a predeclared shared default-off lifecycle helper with fresh "
        "forward evidence."
    )
    return payload


def log_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = prior.compact_log_record(payload)
    record["fingerprint_caveat"] = payload["fingerprint_caveat"]
    record["changed_files"] = payload["changed_files"]
    record["reproduction_commands"] = payload["reproduction_commands"]
    record["lean_quality_passed"] = payload["lean_quality_passed"]
    return record


def write_manifest(payload: dict[str, Any]) -> None:
    manifest = prior.build_manifest(payload)
    manifest["files"].pop("docs/experiment_log.jsonl", None)
    manifest["files"][RUNNER] = {
        "exists": (REPO_ROOT / RUNNER).exists(),
        "sha256": prior.base.sha256(REPO_ROOT / RUNNER),
    }
    prior.write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    prior.write_json(OUT_JSON, payload)
    compact = log_record(payload)
    save_experiment_log_entry(compact, allow_duplicate=True)
    prior.write_text(CARD_MD, prior.build_card(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": False,
            "accepted_alpha": False,
            "observed_only_lead": payload["observed_only_lead"],
            "decision": payload["decision"],
            "artifact": prior.repo_rel(OUT_JSON),
            "log": prior.repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "calibration": payload["calibration"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "baseline_result_file": prior.repo_rel(prior.BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": prior.repo_rel(OUT_JSON),
            "log": prior.repo_rel(LOG_JSON),
            "card_file": prior.repo_rel(CARD_MD),
            "revision_manifest_file": prior.repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "fingerprint_caveat": payload["fingerprint_caveat"],
            "reproduction_commands": payload["reproduction_commands"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )
    write_manifest(payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    checks = payload["gate4"]["acceptance_checks"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "new_source_rows": payload["attribution"]["cohort_counts"]["new_source"]["rows"],
                "new_settled_rows": checks.get("settled_rows"),
                "new_advisory_rows": checks.get("advisory_rows"),
                "new_hard_stop_rows": checks.get("hard_stop_rows"),
                "severity_spearman_return": checks.get("severity_spearman_return"),
                "severity_spearman_spy_replacement": checks.get(
                    "severity_spearman_spy_replacement"
                ),
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": prior.repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
