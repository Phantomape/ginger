"""Deterministic tests for the static-calendar staleness audit (fixed dates)."""

from calendar_audit import (
    audit_finra_publication_pins,
    audit_macro_events,
    audit_market_holidays,
    audit_static_calendars,
)

MACRO_AUDIT_FIXTURE = [
    {"date": "2026-06-05", "family": "NFP", "label": "May 2026 Employment Situation"},
    {"date": "2026-07-02", "family": "NFP", "label": "Jun 2026 Employment Situation"},
    {"date": "2026-08-07", "family": "NFP", "label": "Jul 2026 Employment Situation"},
    {"date": "2026-09-04", "family": "NFP", "label": "Aug 2026 Employment Situation"},
    {"date": "2026-10-02", "family": "NFP", "label": "Sep 2026 Employment Situation"},
    {"date": "2026-11-06", "family": "NFP", "label": "Oct 2026 Employment Situation"},
    {"date": "2026-12-04", "family": "NFP", "label": "Nov 2026 Employment Situation"},
    {"date": "2026-06-10", "family": "CPI", "label": "May 2026 CPI"},
    {"date": "2026-07-14", "family": "CPI", "label": "Jun 2026 CPI"},
    {"date": "2026-09-11", "family": "CPI", "label": "Aug 2026 CPI"},
    {"date": "2026-10-14", "family": "CPI", "label": "Sep 2026 CPI"},
    {"date": "2026-11-10", "family": "CPI", "label": "Oct 2026 CPI"},
    {"date": "2026-12-10", "family": "CPI", "label": "Nov 2026 CPI"},
    {"date": "2026-06-17", "family": "FOMC", "label": "Jun 2026 FOMC decision"},
    {"date": "2026-07-29", "family": "FOMC", "label": "Jul 2026 FOMC decision"},
    {"date": "2026-09-16", "family": "FOMC", "label": "Sep 2026 FOMC decision"},
    {"date": "2026-10-28", "family": "FOMC", "label": "Oct 2026 FOMC decision"},
    {"date": "2026-12-09", "family": "FOMC", "label": "Dec 2026 FOMC decision"},
]


def _by_severity(findings, severity):
    return [f for f in findings if f["severity"] == severity]


def test_macro_audit_flags_missing_future_cpi_month():
    findings = audit_macro_events("2026-06-10", events=MACRO_AUDIT_FIXTURE)
    gaps = _by_severity(findings, "gap")
    assert any(
        f["family"] == "CPI" and f["missing_month"] == "2026-08" for f in gaps
    ), gaps
    # NFP is fully covered month-by-month through December.
    assert not any(f["family"] == "NFP" for f in gaps)
    assert not _by_severity(findings, "stale")


def test_macro_audit_ignores_past_gaps():
    # Late-2025 CPI releases were genuinely irregular; auditing from Dec 2026
    # must not relitigate history (no months between today and coverage end).
    findings = audit_macro_events("2026-12-15", events=MACRO_AUDIT_FIXTURE)
    assert not any(
        f["severity"] == "gap" and f["missing_month"] < "2026-12" for f in findings
    )


def test_macro_audit_warns_before_coverage_runs_out():
    findings = audit_macro_events("2026-11-15", events=MACRO_AUDIT_FIXTURE)
    expiring = {f["family"] for f in _by_severity(findings, "expiring")}
    assert expiring == {"NFP", "CPI", "FOMC"}


def test_macro_audit_reports_stale_after_coverage_end():
    findings = audit_macro_events("2027-02-01", events=MACRO_AUDIT_FIXTURE)
    stale = {f["family"] for f in _by_severity(findings, "stale")}
    assert stale == {"NFP", "CPI", "FOMC"}


def test_holiday_audit_current_then_expiring_then_stale():
    from datetime import date

    fixed = {date(2027, 1, 1), date(2027, 12, 24)}  # coverage through 2027
    assert audit_market_holidays("2026-06-10", holidays=fixed) == []
    expiring = audit_market_holidays("2027-12-01", holidays=fixed)
    assert len(expiring) == 1 and expiring[0]["severity"] == "expiring"
    stale = audit_market_holidays("2028-01-05", holidays=fixed)
    assert len(stale) == 1 and stale[0]["severity"] == "stale"


def test_holiday_audit_live_set_extends_through_next_year():
    # The sleeve's set is rule-extended through (current year + 1) at import,
    # so the live audit must be clean today.
    from datetime import date as _date

    assert audit_market_holidays(_date.today().isoformat()) == []


def test_finra_pins_info_after_last_pin_only():
    assert audit_finra_publication_pins("2026-04-01") == []
    info = audit_finra_publication_pins("2026-06-10")
    assert len(info) == 1 and info[0]["severity"] == "info"
    assert "7-business-day" in info[0]["message"]


def test_combined_audit_orders_severities():
    findings = audit_static_calendars("2026-06-10")
    severities = [f["severity"] for f in findings]
    order = {"error": 0, "stale": 1, "gap": 2, "expiring": 3, "info": 4}
    assert severities == sorted(severities, key=order.__getitem__)
    # Live macro overlay may fill earlier gaps; the FINRA pin info line remains.
    assert "info" in severities
