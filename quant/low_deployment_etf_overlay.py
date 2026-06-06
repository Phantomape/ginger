"""Default-off low-deployment ETF cash-substitute paper attribution.

This module tracks the accepted exp-20260605-035 alpha lead without turning it
into live orders. When the core strategy has at most one active core position,
it chooses one liquid ETF after the signal-date close by 20-day momentum with a
positive 200-day trend and positive 20-day momentum. Paper execution enters at
the next trading day's open and exits at the close 10 trading days after the
signal date.

The output is paper-only. It never changes core ranking, sizing, exits, or
orders. A trade-enabled adapter remains blocked until cash/risk-budget semantics
and forward outcomes pass a separate gate.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from constants import ROUND_TRIP_COST_PCT
from data_paths import data_artifact_path
from fill_model import SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET, apply_slippage
from open_position_schema import core_slot_positions


SLEEVE_NAME = "LOW_DEPLOYMENT_DYNAMIC_ETF_OVERLAY_PAPER"
RULE_VERSION = "low_deployment_etf_cash_substitute_v1"
STATE_SCHEMA_VERSION = 2

DEFAULT_STATE_PATH = data_artifact_path("low_deployment_etf_overlay_state")
DEFAULT_SNAPSHOT_LOG_PATH = data_artifact_path("low_deployment_etf_overlay_snapshots")

DEFAULT_CONFIG = {
    "enabled": False,
    "paper_enabled": True,
    "trade_enabled": False,
    "candidate_tickers": ("QQQ", "SPY", "IWM", "GLD", "SLV"),
    "sleeve_slot_capacity": 1,
    # Only genuine core-strategy positions feed the low-deployment context.
    # This is not a sleeve-capacity gate; the overlay owns a separate paper slot.
    "max_active_core_positions": 1,
    "max_overlay_open_positions": 1,
    "paper_notional_fraction_of_portfolio": 1.0,
    "fallback_paper_notional_usd": 100_000.0,
    "hold_days": 10,
    "state_sma_days": 200,
    "state_momentum_days": 20,
    "forward_gate_min_closed_trades": 60,
    "forward_gate_min_win_rate": 0.52,
    "forward_gate_positive_net_pnl": True,
    "forward_gate_max_single_ticker_positive_share": 0.75,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_low_deployment_etf_overlay_snapshot(as_of: str, reason: str) -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "asof_date": str(as_of)[:10],
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": False,
        "trade_enabled": False,
        "candidate_count": 0,
        "new_pending_count": 0,
        "pending_count": 0,
        "filled_count": 0,
        "open_position_count": 0,
        "closed_count_today": 0,
        "closed_position_count": 0,
        "realized_pnl_to_date": 0.0,
        "unrealized_pnl": 0.0,
        "candidate": None,
        "candidates": [],
        "new_pending_entries": [],
        "filled_today": [],
        "open_positions": [],
        "closed_today": [],
        "closed_positions_today": [],
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "production_impact": _production_impact(),
        "error": reason,
    }


def empty_low_deployment_etf_overlay_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_days": [],
    }


def load_low_deployment_etf_overlay_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_low_deployment_etf_overlay_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_low_deployment_etf_overlay_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_low_deployment_etf_overlay_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_low_deployment_etf_overlay_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, sort_keys=True) + "\n")


def build_low_deployment_etf_overlay_snapshot(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any],
    open_positions: dict[str, Any] | None = None,
    portfolio_value: float | None = None,
    state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    persist: bool = True,
    state_path: Path | str = DEFAULT_STATE_PATH,
    snapshot_log_path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> dict[str, Any]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    cfg["enabled"] = False
    cfg["trade_enabled"] = False
    as_of_date = str(as_of)[:10]
    working_state = deepcopy(
        state if state is not None else load_low_deployment_etf_overlay_state(state_path)
    )
    _normalise_state(working_state)

    active_core_positions = _active_core_position_count(
        open_positions,
        overlay_tickers={str(ticker).upper() for ticker in cfg["candidate_tickers"]},
    )
    core_deployment_context = _core_deployment_context(active_core_positions, cfg)

    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(ohlcv_by_ticker.get(ticker))
        for ticker in cfg["candidate_tickers"]
    }
    filled_today = _fill_pending_entries(
        working_state,
        rows_by_ticker=rows_by_ticker,
        as_of=as_of_date,
        config=cfg,
    )
    closed_today = _advance_open_positions(
        working_state,
        rows_by_ticker=rows_by_ticker,
        as_of=as_of_date,
        config=cfg,
    )
    skipped_today: list[dict[str, Any]] = []
    candidate: dict[str, Any] | None = None
    new_pending_entries: list[dict[str, Any]] = []
    active_overlay_positions = _active_overlay_position_count(working_state)
    if not core_deployment_context["low_deployment_condition_passed"]:
        skipped = _skip_payload(
            as_of_date,
            "core_above_low_deployment_threshold",
            active_core_positions=active_core_positions,
            core_deployment_context=core_deployment_context,
            config=cfg,
        )
        _append_skip_once(working_state, skipped)
        skipped_today.append(skipped)
    elif active_overlay_positions >= int(cfg["max_overlay_open_positions"]):
        skipped = _skip_payload(
            as_of_date,
            "overlay_position_cap_full",
            active_core_positions=active_core_positions,
            core_deployment_context=core_deployment_context,
            config=cfg,
        )
        _append_skip_once(working_state, skipped)
        skipped_today.append(skipped)
    else:
        candidate = _select_candidate(
            rows_by_ticker,
            as_of=as_of_date,
            active_core_positions=active_core_positions,
            core_deployment_context=core_deployment_context,
            config=cfg,
        )
    if (
        candidate is not None
        and cfg.get("paper_enabled", True)
        and not _has_pending_or_open_decision(working_state, candidate["decision_id"])
    ):
        pending = _pending_entry_from_candidate(
            candidate,
            portfolio_value=portfolio_value,
            config=cfg,
        )
        working_state["pending_entries"].append(pending)
        new_pending_entries.append(pending)
    elif candidate is None and not skipped_today:
        skipped = _skip_payload(
            as_of_date,
            "no_positive_trend_momentum_etf_candidate",
            active_core_positions=active_core_positions,
            core_deployment_context=core_deployment_context,
            config=cfg,
        )
        _append_skip_once(working_state, skipped)
        skipped_today.append(skipped)

    snapshot = _snapshot_payload(
        working_state,
        as_of=as_of_date,
        candidate=candidate,
        new_pending_entries=new_pending_entries,
        filled_today=filled_today,
        closed_today=closed_today,
        skipped_today=skipped_today,
        active_core_positions=active_core_positions,
        core_deployment_context=core_deployment_context,
        rows_by_ticker=rows_by_ticker,
        config=cfg,
    )
    if persist:
        save_low_deployment_etf_overlay_state(working_state, state_path)
        append_low_deployment_etf_overlay_snapshot(snapshot, snapshot_log_path)
    return snapshot


def _normalise_state(state: dict[str, Any]) -> None:
    state.setdefault("schema_version", STATE_SCHEMA_VERSION)
    state.setdefault("sleeve", SLEEVE_NAME)
    state.setdefault("pending_entries", [])
    state.setdefault("open_positions", [])
    state.setdefault("closed_positions", [])
    state.setdefault("skipped_days", [])


def _active_core_position_count(
    open_positions: dict[str, Any] | None,
    *,
    overlay_tickers: set[str],
) -> int:
    count = 0
    for row in core_slot_positions(open_positions):
        ticker = str(row.get("ticker") or "").upper()
        shares = _float_or_none(row.get("shares")) or 0.0
        if ticker and shares > 0 and ticker not in overlay_tickers:
            count += 1
    return count


def _core_deployment_context(
    active_core_positions: int,
    config: dict[str, Any],
) -> dict[str, Any]:
    max_active = int(config["max_active_core_positions"])
    low_deployment_passed = active_core_positions <= max_active
    status = "passed" if low_deployment_passed else "core_above_reference_threshold"
    return {
        "slot_policy": "sleeve_independent_paper_slot",
        "sleeve_slot_capacity": int(config.get("sleeve_slot_capacity", 1)),
        "active_core_positions": active_core_positions,
        "max_active_core_positions": max_active,
        "low_deployment_condition_passed": low_deployment_passed,
        "low_deployment_condition_status": status,
        "core_capacity_blocks_observation": False,
        "trade_enabled": False,
        "alters_orders": False,
    }


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
                    "close": _float_or_none(row.get("Close")),
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
                    "close": _float_or_none(raw.get("Close") or raw.get("close")),
                }
            )
    return sorted([row for row in rows if row.get("date")], key=lambda row: row["date"])


def _select_candidate(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    *,
    as_of: str,
    active_core_positions: int,
    core_deployment_context: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any] | None:
    candidates = []
    for ticker, rows in rows_by_ticker.items():
        idx = _index_on_date(rows, as_of)
        if idx is None:
            continue
        state = _candidate_state(rows, idx, config)
        if state is None:
            continue
        signal_row = rows[idx]
        candidates.append(
            {
                "ticker": ticker,
                "signal_date": signal_row["date"],
                "date": signal_row["date"],
                "decision_date": state["decision_date"],
                "entry_date": None,
                "entry_timing": "next_session_open",
                "active_core_positions": active_core_positions,
                "core_deployment_context": deepcopy(core_deployment_context),
                "slot_policy": core_deployment_context["slot_policy"],
                "sleeve_slot_capacity": core_deployment_context["sleeve_slot_capacity"],
                "low_deployment_condition_passed": core_deployment_context[
                    "low_deployment_condition_passed"
                ],
                "low_deployment_condition_status": core_deployment_context[
                    "low_deployment_condition_status"
                ],
                "core_capacity_blocks_observation": False,
                "signal_close": _round(state["signal_close"], 4),
                "sma200": _round(state["sma200"], 4),
                "momentum20": _round(state["momentum20"], 6),
                "prior_close": _round(state["signal_close"], 4),
                "prior_sma200": _round(state["sma200"], 4),
                "prior_momentum20": _round(state["momentum20"], 6),
                "state": state,
            }
        )
    if not candidates:
        return None
    chosen = max(candidates, key=lambda row: (row["prior_momentum20"], row["ticker"]))
    chosen["decision_id"] = (
        f"{SLEEVE_NAME}:{RULE_VERSION}:{chosen['signal_date']}:{chosen['ticker']}"
    )
    chosen["paper_enabled"] = bool(config.get("paper_enabled", True))
    chosen["trade_enabled"] = False
    chosen["alters_orders"] = False
    chosen["admission_reason"] = (
        "low_deployment_condition_passed"
        if chosen["low_deployment_condition_passed"]
        else "core_above_low_deployment_threshold"
    )
    return chosen


def _candidate_state(
    rows: list[dict[str, Any]],
    trade_idx: int,
    config: dict[str, Any],
) -> dict[str, Any] | None:
    sma_days = int(config["state_sma_days"])
    momentum_days = int(config["state_momentum_days"])
    if trade_idx < max(sma_days, momentum_days):
        return None
    signal = rows[trade_idx]
    signal_close = _positive_float(signal.get("close"))
    if not signal_close:
        return None
    sma_window = rows[trade_idx - sma_days + 1 : trade_idx + 1]
    sma_values = [_positive_float(row.get("close")) for row in sma_window]
    if any(value is None for value in sma_values) or len(sma_values) != sma_days:
        return None
    sma = sum(float(value) for value in sma_values) / len(sma_values)
    momentum_base = _positive_float(rows[trade_idx - momentum_days].get("close"))
    if not momentum_base:
        return None
    momentum = signal_close / momentum_base - 1.0
    if signal_close <= sma or momentum <= 0.0:
        return None
    return {
        "decision_date": signal["date"],
        "signal_close": signal_close,
        "sma200": sma,
        "momentum20": momentum,
    }


def _pending_entry_from_candidate(
    candidate: dict[str, Any],
    *,
    portfolio_value: float | None,
    config: dict[str, Any],
) -> dict[str, Any]:
    base_notional = _float_or_none(portfolio_value)
    if base_notional is None or base_notional <= 0:
        base_notional = float(config["fallback_paper_notional_usd"])
    notional = base_notional * float(config["paper_notional_fraction_of_portfolio"])
    out = deepcopy(candidate)
    out.update(
        {
            "sleeve": SLEEVE_NAME,
            "rule_version": RULE_VERSION,
            "notional_usd": _round(notional, 2),
            "paper_notional_usd": _round(notional, 2),
            "entry_after_signal_date": candidate["signal_date"],
            "hold_days": int(config["hold_days"]),
            "paper_status": "pending_entry",
            "trade_enabled": False,
            "alters_orders": False,
        }
    )
    return out


def _fill_pending_entries(
    state: dict[str, Any],
    *,
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
        rows = rows_by_ticker.get(ticker) or []
        idx = _index_on_date(rows, as_of)
        if idx is None or as_of <= str(pending.get("signal_date") or ""):
            still_pending.append(pending)
            continue
        open_price = _positive_float(rows[idx].get("open"))
        if open_price is None:
            still_pending.append(pending)
            continue
        entry_price = apply_slippage(open_price, SLIPPAGE_BPS_ENTRY, "buy")
        opened = deepcopy(pending)
        opened.update(
            {
                "entry_date": as_of,
                "entry_raw_open": _round(open_price, 4),
                "entry_price": _round(entry_price, 4),
                "paper_status": "open",
                "observed_trading_days": 1,
                "last_observed_date": as_of,
            }
        )
        state["open_positions"].append(opened)
        filled_today.append(opened)
    state["pending_entries"] = still_pending
    return filled_today


def _advance_open_positions(
    state: dict[str, Any],
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    as_of: str,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    still_open: list[dict[str, Any]] = []
    closed_today: list[dict[str, Any]] = []
    hold_days = int(config["hold_days"])
    for position in state.get("open_positions") or []:
        if not isinstance(position, dict):
            continue
        ticker = str(position.get("ticker") or "").upper()
        rows = rows_by_ticker.get(ticker) or []
        idx = _index_on_date(rows, as_of)
        if idx is None or as_of < str(position.get("entry_date") or ""):
            still_open.append(position)
            continue
        working = deepcopy(position)
        if str(working.get("last_observed_date") or "") != as_of:
            working["observed_trading_days"] = int(working.get("observed_trading_days") or 0) + 1
            working["last_observed_date"] = as_of
        if int(working.get("observed_trading_days") or 0) < hold_days:
            still_open.append(working)
            continue
        close_price = _positive_float(rows[idx].get("close"))
        entry_price = _positive_float(working.get("entry_price"))
        notional = _positive_float(working.get("notional_usd")) or _positive_float(
            working.get("paper_notional_usd")
        )
        if close_price is None or entry_price is None or notional is None:
            still_open.append(working)
            continue
        exit_price = apply_slippage(close_price, SLIPPAGE_BPS_TARGET, "sell")
        pnl_pct_net = (exit_price / entry_price) - 1.0 - ROUND_TRIP_COST_PCT
        pnl = notional * pnl_pct_net
        closed = deepcopy(working)
        closed.update(
            {
                "exit_date": as_of,
                "exit_raw_close": _round(close_price, 4),
                "exit_price": _round(exit_price, 4),
                "pnl_pct_net": _round(pnl_pct_net, 6),
                "net_return_pct": _round(pnl_pct_net, 6),
                "pnl": _round(pnl, 2),
                "paper_status": "closed",
                "trade_enabled": False,
                "alters_orders": False,
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
    candidate: dict[str, Any] | None,
    new_pending_entries: list[dict[str, Any]],
    filled_today: list[dict[str, Any]],
    closed_today: list[dict[str, Any]],
    skipped_today: list[dict[str, Any]],
    active_core_positions: int,
    core_deployment_context: dict[str, Any],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    config: dict[str, Any],
) -> dict[str, Any]:
    pending = [row for row in state.get("pending_entries") or [] if isinstance(row, dict)]
    open_positions = [row for row in state.get("open_positions") or [] if isinstance(row, dict)]
    closed = [row for row in state.get("closed_positions") or [] if isinstance(row, dict)]
    realized = round(sum(_float_or_none(row.get("pnl")) or 0.0 for row in closed), 2)
    wins = sum(1 for row in closed if (_float_or_none(row.get("pnl")) or 0.0) > 0)
    win_rate = round(wins / len(closed), 4) if closed else None
    unrealized = _unrealized_pnl(open_positions, rows_by_ticker, as_of)
    gate = _forward_paper_gate(closed, config)
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "asof_date": as_of,
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": bool(config.get("paper_enabled", True)),
        "trade_enabled": False,
        "trade_enabled_reason": (
            "default_off_until_forward_gate_cash_semantics_and_live_adapter_pass"
        ),
        "candidate_count": 1 if candidate else 0,
        "candidate": candidate,
        "candidates": [candidate] if candidate else [],
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
        "skipped_today": skipped_today,
        "skipped_count_today": len(skipped_today),
        "active_core_positions": active_core_positions,
        "max_active_core_positions": int(config["max_active_core_positions"]),
        "core_deployment_context": deepcopy(core_deployment_context),
        "slot_policy": core_deployment_context["slot_policy"],
        "sleeve_slot_capacity": core_deployment_context["sleeve_slot_capacity"],
        "low_deployment_condition_passed": core_deployment_context[
            "low_deployment_condition_passed"
        ],
        "low_deployment_condition_status": core_deployment_context[
            "low_deployment_condition_status"
        ],
        "core_capacity_blocks_observation": False,
        "closed_position_count": len(closed),
        "closed_positions": closed,
        "realized_pnl_to_date": realized,
        "unrealized_pnl": unrealized,
        "win_rate": win_rate,
        "forward_paper_gate": gate,
        "parameters": dict(config),
        "production_impact": _production_impact(),
        "next_action": "paper_observe_forward_outcomes_only_no_orders",
    }


def _forward_paper_gate(
    closed_positions: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    closed = [row for row in closed_positions if isinstance(row, dict)]
    realized = round(sum(_float_or_none(row.get("pnl")) or 0.0 for row in closed), 2)
    wins = sum(1 for row in closed if (_float_or_none(row.get("pnl")) or 0.0) > 0)
    win_rate = round(wins / len(closed), 4) if closed else None
    concentration = _single_ticker_positive_share(closed)
    checks = {
        "min_closed_trades": len(closed) >= int(config["forward_gate_min_closed_trades"]),
        "positive_net_pnl": (
            realized > 0 if bool(config["forward_gate_positive_net_pnl"]) else True
        ),
        "min_win_rate": win_rate is not None
        and win_rate >= float(config["forward_gate_min_win_rate"]),
        "max_single_ticker_positive_share": concentration is not None
        and concentration <= float(config["forward_gate_max_single_ticker_positive_share"]),
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
            "single_ticker_positive_share": concentration,
        },
        "thresholds": {
            "min_closed_trades": int(config["forward_gate_min_closed_trades"]),
            "min_win_rate": float(config["forward_gate_min_win_rate"]),
            "max_single_ticker_positive_share": float(
                config["forward_gate_max_single_ticker_positive_share"]
            ),
        },
        "trade_enabled_after_gate": False,
    }


def _single_ticker_positive_share(rows: list[dict[str, Any]]) -> float | None:
    by_ticker: dict[str, float] = {}
    total_positive = 0.0
    for row in rows:
        pnl = _float_or_none(row.get("pnl")) or 0.0
        if pnl <= 0:
            continue
        total_positive += pnl
        ticker = str(row.get("ticker") or "").upper()
        by_ticker[ticker] = by_ticker.get(ticker, 0.0) + pnl
    if total_positive <= 0 or not by_ticker:
        return None
    return round(max(by_ticker.values()) / total_positive, 4)


def _skip_payload(
    as_of: str,
    reason: str,
    *,
    active_core_positions: int,
    core_deployment_context: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    return {
        "decision_id": f"{SLEEVE_NAME}:{RULE_VERSION}:{as_of}:SKIP:{reason}",
        "date": as_of,
        "reason": reason,
        "active_core_positions": active_core_positions,
        "max_active_core_positions": int(config["max_active_core_positions"]),
        "core_deployment_context": deepcopy(core_deployment_context),
        "slot_policy": core_deployment_context["slot_policy"],
        "sleeve_slot_capacity": core_deployment_context["sleeve_slot_capacity"],
        "low_deployment_condition_passed": core_deployment_context[
            "low_deployment_condition_passed"
        ],
        "low_deployment_condition_status": core_deployment_context[
            "low_deployment_condition_status"
        ],
        "core_capacity_blocks_observation": False,
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


def _has_pending_or_open_decision(state: dict[str, Any], decision_id: str) -> bool:
    for bucket in ("pending_entries", "open_positions"):
        if any(
            str(row.get("decision_id") or "") == decision_id
            for row in state.get(bucket) or []
            if isinstance(row, dict)
        ):
            return True
    return False


def _active_overlay_position_count(state: dict[str, Any]) -> int:
    pending = [row for row in state.get("pending_entries") or [] if isinstance(row, dict)]
    open_positions = [
        row for row in state.get("open_positions") or [] if isinstance(row, dict)
    ]
    return len(pending) + len(open_positions)


def _unrealized_pnl(
    open_positions: list[dict[str, Any]],
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    as_of: str,
) -> float:
    total = 0.0
    for position in open_positions:
        ticker = str(position.get("ticker") or "").upper()
        rows = rows_by_ticker.get(ticker) or []
        idx = _index_on_date(rows, as_of)
        if idx is None:
            continue
        close_price = _positive_float(rows[idx].get("close"))
        entry_price = _positive_float(position.get("entry_price"))
        notional = _positive_float(position.get("notional_usd")) or _positive_float(
            position.get("paper_notional_usd")
        )
        if close_price is None or entry_price is None or notional is None:
            continue
        total += notional * (close_price / entry_price - 1.0)
    return round(total, 2)


def _index_on_date(rows: list[dict[str, Any]], as_of: str) -> int | None:
    target = str(as_of)[:10]
    for idx, row in enumerate(rows):
        if str(row.get("date") or "") == target:
            return idx
    return None


def _latest_index_on_or_before(rows: list[dict[str, Any]], as_of: str) -> int | None:
    matches = [
        idx
        for idx, row in enumerate(rows)
        if str(row.get("date") or "") <= str(as_of)[:10]
    ]
    return max(matches) if matches else None


def replay_low_deployment_etf_cash_substitute_trades(
    *,
    core_backtest_result: dict[str, Any],
    ohlcv_by_ticker: dict[str, Any],
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Replay the shared cash-substitute paper semantics on a backtest result.

    This is the historical counterpart of ``build_low_deployment_etf_overlay_snapshot``.
    It uses the same ETF selector, low-deployment definition, one-open-position
    cap, next-open entry, 10-trading-day close exit, slippage, and cost model.
    """

    cfg = {**DEFAULT_CONFIG, **(config or {})}
    cfg["enabled"] = False
    cfg["trade_enabled"] = False
    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(ohlcv_by_ticker.get(ticker))
        for ticker in cfg["candidate_tickers"]
    }
    core_counts = _core_active_count_by_date(core_backtest_result)
    open_overlay_exits: list[str] = []
    trades: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    low_deployment_day_count = 0
    selectable_day_count = 0

    for day, _ in core_backtest_result.get("equity_curve") or []:
        signal_date = str(day)[:10]
        open_overlay_exits = [
            exit_date for exit_date in open_overlay_exits if exit_date > signal_date
        ]
        active_core_positions = int(core_counts.get(signal_date, 0))
        context = _core_deployment_context(active_core_positions, cfg)
        if not context["low_deployment_condition_passed"]:
            skipped["core_above_low_deployment_threshold"] += 1
            continue
        low_deployment_day_count += 1
        if len(open_overlay_exits) >= int(cfg["max_overlay_open_positions"]):
            skipped["overlay_position_cap_full"] += 1
            continue
        selection = _select_candidate(
            rows_by_ticker,
            as_of=signal_date,
            active_core_positions=active_core_positions,
            core_deployment_context=context,
            config=cfg,
        )
        if selection is None:
            skipped["no_etf_passing_signal_close_state"] += 1
            continue
        selectable_day_count += 1
        trade = _replay_trade_from_candidate(
            rows_by_ticker=rows_by_ticker,
            candidate=selection,
            config=cfg,
        )
        if trade is None:
            skipped["missing_entry_or_exit_price"] += 1
            continue
        trades.append(trade)
        open_overlay_exits.append(str(trade["exit_date"]))

    return trades, {
        "low_deployment_day_count": low_deployment_day_count,
        "selectable_day_count_before_position_cap": selectable_day_count,
        "skipped": dict(skipped),
        "max_active_core_positions": int(cfg["max_active_core_positions"]),
        "max_overlay_open_positions": int(cfg["max_overlay_open_positions"]),
    }


def _core_active_count_by_date(result: dict[str, Any]) -> dict[str, int]:
    curve_dates = [str(day)[:10] for day, _ in result.get("equity_curve") or []]
    counts = {day: 0 for day in curve_dates}
    for trade in result.get("trades") or []:
        if trade.get("strategy") not in {"trend_long", "breakout_long"}:
            continue
        entry_date = str(trade.get("entry_date") or "")[:10]
        exit_date = str(trade.get("exit_date") or "")[:10]
        if not entry_date or not exit_date:
            continue
        for day in curve_dates:
            if entry_date <= day <= exit_date:
                counts[day] = counts.get(day, 0) + 1
    return counts


def _replay_trade_from_candidate(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    candidate: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any] | None:
    ticker = str(candidate["ticker"]).upper()
    rows = rows_by_ticker.get(ticker) or []
    signal_idx = _index_on_date(rows, str(candidate["signal_date"]))
    if signal_idx is None:
        return None
    entry_idx = signal_idx + 1
    exit_idx = signal_idx + int(config["hold_days"])
    if entry_idx >= len(rows) or exit_idx >= len(rows):
        return None
    entry_raw = _positive_float(rows[entry_idx].get("open"))
    exit_raw = _positive_float(rows[exit_idx].get("close"))
    if entry_raw is None or exit_raw is None:
        return None
    entry_price = apply_slippage(entry_raw, SLIPPAGE_BPS_ENTRY, "buy")
    exit_price = apply_slippage(exit_raw, SLIPPAGE_BPS_TARGET, "sell")
    notional = float(config["fallback_paper_notional_usd"])
    pnl_pct_net = (exit_price / entry_price) - 1.0 - ROUND_TRIP_COST_PCT
    pnl = notional * pnl_pct_net
    return {
        "ticker": ticker,
        "source": "low_deployment_etf_cash_substitute",
        "date": candidate["signal_date"],
        "signal_date": candidate["signal_date"],
        "decision_id": candidate["decision_id"],
        "entry_date": rows[entry_idx]["date"],
        "exit_date": rows[exit_idx]["date"],
        "active_core_positions_on_signal": candidate["active_core_positions"],
        "entry_raw_open": _round(entry_raw, 4),
        "exit_raw_close": _round(exit_raw, 4),
        "entry_price": _round(entry_price, 4),
        "exit_price": _round(exit_price, 4),
        "hold_days": int(config["hold_days"]),
        "paper_notional_usd": _round(notional, 2),
        "pnl_pct_net": _round(pnl_pct_net, 6),
        "pnl": _round(pnl, 2),
        "selector_state": {
            "signal_close": candidate["signal_close"],
            "sma200": candidate["sma200"],
            "momentum20": candidate["momentum20"],
        },
        "trade_enabled": False,
        "alters_orders": False,
    }


def _date10(value: Any) -> str | None:
    if value is None:
        return None
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


def _production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": True,
        "shared_policy_note": "paper attribution module only; core trading policy unchanged",
        "backtester_adapter_changed": False,
        "run_adapter_changed": True,
        "replay_only": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "alters_orders": False,
        "trade_enabled": False,
        "scope": "default_off_low_deployment_etf_overlay_paper_attribution",
    }
