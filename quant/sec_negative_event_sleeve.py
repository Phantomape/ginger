"""Default-off SEC negative-reaction paper event sleeve.

This module turns the observe-only SEC negative-reaction forward queue into a
production-visible paper ledger. It does not emit orders, rank core candidates,
size positions, or consume core A/B slots.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from data_paths import data_artifact_path

try:
    from constants import ROUND_TRIP_COST_PCT
    from price_asof_guard import filter_prices_for_asof
    from sec_event_queue import PRIMARY_HORIZON_TRADING_DAYS, RULE_VERSION
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.price_asof_guard import filter_prices_for_asof
    from quant.sec_event_queue import PRIMARY_HORIZON_TRADING_DAYS, RULE_VERSION


SLEEVE_NAME = "SEC_NEGATIVE_REACTION_EVENT_SLEEVE_PAPER"
STATE_SCHEMA_VERSION = 1
DEFAULT_EVENT_NOTIONAL_USD = 10_000.0
DEFAULT_MAX_POSITIONS = 1
DEFAULT_STATE_PATH = data_artifact_path("sec_negative_event_sleeve_paper_state")
DEFAULT_SNAPSHOT_LOG_PATH = data_artifact_path("sec_negative_event_sleeve_paper_snapshots")

DEFAULT_CONFIG = {
    "enabled": False,
    "paper_enabled": True,
    "trade_enabled": False,
    "max_positions": DEFAULT_MAX_POSITIONS,
    "event_notional_usd": DEFAULT_EVENT_NOTIONAL_USD,
    "hold_days": PRIMARY_HORIZON_TRADING_DAYS,
    "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
    "fill_price_policy": "pending_next_session_open_when_available",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_sec_negative_event_sleeve_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_entries": [],
    }


def load_sec_negative_event_sleeve_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_sec_negative_event_sleeve_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_sec_negative_event_sleeve_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_sec_negative_event_sleeve_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_sec_negative_event_sleeve_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, sort_keys=True) + "\n")


def build_sec_negative_event_sleeve_snapshot(
    *,
    sec_event_queue: dict[str, Any] | None,
    as_of: str,
    open_prices: dict[str, Any] | None = None,
    current_prices: dict[str, Any] | None = None,
    open_price_dates: dict[str, Any] | None = None,
    current_price_dates: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
    persist: bool = True,
    state_path: Path | str = DEFAULT_STATE_PATH,
    snapshot_log_path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> dict[str, Any]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    cfg["enabled"] = False
    cfg["trade_enabled"] = False

    working_state = deepcopy(
        state if state is not None else load_sec_negative_event_sleeve_state(state_path)
    )
    _normalise_state(working_state)

    as_of_date = str(as_of)[:10]
    opens = filter_prices_for_asof(
        _normalise_prices(open_prices),
        open_price_dates,
        as_of=as_of_date,
    )
    closes = filter_prices_for_asof(
        _normalise_prices(current_prices),
        current_price_dates,
        as_of=as_of_date,
    )

    closed_today = _advance_open_positions(
        working_state,
        as_of=as_of_date,
        current_prices=closes,
        config=cfg,
    )
    filled_today, skipped_today = _fill_pending_entries(
        working_state,
        as_of=as_of_date,
        open_prices=opens,
        current_prices=closes,
        config=cfg,
    )
    new_pending = _add_queue_candidates(
        working_state,
        sec_event_queue or {},
        as_of=as_of_date,
        config=cfg,
    )

    snapshot = _snapshot_payload(
        working_state,
        sec_event_queue or {},
        as_of=as_of_date,
        config=cfg,
        new_pending=new_pending,
        filled_today=filled_today,
        closed_today=closed_today,
        skipped_today=skipped_today,
    )

    if persist:
        save_sec_negative_event_sleeve_state(working_state, state_path)
        append_sec_negative_event_sleeve_snapshot(snapshot, snapshot_log_path)
    return snapshot


def empty_sec_negative_event_sleeve_snapshot(as_of: str, reason: str) -> dict[str, Any]:
    return {
        "sleeve": SLEEVE_NAME,
        "asof_date": str(as_of)[:10],
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": False,
        "trade_enabled": False,
        "candidate_count": 0,
        "pending_count": 0,
        "open_position_count": 0,
        "closed_position_count": 0,
        "realized_pnl_to_date": 0.0,
        "unrealized_pnl": 0.0,
        "data_source": {"status": reason},
        "production_impact": _production_impact(),
        "error": reason,
    }


def _normalise_state(state: dict[str, Any]) -> None:
    state.setdefault("schema_version", STATE_SCHEMA_VERSION)
    state.setdefault("sleeve", SLEEVE_NAME)
    state.setdefault("pending_entries", [])
    state.setdefault("open_positions", [])
    state.setdefault("closed_positions", [])
    state.setdefault("skipped_entries", [])


def _normalise_prices(prices: dict[str, Any] | None) -> dict[str, float]:
    out: dict[str, float] = {}
    for ticker, value in (prices or {}).items():
        parsed = _float_or_none(value)
        if parsed is not None and parsed > 0:
            out[str(ticker).upper()] = parsed
    return out


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
    hold_days = int(config["hold_days"])
    cost = float(config["round_trip_cost_pct"])

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
        _mark_unrealized(position, current, cost)

        if int(position.get("observed_trading_days") or 0) >= hold_days:
            closed = _close_position(position, current, as_of, cost)
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

    max_positions = int(config["max_positions"])
    notional = float(config["event_notional_usd"])
    cost = float(config["round_trip_cost_pct"])
    remaining = []
    filled_today = []
    skipped_today = []

    for entry in sorted(state["pending_entries"], key=_pending_sort_key):
        if str(entry.get("created_asof") or "")[:10] >= as_of:
            remaining.append(entry)
            continue
        if len(state["open_positions"]) >= max_positions:
            skipped = {
                **entry,
                "status": "skipped_capacity_full",
                "skipped_asof": as_of,
                "trade_enabled": False,
            }
            state["skipped_entries"].append(skipped)
            skipped_today.append(skipped)
            continue

        ticker = str(entry.get("ticker") or "").upper()
        entry_open = open_prices.get(ticker)
        if entry_open is None:
            entry["status"] = "pending_missing_entry_open_price"
            entry["last_checked_asof"] = as_of
            remaining.append(entry)
            continue

        position = {
            "decision_id": entry["decision_id"],
            "sleeve": SLEEVE_NAME,
            "ticker": ticker,
            "source_event_date": entry.get("source_event_date"),
            "entry_date": as_of,
            "entry_price": entry_open,
            "notional": notional,
            "shares": round(notional / entry_open, 8),
            "hold_days": int(config["hold_days"]),
            "observed_trading_days": 0,
            "last_seen_date": as_of,
            "last_price": current_prices.get(ticker),
            "trade_enabled": False,
            "paper_status": "open",
            "source_candidate": entry.get("candidate") or {},
        }
        if position["last_price"] is not None:
            _mark_unrealized(position, float(position["last_price"]), cost)
        state["open_positions"].append(position)
        filled_today.append(position)

    state["pending_entries"] = remaining
    return filled_today, skipped_today


def _add_queue_candidates(
    state: dict[str, Any],
    queue: dict[str, Any],
    *,
    as_of: str,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    if not config.get("paper_enabled", True):
        return []
    existing_ids = _existing_decision_ids(state)
    new_entries = []
    for candidate in sorted(queue.get("candidates") or [], key=_candidate_sort_key):
        decision_id = _decision_id(candidate)
        if decision_id in existing_ids:
            continue
        entry = {
            "decision_id": decision_id,
            "sleeve": SLEEVE_NAME,
            "ticker": str(candidate.get("ticker") or "").upper(),
            "created_asof": as_of,
            "source_event_date": str(candidate.get("usable_trade_date") or "")[:10],
            "status": "pending_next_session_open",
            "intended_entry_timing": "next_session_open",
            "trade_enabled": False,
            "candidate": deepcopy(candidate),
        }
        state["pending_entries"].append(entry)
        new_entries.append(entry)
        existing_ids.add(decision_id)
    return new_entries


def _pending_sort_key(entry: dict[str, Any]) -> tuple[str, float, str]:
    candidate = entry.get("candidate") or {}
    return (
        str(entry.get("created_asof") or ""),
        float(candidate.get("reaction_excess_return") or 0.0),
        str(entry.get("ticker") or ""),
    )


def _candidate_sort_key(candidate: dict[str, Any]) -> tuple[float, str]:
    return (
        float(candidate.get("reaction_excess_return") or 0.0),
        str(candidate.get("ticker") or ""),
    )


def _existing_decision_ids(state: dict[str, Any]) -> set[str]:
    ids = set()
    for bucket in (
        "pending_entries",
        "open_positions",
        "closed_positions",
        "skipped_entries",
    ):
        ids.update(
            str(item.get("decision_id"))
            for item in state.get(bucket, [])
            if item.get("decision_id")
        )
    return ids


def _decision_id(candidate: dict[str, Any]) -> str:
    ticker = str(candidate.get("ticker") or "").upper()
    usable = str(candidate.get("usable_trade_date") or "")[:10]
    accession = str(candidate.get("accession_number") or "no_accession")
    return f"{SLEEVE_NAME}:{RULE_VERSION}:{usable}:{ticker}:{accession}"


def _mark_unrealized(
    position: dict[str, Any],
    current_price: float,
    round_trip_cost_pct: float,
) -> None:
    entry = float(position["entry_price"])
    notional = float(position["notional"])
    gross_return = current_price / entry - 1.0
    position["unrealized_return_pct"] = round(gross_return * 100.0, 6)
    position["unrealized_pnl"] = round(notional * gross_return, 2)
    position["net_pnl_if_closed_now"] = round(
        notional * (gross_return - round_trip_cost_pct),
        2,
    )


def _close_position(
    position: dict[str, Any],
    exit_price: float,
    exit_date: str,
    round_trip_cost_pct: float,
) -> dict[str, Any]:
    entry = float(position["entry_price"])
    notional = float(position["notional"])
    gross_return = exit_price / entry - 1.0
    net_return = gross_return - round_trip_cost_pct
    closed = dict(position)
    closed.update(
        {
            "paper_status": "closed",
            "exit_date": exit_date,
            "exit_price": exit_price,
            "gross_return_pct": round(gross_return * 100.0, 6),
            "net_return_pct": round(net_return * 100.0, 6),
            "pnl": round(notional * net_return, 2),
            "trade_enabled": False,
        }
    )
    return closed


def _snapshot_payload(
    state: dict[str, Any],
    queue: dict[str, Any],
    *,
    as_of: str,
    config: dict[str, Any],
    new_pending: list[dict[str, Any]],
    filled_today: list[dict[str, Any]],
    closed_today: list[dict[str, Any]],
    skipped_today: list[dict[str, Any]],
) -> dict[str, Any]:
    realized = round(
        sum(float(item.get("pnl") or 0.0) for item in state["closed_positions"]),
        2,
    )
    unrealized = round(
        sum(float(item.get("net_pnl_if_closed_now") or 0.0) for item in state["open_positions"]),
        2,
    )
    return {
        "sleeve": SLEEVE_NAME,
        "asof_date": as_of,
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": bool(config.get("paper_enabled", True)),
        "trade_enabled": False,
        "candidate_count": int(queue.get("candidate_count") or 0),
        "new_pending_count": len(new_pending),
        "filled_count": len(filled_today),
        "closed_count_today": len(closed_today),
        "skipped_count_today": len(skipped_today),
        "pending_count": len(state["pending_entries"]),
        "open_position_count": len(state["open_positions"]),
        "closed_position_count": len(state["closed_positions"]),
        "realized_pnl_to_date": realized,
        "unrealized_pnl": unrealized,
        "parameters": dict(config),
        "data_source": queue.get("data_source") or {},
        "new_pending_entries": deepcopy(new_pending),
        "filled_entries": deepcopy(filled_today),
        "closed_positions_today": deepcopy(closed_today),
        "closed_positions": deepcopy(state["closed_positions"]),
        "skipped_entries_today": deepcopy(skipped_today),
        "pending_entries": deepcopy(state["pending_entries"]),
        "open_positions": deepcopy(state["open_positions"]),
        "production_impact": _production_impact(),
        "next_action": (
            "paper_observe_forward_outcomes_only_no_orders"
            if config.get("paper_enabled", True)
            else "paper_harness_disabled"
        ),
    }


def _production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": False,
        "run_adapter_changed": True,
        "backtester_adapter_changed": False,
        "parity_test_added": False,
        "replay_only": False,
        "production_signal_path_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_orders": False,
        "scope": "default_off_sec_negative_reaction_paper_event_sleeve",
    }
