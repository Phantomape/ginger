"""exp-20260704-003: FINRA OTC weekly internalization archive readiness.

Measurement/readiness only. The next legal venue-decomposition alpha candidate
after the rejected ATS dark-share scan is FINRA's non-ATS OTC weekly summary
(`OTC_W_SMBL`). This runner checks whether the source exists locally or can be
reached from the current automation environment, then records the reopen
condition needed before any candidate-pool, ranking, sizing, or paper-order
rule is attempted.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260704-003"
OWNER = "alpha-explore"
SLUG = "finra_otc_weekly_internalization_archive_readiness"
RUNNER = f"quant/experiments/exp_20260704_003_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
ATS_DIR = REPO_ROOT / "data" / "non_ohlcv" / "finra_ats_weekly"
ATS_ROWS = ATS_DIR / "rows.jsonl"
ATS_MANIFEST = ATS_DIR / "manifest.json"
OTC_DIR = REPO_ROOT / "data" / "non_ohlcv" / "finra_otc_weekly"
OTC_ROWS = OTC_DIR / "rows.jsonl"
OTC_MANIFEST = OTC_DIR / "manifest.json"

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260704_003_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Alpha blocker: FINRA non-ATS OTC weekly internalization is the next legal "
    "venue-decomposition alpha surface after exp-20260703-016 ATS dark-share "
    "rejection, but the repo must first prove an as-of weekly OTC_W_SMBL archive "
    "can be materialized before any candidate-pool or sizing rule is credible."
)
ALPHA_HYPOTHESIS = (
    "If non-ATS wholesaler/internalization flow is the missing venue split, then "
    "tickers with unusually high OTC weekly share or notional internalization "
    "should separate liquidity-friction/flow-absorption candidates from ATS dark "
    "pool false positives once the source is available as a PIT weekly archive."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "finra_non_ats_wholesaler_internalization"
TRIAL_FAMILY = "finra_weekly_venue_decomposition_source_readiness"
TRIAL_VARIANT_ID = "otc_w_smbl_initial_archive_readiness_v1"
CHANGED_VARIABLE = "finra_otc_weekly_internalization_archive_readiness_v1"
NEW_EVIDENCE_TYPE = "new_finra_otc_w_smbl_summary_type_source_readiness"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260703-016",
    "exp-20260625-019",
    "exp-20260625-024",
    "exp-20260627-023",
]
CAUSAL_COMPONENTS = [
    "local FINRA ATS archive cross-check",
    "local FINRA OTC archive readiness audit",
    "FINRA OTC_W_SMBL endpoint availability probe",
    "blocked reopen-condition contract",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260704_003_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]
PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "no_local_otc_cache",
        "finra_api_network_blocked",
        "otc_schema_not_pit_enough",
        "insufficient_weekly_history",
    ],
    "confidence_reason": (
        "Prior ATS experiment found this as the legal sibling source, but local "
        "cache checks found only ATS_W_SMBL and the current automation "
        "environment appears to block outbound FINRA API calls."
    ),
    "recorded_at": "2026-07-04T02:07:46+00:00",
}

OTC_SUMMARY_TYPE = "OTC_W_SMBL"
ATS_SUMMARY_TYPE = "ATS_W_SMBL"
REQUIRED_OTC_FIELDS = [
    "summaryTypeCode",
    "issueSymbolIdentifier",
    "weekStartDate",
    "initialPublishedDate",
    "totalWeeklyShareQuantity",
    "totalWeeklyTradeCount",
    "totalNotionalSum",
]
REOPEN_CONDITION = (
    "Reopen only after a local PIT FINRA OTC_W_SMBL weekly archive is available "
    "with summaryTypeCode, issueSymbolIdentifier, weekStartDate, publication/as-of "
    "date, share quantity, trade count, and notional fields for at least 26 "
    "published weeks and >=40 Kova candidate tickers, or after network/cache "
    "access is restored enough to materialize that archive. Then run a "
    "shared-paper-first candidate source with Gate 1-4; do not retune ATS_W_SMBL "
    "dark-share thresholds."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path, default: Any = None) -> Any:
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def read_jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(item)
            if limit is not None and len(rows) >= limit:
                break
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    if path.exists():
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    records.append({"raw": line})
                    continue
                if item.get("experiment_id") != EXPERIMENT_ID:
                    records.append(item)
    records.append(record)
    path.write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in records),
        encoding="utf-8",
    )


def summarize_rows(rows: list[dict[str, Any]], summary_type: str) -> dict[str, Any]:
    matching = [row for row in rows if str(row.get("summaryTypeCode", "")) == summary_type]
    tickers = {
        str(row.get("issueSymbolIdentifier") or row.get("symbol") or "").upper()
        for row in matching
        if row.get("issueSymbolIdentifier") or row.get("symbol")
    }
    weeks = {
        str(row.get("weekStartDate") or row.get("week_start") or "")
        for row in matching
        if row.get("weekStartDate") or row.get("week_start")
    }
    published = {
        str(row.get("initialPublishedDate") or row.get("published_date") or "")
        for row in matching
        if row.get("initialPublishedDate") or row.get("published_date")
    }
    return {
        "row_count": len(matching),
        "unique_tickers": len(tickers),
        "week_count": len(weeks),
        "published_date_count": len(published),
        "sample_tickers": sorted(tickers)[:10],
        "sample_weeks": sorted(weeks)[:5],
    }


def summarize_weekly_archive(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tickers = {
        str(row.get("issueSymbolIdentifier") or row.get("ticker") or row.get("symbol") or "").upper()
        for row in rows
        if row.get("issueSymbolIdentifier") or row.get("ticker") or row.get("symbol")
    }
    weeks = {
        str(row.get("weekStartDate") or row.get("week_start_date") or row.get("week_start") or "")
        for row in rows
        if row.get("weekStartDate") or row.get("week_start_date") or row.get("week_start")
    }
    published = {
        str(
            row.get("initialPublishedDate")
            or row.get("published_date")
            or row.get("publication_date")
            or ""
        )
        for row in rows
        if row.get("initialPublishedDate")
        or row.get("published_date")
        or row.get("publication_date")
    }
    return {
        "row_count": len(rows),
        "unique_tickers": len(tickers),
        "week_count": len(weeks),
        "published_date_count": len(published),
        "sample_tickers": sorted(tickers)[:10],
        "sample_weeks": sorted(weeks)[:5],
    }


def scan_for_local_otc_mentions() -> list[str]:
    hits: list[str] = []
    roots = [REPO_ROOT / "data" / "non_ohlcv", REPO_ROOT / "data" / "experiments"]
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            name = path.name.lower()
            parent = path.parent.as_posix().lower()
            if "otc" in name or "otc" in parent:
                hits.append(repo_rel(path))
                if len(hits) >= 50:
                    return hits
    return hits


def ascii_safe(value: Any) -> str:
    return str(value).encode("ascii", "backslashreplace").decode("ascii")


def probe_finra_otc_endpoint() -> dict[str, Any]:
    payload = {
        "limit": 1,
        "offset": 0,
        "fields": REQUIRED_OTC_FIELDS + ["tierIdentifier"],
        "compareFilters": [
            {
                "compareType": "EQUAL",
                "fieldName": "summaryTypeCode",
                "fieldValue": OTC_SUMMARY_TYPE,
            },
            {
                "compareType": "GTE",
                "fieldName": "weekStartDate",
                "fieldValue": "2026-05-01",
            },
        ],
    }
    url = "https://api.finra.org/data/group/otcMarket/name/weeklySummary"
    try:
        import requests

        response = requests.post(
            url,
            json=payload,
            headers={"Accept": "application/json"},
            timeout=12,
        )
        text = ascii_safe(response.text[:500])
        rows = response.json() if response.ok else None
        if isinstance(rows, list):
            row_count = len(rows)
            sample_keys = sorted(rows[0].keys()) if rows and isinstance(rows[0], dict) else []
        else:
            row_count = None
            sample_keys = []
        return {
            "attempted": True,
            "url": url,
            "status_code": response.status_code,
            "ok": response.ok,
            "row_count": row_count,
            "sample_keys": sample_keys,
            "text_prefix": text,
            "error_type": None,
            "error": None,
            "https_proxy": os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"),
            "http_proxy": os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy"),
        }
    except Exception as exc:  # noqa: BLE001 - this is a diagnostic probe.
        return {
            "attempted": True,
            "url": url,
            "ok": False,
            "status_code": None,
            "row_count": None,
            "sample_keys": [],
            "text_prefix": "",
            "error_type": type(exc).__name__,
            "error": ascii_safe(exc),
            "https_proxy": os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"),
            "http_proxy": os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy"),
        }


def baseline_gate() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    return {
        "exists": BASELINE_RESULT.exists(),
        "path": repo_rel(BASELINE_RESULT),
        "sha256": sha256(BASELINE_RESULT),
        "top_level_keys": sorted(payload.keys())[:20] if isinstance(payload, dict) else [],
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    ats_manifest = read_json(ATS_MANIFEST, {})
    otc_manifest = read_json(OTC_MANIFEST, {})
    ats_rows = read_jsonl(ATS_ROWS)
    otc_rows = read_jsonl(OTC_ROWS)
    api_probe = probe_finra_otc_endpoint()

    ats_summary = summarize_weekly_archive(ats_rows)
    ats_otc_accidental = summarize_rows(ats_rows, OTC_SUMMARY_TYPE)
    otc_summary = summarize_weekly_archive(otc_rows)
    local_otc_ready = (
        otc_summary["row_count"] > 0
        and otc_summary["week_count"] >= 26
        and otc_summary["unique_tickers"] >= 40
    )
    api_materializable = bool(api_probe.get("ok") and api_probe.get("row_count"))

    failed_reasons: list[str] = []
    if otc_summary["row_count"] == 0:
        failed_reasons.append("no_local_otc_w_smbl_rows")
    if ats_otc_accidental["row_count"] == 0:
        failed_reasons.append("existing_finra_ats_archive_contains_no_otc_w_smbl_rows")
    if not api_probe.get("ok"):
        failed_reasons.append("finra_api_probe_failed")
    if api_probe.get("error_type") == "ProxyError":
        failed_reasons.append("network_proxy_blocks_finra_api")
    if not local_otc_ready:
        failed_reasons.append("otc_archive_not_gate_ready")

    status = "blocked"
    decision = "blocked_finra_otc_w_smbl_archive_not_materialized"
    accepted_measurement_repair = False
    if local_otc_ready:
        status = "accepted_measurement_repair"
        decision = "accepted_finra_otc_w_smbl_archive_ready_for_full_stack"
        accepted_measurement_repair = True
        failed_reasons = []

    return {
        "experiment_id": EXPERIMENT_ID,
        "status": status,
        "decision": decision,
        "lane": "measurement_repair",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "measurement_readiness_audit_no_strategy_change",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "prediction": PREDICTION,
        "gate1": {
            "baseline_identity": baseline_gate(),
            "baseline_reused_without_strategy_mutation": True,
        },
        "gate2": {
            "required_fields_for_future_otc_alpha": REQUIRED_OTC_FIELDS,
            "entry_date_target_price_check": "not_applicable_no_trade_rows_created",
            "runtime_dependencies_present": local_otc_ready,
            "reason": (
                "Future full-stack alpha requires a PIT weekly OTC archive. This "
                "runner found the source absent locally, so no signal rows were built."
            ),
        },
        "gate3": {
            "signals_generated": 0,
            "signals_survived": 0,
            "survival_rate": None,
            "reason": "blocked before signal generation; no extra filter added",
        },
        "gate4": {
            "ran": False,
            "accepted_measurement_repair": accepted_measurement_repair,
            "accepted_alpha": False,
            "expected_value_score_delta": 0.0,
            "pnl_delta": 0.0,
            "failed_reasons": failed_reasons,
        },
        "source_audit": {
            "ats_manifest": {
                "exists": ATS_MANIFEST.exists(),
                "path": repo_rel(ATS_MANIFEST),
                "sha256": sha256(ATS_MANIFEST),
                "summary": ats_manifest if isinstance(ats_manifest, dict) else {},
            },
            "ats_rows": {
                "exists": ATS_ROWS.exists(),
                "path": repo_rel(ATS_ROWS),
                "sha256": sha256(ATS_ROWS),
                "ats_w_smbl_summary": ats_summary,
                "otc_w_smbl_rows_inside_ats_archive": ats_otc_accidental,
            },
            "otc_manifest": {
                "exists": OTC_MANIFEST.exists(),
                "path": repo_rel(OTC_MANIFEST),
                "sha256": sha256(OTC_MANIFEST),
                "summary": otc_manifest if isinstance(otc_manifest, dict) else {},
            },
            "otc_rows": {
                "exists": OTC_ROWS.exists(),
                "path": repo_rel(OTC_ROWS),
                "sha256": sha256(OTC_ROWS),
                "otc_w_smbl_summary": otc_summary,
            },
            "local_otc_candidate_paths": scan_for_local_otc_mentions(),
            "finra_api_probe": api_probe,
        },
        "production_impact": {
            "trade_enabled_changed": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "ranking_sizing_entry_exit_changed": False,
            "llm_boundary_changed": False,
            "default_off_only": True,
            "live_realistic_execution_envelope": (
                "Not evaluated; source is not materialized, so no live or paper "
                "candidate rule exists."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The repo has a useful ATS_W_SMBL weekly cache from exp-20260703-016, "
                "but no local OTC_W_SMBL archive. The direct FINRA weeklySummary "
                "probe failed in this automation environment, so the non-ATS "
                "internalization alpha cannot be credibly backtested yet."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not rerun ATS dark-share threshold/topN/hold/notional retunes, "
                "and do not reserve another OTC readiness audit until the local "
                "OTC_W_SMBL row count, week count, or network/cache access has actually changed."
            ),
            "new_evidence_required": REOPEN_CONDITION,
        },
        "reopen_condition": REOPEN_CONDITION,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "manifest": repo_rel(MANIFEST_JSON),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "related_files": [
            repo_rel(BASELINE_RESULT),
            repo_rel(ATS_MANIFEST),
            repo_rel(ATS_ROWS),
            repo_rel(OTC_MANIFEST),
            repo_rel(OTC_ROWS),
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "ticket_before": ticket,
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": False,
        "updated_at": utc_now(),
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "lane": payload["lane"],
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis": payload["alpha_hypothesis"],
        "change_type": CHANGE_TYPE,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "decision": payload["decision"],
        "prediction": payload["prediction"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "source_audit_summary": {
            "ats_rows": payload["source_audit"]["ats_rows"]["ats_w_smbl_summary"],
            "otc_rows": payload["source_audit"]["otc_rows"]["otc_w_smbl_summary"],
            "api_ok": payload["source_audit"]["finra_api_probe"]["ok"],
            "api_error_type": payload["source_audit"]["finra_api_probe"]["error_type"],
        },
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "reopen_condition": payload["reopen_condition"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "runner": payload["runner"],
        "changed_files": payload["changed_files"],
        "lean_quality_passed": payload["lean_quality_passed"],
        "updated_at": payload["updated_at"],
    }


def build_card(payload: dict[str, Any]) -> str:
    audit = payload["source_audit"]
    probe = audit["finra_api_probe"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} FINRA OTC Weekly Internalization Archive Readiness",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Alpha Hypothesis",
            "",
            payload["alpha_hypothesis"],
            "",
            "## What Ran",
            "",
            f"- Command: `{RUNNER_COMMAND}`",
            "- Strategy behavior changed: no",
            "- Paper/live orders changed: no",
            "",
            "## Source Audit",
            "",
            f"- ATS cache rows: {audit['ats_rows']['ats_w_smbl_summary']['row_count']}",
            f"- OTC rows inside ATS cache: {audit['ats_rows']['otc_w_smbl_rows_inside_ats_archive']['row_count']}",
            f"- Local OTC cache rows: {audit['otc_rows']['otc_w_smbl_summary']['row_count']}",
            f"- FINRA API probe ok: {probe['ok']}",
            f"- FINRA API error: {probe['error_type']} {probe['error']}",
            "",
            "## Gate 4",
            "",
            f"- Ran: {payload['gate4']['ran']}",
            f"- Failed reasons: {', '.join(payload['gate4']['failed_reasons'])}",
            "",
            "## Reopen Condition",
            "",
            payload["reopen_condition"],
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "## Forbidden Near-Neighbor Retry",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        BASELINE_RESULT,
        ATS_MANIFEST,
        ATS_ROWS,
        OTC_MANIFEST,
        OTC_ROWS,
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
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=payload["prediction"],
        result={
            "accepted": payload["status"] == "accepted_measurement_repair",
            "accepted_alpha": False,
            "accepted_measurement_repair": payload["gate4"]["accepted_measurement_repair"],
            "alpha_ready": False,
            "observed_only_lead": False,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
            "reopen_condition": payload["reopen_condition"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": CHANGE_TYPE,
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": "minimal",
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "reopen_condition": payload["reopen_condition"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "novelty": payload["ticket_before"].get("novelty"),
            "claimed_at": payload["ticket_before"].get("claimed_at"),
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    audit = payload["source_audit"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "ats_rows": audit["ats_rows"]["ats_w_smbl_summary"]["row_count"],
                "otc_rows": audit["otc_rows"]["otc_w_smbl_summary"]["row_count"],
                "api_ok": audit["finra_api_probe"]["ok"],
                "api_error_type": audit["finra_api_probe"]["error_type"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
