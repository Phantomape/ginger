"""
Portfolio Engine: Convert signals into position sizes and enforce risk limits.

Rules per inst_5.txt:
  risk_per_trade ≤ 1% of portfolio
  position_size  = risk_amount / (entry_price − stop_price)
  portfolio_heat ≤ 8%  (total at-risk / portfolio_value)
"""

import math
import logging

logger = logging.getLogger(__name__)

RISK_PER_TRADE_PCT = 0.01   # 1% portfolio risk per new trade
MAX_PORTFOLIO_HEAT = 0.08   # 8% total heat cap (per inst_5.txt)
HARD_STOP_PCT      = 0.12   # −12% from entry for heat calculation


def compute_position_size(portfolio_value, entry_price, stop_price,
                           risk_pct=RISK_PER_TRADE_PCT):
    """
    Compute shares to buy using the 1% fixed-fraction risk rule.

    Formula:
        risk_amount    = portfolio_value × risk_pct
        risk_per_share = entry_price − stop_price
        shares         = floor(risk_amount / risk_per_share)   (min 1)

    Returns:
        dict or None
    """
    if portfolio_value <= 0 or entry_price <= 0 or stop_price <= 0:
        return None
    if stop_price >= entry_price:
        logger.warning("stop_price >= entry_price; position size skipped")
        return None

    risk_amount    = portfolio_value * risk_pct
    risk_per_share = entry_price - stop_price
    shares         = max(1, math.floor(risk_amount / risk_per_share))
    position_value = shares * entry_price

    return {
        "portfolio_value_usd":       round(portfolio_value, 2),
        "risk_pct":                  risk_pct,
        "risk_amount_usd":           round(risk_amount, 2),
        "entry_price":               round(entry_price, 2),
        "stop_price":                round(stop_price, 2),
        "risk_per_share":            round(risk_per_share, 2),
        "shares_to_buy":             shares,
        "position_value_usd":        round(position_value, 2),
        "position_pct_of_portfolio": round(position_value / portfolio_value, 4),
    }


def compute_portfolio_heat(open_positions, current_prices, portfolio_value):
    """
    Compute total portfolio risk exposure (portfolio heat).

    For each position:
        at_risk_usd = shares × max(0, current_price − hard_stop_price)

    Stop logic (mirrors news_collector/position_manager.py):
        manual override > auto_rolling (legacy PnL > 100%) > default (avg_cost × 0.88)

    Heat cap: 8%.

    Returns:
        dict or None
    """
    if not open_positions or portfolio_value <= 0:
        return None

    breakdown     = []
    total_at_risk = 0.0

    for pos in open_positions.get("positions", []):
        ticker   = pos.get("ticker")
        shares   = pos.get("shares", 0)
        avg_cost = pos.get("avg_cost", 0)

        if not ticker or avg_cost <= 0 or shares <= 0:
            continue

        current_price      = current_prices.get(ticker, avg_cost)
        unrealized_pnl_pct = (current_price - avg_cost) / avg_cost
        legacy             = unrealized_pnl_pct > 1.0

        manual_override = pos.get("override_stop_price")
        if manual_override:
            hard_stop = manual_override
            stop_src  = "manual"
        elif legacy:
            hard_stop = current_price * (1 - HARD_STOP_PCT)
            stop_src  = "auto_rolling"
        else:
            hard_stop = avg_cost * (1 - HARD_STOP_PCT)
            stop_src  = "default"

        at_risk_usd    = shares * max(0.0, current_price - hard_stop)
        total_at_risk += at_risk_usd

        breakdown.append({
            "ticker":         ticker,
            "shares":         shares,
            "current_price":  round(current_price, 2),
            "hard_stop":      round(hard_stop, 2),
            "stop_source":    stop_src,
            "at_risk_usd":    round(at_risk_usd, 2),
            "at_risk_pct":    round(at_risk_usd / portfolio_value, 4),
        })

    heat_pct = total_at_risk / portfolio_value
    can_add  = heat_pct < MAX_PORTFOLIO_HEAT

    return {
        "portfolio_value_usd":   portfolio_value,
        "total_at_risk_usd":     round(total_at_risk, 2),
        "portfolio_heat_pct":    round(heat_pct, 4),
        "max_heat_pct":          MAX_PORTFOLIO_HEAT,
        "can_add_new_positions": can_add,
        "heat_note": (
            f"Heat {heat_pct*100:.1f}% {'<' if can_add else '>='} "
            f"{MAX_PORTFOLIO_HEAT*100:.0f}% cap — "
            f"{'new positions permitted' if can_add else 'NO new positions — reduce existing risk first'}"
        ),
        "position_breakdown": breakdown,
    }


def size_signals(signals, portfolio_value):
    """
    Add position_size dict to each signal.

    Args:
        signals         (list[dict]): Enriched signals with stop_price
        portfolio_value (float):      Total portfolio value

    Returns:
        list[dict]: Signals with 'sizing' field added
    """
    sized = []
    for sig in signals:
        entry = sig.get("entry_price")
        stop  = sig.get("stop_price")
        if entry and stop and portfolio_value:
            sizing = compute_position_size(portfolio_value, entry, stop)
            if sizing:
                sig = {**sig, "sizing": sizing}
        sized.append(sig)
    return sized
