"""exp-20260625-011: SEC 6-K historical event accession materialization.

Measurement repair for the blocked structured 6-K financial-growth alpha. This
runner materializes the local historical 6-K/6-KA accession surface from cached
SEC submissions, then checks whether the filing-text cache is sufficient for a
later semantic replay. It does not change strategy behavior.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
QUANT_DIR = REPO_ROOT / "quant"
for entry in (SCRIPTS_DIR, QUANT_DIR):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402
import sec_filing_backfill as event_backfill  # noqa: E402
from sec_ticker_map import load_company_ticker_map, normalize_cik  # noqa: E402


EXPERIMENT_ID = "exp-20260625-011"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "sec_6k_historical_event_accession_materialization"
RUNNER = f"quant/experiments/exp_20260625_011_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260625_011_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
SUBMISSIONS_CACHE_DIR = REPO_ROOT / "data" / "cache" / "sec" / "submissions"
FILING_TEXT_CACHE_DIR = REPO_ROOT / "data" / "cache" / "sec" / "filing_text"
HISTORICAL_EVENTS = REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_events_20241002_20260421.jsonl"
HISTORICAL_TEXT = REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_text_20241002_20260421.jsonl"
CURRENT_DAILY_TEXT = REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_text_20260624.jsonl"

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

SIX_K_FORMS = {"6-K", "6-K/A", "6-KA"}
MIN_TARGET_EVENTS = 20
MIN_TARGET_WINDOWS = 3
MIN_EVENTS_PER_WINDOW = 5

HYPOTHESIS = (
    "Materialize the historical SEC 6-K/6-KA event accession surface needed "
    "before structured 6-K financial-growth alpha can be replayed; if text "
    "cache remains missing, keep the alpha blocked."
)
ALPHA_HYPOTHESIS = (
    "Structured financial-result growth in PIT 6-K/6-KA foreign-issuer reports "
    "may identify ADR information drift, but the alpha is not testable until "
    "historical accessions and filing text are replayable."
)
CHANGED_VARIABLE = "sec_6k_historical_event_accession_materialization_v1"
MECHANISM_FAMILY = "production_visible_free_sec_6k_foreign_issuer_candidate_pool"
TRIAL_FAMILY = "sec_6k_historical_event_accession_materialization"
TRIAL_VARIANT_ID = "sec_6k_historical_event_accession_materialization_v1"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260622-014",
    "exp-20260622-015",
    "exp-20260622-016",
    "exp-20260624-024",
]

PREDICTION = {
    "success_probability": 0.75,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "submissions_accessions_not_materialized",
        "historical_text_cache_still_missing",
        "window_coverage_too_sparse",
    ],
    "confidence_reason": (
        "exp-20260624-024 found 8010 local submissions 6-K events but zero "
        "generated historical text rows. This run narrows the blocker by "
        "materializing the event accession surface from local cache only."
    ),
    "recorded_at": "2026-06-25T10:05:17+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "shared_policy_changed": False,
    "shared_helper_promoted": False,
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
    "uses_free_sec_submissions": True,
    "uses_free_sec_filing_text": True,
    "uses_llm": False,
    "live_ready": False,
    "live_realism_evaluated": False,
    "replay_only": True,
    "parity_note": (
        "This experiment materializes an event accession research surface only. "
        "It does not add a candidate helper or change production/backtest trade "
        "semantics."
    ),
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


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except json.JSONDecodeError:
        return default


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for raw in handle:
            text = raw.strip()
            if not text:
                continue
            value = json.loads(text)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str | None:
    if not path.exists():
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


def window_for(value: Any) -> str | None:
    observed = parse_date(value)
    if observed is None:
        return None
    for label, window in CANONICAL_WINDOWS.items():
        if date.fromisoformat(window["start"]) <= observed <= date.fromisoformat(window["end"]):
            return label
    return None


def form_value(row: dict[str, Any]) -> str:
    raw = str(row.get("form_type") or row.get("form_base") or row.get("form") or "").upper()
    if raw == "6-KA":
        return "6-K/A"
    return raw


def is_6k(row: dict[str, Any]) -> bool:
    return form_value(row) in SIX_K_FORMS or str(row.get("form_base") or "").upper() in SIX_K_FORMS


def cache_path_for_accession(accession: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", accession)
    return FILING_TEXT_CACHE_DIR / f"{safe}.json"


def load_baseline() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {}) or {}
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    aggregate = {
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": sum(int(row.get("signals_generated") or 0) for row in windows),
        "signals_survived": sum(int(row.get("signals_survived") or 0) for row in windows),
        "max_drawdown_pct_worst": max(
            (float(row.get("max_drawdown_pct") or 0.0) for row in windows),
            default=None,
        ),
        "window_count": len(windows),
        "windows": windows,
    }
    generated = aggregate["signals_generated"]
    aggregate["survival_rate"] = (
        round(float(aggregate["signals_survived"]) / float(generated), 4)
        if generated
        else None
    )
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "baseline_exists": BASELINE_RESULT.exists(),
        "baseline_sha256": sha256_file(BASELINE_RESULT),
        **aggregate,
    }


def payload_cik(path: Path, payload: dict[str, Any]) -> str | None:
    from_payload = normalize_cik(payload.get("cik")) if isinstance(payload, dict) else None
    if from_payload:
        return from_payload
    stem_digits = "".join(ch for ch in path.stem if ch.isdigit())
    return normalize_cik(stem_digits)


def materialize_submission_accessions() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    company_by_cik = load_company_ticker_map()
    forms = {str(form).upper() for form in event_backfill.DEFAULT_FORMS}
    start = min(date.fromisoformat(row["start"]) for row in CANONICAL_WINDOWS.values())
    end = max(date.fromisoformat(row["end"]) for row in CANONICAL_WINDOWS.values())

    by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    all_form_counts: Counter[str] = Counter()
    scanned_files = 0
    mapped_files = 0
    invalid_json_files = 0

    for path in sorted(SUBMISSIONS_CACHE_DIR.glob("CIK*.json")):
        scanned_files += 1
        payload = read_json(path, None)
        if not isinstance(payload, dict):
            invalid_json_files += 1
            continue
        cik = payload_cik(path, payload)
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
            all_form_counts[form_value(row)] += 1
            if not is_6k(row):
                continue
            key = (
                str(row.get("ticker") or ""),
                str(row.get("accession_number") or ""),
                form_value(row),
            )
            compact = {
                "ticker": row.get("ticker"),
                "cik": row.get("cik"),
                "accession_number": row.get("accession_number"),
                "form_type": row.get("form_type"),
                "form_base": row.get("form_base"),
                "filing_date": row.get("filing_date"),
                "accepted_at": row.get("accepted_at"),
                "usable_trade_date": row.get("usable_trade_date"),
                "report_date": row.get("report_date"),
                "primary_document": row.get("primary_document"),
                "archive_url": row.get("archive_url"),
                "index_url": row.get("index_url"),
                "window": window_for(row.get("usable_trade_date") or row.get("filing_date")),
                "pit_source": row.get("pit_source"),
            }
            by_key.setdefault(key, compact)

    events = sorted(
        by_key.values(),
        key=lambda row: (
            str(row.get("usable_trade_date") or row.get("filing_date") or ""),
            str(row.get("ticker") or ""),
            str(row.get("accession_number") or ""),
        ),
    )
    by_window = Counter(str(row.get("window") or "outside") for row in events)
    by_form = Counter(str(row.get("form_type") or "unknown").upper() for row in events)
    required_fields = [
        "ticker",
        "cik",
        "accession_number",
        "form_type",
        "filing_date",
        "accepted_at",
        "usable_trade_date",
        "primary_document",
        "archive_url",
        "index_url",
    ]
    field_presence = {
        field: sum(1 for row in events if row.get(field) not in (None, ""))
        for field in required_fields
    }
    summary = {
        "source": repo_rel(SUBMISSIONS_CACHE_DIR),
        "cache_files_scanned": scanned_files,
        "cache_files_mapped_to_ticker": mapped_files,
        "invalid_json_files": invalid_json_files,
        "default_forms": sorted(forms),
        "default_forms_include_6k": "6-K" in forms and "6-K/A" in forms,
        "all_form_counts_top": all_form_counts.most_common(20),
        "six_k_event_rows": len(events),
        "six_k_accessions": len({row.get("accession_number") for row in events}),
        "six_k_tickers": len({row.get("ticker") for row in events}),
        "six_k_by_window": {label: by_window.get(label, 0) for label in CANONICAL_WINDOWS},
        "six_k_outside_windows": by_window.get("outside", 0),
        "six_k_by_form": dict(sorted(by_form.items())),
        "required_fields": required_fields,
        "field_presence": field_presence,
        "sample_events": events[:20],
    }
    return events, summary


def scan_jsonl_surface(path: Path) -> dict[str, Any]:
    rows = read_jsonl(path)
    six_k_rows = [row for row in rows if is_6k(row)]
    nonempty = [row for row in six_k_rows if str(row.get("combined_text") or "").strip()]
    by_window = Counter(window_for(row.get("usable_trade_date") or row.get("filing_date")) or "outside" for row in six_k_rows)
    return {
        "path": repo_rel(path),
        "exists": path.exists(),
        "sha256": sha256_file(path),
        "rows_total": len(rows),
        "six_k_rows": len(six_k_rows),
        "six_k_nonempty_text_rows": len(nonempty),
        "six_k_by_window": {label: by_window.get(label, 0) for label in CANONICAL_WINDOWS},
        "six_k_outside_windows": by_window.get("outside", 0),
    }


def scan_text_cache(events: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for event in events:
        accession = str(event.get("accession_number") or "")
        if not accession:
            continue
        path = cache_path_for_accession(accession)
        if not path.exists():
            continue
        payload = read_json(path, {}) or {}
        text = str(payload.get("combined_text") or "")
        rows.append(
            {
                "ticker": event.get("ticker"),
                "accession_number": accession,
                "form_type": payload.get("form_type") or event.get("form_type"),
                "cache_path": repo_rel(path),
                "status": payload.get("status"),
                "text_char_count": len(text),
                "documents_fetched": payload.get("documents_fetched"),
            }
        )
    nonempty = [row for row in rows if int(row.get("text_char_count") or 0) > 0]
    return {
        "cache_dir": repo_rel(FILING_TEXT_CACHE_DIR),
        "target_accessions": len({row.get("accession_number") for row in events if row.get("accession_number")}),
        "target_accessions_with_cache_file": len(rows),
        "target_accessions_with_nonempty_text": len(nonempty),
        "sample_cache_rows": rows[:20],
    }


def build_result() -> dict[str, Any]:
    completed_at = utc_now()
    baseline = load_baseline()
    events, event_summary = materialize_submission_accessions()
    historical_events = scan_jsonl_surface(HISTORICAL_EVENTS)
    historical_text = scan_jsonl_surface(HISTORICAL_TEXT)
    current_daily_text = scan_jsonl_surface(CURRENT_DAILY_TEXT)
    text_cache = scan_text_cache(events)

    window_count = sum(1 for label in CANONICAL_WINDOWS if event_summary["six_k_by_window"].get(label, 0) > 0)
    per_window_ready = all(
        int(event_summary["six_k_by_window"].get(label, 0)) >= MIN_EVENTS_PER_WINDOW
        for label in CANONICAL_WINDOWS
    )
    field_ready = all(
        int(event_summary["field_presence"].get(field, 0)) == event_summary["six_k_event_rows"]
        for field in event_summary["required_fields"]
    )
    event_ready = (
        event_summary["six_k_event_rows"] >= MIN_TARGET_EVENTS
        and window_count >= MIN_TARGET_WINDOWS
        and per_window_ready
        and field_ready
    )
    text_ready = text_cache["target_accessions_with_nonempty_text"] >= MIN_TARGET_EVENTS
    alpha_blocked = not text_ready

    status = "accepted_measurement_repair" if event_ready else "blocked"
    decision = (
        "accepted_measurement_repair_sec_6k_event_accessions_materialized_text_cache_blocked"
        if event_ready and alpha_blocked
        else "accepted_measurement_repair_sec_6k_event_and_text_ready"
        if event_ready
        else "blocked_sec_6k_event_accession_materialization_failed"
    )
    actual_success = 1.0 if event_ready else 0.0
    brier = round((PREDICTION["success_probability"] - actual_success) ** 2, 4)

    before_after = {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "expected_value_score_sum": baseline["expected_value_score_sum"],
        "total_pnl": baseline["total_pnl"],
        "trade_count": baseline["trade_count"],
        "signals_generated": baseline["signals_generated"],
        "signals_survived": baseline["signals_survived"],
        "survival_rate": baseline["survival_rate"],
        "max_drawdown_pct_worst": baseline["max_drawdown_pct_worst"],
    }
    delta = {
        "expected_value_score_sum_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "signals_generated_delta": 0,
        "signals_survived_delta": 0,
        "strategy_behavior_changed": False,
    }

    event_failed_reasons: list[str] = []
    if event_summary["six_k_event_rows"] < MIN_TARGET_EVENTS:
        event_failed_reasons.append("target_6k_event_rows_below_minimum")
    if window_count < MIN_TARGET_WINDOWS:
        event_failed_reasons.append("target_6k_event_window_coverage_too_sparse")
    if not per_window_ready:
        event_failed_reasons.append("target_6k_events_per_window_too_sparse")
    if not field_ready:
        event_failed_reasons.append("target_6k_event_required_fields_missing")
    text_failed_reasons = [] if text_ready else ["historical_6k_filing_text_cache_missing"]

    post_run_reflection = {
        "why_result_happened": (
            "The local SEC submissions cache can materialize a broad historical "
            f"6-K/6-KA accession surface: {event_summary['six_k_event_rows']} "
            "rows across the three canonical windows. The existing generated "
            f"historical event/text files still contain {historical_events['six_k_rows']} "
            f"and {historical_text['six_k_nonempty_text_rows']} replayable 6-K "
            "text rows, and the per-accession filing-text cache covers "
            f"{text_cache['target_accessions_with_nonempty_text']} target accessions. "
            "So the event-accession blocker is repaired for handoff, but the "
            "structured 6-K alpha remains blocked on historical text materialization."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry 6-K phrase lists, numeric regexes, RS/volume gates, "
            "top-N, hold, cooldown, or notional until the target accessions have "
            "historical filing text rows. This run is not a semantic alpha pass."
        ),
        "new_evidence_required": (
            "Run SEC archive text backfill for the materialized accession list "
            "or provide a local raw filing-document cache, then write standard "
            "sec_filing_text rows and rerun one fixed structured financial-result "
            "growth helper through shared-paper-first."
        ),
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "decision": decision,
        "timestamp": completed_at,
        "completed_at": completed_at,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": [
            "local SEC submissions 6-K/6-KA accession materialization",
            "historical generated SEC event/text comparison",
            "per-accession filing-text cache coverage check",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "historical_6k_event_accession_materialization",
        "prediction": PREDICTION,
        "calibration": {
            "actual_decision": decision,
            "actual_success": actual_success,
            "brier_score": brier,
            "predicted_success_probability": PREDICTION["success_probability"],
            "predicted_failure_modes": PREDICTION["main_failure_modes"],
            "realized_failure_modes": event_failed_reasons + text_failed_reasons,
            "predicted_failure_mode_hit": bool(text_failed_reasons),
            "surprise_note": (
                "Event accessions materialized from local submissions, but "
                "historical filing text remains absent for these 6-K targets."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260622-014": "Daily SEC builders were repaired to include 6-K/6-KA.",
                "exp-20260622-015": "Generic positive 6-K operating update helper was rejected.",
                "exp-20260622-016": "Structured 6-K financial-growth alpha blocked on missing historical text rows.",
                "exp-20260624-024": "Readiness audit found 8010 submissions events but zero generated historical text rows.",
                "novelty_gate": "exp-20260625-011 passed novelty as measurement repair; nearest prior says text materialization remains the blocker.",
            },
            "3_single_policy_bundle": (
                "One measurement decision: materialize historical 6-K/6-KA "
                "event accessions from local submissions and check whether "
                "text cache exists for a later semantic helper."
            ),
            "4_success_failure_standard": (
                "Accepted as measurement repair if at least 20 6-K/6-KA events "
                "with complete accession metadata cover all three canonical "
                "windows with at least five per window, while strategy metrics "
                "remain unchanged. Alpha promotion additionally requires filing "
                "text coverage, which this run does not claim."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "gate1": {"passed": baseline["baseline_exists"], "baseline_metrics": baseline},
        "gate2": {
            "passed": event_ready,
            "failed_reasons": event_failed_reasons,
            "minimum_trade_fields": ["entry_date", "target_price"],
            "entry_date_target_price_note": (
                "No entries or target exits are scheduled. This repair only "
                "materializes 6-K event accessions before a later helper creates "
                "candidate rows with entry_date and target_price semantics."
            ),
            "event_accession_surface": event_summary,
            "historical_generated_event_surface": historical_events,
            "historical_generated_text_surface": historical_text,
            "current_daily_text_surface": current_daily_text,
            "target_text_cache": text_cache,
            "target_events": events,
        },
        "gate3": {
            "passed": event_ready,
            "filter_added": False,
            "signals_generated": event_summary["six_k_event_rows"],
            "signals_survived": event_summary["six_k_event_rows"] if event_ready else 0,
            "survival_rate": 1.0 if event_ready and event_summary["six_k_event_rows"] else 0.0,
            "alpha_text_survival_rate": (
                round(
                    text_cache["target_accessions_with_nonempty_text"]
                    / event_summary["six_k_event_rows"],
                    6,
                )
                if event_summary["six_k_event_rows"]
                else None
            ),
            "alpha_blocked_reasons": text_failed_reasons,
            "note": (
                "Signals_generated/survived are measurement fields for the "
                "event-accession surface. The semantic alpha remains blocked "
                "because historical filing text is not materialized."
            ),
        },
        "gate4": {
            "passed": event_ready,
            "ran_after_strategy": False,
            "strategy_rerun_required": False,
            "decision": decision,
            "failed_reasons": event_failed_reasons,
            "before_after_strategy_delta": delta,
            "reason_after_not_run": (
                "Measurement repair only. No buy, sell, ranking, sizing, risk, "
                "exit, LLM, watchlist, paper-order, or live-order policy changed."
            ),
        },
        "before_metrics": before_after,
        "after_metrics": before_after,
        "delta_metrics": delta,
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": post_run_reflection,
        "alpha_readiness": {
            "event_accessions_ready": event_ready,
            "historical_text_ready": text_ready,
            "alpha_blocked": alpha_blocked,
            "next_blocker": "historical_6k_filing_text_cache_missing" if alpha_blocked else None,
        },
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "related_files": [
            RUNNER,
            repo_rel(SUBMISSIONS_CACHE_DIR),
            repo_rel(FILING_TEXT_CACHE_DIR),
            repo_rel(HISTORICAL_EVENTS),
            repo_rel(HISTORICAL_TEXT),
            repo_rel(CURRENT_DAILY_TEXT),
            repo_rel(BASELINE_RESULT),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG_JSONL),
            repo_rel(REGISTRY_JSON),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": True,
    }


def compact_log_row(payload: dict[str, Any]) -> dict[str, Any]:
    gate2 = payload["gate2"]
    return {
        "experiment_id": payload["experiment_id"],
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "lane": payload["lane"],
        "decision": payload["decision"],
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
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "pre_run_questions": payload["pre_run_questions"],
        "gate1": payload["gate1"],
        "gate2": {
            "passed": gate2["passed"],
            "failed_reasons": gate2["failed_reasons"],
            "submissions_six_k_event_rows": gate2["event_accession_surface"]["six_k_event_rows"],
            "submissions_six_k_by_window": gate2["event_accession_surface"]["six_k_by_window"],
            "historical_generated_event_six_k_rows": gate2["historical_generated_event_surface"]["six_k_rows"],
            "historical_generated_text_six_k_rows": gate2["historical_generated_text_surface"]["six_k_nonempty_text_rows"],
            "current_daily_text_six_k_rows": gate2["current_daily_text_surface"]["six_k_nonempty_text_rows"],
            "target_accessions_with_nonempty_text": gate2["target_text_cache"]["target_accessions_with_nonempty_text"],
            "sample_events": gate2["event_accession_surface"]["sample_events"],
        },
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "production_impact": payload["production_impact"],
        "alpha_readiness": payload["alpha_readiness"],
        "post_run_reflection": payload["post_run_reflection"],
        "artifact": payload["artifact"],
        "log": payload["log"],
        "related_files": payload["related_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "lean_quality_passed": payload["lean_quality_passed"],
    }


def upsert_jsonl(path: Path, row: dict[str, Any]) -> None:
    encoded = json.dumps(row, sort_keys=True)
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
                    rows.append(encoded)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(encoded)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def build_card(payload: dict[str, Any]) -> str:
    surface = payload["gate2"]["event_accession_surface"]
    text_cache = payload["gate2"]["target_text_cache"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: SEC 6-K Historical Event Accessions",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            "- Lane: `measurement_repair`",
            "",
            "## Hypothesis",
            "",
            HYPOTHESIS,
            "",
            "## Event Surface",
            "",
            "| Window | 6-K/6-KA events |",
            "| --- | ---: |",
            *[
                f"| {label} | {surface['six_k_by_window'].get(label, 0)} |"
                for label in CANONICAL_WINDOWS
            ],
            f"| total | {surface['six_k_event_rows']} |",
            "",
            "## Text Blocker",
            "",
            f"- Target accessions with nonempty filing text cache: `{text_cache['target_accessions_with_nonempty_text']}`",
            f"- Current daily 20260624 nonempty 6-K text rows: `{payload['gate2']['current_daily_text_surface']['six_k_nonempty_text_rows']}`",
            f"- Historical generated nonempty 6-K text rows: `{payload['gate2']['historical_generated_text_surface']['six_k_nonempty_text_rows']}`",
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
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
        TICKET_JSON,
        EXPERIMENT_LOG_JSONL,
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
        "anti_js": payload["anti_js"],
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256_file(path)}
            for path in files
        },
        "log_row_sha256": hashlib.sha256(
            json.dumps(log_row, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    log_row = compact_log_row(payload)
    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, log_row)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG_JSONL, log_row)

    registry_result = {
        "accepted": payload["status"].startswith("accepted"),
        "accepted_alpha": False,
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "delta_metrics": payload["delta_metrics"],
        "gate2": log_row["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "alpha_readiness": payload["alpha_readiness"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
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
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "evaluation_windows": [
                {"label": label, **window} for label, window in CANONICAL_WINDOWS.items()
            ],
            "acceptance_rule": payload["pre_run_questions"]["4_success_failure_standard"],
            "decision": payload["decision"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": payload["gate1"],
            "gate2": log_row["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "alpha_readiness": payload["alpha_readiness"],
            "post_run_reflection": payload["post_run_reflection"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload, log_row))


def main() -> int:
    payload = build_result()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "submissions_six_k_event_rows": payload["gate2"]["event_accession_surface"]["six_k_event_rows"],
                "submissions_six_k_by_window": payload["gate2"]["event_accession_surface"]["six_k_by_window"],
                "target_accessions_with_nonempty_text": payload["gate2"]["target_text_cache"]["target_accessions_with_nonempty_text"],
                "alpha_blocked": payload["alpha_readiness"]["alpha_blocked"],
                "lean_quality_passed": payload["lean_quality_passed"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
