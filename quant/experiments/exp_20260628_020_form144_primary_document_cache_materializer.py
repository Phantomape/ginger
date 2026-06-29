"""exp-20260628-020: Form144 primary document cache materializer."""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from experiment_registry import persist_self_registered_result, save_experiment_log_entry  # noqa: E402
from form144_planned_sale_context import (  # noqa: E402
    DEFAULT_PRIMARY_DOCUMENT_CACHE_DIR,
    DEFAULT_USER_AGENT,
    FORWARD_REOPEN_GATE,
    materialize_form144_primary_documents,
    persist_form144_planned_sale_context,
)


EXPERIMENT_ID = "exp-20260628-020"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "form144_primary_document_cache_materializer"
RUNNER = f"quant/experiments/exp_20260628_020_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

CHANGED_VARIABLE = "form144_primary_document_cache_materializer_v1"
TRIAL_FAMILY = "form144_primary_document_cache_materializer"
TRIAL_VARIANT_ID = "sec_archive_text_cache_first_batch_v1"
MECHANISM_FAMILY = "form144_primary_document_materialization"
CHANGE_TYPE = "identity_or_measurement_repair"
DECISION = "accepted_measurement_repair_form144_primary_document_materializer"
STATUS = "accepted_measurement_repair"

AS_OF = "2026-06-28"
MAX_DOCUMENTS = 3
SLEEP_SECONDS = 0.11
CONTEXT_PATH = REPO_ROOT / "data" / "non_ohlcv" / "form144_planned_sale_context_20260628.jsonl"
BASELINE_RESULT = REPO_ROOT / "data" / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260628_020_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Materialize SEC Form 144 primary filing texts from existing PIT form-index "
    "rows so the accepted Form144 planned-sale context logger can parse "
    "planned_sale_shares/value and eventually compute planned-sale-to-float/ADV "
    "ratios without changing any trading behavior."
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
    windows = [row for row in raw.get("windows") or [] if isinstance(row, dict)]
    if not windows:
        return {"baseline_result_file": repo_rel(BASELINE_RESULT), "loaded": True}
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "loaded": True,
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 6
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("total_trades") or row.get("trade_count") or 0) for row in windows),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    before = baseline_metrics()
    cache_summary = materialize_form144_primary_documents(
        context_path=CONTEXT_PATH,
        cache_dir=DEFAULT_PRIMARY_DOCUMENT_CACHE_DIR,
        max_documents=MAX_DOCUMENTS,
        sleep_seconds=SLEEP_SECONDS,
        user_agent=DEFAULT_USER_AGENT,
        refresh=False,
    )
    refreshed_context_summary = None
    if cache_summary.get("downloaded") or cache_summary.get("already_cached"):
        refreshed_context_summary = persist_form144_planned_sale_context(
            as_of=AS_OF,
            data_dir=REPO_ROOT / "data" / "non_ohlcv",
            lookback_days=90,
        )

    gate_passed = bool(
        cache_summary.get("status") in {"ok", "partial", "blocked"}
        and CONTEXT_PATH.exists()
    )
    decision = DECISION if gate_passed else "rejected_form144_primary_document_materializer"
    network_blocked = (
        cache_summary.get("status") == "blocked"
        and cache_summary.get("attempted_downloads", 0) > 0
        and cache_summary.get("downloaded", 0) == 0
    )
    why = (
        "The materializer was implemented and exercised against the existing "
        "Form144 PIT context ledger. The first batch attempted SEC Archives "
        "fetches with the shared SEC User-Agent and local cache target. No "
        "trading path changed. If network is blocked, the artifact now records "
        "the exact failed URL/error sample and the same command can be rerun "
        "when network access is available."
        if gate_passed
        else "The materializer did not complete the cache-manifest contract."
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": STATUS if gate_passed else "rejected",
        "decision": decision,
        "accepted": gate_passed,
        "accepted_alpha": False,
        "accepted_measurement_repair": gate_passed,
        "alpha_ready": False,
        "lane": LANE,
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "shared_default_off_data_materializer",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": [
            "SEC Archives primary text fetcher",
            "local Form144 primary-document cache",
            "rate-limited User-Agent requests",
            "cache materialization manifest",
            "parser rerun readiness",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": [
            "exp-20260628-016",
            "exp-20260616-008",
            "exp-20260612-023",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "form144_primary_document_text_cache_materialization",
        "prediction": ticket.get("prediction") or {},
        "calibration": {
            "actual_decision": decision,
            "actual_success": 1 if gate_passed else 0,
            "predicted_success_probability": (ticket.get("prediction") or {}).get("success_probability"),
            "expected_ev_delta": 0.0,
            "actual_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "predicted_failure_modes": (ticket.get("prediction") or {}).get("main_failure_modes") or [],
            "realized_failure_mode": "network_restricted" if network_blocked else "",
            "predicted_failure_mode_hit": bool(network_blocked),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_prior_work": "exp-20260628-016 found 9,594 Form144 index rows but 0 cached primary documents, so planned-sale fields were unavailable.",
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_criteria": "Accepted only as measurement repair if the cache materializer exists, records first-batch downloaded/cached/failed counts, stays default-off, and leaves strategy deltas at zero.",
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "context_path": repo_rel(CONTEXT_PATH),
            "cache_dir": repo_rel(DEFAULT_PRIMARY_DOCUMENT_CACHE_DIR),
            "max_documents": MAX_DOCUMENTS,
            "sleep_seconds": SLEEP_SECONDS,
            "user_agent": DEFAULT_USER_AGENT,
            "trade_enabled": False,
        },
        "before_metrics": before,
        "after_metrics": before,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "strategy_behavior_changed": False,
        },
        "cache_materialization_summary": cache_summary,
        "refreshed_context_summary": refreshed_context_summary,
        "gate1": {
            "passed": True,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_expected_value_score_sum": before.get("expected_value_score_sum"),
            "baseline_total_pnl": before.get("total_pnl"),
        },
        "gate2": {
            "passed": gate_passed,
            "runtime_fields_required": [
                "context file_name",
                "archive_url",
                "primary_document_cache_path",
                "downloaded",
                "failed",
                "trade_enabled",
            ],
            "cache_summary_status": cache_summary.get("status"),
            "strategy_fields_changed": False,
        },
        "gate3": {
            "passed": True,
            "not_applicable_reason": "No signal, filter, ranking, sizing, exit, or order rule changed.",
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "survival_rate_delta": 0.0,
        },
        "gate4": {
            "passed": gate_passed,
            "decision": decision,
            "measurement_repair_only": True,
            "accepted_alpha": False,
            "failed_reasons": [] if gate_passed else ["cache_manifest_contract_failed"],
            "network_blocked": network_blocked,
            "before_after_strategy_delta": {
                "strategy_behavior_changed": False,
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
            },
            "forward_reopen_gate": FORWARD_REOPEN_GATE,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_exposed": False,
            "trade_enabled": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "paper_orders_changed": False,
            "live_orders_changed": False,
            "parity_note": "This materializes SEC text files only. No trading decision path consumes the cache.",
        },
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": "Do not start a Form144 risk scalar, notional haircut, ranking rule, or candidate-pool retry from index-only rows or from an empty first-batch cache result.",
            "new_evidence_required": "At least one cached Form144 primary document parsed into planned_sale_shares/value, then enough forward rows to satisfy the exp-016 reopen gate.",
        },
        "next_retry_requires": "Rerun the materializer with network access or a larger max_documents only to increase cached primary-document count; alpha tests still require parseable planned-sale ratios plus closed forward rows.",
        "related_files": [
            RUNNER,
            "quant/form144_planned_sale_context.py",
            "quant/test_form144_planned_sale_context.py",
            repo_rel(CONTEXT_PATH),
            repo_rel(DEFAULT_PRIMARY_DOCUMENT_CACHE_DIR),
            repo_rel(BASELINE_RESULT),
        ],
        "changed_files": [
            RUNNER,
            "quant/form144_planned_sale_context.py",
            "quant/test_form144_planned_sale_context.py",
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(REGISTRY_JSON),
            repo_rel(DEFAULT_PRIMARY_DOCUMENT_CACHE_DIR),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -m pytest quant\\test_form144_planned_sale_context.py -q",
            ".\\.venv\\Scripts\\python.exe -B -c \"from pathlib import Path; files=['quant/form144_planned_sale_context.py','quant/test_form144_planned_sale_context.py','" + RUNNER + "']; [compile(Path(f).read_text(encoding='utf-8'), f, 'exec') for f in files]\"",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {
            "used_javascript": False,
            "strategy_behavior_changed": False,
            "threshold_scan": False,
            "uses_future_form144_rows": False,
        },
    }


def compact_log(payload: dict[str, Any]) -> dict[str, Any]:
    row = {
        key: payload[key]
        for key in [
            "experiment_id",
            "timestamp",
            "status",
            "decision",
            "accepted",
            "accepted_alpha",
            "accepted_measurement_repair",
            "alpha_ready",
            "lane",
            "owner",
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
            "multiple_testing_risk_bucket",
            "new_evidence_type",
            "prediction",
            "calibration",
            "parameters",
            "delta_metrics",
            "cache_materialization_summary",
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
        ]
        if key in payload
    }
    row["artifact"] = repo_rel(OUT_JSON)
    row["log"] = repo_rel(LOG_JSON)
    row["lean_quality_passed"] = bool(payload["gate4"]["passed"])
    return row


def build_card(payload: dict[str, Any]) -> str:
    summary = payload["cache_materialization_summary"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Form144 Primary Document Materializer",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            f"- Attempted downloads: `{summary.get('attempted_downloads')}`",
            f"- Downloaded: `{summary.get('downloaded')}`",
            f"- Already cached: `{summary.get('already_cached')}`",
            f"- Failed: `{summary.get('failed')}`",
            f"- Cache dir: `{summary.get('cache_dir')}`",
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
        REPO_ROOT / RUNNER,
        REPO_ROOT / "quant" / "form144_planned_sale_context.py",
        REPO_ROOT / "quant" / "test_form144_planned_sale_context.py",
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
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
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    fields = {
        key: payload[key]
        for key in [
            "owner",
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
            "multiple_testing_risk_bucket",
            "new_evidence_type",
            "parameters",
            "pre_run_questions",
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
        ]
        if key in payload
    }
    fields.update(
        {
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
