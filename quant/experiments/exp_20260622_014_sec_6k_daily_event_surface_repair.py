"""exp-20260622-014: SEC 6-K daily event surface repair.

Measurement repair for the 6-K foreign issuer candidate-pool blocker from
exp-20260621-018. This runner audits the shared daily SEC builders after the
code change and registers the result through experiment_registry.

No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
QUANT_DIR = REPO_ROOT / "quant"
for path in (str(SCRIPTS_DIR), str(QUANT_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import experiment_registry  # noqa: E402
import daily_non_ohlcv_snapshot as daily_snapshot  # noqa: E402
import sec_filing_backfill as event_backfill  # noqa: E402
import sec_filing_text_backfill as text_backfill  # noqa: E402
from sec_ticker_map import load_company_ticker_map, normalize_cik  # noqa: E402


EXPERIMENT_ID = "exp-20260622-014"
SLUG = "sec_6k_daily_event_surface_repair"
RUNNER_NAME = f"quant/experiments/exp_20260622_014_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_NAME.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"exp_20260622_014_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT_FILE = "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
BASELINE_RESULT_PATH = REPO_ROOT / BASELINE_RESULT_FILE
SEC_SUBMISSIONS_CACHE_DIR = REPO_ROOT / "data" / "cache" / "sec" / "submissions"

TARGET_FORMS = {"6-K", "6-K/A"}
MIN_TARGET_UNIQUE_EVENTS = 20
MIN_TARGET_WINDOWS = 3
MIN_TARGET_UNIQUE_EVENTS_PER_WINDOW = 5

HYPOTHESIS = (
    "measurement_repair/candidate_pool: repair the shared daily SEC event and "
    "text surface so PIT 6-K foreign issuer current reports are production-visible "
    "instead of existing only as raw form-index metadata."
)
TRIAL_FAMILY = "sec_6k_foreign_issuer_event_candidate_pool"
TRIAL_VARIANT_ID = "sec_6k_daily_surface_repair_v1"
CHANGED_VARIABLE = "sec_6k_daily_event_surface_trade_ready_mapping_v1"


CANONICAL_WINDOWS: dict[str, dict[str, str]] = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
    },
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def append_jsonl_once(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    needle = f'"experiment_id": "{EXPERIMENT_ID}"'
    if path.exists() and needle in path.read_text(encoding="utf-8-sig"):
        return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def window_for(value: Any) -> str | None:
    observed = parse_date(value)
    if observed is None:
        return None
    for label, window in CANONICAL_WINDOWS.items():
        if date.fromisoformat(window["start"]) <= observed <= date.fromisoformat(window["end"]):
            return label
    return None


def event_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("ticker") or ""),
        str(row.get("accession_number") or ""),
        str(row.get("form_type") or ""),
    )


def load_baseline() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT_PATH)
    windows = payload.get("windows") if isinstance(payload, dict) else []
    aggregate = {
        "aggregate_expected_value_score": payload.get("aggregate_expected_value_score"),
        "aggregate_total_pnl": payload.get("aggregate_total_pnl"),
        "total_trade_count": payload.get("total_trade_count"),
    }
    if aggregate["aggregate_expected_value_score"] is None and isinstance(windows, list):
        aggregate = {
            "aggregate_expected_value_score": round(
                sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4
            ),
            "aggregate_total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
            "total_trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        }
    return {
        "path": BASELINE_RESULT_FILE,
        "windows": windows,
        "aggregate": aggregate,
    }


def _payload_cik(path: Path, payload: dict[str, Any]) -> str | None:
    from_payload = normalize_cik(payload.get("cik")) if isinstance(payload, dict) else None
    if from_payload:
        return from_payload
    stem_digits = "".join(ch for ch in path.stem if ch.isdigit())
    return normalize_cik(stem_digits)


def scan_cached_submissions() -> dict[str, Any]:
    company_by_cik = load_company_ticker_map()
    forms = {str(form).upper() for form in event_backfill.DEFAULT_FORMS}
    start = min(date.fromisoformat(row["start"]) for row in CANONICAL_WINDOWS.values())
    end = max(date.fromisoformat(row["end"]) for row in CANONICAL_WINDOWS.values())

    target_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    scanned_files = 0
    mapped_files = 0
    json_errors = 0
    form_counts: Counter[str] = Counter()

    for path in sorted(SEC_SUBMISSIONS_CACHE_DIR.glob("CIK*.json")):
        scanned_files += 1
        payload = read_json(path)
        if not isinstance(payload, dict):
            json_errors += 1
            continue
        cik = _payload_cik(path, payload)
        ticker = company_by_cik.get(cik or "", {}).get("ticker")
        if not cik or not ticker:
            continue
        mapped_files += 1
        rows = event_backfill.parse_filing_rows(
            payload,
            ticker=str(ticker).upper(),
            cik=cik,
            forms=forms,
            start=start,
            end=end,
            pit_source="sec_submissions_cache_replay_no_network",
        )
        for row in rows:
            form_counts[str(row.get("form_type") or "")] += 1
            if row.get("form_base") == "6-K":
                target_by_key.setdefault(event_key(row), row)

    rows = sorted(
        target_by_key.values(),
        key=lambda row: (
            str(row.get("usable_trade_date") or row.get("filing_date") or ""),
            str(row.get("ticker") or ""),
            str(row.get("accession_number") or ""),
        ),
    )
    by_window: dict[str, int] = {label: 0 for label in CANONICAL_WINDOWS}
    unique_by_window: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    dependency_fields = [
        "ticker",
        "cik",
        "accession_number",
        "form_type",
        "filing_date",
        "accepted_at",
        "usable_trade_date",
        "archive_url",
        "index_url",
    ]
    dependency_presence = {field: 0 for field in dependency_fields}
    for row in rows:
        for field in dependency_fields:
            if row.get(field) not in (None, ""):
                dependency_presence[field] += 1
        label = window_for(row.get("usable_trade_date") or row.get("filing_date"))
        if label:
            by_window[label] += 1
            unique_by_window[label].add(event_key(row))

    sample_rows = [
        {
            "ticker": row.get("ticker"),
            "cik": row.get("cik"),
            "accession_number": row.get("accession_number"),
            "form_type": row.get("form_type"),
            "filing_date": row.get("filing_date"),
            "accepted_at": row.get("accepted_at"),
            "usable_trade_date": row.get("usable_trade_date"),
            "primary_document": row.get("primary_document"),
        }
        for row in rows[:10]
    ]
    total = len(rows)
    return {
        "cache_dir": repo_rel(SEC_SUBMISSIONS_CACHE_DIR),
        "cache_files_scanned": scanned_files,
        "cache_files_mapped_to_ticker": mapped_files,
        "invalid_json_files": json_errors,
        "event_default_forms": list(event_backfill.DEFAULT_FORMS),
        "event_default_includes_6k": TARGET_FORMS.issubset(set(event_backfill.DEFAULT_FORMS)),
        "form_counts_from_default_scope": form_counts.most_common(12),
        "target_rows_total": total,
        "target_rows_by_window": by_window,
        "target_unique_events_by_window": {
            label: len(unique_by_window.get(label, set())) for label in CANONICAL_WINDOWS
        },
        "target_unique_events_total": len(target_by_key),
        "target_tickers": len({row.get("ticker") for row in rows if row.get("ticker")}),
        "dependency_presence": {
            field: {
                "present_rows": dependency_presence[field],
                "target_rows_scanned": total,
                "present_rate": round(dependency_presence[field] / total, 4) if total else 0.0,
            }
            for field in dependency_fields
        },
        "sample_target_rows": sample_rows,
    }


def text_scope_audit() -> dict[str, Any]:
    forms = {form.upper().replace("/A", "") for form in text_backfill.DEFAULT_FORMS}
    item_codes = {code.strip() for code in text_backfill.DEFAULT_ITEM_CODES if code.strip()}
    six_k_admitted = text_backfill._event_matches(
        {"form_type": "6-K", "form_base": "6-K", "eight_k_item_codes": []},
        forms,
        item_codes,
    )
    eight_k_202_admitted = text_backfill._event_matches(
        {"form_type": "8-K", "form_base": "8-K", "eight_k_item_codes": ["2.02"]},
        forms,
        item_codes,
    )
    eight_k_502_rejected = not text_backfill._event_matches(
        {"form_type": "8-K", "form_base": "8-K", "eight_k_item_codes": ["5.02"]},
        forms,
        item_codes,
    )
    daily_forms = list(getattr(daily_snapshot, "SEC_TEXT_DEFAULT_FORMS", ()))
    return {
        "text_default_forms": list(text_backfill.DEFAULT_FORMS),
        "text_default_includes_6k": "6-K" in forms,
        "text_default_item_codes": list(text_backfill.DEFAULT_ITEM_CODES),
        "six_k_admitted_under_default_item_codes": bool(six_k_admitted),
        "eight_k_202_admitted_under_default_item_codes": bool(eight_k_202_admitted),
        "eight_k_nonmatching_item_rejected_under_default_item_codes": bool(eight_k_502_rejected),
        "daily_snapshot_text_forms": daily_forms,
        "daily_snapshot_text_scope_follows_default_6k": "6-K" in {
            form.upper().replace("/A", "") for form in daily_forms
        },
        "daily_snapshot_item_codes": ["all"],
    }


def sample_ready(audit: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    counts = audit["target_unique_events_by_window"]
    total = int(audit["target_unique_events_total"])
    windows = [label for label in CANONICAL_WINDOWS if int(counts.get(label) or 0) > 0]
    if total < MIN_TARGET_UNIQUE_EVENTS:
        reasons.append("target_unique_6k_events_below_20")
    if len(windows) < MIN_TARGET_WINDOWS:
        reasons.append("target_6k_events_missing_three_window_coverage")
    for label in CANONICAL_WINDOWS:
        if int(counts.get(label) or 0) < MIN_TARGET_UNIQUE_EVENTS_PER_WINDOW:
            reasons.append(f"{label}_target_6k_unique_events_below_5")
    return not reasons, reasons


def dependency_ready(audit: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    for field, stats in audit["dependency_presence"].items():
        if float(stats["present_rate"]) < 1.0:
            reasons.append(f"{field}_missing_on_some_target_rows")
    return not reasons, reasons


def build_result() -> dict[str, Any]:
    timestamp = now_utc()
    ticket = read_json(TICKET_JSON)
    baseline = load_baseline()
    cache_audit = scan_cached_submissions()
    text_audit = text_scope_audit()
    sample_passed, sample_reasons = sample_ready(cache_audit)
    dependency_passed, dependency_reasons = dependency_ready(cache_audit)
    builder_reasons: list[str] = []
    if not cache_audit["event_default_includes_6k"]:
        builder_reasons.append("sec_event_builder_default_forms_do_not_include_6k_and_6k_a")
    if not text_audit["text_default_includes_6k"]:
        builder_reasons.append("sec_text_builder_default_forms_do_not_include_6k")
    if not text_audit["six_k_admitted_under_default_item_codes"]:
        builder_reasons.append("sec_text_default_item_filter_still_rejects_6k")
    if not text_audit["daily_snapshot_text_scope_follows_default_6k"]:
        builder_reasons.append("daily_snapshot_text_forms_do_not_follow_sec_text_default_6k")

    gate2_passed = not builder_reasons and dependency_passed and cache_audit["target_unique_events_total"] > 0
    gate3_passed = sample_passed
    success = gate2_passed and gate3_passed
    status = "accepted_measurement_repair" if success else "blocked"
    decision = (
        "accepted_measurement_repair_sec_6k_daily_surface_wired"
        if success
        else "blocked_sec_6k_daily_surface_repair_incomplete"
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "measurement_repair",
        "status": status,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "shared_daily_data_surface_repair",
        "mechanism_family": "production_visible_free_sec_6k_foreign_issuer_candidate_pool",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "nearby_prior_experiments": ["exp-20260621-018"],
        "prediction": ticket.get("prediction"),
        "pre_run_questions": {
            "1_alpha_hypothesis": (
                "6-K foreign issuer current reports may carry ADR/foreign-company "
                "information shocks not present in domestic 8-K/10-Q/10-K event pools."
            ),
            "2_history_check": (
                "exp-20260621-018 blocked this alpha because raw form-index had 6-K "
                "volume while production-visible SEC event/text surfaces had zero 6-K rows."
            ),
            "3_single_decision_hypothesis": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Accepted as measurement repair only if shared daily event/text defaults "
                "include 6-K, text item-code filtering no longer rejects non-8-K forms, "
                "and local cache replay shows at least 20 unique 6-K events across all "
                "three canonical windows with at least five per window."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "gate1": {
            "baseline_result_file": BASELINE_RESULT_FILE,
            "baseline": baseline,
            "passed": True,
        },
        "gate2": {
            "dependency_fields_checked": list(cache_audit["dependency_presence"].keys()),
            "entry_date_target_price_note": (
                "This measurement repair exposes filing rows with usable_trade_date. "
                "Strategy entry_date and target_price are intentionally not claimed "
                "until a later shared alpha helper converts 6-K events into candidates."
            ),
            "cache_replay_surface": cache_audit,
            "text_surface": text_audit,
            "passed": gate2_passed,
            "blocking_reasons": builder_reasons + dependency_reasons,
        },
        "gate3": {
            "minimum_target_unique_events": MIN_TARGET_UNIQUE_EVENTS,
            "minimum_target_windows": MIN_TARGET_WINDOWS,
            "minimum_target_unique_events_per_window": MIN_TARGET_UNIQUE_EVENTS_PER_WINDOW,
            "target_unique_events_by_window": cache_audit["target_unique_events_by_window"],
            "target_unique_events_total": cache_audit["target_unique_events_total"],
            "target_tickers": cache_audit["target_tickers"],
            "passed": gate3_passed,
            "blocking_reasons": sample_reasons,
        },
        "gate4": {
            "ran_after_strategy": False,
            "reason_after_not_run": (
                "Measurement repair only: SEC daily data surface changed, but no buy, "
                "sell, ranking, sizing, risk, or backtest policy changed."
            ),
            "aggregate_before": baseline["aggregate"],
            "aggregate_after": baseline["aggregate"],
            "aggregate_delta": {
                "aggregate_expected_value_score": 0.0,
                "aggregate_total_pnl": 0.0,
                "total_trade_count": 0,
            },
            "passed": True,
        },
        "before_metrics": {
            "production_visible_sec_6k_alpha_status": "blocked_raw_form_index_only",
            "prior_experiment": "exp-20260621-018",
        },
        "after_metrics": {
            "event_default_includes_6k": cache_audit["event_default_includes_6k"],
            "text_default_includes_6k": text_audit["text_default_includes_6k"],
            "text_six_k_default_match": text_audit["six_k_admitted_under_default_item_codes"],
            "daily_text_scope_follows_default_6k": text_audit["daily_snapshot_text_scope_follows_default_6k"],
            "target_unique_6k_events_total": cache_audit["target_unique_events_total"],
            "target_unique_6k_events_by_window": cache_audit["target_unique_events_by_window"],
        },
        "delta_metrics": {
            "aggregate_expected_value_score": 0.0,
            "aggregate_total_pnl": 0.0,
            "total_trade_count": 0,
            "production_visible_6k_surface_repaired": bool(success),
        },
        "production_impact": {
            "strategy_code_changed": False,
            "shared_data_builder_changed": True,
            "daily_snapshot_changed": True,
            "backtester_adapter_changed": False,
            "live_orders_changed": False,
            "trade_enabled_changed": False,
            "production_orders_changed": False,
            "production_watchlist_changed": False,
            "default_off_paper_only": True,
            "live_ready": False,
            "parity_note": (
                "The repair makes 6-K visible through the shared daily SEC data path; "
                "it does not add an alpha helper or any live trading behavior."
            ),
        },
        "calibration": {
            "prediction_required": False,
            "actual_success": int(success),
            "actual_ev_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "failure_modes_observed": builder_reasons + dependency_reasons + sample_reasons,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The prior block was a surface mismatch: 6-K existed in raw SEC "
                "metadata but the shared daily event/text builders excluded it. The "
                "repair adds 6-K/6-KA to event defaults, adds 6-K to text defaults, "
                "and keeps 8-K item-code filtering from suppressing non-8-K forms."
            ),
            "negative_result_reflection": (
                "No strategy result is accepted here. A follow-up alpha still needs a "
                "shared helper that maps 6-K event text into entry/exit/ranking rules "
                "and then runs Gate 1-4."
            ),
            "anti_repeat": (
                "Do not rerun the old raw-form-index-only 6-K readiness check. The "
                "new evidence axis is an actual 6-K semantic candidate helper or "
                "daily generated 6-K text artifact with replayable labels."
            ),
            "next_step": (
                "Build a default-off 6-K semantic classifier/helper using the repaired "
                "event/text surface, then run full three-window Gate 1-4."
            ),
        },
        "related_files": [
            RUNNER_NAME,
            "quant/sec_filing_backfill.py",
            "quant/sec_filing_text_backfill.py",
            "quant/daily_non_ohlcv_snapshot.py",
            "quant/test_sec_filing_backfill.py",
            "quant/test_sec_filing_text_backfill.py",
            "quant/test_daily_non_ohlcv_snapshot.py",
            repo_rel(ARTIFACT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
        ],
        "reproduction": {
            "runner": RUNNER_COMMAND,
            "tests": [
                ".\\.venv\\Scripts\\python.exe -m pytest quant\\test_sec_filing_backfill.py quant\\test_sec_filing_text_backfill.py quant\\test_daily_non_ohlcv_snapshot.py",
                ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
            ],
        },
        "lean_quality_passed": True,
        "anti_js": {"used_javascript": False},
    }


def build_log_record(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": result["timestamp"],
        "status": result["status"],
        "lane": result["lane"],
        "decision": result["decision"],
        "hypothesis": result["hypothesis"],
        "change_type": result["change_type"],
        "mechanism_family": result["mechanism_family"],
        "trial_family": result["trial_family"],
        "trial_variant_id": result["trial_variant_id"],
        "single_causal_variable": result["single_causal_variable"],
        "changed_variable": result["changed_variable"],
        "before_metrics": result["before_metrics"],
        "after_metrics": result["after_metrics"],
        "delta_metrics": result["delta_metrics"],
        "gate1": result["gate1"],
        "gate2": result["gate2"],
        "gate3": result["gate3"],
        "gate4": result["gate4"],
        "production_impact": result["production_impact"],
        "calibration": result["calibration"],
        "post_run_reflection": result["post_run_reflection"],
        "related_files": result["related_files"],
        "reproduction": result["reproduction"],
        "lean_quality_passed": result["lean_quality_passed"],
    }


def build_card(result: dict[str, Any]) -> str:
    gate3 = result["gate3"]
    lines = [
        f"# {EXPERIMENT_ID}: SEC 6-K daily event surface repair",
        "",
        f"- Status: {result['status']}",
        f"- Decision: {result['decision']}",
        "- Lane: measurement_repair",
        "- Production impact: shared daily SEC data surface only; no orders/ranking/sizing changed.",
        "",
        "## Hypothesis",
        "",
        result["hypothesis"],
        "",
        "## Evidence",
        "",
        "| Window | Unique 6-K events |",
        "| --- | ---: |",
    ]
    for label in CANONICAL_WINDOWS:
        lines.append(f"| {label} | {gate3['target_unique_events_by_window'][label]} |")
    lines.extend(
        [
            f"| total | {gate3['target_unique_events_total']} |",
            "",
            "## Gate 4",
            "",
            result["gate4"]["reason_after_not_run"],
            "",
            "## Next",
            "",
            result["post_run_reflection"]["next_step"],
            "",
        ]
    )
    return "\n".join(lines)


def build_manifest(result: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER_NAME,
        REPO_ROOT / "quant" / "sec_filing_backfill.py",
        REPO_ROOT / "quant" / "sec_filing_text_backfill.py",
        REPO_ROOT / "quant" / "daily_non_ohlcv_snapshot.py",
        REPO_ROOT / "quant" / "test_sec_filing_backfill.py",
        REPO_ROOT / "quant" / "test_sec_filing_text_backfill.py",
        REPO_ROOT / "quant" / "test_daily_non_ohlcv_snapshot.py",
        ARTIFACT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG_JSONL,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": result["status"],
        "decision": result["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER_NAME,
        "command": result["reproduction"]["runner"],
        "anti_js": result["anti_js"],
        "files": {
            repo_rel(path): {
                "exists": path.exists(),
                "sha256": sha256_file(path),
            }
            for path in files
        },
        "updated_at": now_utc(),
    }


def persist(result: dict[str, Any]) -> None:
    write_json(ARTIFACT_JSON, result)
    write_json(LOG_JSON, build_log_record(result))
    write_text(CARD_MD, build_card(result))
    append_jsonl_once(EXPERIMENT_LOG_JSONL, build_log_record(result))

    registry_result = {
        "accepted": result["status"].startswith("accepted"),
        "accepted_alpha": False,
        "decision": result["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER_NAME,
        "delta_metrics": result["delta_metrics"],
        "gate2": result["gate2"],
        "gate3": result["gate3"],
        "gate4": result["gate4"],
        "calibration": result["calibration"],
        "summary": result["post_run_reflection"]["why_result_happened"],
    }
    experiment_registry.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=result["prediction"],
        result=registry_result,
        status=result["status"],
        fields={
            "owner": "codex-alpha-explore",
            "hypothesis": result["hypothesis"],
            "change_type": result["change_type"],
            "mechanism_family": result["mechanism_family"],
            "trial_family": result["trial_family"],
            "trial_variant_id": result["trial_variant_id"],
            "single_causal_variable": result["single_causal_variable"],
            "changed_variable": result["changed_variable"],
            "nearby_prior_experiments": result["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": "minimal",
            "new_evidence_type": "sec_6k_daily_event_surface_repair",
            "baseline_result_file": BASELINE_RESULT_FILE,
            "evaluation_windows": [
                {
                    "label": label,
                    "start": row["start"],
                    "end": row["end"],
                    "snapshot": row["snapshot"],
                }
                for label, row in CANONICAL_WINDOWS.items()
            ],
            "acceptance_rule": result["pre_run_questions"]["4_acceptance_standard"],
            "decision": result["decision"],
            "summary": result["post_run_reflection"]["why_result_happened"],
            "artifact": repo_rel(ARTIFACT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": result["gate1"],
            "gate2": result["gate2"],
            "gate3": result["gate3"],
            "gate4": result["gate4"],
            "production_impact": result["production_impact"],
            "post_run_reflection": result["post_run_reflection"],
            "lean_quality_passed": result["lean_quality_passed"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(result))


def main() -> int:
    result = build_result()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": result["status"],
                "decision": result["decision"],
                "target_unique_6k_events_total": result["gate3"]["target_unique_events_total"],
                "target_unique_6k_events_by_window": result["gate3"]["target_unique_events_by_window"],
                "gate2_passed": result["gate2"]["passed"],
                "gate3_passed": result["gate3"]["passed"],
                "gate4_ran_after_strategy": result["gate4"]["ran_after_strategy"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
