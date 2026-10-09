"""A-class: Faber (2007) 10-month moving-average timing across five asset classes, monthly.

Registration: v3/strategies/REGISTRATION_A_20261008.md (order 2).
"""
CLASS = "A"
FAMILY = "faber_sma"
FREQ = "M"

ASSETS = ["SPY", "EFA", "IEF", "VNQ", "DBC"]
SMA_MONTHS = 10


def _trading(hist):
    out = {}
    for a in ASSETS:
        r = hist.returns[a].dropna()
        if r.empty:
            continue
        index = (1 + r).cumprod()
        month_end = index.groupby(index.index.to_period("M")).last()
        # the current month is complete because signals are taken on the last session of the month
        if len(month_end) < SMA_MONTHS + 1:
            continue
        if month_end.iloc[-1] > month_end.iloc[-SMA_MONTHS:].mean():
            out[a] = 1 / len(ASSETS)
    return out


SIGNALS = {"trading": _trading}
