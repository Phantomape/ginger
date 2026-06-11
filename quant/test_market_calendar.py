"""Tests for the rule-generated NYSE holiday calendar."""

from datetime import date

from market_calendar import nyse_holidays, nyse_holidays_through

# Hand-verified pins (official NYSE Group calendars) — the generator must
# reproduce these exactly, which is what makes the auto-extension in
# finra_iwm_paper_sleeve replay-safe.
PINNED = {
    2025: {
        date(2025, 1, 1), date(2025, 1, 20), date(2025, 2, 17),
        date(2025, 4, 18), date(2025, 5, 26), date(2025, 6, 19),
        date(2025, 7, 4), date(2025, 9, 1), date(2025, 11, 27),
        date(2025, 12, 25),
    },
    2026: {
        date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16),
        date(2026, 4, 3), date(2026, 5, 25), date(2026, 6, 19),
        date(2026, 7, 3), date(2026, 9, 7), date(2026, 11, 26),
        date(2026, 12, 25),
    },
    2027: {
        date(2027, 1, 1), date(2027, 1, 18), date(2027, 2, 15),
        date(2027, 3, 26), date(2027, 5, 31), date(2027, 6, 18),
        date(2027, 7, 5), date(2027, 9, 6), date(2027, 11, 25),
        date(2027, 12, 24),
    },
}


def test_generator_reproduces_official_pins():
    for year, expected in PINNED.items():
        assert nyse_holidays(year) == expected, year


def test_weekend_observance_rules():
    # 2027: Juneteenth Sat -> Fri 6/18, July 4 Sun -> Mon 7/5,
    # Christmas Sat -> Fri 12/24 (all covered by the pin test); spot-check
    # the New Year's Saturday exception: Jan 1 2028 is a Saturday and is NOT
    # observed (the prior Friday stays a trading day).
    closures_2028 = nyse_holidays(2028)
    assert date(2027, 12, 31) not in closures_2028
    assert not any(d.month == 1 and d.day in (1, 2) for d in closures_2028)
    assert len(closures_2028) == 9  # one fewer than a normal year
    # Known 2022 precedent: Jan 1 fell on Saturday, market did not close.
    assert not any(d.month == 1 and d.day in (1, 2) for d in nyse_holidays(2022)
                   if d != date(2022, 1, 17))


def test_good_friday_from_computus():
    assert date(2025, 4, 18) in nyse_holidays(2025)
    assert date(2026, 4, 3) in nyse_holidays(2026)
    assert date(2027, 3, 26) in nyse_holidays(2027)
    assert date(2028, 4, 14) in nyse_holidays(2028)


def test_through_helper_unions_years():
    span = nyse_holidays_through(2027)
    assert span == PINNED[2025] | PINNED[2026] | PINNED[2027]


def test_sleeve_holiday_set_covers_next_year():
    from finra_iwm_paper_sleeve import US_MARKET_HOLIDAYS

    assert max(d.year for d in US_MARKET_HOLIDAYS) >= date.today().year + 1
    # Pinned (verified) years are still fully present.
    for year, expected in PINNED.items():
        assert expected <= set(US_MARKET_HOLIDAYS), year
