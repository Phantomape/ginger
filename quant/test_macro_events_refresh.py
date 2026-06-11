"""Offline tests for the macro event calendar auto-refresh (fixture sources)."""

import json

import macro_events
from macro_events_refresh import (
    parse_bls_schedule_dates,
    parse_fomc_decision_days,
    refresh_macro_events_overlay,
)

BLS_FIXTURE = """
<html><body><table>
<tr><td>Consumer Price Index for July 2026</td><td>Aug. 12, 2026</td><td>08:30 AM</td></tr>
<tr><td>Consumer Price Index for August 2026</td><td>Sep. 11, 2026</td><td>08:30 AM</td></tr>
<tr><td>Consumer Price Index for September 2026</td><td>October 14, 2026</td><td>08:30 AM</td></tr>
</table>
<p>Last Modified Date: June 1, 2026</p>
</body></html>
"""

FED_FIXTURE = """
<html><body>
<h4>2026 FOMC Meetings</h4>
<div>June 16-17</div>
<div>July 28-29</div>
<div>October 27-28</div>
<h4>2027 FOMC Meetings</h4>
<div>January 26-27</div>
<div>April 27-28</div>
</body></html>
"""


def test_bls_parser_extracts_release_dates_and_skips_footer():
    dates = parse_bls_schedule_dates(BLS_FIXTURE)
    assert dates == ["2026-08-12", "2026-09-11", "2026-10-14"]
    assert "2026-06-01" not in dates  # 'Last Modified' footer excluded


def test_fomc_parser_takes_decision_day_per_year_section():
    days = parse_fomc_decision_days(FED_FIXTURE)
    assert "2026-06-17" in days
    assert "2026-07-29" in days
    assert "2027-01-27" in days
    assert "2027-04-28" in days


def _fake_http_get(url, timeout=30):
    if "bls.gov" in url:
        return BLS_FIXTURE
    if "federalreserve.gov" in url:
        return FED_FIXTURE
    raise RuntimeError(f"unexpected url {url}")


def test_refresh_appends_only_new_future_dates(tmp_path, monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    overlay = tmp_path / "macro_events_overlay.json"
    before_rows = list(macro_events.MACRO_EVENTS)
    seeded_rows = [
        row for row in before_rows
        if row["date"] <= "2026-12-10" and (row["date"], row["family"]) != ("2026-08-12", "CPI")
    ]
    try:
        macro_events.MACRO_EVENTS[:] = seeded_rows
        summary = refresh_macro_events_overlay(
            "2026-06-10", path=overlay, http_get=_fake_http_get, force=True
        )
        assert summary["status"] == "refreshed"
        payload = json.loads(overlay.read_text(encoding="utf-8"))
        keys = {(e["date"], e["family"]) for e in payload["events"]}
        # New: the Aug 2026 CPI gap gets filled from the official page.
        assert ("2026-08-12", "CPI") in keys
        # Already in the hand-verified seed -> NOT duplicated into overlay.
        assert ("2026-09-11", "CPI") not in keys
        assert ("2026-06-17", "FOMC") not in keys
        # Future-year FOMC accumulates.
        assert ("2027-01-27", "FOMC") in keys
        # In-memory list was extended in place (identity preserved).
        assert len(macro_events.MACRO_EVENTS) == len(seeded_rows) + summary["added"]
        import macro_relief_leadership_paper_sleeve as sleeve
        assert sleeve.MACRO_EVENTS is macro_events.MACRO_EVENTS
        assert macro_events.macro_events_on("2026-08-12")
    finally:
        # Restore the shared module-level list exactly (it is sorted after
        # attach, so truncation would drop the wrong rows).
        macro_events.MACRO_EVENTS[:] = before_rows


def test_refresh_is_throttled_by_fetched_at(tmp_path, monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    overlay = tmp_path / "macro_events_overlay.json"
    before_rows = list(macro_events.MACRO_EVENTS)
    try:
        first = refresh_macro_events_overlay(
            "2026-06-10", path=overlay, http_get=_fake_http_get
        )
        assert first["status"] == "refreshed"
        calls = []

        def counting_get(url, timeout=30):
            calls.append(url)
            return _fake_http_get(url)

        second = refresh_macro_events_overlay(
            "2026-06-10", path=overlay, http_get=counting_get
        )
        assert second["status"] == "fresh"
        assert calls == []  # within TTL -> no network at all
    finally:
        macro_events.MACRO_EVENTS[:] = before_rows


def test_refresh_total_failure_changes_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    overlay = tmp_path / "macro_events_overlay.json"
    before = list(macro_events.MACRO_EVENTS)

    def broken_get(url, timeout=30):
        raise RuntimeError("network down")

    summary = refresh_macro_events_overlay(
        "2026-06-10", path=overlay, http_get=broken_get, force=True
    )
    assert summary["status"] == "failed"
    assert not overlay.exists()
    assert macro_events.MACRO_EVENTS == before


def test_overlay_loader_rejects_history_and_garbage(tmp_path):
    overlay = tmp_path / "overlay.json"
    overlay.write_text(json.dumps({"events": [
        {"date": "2026-04-10", "family": "CPI", "label": "history rewrite"},
        {"date": "2026-08-12", "family": "CPI", "label": "ok"},
        {"date": "not-a-date", "family": "CPI", "label": "bad"},
        {"date": "2026-09-30", "family": "PMI", "label": "unknown family"},
        {"date": "2026-08-12", "family": "CPI", "label": "duplicate"},
    ]}), encoding="utf-8")
    rows = macro_events.load_overlay_events(overlay)
    assert rows == [{"date": "2026-08-12", "family": "CPI", "label": "ok"}]
