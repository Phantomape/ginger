"""Default-off low-deployment ETF overlay paper attribution.

This module tracks the strongest current replacement-value alpha lead without
turning it into live orders. It mirrors exp-20260510-007: when the core book is
materially under-deployed, choose one liquid ETF by prior-close 20-day momentum
after requiring positive 200-day trend and positive 20-day momentum.

The output is paper-only. It never changes core ranking, sizing, exits, or
orders. A trade-enabled adapter remains blocked until cash/risk-budget semantics
and forward outcomes pass a separate gate.
"""

from __future__ import annotations

import json
import math
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from data_paths import data_artifact_path
from open_position_schema import core_slot_positions


SLEEVE_NAME = "LOW_DEPLOYMENT_DYNAMIC_ETF_OVERLAY_PAPER"
RULE_VERSION = "low_deployment_dynamic_etf_overlay_v1"
STATE_SCHEMA_VERSION = 1

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
    "paper_notional_fraction_of_portfolio": 1.0,
    "fallback_paper_notional_usd": 100_000.0,
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
        "closed_count_today": 0,
        "closed_position_count": 0,
        "realized_pnl_to_date": 0.0,
        "candidate": None,
        "closed_today": [],
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "production_impact": _production_impact(),
        "error": reason,
    }


def empty_low_deployment_etf_overlay_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
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
    candidate = _select_candidate(
        rows_by_ticker,
        as_of=as_of_date,
        active_core_positions=active_core_positions,
        core_deployment_context=core_deployment_context,
        config=cfg,
    )
    skipped_today: list[dict[str, Any]] = []
    if candidate is None:
        skipped = _skip_payload(
            as_of_date,
            "no_positive_trend_momentum_etf_candidate",
            active_core_positions=active_core_positions,
            core_deployment_context=core_deployment_context,
            config=cfg,
        )
        _append_skip_once(working_state, skipped)
        skipped_today.append(skipped)

    closed_today = []
    if candidate is not None and cfg.get("paper_enabled", True):
        closed = _closed_trade_from_candidate(
            candidate,
            portfolio_value=portfolio_value,
            config=cfg,
        )
        if not _has_closed_decision(working_state, closed["decision_id"]):
            working_state["closed_positions"].append(closed)
            closed_today.append(closed)

    snapshot = _snapshot_payload(
        working_state,
        as_of=as_of_date,
        candidate=candidate,
        closed_today=closed_today,
        skipped_today=skipped_today,
        active_core_positions=active_core_positions,
        core_deployment_context=core_deployment_context,
        config=cfg,
    )
    if persist:
        save_low_deployment_etf_overlay_state(working_state, state_path)
        append_low_deployment_etf_overlay_snapshot(snapshot, snapshot_log_path)
    return snapshot


def _normalise_state(state: dict[str, Any]) -> None:
    state.setdefault("schema_version", STATE_SCHEMA_VERSION)
    state.setdefault("sleeve", SLEEVE_NAME)
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
        idx = _latest_index_on_or_before(rows, as_of)
        if idx is None:
            continue
        state = _candidate_state(rows, idx, config)
        if state is None:
            continue
        trade_row = rows[idx]
        candidates.append(
            {
                "ticker": ticker,
                "trade_date": trade_row["date"],
                "decision_date": state["decision_date"],
                "entry_date": trade_row["date"],
                "entry_timing": "same_session_open_paper_replay",
                "open": _round(trade_row.get("open"), 4),
                "close": _round(trade_row.get("close"), 4),
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
                "prior_close": _round(state["prior_close"], 4),
                "prior_sma200": _round(state["prior_sma200"], 4),
                "prior_momentum20": _round(state["prior_momentum20"], 6),
                "state": state,
            }
        )
    if not candidates:
        return None
    chosen = max(candidates, key=lambda row: (row["prior_momentum20"], row["ticker"]))
    chosen["decision_id"] = (
        f"{SLEEVE_NAME}:{RULE_VERSION}:{chosen['trade_date']}:{chosen['ticker']}"
    )
    chosen["paper_enabled"] = bool(config.get("paper_enabled", True))
    chosen["trade_enabled"] = False
    chosen["alters_orders"] = False
    chosen["admission_reason"] = (
        "low_deployment_condition_passed"
        if chosen["low_deployment_condition_passed"]
        else "sleeve_independent_forward_observation_core_above_reference_threshold"
    )
    return chosen


def _candidate_state(
    rows: list[dict[str, Any]],
    trade_idx: int,
    config: dict[str, Any],
) -> dict[str, Any] | None:
    sma_days = int(config["state_sma_days"])
    momentum_days = int(config["state_momentum_days"])
    if trade_idx < max(sma_days, momentum_days) + 1:
        return None
    prior_idx = trade_idx - 1
    prior = rows[prior_idx]
    prior_close = _positive_float(prior.get("close"))
    trade_open = _positive_float(rows[trade_idx].get("open"))
    trade_close = _positive_float(rows[trade_idx].get("close"))
    if not prior_close or not trade_open or not trade_close:
        return None
    sma_window = rows[prior_idx - sma_days + 1 : prior_idx + 1]
    sma_values = [_positive_float(row.get("close")) for row in sma_window]
    if any(value is None for value in sma_values) or len(sma_values) != sma_days:
        return None
    sma = sum(float(value) for value in sma_values) / len(sma_values)
    momentum_base = _positive_float(rows[prior_idx - momentum_days].get("close"))
    if not momentum_base:
        return None
    momentum = prior_close / momentum_base - 1.0
    if prior_close <= sma or momentum <= 0.0:
        return None
    return {
        "decision_date": prior["date"],
        "prior_close": prior_close,
        "prior_sma200": sma,
        "prior_momentum20": momentum,
    }


def _closed_trade_from_candidate(
    candidate: dict[str, Any],
    *,
    portfolio_value: float | None,
    config: dict[str, Any],
) -> dict[str, Any]:
    base_notional = _float_or_none(portfolio_value)
    if base_notional is None or base_notional <= 0:
        base_notional = float(config["fallback_paper_notional_usd"])
    notional = base_notional * float(config["paper_notional_fraction_of_portfolio"])
    entry = _positive_float(candidate.get("open")) or 0.0
    exit_price = _positive_float(candidate.get("close")) or entry
    pnl = notional * (exit_price / entry - 1.0) if entry > 0 else 0.0
    out = deepcopy(candidate)
    out.update(
        {
            "sleeve": SLEEVE_NAME,
            "rule_version": RULE_VERSION,
            "notional_usd": _round(notional, 2),
            "exit_date": candidate["trade_date"],
            "exit_price": _round(exit_price, 4),
            "pnl": _round(pnl, 2),
            "net_return_pct": _round(pnl / notional, 6) if notional else None,
            "paper_status": "closed",
            "trade_enabled": False,
            "alters_orders": False,
        }
    )
    return out


def _snapshot_payload(
    state: dict[str, Any],
    *,
    as_of: str,
    candidate: dict[str, Any] | None,
    closed_today: list[dict[str, Any]],
    skipped_today: list[dict[str, Any]],
    active_core_positions: int,
    core_deployment_context: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    closed = [row for row in state.get("closed_positions") or [] if isinstance(row, dict)]
    realized = round(sum(_float_or_none(row.get("pnl")) or 0.0 for row in closed), 2)
    wins = sum(1 for row in closed if (_float_or_none(row.get("pnl")) or 0.0) > 0)
    win_rate = round(wins / len(closed), 4) if closed else None
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
        "closed_today": closed_today,
        "closed_count_today": len(closed_today),
        "skipped_today": skipped_today,
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
        "realized_pnl_to_date": realized,
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


def _latest_index_on_or_before(rows: list[dict[str, Any]], as_of: str) -> int | None:
    matches = [
        idx
        for idx, row in enumerate(rows)
        if str(row.get("date") or "") <= str(as_of)[:10]
    ]
    return max(matches) if matches else None


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
