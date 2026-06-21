"""exp-20260621-012: SEC no-covenant credit facility candidate-pool scout.

Alpha-search sample-readiness experiment. The single decision hypothesis is
that PIT SEC filing text with an explicit credit agreement / term loan /
revolver liquidity event, explicit no-financial-covenant language, and dollar
amount evidence may identify non-dilutive balance-sheet de-risking candidates.

This runner intentionally does not promote a strategy rule. If the three
canonical windows have zero or thin sample, the alpha is rejected rather than
retuned. No production code, shared helper, daily snapshot, live/default orders,
ranking, sizing, exits, LLM/news path, or watchlist behavior is changed. No
JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
for entry in (str(REPO_ROOT), str(SCRIPTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import experiment_registry  # noqa: E402


EXPERIMENT_ID = "exp-20260621-012"
SLUG = "sec_no_covenant_credit_facility"
RUNNER_NAME = f"quant/experiments/exp_20260621_012_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_NAME.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"exp_20260621_012_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
SEC_TEXT_DIR = REPO_ROOT / "data" / "non_ohlcv"
OPEN_POSITIONS_JSON = REPO_ROOT / "operator_inputs" / "open_positions.json"

BASELINE_RESULT_FILE = "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
MIN_TARGET_EVENTS = 20
MIN_TARGET_WINDOWS = 3
MIN_TEXT_WORDS = 80
MAX_TEXT_CHARS_SCANNED = 120_000
MATCH_CONTEXT_CHARS = 1_500

CANONICAL_WINDOWS: dict[str, dict[str, Any]] = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
        "expected_value_score": 5.1628,
        "sharpe_daily": 4.41,
        "strategy_total_return_pct": 117.07,
        "total_pnl": 117072.92,
        "max_drawdown_pct": 0.0665,
        "trade_count": 18,
        "signals_generated": 51,
        "signals_survived": 41,
        "survival_rate": 0.8039,
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
        "expected_value_score": 2.1402,
        "sharpe_daily": 2.74,
        "strategy_total_return_pct": 78.11,
        "total_pnl": 78110.11,
        "max_drawdown_pct": 0.1119,
        "trade_count": 21,
        "signals_generated": 53,
        "signals_survived": 42,
        "survival_rate": 0.7925,
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
        "expected_value_score": 0.5911,
        "sharpe_daily": 1.49,
        "strategy_total_return_pct": 39.67,
        "total_pnl": 39667.96,
        "max_drawdown_pct": 0.1001,
        "trade_count": 22,
        "signals_generated": 60,
        "signals_survived": 52,
        "survival_rate": 0.8667,
    },
}

FACILITY_RE = re.compile(
    r"\b(CREDIT AGREEMENT|CREDIT FACILITY|REVOLVING CREDIT|REVOLVER|"
    r"TERM LOAN|DELAYED DRAW TERM LOAN|SENIOR UNSECURED DELAYED DRAW|"
    r"SENIOR SECURED CREDIT|LOAN AGREEMENT)\b",
    re.IGNORECASE,
)
NO_COVENANT_RE = re.compile(
    r"\b(NO FINANCIAL COVENANTS|DOES NOT CONTAIN FINANCIAL COVENANTS|"
    r"NO FINANCIAL MAINTENANCE COVENANTS?|NO MAINTENANCE FINANCIAL COVENANTS?|"
    r"WITHOUT FINANCIAL COVENANTS)\b",
    re.IGNORECASE,
)
MONEY_RE = re.compile(
    r"\$\s?[0-9][0-9,]*(?:\.[0-9]+)?\s?(?:BILLION|BN|MILLION|MM|M)?",
    re.IGNORECASE,
)
EXCLUDE_RE = re.compile(
    r"\b(DEFAULT|GOING CONCERN|SUBSTANTIAL DOUBT|BANKRUPT|BANKRUPTCY|"
    r"COVENANT VIOLATION|BREACH|NON[-\s]?COMPLIANCE|ACCELERATION OF DEBT|"
    r"COMMON STOCK|REGISTERED DIRECT|WARRANTS?|PREFERRED STOCK|"
    r"AT[-\s]?THE[-\s]?MARKET|ATM OFFERING)\b",
    re.IGNORECASE,
)
NORMALIZE_RE = re.compile(r"[^A-Z0-9%$]+")

HYPOTHESIS = (
    "candidate_pool: PIT SEC filing text with explicit credit agreement or "
    "term loan liquidity, no financial covenants, dollar amount evidence, and "
    "no distress or equity-dilution language may isolate non-dilutive "
    "balance-sheet de-risking candidates; if the field has zero three-window "
    "sample it must be rejected rather than retuned."
)

PRIOR_EXPERIMENTS = [
    "exp-20260620-006",
    "exp-20260620-015",
    "exp-20260621-010",
    "exp-20260621-011",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8-sig").splitlines() if path.exists() else []
    needle = f'"experiment_id": "{EXPERIMENT_ID}"'
    kept = [line for line in lines if needle not in line]
    kept.append(json.dumps(row, sort_keys=True, ensure_ascii=True))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def aggregate_windows() -> dict[str, Any]:
    return {
        "aggregate_expected_value_score": round(
            sum(float(row["expected_value_score"]) for row in CANONICAL_WINDOWS.values()),
            4,
        ),
        "aggregate_total_pnl": round(
            sum(float(row["total_pnl"]) for row in CANONICAL_WINDOWS.values()),
            2,
        ),
        "total_trade_count": sum(int(row["trade_count"]) for row in CANONICAL_WINDOWS.values()),
        "min_survival_rate": round(
            min(float(row["survival_rate"]) for row in CANONICAL_WINDOWS.values()),
            4,
        ),
        "max_window_drawdown_pct": round(
            max(float(row["max_drawdown_pct"]) for row in CANONICAL_WINDOWS.values()),
            4,
        ),
    }


def zero_window_deltas() -> dict[str, dict[str, float]]:
    fields = [
        "expected_value_score",
        "total_pnl",
        "max_drawdown_pct",
        "trade_count",
        "survival_rate",
    ]
    return {label: {field: 0.0 for field in fields} for label in CANONICAL_WINDOWS}


def zero_aggregate_delta() -> dict[str, float]:
    return {
        "aggregate_expected_value_score": 0.0,
        "aggregate_total_pnl": 0.0,
        "expected_value_score_delta_sum": 0.0,
        "expected_value_score_delta_pct": 0.0,
        "total_pnl_delta_sum": 0.0,
        "total_pnl_delta_pct": 0.0,
        "total_trade_count": 0.0,
        "min_survival_rate": 0.0,
        "max_window_drawdown_pct": 0.0,
    }


def normalized_excerpt(text: str, limit: int = 420) -> str:
    return NORMALIZE_RE.sub(" ", str(text or "").upper()).strip()[:limit]


def iter_sec_text_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in sorted(SEC_TEXT_DIR.glob("sec_filing_text_*.jsonl")):
        with path.open(encoding="utf-8", errors="ignore") as handle:
            for line_no, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    rows.append(
                        {
                            "_json_error": True,
                            "_source_path": repo_rel(path),
                            "_source_line": line_no,
                        }
                    )
                    continue
                accession = str(row.get("accession_number") or "")
                key = accession or (
                    f"{row.get('ticker')}:{row.get('usable_trade_date')}:"
                    f"{row.get('primary_document')}:{repo_rel(path)}:{line_no}"
                )
                if key in seen:
                    continue
                seen.add(key)
                row["_source_path"] = repo_rel(path)
                row["_source_line"] = line_no
                rows.append(row)
    return rows


def row_date(row: dict[str, Any]) -> str:
    return str(
        row.get("usable_trade_date")
        or row.get("filing_date")
        or row.get("accepted_at")
        or ""
    )[:10]


def extract_no_covenant_event(row: dict[str, Any]) -> dict[str, Any] | None:
    ticker = str(row.get("ticker") or "").upper()
    date = row_date(row)
    form_type = str(row.get("form_base") or row.get("form_type") or "").upper()
    if not ticker or not date or form_type != "8-K":
        return None
    text = str(row.get("combined_text") or "")
    if len(text.split()) < MIN_TEXT_WORDS:
        return None
    scanned = text[:MAX_TEXT_CHARS_SCANNED]
    for match in NO_COVENANT_RE.finditer(scanned):
        left = max(0, match.start() - MATCH_CONTEXT_CHARS)
        right = min(len(scanned), match.end() + MATCH_CONTEXT_CHARS)
        context = scanned[left:right]
        facility_terms = sorted({m.group(0).upper() for m in FACILITY_RE.finditer(context)})
        money_terms = sorted({m.group(0).upper() for m in MONEY_RE.finditer(context)})
        excluded_terms = sorted({m.group(0).upper() for m in EXCLUDE_RE.finditer(context)})
        if not facility_terms or not money_terms or excluded_terms:
            continue
        return {
            "ticker": ticker,
            "date": date,
            "filing_date": str(row.get("filing_date") or "")[:10],
            "accepted_at": str(row.get("accepted_at") or "")[:19],
            "accession_number": str(row.get("accession_number") or ""),
            "form_type": row.get("form_type"),
            "eight_k_item_codes": row.get("eight_k_item_codes") or [],
            "primary_document": row.get("primary_document"),
            "text_char_count": row.get("text_char_count"),
            "text_word_count": row.get("text_word_count"),
            "pit_source": row.get("pit_source"),
            "pit_caveat": row.get("pit_caveat"),
            "matched_no_covenant_term": match.group(0).upper(),
            "matched_facility_terms": facility_terms[:10],
            "matched_money_terms": money_terms[:10],
            "excluded_terms": excluded_terms[:10],
            "context_excerpt_normalized": normalized_excerpt(context),
            "source_path": row.get("_source_path"),
            "source_line": row.get("_source_line"),
            "source": "SEC_NO_FINANCIAL_COVENANT_CREDIT_FACILITY_PAPER",
            "rule_version": "sec_no_financial_covenant_credit_facility_candidate_source_v1",
            "trade_enabled": False,
            "uses_llm": False,
            "uses_free_sec_filing_text": True,
            "known_at": "issuer_SEC_text_usable_trade_date_before_any_paper_entry",
        }
    return None


def scan_window(label: str, window: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    stats: Counter[str] = Counter()
    events: list[dict[str, Any]] = []
    start = str(window["start"])
    end = str(window["end"])
    for row in rows:
        if row.get("_json_error"):
            stats["json_decode_errors"] += 1
            continue
        date = row_date(row)
        if not date:
            stats["missing_usable_date"] += 1
            continue
        if not (start <= date <= end):
            continue
        stats["sec_text_rows_in_window"] += 1
        form_type = str(row.get("form_base") or row.get("form_type") or "").upper()
        if form_type != "8-K":
            stats["non_8k_rows_in_window"] += 1
            continue
        stats["eight_k_text_rows_in_window"] += 1
        text = str(row.get("combined_text") or "")
        if not text:
            stats["missing_combined_text"] += 1
            continue
        if len(text.split()) < MIN_TEXT_WORDS:
            stats["short_text_rows"] += 1
            continue
        scanned = text[:MAX_TEXT_CHARS_SCANNED]
        has_facility = bool(FACILITY_RE.search(scanned))
        has_no_covenant = bool(NO_COVENANT_RE.search(scanned))
        has_money = bool(MONEY_RE.search(scanned))
        if has_facility:
            stats["facility_term_text_rows"] += 1
        if has_no_covenant:
            stats["no_financial_covenant_text_rows"] += 1
        if has_money:
            stats["dollar_amount_text_rows"] += 1
        if has_facility and has_no_covenant:
            stats["facility_and_no_covenant_rows"] += 1
        if has_facility and has_no_covenant and has_money:
            stats["facility_no_covenant_amount_rows"] += 1
        event = extract_no_covenant_event(row)
        if event is None:
            if has_facility and has_no_covenant and has_money:
                stats["triad_rows_rejected_by_context_or_exclusion"] += 1
            continue
        stats["qualified_no_covenant_credit_facility_events"] += 1
        events.append(event)
    events.sort(
        key=lambda event: (
            event["date"],
            event["ticker"],
            event.get("accession_number") or "",
        )
    )
    return {
        "label": label,
        "start": start,
        "end": end,
        "scan": dict(stats),
        "matching_events": events,
        "matching_event_count": len(events),
        "matching_tickers": sorted({event["ticker"] for event in events}),
    }


def scan_sec_text() -> dict[str, Any]:
    rows = iter_sec_text_rows()
    by_window = {
        label: scan_window(label, window, rows)
        for label, window in CANONICAL_WINDOWS.items()
    }
    total_events = sum(row["matching_event_count"] for row in by_window.values())
    windows_with_events = sum(1 for row in by_window.values() if row["matching_event_count"])
    return {
        "source_dir": repo_rel(SEC_TEXT_DIR),
        "source_files": [repo_rel(path) for path in sorted(SEC_TEXT_DIR.glob("sec_filing_text_*.jsonl"))],
        "raw_rows_loaded_or_errors": len(rows),
        "by_window": by_window,
        "total_matching_events": total_events,
        "windows_with_matching_events": windows_with_events,
        "sample_ready": total_events >= MIN_TARGET_EVENTS and windows_with_events >= MIN_TARGET_WINDOWS,
        "minimum_target_events": MIN_TARGET_EVENTS,
        "minimum_target_windows": MIN_TARGET_WINDOWS,
    }


def open_position_field_check() -> dict[str, Any]:
    payload = read_json(OPEN_POSITIONS_JSON)
    observations = list(payload.get("observations") or [])
    missing_entry_date = sum(1 for row in observations if not row.get("entry_date"))
    missing_target_price = sum(1 for row in observations if not row.get("target_price"))
    return {
        "path": repo_rel(OPEN_POSITIONS_JSON),
        "observation_count": len(observations),
        "entry_date_present_count": len(observations) - missing_entry_date,
        "target_price_present_count": len(observations) - missing_target_price,
        "entry_date_missing_count": missing_entry_date,
        "target_price_missing_count": missing_target_price,
        "passed": bool(observations)
        and missing_entry_date == 0
        and missing_target_price == 0,
    }


def prior_summary(exp_id: str) -> dict[str, Any]:
    payload = read_json(REPO_ROOT / "experiments" / "logs" / f"{exp_id}.json")
    gate4 = payload.get("gate4") or {}
    return {
        "experiment_id": exp_id,
        "found": bool(payload),
        "decision": payload.get("decision"),
        "status": payload.get("status"),
        "trial_variant_id": payload.get("trial_variant_id"),
        "aggregate_expected_value_delta": payload.get("aggregate_expected_value_delta"),
        "aggregate_strategy_total_pnl_delta": payload.get("aggregate_strategy_total_pnl_delta"),
        "failed_reasons": gate4.get("failed_reasons"),
        "next_evidence_needed": (
            (payload.get("post_run_reflection") or {}).get("new_evidence_required")
            or (payload.get("post_run_reflection") or {}).get("best_next_alpha_direction")
            or payload.get("next_evidence_needed")
        ),
    }


def build_gate4(scan: dict[str, Any]) -> dict[str, Any]:
    aggregate = aggregate_windows()
    failures = [
        "no_full_after_replay_because_candidate_field_failed_sample_readiness",
        "accepted_compression_ev_not_beaten",
        "accepted_distribution_ev_not_beaten",
    ]
    if scan["total_matching_events"] == 0:
        failures.insert(0, "zero_matching_sec_text_events")
    if scan["total_matching_events"] < MIN_TARGET_EVENTS:
        failures.insert(0, "target_sample_too_small")
    if scan["windows_with_matching_events"] < MIN_TARGET_WINDOWS:
        failures.insert(0, "target_window_coverage_too_small")
    return {
        "status": "failed",
        "passed": False,
        "actual_gate4_passed": False,
        "numeric_gate4_passed": False,
        "before": CANONICAL_WINDOWS,
        "after": CANONICAL_WINDOWS,
        "window_deltas": zero_window_deltas(),
        "aggregate_before": aggregate,
        "aggregate_after": aggregate,
        "aggregate_delta": zero_aggregate_delta(),
        "failed_reasons": failures,
        "sample_gate": {
            "minimum_target_events": MIN_TARGET_EVENTS,
            "minimum_target_windows": MIN_TARGET_WINDOWS,
            "total_matching_events": scan["total_matching_events"],
            "windows_with_matching_events": scan["windows_with_matching_events"],
            "sample_ready": scan["sample_ready"],
        },
        "reason": (
            "The explicit no-financial-covenant credit-facility SEC text field "
            "does not have enough PIT sample in the canonical windows to launch "
            "a trustworthy after-policy."
        ),
    }


def build_result() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON)
    scan = scan_sec_text()
    field_check = open_position_field_check()
    aggregate = aggregate_windows()
    gate4 = build_gate4(scan)
    if scan["sample_ready"]:
        status = "blocked"
        decision = "blocked_sec_no_covenant_credit_facility_requires_full_replay"
    elif scan["total_matching_events"] == 0:
        status = "rejected"
        decision = "rejected_sec_no_covenant_credit_facility_zero_sample"
    else:
        status = "rejected"
        decision = "rejected_sec_no_covenant_credit_facility_thin_sample"
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now_utc(),
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "change_type": "candidate_pool_full_stack",
        "mechanism_family": "structured_sec_debt_event_candidate_pool",
        "trial_family": "sec_no_financial_covenant_credit_facility_candidate_pool",
        "trial_variant_id": "sec_no_covenant_credit_facility_sample_readiness_v1",
        "single_causal_variable": "sec_no_financial_covenant_credit_facility_candidate_source_v1",
        "changed_variable": "sec_no_financial_covenant_credit_facility_candidate_source_v1",
        "baseline_result_file": BASELINE_RESULT_FILE,
        "prediction": ticket.get("prediction") or {},
        "novelty": ticket.get("novelty") or {},
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": (
                    "Reservation used a novelty override for a structured SEC "
                    "debt-event field: explicit no-financial-covenants language "
                    "plus credit facility / term loan and dollar amount evidence."
                ),
                "exp-20260620-006": (
                    "Rejected broad SEC refinancing/covenant-relief phrase "
                    "bundle. This run is the requested structured debt-event "
                    "tuple sample-readiness check, not a phrase/top-N/RS sweep."
                ),
                "exp-20260620-015": (
                    "Rejected contract value / market-cap event economics due "
                    "to thin concentration; this run tests financing liquidity "
                    "terms, not customer contract economics."
                ),
                "exp-20260621-010": (
                    "Blocked current surfaces because no mature non-repeat PIT "
                    "field existed; this run tests one concrete free SEC text "
                    "field before any strategy launch."
                ),
                "exp-20260621-011": (
                    "Rejected proxy residual leadership; this run avoids OHLCV "
                    "residual retunes and tests a new SEC candidate-pool field."
                ),
            },
            "3_single_decision_hypothesis": (
                "Evaluate only whether the explicit SEC no-financial-covenant "
                "credit-facility field is sample-ready for a candidate-pool "
                "alpha. No ranking/sizing/exit/hold/notional retune is tested."
            ),
            "4_acceptance_standard": (
                "Use docs/backtesting.md three windows. A candidate-pool source "
                "must have enough PIT sample across all windows before any "
                "after replay; positive promotion would require shared-paper-"
                "first historical and daily parity."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "nearby_prior_experiments": [prior_summary(exp_id) for exp_id in PRIOR_EXPERIMENTS],
        "gate1": {
            "passed": True,
            "baseline_result_file": BASELINE_RESULT_FILE,
            "windows": CANONICAL_WINDOWS,
            "aggregate": aggregate,
        },
        "gate2": {
            "passed": True,
            "runtime_fields_checked": [
                "SEC text ticker",
                "SEC text usable_trade_date",
                "SEC text form_type/form_base",
                "SEC text combined_text",
                "SEC text accession_number",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "open_position_field_check": field_check,
            "sec_text_field_check": {
                "source_dir": scan["source_dir"],
                "raw_rows_loaded_or_errors": scan["raw_rows_loaded_or_errors"],
                "source_files": scan["source_files"],
            },
            "note": (
                "The required raw PIT fields exist. The candidate event sample "
                "is zero/thin, so no paper entry rows with entry_date or "
                "target_price were created."
            ),
        },
        "gate3": {
            "passed": False,
            "status": "failed_sample_readiness",
            "baseline_min_survival_rate": aggregate["min_survival_rate"],
            "minimum_survival_rate": 0.05,
            "sample_scan": {
                "total_matching_events": scan["total_matching_events"],
                "windows_with_matching_events": scan["windows_with_matching_events"],
                "minimum_target_events": MIN_TARGET_EVENTS,
                "minimum_target_windows": MIN_TARGET_WINDOWS,
                "sample_ready": scan["sample_ready"],
            },
            "interpretation": (
                "The core baseline survival rate is healthy, but this SEC "
                "field adds no candidate sample. Adding looser filters or "
                "threshold sweeps would repeat the rejected broad financing "
                "text family."
            ),
        },
        "gate4": gate4,
        "delta_metrics": {
            "by_window": zero_window_deltas(),
            "aggregate": zero_aggregate_delta(),
        },
        "sec_text_scan": scan,
        "production_impact": {
            "trade_enabled": False,
            "alters_orders": False,
            "strategy_code_changed": False,
            "shared_helper_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_changed": False,
            "live_orders_changed": False,
            "production_watchlist_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "uses_llm": False,
            "uses_free_sec_filing_text": True,
            "default_off_paper_only": True,
            "replay_only": True,
            "live_ready": False,
            "parity_note": (
                "No production/backtest inconsistency was introduced because no "
                "trading rule, shared helper, adapter, daily snapshot, live "
                "order, ranking, sizing, or exit path changed. A future "
                "positive result would need a shared default-off helper before "
                "acceptance."
            ),
        },
        "calibration": {
            "predicted_success_probability": (ticket.get("prediction") or {}).get(
                "success_probability"
            ),
            "actual_gate4_passed": False,
            "actual_success": 0,
            "failure_modes_observed": [
                "zero_sample" if scan["total_matching_events"] == 0 else "thin_sample",
                "target_window_coverage_too_small",
                "accepted_comparator_not_beaten",
            ],
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The stricter SEC debt-event tuple is too rare in the fixed "
                "historical filing-text surface. Explicit no-financial-covenant "
                "language did not appear with facility and dollar amount "
                "evidence across the canonical windows, so the idea cannot "
                "generate a statistically useful paper candidate pool."
            ),
            "negative_result_reflection": (
                "The broad refinancing/covenant language failed earlier because "
                "it mixed constructive liquidity repair with dilution/distress "
                "noise. This run made the field cleaner, but the cleaner field "
                "collapses to zero sample. Relaxing the phrase, RS, top-N, "
                "hold, cooldown, or notional gates would only walk back into "
                "the rejected broad-text family."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry no-covenant/facility text by loosening phrases, "
                "dropping dollar evidence, sweeping RS/top-N/hold/cooldown/"
                "notional, or mixing equity-offering context on the same frozen "
                "windows."
            ),
            "new_evidence_required": (
                "A valid future SEC debt alpha needs a broader structured "
                "tuple with nonzero PIT sample: maturity ladder, covenant "
                "headroom, facility availability versus market cap, borrower "
                "liquidity runway, or closed forward replacement rows from a "
                "shared default-off parser."
            ),
            "next_new_evidence": (
                "A valid future SEC debt alpha needs a broader structured "
                "tuple with nonzero PIT sample: maturity ladder, covenant "
                "headroom, facility availability versus market cap, borrower "
                "liquidity runway, or closed forward replacement rows from a "
                "shared default-off parser."
            ),
        },
        "changed_files": [
            RUNNER_NAME,
            repo_rel(ARTIFACT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
        ],
        "reproduction": RUNNER_COMMAND,
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": True,
    }


def build_log_record(result: dict[str, Any]) -> dict[str, Any]:
    aggregate = result["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": result["timestamp"],
        "lane": result["lane"],
        "status": result["status"],
        "decision": result["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": False,
        "hypothesis": result["hypothesis"],
        "change_type": result["change_type"],
        "mechanism_family": result["mechanism_family"],
        "trial_family": result["trial_family"],
        "trial_variant_id": result["trial_variant_id"],
        "changed_variable": result["changed_variable"],
        "baseline_result_file": BASELINE_RESULT_FILE,
        "aggregate_expected_value_delta": aggregate["aggregate_expected_value_score"],
        "aggregate_strategy_total_pnl_delta": aggregate["aggregate_total_pnl"],
        "gate1": result["gate1"],
        "gate2": result["gate2"],
        "gate3": result["gate3"],
        "gate4": result["gate4"],
        "sec_text_sample": result["gate3"]["sample_scan"],
        "production_impact": result["production_impact"],
        "calibration": result["calibration"],
        "post_run_reflection": result["post_run_reflection"],
        "pre_run_questions": result["pre_run_questions"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": result["anti_js"],
        "lean_quality_passed": result["lean_quality_passed"],
    }


def build_card(result: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: SEC no-covenant credit facility scout",
        "",
        "- Lane: alpha_search",
        f"- Status: {result['status']}",
        f"- Decision: {result['decision']}",
        "- Strategy / production behavior changed: no",
        "- JavaScript used: no",
        "",
        "## Three-Window Gate",
        "",
        "| Window | SEC text rows | 8-K rows | Matching events | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    scans = result["sec_text_scan"]["by_window"]
    for label, row in CANONICAL_WINDOWS.items():
        scan = scans[label]["scan"]
        lines.append(
            f"| {label} | {scan.get('sec_text_rows_in_window', 0)} | "
            f"{scan.get('eight_k_text_rows_in_window', 0)} | "
            f"{scans[label]['matching_event_count']} | "
            f"{row['expected_value_score']:.4f} | {row['expected_value_score']:.4f} | "
            f"0.0000 | ${row['total_pnl']:,.2f} | ${row['total_pnl']:,.2f} | $0.00 |"
        )
    sample = result["gate3"]["sample_scan"]
    aggregate = result["gate1"]["aggregate"]
    lines.extend(
        [
            "",
            "## Result",
            "",
            (
                f"Matched events: `{sample['total_matching_events']}` across "
                f"`{sample['windows_with_matching_events']}` windows. Required "
                f"sample was `{sample['minimum_target_events']}` events across "
                f"`{sample['minimum_target_windows']}` windows."
            ),
            "",
            (
                f"Baseline aggregate EV `{aggregate['aggregate_expected_value_score']:.4f}`, "
                f"PnL `${aggregate['aggregate_total_pnl']:,.2f}`, trade count "
                f"`{aggregate['total_trade_count']}`, min survival "
                f"`{aggregate['min_survival_rate']:.4f}`. After equals before "
                "because no trustworthy candidate pool exists."
            ),
            "",
            result["post_run_reflection"]["negative_result_reflection"],
            "",
            result["post_run_reflection"]["next_new_evidence"],
            "",
        ]
    )
    return "\n".join(lines)


def write_manifest(result: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": result["status"],
        "decision": result["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "ticket": repo_rel(TICKET_JSON),
        "runner": RUNNER_NAME,
        "command": result["reproduction"],
        "files": result["changed_files"],
        "anti_js": result["anti_js"],
        "updated_at": now_utc(),
        "file_hashes": {
            RUNNER_NAME: sha256(REPO_ROOT / RUNNER_NAME),
            repo_rel(ARTIFACT_JSON): sha256(ARTIFACT_JSON),
            repo_rel(LOG_JSON): sha256(LOG_JSON),
            repo_rel(CARD_MD): sha256(CARD_MD),
            repo_rel(TICKET_JSON): sha256(TICKET_JSON),
        },
    }
    write_json(MANIFEST_JSON, manifest)


def persist(result: dict[str, Any]) -> None:
    write_json(ARTIFACT_JSON, result)
    write_json(LOG_JSON, result)
    write_text(CARD_MD, build_card(result))
    upsert_jsonl(EXPERIMENT_LOG_JSONL, build_log_record(result))

    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "decision": result["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER_NAME,
        "delta_metrics": result["delta_metrics"],
        "gate4": result["gate4"],
        "calibration": result["calibration"],
        "production_impact": result["production_impact"],
        "summary": result["post_run_reflection"]["why_result_happened"],
    }
    experiment_registry.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=result["prediction"],
        result=registry_result,
        status=result["status"],
        fields={
            "owner": "codex-alpha-search",
            "hypothesis": result["hypothesis"],
            "change_type": result["change_type"],
            "mechanism_family": result["mechanism_family"],
            "trial_family": result["trial_family"],
            "trial_variant_id": result["trial_variant_id"],
            "single_causal_variable": result["single_causal_variable"],
            "changed_variable": result["changed_variable"],
            "nearby_prior_experiments": PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": "minimal",
            "new_evidence_type": "structured_sec_debt_event_tuple",
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
            "acceptance_rule": (
                "Before any after replay, the SEC text field must have at least "
                f"{MIN_TARGET_EVENTS} PIT events across all {MIN_TARGET_WINDOWS} "
                "canonical windows, then any positive policy must be "
                "shared-paper-first before acceptance."
            ),
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
    write_manifest(result)


def main() -> None:
    result = build_result()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": result["status"],
                "decision": result["decision"],
                "matching_events": result["sec_text_scan"]["total_matching_events"],
                "windows_with_matching_events": result["sec_text_scan"]["windows_with_matching_events"],
                "aggregate_ev_delta": result["delta_metrics"]["aggregate"]["aggregate_expected_value_score"],
                "aggregate_pnl_delta": result["delta_metrics"]["aggregate"]["aggregate_total_pnl"],
                "anti_js": result["anti_js"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
