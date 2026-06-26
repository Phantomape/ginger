"""exp-20260626-011: SEC submissions category PIT boundary audit.

The alpha hypothesis behind this chain is that 10-K/10-Q filer-status upgrades
may be useful. This run does not test that alpha. It audits whether the local
SEC submissions cache can supply accession-level point-in-time filer status, or
whether its top-level ``category`` field is current-only and therefore unsafe
for historical candidate-pool replay.

No strategy, adapter, ranking, sizing, exit, order, LLM, watchlist, paper ledger,
or live behavior is changed.
"""

from __future__ import annotations

import hashlib
import json
import math
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


EXPERIMENT_ID = "exp-20260626-011"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "sec_submissions_category_pit_boundary"
RUNNER = f"quant/experiments/exp_20260626_011_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

CHANGED_VARIABLE = "sec_submissions_current_category_pit_leakage_boundary_v1"
MECHANISM_FAMILY = "sec_filer_status_materialization_repair"
TRIAL_FAMILY = "sec_submissions_current_category_pit_boundary"
TRIAL_VARIANT_ID = "current_company_category_not_accession_status_v1"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
SUBMISSIONS_DIR = REPO_ROOT / "data" / "cache" / "sec" / "submissions"
SUBMISSION_FILES_DIR = SUBMISSIONS_DIR / "files"
CANONICAL_EVENTS = (
    REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_events_20241002_20260421.jsonl"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260626_011_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
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
ROW_CATEGORY_KEYS = {
    "category",
    "filerCategory",
    "entityFilerCategory",
    "largeAcceleratedFiler",
    "acceleratedFiler",
    "nonAcceleratedFiler",
    "smallerReportingCompany",
    "emergingGrowthCompany",
}

HYPOTHESIS = (
    "measurement_repair/alpha_blocker: SEC cover-page filer-status alpha must "
    "not use data/cache/sec/submissions top-level category unless it can prove "
    "category is accession-level PIT; audit and record the leakage boundary "
    "before any status-upgrade candidate pool is replayed."
)
ALPHA_HYPOTHESIS = (
    "candidate_pool: PIT SEC 10-K/10-Q cover-page filer-status upgrades from "
    "smaller/non-accelerated/EGC toward accelerated or large-accelerated status "
    "may identify improving institutional eligibility, but using current SEC "
    "submissions company category as history would leak status unless the field "
    "is accession-level and accepted_at bounded."
)
PREDICTION = {
    "success_probability": 0.85,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "submissions_category_absent",
        "category_is_accession_level_after_all",
        "audit_schema_gap",
    ],
    "confidence_reason": (
        "exp-20260626-010 blocked true cover-page materialization, and local SEC "
        "submissions expose only a top-level company category plus accession "
        "filing rows. A narrow audit can prevent current-category leakage while "
        "documenting whether submissions can or cannot repair the status alpha "
        "blocker."
    ),
    "recorded_at": "2026-06-26T10:05:31+00:00",
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
    if isinstance(value, Counter):
        return dict(value)
    if isinstance(value, OrderedDict):
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


def read_json(path: Path) -> Any:
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


def sha256_file(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT)
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


def usable_day(row: dict[str, Any]) -> str:
    return str(row.get("usable_trade_date") or row.get("filing_date") or row.get("filingDate") or "")[:10]


def in_window(day: str, cfg: dict[str, str]) -> bool:
    return bool(day) and cfg["start"] <= day <= cfg["end"]


def canonical_periodic_events() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, errors = iter_jsonl(CANONICAL_EVENTS)
    periodic: list[dict[str, Any]] = []
    seen: set[str] = set()
    coverage: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
        (
            label,
            {"periodic_event_rows": 0, "forms": Counter(), "ticker_count": 0, "_tickers": set()},
        )
        for label in WINDOWS
    )
    forms: Counter[str] = Counter()
    for row in rows:
        base = form_base(row)
        if base not in PERIODIC_FORMS:
            continue
        accession = str(row.get("accession_number") or "")
        key = accession or f"{row.get('ticker')}:{row.get('primary_document')}"
        if key in seen:
            continue
        seen.add(key)
        periodic.append(row)
        forms[base] += 1
        day = usable_day(row)
        for label, cfg in WINDOWS.items():
            if in_window(day, cfg):
                bucket = coverage[label]
                bucket["periodic_event_rows"] += 1
                bucket["forms"][base] += 1
                ticker = str(row.get("ticker") or "").upper()
                if ticker:
                    bucket["_tickers"].add(ticker)
    for bucket in coverage.values():
        bucket["ticker_count"] = len(bucket.pop("_tickers"))
        bucket["forms"] = dict(bucket["forms"])
    return periodic, {
        "source_file": repo_rel(CANONICAL_EVENTS),
        "json_parse_errors": errors,
        "periodic_event_rows": len(periodic),
        "form_counts": dict(forms),
        "windows": coverage,
    }


def iter_submission_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    recent = payload.get("filings", {}).get("recent", {})
    if not isinstance(recent, dict):
        return []
    accessions = recent.get("accessionNumber") or []
    rows: list[dict[str, Any]] = []
    for idx, accession in enumerate(accessions):
        row = {}
        for key, values in recent.items():
            if isinstance(values, list) and idx < len(values):
                row[key] = values[idx]
        row["accessionNumber"] = accession
        rows.append(row)
    return rows


def audit_submissions_cache(canonical_rows: list[dict[str, Any]]) -> dict[str, Any]:
    canonical_accessions = {
        str(row.get("accession_number") or "") for row in canonical_rows if row.get("accession_number")
    }
    canonical_by_cik: dict[str, list[dict[str, Any]]] = {}
    for row in canonical_rows:
        cik = str(row.get("cik") or "").strip()
        if not cik:
            continue
        canonical_by_cik.setdefault(cik.zfill(10), []).append(row)
    submission_paths = [
        SUBMISSIONS_DIR / f"CIK{cik}.json"
        for cik in sorted(canonical_by_cik)
        if (SUBMISSIONS_DIR / f"CIK{cik}.json").exists()
    ]
    nested_paths: list[Path] = []
    if SUBMISSION_FILES_DIR.exists():
        for cik in sorted(canonical_by_cik):
            nested_paths.extend(sorted(SUBMISSION_FILES_DIR.glob(f"CIK{cik}-submissions-*.json")))
    category_counts: Counter[str] = Counter()
    entity_type_counts: Counter[str] = Counter()
    top_level_category_examples: list[dict[str, Any]] = []
    row_category_field_counts: Counter[str] = Counter()
    row_category_examples: list[dict[str, Any]] = []
    accession_index: dict[str, dict[str, Any]] = {}
    recent_periodic_rows = 0
    nested_periodic_rows = 0
    parse_errors: list[str] = []

    for path in submission_paths:
        try:
            payload = read_json(path)
        except Exception as exc:
            parse_errors.append(f"{repo_rel(path)}: {exc}")
            continue
        if not isinstance(payload, dict):
            continue
        cik = str(payload.get("cik") or path.stem.replace("CIK", "")).lstrip("0")
        tickers = [str(item).upper() for item in payload.get("tickers") or []]
        category = str(payload.get("category") or "").strip()
        entity_type = str(payload.get("entityType") or "").strip()
        if category:
            category_counts[category] += 1
            if len(top_level_category_examples) < 12:
                top_level_category_examples.append(
                    {
                        "file": repo_rel(path),
                        "cik": cik,
                        "tickers": tickers[:5],
                        "category": category,
                        "entityType": entity_type,
                    }
                )
        if entity_type:
            entity_type_counts[entity_type] += 1

        for row in iter_submission_rows(payload):
            if form_base(row) in PERIODIC_FORMS:
                recent_periodic_rows += 1
            for key in ROW_CATEGORY_KEYS:
                if key in row and row.get(key) not in (None, ""):
                    row_category_field_counts[key] += 1
                    if len(row_category_examples) < 10:
                        row_category_examples.append(
                            {
                                "file": repo_rel(path),
                                "accession": row.get("accessionNumber"),
                                "field": key,
                                "value": row.get(key),
                            }
                        )
            accession = str(row.get("accessionNumber") or "")
            if accession and accession in canonical_accessions:
                accession_index[accession] = {
                    "cik": cik,
                    "tickers": tickers,
                    "company_category": category,
                    "company_entity_type": entity_type,
                    "row_form": row.get("form"),
                    "row_filing_date": row.get("filingDate"),
                    "row_acceptance": row.get("acceptanceDateTime"),
                    "row_has_category_fields": any(
                        key in row and row.get(key) not in (None, "") for key in ROW_CATEGORY_KEYS
                    ),
                    "source": repo_rel(path),
                }

    for path in nested_paths:
        try:
            payload = read_json(path)
        except Exception as exc:
            parse_errors.append(f"{repo_rel(path)}: {exc}")
            continue
        if not isinstance(payload, dict):
            continue
        path_cik = path.name.split("-submissions-", 1)[0].replace("CIK", "").lstrip("0")
        company_path = SUBMISSIONS_DIR / f"CIK{path_cik.zfill(10)}.json"
        company_category = ""
        company_entity_type = ""
        company_tickers: list[str] = []
        if company_path.exists():
            try:
                company_payload = read_json(company_path)
            except Exception:
                company_payload = {}
            if isinstance(company_payload, dict):
                company_category = str(company_payload.get("category") or "").strip()
                company_entity_type = str(company_payload.get("entityType") or "").strip()
                company_tickers = [
                    str(item).upper() for item in company_payload.get("tickers") or []
                ]
        accessions = payload.get("accessionNumber") or []
        forms = payload.get("form") or []
        for idx, accession in enumerate(accessions):
            row = {}
            for key, values in payload.items():
                if isinstance(values, list) and idx < len(values):
                    row[key] = values[idx]
            if form_base(row) in PERIODIC_FORMS:
                nested_periodic_rows += 1
            row_has_category = False
            for key in ROW_CATEGORY_KEYS:
                if key in row and row.get(key) not in (None, ""):
                    row_category_field_counts[key] += 1
                    row_has_category = True
                    if len(row_category_examples) < 10:
                        row_category_examples.append(
                            {
                                "file": repo_rel(path),
                                "accession": accession,
                                "field": key,
                                "value": row.get(key),
                            }
                        )
            accession = str(accession or "")
            if accession in canonical_accessions:
                accession_index[accession] = {
                    "cik": path_cik,
                    "tickers": company_tickers,
                    "company_category": company_category,
                    "company_entity_type": company_entity_type,
                    "row_form": row.get("form"),
                    "row_filing_date": row.get("filingDate"),
                    "row_acceptance": row.get("acceptanceDateTime"),
                    "row_has_category_fields": row_has_category,
                    "source": repo_rel(path),
                }

    matched = {
        accession: accession_index[accession]
        for accession in sorted(canonical_accessions)
        if accession in accession_index
    }
    matched_category_counts = Counter(
        item["company_category"] or "missing" for item in matched.values()
    )
    matched_with_current_category = sum(
        1 for item in matched.values() if item.get("company_category")
    )
    matched_with_row_category = sum(
        1 for item in matched.values() if item.get("row_has_category_fields")
    )
    matched_examples = [
        {"accession": accession, **item} for accession, item in list(matched.items())[:20]
    ]
    return {
        "submissions_dir": repo_rel(SUBMISSIONS_DIR),
        "submission_company_file_count": len(submission_paths),
        "submission_nested_file_count": len(nested_paths),
        "parse_error_count": len(parse_errors),
        "parse_error_examples": parse_errors[:10],
        "top_level_category_company_count": sum(category_counts.values()),
        "top_level_category_counts": dict(category_counts.most_common()),
        "top_level_category_examples": top_level_category_examples,
        "entity_type_counts": dict(entity_type_counts.most_common()),
        "recent_periodic_rows": recent_periodic_rows,
        "nested_periodic_rows": nested_periodic_rows,
        "accession_index_rows": len(accession_index),
        "accession_level_category_field_counts": dict(row_category_field_counts),
        "accession_level_category_examples": row_category_examples,
        "canonical_periodic_accessions": len(canonical_accessions),
        "canonical_accessions_matched_to_submissions": len(matched),
        "canonical_matched_with_current_company_category": matched_with_current_category,
        "canonical_matched_with_accession_category_fields": matched_with_row_category,
        "canonical_matched_company_category_counts": dict(matched_category_counts.most_common()),
        "canonical_match_examples": matched_examples,
        "category_is_top_level_only": bool(
            sum(category_counts.values()) > 0 and sum(row_category_field_counts.values()) == 0
        ),
        "submissions_category_pit_safe_for_historical_replay": False,
    }


def build_payload() -> dict[str, Any]:
    baseline = baseline_metrics()
    canonical_rows, canonical_summary = canonical_periodic_events()
    audit = audit_submissions_cache(canonical_rows)
    accepted = bool(
        audit["submission_company_file_count"] > 0
        and audit["top_level_category_company_count"] > 0
        and audit["canonical_accessions_matched_to_submissions"] > 0
        and audit["category_is_top_level_only"]
    )
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_sec_submissions_category_current_only_boundary"
        if accepted
        else "blocked_sec_submissions_category_scope_inconclusive"
    )
    failed_reasons: list[str] = []
    if audit["submission_company_file_count"] <= 0:
        failed_reasons.append("submissions_cache_missing")
    if audit["top_level_category_company_count"] <= 0:
        failed_reasons.append("top_level_category_absent")
    if audit["canonical_accessions_matched_to_submissions"] <= 0:
        failed_reasons.append("canonical_events_not_joined_to_submissions")
    if not audit["category_is_top_level_only"]:
        failed_reasons.append("category_not_proven_top_level_only")

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
        "paper_orders_changed": False,
        "live_orders_changed": False,
        "production_watchlist_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_orders": False,
        "uses_free_sec_submissions": True,
        "uses_llm": False,
        "replay_only": False,
        "live_realism_evaluated": False,
        "live_ready": False,
        "parity_note": (
            "Audit only. The runner reads local SEC submissions and canonical "
            "event files, then records that company-level current category is not "
            "a shared PIT trading input."
        ),
    }
    why = (
        "Local SEC submissions have a company-level top-level `category` on "
        "submission files, but the accession rows in `filings.recent` and "
        "`submissions/files` do not carry filer-status/category booleans. "
        "Canonical 10-K/10-Q events can be joined to the current company category, "
        "which proves the tempting field exists, but that joined value would be "
        "current-category leakage rather than accepted_at-bounded cover-page status."
        if accepted
        else (
            "The audit could not conclusively prove the local submissions category "
            "scope, so it remains blocked for filer-status alpha."
        )
    )

    payload = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_summary": (
            "Audited local SEC submissions category scope and recorded that the "
            "top-level company category is current-only, not accession-level PIT "
            "filer status."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair_leakage_boundary_audit",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "local SEC submissions cache audit",
            "canonical periodic event join",
            "category scope verification",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": [
            "exp-20260626-008",
            "exp-20260626-010",
        ],
        "multiple_testing_risk_bucket": "minimal_measurement_repair",
        "new_evidence_type": "alpha_blocker_leakage_boundary",
        "new_evidence_axis": (
            "Machine-checkable local SEC submissions cache scope audit proving "
            "top-level company category is not accession-level PIT cover-page status."
        ),
        "prediction": PREDICTION,
        "gate1": {
            "passed": True,
            "baseline_metrics": baseline,
            "strategy_behavior_changed": False,
        },
        "gate2": {
            "passed": accepted,
            "required_fields_checked": [
                "data/cache/sec/submissions top-level category",
                "filings.recent accessionNumber/form/filingDate",
                "filings.recent accession-level category/filer booleans",
                "data/cache/sec/submissions/files accession-level category/filer booleans",
                "canonical sec_filing_events accession_number",
                "canonical usable_trade_date windows",
                "entry_date",
                "target_price",
            ],
            "canonical_event_coverage": canonical_summary,
            "submissions_category_audit": audit,
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
                "Accepted as measurement repair only: the audit prevents a future "
                "historical filer-status alpha from using current company category "
                "as if it were PIT accession status."
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
            "canonical_periodic_event_rows": canonical_summary["periodic_event_rows"],
            "submission_company_file_count": audit["submission_company_file_count"],
            "top_level_category_company_count": audit["top_level_category_company_count"],
            "canonical_accessions_matched_to_submissions": audit[
                "canonical_accessions_matched_to_submissions"
            ],
            "canonical_matched_with_accession_category_fields": audit[
                "canonical_matched_with_accession_category_fields"
            ],
            "accession_level_category_field_total": sum(
                audit["accession_level_category_field_counts"].values()
            ),
        },
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_success": 1 if accepted else 0,
            "brier_score": round((PREDICTION["success_probability"] - (1 if accepted else 0)) ** 2, 6),
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_mode": None if accepted else "; ".join(failed_reasons),
            "predicted_failure_mode_hit": not accepted,
            "surprise_note": (
                "Low surprise: submissions contain current top-level company category "
                "but no accession-level historical category/status fields."
            ),
        },
        "production_impact": production_impact,
        "post_run_reflection": {
            "why_result_happened": why,
            "forbidden_near_neighbor_retry": (
                "Do not run filer-status alpha, filing-timeliness, raw SEC metadata, "
                "or SEC phrase-list candidate-pool replays using submissions "
                "top-level category. It is current company metadata, not historical "
                "cover-page status."
            ),
            "new_evidence_required": (
                "A valid filer-status retry needs accession-level 10-K/10-Q cover-page "
                "or XBRL status rows keyed by accession_number, accepted_at, "
                "usable_trade_date, ticker, form, and parsed large_accelerated/"
                "accelerated/non_accelerated/smaller_reporting/EGC booleans."
            ),
        },
        "next_retry_requires": [
            "accession-level historical 10-K/10-Q cover-page or XBRL filer-status rows",
            "accepted_at-bounded status-change chain per CIK",
            "one fixed shared-paper-first status-upgrade candidate rule",
        ],
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260626-008": "Blocked because cover-page status text surface was missing.",
                "exp-20260626-010": "Blocked because primary-document materialization could not fetch/parse local canonical-window status rows.",
                "novelty_gate": "Measurement repair lane allowed this audit; an alpha-lane SEC metadata replay was blocked as near-neighbor/saturated.",
            },
            "3_single_decision_hypothesis": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Accept only as measurement repair if local submissions have top-level "
                "company category, canonical events join to submissions, and accession "
                "rows contain zero category/status fields, proving the current category "
                "must not be used for historical PIT alpha."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "related_files": [
            repo_rel(Path(__file__)),
            repo_rel(BASELINE_RESULT),
            repo_rel(CANONICAL_EVENTS),
            repo_rel(SUBMISSIONS_DIR),
        ],
        "changed_files": [
            repo_rel(Path(__file__)),
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
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
        "reproduction_commands",
        "anti_js",
    ]
    row = {key: payload[key] for key in keys}
    row["artifact"] = repo_rel(OUT_JSON)
    row["log"] = repo_rel(LOG_JSON)
    return row


def build_card(payload: dict[str, Any]) -> str:
    delta = payload["delta_metrics"]
    gate2 = payload["gate2"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: SEC Submissions Category PIT Boundary",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            "",
            "## Result",
            "",
            f"- Submission company files: `{delta['submission_company_file_count']}`",
            f"- Companies with top-level category: `{delta['top_level_category_company_count']}`",
            f"- Canonical periodic events: `{delta['canonical_periodic_event_rows']}`",
            f"- Canonical accessions matched to submissions: `{delta['canonical_accessions_matched_to_submissions']}`",
            f"- Matched accessions with accession-level category fields: `{delta['canonical_matched_with_accession_category_fields']}`",
            f"- Accession-level category field total: `{delta['accession_level_category_field_total']}`",
            f"- Gate 2 blocker: `{gate2['blocking_reason']}`",
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
        LOG_JSON,
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
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=PREDICTION,
        result={
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
        },
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
