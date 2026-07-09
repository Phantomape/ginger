"""exp-20260708-003: SEC Item 5.02 leadership-quality text gate.

This alpha search reopens the rejected SEC Item 5.02 positive-reaction family
only on the evidence axis named in exp-20260529-019: a filing-body text field
that separates clear C-suite appointment / succession events from abrupt
departure risk. The paper sleeve remains replay-only and default-off.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260529_015_sec_fd_other_8k_positive_reaction_candidate_pool as fd_framework
import exp_20260529_019_sec_item502_positive_reaction_candidate_pool as item502_prior


REPO_ROOT = Path(__file__).resolve().parents[2]
framework = item502_prior.framework

EXPERIMENT_ID = "exp-20260708-003"
STEM = "sec_item502_leadership_quality_text"
TRIAL_FAMILY = "sec_item502_leadership_quality_text_candidate_pool"
CHANGED_VARIABLE = "sec_item502_leadership_quality_text_gate_v1"
RULE_VERSION = "sec_item502_leadership_quality_text_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260708_003_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

SEC_TEXT_GLOB = REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_text_*.jsonl"
SEC_EVENTS_GLOB = REPO_ROOT / "data" / "non_ohlcv" / "sec_filing_events_*.jsonl"

TARGET_ITEM_CODES = {"5.02"}
EXCLUDED_ITEM_CODES = item502_prior.EXCLUDED_ITEM_CODES
MOVING_AVERAGE_DAYS = item502_prior.MOVING_AVERAGE_DAYS
RELATIVE_STRENGTH_DAYS = item502_prior.RELATIVE_STRENGTH_DAYS
AVG_DOLLAR_VOLUME_DAYS = item502_prior.AVG_DOLLAR_VOLUME_DAYS
MIN_CLOSE = item502_prior.MIN_CLOSE
MIN_AVG_DOLLAR_VOLUME_20D = item502_prior.MIN_AVG_DOLLAR_VOLUME_20D
MIN_RS20_VS_SPY = item502_prior.MIN_RS20_VS_SPY
MIN_SIGNAL_EXCESS_RETURN_1D_VS_SPY = item502_prior.MIN_SIGNAL_EXCESS_RETURN_1D_VS_SPY
MIN_SIGNAL_CLOSE_LOCATION = item502_prior.MIN_SIGNAL_CLOSE_LOCATION
MAX_PAPER_TRADES_PER_DAY = item502_prior.MAX_PAPER_TRADES_PER_DAY
MIN_TARGET_TRADES = item502_prior.MIN_TARGET_TRADES
MIN_TARGET_WINDOWS = item502_prior.MIN_TARGET_WINDOWS
MAX_DRAWDOWN_WORSE = item502_prior.MAX_DRAWDOWN_WORSE
MAX_SINGLE_POSITIVE_SHARE = item502_prior.MAX_SINGLE_POSITIVE_SHARE
MAX_POSITIVE_HHI = item502_prior.MAX_POSITIVE_HHI

_TEXT_ROWS_CACHE: list[dict[str, Any]] | None = None
_EVENT_METADATA_CACHE: dict[str, dict[str, Any]] | None = None
_TEXT_SOURCE_STATS: dict[str, Any] | None = None


EXEC_ROLE_RE = re.compile(
    r"\b("
    r"chief executive officer|chief financial officer|chief operating officer|"
    r"chief accounting officer|principal executive officer|"
    r"principal financial officer|ceo|cfo|coo|president"
    r")\b",
    re.I,
)
EXEC_APPOINT_RE = re.compile(
    r"\b("
    r"appoint(?:ed|ment)?|named|elected|promoted|will become|has become|"
    r"assume(?:d)?|designat(?:ed|ion)"
    r")\b",
    re.I,
)
SUCCESSION_RE = re.compile(
    r"\b(successor|succeed(?:s|ed)?|succession|transition|replacement|effective)\b",
    re.I,
)
ABRUPT_DEPARTURE_RE = re.compile(
    r"\b("
    r"resign(?:ed|ation)?|depart(?:ed|ure)?|terminated|removed|ceased|"
    r"separation|step(?:ped)? down|death|deceased"
    r")\b",
    re.I,
)
BOARD_APPOINTMENT_RE = re.compile(
    r"\b(appoint(?:ed|ment)?|elected|join(?:ed)?|named)\b.{0,180}\b(board of directors|board)\b|"
    r"\b(board of directors|board)\b.{0,180}\b(appoint(?:ed|ment)?|elected|join(?:ed)?|named)\b",
    re.I | re.S,
)
DIRECT_EXEC_APPOINTMENT_RE = re.compile(
    r"\b(appoint(?:ed|ment)?|named|elected|promoted|will become|has become|assume(?:d)?|designat(?:ed|ion))\b"
    r".{0,220}\b(chief executive officer|chief financial officer|chief operating officer|"
    r"chief accounting officer|principal executive officer|principal financial officer|"
    r"ceo|cfo|coo|president)\b|"
    r"\b(chief executive officer|chief financial officer|chief operating officer|"
    r"chief accounting officer|principal executive officer|principal financial officer|"
    r"ceo|cfo|coo|president)\b.{0,220}"
    r"\b(appoint(?:ed|ment)?|named|elected|promoted|will become|has become|assume(?:d)?|designat(?:ed|ion))\b",
    re.I | re.S,
)
EVIDENCE_NEEDLES_RE = re.compile(
    r"(?i)(chief executive officer|chief financial officer|ceo|cfo|coo|"
    r"president|appointed|appointment|named|elected|promoted|successor|"
    r"succession|transition|resigned|resignation|departed|departure|"
    r"terminated|removed|ceased|board of directors)"
)


def _patch_framework() -> None:
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.BEFORE_AGG_JSON = BEFORE_AGG_JSON
    framework.AFTER_AGG_JSON = AFTER_AGG_JSON
    framework.LOG_JSON = LOG_JSON
    framework.TICKET_JSON = TICKET_JSON
    framework.DOC_TICKET_JSON = TICKET_JSON
    framework.ARTIFACT_MD = ARTIFACT_MD
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._gate4 = fd_framework._gate4
    framework._build_report = _build_report


def _load_event_metadata_by_accession() -> dict[str, dict[str, Any]]:
    global _EVENT_METADATA_CACHE
    if _EVENT_METADATA_CACHE is not None:
        return _EVENT_METADATA_CACHE

    metadata: dict[str, dict[str, Any]] = {}
    for path in sorted(SEC_EVENTS_GLOB.parent.glob(SEC_EVENTS_GLOB.name)):
        if path.name.startswith("sec_filing_events_6k") or path.stat().st_size == 0:
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                accession = str(row.get("accession_number") or "").strip()
                if not accession:
                    continue
                metadata[accession] = {
                    "accession_number": accession,
                    "ticker": str(row.get("ticker") or "").upper().strip() or None,
                    "usable_trade_date": str(row.get("usable_trade_date") or "")[:10] or None,
                    "accepted_at": row.get("accepted_at"),
                    "filing_date": str(row.get("filing_date") or "")[:10] or None,
                    "form_type": row.get("form_type"),
                    "form_base": row.get("form_base"),
                    "eight_k_item_codes": row.get("eight_k_item_codes") or [],
                    "is_amendment": bool(row.get("is_amendment")),
                    "pit_safe_flag": row.get("pit_safe_flag"),
                    "archive_url": row.get("archive_url"),
                    "pit_source": row.get("pit_source"),
                    "event_source_file": path.name,
                }
    _EVENT_METADATA_CACHE = metadata
    return metadata


def _evidence_snippets(text: str, max_snippets: int = 8, radius: int = 360) -> list[str]:
    snippets: list[str] = []
    for match in EVIDENCE_NEEDLES_RE.finditer(text):
        start = max(0, match.start() - radius)
        end = min(len(text), match.end() + radius)
        snippet = " ".join(text[start:end].split())
        if snippet and snippet not in snippets:
            snippets.append(snippet)
        if len(snippets) >= max_snippets:
            break
    return snippets


def _classify_leadership_text(text: str) -> dict[str, Any]:
    snippets = _evidence_snippets(text)
    evidence_blob = " ".join(snippets) if snippets else " ".join(text[:5000].split())
    has_exec_role = bool(EXEC_ROLE_RE.search(evidence_blob))
    has_direct_exec_appointment = bool(DIRECT_EXEC_APPOINTMENT_RE.search(evidence_blob))
    has_appointment = bool(EXEC_APPOINT_RE.search(evidence_blob))
    has_succession = bool(SUCCESSION_RE.search(evidence_blob))
    has_abrupt_departure = bool(ABRUPT_DEPARTURE_RE.search(evidence_blob))
    has_board_appointment = bool(BOARD_APPOINTMENT_RE.search(evidence_blob))

    if has_direct_exec_appointment and has_succession and not has_abrupt_departure:
        label = "clear_exec_appointment_succession"
        quality_score = 3.0
        admission = True
    elif has_direct_exec_appointment and not has_abrupt_departure and not has_board_appointment:
        label = "clear_exec_appointment"
        quality_score = 2.5
        admission = True
    elif has_exec_role and has_appointment and has_abrupt_departure and has_succession:
        label = "planned_transition_mixed_departure"
        quality_score = 1.0
        admission = False
    elif has_exec_role and has_abrupt_departure:
        label = "exec_departure_risk"
        quality_score = -2.0
        admission = False
    elif has_board_appointment:
        label = "board_appointment_not_csuite"
        quality_score = 0.0
        admission = False
    else:
        label = "other_item502_text"
        quality_score = 0.0
        admission = False

    return {
        "admission": admission,
        "label": label,
        "quality_score": quality_score,
        "has_exec_role": has_exec_role,
        "has_direct_exec_appointment": has_direct_exec_appointment,
        "has_appointment": has_appointment,
        "has_succession": has_succession,
        "has_abrupt_departure": has_abrupt_departure,
        "has_board_appointment": has_board_appointment,
        "evidence_snippets": snippets[:3],
    }


def _load_sec_item502_text_events() -> list[dict[str, Any]]:
    global _TEXT_ROWS_CACHE, _TEXT_SOURCE_STATS
    if _TEXT_ROWS_CACHE is not None:
        return _TEXT_ROWS_CACHE

    event_metadata = _load_event_metadata_by_accession()
    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    stats: Counter[str] = Counter()
    raw_classification_counts: Counter[str] = Counter()
    source_files: Counter[str] = Counter()

    for path in sorted(SEC_TEXT_GLOB.parent.glob(SEC_TEXT_GLOB.name)):
        if path.stat().st_size == 0:
            continue
        source_files[path.name] += 1
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    stats["text_json_decode_error"] += 1
                    continue
                accession = str(row.get("accession_number") or "").strip()
                metadata = event_metadata.get(accession)
                if not accession or metadata is None:
                    stats["missing_event_metadata"] += 1
                    continue
                ticker = str(metadata.get("ticker") or row.get("ticker") or "").upper().strip()
                usable_trade_date = str(
                    metadata.get("usable_trade_date") or row.get("usable_trade_date") or ""
                )[:10]
                if not ticker or not usable_trade_date:
                    stats["missing_ticker_or_usable_trade_date"] += 1
                    continue
                form = str(metadata.get("form_base") or metadata.get("form_type") or "").upper()
                if form != "8-K":
                    stats["not_8k"] += 1
                    continue
                item_codes = {
                    str(code).strip()
                    for code in (metadata.get("eight_k_item_codes") or row.get("eight_k_item_codes") or [])
                    if str(code).strip()
                }
                if not item_codes.intersection(TARGET_ITEM_CODES):
                    stats["not_item502"] += 1
                    continue
                if item_codes.intersection(EXCLUDED_ITEM_CODES):
                    stats["excluded_item_code"] += 1
                    continue
                if metadata.get("pit_safe_flag") is not True:
                    stats["not_pit_safe"] += 1
                    continue
                if bool(metadata.get("is_amendment")):
                    stats["amendment"] += 1
                    continue
                text = str(row.get("combined_text") or "")
                if str(row.get("status") or "") != "ok" or not text:
                    stats["missing_text"] += 1
                    continue

                classification = _classify_leadership_text(text)
                raw_classification_counts[str(classification["label"])] += 1
                key = (ticker, accession, usable_trade_date)
                deduped[key] = {
                    "ticker": ticker,
                    "usable_trade_date": usable_trade_date,
                    "accession_number": accession,
                    "accepted_at": metadata.get("accepted_at") or row.get("accepted_at"),
                    "filing_date": metadata.get("filing_date") or row.get("filing_date"),
                    "form_type": metadata.get("form_type") or row.get("form_type"),
                    "form_base": metadata.get("form_base") or row.get("form_base"),
                    "eight_k_item_codes": sorted(item_codes),
                    "archive_url": metadata.get("archive_url"),
                    "pit_source": metadata.get("pit_source") or row.get("pit_source"),
                    "event_source_file": metadata.get("event_source_file"),
                    "text_source_file": path.name,
                    "text_word_count": row.get("text_word_count"),
                    "text_char_count": row.get("text_char_count"),
                    "classification": classification,
                    "known_at": (
                        "after_sec_8k_usable_trade_date_close_before_next_open_paper_entry"
                    ),
                    "pit_caveat": row.get("pit_caveat")
                    or "SEC public archive text fetched after the fact and keyed by usable_trade_date.",
                }

    rows = sorted(
        deduped.values(),
        key=lambda row: (
            str(row["usable_trade_date"]),
            str(row["ticker"]),
            str(row["accession_number"]),
        ),
    )
    deduped_classification_counts = Counter(
        str(row["classification"]["label"]) for row in rows
    )
    _TEXT_SOURCE_STATS = {
        "unique_item502_text_rows": len(rows),
        "admitted_text_rows": sum(1 for row in rows if row["classification"]["admission"]),
        "classification_counts": dict(sorted(deduped_classification_counts.items())),
        "raw_pre_dedupe_classification_counts": dict(
            sorted(raw_classification_counts.items())
        ),
        "load_reject_counts": dict(sorted(stats.items())),
        "text_source_file_count": len(source_files),
        "text_source_glob": framework.base._repo_rel(SEC_TEXT_GLOB),
        "event_source_glob": framework.base._repo_rel(SEC_EVENTS_GLOB),
    }
    _TEXT_ROWS_CACHE = rows
    return _TEXT_ROWS_CACHE


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = framework.ohlcv_helper._baseline_entries(before_result)
    dates = {
        date
        for date in framework.ohlcv_helper._trading_dates(snapshot)
        if str(cfg["start"]) <= date <= str(cfg["end"])
    }
    spy_rows = framework.ohlcv_helper._series(snapshot, "SPY")
    spy_index = framework.ohlcv_helper._row_index(spy_rows)
    events = [
        event for event in _load_sec_item502_text_events() if event["usable_trade_date"] in dates
    ]
    candidates: list[dict[str, Any]] = []
    audit: Counter[str] = Counter()
    seen_ticker_dates: set[tuple[str, str]] = set()
    label_counts: Counter[str] = Counter()

    for event in events:
        classification = event["classification"]
        label_counts[str(classification["label"])] += 1
        if not classification["admission"]:
            audit[f"text_rejected_{classification['label']}"] += 1
            continue

        ticker = str(event["ticker"]).upper()
        signal_date = str(event["usable_trade_date"])
        if ticker in framework.EXCLUDED_TICKERS:
            audit["excluded_ticker"] += 1
            continue
        rows = framework.ohlcv_helper._series(snapshot, ticker)
        idx = framework.ohlcv_helper._row_index(rows).get(signal_date)
        spy_idx = spy_index.get(signal_date)
        if (
            idx is None
            or spy_idx is None
            or idx < max(MOVING_AVERAGE_DAYS, RELATIVE_STRENGTH_DAYS)
            or spy_idx < RELATIVE_STRENGTH_DAYS
        ):
            audit["missing_ohlcv_or_history"] += 1
            continue

        close = framework.ohlcv_helper._value(rows[idx], "Close")
        volume = framework.ohlcv_helper._value(rows[idx], "Volume")
        if close is None or volume is None or float(close) < MIN_CLOSE:
            audit["missing_or_low_price_volume"] += 1
            continue

        avg_dollar_volume = fd_framework._avg_dollar_volume(
            rows,
            idx,
            AVG_DOLLAR_VOLUME_DAYS,
        )
        if avg_dollar_volume is None or avg_dollar_volume < MIN_AVG_DOLLAR_VOLUME_20D:
            audit["low_avg_dollar_volume"] += 1
            continue

        ma50 = framework._prior_average(rows, idx, MOVING_AVERAGE_DAYS, "Close")
        if ma50 is None or float(close) <= float(ma50):
            audit["below_50d_trend"] += 1
            continue

        ret20 = framework._close_return(rows, idx - RELATIVE_STRENGTH_DAYS, idx)
        spy_ret20 = framework._close_return(
            spy_rows,
            spy_idx - RELATIVE_STRENGTH_DAYS,
            spy_idx,
        )
        if ret20 is None or spy_ret20 is None:
            audit["missing_rs20"] += 1
            continue
        rs20_vs_spy = ret20 - spy_ret20
        if rs20_vs_spy < MIN_RS20_VS_SPY:
            audit["weak_rs20_vs_spy"] += 1
            continue

        signal_return_1d = fd_framework._daily_return(rows, idx)
        spy_return_1d = fd_framework._daily_return(spy_rows, spy_idx)
        if signal_return_1d is None or spy_return_1d is None:
            audit["missing_signal_return"] += 1
            continue
        signal_excess_return = signal_return_1d - spy_return_1d
        if signal_excess_return < MIN_SIGNAL_EXCESS_RETURN_1D_VS_SPY:
            audit["weak_signal_day_excess_return"] += 1
            continue

        signal_close_location = fd_framework._close_location(rows[idx])
        if signal_close_location is None or signal_close_location < MIN_SIGNAL_CLOSE_LOCATION:
            audit["weak_close_location"] += 1
            continue

        key = (ticker, signal_date)
        if key in seen_ticker_dates:
            audit["duplicate_ticker_date_item502_text"] += 1
            continue
        seen_ticker_dates.add(key)

        ab_entries = entries_by_date.get(signal_date, [])
        score = (
            float(classification["quality_score"])
            + rs20_vs_spy
            + signal_excess_return
            + (signal_close_location * 0.10)
            + min(math.log10(max(avg_dollar_volume, 1.0)) / 100.0, 0.10)
        )
        candidates.append(
            {
                "date": signal_date,
                "ticker": ticker,
                "strategy": STEM,
                "rule_version": RULE_VERSION,
                "sec_accession_number": event.get("accession_number"),
                "sec_accepted_at": event.get("accepted_at"),
                "sec_filing_date": event.get("filing_date"),
                "sec_form_type": event.get("form_type"),
                "sec_8k_item_codes": event.get("eight_k_item_codes"),
                "sec_archive_url": event.get("archive_url"),
                "sec_pit_source": event.get("pit_source"),
                "sec_event_source_file": event.get("event_source_file"),
                "sec_text_source_file": event.get("text_source_file"),
                "sec_text_word_count": event.get("text_word_count"),
                "leadership_quality_label": classification["label"],
                "leadership_quality_score": framework.base._round(
                    classification["quality_score"],
                    4,
                ),
                "leadership_text_evidence": classification["evidence_snippets"],
                "leadership_has_exec_role": classification["has_exec_role"],
                "leadership_has_direct_exec_appointment": classification[
                    "has_direct_exec_appointment"
                ],
                "leadership_has_succession": classification["has_succession"],
                "leadership_has_abrupt_departure": classification["has_abrupt_departure"],
                "leadership_has_board_appointment": classification["has_board_appointment"],
                "close": framework.base._round(close, 4),
                "volume": framework.base._round(volume, 2),
                "ma50": framework.base._round(ma50, 4),
                "avg_dollar_volume_20d": framework.base._round(avg_dollar_volume, 2),
                "ret20": framework.base._round(ret20, 6),
                "spy_ret20": framework.base._round(spy_ret20, 6),
                "rs20_vs_spy": framework.base._round(rs20_vs_spy, 6),
                "signal_return_1d": framework.base._round(signal_return_1d, 6),
                "spy_return_1d": framework.base._round(spy_return_1d, 6),
                "signal_excess_return_1d_vs_spy": framework.base._round(
                    signal_excess_return,
                    6,
                ),
                "signal_close_location": framework.base._round(signal_close_location, 6),
                "item502_text_candidate_score": framework.base._round(score, 6),
                "same_day_ab_entry_count": len(ab_entries),
                "same_day_ab_overlap": bool(ab_entries),
                "same_ticker_ab_overlap": any(
                    trade.get("ticker") == ticker for trade in ab_entries
                ),
                "known_at": event.get("known_at"),
                "trade_enabled": False,
                "alters_orders": False,
            }
        )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["item502_text_candidate_score"]),
            -float(row["leadership_quality_score"]),
            -float(row["rs20_vs_spy"]),
            -float(row["signal_excess_return_1d_vs_spy"]),
            -float(row["avg_dollar_volume_20d"]),
            row["ticker"],
        )
    )
    return candidates, {
        "dates_checked": len(dates),
        "sec_item502_text_events_in_window": len(events),
        "candidate_count": len(candidates),
        "candidate_days": len({row["date"] for row in candidates}),
        "unique_candidate_tickers": len({row["ticker"] for row in candidates}),
        "candidate_universe_argument_count": len(universe),
        "label_counts_before_filters": dict(sorted(label_counts.items())),
        "audit_reject_counts": dict(sorted(audit.items())),
        "rule_version": RULE_VERSION,
        "text_source_stats": _TEXT_SOURCE_STATS,
    }


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    decision = (
        "accepted_candidate_sec_item502_leadership_quality_text"
        if gate4["passed"]
        else "rejected_sec_item502_leadership_quality_text"
    )
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]
    actual_success = 1 if gate4["passed"] else 0
    aggregate = payload["delta_metrics"]["aggregate"]
    prediction = {
        "success_probability": 0.18,
        "expected_ev_delta": 0.15,
        "expected_pnl_delta": 2500.0,
        "main_failure_modes": [
            "text_quality_subset_too_sparse",
            "leadership_text_overmatches_departures",
            "window_regression",
            "accepted_comparator_not_beaten",
        ],
        "confidence_reason": (
            "Prior Item 5.02 positive-reaction source failed, but its own "
            "closeout named CEO/CFO appointment versus resignation and "
            "evidence-bound text classification as the legal reopen axis; "
            "local text cache has a usable broad Item 5.02 filing-body sample."
        ),
        "recorded_at": "2026-07-08T02:11:02+00:00",
        "brier_score": round((0.18 - actual_success) ** 2, 6),
    }

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "candidate_pool/full_stack: SEC 8-K Item 5.02 filing-body text "
                "that shows clear C-suite appointment or succession clarity, "
                "while excluding abrupt departure/resignation risk, may isolate "
                "leadership-change events with better next-open 10-session "
                "replacement value than the rejected generic Item 5.02 "
                "positive-reaction source."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": (
                "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
            ),
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 1,
            "nearby_prior_experiments": ["exp-20260529-019"],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "filing_body_leadership_quality_text_classification",
            "new_evidence_axis": (
                "New gate shape on the failed Item 5.02 family: filing-body text "
                "classification for clear C-suite appointment/succession versus "
                "departure/resignation risk, which exp-20260529-019 explicitly "
                "named as the legal reopen field. No OHLCV threshold, top-N, "
                "hold, cooldown, notional, or response-function retune."
            ),
            "prediction": prediction,
            "parameters": {
                "base_universe_count": payload["parameters"]["base_universe_count"],
                "stock_excluded_tickers": sorted(framework.EXCLUDED_TICKERS),
                "paper_notional_usd": framework.base.BASE_NOTIONAL_USD,
                "hold_days": framework.base.HOLD_DAYS,
                "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
                "target_item_codes": sorted(TARGET_ITEM_CODES),
                "excluded_item_codes": sorted(EXCLUDED_ITEM_CODES),
                "moving_average_days": MOVING_AVERAGE_DAYS,
                "relative_strength_days": RELATIVE_STRENGTH_DAYS,
                "avg_dollar_volume_days": AVG_DOLLAR_VOLUME_DAYS,
                "min_close": MIN_CLOSE,
                "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
                "min_rs20_vs_spy": MIN_RS20_VS_SPY,
                "min_signal_excess_return_1d_vs_spy": (
                    MIN_SIGNAL_EXCESS_RETURN_1D_VS_SPY
                ),
                "min_signal_close_location": MIN_SIGNAL_CLOSE_LOCATION,
                "leadership_quality_admitted_labels": [
                    "clear_exec_appointment_succession",
                    "clear_exec_appointment",
                ],
                "source_definition": [
                    "SEC filing text row is joined to a PIT-safe SEC 8-K event row",
                    "item codes must include 5.02 leadership-change disclosure",
                    "amended 8-K rows are excluded",
                    "old Item 5.02 excluded item-code bundle is unchanged",
                    "filing-body evidence must show direct C-suite appointment or succession",
                    "abrupt resignation, departure, termination, removal, death, or separation language rejects admission",
                    "board-only appointments reject admission",
                    "old OHLCV confirmation thresholds from exp-20260529-019 are unchanged",
                    "top-1 selected paper entry per signal date",
                ],
                "selection_rank": [
                    "signal_date",
                    "item502_text_candidate_score desc",
                    "leadership_quality_score desc",
                    "rs20_vs_spy desc",
                    "signal_excess_return_1d_vs_spy desc",
                    "avg_dollar_volume_20d desc",
                    "ticker asc",
                ],
                "locked_variables": [
                    "core universe membership",
                    "core signal generation",
                    "core ranking",
                    "core position sizing",
                    "core exits",
                    "portfolio heat",
                    "slot rules",
                    "LLM/news replay",
                    "watchlists",
                    "live/default orders",
                    "Item 5.02 item-code family",
                    "old exp-20260529-019 OHLCV confirmation thresholds",
                ],
                "acceptance": {
                    "aggregate_ev_delta_gt": 0,
                    "aggregate_pnl_delta_gt": 0,
                    "max_ev_regressed_windows": 0,
                    "max_pnl_regressed_windows": 0,
                    "min_target_trades": MIN_TARGET_TRADES,
                    "min_target_windows": MIN_TARGET_WINDOWS,
                    "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
                    "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                    "max_positive_hhi": MAX_POSITIVE_HHI,
                },
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "candidate_pool / entry: leadership-change 8-Ks whose "
                    "filing-body text shows direct C-suite appointment or "
                    "succession clarity should preserve the deployable subset "
                    "that the rejected generic Item 5.02 positive-reaction "
                    "source could not isolate."
                ),
                "2_history_check": {
                    "exp-20260529-019": (
                        "Rejected generic Item 5.02 positive-reaction source; "
                        "its closeout explicitly required CEO/CFO appointment "
                        "versus resignation, succession clarity, or evidence-"
                        "bound text classification for a legal retry."
                    ),
                    "novelty_gate": (
                        "experiment.py new warned on unrelated forward-"
                        "replacement near-neighbors because the wording "
                        "included replacement value; override recorded a legal "
                        "new gate shape on the Item 5.02 family."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same docs/backtesting.md three-window Gate 1-4 standard: "
                    "positive aggregate EV/PnL, no EV/PnL-regressed window, "
                    ">=20 paper trades across all 3 windows, drawdown drift "
                    "<=0.5pp, survival >=5%, and concentration guardrails."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260708_003_sec_item502_leadership_quality_text.py"
                ),
            },
            "why_not_other_changes": (
                "Skipped Item 5.02 threshold, top-N, hold, cooldown, notional, "
                "and OHLCV response retunes. Skipped shared daily adapter "
                "promotion until this sharper text gate proves replacement "
                "value on the frozen windows."
            ),
            "production_impact": {
                "shared_policy_changed": False,
                "backtester_adapter_changed": False,
                "run_adapter_changed": False,
                "replay_only": True,
                "parity_test_added": False,
                "default_off_paper_only": True,
                "production_watchlist_changed": False,
                "production_orders_changed": False,
                "trade_enabled": False,
                "promotion_requirement": (
                    "A retained result would still require a shared default-off "
                    "paper adapter, daily snapshot, and parity tests before any "
                    "daily report or live/default behavior changes."
                ),
            },
            "production_parity": {
                "alters_production_orders": False,
                "alters_live_watchlists": False,
                "alters_core_backtester": False,
                "default_enabled": False,
                "replay_only": True,
                "parity_note": (
                    "No production code path changed. Historical replay uses "
                    "local SEC text rows joined to PIT-safe event metadata; "
                    "promotion would require a shared parser/helper and daily "
                    "snapshot parity."
                ),
            },
            "interpretation": (
                "The Item 5.02 leadership-quality text gate cleared Gate 4 as "
                "a replay-only default-off lead; promotion still requires a "
                "shared helper and daily parity."
                if gate4["passed"]
                else (
                    "The Item 5.02 leadership-quality text gate did not clear "
                    "Gate 4. Do not retry nearby Item 5.02 text labels by "
                    "changing appointment/departure regexes or OHLCV thresholds "
                    "without forward rows, normalized executive-role extraction, "
                    "or another genuinely new evidence source."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "reflection": {
                "forbidden_near_neighbor_retry": (
                    "Do not retry Item 5.02 by changing appointment/departure "
                    "regexes, board-only inclusion, positive-reaction thresholds, "
                    "RS/close-location/volume filters, top-N, hold, cooldown, "
                    "or notional on this same text/event cache."
                ),
                "new_evidence_required": (
                    "A legal retry needs prospective closed forward replacement "
                    "rows, normalized executive-role extraction from primary "
                    "documents, independent management-change data, or another "
                    "non-SEC source that identifies leadership quality."
                ),
                "why_result_happened": (
                    f"Gate 4 evaluated the fixed text-quality Item 5.02 policy: "
                    f"EV delta {aggregate['expected_value_score_delta_sum']}, "
                    f"PnL delta {aggregate['total_pnl_delta_sum']}, failed "
                    f"{gate4['failed_reasons']}."
                ),
            },
            "next_evidence_needed": (
                "Prospective closed forward rows or normalized executive-role "
                "extraction from primary documents before another Item 5.02 retry."
            ),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["post_run_reflection"] = dict(payload["reflection"])
    payload["backtest_protocol"]["execution_model"] = (
        "SEC 8-K text rows are joined to PIT-safe event metadata and use the "
        "same usable_trade_date boundary as exp-20260529-019. OHLCV filters "
        "are observed through the signal-date close; paper entry is the next "
        "available open with production entry slippage; exit is ten trading "
        "days after the signal with target-side sell slippage and round-trip costs."
    )
    payload["gate2"]["runtime_field_coverage"] = {
        "sec_text_events": {
            "text_source_glob": framework.base._repo_rel(SEC_TEXT_GLOB),
            "event_source_glob": framework.base._repo_rel(SEC_EVENTS_GLOB),
            "required_fields": [
                "ticker",
                "usable_trade_date",
                "accession_number",
                "form_base/form_type",
                "pit_safe_flag",
                "eight_k_item_codes",
                "is_amendment",
                "combined_text",
            ],
            "text_source_stats": _TEXT_SOURCE_STATS,
        }
    }
    payload["gate2"]["target_trade_field_coverage"] = framework._field_coverage(
        all_target_trades,
        [
            "ticker",
            "signal_date",
            "entry_date",
            "exit_date",
            "entry_price",
            "exit_price",
            "pnl",
            "known_at",
            "sec_accession_number",
            "leadership_quality_label",
            "leadership_quality_score",
            "leadership_text_evidence",
            "rs20_vs_spy",
            "signal_excess_return_1d_vs_spy",
            "avg_dollar_volume_20d",
        ],
    )
    payload["related_files"] = [
        framework.base._repo_rel(Path(__file__)),
        framework.base._repo_rel(OUT_JSON),
        framework.base._repo_rel(BEFORE_AGG_JSON),
        framework.base._repo_rel(AFTER_AGG_JSON),
        framework.base._repo_rel(LOG_JSON),
        framework.base._repo_rel(TICKET_JSON),
        framework.base._repo_rel(CARD_MD),
        framework.base._repo_rel(ARTIFACT_MD),
        framework.base._repo_rel(EXPERIMENT_LOG),
        framework.base._repo_rel(SEC_TEXT_GLOB),
        framework.base._repo_rel(SEC_EVENTS_GLOB),
    ]
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {raw} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                raw=payload["raw_candidate_counts"][label],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    text_stats = _TEXT_SOURCE_STATS or {}
    return "\n".join(
        [
            "# exp-20260708-003 SEC Item 5.02 Leadership-Quality Text Gate",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: a default-off paper candidate source that admits PIT-safe SEC 8-K Item 5.02 filings only when filing-body text shows direct C-suite appointment/succession clarity and rejects abrupt departure or board-only rows.",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}` across `{len(payload['target_trade_summary']['windows_with_target_trades'])}` windows",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            "",
            "## Text Surface",
            "",
            "```json",
            json.dumps(text_stats, indent=2, sort_keys=True),
            "```",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(gate4, indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    framework.base._write_json(OUT_JSON, payload)
    framework.base._write_json(BEFORE_AGG_JSON, payload["judge_before_aggregate"])
    framework.base._write_json(AFTER_AGG_JSON, payload["judge_after_aggregate"])
    framework.base._write_json(LOG_JSON, payload)
    existing_ticket: dict[str, Any] = {}
    if TICKET_JSON.exists():
        try:
            existing_ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing_ticket = {}
    ticket_payload = {
        **existing_ticket,
        "experiment_id": EXPERIMENT_ID,
        "title": "SEC Item 5.02 leadership-quality text gate",
        "lane": "alpha_search",
        "owner": "alpha-explore",
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": payload["single_causal_variable"],
        "changed_variable": payload["changed_variable"],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "prediction": payload["prediction"],
        "post_run_reflection": payload["post_run_reflection"],
        "acceptance_rule": payload["gate_questions"]["4_acceptance_standard"],
        "locked_variables": payload["parameters"]["locked_variables"],
        "created_at": existing_ticket.get("created_at") or "2026-07-08T02:11:39+00:00",
        "claimed_at": existing_ticket.get("claimed_at") or "2026-07-08T02:11:50+00:00",
        "completed_at": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": framework.base._repo_rel(ARTIFACT_MD),
        "json": framework.base._repo_rel(OUT_JSON),
        "before_aggregate": framework.base._repo_rel(BEFORE_AGG_JSON),
        "after_aggregate": framework.base._repo_rel(AFTER_AGG_JSON),
        "summary": payload["interpretation"],
        "rejection_reason": payload.get("rejection_reason"),
        "result": {
            "decision": "accepted" if payload["gate4"]["passed"] else "rejected",
            "acceptance_reasons": [],
            "before_result_file": framework.base._repo_rel(BEFORE_AGG_JSON),
            "after_result_file": framework.base._repo_rel(AFTER_AGG_JSON),
            "delta_metrics": {
                "expected_value_score": payload["expected_value_score_delta"],
                "total_pnl": payload["total_pnl_delta"],
                "max_drawdown_pct": payload["delta_metrics"]["aggregate"][
                    "max_drawdown_delta_max"
                ],
                "trade_count": 0,
                "survival_rate": 0.0,
            },
        },
    }
    framework.base._write_json(TICKET_JSON, ticket_payload)
    framework.base._write_text(ARTIFACT_MD, _build_report(payload))
    framework.base._write_text(CARD_MD, _build_report(payload))
    framework.base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    _patch_framework()
    payload = _postprocess_payload(framework._build_payload())
    _persist(payload)
    print(
        json.dumps(
            framework.base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
                    "text_source_stats": _TEXT_SOURCE_STATS,
                    "artifact": framework.base._repo_rel(ARTIFACT_MD),
                    "before_aggregate": framework.base._repo_rel(BEFORE_AGG_JSON),
                    "after_aggregate": framework.base._repo_rel(AFTER_AGG_JSON),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    if not math.isfinite(1.0):
        raise SystemExit("unexpected math failure")
    raise SystemExit(main())
