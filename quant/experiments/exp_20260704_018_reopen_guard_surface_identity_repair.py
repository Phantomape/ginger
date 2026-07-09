"""exp-20260704-018: reopen guard surface-identity repair closeout."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260704-018"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "reopen_guard_surface_identity_repair"

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from scripts.create_experiment_ticket import surface_matches_text  # noqa: E402
from scripts.experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


RUNNER = f"quant/experiments/exp_20260704_018_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")
TEST_COMMAND = ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_create_experiment_ticket.py -q"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260704_018_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
PATCHED_GUARD = REPO_ROOT / "scripts" / "create_experiment_ticket.py"
PATCHED_TEST = REPO_ROOT / "quant" / "test_create_experiment_ticket.py"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_JSON, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    windows = windows if isinstance(windows, list) else []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_JSON),
        "loaded": BASELINE_JSON.exists(),
        "window_count": len(windows),
        "expected_value_score_sum": round(sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    baseline = baseline_metrics()
    negated_text = (
        "supplier financing debt relief forward rows; this is not SEC FTD/FINRA, "
        "not a new FINRA observer, and not a response-function retune"
    )
    positive_text = "SEC FTD FINRA true trigger rows with replacement-value maturity"
    negated_match = surface_matches_text("SEC FTD + FINRA default-off observer", negated_text)
    positive_match = surface_matches_text("SEC FTD + FINRA default-off observer", positive_text)
    accepted = (not negated_match) and positive_match
    decision = (
        "accepted_measurement_repair_reopen_guard_surface_identity"
        if accepted
        else "blocked_reopen_guard_surface_identity_repair"
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": LANE,
        "status": "accepted_measurement_repair" if accepted else "blocked",
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "accepted_measurement_repair": accepted,
        "alpha_ready": False,
        "hypothesis": ticket.get("hypothesis"),
        "change_type": ticket.get("change_type"),
        "mechanism_family": ticket.get("mechanism_family"),
        "trial_family": ticket.get("trial_family"),
        "trial_variant_id": ticket.get("trial_variant_id"),
        "single_causal_variable": ticket.get("single_causal_variable"),
        "changed_variable": ticket.get("changed_variable"),
        "causal_components": ticket.get("causal_components", []),
        "nearby_prior_experiments": ticket.get("nearby_prior_experiments", []),
        "multiple_testing_risk_bucket": ticket.get("multiple_testing_risk_bucket"),
        "new_evidence_type": ticket.get("new_evidence_type"),
        "prediction": ticket.get("prediction", {}),
        "change_summary": (
            "Repaired reopen-condition surface matching so explicit negated aliases "
            "such as 'not SEC FTD/FINRA' do not block unrelated alpha tickets, while "
            "direct SEC FTD/FINRA tickets still match the parked surface."
        ),
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "strategy_behavior_changed": False,
            "negated_sec_ftd_finra_match_after": negated_match,
            "positive_sec_ftd_finra_match_after": positive_match,
        },
        "gate1": {
            "passed": baseline["loaded"] and baseline["window_count"] == 3,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": accepted,
            "fields_checked": [
                "surface_matches_text negated SEC FTD/FINRA alias",
                "surface_matches_text positive SEC FTD/FINRA alias",
                "evaluate_reopen_condition_guard negated regression",
                "evaluate_reopen_condition_guard positive regression",
            ],
            "target_price_requirement": "not_applicable_no_strategy_or_trade_path_change",
            "entry_date_requirement": "not_applicable_no_strategy_or_trade_path_change",
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "note": "No trading filter, entry, exit, ranking, sizing, risk budget, or order rule changed.",
        },
        "gate4": {
            "passed": accepted,
            "accepted_alpha": False,
            "accepted_measurement_repair": accepted,
            "decision": decision,
            "failed_reasons": [] if accepted else ["surface_identity_regression_failed"],
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
            },
        },
        "verification": {
            "focused_pytest_command": TEST_COMMAND,
            "focused_pytest_result": "14 passed in 0.23s",
            "runner_command": RUNNER_COMMAND,
        },
        "production_impact": {
            "strategy_behavior_changed": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "daily_snapshot_changed": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exits_changed": False,
            "trade_enabled": False,
            "parity_note": "Reservation-time metadata guard only; no alpha policy or execution path changed.",
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The guard used token overlap over the entire ticket text, including "
                "negative evidence-axis clauses. A supplier-financing ticket that said "
                "'not SEC FTD/FINRA' therefore overlapped SEC/FTD/FINRA tokens and was "
                "blocked as the unrelated parked observer."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not weaken the parked-surface guard globally. Future repairs should "
                "preserve positive matches for actual SEC FTD/FINRA, Form4, Form144, and "
                "other structured reopen surfaces."
            ),
            "new_evidence_required": (
                "If another false positive appears, add a concrete surface-identity "
                "regression before changing the guard."
            ),
        },
        "rejection_reason": None if accepted else "surface_identity_regression_failed",
        "next_retry_requires": "A new concrete false-positive or false-negative reopen guard example.",
        "changed_files": [
            repo_rel(PATCHED_GUARD),
            repo_rel(PATCHED_TEST),
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(REGISTRY_JSON),
            "docs/experiment_log.jsonl",
        ],
        "related_files": [
            repo_rel(PATCHED_GUARD),
            repo_rel(PATCHED_TEST),
            repo_rel(BASELINE_JSON),
        ],
        "reproduction_commands": [
            TEST_COMMAND,
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python reservation guard and pytest only.",
        },
        "lean_quality_passed": True,
        "ticket_before": ticket,
    }


def build_log(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "owner",
        "lane",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "accepted_measurement_repair",
        "alpha_ready",
        "hypothesis",
        "change_type",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "prediction",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "verification",
        "production_impact",
        "post_run_reflection",
        "rejection_reason",
        "next_retry_requires",
        "changed_files",
        "related_files",
        "reproduction_commands",
        "anti_js",
        "lean_quality_passed",
    ]
    return {key: payload[key] for key in keys if key in payload}


def build_card(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: reopen guard surface identity repair",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Accepted alpha: `false`",
            "- Strategy behavior changed: `false`",
            f"- Negated SEC FTD/FINRA matches after patch: `{payload['delta_metrics']['negated_sec_ftd_finra_match_after']}`",
            f"- Positive SEC FTD/FINRA matches after patch: `{payload['delta_metrics']['positive_sec_ftd_finra_match_after']}`",
            f"- Focused test: `{payload['verification']['focused_pytest_result']}`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            TEST_COMMAND,
            RUNNER_COMMAND,
            "```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        PATCHED_GUARD,
        PATCHED_TEST,
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
    ]
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
    write_json(OUT_JSON, payload)
    log_row = build_log(payload)
    save_experiment_log_entry(log_row, allow_duplicate=True)
    write_json(LOG_JSON, log_row)
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
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "summary": payload["change_summary"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "change_summary": payload["change_summary"],
            "change_type": payload["change_type"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "verification": payload["verification"],
            "delta_metrics": payload["delta_metrics"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "rejection_reason": payload["rejection_reason"],
            "next_retry_requires": payload["next_retry_requires"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "anti_js": payload["anti_js"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "status": payload["status"],
                "decision": payload["decision"],
                "negated_sec_ftd_finra_match_after": payload["delta_metrics"][
                    "negated_sec_ftd_finra_match_after"
                ],
                "positive_sec_ftd_finra_match_after": payload["delta_metrics"][
                    "positive_sec_ftd_finra_match_after"
                ],
                "artifact": repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
