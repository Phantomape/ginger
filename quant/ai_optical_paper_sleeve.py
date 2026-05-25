"""Default-off AI optical IWM-confirmed paper sleeve.

This promotes the exp-20260525-003 alpha lead into a shared,
production-visible observation path. It never emits live orders and never
changes core signal generation, ranking, sizing, exits, heat, or LLM/news
behavior.
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


SLEEVE_NAME = "AI_OPTICAL_IWM_CONFIRMED_PAPER"
RULE_VERSION = "ai_optical_iwm_confirmed_fixed_notional_v1"
MARKET_CONFIRMATION_RULE_VERSION = "ai_optical_iwm_spy_momentum_confirmation_v1"
REPLACEMENT_VALUE_RULE_VERSION = "ai_optical_forward_replacement_value_v1"
UNIVERSE_STATE_FEED_RULE_VERSION = "ai_optical_universe_state_observation_feed_v1"
STATE_SCHEMA_VERSION = 1

DEFAULT_STATE_PATH = data_artifact_path("ai_optical_paper_state")
DEFAULT_SNAPSHOT_LOG_PATH = data_artifact_path("ai_optical_paper_snapshots")

DEFAULT_CONFIG = {
    "enabled": False,
    "paper_enabled": True,
    "trade_enabled": False,
    "target_theme": "ai_optical_connectivity",
    "target_segment": "optical_connectivity",
    "allowed_statuses": ["pilot", "research"],
    "allowed_liquidity_tiers": ["ok", "watch"],
    "required_history_class": "full_history",
    "paper_notional_usd": 10_000.0,
    "min_iwm_spy_momentum_spread": 0.003,
    "momentum_lookback_days": 20,
    "max_active_positions": 5,
    "daily_entry_slots": 3,
    "hold_days": 20,
    "round_trip_cost_pct": ROUND_TRIP_COST_PCT,
    "forward_gate_min_closed_trades": 20,
    "forward_gate_positive_net_pnl": True,
    "forward_gate_min_win_rate": 0.50,
    "forward_gate_max_single_ticker_positive_share": 0.50,
    "forward_gate_max_top5_positive_share": 0.70,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_ai_optical_paper_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_entries": [],
    }


def load_ai_optical_paper_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_ai_optical_paper_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_ai_optical_paper_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_ai_optical_paper_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_ai_optical_paper_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, sort_keys=True) + "\n")


def empty_ai_optical_paper_sleeve_snapshot(as_of: str, reason: str) -> dict[str, Any]:
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
        "rejected_candidate_count": 0,
        "new_pending_count": 0,
        "filled_count": 0,
        "closed_count_today": 0,
        "pending_count": 0,
        "open_position_count": 0,
        "closed_position_count": 0,
        "realized_pnl_to_date": 0.0,
        "unrealized_pnl": 0.0,
        "market_confirmation": {"passed": False, "status": reason},
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "data_source": {"status": reason},
        "production_impact": _production_impact(),
        "error": reason,
    }


def build_ai_optical_candidate_universe_from_universe_state(
    universe_state: dict[str, Any] | None,
    *,
    current_core_universe: list[str] | set[str] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the governed optical observation feed from the daily universe state."""
    cfg = _config(config)
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
    observation = {
        str(ticker).upper()
        for ticker in (universe_state.get("observation_universe") or [])
        if ticker
    }
    if not observation:
        observation = {str(ticker).upper() for ticker in records_by_ticker if ticker}
    core = {str(ticker).upper() for ticker in (current_core_universe or set()) if ticker}

    records: dict[str, dict[str, Any]] = {}
    excluded: list[dict[str, Any]] = []
    for ticker in sorted(observation):
        raw_record = records_by_ticker.get(ticker) or {}
        record = dict(raw_record) if isinstance(raw_record, dict) else {}
        record["ticker"] = ticker
        reasons = _ai_optical_feed_exclusion_reasons(
            ticker,
            record,
            current_core_universe=core,
            config=cfg,
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
            "history_class": record.get("history_class"),
            "liquidity_tier": record.get("liquidity_tier"),
            "eligible_as_of": record.get("eligible_as_of"),
            "source": record.get("source"),
            "source_reason": record.get("source_reason"),
            "pilot_sleeve": record.get("pilot_sleeve"),
            "feed_rule_version": UNIVERSE_STATE_FEED_RULE_VERSION,
        }

    return {
        "status": "universe_state_ai_optical_feed",
        "path": universe_state.get("artifact_path") or universe_state.get("path"),
        "as_of": universe_state.get("as_of"),
        "rule_version": UNIVERSE_STATE_FEED_RULE_VERSION,
        "tickers": sorted(records),
        "records": records,
        "excluded_count": len(excluded),
        "excluded_sample": excluded[:25],
        "source_counts": {
            "observation_universe": len(observation),
            "records": len(records_by_ticker),
            "current_core_universe": len(core),
        },
    }


def build_ai_optical_paper_sleeve_snapshot(
    *,
    as_of: str,
    candidate_signals: list[dict[str, Any]] | None = None,
    ohlcv_by_ticker: dict[str, Any] | None = None,
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
        state if state is not None else load_ai_optical_paper_state(state_path)
    )
    _normalise_state(working_state)

    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    loaded_universe = _normalise_candidate_universe(candidate_universe)
    current = _normalise_prices(current_prices)
    opens = _normalise_prices(open_prices)
    if not current:
        current = {
            ticker: rows[idx]["close"]
            for ticker, rows in rows_by_ticker.items()
            for idx in [_latest_index_on_or_before(rows, as_of_date)]
            if idx is not None and _positive_float(rows[idx].get("close")) is not None
        }
    if not opens:
        opens = {
            ticker: rows[idx]["open"]
            for ticker, rows in rows_by_ticker.items()
            for idx in [_latest_index_on_or_before(rows, as_of_date)]
            if idx is not None and _positive_float(rows[idx].get("open")) is not None
        }

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

    candidates, rejected_candidates, market_confirmation = _build_ai_optical_candidates(
        as_of=as_of_date,
        candidate_signals=candidate_signals or [],
        ohlcv_by_ticker=rows_by_ticker,
        candidate_tickers=loaded_universe["tickers"],
        ticker_metadata=loaded_universe["records"],
        open_position_tickers={
            str(row.get("ticker") or "").upper()
            for row in working_state.get("open_positions") or []
        },
        pending_tickers={
            str(row.get("ticker") or "").upper()
            for row in working_state.get("pending_entries") or []
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
        rejected_candidates=rejected_candidates,
        market_confirmation=market_confirmation,
        new_pending=new_pending,
        filled_today=filled_today,
        closed_today=closed_today,
        skipped_today=skipped_today,
    )
    if persist:
        save_ai_optical_paper_state(working_state, state_path)
        append_ai_optical_paper_snapshot(snapshot, snapshot_log_path)
    return snapshot


def build_ai_optical_paper_candidates(
    *,
    as_of: str,
    candidate_signals: list[dict[str, Any]],
    ohlcv_by_ticker: dict[str, Any],
    candidate_tickers: list[str] | tuple[str, ...],
    ticker_metadata: dict[str, dict[str, Any]] | None = None,
    open_position_tickers: set[str] | None = None,
    pending_tickers: set[str] | None = None,
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    candidates, _rejected, _market = _build_ai_optical_candidates(
        as_of=as_of,
        candidate_signals=candidate_signals,
        ohlcv_by_ticker=ohlcv_by_ticker,
        candidate_tickers=candidate_tickers,
        ticker_metadata=ticker_metadata,
        open_position_tickers=open_position_tickers,
        pending_tickers=pending_tickers,
        config=config,
    )
    return candidates


def build_ai_optical_replacement_value_report(
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


def _build_ai_optical_candidates(
    *,
    as_of: str,
    candidate_signals: list[dict[str, Any]],
    ohlcv_by_ticker: dict[str, Any],
    candidate_tickers: list[str] | tuple[str, ...],
    ticker_metadata: dict[str, dict[str, Any]] | None = None,
    open_position_tickers: set[str] | None = None,
    pending_tickers: set[str] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    cfg = _config(config)
    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    market = _market_confirmation(rows_by_ticker, as_of=as_of, config=cfg)
    feed_tickers = {str(value).upper() for value in candidate_tickers if value}
    active = {str(value).upper() for value in (open_position_tickers or set())}
    pending = {str(value).upper() for value in (pending_tickers or set())}
    metadata = ticker_metadata or {}
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for signal in candidate_signals or []:
        if not isinstance(signal, dict):
            continue
        ticker = str(signal.get("ticker") or "").upper()
        if not ticker or ticker in {"SPY", "QQQ", "IWM"}:
            continue
        rejection_reasons: list[str] = []
        if ticker not in feed_tickers:
            rejection_reasons.append("not_in_ai_optical_feed")
        if ticker in active:
            rejection_reasons.append("already_open_in_paper_sleeve")
        if ticker in pending:
            rejection_reasons.append("already_pending_in_paper_sleeve")
        record = metadata.get(ticker) or {}
        if record and _excluded_candidate_record(record, cfg):
            rejection_reasons.append("feed_record_exclusion")
        if not market.get("passed"):
            rejection_reasons.append("iwm_spy_confirmation_failed")

        entry_price = _positive_float(signal.get("entry_price"))
        stop_price = _positive_float(signal.get("stop_price"))
        target_price = _positive_float(signal.get("target_price"))
        if entry_price is None:
            rejection_reasons.append("missing_entry_price")
        if stop_price is None:
            rejection_reasons.append("missing_stop_price")
        if target_price is None:
            rejection_reasons.append("missing_target_price")

        if rejection_reasons:
            if ticker in feed_tickers:
                rejected.append(
                    {
                        "ticker": ticker,
                        "strategy": signal.get("strategy"),
                        "reasons": rejection_reasons,
                        "market_confirmation": market,
                    }
                )
            continue

        candidate = _candidate_from_signal(
            signal,
            record=record,
            as_of=as_of,
            entry_price=float(entry_price),
            stop_price=float(stop_price),
            target_price=float(target_price),
            market_confirmation=market,
            config=cfg,
        )
        accepted.append(candidate)

    accepted = sorted(accepted, key=_candidate_sort_key)
    limited = accepted[: int(cfg["daily_entry_slots"])]
    for rank, candidate in enumerate(limited, start=1):
        candidate["source_rank"] = rank
    return limited, rejected[:25], market


def _candidate_from_signal(
    signal: dict[str, Any],
    *,
    record: dict[str, Any],
    as_of: str,
    entry_price: float,
    stop_price: float,
    target_price: float,
    market_confirmation: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    ticker = str(signal.get("ticker") or "").upper()
    strategy = str(signal.get("strategy") or "unknown")
    intended_notional = round(float(config["paper_notional_usd"]), 2)
    decision_id = (
        f"{SLEEVE_NAME}:{RULE_VERSION}:{as_of}:{ticker}:{strategy}:"
        f"{entry_price:.4f}:{target_price:.4f}"
    )
    return {
        "decision_id": decision_id,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "ticker": ticker,
        "strategy": strategy,
        "decision_date": as_of,
        "entry_price": round(entry_price, 4),
        "stop_price": round(stop_price, 4),
        "target_price": round(target_price, 4),
        "confidence_score": _round(signal.get("confidence_score"), 4),
        "trade_quality_score": _round(signal.get("trade_quality_score"), 4),
        "risk_reward_ratio": _round(signal.get("risk_reward_ratio"), 4),
        "exec_lag_adj_net_rr": _round(signal.get("exec_lag_adj_net_rr"), 4),
        "intended_notional": intended_notional,
        "paper_notional_usd": intended_notional,
        "intended_entry_timing": "next_session_open",
        "market_confirmation_rule_version": MARKET_CONFIRMATION_RULE_VERSION,
        "market_confirmation": deepcopy(market_confirmation),
        "theme": record.get("theme"),
        "theme_segment": record.get("theme_segment"),
        "status": record.get("status"),
        "liquidity_tier": record.get("liquidity_tier"),
        "history_class": record.get("history_class"),
        "source_reason": record.get("source_reason"),
        "replacement_value_context": {
            "rule_version": REPLACEMENT_VALUE_RULE_VERSION,
            "displaced_resource": "paper_cash_slot",
            "core_displacement": False,
        },
        "trade_enabled": False,
        "alters_orders": False,
    }


def _market_confirmation(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    *,
    as_of: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    lookback = int(config["momentum_lookback_days"])
    iwm_rows = rows_by_ticker.get("IWM") or []
    spy_rows = rows_by_ticker.get("SPY") or []
    iwm_mom, iwm_date = _momentum(iwm_rows, as_of, lookback)
    spy_mom, spy_date = _momentum(spy_rows, as_of, lookback)
    spread = (
        iwm_mom - spy_mom
        if iwm_mom is not None and spy_mom is not None
        else None
    )
    passed = spread is not None and spread >= float(config["min_iwm_spy_momentum_spread"])
    reasons = []
    if iwm_mom is None:
        reasons.append("missing_iwm_momentum")
    if spy_mom is None:
        reasons.append("missing_spy_momentum")
    if spread is not None and not passed:
        reasons.append("iwm_spy_momentum_spread_below_min")
    return {
        "rule_version": MARKET_CONFIRMATION_RULE_VERSION,
        "as_of": as_of,
        "market_state_as_of": min(
            [date for date in (iwm_date, spy_date) if date],
            default=None,
        ),
        "lookback_trading_days": lookback,
        "iwm_momentum20": _round(iwm_mom, 6),
        "spy_momentum20": _round(spy_mom, 6),
        "iwm_spy_momentum_spread": _round(spread, 6),
        "min_iwm_spy_momentum_spread": float(config["min_iwm_spy_momentum_spread"]),
        "passed": passed,
        "status": "passed" if passed else "blocked",
        "reasons": reasons,
        "free_data_sources": ["IWM OHLCV", "SPY OHLCV"],
    }


def _momentum(
    rows: list[dict[str, Any]],
    as_of: str,
    lookback: int,
) -> tuple[float | None, str | None]:
    idx = _latest_index_on_or_before(rows, as_of)
    if idx is None or idx < lookback:
        return None, None
    close = _positive_float(rows[idx].get("close"))
    prior = _positive_float(rows[idx - lookback].get("close"))
    if not close or not prior:
        return None, None
    return close / prior - 1.0, str(rows[idx].get("date") or "")[:10]


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
        observed_days = int(position.get("observed_trading_days") or 0) + 1
        position["observed_trading_days"] = observed_days
        if current_price:
            position["last_price"] = current_price
            position["last_price_asof"] = as_of
            position["unrealized_pnl"] = _pnl(
                position.get("entry_price"),
                current_price,
                position.get("notional"),
                float(config["round_trip_cost_pct"]),
            )
        exit_reason = None
        if current_price:
            target = _positive_float(position.get("target_price"))
            stop = _positive_float(position.get("stop_price"))
            if target and current_price >= target:
                exit_reason = "target_close_reached"
            elif stop and current_price <= stop:
                exit_reason = "stop_close_reached"
        if exit_reason is None and observed_days >= int(config["hold_days"]):
            exit_reason = "max_hold_days"
        if exit_reason and current_price:
            closed = deepcopy(position)
            closed.update(
                {
                    "status": "closed",
                    "exit_date": as_of,
                    "exit_price": current_price,
                    "exit_reason": exit_reason,
                    "pnl": _pnl(
                        position.get("entry_price"),
                        current_price,
                        position.get("notional"),
                        float(config["round_trip_cost_pct"]),
                    ),
                    "return_pct_net": _return_pct(
                        position.get("entry_price"),
                        current_price,
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
        candidate = entry.get("candidate") or {}
        decision_entry = _positive_float(candidate.get("entry_price"))
        if open_price is None or decision_entry is None:
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
        max_open = decision_entry * 1.015
        min_open = decision_entry * 0.980
        if open_price > max_open or open_price < min_open:
            skipped_entry = deepcopy(entry)
            skipped_entry.update(
                {
                    "status": "skipped_open_outside_signal_band",
                    "skipped_asof": as_of,
                    "next_open": open_price,
                    "max_allowed_open": round(max_open, 4),
                    "min_allowed_open": round(min_open, 4),
                    "trade_enabled": False,
                }
            )
            skipped.append(skipped_entry)
            state["skipped_entries"].append(skipped_entry)
            continue
        position = {
            "decision_id": entry.get("decision_id"),
            "sleeve": SLEEVE_NAME,
            "ticker": ticker,
            "strategy": candidate.get("strategy"),
            "entry_date": as_of,
            "entry_price": round(open_price, 4),
            "decision_entry_price": decision_entry,
            "stop_price": candidate.get("stop_price"),
            "target_price": candidate.get("target_price"),
            "notional": entry.get("intended_notional"),
            "status": "open",
            "observed_trading_days": 0,
            "hold_days": int(config["hold_days"]),
            "last_price": current_prices.get(ticker),
            "source_candidate": deepcopy(candidate),
            "trade_enabled": False,
        }
        if current_prices.get(ticker):
            position["unrealized_pnl"] = _pnl(
                position["entry_price"],
                current_prices[ticker],
                position["notional"],
                float(config["round_trip_cost_pct"]),
            )
        filled.append(position)
        state["open_positions"].append(position)
    state["pending_entries"] = still_pending
    return filled, skipped


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
    capacity = min(capacity, int(config["daily_entry_slots"]))
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
    rejected_candidates: list[dict[str, Any]],
    market_confirmation: dict[str, Any],
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
    replacement_value_report = build_ai_optical_replacement_value_report(
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
        "rejected_candidate_count": len(rejected_candidates),
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
        "market_confirmation": deepcopy(market_confirmation),
        "parameters": dict(config),
        "data_source": {
            "status": data_source.get("status"),
            "path": data_source.get("path"),
            "rule_version": data_source.get("rule_version"),
            "ticker_count": len(data_source.get("tickers") or []),
            "excluded_count": data_source.get("excluded_count"),
        },
        "candidates": deepcopy(candidates),
        "rejected_candidates": deepcopy(rejected_candidates),
        "new_pending_entries": deepcopy(new_pending),
        "filled_entries": deepcopy(filled_today),
        "closed_positions_today": deepcopy(closed_today),
        "closed_positions": deepcopy(closed),
        "skipped_entries_today": deepcopy(skipped_today),
        "pending_entries": deepcopy(state["pending_entries"]),
        "open_positions": deepcopy(open_positions),
        "forward_paper_gate": gate,
        "production_impact": _production_impact(),
        "next_action": "paper_observe_forward_replacement_value_no_orders",
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


def _normalise_candidate_universe(value: dict[str, Any] | list[str] | None) -> dict[str, Any]:
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
    return {"status": "missing", "path": None, "tickers": [], "records": {}}


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


def _latest_index_on_or_before(rows: list[dict[str, Any]], as_of: str) -> int | None:
    matches = [
        idx
        for idx, row in enumerate(rows or [])
        if str(row.get("date") or "")[:10] <= str(as_of)[:10]
    ]
    return max(matches) if matches else None


def _ai_optical_feed_exclusion_reasons(
    ticker: str,
    record: dict[str, Any],
    *,
    current_core_universe: set[str],
    config: dict[str, Any],
) -> list[str]:
    reasons: list[str] = []
    if ticker in current_core_universe:
        reasons.append("already_core_trade_universe")
    if ticker in {"SPY", "QQQ", "IWM"}:
        reasons.append("benchmark")
    if _excluded_candidate_record(record, config):
        reasons.append("record_exclusion")
    return reasons


def _excluded_candidate_record(record: dict[str, Any], config: dict[str, Any]) -> bool:
    status = str(record.get("status") or "").lower()
    theme = str(record.get("theme") or "").lower()
    segment = str(record.get("theme_segment") or "").lower()
    history_class = str(record.get("history_class") or "").lower()
    liquidity = str(record.get("liquidity_tier") or "").lower()
    return bool(
        status not in {str(value).lower() for value in config["allowed_statuses"]}
        or theme != str(config["target_theme"]).lower()
        or segment != str(config["target_segment"]).lower()
        or history_class != str(config["required_history_class"]).lower()
        or liquidity not in {
            str(value).lower() for value in config["allowed_liquidity_tiers"]
        }
    )


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


def _candidate_sort_key(candidate: dict[str, Any]) -> tuple[float, float, float, str]:
    return (
        -float(candidate.get("trade_quality_score") or 0.0),
        -float(candidate.get("confidence_score") or 0.0),
        -float(candidate.get("risk_reward_ratio") or 0.0),
        str(candidate.get("ticker") or ""),
    )


def _ticker_summary(
    closed: list[dict[str, Any]],
    open_positions: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in candidates:
        ticker = str(row.get("ticker") or "").upper()
        rec = out.setdefault(
            ticker,
            {"candidate_count": 0, "open_count": 0, "closed_count": 0, "pnl": 0.0},
        )
        rec["candidate_count"] += 1
    for row in open_positions:
        ticker = str(row.get("ticker") or "").upper()
        rec = out.setdefault(
            ticker,
            {"candidate_count": 0, "open_count": 0, "closed_count": 0, "pnl": 0.0},
        )
        rec["open_count"] += 1
    for row in closed:
        ticker = str(row.get("ticker") or "").upper()
        rec = out.setdefault(
            ticker,
            {"candidate_count": 0, "open_count": 0, "closed_count": 0, "pnl": 0.0},
        )
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


def _round(value: Any, digits: int = 4) -> Any:
    parsed = _float_or_none(value)
    if parsed is None:
        return None
    return round(parsed, digits)


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
        "scope": "default_off_ai_optical_iwm_confirmed_paper_attribution",
    }
