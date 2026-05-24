from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any


QUEUE_NAME = "SEC_NEGATIVE_REACTION_FORWARD_QUEUE"
RULE_VERSION = "sec_negative_language_negative_reaction_v1"
GOVERNANCE_QUEUE_NAME = "SEC_GOVERNANCE_PROCEDURAL_FORWARD_QUEUE"
GOVERNANCE_RULE_VERSION = "sec_governance_procedural_mild_reaction_v1"
LEADERSHIP_QUEUE_NAME = "SEC_LEADERSHIP_CHANGE_FORWARD_QUEUE"
LEADERSHIP_RULE_VERSION = "sec_leadership_change_negative_reaction_v1"
FINANCIAL_REPORT_T1_QUEUE_NAME = "SEC_FINANCIAL_REPORT_T1_DRIFT_FORWARD_QUEUE"
FINANCIAL_REPORT_T1_RULE_VERSION = "sec_financial_report_positive_t1_excess_ge_1pct_non_platform_v3"
LANGUAGE_FEATURE_RULE_VERSION = "sec_language_features_v1"
PRIMARY_HORIZON_TRADING_DAYS = 10
MAX_COUNTERFACTUAL_SIGNALS = 3
REQUIRED_ITEM_CODE = "2.02"
LEADERSHIP_REQUIRED_ITEM_CODE = "5.02"
LEADERSHIP_MAX_EXCESS_REACTION = -0.02
FINANCIAL_REPORT_EVENT_FAMILIES = ("earnings_8k", "periodic_report")
FINANCIAL_REPORT_T1_EXCLUDED_COHORTS = ("platform_pool",)
FINANCIAL_REPORT_T1_MIN_EXCESS_RETURN_VS_SPY = 0.01
GOVERNANCE_TARGET_CELLS = {
    ("shareholder_vote", "negative_excess_0_to_minus_2pct"),
    ("charter_or_securities_change", "positive_excess_0_to_2pct"),
    ("exhibit_only", "negative_excess_0_to_minus_2pct"),
    ("exhibit_only", "positive_excess_0_to_2pct"),
}

POSITIVE_PHRASES = (
    "record revenue",
    "record quarterly",
    "record results",
    "strong demand",
    "robust demand",
    "accelerating demand",
    "continued momentum",
    "margin expansion",
    "expanded margin",
    "operating leverage",
    "free cash flow",
    "above expectations",
    "exceeded expectations",
    "better than expected",
)
NEGATIVE_PHRASES = (
    "weak demand",
    "soft demand",
    "lower demand",
    "headwinds",
    "margin pressure",
    "cost pressure",
    "challenging environment",
    "macroeconomic uncertainty",
    "inventory correction",
    "restructuring",
    "impairment",
    "declined",
    "decreased",
)
GUIDANCE_RAISE_PATTERNS = (
    r"\brais(?:e|es|ed|ing)\b.{0,80}\bguidance\b",
    r"\bguidance\b.{0,80}\brais(?:e|es|ed|ing)\b",
    r"\bincreas(?:e|es|ed|ing)\b.{0,80}\b(outlook|guidance)\b",
    r"\brais(?:e|es|ed|ing)\b.{0,80}\b(outlook|forecast)\b",
)
GUIDANCE_CUT_PATTERNS = (
    r"\blower(?:s|ed|ing)?\b.{0,80}\bguidance\b",
    r"\bguidance\b.{0,80}\blower(?:s|ed|ing)?\b",
    r"\breduc(?:e|es|ed|ing)\b.{0,80}\b(outlook|guidance)\b",
    r"\bcut(?:s|ting)?\b.{0,80}\b(outlook|guidance|forecast)\b",
)
DEFERRED_RESULTS_PHRASES = (
    "preliminary results",
    "expects to report",
    "will report",
    "announced selected",
    "announced preliminary",
)
PRODUCTION_UPDATE_PHRASES = (
    "production update",
    "delivery update",
    "operational update",
    "shipments",
    "deliveries",
)
EARNINGS_RELEASE_PHRASES = (
    "quarterly results",
    "financial results",
    "results for the quarter",
    "earnings release",
    "net income",
    "earnings per share",
)
LANGUAGE_FEATURE_FIELDS = (
    "language_score",
    "language_bucket",
    "positive_phrase_hits",
    "negative_phrase_hits",
    "guidance_raise_hits",
    "guidance_cut_hits",
    "text_event_type",
)


def latest_sec_filing_text_path(data_dir: str | Path) -> Path | None:
    root = Path(data_dir)
    candidates = sorted(root.glob("sec_filing_text_*.jsonl"))
    return candidates[-1] if candidates else None


def latest_sec_filing_events_path(data_dir: str | Path) -> Path | None:
    root = Path(data_dir)
    candidates = sorted(root.glob("sec_filing_events_*.jsonl"))
    return candidates[-1] if candidates else None


def load_sec_filing_text_rows(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    source = Path(path)
    with source.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            row = json.loads(text)
            if isinstance(row, dict):
                rows.append(row)
    return rows


def load_sec_filing_event_rows(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    source = Path(path)
    with source.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            row = json.loads(text)
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _is_semantic_doc_name(name: str, primary_document: str | None) -> bool:
    lowered = name.lower()
    primary = str(primary_document or "").lower()
    if "index-headers" in lowered or re.fullmatch(r"r\d+\.htm", lowered):
        return False
    if re.search(r"(ex[-_]?99|exhibit[-_]?99|ex99|ex991|e991|exhibit99)", lowered):
        return True
    return bool(primary and lowered == primary)


def _document_sections(combined_text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    for match in re.finditer(r"(?:^| )DOCUMENT ([^ ]+) ", combined_text):
        start = match.end()
        end_match = re.search(r" DOCUMENT [^ ]+ ", combined_text[start:])
        end = start + end_match.start() if end_match else len(combined_text)
        sections.append((match.group(1), combined_text[start:end].strip()))
    return sections


def semantic_text(row: dict[str, Any]) -> str:
    combined = str(row.get("combined_text") or row.get("text") or "")
    if not combined:
        return ""
    primary = row.get("primary_document")
    parts = [
        text
        for name, text in _document_sections(combined)
        if _is_semantic_doc_name(name, str(primary) if primary else None)
    ]
    return (" ".join(parts) if parts else combined)[:120000]


def _phrase_count(text: str, phrases: tuple[str, ...]) -> int:
    return sum(text.count(phrase) for phrase in phrases)


def _pattern_count(text: str, patterns: tuple[str, ...]) -> int:
    return sum(len(re.findall(pattern, text, flags=re.IGNORECASE | re.DOTALL)) for pattern in patterns)


def language_features(row: dict[str, Any]) -> dict[str, Any]:
    text = semantic_text(row)
    lowered = text.lower()
    deferred_hits = _phrase_count(lowered, DEFERRED_RESULTS_PHRASES)
    production_hits = _phrase_count(lowered, PRODUCTION_UPDATE_PHRASES)
    earnings_hits = _phrase_count(lowered, EARNINGS_RELEASE_PHRASES)
    positive_hits = _phrase_count(lowered, POSITIVE_PHRASES)
    negative_hits = _phrase_count(lowered, NEGATIVE_PHRASES)
    guidance_raise_hits = _pattern_count(lowered, GUIDANCE_RAISE_PATTERNS)
    guidance_cut_hits = _pattern_count(lowered, GUIDANCE_CUT_PATTERNS)

    if deferred_hits and production_hits:
        event_type = "deferred_results_or_operational_update"
    elif earnings_hits or (
        "revenue" in lowered
        and ("net income" in lowered or "earnings per share" in lowered or "eps" in lowered)
    ):
        event_type = "earnings_release_text"
    elif production_hits:
        event_type = "operational_update"
    else:
        event_type = "item_2_02_other_text"

    score = positive_hits + 2 * guidance_raise_hits - negative_hits - 2 * guidance_cut_hits
    if event_type == "deferred_results_or_operational_update":
        bucket = "deferred_or_operational"
    elif score >= 2:
        bucket = "positive_language"
    elif score <= -2:
        bucket = "negative_language"
    else:
        bucket = "neutral_or_mixed_language"

    return {
        "text_event_type": event_type,
        "language_score": score,
        "language_bucket": bucket,
        "positive_phrase_hits": positive_hits,
        "negative_phrase_hits": negative_hits,
        "guidance_raise_hits": guidance_raise_hits,
        "guidance_cut_hits": guidance_cut_hits,
    }


def _accession_key(value: Any) -> str:
    return str(value or "").strip().lower()


def _text_row_maps(
    rows: list[dict[str, Any]],
) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, dict[str, Any]]]:
    by_ticker_accession: dict[tuple[str, str], dict[str, Any]] = {}
    by_accession: dict[str, dict[str, Any]] = {}
    for row in rows:
        accession = _accession_key(row.get("accession_number"))
        if not accession:
            continue
        ticker = str(row.get("ticker") or "").upper()
        if ticker:
            by_ticker_accession.setdefault((ticker, accession), row)
        by_accession.setdefault(accession, row)
    return by_ticker_accession, by_accession


def _text_row_for_event(
    row: dict[str, Any],
    by_ticker_accession: dict[tuple[str, str], dict[str, Any]],
    by_accession: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    accession = _accession_key(row.get("accession_number"))
    if not accession:
        return None
    ticker = str(row.get("ticker") or "").upper()
    if ticker:
        matched = by_ticker_accession.get((ticker, accession))
        if matched is not None:
            return matched
    return by_accession.get(accession)


def _financial_report_language_features(
    row: dict[str, Any],
    by_ticker_accession: dict[tuple[str, str], dict[str, Any]],
    by_accession: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    text_row = _text_row_for_event(row, by_ticker_accession, by_accession)
    if text_row is not None:
        return {
            **language_features(text_row),
            "sec_text_coverage_status": "covered",
            "sec_text_accession_matched": True,
            "sec_text_primary_document": text_row.get("primary_document"),
            "language_feature_rule_version": LANGUAGE_FEATURE_RULE_VERSION,
        }

    embedded = {
        field: row.get(field)
        for field in LANGUAGE_FEATURE_FIELDS
        if row.get(field) is not None
    }
    if embedded:
        return {
            **embedded,
            "sec_text_coverage_status": "embedded_event_language",
            "sec_text_accession_matched": False,
            "sec_text_primary_document": row.get("primary_document"),
            "language_feature_rule_version": LANGUAGE_FEATURE_RULE_VERSION,
        }

    return {
        "sec_text_coverage_status": "missing_text_row",
        "sec_text_accession_matched": False,
        "sec_text_primary_document": None,
        "language_feature_rule_version": LANGUAGE_FEATURE_RULE_VERSION,
    }


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _normalize_ohlcv_rows(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if hasattr(raw, "reset_index") and hasattr(raw, "to_dict"):
        records = raw.reset_index().to_dict("records")
    elif isinstance(raw, list):
        records = raw
    else:
        return []

    rows: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        date_value = record.get("date") or record.get("Date")
        if date_value is None:
            continue
        rows.append(
            {
                "date": str(date_value)[:10],
                "open": _float_or_none(record.get("open", record.get("Open"))),
                "close": _float_or_none(record.get("close", record.get("Close"))),
            }
        )
    return sorted(rows, key=lambda row: row["date"])


def _idx_on_or_after(rows: list[dict[str, Any]], target: str) -> int | None:
    for idx, row in enumerate(rows):
        if row["date"] >= target:
            return idx
    return None


def reaction_bucket(value: float | None) -> str:
    if value is None:
        return "reaction_missing"
    if value >= 0:
        return "reaction_ge_0"
    if value >= -0.02:
        return "reaction_-2_to_0"
    if value >= -0.05:
        return "reaction_-5_to_-2"
    return "reaction_lt_-5"


def governance_reaction_bucket(value: float | None) -> str:
    if value is None:
        return "reaction_missing"
    if 0 <= value <= 0.02:
        return "positive_excess_0_to_2pct"
    if -0.02 <= value < 0:
        return "negative_excess_0_to_minus_2pct"
    if value > 0.02:
        return "positive_excess_gt_2pct"
    return "negative_excess_lt_minus_2pct"


def governance_semantic_subcategory(row: dict[str, Any]) -> str:
    item_codes = {str(item) for item in row.get("eight_k_item_codes") or []}
    if "5.07" in item_codes:
        return "shareholder_vote"
    if item_codes & {"5.03", "3.02", "3.03"}:
        return "charter_or_securities_change"
    if item_codes == {"9.01"}:
        return "exhibit_only"
    return "misc_other"


def leadership_semantic_subcategory(row: dict[str, Any]) -> str:
    item_codes = {str(item) for item in row.get("eight_k_item_codes") or []}
    return (
        "leadership_change"
        if LEADERSHIP_REQUIRED_ITEM_CODE in item_codes
        else "not_leadership_change"
    )


def sec_event_item_codes(row: dict[str, Any]) -> tuple[str, ...]:
    raw = row.get("eight_k_item_codes")
    if isinstance(raw, list):
        return tuple(str(item) for item in raw if str(item))
    raw = row.get("items_raw")
    if isinstance(raw, str):
        return tuple(item.strip() for item in raw.split(",") if item.strip())
    return ()


def sec_event_family(row: dict[str, Any]) -> str:
    form_base = str(row.get("form_base") or row.get("form_type") or "").upper()
    codes = set(sec_event_item_codes(row))
    if form_base in {"10-K", "10-Q"}:
        return "periodic_report"
    if form_base == "8-K":
        if REQUIRED_ITEM_CODE in codes:
            return "earnings_8k"
        if codes & {"1.01", "2.03", "3.02"}:
            return "capital_contract_8k"
        if codes & {"5.02", "5.03", "5.07"}:
            return "governance_8k"
        if codes & {"7.01", "8.01"}:
            return "fd_other_8k"
        return "other_8k"
    return "other_sec"


def evaluate_first_reaction(
    row: dict[str, Any],
    ohlcv_by_ticker: dict[str, Any],
    spy_ohlcv: Any,
) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").upper()
    usable = str(row.get("usable_trade_date") or "")[:10]
    ticker_rows = _normalize_ohlcv_rows(ohlcv_by_ticker.get(ticker))
    spy_rows = _normalize_ohlcv_rows(spy_ohlcv)
    if not ticker or not usable or not ticker_rows or not spy_rows:
        return {
            "price_status": "missing_ticker_spy_or_usable_date",
            "reaction_bucket": "reaction_missing",
        }

    ticker_idx = _idx_on_or_after(ticker_rows, usable)
    spy_idx = _idx_on_or_after(spy_rows, usable)
    if ticker_idx is None or spy_idx is None:
        return {
            "price_status": "missing_reaction_date",
            "reaction_bucket": "reaction_missing",
        }
    ticker_day = ticker_rows[ticker_idx]
    spy_day = spy_rows[spy_idx]
    ticker_open = ticker_day.get("open")
    ticker_close = ticker_day.get("close")
    spy_open = spy_day.get("open")
    spy_close = spy_day.get("close")
    if not ticker_open or not ticker_close or not spy_open or not spy_close:
        return {
            "price_status": "missing_reaction_price",
            "reaction_bucket": "reaction_missing",
        }

    ticker_reaction = ticker_close / ticker_open - 1.0
    spy_reaction = spy_close / spy_open - 1.0
    excess = ticker_reaction - spy_reaction
    return {
        "price_status": "covered",
        "reaction_date": ticker_day["date"],
        "reaction_return": round(ticker_reaction, 6),
        "spy_reaction_return": round(spy_reaction, 6),
        "reaction_excess_return": round(excess, 6),
        "reaction_bucket": reaction_bucket(excess),
    }


def _close_return_between(
    rows: list[dict[str, Any]],
    start_idx: int,
    end_idx: int,
) -> float | None:
    if start_idx < 0 or end_idx >= len(rows):
        return None
    start_close = rows[start_idx].get("close")
    end_close = rows[end_idx].get("close")
    if not start_close or not end_close:
        return None
    return end_close / start_close - 1.0


def financial_report_drift_bucket(
    t1_return: float | None,
    spy_t1_return: float | None,
) -> str:
    if t1_return is None or spy_t1_return is None:
        return "immature_or_missing_t1"
    if t1_return > 0 and t1_return > spy_t1_return:
        return "positive_t1_excess_drift"
    if t1_return > 0:
        return "positive_t1_absolute_only"
    return "negative_or_zero_t1_drift"


def evaluate_t1_excess_drift(
    row: dict[str, Any],
    ohlcv_by_ticker: dict[str, Any],
    spy_ohlcv: Any,
) -> dict[str, Any]:
    ticker = str(row.get("ticker") or "").upper()
    usable = str(row.get("usable_trade_date") or "")[:10]
    ticker_rows = _normalize_ohlcv_rows(ohlcv_by_ticker.get(ticker))
    spy_rows = _normalize_ohlcv_rows(spy_ohlcv)
    if not ticker or not usable or not ticker_rows or not spy_rows:
        return {
            "price_status": "missing_ticker_spy_or_usable_date",
            "drift_bucket": "immature_or_missing_t1",
        }

    event_idx = _idx_on_or_after(ticker_rows, usable)
    spy_idx = _idx_on_or_after(spy_rows, usable)
    if event_idx is None or spy_idx is None:
        return {
            "price_status": "missing_event_trading_date",
            "drift_bucket": "immature_or_missing_t1",
        }

    t1_idx = event_idx + 1
    spy_t1_idx = spy_idx + 1
    t1_return = _close_return_between(ticker_rows, event_idx, t1_idx)
    spy_t1_return = _close_return_between(spy_rows, spy_idx, spy_t1_idx)
    bucket = financial_report_drift_bucket(t1_return, spy_t1_return)
    event_day = ticker_rows[event_idx]
    t1_day = ticker_rows[t1_idx] if t1_idx < len(ticker_rows) else None
    entry_idx = event_idx + 2
    entry_day = ticker_rows[entry_idx] if entry_idx < len(ticker_rows) else None
    excess = (
        t1_return - spy_t1_return
        if isinstance(t1_return, (int, float))
        and isinstance(spy_t1_return, (int, float))
        else None
    )
    return {
        "price_status": "covered" if t1_day else "missing_t1_close",
        "event_trading_date": event_day["date"],
        "t1_date": t1_day["date"] if t1_day else None,
        "shadow_entry_date": entry_day["date"] if entry_day else None,
        "t1_return": round(t1_return, 6) if t1_return is not None else None,
        "spy_t1_return": (
            round(spy_t1_return, 6) if spy_t1_return is not None else None
        ),
        "t1_excess_return_vs_spy": round(excess, 6) if excess is not None else None,
        "drift_bucket": bucket,
    }


def qualifies_sec_negative_reaction_event(event: dict[str, Any]) -> bool:
    item_codes = {str(item) for item in event.get("eight_k_item_codes") or []}
    reaction = event.get("reaction_excess_return")
    return (
        event.get("status") == "ok"
        and REQUIRED_ITEM_CODE in item_codes
        and event.get("language_bucket") == "negative_language"
        and event.get("price_status") == "covered"
        and isinstance(reaction, (int, float))
        and reaction < 0
    )


def qualifies_sec_governance_procedural_event(event: dict[str, Any]) -> bool:
    item_codes = {str(item) for item in event.get("eight_k_item_codes") or []}
    semantic = governance_semantic_subcategory(event)
    bucket = governance_reaction_bucket(event.get("reaction_excess_return"))
    return (
        event.get("status") == "ok"
        and event.get("price_status") == "covered"
        and "2.02" not in item_codes
        and (semantic, bucket) in GOVERNANCE_TARGET_CELLS
    )


def qualifies_sec_leadership_change_event(event: dict[str, Any]) -> bool:
    item_codes = {str(item) for item in event.get("eight_k_item_codes") or []}
    reaction = event.get("reaction_excess_return")
    return (
        event.get("status") == "ok"
        and LEADERSHIP_REQUIRED_ITEM_CODE in item_codes
        and event.get("price_status") == "covered"
        and isinstance(reaction, (int, float))
        and reaction <= LEADERSHIP_MAX_EXCESS_REACTION
    )


def qualifies_sec_financial_report_t1_event(event: dict[str, Any]) -> bool:
    cohort = str(event.get("cohort") or "")
    t1_excess = event.get("t1_excess_return_vs_spy")
    return (
        event.get("status") == "ok"
        and event.get("event_family") in FINANCIAL_REPORT_EVENT_FAMILIES
        and bool(cohort)
        and cohort not in FINANCIAL_REPORT_T1_EXCLUDED_COHORTS
        and event.get("price_status") == "covered"
        and event.get("drift_bucket") == "positive_t1_excess_drift"
        and isinstance(t1_excess, (int, float))
        and t1_excess >= FINANCIAL_REPORT_T1_MIN_EXCESS_RETURN_VS_SPY
    )


def build_sec_event_queue(
    rows: list[dict[str, Any]],
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any] | None = None,
    spy_ohlcv: Any = None,
    core_signals: list[dict[str, Any]] | None = None,
    source_path: str | Path | None = None,
    source_status: str = "loaded",
) -> dict[str, Any]:
    ohlcv_by_ticker = ohlcv_by_ticker or {}
    candidates: list[dict[str, Any]] = []
    evaluated_count = 0
    as_of_date = str(as_of)[:10]

    for row in rows:
        if str(row.get("usable_trade_date") or "")[:10] != as_of_date:
            continue
        evaluated_count += 1
        event = {
            **row,
            **language_features(row),
            **evaluate_first_reaction(row, ohlcv_by_ticker, spy_ohlcv),
        }
        if qualifies_sec_negative_reaction_event(event):
            candidates.append(_candidate_payload(event, core_signals=core_signals or []))

    return {
        "queue_name": QUEUE_NAME,
        "rule_version": RULE_VERSION,
        "enabled": False,
        "asof_date": as_of_date,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "data_source": {
            "status": source_status,
            "path": str(source_path) if source_path else None,
            "loaded_row_count": len(rows),
            "same_day_evaluated_count": evaluated_count,
        },
        "parameters": {
            "packet_rule": "8-K Item 2.02 AND language_bucket == negative_language AND reaction_excess_return < 0",
            "primary_horizon_trading_days": PRIMARY_HORIZON_TRADING_DAYS,
            "entry_timing": "next_trading_day_open_after_reaction_close",
        },
        "production_impact": {
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "scope": "observe_only_forward_event_queue",
        },
        "next_action": "freeze_counterfactuals_and_measure_forward_replacement_value",
    }


def build_sec_governance_procedural_queue(
    rows: list[dict[str, Any]],
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any] | None = None,
    spy_ohlcv: Any = None,
    core_signals: list[dict[str, Any]] | None = None,
    source_path: str | Path | None = None,
    source_status: str = "loaded",
) -> dict[str, Any]:
    ohlcv_by_ticker = ohlcv_by_ticker or {}
    candidates: list[dict[str, Any]] = []
    evaluated_count = 0
    as_of_date = str(as_of)[:10]

    for row in rows:
        if str(row.get("usable_trade_date") or "")[:10] != as_of_date:
            continue
        evaluated_count += 1
        event = {
            **row,
            **evaluate_first_reaction(row, ohlcv_by_ticker, spy_ohlcv),
        }
        if qualifies_sec_governance_procedural_event(event):
            candidates.append(
                _governance_candidate_payload(
                    event,
                    core_signals=core_signals or [],
                )
            )

    return {
        "queue_name": GOVERNANCE_QUEUE_NAME,
        "rule_version": GOVERNANCE_RULE_VERSION,
        "enabled": False,
        "asof_date": as_of_date,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "data_source": {
            "status": source_status,
            "path": str(source_path) if source_path else None,
            "loaded_row_count": len(rows),
            "same_day_evaluated_count": evaluated_count,
        },
        "parameters": {
            "packet_rule": (
                "8-K governance/procedural semantic cells from exp-20260504-039 "
                "with mild first-day excess reaction"
            ),
            "target_cells": sorted(
                f"{semantic}|{bucket}"
                for semantic, bucket in GOVERNANCE_TARGET_CELLS
            ),
            "primary_horizon_trading_days": PRIMARY_HORIZON_TRADING_DAYS,
            "entry_timing": "next_trading_day_open_after_reaction_close",
        },
        "production_impact": {
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "scope": "observe_only_forward_governance_event_queue",
        },
        "next_action": "freeze_paper_entries_and_measure_forward_replacement_value",
    }


def build_sec_leadership_change_queue(
    rows: list[dict[str, Any]],
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any] | None = None,
    spy_ohlcv: Any = None,
    core_signals: list[dict[str, Any]] | None = None,
    source_path: str | Path | None = None,
    source_status: str = "loaded",
) -> dict[str, Any]:
    ohlcv_by_ticker = ohlcv_by_ticker or {}
    candidates: list[dict[str, Any]] = []
    evaluated_count = 0
    as_of_date = str(as_of)[:10]

    for row in rows:
        if str(row.get("usable_trade_date") or "")[:10] != as_of_date:
            continue
        evaluated_count += 1
        event = {
            **row,
            **evaluate_first_reaction(row, ohlcv_by_ticker, spy_ohlcv),
        }
        if qualifies_sec_leadership_change_event(event):
            candidates.append(
                _leadership_candidate_payload(
                    event,
                    core_signals=core_signals or [],
                )
            )

    return {
        "queue_name": LEADERSHIP_QUEUE_NAME,
        "rule_version": LEADERSHIP_RULE_VERSION,
        "enabled": False,
        "asof_date": as_of_date,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "data_source": {
            "status": source_status,
            "path": str(source_path) if source_path else None,
            "loaded_row_count": len(rows),
            "same_day_evaluated_count": evaluated_count,
        },
        "parameters": {
            "packet_rule": (
                "8-K Item 5.02 AND first-day SPY-relative reaction <= -2%"
            ),
            "target_cell": (
                "leadership_change|negative_excess_le_minus_2pct"
            ),
            "primary_horizon_trading_days": PRIMARY_HORIZON_TRADING_DAYS,
            "entry_timing": "next_trading_day_open_after_reaction_close",
        },
        "production_impact": {
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "scope": "observe_only_forward_leadership_event_queue",
        },
        "next_action": "freeze_paper_entries_and_measure_forward_replacement_value",
    }


def build_sec_financial_report_t1_queue(
    rows: list[dict[str, Any]],
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any] | None = None,
    spy_ohlcv: Any = None,
    core_signals: list[dict[str, Any]] | None = None,
    source_path: str | Path | None = None,
    source_status: str = "loaded",
    text_rows: list[dict[str, Any]] | None = None,
    text_source_path: str | Path | None = None,
    text_source_status: str | None = None,
) -> dict[str, Any]:
    ohlcv_by_ticker = ohlcv_by_ticker or {}
    text_rows = text_rows or []
    text_by_ticker_accession, text_by_accession = _text_row_maps(text_rows)
    effective_text_status = text_source_status or (
        "loaded" if text_rows else "not_provided"
    )
    candidates: list[dict[str, Any]] = []
    evaluated_count = 0
    language_covered_count = 0
    language_embedded_event_count = 0
    language_missing_text_count = 0
    skipped_not_pit_safe = 0
    as_of_date = str(as_of)[:10]
    seen_shadow_keys: set[tuple[str, str, str]] = set()

    for row in rows:
        if row.get("pit_safe_flag") is False:
            skipped_not_pit_safe += 1
            continue
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        family = sec_event_family(row)
        event = {
            **row,
            "status": row.get("status") or "ok",
            "ticker": ticker,
            "event_family": family,
            "item_codes": list(sec_event_item_codes(row)),
            **_financial_report_language_features(
                row,
                text_by_ticker_accession,
                text_by_accession,
            ),
            **evaluate_t1_excess_drift(row, ohlcv_by_ticker, spy_ohlcv),
        }
        if event.get("t1_date") != as_of_date:
            continue
        evaluated_count += 1
        coverage_status = str(event.get("sec_text_coverage_status") or "")
        if coverage_status == "covered":
            language_covered_count += 1
        elif coverage_status == "embedded_event_language":
            language_embedded_event_count += 1
        elif coverage_status == "missing_text_row":
            language_missing_text_count += 1
        shadow_key = (
            ticker,
            str(event.get("event_trading_date") or ""),
            family,
        )
        if shadow_key in seen_shadow_keys:
            continue
        seen_shadow_keys.add(shadow_key)
        if qualifies_sec_financial_report_t1_event(event):
            candidates.append(
                _financial_report_t1_candidate_payload(
                    event,
                    core_signals=core_signals or [],
                )
            )

    return {
        "queue_name": FINANCIAL_REPORT_T1_QUEUE_NAME,
        "rule_version": FINANCIAL_REPORT_T1_RULE_VERSION,
        "enabled": False,
        "asof_date": as_of_date,
        "candidate_count": len(candidates),
        "candidates": sorted(
            candidates,
            key=lambda candidate: (
                -float(candidate.get("t1_excess_return_vs_spy") or 0.0),
                str(candidate.get("ticker") or ""),
            ),
        ),
        "data_source": {
            "status": source_status,
            "path": str(source_path) if source_path else None,
            "loaded_row_count": len(rows),
            "text_status": effective_text_status,
            "text_path": str(text_source_path) if text_source_path else None,
            "loaded_text_row_count": len(text_rows),
            "t1_evaluated_count": evaluated_count,
            "language_covered_count": language_covered_count,
            "language_embedded_event_count": language_embedded_event_count,
            "language_missing_text_count": language_missing_text_count,
            "skipped_not_pit_safe_count": skipped_not_pit_safe,
        },
        "parameters": {
            "packet_rule": (
                "event_family in earnings_8k, periodic_report AND "
                "cohort not in platform_pool AND ticker T+1 close-to-close "
                "return > 0 AND > SPY T+1 return"
            ),
            "included_event_families": list(FINANCIAL_REPORT_EVENT_FAMILIES),
            "excluded_cohorts": list(FINANCIAL_REPORT_T1_EXCLUDED_COHORTS),
            "min_t1_excess_return_vs_spy": FINANCIAL_REPORT_T1_MIN_EXCESS_RETURN_VS_SPY,
            "primary_horizon_trading_days": PRIMARY_HORIZON_TRADING_DAYS,
            "entry_timing": "next_trading_day_open_after_t1_close",
            "source_experiment": "exp-20260510-027",
        },
        "production_impact": {
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "scope": "observe_only_forward_sec_financial_report_t1_queue",
        },
        "next_action": "freeze_paper_entries_and_measure_forward_replacement_value",
    }


def build_forward_queue_from_sec_filing_text(
    *,
    data_dir: str | Path,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any] | None = None,
    spy_ohlcv: Any = None,
    core_signals: list[dict[str, Any]] | None = None,
    source_path: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(source_path) if source_path else latest_sec_filing_text_path(data_dir)
    if path is None or not path.exists():
        return empty_sec_event_queue(as_of, "missing_sec_filing_text_jsonl")
    rows = load_sec_filing_text_rows(path)
    return build_sec_event_queue(
        rows,
        as_of=as_of,
        ohlcv_by_ticker=ohlcv_by_ticker,
        spy_ohlcv=spy_ohlcv,
        core_signals=core_signals,
        source_path=path,
    )


def build_forward_governance_queue_from_sec_filing_text(
    *,
    data_dir: str | Path,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any] | None = None,
    spy_ohlcv: Any = None,
    core_signals: list[dict[str, Any]] | None = None,
    source_path: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(source_path) if source_path else latest_sec_filing_text_path(data_dir)
    if path is None or not path.exists():
        return empty_sec_governance_queue(as_of, "missing_sec_filing_text_jsonl")
    rows = load_sec_filing_text_rows(path)
    return build_sec_governance_procedural_queue(
        rows,
        as_of=as_of,
        ohlcv_by_ticker=ohlcv_by_ticker,
        spy_ohlcv=spy_ohlcv,
        core_signals=core_signals,
        source_path=path,
    )


def build_forward_leadership_queue_from_sec_filing_text(
    *,
    data_dir: str | Path,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any] | None = None,
    spy_ohlcv: Any = None,
    core_signals: list[dict[str, Any]] | None = None,
    source_path: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(source_path) if source_path else latest_sec_filing_text_path(data_dir)
    if path is None or not path.exists():
        return empty_sec_leadership_queue(as_of, "missing_sec_filing_text_jsonl")
    rows = load_sec_filing_text_rows(path)
    return build_sec_leadership_change_queue(
        rows,
        as_of=as_of,
        ohlcv_by_ticker=ohlcv_by_ticker,
        spy_ohlcv=spy_ohlcv,
        core_signals=core_signals,
        source_path=path,
    )


def build_forward_financial_report_t1_queue_from_sec_filing_events(
    *,
    data_dir: str | Path,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any] | None = None,
    spy_ohlcv: Any = None,
    core_signals: list[dict[str, Any]] | None = None,
    source_path: str | Path | None = None,
    text_source_path: str | Path | None = None,
) -> dict[str, Any]:
    path = Path(source_path) if source_path else latest_sec_filing_events_path(data_dir)
    if path is None or not path.exists():
        return empty_sec_financial_report_t1_queue(
            as_of,
            "missing_sec_filing_events_jsonl",
        )
    text_path = (
        Path(text_source_path)
        if text_source_path
        else latest_sec_filing_text_path(data_dir)
    )
    text_rows: list[dict[str, Any]] = []
    text_status = "missing_sec_filing_text_jsonl"
    if text_path is not None and text_path.exists():
        text_rows = load_sec_filing_text_rows(text_path)
        text_status = "loaded"
    rows = load_sec_filing_event_rows(path)
    return build_sec_financial_report_t1_queue(
        rows,
        as_of=as_of,
        ohlcv_by_ticker=ohlcv_by_ticker,
        spy_ohlcv=spy_ohlcv,
        core_signals=core_signals,
        source_path=path,
        text_rows=text_rows,
        text_source_path=text_path,
        text_source_status=text_status,
    )


def empty_sec_event_queue(as_of: str, reason: str) -> dict[str, Any]:
    queue = build_sec_event_queue([], as_of=as_of, source_status=reason)
    queue["error"] = reason
    return queue


def empty_sec_governance_queue(as_of: str, reason: str) -> dict[str, Any]:
    queue = build_sec_governance_procedural_queue(
        [],
        as_of=as_of,
        source_status=reason,
    )
    queue["error"] = reason
    return queue


def empty_sec_leadership_queue(as_of: str, reason: str) -> dict[str, Any]:
    queue = build_sec_leadership_change_queue(
        [],
        as_of=as_of,
        source_status=reason,
    )
    queue["error"] = reason
    return queue


def empty_sec_financial_report_t1_queue(as_of: str, reason: str) -> dict[str, Any]:
    queue = build_sec_financial_report_t1_queue(
        [],
        as_of=as_of,
        source_status=reason,
    )
    queue["error"] = reason
    return queue


def _candidate_payload(
    event: dict[str, Any],
    *,
    core_signals: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "ticker": event.get("ticker"),
        "usable_trade_date": event.get("usable_trade_date"),
        "filing_date": event.get("filing_date"),
        "accepted_at": event.get("accepted_at"),
        "accession_number": event.get("accession_number"),
        "primary_document": event.get("primary_document"),
        "index_url": event.get("index_url"),
        "language_score": event.get("language_score"),
        "language_bucket": event.get("language_bucket"),
        "negative_phrase_hits": event.get("negative_phrase_hits"),
        "guidance_cut_hits": event.get("guidance_cut_hits"),
        "text_event_type": event.get("text_event_type"),
        "reaction_date": event.get("reaction_date"),
        "reaction_return": event.get("reaction_return"),
        "spy_reaction_return": event.get("spy_reaction_return"),
        "reaction_excess_return": event.get("reaction_excess_return"),
        "reaction_bucket": event.get("reaction_bucket"),
        "trade_enabled": False,
        "action": "observe_only",
        "counterfactual": _counterfactual_payload(core_signals),
    }


def _governance_candidate_payload(
    event: dict[str, Any],
    *,
    core_signals: list[dict[str, Any]],
) -> dict[str, Any]:
    semantic = governance_semantic_subcategory(event)
    bucket = governance_reaction_bucket(event.get("reaction_excess_return"))
    return {
        "ticker": event.get("ticker"),
        "usable_trade_date": event.get("usable_trade_date"),
        "filing_date": event.get("filing_date"),
        "accepted_at": event.get("accepted_at"),
        "accession_number": event.get("accession_number"),
        "primary_document": event.get("primary_document"),
        "index_url": event.get("index_url"),
        "semantic_subcategory": semantic,
        "reaction_bucket": bucket,
        "target_cell": f"{semantic}|{bucket}",
        "eight_k_item_codes": event.get("eight_k_item_codes"),
        "reaction_date": event.get("reaction_date"),
        "reaction_return": event.get("reaction_return"),
        "spy_reaction_return": event.get("spy_reaction_return"),
        "reaction_excess_return": event.get("reaction_excess_return"),
        "trade_enabled": False,
        "action": "observe_only",
        "counterfactual": _counterfactual_payload(core_signals),
    }


def _leadership_candidate_payload(
    event: dict[str, Any],
    *,
    core_signals: list[dict[str, Any]],
) -> dict[str, Any]:
    semantic = leadership_semantic_subcategory(event)
    return {
        "ticker": event.get("ticker"),
        "usable_trade_date": event.get("usable_trade_date"),
        "filing_date": event.get("filing_date"),
        "accepted_at": event.get("accepted_at"),
        "accession_number": event.get("accession_number"),
        "primary_document": event.get("primary_document"),
        "index_url": event.get("index_url"),
        "semantic_subcategory": semantic,
        "reaction_bucket": "negative_excess_le_minus_2pct",
        "target_cell": f"{semantic}|negative_excess_le_minus_2pct",
        "eight_k_item_codes": event.get("eight_k_item_codes"),
        "reaction_date": event.get("reaction_date"),
        "reaction_return": event.get("reaction_return"),
        "spy_reaction_return": event.get("spy_reaction_return"),
        "reaction_excess_return": event.get("reaction_excess_return"),
        "trade_enabled": False,
        "action": "observe_only",
        "counterfactual": _counterfactual_payload(core_signals),
    }


def _financial_report_t1_candidate_payload(
    event: dict[str, Any],
    *,
    core_signals: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "ticker": event.get("ticker"),
        "usable_trade_date": event.get("usable_trade_date"),
        "event_trading_date": event.get("event_trading_date"),
        "t1_date": event.get("t1_date"),
        "shadow_entry_date": event.get("shadow_entry_date"),
        "filing_date": event.get("filing_date"),
        "accepted_at": event.get("accepted_at"),
        "accession_number": event.get("accession_number"),
        "form_type": event.get("form_type"),
        "form_base": event.get("form_base"),
        "event_family": event.get("event_family"),
        "cohort": event.get("cohort"),
        "item_codes": event.get("item_codes"),
        "primary_document": event.get("primary_document"),
        "index_url": event.get("index_url"),
        "archive_url": event.get("archive_url"),
        "language_score": event.get("language_score"),
        "language_bucket": event.get("language_bucket"),
        "positive_phrase_hits": event.get("positive_phrase_hits"),
        "negative_phrase_hits": event.get("negative_phrase_hits"),
        "guidance_raise_hits": event.get("guidance_raise_hits"),
        "guidance_cut_hits": event.get("guidance_cut_hits"),
        "text_event_type": event.get("text_event_type"),
        "sec_text_coverage_status": event.get("sec_text_coverage_status"),
        "sec_text_accession_matched": event.get("sec_text_accession_matched"),
        "sec_text_primary_document": event.get("sec_text_primary_document"),
        "language_feature_rule_version": event.get("language_feature_rule_version"),
        "t1_return": event.get("t1_return"),
        "spy_t1_return": event.get("spy_t1_return"),
        "t1_excess_return_vs_spy": event.get("t1_excess_return_vs_spy"),
        "drift_bucket": event.get("drift_bucket"),
        "trade_enabled": False,
        "action": "observe_only",
        "counterfactual": _counterfactual_payload(core_signals),
    }


def _counterfactual_payload(core_signals: list[dict[str, Any]]) -> dict[str, Any]:
    alternatives: list[dict[str, Any]] = []
    for signal in core_signals[:MAX_COUNTERFACTUAL_SIGNALS]:
        alternatives.append(
            {
                "type": "core_signal",
                "ticker": signal.get("ticker"),
                "strategy": signal.get("strategy"),
                "confidence_score": signal.get("confidence_score"),
                "trade_quality_score": signal.get("trade_quality_score"),
                "risk_reward_ratio": signal.get("risk_reward_ratio"),
            }
        )
    alternatives.append({"type": "cash"})
    return {
        "frozen": True,
        "primary_horizon_trading_days": PRIMARY_HORIZON_TRADING_DAYS,
        "alternatives": alternatives,
    }
