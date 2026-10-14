"""A-class stock-sort candidate: momentum, top decile of prior 12-2 month return (Jegadeesh & Titman 1993).

Evidence: Ken French value-weighted portfolio "MOM:Hi PRIOR" (all CRSP stocks, delisted included).
Trading: MTUM (long-only factor ETF; an approximation of the sort, not the same portfolio).
Registration: v3/strategies/REGISTRATION_A_20261009.md.
"""
CLASS = "A"
FAMILY = "stock_momentum"
FREQ = "M"

EVIDENCE_PORTFOLIO = "MOM:Hi PRIOR"
TRADING_ETF = "MTUM"


def _evidence(hist):
    return {EVIDENCE_PORTFOLIO: 1.0} if hist.returns[EVIDENCE_PORTFOLIO].notna().iloc[-1] else {}


def _trading(hist):
    return {TRADING_ETF: 1.0} if hist.returns[TRADING_ETF].notna().iloc[-1] else {}


SIGNALS = {"evidence_sorts": _evidence, "trading": _trading}
