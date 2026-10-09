"""A-class: time-series momentum (Moskowitz, Ooi & Pedersen 2012), long-only, unlevered, monthly.

Hold an asset only if its past 12-month return exceeds cash over the same period.  Weights are
inverse ex-ante volatility (EWMA of squared daily returns, centre of mass 60 days), normalised over
the whole eligible pool, so the share of assets with a negative signal stays in cash.

Registration: v3/strategies/REGISTRATION_A_20261008.md (order 3).
"""
import math

CLASS = "A"
FAMILY = "tsmom"
FREQ = "M"

ASSETS = ["SPY", "IWM", "EFA", "EEM", "IEF", "TLT", "LQD", "GLD", "DBC", "UUP"]
LOOKBACK_DAYS = 252
VOL_COM = 60


def _trading(hist):
    r = hist.returns[ASSETS]
    if len(r) < LOOKBACK_DAYS + 1:
        return {}
    window = r.iloc[-LOOKBACK_DAYS:]
    eligible = [a for a in ASSETS if window[a].notna().all()]
    if not eligible:
        return {}
    cash_12m = (1 + hist.cash.iloc[-LOOKBACK_DAYS:]).prod() - 1
    inv_vol = {}
    for a in eligible:
        var = (r[a].dropna() ** 2).ewm(com=VOL_COM).mean().iloc[-1]
        vol = math.sqrt(var * 252)
        if vol > 0:
            inv_vol[a] = 1 / vol
    total = sum(inv_vol.values())
    out = {}
    for a, iv in inv_vol.items():
        if (1 + window[a]).prod() - 1 > cash_12m:
            out[a] = iv / total
    return out


SIGNALS = {"trading": _trading}
