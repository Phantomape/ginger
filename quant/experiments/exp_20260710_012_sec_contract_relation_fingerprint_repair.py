"""exp-20260710-012: SEC contract-relation fingerprint repair.

Measurement repair. SEC Item 1.01 contract-relation provenance is a distinct
relation evidence surface, but the novelty/fingerprint classifier routed those
proposals into generic SEC text. This runner records the source-key repair and
verifies the controls without changing strategy behavior.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


EXPERIMENT_ID = "exp-20260710-012"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "sec_contract_relation_fingerprint_repair"
RUNNER = f"quant/experiments/exp_20260710_012_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (REPO_ROOT / "scripts", REPO_ROOT / "quant", REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import experiment_fingerprint as fp  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


DATA_DIR = REPO_ROOT / "data"
OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260710_012_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
BASELINE_RESULT = (
    DATA_DIR
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

HYPOTHESIS = (
    "Alpha blocker: SEC Item 1.01 contract-relation provenance proposals are "
    "overmatched into generic SEC text, so novelty and saturation guards count "
    "a real relation evidence surface against the wrong population before "
    "future CIK-linked customer-supplier graph work can be evaluated."
)
ALPHA_HYPOTHESIS = (
    "candidate_pool/relation graph: Item 1.01 contract relationships may become "
    "useful only after counterparty identity is CIK-linked and shared by replay "
    "and daily code; this run repairs guard accounting only and makes no alpha "
    "claim."
)
CHANGE_TYPE = "identity_or_measurement_repair"
IMPLEMENTATION_MODE = "fingerprint_data_source_guard_repair"
MECHANISM_FAMILY = "alpha_novelty_guard_data_source_coverage"
TRIAL_FAMILY = "sec_contract_relation_fingerprint_coverage"
TRIAL_VARIANT_ID = "sec_contract_relation_source_key_v1"
SINGLE_CAUSAL_VARIABLE = "sec_contract_relation_fingerprint_data_source_repair_v1"
CAUSAL_COMPONENTS = [
    "sec_contract_relation_data_source_keyword",
    "fingerprint_regression_tests",
    "no_strategy_change",
]
NEARBY_PRIORS = [
    "exp-20260703-017",
    "exp-20260704-004",
    "exp-20260710-004",
]
NEW_EVIDENCE_AXIS = (
    "Fingerprint classifier repair for a distinct SEC Item 1.01 contract-"
    "relation evidence surface; this changes novelty accounting only, not "
    "relation regexes, thresholds, candidate ranking, holds, notional, or alpha "
    "response shape."
)
ACCEPTANCE_RULE = (
    "Accepted measurement repair if SEC contract-relation examples resolve to "
    "sec_contract_relation, SEC 13D/13G remains sec13d_ownership, SEC 13F "
    "remains sec13f_ownership, generic 8-K text remains sec_text_event, OHLCV "
    "relation remains ohlcv_relation, and no strategy/live behavior changes."
)

CHECKS = {
    "sec_contract_relation_surface": {
        "text": "SEC Item 1.01 contract-relation provenance candidate pool",
        "expected_source": "sec_contract_relation",
        "expected_shape": "candidate_pool_top1_10d",
    },
    "sec_contract_relation_daily_source": {
        "text": "sec_contract_relation_provenance daily source key",
        "expected_source": "sec_contract_relation",
        "expected_shape": "other",
    },
    "sec_contract_relation_public_counterparty": {
        "text": "SEC item101 contract relation public-counterparty target",
        "expected_source": "sec_contract_relation",
        "expected_shape": "other",
    },
    "sec_contract_relation_cik_graph": {
        "text": "CIK-linked customer-supplier graph for Item 1.01 rows",
        "expected_source": "sec_contract_relation",
        "expected_shape": "other",
    },
    "sec13d_control": {
        "text": "parsed SEC 13D Item-4 campaign-provenance board appointment candidate pool",
        "expected_source": "sec13d_ownership",
        "expected_shape": "candidate_pool_top1_10d",
    },
    "sec13f_control": {
        "text": "SEC 13F institutional sponsorship holder signal",
        "expected_source": "sec13f_ownership",
        "expected_shape": "other",
    },
    "sec_text_control": {
        "text": "SEC 8-K item 3.01 listing noncompliance entry risk",
        "expected_source": "sec_text_event",
        "expected_shape": "other",
    },
    "ohlcv_relation_control": {
        "text": "lead_lag peer rolling_corr relation candidate pool",
        "expected_source": "ohlcv_relation",
        "expected_shape": "candidate_pool_top1_10d",
    },
}

CHANGED_FILES = [
    RUNNER,
    "scripts/experiment_fingerprint.py",
    "quant/test_experiment_fingerprint.py",
    f"data/experiments/{EXPERIMENT_ID}/exp_20260710_012_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]
VERIFICATION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile scripts\\experiment_fingerprint.py "
    + RUNNER.replace("/", "\\"),
    ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_experiment_fingerprint.py -q",
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(v) for v in value]
    if isinstance(value, Path):
        return repo_rel(value)
    return value


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    try:
        tmp.replace(path)
    except PermissionError:
        path.write_text(
            json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        try:
            tmp.unlink()
        except OSError:
            pass


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_checks() -> dict[str, Any]:
    results: dict[str, Any] = {}
    for name, spec in CHECKS.items():
        actual = fp.infer_fingerprint(spec["text"])
        source_ok = actual["data_source"] == spec["expected_source"]
        shape_ok = actual["gate_shape"] == spec["expected_shape"]
        results[name] = {
            **spec,
            "actual": actual,
            "source_ok": source_ok,
            "shape_ok": shape_ok,
            "passed": source_ok and shape_ok,
        }
    return results


def build_payload() -> dict[str, Any]:
    checks = run_checks()
    failed = [name for name, result in checks.items() if not result["passed"]]
    accepted = not failed
    decision = (
        "accepted_measurement_repair_sec_contract_relation_fingerprint_coverage"
        if accepted
        else "blocked_sec_contract_relation_fingerprint_coverage"
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": LANE,
        "status": "accepted_measurement_repair" if accepted else "blocked",
        "accepted": accepted,
        "accepted_alpha": False,
        "accepted_measurement_repair": accepted,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
        "changed_variable": SINGLE_CAUSAL_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "measurement_repair_guard_coverage",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "fingerprint_checks": checks,
        "headline_metrics": {
            "checks_total": len(checks),
            "checks_passed": sum(1 for result in checks.values() if result["passed"]),
            "failed_checks": failed,
            "strategy_behavior_delta": 0,
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists(),
            "baseline_artifact": repo_rel(BASELINE_RESULT),
            "note": "Measurement repair only; no before/after strategy replay.",
        },
        "gate2": {
            "passed": accepted,
            "runtime_fields": [
                "experiment_fingerprint._DATA_SOURCE_KEYWORDS",
                "experiment_fingerprint.infer_fingerprint",
                "sec_contract_relation",
                "sec13d_ownership",
                "sec13f_ownership",
                "sec_text_event",
                "ohlcv_relation",
            ],
            "entry_date_target_price_applicability": (
                "Not applicable: this runner changes novelty accounting only "
                "and emits no trading signals."
            ),
        },
        "gate3": {
            "passed": True,
            "new_core_filter_added": False,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "note": "No buy/sell/filter/ranking behavior changed.",
        },
        "gate4": {
            "passed": accepted,
            "decision": decision,
            "accepted_alpha": False,
            "measurement_repair_only": True,
            "strategy_behavior_changed": False,
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "signals_generated_delta": 0,
                "signals_survived_delta": 0,
            },
            "failed_reasons": failed,
            "acceptance_rule": ACCEPTANCE_RULE,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "trade_enabled_changed": False,
            "live_orders_changed": False,
            "ranking_sizing_exits_changed": False,
            "novelty_guard_accounting_changed": True,
            "daily_snapshot_exposed": False,
            "live_ready": False,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The keyword table had specific keys for 13D/13G ownership and "
                "generic SEC text, but no dedicated SEC contract-relation key. "
                "As a result, Item 1.01 relation proposals inherited the wrong "
                "SEC text population history."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not use this repair as alpha evidence. Future SEC contract-"
                "relation work still needs a legal evidence axis such as "
                "CIK-linked customer/supplier graph rows, contract value/"
                "duration/revenue exposure, a non-SEC relation source, or "
                "materially more closed replacement rows. Do not sweep relation "
                "regexes, aliases, priorities, top-N, hold days, notional, or "
                "response shape on the same rows."
            ),
            "new_evidence_required": (
                "A valid next alpha ticket should fingerprint as "
                "sec_contract_relation and must still satisfy the prior "
                "contract-relation reopen constraints."
            ),
        },
        "rejection_reason": None if accepted else ";".join(failed),
        "related_files": CHANGED_FILES,
        "changed_files": CHANGED_FILES,
        "reproduction_commands": VERIFICATION_COMMANDS,
        "lean_quality_passed": accepted,
    }


def build_card(payload: Mapping[str, Any]) -> str:
    metrics = payload["headline_metrics"]
    failed = ", ".join(metrics["failed_checks"]) or "none"
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: SEC Contract-Relation Fingerprint Repair",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Checks passed: `{metrics['checks_passed']}/{metrics['checks_total']}`",
            f"- Failed checks: `{failed}`",
            "- Accepted alpha: `false`",
            "- Strategy behavior changed: `false`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            "```",
            "",
        ]
    )


def build_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    files = [REPO_ROOT / rel for rel in CHANGED_FILES]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    atomic_write_json(OUT_JSON, payload)
    save_experiment_log_entry(payload, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=None,
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "headline_metrics": payload["headline_metrics"],
            "summary": "measurement_repair_sec_contract_relation_fingerprint_coverage",
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
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
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "ticket_file": repo_rel(TICKET_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "rejection_reason": payload["rejection_reason"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )
    atomic_write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "artifact": repo_rel(OUT_JSON),
                "headline_metrics": payload["headline_metrics"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if payload["accepted_measurement_repair"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
