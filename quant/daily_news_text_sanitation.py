"""Replayable text-quality audit for daily clean news archives.

This helper is read-only. It audits final daily clean-news and clean-trade-news
JSON files and returns deterministic item hashes, sanitation flags, and ticker
provenance metadata without rewriting the source archives.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

from news_text_sanitizer import annotate_news_item, build_news_sanitation_summary


RULE_VERSION = "daily_news_text_sanitation_contract_v1"
CORE_SANITIZER_SOURCE = "intraday_news_text_sanitation_contract_v1"
NEWS_FILE_PATTERNS = {
    "clean_news": "clean_news_*.json",
    "clean_trade_news": "clean_trade_news_*.json",
}
TEXT_FIELDS = ("title", "summary", "description")
_DATE_RE = re.compile(r"_(\d{8})\.json$")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_news_date(path: Path) -> str | None:
    match = _DATE_RE.search(path.name)
    if not match:
        return None
    value = match.group(1)
    return f"{value[:4]}-{value[4:6]}-{value[6:]}"


def _is_final_json(path: Path) -> bool:
    return path.is_file() and path.suffix == ".json" and not path.name.startswith(".")


def iter_daily_news_files(
    news_root: Path | str,
    *,
    kinds: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Return final daily news archive files and ignored temp-file count."""
    root = Path(news_root)
    selected_kinds = list(kinds or NEWS_FILE_PATTERNS)
    records: list[dict[str, Any]] = []
    ignored_temp_files = 0
    for kind in selected_kinds:
        pattern = NEWS_FILE_PATTERNS[kind]
        folder = root / ("clean" if kind == "clean_news" else "trade")
        for path in sorted(folder.glob(pattern)):
            if _is_final_json(path):
                records.append(
                    {
                        "kind": kind,
                        "path": path,
                        "news_date": _parse_news_date(path),
                    }
                )
            else:
                ignored_temp_files += 1
        ignored_temp_files += sum(1 for path in folder.glob(f".{pattern}.*.tmp") if path.is_file())
    records.sort(key=lambda row: (row["news_date"] or "", row["kind"], str(row["path"])))
    for row in records:
        row["ignored_temp_files_seen"] = ignored_temp_files
    return records


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _item_text_hashes(annotated: Mapping[str, Any]) -> dict[str, str | None]:
    audit = annotated.get("text_sanitation") or {}
    fields = audit.get("fields") or {}
    hashes: dict[str, str | None] = {}
    for field in TEXT_FIELDS:
        field_audit = fields.get(field) or {}
        hashes[f"{field}_pre_hash"] = field_audit.get("pre_sanitize_hash")
        hashes[f"{field}_post_hash"] = field_audit.get("post_sanitize_hash")
    return hashes


def _compact_item_record(index: int, item: Mapping[str, Any]) -> dict[str, Any]:
    audit = item.get("text_sanitation") or {}
    ticker = audit.get("ticker_entity_match") or {}
    return {
        "index": index,
        "source": item.get("source"),
        "tier": item.get("tier"),
        "published_at": item.get("published_at"),
        "tickers": ticker.get("tickers") or item.get("tickers") or [],
        "status": audit.get("status"),
        "flags": audit.get("flags") or [],
        "changed": bool(audit.get("changed")),
        "pre_sanitize_hash": audit.get("pre_sanitize_hash"),
        "post_sanitize_hash": audit.get("post_sanitize_hash"),
        "field_hashes": _item_text_hashes(item),
        "ticker_entity_status": ticker.get("status"),
        "ticker_entity_confidence": ticker.get("confidence"),
        "matched_tickers": ticker.get("matched_tickers") or [],
    }


def audit_daily_news_file(path: Path | str, *, kind: str, news_date: str | None = None) -> dict[str, Any]:
    """Audit one final daily news archive file."""
    source_path = Path(path)
    try:
        raw = _read_json(source_path)
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "kind": kind,
            "path": str(source_path),
            "news_date": news_date or _parse_news_date(source_path),
            "exists": source_path.exists(),
            "readable": False,
            "error": str(exc),
            "rows": 0,
            "summary": build_news_sanitation_summary([]),
            "items": [],
        }

    if not isinstance(raw, list):
        return {
            "kind": kind,
            "path": str(source_path),
            "news_date": news_date or _parse_news_date(source_path),
            "exists": source_path.exists(),
            "readable": True,
            "schema_valid": False,
            "rows": 0,
            "summary": build_news_sanitation_summary([]),
            "items": [],
        }

    annotated = []
    for item in raw:
        row = annotate_news_item(item)
        audit = dict(row.get("text_sanitation") or {})
        audit["source_rule_version"] = audit.get("rule_version") or CORE_SANITIZER_SOURCE
        audit["rule_version"] = RULE_VERSION
        row["text_sanitation"] = audit
        annotated.append(row)

    summary = build_news_sanitation_summary(annotated)
    summary["rule_version"] = RULE_VERSION
    summary["source_rule_version"] = CORE_SANITIZER_SOURCE
    return {
        "kind": kind,
        "path": str(source_path),
        "news_date": news_date or _parse_news_date(source_path),
        "exists": source_path.exists(),
        "readable": True,
        "schema_valid": True,
        "sha256": _sha256_file(source_path),
        "rows": len(raw),
        "summary": summary,
        "items": [_compact_item_record(index, item) for index, item in enumerate(annotated)],
    }


def build_daily_news_sanitation_audit(
    news_root: Path | str,
    *,
    kinds: Iterable[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    sample_limit: int = 8,
) -> dict[str, Any]:
    """Build a repository-wide daily news text sanitation audit."""
    root = Path(news_root)
    files = []
    ignored_temp_files = 0
    for row in iter_daily_news_files(root, kinds=kinds):
        ignored_temp_files = max(ignored_temp_files, int(row.get("ignored_temp_files_seen") or 0))
        news_date = row.get("news_date")
        if start_date and news_date and news_date < start_date:
            continue
        if end_date and news_date and news_date > end_date:
            continue
        files.append(audit_daily_news_file(row["path"], kind=row["kind"], news_date=news_date))

    status_counts: Counter[str] = Counter()
    flag_counts: Counter[str] = Counter()
    ticker_counts: Counter[str] = Counter()
    kind_counts: Counter[str] = Counter()
    rows_by_kind: Counter[str] = Counter()
    flagged_examples: list[dict[str, Any]] = []
    changed_items = 0
    flagged_items = 0
    hash_fields_missing = 0
    total_items = 0
    for file_row in files:
        kind = str(file_row.get("kind") or "unknown")
        kind_counts[kind] += 1
        rows_by_kind[kind] += int(file_row.get("rows") or 0)
        for item in file_row.get("items") or []:
            total_items += 1
            status_counts[str(item.get("status") or "unknown")] += 1
            flags = [str(flag) for flag in item.get("flags") or []]
            if flags:
                flagged_items += 1
                if len(flagged_examples) < sample_limit:
                    flagged_examples.append(
                        {
                            "kind": kind,
                            "news_date": file_row.get("news_date"),
                            "path": file_row.get("path"),
                            "index": item.get("index"),
                            "source": item.get("source"),
                            "tickers": item.get("tickers") or [],
                            "status": item.get("status"),
                            "flags": flags,
                            "ticker_entity_status": item.get("ticker_entity_status"),
                        }
                    )
            flag_counts.update(flags)
            if item.get("changed"):
                changed_items += 1
            ticker_counts[str(item.get("ticker_entity_status") or "unknown")] += 1
            if not item.get("pre_sanitize_hash") or not item.get("post_sanitize_hash"):
                hash_fields_missing += 1

    return {
        "rule_version": RULE_VERSION,
        "source_rule_version": CORE_SANITIZER_SOURCE,
        "news_root": str(root),
        "file_count": len(files),
        "file_count_by_kind": dict(sorted(kind_counts.items())),
        "ignored_temp_file_count": ignored_temp_files,
        "items": total_items,
        "rows_by_kind": dict(sorted(rows_by_kind.items())),
        "changed_items": changed_items,
        "flagged_items": flagged_items,
        "hash_fields_missing": hash_fields_missing,
        "status_counts": dict(sorted(status_counts.items())),
        "flag_counts": dict(sorted(flag_counts.items())),
        "ticker_entity_status_counts": dict(sorted(ticker_counts.items())),
        "all_hash_fields_present": hash_fields_missing == 0,
        "date_range": {
            "start": min((row.get("news_date") for row in files if row.get("news_date")), default=None),
            "end": max((row.get("news_date") for row in files if row.get("news_date")), default=None),
        },
        "flagged_examples": flagged_examples,
        "files": files,
    }
