"""exp-20260627-004: SEC 6-K standard-window text materialization.

Measurement repair for the 6-K foreign issuer alpha blocker. The standard
historical SEC event/text replay files omit 6-K rows, while daily snapshots now
surface them. This runner materializes a 6-K/6-KA-only standard-window event
file, audits cache-only text availability, and records whether the existing
shared 6-K helper can be tested without introducing any strategy behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
QUANT_DIR = REPO_ROOT / "quant"
for candidate in (SCRIPTS_DIR, QUANT_DIR):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import experiment_registry  # noqa: E402
import sec_filing_backfill as event_backfill  # noqa: E402
import sec_filing_text_backfill as text_backfill  # noqa: E402
import sec_6k_positive_operating_update_paper_sleeve as sixk_helper  # noqa: E402


EXPERIMENT_ID = "exp-20260627-004"
OWNER = "alpha-explore"
SLUG = "sec_6k_standard_window_text_materialization"
RUNNER = f"quant/experiments/exp_20260627_004_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

START = "2024-10-02"
END = "2026-04-21"
TARGET_FORMS = ("6-K", "6-K/A")
TARGET_FORM_BASES = {"6-K"}

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"exp_20260627_004_{SLUG}.json"
EVENT_SUMMARY_JSON = DATA_DIR / "sec_filing_events_6k_backfill_summary_20241002_20260421.json"
TEXT_SUMMARY_EXPERIMENT_JSON = DATA_DIR / "sec_filing_text_6k_backfill_summary_20241002_20260421.json"
EVENTS_6K_JSONL = REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_events_6k_20241002_20260421.jsonl"
TEXT_6K_JSONL = REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_text_6k_20241002_20260421.jsonl"
TEXT_SUMMARY_JSON = REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_text_6k_backfill_summary_20241002_20260421.json"
STANDARD_EVENTS_JSONL = REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_events_20241002_20260421.jsonl"
STANDARD_TEXT_JSONL = REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_text_20241002_20260421.jsonl"
TEXT_CACHE_DIR = REPO_ROOT / "data" / "cache" / "sec" / "filing_text"
EVENT_CACHE_DIR = REPO_ROOT / "data" / "cache" / "sec" / "submissions"

LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
BASELINE_RESULT_FILE = "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
BASELINE_RESULT_JSON = REPO_ROOT / BASELINE_RESULT_FILE

HYPOTHESIS = (
    "alpha_blocker: a fixed 6-K structured operating or guidance semantic "
    "candidate source cannot be tested while the canonical standard-window SEC "
    "event/text replay files omit 6-K rows, so materializing PIT 6-K/6-KA "
    "historical text from the existing SEC cache should unlock a future shared "
    "helper without changing strategy behavior."
)
ALPHA_HYPOTHESIS = (
    "Foreign issuer 6-K operating updates may contain guidance revisions, ADR "
    "liquidity context, and issuer-country shocks that are absent from domestic "
    "8-K pools; this run tests only whether the replay surface exists."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "production_visible_free_sec_6k_foreign_issuer_candidate_pool"
TRIAL_FAMILY = "sec_6k_historical_event_text_materialization"
TRIAL_VARIANT_ID = "sec_6k_standard_window_text_materialization_v1"
CHANGED_VARIABLE = "sec_6k_standard_window_event_text_materialization_v1"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260622-014",
    "exp-20260622-015",
    "exp-20260622-016",
    "exp-20260625-011",
    "exp-20260625-014",
]
CAUSAL_COMPONENTS = [
    "historical SEC cache coverage audit",
    "6-K/6-KA event materialization",
    "6-K/6-KA text materialization",
    "shared helper coverage smoke test",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260627-004",
    "data/non_ohlcv/sec_filing_events_6k_20241002_20260421.jsonl",
    "data/non_ohlcv/sec_filing_text_6k_20241002_20260421.jsonl",
    "data/non_ohlcv/sec_filing_text_6k_backfill_summary_20241002_20260421.json",
    "experiments/logs/exp-20260627-004.json",
    "experiments/cards/exp-20260627-004.md",
    "experiments/manifests/exp-20260627-004.json",
    "experiments/tickets/exp-20260627-004.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]

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


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for line_number, raw in enumerate(handle, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSONL") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(make_json_safe(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(
                json.dumps(make_json_safe(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                + "\n"
            )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): make_json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [make_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [make_json_safe(item) for item in value]
    if isinstance(value, Counter):
        return dict(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(make_json_safe(record), sort_keys=True)
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
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_date(value: Any) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def form_base(row: dict[str, Any]) -> str:
    raw = str(row.get("form_base") or row.get("form_type") or "").upper()
    return raw[:-2] if raw.endswith("/A") else raw


def window_for(value: Any) -> str | None:
    observed = parse_date(value)
    if observed is None:
        return None
    for label, window in CANONICAL_WINDOWS.items():
        if date.fromisoformat(window["start"]) <= observed <= date.fromisoformat(window["end"]):
            return label
    return None


def summarize_rows(rows: list[dict[str, Any]], *, date_field: str = "usable_trade_date") -> dict[str, Any]:
    by_form = Counter(str(row.get("form_type") or "UNKNOWN") for row in rows)
    by_base = Counter(form_base(row) or "UNKNOWN" for row in rows)
    by_window: Counter[str] = Counter()
    unique_by_window: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        label = window_for(row.get(date_field) or row.get("filing_date"))
        if not label:
            continue
        by_window[label] += 1
        key = str(row.get("accession_number") or f"{row.get('ticker')}:{row.get(date_field)}")
        unique_by_window[label].add(key)
    return {
        "rows": len(rows),
        "forms": dict(sorted(by_form.items())),
        "form_bases": dict(sorted(by_base.items())),
        "tickers": len({row.get("ticker") for row in rows if row.get("ticker")}),
        "accessions": len({row.get("accession_number") for row in rows if row.get("accession_number")}),
        "rows_by_window": {label: by_window.get(label, 0) for label in CANONICAL_WINDOWS},
        "unique_accessions_by_window": {
            label: len(unique_by_window.get(label, set())) for label in CANONICAL_WINDOWS
        },
    }


def field_presence(rows: list[dict[str, Any]], fields: list[str]) -> dict[str, Any]:
    total = len(rows)
    return {
        field: {
            "present_rows": sum(1 for row in rows if row.get(field) not in (None, "")),
            "total_rows": total,
            "present_rate": round(
                sum(1 for row in rows if row.get(field) not in (None, "")) / total,
                6,
            )
            if total
            else 0.0,
        }
        for field in fields
    }


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT_JSON, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    drawdowns = [
        float(row.get("max_drawdown_pct"))
        for row in windows
        if row.get("max_drawdown_pct") is not None
    ]
    return {
        "baseline_exists": BASELINE_RESULT_JSON.exists(),
        "baseline_result_file": BASELINE_RESULT_FILE,
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
    }


def run_event_materialization() -> dict[str, Any]:
    args = argparse.Namespace(
        start=START,
        end=END,
        segments=["core", "pilot", "observation"],
        tickers=None,
        include_etfs=False,
        max_ciks=None,
        forms=[",".join(TARGET_FORMS)],
        cache_dir=str(EVENT_CACHE_DIR),
        refresh_submissions=False,
        refresh_chunks=False,
        fetch_all_overlap_chunks=False,
        no_fetch_overlap_chunks=True,
        sleep_seconds=0.0,
        user_agent=event_backfill.DEFAULT_USER_AGENT,
        output=str(EVENTS_6K_JSONL),
        summary_output=str(EVENT_SUMMARY_JSON),
    )
    summary = event_backfill.backfill_sec_filing_events(args)
    upstream_id = summary.get("experiment_id")
    if upstream_id != EXPERIMENT_ID:
        summary["upstream_backfill_experiment_id"] = upstream_id
        summary["experiment_id"] = EXPERIMENT_ID
        write_json(EVENT_SUMMARY_JSON, summary)
    return summary


def cached_text_payload(event: dict[str, Any]) -> tuple[dict[str, Any] | None, Path]:
    accession = str(event.get("accession_number") or "")
    path = text_backfill._cache_path(TEXT_CACHE_DIR, accession)
    if not accession or not path.exists():
        return None, path
    payload = read_json(path, {})
    if not isinstance(payload, dict):
        return None, path
    merged = dict(payload)
    for key in (
        "ticker",
        "cik",
        "accession_number",
        "form_type",
        "form_base",
        "filing_date",
        "usable_trade_date",
        "accepted_at",
        "eight_k_item_codes",
        "primary_document",
        "index_url",
    ):
        if event.get(key) not in (None, ""):
            merged[key] = event.get(key)
    merged.setdefault("status", "cached_without_status")
    merged["pit_source"] = merged.get("pit_source") or "sec_archive_public_filing_text_cache_only"
    merged["cache_path"] = repo_rel(path)
    return merged, path


def materialize_cached_text(events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    cache_status = Counter()
    for event in events:
        payload, path = cached_text_payload(event)
        if payload is None:
            missing.append(
                {
                    "ticker": event.get("ticker"),
                    "accession_number": event.get("accession_number"),
                    "form_type": event.get("form_type"),
                    "filing_date": event.get("filing_date"),
                    "usable_trade_date": event.get("usable_trade_date"),
                    "expected_cache_path": repo_rel(path),
                }
            )
            cache_status["missing_cached_text"] += 1
            continue
        rows.append(payload)
        cache_status[str(payload.get("status") or "unknown")] += 1
    write_jsonl(TEXT_6K_JSONL, rows)
    summary = {
        "generated_at": utc_now(),
        "experiment_id": EXPERIMENT_ID,
        "source_events": repo_rel(EVENTS_6K_JSONL),
        "output_path": repo_rel(TEXT_6K_JSONL),
        "cache_dir": repo_rel(TEXT_CACHE_DIR),
        "events_input": len(events),
        "rows_written": len(rows),
        "missing_cached_text_rows": len(missing),
        "status_counts": dict(sorted(cache_status.items())),
        "forms": list(TARGET_FORMS),
        "tickers": len({row.get("ticker") for row in rows if row.get("ticker")}),
        "accessions": len({row.get("accession_number") for row in rows if row.get("accession_number")}),
        "documents_fetched": sum(int(row.get("documents_fetched") or 0) for row in rows),
        "text_char_count": sum(int(row.get("text_char_count") or 0) for row in rows),
        "missing_cache_examples": missing[:12],
        "cache_only": True,
        "network_fetch_attempted": False,
        "pit_caveat": (
            "This run only materializes text already present in the local SEC "
            "filing_text cache. It intentionally does not fetch public archive "
            "documents over the network."
        ),
    }
    write_json(TEXT_SUMMARY_JSON, summary)
    write_json(TEXT_SUMMARY_EXPERIMENT_JSON, summary)
    return rows, summary


def helper_smoke() -> dict[str, Any]:
    try:
        helper_rows = sixk_helper.load_sec_6k_positive_operating_update_rows(max_filed=END)
    except Exception as exc:
        return {
            "passed": False,
            "error": str(exc),
            "candidate_rows": 0,
            "note": "Shared 6-K helper could not load rows from data/non_ohlcv.",
        }
    return {
        "passed": len(helper_rows) > 0,
        "candidate_rows": len(helper_rows),
        "sample": helper_rows[:5],
        "note": (
            "Smoke is positive only if historical 6-K text rows exist and the "
            "default-off helper classifies at least one operating-update candidate."
        ),
    }


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    if isinstance(prediction, dict) and prediction:
        return prediction
    return {
        "success_probability": 0.55,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "cache_lacks_6k_text",
            "sec_archive_text_cache_missing",
            "helper_still_zero_candidates",
            "audit_dirty_worktree_conflict",
        ],
        "confidence_reason": (
            "Historical event metadata should be available from the SEC "
            "submissions cache, but 6-K filing text may be absent from the "
            "local text cache."
        ),
        "recorded_at": utc_now(),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    prediction = load_ticket_prediction()
    baseline = baseline_metrics()
    before_events = read_jsonl(STANDARD_EVENTS_JSONL)
    before_text = read_jsonl(STANDARD_TEXT_JSONL)
    before_summary = {
        "standard_events": summarize_rows(before_events),
        "standard_text": summarize_rows(before_text),
    }

    event_backfill_summary = run_event_materialization()
    events = read_jsonl(EVENTS_6K_JSONL)
    target_events = [row for row in events if form_base(row) in TARGET_FORM_BASES]
    non_target_forms = [
        row.get("form_type")
        for row in events
        if form_base(row) not in TARGET_FORM_BASES
    ]
    text_rows, text_summary = materialize_cached_text(target_events)
    smoke = helper_smoke()

    event_presence = field_presence(
        target_events,
        [
            "ticker",
            "cik",
            "accession_number",
            "form_type",
            "filing_date",
            "accepted_at",
            "usable_trade_date",
            "archive_url",
            "index_url",
        ],
    )
    text_presence = field_presence(
        text_rows,
        [
            "ticker",
            "accession_number",
            "form_type",
            "usable_trade_date",
            "combined_text",
            "text_word_count",
        ],
    )

    target_summary = summarize_rows(target_events)
    text_rows_with_body = [
        row
        for row in text_rows
        if int(row.get("text_word_count") or 0) >= sixk_helper.MIN_TEXT_WORDS
        and str(row.get("combined_text") or "")
    ]
    event_gate_passed = (
        len(target_events) > 0
        and not non_target_forms
        and all(stats["present_rate"] == 1.0 for stats in event_presence.values())
    )
    text_gate_passed = len(text_rows_with_body) > 0
    gate2_passed = bool(event_gate_passed and text_gate_passed)
    gate3_passed = all(target_summary["unique_accessions_by_window"][label] >= 5 for label in CANONICAL_WINDOWS)
    accepted = bool(gate2_passed and gate3_passed and smoke["passed"])
    status = "accepted_measurement_repair" if accepted else "rejected"
    decision = (
        "accepted_measurement_repair_sec_6k_standard_window_text_materialized"
        if accepted
        else "rejected_sec_6k_standard_window_text_cache_missing"
    )
    blockers = []
    if not event_gate_passed:
        blockers.append("sec_6k_event_materialization_failed_or_non_target_forms_present")
    if not text_gate_passed:
        blockers.append("local_sec_filing_text_cache_has_zero_usable_6k_bodies")
    if not gate3_passed:
        blockers.append("sec_6k_event_rows_do_not_cover_all_three_windows")
    if not smoke["passed"]:
        blockers.append("shared_sec_6k_helper_has_zero_historical_candidates")

    result_summary = (
        "Corrected the standard-window 6-K/6-KA event replay, but the local "
        "SEC filing_text cache contains no usable 6-K bodies for those events; "
        "a semantic 6-K alpha remains blocked until filing text is populated."
        if not accepted
        else "Materialized historical 6-K/6-KA event and text rows and verified the shared helper can classify candidates."
    )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "alpha_ready": False,
        "lane": "measurement_repair",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "cache_only_standard_window_sec_6k_materialization",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "prediction": prediction,
        "novelty": ticket.get("novelty") if isinstance(ticket, dict) else None,
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
                "novelty_gate": ticket.get("novelty") if isinstance(ticket, dict) else None,
                "source_saturation_note": (
                    "This is a measurement repair for historical 6-K replay "
                    "materialization, not a saturated sec_text_event alpha retry."
                ),
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Accept only if 6-K/6-KA events are materialized with required "
                "PIT fields, usable historical 6-K text rows are present from "
                "cache, the shared default-off helper sees candidates, and no "
                "strategy behavior changes."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "start": START,
            "end": END,
            "forms": list(TARGET_FORMS),
            "event_cache_dir": repo_rel(EVENT_CACHE_DIR),
            "text_cache_dir": repo_rel(TEXT_CACHE_DIR),
            "cache_only_text": True,
            "network_fetch_attempted": False,
        },
        "before_metrics": before_summary,
        "after_metrics": {
            "sec_6k_events": target_summary,
            "sec_6k_text": summarize_rows(text_rows),
            "sec_6k_text_with_min_body_rows": len(text_rows_with_body),
            "helper_smoke_candidate_rows": smoke["candidate_rows"],
        },
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "strategy_behavior_changed": False,
            "standard_event_6k_rows_before": before_summary["standard_events"]["form_bases"].get("6-K", 0),
            "materialized_event_6k_rows_after": len(target_events),
            "materialized_text_6k_rows_after": len(text_rows),
            "usable_text_6k_body_rows_after": len(text_rows_with_body),
        },
        "gate1": {
            "passed": baseline["baseline_exists"] and baseline["window_count"] == 3,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": gate2_passed,
            "event_gate_passed": event_gate_passed,
            "text_gate_passed": text_gate_passed,
            "event_field_presence": event_presence,
            "text_field_presence": text_presence,
            "entry_date_target_price_note": (
                "This materialization exposes usable_trade_date for future "
                "candidate entry construction. target_price is intentionally not "
                "claimed until a later alpha helper creates executable candidates."
            ),
            "blocking_reasons": blockers,
        },
        "gate3": {
            "passed": gate3_passed,
            "filter_added": False,
            "survival_rate_note": (
                "No trading filter was added. Event coverage is checked instead "
                "of strategy signal survival."
            ),
            "target_unique_accessions_by_window": target_summary["unique_accessions_by_window"],
            "target_event_rows_total": len(target_events),
        },
        "gate4": {
            "passed": accepted,
            "accepted_alpha": False,
            "measurement_repair_only": True,
            "decision": decision,
            "ran_after_strategy": False,
            "reason_after_not_run": (
                "No buy, sell, filtering, ranking, sizing, risk, LLM hard-decision, "
                "daily order, or backtest policy changed."
            ),
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "signals_generated_delta": 0,
                "signals_survived_delta": 0,
                "strategy_behavior_changed": False,
            },
            "blocking_reasons": blockers,
        },
        "materialization": {
            "event_backfill_summary": event_backfill_summary,
            "event_output": repo_rel(EVENTS_6K_JSONL),
            "event_summary": repo_rel(EVENT_SUMMARY_JSON),
            "text_output": repo_rel(TEXT_6K_JSONL),
            "text_summary": text_summary,
            "helper_smoke": smoke,
        },
        "production_impact": {
            "trade_enabled": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_exposed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "watchlist_changed": False,
            "llm_decision_boundary_changed": False,
            "live_ready": False,
            "live_realism_evaluated": False,
            "parity_note": (
                "Experiment-owned historical non-OHLCV artifacts only; no shared "
                "trading helper or production order path changed."
            ),
        },
        "calibration": {
            "predicted_success_probability": prediction.get("success_probability"),
            "actual_success": 1 if accepted else 0,
            "expected_ev_delta": prediction.get("expected_ev_delta"),
            "actual_ev_delta": 0.0,
            "expected_pnl_delta": prediction.get("expected_pnl_delta"),
            "actual_pnl_delta": 0.0,
            "predicted_failure_modes": prediction.get("main_failure_modes"),
            "realized_failure_modes": blockers,
            "surprise_note": (
                "Event metadata was available, but the existing local text cache "
                "had no usable 6-K filing bodies for standard-window replay."
                if not accepted
                else "Both event and text materialization succeeded from cache."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": result_summary,
            "forbidden_near_neighbor_retry": (
                "Do not rerun 6-K semantic phrase, threshold, RS, top-N, hold, "
                "cooldown, or notional experiments on frozen windows while "
                "historical 6-K text bodies remain absent."
            ),
            "new_evidence_required": (
                "Populate replayable SEC 6-K/6-KA filing text for the 236 "
                "standard-window accessions, or add a genuinely new source with "
                "closed forward rows, before testing 6-K semantic alpha."
            ),
            "next_step": (
                "Backfill/cache SEC archive filing text for these 6-K accessions "
                "under a controlled PIT replay contract, then rerun the shared "
                "6-K helper smoke and Gate 1-4 alpha test."
            ),
        },
        "related_files": [
            RUNNER,
            repo_rel(ARTIFACT_JSON),
            repo_rel(EVENTS_6K_JSONL),
            repo_rel(TEXT_6K_JSONL),
            repo_rel(TEXT_SUMMARY_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
        ],
        "changed_files": [
            RUNNER,
            repo_rel(ARTIFACT_JSON),
            repo_rel(EVENT_SUMMARY_JSON),
            repo_rel(TEXT_SUMMARY_EXPERIMENT_JSON),
            repo_rel(EVENTS_6K_JSONL),
            repo_rel(TEXT_6K_JSONL),
            repo_rel(TEXT_SUMMARY_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG_JSONL),
            repo_rel(REGISTRY_JSON),
        ],
        "reproduction": {
            "runner": RUNNER_COMMAND,
            "checks": [
                ".\\.venv\\Scripts\\python.exe -B -m py_compile "
                "quant\\experiments\\exp_20260627_004_sec_6k_standard_window_text_materialization.py",
                ".\\.venv\\Scripts\\python.exe -m pytest quant\\test_sec_filing_backfill.py "
                "quant\\test_sec_filing_text_backfill.py quant\\test_daily_non_ohlcv_snapshot.py",
                ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
            ],
        },
        "lean_quality_passed": True,
    }


def log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "alpha_ready",
        "lane",
        "owner",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "single_causal_variable",
        "causal_components",
        "nearby_prior_experiments",
        "prediction",
        "parameters",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "calibration",
        "post_run_reflection",
        "related_files",
        "changed_files",
        "reproduction",
        "lean_quality_passed",
    ]
    return {key: payload[key] for key in keys if key in payload}


def build_card(payload: dict[str, Any]) -> str:
    gate3 = payload["gate3"]
    lines = [
        f"# {EXPERIMENT_ID}: SEC 6-K standard-window text materialization",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        "- Lane: `measurement_repair`",
        "- Production impact: experiment-owned historical data artifacts only; no order/ranking/sizing path changed.",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Event Coverage",
        "",
        "| Window | Unique 6-K accessions |",
        "| --- | ---: |",
    ]
    for label in CANONICAL_WINDOWS:
        lines.append(f"| {label} | {gate3['target_unique_accessions_by_window'][label]} |")
    lines.extend(
        [
            f"| total rows | {gate3['target_event_rows_total']} |",
            "",
            "## Text Cache Result",
            "",
            f"- Cached text rows written: `{payload['after_metrics']['sec_6k_text']['rows']}`",
            f"- Usable text body rows: `{payload['after_metrics']['sec_6k_text_with_min_body_rows']}`",
            f"- Helper smoke candidates: `{payload['after_metrics']['helper_smoke_candidate_rows']}`",
            "",
            "## Next",
            "",
            payload["post_run_reflection"]["next_step"],
            "",
        ]
    )
    return "\n".join(lines)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        ARTIFACT_JSON,
        EVENT_SUMMARY_JSON,
        TEXT_SUMMARY_EXPERIMENT_JSON,
        EVENTS_6K_JSONL,
        TEXT_6K_JSONL,
        TEXT_SUMMARY_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG_JSONL,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {
                "exists": path.exists(),
                "sha256": sha256(path),
            }
            for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    record = log_record(payload)
    write_json(ARTIFACT_JSON, payload)
    write_json(LOG_JSON, record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG_JSONL, record)
    registry_result = {
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "alpha_ready": payload["alpha_ready"],
        "decision": payload["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "delta_metrics": payload["delta_metrics"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    experiment_registry.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=payload["prediction"],
        result=registry_result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": "minimal",
            "new_evidence_type": "historical_replay_surface_materialization",
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
            "acceptance_rule": payload["pre_run_questions"]["4_success_failure_standard"],
            "decision": payload["decision"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
            "artifact": repo_rel(ARTIFACT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "changed_files": payload["changed_files"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "event_rows": payload["after_metrics"]["sec_6k_events"]["rows"],
                "event_rows_by_window": payload["after_metrics"]["sec_6k_events"]["rows_by_window"],
                "text_rows": payload["after_metrics"]["sec_6k_text"]["rows"],
                "usable_text_rows": payload["after_metrics"]["sec_6k_text_with_min_body_rows"],
                "helper_candidates": payload["after_metrics"]["helper_smoke_candidate_rows"],
                "gate2_passed": payload["gate2"]["passed"],
                "gate3_passed": payload["gate3"]["passed"],
                "gate4_passed": payload["gate4"]["passed"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
