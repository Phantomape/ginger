from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = REPO_ROOT / "data"

SEC_ITEM_RE = re.compile(r"\bitem\s+(\d+\.\d+)\b", re.IGNORECASE)

BUCKET_PATTERNS = {
    "guidance_raise": [
        r"\braises? (?:its )?(?:guidance|outlook|forecast)\b",
        r"\bhikes? (?:its )?(?:guidance|outlook|forecast)\b",
        r"\bboosts? (?:its )?(?:guidance|outlook|forecast)\b",
        r"\bups? (?:its )?(?:guidance|outlook|forecast)\b",
    ],
    "guidance_cut": [
        r"\bcuts? (?:its )?(?:guidance|outlook|forecast)\b",
        r"\blowers? (?:its )?(?:guidance|outlook|forecast)\b",
        r"\btrims? (?:its )?(?:guidance|outlook|forecast)\b",
        r"\bslashed? (?:its )?(?:guidance|outlook|forecast)\b",
    ],
    "earnings_beat": [
        r"\bbeats?\b",
        r"\btops? estimates\b",
        r"\bearnings beat\b",
        r"\beps beat\b",
    ],
    "earnings_miss": [
        r"\bmiss(?:es|ed)?\b",
        r"\bbelow estimates\b",
        r"\bearnings miss\b",
        r"\beps miss\b",
    ],
    "revenue_up": [
        r"\brevenue beat\b",
        r"\bbeats revenue\b",
        r"\bsales beat\b",
        r"\brevenue rises?\b",
        r"\brevenue jumps?\b",
        r"\bsales rise\b",
    ],
    "revenue_down": [
        r"\brevenue miss\b",
        r"\bmisses revenue\b",
        r"\bsales miss\b",
        r"\brevenue falls?\b",
        r"\bsales fall\b",
    ],
    "margin_up": [
        r"\bgross margin expands?\b",
        r"\bmargin expands?\b",
        r"\bmargin improvement\b",
        r"\bprofit margin rises?\b",
    ],
    "margin_down": [
        r"\bgross margin contracts?\b",
        r"\bmargin contracts?\b",
        r"\bmargin pressure\b",
        r"\bprofit margin falls?\b",
    ],
    "fcf_up": [
        r"\bfree cash flow rises?\b",
        r"\bstrong free cash flow\b",
        r"\bcash flow improves?\b",
        r"\boperating cash flow rises?\b",
    ],
    "fcf_down": [
        r"\bfree cash flow falls?\b",
        r"\bweak free cash flow\b",
        r"\bcash burn\b",
        r"\bcash flow deteriorat(?:es|ed)\b",
    ],
    "inventory_warning": [
        r"\binventory build\b",
        r"\binventory rises?\b",
        r"\binventories rise\b",
        r"\bexcess inventory\b",
        r"\binventory pressure\b",
    ],
    "receivables_warning": [
        r"\breceivables rise\b",
        r"\baccounts receivable rises?\b",
        r"\bar climbs?\b",
        r"\bworking capital pressure\b",
    ],
}

POSITIVE_BUCKETS = {
    "guidance_raise",
    "earnings_beat",
    "revenue_up",
    "margin_up",
    "fcf_up",
}
NEGATIVE_BUCKETS = {
    "guidance_cut",
    "earnings_miss",
    "revenue_down",
    "margin_down",
    "fcf_down",
    "inventory_warning",
    "receivables_warning",
}
QUALITY_POSITIVE_BUCKETS = {"revenue_up", "margin_up", "fcf_up"}
QUALITY_WARNING_BUCKETS = {
    "guidance_cut",
    "revenue_down",
    "margin_down",
    "fcf_down",
    "inventory_warning",
    "receivables_warning",
}


def _load_json(path: Path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _archive_path(prefix: str, date_key: str, data_dir: Path) -> Path:
    return data_dir / f"{prefix}_{date_key}.json"


def _dedupe_news_items(items: list[dict]) -> list[dict]:
    deduped = {}
    for item in items:
        key = (
            item.get("title"),
            item.get("url"),
            item.get("source"),
        )
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = item
            continue
        # Prefer raw SEC items because they may carry filing metadata.
        if existing.get("source") != "sec" and item.get("source") == "sec":
            deduped[key] = item
    return list(deduped.values())


def load_news_items(date_key: str, data_dir: Path | str | None = None) -> list[dict]:
    data_dir = Path(data_dir or DEFAULT_DATA_DIR)
    items: list[dict] = []
    for prefix in ("news", "clean_news"):
        payload = _load_json(_archive_path(prefix, date_key, data_dir))
        if not isinstance(payload, list):
            continue
        for raw in payload:
            if not isinstance(raw, dict):
                continue
            item = dict(raw)
            item.setdefault("source_metadata", {})
            filing_type = item.get("filing_type")
            if filing_type and "filing_type" not in item["source_metadata"]:
                item["source_metadata"]["filing_type"] = filing_type
            items.append(item)
    return _dedupe_news_items(items)


def _headline_buckets(text: str) -> list[str]:
    hits = []
    for bucket, patterns in BUCKET_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                hits.append(bucket)
                break
    return sorted(set(hits))


def classify_event_buckets(item: dict) -> list[str]:
    text = f"{item.get('title') or ''} {item.get('summary') or ''}"
    return _headline_buckets(text)


def _infer_surprise_direction(
    buckets: list[str],
    avg_surprise: float | None,
) -> str:
    positive = any(bucket in POSITIVE_BUCKETS for bucket in buckets)
    negative = any(bucket in NEGATIVE_BUCKETS for bucket in buckets)
    if positive and negative:
        return "mixed"
    if positive:
        return "positive"
    if negative:
        return "negative"
    if isinstance(avg_surprise, (int, float)):
        if avg_surprise > 0:
            return "positive"
        if avg_surprise < 0:
            return "negative"
    return "unknown"


def _infer_surprise_strength(
    buckets: list[str],
    avg_surprise: float | None,
    sec_present: bool,
) -> str:
    score = 0
    score += sum(1 for bucket in buckets if bucket in POSITIVE_BUCKETS or bucket in NEGATIVE_BUCKETS)
    if isinstance(avg_surprise, (int, float)):
        if abs(avg_surprise) >= 10:
            score += 2
        elif abs(avg_surprise) >= 5:
            score += 1
    if sec_present:
        score += 1
    if score >= 4:
        return "high"
    if score >= 2:
        return "medium"
    if score >= 1:
        return "low"
    return "unknown"


def _field_state(applicable: bool, value) -> str:
    if not applicable:
        return "not_applicable"
    if value is None:
        return "known_unknown"
    if isinstance(value, list) and not value:
        return "known_unknown"
    return "derived"


def _normalize_confidence(items: list[dict], point_in_time_complete: bool) -> str:
    if any(item.get("source") == "sec" for item in items):
        return "high" if point_in_time_complete else "medium"
    if items:
        return "medium" if point_in_time_complete else "low"
    return "low"


def _quality_flags(buckets: list[str]) -> dict:
    positive = [bucket for bucket in buckets if bucket in QUALITY_POSITIVE_BUCKETS]
    warning = [bucket for bucket in buckets if bucket in QUALITY_WARNING_BUCKETS]
    return {
        "positive": positive,
        "warning": warning,
    }


def _news_items_for_ticker(items: list[dict], ticker: str) -> list[dict]:
    out = []
    for item in items:
        tickers = [str(t).upper() for t in item.get("tickers") or []]
        if ticker in tickers:
            out.append(item)
    return out


def _build_earnings_event(
    ticker: str,
    date_key: str,
    earnings_data: dict,
    items: list[dict],
) -> dict:
    buckets = sorted({
        bucket
        for item in items
        for bucket in classify_event_buckets(item)
    })
    quality = _quality_flags(buckets)
    avg_surprise = earnings_data.get("avg_historical_surprise_pct")
    sec_items = [item for item in items if item.get("source") == "sec"]
    direction = _infer_surprise_direction(buckets, avg_surprise)
    return {
        "ticker": ticker,
        "event_date": date_key,
        "event_type": "earnings",
        "event_subtype": (
            "guidance_raise"
            if "guidance_raise" in buckets
            else "guidance_cut"
            if "guidance_cut" in buckets
            else "earnings_positive"
            if direction == "positive"
            else "earnings_negative"
            if direction == "negative"
            else "earnings_unclassified"
        ),
        "surprise_direction": direction,
        "surprise_strength": _infer_surprise_strength(buckets, avg_surprise, bool(sec_items)),
        "source_confidence": _normalize_confidence(items, True),
        "point_in_time_complete": True,
        "headline_buckets": buckets,
        "quality_flags": quality,
        "source_files": [f"earnings_snapshot_{date_key}.json"],
        "field_availability": {
            "sue_proxy": _field_state(True, avg_surprise),
            "revenue_surprise": _field_state(True, quality["positive"] or quality["warning"]),
            "gross_margin_change": _field_state(True, [bucket for bucket in buckets if "margin_" in bucket]),
            "free_cash_flow_surprise": _field_state(True, [bucket for bucket in buckets if "fcf_" in bucket]),
            "inventory_signal": _field_state(True, [bucket for bucket in buckets if "inventory_" in bucket]),
            "receivables_signal": _field_state(True, [bucket for bucket in buckets if "receivables_" in bucket]),
            "guidance_signal": _field_state(True, [bucket for bucket in buckets if "guidance_" in bucket]),
            "sec_filing_type": _field_state(False, None),
        },
        "attributes": {
            "days_to_earnings": earnings_data.get("days_to_earnings"),
            "eps_estimate": earnings_data.get("eps_estimate"),
            "eps_actual_last": earnings_data.get("eps_actual_last"),
            "avg_historical_surprise_pct": avg_surprise,
            "historical_surprise_pct": earnings_data.get("historical_surprise_pct") or [],
            "sue_proxy": round(float(avg_surprise), 2) if isinstance(avg_surprise, (int, float)) else None,
            "guidance_signal": (
                "raise"
                if "guidance_raise" in buckets
                else "cut"
                if "guidance_cut" in buckets
                else "none"
            ),
            "headline_item_count": len(items),
            "headline_titles": [item.get("title") for item in items[:5]],
            "sec_filing_present": bool(sec_items),
        },
    }


def _sec_event_subtype(item: dict) -> str:
    text = f"{item.get('title') or ''} {item.get('summary') or ''}"
    match = SEC_ITEM_RE.search(text)
    if match:
        item_id = match.group(1).replace(".", "_")
        return f"8k_item_{item_id}"
    filing_type = (
        item.get("filing_type")
        or (item.get("source_metadata") or {}).get("filing_type")
        or "sec"
    )
    return str(filing_type).lower().replace("-", "").replace("/", "_")


def _build_sec_event(
    ticker: str,
    date_key: str,
    item: dict,
) -> dict:
    filing_type = (
        item.get("filing_type")
        or (item.get("source_metadata") or {}).get("filing_type")
        or "sec"
    )
    filing_type_norm = str(filing_type).lower().replace("-", "")
    buckets = classify_event_buckets(item)
    if filing_type_norm == "8k":
        event_type = "8k"
    elif filing_type_norm == "10q":
        event_type = "10q"
    elif filing_type_norm == "10k":
        event_type = "10k"
    else:
        event_type = filing_type_norm
    return {
        "ticker": ticker,
        "event_date": date_key,
        "event_type": event_type,
        "event_subtype": _sec_event_subtype(item),
        "surprise_direction": _infer_surprise_direction(buckets, None),
        "surprise_strength": _infer_surprise_strength(buckets, None, True),
        "source_confidence": "high",
        "point_in_time_complete": True,
        "headline_buckets": buckets,
        "quality_flags": _quality_flags(buckets),
        "source_files": [f"news_{date_key}.json"],
        "field_availability": {
            "sue_proxy": _field_state(False, None),
            "revenue_surprise": _field_state(True, [bucket for bucket in buckets if "revenue_" in bucket]),
            "gross_margin_change": _field_state(True, [bucket for bucket in buckets if "margin_" in bucket]),
            "free_cash_flow_surprise": _field_state(True, [bucket for bucket in buckets if "fcf_" in bucket]),
            "inventory_signal": _field_state(True, [bucket for bucket in buckets if "inventory_" in bucket]),
            "receivables_signal": _field_state(True, [bucket for bucket in buckets if "receivables_" in bucket]),
            "guidance_signal": _field_state(True, [bucket for bucket in buckets if "guidance_" in bucket]),
            "sec_filing_type": _field_state(True, filing_type),
        },
        "attributes": {
            "filing_type": filing_type,
            "filing_recency_days": 0,
            "raw_source": item.get("raw_source"),
            "title": item.get("title"),
            "sec_cik": item.get("sec_cik") or (item.get("source_metadata") or {}).get("sec_cik"),
            "sec_company_name": item.get("sec_company_name")
            or (item.get("source_metadata") or {}).get("sec_company_name"),
            "guidance_signal": (
                "raise"
                if "guidance_raise" in buckets
                else "cut"
                if "guidance_cut" in buckets
                else "none"
            ),
        },
    }


def event_snapshot_path(date_key: str, data_dir: Path | str | None = None) -> Path:
    data_dir = Path(data_dir or DEFAULT_DATA_DIR)
    return data_dir / f"event_snapshot_{date_key}.json"


def build_event_snapshot(
    date_key: str,
    *,
    data_dir: Path | str | None = None,
    universe: list[str] | None = None,
    persist: bool = False,
) -> dict:
    data_dir = Path(data_dir or DEFAULT_DATA_DIR)
    earnings_payload = _load_json(_archive_path("earnings_snapshot", date_key, data_dir)) or {}
    earnings_by_ticker = earnings_payload.get("earnings") if isinstance(earnings_payload, dict) else {}
    earnings_by_ticker = earnings_by_ticker if isinstance(earnings_by_ticker, dict) else {}
    news_items = load_news_items(date_key, data_dir=data_dir)

    by_ticker_news = defaultdict(list)
    unmapped_sec_items = []
    sec_items_total = 0
    for item in news_items:
        tickers = [str(t).upper() for t in item.get("tickers") or []]
        if item.get("source") == "sec":
            sec_items_total += 1
        if not tickers:
            if item.get("source") == "sec":
                unmapped_sec_items.append({
                    "title": item.get("title"),
                    "filing_type": item.get("filing_type") or (item.get("source_metadata") or {}).get("filing_type"),
                    "sec_cik": item.get("sec_cik") or (item.get("source_metadata") or {}).get("sec_cik"),
                    "sec_company_name": item.get("sec_company_name")
                    or (item.get("source_metadata") or {}).get("sec_company_name"),
                })
            continue
        for ticker in tickers:
            by_ticker_news[ticker].append(item)

    if universe is None:
        universe = sorted(set(earnings_by_ticker) | set(by_ticker_news))
    else:
        universe = sorted({str(t).upper() for t in universe})

    events_by_ticker = defaultdict(list)
    coverage = Counter()
    for ticker in universe:
        matched_items = by_ticker_news.get(ticker, [])
        earnings_data = earnings_by_ticker.get(ticker) or {}
        if earnings_data.get("days_to_earnings") == 0:
            events_by_ticker[ticker].append(
                _build_earnings_event(ticker, date_key, earnings_data, matched_items)
            )
            coverage["earnings_events"] += 1
        for item in matched_items:
            if item.get("source") != "sec":
                continue
            events_by_ticker[ticker].append(_build_sec_event(ticker, date_key, item))
            coverage["sec_events"] += 1

    coverage_summary = {
        "tickers_total": len(universe),
        "earnings_snapshot_present": bool(earnings_by_ticker),
        "tickers_with_earnings_snapshot": len(earnings_by_ticker),
        "tickers_with_dte0_event": coverage["earnings_events"],
        "news_items_total": len(news_items),
        "sec_items_total": sec_items_total,
        "sec_items_mapped_to_ticker": coverage["sec_events"],
        "sec_items_unmapped": len(unmapped_sec_items),
        "event_rows_total": sum(len(events) for events in events_by_ticker.values()),
        "tickers_with_event_rows": sum(1 for events in events_by_ticker.values() if events),
        "coverage_blocked": bool(sec_items_total == 0),
    }
    payload = {
        "date": date_key,
        "coverage": coverage_summary,
        "events_by_ticker": {ticker: events for ticker, events in sorted(events_by_ticker.items())},
        "unmapped_sec_items": unmapped_sec_items[:25],
    }
    if persist:
        path = event_snapshot_path(date_key, data_dir=data_dir)
        os.makedirs(path.parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
    return payload
