"""
Position sizing and exit rule computation for the trading system.

Exit Rule Hierarchy (apply in priority order, no exceptions):
1. HARD STOP     -12% from avg_cost        → CRITICAL: exit immediately
2. ATR STOP      entry - 2×ATR(14)         → HIGH: volatility-adjusted floor
3. TRAILING STOP -8% from position high    → HIGH: protect gains
4. PROFIT TARGET +20% from entry           → MEDIUM: exit or partial reduce
5. TIME STOP     20 trading days stagnant  → REVIEW: exit unless new catalyst
"""

import logging
import pandas as pd

logger = logging.getLogger(__name__)

# Rule parameters
RISK_PER_TRADE_PCT    = 0.01   # Risk 1% of total portfolio per new trade
HARD_STOP_PCT         = 0.12   # -12% hard stop from avg_cost
PROFIT_TARGET_PCT     = 0.20   # +20% profit target from entry
TRAILING_STOP_PCT     = 0.08   # -8% trailing stop from position high-water mark
TIME_STOP_DAYS        = 20     # Exit review after 20 trading days
ATR_MULTIPLIER        = 2.0    # Stop = entry - 2 × ATR
ATR_PERIOD            = 14     # Standard ATR lookback
MAX_PORTFOLIO_HEAT    = 0.10   # Max 10% of portfolio at risk simultaneously


def compute_atr(data, period=ATR_PERIOD):
    """
    Compute Average True Range (ATR) using exponential smoothing.

    True Range = max(High - Low, |High - PrevClose|, |Low - PrevClose|)

    Args:
        data (pd.DataFrame): OHLCV data with High, Low, Close columns
        period (int): ATR period (default: 14)

    Returns:
        float: Latest ATR value, or None if insufficient data
    """
    try:
        if len(data) < period + 1:
            return None

        high  = data['High']
        low   = data['Low']
        close = data['Close']

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low  - close.shift(1)).abs()

        true_range  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_series  = true_range.ewm(span=period, adjust=False).mean()

        atr_val = atr_series.iloc[-1]
        result  = float(atr_val.item() if hasattr(atr_val, 'item') else atr_val)
        return round(result, 4)

    except Exception as e:
        logger.error(f"Failed to compute ATR: {e}")
        return None


def compute_position_size(portfolio_value, entry_price, stop_price,
                          risk_pct=RISK_PER_TRADE_PCT):
    """
    Compute position size using fixed-fraction risk model.

    Formula:
        risk_amount    = portfolio_value × risk_pct
        risk_per_share = entry_price - stop_price
        shares         = floor(risk_amount / risk_per_share)

    Args:
        portfolio_value (float): Total portfolio value in USD
        entry_price (float): Expected entry price
        stop_price (float): Stop-loss price (must be below entry)
        risk_pct (float): Fraction of portfolio to risk per trade (default: 1%)

    Returns:
        dict: Position sizing details, or None on error
    """
    try:
        if entry_price <= 0 or stop_price <= 0:
            logger.warning("Invalid entry or stop price")
            return None
        if stop_price >= entry_price:
            logger.warning("Stop price must be below entry price for long trades")
            return None

        risk_amount    = portfolio_value * risk_pct
        risk_per_share = entry_price - stop_price
        shares         = max(1, int(risk_amount / risk_per_share))  # round down, min 1
        position_value = shares * entry_price

        return {
            "portfolio_value_usd":        round(portfolio_value, 2),
            "risk_pct":                   risk_pct,
            "risk_amount_usd":            round(risk_amount, 2),
            "entry_price":                round(entry_price, 2),
            "stop_price":                 round(stop_price, 2),
            "risk_per_share":             round(risk_per_share, 2),
            "shares_to_buy":              shares,
            "position_value_usd":         round(position_value, 2),
            "position_pct_of_portfolio":  round(position_value / portfolio_value, 4),
        }

    except Exception as e:
        logger.error(f"Failed to compute position size: {e}")
        return None


def compute_exit_levels(avg_cost, atr=None, override_stop_price=None, current_price=None):
    """
    Compute all exit price levels for a held position.

    Args:
        avg_cost (float): Average cost / entry price
        atr (float): Optional ATR value for volatility-adjusted stop
        override_stop_price (float): Hard stop override (used for legacy positions).
            For auto_rolling stops this equals current_price × 0.88.
        current_price (float): Current market price — used as ATR reference for
            legacy positions so that atr_stop = current_price - 2×ATR instead of
            the meaningless avg_cost - 2×ATR (e.g. AMD: $27 - $21 = $6).

    Returns:
        dict: Exit levels with prices and percentages
    """
    if override_stop_price:
        hard_stop     = round(override_stop_price, 2)
        hard_stop_pct = round((hard_stop - avg_cost) / avg_cost, 4)
    else:
        hard_stop     = round(avg_cost * (1 - HARD_STOP_PCT), 2)
        hard_stop_pct = -HARD_STOP_PCT

    profit_target = round(avg_cost * (1 + PROFIT_TARGET_PCT), 2)

    levels = {
        "hard_stop_price":     hard_stop,
        "hard_stop_pct":       hard_stop_pct,
        "profit_target_price": profit_target,
        "profit_target_pct":   PROFIT_TARGET_PCT,
        "trailing_stop_pct":   TRAILING_STOP_PCT,
        "time_stop_days":      TIME_STOP_DAYS,
    }
    if override_stop_price:
        levels["override_stop_active"] = True

    if atr is not None:
        # For legacy positions (override active), base ATR stop on current_price.
        # For normal positions, base on avg_cost (the actual entry price).
        atr_ref  = current_price if (override_stop_price and current_price) else avg_cost
        atr_stop = round(atr_ref - ATR_MULTIPLIER * atr, 2)
        levels["atr_stop_price"] = atr_stop
        levels["atr_stop_pct"]   = round((atr_stop - avg_cost) / avg_cost, 4)

    return levels


def evaluate_exit_signals(current_price, avg_cost, exit_levels,
                           high_water_mark=None):
    """
    Evaluate which exit conditions are currently triggered.

    Args:
        current_price (float): Latest market price
        avg_cost (float): Entry / average cost price
        exit_levels (dict): Output of compute_exit_levels()
        high_water_mark (float): Highest close since entry (for trailing stop)

    Returns:
        dict: {
            "any_triggered": bool,
            "critical_exit": bool,
            "high_urgency":  bool,
            "triggered_rules": list[dict]
        }
    """
    triggered = []

    # 1. Hard stop — CRITICAL
    hard_stop = exit_levels.get("hard_stop_price", 0)
    if current_price <= hard_stop:
        triggered.append({
            "rule":    "HARD_STOP",
            "urgency": "CRITICAL",
            "message": f"Price {current_price:.2f} <= hard stop {hard_stop:.2f}",
        })

    # 2. ATR stop — HIGH
    if ("atr_stop_price" in exit_levels
            and current_price <= exit_levels["atr_stop_price"]):
        triggered.append({
            "rule":    "ATR_STOP",
            "urgency": "HIGH",
            "message": (f"Price {current_price:.2f} <= ATR stop "
                        f"{exit_levels['atr_stop_price']:.2f}"),
        })

    # 3. Trailing stop — HIGH (only once price has risen above entry)
    if high_water_mark and high_water_mark > avg_cost:
        trailing_price = round(high_water_mark * (1 - TRAILING_STOP_PCT), 2)
        if current_price <= trailing_price:
            triggered.append({
                "rule":    "TRAILING_STOP",
                "urgency": "HIGH",
                "message": (f"Price {current_price:.2f} <= trailing stop "
                            f"{trailing_price:.2f} "
                            f"({TRAILING_STOP_PCT*100:.0f}% from high "
                            f"{high_water_mark:.2f})"),
            })

    # 4. Profit target — MEDIUM
    profit_target = exit_levels.get("profit_target_price", float('inf'))
    if current_price >= profit_target:
        triggered.append({
            "rule":    "PROFIT_TARGET",
            "urgency": "MEDIUM",
            "message": (f"Price {current_price:.2f} >= profit target "
                        f"{profit_target:.2f}"),
        })

    # 5. Approaching hard stop — WARNING (within 3% above stop)
    if hard_stop > 0 and current_price > hard_stop:
        distance_pct = (current_price - hard_stop) / current_price
        if distance_pct < 0.03 and "HARD_STOP" not in [t["rule"] for t in triggered]:
            triggered.append({
                "rule":    "APPROACHING_HARD_STOP",
                "urgency": "WARNING",
                "message": (f"Only {distance_pct*100:.1f}% above hard stop "
                            f"{hard_stop:.2f} — monitor closely"),
            })

    return {
        "any_triggered":   len(triggered) > 0,
        "critical_exit":   any(t["urgency"] == "CRITICAL" for t in triggered),
        "high_urgency":    any(t["urgency"] in ("CRITICAL", "HIGH") for t in triggered),
        "triggered_rules": triggered,
    }


def compute_portfolio_heat(open_positions, current_prices, portfolio_value):
    """
    Calculate total portfolio risk exposure (portfolio heat).

    For each position:
        at_risk_usd = shares × max(0, current_price - hard_stop_price)

    Portfolio heat = Σ(at_risk_usd) / portfolio_value

    If heat >= MAX_PORTFOLIO_HEAT (10%), no new positions should be added.

    Args:
        open_positions (dict): Open positions data (from open_positions.json)
        current_prices (dict): {ticker: current_close_price}
        portfolio_value (float): Total portfolio value in USD

    Returns:
        dict: Heat metrics including per-position breakdown and overall verdict
    """
    if not open_positions or not portfolio_value or portfolio_value <= 0:
        return None

    position_breakdown = []
    total_at_risk_usd  = 0.0

    for pos in open_positions.get("positions", []):
        ticker   = pos.get("ticker")
        shares   = pos.get("shares", 0)
        avg_cost = pos.get("avg_cost", 0)

        if not ticker or avg_cost <= 0 or shares <= 0:
            continue

        # Use live price if available, fall back to avg_cost
        current_price = current_prices.get(ticker, avg_cost)

        # Use same stop logic as compute_exit_levels / trend_signals:
        #   legacy positions (PnL > 100%): rolling stop = current_price × 0.88
        #   manual override takes precedence if set in open_positions.json
        #   normal positions: avg_cost × 0.88
        manual_override    = pos.get("override_stop_price")
        unrealized_pnl_pct = (current_price - avg_cost) / avg_cost if avg_cost > 0 else 0
        legacy             = unrealized_pnl_pct > 1.0

        if manual_override:
            hard_stop = manual_override
            stop_src  = "manual"
        elif legacy:
            hard_stop = current_price * (1 - HARD_STOP_PCT)
            stop_src  = "auto_rolling"
        else:
            hard_stop = avg_cost * (1 - HARD_STOP_PCT)
            stop_src  = "default"

        # Amount lost if price drops to hard stop from current price
        at_risk_per_share = max(0.0, current_price - hard_stop)
        at_risk_usd       = shares * at_risk_per_share
        at_risk_pct       = at_risk_usd / portfolio_value

        total_at_risk_usd += at_risk_usd

        position_breakdown.append({
            "ticker":         ticker,
            "shares":         shares,
            "current_price":  round(current_price, 2),
            "hard_stop_price":round(hard_stop, 2),
            "stop_source":    stop_src,
            "at_risk_usd":    round(at_risk_usd, 2),
            "at_risk_pct":    round(at_risk_pct, 4),
        })

    heat_pct           = total_at_risk_usd / portfolio_value
    can_add_positions  = heat_pct < MAX_PORTFOLIO_HEAT

    if can_add_positions:
        heat_note = (f"Heat {heat_pct*100:.1f}% < {MAX_PORTFOLIO_HEAT*100:.0f}% cap — "
                     f"new positions permitted")
    else:
        heat_note = (f"Heat {heat_pct*100:.1f}% >= {MAX_PORTFOLIO_HEAT*100:.0f}% cap — "
                     f"NO new positions until existing risk is reduced")

    return {
        "portfolio_value_usd":   portfolio_value,
        "total_at_risk_usd":     round(total_at_risk_usd, 2),
        "portfolio_heat_pct":    round(heat_pct, 4),
        "max_heat_pct":          MAX_PORTFOLIO_HEAT,
        "can_add_new_positions": can_add_positions,
        "heat_note":             heat_note,
        "position_breakdown":    position_breakdown,
    }
