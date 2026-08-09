"""exp-20260710-004: SEC 13D Item-4 fingerprint repair.

Measurement repair. A valid next alpha hypothesis on the newly materialized
SEC 13D Item-4 campaign-provenance surface was blocked before reservation
because the novelty/saturation fingerprint routed 13D/13G ownership text into
generic SEC text or 13F ownership buckets. This runner records the repair and
verifies the new source key without changing any strategy behavior.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


EXPERIMENT_ID = "exp-20260710-004"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "sec13d_item4_campaign_fingerprint_repair"
RUNNER = f"quant/experiments/exp_20260710_004_{SLUG}.py"
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
OUT_JSON = OUT_DIR / f"exp_20260710_004_{SLUG}.json"
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
    "Alpha blocker: parsed SEC 13D/13G ownership and Item-4 campaign-provenance "
    "alpha proposals are overmatched into saturated generic ownership/text "
    "cells, so novelty/saturation gates block valid campaign-outcome "
    "experiments instead of counting the true parsed 13D ownership surface."
)
ALPHA_HYPOTHESIS = (
    "candidate_pool/full_stack: newly materialized Schedule 13D Item-4 concrete "
    "campaign outcomes, limited to actual board appointments, board-size "
    "changes, board departures, or nomination withdrawals, may isolate fresher "
    "activist catalysts than exp-20260629-009's broad governance_terms_present "
    "source."
)
CHANGE_TYPE = "identity_or_measurement_repair"
IMPLEMENTATION_MODE = "fingerprint_data_source_guard_repair"
MECHANISM_FAMILY = "alpha_novelty_guard_data_source_coverage"
TRIAL_FAMILY = "sec13d_item4_campaign_fingerprint_coverage"
TRIAL_VARIANT_ID = "sec13d_ownership_source_key_v1"
SINGLE_CAUSAL_VARIABLE = "sec13d_item4_campaign_fingerprint_data_source_repair"
CAUSAL_COMPONENTS = [
    "sec13d_ownership_data_source_keyword",
    "fingerprint_regression_tests",
    "no_strategy_change",
]
NEARBY_PRIORS = [
    "exp-20260629-009",
    "exp-20260710-003",
]
ACCEPTANCE_RULE = (
    "Accepted measurement repair if SEC 13D/13G and Item-4 campaign examples "
    "resolve to sec13d_ownership, 13F remains sec13f_ownership, generic 8-K "
    "text remains sec_text_event, and no strategy/live behavior changes."
)

CHECKS = {
    "sec13d_campaign_candidate_pool": {
        "text": "parsed SEC 13D Item-4 campaign-provenance board appointment candidate pool",
        "expected_source": "sec13d_ownership",
        "expected_shape": "candidate_pool_top1_10d",
    },
    "sec13d_holder_stake_readiness": {
        "text": "SEC 13D/13G holder stake action readiness",
        "expected_source": "sec13d_ownership",
        "expected_shape": "other",
    },
    "sec13d_forward_rows": {
        "text": "Schedule 13D item4 campaign forward replacement rows",
        "expected_source": "sec13d_ownership",
        "expected_shape": "forward_attribution",
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
}

CHANGED_FILES = [
    RUNNER,
    "scripts/experiment_fingerprint.py",
    "quant/test_experiment_fingerprint.py",
    f"data/experiments/{EXPERIMENT_ID}/exp_20260710_004_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]
VERIFICATION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile scripts\\experiment_fingerprint.py",
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
        "accepted_measurement_repair_sec13d_item4_fingerprint_coverage"
        if accepted
        else "blocked_sec13d_item4_fingerprint_coverage"
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
        "blocked_alpha_attempts": [
            {
                "hypothesis": ALPHA_HYPOTHESIS,
                "observed_blocker": (
                    "Pre-repair alpha reservation was blocked as a near-neighbor "
                    "of sec_13d_item4_governance_terms_candidate_pool and then "
                    "by saturated sec_text_event candidate_pool_top1_10d."
                ),
            },
            {
                "hypothesis": HYPOTHESIS,
                "observed_blocker": (
                    "The measurement-repair ticket itself fingerprinted as "
                    "sec13f_ownership because the prior generic holder keyword "
                    "captured 13D/13G holder-stake language."
                ),
            },
        ],
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
                "sec13d_ownership",
                "sec13f_ownership",
                "sec_text_event",
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
                "The keyword table had generic SEC text and 13F holder entries "
                "but no dedicated parsed 13D/13G ownership key. As a result, "
                "13D Item-4 campaign proposals inherited the wrong saturation "
                "history and were blocked before a valid alpha read could run."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not use this repair as alpha evidence. Future 13D/13G alpha "
                "still needs a legal new evidence axis and Gate 1-4; do not "
                "sweep Item-4 phrases, holder types, classPercent, notional, "
                "hold days, or response shape on frozen rows."
            ),
            "new_evidence_required": (
                "After this repair, a valid 13D alpha ticket should fingerprint "
                "as sec13d_ownership and must still rely on a fixed campaign/"
                "board-seat policy, materially more settled rows, or another "
                "allowed evidence axis."
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
            f"# {EXPERIMENT_ID}: SEC 13D Item-4 Fingerprint Repair",
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
            "summary": "measurement_repair_sec13d_item4_fingerprint_coverage",
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
