"""Parity tests for the MACRO_EVENTS extraction into quant/macro_events.py."""

import macro_events
import macro_relief_leadership_paper_sleeve as sleeve


def test_sleeve_reexports_same_object():
    # Identity (not equality): the sleeve and every experiment that reads
    # macro.MACRO_EVENTS must observe the single shared calendar.
    assert sleeve.MACRO_EVENTS is macro_events.MACRO_EVENTS


def test_historical_rows_moved_verbatim():
    events = macro_events.MACRO_EVENTS
    assert events[0] == {
        "date": "2024-10-04",
        "family": "NFP",
        "label": "Sep 2024 Employment Situation",
    }
    # Last row of the original in-sleeve calendar (48 rows) before the
    # verified 2026 backfill was appended.
    assert events[47] == {
        "date": "2026-04-10",
        "family": "CPI",
        "label": "Mar 2026 CPI",
    }
    assert len(events) >= 48


def test_rows_are_sorted_and_well_formed():
    events = macro_events.MACRO_EVENTS
    dates = [e["date"] for e in events]
    assert dates == sorted(dates)
    assert len(set(dates)) == len(dates)
    assert {e["family"] for e in events} == {"NFP", "CPI", "FOMC"}
    assert all(len(e["date"]) == 10 and e["label"] for e in events)


def test_macro_events_on():
    fomc = macro_events.macro_events_on("2026-03-18")
    assert len(fomc) == 1 and fomc[0]["family"] == "FOMC"
    assert macro_events.macro_events_on("2026-03-19") == []


def test_upcoming_macro_events_window():
    upcoming = macro_events.upcoming_macro_events("2026-06-04", horizon_days=7)
    assert [(e["date"], e["family"]) for e in upcoming] == [
        ("2026-06-05", "NFP"),
        ("2026-06-10", "CPI"),
    ]
    # Strictly after the as-of date: same-day events are not "upcoming".
    upcoming = macro_events.upcoming_macro_events("2026-06-05", horizon_days=7)
    assert ("2026-06-05", "NFP") not in [(e["date"], e["family"]) for e in upcoming]


def test_calendar_coverage():
    coverage = macro_events.calendar_family_coverage()
    assert coverage["NFP"] >= "2026-12-04"
    assert coverage["FOMC"] >= "2026-12-09"
    assert coverage["CPI"] >= "2026-12-10"
    assert macro_events.calendar_coverage_end() == max(coverage.values())
    assert macro_events.calendar_coverage_end("NFP") == coverage["NFP"]
