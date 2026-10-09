"""A-class: industry momentum, 12-1 month formation, equal-weight top tercile, monthly.

Registration: v3/strategies/REGISTRATION_A_20261008.md (order 1).
"""
CLASS = "A"
FAMILY = "industry_momentum"
FREQ = "M"

SECTOR_ETFS = ["XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]
TOP_FRACTION = 1 / 3
TRADING_TOP_N = 3
# Ken French has no Rubbr returns for 1943-07..1944-06 (the only interior gap in the file); a holding
# cannot be valued through it, so the industry is excluded (implementation fix, see registration).
EXCLUDE = ["MKT", "Rubbr"]


def _evidence(hist):
    r = hist.returns.drop(columns=EXCLUDE)
    if len(r) < 12:
        return {}
    window = r.iloc[-12:-1]  # months t-11 .. t-1, skipping the most recent month
    window = window.loc[:, window.notna().all() & r.iloc[-1].notna()]
    score = (1 + window).prod() - 1
    n = max(1, int(len(score) * TOP_FRACTION))
    top = score.sort_values(ascending=False).index[:n]
    return {k: 1 / n for k in top}


def _trading(hist):
    r = hist.returns[SECTOR_ETFS]
    if len(r) < 253:
        return {}
    window = r.iloc[-252:-21]  # about 12 months back, skipping the latest month
    window = window.loc[:, window.notna().all() & r.iloc[-1].notna()]
    if window.shape[1] < TRADING_TOP_N:
        return {}
    score = (1 + window).prod() - 1
    top = score.sort_values(ascending=False).index[:TRADING_TOP_N]
    return {k: 1 / TRADING_TOP_N for k in top}


SIGNALS = {"evidence": _evidence, "trading": _trading}
