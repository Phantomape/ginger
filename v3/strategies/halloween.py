"""A-class: Halloween / "Sell in May" seasonal (Bouman & Jacobsen 2002), monthly.

Hold the market from November through April and cash from May through October.  No parameters.

Evidence: Ken French market (MKT); month-end trades fill at the same close, so the decision at the
end of October covers November.  Trading: SPY, same decision at the last session of the month,
filled at the next close (the evaluator's convention for every trading-layer strategy).
Registration: v3/strategies/REGISTRATION_A_20261012.md.
"""
import pandas as pd

CLASS = "A"
FAMILY = "halloween"
FREQ = "M"

# decision months whose following month lies in November..April
HOLD_AFTER_MONTHS = {10, 11, 12, 1, 2, 3}


def _season(hist, asset):
    if pd.isna(hist.returns[asset].iloc[-1]):
        return {}
    return {asset: 1.0} if hist.returns.index[-1].month in HOLD_AFTER_MONTHS else {}


def _evidence(hist):
    return _season(hist, "MKT")


def _trading(hist):
    return _season(hist, "SPY")


SIGNALS = {"evidence": _evidence, "trading": _trading}
