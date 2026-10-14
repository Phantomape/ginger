"""A-class stock-sort candidate: profitability, top decile of operating profitability (Novy-Marx 2013; Fama & French 2015).

Evidence: Ken French value-weighted portfolio "OP:Hi 10" (all CRSP stocks, delisted included).
Trading: QUAL (long-only factor ETF; an approximation of the sort, not the same portfolio).
Registration: v3/strategies/REGISTRATION_A_20261009.md.
"""
CLASS = "A"
FAMILY = "stock_profitability"
FREQ = "M"

EVIDENCE_PORTFOLIO = "OP:Hi 10"
TRADING_ETF = "QUAL"


def _evidence(hist):
    return {EVIDENCE_PORTFOLIO: 1.0} if hist.returns[EVIDENCE_PORTFOLIO].notna().iloc[-1] else {}


def _trading(hist):
    return {TRADING_ETF: 1.0} if hist.returns[TRADING_ETF].notna().iloc[-1] else {}


SIGNALS = {"evidence_sorts": _evidence, "trading": _trading}
