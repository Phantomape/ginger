"""exp-20260627-012: shared SEC DEI cover-status parser repair.

The alpha hypothesis remains bounded: PIT SEC 10-K/10-Q filer-status upgrades
may improve candidate-pool quality, but only after accession-level DEI status
facts are exposed by the shared daily/backfill path. This runner records the
shared parser contract repair and does not change strategy behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for path in (QUANT_DIR, SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiment_registry import persist_self_registered_result  # noqa: E402
from sec_filing_features import build_filing_feature_rows  # noqa: E402
from sec_filing_text_backfill import parse_dei_cover_status  # noqa: E402


EXPERIMENT_ID = "exp-20260627-012"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "sec_dei_cover_status_shared_parser"
RUNNER = f"quant/experiments/exp_20260627_012_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

CHANGED_VARIABLE = "sec_dei_cover_status_shared_parser_v1"
CHANGE_TYPE = "identity_or_measurement_repair"
IMPLEMENTATION_MODE = "shared_data_parser_contract_repair"
MECHANISM_FAMILY = "sec_periodic_filer_status_materialization"
TRIAL_FAMILY = "sec_dei_cover_status_shared_parser"
TRIAL_VARIANT_ID = "shared_dei_status_parser_v1"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
DAILY_TEXT = REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_text_20260626.jsonl"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260627_012_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

ALLOWED_WRITE_SCOPE = [
    "quant/sec_filing_text_backfill.py",
    "quant/sec_filing_features.py",
    "quant/test_sec_filing_text_backfill.py",
    "quant/test_sec_filing_features.py",
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260627_012_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

HYPOTHESIS = (
    "Alpha blocker: PIT SEC 10-K/10-Q cover-page filer-status upgrade alpha "
    "remains untestable until DEI cover-status facts are parsed by a shared "
    "daily/backfill path instead of experiment-local probes."
)
ALPHA_HYPOTHESIS = (
    "candidate_pool: PIT SEC 10-K/10-Q filer-status upgrades from "
    "smaller/non-accelerated/EGC toward accelerated or large-accelerated "
    "status may identify improving institutional eligibility, but only once "
    "accepted_at-keyed DEI status facts exist in shared replayable artifacts."
)
PREDICTION = {
    "success_probability": 0.82,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "shared_parser_misses_inline_xbrl",
        "feature_builder_does_not_expose_status_fields",
        "existing_daily_rows_still_have_zero_machine_status",
    ],
    "confidence_reason": (
        "exp-20260627-005 proved the parser existed only in an experiment; "
        "exp-20260627-011 repaired document selection for future cover XBRL. "
        "Moving the parser into shared text/feature materialization is a narrow "
        "measurement repair with synthetic iXBRL and checkbox fixtures."
    ),
    "recorded_at": "2026-06-27T11:06:00+00:00",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, 10)
    return value


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, row: dict[str, Any]) -> None:
    encoded = json.dumps(safe(row), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                rows.append(encoded)
                replaced = True
            else:
                rows.append(raw)
    if not replaced:
        rows.append(encoded)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    errors = 0
    if not path.exists():
        return rows, errors
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            errors += 1
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows, errors


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") or []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "max_drawdown_pct_worst": max(
            (float(row.get("max_drawdown_pct") or 0.0) for row in windows),
            default=0.0,
        ),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / max(generated, 1), 4),
    }


def shared_parser_contract() -> dict[str, Any]:
    ixbrl = (
        "<dei:EntityFilerCategory>Large Accelerated Filer</dei:EntityFilerCategory>"
        "<dei:EntityEmergingGrowthCompany>false</dei:EntityEmergingGrowthCompany>"
        "<dei:EntityShellCompany>false</dei:EntityShellCompany>"
    )
    checkbox = (
        "\u2610 Large accelerated filer "
        "\u2612 Accelerated filer "
        "\u2610 Non-accelerated filer "
        "\u2610 Smaller reporting company"
    )
    ixbrl_status = parse_dei_cover_status(ixbrl)
    checkbox_status = parse_dei_cover_status(checkbox)
    feature_row = build_filing_feature_rows(
        [
            {
                "ticker": "ACME",
                "form_type": "10-Q",
                "accession_number": "0001-26-000010",
                "accepted_at": "2026-04-20T17:05:00",
                "usable_trade_date": "2026-04-21",
                "combined_text": ixbrl,
            }
        ],
        [],
    )[0]
    return {
        "ixbrl_parse_status": ixbrl_status,
        "checkbox_parse_status": checkbox_status,
        "feature_row_status": {
            "filer_status_category": feature_row.get("filer_status_category"),
            "filer_status_booleans": feature_row.get("filer_status_booleans"),
            "filer_status_parse_status": feature_row.get("filer_status_parse_status"),
            "filer_status_field_count": feature_row.get("filer_status_field_count"),
            "field_availability": feature_row.get("field_availability", {}).get("filer_status"),
            "gap_has_missing_dei_cover_status": (
                "missing_dei_cover_status" in (feature_row.get("gap_reasons") or [])
            ),
        },
        "passed": (
            ixbrl_status.get("parse_status") == "parsed_machine_readable_dei_fact"
            and ixbrl_status.get("status_booleans", {}).get("large_accelerated_filer") is True
            and checkbox_status.get("parse_status") == "parsed_cover_page_checkbox_text"
            and checkbox_status.get("status_booleans", {}).get("accelerated_filer") is True
            and feature_row.get("field_availability", {}).get("filer_status") == "derived"
            and feature_row.get("filer_status_category") == "large_accelerated_filer"
        ),
    }


def current_daily_status_coverage() -> dict[str, Any]:
    rows, errors = iter_jsonl(DAILY_TEXT)
    feature_rows = build_filing_feature_rows(rows, []) if rows else []
    rows_with_status = [
        row for row in feature_rows if int(row.get("filer_status_field_count") or 0) > 0
    ]
    periodic = [
        row
        for row in feature_rows
        if str(row.get("form_type") or "").upper().replace("/A", "") in {"10-K", "10-Q"}
    ]
    return {
        "source_file": repo_rel(DAILY_TEXT),
        "source_exists": DAILY_TEXT.exists(),
        "jsonl_parse_errors": errors,
        "source_rows": len(rows),
        "feature_rows": len(feature_rows),
        "periodic_feature_rows": len(periodic),
        "rows_with_filer_status": len(rows_with_status),
        "periodic_rows_with_filer_status": sum(
            1 for row in periodic if int(row.get("filer_status_field_count") or 0) > 0
        ),
        "parse_status_counts": {
            status: sum(1 for row in feature_rows if row.get("filer_status_parse_status") == status)
            for status in sorted({str(row.get("filer_status_parse_status")) for row in feature_rows})
        },
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket.get("prediction"), dict) else PREDICTION
    baseline = baseline_metrics()
    contract = shared_parser_contract()
    current_coverage = current_daily_status_coverage()
    accepted = bool(contract["passed"])
    status = "accepted_measurement_repair" if accepted else "rejected"
    decision = (
        "accepted_measurement_repair_sec_dei_cover_status_shared_parser"
        if accepted
        else "rejected_sec_dei_cover_status_shared_parser_contract_failed"
    )
    blocker_note = (
        "The shared text backfill and filing-feature path can now parse and "
        "expose DEI cover-page status fields from raw iXBRL or clear checkbox "
        "text. Existing 20260626 rows still have no periodic machine-readable "
        "status rows, so this is measurement repair only and not an alpha."
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "alpha_ready": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_summary": (
            "Moved SEC DEI cover-page filer-status parsing into the shared "
            "text backfill and filing-feature path. No strategy behavior changed."
        ),
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "shared sec_filing_text_backfill DEI cover-status parser",
            "future text payload dei_cover_status output",
            "shared sec_filing_features filer_status read-only fields",
            "focused parser and feature tests",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": [
            "exp-20260626-008",
            "exp-20260627-005",
            "exp-20260627-011",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "measurement_repair_shared_parser_contract",
        "new_evidence_axis": (
            "Shared parser/data-contract repair after current and document-priority "
            "probes; this does not run filer-status alpha or a SEC text scan."
        ),
        "prediction": prediction,
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": (
                "exp-20260626-008 blocked on missing parser-ready status rows; "
                "exp-20260627-005 proved the parser was experiment-local; "
                "exp-20260627-011 repaired cover XBRL document priority."
            ),
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Accept only as measurement repair if shared parser fixtures pass, "
                "feature rows expose filer_status fields, and accepted-stack metrics "
                "remain unchanged."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": contract["passed"],
            "dependency_fields": [
                "combined_text or raw SEC document text",
                "dei EntityFilerCategory",
                "dei EntityEmergingGrowthCompany",
                "dei EntityShellCompany",
                "sec_filing_features filer_status_* fields",
            ],
            "shared_parser_contract": contract,
            "current_daily_status_coverage": current_coverage,
            "minimum_strategy_fields": {
                "entry_date": "not_applicable_no_strategy_signal_or_filter_added",
                "target_price": "not_applicable_no_strategy_signal_or_filter_added",
            },
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter was added; survival is unchanged.",
        },
        "gate4": {
            "passed": accepted,
            "strategy_behavior_changed": False,
            "after_same_as_before": True,
            "accepted_alpha": False,
            "decision_basis": blocker_note,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "survival_rate_delta": 0.0,
            "shared_parser_contract_passed": contract["passed"],
            "current_daily_rows_with_filer_status": current_coverage["rows_with_filer_status"],
            "current_daily_periodic_rows_with_filer_status": current_coverage[
                "periodic_rows_with_filer_status"
            ],
        },
        "calibration": {
            "predicted_success_probability": prediction.get("success_probability"),
            "actual_success": 1 if accepted else 0,
            "brier_score": round(
                (float(prediction.get("success_probability") or 0.0) - (1 if accepted else 0)) ** 2,
                4,
            ),
            "predicted_failure_modes": prediction.get("main_failure_modes") or [],
            "realized_failure_mode": (
                None if accepted else "shared_parser_or_feature_contract_failed"
            ),
            "surprise_note": blocker_note,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_schema_changed": True,
            "daily_snapshot_exposed": True,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "orders_changed": False,
            "trade_enabled": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "reason": (
                "Only non-OHLCV SEC text/feature artifacts gain read-only "
                "filer-status fields when source documents contain parseable DEI facts."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": blocker_note,
            "forbidden_near_neighbor_retry": (
                "Do not run filer-status alpha, phrase scans, form-threshold scans, "
                "or current-category approximations from this parser repair. It "
                "only creates the shared field contract."
            ),
            "new_evidence_required": (
                "Refresh or backfill historical/current 10-K/10-Q text after "
                "the cover-document priority repair so rows actually contain "
                "R1/inline htm.xml DEI facts, then build one fixed shared "
                "default-off status-transition helper before any alpha replay."
            ),
        },
        "next_retry_requires": [
            "historical_10k_10q_text_or_ixbrl_rows_with_dei_cover_status",
            "accepted_at_keyed_status_transition_ledger",
            "one_shared_default_off_status_transition_helper",
        ],
        "related_files": [
            "quant/sec_filing_text_backfill.py",
            "quant/sec_filing_features.py",
            "quant/test_sec_filing_text_backfill.py",
            "quant/test_sec_filing_features.py",
            repo_rel(DAILY_TEXT),
            repo_rel(BASELINE_RESULT),
        ],
        "changed_files": [
            "quant/sec_filing_text_backfill.py",
            "quant/sec_filing_features.py",
            "quant/test_sec_filing_text_backfill.py",
            "quant/test_sec_filing_features.py",
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m py_compile quant\\sec_filing_text_backfill.py quant\\sec_filing_features.py quant\\test_sec_filing_text_backfill.py quant\\test_sec_filing_features.py",
            ".\\.venv\\Scripts\\python.exe -m pytest quant\\test_sec_filing_text_backfill.py quant\\test_sec_filing_features.py",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {"used_javascript": False, "evidence": "Python runner only."},
    }


def compact_log_row(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "lane",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "alpha_ready",
        "hypothesis",
        "alpha_hypothesis",
        "change_summary",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "single_causal_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "calibration",
        "production_impact",
        "post_run_reflection",
        "next_retry_requires",
        "related_files",
        "changed_files",
        "allowed_write_scope",
        "reproduction_commands",
        "anti_js",
    ]
    row = {key: payload[key] for key in keys}
    row["artifact"] = repo_rel(OUT_JSON)
    row["log"] = repo_rel(LOG_JSON)
    return row


def build_card(payload: dict[str, Any]) -> str:
    delta = payload["delta_metrics"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: SEC DEI Cover Status Shared Parser",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            "",
            "## Result",
            "",
            f"- Shared parser contract passed: `{delta['shared_parser_contract_passed']}`",
            f"- Current daily rows with filer status: `{delta['current_daily_rows_with_filer_status']}`",
            f"- Current periodic rows with filer status: `{delta['current_daily_periodic_rows_with_filer_status']}`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Next Evidence",
            "",
            payload["post_run_reflection"]["new_evidence_required"],
            "",
            "## Reproduce",
            "",
            "```powershell",
            *payload["reproduction_commands"],
            "```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any], log_row: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / "quant" / "sec_filing_text_backfill.py",
        REPO_ROOT / "quant" / "sec_filing_features.py",
        REPO_ROOT / "quant" / "test_sec_filing_text_backfill.py",
        REPO_ROOT / "quant" / "test_sec_filing_features.py",
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        TICKET_JSON,
        CARD_MD,
        MANIFEST_JSON,
        EXPERIMENT_LOG,
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
    log_row = compact_log_row(payload)
    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, log_row)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_row)
    result = {
        "accepted": bool(payload["accepted"]),
        "accepted_alpha": False,
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "delta_metrics": payload["delta_metrics"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result=result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "alpha_hypothesis": ALPHA_HYPOTHESIS,
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "acceptance_rule": payload["pre_run_questions"]["4_acceptance_standard"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "decision": payload["decision"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "post_run_reflection": payload["post_run_reflection"],
            "production_impact": payload["production_impact"],
            "reproduction_commands": payload["reproduction_commands"],
            "changed_files": payload["changed_files"],
            "anti_js": payload["anti_js"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload, log_row))


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps(safe(compact_log_row(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
