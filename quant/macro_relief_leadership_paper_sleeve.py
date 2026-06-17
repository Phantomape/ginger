"""Default-off macro relief stock-leadership paper sleeve.

This module owns the shared semantics for the positive exp-20260606-019 replay
lead. On official CPI/FOMC/NFP event days where both SPY and QQQ rally and
close high in the daily range, it admits up to two liquid stock leaders for
next-open, 10-trading-day default-off paper observation.

The sleeve is paper-only. It never changes core signal generation, ranking,
sizing, exits, heat, LLM/news behavior, watchlists, or orders.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from broad_market_sector_map import load_cache as _load_sector_cache
    from broad_market_sector_map import lookup_sector as _lookup_sector
    from constants import ROUND_TRIP_COST_PCT
    from data_paths import data_artifact_path
    from fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET, apply_slippage
    from macro_events import MACRO_EVENTS
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.broad_market_sector_map import load_cache as _load_sector_cache
    from quant.broad_market_sector_map import lookup_sector as _lookup_sector
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.data_paths import data_artifact_path
    from quant.fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET, apply_slippage
    from quant.macro_events import MACRO_EVENTS


SLEEVE_NAME = "MACRO_RELIEF_LEADERSHIP_PAPER"
RULE_VERSION = "shared_macro_relief_top2_leadership_paper_adapter_v1"
SOURCE_RULE_VERSION = "official_macro_relief_day_stock_leadership_top2_candidate_source_v1"
STATE_SCHEMA_VERSION = 1

DEFAULT_STATE_PATH = data_artifact_path("macro_relief_leadership_paper_state")
DEFAULT_SNAPSHOT_LOG_PATH = data_artifact_path("macro_relief_leadership_paper_snapshots")

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 2
SAME_TICKER_COOLDOWN_DAYS = 10

MIN_SPY_RELIEF_RETURN = 0.004
MIN_QQQ_RELIEF_RETURN = 0.006
MIN_SPY_CLOSE_LOCATION = 0.65
MIN_QQQ_CLOSE_LOCATION = 0.65
MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_SIGNAL_RETURN = 0.010
MIN_RELATIVE_VS_SPY = 0.008
MIN_RELATIVE_VS_QQQ = 0.004
MIN_CLOSE_LOCATION = 0.70
MIN_VOLUME_RATIO_20D = 1.05
MIN_RET20_EXCESS_SPY = 0.0
MIN_RET60_EXCESS_SPY = -0.02
MIN_RET5 = -0.03
MAX_RET5 = 0.15
MAX_REALIZED_VOL_20D = 0.080

DEFAULT_CONFIG = {
    "enabled": False,
    "paper_enabled": True,
    "trade_enabled": False,
    "paper_notional_usd": BASE_NOTIONAL_USD,
    "daily_entry_slots": MAX_PAPER_TRADES_PER_DAY,
    "max_active_positions": 8,
    "hold_days": HOLD_DAYS,
    "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
    "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
    "forward_gate_min_closed_trades": 60,
    "forward_gate_positive_net_pnl": True,
    "forward_gate_min_win_rate": 0.50,
    "forward_gate_max_single_ticker_positive_share": 0.40,
    "forward_gate_max_positive_hhi": 0.30,
}

EXCLUDED_TICKERS = {
    "ARKX",
    "BIL",
    "DIA",
    "GLD",
    "IAU",
    "IBIT",
    "IEF",
    "IWM",
    "QQQ",
    "SHY",
    "SLV",
    "SPY",
    "TLT",
    "UFO",
    "UUP",
    "USO",
    "VIXY",
    "VXX",
}

_SECTOR_CACHE: dict[str, Any] | None = None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_macro_relief_leadership_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_days": [],
    }


def empty_macro_relief_leadership_snapshot(as_of: str, reason: str) -> dict[str, Any]:
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
        "new_pending_count": 0,
        "filled_count": 0,
        "closed_count_today": 0,
        "pending_count": 0,
        "open_position_count": 0,
        "closed_position_count": 0,
        "realized_pnl_to_date": 0.0,
        "unrealized_pnl": 0.0,
        "candidate_universe": {"status": reason, "ticker_count": 0},
        "macro_relief_context": {"status": reason},
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "production_impact": _production_impact(),
        "error": reason,
    }


def load_macro_relief_leadership_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_macro_relief_leadership_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_macro_relief_leadership_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_macro_relief_leadership_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(_safe(state), handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_macro_relief_leadership_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(snapshot), sort_keys=True) + "\n")


def build_macro_relief_leadership_snapshot(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any],
    candidate_universe: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    persist: bool = True,
    state_path: Path | str = DEFAULT_STATE_PATH,
    snapshot_log_path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> dict[str, Any]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    cfg["enabled"] = False
    cfg["trade_enabled"] = False
    as_of_date = _date10(as_of)
    working_state = deepcopy(
        state if state is not None else load_macro_relief_leadership_state(state_path)
    )
    _normalise_state(working_state)
    rows_by_ticker = _normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    filled_today = _fill_pending_entries(working_state, rows_by_ticker, as_of_date, cfg)
    closed_today = _advance_open_positions(working_state, rows_by_ticker, as_of_date, cfg)
    candidates, contexts, scan = candidate_rows_for_dates(
        rows_by_ticker=rows_by_ticker,
        dates=[as_of_date],
        candidate_universe=candidate_universe,
        core_entries_by_date={},
    )
    selected, filtered = select_paper_trades(
        rows_by_ticker=rows_by_ticker,
        candidates=candidates,
        existing_state=working_state,
        config=cfg,
    )
    new_pending_entries: list[dict[str, Any]] = []
    if cfg.get("paper_enabled", True):
        for trade in selected:
            pending = _pending_entry_from_trade(trade, cfg)
            if not _has_pending_open_or_closed_decision(working_state, pending["decision_id"]):
                working_state["pending_entries"].append(pending)
                new_pending_entries.append(pending)
    if not selected and not contexts:
        _append_skip_once(working_state, _skip_payload(as_of_date, "not_official_macro_event_day"))
    elif not selected and contexts and not candidates:
        _append_skip_once(working_state, _skip_payload(as_of_date, "no_macro_relief_leadership_candidate"))

    snapshot = _snapshot_payload(
        working_state,
        as_of=as_of_date,
        candidates=candidates,
        selected=selected,
        filtered=filtered,
        contexts=contexts,
        scan=scan,
        new_pending_entries=new_pending_entries,
        filled_today=filled_today,
        closed_today=closed_today,
        candidate_universe=candidate_universe,
        rows_by_ticker=rows_by_ticker,
        config=cfg,
    )
    if persist:
        save_macro_relief_leadership_state(working_state, state_path)
        append_macro_relief_leadership_snapshot(snapshot, snapshot_log_path)
    return snapshot


def candidate_rows_for_dates(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    dates: list[str],
    candidate_universe: dict[str, Any] | None = None,
    core_entries_by_date: dict[str, list[dict[str, Any]]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    event_map = _macro_event_map()
    indices = {ticker: _row_index(rows) for ticker, rows in rows_by_ticker.items()}
    universe = _candidate_universe_records(candidate_universe, rows_by_ticker)
    core_entries_by_date = core_entries_by_date or {}
    candidates: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    scan = {
        "scanned_trading_days": len(dates),
        "official_macro_event_trading_days": 0,
        "macro_relief_days": 0,
        "non_relief_macro_days": 0,
        "days_with_raw_macro_relief_candidates": 0,
        "raw_macro_relief_candidates": 0,
        "rule_version": SOURCE_RULE_VERSION,
        "macro_event_families": ["CPI", "FOMC", "NFP"],
        "candidate_universe_count": len(universe),
    }
    for signal_date in dates:
        context = _relief_context_for_day(
            rows_by_ticker=rows_by_ticker,
            indices=indices,
            event_map=event_map,
            signal_date=signal_date,
        )
        if context is None:
            continue
        scan["official_macro_event_trading_days"] += 1
        if not context.get("passed"):
            scan["non_relief_macro_days"] += 1
            contexts.append(context)
            continue
        scan["macro_relief_days"] += 1
        day_rows: list[dict[str, Any]] = []
        for ticker, sector_meta in universe.items():
            row = _candidate_for_ticker(
                rows_by_ticker=rows_by_ticker,
                indices=indices,
                sector_meta=sector_meta,
                ticker=ticker,
                signal_date=signal_date,
                context=context,
            )
            if row is None:
                continue
            same_day_entries = core_entries_by_date.get(signal_date, [])
            row["same_day_ab_entry_count"] = len(same_day_entries)
            row["same_day_ab_overlap"] = bool(same_day_entries)
            row["same_ticker_ab_overlap"] = any(
                str(trade.get("ticker") or "").upper() == ticker for trade in same_day_entries
            )
            day_rows.append(row)
        if not day_rows:
            contexts.append({**context, "raw_candidate_count": 0})
            continue
        day_rows.sort(key=_candidate_sort_key)
        candidates.extend(day_rows)
        scan["days_with_raw_macro_relief_candidates"] += 1
        scan["raw_macro_relief_candidates"] += len(day_rows)
        contexts.append(
            {
                **context,
                "raw_candidate_count": len(day_rows),
                "top_candidate": day_rows[0]["ticker"],
                "top_candidate_score": day_rows[0]["candidate_score"],
                "top_candidate_relative_vs_spy": day_rows[0]["candidate_relative_vs_spy"],
                "top_candidate_ret20_excess_spy": day_rows[0]["candidate_ret20_excess_spy"],
            }
        )
    candidates.sort(
        key=lambda row: (
            row["date"],
            *_candidate_sort_key(row),
        )
    )
    scan.update(_parameter_summary())
    return candidates, contexts, scan


def candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    dates: list[str],
    candidate_universe: dict[str, Any] | None = None,
    core_entries_by_date: dict[str, list[dict[str, Any]]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    rows_by_ticker = _normalise_ohlcv_by_ticker(snapshot)
    return candidate_rows_for_dates(
        rows_by_ticker=rows_by_ticker,
        dates=dates,
        candidate_universe=candidate_universe,
        core_entries_by_date=core_entries_by_date,
    )


def select_paper_trades(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
    existing_state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    all_dates = sorted({row["date"] for rows in rows_by_ticker.values() for row in rows})
    date_pos = {date_value: idx for idx, date_value in enumerate(all_dates)}
    next_allowed_pos_by_ticker: dict[str, int] = {}
    if existing_state:
        for row in (existing_state.get("pending_entries") or []) + (
            existing_state.get("open_positions") or []
        ):
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or "").upper()
            date_value = str(row.get("signal_date") or row.get("date") or "")[:10]
            pos = date_pos.get(date_value)
            if ticker and pos is not None:
                next_allowed_pos_by_ticker[ticker] = max(
                    next_allowed_pos_by_ticker.get(ticker, -1),
                    pos + int(cfg["same_ticker_cooldown_days"]),
                )
    for row in candidates:
        signal_date = str(row.get("date") or "")[:10]
        ticker = str(row.get("ticker") or "").upper()
        pos = date_pos.get(signal_date)
        if pos is None:
            filtered.append({**row, "filter_reason": "missing_signal_date_position"})
            continue
        if row.get("same_ticker_ab_overlap"):
            filtered.append({**row, "filter_reason": "same_ticker_core_overlap"})
            continue
        if used_date_counts[signal_date] >= int(cfg["daily_entry_slots"]):
            filtered.append({**row, "filter_reason": "daily_top2_limit"})
            continue
        next_allowed = next_allowed_pos_by_ticker.get(ticker, -1)
        if pos < next_allowed:
            filtered.append({**row, "filter_reason": "same_ticker_cooldown"})
            continue
        trade = replay_trade_from_candidate(
            rows_by_ticker=rows_by_ticker,
            candidate=row,
            config=cfg,
        )
        if trade is None:
            filtered.append({**row, "filter_reason": "missing_next_open_or_exit"})
            continue
        selected.append(trade)
        used_date_counts[signal_date] += 1
        next_allowed_pos_by_ticker[ticker] = pos + int(cfg["same_ticker_cooldown_days"])
    return selected, filtered


def replay_trade_from_candidate(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    candidate: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    ticker = str(candidate.get("ticker") or "").upper()
    rows = rows_by_ticker.get(ticker) or []
    idx = _row_index(rows).get(str(candidate.get("date") or "")[:10])
    if idx is None:
        return None
    entry_idx = idx + 1
    exit_idx = idx + int(cfg["hold_days"])
    if entry_idx >= len(rows) or exit_idx >= len(rows):
        return None
    entry_raw = _positive_float(rows[entry_idx].get("open"))
    exit_raw = _positive_float(rows[exit_idx].get("close"))
    if entry_raw is None or exit_raw is None:
        return None
    entry_price = apply_slippage(entry_raw, SLIPPAGE_BPS_ENTRY, "buy")
    exit_price = apply_slippage(exit_raw, SLIPPAGE_BPS_TARGET, "sell")
    notional = float(cfg["paper_notional_usd"])
    pnl_pct_net = (exit_price / entry_price) - 1.0 - float(cfg["round_trip_cost_pct"])
    pnl = notional * pnl_pct_net
    signal_date = str(candidate["date"])[:10]
    return {
        **deepcopy(candidate),
        "decision_id": f"{SLEEVE_NAME}:{SOURCE_RULE_VERSION}:{signal_date}:{ticker}",
        "sleeve": SLEEVE_NAME,
        "source_rule_version": SOURCE_RULE_VERSION,
        "signal_date": signal_date,
        "entry_date": rows[entry_idx]["date"],
        "entry_raw_open": _round(entry_raw, 4),
        "entry_price": _round(entry_price, 4),
        "exit_date": rows[exit_idx]["date"],
        "exit_raw_close": _round(exit_raw, 4),
        "exit_price": _round(exit_price, 4),
        "hold_days": int(cfg["hold_days"]),
        "paper_notional_usd": _round(notional, 2),
        "pnl_pct_net": _round(pnl_pct_net, 6),
        "net_return_pct": _round(pnl_pct_net, 6),
        "pnl": _round(pnl, 2),
        "paper_status": "closed",
        "trade_enabled": False,
        "alters_orders": False,
    }


def _relief_context_for_day(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    event_map: dict[str, list[dict[str, Any]]],
    signal_date: str,
) -> dict[str, Any] | None:
    events = event_map.get(signal_date)
    if not events:
        return None
    spy_rows = rows_by_ticker.get("SPY") or []
    qqq_rows = rows_by_ticker.get("QQQ") or []
    spy_idx = indices.get("SPY", {}).get(signal_date)
    qqq_idx = indices.get("QQQ", {}).get(signal_date)
    if spy_idx is None or qqq_idx is None:
        return {"date": signal_date, "passed": False, "reason": "missing_spy_or_qqq_event_row", "events": events}
    spy_return = _daily_return(spy_rows, spy_idx)
    qqq_return = _daily_return(qqq_rows, qqq_idx)
    spy_close_location = _close_location(spy_rows[spy_idx])
    qqq_close_location = _close_location(qqq_rows[qqq_idx])
    context = {
        "date": signal_date,
        "events": events,
        "event_families": sorted({str(row.get("family") or "") for row in events}),
        "spy_return": _round(spy_return, 6),
        "qqq_return": _round(qqq_return, 6),
        "spy_close_location": _round(spy_close_location, 6),
        "qqq_close_location": _round(qqq_close_location, 6),
        "min_spy_relief_return": MIN_SPY_RELIEF_RETURN,
        "min_qqq_relief_return": MIN_QQQ_RELIEF_RETURN,
        "min_spy_close_location": MIN_SPY_CLOSE_LOCATION,
        "min_qqq_close_location": MIN_QQQ_CLOSE_LOCATION,
    }
    if spy_return is None or qqq_return is None:
        return {**context, "passed": False, "reason": "missing_daily_return"}
    if spy_close_location is None or qqq_close_location is None:
        return {**context, "passed": False, "reason": "missing_close_location"}
    if spy_return < MIN_SPY_RELIEF_RETURN:
        return {**context, "passed": False, "reason": "spy_relief_return_too_low"}
    if qqq_return < MIN_QQQ_RELIEF_RETURN:
        return {**context, "passed": False, "reason": "qqq_relief_return_too_low"}
    if spy_close_location < MIN_SPY_CLOSE_LOCATION:
        return {**context, "passed": False, "reason": "spy_close_location_too_low"}
    if qqq_close_location < MIN_QQQ_CLOSE_LOCATION:
        return {**context, "passed": False, "reason": "qqq_close_location_too_low"}
    return {**context, "passed": True, "reason": "official_macro_relief_day_passed"}


def _candidate_for_ticker(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_meta: dict[str, Any],
    ticker: str,
    signal_date: str,
    context: dict[str, Any],
) -> dict[str, Any] | None:
    rows = rows_by_ticker.get(ticker) or []
    spy_rows = rows_by_ticker.get("SPY") or []
    qqq_rows = rows_by_ticker.get("QQQ") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    qqq_idx = indices.get("QQQ", {}).get(signal_date)
    if idx is None or spy_idx is None or qqq_idx is None:
        return None
    if idx < 60 or spy_idx < 60 or qqq_idx < 60 or idx + HOLD_DAYS >= len(rows):
        return None
    close = _positive_float(rows[idx].get("close"))
    if close is None or close < MIN_PRICE:
        return None
    adv20 = _avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    signal_return = _daily_return(rows, idx)
    spy_return = _daily_return(spy_rows, spy_idx)
    qqq_return = _daily_return(qqq_rows, qqq_idx)
    close_location = _close_location(rows[idx])
    volume_ratio = _volume_ratio(rows, idx)
    ret5 = _ret(rows, idx, 5)
    ret20 = _ret(rows, idx, 20)
    ret60 = _ret(rows, idx, 60)
    spy_ret20 = _ret(spy_rows, spy_idx, 20)
    spy_ret60 = _ret(spy_rows, spy_idx, 60)
    realized_vol20 = _realized_vol(rows, idx, 20)
    required = [
        signal_return,
        spy_return,
        qqq_return,
        close_location,
        volume_ratio,
        ret5,
        ret20,
        ret60,
        spy_ret20,
        spy_ret60,
        realized_vol20,
    ]
    if any(value is None for value in required):
        return None
    assert signal_return is not None and spy_return is not None and qqq_return is not None
    assert close_location is not None and volume_ratio is not None
    assert ret5 is not None and ret20 is not None and ret60 is not None
    assert spy_ret20 is not None and spy_ret60 is not None and realized_vol20 is not None
    relative_vs_spy = signal_return - spy_return
    relative_vs_qqq = signal_return - qqq_return
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    if signal_return < MIN_SIGNAL_RETURN:
        return None
    if relative_vs_spy < MIN_RELATIVE_VS_SPY or relative_vs_qqq < MIN_RELATIVE_VS_QQQ:
        return None
    if close_location < MIN_CLOSE_LOCATION or volume_ratio < MIN_VOLUME_RATIO_20D:
        return None
    if ret20_excess_spy < MIN_RET20_EXCESS_SPY or ret60_excess_spy < MIN_RET60_EXCESS_SPY:
        return None
    if ret5 < MIN_RET5 or ret5 > MAX_RET5 or realized_vol20 > MAX_REALIZED_VOL_20D:
        return None
    liquidity_score = math.log10(max(adv20, 1.0) / 1_000_000.0)
    score = (
        2.25 * relative_vs_spy
        + 1.25 * relative_vs_qqq
        + 0.80 * ret20_excess_spy
        + 0.35 * ret60_excess_spy
        + 0.30 * close_location
        + 0.10 * min(volume_ratio, 3.0)
        + 0.04 * liquidity_score
        - 0.55 * realized_vol20
        - 0.20 * max(ret5, 0.0)
    )
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": SLEEVE_NAME,
        "candidate_score": round(score, 6),
        "candidate_signal_day_return": round(signal_return, 6),
        "candidate_spy_signal_day_return": round(spy_return, 6),
        "candidate_qqq_signal_day_return": round(qqq_return, 6),
        "candidate_relative_vs_spy": round(relative_vs_spy, 6),
        "candidate_relative_vs_qqq": round(relative_vs_qqq, 6),
        "candidate_close_location": round(close_location, 6),
        "candidate_volume_ratio_20d": round(volume_ratio, 6),
        "candidate_avg_dollar_volume_20d": round(adv20, 2),
        "candidate_ret5": round(ret5, 6),
        "candidate_ret20": round(ret20, 6),
        "candidate_spy_ret20": round(spy_ret20, 6),
        "candidate_ret20_excess_spy": round(ret20_excess_spy, 6),
        "candidate_ret60": round(ret60, 6),
        "candidate_spy_ret60": round(spy_ret60, 6),
        "candidate_ret60_excess_spy": round(ret60_excess_spy, 6),
        "candidate_realized_vol_20d": round(realized_vol20, 6),
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "sector_coverage_status": sector_meta.get("sector_coverage_status"),
        "macro_relief_context": context,
        "rule_version": SOURCE_RULE_VERSION,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
        "uses_free_ohlcv_only": True,
        "uses_llm": False,
        "trade_enabled": False,
        "alters_orders": False,
    }


def _normalise_state(state: dict[str, Any]) -> None:
    state.setdefault("schema_version", STATE_SCHEMA_VERSION)
    state.setdefault("sleeve", SLEEVE_NAME)
    state.setdefault("pending_entries", [])
    state.setdefault("open_positions", [])
    state.setdefault("closed_positions", [])
    state.setdefault("skipped_days", [])


def _pending_entry_from_trade(trade: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(trade)
    for key in ("entry_date", "entry_raw_open", "entry_price", "exit_date", "exit_raw_close", "exit_price", "pnl", "pnl_pct_net"):
        out.pop(key, None)
    out.update(
        {
            "sleeve": SLEEVE_NAME,
            "rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "paper_notional_usd": float(config["paper_notional_usd"]),
            "notional_usd": float(config["paper_notional_usd"]),
            "entry_timing": "next_session_open",
            "hold_days": int(config["hold_days"]),
            "paper_status": "pending_entry",
            "trade_enabled": False,
            "alters_orders": False,
        }
    )
    return out


def _fill_pending_entries(
    state: dict[str, Any],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    as_of: str,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    still_pending: list[dict[str, Any]] = []
    filled_today: list[dict[str, Any]] = []
    for pending in state.get("pending_entries") or []:
        if not isinstance(pending, dict):
            continue
        ticker = str(pending.get("ticker") or "").upper()
        signal_date = str(pending.get("signal_date") or pending.get("date") or "")[:10]
        rows = rows_by_ticker.get(ticker) or []
        idx = _row_index(rows).get(as_of)
        if idx is None or as_of <= signal_date:
            still_pending.append(pending)
            continue
        open_price = _positive_float(rows[idx].get("open"))
        if open_price is None:
            still_pending.append(pending)
            continue
        opened = deepcopy(pending)
        opened.update(
            {
                "entry_date": as_of,
                "entry_raw_open": _round(open_price, 4),
                "entry_price": _round(apply_slippage(open_price, SLIPPAGE_BPS_ENTRY, "buy"), 4),
                "observed_trading_days": 1,
                "last_observed_date": as_of,
                "paper_status": "open",
            }
        )
        state["open_positions"].append(opened)
        filled_today.append(opened)
    state["pending_entries"] = still_pending
    return filled_today


def _advance_open_positions(
    state: dict[str, Any],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    as_of: str,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    still_open: list[dict[str, Any]] = []
    closed_today: list[dict[str, Any]] = []
    for position in state.get("open_positions") or []:
        if not isinstance(position, dict):
            continue
        ticker = str(position.get("ticker") or "").upper()
        rows = rows_by_ticker.get(ticker) or []
        idx = _row_index(rows).get(as_of)
        if idx is None or as_of < str(position.get("entry_date") or "")[:10]:
            still_open.append(position)
            continue
        working = deepcopy(position)
        if str(working.get("last_observed_date") or "") != as_of:
            working["observed_trading_days"] = int(working.get("observed_trading_days") or 0) + 1
            working["last_observed_date"] = as_of
        if int(working.get("observed_trading_days") or 0) < int(config["hold_days"]):
            still_open.append(working)
            continue
        close_price = _positive_float(rows[idx].get("close"))
        entry_price = _positive_float(working.get("entry_price"))
        notional = _positive_float(working.get("notional_usd") or working.get("paper_notional_usd"))
        if close_price is None or entry_price is None or notional is None:
            still_open.append(working)
            continue
        exit_price = apply_slippage(close_price, SLIPPAGE_BPS_TARGET, "sell")
        pnl_pct_net = (exit_price / entry_price) - 1.0 - float(config["round_trip_cost_pct"])
        closed = deepcopy(working)
        closed.update(
            {
                "exit_date": as_of,
                "exit_raw_close": _round(close_price, 4),
                "exit_price": _round(exit_price, 4),
                "pnl_pct_net": _round(pnl_pct_net, 6),
                "net_return_pct": _round(pnl_pct_net, 6),
                "pnl": _round(notional * pnl_pct_net, 2),
                "paper_status": "closed",
            }
        )
        if not _has_closed_decision(state, closed["decision_id"]):
            state["closed_positions"].append(closed)
            closed_today.append(closed)
    state["open_positions"] = still_open
    return closed_today


def _snapshot_payload(
    state: dict[str, Any],
    *,
    as_of: str,
    candidates: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    filtered: list[dict[str, Any]],
    contexts: list[dict[str, Any]],
    scan: dict[str, Any],
    new_pending_entries: list[dict[str, Any]],
    filled_today: list[dict[str, Any]],
    closed_today: list[dict[str, Any]],
    candidate_universe: dict[str, Any] | None,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    config: dict[str, Any],
) -> dict[str, Any]:
    closed = [row for row in state.get("closed_positions") or [] if isinstance(row, dict)]
    pending = [row for row in state.get("pending_entries") or [] if isinstance(row, dict)]
    open_positions = [row for row in state.get("open_positions") or [] if isinstance(row, dict)]
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "asof_date": as_of,
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": bool(config.get("paper_enabled", True)),
        "trade_enabled": False,
        "trade_enabled_reason": "default_off_until_forward_gate_and_trade_adapter_pass",
        "candidate_count": len(selected),
        "raw_candidate_count": len(candidates),
        "candidate": selected[0] if selected else None,
        "candidates": selected,
        "filtered_candidates": filtered[:25],
        "macro_relief_context": contexts[-1] if contexts else {"date": as_of, "passed": False},
        "context_scan": scan,
        "candidate_universe": _candidate_universe_summary(candidate_universe, rows_by_ticker),
        "new_pending_entries": new_pending_entries,
        "new_pending_count": len(new_pending_entries),
        "pending_entries": pending,
        "pending_count": len(pending),
        "filled_today": filled_today,
        "filled_count": len(filled_today),
        "open_positions": open_positions,
        "open_position_count": len(open_positions),
        "closed_today": closed_today,
        "closed_positions_today": closed_today,
        "closed_count_today": len(closed_today),
        "closed_positions": closed,
        "closed_position_count": len(closed),
        "realized_pnl_to_date": _round(sum(_float_or_none(row.get("pnl")) or 0.0 for row in closed), 2),
        "unrealized_pnl": _unrealized_pnl(open_positions, rows_by_ticker, as_of),
        "forward_paper_gate": _forward_paper_gate(closed, config),
        "parameters": dict(config),
        "production_impact": _production_impact(),
        "next_action": "paper_observe_forward_outcomes_only_no_orders",
    }


def _forward_paper_gate(closed_positions: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    closed = [row for row in closed_positions if isinstance(row, dict)]
    realized = _round(sum(_float_or_none(row.get("pnl")) or 0.0 for row in closed), 2)
    wins = sum(1 for row in closed if (_float_or_none(row.get("pnl")) or 0.0) > 0)
    win_rate = round(wins / len(closed), 4) if closed else None
    single_share, hhi = _positive_concentration(closed)
    checks = {
        "min_closed_trades": len(closed) >= int(config["forward_gate_min_closed_trades"]),
        "positive_net_pnl": realized > 0 if config.get("forward_gate_positive_net_pnl") else True,
        "min_win_rate": win_rate is not None and win_rate >= float(config["forward_gate_min_win_rate"]),
        "max_single_ticker_positive_share": single_share is not None and single_share <= float(config["forward_gate_max_single_ticker_positive_share"]),
        "max_positive_hhi": hhi is not None and hhi <= float(config["forward_gate_max_positive_hhi"]),
    }
    reasons = [key for key, passed in checks.items() if not passed]
    return {
        "passed": not reasons,
        "status": "passed" if not reasons else "blocked",
        "reasons": reasons,
        "checks": checks,
        "metrics": {
            "closed_trades": len(closed),
            "realized_pnl": realized,
            "win_rate": win_rate,
            "single_ticker_positive_share": single_share,
            "positive_pnl_hhi": hhi,
        },
        "trade_enabled_after_gate": False,
    }


def _candidate_universe_records(
    candidate_universe: dict[str, Any] | None,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    tickers = sorted(set((candidate_universe or {}).get("tickers") or rows_by_ticker))
    records = (candidate_universe or {}).get("records") or {}
    out: dict[str, dict[str, Any]] = {}
    cache = _sector_cache()
    for raw_ticker in tickers:
        ticker = str(raw_ticker).upper()
        if ticker in EXCLUDED_TICKERS or "." in ticker or "-" in ticker:
            continue
        if ticker not in rows_by_ticker:
            continue
        record = records.get(ticker) if isinstance(records, dict) else None
        sector = (record or {}).get("sector") or (record or {}).get("gics_sector")
        industry = (record or {}).get("industry")
        status = "ok" if sector else None
        if not sector:
            lookup = _lookup_sector(ticker, cache)
            sector = lookup.get("sector")
            industry = lookup.get("industry")
            status = lookup.get("status")
        if status != "ok" or not sector:
            continue
        out[ticker] = {
            "sector": sector,
            "industry": industry,
            "sector_coverage_status": status,
        }
    return out


def _normalise_ohlcv_by_ticker(raw: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {
        str(ticker).upper(): rows
        for ticker, data in raw.items()
        if (rows := _normalise_ohlcv_rows(data))
    }


def _normalise_ohlcv_rows(data: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if data is None:
        return rows
    if hasattr(data, "iterrows"):
        for idx, row in data.iterrows():
            rows.append(_row_from_mapping(row, idx))
    elif isinstance(data, list):
        for row in data:
            if isinstance(row, dict):
                rows.append(_row_from_mapping(row, None))
    return sorted([row for row in rows if row.get("date")], key=lambda row: row["date"])


def _row_from_mapping(row: Any, idx: Any) -> dict[str, Any]:
    def pick(*names: str) -> Any:
        for name in names:
            try:
                value = row.get(name)
            except AttributeError:
                value = None
            if value is not None:
                return value
        return None

    return {
        "date": _date10(pick("Date", "date") or idx),
        "open": _float_or_none(pick("Open", "open")),
        "high": _float_or_none(pick("High", "high")),
        "low": _float_or_none(pick("Low", "low")),
        "close": _float_or_none(pick("Close", "close")),
        "volume": _float_or_none(pick("Volume", "volume")),
    }


def _row_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {str(row.get("date") or "")[:10]: idx for idx, row in enumerate(rows)}


def _macro_event_map() -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for row in MACRO_EVENTS:
        out.setdefault(str(row["date"])[:10], []).append(row)
    return out


def _candidate_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -float(row["candidate_score"]),
        -float(row["candidate_relative_vs_spy"]),
        -float(row["candidate_ret20_excess_spy"]),
        -float(row["candidate_avg_dollar_volume_20d"]),
        str(row.get("sector") or ""),
        row["ticker"],
    )


def _parameter_summary() -> dict[str, Any]:
    return {
        "min_spy_relief_return": MIN_SPY_RELIEF_RETURN,
        "min_qqq_relief_return": MIN_QQQ_RELIEF_RETURN,
        "min_spy_close_location": MIN_SPY_CLOSE_LOCATION,
        "min_qqq_close_location": MIN_QQQ_CLOSE_LOCATION,
        "min_signal_return": MIN_SIGNAL_RETURN,
        "min_relative_vs_spy": MIN_RELATIVE_VS_SPY,
        "min_relative_vs_qqq": MIN_RELATIVE_VS_QQQ,
        "min_close_location": MIN_CLOSE_LOCATION,
        "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
        "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
        "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
        "min_ret5": MIN_RET5,
        "max_ret5": MAX_RET5,
        "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
    }


def _daily_return(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx < 1:
        return None
    prior = _positive_float(rows[idx - 1].get("close"))
    close = _positive_float(rows[idx].get("close"))
    return (close / prior) - 1.0 if prior and close else None


def _ret(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback:
        return None
    prior = _positive_float(rows[idx - lookback].get("close"))
    close = _positive_float(rows[idx].get("close"))
    return (close / prior) - 1.0 if prior and close else None


def _avg_dollar_volume(rows: list[dict[str, Any]], idx: int, lookback: int = 20) -> float | None:
    if idx < lookback - 1:
        return None
    values: list[float] = []
    for row in rows[idx - lookback + 1 : idx + 1]:
        close = _positive_float(row.get("close"))
        volume = _positive_float(row.get("volume"))
        if close is None or volume is None:
            return None
        values.append(close * volume)
    return sum(values) / len(values)


def _volume_ratio(rows: list[dict[str, Any]], idx: int, lookback: int = 20) -> float | None:
    if idx < lookback:
        return None
    current = _positive_float(rows[idx].get("volume"))
    prior = [_positive_float(row.get("volume")) for row in rows[idx - lookback : idx]]
    if current is None or any(value is None for value in prior):
        return None
    avg = sum(float(value) for value in prior if value is not None) / len(prior)
    return current / avg if avg > 0 else None


def _close_location(row: dict[str, Any]) -> float | None:
    high = _float_or_none(row.get("high"))
    low = _float_or_none(row.get("low"))
    close = _float_or_none(row.get("close"))
    if high is None or low is None or close is None:
        return None
    span = high - low
    return 0.5 if span <= 0 else (close - low) / span


def _realized_vol(rows: list[dict[str, Any]], idx: int, lookback: int = 20) -> float | None:
    if idx < lookback:
        return None
    returns = []
    for pos in range(idx - lookback + 1, idx + 1):
        daily = _daily_return(rows, pos)
        if daily is None:
            return None
        returns.append(daily)
    mean = sum(returns) / len(returns)
    variance = sum((value - mean) ** 2 for value in returns) / len(returns)
    return math.sqrt(variance)


def _candidate_universe_summary(
    candidate_universe: dict[str, Any] | None,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    return {
        "status": (candidate_universe or {}).get("status") or "ohlcv_dict",
        "ticker_count": len((candidate_universe or {}).get("tickers") or rows_by_ticker),
        "loaded_ohlcv_ticker_count": len(rows_by_ticker),
    }


def _skip_payload(as_of: str, reason: str) -> dict[str, Any]:
    return {
        "decision_id": f"{SLEEVE_NAME}:{RULE_VERSION}:{as_of}:SKIP:{reason}",
        "date": as_of,
        "reason": reason,
        "trade_enabled": False,
        "alters_orders": False,
    }


def _append_skip_once(state: dict[str, Any], row: dict[str, Any]) -> None:
    existing = {
        str(item.get("decision_id") or "")
        for item in state.get("skipped_days") or []
        if isinstance(item, dict)
    }
    if row["decision_id"] not in existing:
        state["skipped_days"].append(row)


def _has_closed_decision(state: dict[str, Any], decision_id: str) -> bool:
    return any(
        str(row.get("decision_id") or "") == decision_id
        for row in state.get("closed_positions") or []
        if isinstance(row, dict)
    )


def _has_pending_open_or_closed_decision(state: dict[str, Any], decision_id: str) -> bool:
    for bucket in ("pending_entries", "open_positions", "closed_positions"):
        if any(
            str(row.get("decision_id") or "") == decision_id
            for row in state.get(bucket) or []
            if isinstance(row, dict)
        ):
            return True
    return False


def _unrealized_pnl(
    open_positions: list[dict[str, Any]],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    as_of: str,
) -> float:
    total = 0.0
    for position in open_positions:
        rows = rows_by_ticker.get(str(position.get("ticker") or "").upper()) or []
        idx = _row_index(rows).get(as_of)
        close_price = _positive_float(rows[idx].get("close")) if idx is not None else None
        entry_price = _positive_float(position.get("entry_price"))
        notional = _positive_float(position.get("notional_usd") or position.get("paper_notional_usd"))
        if close_price is None or entry_price is None or notional is None:
            continue
        total += notional * (close_price / entry_price - 1.0)
    return round(total, 2)


def _positive_concentration(rows: list[dict[str, Any]]) -> tuple[float | None, float | None]:
    by_ticker: dict[str, float] = {}
    for row in rows:
        pnl = _float_or_none(row.get("pnl")) or 0.0
        if pnl <= 0:
            continue
        ticker = str(row.get("ticker") or "").upper()
        by_ticker[ticker] = by_ticker.get(ticker, 0.0) + pnl
    total = sum(by_ticker.values())
    if total <= 0:
        return None, None
    shares = [value / total for value in by_ticker.values()]
    return round(max(shares), 6), round(sum(share * share for share in shares), 6)


def _sector_cache() -> dict[str, Any]:
    global _SECTOR_CACHE
    if _SECTOR_CACHE is None:
        _SECTOR_CACHE = _load_sector_cache()
    return _SECTOR_CACHE


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _date10(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)[:10]


def _float_or_none(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _positive_float(value: Any) -> float | None:
    number = _float_or_none(value)
    return number if number is not None and number > 0 else None


def _round(value: Any, digits: int = 4) -> Any:
    number = _float_or_none(value)
    return round(number, digits) if number is not None else None


def prep_and_build_macro_relief_leadership_snapshot(
    *,
    as_of: str,
    broad_market_ohlcv: dict,
    broad_market_candidate_universe: dict,
    spy_ohlcv=None,
    ohlcv_dict=None,
    cached_ohlcv_fn=None,
):
    if not broad_market_candidate_universe.get("tickers"):
        return empty_macro_relief_leadership_snapshot(
            as_of, "broad_market_candidate_universe_unavailable")
    ohlcv = dict(broad_market_ohlcv)
    if "SPY" not in ohlcv and spy_ohlcv is not None:
        ohlcv["SPY"] = spy_ohlcv
    if "QQQ" not in ohlcv:
        ohlcv["QQQ"] = (ohlcv_dict or {}).get("QQQ") or (cached_ohlcv_fn("QQQ") if cached_ohlcv_fn else None)
    return build_macro_relief_leadership_snapshot(
        as_of=as_of, ohlcv_by_ticker=ohlcv,
        candidate_universe=broad_market_candidate_universe,
    )


def _production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": True,
        "shared_policy_note": "paper attribution module only; core trading policy unchanged",
        "backtester_adapter_changed": True,
        "run_adapter_changed": True,
        "replay_only": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "trade_enabled": False,
        "scope": "default_off_macro_relief_leadership_paper_attribution",
    }
