"""Default-off broad-market leadership paper sleeve.

The sleeve promotes the exp-20260519-035 alpha lead into a shared,
production-visible observation path. It never emits live orders and never
changes core signal generation, ranking, sizing, exits, or portfolio heat.
"""

from __future__ import annotations

import json
import math
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from data_paths import data_artifact_path

try:
    from constants import ROUND_TRIP_COST_PCT
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.constants import ROUND_TRIP_COST_PCT

try:
    from broad_market_sector_map import (
        load_cache as _load_sector_cache,
        lookup_sector as _lookup_sector,
    )
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.broad_market_sector_map import (
        load_cache as _load_sector_cache,
        lookup_sector as _lookup_sector,
    )


SLEEVE_NAME = "BROAD_MARKET_LEADERSHIP_PAPER"
SECTOR_MAP_RULE_VERSION = "yfinance_gics_proxy_sector_v1"

# Module-level sector cache — loaded once on first lookup, never mutated.
_BROAD_MARKET_SECTOR_CACHE: dict[str, Any] | None = None


def _get_broad_market_sector_cache() -> dict[str, Any]:
    global _BROAD_MARKET_SECTOR_CACHE
    if _BROAD_MARKET_SECTOR_CACHE is None:
        _BROAD_MARKET_SECTOR_CACHE = _load_sector_cache()
    return _BROAD_MARKET_SECTOR_CACHE


RULE_VERSION = "broad_market_price_floor_rank_low_extension_high_volatility_trend_persistence_v1"
REPLACEMENT_VALUE_RULE_VERSION = "broad_market_forward_replacement_value_v1"
RANK_NOTIONAL_RULE_VERSION = "broad_market_rank_notional_profile_v1"
LOW_EXTENSION_RULE_VERSION = "broad_market_low_extension_notional_v1"
HIGH_VOLATILITY_RULE_VERSION = "broad_market_high_volatility_notional_v1"
TREND_PERSISTENCE_RULE_VERSION = "broad_market_trend_persistence_notional_v1"
UNIVERSE_STATE_FEED_RULE_VERSION = "broad_market_universe_state_observation_feed_v1"
STATE_SCHEMA_VERSION = 1

DEFAULT_STATE_PATH = data_artifact_path("broad_market_paper_state")
DEFAULT_SNAPSHOT_LOG_PATH = data_artifact_path("broad_market_paper_snapshots")
DEFAULT_UNIVERSE_PATH = data_artifact_path("broad_market_paper_universe")

TITLE_EXCLUSION_KEYWORDS = (
    " ETF",
    " FUND",
    " TRUST",
    " WARRANT",
    " RIGHTS",
    " UNIT",
    " ACQUISITION",
    " SPAC",
    " PREFERRED",
    " DEPOSITARY",
)

BROAD_MARKET_FEED_EXCLUDED_TICKERS = {
    "ARKX",
    "UFO",
}

DEFAULT_CONFIG = {
    "enabled": False,
    "paper_enabled": True,
    "trade_enabled": False,
    "ret20_excess_spy_min": 0.035,
    "ret60_min": 0.08,
    "near_high_60_min": 0.93,
    "volume_ratio_20_min": 1.00,
    "decision_close_price_min": 40.0,
    "paper_notional_usd": 7_500.0,
    "rank_notional_multipliers": [1.20, 1.00, 0.80],
    "low_extension_ret5_max": 0.02,
    "low_extension_notional_scalar": 1.15,
    "high_volatility_20_min": 0.055,
    "high_volatility_notional_scalar": 1.15,
    "trend_persistence_positive_day_ratio_20_min": 0.55,
    "trend_persistence_notional_scalar": 1.15,
    "max_active_positions": 5,
    "daily_entry_slots": 3,
    "hold_days": 20,
    "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
    "forward_gate_min_closed_trades": 60,
    "forward_gate_positive_net_pnl": True,
    "forward_gate_min_win_rate": 0.52,
    "forward_gate_max_single_ticker_positive_share": 0.50,
    "forward_gate_max_top5_positive_share": 0.70,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sector_fields(ticker: str) -> dict[str, Any]:
    """Return flat sector / industry / coverage-status fields for a ticker.

    Uses the module-level sector cache (loaded once, offline-deterministic).
    Safe to call for any ticker; returns None values if the ticker is absent
    from the cache.  Does not mutate cache or trading state.
    """
    result = _lookup_sector(ticker, _get_broad_market_sector_cache())
    return {
        "sector": result.get("sector"),
        "industry": result.get("industry"),
        "sector_coverage_status": result.get("status"),
    }


def empty_broad_market_paper_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_entries": [],
    }


def load_broad_market_paper_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_broad_market_paper_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_broad_market_paper_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_broad_market_paper_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_broad_market_paper_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, sort_keys=True) + "\n")


def empty_broad_market_paper_sleeve_snapshot(as_of: str, reason: str) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "asof_date": _date10(as_of),
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": False,
        "trade_enabled": False,
        "candidate_count": 0,
        "new_pending_count": 0,
        "filled_count": 0,
        "closed_count_today": 0,
        "pending_count": 0,
        "open_position_count": 0,
        "closed_position_count": 0,
        "realized_pnl_to_date": 0.0,
        "unrealized_pnl": 0.0,
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "data_source": {"status": reason},
        "production_impact": _production_impact(),
        "error": reason,
    }


def load_broad_market_candidate_universe(
    path: Path | str = DEFAULT_UNIVERSE_PATH,
) -> dict[str, Any]:
    """Load the optional broad-market paper universe feed.

    Accepted shapes:
    - ["A", "B"]
    - {"tickers": ["A", "B"], "records": {"A": {"title": "..."}}}
    - {"records": [{"ticker": "A", "title": "..."}]}
    """
    universe_path = Path(path)
    if not universe_path.exists():
        return {
            "status": "missing",
            "path": str(universe_path),
            "tickers": [],
            "records": {},
        }
    with universe_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    records: dict[str, dict[str, Any]] = {}
    tickers: list[str] = []
    if isinstance(payload, list):
        tickers = [str(value).upper() for value in payload if value]
    elif isinstance(payload, dict):
        if isinstance(payload.get("tickers"), list):
            tickers.extend(str(value).upper() for value in payload["tickers"] if value)
        raw_records = payload.get("records")
        if isinstance(raw_records, dict):
            for ticker, record in raw_records.items():
                key = str(ticker).upper()
                records[key] = dict(record or {})
                records[key]["ticker"] = key
        elif isinstance(raw_records, list):
            for record in raw_records:
                if not isinstance(record, dict) or not record.get("ticker"):
                    continue
                key = str(record["ticker"]).upper()
                records[key] = dict(record)
                records[key]["ticker"] = key
        tickers.extend(records)
    tickers = sorted(set(tickers))
    return {
        "status": "loaded",
        "path": str(universe_path),
        "tickers": tickers,
        "records": records,
    }


def build_broad_market_candidate_universe_from_universe_state(
    universe_state: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build a conservative paper feed from the daily governance snapshot.

    This is a fallback for forward observation only. A maintained
    ``data/state/broad_market_paper/universe.json`` file remains authoritative
    when present.
    """
    if not isinstance(universe_state, dict):
        return {
            "status": "universe_state_missing",
            "path": None,
            "tickers": [],
            "records": {},
            "rule_version": UNIVERSE_STATE_FEED_RULE_VERSION,
        }
    raw_records = universe_state.get("records")
    records_by_ticker = raw_records if isinstance(raw_records, dict) else {}
    as_of = universe_state.get("as_of")
    tradeable = {
        str(ticker).upper()
        for key in (
            "core_trade_universe",
            "pilot_trade_universe",
            "governance_tradeable_universe",
        )
        for ticker in (universe_state.get(key) or [])
        if ticker
    }
    observation = {
        str(ticker).upper()
        for ticker in (universe_state.get("observation_universe") or [])
        if ticker
    }
    if not observation:
        observation = {
            str(ticker).upper()
            for ticker in records_by_ticker
            if ticker
        }

    records: dict[str, dict[str, Any]] = {}
    excluded: list[dict[str, Any]] = []
    for ticker in sorted(observation):
        raw_record = records_by_ticker.get(ticker) or {}
        record = dict(raw_record) if isinstance(raw_record, dict) else {}
        record["ticker"] = ticker
        reasons = _broad_market_feed_exclusion_reasons(
            ticker,
            record,
            as_of=as_of,
            tradeable=tradeable,
        )
        if reasons:
            excluded.append({"ticker": ticker, "reasons": reasons})
            continue
        records[ticker] = {
            "ticker": ticker,
            "title": record.get("title") or record.get("company_name") or "",
            "status": record.get("status"),
            "theme": record.get("theme"),
            "theme_segment": record.get("theme_segment"),
            "eligible_as_of": record.get("eligible_as_of"),
            "source": record.get("source"),
            "source_reason": record.get("source_reason"),
            "feed_rule_version": UNIVERSE_STATE_FEED_RULE_VERSION,
        }

    return {
        "status": "universe_state_observation_feed",
        "path": universe_state.get("artifact_path") or universe_state.get("path"),
        "as_of": as_of,
        "rule_version": UNIVERSE_STATE_FEED_RULE_VERSION,
        "tickers": sorted(records),
        "records": records,
        "excluded_count": len(excluded),
        "excluded_sample": excluded[:25],
        "source_counts": {
            "observation_universe": len(observation),
            "tradeable_universe": len(tradeable),
            "records": len(records_by_ticker),
        },
    }


def build_broad_market_paper_sleeve_snapshot(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any] | None = None,
    current_tradeable_universe: list[str] | set[str] | None = None,
    candidate_universe: dict[str, Any] | list[str] | None = None,
    open_prices: dict[str, Any] | None = None,
    current_prices: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    persist: bool = True,
    state_path: Path | str = DEFAULT_STATE_PATH,
    snapshot_log_path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> dict[str, Any]:
    cfg = _config(config)
    as_of_date = _date10(as_of)
    working_state = deepcopy(
        state if state is not None else load_broad_market_paper_state(state_path)
    )
    _normalise_state(working_state)

    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    loaded_universe = _normalise_candidate_universe(candidate_universe)
    tradeable = {str(ticker).upper() for ticker in (current_tradeable_universe or set())}
    current, opens = _exact_asof_price_maps(
        rows_by_ticker,
        as_of=as_of_date,
        current_prices=current_prices,
        open_prices=open_prices,
    )
    asof_has_benchmark_price = (
        _index_on_date(rows_by_ticker.get("SPY") or [], as_of_date) is not None
    )

    if asof_has_benchmark_price:
        closed_today = _advance_open_positions(
            working_state,
            as_of=as_of_date,
            current_prices=current,
            config=cfg,
        )
        filled_today, skipped_today = _fill_pending_entries(
            working_state,
            as_of=as_of_date,
            open_prices=opens,
            current_prices=current,
            config=cfg,
        )
    else:
        closed_today = []
        filled_today = []
        skipped_today = []

    candidates = build_broad_market_paper_candidates(
        as_of=as_of_date,
        ohlcv_by_ticker=rows_by_ticker,
        candidate_tickers=loaded_universe["tickers"],
        ticker_metadata=loaded_universe["records"],
        current_tradeable_universe=tradeable,
        open_position_tickers={
            str(row.get("ticker") or "").upper()
            for row in working_state.get("open_positions") or []
        },
        config=cfg,
    )
    new_pending = _add_candidates(
        working_state,
        candidates,
        as_of=as_of_date,
        config=cfg,
    )

    snapshot = _snapshot_payload(
        working_state,
        as_of=as_of_date,
        config=cfg,
        data_source=loaded_universe,
        candidates=candidates,
        new_pending=new_pending,
        filled_today=filled_today,
        closed_today=closed_today,
        skipped_today=skipped_today,
    )
    if persist:
        save_broad_market_paper_state(working_state, state_path)
        append_broad_market_paper_snapshot(snapshot, snapshot_log_path)
    return snapshot


def build_broad_market_paper_candidates(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any],
    candidate_tickers: list[str] | tuple[str, ...],
    ticker_metadata: dict[str, dict[str, Any]] | None = None,
    current_tradeable_universe: set[str] | None = None,
    open_position_tickers: set[str] | None = None,
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    cfg = _config(config)
    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    spy_rows = rows_by_ticker.get("SPY") or []
    spy_index = _date_index(spy_rows)
    if not spy_rows:
        return []
    tradeable = current_tradeable_universe or set()
    active = open_position_tickers or set()
    metadata = ticker_metadata or {}
    features: list[dict[str, Any]] = []
    for ticker in sorted({str(value).upper() for value in candidate_tickers if value}):
        if ticker in tradeable or ticker in active or ticker in {"SPY", "QQQ"}:
            continue
        record = metadata.get(ticker) or {}
        if _excluded_candidate_record(record):
            continue
        rows = rows_by_ticker.get(ticker) or []
        idx = _index_on_date(rows, as_of)
        if idx is None:
            continue
        feature = build_broad_market_feature(
            ticker=ticker,
            rows=rows,
            idx=idx,
            spy_rows=spy_rows,
            spy_index=spy_index,
        )
        if feature and candidate_passes_profile(feature, cfg):
            features.append(feature)
    features = select_broad_market_features(features, config=cfg)
    return [
        _candidate_from_feature(feature, source_rank=rank, config=cfg)
        for rank, feature in enumerate(features, start=1)
    ]


def _realized_volatility(
    rows: list[dict[str, Any]],
    idx: int,
    lookback: int,
) -> float | None:
    if idx < lookback:
        return None
    returns: list[float] = []
    for cursor in range(idx - lookback + 1, idx + 1):
        prev_close = _positive_float(rows[cursor - 1].get("close"))
        close = _positive_float(rows[cursor].get("close"))
        if not prev_close or not close:
            return None
        returns.append(close / prev_close - 1.0)
    if not returns:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / len(returns)
    return variance ** 0.5


def _positive_day_ratio(
    rows: list[dict[str, Any]],
    idx: int,
    lookback: int,
) -> float | None:
    if idx < lookback:
        return None
    positive_days = 0
    observed_days = 0
    for cursor in range(idx - lookback + 1, idx + 1):
        prev_close = _positive_float(rows[cursor - 1].get("close"))
        close = _positive_float(rows[cursor].get("close"))
        if not prev_close or not close:
            return None
        observed_days += 1
        if close > prev_close:
            positive_days += 1
    if observed_days != lookback:
        return None
    return positive_days / observed_days


def build_broad_market_feature(
    *,
    ticker: str,
    rows: list[dict[str, Any]],
    idx: int,
    spy_rows: list[dict[str, Any]],
    spy_index: dict[str, int],
) -> dict[str, Any] | None:
    if idx < 60:
        return None
    row = rows[idx]
    day = str(row.get("date") or "")[:10]
    spy_idx = spy_index.get(day)
    if spy_idx is None or spy_idx < 20:
        return None
    close = _positive_float(row.get("close"))
    close_5 = _positive_float(rows[idx - 5].get("close"))
    close_20 = _positive_float(rows[idx - 20].get("close"))
    close_60 = _positive_float(rows[idx - 60].get("close"))
    spy_close = _positive_float(spy_rows[spy_idx].get("close"))
    spy_close_20 = _positive_float(spy_rows[spy_idx - 20].get("close"))
    if (
        not close
        or not close_5
        or not close_20
        or not close_60
        or not spy_close
        or not spy_close_20
    ):
        return None
    volume_slice = rows[idx - 20 : idx]
    volume_values = [_positive_float(item.get("volume")) for item in volume_slice]
    if any(value is None for value in volume_values) or len(volume_values) != 20:
        return None
    avg_volume_20 = sum(float(value) for value in volume_values) / len(volume_values)
    if avg_volume_20 <= 0:
        return None
    high_values = [_positive_float(item.get("high")) for item in rows[idx - 59 : idx + 1]]
    if any(value is None for value in high_values) or len(high_values) != 60:
        return None
    high_60 = max(float(value) for value in high_values)
    if high_60 <= 0:
        return None

    ret20 = close / close_20 - 1.0
    spy_ret20 = spy_close / spy_close_20 - 1.0
    ret60 = close / close_60 - 1.0
    ret5 = close / close_5 - 1.0
    volume_ratio_20 = float(row["volume"]) / avg_volume_20
    near_high_60 = close / high_60
    realized_volatility_20 = _realized_volatility(rows, idx, 20)
    if realized_volatility_20 is None:
        return None
    positive_day_ratio_20 = _positive_day_ratio(rows, idx, 20)
    if positive_day_ratio_20 is None:
        return None
    score = (
        ret20 - spy_ret20
        + 0.50 * ret60
        + 0.04 * min(volume_ratio_20, 5.0)
        + 0.20 * (near_high_60 - 0.90)
    )
    return {
        "ticker": str(ticker).upper(),
        "date": day,
        "index": idx,
        "close": round(close, 6),
        "ret20": round(ret20, 6),
        "spy_ret20": round(spy_ret20, 6),
        "ret20_excess_spy": round(ret20 - spy_ret20, 6),
        "ret5": round(ret5, 6),
        "ret60": round(ret60, 6),
        "volume_ratio_20": round(volume_ratio_20, 6),
        "near_high_60": round(near_high_60, 6),
        "realized_volatility_20": round(realized_volatility_20, 6),
        "positive_day_ratio_20": round(positive_day_ratio_20, 6),
        "score": round(score, 6),
    }


def candidate_passes_profile(
    feature: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> bool:
    cfg = _config(config)
    return bool(
        float(feature["ret20_excess_spy"]) >= float(cfg["ret20_excess_spy_min"])
        and float(feature["ret60"]) >= float(cfg["ret60_min"])
        and float(feature["near_high_60"]) >= float(cfg["near_high_60_min"])
        and float(feature["volume_ratio_20"]) >= float(cfg["volume_ratio_20_min"])
        and float(feature["close"]) >= float(cfg["decision_close_price_min"])
    )


def select_broad_market_features(
    features: list[dict[str, Any]],
    *,
    capacity: int | None = None,
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    cfg = _config(config)
    limit = min(
        int(cfg["daily_entry_slots"]),
        int(cfg["max_active_positions"]) if capacity is None else int(capacity),
    )
    ranked = sorted(
        features,
        key=lambda row: (
            float(row["score"]),
            float(row["ret20_excess_spy"]),
            float(row["volume_ratio_20"]),
            str(row["ticker"]),
        ),
        reverse=True,
    )
    return ranked[: max(0, limit)]


def backtest_trade_from_feature(
    *,
    feature: dict[str, Any],
    prices_by_ticker: dict[str, list[dict[str, Any]]],
    window_end: str,
    rank: int,
    config: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    cfg = _config(config)
    ticker = str(feature["ticker"]).upper()
    rows = prices_by_ticker.get(ticker) or []
    entry_idx = int(feature["index"]) + 1
    exit_idx = entry_idx + int(cfg["hold_days"]) - 1
    if exit_idx >= len(rows):
        return None
    entry = rows[entry_idx]
    exit_ = rows[exit_idx]
    if str(entry["date"]) > window_end or str(exit_["date"]) > window_end:
        return None
    entry_open = _positive_float(entry.get("open"))
    exit_close = _positive_float(exit_.get("close"))
    if not entry_open or not exit_close:
        return None
    notional_payload = broad_market_candidate_notional_payload(rank, feature, cfg)
    notional = float(notional_payload["notional"])
    shares = notional / entry_open
    net_return = exit_close / entry_open - 1.0 - float(cfg["round_trip_cost_pct"])
    return {
        "ticker": ticker,
        "decision_date": feature["date"],
        "entry_date": entry["date"],
        "exit_date": exit_["date"],
        "entry_open": round(entry_open, 6),
        "exit_close": round(exit_close, 6),
        "shares": round(shares, 8),
        "notional": notional,
        "pnl": round(notional * net_return, 2),
        "net_return_pct": round(net_return, 6),
        "hold_days": int(cfg["hold_days"]),
        "profile": "price_floor_40",
        "rank": rank,
        "rule_version": RULE_VERSION,
        "rank_notional_rule_version": RANK_NOTIONAL_RULE_VERSION,
        "rank_notional_multiplier": notional_payload["rank_multiplier"],
        "low_extension_rule_version": LOW_EXTENSION_RULE_VERSION,
        "low_extension_ret5_max": cfg["low_extension_ret5_max"],
        "low_extension_notional_scalar": cfg["low_extension_notional_scalar"],
        "low_extension_notional_multiplier": notional_payload["low_extension_multiplier"],
        "low_extension_support_applied": notional_payload["low_extension_support_applied"],
        "high_volatility_rule_version": HIGH_VOLATILITY_RULE_VERSION,
        "high_volatility_20_min": cfg["high_volatility_20_min"],
        "high_volatility_notional_scalar": cfg["high_volatility_notional_scalar"],
        "high_volatility_notional_multiplier": notional_payload["high_volatility_multiplier"],
        "high_volatility_support_applied": notional_payload["high_volatility_support_applied"],
        "trend_persistence_rule_version": TREND_PERSISTENCE_RULE_VERSION,
        "trend_persistence_positive_day_ratio_20_min": cfg["trend_persistence_positive_day_ratio_20_min"],
        "trend_persistence_notional_scalar": cfg["trend_persistence_notional_scalar"],
        "trend_persistence_notional_multiplier": notional_payload["trend_persistence_multiplier"],
        "trend_persistence_support_applied": notional_payload["trend_persistence_support_applied"],
        "base_paper_notional": notional_payload["base_notional"],
        "ret20_excess_spy": feature["ret20_excess_spy"],
        "ret5": feature.get("ret5"),
        "ret60": feature["ret60"],
        "volume_ratio_20": feature["volume_ratio_20"],
        "near_high_60": feature["near_high_60"],
        "realized_volatility_20": feature["realized_volatility_20"],
        "positive_day_ratio_20": feature["positive_day_ratio_20"],
        "decision_close": feature["close"],
        "decision_close_price_min": cfg["decision_close_price_min"],
        "score": feature["score"],
        "sector_map_rule_version": SECTOR_MAP_RULE_VERSION,
        **_sector_fields(ticker),
    }


def _candidate_from_feature(
    feature: dict[str, Any],
    *,
    source_rank: int,
    config: dict[str, Any],
) -> dict[str, Any]:
    ticker = str(feature["ticker"]).upper()
    decision_id = f"{SLEEVE_NAME}:{RULE_VERSION}:{feature['date']}:{ticker}"
    notional_payload = broad_market_candidate_notional_payload(
        source_rank,
        feature,
        config,
    )
    return {
        "decision_id": decision_id,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "ticker": ticker,
        "asof_date": feature["date"],
        "decision_date": feature["date"],
        "source_rank": source_rank,
        "intended_entry_timing": "next_session_open",
        "intended_notional": notional_payload["notional"],
        "base_paper_notional": notional_payload["base_notional"],
        "rank_notional_multiplier": notional_payload["rank_multiplier"],
        "rank_notional_rule_version": RANK_NOTIONAL_RULE_VERSION,
        "low_extension_rule_version": LOW_EXTENSION_RULE_VERSION,
        "low_extension_ret5_max": config["low_extension_ret5_max"],
        "low_extension_notional_scalar": config["low_extension_notional_scalar"],
        "low_extension_notional_multiplier": notional_payload["low_extension_multiplier"],
        "low_extension_support_applied": notional_payload["low_extension_support_applied"],
        "high_volatility_rule_version": HIGH_VOLATILITY_RULE_VERSION,
        "high_volatility_20_min": config["high_volatility_20_min"],
        "high_volatility_notional_scalar": config["high_volatility_notional_scalar"],
        "high_volatility_notional_multiplier": notional_payload["high_volatility_multiplier"],
        "high_volatility_support_applied": notional_payload["high_volatility_support_applied"],
        "trend_persistence_rule_version": TREND_PERSISTENCE_RULE_VERSION,
        "trend_persistence_positive_day_ratio_20_min": config["trend_persistence_positive_day_ratio_20_min"],
        "trend_persistence_notional_scalar": config["trend_persistence_notional_scalar"],
        "trend_persistence_notional_multiplier": notional_payload["trend_persistence_multiplier"],
        "trend_persistence_support_applied": notional_payload["trend_persistence_support_applied"],
        "replacement_value_context": {
            "rule_version": REPLACEMENT_VALUE_RULE_VERSION,
            "read_only": True,
            "displaced_resource": "paper_cash_slot",
            "displaced_core_candidate": None,
            "forward_outcome_horizon_days": int(config["hold_days"]),
            "replacement_value_pending": True,
            "trade_enabled": False,
            "alters_orders": False,
        },
        "trade_enabled": False,
        "alters_orders": False,
        "features": deepcopy(feature),
        "profile": {
            key: config[key]
            for key in (
                "ret20_excess_spy_min",
                "ret60_min",
                "near_high_60_min",
                "volume_ratio_20_min",
                "decision_close_price_min",
            )
        },
        "sector_map_rule_version": SECTOR_MAP_RULE_VERSION,
        **_sector_fields(ticker),
    }


def broad_market_rank_notional_multiplier(
    source_rank: Any,
    config: dict[str, Any] | None = None,
) -> float:
    cfg = _config(config)
    try:
        rank = int(source_rank)
    except (TypeError, ValueError):
        rank = 1
    multipliers = cfg.get("rank_notional_multipliers") or [1.0]
    if not isinstance(multipliers, list) or not multipliers:
        multipliers = [1.0]
    idx = max(0, rank - 1)
    if idx >= len(multipliers):
        idx = len(multipliers) - 1
    parsed = _positive_float(multipliers[idx])
    return round(parsed if parsed is not None else 1.0, 6)


def broad_market_rank_notional_payload(
    source_rank: Any,
    config: dict[str, Any] | None = None,
) -> dict[str, float]:
    cfg = _config(config)
    base_notional = float(cfg["paper_notional_usd"])
    multiplier = broad_market_rank_notional_multiplier(source_rank, cfg)
    return {
        "base_notional": round(base_notional, 2),
        "multiplier": multiplier,
        "notional": round(base_notional * multiplier, 2),
    }


def broad_market_low_extension_multiplier(
    feature: dict[str, Any] | None,
    config: dict[str, Any] | None = None,
) -> float:
    cfg = _config(config)
    ret5 = _float_or_none((feature or {}).get("ret5"))
    max_ret5 = _float_or_none(cfg.get("low_extension_ret5_max"))
    scalar = _positive_float(cfg.get("low_extension_notional_scalar"))
    if ret5 is None or max_ret5 is None or scalar is None:
        return 1.0
    if ret5 <= max_ret5:
        return round(scalar, 6)
    return 1.0


def broad_market_high_volatility_multiplier(
    feature: dict[str, Any] | None,
    config: dict[str, Any] | None = None,
) -> float:
    cfg = _config(config)
    volatility = _float_or_none((feature or {}).get("realized_volatility_20"))
    min_volatility = _float_or_none(cfg.get("high_volatility_20_min"))
    scalar = _positive_float(cfg.get("high_volatility_notional_scalar"))
    if volatility is None or min_volatility is None or scalar is None:
        return 1.0
    if volatility >= min_volatility:
        return round(scalar, 6)
    return 1.0


def broad_market_trend_persistence_multiplier(
    feature: dict[str, Any] | None,
    config: dict[str, Any] | None = None,
) -> float:
    cfg = _config(config)
    ratio = _float_or_none((feature or {}).get("positive_day_ratio_20"))
    min_ratio = _float_or_none(cfg.get("trend_persistence_positive_day_ratio_20_min"))
    scalar = _positive_float(cfg.get("trend_persistence_notional_scalar"))
    if ratio is None or min_ratio is None or scalar is None:
        return 1.0
    if ratio >= min_ratio:
        return round(scalar, 6)
    return 1.0


def broad_market_candidate_notional_payload(
    source_rank: Any,
    feature: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = _config(config)
    rank_payload = broad_market_rank_notional_payload(source_rank, cfg)
    low_extension_multiplier = broad_market_low_extension_multiplier(feature, cfg)
    high_volatility_multiplier = broad_market_high_volatility_multiplier(feature, cfg)
    trend_persistence_multiplier = broad_market_trend_persistence_multiplier(feature, cfg)
    notional = (
        float(rank_payload["base_notional"])
        * float(rank_payload["multiplier"])
        * low_extension_multiplier
        * high_volatility_multiplier
        * trend_persistence_multiplier
    )
    return {
        "base_notional": rank_payload["base_notional"],
        "rank_multiplier": rank_payload["multiplier"],
        "low_extension_multiplier": low_extension_multiplier,
        "low_extension_support_applied": low_extension_multiplier != 1.0,
        "high_volatility_multiplier": high_volatility_multiplier,
        "high_volatility_support_applied": high_volatility_multiplier != 1.0,
        "trend_persistence_multiplier": trend_persistence_multiplier,
        "trend_persistence_support_applied": trend_persistence_multiplier != 1.0,
        "notional": round(notional, 2),
    }


try:
    from us_market_calendar import is_us_equity_session
except ImportError:  # pragma: no cover - package-style import fallback
    from quant.us_market_calendar import is_us_equity_session


def _advance_open_positions(
    state: dict[str, Any],
    *,
    as_of: str,
    current_prices: dict[str, float],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    if not is_us_equity_session(as_of):
        # Non-session run dates (weekends/NYSE holidays) carry only stale
        # bars; they must not age holds or close positions (exp-20260612-001).
        return []
    still_open = []
    closed_today = []
    cost = float(config["round_trip_cost_pct"])
    hold_days = int(config["hold_days"])
    for raw in state["open_positions"]:
        position = dict(raw)
        ticker = str(position.get("ticker") or "").upper()
        current = current_prices.get(ticker)
        if current is None:
            still_open.append(position)
            continue
        entry_date = str(position.get("entry_date") or "")[:10]
        last_seen = str(position.get("last_seen_date") or "")[:10]
        if as_of > entry_date and as_of != last_seen:
            position["observed_trading_days"] = int(
                position.get("observed_trading_days") or 0
            ) + 1
        position["last_seen_date"] = as_of
        position["last_price"] = current
        position["unrealized_pnl"] = _pnl(
            position["entry_price"],
            current,
            position["notional"],
            cost,
        )
        if int(position.get("observed_trading_days") or 0) >= hold_days - 1:
            closed = {
                **position,
                "exit_date": as_of,
                "exit_price": round(current, 4),
                "pnl": position["unrealized_pnl"],
                "net_return_pct": _return_pct(position["entry_price"], current, cost),
                "paper_status": "closed",
                "trade_enabled": False,
            }
            state["closed_positions"].append(closed)
            closed_today.append(closed)
        else:
            still_open.append(position)
    state["open_positions"] = still_open
    return closed_today


def _fill_pending_entries(
    state: dict[str, Any],
    *,
    as_of: str,
    open_prices: dict[str, float],
    current_prices: dict[str, float],
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not is_us_equity_session(as_of):
        # Non-session run dates must not fill entries at stale prices;
        # pending entries wait for the next session (exp-20260612-001).
        return [], []
    if not config.get("paper_enabled", True):
        return [], []
    remaining = []
    filled_today = []
    skipped_today = []
    cost = float(config["round_trip_cost_pct"])
    for entry in sorted(state["pending_entries"], key=_pending_sort_key):
        if str(entry.get("created_asof") or "")[:10] >= as_of:
            remaining.append(entry)
            continue
        ticker = str(entry.get("ticker") or "").upper()
        entry_open = open_prices.get(ticker)
        if entry_open is None:
            entry["status"] = "pending_missing_entry_open_price"
            entry["last_checked_asof"] = as_of
            remaining.append(entry)
            continue
        notional = _positive_float(entry.get("intended_notional"))
        if not notional:
            skipped = {**entry, "status": "skipped_missing_intended_notional"}
            state["skipped_entries"].append(skipped)
            skipped_today.append(skipped)
            continue
        current = current_prices.get(ticker)
        position = {
            "decision_id": entry["decision_id"],
            "sleeve": SLEEVE_NAME,
            "rule_version": RULE_VERSION,
            "ticker": ticker,
            "source_rank": entry.get("source_rank"),
            "created_asof": entry.get("created_asof"),
            "entry_date": as_of,
            "entry_price": round(entry_open, 4),
            "notional": round(notional, 2),
            "paper_shares": round(notional / entry_open, 8),
            "observed_trading_days": 0,
            "last_seen_date": as_of,
            "last_price": current,
            "trade_enabled": False,
            "paper_status": "open",
            "source_candidate": entry.get("candidate") or {},
        }
        if current is not None:
            position["unrealized_pnl"] = _pnl(entry_open, current, notional, cost)
        state["open_positions"].append(position)
        filled_today.append(position)
    state["pending_entries"] = remaining
    return filled_today, skipped_today


def _add_candidates(
    state: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    as_of: str,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    if not config.get("paper_enabled", True):
        return []
    active_count = len(state["open_positions"]) + len(state["pending_entries"])
    capacity = max(0, int(config["max_active_positions"]) - active_count)
    if capacity <= 0:
        return []
    existing = _existing_decision_ids(state)
    new_entries = []
    for candidate in sorted(candidates, key=_candidate_sort_key)[:capacity]:
        decision_id = candidate["decision_id"]
        if decision_id in existing:
            continue
        entry = {
            "decision_id": decision_id,
            "sleeve": SLEEVE_NAME,
            "ticker": candidate["ticker"],
            "source_rank": candidate.get("source_rank"),
            "created_asof": as_of,
            "status": "pending_next_session_open",
            "intended_entry_timing": "next_session_open",
            "intended_notional": candidate["intended_notional"],
            "trade_enabled": False,
            "candidate": deepcopy(candidate),
        }
        state["pending_entries"].append(entry)
        new_entries.append(entry)
        existing.add(decision_id)
    return new_entries


def _snapshot_payload(
    state: dict[str, Any],
    *,
    as_of: str,
    config: dict[str, Any],
    data_source: dict[str, Any],
    candidates: list[dict[str, Any]],
    new_pending: list[dict[str, Any]],
    filled_today: list[dict[str, Any]],
    closed_today: list[dict[str, Any]],
    skipped_today: list[dict[str, Any]],
) -> dict[str, Any]:
    closed = [row for row in state["closed_positions"] if isinstance(row, dict)]
    open_positions = [row for row in state["open_positions"] if isinstance(row, dict)]
    realized = round(sum(_money(row.get("pnl")) for row in closed), 2)
    unrealized = round(sum(_money(row.get("unrealized_pnl")) for row in open_positions), 2)
    gate = _forward_paper_gate(closed, config)
    replacement_value_report = build_broad_market_replacement_value_report(
        candidates=candidates,
        pending_entries=state["pending_entries"],
        open_positions=open_positions,
        closed_positions=closed,
        skipped_entries=state["skipped_entries"],
        config=config,
    )
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "asof_date": as_of,
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": bool(config.get("paper_enabled", True)),
        "trade_enabled": False,
        "trade_enabled_reason": "default_off_until_forward_gate_and_live_adapter_pass",
        "candidate_count": len(candidates),
        "new_pending_count": len(new_pending),
        "filled_count": len(filled_today),
        "closed_count_today": len(closed_today),
        "skipped_count_today": len(skipped_today),
        "pending_count": len(state["pending_entries"]),
        "open_position_count": len(open_positions),
        "closed_position_count": len(closed),
        "realized_pnl_to_date": realized,
        "unrealized_pnl": unrealized,
        "ticker_summary": _ticker_summary(closed, open_positions, candidates),
        "replacement_value_report": replacement_value_report,
        "parameters": dict(config),
        "data_source": {
            "status": data_source.get("status"),
            "path": data_source.get("path"),
            "rule_version": data_source.get("rule_version"),
            "ticker_count": len(data_source.get("tickers") or []),
            "excluded_count": data_source.get("excluded_count"),
        },
        "candidates": deepcopy(candidates),
        "new_pending_entries": deepcopy(new_pending),
        "filled_entries": deepcopy(filled_today),
        "closed_positions_today": deepcopy(closed_today),
        "closed_positions": deepcopy(closed),
        "skipped_entries_today": deepcopy(skipped_today),
        "pending_entries": deepcopy(state["pending_entries"]),
        "open_positions": deepcopy(open_positions),
        "forward_paper_gate": gate,
        "production_impact": _production_impact(),
        "next_action": "paper_observe_forward_outcomes_only_no_orders",
    }


def _forward_paper_gate(
    closed_positions: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    realized = round(sum(_money(row.get("pnl")) for row in closed_positions), 2)
    wins = sum(1 for row in closed_positions if _money(row.get("pnl")) > 0)
    win_rate = round(wins / len(closed_positions), 4) if closed_positions else None
    single_share = _single_ticker_positive_share(closed_positions)
    top5_share = _top5_positive_share(closed_positions)
    checks = {
        "min_closed_trades": len(closed_positions) >= int(config["forward_gate_min_closed_trades"]),
        "positive_net_pnl": realized > 0
        if config.get("forward_gate_positive_net_pnl", True)
        else True,
        "min_win_rate": win_rate is not None
        and win_rate >= float(config["forward_gate_min_win_rate"]),
        "max_single_ticker_positive_share": single_share is not None
        and single_share <= float(config["forward_gate_max_single_ticker_positive_share"]),
        "max_top5_positive_share": top5_share is not None
        and top5_share <= float(config["forward_gate_max_top5_positive_share"]),
    }
    reasons = [name for name, passed in checks.items() if not passed]
    return {
        "passed": not reasons,
        "status": "passed" if not reasons else "blocked",
        "reasons": reasons,
        "checks": checks,
        "metrics": {
            "closed_trades": len(closed_positions),
            "realized_pnl": realized,
            "win_rate": win_rate,
            "single_ticker_positive_share": single_share,
            "top5_positive_share": top5_share,
        },
        "trade_enabled_after_gate": False,
    }


def build_broad_market_replacement_value_report(
    *,
    candidates: list[dict[str, Any]],
    pending_entries: list[dict[str, Any]],
    open_positions: list[dict[str, Any]],
    closed_positions: list[dict[str, Any]],
    skipped_entries: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = _config(config)
    closed = [row for row in closed_positions or [] if isinstance(row, dict)]
    open_rows = [row for row in open_positions or [] if isinstance(row, dict)]
    pending = [row for row in pending_entries or [] if isinstance(row, dict)]
    skipped = [row for row in skipped_entries or [] if isinstance(row, dict)]
    positive_closed = [row for row in closed if _money(row.get("pnl")) > 0.0]
    positive_pnl = round(sum(_money(row.get("pnl")) for row in positive_closed), 2)
    by_ticker: dict[str, dict[str, Any]] = {}
    for bucket, rows in (
        ("candidate", candidates or []),
        ("pending", pending),
        ("open", open_rows),
        ("closed", closed),
        ("skipped", skipped),
    ):
        for row in rows:
            ticker = str(row.get("ticker") or "").upper()
            if not ticker and isinstance(row.get("candidate"), dict):
                ticker = str(row["candidate"].get("ticker") or "").upper()
            if not ticker:
                continue
            rec = by_ticker.setdefault(
                ticker,
                {
                    "candidate_count": 0,
                    "pending_count": 0,
                    "open_count": 0,
                    "closed_count": 0,
                    "skipped_count": 0,
                    "closed_pnl": 0.0,
                    "positive_closed_pnl": 0.0,
                },
            )
            rec[f"{bucket}_count"] += 1
            if bucket == "closed":
                pnl = _money(row.get("pnl"))
                rec["closed_pnl"] = round(float(rec["closed_pnl"]) + pnl, 2)
                if pnl > 0:
                    rec["positive_closed_pnl"] = round(
                        float(rec["positive_closed_pnl"]) + pnl,
                        2,
                    )
    for rec in by_ticker.values():
        rec["positive_pnl_share"] = (
            round(float(rec["positive_closed_pnl"]) / positive_pnl, 4)
            if positive_pnl > 0
            else None
        )
    top_positive_share = (
        max(
            (
                float(row.get("positive_pnl_share") or 0.0)
                for row in by_ticker.values()
            ),
            default=0.0,
        )
        if positive_pnl > 0
        else None
    )
    return {
        "schema_version": 1,
        "rule_version": REPLACEMENT_VALUE_RULE_VERSION,
        "read_only": True,
        "forward_outcome_horizon_days": int(cfg["hold_days"]),
        "displaced_resource_default": "paper_cash_slot",
        "candidate_count": len(candidates or []),
        "pending_count": len(pending),
        "open_count": len(open_rows),
        "closed_count": len(closed),
        "skipped_count": len(skipped),
        "closed_pnl": round(sum(_money(row.get("pnl")) for row in closed), 2),
        "open_unrealized_pnl": round(
            sum(_money(row.get("unrealized_pnl")) for row in open_rows),
            2,
        ),
        "positive_closed_pnl": positive_pnl,
        "top_ticker_positive_pnl_share": top_positive_share,
        "by_ticker": dict(sorted(by_ticker.items())),
        "promotion_blockers": [
            blocker
            for blocker in (
                "needs_closed_forward_outcomes"
                if len(closed) < int(cfg["forward_gate_min_closed_trades"])
                else None,
                "needs_replacement_value_vs_core_or_cash",
            )
            if blocker
        ],
        "trade_enabled": False,
        "alters_orders": False,
    }


def _normalise_candidate_universe(value: dict[str, Any] | list[str] | None) -> dict[str, Any]:
    if value is None:
        return load_broad_market_candidate_universe()
    if isinstance(value, list):
        return {
            "status": "provided",
            "path": None,
            "tickers": sorted({str(item).upper() for item in value if item}),
            "records": {},
        }
    if isinstance(value, dict):
        records = value.get("records") if isinstance(value.get("records"), dict) else {}
        tickers = set(str(item).upper() for item in value.get("tickers") or [] if item)
        tickers.update(str(key).upper() for key in records)
        return {
            "status": value.get("status") or "provided",
            "path": value.get("path"),
            "rule_version": value.get("rule_version"),
            "excluded_count": value.get("excluded_count"),
            "tickers": sorted(tickers),
            "records": {
                str(key).upper(): dict(row or {})
                for key, row in records.items()
                if key
            },
        }
    return {"status": "invalid", "path": None, "tickers": [], "records": {}}


def _normalise_state(state: dict[str, Any]) -> None:
    state.setdefault("schema_version", STATE_SCHEMA_VERSION)
    state.setdefault("sleeve", SLEEVE_NAME)
    state.setdefault("pending_entries", [])
    state.setdefault("open_positions", [])
    state.setdefault("closed_positions", [])
    state.setdefault("skipped_entries", [])


def _config(config: dict[str, Any] | None) -> dict[str, Any]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    cfg["enabled"] = False
    cfg["trade_enabled"] = False
    return cfg


def _normalise_ohlcv_rows(data: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if data is None:
        return rows
    if hasattr(data, "iterrows"):
        for idx, row in data.iterrows():
            date_value = row.get("Date", idx)
            rows.append(
                {
                    "date": _date10(date_value),
                    "open": _float_or_none(row.get("Open")),
                    "high": _float_or_none(row.get("High")),
                    "low": _float_or_none(row.get("Low")),
                    "close": _float_or_none(row.get("Close")),
                    "volume": _float_or_none(row.get("Volume")),
                }
            )
    elif isinstance(data, list):
        for raw in data:
            if not isinstance(raw, dict):
                continue
            rows.append(
                {
                    "date": _date10(raw.get("Date") or raw.get("date")),
                    "open": _float_or_none(raw.get("Open") or raw.get("open")),
                    "high": _float_or_none(raw.get("High") or raw.get("high")),
                    "low": _float_or_none(raw.get("Low") or raw.get("low")),
                    "close": _float_or_none(raw.get("Close") or raw.get("close")),
                    "volume": _float_or_none(raw.get("Volume") or raw.get("volume")),
                }
            )
    return sorted(
        [row for row in rows if row.get("date") and row.get("close") is not None],
        key=lambda row: row["date"],
    )


def _normalise_prices(prices: dict[str, Any] | None) -> dict[str, float]:
    out: dict[str, float] = {}
    for ticker, value in (prices or {}).items():
        parsed = _positive_float(value)
        if parsed is not None:
            out[str(ticker).upper()] = parsed
    return out


def _exact_asof_price_maps(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    *,
    as_of: str,
    current_prices: dict[str, Any] | None,
    open_prices: dict[str, Any] | None,
) -> tuple[dict[str, float], dict[str, float]]:
    exact_current = {
        ticker: rows[idx]["close"]
        for ticker, rows in rows_by_ticker.items()
        for idx in [_index_on_date(rows, as_of)]
        if idx is not None and _positive_float(rows[idx].get("close")) is not None
    }
    exact_opens = {
        ticker: rows[idx]["open"]
        for ticker, rows in rows_by_ticker.items()
        for idx in [_index_on_date(rows, as_of)]
        if idx is not None and _positive_float(rows[idx].get("open")) is not None
    }
    provided_current = _normalise_prices(current_prices)
    provided_opens = _normalise_prices(open_prices)
    current = {
        **exact_current,
        **{
            ticker: value
            for ticker, value in provided_current.items()
            if ticker in exact_current
        },
    }
    opens = {
        **exact_opens,
        **{
            ticker: value
            for ticker, value in provided_opens.items()
            if ticker in exact_opens
        },
    }
    return current, opens


def _date_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {str(row.get("date") or "")[:10]: idx for idx, row in enumerate(rows)}


def _index_on_date(rows: list[dict[str, Any]], as_of: str) -> int | None:
    return _date_index(rows).get(_date10(as_of))


def _latest_index_on_or_before(rows: list[dict[str, Any]], as_of: str) -> int | None:
    matches = [
        idx
        for idx, row in enumerate(rows or [])
        if str(row.get("date") or "")[:10] <= str(as_of)[:10]
    ]
    return max(matches) if matches else None


def _excluded_title(title: Any) -> bool:
    upper = f" {str(title or '').upper()} "
    return any(keyword in upper for keyword in TITLE_EXCLUSION_KEYWORDS)


def _excluded_candidate_record(record: dict[str, Any]) -> bool:
    if _excluded_title(record.get("title")):
        return True
    if record.get("broad_market_excluded") is True:
        return True
    ticker = str(record.get("ticker") or "").upper()
    if ticker in BROAD_MARKET_FEED_EXCLUDED_TICKERS:
        return True
    status = str(record.get("status") or "").lower()
    if status == "quarantine":
        return True
    theme_segment = str(record.get("theme_segment") or "").lower()
    theme = str(record.get("theme") or "").lower()
    return any(
        token in f"{theme_segment} {theme}"
        for token in ("theme_beta_benchmark", "benchmark_etf", "space_theme_etf")
    )


def _broad_market_feed_exclusion_reasons(
    ticker: str,
    record: dict[str, Any],
    *,
    as_of: Any,
    tradeable: set[str],
) -> list[str]:
    reasons: list[str] = []
    if ticker in tradeable:
        reasons.append("already_tradeable")
    if ticker in {"SPY", "QQQ"}:
        reasons.append("benchmark")
    if _excluded_candidate_record(record):
        reasons.append("record_exclusion")
    status = str(record.get("status") or "").lower()
    if status and status not in {"research", "specialist"}:
        reasons.append(f"status_{status}")
    eligible_as_of = str(record.get("eligible_as_of") or "")[:10]
    if as_of and eligible_as_of and eligible_as_of > str(as_of)[:10]:
        reasons.append("not_yet_eligible")
    return reasons


def _existing_decision_ids(state: dict[str, Any]) -> set[str]:
    ids = set()
    for bucket in ("pending_entries", "open_positions", "closed_positions", "skipped_entries"):
        ids.update(
            str(item.get("decision_id"))
            for item in state.get(bucket, [])
            if isinstance(item, dict) and item.get("decision_id")
        )
    return ids


def _pending_sort_key(entry: dict[str, Any]) -> tuple[str, int, str]:
    return (
        str(entry.get("created_asof") or ""),
        int(entry.get("source_rank") or 99),
        str(entry.get("ticker") or ""),
    )


def _candidate_sort_key(candidate: dict[str, Any]) -> tuple[int, str]:
    return (int(candidate.get("source_rank") or 99), str(candidate.get("ticker") or ""))


def _ticker_summary(
    closed: list[dict[str, Any]],
    open_positions: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in candidates:
        ticker = str(row.get("ticker") or "").upper()
        rec = out.setdefault(ticker, {"candidate_count": 0, "open_count": 0, "closed_count": 0, "pnl": 0.0})
        rec["candidate_count"] += 1
    for row in open_positions:
        ticker = str(row.get("ticker") or "").upper()
        rec = out.setdefault(ticker, {"candidate_count": 0, "open_count": 0, "closed_count": 0, "pnl": 0.0})
        rec["open_count"] += 1
    for row in closed:
        ticker = str(row.get("ticker") or "").upper()
        rec = out.setdefault(ticker, {"candidate_count": 0, "open_count": 0, "closed_count": 0, "pnl": 0.0})
        rec["closed_count"] += 1
        rec["pnl"] = round(rec["pnl"] + _money(row.get("pnl")), 2)
    return dict(sorted(out.items()))


def _single_ticker_positive_share(rows: list[dict[str, Any]]) -> float | None:
    by_ticker: dict[str, float] = {}
    total = 0.0
    for row in rows:
        pnl = _money(row.get("pnl"))
        if pnl <= 0:
            continue
        ticker = str(row.get("ticker") or "").upper()
        by_ticker[ticker] = round(by_ticker.get(ticker, 0.0) + pnl, 2)
        total += pnl
    if total <= 0 or not by_ticker:
        return None
    return round(max(by_ticker.values()) / total, 4)


def _top5_positive_share(rows: list[dict[str, Any]]) -> float | None:
    by_ticker: dict[str, float] = {}
    total = 0.0
    for row in rows:
        pnl = _money(row.get("pnl"))
        if pnl <= 0:
            continue
        ticker = str(row.get("ticker") or "").upper()
        by_ticker[ticker] = round(by_ticker.get(ticker, 0.0) + pnl, 2)
        total += pnl
    if total <= 0 or not by_ticker:
        return None
    return round(sum(sorted(by_ticker.values(), reverse=True)[:5]) / total, 4)


def _pnl(entry_price: Any, exit_price: Any, notional: Any, cost: float) -> float:
    entry = _positive_float(entry_price)
    exit_ = _positive_float(exit_price)
    amount = _positive_float(notional)
    if not entry or not exit_ or not amount:
        return 0.0
    return round(amount * (exit_ / entry - 1.0 - cost), 2)


def _return_pct(entry_price: Any, exit_price: Any, cost: float) -> float | None:
    entry = _positive_float(entry_price)
    exit_ = _positive_float(exit_price)
    if not entry or not exit_:
        return None
    return round(exit_ / entry - 1.0 - cost, 6)


def _date10(value: Any) -> str:
    if hasattr(value, "date"):
        try:
            return value.date().isoformat()
        except Exception:
            pass
    return str(value or "")[:10]


def _float_or_none(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def _positive_float(value: Any) -> float | None:
    parsed = _float_or_none(value)
    return parsed if parsed is not None and parsed > 0 else None


def _money(value: Any) -> float:
    parsed = _float_or_none(value)
    return round(parsed or 0.0, 2)


def _production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": True,
        "run_adapter_changed": True,
        "backtester_adapter_changed": False,
        "parity_test_added": True,
        "replay_only": False,
        "default_off_paper_only": True,
        "production_signal_path_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "trade_enabled": False,
        "scope": "default_off_broad_market_leadership_paper_attribution",
    }
