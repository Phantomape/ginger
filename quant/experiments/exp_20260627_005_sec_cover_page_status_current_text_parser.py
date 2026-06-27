"""exp-20260627-005: SEC cover-page status current text parser probe.

Measurement repair for the SEC 10-K/10-Q filer-status blocker. The alpha
hypothesis is still that point-in-time cover-page filer-status upgrades may
improve candidate-pool quality. This runner only checks whether the current
daily SEC text artifact can produce accession-level machine-readable status
fields without using current company metadata or changing strategy behavior.
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


EXPERIMENT_ID = "exp-20260627-005"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "sec_cover_page_status_current_text_parser"
RUNNER = f"quant/experiments/exp_20260627_005_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

CHANGED_VARIABLE = "sec_cover_page_status_accession_parser_v1"
MECHANISM_FAMILY = "identity_or_measurement_repair"
TRIAL_FAMILY = "sec_cover_page_status_current_text_parser"
TRIAL_VARIANT_ID = "daily_text_20260626_accession_status_probe_v1"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
DAILY_TAG = "20260626"
NON_OHLCV_DIR = REPO_ROOT / "data" / "non_ohlcv"
DAILY_TEXT = NON_OHLCV_DIR / f"sec_filing_text_{DAILY_TAG}.jsonl"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260627_005_{SLUG}.json"
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
    f"data/experiments/{EXPERIMENT_ID}/exp_20260627_005_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

HYPOTHESIS = (
    "SEC 10-K/10-Q cover-page filer-status upgrade alpha is blocked until "
    "daily SEC text exposes accession-level parsed cover-page status booleans; "
    "parse current SEC text rows into a PIT keyed status ledger without "
    "changing strategy behavior."
)
ALPHA_HYPOTHESIS = (
    "candidate_pool: PIT SEC 10-K/10-Q cover-page filer-status upgrades from "
    "smaller/non-accelerated/EGC toward accelerated or large-accelerated status "
    "may identify improving institutional eligibility, but only if accessions "
    "carry replayable accepted_at and parsed status booleans."
)
PREDICTION = {
    "success_probability": 0.75,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "daily_text_missing_periodic_rows",
        "checkbox_glyphs_not_distinguishable_after_text_extraction",
        "no_inline_dei_facts_in_current_text_artifact",
    ],
    "confidence_reason": (
        "exp-20260626-016 showed selected periodic rows were previously missing; "
        "the current 20260626 artifact now contains one 10-Q row, so a "
        "network-free parser can determine whether the blocker moved from "
        "materialization to machine-readable cover-page fact extraction."
    ),
    "recorded_at": "2026-06-27T04:08:33+00:00",
}

STATUS_LABELS: "OrderedDict[str, str]" = OrderedDict(
    [
        ("large_accelerated_filer", "large accelerated filer"),
        ("accelerated_filer", "accelerated filer"),
        ("non_accelerated_filer", "non-accelerated filer"),
        ("smaller_reporting_company", "smaller reporting company"),
        ("emerging_growth_company", "emerging growth company"),
        ("shell_company", "shell company"),
    ]
)

FILER_CATEGORY_PATTERNS = [
    re.compile(r"(?:dei[:_])?EntityFilerCategory[^>]*>\s*([^<]+?)\s*<", re.I),
    re.compile(
        r"['\"]?dei[:_]EntityFilerCategory['\"]?\s*[:=]\s*['\"]"
        r"([^'\"]+?)['\"]",
        re.I,
    ),
]
BOOLEAN_FACT_PATTERNS = {
    "emerging_growth_company": [
        re.compile(r"(?:dei[:_])?EntityEmergingGrowthCompany[^>]*>\s*(true|false|1|0)\s*<", re.I),
        re.compile(
            r"['\"]?dei[:_]EntityEmergingGrowthCompany['\"]?\s*[:=]\s*"
            r"['\"]?(true|false|1|0)['\"]?",
            re.I,
        ),
    ],
    "shell_company": [
        re.compile(r"(?:dei[:_])?EntityShellCompany[^>]*>\s*(true|false|1|0)\s*<", re.I),
        re.compile(
            r"['\"]?dei[:_]EntityShellCompany['\"]?\s*[:=]\s*"
            r"['\"]?(true|false|1|0)['\"]?",
            re.I,
        ),
    ],
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
    value = str(row.get("form_base") or row.get("form_type") or row.get("form") or "")
    return value.upper().replace("/A", "")


def bool_value(raw: str) -> bool | None:
    value = raw.strip().lower()
    if value in {"true", "1"}:
        return True
    if value in {"false", "0"}:
        return False
    return None


def normalize_category(raw: str | None) -> str | None:
    if not raw:
        return None
    value = re.sub(r"\s+", " ", raw.strip().lower())
    value = value.replace("_", " ").replace("-", " ")
    if "large accelerated filer" in value:
        return "large_accelerated_filer"
    if "non accelerated filer" in value:
        return "non_accelerated_filer"
    if "accelerated filer" in value:
        return "accelerated_filer"
    if "smaller reporting company" in value:
        return "smaller_reporting_company"
    if "emerging growth company" in value:
        return "emerging_growth_company"
    return None


def extract_fact_category(text: str) -> str | None:
    for pattern in FILER_CATEGORY_PATTERNS:
        match = pattern.search(text)
        if match:
            return normalize_category(match.group(1))
    return None


def extract_boolean_facts(text: str) -> dict[str, bool]:
    facts: dict[str, bool] = {}
    for field, patterns in BOOLEAN_FACT_PATTERNS.items():
        for pattern in patterns:
            match = pattern.search(text)
            if not match:
                continue
            value = bool_value(match.group(1))
            if value is not None:
                facts[field] = value
                break
    return facts


def mention_counts(text: str) -> dict[str, int]:
    lower = text.lower()
    return {
        key: len(re.findall(re.escape(label), lower))
        for key, label in STATUS_LABELS.items()
    }


def checkbox_boundary(text: str) -> dict[str, Any]:
    lower = text.lower()
    start = lower.find("large accelerated filer")
    end = lower.find("if an emerging growth company", start if start >= 0 else 0)
    if start < 0 or end < 0:
        return {
            "cover_checkbox_region_found": False,
            "distinguishable_checkbox_tokens": False,
            "checked_token_count": 0,
            "unchecked_token_count": 0,
            "mojibake_checkbox_token_count": 0,
            "region_excerpt": None,
        }
    region = text[start:end]
    checked_count = sum(region.count(token) for token in ("\u2612", "\u2611", "\u00fe"))
    unchecked_count = region.count("\u2610")
    mojibake_count = region.count("\u923d")
    return {
        "cover_checkbox_region_found": True,
        "distinguishable_checkbox_tokens": checked_count > 0 or unchecked_count > 0,
        "checked_token_count": checked_count,
        "unchecked_token_count": unchecked_count,
        "mojibake_checkbox_token_count": mojibake_count,
        "region_excerpt": re.sub(r"\s+", " ", region[:500]).strip(),
    }


def status_booleans_from_facts(
    category: str | None,
    boolean_facts: dict[str, bool],
) -> dict[str, bool | None]:
    fields = {key: None for key in STATUS_LABELS}
    if category in {
        "large_accelerated_filer",
        "accelerated_filer",
        "non_accelerated_filer",
        "smaller_reporting_company",
    }:
        for key in (
            "large_accelerated_filer",
            "accelerated_filer",
            "non_accelerated_filer",
            "smaller_reporting_company",
        ):
            fields[key] = key == category
    if category == "emerging_growth_company":
        fields["emerging_growth_company"] = True
    for key, value in boolean_facts.items():
        fields[key] = value
    return fields


def parse_status_row(row: dict[str, Any], source: str) -> dict[str, Any]:
    text = str(row.get("combined_text") or "")
    category = extract_fact_category(text)
    boolean_facts = extract_boolean_facts(text)
    booleans = status_booleans_from_facts(category, boolean_facts)
    mentions = mention_counts(text)
    checkbox = checkbox_boundary(text)
    machine_fields = [key for key, value in booleans.items() if value is not None]
    cover_terms_present = any(mentions.values())

    if machine_fields:
        parse_status = "parsed_machine_readable_dei_fact"
    elif cover_terms_present and checkbox["cover_checkbox_region_found"]:
        parse_status = "blocked_ambiguous_extracted_checkbox_glyphs"
    elif cover_terms_present:
        parse_status = "blocked_cover_terms_without_machine_readable_values"
    else:
        parse_status = "blocked_no_cover_page_status_terms"

    return {
        "source_file": source,
        "ticker": row.get("ticker"),
        "form_type": row.get("form_type") or row.get("form"),
        "form_base": form_base(row),
        "accession_number": row.get("accession_number"),
        "accepted_at": row.get("accepted_at"),
        "usable_trade_date": row.get("usable_trade_date"),
        "primary_document": row.get("primary_document"),
        "text_length": len(text),
        "cover_status_mentions": mentions,
        "cover_terms_present": cover_terms_present,
        "machine_readable_filer_category": category,
        "machine_readable_boolean_facts": boolean_facts,
        "parsed_status_booleans": booleans,
        "machine_readable_status_fields": machine_fields,
        "machine_readable_status_field_count": len(machine_fields),
        "checkbox_diagnostics": checkbox,
        "parse_status": parse_status,
        "usable_for_status_transition_alpha": bool(machine_fields),
    }


def build_summary(rows: list[dict[str, Any]], parse_errors: int) -> dict[str, Any]:
    periodic = [row for row in rows if row["form_base"] in PERIODIC_FORMS]
    machine_rows = [row for row in periodic if row["machine_readable_status_field_count"] > 0]
    ambiguous_rows = [
        row
        for row in periodic
        if row["parse_status"] == "blocked_ambiguous_extracted_checkbox_glyphs"
    ]
    return {
        "daily_text_file": repo_rel(DAILY_TEXT),
        "jsonl_parse_errors": parse_errors,
        "total_text_rows": len(rows),
        "periodic_text_rows": len(periodic),
        "periodic_rows_by_form": dict(Counter(row["form_base"] for row in periodic)),
        "periodic_rows_with_cover_terms": sum(1 for row in periodic if row["cover_terms_present"]),
        "periodic_rows_with_machine_readable_status": len(machine_rows),
        "periodic_rows_with_ambiguous_checkbox_glyphs": len(ambiguous_rows),
        "periodic_status_parse_counts": dict(Counter(row["parse_status"] for row in periodic)),
        "machine_readable_periodic_accessions": [
            row["accession_number"] for row in machine_rows
        ],
        "blocked_periodic_accessions": [
            {
                "ticker": row["ticker"],
                "form_base": row["form_base"],
                "accession_number": row["accession_number"],
                "accepted_at": row["accepted_at"],
                "parse_status": row["parse_status"],
            }
            for row in periodic
            if not row["usable_for_status_transition_alpha"]
        ],
    }


def build_payload() -> dict[str, Any]:
    source_rows, parse_errors = iter_jsonl(DAILY_TEXT)
    status_rows = [
        parse_status_row(row, repo_rel(DAILY_TEXT))
        for row in source_rows
    ]
    summary = build_summary(status_rows, parse_errors)
    baseline = baseline_metrics()
    machine_rows = summary["periodic_rows_with_machine_readable_status"]
    accepted_repair = (
        DAILY_TEXT.exists()
        and summary["periodic_text_rows"] > 0
        and summary["periodic_rows_with_cover_terms"] > 0
    )

    blocker_note = (
        "The current 20260626 SEC text artifact now materializes a periodic "
        "10-Q cover page, but its extracted checkbox glyphs are ambiguous and "
        "the text contains no DEI machine-readable filer-category facts. The "
        "status-transition alpha remains blocked until raw iXBRL/DEI facts or "
        "distinguishable checkbox tokens are preserved by accession."
    )
    if machine_rows:
        blocker_note = (
            "At least one periodic accession produced machine-readable cover-page "
            "status fields; this is sufficient for a next shared default-off "
            "status-transition helper after historical coverage is built."
        )

    status = "accepted" if accepted_repair else "rejected"
    decision = (
        "accepted_measurement_repair_sec_cover_page_status_current_text_parser"
        if accepted_repair
        else "rejected_no_current_periodic_cover_page_status_surface"
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "lane": LANE,
        "status": status,
        "decision": decision,
        "accepted": accepted_repair,
        "accepted_alpha": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_summary": (
            "Added an experiment-scoped accession-level parser/readiness ledger "
            "for current daily SEC cover-page status text. No strategy behavior "
            "or production path changed."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "experiment_scoped_readiness_ledger",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "current daily SEC text materialization audit",
            "accession-level cover-page status parser diagnostics",
            "machine-readable DEI fact versus ambiguous checkbox separation",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": [
            "exp-20260626-008",
            "exp-20260626-010",
            "exp-20260626-011",
            "exp-20260626-013",
            "exp-20260626-016",
            "exp-20260627-004",
        ],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "measurement_repair_current_daily_text",
        "new_evidence_axis": (
            "Current 20260626 daily SEC text now contains a 10-Q cover-page row; "
            "this tests machine-readable accession-level status readiness, not "
            "a same-source alpha retune."
        ),
        "prediction": PREDICTION,
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_prior_near_neighbors": (
                "Novelty gate allowed the run and linked the existing "
                "filer-status blocker chain; this run is measurement repair only."
            ),
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Accept as measurement repair if the runner produces a "
                "replayable accession-level ledger separating machine-readable "
                "status rows from blocked ambiguous checkbox rows; accepted_alpha "
                "must remain false."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists(),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": DAILY_TEXT.exists() and parse_errors == 0,
            "dependency_fields": [
                "ticker",
                "form_type",
                "accession_number",
                "accepted_at",
                "usable_trade_date",
                "primary_document",
                "combined_text",
            ],
            "source_file": repo_rel(DAILY_TEXT),
            "source_exists": DAILY_TEXT.exists(),
            "jsonl_parse_errors": parse_errors,
            "runtime_rows": len(source_rows),
        },
        "gate3": {
            "passed": True,
            "strategy_changed": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No filter was added; survival is unchanged from the accepted-stack baseline.",
        },
        "gate4": {
            "passed": accepted_repair,
            "strategy_changed": False,
            "after_same_as_before": True,
            "accepted_alpha": False,
            "decision_basis": blocker_note,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "max_drawdown_pct_worst_delta": 0.0,
            "trade_count_delta": 0,
            "survival_rate_delta": 0.0,
            "periodic_text_rows": summary["periodic_text_rows"],
            "periodic_rows_with_cover_terms": summary["periodic_rows_with_cover_terms"],
            "periodic_rows_with_machine_readable_status": machine_rows,
            "periodic_rows_with_ambiguous_checkbox_glyphs": summary[
                "periodic_rows_with_ambiguous_checkbox_glyphs"
            ],
        },
        "ledger_summary": summary,
        "status_ledger_rows": status_rows,
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_success": 1 if accepted_repair else 0,
            "brier_score": round((PREDICTION["success_probability"] - (1 if accepted_repair else 0)) ** 2, 4),
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_mode": (
                "checkbox_glyphs_not_distinguishable_after_text_extraction"
                if summary["periodic_rows_with_ambiguous_checkbox_glyphs"]
                else None
            ),
            "surprise_note": blocker_note,
        },
        "production_impact": {
            "trade_enabled_changed": False,
            "orders_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "daily_snapshot_changed": False,
            "shared_helper_changed": False,
            "live_ready": False,
            "reason": (
                "Experiment-scoped measurement ledger only; parsed status fields "
                "are not yet wired into shared daily or historical helpers."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": blocker_note,
            "forbidden_near_neighbor_retry": (
                "Do not run a filer-status alpha rule or retune thresholds from "
                "this row. The current periodic text has cover-page terms but no "
                "trustworthy parsed status booleans."
            ),
            "new_evidence_required": (
                "Preserve raw inline XBRL/DEI cover-page facts or distinguishable "
                "checked/unchecked tokens for historical and daily 10-K/10-Q "
                "accessions, then build one shared default-off status-transition "
                "helper before any alpha test."
            ),
        },
        "next_retry_requires": [
            "raw_ixbrl_or_dei_fact_cache_by_accession",
            "historical_10k_10q_status_rows_by_accepted_at",
            "shared_default_off_status_transition_helper",
        ],
        "related_files": [
            repo_rel(DAILY_TEXT),
            repo_rel(BASELINE_RESULT),
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
            repo_rel(TICKET_JSON),
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
    row["log"] = repo_rel(LOG_JSON)
    return row


def build_card(payload: dict[str, Any]) -> str:
    summary = payload["ledger_summary"]
    blocked = summary["blocked_periodic_accessions"]
    blocked_lines = [
        f"- `{row['ticker']}` `{row['form_base']}` `{row['accession_number']}`: `{row['parse_status']}`"
        for row in blocked
    ]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: SEC Cover-Page Status Current Text Parser",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            "",
            "## Result",
            "",
            f"- Periodic text rows: `{summary['periodic_text_rows']}`",
            f"- Rows with cover terms: `{summary['periodic_rows_with_cover_terms']}`",
            f"- Rows with machine-readable status: `{summary['periodic_rows_with_machine_readable_status']}`",
            f"- Rows with ambiguous checkbox glyphs: `{summary['periodic_rows_with_ambiguous_checkbox_glyphs']}`",
            "",
            "## Blocked Periodic Accessions",
            "",
            *(blocked_lines or ["- None"]),
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
        TICKET_JSON,
        CARD_MD,
        MANIFEST_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        DAILY_TEXT,
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
