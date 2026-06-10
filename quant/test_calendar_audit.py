"""Deterministic tests for the static-calendar staleness audit (fixed dates)."""

from calendar_audit import (
    audit_finra_publication_pins,
    audit_macro_events,
    audit_market_holidays,
    audit_static_calendars,
)


def _by_severity(findings, severity):
    return [f for f in findings if f["severity"] == severity]


def test_macro_audit_flags_missing_future_cpi_month():
    findings = audit_macro_events("2026-06-10")
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
    findings = audit_macro_events("2026-12-15")
    assert not any(
        f["severity"] == "gap" and f["missing_month"] < "2026-12" for f in findings
    )


def test_macro_audit_warns_before_coverage_runs_out():
    findings = audit_macro_events("2026-11-15")
    expiring = {f["family"] for f in _by_severity(findings, "expiring")}
    assert expiring == {"NFP", "CPI", "FOMC"}


def test_macro_audit_reports_stale_after_coverage_end():
    findings = audit_macro_events("2027-02-01")
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
    # Today's known facts: the Aug 2026 CPI gap and the FINRA pin info line.
    assert "gap" in severities and "info" in severities
