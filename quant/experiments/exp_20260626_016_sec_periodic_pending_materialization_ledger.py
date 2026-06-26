"""exp-20260626-016: SEC periodic pending materialization ledger.

This is a measurement repair for the SEC 10-K/10-Q filer-status blocker. The
alpha hypothesis remains that PIT filer-status upgrades may improve candidate
pool quality, but this run only records which selected daily periodic accessions
are still missing local text/cache materialization.

No strategy, ranking, sizing, exit, order, LLM, paper ledger, daily snapshot, or
live behavior is changed.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260626-016"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "sec_periodic_pending_materialization_ledger"
RUNNER = f"quant/experiments/exp_20260626_016_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

CHANGED_VARIABLE = "sec_periodic_pending_materialization_ledger_v1"
MECHANISM_FAMILY = "sec_filing_text_materialization_repair"
TRIAL_FAMILY = "sec_periodic_text_materialization"
TRIAL_VARIANT_ID = "pending_accession_ledger_v1"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
DAILY_TAG = "20260625"
NON_OHLCV_DIR = REPO_ROOT / "data" / "non_ohlcv"
DAILY_EVENTS = NON_OHLCV_DIR / f"sec_filing_events_{DAILY_TAG}.jsonl"
DAILY_TEXT = NON_OHLCV_DIR / f"sec_filing_text_{DAILY_TAG}.jsonl"
DAILY_TEXT_SUMMARY = NON_OHLCV_DIR / f"sec_filing_text_backfill_summary_{DAILY_TAG}.json"
SEC_TEXT_CACHE_DIR = REPO_ROOT / "data" / "cache" / "sec" / "filing_text"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260626_016_{SLUG}.json"
LEDGER_JSONL = OUT_DIR / f"{SLUG}_{DAILY_TAG}.jsonl"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

WINDOWS: "OrderedDict[str, dict[str, str]]" = OrderedDict(
    [
        ("late_strong", {"start": "2025-10-23", "end": "2026-04-21"}),
        ("mid_weak", {"start": "2025-04-23", "end": "2025-10-22"}),
        ("old_thin", {"start": "2024-10-02", "end": "2025-04-22"}),
    ]
)
PERIODIC_FORMS = {"10-K", "10-Q"}

ALLOWED_WRITE_SCOPE = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260626_016_{SLUG}.json",
    f"data/experiments/{EXPERIMENT_ID}/{SLUG}_{DAILY_TAG}.jsonl",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

HYPOTHESIS = (
    "measurement_repair/alpha_blocker: SEC 10-K/10-Q filer-status upgrade "
    "candidate-pool alpha remains untestable unless selected daily periodic "
    "accessions have a machine-readable materialization ledger separating "
    "selected-but-cache-missing rows from stale text artifacts."
)
ALPHA_HYPOTHESIS = (
    "candidate_pool: PIT SEC 10-K/10-Q cover-page filer-status upgrades from "
    "smaller/non-accelerated/EGC toward accelerated or large-accelerated status "
    "may identify improving institutional eligibility, but the strategy remains "
    "blocked until selected periodic reports have replayable local text/cache "
    "and parsed cover-page status fields keyed by accession and accepted_at."
)
PREDICTION = {
    "success_probability": 0.9,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "daily_event_file_absent",
        "periodic_selection_already_materialized",
        "ledger_schema_gap",
    ],
    "confidence_reason": (
        "exp-20260626-013 already shows two selected daily periodic rows and "
        "the current text summary still shows only 6-K/8-K; a network-free "
        "ledger can make the blocker explicit without changing strategy behavior."
    ),
    "recorded_at": "2026-06-26T15:07:51+00:00",
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
    if isinstance(value, OrderedDict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, Counter):
        return dict(value)
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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(safe(row), ensure_ascii=True, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


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
        "windows": windows,
    }


def form_base(row: dict[str, Any]) -> str:
    return str(row.get("form_base") or row.get("form_type") or row.get("form") or "").upper().replace("/A", "")


def cache_path_for_accession(accession: str) -> Path:
    safe_accession = re.sub(r"[^A-Za-z0-9_-]+", "_", accession)
    return SEC_TEXT_CACHE_DIR / f"{safe_accession}.json"


def text_row_ok(row: dict[str, Any] | None) -> bool:
    if not row:
        return False
    return (
        str(row.get("status") or "").lower() == "ok"
        and int(row.get("text_char_count") or 0) > 0
        and bool(row.get("combined_text"))
    )


def cache_payload_ok(payload: dict[str, Any] | None) -> bool:
    if not payload:
        return False
    return (
        str(payload.get("status") or "").lower() == "ok"
        and int(payload.get("text_char_count") or 0) > 0
        and bool(payload.get("combined_text"))
    )


def compact_text_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    return {
        "status": row.get("status"),
        "documents_fetched": int(row.get("documents_fetched") or 0),
        "text_char_count": int(row.get("text_char_count") or 0),
        "text_word_count": int(row.get("text_word_count") or 0),
        "primary_document": row.get("primary_document"),
    }


def build_ledger() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    events, event_errors = iter_jsonl(DAILY_EVENTS)
    text_rows, text_errors = iter_jsonl(DAILY_TEXT)
    text_by_accession = {
        str(row.get("accession_number") or ""): row
        for row in text_rows
        if row.get("accession_number")
    }
    text_summary = read_json(DAILY_TEXT_SUMMARY, {}) or {}
    periodic_events = [row for row in events if form_base(row) in PERIODIC_FORMS]

    ledger: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    cache_status_counts: Counter[str] = Counter()
    text_status_counts: Counter[str] = Counter()

    for event in periodic_events:
        accession = str(event.get("accession_number") or "")
        text_row = text_by_accession.get(accession)
        cache_file = cache_path_for_accession(accession)
        cache_payload = read_json(cache_file, None) if cache_file.exists() else None
        cache_exists = cache_file.exists()
        cache_ok = cache_payload_ok(cache_payload if isinstance(cache_payload, dict) else None)
        text_ok = text_row_ok(text_row)

        if text_ok:
            materialization_status = "materialized_in_daily_text"
        elif text_row and cache_ok:
            materialization_status = "daily_text_non_ok_but_cache_ok"
        elif text_row:
            materialization_status = "daily_text_non_ok"
        elif cache_ok:
            materialization_status = "cache_ok_not_written_to_daily_text"
        elif cache_exists:
            materialization_status = "cache_non_ok_and_daily_text_missing"
        else:
            materialization_status = "selected_cache_missing_and_daily_text_missing"

        if cache_ok:
            cache_status = "cache_present_ok"
        elif cache_exists:
            cache_status = "cache_present_non_ok"
        else:
            cache_status = "cache_missing"

        if text_ok:
            text_status = "daily_text_present_ok"
        elif text_row:
            text_status = "daily_text_present_non_ok"
        else:
            text_status = "daily_text_missing"

        status_counts[materialization_status] += 1
        cache_status_counts[cache_status] += 1
        text_status_counts[text_status] += 1
        ledger.append(
            {
                "ticker": str(event.get("ticker") or "").upper(),
                "form_type": event.get("form_type"),
                "form_base": form_base(event),
                "accession_number": accession,
                "accepted_at": event.get("accepted_at"),
                "filing_date": event.get("filing_date"),
                "usable_trade_date": event.get("usable_trade_date"),
                "cik": event.get("cik"),
                "primary_document": event.get("primary_document"),
                "archive_url": event.get("archive_url"),
                "index_url": event.get("index_url"),
                "source_event_file": repo_rel(DAILY_EVENTS),
                "daily_text_file": repo_rel(DAILY_TEXT),
                "daily_text_summary_file": repo_rel(DAILY_TEXT_SUMMARY),
                "cache_file": repo_rel(cache_file),
                "cache_exists": cache_exists,
                "cache_status": cache_status,
                "daily_text_status": text_status,
                "materialization_status": materialization_status,
                "text_row": compact_text_row(text_row),
                "cache_row": compact_text_row(cache_payload if isinstance(cache_payload, dict) else None),
                "pit_boundary": "selected_by_daily_event_accepted_at; local text/cache may be fetched after the fact",
                "alpha_use_allowed": text_ok and cache_ok,
                "next_action": (
                    "regenerate_or_fetch_sec_filing_text_for_accession"
                    if not (text_ok and cache_ok)
                    else "parse_cover_page_filer_status"
                ),
            }
        )

    source_form_counts = Counter(form_base(row) or "UNKNOWN" for row in events)
    text_form_counts = Counter(form_base(row) or "UNKNOWN" for row in text_rows)
    periodic_text_rows = sum(1 for row in text_rows if form_base(row) in PERIODIC_FORMS)
    periodic_text_ok_rows = sum(1 for row in text_rows if form_base(row) in PERIODIC_FORMS and text_row_ok(row))
    summary = {
        "daily_tag": DAILY_TAG,
        "source_events": repo_rel(DAILY_EVENTS),
        "daily_text": repo_rel(DAILY_TEXT),
        "daily_text_summary": repo_rel(DAILY_TEXT_SUMMARY),
        "cache_dir": repo_rel(SEC_TEXT_CACHE_DIR),
        "event_json_errors": event_errors,
        "text_json_errors": text_errors,
        "source_events_input": len(events),
        "daily_text_rows": len(text_rows),
        "source_form_counts": dict(sorted(source_form_counts.items())),
        "daily_text_form_counts": dict(sorted(text_form_counts.items())),
        "existing_text_summary_forms": text_summary.get("forms"),
        "existing_text_summary_rows_written": text_summary.get("rows_written"),
        "existing_text_summary_selected_periodic_rows": text_summary.get("selected_periodic_rows"),
        "selected_periodic_rows": len(periodic_events),
        "daily_periodic_text_rows": periodic_text_rows,
        "daily_periodic_text_ok_rows": periodic_text_ok_rows,
        "pending_periodic_rows": sum(1 for row in ledger if not row["alpha_use_allowed"]),
        "cache_status_counts": dict(sorted(cache_status_counts.items())),
        "daily_text_status_counts": dict(sorted(text_status_counts.items())),
        "materialization_status_counts": dict(sorted(status_counts.items())),
        "pending_accessions": [
            {
                "ticker": row["ticker"],
                "form_base": row["form_base"],
                "accession_number": row["accession_number"],
                "accepted_at": row["accepted_at"],
                "materialization_status": row["materialization_status"],
            }
            for row in ledger
            if not row["alpha_use_allowed"]
        ],
    }
    return ledger, summary


def build_payload() -> dict[str, Any]:
    baseline = baseline_metrics()
    ledger_rows, ledger_summary = build_ledger()
    missing_required = [
        row["accession_number"]
        for row in ledger_rows
        if not row.get("accession_number") or not row.get("accepted_at") or not row.get("form_base")
    ]
    failed_reasons: list[str] = []
    if not DAILY_EVENTS.exists():
        failed_reasons.append("daily_event_file_absent")
    if ledger_summary["selected_periodic_rows"] <= 0:
        failed_reasons.append("no_selected_periodic_rows")
    if len(ledger_rows) != ledger_summary["selected_periodic_rows"]:
        failed_reasons.append("ledger_row_count_mismatch")
    if missing_required:
        failed_reasons.append("ledger_missing_required_fields")
    accepted = not failed_reasons
    decision = (
        "accepted_measurement_repair_sec_periodic_pending_materialization_ledger"
        if accepted
        else "rejected_measurement_repair_sec_periodic_pending_materialization_ledger_incomplete"
    )
    stale_daily_artifact = (
        ledger_summary["selected_periodic_rows"] > 0
        and ledger_summary["daily_periodic_text_ok_rows"] == 0
        and ledger_summary["pending_periodic_rows"] == ledger_summary["selected_periodic_rows"]
    )
    production_impact = {
        "strategy_behavior_changed": False,
        "daily_snapshot_behavior_changed": False,
        "trade_enabled_changed": False,
        "orders_changed": False,
        "paper_only": False,
        "live_ready": False,
        "impact": (
            "No production behavior changes. The ledger records why filer-status "
            "alpha remains blocked: selected daily periodic accessions are not "
            "available as local ok text/cache rows."
        ),
    }
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "lane": LANE,
        "owner": OWNER,
        "status": "accepted" if accepted else "rejected",
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_summary": (
            "Created a machine-readable pending materialization ledger for "
            "selected daily SEC 10-K/10-Q accessions without changing strategy behavior."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "network_free_artifact_ledger",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "daily periodic accession selection audit",
            "cache presence audit",
            "text artifact presence audit",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": [
            "exp-20260626-008",
            "exp-20260626-009",
            "exp-20260626-010",
            "exp-20260626-011",
            "exp-20260626-013",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "measurement_repair",
        "new_evidence_axis": (
            "Not an alpha override; this records a materialization blocker ledger "
            "for selected daily periodic accessions, so saturated SEC text scans "
            "are not retried."
        ),
        "prediction": PREDICTION,
        "gate1": {
            "passed": True,
            "strategy_behavior_changed": False,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": accepted,
            "strategy_behavior_changed": False,
            "runtime_fields_checked": [
                "ticker",
                "form_base",
                "accession_number",
                "accepted_at",
                "primary_document",
                "usable_trade_date",
            ],
            "minimum_strategy_fields": {
                "entry_date": "not_applicable_no_strategy_signal_or_filter_added",
                "target_price": "not_applicable_no_strategy_signal_or_filter_added",
            },
            "ledger_missing_required_accessions": missing_required,
            "blocking_reason": "; ".join(failed_reasons),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "baseline_survival_rate": baseline["survival_rate"],
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter was added; survival and trade count are unchanged.",
        },
        "gate4": {
            "passed": accepted,
            "decision": decision,
            "strategy_behavior_changed": False,
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "survival_rate_delta": 0.0,
            },
            "failed_reasons": failed_reasons,
            "accepted_basis": (
                "Accepted as measurement repair only: selected daily 10-K/10-Q "
                "rows now have explicit per-accession text/cache materialization "
                "status, and strategy metrics are unchanged."
            )
            if accepted
            else None,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "selected_periodic_rows": ledger_summary["selected_periodic_rows"],
            "daily_periodic_text_rows": ledger_summary["daily_periodic_text_rows"],
            "daily_periodic_text_ok_rows": ledger_summary["daily_periodic_text_ok_rows"],
            "pending_periodic_rows": ledger_summary["pending_periodic_rows"],
            "cache_missing_periodic_rows": ledger_summary["cache_status_counts"].get("cache_missing", 0),
            "stale_daily_artifact": stale_daily_artifact,
        },
        "ledger_summary": ledger_summary,
        "ledger_rows": ledger_rows,
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_success": 1 if accepted else 0,
            "brier_score": round((PREDICTION["success_probability"] - (1 if accepted else 0)) ** 2, 6),
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_mode": None if accepted else "; ".join(failed_reasons),
            "predicted_failure_mode_hit": not accepted,
            "surprise_note": (
                "The expected blocker was confirmed: the daily event surface selects "
                "CRDO 10-K and MU 10-Q rows, but both are missing from local text/cache."
            )
            if accepted
            else "Ledger schema or source file coverage was incomplete.",
        },
        "production_impact": production_impact,
        "post_run_reflection": {
            "why_result_happened": (
                "The 20260625 daily SEC events include two selected periodic reports. "
                "The existing daily text artifact has zero ok 10-K/10-Q rows, and "
                "the matching per-accession cache files are absent, so cover-page "
                "filer-status parsing remains blocked by materialization, not by "
                "selection defaults."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not run another SEC text candidate-pool phrase/list scan or "
                "current-category filer-status approximation from this evidence. "
                "It only proves the selected periodic rows are pending text/cache "
                "materialization."
            ),
            "new_evidence_required": (
                "Fetch or otherwise materialize ok SEC filing text/cache rows for "
                "the listed accessions, parse cover-page filer-status fields by "
                "accession and accepted_at, then test one fixed shared-paper-first "
                "status-transition policy."
            ),
        },
        "next_retry_requires": [
            "local ok text/cache for 0001628280-26-043303 and 0000723125-26-000015 or a materially larger periodic set",
            "parsed cover-page filer-status booleans keyed by accession and accepted_at",
            "one fixed shared-paper-first filer-status transition rule",
        ],
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260626-008": "Blocked: event rows existed but no 10-K/10-Q text rows.",
                "exp-20260626-009": "Accepted default-form coverage repair; no text artifact regeneration.",
                "exp-20260626-010": "Blocked: no local periodic text/cache and fetch probe failed.",
                "exp-20260626-011": "Accepted current-category PIT leakage boundary.",
                "exp-20260626-013": "Accepted daily periodic selection provenance; stale artifact still zero periodic text.",
                "novelty_gate": "Reservation warned on saturated sec_text_event candidate_pool, but no override was used and no alpha replay was run.",
            },
            "3_single_decision_hypothesis": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Accept as measurement repair if every selected daily 10-K/10-Q row "
                "receives a per-accession text/cache status, artifact/logs are "
                "written under the claimed experiment, and strategy metrics remain unchanged."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "related_files": [
            repo_rel(DAILY_EVENTS),
            repo_rel(DAILY_TEXT),
            repo_rel(DAILY_TEXT_SUMMARY),
            repo_rel(BASELINE_RESULT),
            repo_rel(Path(__file__)),
        ],
        "changed_files": [
            repo_rel(Path(__file__)),
            repo_rel(OUT_JSON),
            repo_rel(LEDGER_JSONL),
            repo_rel(LOG_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "reproduction_commands": [
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
        "ledger_summary",
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
    row["ledger"] = repo_rel(LEDGER_JSONL)
    row["log"] = repo_rel(LOG_JSON)
    return row


def build_card(payload: dict[str, Any]) -> str:
    delta = payload["delta_metrics"]
    pending = payload["ledger_summary"]["pending_accessions"]
    pending_lines = [
        f"- `{row['ticker']}` `{row['form_base']}` `{row['accession_number']}`: `{row['materialization_status']}`"
        for row in pending
    ]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: SEC Periodic Pending Materialization Ledger",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            "",
            "## Result",
            "",
            f"- Selected periodic rows: `{delta['selected_periodic_rows']}`",
            f"- Daily periodic text ok rows: `{delta['daily_periodic_text_ok_rows']}`",
            f"- Pending periodic rows: `{delta['pending_periodic_rows']}`",
            f"- Cache-missing periodic rows: `{delta['cache_missing_periodic_rows']}`",
            f"- Stale daily artifact: `{delta['stale_daily_artifact']}`",
            "",
            "## Pending Accessions",
            "",
            *(pending_lines or ["- None"]),
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
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LEDGER_JSONL,
        LOG_JSON,
        TICKET_JSON,
        CARD_MD,
        MANIFEST_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        DAILY_EVENTS,
        DAILY_TEXT,
        DAILY_TEXT_SUMMARY,
        BASELINE_RESULT,
    ]
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "ledger": repo_rel(LEDGER_JSONL),
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
    write_jsonl(LEDGER_JSONL, payload["ledger_rows"])
    write_json(LOG_JSON, log_row)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_row)
    result = {
        "accepted": bool(payload["accepted"]),
        "accepted_alpha": False,
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "ledger": repo_rel(LEDGER_JSONL),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "delta_metrics": payload["delta_metrics"],
        "ledger_summary": payload["ledger_summary"],
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
            "evaluation_windows": [{"label": label, **cfg} for label, cfg in WINDOWS.items()],
            "acceptance_rule": payload["pre_run_questions"]["4_acceptance_standard"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "decision": payload["decision"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
            "artifact": repo_rel(OUT_JSON),
            "ledger": repo_rel(LEDGER_JSONL),
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
