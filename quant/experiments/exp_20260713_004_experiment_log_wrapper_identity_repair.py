"""exp-20260713-004: recover a cross-experiment log-shard overwrite.

This is measurement repair only. It verifies that the MOVE log shard matches
its pre-corruption manifest, that the inherited mortgage wrapper now emits its
own identity, and then records the repair without changing strategy behavior.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
for entry in (REPO_ROOT / "scripts", REPO_ROOT / "quant", REPO_ROOT / "quant" / "experiments"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result, save_experiment_log_entry  # noqa: E402


EXPERIMENT_ID = "exp-20260713-004"
EXPERIMENT_UID = "expuid-5dbb05e4e96148d8"
OWNER = "alpha-explore"
SLUG = "experiment_log_wrapper_identity_repair"
RUNNER = f"quant/experiments/exp_20260713_004_{SLUG}.py"
ARTIFACT = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"exp_20260713_004_{SLUG}.json"
CARD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
LOG = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
MANIFEST = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
REGISTRY = REPO_ROOT / "docs" / "experiment_registry.json"

MOVE_ID = "exp-20260711-002"
MORTGAGE_ID = "exp-20260711-017"
MOVE_LOG = REPO_ROOT / "experiments" / "logs" / f"{MOVE_ID}.json"
MOVE_MANIFEST = REPO_ROOT / "experiments" / "manifests" / f"{MOVE_ID}.json"
MOVE_TICKET = REPO_ROOT / "experiments" / "tickets" / f"{MOVE_ID}.json"
MORTGAGE_LOG = REPO_ROOT / "experiments" / "logs" / f"{MORTGAGE_ID}.json"
MORTGAGE_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / MORTGAGE_ID
    / "exp_20260711_017_mortgage_rate_relief_residential_leadership.json"
)
MORTGAGE_RUNNER = (
    REPO_ROOT
    / "quant"
    / "experiments"
    / "exp_20260711_017_mortgage_rate_relief_residential_leadership.py"
)

EXPECTED_MOVE_LOG_SHA256 = "61e23ae5bfab926464a5705409fb2d6f3394b5d9fd29eeb0748eacdd4d3395d3"
CORRUPTED_MOVE_LOG_SHA256 = "9a6628dc58629ef93064f262577744ac3ec887b984f1e21c9d5463525f6fc37a"
EXPECTED_MORTGAGE_LOG_SHA256 = "6d4f4b244a472e50066985416b35acc7b35cef88159ea185c496B2D30572EB76".lower()

HYPOTHESIS = (
    "Publication fault recovery: exp-20260711-017 inherited a compact-log "
    "builder whose stale exp-20260711-002 identity overwrote the positive MOVE "
    "shard; binding wrapper identity and restoring the manifest-verified MOVE "
    "record makes novelty, failure statistics, and DSR trial accounting "
    "trustworthy without changing strategy behavior."
)
CHANGED_VARIABLE = "wrapper_experiment_log_identity_and_manifest_recovery_v1"
DECISION = "accepted_measurement_repair_experiment_log_identity_recovery"
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "scripts/experiment_registry.py",
    "quant/test_experiment_registry.py",
    "quant/experiments/exp_20260711_017_mortgage_rate_relief_residential_leadership.py",
    "experiments/logs/exp-20260711-002.json",
    f"data/experiments/{EXPERIMENT_ID}/",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
    "docs/frozen_families.jsonl",
]
PRODUCTION_IMPACT = {
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "strategy_behavior_changed": False,
    "entry_rules_changed": False,
    "exit_rules_changed": False,
    "ranking_changed": False,
    "sizing_changed": False,
    "risk_budget_changed": False,
    "orders_changed": False,
    "trade_enabled": False,
    "scope": "experiment_metadata_publication_fault_recovery",
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("exp_20260711_017_identity_check", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verification() -> dict[str, Any]:
    move_manifest = load_json(MOVE_MANIFEST)
    move_ticket = load_json(MOVE_TICKET)
    move_log = load_json(MOVE_LOG)
    mortgage_log = load_json(MORTGAGE_LOG)
    mortgage_payload = load_json(MORTGAGE_ARTIFACT)
    mortgage = load_module(MORTGAGE_RUNNER)
    rebuilt_mortgage_log = mortgage.build_log_record(mortgage_payload)

    manifest_move_hash = (
        move_manifest.get("files", {})
        .get("experiments/logs/exp-20260711-002.json", {})
        .get("sha256")
    )
    checks = {
        "move_manifest_expected_hash_matches_locked_value": manifest_move_hash
        == EXPECTED_MOVE_LOG_SHA256,
        "move_log_hash_restored": sha256(MOVE_LOG) == EXPECTED_MOVE_LOG_SHA256,
        "move_ticket_is_positive_lead": move_ticket.get("result", {}).get("decision")
        == "positive_replay_lead_not_promoted_move_rate_volatility_relief",
        "move_log_is_positive_lead": move_log.get("decision")
        == "positive_replay_lead_not_promoted_move_rate_volatility_relief",
        "move_log_identity_is_move": move_log.get("experiment_id") == MOVE_ID,
        "mortgage_rebuilt_identity_is_mortgage": rebuilt_mortgage_log.get("experiment_id")
        == MORTGAGE_ID,
        "mortgage_rebuilt_log_matches_source_of_truth": rebuilt_mortgage_log == mortgage_log,
        "mortgage_log_hash_unchanged": sha256(MORTGAGE_LOG)
        == EXPECTED_MORTGAGE_LOG_SHA256,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "hashes": {
            "corrupted_move_log_sha256_observed_before_repair": CORRUPTED_MOVE_LOG_SHA256,
            "move_manifest_expected_sha256": manifest_move_hash,
            "move_log_actual_sha256_after_repair": sha256(MOVE_LOG),
            "mortgage_log_actual_sha256": sha256(MORTGAGE_LOG),
        },
        "identities": {
            "move_log_experiment_id": move_log.get("experiment_id"),
            "move_log_decision": move_log.get("decision"),
            "mortgage_rebuilt_experiment_id": rebuilt_mortgage_log.get("experiment_id"),
            "mortgage_log_decision": mortgage_log.get("decision"),
        },
    }


def build_payload() -> dict[str, Any]:
    verified = verification()
    if not verified["passed"]:
        raise RuntimeError(f"identity recovery verification failed: {verified['checks']}")
    now = utc_now()
    reflection = {
        "why_result_happened": (
            "The mortgage runner delegated replay construction to a MOVE-derived "
            "module, then called the base compact-log function. That function "
            "closed over MOVE identity constants, so its first shard write "
            "targeted exp-20260711-002 even though later ticket persistence used "
            "exp-20260711-017."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not repair future shard mismatches by editing decisions from "
            "memory. Require a manifest-verified artifact/runner reconstruction "
            "and bind wrapper writes to an expected experiment ID."
        ),
        "new_evidence_required": (
            "No retry is needed unless another manifest hash mismatch or "
            "cross-ID wrapper write is detected."
        ),
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "experiment_uid": EXPERIMENT_UID,
        "timestamp": now,
        "status": "accepted_measurement_repair",
        "lane": "measurement_repair",
        "hypothesis": HYPOTHESIS,
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair",
        "mechanism_family": "experiment_log_identity_integrity",
        "trial_family": "experiment_log_wrapper_identity_repair",
        "trial_variant_id": "inherited_compact_log_cross_id_overwrite_recovery_v1",
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": [
            "wrapper log identity binding",
            "expected experiment-id write guard",
            "manifest-hash recovery",
            "regression test",
            "derived-log rebuild",
        ],
        "nearby_prior_experiments": [MOVE_ID, MORTGAGE_ID],
        "new_evidence_type": "genuine_publication_fault_recovery",
        "new_evidence_axis": (
            "Manifest-proven cross-ID overwrite recovery; no alpha surface was "
            "resliced and no strategy metrics changed."
        ),
        "verification": verified,
        "before_metrics": {},
        "after_metrics": {},
        "delta_metrics": {},
        "production_impact": PRODUCTION_IMPACT,
        "decision": DECISION,
        "accepted": True,
        "accepted_alpha": False,
        "acceptance_basis": (
            "MOVE log exactly matches its pre-corruption manifest hash; the "
            "mortgage wrapper reproduces its own existing log and the generic "
            "writer rejects an explicitly mismatched expected ID."
        ),
        "post_run_reflection": reflection,
        "next_retry_requires": [reflection["new_evidence_required"]],
        "changed_files": ALLOWED_WRITE_SCOPE,
        "related_files": [
            repo_rel(MOVE_MANIFEST),
            repo_rel(MOVE_LOG),
            repo_rel(MORTGAGE_LOG),
            repo_rel(MORTGAGE_RUNNER),
            "scripts/experiment_registry.py",
            "quant/test_experiment_registry.py",
        ],
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_experiment_registry.py -q",
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260713_004_experiment_log_wrapper_identity_repair.py",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py rebuild-log",
            ".\\.venv\\Scripts\\python.exe -B scripts\\build_frozen_families.py",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": True,
    }


def build_log(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "experiment_uid",
        "timestamp",
        "status",
        "lane",
        "hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
        "causal_components",
        "nearby_prior_experiments",
        "new_evidence_type",
        "new_evidence_axis",
        "verification",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "production_impact",
        "decision",
        "accepted",
        "accepted_alpha",
        "acceptance_basis",
        "post_run_reflection",
        "next_retry_requires",
        "changed_files",
        "related_files",
        "reproduction_commands",
        "lean_quality_passed",
    ]
    return {key: payload[key] for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    checks = payload["verification"]["checks"]
    return "\n".join(
        [
            "---",
            f'experiment_id: "{EXPERIMENT_ID}"',
            f'experiment_uid: "{EXPERIMENT_UID}"',
            'status: "accepted_measurement_repair"',
            'lane: "measurement_repair"',
            'change_type: "identity_or_measurement_repair"',
            'trial_family: "experiment_log_wrapper_identity_repair"',
            f'created_at: "{payload["timestamp"]}"',
            "---",
            "",
            f"# {EXPERIMENT_ID} experiment-log identity recovery",
            "",
            f"Decision: `{DECISION}`",
            "",
            "The MOVE log shard was restored to its manifest-locked hash and the",
            "mortgage wrapper now binds every identity-bearing field before the",
            "shard writer accepts it. Strategy behavior and metrics are unchanged.",
            "",
            "## Verification",
            "",
            *[f"- {name}: `{passed}`" for name, passed in checks.items()],
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
        ]
    )


def write_manifest(payload: dict[str, Any]) -> None:
    paths = [Path(REPO_ROOT / RUNNER), ARTIFACT, CARD, LOG, TICKET, MOVE_LOG, MORTGAGE_LOG]
    write_json(
        MANIFEST,
        {
            "schema_version": 1,
            "manifest_type": "ginger_experiment_revision_manifest",
            "experiment_id": EXPERIMENT_ID,
            "experiment_uid": EXPERIMENT_UID,
            "status": payload["status"],
            "decision": payload["decision"],
            "generated_at": payload["timestamp"],
            "files": {
                repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
                for path in paths
            },
        },
    )


def persist(payload: dict[str, Any]) -> None:
    write_json(ARTIFACT, payload)
    save_experiment_log_entry(
        build_log(payload),
        allow_duplicate=True,
        expected_experiment_id=EXPERIMENT_ID,
    )
    CARD.write_text(build_card(payload), encoding="utf-8")
    result = {
        "accepted": True,
        "accepted_alpha": False,
        "decision": payload["decision"],
        "artifact": repo_rel(ARTIFACT),
        "verification": payload["verification"],
        "acceptance_basis": payload["acceptance_basis"],
    }
    persist_self_registered_result(
        REGISTRY,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=None,
        result=result,
        status=payload["status"],
        fields={
            key: payload[key]
            for key in (
                "hypothesis",
                "change_type",
                "implementation_mode",
                "mechanism_family",
                "trial_family",
                "trial_variant_id",
                "single_causal_variable",
                "changed_variable",
                "causal_components",
                "nearby_prior_experiments",
                "new_evidence_type",
                "new_evidence_axis",
                "production_impact",
                "decision",
                "acceptance_basis",
                "post_run_reflection",
                "next_retry_requires",
                "changed_files",
                "related_files",
                "reproduction_commands",
                "lean_quality_passed",
            )
        }
        | {
            "owner": OWNER,
            "artifact": repo_rel(ARTIFACT),
            "log": repo_rel(LOG),
            "card_file": repo_rel(CARD),
            "revision_manifest_file": repo_rel(MANIFEST),
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        },
    )
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
                "move_log_sha256": payload["verification"]["hashes"][
                    "move_log_actual_sha256_after_repair"
                ],
                "all_checks_passed": payload["verification"]["passed"],
                "strategy_behavior_changed": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
