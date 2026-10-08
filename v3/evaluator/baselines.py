"""Fixed external comparators (architecture doc 1c).  Never the incumbent portfolio.

S0  SPY buy-and-hold.
S1  SPY 200-day moving-average timing, checked at month end: SPY total-return index above its
    200-day average -> 100% SPY, otherwise cash.
S2  vol-matched SPY is S0 scaled to the strategy's volatility (metrics.vol_matched).
"""
from __future__ import annotations

from engine import History

SMA_DAYS = 200


def s0_spy(hist: History) -> dict:
    return {"SPY": 1.0}


def s1_spy_200dma(hist: History) -> dict:
    tr = (1 + hist.returns["SPY"].dropna()).cumprod()
    if len(tr) < SMA_DAYS:
        return {}
    return {"SPY": 1.0} if tr.iloc[-1] > tr.iloc[-SMA_DAYS:].mean() else {}
