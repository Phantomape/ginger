"""Replayable text-quality audit for intraday news sent to LLM prompts.

This module is intentionally read-only with respect to trading behavior. It
annotates raw news items with sanitation metadata and hashes while leaving the
original title/summary fields unchanged for downstream compatibility.
"""

from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from collections import Counter
from typing import Any, Iterable, Mapping


RULE_VERSION = "intraday_news_text_sanitation_contract_v1"
HASH_ALGORITHM = "sha256_16"
TEXT_FIELDS = ("title", "summary", "description")
SUSPECT_FLAGS = {
    "hidden_or_control_char",
    "replacement_char",
    "c1_control_char",
    "mojibake_suspect",
    "ticker_entity_metadata_only",
}

_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_MOJIBAKE_MARKERS = (
    "\ufffd",
    "\u00c2",
    "\u00c3",
    "\u00e2\u20ac",
    "\u00e2\u0080",
    "\u201a\u00c4",
)
_WHITESPACE_RE = re.compile(r"\s+")


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()[:16]


def _is_hidden_control(ch: str) -> bool:
    if ch in ("\t", "\n", "\r"):
        return False
    return unicodedata.category(ch) in {"Cc", "Cf"}


def _has_c1_control(value: str) -> bool:
    return any(0x80 <= ord(ch) <= 0x9F for ch in value)


def _mostly_latin_with_cjk(value: str) -> bool:
    latin = len(_LATIN_RE.findall(value))
    cjk = len(_CJK_RE.findall(value))
    return latin >= 5 and cjk > 0


def _looks_like_mojibake(value: str) -> bool:
    if any(marker in value for marker in _MOJIBAKE_MARKERS):
        return True
    if "\ufffd" in value or _has_c1_control(value):
        return True
    return _mostly_latin_with_cjk(value)


def sanitize_text(value: Any) -> dict[str, Any]:
    """Return a deterministic audit block for one text value."""
    original = "" if value is None else str(value)
    unescaped = html.unescape(original)
    flags: list[str] = []
    if unescaped != original:
        flags.append("html_entity_unescaped")
    if any(_is_hidden_control(ch) for ch in unescaped):
        flags.append("hidden_or_control_char")
    if "\ufffd" in unescaped:
        flags.append("replacement_char")
    if _has_c1_control(unescaped):
        flags.append("c1_control_char")
    if _looks_like_mojibake(unescaped):
        flags.append("mojibake_suspect")

    stripped = "".join(" " if _is_hidden_control(ch) else ch for ch in unescaped)
    normalized = unicodedata.normalize("NFKC", stripped)
    sanitized = _WHITESPACE_RE.sub(" ", normalized).strip()
    changed = sanitized != original
    if set(flags) & SUSPECT_FLAGS:
        status = "suspect"
    elif changed:
        status = "changed"
    else:
        status = "ok"
    return {
        "status": status,
        "flags": sorted(set(flags)),
        "changed": changed,
        "original_length": len(original),
        "sanitized_length": len(sanitized),
        "pre_sanitize_hash": _hash_text(original),
        "post_sanitize_hash": _hash_text(sanitized),
        "sanitized_text": sanitized,
    }


def _normalize_tickers(values: Iterable[Any] | None) -> list[str]:
    tickers: list[str] = []
    for raw in values or []:
        ticker = str(raw or "").upper().strip()
        if ticker and ticker not in tickers:
            tickers.append(ticker)
    return tickers


def _ticker_in_text(ticker: str, text: str) -> bool:
    if not ticker:
        return False
    pattern = rf"(?<![A-Z0-9]){re.escape(ticker)}(?![A-Z0-9])"
    return re.search(pattern, text.upper()) is not None


def _ticker_entity_match(item: Mapping[str, Any], field_text: str) -> dict[str, Any]:
    tickers = _normalize_tickers(item.get("tickers"))
    if not tickers:
        return {
            "status": "no_ticker_metadata",
            "confidence": "none",
            "tickers": [],
            "matched_tickers": [],
        }
    matched = [ticker for ticker in tickers if _ticker_in_text(ticker, field_text)]
    if matched:
        status = "explicit_text_match"
        confidence = "high"
    else:
        status = "metadata_only"
        confidence = "medium"
    return {
        "status": status,
        "confidence": confidence,
        "tickers": tickers,
        "matched_tickers": matched,
    }


def annotate_news_item(
    item: Mapping[str, Any] | Any,
    watched_tickers: Iterable[Any] | None = None,
) -> dict[str, Any]:
    """Copy a news item and attach replayable text sanitation metadata."""
    if isinstance(item, Mapping):
        annotated: dict[str, Any] = dict(item)
    else:
        annotated = {"raw_item": item}

    field_audits: dict[str, dict[str, Any]] = {}
    combined_original: list[str] = []
    combined_sanitized: list[str] = []
    flags: set[str] = set()
    changed = False
    statuses: set[str] = set()
    for field in TEXT_FIELDS:
        if field not in annotated:
            continue
        audit = sanitize_text(annotated.get(field))
        field_audits[field] = audit
        combined_original.append("" if annotated.get(field) is None else str(annotated.get(field)))
        combined_sanitized.append(audit["sanitized_text"])
        flags.update(audit["flags"])
        changed = changed or bool(audit["changed"])
        statuses.add(str(audit["status"]))

    joined_original = "\n".join(combined_original)
    joined_sanitized = "\n".join(combined_sanitized)
    ticker_match = _ticker_entity_match(annotated, joined_sanitized)
    watched = set(_normalize_tickers(watched_tickers))
    item_tickers = set(ticker_match["tickers"])
    watched_overlap = sorted(watched & item_tickers)
    if ticker_match["status"] == "metadata_only":
        flags.add("ticker_entity_metadata_only")

    if "suspect" in statuses or "ticker_entity_metadata_only" in flags:
        status = "suspect"
    elif "changed" in statuses or changed:
        status = "changed"
    else:
        status = "ok"

    annotated["text_sanitation"] = {
        "rule_version": RULE_VERSION,
        "status": status,
        "flags": sorted(flags),
        "changed": changed,
        "field_count": len(field_audits),
        "fields": field_audits,
        "pre_sanitize_hash": _hash_text(joined_original),
        "post_sanitize_hash": _hash_text(joined_sanitized),
        "ticker_entity_match": ticker_match,
        "watched_ticker_overlap": watched_overlap,
    }
    return annotated


def annotate_news_items(
    items: Iterable[Mapping[str, Any] | Any] | None,
    watched_tickers: Iterable[Any] | None = None,
) -> list[dict[str, Any]]:
    return [annotate_news_item(item, watched_tickers) for item in (items or [])]


def build_news_sanitation_summary(
    items: Iterable[Mapping[str, Any] | Any] | None,
) -> dict[str, Any]:
    annotated = [
        item if isinstance(item, Mapping) and isinstance(item.get("text_sanitation"), dict)
        else annotate_news_item(item)
        for item in (items or [])
    ]
    status_counts: Counter[str] = Counter()
    flag_counts: Counter[str] = Counter()
    ticker_status_counts: Counter[str] = Counter()
    changed_items = 0
    flagged_items = 0
    for item in annotated:
        audit = item.get("text_sanitation") or {}
        status_counts[str(audit.get("status") or "unknown")] += 1
        flags = [str(flag) for flag in audit.get("flags") or []]
        if flags:
            flagged_items += 1
        flag_counts.update(flags)
        if audit.get("changed"):
            changed_items += 1
        ticker = audit.get("ticker_entity_match") or {}
        ticker_status_counts[str(ticker.get("status") or "unknown")] += 1
    return {
        "rule_version": RULE_VERSION,
        "hash_algorithm": HASH_ALGORITHM,
        "items": len(annotated),
        "flagged_items": flagged_items,
        "changed_items": changed_items,
        "status_counts": dict(sorted(status_counts.items())),
        "flag_counts": dict(sorted(flag_counts.items())),
        "ticker_entity_status_counts": dict(sorted(ticker_status_counts.items())),
        "all_clear": flagged_items == 0,
    }
