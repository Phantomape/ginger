"""A-class stock-sort candidate: value, top decile of book-to-market (Fama & French 1992).

Evidence: Ken French value-weighted portfolio "BM:Hi 10" (all CRSP stocks, delisted included).
Trading: VLUE (long-only factor ETF; an approximation of the sort, not the same portfolio).
Registration: v3/strategies/REGISTRATION_A_20261009.md.
"""
CLASS = "A"
FAMILY = "stock_value"
FREQ = "M"

EVIDENCE_PORTFOLIO = "BM:Hi 10"
TRADING_ETF = "VLUE"


def _evidence(hist):
    return {EVIDENCE_PORTFOLIO: 1.0} if hist.returns[EVIDENCE_PORTFOLIO].notna().iloc[-1] else {}


def _trading(hist):
    return {TRADING_ETF: 1.0} if hist.returns[TRADING_ETF].notna().iloc[-1] else {}


SIGNALS = {"evidence_sorts": _evidence, "trading": _trading}
