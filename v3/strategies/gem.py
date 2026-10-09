"""A-class: Global Equities Momentum (Antonacci 2014), monthly.

If SPY's past 12-month return beats cash, hold whichever of SPY / EFA has the higher 12-month
return; otherwise hold IEF.  Assets without 12 months of history are skipped (cash if none).

Registration: v3/strategies/REGISTRATION_A_20261008.md (order 4).
"""
CLASS = "A"
FAMILY = "gem"
FREQ = "M"

LOOKBACK_DAYS = 252


def _ret12(hist, a):
    w = hist.returns[a].iloc[-LOOKBACK_DAYS:]
    if len(w) < LOOKBACK_DAYS or w.isna().any():
        return None
    return (1 + w).prod() - 1


def _trading(hist):
    spy = _ret12(hist, "SPY")
    if spy is None:
        return {}
    cash = (1 + hist.cash.iloc[-LOOKBACK_DAYS:]).prod() - 1
    if spy > cash:
        efa = _ret12(hist, "EFA")
        return {"EFA": 1.0} if efa is not None and efa > spy else {"SPY": 1.0}
    return {"IEF": 1.0} if _ret12(hist, "IEF") is not None else {}


SIGNALS = {"trading": _trading}
