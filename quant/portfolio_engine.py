"""
Portfolio Engine: Convert signals into position sizes and enforce risk limits.

Rules per inst_5.txt:
  risk_per_trade ≤ 1% of portfolio
  position_size  = risk_amount / (entry_price − stop_price)
  portfolio_heat ≤ 8%  (total at-risk / portfolio_value)
"""

import math
import logging

from constants import (
    RISK_PER_TRADE_PCT,
    MAX_PORTFOLIO_HEAT,
    MAX_POSITION_PCT,
    LOW_TQS_RISK_THRESHOLD,
    LOW_TQS_RISK_MULTIPLIER,
    LOW_TQS_HAIRCUT_EXEMPT_SECTORS,
    LOW_TQS_BREAKOUT_NON_EXEMPT_RISK_MULTIPLIER,
    TREND_INDUSTRIALS_RISK_MULTIPLIER,
    TREND_FINANCIALS_RISK_MULTIPLIER,
    TREND_TECH_GAP_VULN_MIN,
    TREND_TECH_GAP_VULN_MAX,
    TREND_TECH_GAP_RISK_MULTIPLIER,
    TREND_TECH_TIGHT_GAP_VULN_MIN,
    TREND_TECH_TIGHT_GAP_VULN_MAX,
    TREND_TECH_TIGHT_GAP_RISK_MULTIPLIER,
    TREND_TECH_NEAR_HIGH_MAX_PULLBACK,
    TREND_TECH_NEAR_HIGH_RISK_MULTIPLIER,
    BREAKOUT_INDUSTRIALS_GAP_VULN_MIN,
    BREAKOUT_INDUSTRIALS_GAP_VULN_MAX,
    BREAKOUT_INDUSTRIALS_GAP_RISK_MULTIPLIER,
    BREAKOUT_COMMS_NEAR_HIGH_MAX_PULLBACK,
    BREAKOUT_COMMS_NEAR_HIGH_RISK_MULTIPLIER,
    BREAKOUT_COMMS_GAP_VULN_MIN,
    BREAKOUT_COMMS_GAP_VULN_MAX,
    BREAKOUT_COMMS_GAP_RISK_MULTIPLIER,
    BREAKOUT_FINANCIALS_DTE_MIN,
    BREAKOUT_FINANCIALS_DTE_MAX,
    BREAKOUT_FINANCIALS_DTE_RISK_MULTIPLIER,
    BREAKOUT_TECH_DTE_MIN,
    BREAKOUT_TECH_DTE_MAX,
    BREAKOUT_TECH_DTE_RISK_MULTIPLIER,
    BREAKOUT_HEALTHCARE_DTE_MIN,
    BREAKOUT_HEALTHCARE_DTE_MAX,
    BREAKOUT_HEALTHCARE_DTE_RISK_MULTIPLIER,
    TREND_TECH_DTE_MIN,
    TREND_TECH_DTE_MAX,
    TREND_TECH_DTE_RISK_MULTIPLIER,
    TREND_HEALTHCARE_DTE_MIN,
    TREND_HEALTHCARE_DTE_MAX,
    TREND_HEALTHCARE_DTE_RISK_MULTIPLIER,
    TREND_CONSUMER_NEAR_HIGH_DTE_MIN,
    TREND_CONSUMER_NEAR_HIGH_DTE_MAX,
    TREND_CONSUMER_NEAR_HIGH_MAX_PULLBACK,
    TREND_CONSUMER_NEAR_HIGH_DTE_RISK_MULTIPLIER,
    TREND_COMMODITIES_NEAR_HIGH_MAX_PULLBACK,
    TREND_COMMODITIES_NEAR_HIGH_RISK_MULTIPLIER,
    RISK_ON_UNMODIFIED_RISK_MULTIPLIER,
    HARD_STOP_PCT,
    TRAILING_STOP_PCT,
    ATR_STOP_MULT,
    ROUND_TRIP_COST_PCT,
    EXEC_LAG_PCT,
)

logger = logging.getLogger(__name__)

# Earnings gap risk override for Strategy C (earnings_event_long).
# Overnight earnings gaps (±8-15%) bypass ATR stops entirely because they are
# discontinuous events — the market opens at the gap price, never trading through
# the stop.  Sizing based on the ATR stop (typically 2-3% of entry) produces
# positions 3-5× too large: a planned 1% risk becomes 3-5% actual risk.
# Using 8% as the effective risk distance brings actual earnings-gap exposure
# in line with the 1% portfolio risk target.
# The ATR stop is still displayed to the user for order-placement reference;
# only the SIZING uses this gap-risk floor.
EARNINGS_GAP_RISK_PCT   = 0.08     # 8% conservative floor for earnings-gap adverse scenario


def compute_position_size(portfolio_value, entry_price, stop_price,
                           risk_pct=RISK_PER_TRADE_PCT):
    """
    Compute shares to buy using the 1% fixed-fraction risk rule.

    Formula:
        risk_amount    = portfolio_value × risk_pct
        risk_per_share = entry_price − stop_price
        shares         = floor(risk_amount / risk_per_share)   (min 1)

    Position is further capped at MAX_POSITION_PCT of portfolio to prevent
    oversized positions when stop is very tight (e.g. Strategy B breakout_stop).

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
    # Include both execution cost AND exec_lag (next-day open gap) so the position
    # is sized for TRUE 1% risk.
    #
    # Previous formula:  net_risk = (entry - stop) + entry × 0.0035
    # Actual risk:       net_risk = (open  - stop) + open  × 0.0035
    #                             = (entry + gap - stop) + (entry + gap) × 0.0035
    #
    # For a $100 stock, 3% ATR, 0.5% gap:
    #   Old:  net_risk = $4.50 + $0.35 = $4.85  (1.00% of portfolio)
    #   True: net_risk = $4.50 + $0.50 + $0.35 = $5.35  (1.10% of portfolio)
    # Across 8 simultaneous positions the silent 10% overrun → 8.8% heat vs 8% cap.
    # Including EXEC_LAG_PCT brings actual risk in line with the 1% target.
    cost_per_share     = entry_price * ROUND_TRIP_COST_PCT
    gap_per_share      = entry_price * EXEC_LAG_PCT
    net_risk_per_share = risk_per_share + cost_per_share + gap_per_share
    shares             = max(1, math.floor(risk_amount / net_risk_per_share))

    # Cap at MAX_POSITION_PCT — tight stops (e.g. breakout_stop 1% below entry)
    # can produce shares that represent 50-100% of portfolio; enforce hard limit.
    max_shares     = max(1, math.floor(portfolio_value * MAX_POSITION_PCT / entry_price))
    if shares > max_shares:
        logger.warning(
            f"Position capped: {shares} → {max_shares} shares "
            f"({MAX_POSITION_PCT*100:.0f}% portfolio cap, tight stop)"
        )
        shares = max_shares

    position_value = shares * entry_price

    return {
        "portfolio_value_usd":       round(portfolio_value, 2),
        "risk_pct":                  risk_pct,
        "risk_amount_usd":           round(risk_amount, 2),
        "entry_price":               round(entry_price, 2),
        "stop_price":                round(stop_price, 2),
        "risk_per_share":            round(risk_per_share, 2),
        "net_risk_per_share":        round(net_risk_per_share, 4),
        "shares_to_buy":             shares,
        "position_value_usd":        round(position_value, 2),
        "position_pct_of_portfolio": round(position_value / portfolio_value, 4),
    }


def compute_portfolio_heat(open_positions, current_prices, portfolio_value,
                           features_dict=None):
    """
    Compute total portfolio risk exposure (portfolio heat).

    For each position:
        at_risk_usd = shares × max(0, current_price − effective_stop)

    effective_stop = highest of: hard_stop, atr_stop, trailing_stop_from_20d_high.
    Using the tightest (highest) stop reflects true current risk, not worst-case
    cost-basis math. This prevents positions with large unrealised gains from
    inflating heat far beyond their real downside exposure.

    Stop logic for hard_stop baseline:
        manual override > auto_rolling (legacy PnL > 100%) > default (avg_cost × 0.88)

    Heat cap: 8%.

    Args:
        open_positions (dict): Open positions data
        current_prices (dict): {ticker: current_close_price}
        portfolio_value (float): Total portfolio value in USD
        features_dict (dict): Optional {ticker: features} for ATR/high_20d lookups

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

        # Tighten to ATR stop or trailing stop if features are available.
        # effective_stop = max(hard_stop, atr_stop, trailing_stop)
        # A higher stop means less at-risk USD — more accurate for big winners.
        effective_stop = hard_stop
        effective_src  = stop_src
        f = (features_dict or {}).get(ticker)
        if f:
            atr     = f.get("atr")
            high_20d = f.get("high_20d")
            if atr and atr > 0:
                atr_stop = current_price - ATR_STOP_MULT * atr
                if atr_stop > effective_stop:
                    effective_stop = round(atr_stop, 2)
                    effective_src  = "atr"
            if high_20d and high_20d > 0:
                trailing_stop = high_20d * (1 - TRAILING_STOP_PCT)
                if trailing_stop > effective_stop:
                    effective_stop = round(trailing_stop, 2)
                    effective_src  = "trailing"

        at_risk_usd    = shares * max(0.0, current_price - effective_stop)
        total_at_risk += at_risk_usd

        breakdown.append({
            "ticker":                ticker,
            "shares":                shares,
            "current_price":         round(current_price, 2),
            "hard_stop":             round(hard_stop, 2),
            "effective_stop":        round(effective_stop, 2),
            "effective_stop_source": effective_src,
            "at_risk_usd":           round(at_risk_usd, 2),
            "at_risk_pct":           round(at_risk_usd / portfolio_value, 4),
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


def size_signals(signals, portfolio_value, risk_pct=None):
    """
    Add position_size dict to each signal.

    For earnings_event_long signals, position sizing uses the LARGER of:
      (a) ATR-based stop distance (entry − stop_price), or
      (b) EARNINGS_GAP_RISK_PCT × entry_price  (conservative gap risk floor)

    Earnings overnight gaps (±8-15%) are discontinuous events that bypass ATR
    stops entirely.  Sizing off a 2-3% ATR stop when the true loss scenario is
    an 8-15% gap produces positions 3-5× larger than the 1% risk target.
    The effective_stop_for_sizing field documents the adjusted level; the
    signal's stop_price (ATR-based) is preserved for actual order placement.

    Args:
        signals         (list[dict]): Enriched signals with stop_price
        portfolio_value (float):      Total portfolio value
        risk_pct        (float|None): Override risk per trade (default: RISK_PER_TRADE_PCT=1%).
                                      Pass 0.0075 for NEUTRAL, 0.005 for BEAR_SHALLOW.
    Returns:
        list[dict]: Signals with 'sizing' field added
    """
    def _zero_risk_sizing(base_risk_pct, entry_price, stop_price):
        return {
            "portfolio_value_usd": round(portfolio_value, 2),
            "risk_pct": 0.0,
            "risk_amount_usd": 0.0,
            "entry_price": round(entry_price, 2),
            "stop_price": round(stop_price, 2),
            "risk_per_share": round(entry_price - stop_price, 2),
            "net_risk_per_share": round(
                (entry_price - stop_price)
                + entry_price * ROUND_TRIP_COST_PCT
                + entry_price * EXEC_LAG_PCT,
                4,
            ),
            "shares_to_buy": 0,
            "position_value_usd": 0.0,
            "position_pct_of_portfolio": 0.0,
            "base_risk_pct": base_risk_pct,
        }

    effective_risk_pct = risk_pct if risk_pct is not None else RISK_PER_TRADE_PCT
    sized = []
    for sig in signals:
        entry    = sig.get("entry_price")
        stop     = sig.get("stop_price")
        strategy = sig.get("strategy", "")
        if entry and stop and portfolio_value:
            signal_risk_pct = effective_risk_pct
            trade_quality_score = sig.get("trade_quality_score")
            sector = sig.get("sector")
            gap_vulnerability_pct = sig.get("gap_vulnerability_pct")
            days_to_earnings = sig.get("days_to_earnings")
            is_low_tqs = (
                trade_quality_score is not None
                and trade_quality_score < LOW_TQS_RISK_THRESHOLD
            )
            is_breakout_non_exempt = (
                strategy == "breakout_long"
                and sector not in LOW_TQS_HAIRCUT_EXEMPT_SECTORS
            )
            tqs_de_risk_applied = (
                is_low_tqs
                and sector not in LOW_TQS_HAIRCUT_EXEMPT_SECTORS
            )
            tqs_risk_multiplier = 1.0
            if tqs_de_risk_applied:
                if is_breakout_non_exempt:
                    tqs_risk_multiplier = LOW_TQS_BREAKOUT_NON_EXEMPT_RISK_MULTIPLIER
                else:
                    tqs_risk_multiplier = LOW_TQS_RISK_MULTIPLIER
                signal_risk_pct *= tqs_risk_multiplier
            trend_industrials_risk_multiplier = 1.0
            if strategy == "trend_long" and sector == "Industrials":
                trend_industrials_risk_multiplier = TREND_INDUSTRIALS_RISK_MULTIPLIER
                signal_risk_pct *= trend_industrials_risk_multiplier
            trend_financials_risk_multiplier = 1.0
            risk_on_unmodified_risk_multiplier = 1.0
            trend_tech_tight_gap_risk_multiplier = 1.0
            if (
                strategy == "trend_long"
                and sector == "Technology"
                and gap_vulnerability_pct is not None
                and TREND_TECH_TIGHT_GAP_VULN_MIN <= gap_vulnerability_pct < TREND_TECH_TIGHT_GAP_VULN_MAX
            ):
                # Residual audit found this tighter-gap pocket was a stable drag
                # in the weaker windows and absent in the dominant strong tape.
                trend_tech_tight_gap_risk_multiplier = (
                    TREND_TECH_TIGHT_GAP_RISK_MULTIPLIER
                )
                signal_risk_pct *= trend_tech_tight_gap_risk_multiplier
            trend_tech_gap_risk_multiplier = 1.0
            if (
                strategy == "trend_long"
                and sector == "Technology"
                and gap_vulnerability_pct is not None
                and TREND_TECH_GAP_VULN_MIN <= gap_vulnerability_pct < TREND_TECH_GAP_VULN_MAX
            ):
                # Accepted cohort rule: this pocket was too fragile for full size,
                # but a full ban (0x) proved worse than keeping a small 0.25x stake.
                trend_tech_gap_risk_multiplier = TREND_TECH_GAP_RISK_MULTIPLIER
                signal_risk_pct *= trend_tech_gap_risk_multiplier
            trend_tech_near_high_risk_multiplier = 1.0
            pct_from_52w_high = (sig.get("conditions_met") or {}).get("pct_from_52w_high")
            if strategy == "trend_long" and sector == "Financials":
                trend_financials_risk_multiplier = TREND_FINANCIALS_RISK_MULTIPLIER
                signal_risk_pct *= trend_financials_risk_multiplier
            if (
                strategy == "trend_long"
                and sector == "Technology"
                and pct_from_52w_high is not None
                and pct_from_52w_high >= TREND_TECH_NEAR_HIGH_MAX_PULLBACK
            ):
                # Residual trend-Tech drag is concentrated in the near-high entry
                # shape after the accepted stack; keep the pocket tradable, but
                # only at 25% size so deeper-pullback winners still get budget.
                trend_tech_near_high_risk_multiplier = (
                    TREND_TECH_NEAR_HIGH_RISK_MULTIPLIER
                )
                signal_risk_pct *= trend_tech_near_high_risk_multiplier
            trend_tech_dte_risk_multiplier = 1.0
            if (
                strategy == "trend_long"
                and sector == "Technology"
                and days_to_earnings is not None
                and TREND_TECH_DTE_MIN <= days_to_earnings <= TREND_TECH_DTE_MAX
            ):
                # This is the surviving Technology trend DTE sleeve after the
                # rejected 59-69 DTE+gap probe; keep it narrow and partial-size.
                trend_tech_dte_risk_multiplier = TREND_TECH_DTE_RISK_MULTIPLIER
                signal_risk_pct *= trend_tech_dte_risk_multiplier
            breakout_industrials_gap_risk_multiplier = 1.0
            if (
                strategy == "breakout_long"
                and sector == "Industrials"
                and gap_vulnerability_pct is not None
                and BREAKOUT_INDUSTRIALS_GAP_VULN_MIN <= gap_vulnerability_pct < BREAKOUT_INDUSTRIALS_GAP_VULN_MAX
            ):
                breakout_industrials_gap_risk_multiplier = (
                    BREAKOUT_INDUSTRIALS_GAP_RISK_MULTIPLIER
                )
                signal_risk_pct *= breakout_industrials_gap_risk_multiplier
            breakout_comms_near_high_risk_multiplier = 1.0
            if (
                strategy == "breakout_long"
                and sector == "Communication Services"
                and pct_from_52w_high is not None
                and pct_from_52w_high >= BREAKOUT_COMMS_NEAR_HIGH_MAX_PULLBACK
            ):
                # Residual breakout audit found the weak-window leak here was an
                # entry shape, not another sector+gap pocket. Keep the sleeve
                # live, but only at 25% risk so stronger breakout cohorts still
                # dominate slot usage.
                breakout_comms_near_high_risk_multiplier = (
                    BREAKOUT_COMMS_NEAR_HIGH_RISK_MULTIPLIER
                )
                signal_risk_pct *= breakout_comms_near_high_risk_multiplier
            breakout_comms_gap_risk_multiplier = 1.0
            if (
                strategy == "breakout_long"
                and sector == "Communication Services"
                and gap_vulnerability_pct is not None
                and BREAKOUT_COMMS_GAP_VULN_MIN <= gap_vulnerability_pct < BREAKOUT_COMMS_GAP_VULN_MAX
            ):
                # After the accepted near-high haircut, the residual drag in
                # this sleeve still clustered in moderate-gap setups.
                breakout_comms_gap_risk_multiplier = (
                    BREAKOUT_COMMS_GAP_RISK_MULTIPLIER
                )
                signal_risk_pct *= breakout_comms_gap_risk_multiplier
            breakout_financials_dte_risk_multiplier = 1.0
            if (
                strategy == "breakout_long"
                and sector == "Financials"
                and days_to_earnings is not None
                and BREAKOUT_FINANCIALS_DTE_MIN <= days_to_earnings <= BREAKOUT_FINANCIALS_DTE_MAX
            ):
                # Residual breakout audit found that the remaining Financials drag
                # was event-proximity, not another sector-only or price-shape leak.
                breakout_financials_dte_risk_multiplier = (
                    BREAKOUT_FINANCIALS_DTE_RISK_MULTIPLIER
                )
                signal_risk_pct *= breakout_financials_dte_risk_multiplier
            breakout_tech_dte_risk_multiplier = 1.0
            if (
                strategy == "breakout_long"
                and sector == "Technology"
                and days_to_earnings is not None
                and BREAKOUT_TECH_DTE_MIN <= days_to_earnings <= BREAKOUT_TECH_DTE_MAX
            ):
                # Residual audit found this breakout-only Technology pocket was
                # repeatedly weak 26-40 trading days before earnings and absent
                # from the dominant strong tape. This is not the rejected trend
                # Technology DTE+gap family.
                breakout_tech_dte_risk_multiplier = (
                    BREAKOUT_TECH_DTE_RISK_MULTIPLIER
                )
                signal_risk_pct *= breakout_tech_dte_risk_multiplier
            breakout_healthcare_dte_risk_multiplier = 1.0
            if (
                strategy == "breakout_long"
                and sector == "Healthcare"
                and days_to_earnings is not None
                and BREAKOUT_HEALTHCARE_DTE_MIN <= days_to_earnings <= BREAKOUT_HEALTHCARE_DTE_MAX
            ):
                # Runtime residual audit found this Healthcare breakout
                # event-distance sleeve improved the mid/old validation windows.
                # Keep it partial-size; widening to 20-70 DTE cut a late winner.
                breakout_healthcare_dte_risk_multiplier = (
                    BREAKOUT_HEALTHCARE_DTE_RISK_MULTIPLIER
                )
                signal_risk_pct *= breakout_healthcare_dte_risk_multiplier
            trend_healthcare_dte_risk_multiplier = 1.0
            if (
                strategy == "trend_long"
                and sector == "Healthcare"
                and days_to_earnings is not None
                and TREND_HEALTHCARE_DTE_MIN <= days_to_earnings <= TREND_HEALTHCARE_DTE_MAX
            ):
                # Residual trend audit found a wider pre-earnings Healthcare
                # pocket that is outside the hard dte<=3 entry block but still
                # carried unstable event-risk exposure.
                trend_healthcare_dte_risk_multiplier = (
                    TREND_HEALTHCARE_DTE_RISK_MULTIPLIER
                )
                signal_risk_pct *= trend_healthcare_dte_risk_multiplier
            trend_consumer_near_high_dte_risk_multiplier = 1.0
            if (
                strategy == "trend_long"
                and sector == "Consumer Discretionary"
                and days_to_earnings is not None
                and pct_from_52w_high is not None
                and TREND_CONSUMER_NEAR_HIGH_DTE_MIN <= days_to_earnings <= TREND_CONSUMER_NEAR_HIGH_DTE_MAX
                and pct_from_52w_high >= TREND_CONSUMER_NEAR_HIGH_MAX_PULLBACK
            ):
                # Fixed-window residual audit found this MCD-like pocket was a
                # repeat loser and absent from the mid-window winners. Keep the
                # rule narrow: trend only, sector only, near-high only, 30-65 DTE.
                trend_consumer_near_high_dte_risk_multiplier = (
                    TREND_CONSUMER_NEAR_HIGH_DTE_RISK_MULTIPLIER
                )
                signal_risk_pct *= trend_consumer_near_high_dte_risk_multiplier
            trend_commodities_near_high_risk_multiplier = 1.0
            if (
                strategy == "trend_long"
                and sector == "Commodities"
                and pct_from_52w_high is not None
                and pct_from_52w_high >= TREND_COMMODITIES_NEAR_HIGH_MAX_PULLBACK
            ):
                # Commodity trend winners were concentrated near 52-week highs.
                # Keep this as an allocation boost, not a new entry source.
                trend_commodities_near_high_risk_multiplier = (
                    TREND_COMMODITIES_NEAR_HIGH_RISK_MULTIPLIER
                )
                signal_risk_pct *= trend_commodities_near_high_risk_multiplier
            existing_sizing_multipliers = (
                tqs_risk_multiplier,
                trend_industrials_risk_multiplier,
                trend_financials_risk_multiplier,
                trend_tech_tight_gap_risk_multiplier,
                trend_tech_gap_risk_multiplier,
                trend_tech_near_high_risk_multiplier,
                trend_tech_dte_risk_multiplier,
                breakout_industrials_gap_risk_multiplier,
                breakout_comms_near_high_risk_multiplier,
                breakout_comms_gap_risk_multiplier,
                breakout_financials_dte_risk_multiplier,
                breakout_tech_dte_risk_multiplier,
                breakout_healthcare_dte_risk_multiplier,
                trend_healthcare_dte_risk_multiplier,
                trend_consumer_near_high_dte_risk_multiplier,
                trend_commodities_near_high_risk_multiplier,
            )
            has_other_sizing_rule = any(
                multiplier != 1.0 for multiplier in existing_sizing_multipliers
            )
            if (
                sig.get("regime_exit_bucket") == "risk_on"
                and not has_other_sizing_rule
            ):
                risk_on_unmodified_risk_multiplier = (
                    RISK_ON_UNMODIFIED_RISK_MULTIPLIER
                )
                signal_risk_pct *= risk_on_unmodified_risk_multiplier
            if signal_risk_pct <= 0:
                sizing = _zero_risk_sizing(effective_risk_pct, entry, stop)
            elif strategy == "earnings_event_long":
                # Gap risk dominates: size based on max(ATR stop dist, 8% gap risk).
                # For typical ATR ≤ 5%: gap_risk = 8% > ATR stop ≤ 7.5% → gap floor applies.
                # For ATR = 5% (near the 5% gate): max(7.5%, 8%) = 8% — gap floor applies.
                # This reduces earnings position sizes by ~60-75% vs ATR-only sizing.
                atr_risk  = entry - stop
                gap_risk  = entry * EARNINGS_GAP_RISK_PCT
                effective_stop = round(entry - max(atr_risk, gap_risk), 2)
                sizing = compute_position_size(portfolio_value, entry, effective_stop,
                                               risk_pct=signal_risk_pct)
                if sizing:
                    sizing["earnings_gap_risk_applied"]  = True
                    sizing["gap_risk_pct"]               = EARNINGS_GAP_RISK_PCT
                    sizing["effective_stop_for_sizing"]  = effective_stop
            else:
                sizing = compute_position_size(portfolio_value, entry, stop,
                                               risk_pct=signal_risk_pct)
            if sizing:
                sizing["base_risk_pct"] = effective_risk_pct
                sizing["trade_quality_score"] = trade_quality_score
                sizing["low_tqs_haircut_exempt_sector"] = (
                    sector if sector in LOW_TQS_HAIRCUT_EXEMPT_SECTORS else None
                )
                sizing["tqs_risk_multiplier_applied"] = tqs_risk_multiplier
                sizing["trend_industrials_risk_multiplier_applied"] = (
                    trend_industrials_risk_multiplier
                )
                sizing["trend_financials_risk_multiplier_applied"] = (
                    trend_financials_risk_multiplier
                )
                sizing["risk_on_unmodified_risk_multiplier_applied"] = (
                    risk_on_unmodified_risk_multiplier
                )
                sizing["trend_tech_tight_gap_risk_multiplier_applied"] = (
                    trend_tech_tight_gap_risk_multiplier
                )
                sizing["trend_tech_gap_risk_multiplier_applied"] = (
                    trend_tech_gap_risk_multiplier
                )
                sizing["trend_tech_near_high_risk_multiplier_applied"] = (
                    trend_tech_near_high_risk_multiplier
                )
                sizing["trend_tech_dte_risk_multiplier_applied"] = (
                    trend_tech_dte_risk_multiplier
                )
                sizing["breakout_industrials_gap_risk_multiplier_applied"] = (
                    breakout_industrials_gap_risk_multiplier
                )
                sizing["breakout_comms_near_high_risk_multiplier_applied"] = (
                    breakout_comms_near_high_risk_multiplier
                )
                sizing["breakout_comms_gap_risk_multiplier_applied"] = (
                    breakout_comms_gap_risk_multiplier
                )
                sizing["breakout_financials_dte_risk_multiplier_applied"] = (
                    breakout_financials_dte_risk_multiplier
                )
                sizing["breakout_tech_dte_risk_multiplier_applied"] = (
                    breakout_tech_dte_risk_multiplier
                )
                sizing["breakout_healthcare_dte_risk_multiplier_applied"] = (
                    breakout_healthcare_dte_risk_multiplier
                )
                sizing["trend_healthcare_dte_risk_multiplier_applied"] = (
                    trend_healthcare_dte_risk_multiplier
                )
                sizing["trend_consumer_near_high_dte_risk_multiplier_applied"] = (
                    trend_consumer_near_high_dte_risk_multiplier
                )
                sizing["trend_commodities_near_high_risk_multiplier_applied"] = (
                    trend_commodities_near_high_risk_multiplier
                )
                sig = {**sig, "sizing": sizing}
        sized.append(sig)
    return sized
