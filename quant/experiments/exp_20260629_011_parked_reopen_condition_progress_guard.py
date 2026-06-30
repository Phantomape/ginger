"""exp-20260629-011: reservation-time guard for parked reopen conditions.

This measurement repair records and verifies the protocol guard that blocks
alpha-lane reservations against parked forward-context surfaces until their
machine-counted reopen conditions are satisfied. It changes no entry, exit,
ranking, sizing, risk-budget, paper, or live order behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from create_experiment_ticket import evaluate_reopen_condition_guard, load_reopen_conditions  # noqa: E402
from experiment_registry import persist_self_registered_result, save_experiment_log_entry  # noqa: E402


EXPERIMENT_ID = "exp-20260629-011"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "parked_reopen_condition_progress_guard"
RUNNER = f"quant/experiments/exp_20260629_011_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

CHANGED_VARIABLE = "parked_reopen_condition_progress_guard_v1"
TRIAL_FAMILY = "parked_surface_reopen_condition_progress_guard"
TRIAL_VARIANT_ID = "reservation_time_guard_v1"
MECHANISM_FAMILY = "experiment_protocol_measurement_repair"
CHANGE_TYPE = "reservation_gate_contract_repair"
NEW_EVIDENCE_TYPE = "reservation_gate_hard_rule_alignment"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260629_011_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

ALPHA_HYPOTHESIS = (
    "Risk allocation: parked forward-context surfaces such as Form4 sale-overhang "
    "and Form144 planned-sale/float may become useful only after their logged "
    "closed-row and coverage counts advance; until then response retunes are "
    "invalid duplicate alpha attempts."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def baseline_metrics() -> dict[str, Any]:
    raw = read_json(BASELINE_RESULT, {})
    if not isinstance(raw, dict):
        return {"baseline_result_file": repo_rel(BASELINE_RESULT), "loaded": False}
    windows = []
    for row in raw.get("windows") or []:
        if not isinstance(row, dict):
            continue
        windows.append(
            {
                "label": row.get("label"),
                "start": row.get("start"),
                "end": row.get("end"),
                "expected_value_score": row.get("expected_value_score"),
                "sharpe_daily": row.get("sharpe_daily"),
                "total_pnl": row.get("total_pnl"),
                "max_drawdown_pct": row.get("max_drawdown_pct"),
                "trade_count": row.get("trade_count"),
                "signals_generated": row.get("signals_generated"),
                "signals_survived": row.get("signals_survived"),
                "survival_rate": row.get("survival_rate"),
                "win_rate": row.get("win_rate"),
            }
        )
    if not windows:
        return {"baseline_result_file": repo_rel(BASELINE_RESULT), "loaded": True}
    signals_generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    signals_survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "loaded": True,
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 6
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": signals_generated,
        "signals_survived": signals_survived,
        "survival_rate": (
            round(signals_survived / signals_generated, 6) if signals_generated else None
        ),
        "max_drawdown_pct": max(float(row.get("max_drawdown_pct") or 0.0) for row in windows),
        "windows": windows,
    }


def guard_args(**overrides: Any) -> SimpleNamespace:
    base = {
        "lane": "alpha_search",
        "hypothesis": "Form4 sale-overhang risk scalar on accepted core entries",
        "single_causal_variable": "form4_sale_overhang_notional_haircut",
        "changed_variable": "form4_sale_overhang_notional_haircut",
        "trial_family": "form4_sale_overhang_risk_response",
        "trial_variant_id": "v1",
        "mechanism_family": "form4_sale_overhang_forward_context",
        "file_slug": "form4_sale_overhang_risk_response",
        "new_evidence_axis": "",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def guard_audit() -> dict[str, Any]:
    cases = {
        "form4_alpha_response_without_progress": guard_args(),
        "form4_alpha_response_new_source_axis": guard_args(
            new_evidence_axis="new data source: PIT broker locate/borrow sidecar"
        ),
        "form144_alpha_response_without_progress": guard_args(
            hypothesis="Form144 planned-sale float risk scalar on accepted entries",
            single_causal_variable="form144_planned_sale_float_response",
            changed_variable="form144_planned_sale_float_response",
            trial_family="form144_planned_sale_float_risk_response",
            trial_variant_id="v1",
            mechanism_family="form144_planned_sale_float_forward_context",
            file_slug="form144_planned_sale_float_response",
        ),
        "measurement_repair_same_surface": guard_args(lane="measurement_repair"),
    }
    verdicts = {
        name: evaluate_reopen_condition_guard(args, repo_root=REPO_ROOT)
        for name, args in cases.items()
    }
    conditions = load_reopen_conditions(repo_root=REPO_ROOT)
    parked_surfaces = [
        {
            "experiment_id": item.get("experiment_id"),
            "source_log": item.get("source_log"),
            "surface": item.get("surface"),
            "status": item.get("status"),
            "blocking_reason": item.get("blocking_reason"),
            "current_counts": item.get("current_counts"),
            "required_to_reopen": item.get("required_to_reopen"),
        }
        for item in conditions
        if item.get("surface")
    ]
    return {
        "parked_surface_count": len(parked_surfaces),
        "parked_surfaces": parked_surfaces,
        "verdicts": verdicts,
        "passed": bool(
            verdicts["form4_alpha_response_without_progress"].get("blocked")
            and verdicts["form144_alpha_response_without_progress"].get("blocked")
            and verdicts["form4_alpha_response_new_source_axis"].get("override_accepted")
            and not verdicts["measurement_repair_same_surface"].get("applicable")
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    before = baseline_metrics()
    audit = guard_audit()
    repair_passed = bool(before.get("loaded") and audit["passed"])
    after = dict(before)
    delta = {
        "expected_value_score_sum_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "signals_generated_delta": 0,
        "signals_survived_delta": 0,
        "strategy_behavior_changed": False,
    }
    predicted = ticket.get("prediction") or {}
    predicted_success = predicted.get("success_probability")
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "accepted_measurement_repair" if repair_passed else "blocked",
        "decision": (
            "accepted_measurement_repair_parked_reopen_condition_progress_guard"
            if repair_passed
            else "blocked_parked_reopen_condition_progress_guard"
        ),
        "accepted": repair_passed,
        "accepted_alpha": False,
        "accepted_measurement_repair": repair_passed,
        "alpha_ready": False,
        "lane": LANE,
        "owner": OWNER,
        "hypothesis": ticket.get("hypothesis") or ALPHA_HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "reservation_time_reopen_condition_guard",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": [
            "load nested reopen_condition records from experiment logs",
            "surface matcher for parked alpha forward-context surfaces",
            "numeric current_counts versus required_to_reopen checks",
            "alpha-lane block before reservation write",
            "new data source or new gate shape escape hatch",
            "focused unit tests",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": [
            "exp-20260629-002",
            "exp-20260629-005",
            "exp-20260629-010",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "prediction": predicted,
        "calibration": {
            "predicted_success_probability": predicted_success,
            "expected_ev_delta": predicted.get("expected_ev_delta"),
            "expected_pnl_delta": predicted.get("expected_pnl_delta"),
            "actual_success": 1 if repair_passed else 0,
            "actual_ev_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "predicted_failure_modes": predicted.get("main_failure_modes") or [],
            "realized_failure_mode": None if repair_passed else "guard_audit_failed",
            "surprise_level": "low" if repair_passed else "medium",
        },
        "before_metrics": before,
        "after_metrics": after,
        "delta_metrics": delta,
        "guard_audit": audit,
        "gate1": {
            "passed": bool(before.get("loaded")),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_expected_value_score_sum": before.get("expected_value_score_sum"),
            "baseline_total_pnl": before.get("total_pnl"),
            "strategy_metrics_unchanged": True,
        },
        "gate2": {
            "passed": audit["passed"],
            "runtime_fields_checked": [
                "lane",
                "hypothesis",
                "single_causal_variable",
                "changed_variable",
                "trial_family",
                "new_evidence_axis",
                "reopen_condition.surface",
                "reopen_condition.current_counts",
                "reopen_condition.required_to_reopen",
            ],
            "field_status": {
                "form4_blocked_without_progress": audit["verdicts"][
                    "form4_alpha_response_without_progress"
                ].get("blocked"),
                "form144_blocked_without_progress": audit["verdicts"][
                    "form144_alpha_response_without_progress"
                ].get("blocked"),
                "new_source_axis_allowed": audit["verdicts"][
                    "form4_alpha_response_new_source_axis"
                ].get("override_accepted"),
                "measurement_repair_unblocked": not audit["verdicts"][
                    "measurement_repair_same_surface"
                ].get("applicable"),
            },
        },
        "gate3": {
            "passed": True,
            "not_applicable_reason": (
                "No signal, filter, ranking, sizing, exit, risk budget, or order "
                "rule changed."
            ),
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "survival_rate_delta": 0.0,
        },
        "gate4": {
            "passed": repair_passed,
            "accepted_alpha": False,
            "measurement_repair_only": True,
            "decision": (
                "accepted_measurement_repair_parked_reopen_condition_progress_guard"
                if repair_passed
                else "blocked_parked_reopen_condition_progress_guard"
            ),
            "before_after_strategy_delta": delta,
            "failed_reasons": [] if repair_passed else ["reservation_guard_contract_failed"],
        },
        "production_impact": {
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "production_watchlist_changed": False,
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "risk_budget_changed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Reservation protocol only. No backtest, paper, daily, or live "
                "strategy path consumes this guard."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": (
                "exp-20260629-002 parked Form144 planned-sale/float, exp-20260629-005 "
                "parked Form4 sale-overhang alpha responses until closed forward "
                "rows materialize, and exp-20260629-010 repaired saturated-source "
                "override semantics. No current surface had enough new closed rows."
            ),
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Accept only as measurement repair if the reservation tool blocks "
                "Form4/Form144 alpha-lane retries without progress, allows a new "
                "data-source or new-gate-shape axis, and leaves strategy metrics unchanged."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The repo already writes structured reopen_condition records with "
                "current_counts and required_to_reopen thresholds. Wiring those "
                "records into reservation-time checks prevents duplicate alpha "
                "tickets against parked surfaces before any trading code is touched."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not reserve Form4 sale-overhang or Form144 planned-sale/float "
                "readiness audits, notional haircuts, ranking tilts, risk scalars, "
                "vetoes, or response-curve variants while the logged numeric reopen "
                "checks remain unmet."
            ),
            "new_evidence_required": (
                "A valid retry needs the logged reopen counts to satisfy their "
                "numeric checks, or a genuinely new data source or new gate shape "
                "declared in --new-evidence-axis."
            ),
        },
        "next_retry_requires": (
            "Use the guard output before reserving parked-surface alpha tickets; "
            "current Form4/Form144 counts are still below their reopen thresholds."
        ),
        "anti_js": {
            "used_javascript": False,
            "strategy_behavior_changed": False,
            "threshold_scan": False,
            "response_curve_retune": False,
            "new_download_attempts": False,
        },
        "related_files": [
            RUNNER,
            "scripts/create_experiment_ticket.py",
            "quant/test_create_experiment_ticket.py",
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(BASELINE_RESULT),
        ],
        "changed_files": [
            "scripts/create_experiment_ticket.py",
            "quant/test_create_experiment_ticket.py",
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(REGISTRY_JSON),
            "docs/experiment_log.jsonl",
        ],
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m py_compile scripts\\create_experiment_ticket.py quant\\test_create_experiment_ticket.py "
            + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_create_experiment_ticket.py -q",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
    }


def compact_log(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "lane",
        "owner",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "accepted",
        "accepted_alpha",
        "accepted_measurement_repair",
        "alpha_ready",
        "decision",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "guard_audit",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "pre_run_questions",
        "prediction",
        "calibration",
        "post_run_reflection",
        "next_retry_requires",
        "related_files",
        "changed_files",
        "reproduction_commands",
        "anti_js",
    ]
    row = {key: payload[key] for key in keys if key in payload}
    row["artifact"] = repo_rel(OUT_JSON)
    row["log"] = repo_rel(LOG_JSON)
    row["lean_quality_passed"] = bool(payload["gate4"]["passed"])
    return row


def build_card(payload: dict[str, Any]) -> str:
    audit = payload["guard_audit"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Parked Reopen Condition Progress Guard",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            f"- Parked reopen surfaces loaded: `{audit['parked_surface_count']}`",
            f"- Form4 blocked without progress: `{payload['gate2']['field_status']['form4_blocked_without_progress']}`",
            f"- Form144 blocked without progress: `{payload['gate2']['field_status']['form144_blocked_without_progress']}`",
            f"- New-source axis allowed: `{payload['gate2']['field_status']['new_source_axis_allowed']}`",
            "",
            "## Interpretation",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Reproduce",
            "",
            "```powershell",
            RUNNER_COMMAND,
            "```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any], log_row: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / "scripts" / "create_experiment_ticket.py",
        REPO_ROOT / "quant" / "test_create_experiment_ticket.py",
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
        BASELINE_RESULT,
    ]
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256_file(path)}
            for path in files
        },
        "log_row_sha256": hashlib.sha256(
            json.dumps(safe(log_row), sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    log_row = compact_log(payload)
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(log_row, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    result = {
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "accepted_measurement_repair": payload["accepted_measurement_repair"],
        "alpha_ready": False,
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "delta_metrics": payload["delta_metrics"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    fields = {
        key: payload[key]
        for key in [
            "owner",
            "hypothesis",
            "alpha_hypothesis",
            "change_type",
            "implementation_mode",
            "mechanism_family",
            "trial_family",
            "trial_variant_id",
            "single_causal_variable",
            "changed_variable",
            "causal_components",
            "nearby_prior_experiments",
            "multiple_testing_risk_bucket",
            "new_evidence_type",
            "pre_run_questions",
            "guard_audit",
            "gate1",
            "gate2",
            "gate3",
            "gate4",
            "production_impact",
            "post_run_reflection",
            "next_retry_requires",
            "related_files",
            "changed_files",
            "reproduction_commands",
            "anti_js",
            "calibration",
        ]
        if key in payload
    }
    fields.update(
        {
            "accepted_alpha": False,
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
        }
    )
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload.get("prediction") or {},
        result=result,
        status=payload["status"],
        fields=fields,
        allow_missing_prediction=True,
    )
    write_json(MANIFEST_JSON, build_manifest(payload, log_row))


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps(safe(compact_log(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
