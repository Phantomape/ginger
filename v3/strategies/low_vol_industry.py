"""A-class: low-volatility industry tilt, equal-weight lowest-volatility tercile, monthly.

Registration: v3/strategies/REGISTRATION_A_20261008.md (order 5).
"""
CLASS = "A"
FAMILY = "low_vol_industry"
FREQ = "M"

SECTOR_ETFS = ["XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]
BOTTOM_FRACTION = 1 / 3
TRADING_TOP_N = 3
# Ken French has no Rubbr returns for 1943-07..1944-06 (the only interior gap in the file); a holding
# cannot be valued through it, so the industry is excluded (implementation fix, see registration).
EXCLUDE = ["MKT", "Rubbr"]


def _evidence(hist):
    r = hist.returns.drop(columns=EXCLUDE)
    if len(r) < 12:
        return {}
    window = r.iloc[-12:]
    window = window.loc[:, window.notna().all()]
    vol = window.std()
    n = max(1, int(len(vol) * BOTTOM_FRACTION))
    low = vol.sort_values().index[:n]
    return {k: 1 / n for k in low}


def _trading(hist):
    r = hist.returns[SECTOR_ETFS]
    if len(r) < 252:
        return {}
    window = r.iloc[-252:]
    window = window.loc[:, window.notna().all()]
    if window.shape[1] < TRADING_TOP_N:
        return {}
    low = window.std().sort_values().index[:TRADING_TOP_N]
    return {k: 1 / TRADING_TOP_N for k in low}


SIGNALS = {"evidence": _evidence, "trading": _trading}
