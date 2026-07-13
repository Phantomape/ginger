"""exp-20260710-008: exit lifecycle fingerprint coverage.

Measurement repair. Exit lifecycle shadow rows are a separate observer
population from intraday advisory shadow actions. This runner records the
fingerprint repair and verifies the new data_source key without changing any
strategy behavior.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


EXPERIMENT_ID = "exp-20260710-008"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "exit_lifecycle_fingerprint_coverage"
RUNNER = f"quant/experiments/exp_20260710_008_{SLUG}.py"
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
OUT_JSON = OUT_DIR / f"exp_20260710_008_{SLUG}.json"
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
    "Alpha blocker: exit lifecycle and LLM/advisory outcome rows may become an "
    "exit-scoring or risk-allocation evidence surface, but novelty fingerprints "
    "routed exit_lifecycle_shadow_log and exit advisory lifecycle text into "
    "intraday_advisory or other; repair the data_source key before future "
    "exit-lifecycle alpha or forward-row reopen checks."
)
ALPHA_HYPOTHESIS = (
    "Exit lifecycle and advisory outcome rows may eventually support LLM exit "
    "scoring or risk allocation once the observer has settled forward "
    "replacement-value evidence."
)
CHANGE_TYPE = "identity_or_measurement_repair"
IMPLEMENTATION_MODE = "fingerprint_data_source_guard_repair"
MECHANISM_FAMILY = "exit_lifecycle_advisory_outcome"
TRIAL_FAMILY = "exit_lifecycle_fingerprint_coverage"
TRIAL_VARIANT_ID = "exit_lifecycle_data_source_key_v1"
SINGLE_CAUSAL_VARIABLE = "exit_lifecycle_fingerprint_data_source_v1"
CAUSAL_COMPONENTS = [
    "exit_lifecycle_data_source_keyword",
    "fingerprint_regression_tests",
    "no_strategy_change",
]
ACCEPTANCE_RULE = (
    "Accepted measurement repair if exit lifecycle examples resolve to "
    "exit_lifecycle, existing intraday_advisory examples remain "
    "intraday_advisory, tests pass, and no strategy/live behavior changes."
)

CHECKS = {
    "exit_lifecycle_shadow_log": {
        "text": "exit_lifecycle_shadow_log daily position lifecycle rows",
        "expected_source": "exit_lifecycle",
    },
    "exit_advisory_lifecycle": {
        "text": "exit advisory lifecycle breach_status forward attribution",
        "expected_source": "exit_lifecycle",
    },
    "exit_lifecycle_position_fields": {
        "text": "has_advisory_event trailing_stop_from_hwm position lifecycle",
        "expected_source": "exit_lifecycle",
    },
    "intraday_advisory_shadow_action_control": {
        "text": "intraday advisory shadow action risk-review attribution",
        "expected_source": "intraday_advisory",
    },
    "intraday_primary_advisory_control": {
        "text": "primary advisory shadow action forward outcome",
        "expected_source": "intraday_advisory",
    },
}

PRE_REPAIR_OBSERVATION = {
    "source": "experiment.py new novelty output",
    "text": HYPOTHESIS,
    "pre_repair_data_source": "intraday_advisory",
    "pre_repair_note": (
        "The reservation fingerprint classified the repair hypothesis as "
        "intraday_advisory before the dedicated exit_lifecycle key existed."
    ),
}

CHANGED_FILES = [
    RUNNER,
    "scripts/experiment_fingerprint.py",
    "quant/test_experiment_fingerprint.py",
    f"data/experiments/{EXPERIMENT_ID}/exp_20260710_008_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]
VERIFICATION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile "
    "scripts\\experiment_fingerprint.py quant\\test_experiment_fingerprint.py "
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
    text = json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n"
    tmp.write_text(text, encoding="utf-8")
    try:
        tmp.replace(path)
    except PermissionError:
        path.write_text(text, encoding="utf-8")
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
        results[name] = {
            **spec,
            "actual": actual,
            "source_ok": source_ok,
            "passed": source_ok,
        }
    return results


def build_payload() -> dict[str, Any]:
    checks = run_checks()
    failed = [name for name, result in checks.items() if not result["passed"]]
    accepted = not failed
    decision = (
        "accepted_measurement_repair_exit_lifecycle_fingerprint_coverage"
        if accepted
        else "blocked_exit_lifecycle_fingerprint_coverage"
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
        "nearby_prior_experiments": [],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "measurement_repair_guard_coverage",
        "new_evidence_axis": (
            "New measurement surface key, not a strategy retune: "
            "exit_lifecycle_shadow_log rows are distinct from intraday "
            "advisory shadow actions."
        ),
        "pre_repair_observation": PRE_REPAIR_OBSERVATION,
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
                "exit_lifecycle",
                "intraday_advisory",
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
                "The fingerprint keyword table had intraday advisory shadow "
                "action coverage but no dedicated exit_lifecycle key, so "
                "lifecycle rows and future exit/advisory outcome probes could "
                "share the wrong saturation population."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not use this repair as alpha evidence. Do not run exit "
                "lifecycle policy, LLM exit-scoring, threshold, or response "
                "curve experiments until the observer has settled forward "
                "replacement-value rows or another legal evidence axis."
            ),
            "new_evidence_required": (
                "A future exit-lifecycle alpha needs settled forward rows "
                "under this repaired data_source, a distinct gate shape, or a "
                "new PIT field; fingerprint coverage alone is not signal."
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
            f"# {EXPERIMENT_ID}: Exit Lifecycle Fingerprint Coverage",
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
            "summary": "measurement_repair_exit_lifecycle_fingerprint_coverage",
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
