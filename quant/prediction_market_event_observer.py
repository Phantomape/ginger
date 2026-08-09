"""Observer-only prediction-market event collection.

This module collects public event/market probability rows for non-ticker event
themes. It intentionally stays out of prompts, ranking, sizing, exits, and
orders; rows are written only as a separate non-OHLCV observer surface.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from data_paths import DATA_ROOT, atomic_write_json

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1
OBSERVER_NAME = "prediction_market_event_observer"
ARTIFACT_ROOT = Path("non_ohlcv") / OBSERVER_NAME
POLYMARKET_EVENTS_ENDPOINT = "https://gamma-api.polymarket.com/events"
# exp-20260718-002: the /events endpoint silently ignores its `search` param,
# so every query received the same generic first page and relevance rejected
# nearly everything. /public-search?q= is the endpoint that actually filters.
POLYMARKET_PUBLIC_SEARCH_ENDPOINT = "https://gamma-api.polymarket.com/public-search"
OUTCOME_RULE_VERSION = "prediction_market_event_forward_outcome_ledger_v1"


PREDICTION_MARKET_SOURCE_SPECS: list[dict[str, Any]] = [
    {
        "query_id": "spacex_ipo_probability",
        "query": "SpaceX IPO public stock listing Starlink",
        "primary_entity": "SpaceX",
        "theme": "private_space_ipo",
        "relation_type": "private_entity_to_public_space_exposure",
        "candidate_tickers": ["RKLB", "LUNR", "ASTS", "BA", "LMT", "NOC"],
        "match_terms": ["spacex", "starlink", "ipo", "public"],
        "relevance_groups": [
            ["spacex", "starlink"],
            ["ipo", "listing", "public", "public listing", "go public", "stock"],
        ],
        "min_relevance_groups": 2,
        "rationale": (
            "Prediction-market probability changes around a SpaceX or Starlink "
            "listing can timestamp public space-exposure repricing before ticker "
            "news feeds classify it."
        ),
    },
    {
        "query_id": "frontier_ai_private_capex_probability",
        "query": "OpenAI Anthropic data center AI chips investment",
        "primary_entity": "frontier_ai_labs",
        "theme": "ai_capex_private_lab",
        "relation_type": "private_ai_lab_to_public_ai_infrastructure",
        "candidate_tickers": ["NVDA", "AMD", "AVGO", "MU", "CRDO", "ANET", "SMCI"],
        "match_terms": ["openai", "anthropic", "data center", "ai chip", "investment"],
        "relevance_groups": [
            ["openai", "anthropic", "frontier ai"],
            ["data center", "ai chip", "gpu", "investment", "capex", "compute"],
        ],
        "exclude_terms": [
            "consumer hardware",
            "consumer product",
            "browser",
            "phone",
        ],
        "min_relevance_groups": 2,
        "rationale": (
            "Market-implied odds for frontier AI lab capex or supply events can "
            "create a timestamped lead surface for public AI infrastructure."
        ),
    },
    {
        "query_id": "ai_export_controls_probability",
        "query": "AI chips export controls China Nvidia AMD",
        "primary_entity": "US_export_control_policy",
        "theme": "ai_chip_export_controls",
        "relation_type": "regulatory_policy_to_public_semiconductor_exposure",
        "candidate_tickers": ["NVDA", "AMD", "AVGO", "TSM", "ASML", "MU"],
        "match_terms": ["ai chip", "export", "china", "nvidia", "amd"],
        "relevance_groups": [
            ["ai chip", "chip", "semiconductor", "gpu", "nvidia", "amd"],
            ["export", "export control", "china", "taiwan", "restriction", "ban"],
        ],
        "exclude_terms": [
            "military clash",
            "armed conflict",
            "ceasefire",
            "war",
            "india",
            "xi jinping",
            "president",
            "election",
        ],
        "min_relevance_groups": 2,
        "rationale": (
            "Prediction markets can timestamp policy odds before direct company "
            "or semiconductor-ticker news becomes explicit."
        ),
    },
    {
        "query_id": "hyperscaler_power_shortage_probability",
        "query": "AI data center power grid hyperscaler electricity shortage",
        "primary_entity": "hyperscaler_power_demand",
        "theme": "ai_data_center_power",
        "relation_type": "theme_to_public_power_and_infrastructure_exposure",
        "candidate_tickers": ["CEG", "VST", "ETN", "PWR", "GEV", "NVDA", "ANET"],
        "match_terms": ["data center", "power", "grid", "electricity", "hyperscaler"],
        "relevance_groups": [
            ["data center", "hyperscaler", "ai"],
            ["power", "grid", "electricity", "energy", "shortage"],
        ],
        "exclude_terms": [
            "consumer hardware",
            "consumer product",
            "gta",
            "russia",
            "ukraine",
            "ceasefire",
            "war",
            "xi jinping",
            "president",
            "election",
        ],
        "min_relevance_groups": 2,
        "rationale": (
            "Power and grid event probabilities can precede public repricing in "
            "utilities, electrical equipment, and AI infrastructure suppliers."
        ),
    },
    {
        "query_id": "crypto_market_structure_probability",
        "query": "stablecoin crypto market structure bill SEC CFTC",
        "primary_entity": "crypto_market_structure_policy",
        "theme": "crypto_regulation",
        "relation_type": "regulatory_policy_to_public_crypto_exposure",
        "candidate_tickers": ["COIN", "MSTR", "HOOD", "IBIT", "MARA", "RIOT"],
        "match_terms": ["stablecoin", "crypto", "market structure", "sec", "cftc"],
        "relevance_groups": [
            ["stablecoin", "crypto", "bitcoin", "ethereum", "sec", "cftc"],
            ["market structure", "bill", "regulation", "policy", "law", "tax"],
        ],
        "min_relevance_groups": 2,
        "rationale": (
            "Sector policy probabilities can move public crypto exposure before "
            "ticker-specific news feeds identify winners and losers."
        ),
    },
    {
        "query_id": "glp1_market_access_probability",
        "query": "GLP-1 obesity drug Medicare FDA shortage compounding",
        "primary_entity": "GLP1_market_access",
        "theme": "glp1_supply_access",
        "relation_type": "healthcare_theme_to_public_obesity_drug_exposure",
        "candidate_tickers": ["LLY", "NVO", "HIMS", "WW"],
        "match_terms": ["glp-1", "obesity", "medicare", "fda", "compounding"],
        "relevance_groups": [
            [
                "glp-1",
                "glp1",
                "obesity",
                "weight loss",
                "ozempic",
                "wegovy",
                "mounjaro",
                "zepbound",
            ],
            ["medicare", "fda", "shortage", "compounding", "supply", "access", "price"],
        ],
        "min_relevance_groups": 2,
        "rationale": (
            "Prediction-market odds around supply, policy, and access events can "
            "timestamp risks for obesity-drug and adjacent consumer-health names."
        ),
    },
]


def _date_tag(today: str | datetime | None) -> str:
    if today is None:
        return datetime.now().strftime("%Y%m%d")
    if isinstance(today, datetime):
        return today.strftime("%Y%m%d")
    text = str(today)
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y%m%d")
        except ValueError:
            continue
    return text


def _artifact_paths(date_tag: str, data_dir: str | Path | None = None) -> dict[str, Path]:
    root = Path(data_dir) if data_dir is not None else DATA_ROOT
    base = root / ARTIFACT_ROOT
    return {
        "items": base / "daily" / f"{OBSERVER_NAME}_{date_tag}.json",
        "source_stats": base
        / "source_stats"
        / f"{OBSERVER_NAME}_source_stats_{date_tag}.json",
        "source_manifest": base / "source_manifest.json",
        "latest_summary": base / "latest_summary.json",
        "outcome_ledger": base
        / "outcome_ledgers"
        / f"{OBSERVER_NAME}_outcomes_{date_tag}.jsonl",
        "outcome_summary": base
        / "outcome_summaries"
        / f"{OBSERVER_NAME}_outcome_summary_{date_tag}.json",
        "latest_outcome_summary": base / "latest_outcome_summary.json",
    }


def _remove_write_temps(path: Path) -> None:
    for leftover in path.parent.glob(f".{path.name}.*.tmp"):
        try:
            leftover.unlink()
        except OSError:
            pass


def _write_json(payload: Any, path: Path) -> None:
    try:
        atomic_write_json(payload, path, default=str)
        _remove_write_temps(path)
        return
    except PermissionError:
        log.warning("Atomic write failed for %s; falling back to direct write", path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    _remove_write_temps(path)


def get_prediction_market_observer_sources() -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for spec in PREDICTION_MARKET_SOURCE_SPECS:
        metadata = {
            "observer_only": True,
            "observer_name": OBSERVER_NAME,
            "schema_version": SCHEMA_VERSION,
            "provider": "polymarket",
            "query_id": spec["query_id"],
            "query": spec["query"],
            "primary_entity": spec["primary_entity"],
            "theme": spec["theme"],
            "relation_type": spec["relation_type"],
            "candidate_tickers": list(spec["candidate_tickers"]),
            "match_terms": list(spec["match_terms"]),
            "relevance_groups": [list(group) for group in spec["relevance_groups"]],
            "exclude_terms": list(spec.get("exclude_terms") or []),
            "min_relevance_groups": int(spec["min_relevance_groups"]),
            "rationale": spec["rationale"],
        }
        sources.append(
            {
                "url": POLYMARKET_PUBLIC_SEARCH_ENDPOINT,
                "params": {
                    "q": spec["query"],
                    "events_status": "active",
                    "limit_per_type": 100,
                },
                "source_type": "polymarket_prediction_market_event",
                "metadata": metadata,
            }
        )
    return sources


def _default_fetch_json(
    url: str,
    params: dict[str, Any] | None = None,
    *,
    timeout_seconds: float = 10.0,
) -> Any:
    query = urlencode(params or {}, doseq=True)
    full_url = f"{url}?{query}" if query else url
    request = Request(
        full_url,
        headers={
            "Accept": "application/json",
            "User-Agent": "ginger-prediction-market-observer/1.0",
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _jsonish(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return stripped
    return value


def _coerce_float(value: Any) -> float | None:
    parsed = _jsonish(value)
    if isinstance(parsed, bool) or parsed is None:
        return None
    if isinstance(parsed, (int, float)):
        number = float(parsed)
    elif isinstance(parsed, str):
        text = parsed.strip().replace("%", "")
        if not text:
            return None
        try:
            number = float(text)
        except ValueError:
            return None
    else:
        return None
    if 1.0 < number <= 100.0:
        number /= 100.0
    if 0.0 <= number <= 1.0:
        return round(number, 6)
    return None


def _coerce_number(value: Any) -> float | None:
    parsed = _jsonish(value)
    if isinstance(parsed, bool) or parsed is None:
        return None
    if isinstance(parsed, (int, float)):
        return float(parsed)
    if isinstance(parsed, str):
        text = parsed.strip().replace(",", "").replace("%", "")
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _coerce_sequence(value: Any) -> list[Any]:
    parsed = _jsonish(value)
    if parsed is None:
        return []
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, tuple):
        return list(parsed)
    if isinstance(parsed, str) and "," in parsed:
        return [part.strip() for part in parsed.split(",")]
    return [parsed]


def _yes_outcome_index(outcomes: Any) -> int:
    for index, outcome in enumerate(_coerce_sequence(outcomes)):
        if str(outcome).strip().lower() == "yes":
            return index
    return 0


def _probability_from_prices(prices: Any, outcomes: Any = None) -> float | None:
    values = _coerce_sequence(prices)
    if not values:
        return None
    index = _yes_outcome_index(outcomes)
    if index >= len(values):
        index = 0
    return _coerce_float(values[index])


def extract_yes_probability(record: dict[str, Any]) -> float | None:
    outcomes = record.get("outcomes") or record.get("outcomeNames")
    for key in ("outcomePrices", "outcome_prices", "prices"):
        probability = _probability_from_prices(record.get(key), outcomes)
        if probability is not None:
            return probability

    bid = _coerce_float(record.get("bestBid") or record.get("best_bid"))
    ask = _coerce_float(record.get("bestAsk") or record.get("best_ask"))
    if bid is not None and ask is not None:
        return round((bid + ask) / 2.0, 6)

    for key in (
        "yes_probability",
        "probability",
        "lastTradePrice",
        "last_trade_price",
        "lastPrice",
        "price",
        "midpoint",
    ):
        probability = _coerce_float(record.get(key))
        if probability is not None:
            return probability

    for token in _coerce_sequence(record.get("tokens")):
        if not isinstance(token, dict):
            continue
        outcome = str(token.get("outcome") or token.get("name") or "").lower()
        if outcome == "yes":
            for key in ("price", "lastTradePrice", "bestBid", "bestAsk"):
                probability = _coerce_float(token.get(key))
                if probability is not None:
                    return probability
    return None


def _payload_records(payload: Any) -> list[dict[str, Any]]:
    parsed = _jsonish(payload)
    if isinstance(parsed, list):
        return [row for row in parsed if isinstance(row, dict)]
    if not isinstance(parsed, dict):
        return []
    records: list[dict[str, Any]] = []
    for key in ("events", "markets", "data", "results"):
        value = parsed.get(key)
        if isinstance(value, list):
            records.extend(row for row in value if isinstance(row, dict))
        elif isinstance(value, dict):
            records.extend(_payload_records(value))
    if not records and any(key in parsed for key in ("title", "question", "slug", "id")):
        records.append(parsed)
    return records


def _text_blob(*records: dict[str, Any] | None) -> str:
    fields = ("title", "question", "name", "slug", "description", "subtitle")
    pieces: list[str] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        for field in fields:
            value = record.get(field)
            if value is not None:
                pieces.append(str(value))
    return " ".join(pieces).lower()


_TERM_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _term_pattern(term: str) -> re.Pattern[str] | None:
    tokens = _TERM_TOKEN_RE.findall(term.lower())
    if not tokens:
        return None
    body = r"[\W_]+".join(re.escape(token) for token in tokens)
    return re.compile(rf"(?<![a-z0-9]){body}(?![a-z0-9])")


def _term_hits(terms: list[Any], blob: str) -> list[str]:
    hits: list[str] = []
    for term in terms:
        text = str(term).strip().lower()
        pattern = _term_pattern(text)
        if pattern is not None and pattern.search(blob):
            hits.append(text)
    return hits


def prediction_market_source_relevance(
    record: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    blob = _text_blob(record)
    excluded_hits = _term_hits(list(metadata.get("exclude_terms") or []), blob)
    if excluded_hits:
        return {
            "matched": False,
            "matched_group_count": 0,
            "required_group_count": int(metadata.get("min_relevance_groups") or 0),
            "group_hits": [],
            "hit_terms": [],
            "excluded_terms": excluded_hits,
            "method": "relevance_exclusions",
        }

    groups = metadata.get("relevance_groups") or []
    if groups:
        group_hits: list[dict[str, Any]] = []
        for index, group in enumerate(groups):
            hits = _term_hits(list(group), blob)
            if hits:
                group_hits.append({"group_index": index, "hit_terms": hits})
        required = int(metadata.get("min_relevance_groups") or len(groups))
        return {
            "matched": len(group_hits) >= required,
            "matched_group_count": len(group_hits),
            "required_group_count": required,
            "group_hits": group_hits,
            "hit_terms": sorted({term for group in group_hits for term in group["hit_terms"]}),
            "excluded_terms": [],
            "method": "relevance_groups",
        }

    terms = [str(term).lower() for term in metadata.get("match_terms") or []]
    hits = _term_hits(terms, blob)
    required = int(metadata.get("min_match_terms") or (1 if terms else 0))
    return {
        "matched": len(hits) >= required,
        "matched_group_count": len(hits),
        "required_group_count": required,
        "group_hits": [{"group_index": index, "hit_terms": [term]} for index, term in enumerate(hits)],
        "hit_terms": hits,
        "excluded_terms": [],
        "method": "match_terms",
    }


def _market_relevance(
    event: dict[str, Any],
    market: dict[str, Any] | None,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    pieces: list[str] = []
    for row in (event, market or {}):
        if not isinstance(row, dict):
            continue
        for field in ("title", "question", "name", "slug", "description", "subtitle"):
            value = row.get(field)
            if value is not None:
                pieces.append(str(value))
    return prediction_market_source_relevance({"title": " ".join(pieces)}, metadata)


def _matches_source(record: dict[str, Any], metadata: dict[str, Any]) -> bool:
    return bool(prediction_market_source_relevance(record, metadata)["matched"])


def _record_markets(record: dict[str, Any]) -> list[dict[str, Any] | None]:
    markets = record.get("markets")
    if isinstance(markets, list):
        market_rows = [market for market in markets if isinstance(market, dict)]
        return market_rows or [None]
    return [None]


def _record_id(record: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return str(value)
    return None


def _provider_url(event: dict[str, Any], market: dict[str, Any] | None) -> str | None:
    for row in (market, event):
        if not isinstance(row, dict):
            continue
        for key in ("url", "link"):
            value = row.get(key)
            if value:
                return str(value)
    slug = _record_id(event, "slug")
    if slug:
        return f"https://polymarket.com/event/{slug}"
    return None


def _market_item(
    event: dict[str, Any],
    market: dict[str, Any] | None,
    metadata: dict[str, Any],
    observed_at: str,
    relevance: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    relevance = relevance or _market_relevance(event, market, metadata)
    if not relevance.get("matched"):
        return None
    market_row = market or {}
    probability = extract_yes_probability(market_row)
    if probability is None:
        probability = extract_yes_probability(event)
    title = (
        _record_id(event, "title", "question", "name")
        or _record_id(market_row, "title", "question", "name")
        or _record_id(event, "slug")
    )
    question = _record_id(market_row, "question", "title", "name") or title
    return {
        "observer_only": True,
        "observer_name": OBSERVER_NAME,
        "observer_schema_version": SCHEMA_VERSION,
        "provider": metadata.get("provider", "polymarket"),
        "source_type": "polymarket_prediction_market_event",
        "prediction_market_query_id": metadata.get("query_id"),
        "prediction_market_query": metadata.get("query"),
        "primary_entity": metadata.get("primary_entity"),
        "theme": metadata.get("theme"),
        "relation_type": metadata.get("relation_type"),
        "candidate_tickers": list(metadata.get("candidate_tickers") or []),
        "provider_event_id": _record_id(event, "id", "eventId", "event_id"),
        "provider_market_id": _record_id(market_row, "id", "marketId", "conditionId"),
        "provider_slug": _record_id(event, "slug"),
        "title": title,
        "question": question,
        "yes_probability": probability,
        "volume": _coerce_number(market_row.get("volume") or event.get("volume")),
        "liquidity": _coerce_number(
            market_row.get("liquidity") or event.get("liquidity")
        ),
        "active": market_row.get("active", event.get("active")),
        "closed": market_row.get("closed", event.get("closed")),
        "end_date": _record_id(market_row, "endDate", "end_date")
        or _record_id(event, "endDate", "end_date"),
        "updated_at": _record_id(market_row, "updatedAt", "updated_at")
        or _record_id(event, "updatedAt", "updated_at"),
        "observed_at": observed_at,
        "url": _provider_url(event, market),
        "relevance_method": relevance.get("method"),
        "relevance_group_hits": relevance.get("group_hits") or [],
        "relevance_hit_terms": relevance.get("hit_terms") or [],
        "relevance_matched_group_count": relevance.get("matched_group_count"),
        "relevance_required_group_count": relevance.get("required_group_count"),
    }


def _dedupe_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    unique: list[dict[str, Any]] = []
    for item in items:
        key = (
            item.get("prediction_market_query_id"),
            item.get("provider"),
            item.get("provider_event_id") or item.get("provider_slug"),
            item.get("provider_market_id"),
            item.get("title"),
            item.get("question"),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return sorted(
        unique,
        key=lambda item: (
            str(item.get("prediction_market_query_id") or ""),
            str(item.get("provider_event_id") or ""),
            str(item.get("provider_market_id") or ""),
            str(item.get("title") or ""),
        ),
    )


def persist_prediction_market_event_observer(
    today: str | datetime | None = None,
    *,
    data_dir: str | Path | None = None,
    fetch_func=None,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    """Fetch configured prediction-market sources and persist observer artifacts."""
    fetch_func = fetch_func or _default_fetch_json
    date_tag = _date_tag(today)
    observed_at = datetime.now(timezone.utc).isoformat()
    sources = get_prediction_market_observer_sources()
    raw_items: list[dict[str, Any]] = []
    source_stats: list[dict[str, Any]] = []

    for source in sources:
        metadata = dict(source.get("metadata") or {})
        params = dict(source.get("params") or {})
        try:
            payload = fetch_func(
                source["url"],
                params,
                timeout_seconds=timeout_seconds,
            )
            records = _payload_records(payload)
            parsed_items: list[dict[str, Any]] = []
            market_candidate_count = 0
            relevance_rejected_count = 0
            for record in records:
                for market in _record_markets(record):
                    market_candidate_count += 1
                    relevance = _market_relevance(record, market, metadata)
                    if not relevance.get("matched"):
                        relevance_rejected_count += 1
                        continue
                    item = _market_item(record, market, metadata, observed_at, relevance)
                    if item is not None:
                        parsed_items.append(item)
            raw_items.extend(parsed_items)
            source_stats.append(
                {
                    "url": source["url"],
                    "params": params,
                    "source_type": source["source_type"],
                    "metadata": metadata,
                    "status": "ok",
                    "entry_count": len(records),
                    "market_candidate_count": market_candidate_count,
                    "relevance_rejected_count": relevance_rejected_count,
                    "parsed_item_count": len(parsed_items),
                    "error": None,
                }
            )
        except Exception as exc:
            log.warning("Prediction-market source failed: %s", exc)
            source_stats.append(
                {
                    "url": source["url"],
                    "params": params,
                    "source_type": source["source_type"],
                    "metadata": metadata,
                    "status": "error",
                    "entry_count": 0,
                    "market_candidate_count": 0,
                    "relevance_rejected_count": 0,
                    "parsed_item_count": 0,
                    "error": str(exc),
                }
            )

    unique_items = _dedupe_items(raw_items)
    source_manifest = {
        "schema_version": SCHEMA_VERSION,
        "observer_name": OBSERVER_NAME,
        "observer_only": True,
        "strategy_behavior_changed": False,
        "trade_enabled": False,
        "provider": "polymarket",
        "sources": sources,
    }
    paths = _artifact_paths(date_tag, data_dir)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "observer_name": OBSERVER_NAME,
        "status": "ok",
        "date": date_tag,
        "source_count": len(sources),
        "source_error_count": sum(1 for stat in source_stats if stat.get("error")),
        "market_candidate_count": sum(
            int(stat.get("market_candidate_count") or 0) for stat in source_stats
        ),
        "relevance_rejected_count": sum(
            int(stat.get("relevance_rejected_count") or 0) for stat in source_stats
        ),
        "raw_item_count": len(raw_items),
        "unique_item_count": len(unique_items),
        "observer_only": True,
        "strategy_behavior_changed": False,
        "trade_enabled": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "items_path": str(paths["items"]),
        "source_stats_path": str(paths["source_stats"]),
        "source_manifest_path": str(paths["source_manifest"]),
        "latest_summary_path": str(paths["latest_summary"]),
    }

    _write_json(unique_items, paths["items"])
    _write_json(source_stats, paths["source_stats"])
    _write_json(source_manifest, paths["source_manifest"])
    _write_json(summary, paths["latest_summary"])
    return summary


def _date10(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value)
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return text[:10]
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:10], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _bar_date(row: dict[str, Any]) -> str | None:
    for key in ("Date", "date", "timestamp"):
        parsed = _date10(row.get(key))
        if parsed:
            return parsed
    return None


def _bar_float(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = row.get(key)
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _normalise_bars(
    ohlcv_by_ticker: dict[str, Any],
    *,
    as_of_date: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    cutoff = _date10(as_of_date)
    normalised: dict[str, list[dict[str, Any]]] = {}
    for ticker, payload in (ohlcv_by_ticker or {}).items():
        rows: list[Any]
        if isinstance(payload, dict):
            rows = list(payload.values())
        elif isinstance(payload, list):
            rows = payload
        else:
            rows = []
        clean_rows = []
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            day = _bar_date(raw)
            if not day or (cutoff and day > cutoff):
                continue
            clean_rows.append({**raw, "_date": day})
        clean_rows.sort(key=lambda row: row["_date"])
        normalised[str(ticker).upper()] = clean_rows
    return normalised


def _entry_index(rows: list[dict[str, Any]], observed_date: str) -> int | None:
    for index, row in enumerate(rows):
        if row["_date"] > observed_date:
            return index
    return None


def _bar_by_date(rows: list[dict[str, Any]], target_date: str) -> dict[str, Any] | None:
    for row in rows:
        if row.get("_date") == target_date:
            return row
    return None


def _next_market_date(
    bars_by_ticker: dict[str, list[dict[str, Any]]],
    observed_date: str,
) -> str | None:
    dates: list[str] = []
    benchmark_rows = [
        row
        for ticker in ("SPY", "QQQ")
        for row in bars_by_ticker.get(ticker, [])
    ]
    rows = benchmark_rows or [
        row for ticker_rows in bars_by_ticker.values() for row in ticker_rows
    ]
    for row in rows:
        day = row.get("_date")
        if isinstance(day, str) and day > observed_date:
            dates.append(day)
    return min(dates) if dates else None


def _missing_entry_status(
    ticker_bars: list[dict[str, Any]],
    bars_by_ticker: dict[str, list[dict[str, Any]]],
    observed_date: str,
) -> tuple[str, str]:
    if not ticker_bars:
        return "unsettled_no_entry_bar", "ticker_has_no_price_rows"
    if _next_market_date(bars_by_ticker, observed_date) is None:
        return (
            "future_entry_session_not_reached",
            "market_calendar_has_no_session_after_observed_date",
        )
    return (
        "unsettled_no_entry_bar",
        "market_calendar_has_next_session_but_ticker_missing_bar",
    )


def _pnl_for_bars(entry_bar: dict[str, Any], exit_bar: dict[str, Any], notional: float) -> float | None:
    entry_open = _bar_float(entry_bar, "Open", "open")
    exit_close = _bar_float(exit_bar, "Close", "close")
    if not entry_open or not exit_close:
        return None
    return round(notional * (exit_close / entry_open - 1.0), 2)


def build_prediction_market_event_outcome_ledger(
    items: list[dict[str, Any]],
    ohlcv_by_ticker: dict[str, Any],
    *,
    as_of_date: str | None = None,
    horizons: tuple[int, ...] = (10,),
    notional_usd: float = 4000.0,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build observer-only forward outcome rows for prediction-market items.

    The observer emits event/theme rows with candidate public tickers. This
    helper settles each candidate against the next available trading-session
    open and the Nth trading-session close, while preserving immature rows as
    explicit unsettled records.
    """
    bars = _normalise_bars(ohlcv_by_ticker, as_of_date=as_of_date)
    rows: list[dict[str, Any]] = []
    horizon_values = tuple(sorted({int(horizon) for horizon in horizons if int(horizon) > 0}))
    for item_index, item in enumerate(items or []):
        if not isinstance(item, dict):
            continue
        observed_date = (
            _date10(item.get("observed_at"))
            or _date10(item.get("published_at"))
            or _date10(item.get("date"))
            or _date10(as_of_date)
        )
        if not observed_date:
            continue
        candidate_tickers = [
            str(ticker).upper()
            for ticker in (item.get("candidate_tickers") or [])
            if str(ticker).strip()
        ]
        for ticker in candidate_tickers:
            ticker_bars = bars.get(ticker, [])
            entry_idx = _entry_index(ticker_bars, observed_date)
            for horizon in horizon_values:
                base = {
                    "observer_only": True,
                    "observer_name": OBSERVER_NAME,
                    "outcome_rule_version": OUTCOME_RULE_VERSION,
                    "prediction_market_query_id": item.get("prediction_market_query_id"),
                    "provider": item.get("provider"),
                    "provider_event_id": item.get("provider_event_id"),
                    "provider_market_id": item.get("provider_market_id"),
                    "provider_slug": item.get("provider_slug"),
                    "title": item.get("title"),
                    "question": item.get("question"),
                    "theme": item.get("theme"),
                    "relation_type": item.get("relation_type"),
                    "yes_probability": item.get("yes_probability"),
                    "observed_date": observed_date,
                    "candidate_ticker": ticker,
                    "candidate_item_index": item_index,
                    "horizon_trading_days": horizon,
                    "notional_usd": notional_usd,
                    "trade_enabled": False,
                }
                if entry_idx is None:
                    status, detail = _missing_entry_status(
                        ticker_bars,
                        bars,
                        observed_date,
                    )
                    rows.append(
                        {
                            **base,
                            "outcome_status": status,
                            "outcome_status_detail": detail,
                        }
                    )
                    continue
                exit_idx = entry_idx + horizon - 1
                entry_bar = ticker_bars[entry_idx]
                base["entry_date"] = entry_bar["_date"]
                base["entry_open"] = _bar_float(entry_bar, "Open", "open")
                if exit_idx >= len(ticker_bars):
                    rows.append({**base, "outcome_status": "unsettled_horizon"})
                    continue
                exit_bar = ticker_bars[exit_idx]
                pnl = _pnl_for_bars(entry_bar, exit_bar, notional_usd)
                base.update(
                    {
                        "exit_date": exit_bar["_date"],
                        "exit_close": _bar_float(exit_bar, "Close", "close"),
                        "pnl_usd": pnl,
                        "replacement_value_vs_cash_usd": pnl,
                    }
                )
                comparator_detail: dict[str, Any] = {}
                missing_comparator = False
                for comparator in ("SPY", "QQQ"):
                    comp_rows = bars.get(comparator, [])
                    comp_entry = _bar_by_date(comp_rows, entry_bar["_date"])
                    comp_exit = _bar_by_date(comp_rows, exit_bar["_date"])
                    comp_pnl = (
                        _pnl_for_bars(comp_entry, comp_exit, notional_usd)
                        if comp_entry and comp_exit
                        else None
                    )
                    if comp_pnl is None or pnl is None:
                        missing_comparator = True
                    field = f"replacement_value_vs_{comparator.lower()}_usd"
                    base[field] = round(pnl - comp_pnl, 2) if pnl is not None and comp_pnl is not None else None
                    comparator_detail[comparator] = {
                        "entry_date": entry_bar["_date"] if comp_entry else None,
                        "exit_date": exit_bar["_date"] if comp_exit else None,
                        "pnl_usd": comp_pnl,
                    }
                base["comparator_detail"] = comparator_detail
                base["outcome_status"] = (
                    "missing_comparator_bars" if missing_comparator else "settled"
                )
                rows.append(base)

    status_counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("outcome_status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    summary = {
        "observer_only": True,
        "observer_name": OBSERVER_NAME,
        "outcome_rule_version": OUTCOME_RULE_VERSION,
        "source_item_count": len(items or []),
        "candidate_outcome_row_count": len(rows),
        "settled_count": status_counts.get("settled", 0),
        "unsettled_count": sum(
            count for status, count in status_counts.items() if status != "settled"
        ),
        "status_counts": dict(sorted(status_counts.items())),
        "horizons": list(horizon_values),
        "notional_usd": notional_usd,
        "as_of_date": _date10(as_of_date),
        "strategy_behavior_changed": False,
        "trade_enabled": False,
    }
    return rows, summary


def _daily_item_file_date(path: Path) -> str | None:
    stem = path.stem
    prefix = f"{OBSERVER_NAME}_"
    if not stem.startswith(prefix):
        return None
    return _date10(stem[len(prefix) :])


def _daily_item_paths_through(
    date_tag: str,
    *,
    data_dir: str | Path | None = None,
) -> list[Path]:
    root = Path(data_dir) if data_dir is not None else DATA_ROOT
    daily_dir = root / ARTIFACT_ROOT / "daily"
    cutoff = _date10(date_tag)
    if not daily_dir.exists():
        return []
    paths = []
    for path in daily_dir.glob(f"{OBSERVER_NAME}_*.json"):
        file_date = _daily_item_file_date(path)
        if not file_date:
            continue
        if cutoff and file_date > cutoff:
            continue
        paths.append(path)
    return sorted(paths, key=lambda path: (_daily_item_file_date(path) or "", path.name))


def _load_daily_items_through(
    date_tag: str,
    *,
    data_dir: str | Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    items: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    for path in _daily_item_paths_through(date_tag, data_dir=data_dir):
        file_date = _daily_item_file_date(path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            files.append(
                {
                    "path": str(path),
                    "date": file_date,
                    "status": "error",
                    "item_count": 0,
                    "error": str(exc),
                }
            )
            continue
        if isinstance(payload, list):
            rows = [row for row in payload if isinstance(row, dict)]
        elif isinstance(payload, dict):
            raw_rows = payload.get("items") or payload.get("rows") or []
            rows = [row for row in raw_rows if isinstance(row, dict)]
        else:
            rows = []
        for row in rows:
            item = dict(row)
            item.setdefault("observer_item_file_date", file_date)
            item.setdefault("date", file_date)
            items.append(item)
        files.append(
            {
                "path": str(path),
                "date": file_date,
                "status": "ok",
                "item_count": len(rows),
                "error": None,
            }
        )
    return items, files


def _candidate_tickers_for_outcomes(items: list[dict[str, Any]]) -> list[str]:
    tickers = {
        str(ticker).upper()
        for item in items
        for ticker in (item.get("candidate_tickers") or [])
        if str(ticker).strip()
    }
    tickers.update({"SPY", "QQQ"})
    return sorted(tickers)


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _table_columns(con: sqlite3.Connection, table: str) -> dict[str, str]:
    return {
        str(row[1]).lower(): str(row[1])
        for row in con.execute(f"pragma table_info({_quote_identifier(table)})")
    }


def _load_warehouse_bars_from_table(
    con: sqlite3.Connection,
    *,
    table: str,
    tickers: list[str],
) -> list[dict[str, Any]]:
    columns = _table_columns(con, table)

    def column(*names: str) -> str | None:
        for name in names:
            if name.lower() in columns:
                return columns[name.lower()]
        return None

    ticker_col = column("ticker", "symbol")
    date_col = column("date", "Date", "timestamp")
    open_col = column("open", "Open")
    high_col = column("high", "High")
    low_col = column("low", "Low")
    close_col = column("close", "Close")
    volume_col = column("volume", "Volume")
    required = [ticker_col, date_col, open_col, high_col, low_col, close_col]
    if any(value is None for value in required):
        return []
    placeholders = ",".join("?" for _ in tickers)
    select_volume = _quote_identifier(volume_col) if volume_col else "null"
    query = f"""
        select
            {_quote_identifier(ticker_col)} as ticker,
            {_quote_identifier(date_col)} as date,
            {_quote_identifier(open_col)} as open,
            {_quote_identifier(high_col)} as high,
            {_quote_identifier(low_col)} as low,
            {_quote_identifier(close_col)} as close,
            {select_volume} as volume
        from {_quote_identifier(table)}
        where upper({_quote_identifier(ticker_col)}) in ({placeholders})
        order by {_quote_identifier(ticker_col)}, {_quote_identifier(date_col)}
    """
    params = [ticker.upper() for ticker in tickers]
    return [
        {
            "ticker": str(ticker).upper(),
            "date": date,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
        for ticker, date, open_, high, low, close, volume in con.execute(query, params)
    ]


def _default_warehouse_paths(data_dir: str | Path | None = None) -> list[Path]:
    root = Path(data_dir) if data_dir is not None else DATA_ROOT
    return [
        root / "warehouse" / "warehouse_main_hot.sqlite",
        root / "warehouse" / "warehouse_main.sqlite",
        root / "experiments" / "exp-20260519-030" / "warehouse_main.sqlite",
    ]


def _load_warehouse_bars_for_tickers(
    tickers: list[str],
    *,
    data_dir: str | Path | None = None,
    warehouse_paths: list[str | Path] | tuple[str | Path, ...] | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    if not tickers:
        return {}, {"status": "no_tickers", "sources": []}
    paths = [Path(path) for path in (warehouse_paths or _default_warehouse_paths(data_dir))]
    requested = sorted({str(ticker).upper() for ticker in tickers if str(ticker).strip()})
    bars: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in requested}
    seen: set[tuple[str, str]] = set()
    sources: list[dict[str, Any]] = []
    for path in paths:
        source = {"path": str(path), "exists": path.exists(), "tables": [], "returned_rows": 0}
        if not path.exists():
            sources.append(source)
            continue
        try:
            with sqlite3.connect(path) as con:
                tables = {
                    str(row[0])
                    for row in con.execute(
                        "select name from sqlite_master where type='table'"
                    )
                }
                for table in ("ohlcv", "ohlcv_snapshot_versions"):
                    if table not in tables:
                        continue
                    row_count = int(
                        con.execute(f"select count(*) from {_quote_identifier(table)}").fetchone()[0]
                    )
                    table_info = {"table": table, "row_count": row_count, "returned_rows": 0}
                    if row_count > 0:
                        rows = _load_warehouse_bars_from_table(
                            con,
                            table=table,
                            tickers=requested,
                        )
                        for row in rows:
                            day = _date10(row.get("date"))
                            ticker = str(row.get("ticker") or "").upper()
                            if not day or ticker not in bars:
                                continue
                            key = (ticker, day)
                            if key in seen:
                                continue
                            seen.add(key)
                            bars[ticker].append(row)
                        table_info["returned_rows"] = len(rows)
                        source["returned_rows"] += len(rows)
                    source["tables"].append(table_info)
        except Exception as exc:
            source["error"] = str(exc)
        sources.append(source)
    for rows in bars.values():
        rows.sort(key=lambda row: _date10(row.get("date")) or "")
    all_dates = [
        _date10(row.get("date"))
        for ticker_rows in bars.values()
        for row in ticker_rows
        if _date10(row.get("date"))
    ]
    returned_tickers = sorted(ticker for ticker, rows in bars.items() if rows)
    return bars, {
        "status": "ok" if all_dates else "no_bars",
        "requested_tickers": len(requested),
        "returned_tickers": len(returned_tickers),
        "returned_rows": sum(len(rows) for rows in bars.values()),
        "date_min": min(all_dates) if all_dates else None,
        "date_max": max(all_dates) if all_dates else None,
        "sources": sources,
    }


def persist_prediction_market_event_outcome_ledger(
    today: str | datetime | None = None,
    *,
    data_dir: str | Path | None = None,
    ohlcv_by_ticker: dict[str, Any] | None = None,
    warehouse_paths: list[str | Path] | tuple[str | Path, ...] | None = None,
    horizons: tuple[int, ...] = (10,),
    notional_usd: float = 4000.0,
) -> dict[str, Any]:
    """Refresh the observer-only forward outcome ledger through ``today``.

    The ledger is a daily materialized measurement surface. It never feeds
    prompts, ranking, sizing, exits, or orders.
    """
    date_tag = _date_tag(today)
    items, item_files = _load_daily_items_through(date_tag, data_dir=data_dir)
    tickers = _candidate_tickers_for_outcomes(items)
    if ohlcv_by_ticker is None:
        bars, warehouse_summary = _load_warehouse_bars_for_tickers(
            tickers,
            data_dir=data_dir,
            warehouse_paths=warehouse_paths,
        )
    else:
        bars = ohlcv_by_ticker
        warehouse_summary = {
            "status": "provided",
            "requested_tickers": len(tickers),
            "returned_tickers": len([ticker for ticker, rows in bars.items() if rows]),
            "returned_rows": sum(len(rows) for rows in bars.values() if isinstance(rows, list)),
            "sources": [],
        }
    rows, summary = build_prediction_market_event_outcome_ledger(
        items,
        bars,
        as_of_date=date_tag,
        horizons=horizons,
        notional_usd=notional_usd,
    )
    paths = _artifact_paths(date_tag, data_dir)
    summary.update(
        {
            "status": "ok" if item_files else "missing_items",
            "date": date_tag,
            "daily_item_file_count": len(item_files),
            "daily_item_files": item_files,
            "candidate_ticker_count": len(tickers),
            "warehouse": warehouse_summary,
            "ledger_path": str(paths["outcome_ledger"]),
            "summary_path": str(paths["outcome_summary"]),
            "latest_summary_path": str(paths["latest_outcome_summary"]),
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
        }
    )
    write_prediction_market_event_outcome_ledger(
        rows,
        summary,
        ledger_path=paths["outcome_ledger"],
        summary_path=paths["outcome_summary"],
    )
    _write_json(summary, paths["latest_outcome_summary"])
    return summary


def write_prediction_market_event_outcome_ledger(
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    ledger_path: str | Path,
    summary_path: str | Path,
) -> None:
    ledger = Path(ledger_path)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    _remove_write_temps(ledger)
    _write_json(summary, Path(summary_path))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=None, help="Date tag YYYYMMDD or YYYY-MM-DD.")
    parser.add_argument("--data-dir", default=None, help="Optional data root override.")
    args = parser.parse_args(argv)
    summary = persist_prediction_market_event_observer(
        args.date,
        data_dir=args.data_dir,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


__all__ = [
    "OBSERVER_NAME",
    "OUTCOME_RULE_VERSION",
    "PREDICTION_MARKET_SOURCE_SPECS",
    "build_prediction_market_event_outcome_ledger",
    "extract_yes_probability",
    "get_prediction_market_observer_sources",
    "persist_prediction_market_event_observer",
    "persist_prediction_market_event_outcome_ledger",
    "prediction_market_source_relevance",
    "write_prediction_market_event_outcome_ledger",
]


if __name__ == "__main__":
    raise SystemExit(main())
