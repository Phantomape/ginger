"""exp-20260627-011: SEC periodic cover XBRL document priority repair.

Measurement repair for the SEC 10-K/10-Q filer-status blocker. This run checks
that the filing text materializer now keeps cover-page XBRL/IDEA documents in
the small per-accession fetch budget, without changing any strategy behavior.
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
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for path in (QUANT_DIR, SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from experiment_registry import persist_self_registered_result  # noqa: E402
from sec_filing_text_backfill import candidate_documents  # noqa: E402


EXPERIMENT_ID = "exp-20260627-011"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "sec_periodic_cover_xbrl_doc_priority"
RUNNER = f"quant/experiments/exp_20260627_011_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

CHANGED_VARIABLE = "sec_periodic_cover_xbrl_document_priority_v1"
MECHANISM_FAMILY = "sec_periodic_filer_status_materialization"
TRIAL_FAMILY = "sec_periodic_cover_xbrl_doc_priority"
TRIAL_VARIANT_ID = "current_mu_10q_cover_xbrl_fetch_budget_v1"

BASELINE_RESULT = REPO_ROOT / "data" / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
CURRENT_SEC_TEXT = REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_text_20260626.jsonl"
CURRENT_FEATURE_SUMMARY = REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_features_summary_20260626.json"
MU_CACHE = REPO_ROOT / "data" / "cache" / "sec" / "filing_text" / "0000723125-26-000015.json"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260627_011_{SLUG}.json"
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

HYPOTHESIS = (
    "Alpha blocker: SEC 10-K/10-Q filer-status upgrade alpha remains untestable "
    "while the text materializer lets exhibits crowd out accession-level cover "
    "XBRL/IDEA documents; prioritize cover XBRL text documents so future "
    "daily/replay rows can preserve machine-readable DEI status fields without "
    "changing strategy behavior."
)
ALPHA_HYPOTHESIS = (
    "candidate_pool: point-in-time SEC 10-K/10-Q filer-status upgrades may "
    "identify improving institutional eligibility, but the alpha remains blocked "
    "until cover-page status facts are materialized by accession and accepted_at."
)
PREDICTION = {
    "success_probability": 0.8,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "SEC index names do not expose cover XBRL",
        "inline XML parsing remains insufficient",
        "current cache must be refreshed before status fields appear",
    ],
    "confidence_reason": (
        "Current MU periodic cache has only primary/header/exhibit docs while "
        "its index header references R1 and htm.xml cover artifacts; candidate "
        "selection can be repaired without strategy changes."
    ),
    "recorded_at": "2026-06-27T10:08:28+00:00",
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
        return {str(key): safe(item) for key, item in value.items()}
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


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {}) or {}
    windows = payload.get("windows") or []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "max_drawdown_pct_worst": max((float(row.get("max_drawdown_pct") or 0.0) for row in windows), default=0.0),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / max(generated, 1), 4),
        "windows": windows,
    }


def old_is_text_document(name: str) -> bool:
    lowered = name.lower()
    if not lowered.endswith((".htm", ".html", ".txt")):
        return False
    excluded_tokens = (
        "-index.htm",
        "filingsummary",
        "metalinks",
        "_cal.",
        "_def.",
        "_lab.",
        "_pre.",
        ".xsd",
        ".xml",
    )
    return not any(token in lowered for token in excluded_tokens)


def old_document_priority(name: str, primary_document: str | None) -> tuple[int, str]:
    lowered = name.lower()
    primary = str(primary_document or "").lower()
    score = 0
    if primary and lowered == primary:
        score += 80
    if re.search(r"(ex[-_]?99|exhibit[-_]?99|ex99|ex991|e991|exhibit99)", lowered):
        score += 100
    if "earn" in lowered or "result" in lowered or "release" in lowered:
        score += 30
    if lowered.endswith(".txt"):
        score -= 20
    if "8k" in lowered:
        score += 10
    return (-score, lowered)


def old_candidate_documents(names: list[str], primary_document: str | None, max_documents: int) -> list[str]:
    selected = [name for name in names if old_is_text_document(name)]
    if primary_document and old_is_text_document(primary_document):
        selected.append(primary_document)
    deduped = list(dict.fromkeys(selected))
    deduped.sort(key=lambda name: old_document_priority(name, primary_document))
    return deduped[:max_documents]


def extract_header_document_names(cache_payload: dict[str, Any]) -> list[str]:
    combined_text = str(cache_payload.get("combined_text") or "")
    names = re.findall(r"<FILENAME>\s*([^\s<]+)", combined_text, flags=re.I)
    return list(dict.fromkeys(name.strip() for name in names if name.strip()))


def fetched_document_names(cache_payload: dict[str, Any]) -> list[str]:
    docs = cache_payload.get("documents") or []
    return [
        str(doc.get("name"))
        for doc in docs
        if isinstance(doc, dict) and doc.get("name")
    ]


def build_payload() -> dict[str, Any]:
    baseline = baseline_metrics()
    cache_payload = read_json(MU_CACHE, {}) or {}
    feature_summary = read_json(CURRENT_FEATURE_SUMMARY, {}) or {}
    header_names = extract_header_document_names(cache_payload if isinstance(cache_payload, dict) else {})
    primary_document = str(cache_payload.get("primary_document") or "mu-20260528.htm")
    index_payload = {"directory": {"item": [{"name": name} for name in header_names]}}
    before_selection = old_candidate_documents(header_names, primary_document, max_documents=4)
    after_selection = candidate_documents(index_payload, primary_document=primary_document, max_documents=4)
    fetched_before = fetched_document_names(cache_payload if isinstance(cache_payload, dict) else {})

    cover_docs = ["R1.htm", f"{Path(primary_document).stem}_htm.xml"]
    before_missing_cover = [name for name in cover_docs if name not in before_selection]
    after_cover = [name for name in cover_docs if name in after_selection]
    fetched_missing_cover = [name for name in cover_docs if name not in fetched_before]
    accepted = (
        MU_CACHE.exists()
        and "R1.htm" in header_names
        and cover_docs[1] in header_names
        and set(cover_docs).issubset(set(after_selection))
        and set(cover_docs).isdisjoint(set(before_selection))
    )

    blocker_note = (
        "The current MU 10-Q cache proves the selected accession exposes R1.htm "
        "and the inline htm.xml cover artifact in the SEC header, but the old "
        "four-document selection spent its budget on the primary/header/exhibits. "
        "The patched selector keeps both cover XBRL documents in the first four "
        "documents, creating the missing materialization path for future parsed "
        "DEI status fields."
    )
    if not accepted:
        blocker_note = (
            "The current local cache did not provide enough evidence that the "
            "patched selector keeps cover XBRL documents ahead of exhibits."
        )

    payload = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "lane": LANE,
        "owner": OWNER,
        "status": "accepted" if accepted else "rejected",
        "decision": (
            "accepted_measurement_repair_sec_periodic_cover_xbrl_doc_priority"
            if accepted
            else "rejected_measurement_repair_sec_periodic_cover_xbrl_doc_priority"
        ),
        "accepted": accepted,
        "accepted_alpha": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_summary": (
            "Prioritized SEC periodic cover XBRL/IDEA documents in the filing "
            "text materializer and recorded a network-free MU 10-Q fetch-budget "
            "proof. No strategy behavior changed."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "shared_materializer_document_selection_repair",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "allow inline cover htm.xml as text materialization input",
            "prioritize R1.htm and htm.xml ahead of ordinary exhibits",
            "network-free current MU 10-Q before-after selection proof",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": [
            "exp-20260626-010",
            "exp-20260626-016",
            "exp-20260627-004",
            "exp-20260627-005",
            "exp-20260627-010",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "measurement_repair_current_periodic_sec_row",
        "new_evidence_axis": (
            "Current MU 10-Q cache header exposes cover XBRL files that the old "
            "fetch budget skipped; this repairs materialization, not an alpha scan."
        ),
        "prediction": PREDICTION,
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_prior_near_neighbors": (
                "Novelty gate did not block. Nearest experiments identify the "
                "same filer-status materialization blocker and require raw "
                "iXBRL/DEI cover-page facts before any alpha test."
            ),
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Accept as measurement repair if current MU header names include "
                "R1.htm and htm.xml, the old top-four selection excludes them, "
                "and the patched top-four selection includes them with zero "
                "strategy metric delta."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists(),
            "strategy_behavior_changed": False,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": bool(MU_CACHE.exists() and header_names and primary_document),
            "dependency_fields": [
                "accession_number",
                "primary_document",
                "combined_text header <FILENAME> entries",
                "documents[].name",
            ],
            "minimum_strategy_fields": {
                "entry_date": "not_applicable_no_strategy_signal_or_filter_added",
                "target_price": "not_applicable_no_strategy_signal_or_filter_added",
            },
            "source_cache": repo_rel(MU_CACHE),
            "header_document_count": len(header_names),
            "fetched_document_names": fetched_before,
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
            "cover_docs_excluded_by_old_selection": len(before_missing_cover),
            "cover_docs_included_by_after_selection": len(after_cover),
            "cover_docs_missing_from_current_cache_fetch": len(fetched_missing_cover),
        },
        "selection_audit": {
            "primary_document": primary_document,
            "cover_docs_required": cover_docs,
            "header_names_contain_cover_docs": {name: name in header_names for name in cover_docs},
            "current_cache_fetched_documents": fetched_before,
            "current_cache_missing_cover_docs": fetched_missing_cover,
            "old_top4_selection": before_selection,
            "old_top4_missing_cover_docs": before_missing_cover,
            "patched_top4_selection": after_selection,
            "patched_top4_cover_docs": after_cover,
            "patched_top4_excluded_linkbases": [
                name
                for name in ("mu-20260528_cal.xml", "mu-20260528_def.xml", "mu-20260528_lab.xml", "mu-20260528_pre.xml")
                if name not in after_selection
            ],
        },
        "current_surface_context": {
            "sec_text_file": repo_rel(CURRENT_SEC_TEXT),
            "sec_feature_summary": repo_rel(CURRENT_FEATURE_SUMMARY),
            "feature_rows_written": feature_summary.get("rows_written"),
            "rows_with_same_accession_facts": feature_summary.get("rows_with_same_accession_facts"),
            "field_counts": feature_summary.get("field_counts"),
        },
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_success": 1 if accepted else 0,
            "brier_score": round((PREDICTION["success_probability"] - (1 if accepted else 0)) ** 2, 6),
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_mode": None if accepted else "cover_xbrl_priority_not_proven",
            "surprise_note": blocker_note,
        },
        "production_impact": {
            "trade_enabled_changed": False,
            "orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "daily_snapshot_changed": True,
            "daily_snapshot_impact": "Only future SEC filing text document fetch composition changes.",
            "live_ready": False,
            "reason": (
                "This preserves cover XBRL documents for future parsing; no "
                "shared alpha helper or live trading decision consumes it yet."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": blocker_note,
            "forbidden_near_neighbor_retry": (
                "Do not run a filer-status alpha or same-row phrase retune from "
                "this repair. It only makes future cover XBRL/status "
                "materialization possible."
            ),
            "new_evidence_required": (
                "Refresh or backfill SEC periodic text after this selector repair, "
                "parse R1/inline htm.xml DEI status facts by accession and "
                "accepted_at, then build one shared default-off status-transition "
                "helper before any alpha replay."
            ),
        },
        "next_retry_requires": [
            "refreshed daily or historical 10-K/10-Q cache rows containing R1.htm or htm.xml text",
            "parsed DEI filer-status booleans keyed by accession_number and accepted_at",
            "one shared default-off status-transition helper",
        ],
        "related_files": [
            repo_rel(BASELINE_RESULT),
            repo_rel(CURRENT_SEC_TEXT),
            repo_rel(CURRENT_FEATURE_SUMMARY),
            repo_rel(MU_CACHE),
            "quant/sec_filing_text_backfill.py",
            "quant/test_sec_filing_text_backfill.py",
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
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "allowed_write_scope": [
            "quant/sec_filing_text_backfill.py",
            "quant/test_sec_filing_text_backfill.py",
            RUNNER,
            f"data/experiments/{EXPERIMENT_ID}/",
            f"experiments/logs/{EXPERIMENT_ID}.json",
            f"experiments/cards/{EXPERIMENT_ID}.md",
            f"experiments/manifests/{EXPERIMENT_ID}.json",
            f"experiments/tickets/{EXPERIMENT_ID}.json",
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
    return payload


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
        "pre_run_questions",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "selection_audit",
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
    audit = payload["selection_audit"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: SEC Periodic Cover XBRL Doc Priority",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            "",
            "## Selection Audit",
            "",
            f"- Old top 4: `{audit['old_top4_selection']}`",
            f"- Patched top 4: `{audit['patched_top4_selection']}`",
            f"- Required cover docs: `{audit['cover_docs_required']}`",
            f"- Current cache missing cover docs: `{audit['current_cache_missing_cover_docs']}`",
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
        CURRENT_SEC_TEXT,
        CURRENT_FEATURE_SUMMARY,
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
        "log_row_sha256": hashlib.sha256(json.dumps(safe(log_row), sort_keys=True).encode("utf-8")).hexdigest(),
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
        "selection_audit": payload["selection_audit"],
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
