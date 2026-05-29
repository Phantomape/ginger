"""Default-off volume-breadth confirmed breakout paper sleeve.

This shared helper promotes the exp-20260526-013 free-OHLCV replay lead into a
production-visible forward observation boundary. It emits paper candidates and
ledger state only; it never emits live orders and never changes core signal
generation, ranking, sizing, exits, heat, LLM, or news behavior.
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
    from fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage
    from risk_engine import SECTOR_MAP
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.constants import ROUND_TRIP_COST_PCT
    from quant.fill_model import SLIPPAGE_BPS_TARGET, apply_entry_fill, apply_slippage
    from quant.risk_engine import SECTOR_MAP


SLEEVE_NAME = "VOLUME_BREADTH_BREAKOUT_PAPER"
RULE_VERSION = "volume_breadth_breakout_shared_top1_v1"
BREADTH_RULE_VERSION = "volume_breadth_thrust_confirmed_breakout_v1"
BREADTH_INTENSITY_RULE_VERSION = "vbb_breadth_intensity_support_v1"
HIGH_CLOSE_SUPPORT_RULE_VERSION = "vbb_signal_day_high_close_support_v1"
COST_LIQUIDITY_SUPPORT_RULE_VERSION = "vbb_cost_liquidity_support_v1"
REPLACEMENT_VALUE_RULE_VERSION = "volume_breadth_breakout_forward_replacement_value_v1"
STATE_SCHEMA_VERSION = 1

DEFAULT_STATE_PATH = data_artifact_path("volume_breadth_breakout_paper_state")
DEFAULT_SNAPSHOT_LOG_PATH = data_artifact_path("volume_breadth_breakout_paper_snapshots")

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
    "breakout_lookback_days": 20,
    "moving_average_days": 50,
    "volume_lookback_days": 20,
    "min_dollar_volume": 40_000_000.0,
    "min_candidate_volume_ratio_20": 1.25,
    "min_candidate_rs_vs_spy": 0.0,
    "min_volume_breadth_fraction": 0.12,
    "min_market_up_fraction": 0.52,
    "min_above_50d_fraction": 0.45,
    "breadth_intensity_min_volume_breadth_fraction": 0.25,
    "breadth_intensity_notional_scalar": 1.10,
    "high_close_support_min_close_location": 0.70,
    "high_close_support_notional_scalar": 1.10,
    "cost_liquidity_min_dollar_volume": 200_000_000.0,
    "cost_liquidity_max_range_pct": 0.10,
    "cost_liquidity_notional_scalar": 1.05,
    "min_breadth_eligible_tickers": 30,
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


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def empty_volume_breadth_breakout_paper_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_entries": [],
    }


def load_volume_breadth_breakout_paper_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_volume_breadth_breakout_paper_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_volume_breadth_breakout_paper_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_volume_breadth_breakout_paper_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(_safe(state), handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_volume_breadth_breakout_paper_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(snapshot), sort_keys=True) + "\n")


def empty_volume_breadth_breakout_paper_sleeve_snapshot(
    as_of: str,
    reason: str,
) -> dict[str, Any]:
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
        "volume_breadth_context": {"passed": False, "status": reason},
        "breadth_intensity_support": {
            "rule_version": BREADTH_INTENSITY_RULE_VERSION,
            "supported_candidate_count": 0,
            "trade_enabled": False,
            "alters_orders": False,
        },
        "high_close_support": {
            "rule_version": HIGH_CLOSE_SUPPORT_RULE_VERSION,
            "supported_candidate_count": 0,
            "trade_enabled": False,
            "alters_orders": False,
        },
        "cost_liquidity_support": {
            "rule_version": COST_LIQUIDITY_SUPPORT_RULE_VERSION,
            "supported_candidate_count": 0,
            "trade_enabled": False,
            "alters_orders": False,
        },
        "candidate_universe": {"status": reason, "ticker_count": 0},
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "production_impact": _production_impact(),
        "error": reason,
    }


def build_volume_breadth_breakout_paper_sleeve_snapshot(
    *,
    as_of: str,
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
    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    if not rows_by_ticker:
        return empty_volume_breadth_breakout_paper_sleeve_snapshot(
            as_of_date,
            "missing_ohlcv",
        )

    working_state = deepcopy(
        state
        if state is not None
        else load_volume_breadth_breakout_paper_state(state_path)
    )
    _normalise_state(working_state)

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
    candidates, rejected, breadth = build_volume_breadth_breakout_candidates(
        as_of=as_of_date,
        ohlcv_by_ticker=rows_by_ticker,
        candidate_universe=universe,
        open_position_tickers=active_tickers,
        pending_tickers=pending_tickers,
        config=cfg,
    )

    open_positions = working_state.get("open_positions") or []
    room = max(0, int(cfg["max_active_positions"]) - len(open_positions))
    new_pending = []
    if room > 0 and cfg.get("paper_enabled", True):
        capacity = min(room, int(cfg["daily_entry_slots"]))
        for candidate in candidates[:capacity]:
            entry = _pending_entry_from_candidate(candidate, as_of=as_of_date, config=cfg)
            working_state["pending_entries"].append(entry)
            new_pending.append(entry)
    for candidate in candidates[len(new_pending):]:
        rejected.append({**candidate, "reasons": ["daily_top1_or_capacity_limit"]})

    closed = working_state.get("closed_positions") or []
    open_positions = working_state.get("open_positions") or []
    replacement_value_report = build_volume_breadth_breakout_replacement_value_report(
        candidates=candidates,
        pending_entries=working_state.get("pending_entries") or [],
        open_positions=open_positions,
        closed_positions=closed,
        skipped_entries=working_state.get("skipped_entries") or [],
        config=cfg,
    )
    gate = _forward_paper_gate(closed, cfg)

    snapshot = {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "rule_version": RULE_VERSION,
        "volume_breadth_rule_version": BREADTH_RULE_VERSION,
        "replacement_value_rule_version": REPLACEMENT_VALUE_RULE_VERSION,
        "asof_date": as_of_date,
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": bool(cfg.get("paper_enabled", True)),
        "trade_enabled": False,
        "trade_enabled_reason": "default_off_until_forward_gate_and_live_adapter_pass",
        "candidate_count": len(candidates),
        "rejected_candidate_count": len(rejected),
        "new_pending_count": len(new_pending),
        "filled_count": len(filled_today),
        "closed_count_today": len(closed_today),
        "pending_count": len(working_state.get("pending_entries") or []),
        "open_position_count": len(open_positions),
        "closed_position_count": len(closed),
        "realized_pnl_to_date": round(sum(_money(row.get("pnl")) for row in closed), 2),
        "unrealized_pnl": round(sum(_money(row.get("unrealized_pnl")) for row in open_positions), 2),
        "volume_breadth_context": breadth,
        "breadth_intensity_support": {
            "rule_version": BREADTH_INTENSITY_RULE_VERSION,
            "min_volume_breadth_fraction": float(
                cfg["breadth_intensity_min_volume_breadth_fraction"]
            ),
            "paper_notional_scalar": float(cfg["breadth_intensity_notional_scalar"]),
            "supported_candidate_count": sum(
                1 for row in candidates if row.get("breadth_intensity_support_pass_v1")
            ),
            "trade_enabled": False,
            "alters_orders": False,
        },
        "high_close_support": {
            "rule_version": HIGH_CLOSE_SUPPORT_RULE_VERSION,
            "min_close_location": float(cfg["high_close_support_min_close_location"]),
            "paper_notional_scalar": float(cfg["high_close_support_notional_scalar"]),
            "supported_candidate_count": sum(
                1 for row in candidates if row.get("high_close_support_pass_v1")
            ),
            "trade_enabled": False,
            "alters_orders": False,
        },
        "cost_liquidity_support": {
            "rule_version": COST_LIQUIDITY_SUPPORT_RULE_VERSION,
            "min_dollar_volume": float(cfg["cost_liquidity_min_dollar_volume"]),
            "max_range_pct": float(cfg["cost_liquidity_max_range_pct"]),
            "paper_notional_scalar": float(cfg["cost_liquidity_notional_scalar"]),
            "supported_candidate_count": sum(
                1 for row in candidates if row.get("cost_liquidity_support_pass_v1")
            ),
            "trade_enabled": False,
            "alters_orders": False,
        },
        "candidate_universe": {
            "status": universe["status"],
            "ticker_count": len(universe["tickers"]),
        },
        "candidates": deepcopy(candidates),
        "rejected_candidates": deepcopy(rejected[:50]),
        "new_pending_entries": deepcopy(new_pending),
        "filled_entries": deepcopy(filled_today),
        "closed_positions_today": deepcopy(closed_today),
        "pending_entries": deepcopy(working_state["pending_entries"]),
        "open_positions": deepcopy(open_positions),
        "closed_positions": deepcopy(closed),
        "skipped_entries_today": deepcopy(skipped_today),
        "replacement_value_report": replacement_value_report,
        "forward_paper_gate": gate,
        "production_impact": _production_impact(),
        "next_action": "paper_observe_forward_replacement_value_no_orders",
    }

    if persist:
        save_volume_breadth_breakout_paper_state(working_state, state_path)
        append_volume_breadth_breakout_paper_snapshot(snapshot, snapshot_log_path)
    return _safe(snapshot)


def build_volume_breadth_breakout_candidates(
    *,
    as_of: str,
    ohlcv_by_ticker: dict[str, Any],
    candidate_universe: dict[str, Any] | list[str] | None = None,
    open_position_tickers: set[str] | None = None,
    pending_tickers: set[str] | None = None,
    config: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    cfg = _config(config)
    as_of_date = _date10(as_of)
    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    universe = _normalise_candidate_universe(candidate_universe, rows_by_ticker)
    breadth = build_volume_breadth_context(
        rows_by_ticker,
        as_of=as_of_date,
        candidate_universe=universe,
        config=cfg,
    )
    active = {str(value).upper() for value in (open_position_tickers or set())}
    pending = {str(value).upper() for value in (pending_tickers or set())}
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for ticker in universe["tickers"]:
        if ticker in EXCLUDED_TICKERS:
            continue
        rows = rows_by_ticker.get(ticker) or []
        candidate = _candidate_for_ticker(rows_by_ticker, ticker, rows, as_of_date, cfg)
        if candidate is None:
            continue
        reasons = []
        if breadth["passed"] is not True:
            reasons.append("volume_breadth_thrust_failed")
        if ticker in active:
            reasons.append("already_open_in_paper_sleeve")
        if ticker in pending:
            reasons.append("already_pending_in_paper_sleeve")
        candidate["volume_breadth_context"] = deepcopy(breadth)
        candidate["rule_version"] = RULE_VERSION
        candidate["volume_breadth_rule_version"] = BREADTH_RULE_VERSION
        candidate["trade_enabled"] = False
        candidate["alters_orders"] = False
        if reasons:
            rejected.append({**candidate, "reasons": reasons})
            continue
        accepted.append(candidate)

    accepted.sort(
        key=lambda row: (
            row["date"],
            -float(row["volume_breadth_score"]),
            -float(row["candidate_day_rs_vs_spy"]),
            -float(row["volume_ratio_20"]),
            -float(row["dollar_volume"]),
            row["ticker"],
        )
    )
    for rank, candidate in enumerate(accepted, start=1):
        breadth_fraction = _float_or_none(
            (candidate.get("volume_breadth_context") or {}).get("volume_breadth_fraction")
        )
        support_pass = (
            breadth_fraction is not None
            and breadth_fraction >= float(cfg["breadth_intensity_min_volume_breadth_fraction"])
        )
        support_scalar = (
            float(cfg["breadth_intensity_notional_scalar"]) if support_pass else 1.0
        )
        close_location = _float_or_none(candidate.get("signal_day_close_location_value"))
        high_close_pass = (
            close_location is not None
            and close_location >= float(cfg["high_close_support_min_close_location"])
        )
        high_close_scalar = (
            float(cfg["high_close_support_notional_scalar"]) if high_close_pass else 1.0
        )
        cost_liquidity = _candidate_cost_liquidity(candidate)
        cost_liquidity_pass = (
            cost_liquidity["dollar_volume"] is not None
            and cost_liquidity["signal_day_range_pct"] is not None
            and cost_liquidity["dollar_volume"] >= float(cfg["cost_liquidity_min_dollar_volume"])
            and cost_liquidity["signal_day_range_pct"] <= float(cfg["cost_liquidity_max_range_pct"])
        )
        cost_liquidity_scalar = (
            float(cfg["cost_liquidity_notional_scalar"]) if cost_liquidity_pass else 1.0
        )
        base_notional = float(cfg["paper_notional_usd"])
        candidate["volume_breadth_candidate_rank_on_signal_date"] = rank
        candidate["max_paper_trades_per_day"] = int(cfg["daily_entry_slots"])
        candidate["base_paper_notional_usd"] = base_notional
        candidate["breadth_intensity_support_rule_version"] = BREADTH_INTENSITY_RULE_VERSION
        candidate["breadth_intensity_known_at"] = "after_signal_date_close_before_next_open_paper_entry"
        candidate["breadth_intensity_trade_enabled"] = False
        candidate["breadth_intensity_alters_orders"] = False
        candidate["breadth_intensity_min_volume_breadth_fraction"] = float(
            cfg["breadth_intensity_min_volume_breadth_fraction"]
        )
        candidate["breadth_intensity_fraction"] = _round(breadth_fraction, 6)
        candidate["breadth_intensity_support_pass_v1"] = support_pass
        candidate["breadth_intensity_notional_scalar"] = support_scalar
        candidate["high_close_support_rule_version"] = HIGH_CLOSE_SUPPORT_RULE_VERSION
        candidate["high_close_support_known_at"] = "after_signal_date_close_before_next_open_paper_entry"
        candidate["high_close_support_trade_enabled"] = False
        candidate["high_close_support_alters_orders"] = False
        candidate["high_close_support_min_close_location"] = float(
            cfg["high_close_support_min_close_location"]
        )
        candidate["high_close_support_pass_v1"] = high_close_pass
        candidate["high_close_support_notional_scalar"] = high_close_scalar
        candidate["cost_liquidity_support_rule_version"] = COST_LIQUIDITY_SUPPORT_RULE_VERSION
        candidate["cost_liquidity_known_at"] = "after_signal_date_close_before_next_open_paper_entry"
        candidate["cost_liquidity_trade_enabled"] = False
        candidate["cost_liquidity_alters_orders"] = False
        candidate["cost_liquidity_min_dollar_volume"] = float(
            cfg["cost_liquidity_min_dollar_volume"]
        )
        candidate["cost_liquidity_max_range_pct"] = float(
            cfg["cost_liquidity_max_range_pct"]
        )
        candidate["cost_liquidity_dollar_volume"] = _round(
            cost_liquidity["dollar_volume"],
            2,
        )
        candidate["cost_liquidity_signal_day_range_pct"] = _round(
            cost_liquidity["signal_day_range_pct"],
            6,
        )
        candidate["cost_liquidity_support_pass_v1"] = cost_liquidity_pass
        candidate["cost_liquidity_notional_scalar"] = cost_liquidity_scalar
        candidate["intended_notional"] = round(
            base_notional * support_scalar * high_close_scalar * cost_liquidity_scalar,
            2,
        )
    return accepted, rejected, breadth


def build_volume_breadth_context(
    ohlcv_by_ticker: dict[str, Any],
    *,
    as_of: str,
    candidate_universe: dict[str, Any] | list[str] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = _config(config)
    as_of_date = _date10(as_of)
    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    universe = _normalise_candidate_universe(candidate_universe, rows_by_ticker)
    tickers = sorted(set(universe["tickers"]).difference(EXCLUDED_TICKERS))
    eligible = 0
    up_volume_spike = 0
    positive_day = 0
    above_50d = 0
    ma_days = int(cfg["moving_average_days"])
    vol_days = int(cfg["volume_lookback_days"])

    for ticker in tickers:
        rows = rows_by_ticker.get(ticker) or []
        idx = _index_on_date(rows, as_of_date)
        if idx is None or idx < ma_days or idx <= 0:
            continue
        close = _positive_float(rows[idx].get("close"))
        prev_close = _positive_float(rows[idx - 1].get("close"))
        volume = _positive_float(rows[idx].get("volume"))
        avg_volume = _prior_average(rows, idx, vol_days, "volume")
        ma50 = _prior_average(rows, idx, ma_days, "close")
        if not close or not prev_close or not volume or not avg_volume or not ma50:
            continue
        eligible += 1
        volume_ratio = volume / avg_volume if avg_volume else 0.0
        if close > prev_close:
            positive_day += 1
        if close > ma50:
            above_50d += 1
        if close > prev_close and volume_ratio >= float(cfg["min_candidate_volume_ratio_20"]):
            up_volume_spike += 1

    volume_breadth = up_volume_spike / eligible if eligible else None
    market_up = positive_day / eligible if eligible else None
    above50 = above_50d / eligible if eligible else None
    passed = (
        eligible >= int(cfg["min_breadth_eligible_tickers"])
        and volume_breadth is not None
        and market_up is not None
        and above50 is not None
        and volume_breadth >= float(cfg["min_volume_breadth_fraction"])
        and market_up >= float(cfg["min_market_up_fraction"])
        and above50 >= float(cfg["min_above_50d_fraction"])
    )
    status = "passed" if passed else "failed"
    if eligible < int(cfg["min_breadth_eligible_tickers"]):
        status = "insufficient_eligible_tickers"
    return {
        "rule_version": BREADTH_RULE_VERSION,
        "asof_date": as_of_date,
        "passed": passed,
        "status": status,
        "eligible_ticker_count": eligible,
        "candidate_source_ticker_count": len(tickers),
        "up_volume_spike_count": up_volume_spike,
        "positive_day_count": positive_day,
        "above_50d_count": above_50d,
        "volume_breadth_fraction": _round(volume_breadth, 6),
        "market_up_fraction": _round(market_up, 6),
        "above_50d_fraction": _round(above50, 6),
        "min_volume_breadth_fraction": float(cfg["min_volume_breadth_fraction"]),
        "min_market_up_fraction": float(cfg["min_market_up_fraction"]),
        "min_above_50d_fraction": float(cfg["min_above_50d_fraction"]),
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
        "trade_enabled": False,
        "alters_orders": False,
    }


def build_volume_breadth_breakout_replacement_value_report(
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


def _candidate_for_ticker(
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    ticker: str,
    rows: list[dict[str, Any]],
    as_of: str,
    config: dict[str, Any],
) -> dict[str, Any] | None:
    idx = _index_on_date(rows, as_of)
    spy_rows = rows_by_ticker.get("SPY") or []
    spy_idx = _index_on_date(spy_rows, as_of)
    ma_days = int(config["moving_average_days"])
    breakout_days = int(config["breakout_lookback_days"])
    volume_days = int(config["volume_lookback_days"])
    if idx is None or spy_idx is None or idx < ma_days or spy_idx < 1:
        return None
    close = _positive_float(rows[idx].get("close"))
    high = _positive_float(rows[idx].get("high"))
    low = _positive_float(rows[idx].get("low"))
    volume = _positive_float(rows[idx].get("volume"))
    if not close or not volume:
        return None
    dollar_volume = close * volume
    if dollar_volume < float(config["min_dollar_volume"]):
        return None
    prior_high = _prior_high(rows, idx, breakout_days)
    ma50 = _prior_average(rows, idx, ma_days, "close")
    avg_volume = _prior_average(rows, idx, volume_days, "volume")
    if not prior_high or not ma50 or not avg_volume:
        return None
    volume_ratio = volume / avg_volume if avg_volume else None
    if volume_ratio is None or volume_ratio < float(config["min_candidate_volume_ratio_20"]):
        return None
    if close <= prior_high or close <= ma50:
        return None
    candidate_ret = _close_return(rows, idx - 1, idx)
    spy_ret = _close_return(spy_rows, spy_idx - 1, spy_idx)
    if candidate_ret is None or spy_ret is None:
        return None
    rs_vs_spy = candidate_ret - spy_ret
    if rs_vs_spy <= float(config["min_candidate_rs_vs_spy"]):
        return None
    score = (
        max(rs_vs_spy, 0.0) * 8.0
        + min(max(volume_ratio - 1.0, 0.0), 3.0)
        + max((close / prior_high) - 1.0, 0.0) * 3.0
    )
    return {
        "date": as_of,
        "signal_date": as_of,
        "ticker": ticker,
        "sector": SECTOR_MAP.get(ticker, "Unknown"),
        "strategy": "volume_breadth_breakout",
        "close": _round(close, 4),
        "signal_day_high": _round(high, 4),
        "signal_day_low": _round(low, 4),
        "signal_day_close_location_value": _round(
            _close_location_value(close=close, high=high, low=low),
            6,
        ),
        "entry_price": _round(close, 4),
        "breakout_above_prior_20d_high_pct": _round((close / prior_high) - 1.0, 6),
        "pct_above_50d_ma": _round((close / ma50) - 1.0, 6),
        "candidate_day_return": _round(candidate_ret, 6),
        "candidate_day_spy_return": _round(spy_ret, 6),
        "candidate_day_rs_vs_spy": _round(rs_vs_spy, 6),
        "volume_ratio_20": _round(volume_ratio, 6),
        "dollar_volume": _round(dollar_volume, 2),
        "volume_breadth_score": _round(score, 6),
        "source_universe": "current_production_universe_ohlcv",
        "same_day_core_entry_count": 0,
        "same_day_core_overlap": False,
        "same_ticker_core_overlap": False,
        "intended_notional": float(config["paper_notional_usd"]),
    }


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
        exit_reason = "max_hold_days" if observed_days >= int(config["hold_days"]) else None
        if exit_reason:
            exit_price = apply_slippage(current_price, SLIPPAGE_BPS_TARGET, "sell")
            closed = deepcopy(position)
            closed.update(
                {
                    "status": "closed",
                    "exit_date": as_of,
                    "exit_price": exit_price,
                    "exit_reason": exit_reason,
                    "pnl": _pnl(
                        position.get("entry_price"),
                        exit_price,
                        position.get("notional"),
                        float(config["round_trip_cost_pct"]),
                    ),
                    "return_pct_net": _return_pct(
                        position.get("entry_price"),
                        exit_price,
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
        notional = _entry_notional(entry, config)
        candidate = entry.get("candidate") or {}
        position = {
            "decision_id": entry.get("decision_id"),
            "sleeve": SLEEVE_NAME,
            "ticker": ticker,
            "strategy": "volume_breadth_breakout",
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
    notional = _positive_float(candidate.get("intended_notional"))
    if notional is None:
        notional = float(config["paper_notional_usd"])
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


def _normalise_candidate_universe(
    value: dict[str, Any] | list[str] | None,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    if isinstance(value, list):
        return {
            "status": "provided",
            "tickers": sorted({str(item).upper() for item in value if item}),
            "records": {},
        }
    if isinstance(value, dict):
        records = value.get("records") if isinstance(value.get("records"), dict) else {}
        tickers = {str(item).upper() for item in value.get("tickers") or [] if item}
        tickers.update(str(key).upper() for key in records)
        return {
            "status": value.get("status") or "provided",
            "path": value.get("path"),
            "tickers": sorted(tickers),
            "records": {
                str(key).upper(): dict(row or {})
                for key, row in records.items()
                if key
            },
        }
    return {
        "status": "default_rows_by_ticker",
        "tickers": sorted(ticker for ticker in rows_by_ticker if ticker not in EXCLUDED_TICKERS),
        "records": {},
    }


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


def _latest_index_on_or_before(rows: list[dict[str, Any]], as_of: str) -> int | None:
    matches = [
        idx
        for idx, row in enumerate(rows or [])
        if str(row.get("date") or "")[:10] <= str(as_of)[:10]
    ]
    return max(matches) if matches else None


def _index_on_date(rows: list[dict[str, Any]], as_of: str) -> int | None:
    target = _date10(as_of)
    for idx, row in enumerate(rows or []):
        if str(row.get("date") or "")[:10] == target:
            return idx
    return None


def _close_return(rows: list[dict[str, Any]], start_idx: int, end_idx: int) -> float | None:
    if start_idx < 0 or end_idx >= len(rows):
        return None
    start_close = _positive_float(rows[start_idx].get("close"))
    end_close = _positive_float(rows[end_idx].get("close"))
    if not start_close or end_close is None:
        return None
    return (end_close / start_close) - 1.0


def _prior_high(rows: list[dict[str, Any]], idx: int, days: int) -> float | None:
    if idx < days:
        return None
    clean = [
        _positive_float(row.get("high"))
        for row in rows[idx - days:idx]
    ]
    values = [value for value in clean if value is not None]
    if len(values) < days:
        return None
    return max(values)


def _close_location_value(
    *,
    close: float | None,
    high: float | None,
    low: float | None,
) -> float | None:
    if close is None or high is None or low is None or high <= low:
        return None
    return max(0.0, min(1.0, (close - low) / (high - low)))


def _candidate_cost_liquidity(candidate: dict[str, Any]) -> dict[str, float | None]:
    close = _positive_float(candidate.get("close"))
    high = _positive_float(candidate.get("signal_day_high"))
    low = _positive_float(candidate.get("signal_day_low"))
    dollar_volume = _positive_float(candidate.get("dollar_volume"))
    range_pct = None
    if close and high is not None and low is not None:
        range_pct = max(0.0, (high - low) / close)
    return {
        "dollar_volume": dollar_volume,
        "signal_day_range_pct": range_pct,
    }


def _prior_average(
    rows: list[dict[str, Any]],
    idx: int,
    days: int,
    key: str,
) -> float | None:
    if idx < days:
        return None
    clean = [
        _positive_float(row.get(key))
        for row in rows[idx - days:idx]
    ]
    values = [value for value in clean if value is not None]
    if len(values) < days:
        return None
    return sum(values) / len(values)


def _entry_notional(entry: dict[str, Any], config: dict[str, Any]) -> float:
    notional = _positive_float(entry.get("notional"))
    if notional is not None:
        return notional
    candidate = entry.get("candidate") or {}
    candidate_notional = _positive_float(candidate.get("intended_notional"))
    if candidate_notional is not None:
        return candidate_notional
    return float(config["paper_notional_usd"])


def _pnl(entry_price: Any, exit_price: Any, notional: Any, cost_pct: float) -> float:
    entry = _positive_float(entry_price)
    exit_ = _positive_float(exit_price)
    amount = _positive_float(notional)
    if not entry or exit_ is None or amount is None:
        return 0.0
    return round(amount * ((exit_ / entry) - 1.0 - cost_pct), 2)


def _return_pct(entry_price: Any, exit_price: Any, cost_pct: float) -> float:
    entry = _positive_float(entry_price)
    exit_ = _positive_float(exit_price)
    if not entry or exit_ is None:
        return 0.0
    return round((exit_ / entry) - 1.0 - cost_pct, 6)


def _single_ticker_positive_share(rows: list[dict[str, Any]]) -> float | None:
    by_ticker: dict[str, float] = {}
    for row in rows:
        pnl = _money(row.get("pnl"))
        if pnl <= 0:
            continue
        ticker = str(row.get("ticker") or "").upper()
        by_ticker[ticker] = round(by_ticker.get(ticker, 0.0) + pnl, 2)
    total = sum(by_ticker.values())
    if total <= 0:
        return None
    return round(max(by_ticker.values()) / total, 6)


def _top5_positive_share(rows: list[dict[str, Any]]) -> float | None:
    by_ticker: dict[str, float] = {}
    for row in rows:
        pnl = _money(row.get("pnl"))
        if pnl <= 0:
            continue
        ticker = str(row.get("ticker") or "").upper()
        by_ticker[ticker] = round(by_ticker.get(ticker, 0.0) + pnl, 2)
    total = sum(by_ticker.values())
    if total <= 0:
        return None
    top5 = sum(sorted(by_ticker.values(), reverse=True)[:5])
    return round(top5 / total, 6)


def _pending_sort_key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("created_asof") or ""), str(row.get("ticker") or ""))


def _production_impact() -> dict[str, Any]:
    return {
        "shared_policy_changed": True,
        "run_adapter_changed": True,
        "backtester_adapter_changed": False,
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
        "scope": "default_off_volume_breadth_breakout_paper_attribution",
    }


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(row) for key, row in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(row) for row in value]
    if isinstance(value, set):
        return sorted(_safe(row) for row in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _round(value: Any, digits: int = 4) -> Any:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _money(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(number):
        return 0.0
    return number


def _positive_float(value: Any) -> float | None:
    parsed = _float_or_none(value)
    if parsed is None or parsed <= 0:
        return None
    return parsed


def _float_or_none(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _date10(value: Any) -> str:
    if value is None:
        return ""
    return str(value)[:10]
