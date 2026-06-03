"""exp-20260603-005: post-earnings characteristic-similarity peer transfer.

This alpha search tests one relation-construction candidate source. A confirmed
positive EPS-surprise issuer must have a positive event-day reaction, then a
liquid same-sector peer can enter a default-off paper sleeve only if it is close
to the issuer on point-in-time SEC Companyfacts and OHLCV characteristics.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
shared adapters, and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260602_006_post_earnings_positive_surprise_drift_candidate_pool as parent
from broad_market_sector_map import DEFAULT_CACHE_PATH, load_cache, lookup_sector


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from fundamental_growth_rs_paper_sleeve import (  # noqa: E402
    CompanyfactsFundamentalIndex,
    DEFAULT_CONFIG as FUNDAMENTAL_CONFIG,
    load_companyfacts_rows,
)


EXPERIMENT_ID = "exp-20260603-005"
STEM = "post_earnings_characteristic_similarity_peer_transfer"
TRIAL_FAMILY = "post_earnings_characteristic_similarity_peer_transfer"
CHANGED_VARIABLE = "post_earnings_characteristic_similarity_peer_transfer_candidate_source_v1"
RULE_VERSION = "post_earnings_characteristic_similarity_peer_transfer_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260603_005_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

RECENT_SIGNAL_DAYS_MIN = 0
RECENT_SIGNAL_DAYS_MAX = 3
MIN_ISSUER_EVENT_EXCESS_VS_SPY = 0.01
MIN_ISSUER_EVENT_CLOSE_LOCATION = 0.55
MIN_PEER_SIGNAL_EXCESS_VS_SPY = 0.003
MIN_PEER_EVENT_TO_SIGNAL_EXCESS_VS_SPY = 0.0
MIN_PEER_CLOSE_LOCATION = 0.55
MIN_CHARACTERISTIC_SIMILARITY = 0.55
MIN_COMMON_CHARACTERISTICS = 5
MIN_COMMON_FUNDAMENTAL_CHARACTERISTICS = 2
RET60_DAYS = 60
VOLATILITY_DAYS = 20
MOVING_AVERAGE_DAYS = parent.MOVING_AVERAGE_DAYS
RELATIVE_STRENGTH_DAYS = parent.RELATIVE_STRENGTH_DAYS
AVG_DOLLAR_VOLUME_DAYS = parent.AVG_DOLLAR_VOLUME_DAYS
MIN_AVG_DOLLAR_VOLUME_20D = parent.MIN_AVG_DOLLAR_VOLUME_20D
MIN_RS20_VS_SPY = parent.MIN_RS20_VS_SPY

_FUNDAMENTAL_INDEX_CACHE: dict[
    tuple[str, tuple[str, ...]],
    CompanyfactsFundamentalIndex,
] = {}


def _sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _patch_parent() -> None:
    parent.EXPERIMENT_ID = EXPERIMENT_ID
    parent.STEM = STEM
    parent.TRIAL_FAMILY = TRIAL_FAMILY
    parent.CHANGED_VARIABLE = CHANGED_VARIABLE
    parent.RULE_VERSION = RULE_VERSION
    parent.OUT_DIR = OUT_DIR
    parent.OUT_JSON = OUT_JSON
    parent.BEFORE_AGG_JSON = BEFORE_AGG_JSON
    parent.AFTER_AGG_JSON = AFTER_AGG_JSON
    parent.LOG_JSON = LOG_JSON
    parent.TICKET_JSON = TICKET_JSON
    parent.CARD_MD = CARD_MD
    parent.ARTIFACT_MD = ARTIFACT_MD
    parent.EXPERIMENT_LOG = EXPERIMENT_LOG
    parent.MANIFEST_JSON = MANIFEST_JSON
    parent._patch_framework()
    parent.framework._candidate_rows_for_window = _candidate_rows_for_window
    parent.framework._build_report = _build_report


def _norm_sector(value: Any) -> str:
    return str(value or "").strip().lower()


def _sector_peers(
    universe: list[str],
    snapshot: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]], dict[str, Any]]:
    cache = load_cache(DEFAULT_CACHE_PATH)
    lookups: dict[str, dict[str, Any]] = {}
    by_sector: dict[str, list[str]] = defaultdict(list)
    candidate_universe = sorted(
        set(universe).intersection(snapshot).difference(parent.framework.EXCLUDED_TICKERS)
    )
    for ticker in candidate_universe:
        lookup = lookup_sector(ticker, cache)
        lookups[ticker] = lookup
        if lookup.get("status") != "ok":
            continue
        sector = _norm_sector(lookup.get("sector"))
        if not sector:
            continue
        by_sector[sector].append(ticker)
    coverage = {
        "cache_path": str(DEFAULT_CACHE_PATH.relative_to(REPO_ROOT)),
        "cache_generated_at": cache.get("generated_at"),
        "tickers_with_lookup": len(lookups),
        "ok_lookup_count": sum(1 for row in lookups.values() if row.get("status") == "ok"),
        "sector_count": len(by_sector),
    }
    return lookups, by_sector, coverage


def _fundamental_index(max_filed: str, tickers: list[str]) -> CompanyfactsFundamentalIndex:
    key = (max_filed, tuple(sorted(set(tickers))))
    cached = _FUNDAMENTAL_INDEX_CACHE.get(key)
    if cached is not None:
        return cached
    rows = load_companyfacts_rows(max_filed=max_filed, tickers=list(key[1]))
    index = CompanyfactsFundamentalIndex(rows, config=dict(FUNDAMENTAL_CONFIG))
    _FUNDAMENTAL_INDEX_CACHE[key] = index
    return index


def _realized_volatility(rows: list[dict[str, Any]], idx: int, days: int) -> float | None:
    if idx < days:
        return None
    values: list[float] = []
    for cursor in range(idx - days + 1, idx + 1):
        prev_close = parent.framework.ohlcv_helper._value(rows[cursor - 1], "Close")
        close = parent.framework.ohlcv_helper._value(rows[cursor], "Close")
        if not prev_close or close is None:
            return None
        values.append((float(close) / float(prev_close)) - 1.0)
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(max(variance, 0.0))


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


def _characteristic_vector(
    *,
    ticker: str,
    signal_date: str,
    rows: list[dict[str, Any]],
    idx: int,
    avg_dollar_volume: float,
    fundamentals: CompanyfactsFundamentalIndex,
) -> dict[str, float | None]:
    fundamental = fundamentals.fundamental_context(ticker, signal_date)
    operating = fundamentals.operating_quality(ticker, signal_date)
    balance = fundamentals.balance_sheet_quality(ticker, signal_date)
    ret20 = parent.earnings_helper._close_return(rows, idx - RELATIVE_STRENGTH_DAYS, idx)
    ret60 = parent.earnings_helper._close_return(rows, idx - RET60_DAYS, idx)
    volatility = _realized_volatility(rows, idx, VOLATILITY_DAYS)
    return {
        "revenue_yoy_growth": _float_or_none(fundamental.get("revenue_yoy_growth")),
        "eps_yoy_growth": _float_or_none(fundamental.get("eps_yoy_growth")),
        "operating_margin_current": _float_or_none(
            operating.get("operating_margin_current")
        ),
        "liabilities_assets_ratio": _float_or_none(
            balance.get("liabilities_assets_ratio")
        ),
        "ret20": _float_or_none(ret20),
        "ret60": _float_or_none(ret60),
        "realized_volatility_20d": _float_or_none(volatility),
        "log_avg_dollar_volume_20d": math.log(max(float(avg_dollar_volume), 1.0)),
    }


def _rounded_vector(vector: dict[str, float | None]) -> dict[str, float | None]:
    return {
        key: None if value is None else parent.framework.base._round(value, 6)
        for key, value in sorted(vector.items())
    }


def _similarity(
    issuer: dict[str, float | None],
    peer: dict[str, float | None],
) -> dict[str, Any] | None:
    normalizers = {
        "revenue_yoy_growth": 1.50,
        "eps_yoy_growth": 1.50,
        "operating_margin_current": 0.75,
        "liabilities_assets_ratio": 0.75,
        "ret20": 0.35,
        "ret60": 0.75,
        "realized_volatility_20d": 0.05,
        "log_avg_dollar_volume_20d": 2.00,
    }
    fundamental_keys = {
        "revenue_yoy_growth",
        "eps_yoy_growth",
        "operating_margin_current",
        "liabilities_assets_ratio",
    }
    distances: dict[str, float] = {}
    for key, normalizer in normalizers.items():
        left = issuer.get(key)
        right = peer.get(key)
        if left is None or right is None:
            continue
        distances[key] = min(abs(float(left) - float(right)) / normalizer, 1.0)
    common_fundamental = len([key for key in distances if key in fundamental_keys])
    if len(distances) < MIN_COMMON_CHARACTERISTICS:
        return None
    if common_fundamental < MIN_COMMON_FUNDAMENTAL_CHARACTERISTICS:
        return None
    avg_distance = sum(distances.values()) / len(distances)
    score = max(0.0, 1.0 - avg_distance)
    return {
        "characteristic_similarity_score": score,
        "common_characteristics": len(distances),
        "common_fundamental_characteristics": common_fundamental,
        "characteristic_distance_components": {
            key: parent.framework.base._round(value, 6)
            for key, value in sorted(distances.items())
        },
    }


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = parent.framework.ohlcv_helper._baseline_entries(before_result)
    trading_dates = [
        date_value
        for date_value in parent.framework.ohlcv_helper._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    trading_pos = {date_value: idx for idx, date_value in enumerate(trading_dates)}
    spy_rows = parent.framework.ohlcv_helper._series(snapshot, "SPY")
    spy_index = parent.framework.ohlcv_helper._row_index(spy_rows)
    sector_lookup, peers_by_sector, sector_coverage = _sector_peers(universe, snapshot)
    peer_universe = sorted(
        set(universe).intersection(snapshot).difference(parent.framework.EXCLUDED_TICKERS)
    )
    fundamentals = _fundamental_index(str(cfg["end"]), peer_universe)
    candidates: list[dict[str, Any]] = []
    audit: Counter[str] = Counter()
    event_count = 0
    issuer_reaction_count = 0
    characteristic_peer_relation_count = 0
    min_idx = max(
        MOVING_AVERAGE_DAYS,
        RELATIVE_STRENGTH_DAYS,
        AVG_DOLLAR_VOLUME_DAYS,
        RET60_DAYS,
        VOLATILITY_DAYS + 1,
    )

    for event_ticker in peer_universe:
        issuer_lookup = sector_lookup.get(event_ticker) or {}
        issuer_sector = _norm_sector(issuer_lookup.get("sector"))
        if not issuer_sector:
            audit["event_issuer_missing_sector"] += 1
            continue
        peer_tickers = [
            ticker
            for ticker in peers_by_sector.get(issuer_sector, [])
            if ticker != event_ticker
        ]
        if not peer_tickers:
            audit["no_same_sector_peers"] += 1
            continue

        issuer_rows = parent.framework.ohlcv_helper._series(snapshot, event_ticker)
        issuer_idx_by_date = parent.framework.ohlcv_helper._row_index(issuer_rows)
        events = parent._positive_surprise_events(event_ticker, cfg, trading_dates)
        event_count += len(events)
        for event in events:
            event_date = str(event["event_confirmed_date"])
            event_trade_pos = trading_pos.get(event_date)
            issuer_event_idx = issuer_idx_by_date.get(event_date)
            event_spy_idx = spy_index.get(event_date)
            if event_trade_pos is None or issuer_event_idx is None or event_spy_idx is None:
                audit["missing_event_ohlcv"] += 1
                continue
            if issuer_event_idx <= 0 or event_spy_idx <= 0:
                audit["missing_event_prior_close"] += 1
                continue
            if issuer_event_idx < min_idx:
                audit["issuer_insufficient_characteristic_history"] += 1
                continue

            issuer_event_return = parent.earnings_helper._close_return(
                issuer_rows,
                issuer_event_idx - 1,
                issuer_event_idx,
            )
            spy_event_return = parent.earnings_helper._close_return(
                spy_rows,
                event_spy_idx - 1,
                event_spy_idx,
            )
            issuer_close_location = parent.framework._close_location(
                issuer_rows[issuer_event_idx]
            )
            if issuer_event_return is None or spy_event_return is None:
                audit["missing_issuer_event_reaction"] += 1
                continue
            issuer_event_excess = issuer_event_return - spy_event_return
            if issuer_event_excess < MIN_ISSUER_EVENT_EXCESS_VS_SPY:
                audit["issuer_event_reaction_too_weak"] += 1
                continue
            if issuer_close_location is None or issuer_close_location < MIN_ISSUER_EVENT_CLOSE_LOCATION:
                audit["issuer_weak_close_location"] += 1
                continue
            issuer_avg_dollar_volume = parent.earnings_helper._avg_dollar_volume(
                issuer_rows,
                issuer_event_idx,
                AVG_DOLLAR_VOLUME_DAYS,
            )
            if issuer_avg_dollar_volume is None:
                audit["issuer_missing_avg_dollar_volume"] += 1
                continue
            issuer_vector = _characteristic_vector(
                ticker=event_ticker,
                signal_date=event_date,
                rows=issuer_rows,
                idx=issuer_event_idx,
                avg_dollar_volume=issuer_avg_dollar_volume,
                fundamentals=fundamentals,
            )
            issuer_reaction_count += 1

            for offset in range(RECENT_SIGNAL_DAYS_MIN, RECENT_SIGNAL_DAYS_MAX + 1):
                signal_pos = event_trade_pos + offset
                if signal_pos >= len(trading_dates):
                    audit["signal_window_out_of_range"] += 1
                    continue
                signal_date = trading_dates[signal_pos]
                spy_idx = spy_index.get(signal_date)
                if spy_idx is None or spy_idx < min_idx:
                    audit["missing_signal_spy_context"] += 1
                    continue
                spy_signal_1d = parent.earnings_helper._close_return(
                    spy_rows,
                    spy_idx - 1,
                    spy_idx,
                )
                spy_event_to_signal_return = parent.earnings_helper._close_return(
                    spy_rows,
                    event_spy_idx - 1,
                    spy_idx,
                )
                if spy_signal_1d is None or spy_event_to_signal_return is None:
                    audit["missing_spy_return_context"] += 1
                    continue

                for peer_ticker in peer_tickers:
                    peer_rows = parent.framework.ohlcv_helper._series(snapshot, peer_ticker)
                    idx_by_date = parent.framework.ohlcv_helper._row_index(peer_rows)
                    event_peer_idx = idx_by_date.get(event_date)
                    idx = idx_by_date.get(signal_date)
                    if event_peer_idx is None or idx is None:
                        audit["peer_missing_event_or_signal_date"] += 1
                        continue
                    if idx < min_idx or event_peer_idx <= 0:
                        audit["peer_insufficient_ohlcv_history"] += 1
                        continue
                    close = parent.framework.ohlcv_helper._value(peer_rows[idx], "Close")
                    volume = parent.framework.ohlcv_helper._value(peer_rows[idx], "Volume")
                    if not close or volume is None:
                        audit["peer_missing_close_or_volume"] += 1
                        continue
                    avg_dollar_volume = parent.earnings_helper._avg_dollar_volume(
                        peer_rows,
                        idx,
                        AVG_DOLLAR_VOLUME_DAYS,
                    )
                    if avg_dollar_volume is None:
                        audit["peer_missing_avg_dollar_volume"] += 1
                        continue
                    if avg_dollar_volume < MIN_AVG_DOLLAR_VOLUME_20D:
                        audit["peer_low_avg_dollar_volume"] += 1
                        continue

                    ma50 = parent.earnings_helper._prior_average(
                        peer_rows,
                        idx,
                        MOVING_AVERAGE_DAYS,
                        "Close",
                    )
                    if ma50 is None or float(close) <= ma50:
                        audit["peer_below_50d_trend"] += 1
                        continue
                    close_location = parent.framework._close_location(peer_rows[idx])
                    if close_location is None or close_location < MIN_PEER_CLOSE_LOCATION:
                        audit["peer_weak_close_location"] += 1
                        continue

                    ret20 = parent.earnings_helper._close_return(
                        peer_rows,
                        idx - RELATIVE_STRENGTH_DAYS,
                        idx,
                    )
                    spy_ret20 = parent.earnings_helper._close_return(
                        spy_rows,
                        spy_idx - RELATIVE_STRENGTH_DAYS,
                        spy_idx,
                    )
                    if ret20 is None or spy_ret20 is None:
                        audit["peer_missing_relative_strength"] += 1
                        continue
                    rs20_vs_spy = ret20 - spy_ret20
                    if rs20_vs_spy <= MIN_RS20_VS_SPY:
                        audit["peer_rs20_not_positive_vs_spy"] += 1
                        continue

                    peer_signal_return_1d = parent.earnings_helper._close_return(
                        peer_rows,
                        idx - 1,
                        idx,
                    )
                    if peer_signal_return_1d is None:
                        audit["peer_missing_signal_return"] += 1
                        continue
                    peer_signal_excess = peer_signal_return_1d - spy_signal_1d
                    if peer_signal_excess < MIN_PEER_SIGNAL_EXCESS_VS_SPY:
                        audit["peer_signal_day_too_weak"] += 1
                        continue

                    peer_event_to_signal_return = parent.earnings_helper._close_return(
                        peer_rows,
                        event_peer_idx - 1,
                        idx,
                    )
                    if peer_event_to_signal_return is None:
                        audit["peer_missing_event_to_signal_return"] += 1
                        continue
                    peer_event_to_signal_excess = (
                        peer_event_to_signal_return - spy_event_to_signal_return
                    )
                    if peer_event_to_signal_excess < MIN_PEER_EVENT_TO_SIGNAL_EXCESS_VS_SPY:
                        audit["peer_event_to_signal_excess_too_weak"] += 1
                        continue

                    peer_vector = _characteristic_vector(
                        ticker=peer_ticker,
                        signal_date=signal_date,
                        rows=peer_rows,
                        idx=idx,
                        avg_dollar_volume=avg_dollar_volume,
                        fundamentals=fundamentals,
                    )
                    similarity = _similarity(issuer_vector, peer_vector)
                    if similarity is None:
                        audit["peer_insufficient_characteristic_overlap"] += 1
                        continue
                    similarity_score = float(similarity["characteristic_similarity_score"])
                    if similarity_score < MIN_CHARACTERISTIC_SIMILARITY:
                        audit["peer_low_characteristic_similarity"] += 1
                        continue

                    ab_entries = entries_by_date.get(signal_date, [])
                    peer_lookup = sector_lookup.get(peer_ticker) or {}
                    score = (
                        (1.75 * issuer_event_excess)
                        + (2.00 * similarity_score)
                        + (1.25 * rs20_vs_spy)
                        + peer_signal_excess
                        + peer_event_to_signal_excess
                        + (float(event["latest_surprise_pct"]) / 100.0)
                        + (0.20 * close_location)
                    )
                    candidates.append(
                        {
                            "ticker": peer_ticker,
                            "date": signal_date,
                            "strategy": STEM,
                            "rule_version": RULE_VERSION,
                            "close": parent.framework.base._round(close, 4),
                            "volume": parent.framework.base._round(volume, 2),
                            "avg_dollar_volume_20d": parent.framework.base._round(
                                avg_dollar_volume,
                                2,
                            ),
                            "ma50": parent.framework.base._round(ma50, 4),
                            "close_location": parent.framework.base._round(
                                close_location,
                                6,
                            ),
                            "ret20": parent.framework.base._round(ret20, 6),
                            "spy_ret20": parent.framework.base._round(spy_ret20, 6),
                            "rs20_vs_spy": parent.framework.base._round(rs20_vs_spy, 6),
                            "peer_signal_return_1d": parent.framework.base._round(
                                peer_signal_return_1d,
                                6,
                            ),
                            "peer_signal_excess_return_1d_vs_spy": (
                                parent.framework.base._round(peer_signal_excess, 6)
                            ),
                            "peer_event_to_signal_return": parent.framework.base._round(
                                peer_event_to_signal_return,
                                6,
                            ),
                            "peer_event_to_signal_excess_vs_spy": (
                                parent.framework.base._round(
                                    peer_event_to_signal_excess,
                                    6,
                                )
                            ),
                            "event_ticker": event_ticker,
                            "event_confirmed_date": event_date,
                            "event_industry": issuer_lookup.get("industry"),
                            "event_sector": issuer_lookup.get("sector"),
                            "event_issuer_return_1d": parent.framework.base._round(
                                issuer_event_return,
                                6,
                            ),
                            "event_issuer_excess_return_1d_vs_spy": (
                                parent.framework.base._round(issuer_event_excess, 6)
                            ),
                            "event_issuer_close_location": parent.framework.base._round(
                                issuer_close_location,
                                6,
                            ),
                            "peer_industry": peer_lookup.get("industry"),
                            "peer_sector": peer_lookup.get("sector"),
                            "peer_relation_source": (
                                "same_sector_companyfacts_ohlcv_characteristic_similarity"
                            ),
                            "peer_relation_key": issuer_sector,
                            "characteristic_similarity_score": parent.framework.base._round(
                                similarity_score,
                                6,
                            ),
                            "common_characteristics": similarity[
                                "common_characteristics"
                            ],
                            "common_fundamental_characteristics": similarity[
                                "common_fundamental_characteristics"
                            ],
                            "characteristic_distance_components": similarity[
                                "characteristic_distance_components"
                            ],
                            "issuer_characteristics": _rounded_vector(issuer_vector),
                            "peer_characteristics": _rounded_vector(peer_vector),
                            "recent_signal_trading_day_offset": offset,
                            "latest_surprise_pct": parent.framework.base._round(
                                event["latest_surprise_pct"],
                                6,
                            ),
                            "avg_historical_surprise_pct": parent.framework.base._round(
                                event["avg_historical_surprise_pct"],
                                6,
                            ),
                            "historical_surprise_count": event[
                                "historical_surprise_count"
                            ],
                            "positive_historical_surprise_count": event[
                                "positive_historical_surprise_count"
                            ],
                            "eps_actual_last": parent.framework.base._round(
                                event["eps_actual_last"],
                                6,
                            ),
                            "earnings_snapshot_source_date": event[
                                "earnings_snapshot_source_date"
                            ],
                            "previous_snapshot_source_date": event[
                                "previous_snapshot_source_date"
                            ],
                            "peer_transfer_score": parent.framework.base._round(score, 6),
                            "same_day_ab_entry_count": len(ab_entries),
                            "same_day_ab_overlap": bool(ab_entries),
                            "same_ticker_ab_overlap": any(
                                trade.get("ticker") == peer_ticker for trade in ab_entries
                            ),
                            "known_at": (
                                "after_peer_signal_date_close_before_next_open_paper_entry"
                            ),
                            "trade_enabled": False,
                            "alters_orders": False,
                        }
                    )
                    characteristic_peer_relation_count += 1

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["peer_transfer_score"]),
            -float(row["characteristic_similarity_score"]),
            int(row["recent_signal_trading_day_offset"]),
            -float(row["event_issuer_excess_return_1d_vs_spy"]),
            -float(row["peer_signal_excess_return_1d_vs_spy"]),
            -float(row["peer_event_to_signal_excess_vs_spy"]),
            -float(row["rs20_vs_spy"]),
            -float(row["avg_dollar_volume_20d"]),
            row["ticker"],
        )
    )
    return candidates, {
        "dates_checked": len(trading_dates),
        "positive_surprise_event_count": event_count,
        "issuer_positive_reaction_event_count": issuer_reaction_count,
        "characteristic_peer_relation_candidate_count": (
            characteristic_peer_relation_count
        ),
        "candidate_count": len(candidates),
        "candidate_days": len({row["date"] for row in candidates}),
        "unique_candidate_tickers": len({row["ticker"] for row in candidates}),
        "unique_event_tickers": len({row["event_ticker"] for row in candidates}),
        "sector_map_source": "data/reference/broad_market_sector_map.json",
        "sector_map_coverage": sector_coverage,
        "relation_field": "same-sector PIT Companyfacts plus OHLCV characteristic similarity",
        "min_characteristic_similarity": MIN_CHARACTERISTIC_SIMILARITY,
        "min_common_characteristics": MIN_COMMON_CHARACTERISTICS,
        "min_common_fundamental_characteristics": (
            MIN_COMMON_FUNDAMENTAL_CHARACTERISTICS
        ),
        "audit_reject_counts": dict(sorted(audit.items())),
        "rule_version": RULE_VERSION,
        "earnings_snapshot_source": "data/daily/snapshots/earnings/earnings_snapshot_*.json",
    }


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    decision = (
        "positive_replay_lead_not_promoted_requires_shared_adapter_and_forward_rows"
        if gate4["passed"]
        else "rejected_post_earnings_characteristic_similarity_peer_transfer"
    )
    actual_success = 1 if gate4["passed"] else 0
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]
    prediction = {
        "success_probability": 0.24,
        "expected_ev_delta": None,
        "expected_pnl_delta": None,
        "main_failure_modes": [
            "thin_sample",
            "window_regression",
            "concentration_failed",
            "relation_noise",
        ],
        "confidence_reason": (
            "Same-sector and exact-industry peer transfer failed robustness, but "
            "the playbook identifies characteristic-similarity peer relations as "
            "the correct retry path after raw relation failures."
        ),
        "recorded_at": "2026-06-03T03:06:16+00:00",
        "brier_score": round((0.24 - actual_success) ** 2, 6),
    }
    aggregate = payload["delta_metrics"]["aggregate"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "Positive EPS-surprise issuer reactions may transfer to peers only "
                "when issuer and peer share point-in-time Companyfacts and OHLCV "
                "characteristics, reducing relation noise versus same-sector or "
                "exact-industry links."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": (
                "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
            ),
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 3,
            "nearby_prior_experiments": [
                "exp-20260602-012",
                "exp-20260602-019",
                "exp-20260531-010",
            ],
            "multiple_testing_risk_bucket": "high",
            "new_evidence_type": (
                "free_earnings_snapshot_plus_companyfacts_ohlcv_characteristic_peer_relation"
            ),
            "prediction": prediction,
            "calibration": {
                "actual_decision": decision,
                "actual_success": actual_success,
                "predicted_success_probability": prediction["success_probability"],
                "brier_score": prediction["brier_score"],
                "expected_ev_delta": prediction["expected_ev_delta"],
                "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
                "expected_pnl_delta": prediction["expected_pnl_delta"],
                "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
                "predicted_failure_modes": prediction["main_failure_modes"],
                "realized_failure_mode": None
                if gate4["passed"]
                else "; ".join(gate4["failed_reasons"]),
                "predicted_failure_mode_hit": (
                    False
                    if gate4["passed"]
                    else any(
                        token in "; ".join(gate4["failed_reasons"])
                        for token in ["window", "sample", "concentration"]
                    )
                ),
            },
            "parameters": {
                "base_universe_count": payload["parameters"]["base_universe_count"],
                "paper_notional_usd": parent.framework.base.BASE_NOTIONAL_USD,
                "hold_days": parent.framework.base.HOLD_DAYS,
                "max_paper_trades_per_day": parent.framework.MAX_PAPER_TRADES_PER_DAY,
                "recent_signal_days_min": RECENT_SIGNAL_DAYS_MIN,
                "recent_signal_days_max": RECENT_SIGNAL_DAYS_MAX,
                "min_issuer_event_excess_vs_spy": MIN_ISSUER_EVENT_EXCESS_VS_SPY,
                "min_issuer_event_close_location": MIN_ISSUER_EVENT_CLOSE_LOCATION,
                "min_peer_signal_excess_vs_spy": MIN_PEER_SIGNAL_EXCESS_VS_SPY,
                "min_peer_event_to_signal_excess_vs_spy": (
                    MIN_PEER_EVENT_TO_SIGNAL_EXCESS_VS_SPY
                ),
                "min_peer_close_location": MIN_PEER_CLOSE_LOCATION,
                "min_rs20_vs_spy": MIN_RS20_VS_SPY,
                "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
                "ret60_days": RET60_DAYS,
                "volatility_days": VOLATILITY_DAYS,
                "min_characteristic_similarity": MIN_CHARACTERISTIC_SIMILARITY,
                "min_common_characteristics": MIN_COMMON_CHARACTERISTICS,
                "min_common_fundamental_characteristics": (
                    MIN_COMMON_FUNDAMENTAL_CHARACTERISTICS
                ),
                "characteristic_components": [
                    "revenue_yoy_growth",
                    "eps_yoy_growth",
                    "operating_margin_current",
                    "liabilities_assets_ratio",
                    "ret20",
                    "ret60",
                    "realized_volatility_20d",
                    "log_avg_dollar_volume_20d",
                ],
                "locked_parent_positive_surprise_variables": {
                    "min_latest_surprise_pct": parent.MIN_LATEST_SURPRISE_PCT,
                    "min_positive_surprise_count": parent.MIN_POSITIVE_SURPRISE_COUNT,
                    "min_surprise_history_count": parent.MIN_SURPRISE_HISTORY_COUNT,
                    "min_reset_dte": parent.MIN_RESET_DTE,
                    "max_pre_reset_dte": parent.MAX_PRE_RESET_DTE,
                },
                "source_definition": [
                    "event issuer has PIT earnings snapshot transition-confirmed positive EPS surprise",
                    "issuer event-day return beats SPY by at least 1pp and closes in upper 55% of range",
                    "candidate is a different same-sector ticker",
                    "issuer and candidate share at least 5 characteristic fields and 2 fundamental fields",
                    "candidate characteristic similarity score is at least 0.55",
                    "candidate has signal-day return beating SPY by at least 0.3pp",
                    "candidate event-to-signal return beats SPY and has positive 20d RS",
                    "candidate is liquid, above prior 50d average, and close_location >= 0.55",
                    "top-1 selected paper entry per signal date",
                ],
                "acceptance": payload["parameters"]["acceptance"],
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "candidate_pool / entry: positive earnings-surprise reactions "
                    "may transfer to peers only when the peer is fundamentally and "
                    "technically similar enough to the issuer."
                ),
                "2_history_check": {
                    "exp-20260602-012": (
                        "Exact-industry post-earnings peer transfer failed "
                        "robustness and sample/concentration gates."
                    ),
                    "exp-20260602-019": (
                        "Same-sector post-earnings peer transfer regressed old_thin "
                        "and showed relation noise."
                    ),
                    "exp-20260531-010": (
                        "SEC Item 2.02 characteristic similarity failed; this run "
                        "uses confirmed positive EPS surprise plus issuer reaction, "
                        "not SEC filing events alone."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same three docs/backtesting.md windows; positive aggregate "
                    "EV/PnL; 3/3 EV-improved windows; no PnL-regressed window; "
                    ">=20 paper trades across all 3 windows; drawdown drift <=0.5pp; "
                    "survival >=5%; concentration inside guardrails."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260603_005_post_earnings_characteristic_similarity_peer_transfer.py"
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay-safe soft-ranking rows are "
                "still insufficient. Skipped Companyfacts source/provenance retunes, "
                "FINRA, VBB, consensus, Space, and state-surface scalar retunes "
                "because the current playbook requires materially new forward rows "
                "or fields before retrying those families. This tests a distinct "
                "free-data relation-construction field."
            ),
            "production_parity": {
                "alters_production_orders": False,
                "alters_live_watchlists": False,
                "alters_core_backtester": False,
                "default_enabled": False,
                "replay_only": True,
                "parity_note": (
                    "No production code path is changed. A future promotion would "
                    "need the exact relation field moved into a shared default-off "
                    "adapter using the same earnings snapshot, sector-map, "
                    "Companyfacts, and OHLCV inputs available to production before "
                    "next-open paper entry."
                ),
            },
            "production_impact": {
                "shared_policy_changed": False,
                "backtester_adapter_changed": False,
                "run_adapter_changed": False,
                "replay_only": True,
                "parity_test_added": False,
                "live_orders_changed": False,
            },
            "interpretation": (
                "The post-earnings characteristic-similarity peer-transfer source "
                "cleared Gate 4 as a replay lead, but no shared adapter was promoted."
                if gate4["passed"]
                else (
                    "The post-earnings characteristic-similarity peer-transfer source "
                    "did not clear Gate 4. Do not promote it or retry nearby peer "
                    "relation thresholds on these frozen windows without forward "
                    "rows or a stronger relation source."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "next_evidence_needed": (
                "Forward replacement-value rows or a stronger peer relation source "
                "such as audited customer/supplier links, source overlap, or "
                "multi-season early-peer earnings transfer evidence."
            ),
            "related_files": [
                "quant/experiments/exp_20260603_005_post_earnings_characteristic_similarity_peer_transfer.py",
                "data/experiments/exp-20260603-005/exp_20260603_005_post_earnings_characteristic_similarity_peer_transfer.json",
                "data/experiments/exp-20260603-005/post_earnings_characteristic_similarity_peer_transfer_before_aggregate.json",
                "data/experiments/exp-20260603-005/post_earnings_characteristic_similarity_peer_transfer_after_aggregate.json",
                "experiments/logs/exp-20260603-005.json",
                "experiments/tickets/exp-20260603-005.json",
                "experiments/artifacts/exp-20260603-005_post_earnings_characteristic_similarity_peer_transfer.md",
                "docs/experiment_log.jsonl",
            ],
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Issuer event confirmation is derived from canonical daily earnings "
        "snapshot transitions. Issuer and peer OHLCV are observed through the "
        "peer signal-date close; Companyfacts contexts are max_filed at the "
        "window end and queried by signal date; paper entry is next open and "
        "exit is ten trading days after signal."
    )
    payload["gate2"]["runtime_field_coverage"] = {
        "earnings_snapshots": {
            "source": "data/daily/snapshots/earnings/earnings_snapshot_*.json",
            "snapshots_loaded": parent.earnings_helper._EARNINGS_DATE_COUNT,
            "required_fields": [
                "days_to_earnings",
                "eps_actual_last",
                "historical_surprise_pct",
                "avg_historical_surprise_pct",
            ],
            "tickers_with_snapshot_rows": len(parent.earnings_helper._load_earnings_index()),
        },
        "peer_relation": {
            "source": "data/reference/broad_market_sector_map.json + data/sec/companyfacts",
            "required_fields": [
                "sector",
                "revenue_yoy_growth",
                "eps_yoy_growth",
                "operating_margin_current",
                "liabilities_assets_ratio",
                "ret20",
                "ret60",
                "realized_volatility_20d",
                "avg_dollar_volume_20d",
            ],
            "relation": "same-sector PIT Companyfacts plus OHLCV characteristic similarity",
        },
        "ohlcv": {
            "required_fields": [
                "issuer event-day OHLCV",
                "peer signal-day OHLCV",
                "SPY event and signal-day OHLCV",
            ],
            "decision_time": "known after peer signal-day close before next-open paper entry",
        },
    }
    payload["gate2"]["target_trade_field_coverage"] = parent.framework._field_coverage(
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
            "event_ticker",
            "event_confirmed_date",
            "event_sector",
            "peer_sector",
            "latest_surprise_pct",
            "eps_actual_last",
            "event_issuer_excess_return_1d_vs_spy",
            "peer_signal_excess_return_1d_vs_spy",
            "peer_event_to_signal_excess_vs_spy",
            "characteristic_similarity_score",
            "common_characteristics",
            "common_fundamental_characteristics",
            "rs20_vs_spy",
            "avg_dollar_volume_20d",
        ],
    )
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Events | Issuer reactions | Characteristic candidates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in parent.framework.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["candidate_audits"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {events} | {reactions} | {raw} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                events=audit.get("positive_surprise_event_count", 0),
                reactions=audit.get("issuer_positive_reaction_event_count", 0),
                raw=audit.get("characteristic_peer_relation_candidate_count", 0),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    return "\n".join(
        [
            "# exp-20260603-005 Post-Earnings Characteristic Similarity Peer Transfer",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: same-sector Companyfacts/OHLCV characteristic-similarity peer-transfer candidate source after a confirmed positive EPS-surprise issuer reaction.",
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
    base = parent.framework.base
    base._write_json(OUT_JSON, payload)
    base._write_json(BEFORE_AGG_JSON, payload["judge_before_aggregate"])
    base._write_json(AFTER_AGG_JSON, payload["judge_after_aggregate"])
    base._write_json(LOG_JSON, payload)
    ticket_payload: dict[str, Any] = {}
    if TICKET_JSON.exists():
        ticket_payload = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
    ticket_payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Post-earnings characteristic-similarity peer transfer",
            "status": payload["status"],
            "decision": payload["decision"],
            "completed_at": payload["timestamp"],
            "artifact": base._repo_rel(ARTIFACT_MD),
            "json": base._repo_rel(OUT_JSON),
            "before_aggregate": base._repo_rel(BEFORE_AGG_JSON),
            "after_aggregate": base._repo_rel(AFTER_AGG_JSON),
            "result": {
                "decision": payload["decision"],
                "gate4": payload["gate4"],
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "total_pnl_delta": payload["total_pnl_delta"],
                "target_trade_summary": payload["target_trade_summary"],
            },
            "summary": payload["interpretation"],
        }
    )
    base._write_json(TICKET_JSON, ticket_payload)
    base._write_text(ARTIFACT_MD, _build_report(payload))
    base._write_text(CARD_MD, _build_report(payload))
    base._upsert_jsonl(EXPERIMENT_LOG, payload)
    _write_manifest()


def _write_manifest() -> None:
    base = parent.framework.base
    files = {
        "runner": base._repo_rel(Path(__file__)),
        "result": base._repo_rel(OUT_JSON),
        "before_aggregate": base._repo_rel(BEFORE_AGG_JSON),
        "after_aggregate": base._repo_rel(AFTER_AGG_JSON),
        "log": base._repo_rel(LOG_JSON),
        "ticket": base._repo_rel(TICKET_JSON),
        "card": base._repo_rel(CARD_MD),
        "artifact": base._repo_rel(ARTIFACT_MD),
        "manifest": base._repo_rel(MANIFEST_JSON),
        "experiment_log": base._repo_rel(EXPERIMENT_LOG),
    }
    manifest = {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": {
            label: {
                "path": rel_path,
                "exists": (REPO_ROOT / rel_path).exists(),
                "sha256": _sha256(REPO_ROOT / rel_path),
            }
            for label, rel_path in files.items()
        },
    }
    base._write_json(MANIFEST_JSON, manifest)


def main() -> int:
    _patch_parent()
    payload = _postprocess_payload(parent.framework._build_payload())
    _persist(payload)
    print(
        json.dumps(
            parent.framework.base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
                    "artifact": parent.framework.base._repo_rel(ARTIFACT_MD),
                    "before_aggregate": parent.framework.base._repo_rel(BEFORE_AGG_JSON),
                    "after_aggregate": parent.framework.base._repo_rel(AFTER_AGG_JSON),
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
