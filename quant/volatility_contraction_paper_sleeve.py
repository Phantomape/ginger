"""Default-off QQQ-confirmed volatility-contraction paper sleeve.

This shared helper promotes the exp-20260525-022 replay lead into a reusable
forward-observation boundary. It emits paper candidates and ledger state only;
it never emits live orders and never changes core signal generation, ranking,
sizing, exits, heat, LLM, or news behavior.
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


SLEEVE_NAME = "VOLATILITY_CONTRACTION_QQQ_CONFIRMED_PAPER"
RULE_VERSION = "volatility_contraction_qqq_confirmed_top2_v1"
TOPN_CANDIDATE_RULE_VERSION = "vcp_qqq_confirmed_topn_equal_notional_v1"
RANK_NOTIONAL_PROFILE_RULE_VERSION = "vcp_top2_rank_notional_profile_v1"
MARKET_CONFIRMATION_RULE_VERSION = "volatility_contraction_qqq_gt_spy20_v1"
REPLACEMENT_VALUE_RULE_VERSION = "volatility_contraction_forward_replacement_value_v1"
POCKET_PIVOT_CONTEXT_RULE_VERSION = "pre_signal_pocket_pivot_10d_v1"
STATE_SCHEMA_VERSION = 1

DEFAULT_STATE_PATH = data_artifact_path("volatility_contraction_paper_state")
DEFAULT_SNAPSHOT_LOG_PATH = data_artifact_path("volatility_contraction_paper_snapshots")

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
    "rank_notional_profile": [1.0, 1.25],
    "short_atr_days": 10,
    "long_atr_days": 50,
    "breakout_lookback_days": 20,
    "ma_days": 50,
    "max_short_to_long_atr_ratio": 0.75,
    "min_candidate_rs_vs_spy": 0.0,
    "min_dollar_volume": 25_000_000.0,
    "market_confirmation_lookback_days": 20,
    "daily_entry_slots": 2,
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


def empty_volatility_contraction_paper_state() -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "sleeve": SLEEVE_NAME,
        "updated_at": None,
        "pending_entries": [],
        "open_positions": [],
        "closed_positions": [],
        "skipped_entries": [],
    }


def load_volatility_contraction_paper_state(
    path: Path | str = DEFAULT_STATE_PATH,
) -> dict[str, Any]:
    state_path = Path(path)
    if not state_path.exists():
        return empty_volatility_contraction_paper_state()
    with state_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    state = empty_volatility_contraction_paper_state()
    if isinstance(payload, dict):
        state.update(payload)
    _normalise_state(state)
    return state


def save_volatility_contraction_paper_state(
    state: dict[str, Any],
    path: Path | str = DEFAULT_STATE_PATH,
) -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now_iso()
    with state_path.open("w", encoding="utf-8") as handle:
        json.dump(_safe(state), handle, indent=2, sort_keys=True)
        handle.write("\n")


def append_volatility_contraction_paper_snapshot(
    snapshot: dict[str, Any],
    path: Path | str = DEFAULT_SNAPSHOT_LOG_PATH,
) -> None:
    log_path = Path(path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_safe(snapshot), sort_keys=True) + "\n")


def empty_volatility_contraction_paper_sleeve_snapshot(
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
        "market_confirmation": {"passed": False, "status": reason},
        "forward_paper_gate": {"passed": False, "status": "blocked", "reasons": [reason]},
        "production_impact": _production_impact(),
        "error": reason,
    }


def build_volatility_contraction_paper_sleeve_snapshot(
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
        return empty_volatility_contraction_paper_sleeve_snapshot(
            as_of_date,
            "missing_ohlcv",
        )

    working_state = deepcopy(
        state
        if state is not None
        else load_volatility_contraction_paper_state(state_path)
    )
    _normalise_state(working_state)

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
    candidates, rejected, market = build_volatility_contraction_candidates(
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
        for candidate in candidates[: min(room, int(cfg["daily_entry_slots"]))]:
            entry = _pending_entry_from_candidate(candidate, as_of=as_of_date, config=cfg)
            working_state["pending_entries"].append(entry)
            new_pending.append(entry)
    for candidate in candidates[len(new_pending):]:
        rejected.append({**candidate, "reasons": ["daily_topn_or_capacity_limit"]})

    closed = working_state.get("closed_positions") or []
    open_positions = working_state.get("open_positions") or []
    replacement_value_report = build_volatility_contraction_replacement_value_report(
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
        "market_confirmation_rule_version": MARKET_CONFIRMATION_RULE_VERSION,
        "replacement_value_rule_version": REPLACEMENT_VALUE_RULE_VERSION,
        "asof_date": as_of_date,
        "generated_at": utc_now_iso(),
        "enabled": False,
        "paper_enabled": bool(cfg.get("paper_enabled", True)),
        "trade_enabled": False,
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
        "market_confirmation": market,
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
        save_volatility_contraction_paper_state(working_state, state_path)
        append_volatility_contraction_paper_snapshot(snapshot, snapshot_log_path)
    return _safe(snapshot)


def build_volatility_contraction_candidates(
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
    market = build_qqq_spy_market_confirmation(
        rows_by_ticker,
        as_of=as_of_date,
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
        candidate.update(compute_pre_signal_pocket_pivot_context(rows, as_of_date))
        reasons = []
        if market["passed"] is not True:
            reasons.append("qqq_spy_confirmation_failed")
        if ticker in active:
            reasons.append("already_open_in_paper_sleeve")
        if ticker in pending:
            reasons.append("already_pending_in_paper_sleeve")
        candidate["market_confirmation"] = deepcopy(market)
        candidate["rule_version"] = RULE_VERSION
        candidate["market_confirmation_rule_version"] = MARKET_CONFIRMATION_RULE_VERSION
        candidate["trade_enabled"] = False
        candidate["alters_orders"] = False
        if reasons:
            rejected.append({**candidate, "reasons": reasons})
            continue
        accepted.append(candidate)

    accepted.sort(
        key=lambda row: (
            row["date"],
            row["short_to_long_atr_ratio"],
            -row["candidate_day_rs_vs_spy"],
            -row["dollar_volume"],
            row["ticker"],
        )
    )
    for rank, candidate in enumerate(accepted, start=1):
        candidate["topn_candidate_rule_version"] = TOPN_CANDIDATE_RULE_VERSION
        candidate["vcp_candidate_rank_on_signal_date"] = rank
        candidate["max_paper_trades_per_day"] = int(cfg["daily_entry_slots"])
        _apply_rank_notional_profile(candidate, rank=rank, config=cfg)
    return accepted, rejected, market


def build_qqq_spy_market_confirmation(
    ohlcv_by_ticker: dict[str, Any],
    *,
    as_of: str,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = _config(config)
    lookback = int(cfg["market_confirmation_lookback_days"])
    rows_by_ticker = {
        str(ticker).upper(): _normalise_ohlcv_rows(rows)
        for ticker, rows in (ohlcv_by_ticker or {}).items()
    }
    qqq_ret, qqq_date = _momentum(rows_by_ticker.get("QQQ") or [], as_of, lookback)
    spy_ret, spy_date = _momentum(rows_by_ticker.get("SPY") or [], as_of, lookback)
    status = "ok"
    if qqq_ret is None or spy_ret is None:
        status = "missing_market_context"
    passed = qqq_ret is not None and spy_ret is not None and qqq_ret > spy_ret
    return {
        "rule_version": MARKET_CONFIRMATION_RULE_VERSION,
        "passed": passed,
        "status": status if passed else "qqq_not_leading_spy" if status == "ok" else status,
        "lookback_trading_days": lookback,
        "asof_date": _date10(as_of),
        "qqq_asof_date": qqq_date,
        "spy_asof_date": spy_date,
        "qqq_return_20d": _round(qqq_ret, 6),
        "spy_return_20d": _round(spy_ret, 6),
        "qqq_minus_spy_return_20d": _round(
            qqq_ret - spy_ret if qqq_ret is not None and spy_ret is not None else None,
            6,
        ),
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
        "trade_enabled": False,
        "alters_orders": False,
    }


def compute_pre_signal_pocket_pivot_context(
    rows: list[dict[str, Any]],
    signal_date: str,
    *,
    scan_days: int = 10,
    down_volume_lookback_days: int = 10,
) -> dict[str, Any]:
    """Return PIT-safe pocket-pivot support metadata before a signal date."""
    normalised = _normalise_ohlcv_rows(rows)
    signal_idx = _latest_index_on_or_before(normalised, _date10(signal_date))
    base = {
        "pocket_pivot_context_rule_version": POCKET_PIVOT_CONTEXT_RULE_VERSION,
        "pre_signal_pocket_pivot_seen_10d": False,
        "pre_signal_pocket_pivot_count_10d": 0,
        "latest_pre_signal_pocket_pivot_date": None,
        "latest_pre_signal_pocket_pivot_volume_ratio": None,
        "pocket_pivot_context_status": "unavailable",
        "pocket_pivot_scan_days": int(scan_days),
        "pocket_pivot_down_volume_lookback_days": int(down_volume_lookback_days),
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
        "trade_enabled": False,
        "alters_orders": False,
    }
    if signal_idx is None or str(normalised[signal_idx].get("date") or "") != _date10(signal_date):
        return {**base, "pocket_pivot_context_status": "missing_signal_date"}
    if signal_idx <= 0 or scan_days <= 0 or down_volume_lookback_days <= 0:
        return {**base, "pocket_pivot_context_status": "insufficient_history"}

    scan_start = max(1, signal_idx - int(scan_days))
    hits: list[dict[str, Any]] = []
    prior_up_days = 0
    up_days_without_down_volume = 0
    up_days_with_down_volume = 0

    for pivot_idx in range(scan_start, signal_idx):
        cur_close = _positive_float(normalised[pivot_idx].get("close"))
        prev_close = _positive_float(normalised[pivot_idx - 1].get("close"))
        volume = _positive_float(normalised[pivot_idx].get("volume"))
        if cur_close is None or prev_close is None or volume is None:
            continue
        if cur_close <= prev_close:
            continue
        prior_up_days += 1
        down_volumes: list[float] = []
        lookback_start = max(1, pivot_idx - int(down_volume_lookback_days))
        for prior_idx in range(lookback_start, pivot_idx):
            prior_close = _positive_float(normalised[prior_idx].get("close"))
            prior_prev_close = _positive_float(normalised[prior_idx - 1].get("close"))
            prior_volume = _positive_float(normalised[prior_idx].get("volume"))
            if prior_close is None or prior_prev_close is None or prior_volume is None:
                continue
            if prior_close < prior_prev_close:
                down_volumes.append(prior_volume)
        if not down_volumes:
            up_days_without_down_volume += 1
            continue
        up_days_with_down_volume += 1
        max_down_volume = max(down_volumes)
        volume_ratio = volume / max_down_volume if max_down_volume > 0 else None
        if volume > max_down_volume:
            hits.append(
                {
                    "date": normalised[pivot_idx]["date"],
                    "volume_ratio": _round(volume_ratio, 6),
                    "volume": _round(volume, 2),
                    "max_prior_down_volume": _round(max_down_volume, 2),
                }
            )

    if hits:
        latest = hits[-1]
        return {
            **base,
            "pre_signal_pocket_pivot_seen_10d": True,
            "pre_signal_pocket_pivot_count_10d": len(hits),
            "latest_pre_signal_pocket_pivot_date": latest["date"],
            "latest_pre_signal_pocket_pivot_volume_ratio": latest["volume_ratio"],
            "pocket_pivot_context_status": "available",
            "prior_up_days_checked": prior_up_days,
            "prior_up_days_with_down_volume": up_days_with_down_volume,
            "prior_up_days_without_down_volume": up_days_without_down_volume,
        }
    if up_days_with_down_volume:
        status = "available"
    elif prior_up_days:
        status = "no_prior_down_volume"
    else:
        status = "no_prior_up_day"
    return {
        **base,
        "pocket_pivot_context_status": status,
        "prior_up_days_checked": prior_up_days,
        "prior_up_days_with_down_volume": up_days_with_down_volume,
        "prior_up_days_without_down_volume": up_days_without_down_volume,
    }


def build_volatility_contraction_replacement_value_report(
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
            round(float(rec["positive_closed_pnl"]) / positive_pnl, 6)
            if positive_pnl > 0
            else None
        )
    top_positive_share = (
        max(
            (float(row.get("positive_pnl_share") or 0.0) for row in by_ticker.values()),
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
    idx = _latest_index_on_or_before(rows, as_of)
    spy_rows = rows_by_ticker.get("SPY") or []
    spy_idx = _latest_index_on_or_before(spy_rows, as_of)
    min_history = (
        max(
            int(config["long_atr_days"]),
            int(config["ma_days"]),
            int(config["breakout_lookback_days"]),
        )
        + 2
    )
    if idx is None or spy_idx is None or idx < min_history or spy_idx < 1:
        return None
    cur = rows[idx]
    if str(cur.get("date") or "")[:10] != as_of:
        return None
    close = _positive_float(cur.get("close"))
    volume = _positive_float(cur.get("volume"))
    if close is None or volume is None:
        return None
    dollar_volume = close * volume
    if dollar_volume < float(config["min_dollar_volume"]):
        return None

    breakout_days = int(config["breakout_lookback_days"])
    prior_highs = [
        _positive_float(row.get("high"))
        for row in rows[idx - breakout_days:idx]
    ]
    prior_high_values = [value for value in prior_highs if value is not None]
    if len(prior_high_values) < breakout_days:
        return None
    prior_breakout_high = max(prior_high_values)
    if close <= prior_breakout_high:
        return None

    ma_days = int(config["ma_days"])
    ma_values = [
        _positive_float(row.get("close"))
        for row in rows[idx - ma_days:idx]
    ]
    moving_average = _avg(ma_values)
    if moving_average is None or close <= moving_average:
        return None

    short_days = int(config["short_atr_days"])
    long_days = int(config["long_atr_days"])
    short_atr = _avg([
        _true_range_pct(rows, tr_idx)
        for tr_idx in range(idx - short_days, idx)
    ])
    long_atr = _avg([
        _true_range_pct(rows, tr_idx)
        for tr_idx in range(idx - long_days, idx - short_days)
    ])
    if short_atr is None or long_atr is None or long_atr <= 0:
        return None
    atr_ratio = short_atr / long_atr
    if atr_ratio > float(config["max_short_to_long_atr_ratio"]):
        return None

    candidate_ret = _close_return(rows, idx - 1, idx)
    spy_candidate_ret = _close_return(spy_rows, spy_idx - 1, spy_idx)
    if candidate_ret is None or spy_candidate_ret is None:
        return None
    rs_vs_spy = candidate_ret - spy_candidate_ret
    if rs_vs_spy <= float(config["min_candidate_rs_vs_spy"]):
        return None

    return {
        "date": as_of,
        "signal_date": as_of,
        "ticker": ticker,
        "sector": SECTOR_MAP.get(ticker, "Unknown"),
        "strategy": "volatility_contraction_breakout",
        "close": round(close, 4),
        "entry_price": round(close, 4),
        "breakout_above_prior_20d_high_pct": round((close / prior_breakout_high) - 1.0, 6),
        "pct_above_50d_ma": round((close / moving_average) - 1.0, 6),
        "short_atr_pct": round(short_atr, 6),
        "long_atr_pct": round(long_atr, 6),
        "short_to_long_atr_ratio": round(atr_ratio, 6),
        "candidate_day_return": round(candidate_ret, 6),
        "candidate_day_spy_return": round(spy_candidate_ret, 6),
        "candidate_day_rs_vs_spy": round(rs_vs_spy, 6),
        "dollar_volume": round(dollar_volume, 2),
        "intended_notional": float(config["paper_notional_usd"]),
    }


def _apply_rank_notional_profile(
    candidate: dict[str, Any],
    *,
    rank: int,
    config: dict[str, Any],
) -> None:
    profile = _normalise_rank_notional_profile(config)
    base_notional = float(config["paper_notional_usd"])
    scalar = _rank_notional_scalar(rank, profile)
    candidate["rank_notional_profile_rule_version"] = RANK_NOTIONAL_PROFILE_RULE_VERSION
    candidate["rank_notional_profile"] = profile
    candidate["rank_notional_scalar"] = round(scalar, 6)
    candidate["base_paper_notional_usd"] = base_notional
    candidate["intended_notional"] = round(base_notional * scalar, 2)
    candidate["trade_enabled"] = False
    candidate["alters_orders"] = False


def _normalise_rank_notional_profile(config: dict[str, Any]) -> list[float]:
    raw_profile = config.get("rank_notional_profile")
    if not isinstance(raw_profile, (list, tuple)) or not raw_profile:
        return [1.0]
    profile: list[float] = []
    for raw_scalar in raw_profile:
        scalar = _float_or_none(raw_scalar)
        profile.append(scalar if scalar is not None and scalar > 0 else 1.0)
    return profile


def _rank_notional_scalar(rank: int, profile: list[float]) -> float:
    if rank <= 0:
        return 1.0
    idx = rank - 1
    if idx >= len(profile):
        return 1.0
    return profile[idx]


def _entry_notional(entry: dict[str, Any], config: dict[str, Any]) -> float:
    notional = _positive_float(entry.get("notional"))
    if notional is not None:
        return notional
    candidate = entry.get("candidate") or {}
    candidate_notional = _positive_float(candidate.get("intended_notional"))
    if candidate_notional is not None:
        return candidate_notional
    return float(config["paper_notional_usd"])


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
        if exit_reason and current_price:
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
            "strategy": "volatility_contraction_breakout",
            "entry_date": as_of,
            "entry_price": entry_price,
            "decision_close_price": candidate.get("close"),
            "notional": notional,
            "shares": round(notional / entry_price, 6) if entry_price else None,
            "observed_trading_days": 0,
            "last_price": current_prices.get(ticker),
            "status": "open",
            "candidate": deepcopy(candidate),
            "rank_notional_profile_rule_version": candidate.get(
                "rank_notional_profile_rule_version"
            ),
            "rank_notional_scalar": candidate.get("rank_notional_scalar"),
            "base_paper_notional_usd": candidate.get("base_paper_notional_usd"),
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
        "decision_id": f"{SLEEVE_NAME}:{as_of}:{ticker}",
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


def _latest_index_on_or_before(rows: list[dict[str, Any]], as_of: str) -> int | None:
    matches = [
        idx
        for idx, row in enumerate(rows or [])
        if str(row.get("date") or "")[:10] <= str(as_of)[:10]
    ]
    return max(matches) if matches else None


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


def _close_return(rows: list[dict[str, Any]], start_idx: int, end_idx: int) -> float | None:
    if start_idx < 0 or end_idx >= len(rows):
        return None
    start_close = _positive_float(rows[start_idx].get("close"))
    end_close = _positive_float(rows[end_idx].get("close"))
    if not start_close or end_close is None:
        return None
    return (end_close / start_close) - 1.0


def _true_range_pct(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx <= 0 or idx >= len(rows):
        return None
    high = _positive_float(rows[idx].get("high"))
    low = _positive_float(rows[idx].get("low"))
    prev_close = _positive_float(rows[idx - 1].get("close"))
    close = _positive_float(rows[idx].get("close"))
    if high is None or low is None or prev_close is None or not close:
        return None
    true_range = max(high - low, abs(high - prev_close), abs(low - prev_close))
    return true_range / close


def _avg(values: list[float | None]) -> float | None:
    clean = [value for value in values if isinstance(value, (int, float))]
    if not clean:
        return None
    return sum(clean) / len(clean)


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
        "scope": "default_off_volatility_contraction_qqq_confirmed_paper_attribution",
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
