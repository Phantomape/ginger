"""exp-20260604-014: SEC text-price peer/theme propagation.

This alpha search tests one relation-construction candidate source. A
high/medium credibility SEC filing must already pass the prior text-price
alignment source test, then a liquid same-sector peer can become a default-off
paper candidate only if the peer independently shows signal-date trend,
relative strength, and liquidity confirmation before next-session entry.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
shared adapters, and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260603_012_sec_customer_contract_business_win as parent
import exp_20260604_003_sec_text_price_alignment_issuer_continuation as issuer_source
from broad_market_sector_map import DEFAULT_CACHE_PATH, load_cache, lookup_sector


EXP_ID = "exp-20260604-014"
STEM = "sec_text_peer_theme_propagation"
TRIAL_FAMILY = "sec_text_peer_theme_propagation_candidate_pool"
CHANGED_VARIABLE = "sec_text_price_alignment_same_sector_peer_propagation_candidate_source_v1"
RULE_VERSION = "sec_text_price_alignment_same_sector_peer_propagation_v1"

OUT_DIR = parent.REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = parent.REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = parent.REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
CARD_MD = parent.REPO_ROOT / "experiments" / "cards" / f"{EXP_ID}.md"
ARTIFACT_MD = parent.REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"
MANIFEST_JSON = parent.REPO_ROOT / "experiments" / "manifests" / f"{EXP_ID}.json"

EVENT_NOTIONAL = 4_000.0
MAX_PAPER_TRADES_PER_DAY = 1
MIN_PEER_AVG_DOLLAR_VOLUME_20D = 40_000_000.0
MIN_PEER_CLOSE_PRICE = 10.0
MIN_PEER_RS20_VS_SPY = 0.0
MIN_PEER_SIGNAL_EXCESS_VS_SPY = 0.003
MIN_PEER_CLOSE_LOCATION = 0.55
MOVING_AVERAGE_DAYS = 50
RELATIVE_STRENGTH_DAYS = 20
AVG_DOLLAR_VOLUME_DAYS = 20
MAX_PEERS_PER_SOURCE_EVENT = 3

MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30

EXCLUDED_PEER_TICKERS = {
    "DIA",
    "GLD",
    "IEF",
    "IWM",
    "QQQ",
    "SH",
    "SPY",
    "SQQQ",
    "TBT",
    "TLT",
    "TQQQ",
    "UUP",
    "UVXY",
    "VIXY",
    "XLE",
    "XLP",
    "XLU",
    "XLV",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "default_off_paper_only": True,
    "lookahead_guard": (
        "Source issuer filing text and source/peer OHLCV reactions are observed "
        "only through the signal-date close. The paper event usable_trade_date "
        "is shifted to the peer's next trading session before the existing "
        "next-open event helper prices the trade."
    ),
    "parity_note": (
        "This experiment changes no production code. A positive replay result "
        "cannot be promoted until the same SEC source filter, sector peer "
        "relation, peer OHLCV confirmations, next-session entry shift, and "
        "selection order are implemented in a shared default-off adapter with "
        "production/backtest parity tests."
    ),
}

_RAW_OHLCV_CACHE: dict[str, list[dict[str, Any]]] | None = None
_SECTOR_CACHE: dict[str, Any] | None = None
_SECTOR_LOOKUP_CACHE: tuple[dict[str, dict[str, Any]], dict[str, list[str]], dict[str, Any]] | None = None


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _configure_parent() -> None:
    parent.EXP_ID = EXP_ID
    parent.STEM = STEM
    parent.TRIAL_FAMILY = TRIAL_FAMILY
    parent.CHANGED_VARIABLE = CHANGED_VARIABLE
    parent.RULE_VERSION = RULE_VERSION
    parent.OUT_DIR = OUT_DIR
    parent.OUT_JSON = OUT_JSON
    parent.BEFORE_JSON = BEFORE_JSON
    parent.AFTER_JSON = AFTER_JSON
    parent.LOG_JSON = LOG_JSON
    parent.TICKET_JSON = TICKET_JSON
    parent.CARD_MD = CARD_MD
    parent.ARTIFACT_MD = ARTIFACT_MD
    parent.EVENT_NOTIONAL = EVENT_NOTIONAL
    parent.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    parent.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    parent.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    parent.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    parent._load_candidate_events = _load_candidate_events
    parent._write_artifact = _write_artifact
    parent._gate4_decision = _gate4_decision


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def _safe_round(value: Any, digits: int = 6) -> Any:
    number = _float_or_none(value)
    return None if number is None else round(number, digits)


def _date_value(row: dict[str, Any]) -> str:
    return str(row.get("Date") or row.get("date") or "")[:10]


def _price_value(row: dict[str, Any], key: str) -> float | None:
    return _float_or_none(row.get(key) if key in row else row.get(key.lower()))


def _load_raw_ohlcv() -> dict[str, list[dict[str, Any]]]:
    global _RAW_OHLCV_CACHE
    if _RAW_OHLCV_CACHE is not None:
        return _RAW_OHLCV_CACHE
    by_ticker_date: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for window in parent.WINDOWS.values():
        path = parent.REPO_ROOT / str(window["snapshot"])
        payload = parent._load_json(path, {})
        ohlcv = payload.get("ohlcv") if isinstance(payload, dict) else {}
        if not isinstance(ohlcv, dict):
            continue
        for ticker, rows in ohlcv.items():
            if not isinstance(rows, list):
                continue
            ticker_key = str(ticker).upper()
            for row in rows:
                if not isinstance(row, dict):
                    continue
                date_key = _date_value(row)
                if not date_key:
                    continue
                by_ticker_date[ticker_key][date_key] = row
    _RAW_OHLCV_CACHE = {
        ticker: sorted(rows.values(), key=_date_value)
        for ticker, rows in by_ticker_date.items()
    }
    return _RAW_OHLCV_CACHE


def _row_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {_date_value(row): idx for idx, row in enumerate(rows) if _date_value(row)}


def _close_return(rows: list[dict[str, Any]], start_idx: int, end_idx: int) -> float | None:
    if start_idx < 0 or end_idx < 0 or start_idx >= len(rows) or end_idx >= len(rows):
        return None
    start_close = _price_value(rows[start_idx], "Close")
    end_close = _price_value(rows[end_idx], "Close")
    if not start_close or end_close is None:
        return None
    return float(end_close) / float(start_close) - 1.0


def _average_close(rows: list[dict[str, Any]], idx: int, days: int) -> float | None:
    if idx < days - 1:
        return None
    values = [_price_value(row, "Close") for row in rows[idx - days + 1 : idx + 1]]
    if any(value is None for value in values):
        return None
    return float(sum(float(value) for value in values)) / float(days)


def _avg_dollar_volume(rows: list[dict[str, Any]], idx: int, days: int) -> float | None:
    if idx < days - 1:
        return None
    values: list[float] = []
    for row in rows[idx - days + 1 : idx + 1]:
        close = _price_value(row, "Close")
        volume = _price_value(row, "Volume")
        if close is None or volume is None:
            return None
        values.append(float(close) * float(volume))
    return sum(values) / len(values) if values else None


def _close_location(row: dict[str, Any]) -> float | None:
    high = _price_value(row, "High")
    low = _price_value(row, "Low")
    close = _price_value(row, "Close")
    if high is None or low is None or close is None:
        return None
    if float(high) <= float(low):
        return None
    return (float(close) - float(low)) / (float(high) - float(low))


def _next_row_index(rows: list[dict[str, Any]], signal_date: str) -> int | None:
    for idx, row in enumerate(rows):
        if _date_value(row) > signal_date:
            return idx
    return None


def _sector_cache() -> dict[str, Any]:
    global _SECTOR_CACHE
    if _SECTOR_CACHE is None:
        _SECTOR_CACHE = load_cache(DEFAULT_CACHE_PATH)
    return _SECTOR_CACHE


def _norm_sector(value: Any) -> str:
    return str(value or "").strip().lower()


def _sector_lookups() -> tuple[dict[str, dict[str, Any]], dict[str, list[str]], dict[str, Any]]:
    global _SECTOR_LOOKUP_CACHE
    if _SECTOR_LOOKUP_CACHE is not None:
        return _SECTOR_LOOKUP_CACHE
    prices = _load_raw_ohlcv()
    cache = _sector_cache()
    lookups: dict[str, dict[str, Any]] = {}
    by_sector: dict[str, list[str]] = defaultdict(list)
    for ticker in sorted(set(prices).difference(EXCLUDED_PEER_TICKERS)):
        lookup = lookup_sector(ticker, cache)
        lookups[ticker] = lookup
        if lookup.get("status") != "ok":
            continue
        sector = _norm_sector(lookup.get("sector"))
        if sector:
            by_sector[sector].append(ticker)
    coverage = {
        "cache_path": parent._repo_rel(DEFAULT_CACHE_PATH),
        "cache_generated_at": cache.get("generated_at"),
        "snapshot_ticker_count": len(prices),
        "lookup_count": len(lookups),
        "ok_lookup_count": sum(1 for row in lookups.values() if row.get("status") == "ok"),
        "sector_count": len(by_sector),
        "sector_member_counts": {
            sector: len(tickers) for sector, tickers in sorted(by_sector.items())
        },
    }
    _SECTOR_LOOKUP_CACHE = (lookups, by_sector, coverage)
    return _SECTOR_LOOKUP_CACHE


def _peer_context(
    *,
    peer_ticker: str,
    signal_date: str,
    source_event: dict[str, Any],
    sector_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    prices = _load_raw_ohlcv()
    rows = prices.get(peer_ticker)
    spy_rows = prices.get("SPY")
    if not rows or not spy_rows:
        return None
    idx_by_date = _row_index(rows)
    spy_idx_by_date = _row_index(spy_rows)
    idx = idx_by_date.get(signal_date)
    spy_idx = spy_idx_by_date.get(signal_date)
    if idx is None or spy_idx is None:
        return None
    min_idx = max(MOVING_AVERAGE_DAYS, RELATIVE_STRENGTH_DAYS, AVG_DOLLAR_VOLUME_DAYS)
    if idx < min_idx or spy_idx < RELATIVE_STRENGTH_DAYS or idx <= 0 or spy_idx <= 0:
        return None

    close = _price_value(rows[idx], "Close")
    if close is None or close < MIN_PEER_CLOSE_PRICE:
        return None
    avg_dollar_volume = _avg_dollar_volume(rows, idx, AVG_DOLLAR_VOLUME_DAYS)
    if avg_dollar_volume is None or avg_dollar_volume < MIN_PEER_AVG_DOLLAR_VOLUME_20D:
        return None
    ma50 = _average_close(rows, idx, MOVING_AVERAGE_DAYS)
    if ma50 is None or close <= ma50:
        return None
    close_location = _close_location(rows[idx])
    if close_location is None or close_location < MIN_PEER_CLOSE_LOCATION:
        return None

    peer_ret20 = _close_return(rows, idx - RELATIVE_STRENGTH_DAYS, idx)
    spy_ret20 = _close_return(spy_rows, spy_idx - RELATIVE_STRENGTH_DAYS, spy_idx)
    if peer_ret20 is None or spy_ret20 is None:
        return None
    rs20_vs_spy = peer_ret20 - spy_ret20
    if rs20_vs_spy < MIN_PEER_RS20_VS_SPY:
        return None

    peer_signal_return = _close_return(rows, idx - 1, idx)
    spy_signal_return = _close_return(spy_rows, spy_idx - 1, spy_idx)
    if peer_signal_return is None or spy_signal_return is None:
        return None
    peer_signal_excess = peer_signal_return - spy_signal_return
    if peer_signal_excess < MIN_PEER_SIGNAL_EXCESS_VS_SPY:
        return None

    next_idx = _next_row_index(rows, signal_date)
    if next_idx is None or next_idx >= len(rows):
        return None
    entry_date = _date_value(rows[next_idx])
    window = parent._window_name(entry_date)
    if not window:
        return None

    peer_lookup = sector_lookup.get(peer_ticker) or {}
    source_industry = str(source_event.get("source_industry") or "")
    peer_industry = str(peer_lookup.get("industry") or "")
    same_industry = bool(source_industry and peer_industry and source_industry == peer_industry)
    source_score = float(source_event.get("candidate_selection_score") or 0.0)
    source_excess = float(source_event.get("signal_day_excess_vs_spy_pct") or 0.0) / 100.0
    score = (
        10.0 * source_score
        + 70.0 * source_excess
        + 35.0 * peer_signal_excess
        + 15.0 * rs20_vs_spy
        + 0.20 * math.log(max(float(avg_dollar_volume), 1.0))
        + (0.50 if same_industry else 0.0)
    )
    return {
        "ticker": peer_ticker,
        "usable_trade_date": entry_date,
        "signal_date": signal_date,
        "window": window,
        "status": "event_ready",
        "rule_version": RULE_VERSION,
        "strategy": STEM,
        "source_ticker": source_event["ticker"],
        "source_signal_date": signal_date,
        "source_sec_usable_trade_date": source_event.get("sec_usable_trade_date"),
        "source_entry_date": source_event.get("usable_trade_date"),
        "source_accession_number": source_event.get("accession_number"),
        "source_primary_document": source_event.get("primary_document"),
        "source_form_type": source_event.get("form_type"),
        "source_eight_k_item_codes": source_event.get("eight_k_item_codes"),
        "source_credibility_bucket": source_event.get("source_credibility_bucket"),
        "source_language_bucket": source_event.get("language_bucket"),
        "source_text_event_type": source_event.get("text_event_type"),
        "source_language_score": source_event.get("language_score"),
        "source_positive_phrase_hits": source_event.get("positive_phrase_hits"),
        "source_guidance_raise_hits": source_event.get("guidance_raise_hits"),
        "source_signal_day_return_pct": source_event.get("signal_day_return_pct"),
        "source_signal_day_excess_vs_spy_pct": source_event.get("signal_day_excess_vs_spy_pct"),
        "source_sector": source_event.get("source_sector"),
        "source_industry": source_industry or None,
        "peer_sector": peer_lookup.get("sector"),
        "peer_industry": peer_industry or None,
        "same_industry": same_industry,
        "candidate_selection_score": round(score, 6),
        "peer_signal_return_pct": round(peer_signal_return * 100.0, 6),
        "peer_signal_excess_vs_spy_pct": round(peer_signal_excess * 100.0, 6),
        "peer_rs20_vs_spy_pct": round(rs20_vs_spy * 100.0, 6),
        "peer_close_location": round(close_location, 6),
        "peer_close_price": round(float(close), 6),
        "peer_ma50": round(float(ma50), 6),
        "peer_avg_dollar_volume_20d": round(float(avg_dollar_volume), 2),
        "min_peer_avg_dollar_volume_20d": MIN_PEER_AVG_DOLLAR_VOLUME_20D,
        "min_peer_signal_excess_vs_spy_pct": MIN_PEER_SIGNAL_EXCESS_VS_SPY * 100.0,
        "min_peer_rs20_vs_spy_pct": MIN_PEER_RS20_VS_SPY * 100.0,
        "min_peer_close_location": MIN_PEER_CLOSE_LOCATION,
        "known_at": "after_source_and_peer_signal_date_close_before_peer_next_session_open",
        "trade_enabled": False,
        "alters_orders": False,
    }


def _load_source_events() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = parent.load_sec_filing_text_rows(parent.SEC_TEXT_PATH)
    sector_lookup, _by_sector, sector_coverage = _sector_lookups()
    events: list[dict[str, Any]] = []
    source_rows_by_window: Counter[str] = Counter()
    source_event_by_window: Counter[str] = Counter()
    missing_sector = 0
    for row in rows:
        usable = str(row.get("usable_trade_date") or "")[:10]
        window = parent._window_name(usable)
        if window:
            source_rows_by_window[window] += 1
        source = issuer_source._candidate_from_row(row)
        if source is None:
            continue
        ticker = str(source.get("ticker") or "").upper()
        lookup = sector_lookup.get(ticker) or lookup_sector(ticker, _sector_cache())
        if lookup.get("status") != "ok" or not lookup.get("sector"):
            missing_sector += 1
            continue
        source = dict(source)
        source["source_sector"] = lookup.get("sector")
        source["source_industry"] = lookup.get("industry")
        source["source_sector_lookup"] = lookup
        events.append(source)
        source_event_by_window[str(source.get("window") or "unknown")] += 1
    events.sort(
        key=lambda row: (
            str(row.get("signal_date") or ""),
            -float(row.get("candidate_selection_score") or 0.0),
            str(row.get("ticker") or ""),
        )
    )
    return events, {
        "sec_text_file": parent._repo_rel(parent.SEC_TEXT_PATH),
        "source_row_count": len(rows),
        "source_rows_by_window": dict(sorted(source_rows_by_window.items())),
        "text_price_aligned_source_event_count": len(events),
        "text_price_aligned_source_events_by_window": dict(sorted(source_event_by_window.items())),
        "source_events_missing_sector": missing_sector,
        "sector_coverage": sector_coverage,
    }


def _load_candidate_events() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_events, source_audit = _load_source_events()
    sector_lookup, by_sector, sector_coverage = _sector_lookups()
    best_by_peer_entry: dict[tuple[str, str], dict[str, Any]] = {}
    audit: Counter[str] = Counter()
    raw_relation_count = 0
    for source_event in source_events:
        source_ticker = str(source_event.get("ticker") or "").upper()
        signal_date = str(source_event.get("signal_date") or "")[:10]
        source_sector = _norm_sector(source_event.get("source_sector"))
        if not source_ticker or not signal_date or not source_sector:
            audit["source_missing_relation_context"] += 1
            continue
        peers = [
            ticker
            for ticker in by_sector.get(source_sector, [])
            if ticker != source_ticker and ticker not in EXCLUDED_PEER_TICKERS
        ]
        if not peers:
            audit["source_has_no_same_sector_peers"] += 1
            continue
        peer_rows: list[dict[str, Any]] = []
        for peer_ticker in peers:
            context = _peer_context(
                peer_ticker=peer_ticker,
                signal_date=signal_date,
                source_event=source_event,
                sector_lookup=sector_lookup,
            )
            if context is None:
                audit["peer_failed_context_or_thresholds"] += 1
                continue
            raw_relation_count += 1
            peer_rows.append(context)
        if not peer_rows:
            audit["source_has_no_qualified_peer"] += 1
            continue
        peer_rows.sort(
            key=lambda row: (
                -float(row.get("candidate_selection_score") or 0.0),
                -float(row.get("peer_signal_excess_vs_spy_pct") or 0.0),
                -float(row.get("peer_rs20_vs_spy_pct") or 0.0),
                str(row.get("ticker") or ""),
            )
        )
        for row in peer_rows[:MAX_PEERS_PER_SOURCE_EVENT]:
            key = (str(row["ticker"]), str(row["usable_trade_date"]))
            existing = best_by_peer_entry.get(key)
            if existing is None:
                row["source_event_count_for_peer_entry"] = 1
                best_by_peer_entry[key] = row
                continue
            existing["source_event_count_for_peer_entry"] = int(
                existing.get("source_event_count_for_peer_entry") or 1
            ) + 1
            if float(row.get("candidate_selection_score") or 0.0) > float(
                existing.get("candidate_selection_score") or 0.0
            ):
                row["source_event_count_for_peer_entry"] = existing[
                    "source_event_count_for_peer_entry"
                ]
                best_by_peer_entry[key] = row

    events = sorted(
        best_by_peer_entry.values(),
        key=lambda row: (
            str(row.get("usable_trade_date") or ""),
            -float(row.get("candidate_selection_score") or 0.0),
            str(row.get("ticker") or ""),
        ),
    )
    return events, {
        **source_audit,
        "sector_coverage": sector_coverage,
        "raw_peer_relation_count": raw_relation_count,
        "candidate_count": len(events),
        "candidate_count_by_window": dict(sorted(Counter(row["window"] for row in events).items())),
        "candidate_ticker_count": len({row["ticker"] for row in events}),
        "candidate_tickers": sorted({row["ticker"] for row in events}),
        "reject_counts": dict(sorted(audit.items())),
        "parameters": {
            "max_peers_per_source_event": MAX_PEERS_PER_SOURCE_EVENT,
            "min_peer_avg_dollar_volume_20d": MIN_PEER_AVG_DOLLAR_VOLUME_20D,
            "min_peer_close_price": MIN_PEER_CLOSE_PRICE,
            "min_peer_rs20_vs_spy": MIN_PEER_RS20_VS_SPY,
            "min_peer_signal_excess_vs_spy": MIN_PEER_SIGNAL_EXCESS_VS_SPY,
            "min_peer_close_location": MIN_PEER_CLOSE_LOCATION,
            "moving_average_days": MOVING_AVERAGE_DAYS,
            "relative_strength_days": RELATIVE_STRENGTH_DAYS,
            "avg_dollar_volume_days": AVG_DOLLAR_VOLUME_DAYS,
        },
    }


def _field_coverage(rows: list[dict[str, Any]], fields: list[str]) -> dict[str, Any]:
    total = len(rows)
    return {
        field: {
            "present_count": sum(1 for row in rows if field in row),
            "non_null_count": sum(
                1 for row in rows if row.get(field) not in (None, "", [], {})
            ),
            "total_count": total,
            "non_null_share": round(
                sum(1 for row in rows if row.get(field) not in (None, "", [], {})) / total,
                6,
            )
            if total
            else None,
        }
        for field in fields
    }


def _open_positions_field_coverage() -> dict[str, Any]:
    path = parent.REPO_ROOT / "operator_inputs" / "open_positions.json"
    payload = parent._load_json(path, {})
    rows: list[dict[str, Any]] = []
    if isinstance(payload, dict):
        for key in ("observations", "core_positions", "positions"):
            value = payload.get(key)
            if isinstance(value, list):
                rows.extend([row for row in value if isinstance(row, dict)])
    return {
        "path": parent._repo_rel(path),
        "position_count": len(rows),
        "coverage": _field_coverage(rows, ["ticker", "entry_date", "target_price"]),
    }


def _gate3_audit(core_run_audit: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = {}
    min_survival = 1.0
    for label, row in core_run_audit.items():
        survival = float(row.get("survival_rate") or 0.0)
        min_survival = min(min_survival, survival)
        rows[label] = {
            "signals_generated": row.get("signals_generated"),
            "signals_survived": row.get("signals_survived"),
            "survival_rate": survival,
            "survival_rate_floor_passed": survival >= 0.05,
        }
    return {
        "survival_rate_floor": 0.05,
        "min_survival_rate": min_survival,
        "passed": all(row["survival_rate_floor_passed"] for row in rows.values()),
        "by_window": rows,
    }


def _gate4_decision(
    aggregate: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    gate4 = issuer_source._PARENT_GATE4_DECISION(aggregate, results, target_summary)
    passed = bool(gate4["passed"])
    gate4["decision"] = (
        "positive_sec_text_peer_theme_propagation_replay_lead_requires_shared_adapter"
        if passed
        else "rejected_sec_text_peer_theme_propagation_candidate_pool"
    )
    gate4["status"] = "observed_only" if passed else "rejected"
    gate4["requires_parity_before_promotion"] = passed
    gate4["rationale"] = (
        "The SEC text-price peer/theme propagation replay passed all Gate 4 "
        "checks, but remains replay-only. It cannot affect production or be "
        "retained as a live surface until a shared default-off adapter and "
        "parity tests are added."
        if passed
        else "One or more Gate 4 checks failed, so the SEC text-price peer/theme "
        "propagation candidate source is not retained."
    )
    return gate4


def _window_table(results: list[dict[str, Any]]) -> str:
    lines = [
        "| Window | Target trades | Target PnL | EV before | EV after | EV delta | PnL delta | DD delta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in results:
        lines.append(
            "| {label} | {count} | ${target_pnl:,.2f} | {before_ev:.4f} | {after_ev:.4f} | {ev_delta:+.4f} | ${pnl_delta:+,.2f} | {dd_delta:+.4f} |".format(
                label=row["label"],
                count=row["target_trade_count"],
                target_pnl=float(row["target_trade_pnl_usd"]),
                before_ev=float(row["before"]["expected_value_score"]),
                after_ev=float(row["after"]["expected_value_score"]),
                ev_delta=float(row["comparison"]["expected_value_score_delta"]),
                pnl_delta=float(row["comparison"]["strategy_total_pnl_delta"]),
                dd_delta=float(row["comparison"]["max_drawdown_delta"]),
            )
        )
    return "\n".join(lines)


def _write_artifact(payload: dict[str, Any]) -> None:
    comparison = payload["aggregate"]["comparison"]
    lines = [
        f"# {EXP_ID} SEC Text-Price Peer/Theme Propagation",
        "",
        f"- Trial family: `{TRIAL_FAMILY}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Aggregate EV delta: {float(comparison['expected_value_score_delta']):+.4f}",
        f"- Aggregate PnL delta: ${float(comparison['strategy_total_pnl_delta']):+,.2f}",
        f"- Target trades: {payload['target_summary']['target_trade_count']}",
        f"- Production impact: `{PRODUCTION_IMPACT['adapter_status']}`",
        "",
        "## Gate 1-4",
        "",
        _window_table(payload["results"]),
        "",
        "## Gate 2 Field Coverage",
        "",
        "```json",
        json.dumps(payload["gate2"], indent=2, sort_keys=True),
        "```",
        "",
        "## Gate 3 Survival Audit",
        "",
        "```json",
        json.dumps(payload["gate3"], indent=2, sort_keys=True),
        "```",
        "",
        "## Gate 4 Checks",
        "",
    ]
    for key, value in payload["gate4"]["gates"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Decision Rationale",
            "",
            payload["gate4"]["rationale"],
            "",
            "## Lookahead / Parity Guard",
            "",
            PRODUCTION_IMPACT["lookahead_guard"],
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reproducibility",
            "",
            (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260604_014_sec_text_peer_theme_propagation.py"
            ),
            "",
            "No JavaScript was used.",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _patch_payload(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate"]["comparison"]
    actual_success = 1 if payload["gate4"]["passed"] else 0
    all_target_trades = [
        trade
        for rows in payload["event_candidate_details"].values()
        for trade in rows.get("selected_trades", [])
    ]
    prediction = {
        "success_probability": 0.18,
        "expected_ev_delta": 0.16,
        "expected_pnl_delta": 3000.0,
        "main_failure_modes": [
            "window_regression",
            "thin_sample",
            "peer_relation_noise",
            "concentration_failed",
        ],
        "confidence_reason": (
            "Prior standalone SEC issuer text-price alignment failed late_strong; "
            "this run changes only relation construction to peers, using free "
            "production-visible SEC text plus OHLCV."
        ),
        "recorded_at": "2026-06-04T14:11:16Z",
        "actual_success": actual_success,
        "actual_ev_delta": comparison["expected_value_score_delta"],
        "actual_pnl_delta": comparison["strategy_total_pnl_delta"],
        "brier_score": round((0.18 - actual_success) ** 2, 6),
    }
    payload.update(
        {
            "experiment_id": EXP_ID,
            "completed_at": _utc_now(),
            "lane": "alpha_search",
            "trial_family": TRIAL_FAMILY,
            "changed_variable": CHANGED_VARIABLE,
            "rule_version": RULE_VERSION,
            "preflight": {
                "alpha_hypothesis": (
                    "SEC positive text-price aligned source issuers may transfer "
                    "to liquid same-sector peers with independent signal-date "
                    "strength, producing a cleaner candidate pool than standalone "
                    "issuer continuation."
                ),
                "category": "entry / candidate_pool",
                "playbook_alignment": (
                    "Uses a free, production-visible SEC text/OHLCV relation field "
                    "and follows the playbook note to retry SEC text only with "
                    "richer relation/source-span structure. It avoids LLM "
                    "soft-ranking, consensus retunes, Companyfacts support retunes, "
                    "and state-surface capital allocation tweaks."
                ),
                "nearby_prior_experiments": {
                    "exp-20260604-003": (
                        "Standalone SEC text-price issuer continuation was rejected: "
                        "positive aggregate but late_strong regressed."
                    ),
                    "exp-20260603-012": (
                        "SEC customer-contract/business-win text was rejected: "
                        "semantic false positives and weak aggregate."
                    ),
                    "exp-20260603-005": (
                        "Post-earnings characteristic peer transfer was rejected: "
                        "peer relation noise/concentration."
                    ),
                    "exp-20260602-020": (
                        "Pure OHLCV sector peer moderate shock failed; this run "
                        "uses SEC text-price events as the source relation."
                    ),
                },
                "single_causal_variable": CHANGED_VARIABLE,
                "acceptance_criteria": {
                    "canonical_windows": list(parent.WINDOWS.keys()),
                    "aggregate_expected_value_delta": "> 0",
                    "aggregate_pnl_delta": "> 0",
                    "per_window_expected_value_delta": "3 of 3 windows > 0",
                    "per_window_pnl_delta": "3 of 3 windows > 0",
                    "minimum_target_trades": parent.MIN_TARGET_TRADES,
                    "minimum_target_windows": parent.MIN_TARGET_WINDOWS,
                    "max_drawdown_drift": parent.MAX_DRAWDOWN_WORSE,
                    "survival_rate_floor": 0.05,
                    "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                    "positive_pnl_hhi_max": MAX_POSITIVE_HHI,
                    "promotion_parity": (
                        "Positive replay cannot be promoted until implemented "
                        "through a shared default-off production/backtest helper."
                    ),
                },
                "reproducibility": (
                    "The runner persists canonical before/after metrics, selected "
                    "peer trades, Gate 2/3/4 checks, ticket, card, artifact, and "
                    "experiment_log.jsonl record under exp-20260604-014."
                ),
            },
            "parameters": {
                **payload.get("parameters", {}),
                "event_notional": EVENT_NOTIONAL,
                "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
                "max_peers_per_source_event": MAX_PEERS_PER_SOURCE_EVENT,
                "source_rule": issuer_source.RULE_VERSION,
                "peer_thresholds": {
                    "min_avg_dollar_volume_20d": MIN_PEER_AVG_DOLLAR_VOLUME_20D,
                    "min_close_price": MIN_PEER_CLOSE_PRICE,
                    "min_rs20_vs_spy": MIN_PEER_RS20_VS_SPY,
                    "min_signal_excess_vs_spy": MIN_PEER_SIGNAL_EXCESS_VS_SPY,
                    "min_close_location": MIN_PEER_CLOSE_LOCATION,
                    "moving_average_days": MOVING_AVERAGE_DAYS,
                    "relative_strength_days": RELATIVE_STRENGTH_DAYS,
                },
                "selection_order": (
                    "entry_date asc, candidate_selection_score desc, "
                    "source/peer strength desc, ticker asc"
                ),
            },
            "prediction": prediction,
            "production_impact": PRODUCTION_IMPACT,
            "llm_metrics": {
                "used_llm": False,
                "llm_change_scope": "none",
                "note": "No LLM soft-ranking was used because replay-safe LLM rows remain sparse.",
            },
            "gate2": {
                "open_positions_required_fields": _open_positions_field_coverage(),
                "source_fields": {
                    "sec_text_path": parent._repo_rel(parent.SEC_TEXT_PATH),
                    "required_fields": [
                        "ticker",
                        "usable_trade_date",
                        "accepted_at",
                        "form_type",
                        "form_base",
                        "eight_k_item_codes",
                        "combined_text",
                        "pit_source",
                    ],
                    "source_decision_time": (
                        "SEC text accepted_at/usable_trade_date plus signal-date "
                        "OHLCV close; entry shifted to next trading session."
                    ),
                },
                "peer_target_trade_field_coverage": _field_coverage(
                    all_target_trades,
                    [
                        "ticker",
                        "source_ticker",
                        "signal_date",
                        "usable_trade_date",
                        "entry_date",
                        "exit_date",
                        "pnl",
                        "source_accession_number",
                        "source_language_bucket",
                        "source_signal_day_excess_vs_spy_pct",
                        "peer_signal_excess_vs_spy_pct",
                        "peer_rs20_vs_spy_pct",
                        "peer_avg_dollar_volume_20d",
                        "known_at",
                    ],
                ),
                "production_boundary": PRODUCTION_IMPACT,
            },
            "gate3": _gate3_audit(payload["core_run_audit"]),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["next_action"] = (
        "If positive, implement the exact rule in a shared default-off adapter "
        "with parity tests before any promotion; if rejected, do not retune "
        "nearby SEC same-sector peer thresholds on this frozen sample."
        if payload["gate4"]["passed"]
        else (
            "Do not retune nearby SEC same-sector peer thresholds on this frozen "
            "sample; move to a different free-data relation mechanism."
        )
    )
    return payload


def _write_manifest() -> None:
    files = {
        "runner": parent._repo_rel(Path(__file__)),
        "result": parent._repo_rel(OUT_JSON),
        "before_aggregate": parent._repo_rel(BEFORE_JSON),
        "after_aggregate": parent._repo_rel(AFTER_JSON),
        "log": parent._repo_rel(LOG_JSON),
        "ticket": parent._repo_rel(TICKET_JSON),
        "card": parent._repo_rel(CARD_MD),
        "artifact": parent._repo_rel(ARTIFACT_MD),
        "manifest": parent._repo_rel(MANIFEST_JSON),
        "experiment_log": parent._repo_rel(parent.EXPERIMENT_LOG),
    }
    manifest = {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXP_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": {
            label: {
                "path": rel_path,
                "exists": (parent.REPO_ROOT / rel_path).exists(),
                "sha256": _sha256(parent.REPO_ROOT / rel_path),
            }
            for label, rel_path in files.items()
        },
    }
    parent._write_json(MANIFEST_JSON, manifest)


def main() -> int:
    _configure_parent()
    payload = parent.build_payload()
    payload = _patch_payload(payload)
    parent.persist(payload)
    _write_manifest()
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["gate4"]["decision"],
                "aggregate": payload["aggregate"]["comparison"],
                "target_summary": payload["target_summary"],
                "gate4": payload["gate4"],
                "anti_js": payload["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
