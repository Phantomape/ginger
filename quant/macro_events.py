"""Shared macro event calendar (NFP / CPI / FOMC official release days).

Single source of truth for scheduled macro event dates. Historical rows were
moved verbatim from macro_relief_leadership_paper_sleeve.py — do not edit
existing rows: the macro relief paper sleeve's replay semantics and several
experiments (quant/experiments/exp_20260606_*) depend on them. Appending
future dates is a pure data update.

Date provenance:
- NFP (Employment Situation) and CPI release dates: BLS official release
  schedule (bls.gov/schedule) cross-checked against the OMB Principal Federal
  Economic Indicators schedule for CY2026.
- FOMC decision days: federalreserve.gov FOMC meeting calendar (second day
  of each two-day meeting).

TODO: the Aug 2026 CPI release date (Jul 2026 data, expected mid-August)
could not be verified against the official schedule when this calendar was
last updated — add it from bls.gov/schedule/news_release/cpi.htm.
quant/calendar_audit.py flags this gap (and any future coverage expiry) in
the intraday report's DATA QUALITY section, so staleness is never silent.
"""

from __future__ import annotations

from datetime import date, timedelta

MACRO_EVENTS = [
    {"date": "2024-10-04", "family": "NFP", "label": "Sep 2024 Employment Situation"},
    {"date": "2024-10-10", "family": "CPI", "label": "Sep 2024 CPI"},
    {"date": "2024-11-01", "family": "NFP", "label": "Oct 2024 Employment Situation"},
    {"date": "2024-11-07", "family": "FOMC", "label": "Nov 2024 FOMC decision"},
    {"date": "2024-11-13", "family": "CPI", "label": "Oct 2024 CPI"},
    {"date": "2024-12-06", "family": "NFP", "label": "Nov 2024 Employment Situation"},
    {"date": "2024-12-11", "family": "CPI", "label": "Nov 2024 CPI"},
    {"date": "2024-12-18", "family": "FOMC", "label": "Dec 2024 FOMC decision"},
    {"date": "2025-01-10", "family": "NFP", "label": "Dec 2024 Employment Situation"},
    {"date": "2025-01-15", "family": "CPI", "label": "Dec 2024 CPI"},
    {"date": "2025-01-29", "family": "FOMC", "label": "Jan 2025 FOMC decision"},
    {"date": "2025-02-07", "family": "NFP", "label": "Jan 2025 Employment Situation"},
    {"date": "2025-02-12", "family": "CPI", "label": "Jan 2025 CPI"},
    {"date": "2025-03-07", "family": "NFP", "label": "Feb 2025 Employment Situation"},
    {"date": "2025-03-12", "family": "CPI", "label": "Feb 2025 CPI"},
    {"date": "2025-03-19", "family": "FOMC", "label": "Mar 2025 FOMC decision"},
    {"date": "2025-04-04", "family": "NFP", "label": "Mar 2025 Employment Situation"},
    {"date": "2025-04-10", "family": "CPI", "label": "Mar 2025 CPI"},
    {"date": "2025-05-02", "family": "NFP", "label": "Apr 2025 Employment Situation"},
    {"date": "2025-05-07", "family": "FOMC", "label": "May 2025 FOMC decision"},
    {"date": "2025-05-13", "family": "CPI", "label": "Apr 2025 CPI"},
    {"date": "2025-06-06", "family": "NFP", "label": "May 2025 Employment Situation"},
    {"date": "2025-06-11", "family": "CPI", "label": "May 2025 CPI"},
    {"date": "2025-06-18", "family": "FOMC", "label": "Jun 2025 FOMC decision"},
    {"date": "2025-07-03", "family": "NFP", "label": "Jun 2025 Employment Situation"},
    {"date": "2025-07-15", "family": "CPI", "label": "Jun 2025 CPI"},
    {"date": "2025-07-30", "family": "FOMC", "label": "Jul 2025 FOMC decision"},
    {"date": "2025-08-01", "family": "NFP", "label": "Jul 2025 Employment Situation"},
    {"date": "2025-08-12", "family": "CPI", "label": "Jul 2025 CPI"},
    {"date": "2025-09-05", "family": "NFP", "label": "Aug 2025 Employment Situation"},
    {"date": "2025-09-11", "family": "CPI", "label": "Aug 2025 CPI"},
    {"date": "2025-09-17", "family": "FOMC", "label": "Sep 2025 FOMC decision"},
    {"date": "2025-10-03", "family": "NFP", "label": "Sep 2025 Employment Situation"},
    {"date": "2025-10-29", "family": "FOMC", "label": "Oct 2025 FOMC decision"},
    {"date": "2025-11-07", "family": "NFP", "label": "Oct 2025 Employment Situation"},
    {"date": "2025-12-05", "family": "NFP", "label": "Nov 2025 Employment Situation"},
    {"date": "2025-12-10", "family": "FOMC", "label": "Dec 2025 FOMC decision"},
    {"date": "2025-12-18", "family": "CPI", "label": "Nov 2025 CPI"},
    {"date": "2026-01-09", "family": "NFP", "label": "Dec 2025 Employment Situation"},
    {"date": "2026-01-13", "family": "CPI", "label": "Dec 2025 CPI"},
    {"date": "2026-01-28", "family": "FOMC", "label": "Jan 2026 FOMC decision"},
    {"date": "2026-02-06", "family": "NFP", "label": "Jan 2026 Employment Situation"},
    {"date": "2026-02-13", "family": "CPI", "label": "Jan 2026 CPI"},
    {"date": "2026-03-06", "family": "NFP", "label": "Feb 2026 Employment Situation"},
    {"date": "2026-03-11", "family": "CPI", "label": "Feb 2026 CPI"},
    {"date": "2026-03-18", "family": "FOMC", "label": "Mar 2026 FOMC decision"},
    {"date": "2026-04-03", "family": "NFP", "label": "Mar 2026 Employment Situation"},
    {"date": "2026-04-10", "family": "CPI", "label": "Mar 2026 CPI"},
    {"date": "2026-04-29", "family": "FOMC", "label": "Apr 2026 FOMC decision"},
    {"date": "2026-05-08", "family": "NFP", "label": "Apr 2026 Employment Situation"},
    {"date": "2026-05-12", "family": "CPI", "label": "Apr 2026 CPI"},
    {"date": "2026-06-05", "family": "NFP", "label": "May 2026 Employment Situation"},
    {"date": "2026-06-10", "family": "CPI", "label": "May 2026 CPI"},
    {"date": "2026-06-17", "family": "FOMC", "label": "Jun 2026 FOMC decision"},
    {"date": "2026-07-02", "family": "NFP", "label": "Jun 2026 Employment Situation"},
    {"date": "2026-07-14", "family": "CPI", "label": "Jun 2026 CPI"},
    {"date": "2026-07-29", "family": "FOMC", "label": "Jul 2026 FOMC decision"},
    {"date": "2026-08-07", "family": "NFP", "label": "Jul 2026 Employment Situation"},
    {"date": "2026-09-04", "family": "NFP", "label": "Aug 2026 Employment Situation"},
    {"date": "2026-09-11", "family": "CPI", "label": "Aug 2026 CPI"},
    {"date": "2026-09-16", "family": "FOMC", "label": "Sep 2026 FOMC decision"},
    {"date": "2026-10-02", "family": "NFP", "label": "Sep 2026 Employment Situation"},
    {"date": "2026-10-14", "family": "CPI", "label": "Sep 2026 CPI"},
    {"date": "2026-10-28", "family": "FOMC", "label": "Oct 2026 FOMC decision"},
    {"date": "2026-11-06", "family": "NFP", "label": "Oct 2026 Employment Situation"},
    {"date": "2026-11-10", "family": "CPI", "label": "Oct 2026 CPI"},
    {"date": "2026-12-04", "family": "NFP", "label": "Nov 2026 Employment Situation"},
    {"date": "2026-12-09", "family": "FOMC", "label": "Dec 2026 FOMC decision"},
    {"date": "2026-12-10", "family": "CPI", "label": "Nov 2026 CPI"},
]


def macro_events_on(date_iso: str) -> list[dict]:
    """Return all scheduled macro events on the given ISO date (YYYY-MM-DD)."""
    return [dict(event) for event in MACRO_EVENTS if event["date"] == date_iso]


def upcoming_macro_events(date_iso: str, horizon_days: int = 7) -> list[dict]:
    """Return events strictly after ``date_iso`` within ``horizon_days`` days."""
    start = date.fromisoformat(date_iso)
    end = start + timedelta(days=horizon_days)
    return [
        dict(event)
        for event in MACRO_EVENTS
        if start < date.fromisoformat(event["date"]) <= end
    ]


def calendar_coverage_end(family: str | None = None) -> str | None:
    """Latest date in the calendar, optionally for a single event family.

    Consumers should treat dates beyond this as "calendar not maintained",
    not as "no event scheduled".
    """
    dates = [
        event["date"]
        for event in MACRO_EVENTS
        if family is None or event["family"] == family
    ]
    return max(dates) if dates else None


def calendar_family_coverage() -> dict[str, str]:
    """Coverage end date per event family (NFP / CPI / FOMC)."""
    coverage: dict[str, str] = {}
    for event in MACRO_EVENTS:
        family = event["family"]
        if family not in coverage or event["date"] > coverage[family]:
            coverage[family] = event["date"]
    return coverage
