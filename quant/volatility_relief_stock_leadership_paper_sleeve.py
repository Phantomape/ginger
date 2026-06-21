"""Default-off volatility-relief stock-leadership paper sleeve.

Shared helper for the positive exp-20260607-018 replay lead. On days where
VIXY sells off while SPY and QQQ confirm risk relief, it admits up to two
liquid stock leaders for next-open, 10-trading-day default-off paper
observation.

The sleeve is paper-only. It never changes core signal generation, ranking,
sizing, exits, heat, LLM/news behavior, watchlists, or orders.
"""

from __future__ import annotations

import json
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import macro_relief_leadership_paper_sleeve as leader
    from constants import ROUND_TRIP_COST_PCT
    from data_paths import DATA_ROOT
    from fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET, apply_slippage
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant import macro_relief_leadership_paper_sleeve as leader
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.data_paths import DATA_ROOT
    from quant.fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET, apply_slippage


SLEEVE_NAME = "VOLATILITY_RELIEF_LEADERSHIP_PAPER"
RULE_VERSION = "volatility_relief_stock_leadership_shared_default_off_adapter_v1"
SOURCE_RULE_VERSION = "volatility_relief_stock_leadership_candidate_source_v1"
STATE_SCHEMA_VERSION = 1

DEFAULT_STATE_PATH = (
    DATA_ROOT / "paper_sleeves" / "volatility_relief_leadership" / "state.json"
)
DEFAULT_SNAPSHOT_LOG_PATH = (
    DATA_ROOT / "paper_sleeves" / "volatility_relief_leadership" / "snapshots.jsonl"
)

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 2
SAME_TICKER_COOLDOWN_DAYS = 10

MAX_VIXY_RELIEF_RETURN = -0.035
MAX_VIXY_CLOSE_LOCATION = 0.45
MIN_SPY_RELIEF_RETURN = 0.003
MIN_QQQ_RELIEF_RETURN = 0.004
MIN_SPY_CLOSE_LOCATION = 0.55
MIN_QQQ_CLOSE_LOCATION = 0.55
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


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_volatility_relief_stock_leadership_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_days": [],
    }


def empty_volatility_relief_stock_leadership_snapshot(
    as_of: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "asof_date": leader._date10(as_of),
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": False,
        "trade_enabled": False,
        "candidate_count": 0,
        "raw_candidate_count": 0,
        "new_pending_count": 0,
        "filled_count": 0,
        "closed_count_today": 0,
        "pending_count": 0,
        "open_position_count": 0,
        "closed_position_count": 0,
        "realized_pnl_to_date": 0.0,
        "unrealized_pnl": 0.0,
        "candidate_universe": {"status": reason, "ticker_count": 0},
        "volatility_relief_context": {"status": reason},
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "production_impact": _production_impact(),
        "error": reason,
    }


def load_volatility_relief_stock_leadership_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_volatility_relief_stock_leadership_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_volatility_relief_stock_leadership_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_volatility_relief_stock_leadership_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(leader._safe(state), handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_volatility_relief_stock_leadership_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(leader._safe(snapshot), sort_keys=True) + "\n")


def build_volatility_relief_stock_leadership_snapshot(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any],
    candidate_universe: dict[str, Any] | None = None,
    core_entries: list[dict[str, Any]] | None = None,
    state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    persist: bool = True,
    state_path: Path | str = DEFAULT_STATE_PATH,
    snapshot_log_path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> dict[str, Any]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    cfg["enabled"] = False
    cfg["trade_enabled"] = False
    as_of_date = leader._date10(as_of)
    working_state = deepcopy(
        state
        if state is not None
        else load_volatility_relief_stock_leadership_state(state_path)
    )
    _normalise_state(working_state)
    rows_by_ticker = leader._normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    filled_today = leader._fill_pending_entries(
        working_state,
        rows_by_ticker,
        as_of_date,
        cfg,
    )
    closed_today = leader._advance_open_positions(
        working_state,
        rows_by_ticker,
        as_of_date,
        cfg,
    )
    core_entries_by_date = _core_entries_by_date(core_entries or [])
    candidates, contexts, scan = candidate_rows_for_dates(
        rows_by_ticker=rows_by_ticker,
        dates=[as_of_date],
        candidate_universe=candidate_universe,
        core_entries_by_date=core_entries_by_date,
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
            if not leader._has_pending_open_or_closed_decision(
                working_state,
                pending["decision_id"],
            ):
                working_state["pending_entries"].append(pending)
                new_pending_entries.append(pending)
    if not selected and not contexts:
        _append_skip_once(working_state, _skip_payload(as_of_date, "missing_volatility_relief_context"))
    elif not selected and contexts and not candidates:
        _append_skip_once(working_state, _skip_payload(as_of_date, "no_volatility_relief_leadership_candidate"))

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
        save_volatility_relief_stock_leadership_state(working_state, state_path)
        append_volatility_relief_stock_leadership_snapshot(snapshot, snapshot_log_path)
    return snapshot


def build_volatility_relief_stock_leadership_historical_trades(
    *,
    ohlcv_by_ticker: dict[str, Any],
    dates: list[str],
    candidate_universe: dict[str, Any] | None = None,
    core_entries_by_date: dict[str, list[dict[str, Any]]] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows_by_ticker = leader._normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    candidates, contexts, scan = candidate_rows_for_dates(
        rows_by_ticker=rows_by_ticker,
        dates=dates,
        candidate_universe=candidate_universe,
        core_entries_by_date=core_entries_by_date,
    )
    selected, filtered = select_paper_trades(
        rows_by_ticker=rows_by_ticker,
        candidates=candidates,
        config=config,
    )
    return {
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "trade_enabled": False,
        "candidates": candidates,
        "filtered_candidates": filtered,
        "trades": selected,
        "contexts": contexts,
        "context_scan": scan,
        "production_impact": _production_impact(),
    }


def candidate_rows_for_dates(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    dates: list[str],
    candidate_universe: dict[str, Any] | None = None,
    core_entries_by_date: dict[str, list[dict[str, Any]]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    indices = {ticker: leader._row_index(rows) for ticker, rows in rows_by_ticker.items()}
    universe = leader._candidate_universe_records(candidate_universe, rows_by_ticker)
    core_entries_by_date = core_entries_by_date or {}
    candidates: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    scan = {
        "scanned_trading_days": len(dates),
        "volatility_relief_days": 0,
        "non_relief_days": 0,
        "days_with_raw_volatility_relief_candidates": 0,
        "raw_volatility_relief_candidates": 0,
        "rule_version": SOURCE_RULE_VERSION,
        "candidate_universe_count": len(universe),
    }
    for signal_date in dates:
        context = _volatility_relief_context_for_day(
            rows_by_ticker=rows_by_ticker,
            indices=indices,
            signal_date=signal_date,
        )
        if context is None:
            continue
        if not context.get("passed"):
            scan["non_relief_days"] += 1
            contexts.append(context)
            continue
        scan["volatility_relief_days"] += 1
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
                str(trade.get("ticker") or "").upper() == ticker
                for trade in same_day_entries
            )
            day_rows.append(row)
        if not day_rows:
            contexts.append({**context, "raw_candidate_count": 0})
            continue
        day_rows.sort(key=leader._candidate_sort_key)
        candidates.extend(day_rows)
        scan["days_with_raw_volatility_relief_candidates"] += 1
        scan["raw_volatility_relief_candidates"] += len(day_rows)
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
    candidates.sort(key=lambda row: (row["date"], *leader._candidate_sort_key(row)))
    scan.update(_parameter_summary())
    return candidates, contexts, scan


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
    idx = leader._row_index(rows).get(str(candidate.get("date") or "")[:10])
    if idx is None:
        return None
    entry_idx = idx + 1
    exit_idx = idx + int(cfg["hold_days"])
    if entry_idx >= len(rows) or exit_idx >= len(rows):
        return None
    entry_raw = leader._positive_float(rows[entry_idx].get("open"))
    exit_raw = leader._positive_float(rows[exit_idx].get("close"))
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
        "entry_raw_open": leader._round(entry_raw, 4),
        "entry_price": leader._round(entry_price, 4),
        "exit_date": rows[exit_idx]["date"],
        "exit_raw_close": leader._round(exit_raw, 4),
        "exit_price": leader._round(exit_price, 4),
        "hold_days": int(cfg["hold_days"]),
        "paper_notional_usd": leader._round(notional, 2),
        "pnl_pct_net": leader._round(pnl_pct_net, 6),
        "net_return_pct": leader._round(pnl_pct_net, 6),
        "pnl": leader._round(pnl, 2),
        "paper_status": "closed",
        "trade_enabled": False,
        "alters_orders": False,
    }


def _volatility_relief_context_for_day(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    signal_date: str,
) -> dict[str, Any] | None:
    vixy_rows = rows_by_ticker.get("VIXY") or []
    spy_rows = rows_by_ticker.get("SPY") or []
    qqq_rows = rows_by_ticker.get("QQQ") or []
    vixy_idx = indices.get("VIXY", {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    qqq_idx = indices.get("QQQ", {}).get(signal_date)
    if vixy_idx is None or spy_idx is None or qqq_idx is None:
        return None
    vixy_return = leader._daily_return(vixy_rows, vixy_idx)
    spy_return = leader._daily_return(spy_rows, spy_idx)
    qqq_return = leader._daily_return(qqq_rows, qqq_idx)
    vixy_close_location = leader._close_location(vixy_rows[vixy_idx])
    spy_close_location = leader._close_location(spy_rows[spy_idx])
    qqq_close_location = leader._close_location(qqq_rows[qqq_idx])
    context = {
        "date": signal_date,
        "vixy_return": leader._round(vixy_return, 6),
        "spy_return": leader._round(spy_return, 6),
        "qqq_return": leader._round(qqq_return, 6),
        "vixy_close_location": leader._round(vixy_close_location, 6),
        "spy_close_location": leader._round(spy_close_location, 6),
        "qqq_close_location": leader._round(qqq_close_location, 6),
        "max_vixy_relief_return": MAX_VIXY_RELIEF_RETURN,
        "max_vixy_close_location": MAX_VIXY_CLOSE_LOCATION,
        "min_spy_relief_return": MIN_SPY_RELIEF_RETURN,
        "min_qqq_relief_return": MIN_QQQ_RELIEF_RETURN,
        "min_spy_close_location": MIN_SPY_CLOSE_LOCATION,
        "min_qqq_close_location": MIN_QQQ_CLOSE_LOCATION,
        "rule_version": SOURCE_RULE_VERSION,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }
    if vixy_return is None or spy_return is None or qqq_return is None:
        return {**context, "passed": False, "reason": "missing_daily_return"}
    if (
        vixy_close_location is None
        or spy_close_location is None
        or qqq_close_location is None
    ):
        return {**context, "passed": False, "reason": "missing_close_location"}
    if vixy_return > MAX_VIXY_RELIEF_RETURN:
        return {**context, "passed": False, "reason": "vixy_decline_too_small"}
    if vixy_close_location > MAX_VIXY_CLOSE_LOCATION:
        return {**context, "passed": False, "reason": "vixy_close_not_weak_enough"}
    if spy_return < MIN_SPY_RELIEF_RETURN:
        return {**context, "passed": False, "reason": "spy_relief_return_too_low"}
    if qqq_return < MIN_QQQ_RELIEF_RETURN:
        return {**context, "passed": False, "reason": "qqq_relief_return_too_low"}
    if spy_close_location < MIN_SPY_CLOSE_LOCATION:
        return {**context, "passed": False, "reason": "spy_close_location_too_low"}
    if qqq_close_location < MIN_QQQ_CLOSE_LOCATION:
        return {**context, "passed": False, "reason": "qqq_close_location_too_low"}
    return {**context, "passed": True, "reason": "vixy_spy_qqq_volatility_relief_passed"}


def _candidate_for_ticker(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_meta: dict[str, Any],
    ticker: str,
    signal_date: str,
    context: dict[str, Any],
) -> dict[str, Any] | None:
    row = leader._candidate_for_ticker(
        rows_by_ticker=rows_by_ticker,
        indices=indices,
        sector_meta=sector_meta,
        ticker=ticker,
        signal_date=signal_date,
        context=context,
    )
    if row is None:
        return None
    row["source"] = SLEEVE_NAME
    row["volatility_relief_context"] = row.pop("macro_relief_context", context)
    row["rule_version"] = SOURCE_RULE_VERSION
    return row


def _normalise_state(state: dict[str, Any]) -> None:
    state.setdefault("schema_version", STATE_SCHEMA_VERSION)
    state.setdefault("sleeve", SLEEVE_NAME)
    state.setdefault("pending_entries", [])
    state.setdefault("open_positions", [])
    state.setdefault("closed_positions", [])
    state.setdefault("skipped_days", [])


def _pending_entry_from_trade(trade: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(trade)
    for key in (
        "entry_date",
        "entry_raw_open",
        "entry_price",
        "exit_date",
        "exit_raw_close",
        "exit_price",
        "pnl",
        "pnl_pct_net",
    ):
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
    open_positions = [
        row for row in state.get("open_positions") or [] if isinstance(row, dict)
    ]
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
        "volatility_relief_context": contexts[-1] if contexts else {"date": as_of, "passed": False},
        "context_scan": scan,
        "candidate_universe": leader._candidate_universe_summary(
            candidate_universe,
            rows_by_ticker,
        ),
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
        "realized_pnl_to_date": leader._round(
            sum(leader._float_or_none(row.get("pnl")) or 0.0 for row in closed),
            2,
        ),
        "unrealized_pnl": leader._unrealized_pnl(open_positions, rows_by_ticker, as_of),
        "forward_paper_gate": leader._forward_paper_gate(closed, config),
        "parameters": dict(config),
        "production_impact": _production_impact(),
        "next_action": "paper_observe_forward_outcomes_only_no_orders",
    }


def _parameter_summary() -> dict[str, Any]:
    return {
        "max_vixy_relief_return": MAX_VIXY_RELIEF_RETURN,
        "max_vixy_close_location": MAX_VIXY_CLOSE_LOCATION,
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


def _core_entries_by_date(entries: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for row in entries:
        if not isinstance(row, dict):
            continue
        date_value = str(row.get("entry_date") or row.get("date") or "")[:10]
        if date_value:
            out.setdefault(date_value, []).append(row)
    return out


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


def prep_and_build_volatility_relief_stock_leadership_snapshot(
    *,
    as_of: str,
    broad_market_ohlcv: dict,
    broad_market_candidate_universe: dict,
    spy_ohlcv=None,
    ohlcv_dict=None,
    cached_ohlcv_fn=None,
    core_entries=None,
    persist: bool = True,
):
    if not broad_market_candidate_universe.get("tickers"):
        return empty_volatility_relief_stock_leadership_snapshot(
            as_of, "broad_market_candidate_universe_unavailable")
    ohlcv = dict(broad_market_ohlcv)
    if "SPY" not in ohlcv and spy_ohlcv is not None:
        ohlcv["SPY"] = spy_ohlcv
    if "QQQ" not in ohlcv:
        ohlcv["QQQ"] = leader._lookup_ohlcv_source(ohlcv_dict, "QQQ", cached_ohlcv_fn)
    if "VIXY" not in ohlcv:
        ohlcv["VIXY"] = leader._lookup_ohlcv_source(ohlcv_dict, "VIXY", cached_ohlcv_fn)
    return build_volatility_relief_stock_leadership_snapshot(
        as_of=as_of, ohlcv_by_ticker=ohlcv,
        candidate_universe=broad_market_candidate_universe,
        core_entries=core_entries,
        persist=persist,
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
        "uses_free_ohlcv_only": True,
        "scope": "default_off_volatility_relief_stock_leadership_paper_attribution",
    }
