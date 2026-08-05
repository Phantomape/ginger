"""Deterministic US equity session calendar for sleeve state advancement.

exp-20260612-001: daily production runs execute every calendar day, but the
older paper sleeves advanced hold-day counters and filled pending entries on
any run date. On weekends and NYSE holidays the latest downloaded bar is still
Friday's, so those sleeves booked phantom same-day rows at stale prices and
closed nominal 10-trading-day holds after ~7 actual sessions. This module
answers one question - "is this date a regular US equity session?" - from pure
calendar rules (weekday + computed NYSE holidays), so no market data needs to
be plumbed into sleeve advance/fill functions.

Half-days (early closes) are still sessions and intentionally return True.
"""

from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo


_NEW_YORK = ZoneInfo("America/New_York")


def _easter_sunday(year: int) -> datetime.date:
    """Anonymous Gregorian computus."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return datetime.date(year, month, day + 1)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> datetime.date:
    """n-th (1-based) given weekday of a month; weekday: Monday=0."""
    first = datetime.date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + datetime.timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> datetime.date:
    next_month = datetime.date(year + (month == 12), (month % 12) + 1, 1)
    last = next_month - datetime.timedelta(days=1)
    return last - datetime.timedelta(days=(last.weekday() - weekday) % 7)


def _observed(date: datetime.date) -> datetime.date:
    """NYSE observation shift: Saturday -> Friday, Sunday -> Monday."""
    if date.weekday() == 5:
        return date - datetime.timedelta(days=1)
    if date.weekday() == 6:
        return date + datetime.timedelta(days=1)
    return date


def nyse_holidays(year: int) -> set[datetime.date]:
    """Regular full-day NYSE holidays for a year (no special closures)."""
    easter = _easter_sunday(year)
    holidays = {
        _observed(datetime.date(year, 1, 1)),                  # New Year's Day
        _nth_weekday(year, 1, 0, 3),                           # MLK Day
        _nth_weekday(year, 2, 0, 3),                           # Washington's Birthday
        easter - datetime.timedelta(days=2),                   # Good Friday
        _last_weekday(year, 5, 0),                             # Memorial Day
        _observed(datetime.date(year, 7, 4)),                  # Independence Day
        _nth_weekday(year, 9, 0, 1),                           # Labor Day
        _nth_weekday(year, 11, 3, 4),                          # Thanksgiving
        _observed(datetime.date(year, 12, 25)),                # Christmas
    }
    if year >= 2022:
        holidays.add(_observed(datetime.date(year, 6, 19)))    # Juneteenth
    # New Year's Day observed on a Saturday shifts to the prior Friday, which
    # falls in the previous year; NYSE does not close that Friday, so drop it.
    holidays = {d for d in holidays if d.year == year}
    return holidays


def is_us_equity_session(as_of: str | datetime.date) -> bool:
    """True when ``as_of`` is a regular US equity trading session."""
    if isinstance(as_of, datetime.date):
        date = as_of
    else:
        date = datetime.date.fromisoformat(str(as_of)[:10])
    if date.weekday() >= 5:
        return False
    return date not in nyse_holidays(date.year)


def latest_completed_us_equity_session(
    as_of: datetime.datetime,
    completion_buffer_minutes: int = 15,
) -> datetime.date:
    """Return the latest regular US equity session completed by ``as_of``.

    A regular session is treated as complete at 16:00 America/New_York plus
    ``completion_buffer_minutes``.  Before that boundary, the current local
    date is deliberately excluded.  Half-days use the same conservative
    boundary, while weekends and full-day NYSE holidays are skipped.

    ``as_of`` must be timezone-aware so callers cannot accidentally interpret
    a UTC wall clock as a New York market date.
    """
    if not isinstance(as_of, datetime.datetime):
        raise TypeError("as_of must be a timezone-aware datetime")
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")
    if completion_buffer_minutes < 0:
        raise ValueError("completion_buffer_minutes must be non-negative")

    local_as_of = as_of.astimezone(_NEW_YORK)
    completion_at = local_as_of.replace(
        hour=16,
        minute=0,
        second=0,
        microsecond=0,
    ) + datetime.timedelta(minutes=completion_buffer_minutes)
    candidate = local_as_of.date()
    if local_as_of < completion_at:
        candidate -= datetime.timedelta(days=1)

    while not is_us_equity_session(candidate):
        candidate -= datetime.timedelta(days=1)
    return candidate
