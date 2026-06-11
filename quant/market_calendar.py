"""Rule-generated NYSE full-day holiday calendar.

NYSE full-day closures are deterministic from published exchange rules, so
instead of a hand-maintained date set that silently goes stale, this module
generates them for any year:

  New Year's Day        Jan 1   (Saturday -> NOT observed, per NYSE rule;
                                 Sunday -> observed Monday)
  Martin Luther King Jr 3rd Monday of January
  Washington's Birthday 3rd Monday of February
  Good Friday           2 days before Easter Sunday (Gregorian computus)
  Memorial Day          last Monday of May
  Juneteenth            Jun 19 (weekend-observed; NYSE holiday since 2022)
  Independence Day      Jul 4  (weekend-observed)
  Labor Day             1st Monday of September
  Thanksgiving Day      4th Thursday of November
  Christmas Day         Dec 25 (weekend-observed)

Weekend observance: Saturday -> preceding Friday, Sunday -> following Monday.

Unscheduled special closures (e.g. days of mourning) cannot be generated and
are not predicted here; finra_iwm_paper_sleeve keeps its verified pinned set
and unions it with this generator (tests assert the generator reproduces the
pinned 2025-2027 sets exactly).
"""

from __future__ import annotations

from datetime import date, timedelta


def _easter_sunday(year: int) -> date:
    """Gregorian Easter (anonymous/Meeus algorithm)."""
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
    return date(year, month, day + 1)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """n-th given weekday (Mon=0) of a month."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    nxt = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    last = nxt - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _observed(holiday: date) -> date | None:
    """Weekend observance shift; None means not observed that year."""
    if holiday.weekday() == 5:  # Saturday -> preceding Friday
        return holiday - timedelta(days=1)
    if holiday.weekday() == 6:  # Sunday -> following Monday
        return holiday + timedelta(days=1)
    return holiday


def nyse_holidays(year: int) -> set[date]:
    """All full-day NYSE closures for a year (regular rules only)."""
    closures: set[date] = set()

    new_year = date(year, 1, 1)
    if new_year.weekday() == 5:
        pass  # Saturday New Year's is not observed (prior Friday stays open)
    else:
        closures.add(_observed(new_year))

    closures.add(_nth_weekday(year, 1, 0, 3))    # MLK Day
    closures.add(_nth_weekday(year, 2, 0, 3))    # Washington's Birthday
    closures.add(_easter_sunday(year) - timedelta(days=2))  # Good Friday
    closures.add(_last_weekday(year, 5, 0))      # Memorial Day
    closures.add(_observed(date(year, 6, 19)))   # Juneteenth
    closures.add(_observed(date(year, 7, 4)))    # Independence Day
    closures.add(_nth_weekday(year, 9, 0, 1))    # Labor Day
    closures.add(_nth_weekday(year, 11, 3, 4))   # Thanksgiving
    closures.add(_observed(date(year, 12, 25)))  # Christmas
    closures.discard(None)
    return closures


def nyse_holidays_through(last_year: int, first_year: int = 2025) -> set[date]:
    """Union of generated closures for first_year..last_year inclusive."""
    holidays: set[date] = set()
    for year in range(first_year, last_year + 1):
        holidays |= nyse_holidays(year)
    return holidays
