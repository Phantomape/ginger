"""A-class: turn-of-the-month effect (Lakonishok & Smidt 1988; McConnell & Xu 2008), daily.

Hold SPY over the last trading day of each month and the first three trading days of the next
(days -1..+3); cash otherwise.  Window copied from the papers, no parameters tuned.

Timing: a decision at close t fills at close t+1 (evaluator convention), so the position held over
the return of day t+2 is the one decided at t.  The signal therefore asks whether the trading day
two sessions ahead lies in the window, which needs the exchange calendar (known in advance; NYSE
rules below plus the unscheduled closures since SPY's launch).  Trading layer only: Ken French
publishes no daily market series, so there is no evidence layer.
Registration: v3/strategies/REGISTRATION_A_20261012.md.
"""
import bisect
import datetime as dt
from functools import lru_cache

import pandas as pd
from dateutil.easter import easter

CLASS = "A"
FAMILY = "turn_of_month"
FREQ = "D"

ASSET = "SPY"
LAST_DAYS = 1   # trading days before the turn
FIRST_DAYS = 3  # trading days after the turn

SPECIAL_CLOSURES = {
    dt.date(1994, 4, 27), dt.date(2001, 9, 11), dt.date(2001, 9, 12), dt.date(2001, 9, 13),
    dt.date(2001, 9, 14), dt.date(2004, 6, 11), dt.date(2007, 1, 2), dt.date(2012, 10, 29),
    dt.date(2012, 10, 30), dt.date(2018, 12, 5), dt.date(2025, 1, 9),
}


def _nth_weekday(year, month, weekday, n):
    """n-th (1-based) given weekday of the month; n = -1 is the last one."""
    if n > 0:
        first = dt.date(year, month, 1)
        return first + dt.timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))
    nxt = dt.date(year + (month == 12), month % 12 + 1, 1)
    last = nxt - dt.timedelta(days=1)
    return last - dt.timedelta(days=(last.weekday() - weekday) % 7)


def _observed(d):
    """Saturday holidays move to Friday, Sunday holidays to Monday."""
    if d.weekday() == 5:
        return d - dt.timedelta(days=1)
    if d.weekday() == 6:
        return d + dt.timedelta(days=1)
    return d


def _holidays(year):
    h = set()
    ny = dt.date(year, 1, 1)
    if ny.weekday() != 5:  # NYSE does not close the preceding Friday
        h.add(_observed(ny))
    if year >= 1998:
        h.add(_nth_weekday(year, 1, 0, 3))  # Martin Luther King Jr. Day
    h.add(_nth_weekday(year, 2, 0, 3))  # Washington's Birthday
    h.add(easter(year) - dt.timedelta(days=2))  # Good Friday
    h.add(_nth_weekday(year, 5, 0, -1))  # Memorial Day
    if year >= 2022:
        h.add(_observed(dt.date(year, 6, 19)))  # Juneteenth
    h.add(_observed(dt.date(year, 7, 4)))
    h.add(_nth_weekday(year, 9, 0, 1))  # Labor Day
    h.add(_nth_weekday(year, 11, 3, 4))  # Thanksgiving
    h.add(_observed(dt.date(year, 12, 25)))
    return h


@lru_cache(maxsize=None)
def _sessions(year):
    closed = _holidays(year) | {d for d in SPECIAL_CLOSURES if d.year == year}
    d, out = dt.date(year, 1, 1), []
    while d.year == year:
        if d.weekday() < 5 and d not in closed:
            out.append(d)
        d += dt.timedelta(days=1)
    return tuple(out)


def in_window(d):
    month = [s for s in _sessions(d.year) if s.month == d.month]
    return d in month[:FIRST_DAYS] or d in month[-LAST_DAYS:]


def _trading(hist):
    if pd.isna(hist.returns[ASSET].iloc[-1]):
        return {}
    t = hist.returns.index[-1].date()
    days = _sessions(t.year) + _sessions(t.year + 1)
    ahead = days[bisect.bisect_right(days, t) + 1]  # second session after t
    return {ASSET: 1.0} if in_window(ahead) else {}


SIGNALS = {"trading": _trading}
