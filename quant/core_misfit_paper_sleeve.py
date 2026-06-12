"""Default-off core-misfit paper sleeve.

This module turns historically negative-for-core long signals into a
production-visible paper ledger. It never emits orders, changes core ranking,
changes sizing, consumes slots, or enables short selling.
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
    from price_asof_guard import filter_prices_for_asof
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.price_asof_guard import filter_prices_for_asof


SLEEVE_NAME = "CORE_MISFIT_PAPER"
RULE_VERSION = "core_misfit_negative_signal_v2"
NO_TRADE_ALPHA_REPORT_RULE_VERSION = "core_misfit_no_trade_alpha_report_v1"
STATE_SCHEMA_VERSION = 1

DEFAULT_STATE_PATH = data_artifact_path("core_misfit_paper_state")
DEFAULT_SNAPSHOT_LOG_PATH = data_artifact_path("core_misfit_paper_snapshots")

DEFAULT_MISFIT_TICKERS = ("TSM", "ISRG", "V", "DDOG")
DEFAULT_TARGET_STRATEGIES = ("trend_long",)
DEFAULT_HORIZONS = (1, 3, 5, 10)

DEFAULT_CONFIG = {
    "enabled": False,
    "paper_enabled": True,
    "trade_enabled": False,
    "misfit_tickers": DEFAULT_MISFIT_TICKERS,
    "target_strategies": DEFAULT_TARGET_STRATEGIES,
    "horizons_trading_days": DEFAULT_HORIZONS,
    "primary_horizon_days": 10,
    "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
    "fill_price_policy": "pending_next_session_open_when_available",
    "forward_gate_min_closed_primary_outcomes": 20,
    "forward_gate_positive_no_trade_value": True,
    "forward_gate_positive_inverse_pnl": True,
    "forward_gate_max_single_ticker_inverse_positive_share": 0.75,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_core_misfit_paper_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_outcomes": [],
        "skipped_entries": [],
    }


def load_core_misfit_paper_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_core_misfit_paper_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_core_misfit_paper_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_core_misfit_paper_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_core_misfit_paper_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, sort_keys=True) + "\n")


def build_core_misfit_paper_sleeve_snapshot(
    *,
    as_of: str,
    candidate_signals: list[dict[str, Any]] | None = None,
    entry_execution_plan: dict[str, Any] | None = None,
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
    cfg = _config(config)
    working_state = deepcopy(
        state if state is not None else load_core_misfit_paper_state(state_path)
    )
    _normalise_state(working_state)

    as_of_date = _date10(as_of)
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
    candidates = build_core_misfit_paper_candidates(
        candidate_signals=candidate_signals or [],
        entry_execution_plan=entry_execution_plan or {},
        as_of=as_of_date,
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
        candidates=candidates,
        new_pending=new_pending,
        filled_today=filled_today,
        closed_today=closed_today,
        skipped_today=skipped_today,
    )
    if persist:
        save_core_misfit_paper_state(working_state, state_path)
        append_core_misfit_paper_snapshot(snapshot, snapshot_log_path)
    return snapshot


def empty_core_misfit_paper_sleeve_snapshot(as_of: str, reason: str) -> dict[str, Any]:
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
        "closed_outcome_count": 0,
        "primary_closed_outcome_count": 0,
        "realized_fast_long_pnl_to_date": 0.0,
        "realized_no_trade_value_to_date": 0.0,
        "realized_inverse_pnl_to_date": 0.0,
        "unrealized_fast_long_pnl": 0.0,
        "unrealized_no_trade_value": 0.0,
        "unrealized_inverse_pnl": 0.0,
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "data_source": {"status": reason},
        "production_impact": _production_impact(),
        "error": reason,
    }


def build_core_misfit_paper_candidates(
    *,
    candidate_signals: list[dict[str, Any]],
    entry_execution_plan: dict[str, Any],
    as_of: str,
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    cfg = _config(config)
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()

    selected = list(candidate_signals or [])
    sliced = list((entry_execution_plan or {}).get("slot_sliced_signals") or [])
    for source_kind, signals in (
        ("selected_core_signal", selected),
        ("slot_sliced_core_signal", sliced),
    ):
        for rank, signal in enumerate(signals, start=1):
            candidate = _candidate_from_signal(
                signal,
                as_of=_date10(as_of),
                source_kind=source_kind,
                source_rank=rank,
                config=cfg,
            )
            if candidate is None:
                continue
            if candidate["decision_id"] in seen:
                continue
            candidates.append(candidate)
            seen.add(candidate["decision_id"])
    return candidates


def _candidate_from_signal(
    signal: dict[str, Any],
    *,
    as_of: str,
    source_kind: str,
    source_rank: int,
    config: dict[str, Any],
) -> dict[str, Any] | None:
    ticker = str(signal.get("ticker") or "").upper()
    strategy = str(signal.get("strategy") or "")
    if ticker not in _ticker_set(config):
        return None
    if strategy not in _strategy_set(config):
        return None

    sizing = signal.get("sizing") or {}
    shares = int(_float_or_none(sizing.get("shares_to_buy")) or 0)
    if shares <= 0:
        return None
    entry_price = _float_or_none(sizing.get("entry_price")) or _float_or_none(
        signal.get("entry_price")
    )
    if not entry_price or entry_price <= 0:
        return None
    notional = _float_or_none(sizing.get("position_value_usd"))
    if not notional or notional <= 0:
        notional = shares * entry_price

    stop_price = _float_or_none(signal.get("stop_price"))
    target_price = _float_or_none(signal.get("target_price"))
    risk_reward = _float_or_none(signal.get("risk_reward_ratio"))
    decision_id = _decision_id(
        as_of=as_of,
        ticker=ticker,
        strategy=strategy,
        source_kind=source_kind,
        entry_price=entry_price,
    )
    return {
        "decision_id": decision_id,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "ticker": ticker,
        "strategy": strategy,
        "asof_date": as_of,
        "source_kind": source_kind,
        "source_rank": source_rank,
        "shares": shares,
        "intended_entry_price": round(entry_price, 4),
        "intended_notional": round(notional, 2),
        "stop_price": round(stop_price, 4) if stop_price else None,
        "target_price": round(target_price, 4) if target_price else None,
        "risk_reward_ratio": round(risk_reward, 4) if risk_reward is not None else None,
        "confidence_score": _round(signal.get("confidence_score"), 4),
        "trade_quality_score": _round(signal.get("trade_quality_score"), 4),
        "target_mult_used": _round(signal.get("target_mult_used"), 4),
        "regime_exit_bucket": signal.get("regime_exit_bucket"),
        "regime_exit_score": _round(signal.get("regime_exit_score"), 4),
        "paper_surfaces": ["no_trade_avoided_value", "fast_long", "inverse_short"],
        "trade_enabled": False,
        "alters_orders": False,
    }


def _config(config: dict[str, Any] | None) -> dict[str, Any]:
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    cfg["enabled"] = False
    cfg["trade_enabled"] = False
    cfg["misfit_tickers"] = tuple(str(t).upper() for t in cfg["misfit_tickers"])
    cfg["target_strategies"] = tuple(str(s) for s in cfg["target_strategies"])
    cfg["horizons_trading_days"] = tuple(
        sorted({int(value) for value in cfg["horizons_trading_days"]})
    )
    cfg["primary_horizon_days"] = int(cfg["primary_horizon_days"])
    return cfg


def _normalise_state(state: dict[str, Any]) -> None:
    state.setdefault("schema_version", STATE_SCHEMA_VERSION)
    state.setdefault("sleeve", SLEEVE_NAME)
    state.setdefault("pending_entries", [])
    state.setdefault("open_positions", [])
    state.setdefault("closed_outcomes", [])
    state.setdefault("skipped_entries", [])


def _normalise_prices(prices: dict[str, Any] | None) -> dict[str, float]:
    out: dict[str, float] = {}
    for ticker, value in (prices or {}).items():
        parsed = _float_or_none(value)
        if parsed is not None and parsed > 0:
            out[str(ticker).upper()] = parsed
    return out


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
    horizons = set(int(value) for value in config["horizons_trading_days"])
    cost = float(config["round_trip_cost_pct"])
    still_open = []
    closed_today = []
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

        closed_horizons = {
            int(value) for value in position.get("closed_horizons") or []
        }
        observed = int(position.get("observed_trading_days") or 0)
        for horizon in sorted(horizons):
            if observed < horizon or horizon in closed_horizons:
                continue
            outcome = _close_horizon(position, current, as_of, horizon, cost)
            state["closed_outcomes"].append(outcome)
            closed_today.append(outcome)
            closed_horizons.add(horizon)
        position["closed_horizons"] = sorted(closed_horizons)
        if horizons.issubset(closed_horizons):
            position["paper_status"] = "closed_all_horizons"
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

    cost = float(config["round_trip_cost_pct"])
    remaining = []
    filled_today = []
    skipped_today = []
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
        notional = _float_or_none(entry.get("intended_notional")) or 0.0
        if notional <= 0:
            skipped = {
                **entry,
                "status": "skipped_missing_intended_notional",
                "skipped_asof": as_of,
                "trade_enabled": False,
            }
            state["skipped_entries"].append(skipped)
            skipped_today.append(skipped)
            continue
        position = {
            "decision_id": entry["decision_id"],
            "sleeve": SLEEVE_NAME,
            "ticker": ticker,
            "strategy": entry.get("strategy"),
            "source_kind": entry.get("source_kind"),
            "source_rank": entry.get("source_rank"),
            "created_asof": entry.get("created_asof"),
            "entry_date": as_of,
            "entry_price": round(entry_open, 4),
            "notional": round(notional, 2),
            "paper_shares": round(notional / entry_open, 8),
            "observed_trading_days": 0,
            "last_seen_date": as_of,
            "last_price": current_prices.get(ticker),
            "closed_horizons": [],
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


def _add_candidates(
    state: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    as_of: str,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    if not config.get("paper_enabled", True):
        return []
    existing = _existing_decision_ids(state)
    new_entries = []
    for candidate in sorted(candidates, key=_candidate_sort_key):
        decision_id = candidate["decision_id"]
        if decision_id in existing:
            continue
        entry = {
            "decision_id": decision_id,
            "sleeve": SLEEVE_NAME,
            "ticker": candidate["ticker"],
            "strategy": candidate["strategy"],
            "source_kind": candidate["source_kind"],
            "source_rank": candidate["source_rank"],
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
    candidates: list[dict[str, Any]],
    new_pending: list[dict[str, Any]],
    filled_today: list[dict[str, Any]],
    closed_today: list[dict[str, Any]],
    skipped_today: list[dict[str, Any]],
) -> dict[str, Any]:
    closed = list(state["closed_outcomes"])
    primary_horizon = int(config["primary_horizon_days"])
    primary_closed = [
        row for row in closed if int(row.get("horizon_days") or 0) == primary_horizon
    ]
    realized_fast = round(sum(_money(row.get("fast_long_pnl")) for row in closed), 2)
    realized_avoided = round(
        sum(_money(row.get("no_trade_avoided_value_pnl")) for row in closed),
        2,
    )
    realized_inverse = round(
        sum(_money(row.get("inverse_short_pnl")) for row in closed),
        2,
    )
    unrealized_fast = round(
        sum(_money(row.get("fast_long_pnl_if_closed_now")) for row in state["open_positions"]),
        2,
    )
    unrealized_inverse = round(
        sum(_money(row.get("inverse_short_pnl_if_closed_now")) for row in state["open_positions"]),
        2,
    )
    gate = _forward_paper_gate(primary_closed, config)
    no_trade_alpha_report = build_core_misfit_no_trade_alpha_report(
        primary_closed_outcomes=primary_closed,
        open_positions=state["open_positions"],
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
        "candidate_count": len(candidates),
        "new_pending_count": len(new_pending),
        "filled_count": len(filled_today),
        "closed_count_today": len(closed_today),
        "skipped_count_today": len(skipped_today),
        "pending_count": len(state["pending_entries"]),
        "open_position_count": len(state["open_positions"]),
        "closed_outcome_count": len(closed),
        "primary_horizon_days": primary_horizon,
        "primary_closed_outcome_count": len(primary_closed),
        "realized_fast_long_pnl_to_date": realized_fast,
        "realized_no_trade_value_to_date": realized_avoided,
        "realized_inverse_pnl_to_date": realized_inverse,
        "unrealized_fast_long_pnl": unrealized_fast,
        "unrealized_no_trade_value": round(-unrealized_fast, 2),
        "unrealized_inverse_pnl": unrealized_inverse,
        "ticker_summary": _ticker_summary(closed, state["open_positions"], candidates),
        "horizon_summary": _horizon_summary(closed),
        "no_trade_alpha_report": no_trade_alpha_report,
        "parameters": dict(config),
        "data_source": {
            "status": "loaded",
            "source": "current_core_signals_and_entry_execution_plan",
        },
        "candidates": deepcopy(candidates),
        "new_pending_entries": deepcopy(new_pending),
        "filled_entries": deepcopy(filled_today),
        "closed_outcomes_today": deepcopy(closed_today),
        "closed_outcomes": deepcopy(closed),
        "skipped_entries_today": deepcopy(skipped_today),
        "pending_entries": deepcopy(state["pending_entries"]),
        "open_positions": deepcopy(state["open_positions"]),
        "forward_paper_gate": gate,
        "production_impact": _production_impact(),
        "next_action": "paper_observe_forward_outcomes_only_no_orders",
    }


def _forward_paper_gate(
    primary_closed_outcomes: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    closed_count = len(primary_closed_outcomes)
    no_trade = round(
        sum(_money(row.get("no_trade_avoided_value_pnl")) for row in primary_closed_outcomes),
        2,
    )
    inverse = round(
        sum(_money(row.get("inverse_short_pnl")) for row in primary_closed_outcomes),
        2,
    )
    wins = sum(1 for row in primary_closed_outcomes if _money(row.get("inverse_short_pnl")) > 0)
    win_rate = round(wins / closed_count, 4) if closed_count else None
    by_ticker: dict[str, float] = {}
    for row in primary_closed_outcomes:
        ticker = str(row.get("ticker") or "").upper()
        pnl = _money(row.get("inverse_short_pnl"))
        if pnl > 0:
            by_ticker[ticker] = round(by_ticker.get(ticker, 0.0) + pnl, 2)
    positive_total = round(sum(by_ticker.values()), 2)
    max_share = (
        round(max(by_ticker.values()) / positive_total, 4)
        if positive_total > 0 and by_ticker
        else None
    )
    checks = {
        "min_closed_primary_outcomes": closed_count
        >= int(config["forward_gate_min_closed_primary_outcomes"]),
        "positive_no_trade_value": no_trade > 0
        if config.get("forward_gate_positive_no_trade_value", True)
        else True,
        "positive_inverse_pnl": inverse > 0
        if config.get("forward_gate_positive_inverse_pnl", True)
        else True,
        "max_single_ticker_inverse_positive_share": (
            max_share is not None
            and max_share
            <= float(config["forward_gate_max_single_ticker_inverse_positive_share"])
        ),
    }
    reasons = [name for name, passed in checks.items() if not passed]
    return {
        "passed": not reasons,
        "status": "passed" if not reasons else "blocked",
        "reasons": reasons,
        "checks": checks,
        "metrics": {
            "closed_primary_outcomes": closed_count,
            "no_trade_avoided_value": no_trade,
            "inverse_short_pnl": inverse,
            "inverse_short_win_rate": win_rate,
            "max_single_ticker_inverse_positive_share": max_share,
        },
        "trade_enabled_after_gate": False,
    }


def _mark_unrealized(
    position: dict[str, Any],
    current_price: float,
    round_trip_cost_pct: float,
) -> None:
    long_pnl, avoided, inverse_pnl, long_ret, inverse_ret = _outcome_values(
        float(position["entry_price"]),
        current_price,
        float(position["notional"]),
        round_trip_cost_pct,
    )
    position["fast_long_return_if_closed_now_pct"] = round(long_ret * 100.0, 6)
    position["inverse_short_return_if_closed_now_pct"] = round(inverse_ret * 100.0, 6)
    position["fast_long_pnl_if_closed_now"] = long_pnl
    position["no_trade_avoided_value_if_closed_now"] = avoided
    position["inverse_short_pnl_if_closed_now"] = inverse_pnl


def _close_horizon(
    position: dict[str, Any],
    exit_price: float,
    exit_date: str,
    horizon: int,
    round_trip_cost_pct: float,
) -> dict[str, Any]:
    long_pnl, avoided, inverse_pnl, long_ret, inverse_ret = _outcome_values(
        float(position["entry_price"]),
        exit_price,
        float(position["notional"]),
        round_trip_cost_pct,
    )
    return {
        "decision_id": position["decision_id"],
        "sleeve": SLEEVE_NAME,
        "ticker": position["ticker"],
        "strategy": position.get("strategy"),
        "source_kind": position.get("source_kind"),
        "entry_date": position.get("entry_date"),
        "exit_date": exit_date,
        "horizon_days": horizon,
        "entry_price": position.get("entry_price"),
        "exit_price": exit_price,
        "notional": position.get("notional"),
        "fast_long_return_pct": round(long_ret * 100.0, 6),
        "fast_long_pnl": long_pnl,
        "no_trade_avoided_value_pnl": avoided,
        "inverse_short_return_pct": round(inverse_ret * 100.0, 6),
        "inverse_short_pnl": inverse_pnl,
        "trade_enabled": False,
        "paper_status": "closed_horizon",
        "source_candidate": deepcopy(position.get("source_candidate") or {}),
    }


def build_core_misfit_no_trade_alpha_report(
    *,
    primary_closed_outcomes: list[dict[str, Any]],
    open_positions: list[dict[str, Any]],
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = _config(config)
    closed = [
        row for row in primary_closed_outcomes or [] if isinstance(row, dict)
    ]
    open_rows = [row for row in open_positions or [] if isinstance(row, dict)]
    min_closed = int(cfg["forward_gate_min_closed_primary_outcomes"])
    no_trade = round(
        sum(_money(row.get("no_trade_avoided_value_pnl")) for row in closed),
        2,
    )
    inverse = round(sum(_money(row.get("inverse_short_pnl")) for row in closed), 2)
    unrealized_no_trade = round(
        sum(_money(row.get("no_trade_avoided_value_if_closed_now")) for row in open_rows),
        2,
    )
    unrealized_inverse = round(
        sum(_money(row.get("inverse_short_pnl_if_closed_now")) for row in open_rows),
        2,
    )
    status = (
        "gate_test_allowed"
        if len(closed) >= min_closed
        else "observed_only_until_min_closed_10d_outcomes"
    )
    return {
        "schema_version": 1,
        "rule_version": NO_TRADE_ALPHA_REPORT_RULE_VERSION,
        "read_only": True,
        "primary_horizon_days": int(cfg["primary_horizon_days"]),
        "primary_closed_outcome_count": len(closed),
        "min_closed_primary_outcomes": min_closed,
        "closed_outcomes_remaining_before_gate_test": max(
            0,
            min_closed - len(closed),
        ),
        "realized_no_trade_avoided_value": no_trade,
        "realized_inverse_short_pnl": inverse,
        "unrealized_no_trade_avoided_value": unrealized_no_trade,
        "unrealized_inverse_short_pnl": unrealized_inverse,
        "next_allowed_action": status,
        "trade_enabled": False,
        "alters_orders": False,
        "notes": (
            "Live short or exclusion tests stay blocked until the closed 10d "
            "no-trade avoided-value sample reaches the configured gate."
        ),
    }


def _outcome_values(
    entry_price: float,
    exit_price: float,
    notional: float,
    round_trip_cost_pct: float,
) -> tuple[float, float, float, float, float]:
    long_ret = exit_price / entry_price - 1.0 - round_trip_cost_pct
    inverse_ret = entry_price / exit_price - 1.0 - round_trip_cost_pct
    long_pnl = round(notional * long_ret, 2)
    inverse_pnl = round(notional * inverse_ret, 2)
    return long_pnl, round(-long_pnl, 2), inverse_pnl, long_ret, inverse_ret


def _ticker_summary(
    closed: list[dict[str, Any]],
    open_positions: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for ticker in sorted(_ticker_set(DEFAULT_CONFIG)):
        summary[ticker] = {
            "candidate_count": 0,
            "open_position_count": 0,
            "closed_outcome_count": 0,
            "realized_no_trade_value": 0.0,
            "realized_inverse_pnl": 0.0,
        }
    for candidate in candidates:
        row = summary.setdefault(str(candidate.get("ticker") or "").upper(), {})
        row["candidate_count"] = int(row.get("candidate_count") or 0) + 1
    for position in open_positions:
        row = summary.setdefault(str(position.get("ticker") or "").upper(), {})
        row["open_position_count"] = int(row.get("open_position_count") or 0) + 1
    for outcome in closed:
        row = summary.setdefault(str(outcome.get("ticker") or "").upper(), {})
        row["closed_outcome_count"] = int(row.get("closed_outcome_count") or 0) + 1
        row["realized_no_trade_value"] = round(
            float(row.get("realized_no_trade_value") or 0.0)
            + _money(outcome.get("no_trade_avoided_value_pnl")),
            2,
        )
        row["realized_inverse_pnl"] = round(
            float(row.get("realized_inverse_pnl") or 0.0)
            + _money(outcome.get("inverse_short_pnl")),
            2,
        )
    return summary


def _horizon_summary(closed: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for outcome in closed:
        horizon = str(outcome.get("horizon_days"))
        row = summary.setdefault(
            horizon,
            {
                "closed_outcome_count": 0,
                "fast_long_pnl": 0.0,
                "no_trade_avoided_value": 0.0,
                "inverse_short_pnl": 0.0,
                "inverse_positive_count": 0,
            },
        )
        row["closed_outcome_count"] += 1
        row["fast_long_pnl"] = round(
            row["fast_long_pnl"] + _money(outcome.get("fast_long_pnl")),
            2,
        )
        row["no_trade_avoided_value"] = round(
            row["no_trade_avoided_value"]
            + _money(outcome.get("no_trade_avoided_value_pnl")),
            2,
        )
        inverse = _money(outcome.get("inverse_short_pnl"))
        row["inverse_short_pnl"] = round(row["inverse_short_pnl"] + inverse, 2)
        row["inverse_positive_count"] += 1 if inverse > 0 else 0
    return summary


def _pending_sort_key(entry: dict[str, Any]) -> tuple[str, int, str]:
    return (
        str(entry.get("created_asof") or ""),
        int(entry.get("source_rank") or 99),
        str(entry.get("ticker") or ""),
    )


def _candidate_sort_key(candidate: dict[str, Any]) -> tuple[int, str, str]:
    return (
        int(candidate.get("source_rank") or 99),
        str(candidate.get("ticker") or ""),
        str(candidate.get("strategy") or ""),
    )


def _existing_decision_ids(state: dict[str, Any]) -> set[str]:
    ids = set()
    for bucket in ("pending_entries", "open_positions", "closed_outcomes", "skipped_entries"):
        ids.update(
            str(item.get("decision_id"))
            for item in state.get(bucket, [])
            if item.get("decision_id")
        )
    return ids


def _decision_id(
    *,
    as_of: str,
    ticker: str,
    strategy: str,
    source_kind: str,
    entry_price: float,
) -> str:
    return (
        f"{SLEEVE_NAME}:{RULE_VERSION}:{as_of}:{ticker}:"
        f"{strategy}:{source_kind}:{entry_price:.4f}"
    )


def _ticker_set(config: dict[str, Any]) -> set[str]:
    return {str(value).upper() for value in config.get("misfit_tickers") or []}


def _strategy_set(config: dict[str, Any]) -> set[str]:
    return {str(value) for value in config.get("target_strategies") or []}


def _date10(value: Any) -> str:
    if hasattr(value, "date"):
        try:
            return value.date().isoformat()
        except Exception:
            pass
    return str(value or "")[:10]


def _float_or_none(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed


def _round(value: Any, digits: int = 4) -> Any:
    parsed = _float_or_none(value)
    return round(parsed, digits) if parsed is not None else None


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
        "alters_orders": False,
        "live_short_enabled": False,
        "scope": "default_off_core_misfit_paper_attribution",
    }
