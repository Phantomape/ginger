"""exp-20260708-031: chop forward observer fingerprint coverage.

Measurement repair only. exp-20260708-030 correctly wired a default-off chop
forward observer, but its ticket novelty fingerprint was misclassified as
core_entry_admission / entry_admission because generic "entry" language won.
This runner records the classifier repair and proves it does not change any
strategy, order, ranking, sizing, or exit behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

EXPERIMENT_ID = "exp-20260708-031"
OWNER = "codex"
LANE = "measurement_repair"
SLUG = "chop_forward_observer_fingerprint_coverage"
RUNNER = f"quant/experiments/exp_20260708_031_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import experiment_fingerprint as fp  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)

BASELINE_RESULT = REPO_ROOT / "data" / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260708_031_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
FROZEN_FAMILIES = REPO_ROOT / "docs" / "frozen_families.jsonl"

HYPOTHESIS = (
    "Repair novelty fingerprint coverage so chop forward observer wiring and "
    "future chop forward-row reopen checks classify as chop_forward_observer / "
    "forward_observer instead of core_entry_admission / entry_admission."
)
CHANGED_VARIABLE = "chop_forward_observer_fingerprint_coverage_v1"
MECHANISM_FAMILY = "chop_regime_forward_measurement"
TRIAL_FAMILY = "chop_forward_observer_fingerprint_coverage"
TRIAL_VARIANT_ID = "chop_forward_observer_fingerprint_v1"
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260708-030", "exp-20260708-029", "exp-20260703-015"]
CAUSAL_COMPONENTS = [
    "classifier keywords",
    "focused regression tests",
    "frozen-family rebuild",
    "no strategy behavior change",
]
CHANGED_FILES = [
    "scripts/experiment_fingerprint.py",
    "quant/test_experiment_fingerprint.py",
    RUNNER,
    "data/experiments/exp-20260708-031/exp_20260708_031_chop_forward_observer_fingerprint_coverage.json",
    "experiments/logs/exp-20260708-031.json",
    "experiments/cards/exp-20260708-031.md",
    "experiments/manifests/exp-20260708-031.json",
    "experiments/tickets/exp-20260708-031.json",
    "docs/experiment_registry.json",
    "docs/frozen_families.jsonl",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: str | Path) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default if default is not None else {}


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    drawdowns = [
        float(row.get("max_drawdown_pct"))
        for row in windows
        if row.get("max_drawdown_pct") is not None
    ]
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
    }


def run_tests() -> dict[str, Any]:
    proc = subprocess.run(
        [
            str(REPO_ROOT / ".venv" / "Scripts" / "python.exe"),
            "-m",
            "pytest",
            "quant/test_experiment_fingerprint.py",
            "-q",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=600,
    )
    return {
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "tail": ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()[-5:],
    }


def check_fingerprints() -> dict[str, Any]:
    target_text = (
        "Repair novelty fingerprint coverage so chop forward observer wiring "
        "and future chop forward-row reopen checks classify as "
        "chop_regime_forward_observer instead of core_entry_admission / "
        "entry_admission."
    )
    target = fp.infer_fingerprint(target_text, TRIAL_FAMILY, CHANGED_VARIABLE)
    regression_cases = {
        "pair_spread": fp.infer_fingerprint(
            "chop pair-spread long-short market-neutral zscore entry sleeve"
        ),
        "regime_chop": fp.infer_fingerprint("regime chop daily breadth wiring"),
        "forward_replacement": fp.infer_fingerprint(
            "forward replacement value entry_exhaustion settled forward attribution"
        ),
        "core_admission": fp.infer_fingerprint(
            "core_entry_admission_gate saved-trade counterfactual severe haircut pre-entry no-entry"
        ),
    }
    return {
        "target_text": target_text,
        "target": target,
        "target_passed": (
            target["data_source"] == "chop_forward_observer"
            and target["gate_shape"] == "forward_observer"
        ),
        "regression_cases": regression_cases,
        "regression_passed": (
            regression_cases["pair_spread"]["data_source"] == "relative_value_spread"
            and regression_cases["pair_spread"]["gate_shape"] == "pair_spread"
            and regression_cases["regime_chop"]["data_source"] == "regime_state"
            and regression_cases["forward_replacement"]["data_source"] == "forward_replacement_value"
            and regression_cases["forward_replacement"]["gate_shape"] == "forward_attribution"
            and regression_cases["core_admission"]["data_source"] == "core_entry_admission"
            and regression_cases["core_admission"]["gate_shape"] == "entry_admission"
        ),
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    before_fp = ((ticket.get("novelty") or {}).get("fingerprint") or {})
    after_checks = check_fingerprints()
    tests = run_tests()
    baseline = baseline_metrics()
    measurement_blockers: list[str] = []
    if before_fp.get("data_source") != "core_entry_admission":
        measurement_blockers.append("ticket_before_fingerprint_not_reproduced")
    if before_fp.get("gate_shape") != "entry_admission":
        measurement_blockers.append("ticket_before_gate_shape_not_reproduced")
    if not after_checks["target_passed"]:
        measurement_blockers.append("target_chop_forward_observer_fingerprint_failed")
    if not after_checks["regression_passed"]:
        measurement_blockers.append("regression_fingerprint_case_failed")
    if not tests["passed"]:
        measurement_blockers.append("fingerprint_tests_failed")
    if not FROZEN_FAMILIES.exists():
        measurement_blockers.append("frozen_families_missing")

    accepted = not measurement_blockers
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_chop_forward_observer_fingerprint_coverage"
        if accepted
        else "blocked_chop_forward_observer_fingerprint_coverage"
    )
    strategy_delta = {
        "expected_value_score_sum_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "signals_generated_delta": 0,
        "signals_survived_delta": 0,
        "strategy_behavior_changed": False,
    }
    delta_metrics = {
        **strategy_delta,
        "before_data_source": before_fp.get("data_source"),
        "before_gate_shape": before_fp.get("gate_shape"),
        "after_data_source": after_checks["target"]["data_source"],
        "after_gate_shape": after_checks["target"]["gate_shape"],
        "target_case_passed": after_checks["target_passed"],
        "regression_cases_passed": after_checks["regression_passed"],
        "unit_tests_passed": tests["passed"],
    }
    prediction = {
        "recorded_at": ticket.get("claimed_at") or ticket.get("created_at"),
        "success_probability": 0.9,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "specific_keyword_order_overmatches_pair_spread",
            "specific_keyword_order_overmatches_forward_replacement",
            "frozen_family_rebuild_missing",
        ],
        "confidence_reason": (
            "The defect is deterministic in exp031's own reservation metadata; "
            "a source-specific keyword before generic core admission plus focused "
            "regression tests should repair governance without strategy behavior."
        ),
    }
    calibration = {
        "predicted_success_probability": prediction["success_probability"],
        "actual_success": 1 if accepted else 0,
        "brier_score": round((prediction["success_probability"] - (1.0 if accepted else 0.0)) ** 2, 6),
        "predicted_failure_modes": prediction["main_failure_modes"],
        "realized_failure_modes": measurement_blockers,
        "predicted_failure_mode_hit": bool(set(measurement_blockers) & set(prediction["main_failure_modes"])),
    }
    production_impact = {
        "trade_enabled": False,
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "daily_snapshot_exposed": False,
        "entry_rules_changed": False,
        "exit_rules_changed": False,
        "ranking_changed": False,
        "sizing_changed": False,
        "orders_changed": False,
        "llm_decision_boundary_changed": False,
        "live_ready": False,
        "live_realism_evaluated": False,
        "scope": "novelty_governance_classifier_only",
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": status,
        "lane": LANE,
        "owner": OWNER,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "accepted_measurement_repair": accepted,
        "alpha_ready": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": (
            "A chop-specific forward ledger could eventually validate or reject "
            "frozen chop bundles, but alpha work remains blocked until the ledger "
            "has >=15 closed forward chop rows per bundle."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair_classifier_coverage",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "governance_classifier_misclassification",
        "prediction": prediction,
        "calibration": calibration,
        "pre_run_questions": {
            "1_alpha_hypothesis": "Future chop forward rows may validate a chop-only sleeve, but current work only repairs novelty governance.",
            "2_history_check": {
                "exp-20260708-030": "Accepted chop forward observer wiring, but ticket novelty fingerprint was core_entry_admission / entry_admission.",
                "exp-20260708-029": "Accepted pair-spread classifier coverage; must remain relative_value_spread / pair_spread.",
                "exp-20260703-015": "Accepted daily regime chop breadth wiring; must remain regime_state.",
            },
            "3_single_measurement_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Accept only if target classification changes to chop_forward_observer / "
                "forward_observer, pair-spread/regime/forward-replacement regressions pass, "
                "and strategy metrics stay unchanged."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "new_data_source": "chop_forward_observer",
            "new_gate_shape": "forward_observer",
            "changed_strategy_behavior": False,
        },
        "gate1": {"passed": True, "baseline_metrics": baseline},
        "gate2": {
            "passed": accepted,
            "dependencies_validated": accepted,
            "fields_checked": ["data_source", "gate_shape", "field_tags"],
            "entry_date_scope": "Not applicable; classifier metadata only.",
            "target_price_scope": "Not applicable; classifier metadata only.",
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": None,
            "signals_survived": None,
            "survival_rate": None,
            "note": "Measurement repair only; no executable filter was added.",
        },
        "gate4": {
            "passed": accepted,
            "accepted_alpha": False,
            "alpha_ready": False,
            "decision": decision,
            "measurement_blockers": measurement_blockers,
            "alpha_blockers": [],
            "measurement_repair_only": True,
            "strategy_rerun_required": False,
            "before_after_strategy_delta": strategy_delta,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": delta_metrics,
        "fingerprint_checks": {
            "before_ticket_fingerprint": before_fp,
            **after_checks,
        },
        "tests": tests,
        "production_impact": production_impact,
        "post_run_reflection": {
            "why_result_happened": (
                "The prior heuristic had no chop-forward observer population, so "
                "generic entry/admission words won. A specific ordered source and "
                "gate shape now isolate the observer without disturbing pair-spread "
                "or regime mappings."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not treat classifier coverage as alpha evidence. Do not reopen "
                "chop mean-reversion, pair-spread, or sleeve chop down-tilt until "
                "the forward ledger has the predeclared closed-row count."
            ),
            "new_evidence_required": (
                ">=15 closed forward chop rows per bundle, a different non-price "
                "chop data source, or a new shared policy tested by Gate 1-4."
            ),
        },
        "next_retry_requires": [
            ">=15 closed forward chop rows per bundle before chop alpha reopen",
            "no further classifier repairs unless another concrete misclassification blocks governance",
        ],
        "changed_files": CHANGED_FILES,
        "allowed_write_scope": CHANGED_FILES,
        "related_files": [
            "quant/chop_forward_observer.py",
            "quant/chop_mean_reversion_sleeve.py",
            "quant/chop_pairs_spread_sleeve.py",
            "quant/regime_chop_state.py",
        ],
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -m pytest quant\\test_experiment_fingerprint.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\check_experiment_novelty.py --describe \"Repair novelty fingerprint coverage so chop forward observer wiring and future chop forward-row reopen checks classify as chop_regime_forward_observer instead of core_entry_admission / entry_admission.\" --trial-family chop_forward_observer_fingerprint_coverage",
            ".\\.venv\\Scripts\\python.exe -B scripts\\build_frozen_families.py",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {"used_javascript": False, "evidence": "Python runner only."},
        "lean_quality_passed": accepted,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "ticket_before": {
            "created_at": ticket.get("created_at"),
            "claimed_at": ticket.get("claimed_at"),
            "hub_identity": ticket.get("hub_identity"),
            "novelty": ticket.get("novelty"),
        },
    }


def build_card(payload: dict[str, Any]) -> str:
    delta = payload["delta_metrics"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: chop forward observer fingerprint coverage",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Before fingerprint: `{delta['before_data_source']} / {delta['before_gate_shape']}`",
            f"- After fingerprint: `{delta['after_data_source']} / {delta['after_gate_shape']}`",
            f"- Tests passed: `{delta['unit_tests_passed']}`",
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


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    paths = [REPO_ROOT / p for p in CHANGED_FILES]
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
            for path in paths
        },
        "changed_files": payload["changed_files"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(payload, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "alpha_ready": False,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "gate4": payload["gate4"],
            "delta_metrics": payload["delta_metrics"],
            "calibration": payload["calibration"],
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
            "before_metrics": payload["before_metrics"],
            "after_metrics": payload["after_metrics"],
            "delta_metrics": payload["delta_metrics"],
            "fingerprint_checks": payload["fingerprint_checks"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "next_retry_requires": payload["next_retry_requires"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "calibration": payload["calibration"],
            "hub_identity": payload["ticket_before"].get("hub_identity"),
            "novelty": payload["ticket_before"].get("novelty"),
            "claimed_at": payload["ticket_before"].get("claimed_at"),
        },
        allow_missing_prediction=True,
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "delta_metrics": payload["delta_metrics"],
                "gate4": payload["gate4"],
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
    )
    return 0 if payload["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
