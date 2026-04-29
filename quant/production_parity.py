"""Production helpers that mirror backtester entry-side mechanics.

These functions keep run.py from advertising trades that the backtester would
not execute, and expose follow-through add-ons as explicit actions instead of
accidental duplicate new entries.
"""

import math

import pandas as pd

from constants import (
    ADVERSE_GAP_CANCEL_PCT,
    ADDON_CHECKPOINT_DAYS,
    ADDON_ENABLED,
    ADDON_FRACTION_OF_ORIGINAL_SHARES,
    ADDON_MAX_POSITION_PCT,
    ADDON_MIN_RS_VS_SPY,
    ADDON_MIN_UNREALIZED_PCT,
    DEFER_BREAKOUT_MAX_MIN_INDEX_PCT_FROM_MA,
    DEFER_BREAKOUT_WHEN_SLOTS_LTE,
    MAX_PER_SECTOR,
    MAX_PORTFOLIO_HEAT,
    MAX_POSITIONS,
    SECOND_ADDON_CHECKPOINT_DAYS,
    SECOND_ADDON_ENABLED,
    SECOND_ADDON_FRACTION_OF_ORIGINAL_SHARES,
    SECOND_ADDON_MAX_POSITION_PCT,
    SECOND_ADDON_MIN_RS_VS_SPY,
    SECOND_ADDON_MIN_UNREALIZED_PCT,
)


def _positive_positions(open_positions):
    return [
        p for p in (open_positions or {}).get("positions", [])
        if p.get("ticker") and (p.get("shares") or 0) > 0
    ]


def filter_entry_signal_candidates(
    signals,
    open_positions=None,
    active_tickers=None,
    market_regime=None,
    spy_pct_from_ma=None,
    qqq_pct_from_ma=None,
    max_per_sector=MAX_PER_SECTOR,
):
    """Apply shared pre-sizing entry candidate gates used by production/backtest."""
    planned = list(signals or [])
    audit = {
        "signals_before_entry_filters": len(planned),
        "already_held_dropped": [],
        "sector_cap_dropped": [],
        "bear_shallow_dropped": [],
        "signals_after_entry_filters": None,
        "max_per_sector": max_per_sector,
        "bear_shallow_active": False,
    }

    held = set(active_tickers or [])
    held.update(p.get("ticker") for p in _positive_positions(open_positions))
    held.discard(None)
    if held:
        kept = []
        for sig in planned:
            if sig.get("ticker") in held:
                audit["already_held_dropped"].append(sig)
            else:
                kept.append(sig)
        planned = kept

    sector_counts = {}
    kept = []
    for sig in planned:
        sector = sig.get("sector", "Unknown")
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
        if sector_counts[sector] <= max_per_sector:
            kept.append(sig)
        else:
            audit["sector_cap_dropped"].append(sig)
    planned = kept

    regime = str(market_regime or "").upper()
    bear_shallow = (
        regime == "BEAR"
        and spy_pct_from_ma is not None
        and qqq_pct_from_ma is not None
        and min(spy_pct_from_ma, qqq_pct_from_ma) > -0.05
    )
    audit["bear_shallow_active"] = bear_shallow
    if bear_shallow:
        bear_sectors = {"Commodities", "Healthcare"}
        kept = []
        for sig in planned:
            if (
                sig.get("sector") in bear_sectors
                and (sig.get("trade_quality_score") or 0) >= 0.75
            ):
                kept.append(sig)
            else:
                audit["bear_shallow_dropped"].append(sig)
        planned = kept

    audit["signals_after_entry_filters"] = len(planned)
    return planned, audit


def plan_entry_candidates(
    signals,
    open_positions,
    market_context=None,
    max_positions=MAX_POSITIONS,
    defer_breakout_when_slots_lte=DEFER_BREAKOUT_WHEN_SLOTS_LTE,
    defer_breakout_max_min_index_pct_from_ma=DEFER_BREAKOUT_MAX_MIN_INDEX_PCT_FROM_MA,
    active_positions_count=None,
):
    """Apply the backtester's scarce-slot breakout deferral and slot slicing."""
    market_context = market_context or {}
    input_signals = list(signals or [])
    active_positions = (
        int(active_positions_count)
        if active_positions_count is not None
        else len(_positive_positions(open_positions))
    )
    slots = max(0, max_positions - active_positions)

    planned = list(input_signals)
    deferred_breakouts = []
    min_index_pct_from_ma = None
    state_ok = True
    if defer_breakout_max_min_index_pct_from_ma is not None:
        spy_pct = market_context.get("spy_pct_from_ma")
        qqq_pct = market_context.get("qqq_pct_from_ma")
        if spy_pct is not None and qqq_pct is not None:
            min_index_pct_from_ma = min(spy_pct, qqq_pct)
            state_ok = min_index_pct_from_ma <= defer_breakout_max_min_index_pct_from_ma
        else:
            state_ok = False

    if (
        defer_breakout_when_slots_lte is not None
        and slots <= defer_breakout_when_slots_lte
        and state_ok
    ):
        kept = []
        for sig in planned:
            if sig.get("strategy") == "breakout_long":
                deferred_breakouts.append({
                    "ticker": sig.get("ticker"),
                    "strategy": sig.get("strategy"),
                    "sector": sig.get("sector", "Unknown"),
                    "available_slots": slots,
                    "trade_quality_score": sig.get("trade_quality_score"),
                    "confidence_score": sig.get("confidence_score"),
                    "pct_from_52w_high": sig.get("pct_from_52w_high"),
                    "entry_price": sig.get("entry_price"),
                    "stop_price": sig.get("stop_price"),
                    "target_price": sig.get("target_price"),
                    "min_index_pct_from_ma": min_index_pct_from_ma,
                })
            else:
                kept.append(sig)
        planned = kept

    signals_after_deferral = len(planned)
    slot_sliced = planned[slots:] if slots >= 0 else planned
    planned = planned[:slots]

    return planned, {
        "active_positions": active_positions,
        "max_positions": max_positions,
        "available_slots": slots,
        "signals_before_entry_plan": len(input_signals),
        "signals_after_deferral": signals_after_deferral,
        "signals_after_entry_plan": len(planned),
        "deferred_breakout_signals": deferred_breakouts,
        "slot_sliced_signals": slot_sliced,
        "defer_breakout_when_slots_lte": defer_breakout_when_slots_lte,
        "defer_breakout_max_min_index_pct_from_ma": (
            defer_breakout_max_min_index_pct_from_ma
        ),
        "min_index_pct_from_ma": min_index_pct_from_ma,
    }


def classify_entry_open_cancel(
    fill_price,
    signal_entry,
    stop_price=None,
    upside_gap_cancel_pct=None,
    adverse_gap_cancel_pct=ADVERSE_GAP_CANCEL_PCT,
):
    """Return the shared next-open cancel reason, or None when entry may fill."""
    if fill_price is None or signal_entry is None:
        return None
    fill = float(fill_price)
    entry = float(signal_entry)
    if upside_gap_cancel_pct is not None and fill > entry * (1.0 + upside_gap_cancel_pct):
        return "gap_cancel"
    if adverse_gap_cancel_pct is not None and fill < entry * (1.0 - adverse_gap_cancel_pct):
        return "adverse_gap_down_cancel"
    if stop_price is not None and fill <= float(stop_price):
        return "stop_breach_cancel"
    return None


def _latest_close(df):
    if df is None or len(df) == 0 or "Close" not in df:
        return None
    value = df["Close"].iloc[-1]
    return float(value.item() if hasattr(value, "item") else value)


def _entry_index(df, entry_date):
    entry_ts = pd.Timestamp(entry_date)
    matching = df.index[df.index >= entry_ts]
    if len(matching) == 0:
        return None
    return df.index.get_loc(matching[0])


def _position_heat_stop(portfolio_heat, ticker):
    for item in (portfolio_heat or {}).get("position_breakdown", []) or []:
        if item.get("ticker") == ticker:
            return item.get("effective_stop")
    return None


def _cap_addon_shares(
    ticker,
    requested_shares,
    current_shares,
    price,
    portfolio_value,
    addon_position_cap,
    portfolio_heat=None,
):
    if requested_shares <= 0 or price <= 0 or not portfolio_value:
        return 0, {"requested_shares": requested_shares, "cap_reason": "invalid_input"}

    shares = int(requested_shares)
    position_cap_shares = math.floor(portfolio_value * addon_position_cap / price)
    position_cap_room = max(0, position_cap_shares - current_shares)
    shares = min(shares, position_cap_room)

    heat_room_shares = None
    effective_stop = _position_heat_stop(portfolio_heat, ticker)
    if portfolio_heat and effective_stop is not None:
        total_at_risk = portfolio_heat.get("total_at_risk_usd", 0) or 0
        max_heat = portfolio_heat.get("max_heat_pct", MAX_PORTFOLIO_HEAT)
        heat_room_usd = max(0.0, portfolio_value * max_heat - total_at_risk)
        risk_per_share = max(0.0, price - effective_stop)
        if risk_per_share > 0:
            heat_room_shares = math.floor(heat_room_usd / risk_per_share)
            shares = min(shares, heat_room_shares)

    return max(0, int(shares)), {
        "requested_shares": int(requested_shares),
        "position_cap_room_shares": int(position_cap_room),
        "heat_room_shares": heat_room_shares,
        "effective_stop": effective_stop,
    }


def build_followthrough_addon_actions(
    open_positions,
    ohlcv_dict,
    portfolio_value,
    current_prices,
    portfolio_heat=None,
    addon_enabled=ADDON_ENABLED,
):
    """Return eligible add-on actions plus rejected audit rows.

    The timing mirrors backtester.py: a position is evaluated on the exact
    checkpoint close, and the resulting action is intended for next-session open.
    """
    actions = []
    audit = []
    if not addon_enabled:
        return actions, audit

    spy_df = (ohlcv_dict or {}).get("SPY")
    if spy_df is None or len(spy_df) == 0:
        return actions, [{
            "ticker": "SPY",
            "status": "skipped",
            "reason": "missing_spy_ohlcv_for_relative_strength",
        }]

    for pos in _positive_positions(open_positions):
        ticker = str(pos.get("ticker", "")).upper()
        df = (ohlcv_dict or {}).get(ticker)
        if df is None or len(df) == 0:
            audit.append({"ticker": ticker, "status": "skipped", "reason": "missing_ohlcv"})
            continue

        entry_date = pos.get("entry_date")
        if not entry_date:
            audit.append({"ticker": ticker, "status": "skipped", "reason": "missing_entry_date"})
            continue

        entry_idx = _entry_index(df, entry_date)
        spy_entry_idx = _entry_index(spy_df, entry_date)
        if entry_idx is None or spy_entry_idx is None:
            audit.append({"ticker": ticker, "status": "skipped", "reason": "entry_date_not_in_ohlcv"})
            continue

        today_idx = len(df.index) - 1
        addon_count = int(pos.get("addon_count") or (1 if (pos.get("addon_shares") or 0) > 0 else 0))
        if addon_count >= (2 if SECOND_ADDON_ENABLED else 1):
            audit.append({"ticker": ticker, "status": "skipped", "reason": "addon_already_done"})
            continue

        if addon_count == 0:
            checkpoint_days = ADDON_CHECKPOINT_DAYS
            min_unrealized = ADDON_MIN_UNREALIZED_PCT
            min_rs = ADDON_MIN_RS_VS_SPY
            fraction = ADDON_FRACTION_OF_ORIGINAL_SHARES
            addon_position_cap = ADDON_MAX_POSITION_PCT
        else:
            checkpoint_days = SECOND_ADDON_CHECKPOINT_DAYS
            min_unrealized = SECOND_ADDON_MIN_UNREALIZED_PCT
            min_rs = SECOND_ADDON_MIN_RS_VS_SPY
            fraction = SECOND_ADDON_FRACTION_OF_ORIGINAL_SHARES
            addon_position_cap = SECOND_ADDON_MAX_POSITION_PCT

        days_since_entry = today_idx - entry_idx
        if days_since_entry != checkpoint_days:
            audit.append({
                "ticker": ticker,
                "status": "skipped",
                "reason": "not_checkpoint_day",
                "days_since_entry": int(days_since_entry),
                "checkpoint_days": checkpoint_days,
            })
            continue

        close = current_prices.get(ticker) or _latest_close(df)
        spy_close = _latest_close(spy_df)
        if not close or not spy_close:
            audit.append({"ticker": ticker, "status": "skipped", "reason": "missing_close"})
            continue

        entry_close = float(df["Close"].iloc[entry_idx])
        spy_entry_close = float(spy_df["Close"].iloc[spy_entry_idx])
        avg_cost = pos.get("avg_cost") or entry_close
        unrealized = (close - avg_cost) / avg_cost
        ticker_ret = (close - entry_close) / entry_close
        spy_ret = (spy_close - spy_entry_close) / spy_entry_close
        rs_vs_spy = ticker_ret - spy_ret

        if unrealized < min_unrealized or rs_vs_spy <= min_rs:
            audit.append({
                "ticker": ticker,
                "status": "rejected",
                "reason": "followthrough_threshold_not_met",
                "unrealized_pct": round(unrealized, 4),
                "rs_vs_spy": round(rs_vs_spy, 4),
                "min_unrealized_pct": min_unrealized,
                "min_rs_vs_spy": min_rs,
            })
            continue

        current_shares = int(pos.get("shares") or 0)
        original_shares = int(
            pos.get("original_shares")
            or max(1, current_shares - int(pos.get("addon_shares") or 0))
        )
        requested = math.floor(original_shares * fraction)
        shares, cap_detail = _cap_addon_shares(
            ticker,
            requested,
            current_shares,
            close,
            portfolio_value,
            addon_position_cap,
            portfolio_heat=portfolio_heat,
        )
        if shares <= 0:
            audit.append({
                "ticker": ticker,
                "status": "rejected",
                "reason": "addon_cap_no_room",
                **cap_detail,
            })
            continue

        action = {
            "ticker": ticker,
            "action": "ADD",
            "decision_mode": "code_followthrough_addon",
            "fill_timing": "next_session_open",
            "addon_number": addon_count + 1,
            "checkpoint_days": checkpoint_days,
            "days_since_entry": int(days_since_entry),
            "shares_to_buy": shares,
            "requested_shares": requested,
            "current_shares": current_shares,
            "original_shares": original_shares,
            "estimated_price": round(close, 2),
            "estimated_position_value_usd": round(shares * close, 2),
            "unrealized_pct": round(unrealized, 4),
            "rs_vs_spy": round(rs_vs_spy, 4),
            "min_unrealized_pct": min_unrealized,
            "min_rs_vs_spy": min_rs,
            "addon_fraction_of_original_shares": fraction,
            "addon_position_cap_pct": addon_position_cap,
            "cap_detail": cap_detail,
            "reason": (
                f"day-{checkpoint_days} follow-through: "
                f"unrealized {unrealized:.1%}, RS vs SPY {rs_vs_spy:.1%}"
            ),
        }
        actions.append(action)
        audit.append({"ticker": ticker, "status": "eligible", **action})

    return actions, audit
