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

import json
import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)

VALID_FAMILIES = {"NFP", "CPI", "FOMC"}

# Overlay rows (auto-fetched from official schedules by macro_events_refresh)
# may only ADD events strictly after this date — the day overlay support
# landed. Everything at or before it is hand-verified seed history that
# replay/experiment semantics depend on; automation must never touch it.
OVERLAY_MIN_DATE = "2026-06-10"

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


def overlay_path():
    """Path of the auto-maintained overlay file (data/reference/...)."""
    try:
        from data_paths import data_artifact_path
    except ImportError:  # pragma: no cover - package-style imports in tests
        from quant.data_paths import data_artifact_path
    return data_artifact_path("macro_events_overlay")


def _valid_overlay_row(row) -> bool:
    if not isinstance(row, dict):
        return False
    date_iso = row.get("date")
    if not isinstance(date_iso, str) or len(date_iso) != 10:
        return False
    try:
        date.fromisoformat(date_iso)
    except ValueError:
        return False
    if date_iso <= OVERLAY_MIN_DATE:
        return False
    return row.get("family") in VALID_FAMILIES and bool(row.get("label"))


def load_overlay_events(path=None) -> list[dict]:
    """Validated overlay rows; invalid/old rows are dropped (and logged)."""
    target = path if path is not None else overlay_path()
    try:
        with open(target, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError:
        return []
    except Exception as e:
        logger.warning("macro events overlay unreadable (%s) — ignoring", e)
        return []
    rows = payload.get("events", []) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    valid, seen = [], set()
    for row in rows:
        if not _valid_overlay_row(row):
            logger.warning("macro events overlay: dropping invalid row %r", row)
            continue
        key = (row["date"], row["family"])
        if key in seen:
            continue
        seen.add(key)
        valid.append({"date": row["date"], "family": row["family"],
                      "label": str(row["label"])})
    valid.sort(key=lambda r: (r["date"], r["family"]))
    return valid


def attach_overlay(path=None) -> int:
    """Merge overlay rows into MACRO_EVENTS in place (identity preserved).

    In-place mutation matters: the macro relief sleeve and several experiments
    hold references to this exact list object.
    """
    existing = {(e["date"], e["family"]) for e in MACRO_EVENTS}
    added = 0
    for row in load_overlay_events(path):
        key = (row["date"], row["family"])
        if key in existing:
            continue
        MACRO_EVENTS.append(row)
        existing.add(key)
        added += 1
    if added:
        MACRO_EVENTS.sort(key=lambda r: (r["date"], r["family"]))
    return added


try:
    attach_overlay()
except Exception as e:  # pragma: no cover - overlay must never break imports
    logger.warning("macro events overlay attach failed: %s", e)


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
