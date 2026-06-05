"""exp-20260605-024: lagged-consensus characteristic peer transfer.

Replay-only alpha search. The accepted lagged free-data consensus surface is
kept fixed as the before comparator. This experiment adds one candidate source:
liquid same-sector peers of lagged-independent source trades, admitted only when
the peer is characteristic-similar on point-in-time Companyfacts/OHLCV fields
and shows independent signal-day strength.

No production code, shared adapter, live orders, ranking, sizing, exits, source
artifacts, source-family maps, notional, hold period, or cooldown is changed.
No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = REPO_ROOT / "quant" / "experiments"
QUANT_DIR = REPO_ROOT / "quant"
for import_path in (REPO_ROOT, EXPERIMENTS_DIR, QUANT_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260604_008_lagged_independent_source_consensus as lagged  # noqa: E402
from broad_market_sector_map import DEFAULT_CACHE_PATH, load_cache, lookup_sector  # noqa: E402
from fundamental_growth_rs_paper_sleeve import (  # noqa: E402
    CompanyfactsFundamentalIndex,
    DEFAULT_CONFIG as FUNDAMENTAL_CONFIG,
    load_companyfacts_rows,
)


same_day = lagged.same_day

EXPERIMENT_ID = "exp-20260605-024"
STEM = "lagged_consensus_characteristic_peer_transfer"
TRIAL_FAMILY = "accepted_lagged_consensus_characteristic_peer_transfer"
TRIAL_VARIANT_ID = "lagged_consensus_characteristic_peer_transfer_v1"
CHANGED_VARIABLE = (
    "accepted_lagged_consensus_characteristic_similarity_peer_transfer_candidate_source_v1"
)
RULE_VERSION = "lagged_consensus_characteristic_peer_transfer_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260605_024_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

SOURCE_COMPARATOR_ID = "exp-20260604-009"
SOURCE_REPLAY_ID = "exp-20260604-008"
ACCEPTED_REPLAY_JSON = (
    REPO_ROOT / "data" / "experiments" / SOURCE_REPLAY_ID / "lagged_independent_source_consensus.json"
)

PEER_SIGNAL_OFFSET_MIN = 1
PEER_SIGNAL_OFFSET_MAX = 3
MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_PEER_SIGNAL_EXCESS_VS_SPY = 0.003
MIN_PEER_SOURCE_TO_SIGNAL_EXCESS_VS_SPY = 0.0
MIN_PEER_CLOSE_LOCATION = 0.55
MIN_RS20_VS_SPY = 0.0
MIN_CHARACTERISTIC_SIMILARITY = 0.55
MIN_COMMON_CHARACTERISTICS = 5
MIN_COMMON_FUNDAMENTAL_CHARACTERISTICS = 2
MOVING_AVERAGE_DAYS = 50
RELATIVE_STRENGTH_DAYS = 20
RET60_DAYS = 60
VOLATILITY_DAYS = 20
AVG_DOLLAR_VOLUME_DAYS = 20
MIN_INCREMENTAL_PEER_TRADES = 20
MIN_INCREMENTAL_WINDOWS = 3

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "peer_relation_noise",
        "open_slot_sample_too_thin",
        "accepted_lagged_comparator_not_improved",
        "window_regression",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Prior same-sector and post-earnings peer transfer failed, but accepted "
        "lagged consensus is the strongest current free-data source. This tests "
        "a different relation construction with open-slot incremental selection."
    ),
    "recorded_at": "2026-06-05T16:06:33Z",
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
    "production_watchlist_changed": False,
    "production_orders_changed": False,
    "parity_note": (
        "This experiment changes no production code. If accepted, promotion "
        "would require a shared default-off adapter using the same lagged "
        "source rows, sector map, Companyfacts contexts, OHLCV features, "
        "open-slot selection rules, and next-open paper-entry timing in both "
        "historical replay and daily production before any report queue, paper "
        "notional, candidate priority, or order surface could change."
    ),
}

_FUNDAMENTAL_INDEX_CACHE: dict[
    tuple[str, tuple[str, ...]],
    CompanyfactsFundamentalIndex,
] = {}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(_safe(payload), handle, ensure_ascii=True, indent=2, sort_keys=True)
        handle.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sha256(path: Path) -> str | None:
    if not path.exists() or path.is_dir():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _safe(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {str(key): _safe(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_safe(value) for value in payload]
    if isinstance(payload, tuple):
        return [_safe(value) for value in payload]
    if isinstance(payload, Counter):
        return dict(payload)
    if isinstance(payload, Path):
        return str(payload)
    if isinstance(payload, float):
        if math.isnan(payload) or math.isinf(payload):
            return None
        return round(payload, 10)
    return payload


def _round(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    number = _safe_float(value, default=float("nan"))
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _configure_modules() -> None:
    lagged._configure_same_day_modules()
    base = same_day.prior.base
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = RULE_VERSION
    base.BASE_NOTIONAL_USD = same_day.prior.BASE_NOTIONAL_USD
    base.HOLD_DAYS = same_day.prior.HOLD_DAYS
    base.MAX_PAPER_TRADES_PER_DAY = same_day.prior.MAX_PAPER_TRADES_PER_DAY
    base.MIN_TARGET_TRADES = same_day.prior.MIN_TARGET_TRADES
    base.MIN_TARGET_WINDOWS = same_day.prior.MIN_TARGET_WINDOWS
    base.MAX_DRAWDOWN_WORSE = same_day.prior.MAX_DRAWDOWN_WORSE
    base.MAX_SINGLE_POSITIVE_SHARE = same_day.prior.MAX_SINGLE_POSITIVE_SHARE
    base.MAX_POSITIVE_HHI = same_day.prior.MAX_POSITIVE_HHI


def _series(snapshot: dict[str, Any], ticker: str) -> list[dict[str, Any]]:
    return same_day.prior.base.shadow._series(snapshot, ticker)


def _row_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return same_day.prior.base.shadow._row_index(rows)


def _trading_dates(snapshot: dict[str, Any]) -> list[str]:
    return same_day.prior.base.shadow._trading_dates(snapshot)


def _value(row: dict[str, Any], key: str) -> float | None:
    value = same_day.prior.base.shadow._value(row, key)
    if value is None:
        value = same_day.prior.base.shadow._value(row, key.lower())
    if value is None:
        return None
    number = _safe_float(value, default=float("nan"))
    if not math.isfinite(number):
        return None
    return number


def _close_return(rows: list[dict[str, Any]], start_idx: int, end_idx: int) -> float | None:
    if start_idx < 0 or end_idx >= len(rows):
        return None
    start_close = _value(rows[start_idx], "Close")
    end_close = _value(rows[end_idx], "Close")
    if not start_close or end_close is None:
        return None
    return (float(end_close) / float(start_close)) - 1.0


def _prior_average(rows: list[dict[str, Any]], idx: int, days: int, key: str) -> float | None:
    if idx < days:
        return None
    values = [_value(row, key) for row in rows[idx - days : idx]]
    clean = [float(value) for value in values if value is not None]
    if len(clean) < days:
        return None
    return sum(clean) / len(clean)


def _avg_dollar_volume(rows: list[dict[str, Any]], idx: int, days: int) -> float | None:
    start = idx - days + 1
    if start < 0:
        return None
    values: list[float] = []
    for row in rows[start : idx + 1]:
        close = _value(row, "Close")
        volume = _value(row, "Volume")
        if close is None or volume is None:
            return None
        values.append(float(close) * float(volume))
    return sum(values) / len(values) if len(values) == days else None


def _realized_volatility(rows: list[dict[str, Any]], idx: int, days: int) -> float | None:
    if idx < days:
        return None
    values: list[float] = []
    for cursor in range(idx - days + 1, idx + 1):
        daily_return = _close_return(rows, cursor - 1, cursor)
        if daily_return is None:
            return None
        values.append(daily_return)
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(max(variance, 0.0))


def _close_location(row: dict[str, Any]) -> float | None:
    high = _value(row, "High")
    low = _value(row, "Low")
    close = _value(row, "Close")
    if high is None or low is None or close is None:
        return None
    if high <= low:
        return 0.5
    return (close - low) / (high - low)


def _norm_sector(value: Any) -> str:
    return str(value or "").strip().lower()


def _sector_peers(
    universe: list[str],
    snapshot: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]], dict[str, Any]]:
    cache = load_cache(DEFAULT_CACHE_PATH)
    excluded = set(same_day.prior.base.shadow.EXCLUDED_TICKERS)
    candidate_universe = sorted(set(universe).intersection(snapshot).difference(excluded))
    lookups: dict[str, dict[str, Any]] = {}
    by_sector: dict[str, list[str]] = defaultdict(list)
    for ticker in candidate_universe:
        lookup = lookup_sector(ticker, cache)
        lookups[ticker] = lookup
        if lookup.get("status") != "ok":
            continue
        sector = _norm_sector(lookup.get("sector"))
        if sector:
            by_sector[sector].append(ticker)
    return lookups, by_sector, {
        "cache_path": _repo_rel(DEFAULT_CACHE_PATH),
        "cache_generated_at": cache.get("generated_at"),
        "candidate_universe": len(candidate_universe),
        "tickers_with_lookup": len(lookups),
        "ok_lookup_count": sum(1 for row in lookups.values() if row.get("status") == "ok"),
        "sector_count": len(by_sector),
    }


def _fundamental_index(max_filed: str, tickers: list[str]) -> CompanyfactsFundamentalIndex:
    key = (max_filed, tuple(sorted(set(tickers))))
    cached = _FUNDAMENTAL_INDEX_CACHE.get(key)
    if cached is not None:
        return cached
    rows = load_companyfacts_rows(max_filed=max_filed, tickers=list(key[1]))
    index = CompanyfactsFundamentalIndex(rows, config=dict(FUNDAMENTAL_CONFIG))
    _FUNDAMENTAL_INDEX_CACHE[key] = index
    return index


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    number = _safe_float(value, default=float("nan"))
    return number if math.isfinite(number) else None


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
    ret20 = _close_return(rows, idx - RELATIVE_STRENGTH_DAYS, idx)
    ret60 = _close_return(rows, idx - RET60_DAYS, idx)
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
    return {key: _round(value, 6) for key, value in sorted(vector.items())}


def _similarity(
    source: dict[str, float | None],
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
        left = source.get(key)
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
            key: _round(value, 6) for key, value in sorted(distances.items())
        },
    }


def _source_quality_score(source_trade: dict[str, Any]) -> float:
    family_count = int(source_trade.get("source_family_count") or 0)
    source_count = int(source_trade.get("source_count") or 0)
    lagged_bonus = 1.0 if source_trade.get("has_lagged_independent_confirmation") else 0.0
    return (0.35 * family_count) + (0.12 * source_count) + (0.50 * lagged_bonus)


def _peer_candidates_for_window(
    *,
    label: str,
    snapshot: dict[str, Any],
    cfg: dict[str, str],
    accepted_trades: list[dict[str, Any]],
    universe: list[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    trading_dates = [
        date_value
        for date_value in _trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    trading_pos = {date_value: idx for idx, date_value in enumerate(trading_dates)}
    spy_rows = _series(snapshot, "SPY")
    spy_index = _row_index(spy_rows)
    sector_lookup, peers_by_sector, sector_coverage = _sector_peers(universe, snapshot)
    peer_universe = sorted(
        set(universe).intersection(snapshot).difference(same_day.prior.base.shadow.EXCLUDED_TICKERS)
    )
    fundamentals = _fundamental_index(str(cfg["end"]), peer_universe)
    lagged_source_trades = [
        row for row in accepted_trades if row.get("has_lagged_independent_confirmation")
    ]
    accepted_keys = {
        (str(row.get("signal_date") or row.get("date") or ""), str(row.get("ticker") or ""))
        for row in accepted_trades
    }
    candidates: list[dict[str, Any]] = []
    audit: Counter[str] = Counter()
    min_idx = max(
        MOVING_AVERAGE_DAYS,
        RELATIVE_STRENGTH_DAYS,
        RET60_DAYS,
        VOLATILITY_DAYS + 1,
        AVG_DOLLAR_VOLUME_DAYS,
    )

    for source_trade in lagged_source_trades:
        source_ticker = str(source_trade.get("ticker") or "").upper()
        source_date = str(source_trade.get("signal_date") or source_trade.get("date") or "")[:10]
        source_pos = trading_pos.get(source_date)
        if source_pos is None:
            audit["source_date_outside_window"] += 1
            continue
        source_lookup = sector_lookup.get(source_ticker) or {}
        source_sector = _norm_sector(source_lookup.get("sector"))
        if not source_sector:
            audit["source_missing_sector"] += 1
            continue
        peer_tickers = [ticker for ticker in peers_by_sector.get(source_sector, []) if ticker != source_ticker]
        if not peer_tickers:
            audit["source_no_same_sector_peers"] += 1
            continue
        source_rows = _series(snapshot, source_ticker)
        source_idx = _row_index(source_rows).get(source_date)
        source_spy_idx = spy_index.get(source_date)
        if source_idx is None or source_spy_idx is None or source_idx < min_idx or source_spy_idx <= 0:
            audit["source_insufficient_ohlcv_context"] += 1
            continue
        source_adv = _avg_dollar_volume(source_rows, source_idx, AVG_DOLLAR_VOLUME_DAYS)
        if source_adv is None:
            audit["source_missing_avg_dollar_volume"] += 1
            continue
        source_vector = _characteristic_vector(
            ticker=source_ticker,
            signal_date=source_date,
            rows=source_rows,
            idx=source_idx,
            avg_dollar_volume=source_adv,
            fundamentals=fundamentals,
        )
        source_signal_return = _close_return(source_rows, source_idx - 1, source_idx)
        spy_source_return = _close_return(spy_rows, source_spy_idx - 1, source_spy_idx)
        source_signal_excess = (
            None
            if source_signal_return is None or spy_source_return is None
            else source_signal_return - spy_source_return
        )

        for offset in range(PEER_SIGNAL_OFFSET_MIN, PEER_SIGNAL_OFFSET_MAX + 1):
            signal_pos = source_pos + offset
            if signal_pos >= len(trading_dates):
                audit["peer_signal_window_out_of_range"] += 1
                continue
            signal_date = trading_dates[signal_pos]
            spy_idx = spy_index.get(signal_date)
            if spy_idx is None or spy_idx < min_idx:
                audit["missing_spy_signal_context"] += 1
                continue
            spy_signal_1d = _close_return(spy_rows, spy_idx - 1, spy_idx)
            spy_source_to_signal = _close_return(spy_rows, source_spy_idx, spy_idx)
            if spy_signal_1d is None or spy_source_to_signal is None:
                audit["missing_spy_return_context"] += 1
                continue

            for peer_ticker in peer_tickers:
                if (signal_date, peer_ticker) in accepted_keys:
                    audit["peer_already_accepted_lagged_trade_same_day"] += 1
                    continue
                peer_rows = _series(snapshot, peer_ticker)
                peer_index = _row_index(peer_rows)
                source_peer_idx = peer_index.get(source_date)
                peer_idx = peer_index.get(signal_date)
                if source_peer_idx is None or peer_idx is None:
                    audit["peer_missing_source_or_signal_date"] += 1
                    continue
                if peer_idx < min_idx or source_peer_idx <= 0:
                    audit["peer_insufficient_ohlcv_history"] += 1
                    continue
                close = _value(peer_rows[peer_idx], "Close")
                volume = _value(peer_rows[peer_idx], "Volume")
                if close is None or volume is None:
                    audit["peer_missing_close_or_volume"] += 1
                    continue
                if float(close) < MIN_PRICE:
                    audit["peer_below_price_floor"] += 1
                    continue
                avg_dollar_volume = _avg_dollar_volume(
                    peer_rows,
                    peer_idx,
                    AVG_DOLLAR_VOLUME_DAYS,
                )
                if avg_dollar_volume is None:
                    audit["peer_missing_avg_dollar_volume"] += 1
                    continue
                if avg_dollar_volume < MIN_AVG_DOLLAR_VOLUME_20D:
                    audit["peer_low_avg_dollar_volume"] += 1
                    continue
                ma50 = _prior_average(peer_rows, peer_idx, MOVING_AVERAGE_DAYS, "Close")
                if ma50 is None or float(close) <= ma50:
                    audit["peer_below_50d_trend"] += 1
                    continue
                close_location = _close_location(peer_rows[peer_idx])
                if close_location is None or close_location < MIN_PEER_CLOSE_LOCATION:
                    audit["peer_weak_close_location"] += 1
                    continue
                ret20 = _close_return(peer_rows, peer_idx - RELATIVE_STRENGTH_DAYS, peer_idx)
                spy_ret20 = _close_return(spy_rows, spy_idx - RELATIVE_STRENGTH_DAYS, spy_idx)
                if ret20 is None or spy_ret20 is None:
                    audit["peer_missing_relative_strength"] += 1
                    continue
                rs20_vs_spy = ret20 - spy_ret20
                if rs20_vs_spy <= MIN_RS20_VS_SPY:
                    audit["peer_rs20_not_positive_vs_spy"] += 1
                    continue
                peer_signal_return_1d = _close_return(peer_rows, peer_idx - 1, peer_idx)
                if peer_signal_return_1d is None:
                    audit["peer_missing_signal_return"] += 1
                    continue
                peer_signal_excess = peer_signal_return_1d - spy_signal_1d
                if peer_signal_excess < MIN_PEER_SIGNAL_EXCESS_VS_SPY:
                    audit["peer_signal_day_too_weak"] += 1
                    continue
                peer_source_to_signal_return = _close_return(peer_rows, source_peer_idx, peer_idx)
                if peer_source_to_signal_return is None:
                    audit["peer_missing_source_to_signal_return"] += 1
                    continue
                peer_source_to_signal_excess = peer_source_to_signal_return - spy_source_to_signal
                if peer_source_to_signal_excess < MIN_PEER_SOURCE_TO_SIGNAL_EXCESS_VS_SPY:
                    audit["peer_source_to_signal_excess_too_weak"] += 1
                    continue

                peer_vector = _characteristic_vector(
                    ticker=peer_ticker,
                    signal_date=signal_date,
                    rows=peer_rows,
                    idx=peer_idx,
                    avg_dollar_volume=avg_dollar_volume,
                    fundamentals=fundamentals,
                )
                similarity = _similarity(source_vector, peer_vector)
                if similarity is None:
                    audit["peer_insufficient_characteristic_overlap"] += 1
                    continue
                similarity_score = float(similarity["characteristic_similarity_score"])
                if similarity_score < MIN_CHARACTERISTIC_SIMILARITY:
                    audit["peer_low_characteristic_similarity"] += 1
                    continue

                peer_lookup = sector_lookup.get(peer_ticker) or {}
                source_quality = _source_quality_score(source_trade)
                selection_score = (
                    (2.00 * similarity_score)
                    + (1.50 * peer_signal_excess)
                    + (0.80 * peer_source_to_signal_excess)
                    + (1.00 * rs20_vs_spy)
                    + (0.20 * close_location)
                    + (0.10 * math.log(max(avg_dollar_volume, 1.0)))
                    + (0.20 * source_quality)
                )
                candidates.append(
                    {
                        "ticker": peer_ticker,
                        "date": signal_date,
                        "strategy": "paper_candidate_pool_default_off",
                        "rule_version": RULE_VERSION,
                        "candidate_source_type": "lagged_consensus_characteristic_peer_transfer",
                        "source_ticker": source_ticker,
                        "source_signal_date": source_date,
                        "source_sector": source_lookup.get("sector"),
                        "source_industry": source_lookup.get("industry"),
                        "peer_sector": peer_lookup.get("sector"),
                        "peer_industry": peer_lookup.get("industry"),
                        "peer_relation_source": (
                            "lagged_consensus_same_sector_companyfacts_ohlcv_characteristic_similarity"
                        ),
                        "peer_relation_key": source_sector,
                        "peer_signal_trading_day_offset": offset,
                        "close": _round(close, 4),
                        "volume": _round(volume, 2),
                        "avg_dollar_volume_20d": _round(avg_dollar_volume, 2),
                        "ma50": _round(ma50, 4),
                        "close_location": _round(close_location, 6),
                        "ret20": _round(ret20, 6),
                        "spy_ret20": _round(spy_ret20, 6),
                        "rs20_vs_spy": _round(rs20_vs_spy, 6),
                        "peer_signal_return_1d": _round(peer_signal_return_1d, 6),
                        "peer_signal_excess_return_1d_vs_spy": _round(
                            peer_signal_excess,
                            6,
                        ),
                        "peer_source_to_signal_return": _round(
                            peer_source_to_signal_return,
                            6,
                        ),
                        "peer_source_to_signal_excess_vs_spy": _round(
                            peer_source_to_signal_excess,
                            6,
                        ),
                        "source_signal_return_1d": _round(source_signal_return, 6),
                        "source_signal_excess_return_1d_vs_spy": _round(
                            source_signal_excess,
                            6,
                        ),
                        "source_quality_score": _round(source_quality, 6),
                        "characteristic_similarity_score": _round(similarity_score, 6),
                        "common_characteristics": similarity["common_characteristics"],
                        "common_fundamental_characteristics": similarity[
                            "common_fundamental_characteristics"
                        ],
                        "characteristic_distance_components": similarity[
                            "characteristic_distance_components"
                        ],
                        "source_characteristics": _rounded_vector(source_vector),
                        "peer_characteristics": _rounded_vector(peer_vector),
                        "source_names": source_trade.get("source_names") or [],
                        "source_families": source_trade.get("source_families") or [],
                        "source_family_count": source_trade.get("source_family_count") or 0,
                        "source_count": source_trade.get("source_count") or 0,
                        "source_experiment_ids": source_trade.get("source_experiment_ids") or {},
                        "source_rows": source_trade.get("source_rows") or [],
                        "source_agreement_rule": (
                            "peer_transfer_from_selected_lagged_independent_consensus_trade"
                        ),
                        "source_trade_pnl": source_trade.get("pnl"),
                        "source_trade_entry_date": source_trade.get("entry_date"),
                        "source_trade_exit_date": source_trade.get("exit_date"),
                        "source_trade_has_lagged_independent_confirmation": True,
                        "candidate_selection_score": _round(selection_score, 6),
                        "known_at": f"{signal_date}T21:00:00Z",
                        "trade_enabled": False,
                        "alters_orders": False,
                    }
                )
                audit["characteristic_peer_relation_candidate_count"] += 1

    candidates.sort(
        key=lambda row: (
            str(row["date"]),
            -float(row.get("candidate_selection_score") or 0.0),
            -float(row.get("characteristic_similarity_score") or 0.0),
            int(row.get("peer_signal_trading_day_offset") or 99),
            -float(row.get("peer_signal_excess_return_1d_vs_spy") or 0.0),
            -float(row.get("peer_source_to_signal_excess_vs_spy") or 0.0),
            -float(row.get("rs20_vs_spy") or 0.0),
            -float(row.get("avg_dollar_volume_20d") or 0.0),
            str(row["ticker"]),
        )
    )
    return candidates, {
        "lagged_source_trade_count": len(accepted_trades),
        "lagged_independent_source_trade_count": len(lagged_source_trades),
        "candidate_count": len(candidates),
        "candidate_days": len({row["date"] for row in candidates}),
        "unique_candidate_tickers": len({row["ticker"] for row in candidates}),
        "unique_source_tickers": len({row["source_ticker"] for row in candidates}),
        "sector_map_source": _repo_rel(DEFAULT_CACHE_PATH),
        "sector_map_coverage": sector_coverage,
        "relation_field": (
            "same-sector PIT Companyfacts plus OHLCV characteristic similarity "
            "from selected lagged-independent consensus source rows"
        ),
        "peer_signal_offset_min": PEER_SIGNAL_OFFSET_MIN,
        "peer_signal_offset_max": PEER_SIGNAL_OFFSET_MAX,
        "min_characteristic_similarity": MIN_CHARACTERISTIC_SIMILARITY,
        "min_common_characteristics": MIN_COMMON_CHARACTERISTICS,
        "min_common_fundamental_characteristics": MIN_COMMON_FUNDAMENTAL_CHARACTERISTICS,
        "audit_reject_counts": dict(sorted(audit.items())),
        "rule_version": RULE_VERSION,
    }


def _select_incremental_peer_trades(
    snapshot: dict[str, Any],
    candidates: list[dict[str, Any]],
    existing_trades: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    selected_keys = {
        (str(row.get("signal_date") or row.get("date") or ""), str(row.get("ticker") or ""))
        for row in existing_trades
    }
    selected_per_day: Counter[str] = Counter(
        str(row.get("signal_date") or row.get("date") or "") for row in existing_trades
    )
    last_admitted_by_ticker: dict[str, date] = {}
    for row in existing_trades:
        signal_date = str(row.get("signal_date") or row.get("date") or "")[:10]
        ticker = str(row.get("ticker") or "")
        if signal_date and ticker:
            parsed = date.fromisoformat(signal_date)
            current = last_admitted_by_ticker.get(ticker)
            if current is None or parsed > current:
                last_admitted_by_ticker[ticker] = parsed

    rejection_counts: Counter[str] = Counter()
    for candidate in candidates:
        signal_date = str(candidate["date"])
        ticker = str(candidate["ticker"])
        key = (signal_date, ticker)
        if key in selected_keys:
            rejection_counts["duplicate_existing_or_peer_same_day_ticker"] += 1
            continue
        if selected_per_day[signal_date] >= same_day.prior.MAX_PAPER_TRADES_PER_DAY:
            rejection_counts["daily_trade_cap_after_accepted_lagged_prefill"] += 1
            continue
        parsed_date = date.fromisoformat(signal_date)
        last_date = last_admitted_by_ticker.get(ticker)
        if (
            last_date is not None
            and (parsed_date - last_date).days < same_day.prior.SAME_TICKER_COOLDOWN_DAYS
        ):
            rejection_counts["same_ticker_cooldown_after_accepted_lagged_prefill"] += 1
            continue

        trade = same_day.prior.base._paper_trade_from_candidate(snapshot, candidate)
        if trade is None:
            rejection_counts["missing_ohlcv_or_invalid_exit"] += 1
            continue
        trade.update(
            {
                "paper_pnl": trade.get("pnl"),
                "paper_notional_usd": same_day.prior.BASE_NOTIONAL_USD,
                "hold_days": same_day.prior.HOLD_DAYS,
                "same_ticker_cooldown_days": same_day.prior.SAME_TICKER_COOLDOWN_DAYS,
                "trade_enabled": False,
                "alters_orders": False,
                "rule_version": RULE_VERSION,
                "strategy": "paper_candidate_pool_default_off",
            }
        )
        selected.append(trade)
        selected_keys.add(key)
        selected_per_day[signal_date] += 1
        last_admitted_by_ticker[ticker] = parsed_date

    return selected, {
        "raw_peer_candidates": len(candidates),
        "selected_incremental_peer_trades": len(selected),
        "rejection_counts": dict(sorted(rejection_counts.items())),
        "selected_peer_trade_dates": sorted({str(row.get("signal_date")) for row in selected}),
        "selected_peer_source_tickers": dict(
            sorted(Counter(str(row.get("source_ticker") or "") for row in selected).items())
        ),
        "selected_peer_relation_sector_counts": dict(
            sorted(Counter(str(row.get("peer_sector") or "") for row in selected).items())
        ),
    }


def _run_peer_windows(
    baselines: dict[str, dict[str, Any]],
    accepted_results: list[dict[str, Any]],
    accepted_trades_by_window: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    accepted_by_label = {row["label"]: row for row in accepted_results}
    results: list[dict[str, Any]] = []
    peer_trades_by_window: dict[str, list[dict[str, Any]]] = {}
    candidate_audits: dict[str, Any] = {}
    universe = sorted(same_day.prior.base.get_universe())

    for label, cfg in same_day.prior.base.WINDOWS.items():
        snapshot = same_day.prior.base.shadow._load_snapshot(cfg["snapshot"])
        accepted_trades = accepted_trades_by_window[label]
        candidates, candidate_audit = _peer_candidates_for_window(
            label=label,
            snapshot=snapshot,
            cfg=cfg,
            accepted_trades=accepted_trades,
            universe=universe,
        )
        peer_trades, target_diagnostics = _select_incremental_peer_trades(
            snapshot,
            candidates,
            accepted_trades,
        )
        before_result = baselines[label]["result"]
        accepted_before = accepted_by_label[label]["after"]
        combined_trades = accepted_trades + peer_trades
        combined_overlay = same_day.prior.base._overlay_from_paper_trades(
            before_result,
            combined_trades,
        )
        after = same_day.prior.base.overlay_helper._metrics_with_overlay(
            before_result,
            combined_overlay,
        )
        incremental_delta = same_day.prior.base.overlay_helper._delta(after, accepted_before)
        core_delta = same_day.prior.base.overlay_helper._delta(
            after,
            baselines[label]["metrics"],
        )
        results.append(
            {
                "label": label,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "before": accepted_before,
                "after": after,
                "comparison": {
                    "expected_value_score_delta": incremental_delta["expected_value_score"],
                    "strategy_total_pnl_delta": incremental_delta["total_pnl"],
                    "total_pnl_delta": incremental_delta["total_pnl"],
                    "max_drawdown_delta": incremental_delta["max_drawdown_pct"],
                    "raw_delta": incremental_delta,
                },
                "core_before": baselines[label]["metrics"],
                "core_comparison": {
                    "expected_value_score_delta": core_delta["expected_value_score"],
                    "strategy_total_pnl_delta": core_delta["total_pnl"],
                    "total_pnl_delta": core_delta["total_pnl"],
                    "max_drawdown_delta": core_delta["max_drawdown_pct"],
                    "raw_delta": core_delta,
                },
                "accepted_lagged_trade_count": len(accepted_trades),
                "target_trade_count": len(peer_trades),
                "target_trade_pnl_usd": sum(_safe_float(row.get("pnl")) for row in peer_trades),
                "combined_trade_count": len(combined_trades),
                "combined_trade_pnl_usd": sum(_safe_float(row.get("pnl")) for row in combined_trades),
                "raw_peer_candidate_count": len(candidates),
                "target_diagnostics": target_diagnostics,
            }
        )
        peer_trades_by_window[label] = peer_trades
        candidate_audits[label] = candidate_audit
    return results, peer_trades_by_window, candidate_audits


def _aggregate_core_after(results: list[dict[str, Any]]) -> dict[str, Any]:
    before_ev = sum(_safe_float(row["core_before"].get("expected_value_score")) for row in results)
    after_ev = sum(_safe_float(row["after"].get("expected_value_score")) for row in results)
    before_pnl = sum(_safe_float(row["core_before"].get("total_pnl")) for row in results)
    after_pnl = sum(_safe_float(row["after"].get("total_pnl")) for row in results)
    before = {
        "expected_value_score": round(before_ev, 6),
        "strategy_total_pnl": round(before_pnl, 2),
        "total_pnl": round(before_pnl, 2),
    }
    after = {
        "expected_value_score": round(after_ev, 6),
        "strategy_total_pnl": round(after_pnl, 2),
        "total_pnl": round(after_pnl, 2),
    }
    comparison = {
        "expected_value_score_delta": round(after_ev - before_ev, 6),
        "expected_value_score_delta_pct": round((after_ev - before_ev) / before_ev, 6)
        if before_ev
        else None,
        "strategy_total_pnl_delta": round(after_pnl - before_pnl, 2),
        "total_pnl_delta": round(after_pnl - before_pnl, 2),
        "strategy_total_pnl_delta_pct": round((after_pnl - before_pnl) / before_pnl, 6)
        if before_pnl
        else None,
    }
    return {"before": before, "after": after, "comparison": comparison}


def _gate4_incremental(
    aggregate: dict[str, Any],
    results: list[dict[str, Any]],
    peer_summary: dict[str, Any],
) -> dict[str, Any]:
    comparison = aggregate["comparison"]
    ev_delta = _safe_float(comparison.get("expected_value_score_delta"))
    pnl_delta = _safe_float(comparison.get("strategy_total_pnl_delta"))
    ev_windows_improved = [
        row["label"] for row in results if _safe_float(row["comparison"].get("expected_value_score_delta")) > 0.0
    ]
    pnl_windows_improved = [
        row["label"] for row in results if _safe_float(row["comparison"].get("strategy_total_pnl_delta")) > 0.0
    ]
    max_drawdown_delta = max(_safe_float(row["comparison"].get("max_drawdown_delta")) for row in results)
    min_survival_rate = min(_safe_float(row["after"].get("survival_rate")) for row in results)
    target_trade_count = int(peer_summary["target_trade_count"])
    target_windows = sum(1 for row in results if int(row["target_trade_count"]) > 0)
    gates = {
        "incremental_expected_value_positive_vs_accepted_lagged": ev_delta > 0.0,
        "incremental_pnl_positive_vs_accepted_lagged": pnl_delta > 0.0,
        "all_windows_incremental_expected_value_improved": len(ev_windows_improved) == len(results),
        "all_windows_incremental_pnl_improved": len(pnl_windows_improved) == len(results),
        "incremental_peer_trade_count_passed": target_trade_count >= MIN_INCREMENTAL_PEER_TRADES,
        "incremental_peer_window_count_passed": target_windows >= MIN_INCREMENTAL_WINDOWS,
        "drawdown_drift_vs_accepted_lagged_passed": (
            max_drawdown_delta <= same_day.prior.MAX_DRAWDOWN_WORSE
        ),
        "survival_floor_passed": min_survival_rate >= 0.05,
        "incremental_peer_concentration_guard_passed": (
            _safe_float(peer_summary["max_single_positive_share"])
            <= same_day.prior.MAX_SINGLE_POSITIVE_SHARE
            and _safe_float(peer_summary["positive_pnl_hhi"])
            <= same_day.prior.MAX_POSITIVE_HHI
        ),
    }
    passed = all(gates.values())
    if passed:
        decision = (
            "positive_replay_lead_not_promoted_requires_lagged_peer_shared_adapter"
        )
        rationale = (
            "Characteristic peer-transfer rows improved the accepted lagged "
            "consensus comparator across all three canonical windows without "
            "production changes. Promotion would require a shared adapter and "
            "parity tests first."
        )
    else:
        decision = (
            "rejected_lagged_consensus_characteristic_peer_transfer_candidate_pool"
        )
        failed = [name for name, ok in gates.items() if not ok]
        rationale = "Gate 4 failed: " + "; ".join(failed)
    return {
        "passed": passed,
        "decision": decision,
        "rationale": rationale,
        "gates": gates,
        "ev_windows_improved": ev_windows_improved,
        "pnl_windows_improved": pnl_windows_improved,
        "max_drawdown_delta": max_drawdown_delta,
        "min_survival_rate": min_survival_rate,
        "requires_parity_before_promotion": passed,
        "accepted_comparator": SOURCE_COMPARATOR_ID,
        "incremental_before": "accepted_lagged_consensus_surface",
    }


def _field_coverage(rows: list[dict[str, Any]], fields: list[str]) -> dict[str, Any]:
    return {
        "row_count": len(rows),
        "fields": {
            field: {
                "present_count": sum(
                    1 for row in rows if row.get(field) not in (None, "", [])
                ),
                "non_null_rate": (
                    sum(1 for row in rows if row.get(field) not in (None, "", []))
                    / len(rows)
                    if rows
                    else 0.0
                ),
            }
            for field in fields
        },
    }


def _source_summary(
    accepted_trades_by_window: dict[str, list[dict[str, Any]]],
    peer_trades_by_window: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    source_rows = [
        row for rows in accepted_trades_by_window.values() for row in rows if row.get("has_lagged_independent_confirmation")
    ]
    peer_rows = [row for rows in peer_trades_by_window.values() for row in rows]
    return {
        "accepted_lagged_selected_trade_count": sum(
            len(rows) for rows in accepted_trades_by_window.values()
        ),
        "lagged_independent_source_trade_count": len(source_rows),
        "lagged_independent_source_trade_count_by_window": {
            label: sum(1 for row in rows if row.get("has_lagged_independent_confirmation"))
            for label, rows in accepted_trades_by_window.items()
        },
        "incremental_peer_trade_count": len(peer_rows),
        "incremental_peer_trade_count_by_window": {
            label: len(rows) for label, rows in peer_trades_by_window.items()
        },
        "incremental_peer_source_ticker_counts": dict(
            sorted(Counter(str(row.get("source_ticker") or "") for row in peer_rows).items())
        ),
        "incremental_peer_ticker_counts": dict(
            sorted(Counter(str(row.get("ticker") or "") for row in peer_rows).items())
        ),
        "incremental_peer_relation_sector_counts": dict(
            sorted(Counter(str(row.get("peer_sector") or "") for row in peer_rows).items())
        ),
    }


def _preflight_payload() -> dict[str, Any]:
    return {
        "alpha_hypothesis": (
            "entry/candidate_pool: selected lagged-independent free-data "
            "consensus trades may identify characteristic-similar liquid peers "
            "that continue reacting over the next 1-3 trading days and can fill "
            "open paper slots without replacing accepted lagged rows."
        ),
        "category": "entry/candidate_pool",
        "playbook_alignment": (
            "The alpha playbook favors production-visible default-off candidate "
            "pool adapters and says future peer work should use better relation "
            "construction, such as characteristic similarity, rather than simple "
            "same-sector membership."
        ),
        "nearby_prior_experiments": {
            "exp-20260603-005": (
                "Post-earnings characteristic-similarity peer transfer failed; "
                "this run changes the source to accepted lagged consensus rows "
                "and tests open-slot incremental value."
            ),
            "exp-20260604-014": (
                "SEC text same-sector peer propagation failed; this run uses "
                "Companyfacts/OHLCV characteristic similarity, not simple sector."
            ),
            "exp-20260604-008": (
                "Lagged independent-source consensus cleared replay gates; this "
                "run uses its selected lagged-independent rows as source events."
            ),
            "exp-20260605-021": (
                "Lagged consensus fill-delay gap guard damaged the accepted "
                "adapter. This run does not change fill timing or accepted rows."
            ),
        },
        "prior_difference": (
            "Single causal variable is a new peer-transfer candidate source "
            "around accepted lagged-independent source rows. No source threshold, "
            "source family, notional, hold period, exit, fill, or production "
            "adapter behavior is changed."
        ),
        "single_causal_variable": CHANGED_VARIABLE,
        "acceptance_criteria": {
            "canonical_windows": list(same_day.prior.base.WINDOWS.keys()),
            "before_comparator": SOURCE_COMPARATOR_ID,
            "aggregate_expected_value_delta_vs_accepted_lagged": "> 0",
            "aggregate_pnl_delta_vs_accepted_lagged": "> 0",
            "per_window_expected_value_delta_vs_accepted_lagged": "3 of 3 windows > 0",
            "per_window_pnl_delta_vs_accepted_lagged": "3 of 3 windows > 0",
            "minimum_incremental_peer_trades": MIN_INCREMENTAL_PEER_TRADES,
            "minimum_incremental_peer_windows": MIN_INCREMENTAL_WINDOWS,
            "max_drawdown_drift": same_day.prior.MAX_DRAWDOWN_WORSE,
            "survival_rate_floor": 0.05,
            "max_single_positive_share": same_day.prior.MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi_max": same_day.prior.MAX_POSITIVE_HHI,
        },
        "reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260605_024_lagged_consensus_characteristic_peer_transfer.py"
        ),
    }


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["incremental_aggregate"]["comparison"]
    core = payload["core_after_aggregate"]["comparison"]
    actual_success = 1 if payload["gate4"]["passed"] else 0
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["completed_at"],
        "lane": "alpha_search",
        "status": "accepted" if payload["gate4"]["passed"] else "rejected",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "change_type": "default_off_paper_candidate_pool",
        "mechanism_family": (
            "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
        ),
        "prior_trial_count": 4,
        "nearby_prior_experiments": list(payload["preflight"]["nearby_prior_experiments"].keys()),
        "multiple_testing_risk_bucket": "medium",
        "new_evidence_type": (
            "accepted_lagged_consensus_plus_companyfacts_ohlcv_characteristic_peer_relation"
        ),
        "decision": payload["gate4"]["decision"],
        "accepted": bool(payload["gate4"]["passed"]),
        "rejection_reason": None if payload["gate4"]["passed"] else payload["gate4"]["rationale"],
        "prediction": payload["prediction"],
        "calibration": {
            "actual_decision": payload["gate4"]["decision"],
            "actual_success": actual_success,
            "predicted_success_probability": payload["prediction"]["success_probability"],
            "brier_score": round(
                (payload["prediction"]["success_probability"] - actual_success) ** 2,
                6,
            ),
            "expected_ev_delta": payload["prediction"]["expected_ev_delta"],
            "actual_ev_delta": aggregate["expected_value_score_delta"],
            "expected_pnl_delta": payload["prediction"]["expected_pnl_delta"],
            "actual_pnl_delta": aggregate["strategy_total_pnl_delta"],
            "realized_failure_mode": None if payload["gate4"]["passed"] else payload["gate4"]["decision"],
        },
        "production_impact": PRODUCTION_IMPACT,
        "requires_parity_before_promotion": bool(payload["gate4"]["passed"]),
        "metrics": {
            "incremental_expected_value_before": payload["incremental_aggregate"]["before"][
                "expected_value_score"
            ],
            "incremental_expected_value_after": payload["incremental_aggregate"]["after"][
                "expected_value_score"
            ],
            "incremental_expected_value_delta": aggregate["expected_value_score_delta"],
            "incremental_strategy_total_pnl_before": payload["incremental_aggregate"]["before"][
                "strategy_total_pnl"
            ],
            "incremental_strategy_total_pnl_after": payload["incremental_aggregate"]["after"][
                "strategy_total_pnl"
            ],
            "incremental_strategy_total_pnl_delta": aggregate["strategy_total_pnl_delta"],
            "core_expected_value_delta": core["expected_value_score_delta"],
            "core_strategy_total_pnl_delta": core["strategy_total_pnl_delta"],
            "incremental_peer_trade_count": payload["peer_target_summary"]["target_trade_count"],
            "incremental_peer_trade_pnl_usd": payload["peer_target_summary"]["target_trade_pnl_usd"],
            "max_drawdown_delta_vs_accepted_lagged": payload["gate4"]["max_drawdown_delta"],
            "max_single_positive_share": payload["peer_target_summary"]["max_single_positive_share"],
            "positive_pnl_hhi": payload["peer_target_summary"]["positive_pnl_hhi"],
        },
        "windows": [
            {
                "label": row["label"],
                "expected_value_before": row["before"]["expected_value_score"],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta": row["comparison"]["expected_value_score_delta"],
                "strategy_total_pnl_delta": row["comparison"]["strategy_total_pnl_delta"],
                "incremental_peer_trade_count": row["target_trade_count"],
                "incremental_peer_trade_pnl_usd": row["target_trade_pnl_usd"],
                "raw_peer_candidate_count": row["raw_peer_candidate_count"],
            }
            for row in payload["results"]
        ],
        "artifact_path": _repo_rel(OUT_JSON),
        "anti_js": "No JavaScript was used.",
    }


def _write_card(payload: dict[str, Any]) -> None:
    comp = payload["incremental_aggregate"]["comparison"]
    core = payload["core_after_aggregate"]["comparison"]
    lines = [
        f"# {EXPERIMENT_ID} Lagged-consensus characteristic peer transfer",
        "",
        "## Decision",
        "",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Rationale: {payload['gate4']['rationale']}",
        "",
        "## Three-window Result",
        "",
        "| Window | Peer trades | Peer PnL | EV before | EV after | dEV vs accepted | dPnL vs accepted | Raw candidates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["results"]:
        lines.append(
            "| {label} | {count} | ${target_pnl:,.2f} | {before_ev:.4f} | {after_ev:.4f} | {dev:+.4f} | ${dpnl:+,.2f} | {raw} |".format(
                label=row["label"],
                count=int(row["target_trade_count"]),
                target_pnl=float(row["target_trade_pnl_usd"]),
                before_ev=float(row["before"]["expected_value_score"]),
                after_ev=float(row["after"]["expected_value_score"]),
                dev=float(row["comparison"]["expected_value_score_delta"]),
                dpnl=float(row["comparison"]["strategy_total_pnl_delta"]),
                raw=int(row["raw_peer_candidate_count"]),
            )
        )
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- Incremental vs accepted lagged consensus: EV `{comp['expected_value_score_delta']:+.4f}`, PnL `${comp['strategy_total_pnl_delta']:+,.2f}`",
            f"- Combined vs canonical core baseline: EV `{core['expected_value_score_delta']:+.4f}`, PnL `${core['strategy_total_pnl_delta']:+,.2f}`",
            f"- Incremental peer trades: `{payload['peer_target_summary']['target_trade_count']}`",
            f"- Max single positive share: `{payload['peer_target_summary']['max_single_positive_share']}`",
            f"- Positive PnL HHI: `{payload['peer_target_summary']['positive_pnl_hhi']}`",
            "",
            "## Production Impact",
            "",
            "- Replay-only; no production code or live/default order behavior changed.",
            "- Positive retention would require a shared lagged-peer adapter and parity tests first.",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    _write_text(CARD_MD, "\n".join(lines))


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "id": EXPERIMENT_ID,
            "experiment_id": EXPERIMENT_ID,
            "status": "completed",
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "artifact": _repo_rel(OUT_JSON),
            "card": _repo_rel(CARD_MD),
            "log": _repo_rel(LOG_JSON),
            "production_impact": PRODUCTION_IMPACT,
            "claim_conflict_note": payload["claim_conflict_note"],
            "gate4": payload["gate4"],
            "result": {
                "decision": payload["gate4"]["decision"],
                "incremental_expected_value_delta": payload["incremental_aggregate"][
                    "comparison"
                ]["expected_value_score_delta"],
                "incremental_total_pnl_delta": payload["incremental_aggregate"][
                    "comparison"
                ]["strategy_total_pnl_delta"],
                "peer_target_summary": payload["peer_target_summary"],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)


def _update_manifest(payload: dict[str, Any]) -> None:
    files = {
        "runner": Path(__file__),
        "result": OUT_JSON,
        "log": LOG_JSON,
        "ticket": TICKET_JSON,
        "card": CARD_MD,
        "manifest": MANIFEST_JSON,
        "experiment_log": EXPERIMENT_LOG,
        "registry": REGISTRY_JSON,
    }
    manifest = {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "status": "completed",
        "decision": payload["gate4"]["decision"],
        "generated_at": payload["completed_at"],
        "artifacts": [_repo_rel(path) for path in files.values()],
        "files": {
            label: {
                "path": _repo_rel(path),
                "exists": path.exists(),
                "sha256": _sha256(path),
            }
            for label, path in files.items()
        },
    }
    _write_json(MANIFEST_JSON, manifest)


def _upsert_registry(payload: dict[str, Any]) -> None:
    if not REGISTRY_JSON.exists():
        return
    registry = _load_json(REGISTRY_JSON)
    experiments = registry.get("experiments")
    if not isinstance(experiments, list):
        return
    for item in experiments:
        if isinstance(item, dict) and item.get("experiment_id") == EXPERIMENT_ID:
            item["status"] = "completed"
            item["decision"] = payload["gate4"]["decision"]
            item["completed_at"] = payload["completed_at"]
            item["artifact"] = _repo_rel(OUT_JSON)
            item["log"] = _repo_rel(LOG_JSON)
            item["aggregate_expected_value_delta"] = payload["incremental_aggregate"][
                "comparison"
            ]["expected_value_score_delta"]
            item["aggregate_strategy_total_pnl_delta"] = payload["incremental_aggregate"][
                "comparison"
            ]["strategy_total_pnl_delta"]
            item["updated_at"] = payload["completed_at"]
            break
    registry["updated_at"] = payload["completed_at"]
    _write_json(REGISTRY_JSON, registry)


def main() -> None:
    _configure_modules()
    gate2 = same_day.prior.base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    source_rows = same_day.prior._source_rows_by_window()
    baselines = same_day.prior._load_baselines()
    accepted_results, accepted_trades = lagged._run_lagged_windows(baselines, source_rows)
    accepted_aggregate = same_day.prior._aggregate_results(accepted_results)
    results, peer_trades_by_window, candidate_audits = _run_peer_windows(
        baselines,
        accepted_results,
        accepted_trades,
    )
    incremental_aggregate = same_day.prior._aggregate_results(results)
    core_after_aggregate = _aggregate_core_after(results)
    peer_target_summary = same_day.prior._target_summary(peer_trades_by_window)
    source_summary = _source_summary(accepted_trades, peer_trades_by_window)
    gate4 = _gate4_incremental(incremental_aggregate, results, peer_target_summary)
    all_peer_trades = [row for rows in peer_trades_by_window.values() for row in rows]
    completed_at = _utc_now()

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": completed_at,
        "completed_at": completed_at,
        "lane": "alpha_search",
        "preflight": _preflight_payload(),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "entry/candidate_pool: characteristic-similar peers of accepted "
                "lagged-independent source trades may fill open paper slots."
            ),
            "2_history_check": _preflight_payload()["nearby_prior_experiments"],
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Use docs/backtesting.md three fixed windows; before is the "
                "accepted lagged consensus surface and after adds only this "
                "peer-transfer source. Accept only if incremental EV/PnL improve "
                "in all windows with sample, drawdown, survival, and concentration "
                "guardrails."
            ),
            "5_reproducibility": _preflight_payload()["reproducibility"],
        },
        "source_files": {
            name: _repo_rel(REPO_ROOT / path) for name, path in same_day.SOURCE_FILES.items()
        },
        "rule": {
            "rule_version": RULE_VERSION,
            "peer_signal_offset_min": PEER_SIGNAL_OFFSET_MIN,
            "peer_signal_offset_max": PEER_SIGNAL_OFFSET_MAX,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "min_peer_signal_excess_vs_spy": MIN_PEER_SIGNAL_EXCESS_VS_SPY,
            "min_peer_source_to_signal_excess_vs_spy": (
                MIN_PEER_SOURCE_TO_SIGNAL_EXCESS_VS_SPY
            ),
            "min_peer_close_location": MIN_PEER_CLOSE_LOCATION,
            "min_rs20_vs_spy": MIN_RS20_VS_SPY,
            "min_characteristic_similarity": MIN_CHARACTERISTIC_SIMILARITY,
            "min_common_characteristics": MIN_COMMON_CHARACTERISTICS,
            "min_common_fundamental_characteristics": (
                MIN_COMMON_FUNDAMENTAL_CHARACTERISTICS
            ),
            "base_notional_usd": same_day.prior.BASE_NOTIONAL_USD,
            "hold_days": same_day.prior.HOLD_DAYS,
            "max_paper_trades_per_day": same_day.prior.MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": same_day.prior.SAME_TICKER_COOLDOWN_DAYS,
        },
        "claim_conflict_note": (
            "scripts/experiment.py claim reported active exp-20260605-023 has a "
            "generic modified_code conflict. This runner stayed inside the "
            "reserved exp-20260605-024 write scope and changed only the locked "
            "variable listed in its ticket."
        ),
        "production_impact": PRODUCTION_IMPACT,
        "prediction": PREDICTION,
        "gate2": {
            **gate2,
            "target_trade_field_coverage": _field_coverage(
                all_peer_trades,
                [
                    "ticker",
                    "signal_date",
                    "entry_date",
                    "exit_date",
                    "entry_price",
                    "exit_price",
                    "pnl",
                    "known_at",
                    "source_ticker",
                    "source_signal_date",
                    "source_sector",
                    "peer_sector",
                    "peer_signal_excess_return_1d_vs_spy",
                    "peer_source_to_signal_excess_vs_spy",
                    "characteristic_similarity_score",
                    "common_characteristics",
                    "common_fundamental_characteristics",
                    "rs20_vs_spy",
                    "avg_dollar_volume_20d",
                ],
            ),
        },
        "gate3": {
            "survival_floor": 0.05,
            "new_core_filter_added": False,
            "candidate_pool_source_admission_only": True,
            "min_survival_rate": min(_safe_float(row["after"].get("survival_rate")) for row in results),
        },
        "accepted_comparator": {
            "experiment_id": SOURCE_COMPARATOR_ID,
            "replay_source_experiment_id": SOURCE_REPLAY_ID,
            "source_artifact": _repo_rel(ACCEPTED_REPLAY_JSON),
            "aggregate": accepted_aggregate,
            "target_summary": same_day.prior._target_summary(accepted_trades),
        },
        "incremental_aggregate": incremental_aggregate,
        "core_after_aggregate": core_after_aggregate,
        "results": results,
        "peer_target_summary": peer_target_summary,
        "source_summary": source_summary,
        "candidate_audits": candidate_audits,
        "peer_trades_by_window": peer_trades_by_window,
        "gate4": gate4,
        "anti_js": "No JavaScript was used.",
        "interpretation": (
            "The lagged-consensus characteristic peer-transfer source cleared "
            "incremental Gate 4 as a replay lead, but no shared adapter was promoted."
            if gate4["passed"]
            else (
                "The lagged-consensus characteristic peer-transfer source did not "
                "clear incremental Gate 4 against the accepted lagged consensus "
                "comparator. Do not promote it or retune nearby peer thresholds on "
                "these frozen windows without forward rows or a stronger relation source."
            )
        ),
        "why_not_other_alpha": (
            "Skipped LLM soft-ranking because replay-safe soft-ranking rows remain "
            "insufficient. Skipped Companyfacts threshold retunes, FINRA/FTD threshold "
            "retunes, SEC text phrase variants, lagged fill timing, Space activation, "
            "and state-surface scalar retunes because the playbook marks those nearby "
            "families as frozen or requiring materially new forward evidence."
        ),
    }

    _write_json(OUT_JSON, payload)
    record = _experiment_log_record(payload)
    _write_json(LOG_JSON, record)
    _write_card(payload)
    _update_ticket(payload)
    _upsert_registry(payload)
    same_day.prior.base._upsert_jsonl(EXPERIMENT_LOG, record)
    _update_manifest(payload)

    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": gate4["decision"],
                    "incremental_vs_accepted_lagged": incremental_aggregate["comparison"],
                    "combined_vs_core": core_after_aggregate["comparison"],
                    "peer_target_summary": peer_target_summary,
                    "source_summary": source_summary,
                    "anti_js": "No JavaScript was used.",
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
