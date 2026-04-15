"""Shared fill model for backtester and forward_tester.

Single source of truth for slippage assumptions and the gap-aware fill
helpers, so that the two simulators cannot drift apart when we tune
execution cost.  Commission (ROUND_TRIP_COST_PCT) is NOT here — that
constant lives in portfolio_engine.py and is applied separately as a
per-trade cost; this module only models the price you actually realize
on each leg.
"""

# Slippage in basis points (1 bp = 0.01%).  Watchlist is primarily large-cap
# US equity with a tail of less liquid names (CRDO, APP).  Stop slippage is
# higher because stops execute in the same direction as adverse price moves
# and are disproportionately hit on gap / high-volatility days.
SLIPPAGE_BPS_ENTRY  = 5
SLIPPAGE_BPS_STOP   = 10
SLIPPAGE_BPS_TARGET = 5


def apply_slippage(price, bps, side):
    """Adjust a theoretical fill price for adverse slippage.

    side='buy'  → raise price  (you pay more than the quoted price)
    side='sell' → lower price  (you receive less than the quoted price)
    """
    if price is None:
        return None
    factor = 1 + (bps / 10000.0) if side == "buy" else 1 - (bps / 10000.0)
    return round(price * factor, 4)


def apply_entry_fill(open_price):
    """Long entry: next-day Open with buy-side slippage."""
    return apply_slippage(open_price, SLIPPAGE_BPS_ENTRY, "buy")


def apply_stop_fill(open_price, stop_price):
    """Gap-aware stop fill with sell-side slippage.

    Gap-down (Open < stop): execution happens at Open (below stop already).
    Intraday (Open >= stop, Low <= stop): execution approximated at stop_price.
    Slippage is applied on top so the realized sell is strictly worse than
    the theoretical trigger.
    """
    raw = open_price if open_price < stop_price else stop_price
    return apply_slippage(raw, SLIPPAGE_BPS_STOP, "sell")


def apply_target_fill(open_price, target_price):
    """Gap-aware target fill with sell-side slippage.

    Gap-up (Open >= target): execution at Open (bonus over target).
    Intraday (Open < target, High >= target): execution at target_price.
    Slippage is applied so the realized sell is strictly worse than raw.
    """
    raw = open_price if open_price >= target_price else target_price
    return apply_slippage(raw, SLIPPAGE_BPS_TARGET, "sell")
