"""Shared default-off MOVE rate-volatility relief paper sleeve.

The fixed rule promoted from exp-20260711-002 is deliberately narrow: the
first ICE BofA MOVE close below its trailing 20-session mean marks rate-
volatility relief, then the unchanged exp-20260607-018 stock-leadership
selector admits at most two next-open, 10-session paper observations.

This module is paper-only.  It never changes core signals, ranking, sizing,
exits, LLM decisions, watchlists, or orders.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

try:
    import volatility_relief_stock_leadership_paper_sleeve as base
    from data_paths import DATA_ROOT
except ImportError:  # pragma: no cover
    from quant import volatility_relief_stock_leadership_paper_sleeve as base
    from quant.data_paths import DATA_ROOT


leader = base.leader
SLEEVE_NAME = "MOVE_RATE_VOLATILITY_RELIEF_LEADERSHIP_PAPER"
RULE_VERSION = "move_rate_volatility_relief_shared_default_off_adapter_v1"
SOURCE_RULE_VERSION = "move20_cross_below_rate_volatility_relief_stock_leadership_v1"
STATE_SCHEMA_VERSION = 1
MOVE_TICKER = "MOVE"
MOVE_DELIVERY_TICKER = "^MOVE"
MOVE_SMA_SESSIONS = 20

DEFAULT_STATE_PATH = DATA_ROOT / "paper_sleeves" / "move_rate_volatility_relief" / "state.json"
DEFAULT_SNAPSHOT_LOG_PATH = (
    DATA_ROOT / "paper_sleeves" / "move_rate_volatility_relief" / "snapshots.jsonl"
)
DEFAULT_CONFIG = dict(base.DEFAULT_CONFIG)


def empty_move_rate_volatility_relief_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_days": [],
    }


def _normalise_state(state: dict[str, Any]) -> None:
    state.setdefault("schema_version", STATE_SCHEMA_VERSION)
    state["sleeve"] = SLEEVE_NAME
    for key in ("pending_entries", "open_positions", "closed_positions", "skipped_days"):
        state.setdefault(key, [])


def load_move_rate_volatility_relief_state(path: Path | str = DEFAULT_STATE_PATH) -> dict[str, Any]:
    state_path = Path(path)
    state = empty_move_rate_volatility_relief_state()
    if state_path.exists():
        payload = json.loads(state_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            state.update(payload)
    _normalise_state(state)
    return state


def save_move_rate_volatility_relief_state(
    state: dict[str, Any], path: Path | str = DEFAULT_STATE_PATH
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = base.utc_now_iso()
    state_path.write_text(
        json.dumps(leader._safe(state), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def append_move_rate_volatility_relief_snapshot(
    snapshot: dict[str, Any], path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(leader._safe(snapshot), sort_keys=True) + "\n")


def move_rate_volatility_relief_context_for_day(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    signal_date: str,
) -> dict[str, Any] | None:
    rows = rows_by_ticker.get(MOVE_TICKER) or []
    idx = indices.get(MOVE_TICKER, {}).get(signal_date)
    if idx is None:
        return None
    context = {
        "date": signal_date,
        "move_sma_sessions": MOVE_SMA_SESSIONS,
        "rule_version": SOURCE_RULE_VERSION,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }
    if idx < MOVE_SMA_SESSIONS:
        return {**context, "passed": False, "reason": "insufficient_move_history"}
    closes = [leader._float_or_none(row.get("close")) for row in rows]
    current_window = closes[idx - MOVE_SMA_SESSIONS + 1 : idx + 1]
    prior_window = closes[idx - MOVE_SMA_SESSIONS : idx]
    current = closes[idx]
    previous = closes[idx - 1]
    if current is None or previous is None or any(
        value is None for value in current_window + prior_window
    ):
        return {**context, "passed": False, "reason": "missing_move_close"}
    current_sma = sum(float(value) for value in current_window) / MOVE_SMA_SESSIONS
    prior_sma = sum(float(value) for value in prior_window) / MOVE_SMA_SESSIONS
    passed = current < current_sma and previous >= prior_sma
    return {
        **context,
        "move_close": leader._round(current, 6),
        "move_prior_close": leader._round(previous, 6),
        "move_sma20": leader._round(current_sma, 6),
        "move_prior_sma20": leader._round(prior_sma, 6),
        "move_discount_to_sma20": leader._round(current / current_sma - 1.0, 6),
        "passed": passed,
        "reason": "move_first_cross_below_sma20" if passed else "not_first_cross_below_sma20",
    }


def move_rate_volatility_relief_candidate_for_ticker(**kwargs: Any) -> dict[str, Any] | None:
    context = kwargs["context"]
    row = base.leader._candidate_for_ticker(**kwargs)
    if row is None:
        return None
    row["source"] = SLEEVE_NAME
    row["move_rate_volatility_relief_context"] = row.pop("macro_relief_context", context)
    row["rule_version"] = SOURCE_RULE_VERSION
    return row


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
        "move_rate_volatility_relief_days": 0,
        "non_relief_days": 0,
        "days_with_raw_candidates": 0,
        "raw_candidates": 0,
        "rule_version": SOURCE_RULE_VERSION,
        "candidate_universe_count": len(universe),
    }
    for signal_date in dates:
        context = move_rate_volatility_relief_context_for_day(
            rows_by_ticker=rows_by_ticker, indices=indices, signal_date=signal_date
        )
        if context is None:
            continue
        if not context.get("passed"):
            scan["non_relief_days"] += 1
            contexts.append(context)
            continue
        scan["move_rate_volatility_relief_days"] += 1
        day_rows: list[dict[str, Any]] = []
        for ticker, sector_meta in universe.items():
            row = move_rate_volatility_relief_candidate_for_ticker(
                rows_by_ticker=rows_by_ticker,
                indices=indices,
                sector_meta=sector_meta,
                ticker=ticker,
                signal_date=signal_date,
                context=context,
            )
            if row is None:
                continue
            same_day = core_entries_by_date.get(signal_date, [])
            row["same_day_ab_entry_count"] = len(same_day)
            row["same_day_ab_overlap"] = bool(same_day)
            row["same_ticker_ab_overlap"] = any(
                str(trade.get("ticker") or "").upper() == ticker for trade in same_day
            )
            day_rows.append(row)
        day_rows.sort(key=leader._candidate_sort_key)
        candidates.extend(day_rows)
        if day_rows:
            scan["days_with_raw_candidates"] += 1
            scan["raw_candidates"] += len(day_rows)
        contexts.append({**context, "raw_candidate_count": len(day_rows)})
    candidates.sort(key=lambda row: (row["date"], *leader._candidate_sort_key(row)))
    scan.update({"move_sma_sessions": MOVE_SMA_SESSIONS, **base._parameter_summary()})
    return candidates, contexts, scan


def _retag_trade(trade: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(trade)
    ticker = str(out.get("ticker") or "").upper()
    signal_date = str(out.get("signal_date") or out.get("date") or "")[:10]
    out.update(
        {
            "decision_id": f"{SLEEVE_NAME}:{SOURCE_RULE_VERSION}:{signal_date}:{ticker}",
            "sleeve": SLEEVE_NAME,
            "source": SLEEVE_NAME,
            "source_rule_version": SOURCE_RULE_VERSION,
            "rule_version": SOURCE_RULE_VERSION,
        }
    )
    return out


def _select_trades(**kwargs: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected, filtered = base.select_paper_trades(**kwargs)
    return [_retag_trade(row) for row in selected], filtered


def build_move_rate_volatility_relief_historical_trades(
    *,
    ohlcv_by_ticker: dict[str, Any],
    dates: list[str],
    candidate_universe: dict[str, Any] | None = None,
    core_entries_by_date: dict[str, list[dict[str, Any]]] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows = leader._normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    candidates, contexts, scan = candidate_rows_for_dates(
        rows_by_ticker=rows,
        dates=dates,
        candidate_universe=candidate_universe,
        core_entries_by_date=core_entries_by_date,
    )
    selected, filtered = _select_trades(
        rows_by_ticker=rows, candidates=candidates, config=config
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


def _pending_entry(trade: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    pending = deepcopy(trade)
    for key in (
        "entry_date", "entry_raw_open", "entry_price", "exit_date",
        "exit_raw_close", "exit_price", "pnl", "pnl_pct_net", "net_return_pct",
    ):
        pending.pop(key, None)
    pending.update(
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
    return pending


def build_move_rate_volatility_relief_snapshot(
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
    cfg.update({"enabled": False, "trade_enabled": False})
    as_of_date = leader._date10(as_of)
    working = deepcopy(
        state if state is not None else load_move_rate_volatility_relief_state(state_path)
    )
    _normalise_state(working)
    rows = leader._normalise_ohlcv_by_ticker(ohlcv_by_ticker)
    filled = leader._fill_pending_entries(working, rows, as_of_date, cfg)
    closed = leader._advance_open_positions(working, rows, as_of_date, cfg)
    by_date = base._core_entries_by_date(core_entries or [])
    candidates, contexts, scan = candidate_rows_for_dates(
        rows_by_ticker=rows,
        dates=[as_of_date],
        candidate_universe=candidate_universe,
        core_entries_by_date=by_date,
    )
    selected, filtered = _select_trades(
        rows_by_ticker=rows,
        candidates=candidates,
        existing_state=working,
        config=cfg,
    )
    new_pending: list[dict[str, Any]] = []
    if cfg.get("paper_enabled", True):
        for trade in selected:
            pending = _pending_entry(trade, cfg)
            if not leader._has_pending_open_or_closed_decision(working, pending["decision_id"]):
                working["pending_entries"].append(pending)
                new_pending.append(pending)
    snapshot = base._snapshot_payload(
        working,
        as_of=as_of_date,
        candidates=candidates,
        selected=selected,
        filtered=filtered,
        contexts=contexts,
        scan=scan,
        new_pending_entries=new_pending,
        filled_today=filled,
        closed_today=closed,
        candidate_universe=candidate_universe,
        rows_by_ticker=rows,
        config=cfg,
    )
    snapshot.update(
        {
            "sleeve": SLEEVE_NAME,
            "rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "move_rate_volatility_relief_context": snapshot.pop(
                "volatility_relief_context", contexts[-1] if contexts else {"date": as_of_date, "passed": False}
            ),
            "production_impact": _production_impact(),
        }
    )
    if persist:
        save_move_rate_volatility_relief_state(working, state_path)
        append_move_rate_volatility_relief_snapshot(snapshot, snapshot_log_path)
    return snapshot


def empty_move_rate_volatility_relief_snapshot(as_of: str, reason: str) -> dict[str, Any]:
    snapshot = base.empty_volatility_relief_stock_leadership_snapshot(as_of, reason)
    snapshot.update(
        {
            "sleeve": SLEEVE_NAME,
            "rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "move_rate_volatility_relief_context": snapshot.pop("volatility_relief_context"),
            "production_impact": _production_impact(),
        }
    )
    return snapshot


def prep_and_build_move_rate_volatility_relief_snapshot(
    *,
    as_of: str,
    broad_market_ohlcv: dict[str, Any],
    broad_market_candidate_universe: dict[str, Any],
    spy_ohlcv: Any = None,
    ohlcv_dict: dict[str, Any] | None = None,
    cached_ohlcv_fn: Any = None,
    core_entries: list[dict[str, Any]] | None = None,
    persist: bool = True,
) -> dict[str, Any]:
    if not broad_market_candidate_universe.get("tickers"):
        return empty_move_rate_volatility_relief_snapshot(
            as_of, "broad_market_candidate_universe_unavailable"
        )
    ohlcv = dict(broad_market_ohlcv)
    if "SPY" not in ohlcv and spy_ohlcv is not None:
        ohlcv["SPY"] = spy_ohlcv
    for ticker in ("QQQ",):
        if ticker not in ohlcv:
            ohlcv[ticker] = leader._lookup_ohlcv_source(ohlcv_dict, ticker, cached_ohlcv_fn)
    if MOVE_TICKER not in ohlcv:
        value = None
        if isinstance(ohlcv_dict, dict):
            value = ohlcv_dict.get(MOVE_TICKER) or ohlcv_dict.get(MOVE_DELIVERY_TICKER)
        if value is None and cached_ohlcv_fn is not None:
            value = cached_ohlcv_fn(MOVE_DELIVERY_TICKER)
        ohlcv[MOVE_TICKER] = value
    return build_move_rate_volatility_relief_snapshot(
        as_of=as_of,
        ohlcv_by_ticker=ohlcv,
        candidate_universe=broad_market_candidate_universe,
        core_entries=core_entries,
        persist=persist,
    )


def _production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": True,
        "shared_policy_note": "default-off paper attribution only; core policy unchanged",
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
        "scope": "default_off_move_rate_volatility_relief_paper_attribution",
    }
