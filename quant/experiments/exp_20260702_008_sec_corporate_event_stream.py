"""exp-20260702-008: SEC corporate event stream from EDGAR quarterly form indexes.

Measurement repair / alpha-enabling data source only. The per-CIK submissions
pipeline structurally cannot discover S-1/F-1 IPO registrations or 425 merger
communications filed by entities outside the tracked universe. This runner
audits the newly ingested `data/non_ohlcv/sec_corporate_event_stream` surface
(built by `quant/sec_corporate_event_stream.py`) across the three canonical
windows plus the current forward stretch, and self-registers the result. It
changes no trading behavior; rows are observation evidence for a later,
separately gated entity->listed-peer propagation alpha experiment
(docs/alpha_next_direction_20260701.md, direction 0, layer L1).
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from data_paths import atomic_write_json, atomic_write_text  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402

EXPERIMENT_ID = "exp-20260702-008"
OWNER = "daniel-agent"
SLUG = "sec_corporate_event_stream"
RUNNER = f"quant/experiments/exp_20260702_008_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

SURFACE_DIR = REPO_ROOT / "data" / "non_ohlcv" / "sec_corporate_event_stream"
ROWS_JSONL = SURFACE_DIR / "rows.jsonl"
MANIFEST_SURFACE = SURFACE_DIR / "manifest.json"
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260702_008_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

WINDOWS = [
    ("old_thin", "2024-10-02", "2025-04-22"),
    ("mid_weak", "2025-04-23", "2025-10-22"),
    ("late_strong", "2025-10-23", "2026-04-21"),
    ("current_forward", "2026-04-22", "2026-12-31"),
]

CHANGED_FILES = [
    "quant/sec_corporate_event_stream.py",
    "quant/test_sec_corporate_event_stream.py",
    f"quant/experiments/exp_20260702_008_{SLUG}.py",
    "data/non_ohlcv/sec_corporate_event_stream/rows.jsonl",
    "data/non_ohlcv/sec_corporate_event_stream/manifest.json",
    f"data/experiments/{EXPERIMENT_ID}/exp_20260702_008_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    "docs/alpha_next_direction_20260701.md",
]

REPRO_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B quant\\sec_corporate_event_stream.py "
    "--start 2024-10-02 --end 2026-07-02 "
    '--user-agent "ginger-research phantomape93@gmail.com"',
    ".\\.venv\\Scripts\\python.exe -B -m pytest "
    "quant\\test_sec_corporate_event_stream.py -q",
    RUNNER_COMMAND,
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_rows() -> list[dict[str, Any]]:
    rows = []
    with ROWS_JSONL.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def audit_surface(rows: list[dict[str, Any]]) -> dict[str, Any]:
    required = {
        "accession",
        "form_type",
        "event_class",
        "is_amendment",
        "filed_date",
        "cik",
        "company_name",
        "ticker_status",
        "source_index_file",
    }
    missing_fields = sorted(
        {field for row in rows for field in required - set(row)}
    )
    # (accession, form_type, cik): one accession legitimately appears under
    # several CIKs (425 acquirer + target), so cik is part of row identity.
    keys = [(r.get("accession"), r.get("form_type"), r.get("cik")) for r in rows]
    duplicate_keys = len(keys) - len(set(keys))
    windows = {}
    for name, start, end in WINDOWS:
        sub = [r for r in rows if start <= r["filed_date"] <= end]
        windows[name] = {
            "start": start,
            "end": end,
            "rows": len(sub),
            "fresh_ipo_registrations": sum(
                1
                for r in sub
                if r["event_class"] == "ipo_registration" and not r["is_amendment"]
            ),
            "ipo_amendments": sum(
                1
                for r in sub
                if r["event_class"] == "ipo_registration" and r["is_amendment"]
            ),
            "merger_communications": sum(
                1 for r in sub if r["event_class"] == "merger_communication"
            ),
            "resolved_ticker_rows": sum(
                1 for r in sub if r["ticker_status"] == "resolved"
            ),
        }
    return {
        "total_rows": len(rows),
        "form_counts": dict(Counter(r["form_type"] for r in rows)),
        "event_class_counts": dict(Counter(r["event_class"] for r in rows)),
        "resolved_ticker_rows": sum(
            1 for r in rows if r["ticker_status"] == "resolved"
        ),
        "unresolved_ticker_rows": sum(
            1 for r in rows if r["ticker_status"] == "unresolved"
        ),
        "unique_ciks": len({r["cik"] for r in rows}),
        "missing_required_fields": missing_fields,
        "duplicate_accession_form_keys": duplicate_keys,
        "filed_date_min": min(r["filed_date"] for r in rows),
        "filed_date_max": max(r["filed_date"] for r in rows),
        "windows": windows,
    }


def evaluate_gates(audit: dict[str, Any]) -> dict[str, Any]:
    canonical = ["old_thin", "mid_weak", "late_strong"]
    failed: list[str] = []
    if audit["missing_required_fields"]:
        failed.append("missing_required_fields")
    if audit["duplicate_accession_form_keys"]:
        failed.append("duplicate_rows")
    for name in canonical:
        window = audit["windows"][name]
        if window["rows"] <= 0:
            failed.append(f"window_empty_{name}")
        if window["fresh_ipo_registrations"] <= 0:
            failed.append(f"no_fresh_ipo_rows_{name}")
    manifest = json.loads(MANIFEST_SURFACE.read_text(encoding="utf-8"))
    incomplete = [
        key
        for key, value in (manifest.get("quarter_status") or {}).items()
        if value.get("status") not in {"ingested"}
    ]
    if incomplete:
        failed.append("quarters_not_ingested:" + ",".join(incomplete))
    return {"passed": not failed, "failed_reasons": failed}


def build_payload(audit: dict[str, Any], gates: dict[str, Any]) -> dict[str, Any]:
    accepted = gates["passed"]
    decision = (
        "accepted_measurement_repair_sec_corporate_event_stream_backfill"
        if accepted
        else "blocked_sec_corporate_event_stream_backfill_incomplete"
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": "measurement_repair",
        "status": "accepted_measurement_repair" if accepted else "blocked",
        "decision": decision,
        "accepted": accepted,
        "hypothesis": (
            "EDGAR daily/quarterly form-index enumeration of S-1/F-1 (IPO "
            "registration) and 425 (merger communication) filings is a "
            "production-visible PIT corporate-event stream the per-CIK "
            "submissions pipeline cannot discover, and it can be materialized "
            "across all three canonical windows plus the current forward "
            "stretch without changing trading behavior."
        ),
        "alpha_hypothesis": (
            "Later, separately gated: events on non-tradable primary entities "
            "(fresh IPO registrations, merger communications) propagate to "
            "related listed tickers via an entity->exposure map "
            "(docs/alpha_next_direction_20260701.md direction 0)."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "shared_module_plus_append_only_surface",
        "mechanism_family": "production_visible_sec_corporate_event_stream",
        "trial_family": "sec_daily_form_index_s1_f1_425_ingestion",
        "trial_variant_id": EXPERIMENT_ID,
        "single_causal_variable": (
            "sec_corporate_event_stream_daily_form_index_ingestion_v1"
        ),
        "changed_variable": "new_non_ohlcv_surface_sec_corporate_event_stream",
        "causal_components": [
            "quarterly_full_index_fetch_with_backoff",
            "right_anchored_idx_row_parser",
            "predeclared_form_set_s1_f1_425",
            "append_only_accession_dedup",
            "cik_ticker_resolution_status",
        ],
        "nearby_prior_experiments": [
            "exp-20260618-016",
            "exp-20260620-018",
            "exp-20260630-002",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "new_data_source_daily_form_index_enumeration",
        "new_evidence_axis": (
            "form-type-first EDGAR index enumeration discovers filers outside "
            "any tracked universe; prior SEC surfaces were CIK-first"
        ),
        "audit": audit,
        "gate1": {
            "note": "measurement repair; canonical backtest baseline unchanged",
        },
        "gate2": {
            "required_fields_present": not audit["missing_required_fields"],
            "missing_fields": audit["missing_required_fields"],
        },
        "gate3": {
            "note": "no signal filtering changed; surface-level counts only",
            "rows_total": audit["total_rows"],
        },
        "gate4": {
            "mode": "measurement_repair_surface_audit",
            "passed": gates["passed"],
            "failed_reasons": gates["failed_reasons"],
        },
        "production_impact": {
            "alters_candidate_ranking": False,
            "alters_exits": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_sizing": False,
            "backtester_adapter_changed": False,
            "daily_collector_changed": False,
            "daily_snapshot_exposed": False,
            "live_orders_changed": False,
            "live_ready": False,
            "paper_orders_changed": False,
            "parity_note": (
                "Read-only non-OHLCV surface. Daily refresh is available via "
                "`sec_corporate_event_stream.py --daily` (one request per run) "
                "but is NOT yet wired into run.py; wiring is deferred to avoid "
                "contending with active run.py claims."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "Quarterly full-index files (8 requests) avoided the daily-index "
                "throttling (HTTP 403) that blocked the per-day approach; the "
                "quarterly idx header is misaligned with data columns, so the "
                "parser is a right-anchored regex rather than fixed-width "
                "slicing."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not widen the form set, re-parse the same indexes with "
                "different filters, or claim alpha from raw event counts. The "
                "next experiment must be the separately gated propagation test "
                "with an entity->exposure map and replacement-value checks."
            ),
            "new_evidence_required": (
                "An entity->listed-ticker exposure map plus next-open forward "
                "replacement-value rows for event-linked tickers, compared "
                "against explicit-ticker control rows and accepted relation "
                "comparators."
            ),
        },
        "related_files": [str(ROWS_JSONL.relative_to(REPO_ROOT)).replace("\\", "/")],
        "changed_files": CHANGED_FILES,
        "reproduction_commands": REPRO_COMMANDS,
        "allowed_write_scope": CHANGED_FILES,
        "lean_quality_passed": True,
    }


def build_card(payload: dict[str, Any]) -> str:
    audit = payload["audit"]
    lines = [
        f"# {EXPERIMENT_ID}: SEC corporate event stream (S-1/F-1/425)",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['decision']}`",
        f"- rows: `{audit['total_rows']}` "
        f"({audit['filed_date_min']} .. {audit['filed_date_max']})",
        f"- event classes: `{audit['event_class_counts']}`",
        f"- ticker resolution: `{audit['resolved_ticker_rows']}` resolved / "
        f"`{audit['unresolved_ticker_rows']}` unresolved (private/pre-IPO "
        "entities are expected to be unresolved)",
        "",
        "## Windows",
        "",
    ]
    for name, window in audit["windows"].items():
        lines.append(
            f"- `{name}` {window['start']}..{window['end']}: rows "
            f"{window['rows']}, fresh IPO {window['fresh_ipo_registrations']}, "
            f"425 {window['merger_communications']}"
        )
    lines += [
        "",
        "## Why",
        "",
        "Form-type-first EDGAR index enumeration discovers filers outside any",
        "tracked universe (the primary-entity side of the propagation",
        "direction in docs/alpha_next_direction_20260701.md). No trading",
        "behavior change; the follow-on propagation alpha test is a separate",
        "gated experiment.",
        "",
        "## Repro",
        "",
    ]
    lines += [f"- `{cmd}`" for cmd in REPRO_COMMANDS]
    return "\n".join(lines) + "\n"


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "owner",
        "lane",
        "status",
        "decision",
        "accepted",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "gate4",
        "production_impact",
        "post_run_reflection",
        "changed_files",
        "reproduction_commands",
    ]
    record = {key: payload[key] for key in keys}
    record["artifact"] = str(OUT_JSON.relative_to(REPO_ROOT)).replace("\\", "/")
    record["audit_summary"] = {
        "total_rows": payload["audit"]["total_rows"],
        "windows": {
            name: window["rows"]
            for name, window in payload["audit"]["windows"].items()
        },
    }
    return record


def upsert_experiment_log(record: dict[str, Any]) -> None:
    lines: list[str] = []
    if EXPERIMENT_LOG.exists():
        for line in EXPERIMENT_LOG.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                lines.append(line)
                continue
            if row.get("experiment_id") != EXPERIMENT_ID:
                lines.append(line)
    lines.append(json.dumps(record, ensure_ascii=False, sort_keys=True))
    atomic_write_text("\n".join(lines) + "\n", EXPERIMENT_LOG)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    tracked = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        ROWS_JSONL,
        MANIFEST_SURFACE,
        LOG_JSON,
        CARD_MD,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": str(OUT_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            str(path.relative_to(REPO_ROOT)).replace("\\", "/"): {
                "exists": path.exists(),
                "sha256": sha256(path),
            }
            for path in tracked
        },
        "updated_at": utc_now(),
    }


def main() -> int:
    if not ROWS_JSONL.exists():
        raise SystemExit("surface missing: run sec_corporate_event_stream.py first")
    rows = load_rows()
    audit = audit_surface(rows)
    gates = evaluate_gates(audit)
    payload = build_payload(audit, gates)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(payload, OUT_JSON)
    log_record = compact_log_record(payload)
    atomic_write_json(log_record, LOG_JSON)
    atomic_write_text(build_card(payload), CARD_MD)
    upsert_experiment_log(log_record)

    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction={
            "success_probability": 0.75,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "main_failure_modes": [
                "daily index coverage gaps or throttling",
                "ticker resolution too sparse to matter later",
                "425 volume dominated by SPAC boilerplate",
            ],
            "confidence_reason": (
                "EDGAR full-index is a stable documented feed; parsing risk "
                "is bounded by fixture tests."
            ),
        },
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "alpha_ready": False,
            "observed_only_lead": False,
            "decision": payload["decision"],
            "artifact": str(OUT_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            "log": str(LOG_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
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
            "new_evidence_axis": payload["new_evidence_axis"],
            "decision": payload["decision"],
            "artifact": str(OUT_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            "log": str(LOG_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            "card_file": str(CARD_MD.relative_to(REPO_ROOT)).replace("\\", "/"),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )
    atomic_write_json(build_manifest(payload), MANIFEST_JSON)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "total_rows": audit["total_rows"],
                "windows": {
                    name: window["rows"]
                    for name, window in audit["windows"].items()
                },
                "failed_reasons": gates["failed_reasons"],
                "artifact": str(OUT_JSON.relative_to(REPO_ROOT)).replace("\\", "/"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
