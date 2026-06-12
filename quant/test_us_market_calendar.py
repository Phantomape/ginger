"""Focused tests for the US equity session calendar (exp-20260612-001)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from us_market_calendar import is_us_equity_session, nyse_holidays


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
