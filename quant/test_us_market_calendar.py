"""Focused tests for the US equity session calendar (exp-20260612-001)."""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from us_market_calendar import (
    is_us_equity_session,
    latest_completed_us_equity_session,
    nyse_holidays,
)


def test_weekends_are_not_sessions():
    assert not is_us_equity_session("2026-05-16")  # Saturday
    assert not is_us_equity_session("2026-05-17")  # Sunday
    assert not is_us_equity_session("2026-06-06")  # Saturday
    assert not is_us_equity_session("2026-06-07")  # Sunday


def test_known_2026_holidays():
    assert not is_us_equity_session("2026-01-01")  # New Year's Day
    assert not is_us_equity_session("2026-01-19")  # MLK Day
    assert not is_us_equity_session("2026-02-16")  # Washington's Birthday
    assert not is_us_equity_session("2026-04-03")  # Good Friday
    assert not is_us_equity_session("2026-05-25")  # Memorial Day
    assert not is_us_equity_session("2026-06-19")  # Juneteenth
    assert not is_us_equity_session("2026-07-03")  # Independence Day observed (Jul 4 = Saturday)
    assert not is_us_equity_session("2026-09-07")  # Labor Day
    assert not is_us_equity_session("2026-11-26")  # Thanksgiving
    assert not is_us_equity_session("2026-12-25")  # Christmas


def test_known_2025_holidays():
    assert not is_us_equity_session("2025-01-01")
    assert not is_us_equity_session("2025-01-20")  # MLK Day
    assert not is_us_equity_session("2025-04-18")  # Good Friday
    assert not is_us_equity_session("2025-05-26")  # Memorial Day
    assert not is_us_equity_session("2025-11-27")  # Thanksgiving


def test_regular_trading_days_are_sessions():
    for day in ("2026-06-08", "2026-06-09", "2026-06-10", "2026-06-11",
                "2026-05-15", "2026-05-26", "2025-04-21", "2024-10-02"):
        assert is_us_equity_session(day), day


def test_audit_phantom_row_dates_are_rejected():
    # The exact dates that produced phantom sleeve rows in the 2026-06-11 audit.
    for day in ("2026-05-09", "2026-05-16", "2026-05-17", "2026-05-23",
                "2026-05-24", "2026-05-25", "2026-05-30", "2026-05-31"):
        assert not is_us_equity_session(day), day


def test_holiday_sets_have_expected_size():
    assert len(nyse_holidays(2026)) == 10
    assert len(nyse_holidays(2025)) == 10


def test_latest_completed_session_keeps_normal_late_evening_session():
    as_of = datetime.datetime.fromisoformat("2026-07-30T21:00:00-04:00")
    assert latest_completed_us_equity_session(as_of) == datetime.date(2026, 7, 30)


def test_latest_completed_session_does_not_use_new_york_date_before_open():
    # The failing production boundary: 04:08 UTC is already July 31 in New
    # York, but the July 31 market session has not happened yet.
    as_of = datetime.datetime.fromisoformat("2026-07-31T04:08:00+00:00")
    assert latest_completed_us_equity_session(as_of) == datetime.date(2026, 7, 30)


def test_latest_completed_session_switches_at_buffered_close():
    before = datetime.datetime.fromisoformat("2026-08-03T16:14:59-04:00")
    after = datetime.datetime.fromisoformat("2026-08-03T16:15:00-04:00")
    assert latest_completed_us_equity_session(before) == datetime.date(2026, 7, 31)
    assert latest_completed_us_equity_session(after) == datetime.date(2026, 8, 3)


def test_latest_completed_session_walks_back_across_weekend():
    as_of = datetime.datetime.fromisoformat("2026-08-02T20:00:00-04:00")
    assert latest_completed_us_equity_session(as_of) == datetime.date(2026, 7, 31)


def test_latest_completed_session_walks_back_across_observed_independence_day():
    as_of = datetime.datetime.fromisoformat("2026-07-03T20:00:00-04:00")
    assert latest_completed_us_equity_session(as_of) == datetime.date(2026, 7, 2)


def test_latest_completed_session_rejects_naive_datetime():
    with pytest.raises(ValueError, match="timezone-aware"):
        latest_completed_us_equity_session(datetime.datetime(2026, 7, 31, 4, 8))


def test_latest_completed_session_is_deterministic_across_restart():
    as_of = datetime.datetime.fromisoformat("2026-07-31T04:08:00+00:00")
    first_run = latest_completed_us_equity_session(as_of)
    restarted_run = latest_completed_us_equity_session(as_of)
    assert restarted_run == first_run == datetime.date(2026, 7, 30)
