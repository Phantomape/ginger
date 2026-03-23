"""
Position sizing and exit rule computation for the trading system.

Exit Rule Hierarchy (apply in priority order, no exceptions):
1. HARD STOP     -12% from avg_cost        → CRITICAL: exit immediately
2. ATR STOP      entry - 1.5×ATR(14)       → HIGH: volatility-adjusted floor
3. TRAILING STOP -8% from position high    → HIGH: protect gains
4. PROFIT TARGET +20% from entry           → MEDIUM: exit or partial reduce
5. TIME STOP     45 trading days stagnant  → REVIEW: exit unless new catalyst
"""

import logging
import pandas as pd

logger = logging.getLogger(__name__)

# Rule parameters
RISK_PER_TRADE_PCT    = 0.01     # Risk 1% of total portfolio per new trade
MAX_POSITION_PCT      = 0.20     # Single position capped at 20% of portfolio
ROUND_TRIP_COST_PCT   = 0.0035   # matches risk_engine.py and performance_engine.py
EXEC_LAG_PCT          = 0.005    # +0.5% assumed next-day open gap (matches risk_engine.py)
HARD_STOP_PCT         = 0.12   # -12% hard stop from avg_cost
PROFIT_TARGET_PCT     = 0.20   # +20% profit target from entry
TRAILING_STOP_PCT     = 0.08   # -8% trailing stop from position high-water mark
TIME_STOP_DAYS        = 45     # Exit review after 45 trading days (~9 weeks; trend strategies need time
ATR_MULTIPLIER        = 1.5    # Stop = entry - 1.5 × ATR (matches signal_engine.py)
ATR_PERIOD            = 14     # Standard ATR lookback
MAX_PORTFOLIO_HEAT    = 0.08   # Max 8% of portfolio at risk simultaneously (per inst_5.txt)


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
        # Wilder's smoothing: alpha = 1/period (≈0.071 for period=14).
        # More stable than EWM(span=period) (alpha=2/15≈0.133); reduces ATR
        # spikes on single high-volatility days. Matches feature_layer.py.
        atr_series  = true_range.ewm(alpha=1.0 / period, adjust=False).mean()

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
        # Include execution cost AND exec_lag gap so the position is sized for TRUE 1% risk.
        # Mirrors portfolio_engine.py — see detailed comment there for the arithmetic.
        cost_per_share     = entry_price * ROUND_TRIP_COST_PCT
        gap_per_share      = entry_price * EXEC_LAG_PCT
        net_risk_per_share = risk_per_share + cost_per_share + gap_per_share
        shares             = max(1, int(risk_amount / net_risk_per_share))  # round down, min 1

        # Cap at MAX_POSITION_PCT — tight stops can produce oversized positions.
        max_shares = max(1, int(portfolio_value * MAX_POSITION_PCT / entry_price))
        if shares > max_shares:
            logger.warning(
                f"Position capped: {shares} → {max_shares} shares "
                f"({MAX_POSITION_PCT*100:.0f}% portfolio cap, tight stop)"
            )
            shares = max_shares

        position_value = shares * entry_price

        return {
            "portfolio_value_usd":        round(portfolio_value, 2),
            "risk_pct":                   risk_pct,
            "risk_amount_usd":            round(risk_amount, 2),
            "entry_price":                round(entry_price, 2),
            "stop_price":                 round(stop_price, 2),
            "risk_per_share":             round(risk_per_share, 2),
            "net_risk_per_share":         round(net_risk_per_share, 4),
            "shares_to_buy":              shares,
            "position_value_usd":         round(position_value, 2),
            "position_pct_of_portfolio":  round(position_value / portfolio_value, 4),
        }

    except Exception as e:
        logger.error(f"Failed to compute position size: {e}")
        return None


def compute_exit_levels(avg_cost, atr=None, override_stop_price=None, current_price=None,
                        signal_target_price=None):
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
        signal_target_price (float): Optional 3.5×ATR target from the original entry
            signal (stored in open_positions.json as "target_price").  When provided,
            enables the SIGNAL_TARGET exit rule: when price reaches this level the
            original R:R is captured — suggest reducing 33% to lock in gains while
            letting the remaining 67% ride toward the +20% PROFIT_TARGET.
            Without this field the +7% to +20% range has no exit instruction, causing
            winners to evaporate before PROFIT_TARGET fires.

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

    # Signal target: 3.5×ATR technical target from the original entry signal.
    # Stored as "target_price" in open_positions.json by the user when opening a trade.
    # This closes the +7% to +20% dead zone where previously no exit instruction existed.
    if signal_target_price is not None and signal_target_price > avg_cost:
        levels["signal_target_price"] = round(signal_target_price, 2)
        levels["signal_target_pct"]   = round((signal_target_price - avg_cost) / avg_cost, 4)

    if atr is not None:
        # Always base ATR stop on current_price when available — this makes the stop
        # meaningful for winning positions (e.g. NVDA at $183: atr_stop=$174, not $93).
        # Using avg_cost for a position with 80% unrealised gain produces a stop so
        # far below market price that it never triggers, providing zero protection.
        # Falls back to avg_cost only when current_price is not supplied (e.g. unit tests).
        atr_ref  = current_price if current_price else avg_cost
        atr_stop = round(atr_ref - ATR_MULTIPLIER * atr, 2)
        levels["atr_stop_price"] = atr_stop
        levels["atr_stop_pct"]   = round((atr_stop - avg_cost) / avg_cost, 4)

    return levels


def evaluate_exit_signals(current_price, avg_cost, exit_levels,
                           high_water_mark=None, legacy_basis=False,
                           days_held=None):
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

    # 3.5. Signal target: 3.5×ATR technical R:R captured — partial profit lock.
    # Fires when price ≥ signal_target_price (stored in open_positions.json).
    # Urgency LOW: suggests 33% reduction to lock the planned R:R while allowing
    # the remaining 67% to run toward the PROFIT_TARGET (+20%).
    # Only fires in the pre-PROFIT_TARGET range; once PROFIT_TARGET fires (20%+)
    # the higher-urgency rule takes over and this check becomes redundant.
    # Skipped for legacy_basis positions — their economics are completely different.
    if (not legacy_basis
            and "signal_target_price" in exit_levels
            and avg_cost > 0):
        sig_target = exit_levels["signal_target_price"]
        profit_tgt = exit_levels.get("profit_target_price", float("inf"))
        # Only fire before the +20% PROFIT_TARGET zone to avoid conflicting messages
        if sig_target <= current_price < profit_tgt:
            triggered.append({
                "rule":    "SIGNAL_TARGET",
                "urgency": "LOW",
                "message": (f"Price {current_price:.2f} >= signal target "
                            f"{sig_target:.2f} (+{exit_levels['signal_target_pct']*100:.1f}%) — "
                            f"3.5×ATR R:R captured; consider reducing 33% to lock gains, "
                            f"let remainder run to +20% target {profit_tgt:.2f}"),
            })

    # 4+6. Profit-taking rules — non-overlapping ladder:
    #   20–30% gain  → PROFIT_TARGET (MEDIUM)  → REDUCE 50%
    #   30–50% gain  → PROFIT_LADDER_30 (LOW)  → HOLD remaining position
    #   50%+  gain   → PROFIT_LADDER_50 (MEDIUM)→ REDUCE 25%
    #
    # PROFIT_LADDER rules are only checked when a LADDER threshold is reached.
    # When a LADDER rule fires, PROFIT_TARGET is suppressed to avoid sending
    # conflicting "REDUCE 50%" vs "HOLD" signals to the LLM.
    ladder_fired = False
    if not legacy_basis and avg_cost > 0:
        pnl_pct = (current_price - avg_cost) / avg_cost
        if pnl_pct >= 0.50:
            triggered.append({
                "rule":    "PROFIT_LADDER_50",
                "urgency": "MEDIUM",
                "message": (f"Unrealised gain {pnl_pct*100:.1f}% — "
                            f"consider reducing 25% to lock in profits"),
            })
            ladder_fired = True
        elif pnl_pct >= 0.30:
            triggered.append({
                "rule":    "PROFIT_LADDER_30",
                "urgency": "LOW",
                "message": (f"Unrealised gain {pnl_pct*100:.1f}% — "
                            f"let winner run; re-evaluate at 50%"),
            })
            ladder_fired = True

    # PROFIT_TARGET: only fire in the 20–30% range (before PROFIT_LADDER takes over).
    # If a LADDER rule already fired (≥30% gain) suppress this to avoid contradiction.
    # Also skip for legacy positions (pnl > 100%) — PROFIT_TARGET is meaningless
    # when avg_cost is far below current price (e.g. AMD avg_cost $27, target $32).
    # The 1.30× upper bound below provides implicit protection, but the explicit
    # legacy_basis check is clearer and consistent with the PROFIT_LADDER guard above.
    if not ladder_fired and not legacy_basis:
        profit_target = exit_levels.get("profit_target_price", float('inf'))
        if current_price >= profit_target and current_price < profit_target * 1.30:
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

    # 7. Time stop — REVIEW (stagnant position: held too long with insufficient progress).
    # Only fires if price is below halfway between avg_cost and profit_target.
    # Positions that have passed the halfway mark are "working" and get more time —
    # a trade at +15% heading toward a +20% target is NOT stagnant, don't interrupt it.
    if days_held is not None and days_held >= TIME_STOP_DAYS:
        profit_target = exit_levels.get("profit_target_price", float("inf"))
        halfway = (avg_cost + profit_target) / 2 if avg_cost > 0 else 0
        if current_price < halfway:
            triggered.append({
                "rule":    "TIME_STOP",
                "urgency": "REVIEW",
                "message": (f"Position held ~{days_held} trading days "
                            f"with insufficient progress — below halfway to target "
                            f"{profit_target:.2f} (halfway={halfway:.2f}) — "
                            f"exit unless new catalyst"),
            })

    return {
        "any_triggered":   len(triggered) > 0,
        "critical_exit":   any(t["urgency"] == "CRITICAL" for t in triggered),
        "high_urgency":    any(t["urgency"] in ("CRITICAL", "HIGH") for t in triggered),
        "triggered_rules": triggered,
    }


