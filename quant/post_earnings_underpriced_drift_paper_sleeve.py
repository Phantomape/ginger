"""Default-off post-earnings underpriced drift paper sleeve.

This shared helper promotes the exp-20260602-023 replay lead into a
production-visible forward observation boundary. It emits paper candidates and
ledger state only; it never emits live orders and never changes core signal
generation, ranking, sizing, exits, heat, LLM, or news behavior.
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_QUANT_DIR = Path(__file__).resolve().parent
if str(_QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(_QUANT_DIR))

try:
    from constants import ROUND_TRIP_COST_PCT
    from data_paths import daily_artifact_glob, data_artifact_path
    from fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage
    from volume_breadth_breakout_paper_sleeve import (
        _close_location_value,
        _close_return,
        _date10,
        _exact_asof_price_maps,
        _float_or_none,
        _index_on_date,
        _money,
        _normalise_candidate_universe,
        _normalise_ohlcv_rows,
        _pnl,
        _positive_float,
        _prior_average,
        _return_pct,
        _round,
        _safe,
        _single_ticker_positive_share,
        _top5_positive_share,
    )
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.data_paths import daily_artifact_glob, data_artifact_path
    from quant.fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage
    from quant.volume_breadth_breakout_paper_sleeve import (
        _close_location_value,
        _close_return,
        _date10,
        _exact_asof_price_maps,
        _float_or_none,
        _index_on_date,
        _money,
        _normalise_candidate_universe,
        _normalise_ohlcv_rows,
        _pnl,
        _positive_float,
        _prior_average,
        _return_pct,
        _round,
        _safe,
        _single_ticker_positive_share,
        _top5_positive_share,
    )


SLEEVE_NAME = "POST_EARNINGS_UNDERPRICED_DRIFT_PAPER"
RULE_VERSION = "post_earnings_underpriced_drift_shared_adapter_v1"
SOURCE_RULE_VERSION = "post_earnings_positive_surprise_pre_event_underpriced_v1"
POSITIVE_SURPRISE_RULE_VERSION = "post_earnings_positive_surprise_drift_v1"
REPLACEMENT_VALUE_RULE_VERSION = "post_earnings_underpriced_forward_replacement_value_v1"
HIGH_LIQUIDITY_SUPPORT_RULE_VERSION = "post_earnings_underpriced_high_liquidity_support_v1"
SECTOR_RESIDUAL_SUPPORT_RULE_VERSION = "post_earnings_sector_residual_support_v1"
NON_CORE_OVERLAP_SUPPORT_RULE_VERSION = "post_earnings_non_same_day_core_overlap_support_v1"
STATE_SCHEMA_VERSION = 1

DEFAULT_STATE_PATH = data_artifact_path("post_earnings_underpriced_drift_paper_state")
DEFAULT_SNAPSHOT_LOG_PATH = data_artifact_path("post_earnings_underpriced_drift_paper_snapshots")
DEFAULT_SECTOR_MAP_PATH = (
    _QUANT_DIR.parent / "data" / "reference" / "broad_market_sector_map.json"
)

EXCLUDED_TICKERS = {
    "ARKX",
    "GLD",
    "IAU",
    "IEF",
    "IWM",
    "QQQ",
    "SLV",
    "SPY",
    "TLT",
    "UFO",
    "UUP",
    "USO",
    "XLE",
    "XLP",
    "XLU",
    "XLV",
}

DEFAULT_CONFIG = {
    "enabled": False,
    "paper_enabled": True,
    "trade_enabled": False,
    "paper_notional_usd": 10_000.0,
    "recent_signal_days_min": 0,
    "recent_signal_days_max": 5,
    "min_latest_surprise_pct": 3.0,
    "min_avg_historical_surprise_pct": 0.0,
    "min_positive_surprise_count": 2,
    "min_surprise_history_count": 4,
    "min_reset_dte": 20,
    "max_pre_reset_dte": 7,
    "moving_average_days": 50,
    "relative_strength_days": 20,
    "avg_dollar_volume_days": 20,
    "min_avg_dollar_volume_20d": 40_000_000.0,
    "min_rs20_vs_spy": 0.0,
    "min_close_location": 0.55,
    "min_event_to_signal_return": 0.0,
    "min_event_to_signal_excess_vs_spy": 0.0,
    "pre_event_rs_days": 20,
    "max_pre_event_rs20_vs_spy": 0.0,
    "high_liquidity_avg_dollar_volume_20d_min": 1_000_000_000.0,
    "high_liquidity_notional_scalar": 1.10,
    "sector_residual_map_path": str(DEFAULT_SECTOR_MAP_PATH),
    "sector_residual_lookback_days": 20,
    "sector_residual_min_excess": 0.0,
    "sector_residual_min_member_returns": 3,
    "sector_residual_notional_scalar": 1.05,
    "sector_by_ticker": None,
    "core_entry_tickers_by_date": None,
    "non_core_overlap_notional_scalar": 1.05,
    "daily_entry_slots": 1,
    "max_active_positions": 5,
    "hold_days": 10,
    "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
    "forward_gate_min_closed_trades": 20,
    "forward_gate_positive_net_pnl": True,
    "forward_gate_min_win_rate": 0.50,
    "forward_gate_max_single_ticker_positive_share": 0.40,
    "forward_gate_max_top5_positive_share": 0.70,
}

_EARNINGS_INDEX_CACHE: dict[str, list[tuple[str, dict[str, Any]]]] | None = None
_EARNINGS_DATE_COUNT = 0
_SECTOR_MAP_CACHE: dict[str, str] | None = None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_post_earnings_underpriced_drift_paper_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_entries": [],
    }


def load_post_earnings_underpriced_drift_paper_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_post_earnings_underpriced_drift_paper_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_post_earnings_underpriced_drift_paper_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_post_earnings_underpriced_drift_paper_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(_safe(state), handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_post_earnings_underpriced_drift_paper_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(snapshot), sort_keys=True) + "\n")


def _sector_by_ticker(config: dict[str, Any]) -> dict[str, str]:
    supplied = config.get("sector_by_ticker")
    if isinstance(supplied, dict):
        return {
            str(ticker).upper(): str(sector)
            for ticker, sector in supplied.items()
            if ticker and sector
        }

    global _SECTOR_MAP_CACHE
    if _SECTOR_MAP_CACHE is not None:
        return _SECTOR_MAP_CACHE
    path = Path(str(config.get("sector_residual_map_path") or DEFAULT_SECTOR_MAP_PATH))
    if not path.exists():
        _SECTOR_MAP_CACHE = {}
        return _SECTOR_MAP_CACHE
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    entries = payload.get("entries") if isinstance(payload, dict) else {}
    _SECTOR_MAP_CACHE = {
        str(ticker).upper(): str(info.get("sector"))
        for ticker, info in (entries or {}).items()
        if isinstance(info, dict)
        and info.get("status") == "ok"
        and info.get("sector")
        and str(info.get("sector")).lower() not in {"none", "nan"}
    }
    return _SECTOR_MAP_CACHE


def _lookback_return_on_date(
    rows: list[dict[str, Any]],
    date_value: str,
    days: int,
) -> float | None:
    idx_by_date = _row_index(rows)
    idx = idx_by_date.get(date_value)
    if idx is None or idx < days:
        return None
    return _close_return(rows, idx - days, idx)


def _sector_residual_context(
    *,
    ticker: str,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    signal_date: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    ticker = str(ticker or "").upper()
    sector = _sector_by_ticker(config).get(ticker)
    if not sector:
        return {
            "sector_residual_context_status": "missing_sector",
            "sector_residual_support": False,
        }
    lookback_days = int(config["sector_residual_lookback_days"])
    returns: list[float] = []
    ticker_return = None
    for peer, peer_sector in _sector_by_ticker(config).items():
        if peer_sector != sector or peer not in rows_by_ticker:
            continue
        peer_return = _lookback_return_on_date(
            rows_by_ticker.get(peer) or [],
            signal_date,
            lookback_days,
        )
        if peer_return is None:
            continue
        returns.append(peer_return)
        if peer == ticker:
            ticker_return = peer_return
    if ticker_return is None:
        return {
            "sector": sector,
            "sector_residual_context_status": "missing_ticker_return",
            "sector_residual_support": False,
            "sector_residual_member_return_count": len(returns),
        }
    if len(returns) < int(config["sector_residual_min_member_returns"]):
        return {
            "sector": sector,
            "sector_residual_context_status": "sector_sample_too_small",
            "sector_residual_support": False,
            "sector_residual_ticker_return_20d": _round(ticker_return, 6),
            "sector_residual_member_return_count": len(returns),
        }
    median_return = sorted(returns)[len(returns) // 2]
    if len(returns) % 2 == 0:
        midpoint = len(returns) // 2
        median_return = (sorted(returns)[midpoint - 1] + sorted(returns)[midpoint]) / 2
    excess = ticker_return - median_return
    supported = excess >= float(config["sector_residual_min_excess"])
    return {
        "sector": sector,
        "sector_residual_context_status": "ok",
        "sector_residual_support": supported,
        "sector_residual_ticker_return_20d": _round(ticker_return, 6),
        "sector_residual_median_return_20d": _round(median_return, 6),
        "sector_residual_excess_vs_median_20d": _round(excess, 6),
        "sector_residual_member_return_count": len(returns),
    }


def _normalise_core_entry_tickers_by_date(
    value: Any,
) -> dict[str, set[str]] | None:
    if value is None or not isinstance(value, dict):
        return None
    normalised: dict[str, set[str]] = {}
    for raw_date, raw_tickers in value.items():
        date_value = _date10(str(raw_date))
        if not date_value:
            continue
        if raw_tickers is None:
            normalised[date_value] = set()
            continue
        if isinstance(raw_tickers, str):
            iterable = [raw_tickers]
        else:
            try:
                iterable = list(raw_tickers)
            except TypeError:
                iterable = []
        normalised[date_value] = {
            str(ticker).upper()
            for ticker in iterable
            if str(ticker or "").strip()
        }
    return normalised


def _non_core_overlap_context(
    *,
    ticker: str,
    signal_date: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    by_date = _normalise_core_entry_tickers_by_date(
        config.get("core_entry_tickers_by_date")
    )
    date_value = _date10(signal_date)
    ticker_value = str(ticker or "").upper()
    if by_date is None or date_value not in by_date:
        return {
            "non_core_overlap_context_status": "missing_core_overlap_context",
            "same_day_ab_entry_count": None,
            "same_day_ab_overlap": None,
            "same_ticker_ab_overlap": None,
            "non_core_overlap_support": False,
        }
    same_day_tickers = by_date.get(date_value) or set()
    same_ticker_overlap = ticker_value in same_day_tickers
    same_day_overlap = bool(same_day_tickers)
    return {
        "non_core_overlap_context_status": "ok",
        "same_day_ab_entry_count": len(same_day_tickers),
        "same_day_ab_overlap": same_day_overlap,
        "same_ticker_ab_overlap": same_ticker_overlap,
        "non_core_overlap_support": not same_day_overlap and not same_ticker_overlap,
    }


def empty_post_earnings_underpriced_drift_paper_sleeve_snapshot(
    as_of: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "asof_date": _date10(as_of),
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": False,
        "trade_enabled": False,
        "candidate_count": 0,
        "raw_candidate_count": 0,
        "rejected_candidate_count": 0,
        "new_pending_count": 0,
        "filled_count": 0,
        "closed_count_today": 0,
        "pending_count": 0,
        "open_position_count": 0,
        "closed_position_count": 0,
        "realized_pnl_to_date": 0.0,
        "unrealized_pnl": 0.0,
        "earnings_snapshot_source": {
            "status": reason,
            "dates_loaded": 0,
            "covered_ticker_count": 0,
        },
        "candidate_universe": {"status": reason, "ticker_count": 0},
        "candidate_reject_counts": {},
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "production_impact": _production_impact(),
        "error": reason,
    }


def build_post_earnings_underpriced_drift_paper_sleeve_snapshot(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any] | None = None,
    candidate_universe: dict[str, Any] | list[str] | None = None,
    earnings_index: dict[str, list[tuple[str, dict[str, Any]]]] | None = None,
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
    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    if not rows_by_ticker:
        return empty_post_earnings_underpriced_drift_paper_sleeve_snapshot(
            as_of_date,
            "missing_ohlcv",
        )

    earnings_rows = earnings_index if earnings_index is not None else load_earnings_snapshot_index()
    if not earnings_rows:
        return empty_post_earnings_underpriced_drift_paper_sleeve_snapshot(
            as_of_date,
            "missing_earnings_snapshots",
        )

    working_state = deepcopy(
        state
        if state is not None
        else load_post_earnings_underpriced_drift_paper_state(state_path)
    )
    _normalise_state(working_state)

    current, opens = _exact_asof_price_maps(
        rows_by_ticker,
        as_of=as_of_date,
        current_prices=current_prices,
        open_prices=open_prices,
    )
    benchmark_ready = _index_on_date(rows_by_ticker.get("SPY") or [], as_of_date) is not None

    closed_today: list[dict[str, Any]] = []
    filled_today: list[dict[str, Any]] = []
    skipped_today: list[dict[str, Any]] = []
    if benchmark_ready:
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

    active_tickers = {
        str(row.get("ticker") or "").upper()
        for row in working_state.get("open_positions") or []
        if isinstance(row, dict)
    }
    pending_tickers = {
        str(row.get("ticker") or "").upper()
        for row in working_state.get("pending_entries") or []
        if isinstance(row, dict)
    }
    universe = _normalise_candidate_universe(candidate_universe, rows_by_ticker)
    candidates, rejected, audit = build_post_earnings_underpriced_drift_candidates(
        as_of=as_of_date,
        ohlcv_by_ticker=rows_by_ticker,
        candidate_universe=universe,
        earnings_index=earnings_rows,
        open_position_tickers=active_tickers,
        pending_tickers=pending_tickers,
        config=cfg,
    )
    raw_candidates = list(candidates)
    candidates = candidates[: int(cfg["daily_entry_slots"])]
    for candidate in raw_candidates[len(candidates):]:
        rejected.append({**candidate, "reasons": ["daily_top1_or_capacity_limit"]})
    high_liquidity_support = {
        "rule_version": HIGH_LIQUIDITY_SUPPORT_RULE_VERSION,
        "avg_dollar_volume_20d_min": float(
            cfg["high_liquidity_avg_dollar_volume_20d_min"]
        ),
        "notional_scalar": float(cfg["high_liquidity_notional_scalar"]),
        "supported_candidate_count": sum(
            1 for candidate in candidates if candidate.get("high_liquidity_support")
        ),
        "supported_raw_candidate_count": sum(
            1 for candidate in raw_candidates if candidate.get("high_liquidity_support")
        ),
        "trade_enabled": False,
        "alters_orders": False,
    }
    sector_residual_support = {
        "rule_version": SECTOR_RESIDUAL_SUPPORT_RULE_VERSION,
        "sector_map_path": str(cfg.get("sector_residual_map_path") or ""),
        "lookback_days": int(cfg["sector_residual_lookback_days"]),
        "min_excess": float(cfg["sector_residual_min_excess"]),
        "min_member_returns": int(cfg["sector_residual_min_member_returns"]),
        "notional_scalar": float(cfg["sector_residual_notional_scalar"]),
        "supported_candidate_count": sum(
            1 for candidate in candidates if candidate.get("sector_residual_support")
        ),
        "supported_raw_candidate_count": sum(
            1 for candidate in raw_candidates if candidate.get("sector_residual_support")
        ),
        "context_status_counts": dict(
            sorted(
                Counter(
                    str(candidate.get("sector_residual_context_status") or "unknown")
                    for candidate in raw_candidates
                ).items()
            )
        ),
        "trade_enabled": False,
        "alters_orders": False,
    }
    non_core_overlap_support = {
        "rule_version": NON_CORE_OVERLAP_SUPPORT_RULE_VERSION,
        "notional_scalar": float(cfg["non_core_overlap_notional_scalar"]),
        "supported_candidate_count": sum(
            1 for candidate in candidates if candidate.get("non_core_overlap_support")
        ),
        "supported_raw_candidate_count": sum(
            1 for candidate in raw_candidates if candidate.get("non_core_overlap_support")
        ),
        "context_status_counts": dict(
            sorted(
                Counter(
                    str(candidate.get("non_core_overlap_context_status") or "unknown")
                    for candidate in raw_candidates
                ).items()
            )
        ),
        "trade_enabled": False,
        "alters_orders": False,
    }

    open_positions = working_state.get("open_positions") or []
    room = max(0, int(cfg["max_active_positions"]) - len(open_positions))
    new_pending: list[dict[str, Any]] = []
    if room > 0 and cfg.get("paper_enabled", True):
        for candidate in candidates[:room]:
            entry = _pending_entry_from_candidate(candidate, as_of=as_of_date, config=cfg)
            working_state["pending_entries"].append(entry)
            new_pending.append(entry)

    closed = working_state.get("closed_positions") or []
    open_positions = working_state.get("open_positions") or []
    gate = _forward_paper_gate(closed, cfg)
    replacement_value_report = build_post_earnings_underpriced_drift_replacement_value_report(
        candidates=candidates,
        pending_entries=working_state.get("pending_entries") or [],
        open_positions=open_positions,
        closed_positions=closed,
        skipped_entries=working_state.get("skipped_entries") or [],
        config=cfg,
    )

    snapshot = {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "positive_surprise_rule_version": POSITIVE_SURPRISE_RULE_VERSION,
        "replacement_value_rule_version": REPLACEMENT_VALUE_RULE_VERSION,
        "asof_date": as_of_date,
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": bool(cfg.get("paper_enabled", True)),
        "trade_enabled": False,
        "trade_enabled_reason": "default_off_until_forward_gate_and_live_adapter_pass",
        "candidate_count": len(candidates),
        "raw_candidate_count": len(raw_candidates),
        "rejected_candidate_count": len(rejected),
        "new_pending_count": len(new_pending),
        "filled_count": len(filled_today),
        "closed_count_today": len(closed_today),
        "pending_count": len(working_state.get("pending_entries") or []),
        "open_position_count": len(open_positions),
        "closed_position_count": len(closed),
        "realized_pnl_to_date": round(sum(_money(row.get("pnl")) for row in closed), 2),
        "unrealized_pnl": round(sum(_money(row.get("unrealized_pnl")) for row in open_positions), 2),
        "earnings_snapshot_source": {
            "status": "provided" if earnings_index is not None else "local_daily_snapshots",
            "dates_loaded": audit.get("earnings_snapshot_dates_loaded"),
            "covered_ticker_count": len(earnings_rows),
            "source": "data/daily/snapshots/earnings/earnings_snapshot_*.json",
            "pit_policy": "snapshot transition date must be <= signal date and present in OHLCV trading dates",
        },
        "candidate_universe": {
            "status": universe.get("status"),
            "ticker_count": len(universe.get("tickers") or []),
        },
        "candidate_reject_counts": audit.get("audit_reject_counts") or {},
        "candidate_audit": audit,
        "high_liquidity_support": high_liquidity_support,
        "sector_residual_support": sector_residual_support,
        "non_core_overlap_support": non_core_overlap_support,
        "candidates": deepcopy(candidates),
        "raw_candidates_sample": deepcopy(raw_candidates[:10]),
        "rejected_candidates": deepcopy(rejected[:50]),
        "new_pending_entries": deepcopy(new_pending),
        "filled_entries": deepcopy(filled_today),
        "closed_positions_today": deepcopy(closed_today),
        "skipped_entries_today": deepcopy(skipped_today),
        "pending_entries": deepcopy(working_state["pending_entries"]),
        "open_positions": deepcopy(open_positions),
        "closed_positions_sample": deepcopy(closed[-20:]),
        "replacement_value_report": replacement_value_report,
        "forward_paper_gate": gate,
        "production_impact": _production_impact(),
        "notes": (
            "Default-off paper only. Positive-surprise earnings snapshot "
            "transitions and pre-event SPY-relative underpricing are surfaced "
            "for forward replacement-value evidence; live/core orders remain unchanged."
        ),
        "next_action": "paper_observe_forward_replacement_value_no_orders",
    }

    if persist:
        save_post_earnings_underpriced_drift_paper_state(working_state, state_path)
        append_post_earnings_underpriced_drift_paper_snapshot(snapshot, snapshot_log_path)
    return _safe(snapshot)


def load_earnings_snapshot_index(
    *,
    paths: list[Path | str] | None = None,
    data_dir: Path | str | None = None,
) -> dict[str, list[tuple[str, dict[str, Any]]]]:
    global _EARNINGS_DATE_COUNT, _EARNINGS_INDEX_CACHE
    if paths is None and data_dir is None and _EARNINGS_INDEX_CACHE is not None:
        return _EARNINGS_INDEX_CACHE

    by_ticker: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    dates_seen: set[str] = set()
    source_paths = [Path(path) for path in paths] if paths is not None else daily_artifact_glob("earnings_snapshot", data_dir)
    for path in source_paths:
        snap_date = _snapshot_date_from_path(path)
        if not snap_date:
            continue
        dates_seen.add(snap_date)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        earnings = payload.get("earnings") if isinstance(payload, dict) else {}
        if not isinstance(earnings, dict):
            continue
        for raw_ticker, info in earnings.items():
            if not isinstance(info, dict):
                continue
            ticker = str(raw_ticker).upper().strip()
            if ticker:
                by_ticker.setdefault(ticker, []).append((snap_date, dict(info)))

    for rows in by_ticker.values():
        rows.sort(key=lambda pair: pair[0])
    _EARNINGS_DATE_COUNT = len(dates_seen)
    if paths is None and data_dir is None:
        _EARNINGS_INDEX_CACHE = by_ticker
    return by_ticker


def build_post_earnings_underpriced_drift_candidates(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any],
    candidate_universe: dict[str, Any] | list[str] | None = None,
    earnings_index: dict[str, list[tuple[str, dict[str, Any]]]] | None = None,
    open_position_tickers: set[str] | None = None,
    pending_tickers: set[str] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    return build_post_earnings_underpriced_drift_candidates_for_dates(
        as_of_dates=[_date10(as_of)],
        ohlcv_by_ticker=ohlcv_by_ticker,
        candidate_universe=candidate_universe,
        earnings_index=earnings_index,
        open_position_tickers=open_position_tickers,
        pending_tickers=pending_tickers,
        config=config,
    )


def build_post_earnings_underpriced_drift_candidates_for_dates(
    *,
    as_of_dates: list[str],
    ohlcv_by_ticker: dict[str, Any],
    candidate_universe: dict[str, Any] | list[str] | None = None,
    earnings_index: dict[str, list[tuple[str, dict[str, Any]]]] | None = None,
    open_position_tickers: set[str] | None = None,
    pending_tickers: set[str] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    cfg = _config(config)
    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    universe = _normalise_candidate_universe(candidate_universe, rows_by_ticker)
    earnings_rows = earnings_index if earnings_index is not None else load_earnings_snapshot_index()
    trading_dates = _trading_dates(rows_by_ticker)
    trading_pos = {date_value: idx for idx, date_value in enumerate(trading_dates)}
    wanted_dates = sorted({_date10(value) for value in as_of_dates if _date10(value) in trading_pos})
    wanted_set = set(wanted_dates)
    active = {str(value).upper() for value in (open_position_tickers or set())}
    pending = {str(value).upper() for value in (pending_tickers or set())}
    spy_rows = rows_by_ticker.get("SPY") or []
    spy_index = _row_index(spy_rows)
    min_idx = max(
        int(cfg["moving_average_days"]),
        int(cfg["relative_strength_days"]),
        int(cfg["avg_dollar_volume_days"]),
    )

    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    audit: Counter[str] = Counter()
    event_count = 0

    for ticker in sorted(set(universe.get("tickers") or []).intersection(rows_by_ticker).difference(EXCLUDED_TICKERS)):
        rows = rows_by_ticker.get(ticker) or []
        idx_by_date = _row_index(rows)
        events = _positive_surprise_events(
            ticker=ticker,
            earnings_index=earnings_rows,
            trading_dates=trading_dates,
            config=cfg,
        )
        event_count += len(events)
        for event in events:
            event_date = str(event["event_confirmed_date"])
            event_trade_pos = trading_pos.get(event_date)
            event_idx = idx_by_date.get(event_date)
            event_spy_idx = spy_index.get(event_date)
            if event_trade_pos is None or event_idx is None or event_spy_idx is None:
                audit["missing_event_ohlcv"] += 1
                continue
            if event_idx <= 0 or event_spy_idx <= 0:
                audit["missing_event_prior_close"] += 1
                continue

            admitted_event = False
            for offset in range(
                int(cfg["recent_signal_days_min"]),
                int(cfg["recent_signal_days_max"]) + 1,
            ):
                signal_pos = event_trade_pos + offset
                if signal_pos >= len(trading_dates):
                    audit["signal_window_out_of_range"] += 1
                    continue
                signal_date = trading_dates[signal_pos]
                if signal_date not in wanted_set:
                    continue
                idx = idx_by_date.get(signal_date)
                spy_idx = spy_index.get(signal_date)
                if idx is None or spy_idx is None or idx < min_idx or spy_idx < int(cfg["relative_strength_days"]):
                    audit["insufficient_ohlcv_history"] += 1
                    continue

                candidate = _candidate_from_event(
                    ticker=ticker,
                    rows_by_ticker=rows_by_ticker,
                    rows=rows,
                    spy_rows=spy_rows,
                    idx=idx,
                    spy_idx=spy_idx,
                    event=event,
                    event_idx=event_idx,
                    event_spy_idx=event_spy_idx,
                    signal_date=signal_date,
                    offset=offset,
                    config=cfg,
                    audit=audit,
                )
                if candidate is None:
                    continue
                if ticker in active:
                    rejected.append({**candidate, "reasons": ["already_open_in_post_earnings_underpriced_paper"]})
                    admitted_event = True
                    break
                if ticker in pending:
                    rejected.append({**candidate, "reasons": ["already_pending_in_post_earnings_underpriced_paper"]})
                    admitted_event = True
                    break
                candidates.append(candidate)
                admitted_event = True
                break
            if not admitted_event and any(
                event_trade_pos + offset < len(trading_dates)
                and trading_dates[event_trade_pos + offset] in wanted_set
                for offset in range(int(cfg["recent_signal_days_min"]), int(cfg["recent_signal_days_max"]) + 1)
            ):
                audit["event_without_qualifying_drift_signal"] += 1

    candidates.sort(key=_candidate_sort_key)
    for rank, candidate in enumerate(candidates, start=1):
        candidate["post_earnings_underpriced_rank_on_signal_date"] = rank
        candidate["max_paper_trades_per_day"] = int(cfg["daily_entry_slots"])
    return candidates, rejected, {
        "dates_checked": len(wanted_dates),
        "positive_surprise_event_count": event_count,
        "candidate_count": len(candidates),
        "candidate_days": len({row["date"] for row in candidates}),
        "unique_candidate_tickers": len({row["ticker"] for row in candidates}),
        "earnings_snapshot_dates_loaded": _EARNINGS_DATE_COUNT if earnings_index is None else _earnings_date_count(earnings_rows),
        "audit_reject_counts": dict(sorted(audit.items())),
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "earnings_snapshot_source": "data/daily/snapshots/earnings/earnings_snapshot_*.json",
        "known_at": "after_earnings_snapshot_transition_and_signal_date_close_before_next_open_paper_entry",
    }


def build_post_earnings_underpriced_drift_replacement_value_report(
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
    pending_rows = [row for row in pending_entries or [] if isinstance(row, dict)]
    skipped = [row for row in skipped_entries or [] if isinstance(row, dict)]
    positive_closed = [row for row in closed if _money(row.get("pnl")) > 0.0]
    positive_pnl = round(sum(_money(row.get("pnl")) for row in positive_closed), 2)
    by_ticker: dict[str, dict[str, Any]] = {}
    for bucket, rows in (
        ("candidate", candidates or []),
        ("pending", pending_rows),
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
                    rec["positive_closed_pnl"] = round(float(rec["positive_closed_pnl"]) + pnl, 2)
    for rec in by_ticker.values():
        rec["positive_pnl_share"] = (
            round(float(rec["positive_closed_pnl"]) / positive_pnl, 4)
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
        "pending_count": len(pending_rows),
        "open_count": len(open_rows),
        "closed_count": len(closed),
        "skipped_count": len(skipped),
        "closed_pnl": round(sum(_money(row.get("pnl")) for row in closed), 2),
        "open_unrealized_pnl": round(sum(_money(row.get("unrealized_pnl")) for row in open_rows), 2),
        "positive_closed_pnl": positive_pnl,
        "top_ticker_positive_pnl_share": _single_ticker_positive_share(closed),
        "top5_positive_pnl_share": _top5_positive_share(closed),
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


def _candidate_from_event(
    *,
    ticker: str,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    rows: list[dict[str, Any]],
    spy_rows: list[dict[str, Any]],
    idx: int,
    spy_idx: int,
    event: dict[str, Any],
    event_idx: int,
    event_spy_idx: int,
    signal_date: str,
    offset: int,
    config: dict[str, Any],
    audit: Counter[str],
) -> dict[str, Any] | None:
    close = _positive_float(rows[idx].get("close"))
    high = _positive_float(rows[idx].get("high"))
    low = _positive_float(rows[idx].get("low"))
    volume = _positive_float(rows[idx].get("volume"))
    if not close or volume is None:
        audit["missing_close_or_volume"] += 1
        return None
    avg_dollar_volume = _avg_dollar_volume(rows, idx, int(config["avg_dollar_volume_days"]))
    if avg_dollar_volume is None:
        audit["missing_avg_dollar_volume"] += 1
        return None
    if avg_dollar_volume < float(config["min_avg_dollar_volume_20d"]):
        audit["low_avg_dollar_volume"] += 1
        return None

    ma50 = _prior_average(rows, idx, int(config["moving_average_days"]), "close")
    if ma50 is None or close <= ma50:
        audit["below_50d_trend"] += 1
        return None
    close_location = _close_location_value(close=close, high=high, low=low)
    if close_location is None or close_location < float(config["min_close_location"]):
        audit["weak_close_location"] += 1
        return None

    ret_days = int(config["relative_strength_days"])
    ret20 = _close_return(rows, idx - ret_days, idx)
    spy_ret20 = _close_return(spy_rows, spy_idx - ret_days, spy_idx)
    if ret20 is None or spy_ret20 is None:
        audit["missing_relative_strength"] += 1
        return None
    rs20_vs_spy = ret20 - spy_ret20
    if rs20_vs_spy <= float(config["min_rs20_vs_spy"]):
        audit["rs20_not_positive_vs_spy"] += 1
        return None

    event_to_signal_return = _close_return(rows, event_idx - 1, idx)
    spy_event_to_signal_return = _close_return(spy_rows, event_spy_idx - 1, spy_idx)
    if event_to_signal_return is None or spy_event_to_signal_return is None:
        audit["missing_event_to_signal_return"] += 1
        return None
    event_to_signal_excess = event_to_signal_return - spy_event_to_signal_return
    if event_to_signal_return < float(config["min_event_to_signal_return"]):
        audit["negative_event_to_signal_return"] += 1
        return None
    if event_to_signal_excess < float(config["min_event_to_signal_excess_vs_spy"]):
        audit["negative_event_to_signal_excess_vs_spy"] += 1
        return None

    pre_event_ret20, pre_event_spy_ret20, pre_event_rs = _pre_event_rs20_vs_spy(
        rows=rows,
        spy_rows=spy_rows,
        event_date=str(event["event_confirmed_date"]),
        days=int(config["pre_event_rs_days"]),
    )
    if pre_event_ret20 is None or pre_event_spy_ret20 is None or pre_event_rs is None:
        audit["missing_pre_event_rs20_context"] += 1
        return None
    if pre_event_rs > float(config["max_pre_event_rs20_vs_spy"]):
        audit["pre_event_rs20_outperformed_spy"] += 1
        return None

    score = (
        (float(event["latest_surprise_pct"]) / 100.0)
        + (float(event["avg_historical_surprise_pct"]) / 200.0)
        + event_to_signal_excess
        + rs20_vs_spy
        + (close_location / 10.0)
    )
    base_notional = float(config["paper_notional_usd"])
    high_liquidity_supported = avg_dollar_volume >= float(
        config["high_liquidity_avg_dollar_volume_20d_min"]
    )
    high_liquidity_scalar = (
        float(config["high_liquidity_notional_scalar"])
        if high_liquidity_supported
        else 1.0
    )
    sector_context = _sector_residual_context(
        ticker=ticker,
        rows_by_ticker=rows_by_ticker,
        signal_date=signal_date,
        config=config,
    )
    audit[
        "sector_residual_context_"
        + str(sector_context.get("sector_residual_context_status") or "unknown")
    ] += 1
    sector_residual_supported = bool(sector_context.get("sector_residual_support"))
    sector_residual_scalar = (
        float(config["sector_residual_notional_scalar"])
        if sector_residual_supported
        else 1.0
    )
    non_core_context = _non_core_overlap_context(
        ticker=ticker,
        signal_date=signal_date,
        config=config,
    )
    audit[
        "non_core_overlap_context_"
        + str(non_core_context.get("non_core_overlap_context_status") or "unknown")
    ] += 1
    non_core_overlap_supported = bool(
        non_core_context.get("non_core_overlap_support")
    )
    non_core_overlap_scalar = (
        float(config["non_core_overlap_notional_scalar"])
        if non_core_overlap_supported
        else 1.0
    )
    pre_sector_residual_notional = base_notional * high_liquidity_scalar
    pre_non_core_overlap_notional = (
        pre_sector_residual_notional * sector_residual_scalar
    )
    intended_notional = pre_non_core_overlap_notional * non_core_overlap_scalar
    return {
        "sleeve": SLEEVE_NAME,
        "ticker": ticker,
        "date": signal_date,
        "strategy": "post_earnings_pre_event_underpriced_drift",
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "positive_surprise_rule_version": POSITIVE_SURPRISE_RULE_VERSION,
        "close": _round(close, 4),
        "volume": _round(volume, 2),
        "avg_dollar_volume_20d": _round(avg_dollar_volume, 2),
        "ma50": _round(ma50, 4),
        "close_location": _round(close_location, 6),
        "ret20": _round(ret20, 6),
        "spy_ret20": _round(spy_ret20, 6),
        "rs20_vs_spy": _round(rs20_vs_spy, 6),
        "event_confirmed_date": event["event_confirmed_date"],
        "recent_signal_trading_day_offset": offset,
        "latest_surprise_pct": _round(event["latest_surprise_pct"], 6),
        "avg_historical_surprise_pct": _round(event["avg_historical_surprise_pct"], 6),
        "historical_surprise_count": event["historical_surprise_count"],
        "positive_historical_surprise_count": event["positive_historical_surprise_count"],
        "eps_actual_last": _round(event.get("eps_actual_last"), 6),
        "days_to_next_earnings_after_event": int(event["days_to_next_earnings_after_event"]),
        "earnings_snapshot_source_date": event["earnings_snapshot_source_date"],
        "previous_snapshot_source_date": event["previous_snapshot_source_date"],
        "event_to_signal_return": _round(event_to_signal_return, 6),
        "spy_event_to_signal_return": _round(spy_event_to_signal_return, 6),
        "event_to_signal_excess_vs_spy": _round(event_to_signal_excess, 6),
        "post_earnings_positive_surprise_drift_score": _round(score, 6),
        "pre_event_rs_days": int(config["pre_event_rs_days"]),
        "pre_event_ret20": _round(pre_event_ret20, 6),
        "pre_event_spy_ret20": _round(pre_event_spy_ret20, 6),
        "pre_event_rs20_vs_spy": _round(pre_event_rs, 6),
        "pre_event_underpriced_positive_surprise": True,
        "pre_event_underpricing_threshold": float(config["max_pre_event_rs20_vs_spy"]),
        "high_liquidity_support": high_liquidity_supported,
        "high_liquidity_support_rule_version": HIGH_LIQUIDITY_SUPPORT_RULE_VERSION,
        "high_liquidity_avg_dollar_volume_20d_min": float(
            config["high_liquidity_avg_dollar_volume_20d_min"]
        ),
        "high_liquidity_notional_scalar": _round(high_liquidity_scalar, 6),
        **sector_context,
        "sector_residual_support_rule_version": SECTOR_RESIDUAL_SUPPORT_RULE_VERSION,
        "sector_residual_lookback_days": int(config["sector_residual_lookback_days"]),
        "sector_residual_min_excess": float(config["sector_residual_min_excess"]),
        "sector_residual_min_member_returns": int(
            config["sector_residual_min_member_returns"]
        ),
        "sector_residual_notional_scalar": _round(sector_residual_scalar, 6),
        "pre_sector_residual_paper_notional_usd": _round(
            pre_sector_residual_notional,
            2,
        ),
        **non_core_context,
        "non_core_overlap_support_rule_version": NON_CORE_OVERLAP_SUPPORT_RULE_VERSION,
        "non_core_overlap_notional_scalar": _round(non_core_overlap_scalar, 6),
        "pre_non_core_overlap_paper_notional_usd": _round(
            pre_non_core_overlap_notional,
            2,
        ),
        "known_at": "after_earnings_snapshot_transition_and_signal_date_close_before_next_open_paper_entry",
        "source_universe": "current_production_universe_ohlcv_plus_daily_earnings_snapshots",
        "base_paper_notional_usd": base_notional,
        "intended_notional": _round(intended_notional, 2),
        "trade_enabled": False,
        "alters_orders": False,
    }


def _positive_surprise_events(
    *,
    ticker: str,
    earnings_index: dict[str, list[tuple[str, dict[str, Any]]]],
    trading_dates: list[str],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    index_rows = earnings_index.get(str(ticker).upper(), [])
    if not index_rows:
        return []
    trading_set = set(trading_dates)
    events: list[dict[str, Any]] = []
    for pos in range(1, len(index_rows)):
        snap_date, info = index_rows[pos]
        prev_snap_date, prev_info = index_rows[pos - 1]
        if snap_date not in trading_set:
            continue
        event_min = str(config.get("event_date_min") or "")
        event_max = str(config.get("event_date_max") or "")
        if event_min and snap_date < event_min:
            continue
        if event_max and snap_date > event_max:
            continue
        if not _event_is_confirmed(prev_info, info, config):
            continue
        surprise = _surprise_context(info)
        if surprise is None:
            continue
        latest_surprise = _surprise_tail(info)
        if latest_surprise is None or latest_surprise < float(config["min_latest_surprise_pct"]):
            continue
        if surprise["historical_surprise_count"] < int(config["min_surprise_history_count"]):
            continue
        if surprise["positive_historical_surprise_count"] < int(config["min_positive_surprise_count"]):
            continue
        if surprise["avg_historical_surprise_pct"] < float(config["min_avg_historical_surprise_pct"]):
            continue
        days_to_next = _float_or_none(info.get("days_to_earnings"))
        if days_to_next is None:
            continue
        events.append(
            {
                "ticker": str(ticker).upper(),
                "event_confirmed_date": snap_date,
                "previous_snapshot_source_date": prev_snap_date,
                "earnings_snapshot_source_date": snap_date,
                "latest_surprise_pct": latest_surprise,
                "avg_historical_surprise_pct": surprise["avg_historical_surprise_pct"],
                "historical_surprise_count": surprise["historical_surprise_count"],
                "positive_historical_surprise_count": surprise["positive_historical_surprise_count"],
                "historical_surprise_pct": surprise["historical_surprise_pct"],
                "eps_actual_last": _float_or_none(info.get("eps_actual_last")),
                "days_to_next_earnings_after_event": days_to_next,
            }
        )
    return events


def _event_is_confirmed(
    prev_info: dict[str, Any],
    info: dict[str, Any],
    config: dict[str, Any],
) -> bool:
    prev_dte = _float_or_none(prev_info.get("days_to_earnings"))
    current_dte = _float_or_none(info.get("days_to_earnings"))
    prev_actual = _float_or_none(prev_info.get("eps_actual_last"))
    current_actual = _float_or_none(info.get("eps_actual_last"))
    prev_tail = _surprise_tail(prev_info)
    current_tail = _surprise_tail(info)
    if current_actual is None or current_dte is None:
        return False
    dte_reset = (
        prev_dte is not None
        and prev_dte <= float(config["max_pre_reset_dte"])
        and current_dte >= float(config["min_reset_dte"])
    )
    actual_changed = prev_actual is not None and current_actual != prev_actual
    tail_changed = prev_tail is not None and current_tail is not None and current_tail != prev_tail
    return dte_reset and (actual_changed or tail_changed)


def _surprise_context(info: dict[str, Any]) -> dict[str, Any] | None:
    raw_history = info.get("historical_surprise_pct") or []
    if not isinstance(raw_history, list):
        return None
    history = [
        float(value)
        for value in raw_history
        if _float_or_none(value) is not None
    ]
    if not history:
        return None
    avg = _float_or_none(info.get("avg_historical_surprise_pct"))
    if avg is None:
        avg = sum(history) / len(history)
    return {
        "historical_surprise_pct": history,
        "historical_surprise_count": len(history),
        "positive_historical_surprise_count": sum(1 for value in history if value > 0),
        "avg_historical_surprise_pct": avg,
    }


def _surprise_tail(info: dict[str, Any]) -> float | None:
    context = _surprise_context(info)
    if context is None:
        return None
    history = context.get("historical_surprise_pct") or []
    return float(history[-1]) if history else None


def _pre_event_rs20_vs_spy(
    *,
    rows: list[dict[str, Any]],
    spy_rows: list[dict[str, Any]],
    event_date: str,
    days: int,
) -> tuple[float | None, float | None, float | None]:
    idx = _index_on_date(rows, event_date)
    spy_idx = _index_on_date(spy_rows, event_date)
    if idx is None or spy_idx is None:
        return None, None, None
    event_prior_idx = idx - 1
    spy_event_prior_idx = spy_idx - 1
    if event_prior_idx < days or spy_event_prior_idx < days:
        return None, None, None
    ticker_ret = _close_return(rows, event_prior_idx - days, event_prior_idx)
    spy_ret = _close_return(spy_rows, spy_event_prior_idx - days, spy_event_prior_idx)
    if ticker_ret is None or spy_ret is None:
        return None, None, None
    return ticker_ret, spy_ret, ticker_ret - spy_ret


def _advance_open_positions(
    state: dict[str, Any],
    *,
    as_of: str,
    current_prices: dict[str, float],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    still_open: list[dict[str, Any]] = []
    closed_today: list[dict[str, Any]] = []
    for position in state.get("open_positions") or []:
        if not isinstance(position, dict):
            continue
        ticker = str(position.get("ticker") or "").upper()
        current_price = current_prices.get(ticker)
        if current_price is None:
            still_open.append(position)
            continue
        observed_days = int(position.get("observed_trading_days") or 0) + 1
        position["observed_trading_days"] = observed_days
        exit_mark = apply_slippage(current_price, SLIPPAGE_BPS_TARGET, "sell")
        position["last_price"] = current_price
        position["last_price_asof"] = as_of
        position["unrealized_pnl"] = _pnl(
            position.get("entry_price"),
            exit_mark,
            position.get("notional"),
            float(config["round_trip_cost_pct"]),
        )
        if observed_days >= int(config["hold_days"]):
            closed = deepcopy(position)
            closed.update(
                {
                    "status": "closed",
                    "exit_date": as_of,
                    "exit_price": exit_mark,
                    "exit_reason": "max_hold_days",
                    "pnl": _pnl(
                        position.get("entry_price"),
                        exit_mark,
                        position.get("notional"),
                        float(config["round_trip_cost_pct"]),
                    ),
                    "return_pct_net": _return_pct(
                        position.get("entry_price"),
                        exit_mark,
                        float(config["round_trip_cost_pct"]),
                    ),
                    "trade_enabled": False,
                }
            )
            closed_today.append(closed)
            state["closed_positions"].append(closed)
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
    still_pending: list[dict[str, Any]] = []
    filled: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for entry in sorted(state.get("pending_entries") or [], key=_pending_sort_key):
        if not isinstance(entry, dict):
            continue
        ticker = str(entry.get("ticker") or "").upper()
        if str(entry.get("created_asof") or "") >= as_of:
            still_pending.append(entry)
            continue
        open_price = open_prices.get(ticker)
        if open_price is None:
            skipped_entry = deepcopy(entry)
            skipped_entry.update(
                {
                    "status": "skipped_missing_next_open",
                    "skipped_asof": as_of,
                    "trade_enabled": False,
                }
            )
            skipped.append(skipped_entry)
            state["skipped_entries"].append(skipped_entry)
            continue
        entry_price = apply_entry_fill(open_price)
        notional = _positive_float(entry.get("notional")) or float(config["paper_notional_usd"])
        candidate = entry.get("candidate") or {}
        position = {
            "decision_id": entry.get("decision_id"),
            "sleeve": SLEEVE_NAME,
            "ticker": ticker,
            "strategy": "post_earnings_pre_event_underpriced_drift",
            "entry_date": as_of,
            "entry_price": entry_price,
            "decision_close_price": candidate.get("close"),
            "notional": notional,
            "shares": round(notional / entry_price, 6) if entry_price else None,
            "observed_trading_days": 1,
            "hold_days": int(config["hold_days"]),
            "last_price": current_prices.get(ticker),
            "status": "open",
            "candidate": deepcopy(candidate),
            "trade_enabled": False,
        }
        if current_prices.get(ticker) and entry_price:
            position["unrealized_pnl"] = _pnl(
                entry_price,
                apply_slippage(current_prices[ticker], SLIPPAGE_BPS_TARGET, "sell"),
                position["notional"],
                float(config["round_trip_cost_pct"]),
            )
        filled.append(position)
        state["open_positions"].append(position)
    state["pending_entries"] = still_pending
    return filled, skipped


def _pending_entry_from_candidate(
    candidate: dict[str, Any],
    *,
    as_of: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    ticker = str(candidate.get("ticker") or "").upper()
    notional = _positive_float(candidate.get("intended_notional")) or float(config["paper_notional_usd"])
    return {
        "decision_id": f"{SLEEVE_NAME}:{RULE_VERSION}:{as_of}:{ticker}",
        "sleeve": SLEEVE_NAME,
        "ticker": ticker,
        "created_asof": as_of,
        "status": "pending_next_open",
        "notional": notional,
        "candidate": deepcopy(candidate),
        "trade_enabled": False,
        "alters_orders": False,
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
        "positive_net_pnl": realized > 0 if config.get("forward_gate_positive_net_pnl", True) else True,
        "min_win_rate": win_rate is not None and win_rate >= float(config["forward_gate_min_win_rate"]),
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


def _avg_dollar_volume(rows: list[dict[str, Any]], idx: int, days: int) -> float | None:
    if idx < days:
        return None
    values: list[float] = []
    for row in rows[idx - days:idx]:
        close = _positive_float(row.get("close"))
        volume = _positive_float(row.get("volume"))
        if close is None or volume is None:
            return None
        values.append(close * volume)
    return sum(values) / len(values) if values else None


def _row_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {str(row.get("date") or "")[:10]: idx for idx, row in enumerate(rows or [])}


def _trading_dates(rows_by_ticker: dict[str, list[dict[str, Any]]]) -> list[str]:
    spy_dates = [str(row.get("date") or "")[:10] for row in rows_by_ticker.get("SPY") or []]
    if spy_dates:
        return sorted({date for date in spy_dates if date})
    return sorted(
        {
            str(row.get("date") or "")[:10]
            for rows in rows_by_ticker.values()
            for row in rows
            if str(row.get("date") or "")[:10]
        }
    )


def _snapshot_date_from_path(path: Path) -> str:
    token = path.stem.rsplit("_", 1)[-1]
    if len(token) == 8 and token.isdigit():
        return f"{token[:4]}-{token[4:6]}-{token[6:8]}"
    match = re.search(r"(\d{4}-\d{2}-\d{2})", path.stem)
    return match.group(1) if match else ""


def _earnings_date_count(earnings_index: dict[str, list[tuple[str, dict[str, Any]]]]) -> int:
    return len({snap_date for rows in earnings_index.values() for snap_date, _ in rows})


def _candidate_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row["date"],
        -float(row["post_earnings_positive_surprise_drift_score"]),
        int(row["recent_signal_trading_day_offset"]),
        -float(row["latest_surprise_pct"]),
        -float(row["event_to_signal_excess_vs_spy"]),
        -float(row["rs20_vs_spy"]),
        -float(row["avg_dollar_volume_20d"]),
        row["ticker"],
    )


def _pending_sort_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("created_asof") or ""), str(row.get("ticker") or ""))


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


def prep_and_build_post_earnings_underpriced_drift_paper_sleeve_snapshot(
    *,
    as_of: str,
    ohlcv_dict: dict,
    spy_ohlcv=None,
    signals=None,
    open_prices=None,
    current_prices=None,
):
    ohlcv = dict(ohlcv_dict)
    if spy_ohlcv is not None:
        ohlcv["SPY"] = spy_ohlcv
    candidate_universe = {
        "status": "daily_data_universe",
        "tickers": sorted(
            t for t, f in ohlcv.items()
            if f is not None and str(t).upper() != "SPY"
        ),
    }
    core_entry_tickers_by_date = {
        as_of: sorted(
            {
                str(s.get("ticker") or "").upper()
                for s in (signals or [])
                if str(s.get("ticker") or "").strip()
            }
        )
    }
    return build_post_earnings_underpriced_drift_paper_sleeve_snapshot(
        as_of=as_of, ohlcv_by_ticker=ohlcv, candidate_universe=candidate_universe,
        open_prices=open_prices, current_prices=current_prices,
        config={"core_entry_tickers_by_date": core_entry_tickers_by_date},
    )


def _production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": True,
        "run_adapter_changed": True,
        "backtester_adapter_changed": True,
        "parity_test_added": True,
        "replay_only": False,
        "default_off_paper_only": True,
        "production_signal_path_changed": False,
        "production_orders_changed": False,
        "production_watchlist_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "trade_enabled": False,
        "scope": "default_off_post_earnings_underpriced_drift_paper_attribution",
        "parity_rule": RULE_VERSION,
    }
