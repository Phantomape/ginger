"""Shared fill model for backtester and forward_tester.

Single source of truth for slippage assumptions and the gap-aware fill
helpers, so that the two simulators cannot drift apart when we tune
execution cost.  Commission (ROUND_TRIP_COST_PCT) is NOT here — that
constant lives in portfolio_engine.py and is applied separately as a
per-trade cost; this module only models the price you actually realize
on each leg.
"""

import math

# Slippage in basis points (1 bp = 0.01%).  Watchlist is primarily large-cap
# US equity with a tail of less liquid names (CRDO, APP).  Stop slippage is
# higher because stops execute in the same direction as adverse price moves
# and are disproportionately hit on gap / high-volatility days.
SLIPPAGE_BPS_ENTRY  = 5
SLIPPAGE_BPS_STOP   = 10
SLIPPAGE_BPS_TARGET = 5

# ── Liquidity-aware slippage (opt-in) ────────────────────────────────────────
# The flat bps above understate execution cost for thin names and large orders,
# which silently inflates backtest EV on illiquid trades. When the caller passes
# a name's recent average dollar volume (``adv_dollar``) and the order
# ``notional``, slippage is scaled by a square-root market-impact term plus an
# illiquidity premium. A liquid large-cap (ADV >= LIQUID_REF) with a small order
# is left at ~the base bps, so liquid fills are essentially unchanged.
LIQUID_REF_ADV_USD = 200_000_000.0   # ADV at/above which a name is "liquid"
FLOOR_ADV_USD      = 2_000_000.0     # clamp so ultra-thin names don't explode
IMPACT_BPS         = 50.0            # market-impact bps at 100% participation
MAX_LEG_BPS        = 80.0            # per-leg cap


def liquidity_adjusted_bps(base_bps, adv_dollar, notional):
    """Scale ``base_bps`` up for illiquid names / large participation.

    Reduces to ``base_bps`` for a liquid name (ADV >= LIQUID_REF) with a small
    order, so liquid large-cap fills are unchanged. Monotonically increasing as
    ADV falls or order size rises; capped at MAX_LEG_BPS. Returns ``base_bps``
    unchanged when liquidity context is missing.
    """
    if not adv_dollar or adv_dollar <= 0 or not notional or notional <= 0:
        return base_bps
    illiq = max(1.0, math.sqrt(LIQUID_REF_ADV_USD / max(adv_dollar, FLOOR_ADV_USD)))
    participation = notional / adv_dollar
    impact = IMPACT_BPS * math.sqrt(max(participation, 0.0))
    return min(base_bps * illiq + impact, MAX_LEG_BPS)


def apply_slippage(price, bps, side, *, adv_dollar=None, notional=None):
    """Adjust a theoretical fill price for adverse slippage.

    side='buy'  → raise price  (you pay more than the quoted price)
    side='sell' → lower price  (you receive less than the quoted price)

    When ``adv_dollar`` and ``notional`` are both provided, ``bps`` is replaced
    by the liquidity-adjusted bps; otherwise the flat ``bps`` is used (default).
    """
    if price is None:
        return None
    eff = liquidity_adjusted_bps(bps, adv_dollar, notional)
    factor = 1 + (eff / 10000.0) if side == "buy" else 1 - (eff / 10000.0)
    return round(price * factor, 4)


def apply_entry_fill(open_price, *, adv_dollar=None, notional=None):
    """Long entry: next-day Open with buy-side slippage."""
    return apply_slippage(open_price, SLIPPAGE_BPS_ENTRY, "buy",
                          adv_dollar=adv_dollar, notional=notional)


def apply_stop_fill(open_price, stop_price, *, adv_dollar=None, notional=None):
    """Gap-aware stop fill with sell-side slippage.

    Gap-down (Open < stop): execution happens at Open (below stop already).
    Intraday (Open >= stop, Low <= stop): execution approximated at stop_price.
    Slippage is applied on top so the realized sell is strictly worse than
    the theoretical trigger.
    """
    raw = open_price if open_price < stop_price else stop_price
    return apply_slippage(raw, SLIPPAGE_BPS_STOP, "sell",
                          adv_dollar=adv_dollar, notional=notional)


def apply_target_fill(open_price, target_price, *, adv_dollar=None, notional=None):
    """Gap-aware target fill with sell-side slippage.

    Gap-up (Open >= target): execution at Open (bonus over target).
    Intraday (Open < target, High >= target): execution at target_price.
    Slippage is applied so the realized sell is strictly worse than raw.
    """
    raw = open_price if open_price >= target_price else target_price
    return apply_slippage(raw, SLIPPAGE_BPS_TARGET, "sell",
                          adv_dollar=adv_dollar, notional=notional)
