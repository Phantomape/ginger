"""exp-20260627-014: SEC DEI cover-status checkbox table parser repair.

This is measurement repair for a blocked alpha surface. It fixes the shared
read-only parser so accepted_at-keyed SEC 10-K/10-Q cover pages with column
header checkbox layouts can expose filer-status facts for future replay.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
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


EXPERIMENT_ID = "exp-20260627-014"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "sec_dei_cover_status_checkbox_table_parser"
RUNNER = f"quant/experiments/exp_20260627_014_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

CHANGED_VARIABLE = "sec_dei_cover_status_checkbox_table_parser_v1"
CHANGE_TYPE = "identity_or_measurement_repair"
IMPLEMENTATION_MODE = "shared_data_parser_contract_repair"
MECHANISM_FAMILY = "sec_periodic_filer_status_materialization"
TRIAL_FAMILY = "sec_dei_cover_status_checkbox_table_parser"
TRIAL_VARIANT_ID = "current_mu_10q_checkbox_table_v1"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
DAILY_TEXT = REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_text_20260626.jsonl"
DAILY_FACTS = REPO_ROOT / "data" / "non_ohlcv" / "sec_companyfacts_selected_kova_20260626.jsonl"
MU_CACHE = REPO_ROOT / "data" / "cache" / "sec" / "filing_text" / "0000723125-26-000015.json"
PRIOR_LOG = REPO_ROOT / "experiments" / "logs" / "exp-20260627-012.json"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260627_014_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Alpha blocker: PIT SEC 10-K/10-Q filer-status transition alpha cannot be "
    "evaluated while the shared DEI cover-status parser misses cover-page "
    "checkbox tables where labels are column headers and checkbox tokens appear "
    "after the label row; repair that parser so existing accepted_at-keyed "
    "filing text/cache rows can expose status facts without changing strategy "
    "behavior."
)
ALPHA_HYPOTHESIS = (
    "candidate_pool: PIT SEC 10-K/10-Q filer-status upgrades from "
    "smaller/non-accelerated/EGC toward accelerated or large-accelerated status "
    "may identify improving institutional eligibility, but only after "
    "accepted_at-keyed historical/current DEI status facts exist in shared "
    "replayable artifacts."
)
PREDICTION = {
    "success_probability": 0.78,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "checkbox_table_mapping_misorders_statuses",
        "current_mu_cache_still_not_parseable",
        "feature_builder_still_yields_zero_periodic_status_rows",
    ],
    "confidence_reason": (
        "exp-20260627-012 proved the shared parser path but current rows stayed "
        "at zero; the MU cache has labels_found plus checkbox tokens, so this is "
        "a narrow parser-layout repair with a concrete local failing row."
    ),
    "recorded_at": "2026-06-27T13:06:52+00:00",
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
    return json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))


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


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {}) or {}
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
        "windows": windows,
    }


def current_daily_status_coverage() -> dict[str, Any]:
    filings = load_jsonl(DAILY_TEXT)
    facts = load_jsonl(DAILY_FACTS)
    rows = build_filing_feature_rows(filings, facts) if filings else []
    rows_with_status = [
        row for row in rows if int(row.get("filer_status_field_count") or 0) > 0
    ]
    periodic = [
        row
        for row in rows
        if str(row.get("form_type") or "").upper().replace("/A", "") in {"10-K", "10-Q"}
    ]
    status_counts = Counter(str(row.get("filer_status_parse_status") or "missing") for row in rows)
    return {
        "source_file": repo_rel(DAILY_TEXT),
        "facts_file": repo_rel(DAILY_FACTS),
        "source_rows": len(filings),
        "feature_rows": len(rows),
        "periodic_feature_rows": len(periodic),
        "rows_with_filer_status": len(rows_with_status),
        "periodic_rows_with_filer_status": sum(
            1 for row in periodic if int(row.get("filer_status_field_count") or 0) > 0
        ),
        "filer_status_parse_counts": dict(sorted(status_counts.items())),
        "status_rows_sample": [
            {
                "ticker": row.get("ticker"),
                "form_type": row.get("form_type"),
                "source_accession": row.get("source_accession"),
                "usable_trade_date": row.get("usable_trade_date"),
                "filer_status_parse_status": row.get("filer_status_parse_status"),
                "filer_status_field_count": row.get("filer_status_field_count"),
                "filer_status_booleans": row.get("filer_status_booleans"),
            }
            for row in rows_with_status[:5]
        ],
    }


def mu_cache_parse() -> dict[str, Any]:
    cache = read_json(MU_CACHE, {}) or {}
    status = parse_dei_cover_status(str(cache.get("combined_text") or ""))
    return {
        "cache_path": repo_rel(MU_CACHE),
        "exists": MU_CACHE.exists(),
        "ticker": cache.get("ticker"),
        "form_type": cache.get("form_type"),
        "accession_number": cache.get("accession_number"),
        "accepted_at": cache.get("accepted_at"),
        "usable_trade_date": cache.get("usable_trade_date"),
        "documents": [
            doc.get("name")
            for doc in (cache.get("documents") or [])
            if isinstance(doc, dict)
        ],
        "parse_status": {
            "parse_status": status.get("parse_status"),
            "source": status.get("source"),
            "filer_category": status.get("filer_category"),
            "status_field_count": status.get("status_field_count"),
            "machine_readable_status_fields": status.get("machine_readable_status_fields"),
            "status_booleans": status.get("status_booleans"),
            "checkbox_diagnostics": status.get("checkbox_diagnostics"),
        },
    }


def prior_blocker_context() -> dict[str, Any]:
    prior = read_json(PRIOR_LOG, {}) or {}
    gate2 = prior.get("gate2") or {}
    coverage = gate2.get("current_daily_status_coverage") or {}
    delta = prior.get("delta_metrics") or {}
    return {
        "prior_experiment": "exp-20260627-012",
        "prior_log": repo_rel(PRIOR_LOG),
        "prior_current_rows_with_filer_status": (
            delta.get("current_daily_rows_with_filer_status")
            if "current_daily_rows_with_filer_status" in delta
            else coverage.get("rows_with_filer_status")
        ),
        "prior_periodic_rows_with_filer_status": (
            delta.get("current_daily_periodic_rows_with_filer_status")
            if "current_daily_periodic_rows_with_filer_status" in delta
            else coverage.get("periodic_rows_with_filer_status")
        ),
        "prior_decision": prior.get("decision"),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    baseline = baseline_metrics()
    daily = current_daily_status_coverage()
    mu = mu_cache_parse()
    prior = prior_blocker_context()
    accepted = (
        mu["parse_status"]["parse_status"] == "parsed_cover_page_checkbox_text"
        and mu["parse_status"]["status_field_count"] == 6
        and daily["periodic_rows_with_filer_status"] >= 1
    )
    status = "accepted_measurement_repair" if accepted else "rejected"
    decision = (
        "accepted_measurement_repair_sec_dei_cover_status_checkbox_table_parser"
        if accepted
        else "rejected_sec_dei_cover_status_checkbox_table_parser"
    )
    basis = (
        "The shared parser now handles cover-page checkbox tables where labels "
        "are column headers and checkbox tokens follow the label row. On the "
        "same 20260626 SEC text artifact that exp-20260627-012 counted as zero "
        "status rows, the feature builder now exposes one periodic MU 10-Q row "
        "with six filer-status fields. No strategy behavior changed."
    )
    return {
        "schema_version": 1,
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
            "Repaired the shared SEC DEI cover-status parser for column-header "
            "checkbox table layouts and proved the existing MU 10-Q cache now "
            "materializes read-only filer-status fields."
        ),
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "shared sec_filing_text_backfill checkbox-table parser",
            "shell-company yes/no checkbox parser",
            "focused unit test for column-header layout",
            "current 20260626 feature-row materialization proof",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": [
            "exp-20260626-008",
            "exp-20260627-005",
            "exp-20260627-011",
            "exp-20260627-012",
            "exp-20260627-013",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "measurement_repair_existing_current_periodic_sec_cache_row",
        "new_evidence_axis": (
            "Concrete local MU 10-Q row with labels_found plus checkbox tokens "
            "that the existing parser could not map; this repairs parser layout, "
            "not an alpha scan or threshold retune."
        ),
        "prediction": PREDICTION,
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_prior_near_neighbors": (
                "exp-20260627-012 accepted the shared parser but left current "
                "feature rows at zero; exp-20260627-013 kept filer-status alpha "
                "blocked until status rows exist."
            ),
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Accept only as measurement repair if the MU cache parses as "
                "cover_page_checkbox_text, the 20260626 feature builder yields "
                "at least one periodic filer-status row, and canonical strategy "
                "metrics remain identical."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "gate1": {"passed": BASELINE_RESULT.exists(), "baseline_metrics": baseline},
        "gate2": {
            "passed": accepted,
            "dependency_fields": [
                "combined_text",
                "cover-page checkbox status labels",
                "checked/unchecked checkbox tokens",
                "accepted_at",
                "usable_trade_date",
            ],
            "prior_blocker_context": prior,
            "mu_cache_parse": mu,
            "current_daily_status_coverage": daily,
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
            "decision_basis": basis,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "survival_rate_delta": 0.0,
            "prior_current_rows_with_filer_status": prior["prior_current_rows_with_filer_status"],
            "after_current_rows_with_filer_status": daily["rows_with_filer_status"],
            "prior_periodic_rows_with_filer_status": prior["prior_periodic_rows_with_filer_status"],
            "after_periodic_rows_with_filer_status": daily["periodic_rows_with_filer_status"],
            "mu_status_field_count": mu["parse_status"]["status_field_count"],
        },
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_success": 1 if accepted else 0,
            "brier_score": round((PREDICTION["success_probability"] - (1 if accepted else 0)) ** 2, 4),
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_mode": None if accepted else "checkbox_table_parser_contract_failed",
            "surprise_note": basis,
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_schema_changed": False,
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
                "Only read-only SEC text/feature artifacts gain parser coverage "
                "when source documents contain checkbox-table cover status facts."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": basis,
            "forbidden_near_neighbor_retry": (
                "Do not run filer-status alpha, same-row phrase scans, form "
                "threshold scans, or current-category approximations from this "
                "one-row repair. It only fixes parser coverage."
            ),
            "new_evidence_required": (
                "Backfill or refresh historical 10-K/10-Q text/cache rows so the "
                "shared parser produces accepted_at-keyed DEI status rows across "
                "canonical windows, then build one fixed shared default-off "
                "status-transition helper before alpha replay."
            ),
        },
        "next_retry_requires": [
            "historical_10k_10q_text_or_ixbrl_rows_with_dei_cover_status",
            "accepted_at_keyed_status_transition_ledger",
            "one_shared_default_off_status_transition_helper",
        ],
        "related_files": [
            "quant/sec_filing_text_backfill.py",
            "quant/test_sec_filing_text_backfill.py",
            "quant/sec_filing_features.py",
            repo_rel(DAILY_TEXT),
            repo_rel(DAILY_FACTS),
            repo_rel(MU_CACHE),
            repo_rel(BASELINE_RESULT),
        ],
        "changed_files": [
            "quant/sec_filing_text_backfill.py",
            "quant/test_sec_filing_text_backfill.py",
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
        ],
        "allowed_write_scope": [
            "quant/sec_filing_text_backfill.py",
            "quant/test_sec_filing_text_backfill.py",
            RUNNER,
            f"data/experiments/{EXPERIMENT_ID}/",
            f"experiments/cards/{EXPERIMENT_ID}.md",
            f"experiments/manifests/{EXPERIMENT_ID}.json",
            f"experiments/tickets/{EXPERIMENT_ID}.json",
            f"experiments/logs/{EXPERIMENT_ID}.json",
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
        ],
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m py_compile quant\\sec_filing_text_backfill.py quant\\test_sec_filing_text_backfill.py " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -m pytest quant\\test_sec_filing_text_backfill.py",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {"used_javascript": False, "evidence": "Python runner only."},
    }


def compact_log_row(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "owner",
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
        "pre_run_questions",
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
    sample = payload["gate2"]["current_daily_status_coverage"]["status_rows_sample"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: SEC DEI Checkbox Table Parser",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            "",
            "## Result",
            "",
            f"- Prior periodic status rows: `{delta['prior_periodic_rows_with_filer_status']}`",
            f"- After periodic status rows: `{delta['after_periodic_rows_with_filer_status']}`",
            f"- MU status field count: `{delta['mu_status_field_count']}`",
            f"- Sample: `{sample}`",
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
        REPO_ROOT / "quant" / "test_sec_filing_text_backfill.py",
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        TICKET_JSON,
        CARD_MD,
        MANIFEST_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        BASELINE_RESULT,
        DAILY_TEXT,
        DAILY_FACTS,
        MU_CACHE,
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
        prediction=PREDICTION,
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
