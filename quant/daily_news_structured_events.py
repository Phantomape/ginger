"""Structured daily-news event rows for replayable LLM/event attribution.

This module is read-only with respect to trading behavior. It turns sanitized
daily clean-trade-news items into deterministic actor/object/relation/magnitude
event rows and fixed forward-observation rows that future attribution can close
against cash/SPY/QQQ replacement value.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

from daily_news_text_sanitation import iter_daily_news_files
from news_text_sanitizer import annotate_news_item


STRUCTURED_EVENT_RULE_VERSION = "daily_news_structured_event_ledger_v1"
FORWARD_OBSERVATION_RULE_VERSION = (
    "daily_news_structured_event_forward_observation_contract_v1"
)
TARGET_COHORT_VERSION = "structured_relation_quality_v1"
UNIT_NOTIONAL_USD = 4000.0
ENTRY_SEMANTICS = "next_session_open_after_news_date"
EXIT_SEMANTICS = "ten_trading_day_close_observation"
TEXT_FIELDS = ("title", "summary", "description")
TARGET_RELATIONS = frozenset(
    {
        "customer_order_or_partnership",
        "financial_growth_or_beat",
        "guidance_or_rating_upgrade",
        "product_or_approval_catalyst",
    }
)
EXCLUDED_POSITIVE_RELATIONS = frozenset({"capital_return"})
REQUIRED_EVENT_FIELDS = [
    "event_id",
    "event_date",
    "ticker",
    "relation_type",
    "relation_polarity",
    "actor",
    "object",
    "magnitude",
    "evidence_span",
    "sanitized_text_hash",
    "source_provenance",
]
REQUIRED_OBSERVATION_FIELDS = [
    "observation_id",
    "event_id",
    "event_date",
    "ticker",
    "relation_type",
    "relation_polarity",
    "target_relation_quality",
    "entry_semantics",
    "exit_semantics",
    "unit_notional_usd",
    "outcome_status",
]


RELATION_RULES = [
    {
        "relation_type": "financial_growth_or_beat",
        "relation_polarity": "positive",
        "object_type": "financial_result",
        "patterns": [
            r"\b(?:strong|record|better|solid)\s+(?:earnings|revenue|sales|profit|outlook)\b",
            r"\b(?:earnings|revenue|sales|profit)\s+(?:growth|grew|surges?|jumps?|beats?)\b",
            r"\b(?:beats?|outpaces?)\s+(?:the\s+)?(?:market|estimates|expectations)\b",
        ],
    },
    {
        "relation_type": "guidance_or_rating_upgrade",
        "relation_polarity": "positive",
        "object_type": "forecast_or_rating",
        "patterns": [
            r"\b(?:raises?|boosts?|lifts?)\s+(?:guidance|outlook|forecast|price target)\b",
            r"\b(?:rating\s+)?upgrade\b",
            r"\b(?:buy|outperform|overweight)\s+rating\b",
        ],
    },
    {
        "relation_type": "customer_order_or_partnership",
        "relation_polarity": "positive",
        "object_type": "commercial_relationship",
        "patterns": [
            r"\b(?:order|contract|partnership|supply deal|customer win|agreement)\b",
            r"\bdeal\s+with\b",
        ],
    },
    {
        "relation_type": "capital_return",
        "relation_polarity": "positive",
        "object_type": "capital_allocation",
        "patterns": [
            r"\b(?:buybacks?|repurchases?|dividend|capital return)\b",
        ],
    },
    {
        "relation_type": "product_or_approval_catalyst",
        "relation_polarity": "positive",
        "object_type": "product_catalyst",
        "patterns": [
            r"\b(?:launch|approval|catalyst|turning point|moonshots?)\b",
        ],
    },
    {
        "relation_type": "legal_or_regulatory_pressure",
        "relation_polarity": "negative",
        "object_type": "legal_regulatory_risk",
        "patterns": [
            r"\b(?:lawsuit|probe|investigation|regulatory pressure|faces pressure)\b",
        ],
    },
    {
        "relation_type": "downgrade_or_target_cut",
        "relation_polarity": "negative",
        "object_type": "forecast_or_rating",
        "patterns": [
            r"\b(?:downgrade|rating cut|target cut|cuts? price target)\b",
        ],
    },
    {
        "relation_type": "drawdown_or_failed_transaction",
        "relation_polarity": "negative",
        "object_type": "market_or_transaction_failure",
        "patterns": [
            r"\b(?:in the red|falls?|drops?|slumps?|attempts? continue to fail|fails?)\b",
        ],
    },
]

MAGNITUDE_RE = re.compile(
    r"(?P<value>"
    r"\$\s*\d+(?:\.\d+)?\s*(?:billion|million|bn|m)?"
    r"|"
    r"\b\d+(?:\.\d+)?\s*(?:%|x|billion|million|bn|m|bps|basis points)\b"
    r")",
    flags=re.IGNORECASE,
)
COUNTERPARTY_RE = re.compile(
    r"\b(?:with|from|for|by)\s+([A-Z][A-Za-z0-9&.\- ]{1,48})(?:\b|:|,|-)",
)


def safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def hash_text(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:length]


def sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def repo_rel(path: Path | str, repo_root: Path | str | None = None) -> str:
    value = Path(path)
    root = Path(repo_root).resolve() if repo_root else None
    if root is not None:
        try:
            return value.resolve().relative_to(root).as_posix()
        except ValueError:
            pass
    return value.as_posix()


def compact_text(value: Any) -> str:
    return re.sub(r"\s+", " ", "" if value is None else str(value)).strip()


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default


def sanitized_field_text(annotated: Mapping[str, Any], field: str) -> str:
    audit = (annotated.get("text_sanitation") or {}).get("fields") or {}
    field_audit = audit.get(field) or {}
    return compact_text(field_audit.get("sanitized_text") or annotated.get(field) or "")


def combined_sanitized_text(annotated: Mapping[str, Any]) -> str:
    parts = [sanitized_field_text(annotated, field) for field in TEXT_FIELDS]
    return "\n".join(part for part in parts if part)


def ticker_match_block(annotated: Mapping[str, Any]) -> dict[str, Any]:
    audit = annotated.get("text_sanitation") or {}
    return dict(audit.get("ticker_entity_match") or {})


def event_date_for(file_date: str | None, item: Mapping[str, Any]) -> str | None:
    published = str(item.get("published_at") or "")
    if re.match(r"^\d{4}-\d{2}-\d{2}", published):
        return published[:10]
    return file_date


def evidence_window(text: str, start: int, end: int, radius: int = 140) -> dict[str, Any]:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return {
        "start": start,
        "end": end,
        "context_start": left,
        "context_end": right,
        "text": text[left:right].strip(),
    }


def extract_magnitudes(text: str, start: int, end: int, radius: int = 90) -> dict[str, Any]:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    window = text[left:right]
    values = []
    for match in MAGNITUDE_RE.finditer(window):
        raw = compact_text(match.group("value"))
        if raw:
            values.append(raw)
    return {
        "has_numeric_magnitude": bool(values),
        "values": values[:5],
        "window_hash": hash_text(window),
    }


def infer_object(text: str, match: re.Match[str], rule: Mapping[str, Any]) -> dict[str, Any]:
    left = max(0, match.start() - 80)
    right = min(len(text), match.end() + 100)
    window = text[left:right]
    counterparty = None
    counter_match = COUNTERPARTY_RE.search(window)
    if counter_match:
        counterparty = compact_text(counter_match.group(1)).strip(" .,:;-")
    return {
        "type": rule["object_type"],
        "text": counterparty or rule["object_type"],
        "counterparty_extracted": counterparty is not None,
        "source": "local_evidence_window",
    }


def source_item_hash(
    path: Path,
    index: int,
    item: Mapping[str, Any],
    *,
    repo_root: Path | str | None = None,
) -> str:
    url = str(item.get("url") or "")
    title = compact_text(item.get("title"))
    published = str(item.get("published_at") or "")
    return hash_text(f"{repo_rel(path, repo_root)}|{index}|{published}|{url}|{title}", 24)


def build_event_id(
    event_date: str,
    ticker: str,
    relation_type: str,
    source_hash: str,
    evidence_hash: str,
) -> str:
    return hash_text(
        f"{event_date}|{ticker}|{relation_type}|{source_hash}|{evidence_hash}",
        24,
    )


def build_observation_id(event_row: Mapping[str, Any]) -> str:
    return hash_text(
        "|".join(
            [
                FORWARD_OBSERVATION_RULE_VERSION,
                TARGET_COHORT_VERSION,
                str(event_row.get("event_id") or ""),
                ENTRY_SEMANTICS,
                EXIT_SEMANTICS,
                str(int(UNIT_NOTIONAL_USD)),
            ]
        ),
        24,
    )


def iter_relation_matches(text: str) -> Iterable[tuple[Mapping[str, Any], re.Match[str]]]:
    for rule in RELATION_RULES:
        for pattern in rule["patterns"]:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                yield rule, match


def make_event_rows(
    *,
    file_record: Mapping[str, Any],
    path: Path,
    index: int,
    item: Mapping[str, Any],
    repo_root: Path | str | None = None,
    require_explicit_ticker_text: bool = True,
) -> list[dict[str, Any]]:
    annotated = annotate_news_item(item)
    text = combined_sanitized_text(annotated)
    if not text:
        return []
    ticker_block = ticker_match_block(annotated)
    matched_tickers = [
        str(ticker).upper()
        for ticker in ticker_block.get("matched_tickers") or []
        if str(ticker or "").strip()
    ]
    if require_explicit_ticker_text and not matched_tickers:
        return []

    event_date = event_date_for(str(file_record.get("news_date") or ""), item)
    if not event_date:
        return []
    source_hash = source_item_hash(path, index, item, repo_root=repo_root)
    audit = annotated.get("text_sanitation") or {}
    rows: list[dict[str, Any]] = []
    seen_local: set[tuple[str, str, str, str]] = set()
    for rule, match in iter_relation_matches(text):
        matched_phrase = compact_text(match.group(0)).lower()
        span = evidence_window(text, match.start(), match.end())
        evidence_hash = hash_text(span["text"], 24)
        magnitude = extract_magnitudes(text, match.start(), match.end())
        for ticker in matched_tickers:
            dedupe = (event_date, ticker, str(rule["relation_type"]), matched_phrase)
            if dedupe in seen_local:
                continue
            seen_local.add(dedupe)
            event_id = build_event_id(
                event_date,
                ticker,
                str(rule["relation_type"]),
                source_hash,
                evidence_hash,
            )
            rows.append(
                {
                    "event_id": event_id,
                    "rule_version": STRUCTURED_EVENT_RULE_VERSION,
                    "event_date": event_date,
                    "published_at": item.get("published_at"),
                    "ticker": ticker,
                    "relation_type": rule["relation_type"],
                    "relation_polarity": rule["relation_polarity"],
                    "actor": {
                        "type": "ticker",
                        "ticker": ticker,
                        "match_status": ticker_block.get("status"),
                        "match_confidence": ticker_block.get("confidence"),
                    },
                    "object": infer_object(text, match, rule),
                    "magnitude": magnitude,
                    "evidence_span": span,
                    "evidence_trigger": {
                        "text": matched_phrase,
                        "hash": hash_text(matched_phrase, 16),
                    },
                    "evidence_text_hash": evidence_hash,
                    "sanitized_text_hash": audit.get("post_sanitize_hash") or hash_text(text, 24),
                    "source_item_hash": source_hash,
                    "source_provenance": {
                        "kind": file_record.get("kind"),
                        "news_date": file_record.get("news_date"),
                        "path": repo_rel(path, repo_root),
                        "file_sha256": sha256_file(path),
                        "item_index": index,
                        "source": item.get("source"),
                        "tier": item.get("tier"),
                        "url": item.get("url"),
                        "raw_source": item.get("raw_source"),
                    },
                    "text_quality": {
                        "status": audit.get("status"),
                        "flags": audit.get("flags") or [],
                        "ticker_entity_status": ticker_block.get("status"),
                    },
                }
            )
    return rows


def dedupe_event_rows(rows: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    deduped: dict[str, dict[str, Any]] = {}
    duplicates = 0
    for row in rows:
        event_id = str(row["event_id"])
        if event_id in deduped:
            duplicates += 1
            continue
        deduped[event_id] = row
    ordered = sorted(
        deduped.values(),
        key=lambda row: (
            str(row.get("event_date") or ""),
            str(row.get("ticker") or ""),
            str(row.get("relation_type") or ""),
            str(row.get("event_id") or ""),
        ),
    )
    return ordered, duplicates


def required_field_audit(
    rows: list[dict[str, Any]],
    required_fields: Iterable[str],
) -> dict[str, Any]:
    missing_counts: Counter[str] = Counter()
    required = list(required_fields)
    for row in rows:
        for field in required:
            value = row.get(field)
            if value is None or value == "" or value == {}:
                missing_counts[field] += 1
    return {
        "required_fields": required,
        "missing_counts": dict(sorted(missing_counts.items())),
        "all_required_fields_present": not missing_counts,
    }


def build_structured_event_ledger(
    news_root: Path | str,
    *,
    repo_root: Path | str | None = None,
    kinds: Iterable[str] | None = ("clean_trade_news",),
    start_date: str | None = None,
    end_date: str | None = None,
    require_explicit_ticker_text: bool = True,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    file_count = 0
    raw_items = 0
    explicit_items = 0
    unreadable_files = 0
    source_date_counts: Counter[str] = Counter()
    ignored_temp_files = 0
    for file_record in iter_daily_news_files(news_root, kinds=kinds):
        ignored_temp_files = max(
            ignored_temp_files,
            int(file_record.get("ignored_temp_files_seen") or 0),
        )
        news_date = str(file_record.get("news_date") or "")
        if start_date and news_date and news_date < start_date:
            continue
        if end_date and news_date and news_date > end_date:
            continue
        path = Path(file_record["path"])
        file_count += 1
        raw = read_json(path, [])
        if not isinstance(raw, list):
            unreadable_files += 1
            continue
        raw_items += len(raw)
        for index, item in enumerate(raw):
            if not isinstance(item, Mapping):
                continue
            annotated = annotate_news_item(item)
            ticker_block = ticker_match_block(annotated)
            if ticker_block.get("status") == "explicit_text_match":
                explicit_items += 1
            event_rows = make_event_rows(
                file_record=file_record,
                path=path,
                index=index,
                item=item,
                repo_root=repo_root,
                require_explicit_ticker_text=require_explicit_ticker_text,
            )
            if event_rows:
                source_date_counts[news_date or "unknown"] += len(event_rows)
            rows.extend(event_rows)
    deduped, duplicate_input_rows = dedupe_event_rows(rows)
    dates = [str(row["event_date"]) for row in deduped if row.get("event_date")]
    relation_counts = Counter(str(row["relation_type"]) for row in deduped)
    polarity_counts = Counter(str(row["relation_polarity"]) for row in deduped)
    ticker_counts = Counter(str(row["ticker"]) for row in deduped)
    magnitude_rows = sum(
        1
        for row in deduped
        if isinstance(row.get("magnitude"), Mapping)
        and row["magnitude"].get("has_numeric_magnitude")
    )
    event_id_counts = Counter(str(row["event_id"]) for row in deduped)
    duplicate_event_ids = sum(1 for count in event_id_counts.values() if count > 1)
    target_rows = [row for row in deduped if is_target_relation_quality(row)]
    event_field_audit = required_field_audit(deduped, REQUIRED_EVENT_FIELDS)
    return {
        "rule_version": STRUCTURED_EVENT_RULE_VERSION,
        "rows": deduped,
        "audit": {
            "news_root": str(news_root),
            "source_kind": ",".join(kinds or []),
            "file_count": file_count,
            "ignored_temp_file_count": ignored_temp_files,
            "unreadable_files": unreadable_files,
            "raw_items": raw_items,
            "explicit_ticker_items": explicit_items,
            "raw_event_rows": len(rows),
            "ledger_rows": len(deduped),
            "duplicate_input_rows_removed": duplicate_input_rows,
            "duplicate_event_ids": duplicate_event_ids,
            "date_range": {
                "start": min(dates) if dates else None,
                "end": max(dates) if dates else None,
            },
            "event_date_count": len(set(dates)),
            "source_date_counts": dict(sorted(source_date_counts.items())),
            "relation_counts": dict(sorted(relation_counts.items())),
            "polarity_counts": dict(sorted(polarity_counts.items())),
            "ticker_top20": dict(ticker_counts.most_common(20)),
            "magnitude_rows": magnitude_rows,
            "magnitude_row_share": magnitude_rows / len(deduped) if deduped else 0.0,
            "target_relation_quality_rows": len(target_rows),
            "target_relation_quality_event_dates": len(
                {row["event_date"] for row in target_rows if row.get("event_date")}
            ),
            "target_relation_quality_tickers": len(
                {row["ticker"] for row in target_rows if row.get("ticker")}
            ),
            "required_field_audit": event_field_audit,
        },
    }


def is_target_relation_quality(row: Mapping[str, Any]) -> bool:
    return (
        row.get("relation_polarity") == "positive"
        and str(row.get("relation_type") or "") in TARGET_RELATIONS
    )


def make_forward_observation(row: Mapping[str, Any]) -> dict[str, Any]:
    target = is_target_relation_quality(row)
    magnitude = row.get("magnitude") if isinstance(row.get("magnitude"), Mapping) else {}
    return {
        "observation_id": build_observation_id(row),
        "rule_version": FORWARD_OBSERVATION_RULE_VERSION,
        "target_cohort_version": TARGET_COHORT_VERSION,
        "source_event_rule_version": row.get("rule_version"),
        "event_id": row.get("event_id"),
        "event_date": row.get("event_date"),
        "published_at": row.get("published_at"),
        "ticker": row.get("ticker"),
        "relation_type": row.get("relation_type"),
        "relation_polarity": row.get("relation_polarity"),
        "target_relation_quality": target,
        "excluded_positive_relation": str(row.get("relation_type") or "")
        in EXCLUDED_POSITIVE_RELATIONS,
        "magnitude_qualified": bool(magnitude.get("has_numeric_magnitude")),
        "entry_semantics": ENTRY_SEMANTICS,
        "exit_semantics": EXIT_SEMANTICS,
        "entry_date": None,
        "target_price": None,
        "unit_notional_usd": UNIT_NOTIONAL_USD,
        "outcome_status": "pending_forward_close",
        "forward_5d_return_pct": None,
        "forward_10d_return_pct": None,
        "replacement_value_vs_cash_usd": None,
        "replacement_value_vs_spy_usd": None,
        "replacement_value_vs_qqq_usd": None,
        "evidence_text_hash": row.get("evidence_text_hash"),
        "sanitized_text_hash": row.get("sanitized_text_hash"),
        "source_item_hash": row.get("source_item_hash"),
        "source_provenance": row.get("source_provenance"),
    }


def build_forward_observation_contract(
    event_rows: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    observations = [make_forward_observation(row) for row in event_rows]
    observation_id_counts = Counter(str(row["observation_id"]) for row in observations)
    duplicate_observation_ids = sum(
        1 for count in observation_id_counts.values() if count > 1
    )
    target_rows = [row for row in observations if row["target_relation_quality"]]
    dates = [str(row["event_date"]) for row in observations if row.get("event_date")]
    relation_counts = Counter(str(row["relation_type"]) for row in observations)
    return {
        "rule_version": FORWARD_OBSERVATION_RULE_VERSION,
        "target_cohort_version": TARGET_COHORT_VERSION,
        "rows": observations,
        "audit": {
            "observation_rows": len(observations),
            "duplicate_observation_ids": duplicate_observation_ids,
            "target_relation_quality_rows": len(target_rows),
            "target_relation_quality_event_dates": len(
                {row["event_date"] for row in target_rows if row.get("event_date")}
            ),
            "target_relation_quality_tickers": len(
                {row["ticker"] for row in target_rows if row.get("ticker")}
            ),
            "date_range": {
                "start": min(dates) if dates else None,
                "end": max(dates) if dates else None,
            },
            "event_date_count": len(set(dates)),
            "relation_counts": dict(sorted(relation_counts.items())),
            "required_field_audit": required_field_audit(
                observations,
                REQUIRED_OBSERVATION_FIELDS,
            ),
        },
    }
