"""A-class: moving-average timing of high-volatility stocks (after Han, Yang & Zhou 2013), monthly.

Hold the highest-variance decile while its total-return index is above its 10-month average of
month-end values, otherwise cash.  Han-Yang-Zhou time daily with a 10-day average; Ken French
publishes variance-sorted portfolios only monthly, so this is the monthly analogue (declared
deviation, see registration).

Evidence: Ken French value-weighted "VAR:Hi 10" (all CRSP stocks, delisted included).
Trading: SPHB (S&P 500 high-beta stocks), same rule on month-end values.
Registration: v3/strategies/REGISTRATION_A_20261010.md.
"""
CLASS = "A"
FAMILY = "stock_vol_timing"
FREQ = "M"

EVIDENCE_PORTFOLIO = "VAR:Hi 10"
TRADING_ETF = "SPHB"
SMA_MONTHS = 10


def _above_sma(r, monthly: bool):
    r = r.dropna()
    if r.empty:
        return False
    index = (1 + r).cumprod()
    month_end = index if monthly else index.groupby(index.index.to_period("M")).last()
    if len(month_end) < SMA_MONTHS:
        return False
    return month_end.iloc[-1] > month_end.iloc[-SMA_MONTHS:].mean()


def _evidence(hist):
    return {EVIDENCE_PORTFOLIO: 1.0} if _above_sma(hist.returns[EVIDENCE_PORTFOLIO], True) else {}


def _trading(hist):
    return {TRADING_ETF: 1.0} if _above_sma(hist.returns[TRADING_ETF], False) else {}


SIGNALS = {"evidence_sorts": _evidence, "trading": _trading}
