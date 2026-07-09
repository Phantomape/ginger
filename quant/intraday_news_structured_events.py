"""Structured intraday-news event rows for replayable LLM/event attribution.

This module is read-only with respect to trading behavior. It turns sanitized
intraday trade-news snapshots into deterministic event rows and pending forward
observations so future runs can close them against replacement value without
depending on prompt text.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping

from daily_news_structured_events import (
    EXCLUDED_POSITIVE_RELATIONS,
    TARGET_COHORT_VERSION,
    UNIT_NOTIONAL_USD,
    build_event_id,
    compact_text,
    dedupe_event_rows,
    evidence_window,
    extract_magnitudes,
    hash_text,
    infer_object,
    is_target_relation_quality,
    iter_relation_matches,
    read_json,
    repo_rel,
    required_field_audit,
    safe,
    sanitized_field_text,
    sha256_file,
    source_item_hash,
    ticker_match_block,
)
from news_text_sanitizer import annotate_news_item
try:
    from us_market_calendar import is_us_equity_session
except ModuleNotFoundError:  # pragma: no cover - package import fallback
    from quant.us_market_calendar import is_us_equity_session


STRUCTURED_EVENT_RULE_VERSION = "intraday_news_structured_event_ledger_v1"
FORWARD_OBSERVATION_RULE_VERSION = (
    "intraday_news_structured_event_forward_observation_contract_v1"
)
ENTRY_SEMANTICS = "next_session_open_after_intraday_capture"
EXIT_SEMANTICS = "ten_trading_day_close_observation"
TEXT_FIELDS = ("title", "summary", "description")
REQUIRED_EVENT_FIELDS = [
    "event_id",
    "event_date",
    "capture_date",
    "time_label",
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
    "capture_date",
    "time_label",
    "ticker",
    "relation_type",
    "relation_polarity",
    "target_relation_quality",
    "entry_semantics",
    "exit_semantics",
    "entry_date",
    "entry_date_status",
    "target_price_applicability",
    "unit_notional_usd",
    "outcome_status",
]

_TRADE_NEWS_RE = re.compile(
    r"^intraday_trade_news_(?P<date>\d{8})_(?P<time>[A-Za-z0-9]+)\.json$"
)


def _capture_date(date_token: str | None) -> str | None:
    if not date_token or len(date_token) != 8:
        return None
    return f"{date_token[:4]}-{date_token[4:6]}-{date_token[6:]}"


def _parse_intraday_trade_news_name(path: Path) -> dict[str, str | None] | None:
    match = _TRADE_NEWS_RE.match(path.name)
    if not match:
        return None
    date_token = match.group("date")
    return {
        "date_token": date_token,
        "capture_date": _capture_date(date_token),
        "time_label": match.group("time"),
    }


def intraday_snapshot_path_for(
    news_path: Path | str,
    *,
    intraday_root: Path | str | None = None,
) -> Path:
    path = Path(news_path)
    parsed = _parse_intraday_trade_news_name(path)
    if not parsed:
        return path.with_name(path.name.replace("intraday_trade_news_", "intraday_review_"))
    root = Path(intraday_root) if intraday_root is not None else path.parents[1]
    return (
        root
        / "snapshots"
        / f"intraday_review_{parsed['date_token']}_{parsed['time_label']}.json"
    )


def iter_intraday_trade_news_files(
    intraday_root: Path | str,
) -> list[dict[str, Any]]:
    """Return final intraday trade-news files and ignored temp-file count."""
    root = Path(intraday_root)
    news_dir = root / "news"
    records: list[dict[str, Any]] = []
    ignored_temp_files = 0
    for path in sorted(news_dir.glob("intraday_trade_news_*.json")):
        parsed = _parse_intraday_trade_news_name(path)
        if (
            path.is_file()
            and path.suffix == ".json"
            and not path.name.startswith(".")
            and parsed is not None
        ):
            snapshot_path = intraday_snapshot_path_for(path, intraday_root=root)
            records.append(
                {
                    "kind": "intraday_trade_news",
                    "path": path,
                    "capture_date": parsed["capture_date"],
                    "news_date": parsed["capture_date"],
                    "date_token": parsed["date_token"],
                    "time_label": parsed["time_label"],
                    "snapshot_path": snapshot_path,
                    "snapshot_exists": snapshot_path.exists(),
                }
            )
        else:
            ignored_temp_files += 1
    ignored_temp_files += sum(
        1
        for path in news_dir.glob(".intraday_trade_news_*.json.*.tmp")
        if path.is_file()
    )
    records.sort(
        key=lambda row: (
            str(row.get("capture_date") or ""),
            str(row.get("time_label") or ""),
            str(row.get("path") or ""),
        )
    )
    for row in records:
        row["ignored_temp_files_seen"] = ignored_temp_files
    return records


def _event_date_for(file_record: Mapping[str, Any], item: Mapping[str, Any]) -> str | None:
    published = str(item.get("published_at") or "")
    if re.match(r"^\d{4}-\d{2}-\d{2}", published):
        return published[:10]
    return str(file_record.get("capture_date") or "") or None


def _combined_sanitized_text(annotated: Mapping[str, Any]) -> str:
    parts = [sanitized_field_text(annotated, field) for field in TEXT_FIELDS]
    return "\n".join(part for part in parts if part)


def _snapshot_metadata(file_record: Mapping[str, Any]) -> dict[str, Any]:
    snapshot_path = Path(file_record["snapshot_path"])
    snapshot = read_json(snapshot_path, {})
    if not isinstance(snapshot, Mapping):
        snapshot = {}
    return {
        "snapshot_path": snapshot_path,
        "snapshot_exists": bool(file_record.get("snapshot_exists")),
        "snapshot_file_sha256": sha256_file(snapshot_path)
        if bool(file_record.get("snapshot_exists"))
        else None,
        "generated_at_et": snapshot.get("generated_at_et"),
        "generated_at_pt": snapshot.get("generated_at_pt"),
        "capture_time_et": snapshot.get("capture_time_et"),
        "date": snapshot.get("date"),
        "time_label": snapshot.get("time_label"),
    }


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
    text = _combined_sanitized_text(annotated)
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

    event_date = _event_date_for(file_record, item)
    capture_date = str(file_record.get("capture_date") or "") or None
    time_label = str(file_record.get("time_label") or "") or None
    if not event_date or not capture_date or not time_label:
        return []

    source_hash = source_item_hash(path, index, item, repo_root=repo_root)
    audit = annotated.get("text_sanitation") or {}
    snapshot = _snapshot_metadata(file_record)
    rows: list[dict[str, Any]] = []
    seen_local: set[tuple[str, str, str, str]] = set()
    for rule, match in iter_relation_matches(text):
        matched_phrase = compact_text(match.group(0)).lower()
        span = evidence_window(text, match.start(), match.end())
        evidence_hash = hash_text(span["text"], 24)
        magnitude = extract_magnitudes(text, match.start(), match.end())
        for ticker in matched_tickers:
            dedupe = (capture_date, time_label, ticker, str(rule["relation_type"]), matched_phrase)
            if dedupe in seen_local:
                continue
            seen_local.add(dedupe)
            event_id = build_event_id(
                f"{capture_date}T{time_label}",
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
                    "capture_date": capture_date,
                    "time_label": time_label,
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
                    "sanitized_text_hash": audit.get("post_sanitize_hash")
                    or hash_text(text, 24),
                    "source_item_hash": source_hash,
                    "source_provenance": {
                        "kind": file_record.get("kind"),
                        "capture_date": capture_date,
                        "time_label": time_label,
                        "path": repo_rel(path, repo_root),
                        "file_sha256": sha256_file(path),
                        "item_index": index,
                        "source": item.get("source"),
                        "tier": item.get("tier"),
                        "url": item.get("url"),
                        "raw_source": item.get("raw_source"),
                        "snapshot_path": repo_rel(snapshot["snapshot_path"], repo_root),
                        "snapshot_exists": snapshot["snapshot_exists"],
                        "snapshot_file_sha256": snapshot["snapshot_file_sha256"],
                        "snapshot_generated_at_et": snapshot["generated_at_et"],
                        "snapshot_capture_time_et": snapshot["capture_time_et"],
                    },
                    "text_quality": {
                        "status": audit.get("status"),
                        "flags": audit.get("flags") or [],
                        "ticker_entity_status": ticker_block.get("status"),
                    },
                }
            )
    return rows


def build_structured_event_ledger(
    intraday_root: Path | str,
    *,
    repo_root: Path | str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    require_explicit_ticker_text: bool = True,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    file_count = 0
    raw_items = 0
    explicit_items = 0
    unreadable_files = 0
    missing_snapshots = 0
    ignored_temp_files = 0
    source_capture_counts: Counter[str] = Counter()
    for file_record in iter_intraday_trade_news_files(intraday_root):
        ignored_temp_files = max(
            ignored_temp_files,
            int(file_record.get("ignored_temp_files_seen") or 0),
        )
        capture_date = str(file_record.get("capture_date") or "")
        if start_date and capture_date and capture_date < start_date:
            continue
        if end_date and capture_date and capture_date > end_date:
            continue
        path = Path(file_record["path"])
        file_count += 1
        if not file_record.get("snapshot_exists"):
            missing_snapshots += 1
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
                source_capture_counts[
                    f"{capture_date}_{file_record.get('time_label') or 'unknown'}"
                ] += len(event_rows)
            rows.extend(event_rows)

    deduped, duplicate_input_rows = dedupe_event_rows(rows)
    dates = [str(row["event_date"]) for row in deduped if row.get("event_date")]
    captures = [
        f"{row.get('capture_date')}_{row.get('time_label')}"
        for row in deduped
        if row.get("capture_date") and row.get("time_label")
    ]
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
            "intraday_root": str(intraday_root),
            "source_kind": "intraday_trade_news",
            "file_count": file_count,
            "ignored_temp_file_count": ignored_temp_files,
            "unreadable_files": unreadable_files,
            "missing_snapshot_files": missing_snapshots,
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
            "capture_count": len(set(captures)),
            "event_date_count": len(set(dates)),
            "source_capture_counts": dict(sorted(source_capture_counts.items())),
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


def build_observation_id(event_row: Mapping[str, Any]) -> str:
    return hash_text(
        "|".join(
            [
                FORWARD_OBSERVATION_RULE_VERSION,
                TARGET_COHORT_VERSION,
                str(event_row.get("event_id") or ""),
                str(event_row.get("capture_date") or ""),
                str(event_row.get("time_label") or ""),
                ENTRY_SEMANTICS,
                EXIT_SEMANTICS,
                str(int(UNIT_NOTIONAL_USD)),
            ]
        ),
        24,
    )


def next_session_after(day: str | date | None) -> str | None:
    if day is None:
        return None
    if isinstance(day, date):
        current = day
    else:
        try:
            current = datetime.fromisoformat(str(day)[:10]).date()
        except ValueError:
            return None
    cursor = current + timedelta(days=1)
    for _ in range(14):
        if is_us_equity_session(cursor):
            return cursor.isoformat()
        cursor += timedelta(days=1)
    return None


def make_forward_observation(row: Mapping[str, Any]) -> dict[str, Any]:
    target = is_target_relation_quality(row)
    magnitude = row.get("magnitude") if isinstance(row.get("magnitude"), Mapping) else {}
    entry_date = next_session_after(row.get("capture_date") or row.get("event_date"))
    return {
        "observation_id": build_observation_id(row),
        "rule_version": FORWARD_OBSERVATION_RULE_VERSION,
        "target_cohort_version": TARGET_COHORT_VERSION,
        "source_event_rule_version": row.get("rule_version"),
        "event_id": row.get("event_id"),
        "event_date": row.get("event_date"),
        "capture_date": row.get("capture_date"),
        "time_label": row.get("time_label"),
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
        "entry_date": entry_date,
        "entry_date_status": "planned_next_session_open" if entry_date else "unresolved",
        "target_price": None,
        "target_price_applicability": "not_applicable_fixed_horizon_observation",
        "target_price_reason": (
            "Intraday structured-news observations close by fixed 10-session "
            "attribution horizon; no target-price exit or order is scheduled."
        ),
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
    captures = [
        f"{row.get('capture_date')}_{row.get('time_label')}"
        for row in observations
        if row.get("capture_date") and row.get("time_label")
    ]
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
            "capture_count": len(set(captures)),
            "event_date_count": len(set(dates)),
            "relation_counts": dict(sorted(relation_counts.items())),
            "required_field_audit": required_field_audit(
                observations,
                REQUIRED_OBSERVATION_FIELDS,
            ),
        },
    }


__all__ = [
    "ENTRY_SEMANTICS",
    "EXIT_SEMANTICS",
    "FORWARD_OBSERVATION_RULE_VERSION",
    "REQUIRED_EVENT_FIELDS",
    "REQUIRED_OBSERVATION_FIELDS",
    "STRUCTURED_EVENT_RULE_VERSION",
    "build_forward_observation_contract",
    "build_structured_event_ledger",
    "iter_intraday_trade_news_files",
    "make_event_rows",
    "make_forward_observation",
    "next_session_after",
    "safe",
]
