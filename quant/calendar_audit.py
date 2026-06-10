"""Staleness audit for the repo's static, hand-maintained calendars.

Several production-adjacent modules carry hardcoded date tables that silently
go stale (the class of bug where "no event today" really means "nobody updated
the table"):

  - quant/macro_events.py        MACRO_EVENTS (NFP / CPI / FOMC release days)
  - quant/finra_iwm_paper_sleeve US_MARKET_HOLIDAYS (drives business-day math)
  - quant/finra_iwm_paper_sleeve PUBLICATION_OVERRIDES (verification pins; the
    sleeve falls back to the 7-business-day rule beyond them, which stays
    correct only while US_MARKET_HOLIDAYS is current)

This module turns silent expiry into explicit findings. It is read-only and
advisory: consumed by the intraday risk review's DATA QUALITY section and by
tests. It never changes any calendar or trading behavior.
"""

from __future__ import annotations

from datetime import date, timedelta

try:
    from macro_events import MACRO_EVENTS, calendar_family_coverage
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.macro_events import MACRO_EVENTS, calendar_family_coverage

# Families with a release every calendar month — a missing future month means
# a maintenance gap, not "no event scheduled". FOMC meets ~8x/year on an
# irregular schedule, so month-gap logic does not apply to it.
MONTHLY_FAMILIES = ("NFP", "CPI")

# Start warning this many days before a calendar's coverage runs out.
DEFAULT_WARN_AHEAD_DAYS = 45


def _finding(calendar: str, severity: str, message: str, **extra) -> dict:
    return {"calendar": calendar, "severity": severity, "message": message, **extra}


def _month_key(date_iso: str) -> tuple[int, int]:
    return int(date_iso[:4]), int(date_iso[5:7])


def _iter_months(start: tuple[int, int], end: tuple[int, int]):
    year, month = start
    while (year, month) <= end:
        yield year, month
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)


def audit_macro_events(today_iso: str, warn_ahead_days: int = DEFAULT_WARN_AHEAD_DAYS) -> list[dict]:
    findings: list[dict] = []
    today = date.fromisoformat(today_iso)
    horizon = today + timedelta(days=warn_ahead_days)

    coverage = calendar_family_coverage()
    for family in sorted(coverage):
        end = date.fromisoformat(coverage[family])
        if end < today:
            findings.append(_finding(
                "macro_events", "stale",
                f"{family} coverage ended {coverage[family]} — update "
                "quant/macro_events.py from the official schedule",
                family=family, coverage_end=coverage[family],
            ))
        elif end <= horizon:
            findings.append(_finding(
                "macro_events", "expiring",
                f"{family} coverage ends {coverage[family]} "
                f"({(end - today).days}d away) — refill soon",
                family=family, coverage_end=coverage[family],
            ))

    # Missing-month detection, future months only: past gaps can be genuine
    # history (e.g. delayed releases), future gaps are maintenance bugs.
    for family in MONTHLY_FAMILIES:
        months_with_release = {
            _month_key(e["date"]) for e in MACRO_EVENTS if e["family"] == family
        }
        if not months_with_release:
            continue
        last_covered = max(months_with_release)
        current_month = (today.year, today.month)
        for year, month in _iter_months(current_month, last_covered):
            if (year, month) not in months_with_release:
                findings.append(_finding(
                    "macro_events", "gap",
                    f"{family} has no scheduled release recorded for "
                    f"{year}-{month:02d} although coverage extends past it — "
                    "verify against the official schedule",
                    family=family, missing_month=f"{year}-{month:02d}",
                ))
    return findings


def audit_market_holidays(
    today_iso: str,
    warn_ahead_days: int = DEFAULT_WARN_AHEAD_DAYS,
    holidays=None,
) -> list[dict]:
    """Coverage check for the market holiday set.

    The set is rule-generated through next year at import time
    (quant/market_calendar.py), so findings here indicate the generator or
    its wiring regressed — not a routine data-entry chore.
    """
    if holidays is None:
        try:
            from finra_iwm_paper_sleeve import US_MARKET_HOLIDAYS as holidays
        except ImportError:  # pragma: no cover
            try:
                from quant.finra_iwm_paper_sleeve import (
                    US_MARKET_HOLIDAYS as holidays,
                )
            except Exception as e:
                return [_finding("us_market_holidays", "error",
                                 f"could not load US_MARKET_HOLIDAYS: {e}")]
        except Exception as e:  # pragma: no cover - defensive
            return [_finding("us_market_holidays", "error",
                             f"could not load US_MARKET_HOLIDAYS: {e}")]

    today = date.fromisoformat(today_iso)
    last_year = max(d.year for d in holidays)
    coverage_end = date(last_year, 12, 31)
    if coverage_end < today:
        return [_finding(
            "us_market_holidays", "stale",
            f"market holiday coverage ends {last_year} — the rule-generated "
            "extension in finra_iwm_paper_sleeve / market_calendar is not "
            "working; business-day math will treat holidays as trading days",
            coverage_end=str(coverage_end),
        )]
    if coverage_end <= today + timedelta(days=warn_ahead_days):
        return [_finding(
            "us_market_holidays", "expiring",
            f"market holiday coverage ends {last_year} — auto-extension "
            "should already cover next year; check market_calendar wiring",
            coverage_end=str(coverage_end),
        )]
    return []


def audit_finra_publication_pins(today_iso: str) -> list[dict]:
    """Informational: where verified FINRA publication pins end.

    Beyond the last pin the sleeve falls back to the labeled
    7-business-day rule (every existing pin equals that rule's output), which
    stays correct while US_MARKET_HOLIDAYS is current — so this is "info",
    not "stale", unless the holiday calendar itself is stale.
    """
    try:
        from finra_iwm_paper_sleeve import PUBLICATION_OVERRIDES
    except ImportError:  # pragma: no cover
        try:
            from quant.finra_iwm_paper_sleeve import PUBLICATION_OVERRIDES
        except Exception as e:
            return [_finding("finra_publication_overrides", "error",
                             f"could not load PUBLICATION_OVERRIDES: {e}")]
    except Exception as e:  # pragma: no cover - defensive
        return [_finding("finra_publication_overrides", "error",
                         f"could not load PUBLICATION_OVERRIDES: {e}")]

    last_settlement = max(PUBLICATION_OVERRIDES)
    if date.fromisoformat(today_iso) > last_settlement:
        return [_finding(
            "finra_publication_overrides", "info",
            f"verified FINRA publication pins end at settlement "
            f"{last_settlement} — later cycles use the labeled "
            "7-business-day rule fallback (fine while the holiday calendar "
            "is current; pin new dates from finra.org when convenient)",
            coverage_end=str(last_settlement),
        )]
    return []


def audit_static_calendars(today_iso: str, warn_ahead_days: int = DEFAULT_WARN_AHEAD_DAYS) -> list[dict]:
    """All static-calendar findings, ordered stale > gap > expiring > info."""
    findings = (
        audit_macro_events(today_iso, warn_ahead_days)
        + audit_market_holidays(today_iso, warn_ahead_days)
        + audit_finra_publication_pins(today_iso)
    )
    order = {"error": 0, "stale": 1, "gap": 2, "expiring": 3, "info": 4}
    findings.sort(key=lambda f: order.get(f["severity"], 9))
    return findings
