from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


QUEUE_NAME = "FORM4_MEANINGFUL_PURCHASE_FORWARD_QUEUE"
RULE_VERSION = "form4_meaningful_purchase_ge_500k_v1"
BASE_MEANINGFUL_PURCHASE_VALUE = 50_000.0
FORWARD_QUEUE_MIN_PURCHASE_VALUE = 500_000.0
PRIMARY_HORIZON_TRADING_DAYS = 10
MAX_SAMPLE_VALUES = 4


def _norm_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _float_or_zero(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _owner_is_issuer(row: dict[str, Any]) -> bool:
    owner = _norm_text(row.get("owner_name"))
    issuer = _norm_text(row.get("issuer_name"))
    symbol = _norm_text(row.get("issuer_trading_symbol") or row.get("ticker"))
    if not owner:
        return False
    if issuer and (owner == issuer or issuer in owner or owner in issuer):
        return True
    return bool(symbol and owner == symbol)


def _is_ceo_cfo_or_president(title: Any) -> bool:
    text = str(title or "").lower()
    return any(token in text for token in (
        "chief executive",
        "chief financial",
        "ceo",
        "cfo",
        "president",
    ))


def load_form4_transaction_rows(path: str | Path) -> list[dict[str, Any]]:
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


def latest_form4_transactions_path(data_dir: str | Path) -> Path | None:
    root = Path(data_dir)
    candidates = sorted(root.glob("form4_transactions_*.jsonl"))
    return candidates[-1] if candidates else None


def aggregate_purchase_events(
    rows: list[dict[str, Any]],
    *,
    start: str | None = None,
    end: str | None = None,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}

    for row in rows:
        if not row.get("open_market_purchase_flag"):
            continue
        ticker = str(row.get("ticker") or "").upper()
        usable_trade_date = str(row.get("usable_trade_date") or "")[:10]
        if not ticker or not usable_trade_date:
            continue
        if start and usable_trade_date < start:
            continue
        if end and usable_trade_date > end:
            continue

        key = (ticker, usable_trade_date)
        event = grouped.setdefault(key, {
            "ticker": ticker,
            "usable_trade_date": usable_trade_date,
            "purchase_transaction_count": 0,
            "filing_count": 0,
            "owner_count": 0,
            "total_purchase_value": 0.0,
            "max_purchase_value": 0.0,
            "any_10b5_1_flag": False,
            "any_option_exercise_flag": False,
            "any_owner_is_issuer": False,
            "any_ceo_cfo_or_president": False,
            "any_officer": False,
            "any_director": False,
            "any_10pct_owner": False,
            "_accessions": set(),
            "_owners": set(),
            "sample_owner_names": [],
            "sample_officer_titles": [],
            "sample_archive_urls": [],
        })

        value = _float_or_zero(row.get("transaction_value"))
        event["purchase_transaction_count"] += 1
        event["total_purchase_value"] += value
        event["max_purchase_value"] = max(event["max_purchase_value"], value)
        event["any_10b5_1_flag"] = event["any_10b5_1_flag"] or bool(row.get("10b5_1_flag"))
        event["any_option_exercise_flag"] = event["any_option_exercise_flag"] or bool(row.get("option_exercise_flag"))
        event["any_owner_is_issuer"] = event["any_owner_is_issuer"] or _owner_is_issuer(row)
        event["any_ceo_cfo_or_president"] = event["any_ceo_cfo_or_president"] or _is_ceo_cfo_or_president(row.get("officer_title"))
        event["any_officer"] = event["any_officer"] or bool(row.get("is_officer"))
        event["any_director"] = event["any_director"] or bool(row.get("is_director"))
        event["any_10pct_owner"] = event["any_10pct_owner"] or bool(row.get("is_10pct_owner"))

        if row.get("accession_number"):
            event["_accessions"].add(str(row["accession_number"]))
        if row.get("owner_cik"):
            event["_owners"].add(str(row["owner_cik"]))
        _append_sample(event["sample_owner_names"], row.get("owner_name"))
        _append_sample(event["sample_officer_titles"], row.get("officer_title"))
        _append_sample(event["sample_archive_urls"], row.get("archive_url"))

    events = []
    for event in grouped.values():
        accessions = sorted(event.pop("_accessions"))
        owners = sorted(event.pop("_owners"))
        event["accessions"] = accessions[:MAX_SAMPLE_VALUES]
        event["filing_count"] = len(accessions)
        event["owner_count"] = len(owners)
        event["total_purchase_value"] = round(float(event["total_purchase_value"]), 2)
        event["max_purchase_value"] = round(float(event["max_purchase_value"]), 2)
        event["meaningful_purchase_v1"] = qualifies_meaningful_purchase(event)
        event["form4_forward_queue_candidate"] = qualifies_forward_queue_event(event)
        events.append(event)

    return sorted(events, key=lambda row: (row["usable_trade_date"], row["ticker"]))


def _append_sample(values: list[Any], value: Any) -> None:
    if value and value not in values and len(values) < MAX_SAMPLE_VALUES:
        values.append(value)


def qualifies_meaningful_purchase(
    event: dict[str, Any],
    *,
    min_total_purchase_value: float = BASE_MEANINGFUL_PURCHASE_VALUE,
) -> bool:
    return (
        _float_or_zero(event.get("total_purchase_value")) >= min_total_purchase_value
        and not event.get("any_10b5_1_flag")
        and not event.get("any_option_exercise_flag")
        and not event.get("any_owner_is_issuer")
        and bool(event.get("any_officer") or event.get("any_director") or event.get("any_10pct_owner"))
    )


def qualifies_forward_queue_event(
    event: dict[str, Any],
    *,
    min_total_purchase_value: float = FORWARD_QUEUE_MIN_PURCHASE_VALUE,
) -> bool:
    return (
        qualifies_meaningful_purchase(event)
        and _float_or_zero(event.get("total_purchase_value")) >= min_total_purchase_value
    )


def build_form4_event_queue(
    events: list[dict[str, Any]],
    *,
    as_of: str,
    core_signals: list[dict[str, Any]] | None = None,
    source_path: str | Path | None = None,
    source_status: str = "loaded",
) -> dict[str, Any]:
    candidates = [
        _candidate_payload(event, core_signals=core_signals)
        for event in events
        if str(event.get("usable_trade_date") or "")[:10] == as_of
        and qualifies_forward_queue_event(event)
    ]
    return {
        "queue_name": QUEUE_NAME,
        "rule_version": RULE_VERSION,
        "enabled": False,
        "asof_date": as_of,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "data_source": {
            "status": source_status,
            "path": str(source_path) if source_path else None,
            "loaded_event_count": len(events),
        },
        "parameters": {
            "base_meaningful_purchase_min_total_value": BASE_MEANINGFUL_PURCHASE_VALUE,
            "forward_queue_min_total_purchase_value": FORWARD_QUEUE_MIN_PURCHASE_VALUE,
            "primary_horizon_trading_days": PRIMARY_HORIZON_TRADING_DAYS,
        },
        "production_impact": {
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "scope": "observe_only_forward_event_queue",
        },
        "next_action": "observe_only_freeze_counterfactuals_before_any_trade",
    }


def build_forward_queue_from_transactions(
    *,
    data_dir: str | Path,
    as_of: str,
    core_signals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    path = latest_form4_transactions_path(data_dir)
    if path is None:
        return build_form4_event_queue(
            [],
            as_of=as_of,
            core_signals=core_signals,
            source_status="missing_form4_transactions_jsonl",
        )
    rows = load_form4_transaction_rows(path)
    events = aggregate_purchase_events(rows, start=as_of, end=as_of)
    return build_form4_event_queue(
        events,
        as_of=as_of,
        core_signals=core_signals,
        source_path=path,
    )


def empty_form4_event_queue(as_of: str, reason: str) -> dict[str, Any]:
    queue = build_form4_event_queue([], as_of=as_of, source_status=reason)
    queue["error"] = reason
    return queue


def _candidate_payload(
    event: dict[str, Any],
    *,
    core_signals: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "ticker": event.get("ticker"),
        "usable_trade_date": event.get("usable_trade_date"),
        "total_purchase_value": event.get("total_purchase_value"),
        "purchase_transaction_count": event.get("purchase_transaction_count"),
        "filing_count": event.get("filing_count"),
        "owner_count": event.get("owner_count"),
        "sample_owner_names": event.get("sample_owner_names") or [],
        "sample_officer_titles": event.get("sample_officer_titles") or [],
        "accessions": event.get("accessions") or [],
        "sample_archive_urls": event.get("sample_archive_urls") or [],
        "event_flags": {
            "meaningful_purchase_v1": event.get("meaningful_purchase_v1"),
            "any_ceo_cfo_or_president": event.get("any_ceo_cfo_or_president"),
            "any_officer": event.get("any_officer"),
            "any_director": event.get("any_director"),
            "any_10pct_owner": event.get("any_10pct_owner"),
        },
        "trade_enabled": False,
        "action": "observe_only",
        "counterfactual": _counterfactual_payload(core_signals or []),
    }


def _counterfactual_payload(core_signals: list[dict[str, Any]]) -> dict[str, Any]:
    alternatives: list[dict[str, Any]] = []
    if core_signals:
        top = core_signals[0]
        alternatives.append({
            "type": "core_signal",
            "weight": 0.5,
            "ticker": top.get("ticker"),
            "strategy": top.get("strategy"),
            "confidence_score": top.get("confidence_score"),
            "trade_quality_score": top.get("trade_quality_score"),
        })
    alternatives.append({
        "type": "cash",
        "weight": 0.5 if core_signals else 1.0,
    })
    return {
        "frozen": True,
        "primary_horizon_trading_days": PRIMARY_HORIZON_TRADING_DAYS,
        "alternatives": alternatives,
    }
