"""Focused tests for staleness-triggered FTD/FINRA archive refresh (exp-20260612-003)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import finra_iwm_paper_sleeve as finra
import sec_ftd_finra_paper_sleeve as sec


def _finra_row(ticker, settlement, short_interest=1000):
    return {
        "ticker": ticker,
        "settlement_date": settlement,
        "publication_date": settlement,
        "usable_trade_date": settlement,
        "short_interest": short_interest,
        "days_to_cover": 4.0,
    }


def _ftd_row(ticker, settlement, shares=5000):
    return {
        "ticker": ticker,
        "settlement_date": settlement,
        "usable_trade_date": settlement,
        "pit_safe": True,
        "ftd_shares": shares,
        "ftd_price": 10.0,
        "ftd_notional": shares * 10.0,
    }


def test_finra_fresh_archive_skips_fetch():
    calls = []
    rows, status, _ = finra.refresh_finra_short_interest_archive(
        existing_rows=[_finra_row("AAA", "2026-06-01")],
        tickers={"AAA"},
        as_of="2026-06-11",
        fetch_fn=lambda **kw: calls.append(kw) or ([], []),
        save=False,
    )
    assert status == "local_archive_fresh"
    assert not calls
    assert len(rows) == 1


def test_finra_stale_archive_merges_new_rows():
    fetched = [_finra_row("AAA", "2026-05-29"), _finra_row("AAA", "2026-04-30", 999)]
    rows, status, _ = finra.refresh_finra_short_interest_archive(
        existing_rows=[_finra_row("AAA", "2026-04-30")],
        tickers={"AAA"},
        as_of="2026-06-11",
        fetch_fn=lambda **kw: (list(fetched), []),
        save=False,
    )
    assert status == "local_archive_refreshed"
    settlements = sorted(str(r["settlement_date"]) for r in rows)
    assert settlements == ["2026-04-30", "2026-05-29"]


def test_finra_stale_archive_fetch_empty_keeps_existing():
    rows, status, _ = finra.refresh_finra_short_interest_archive(
        existing_rows=[_finra_row("AAA", "2026-04-30")],
        tickers={"AAA"},
        as_of="2026-06-11",
        fetch_fn=lambda **kw: ([], []),
        save=False,
    )
    assert status == "local_archive_stale_refresh_empty"
    assert len(rows) == 1


def test_ftd_stale_archive_merges_and_audit_dates_trigger():
    # Audit state: archive frozen at 2026-05-14, as_of 2026-06-11 = 28 days stale.
    fetched = [_ftd_row("BBB", "2026-05-29")]
    rows, status, _ = sec.refresh_sec_ftd_archive(
        existing_rows=[_ftd_row("BBB", "2026-05-14")],
        tickers={"BBB"},
        as_of="2026-06-11",
        fetch_fn=lambda **kw: (list(fetched), []),
        save=False,
    )
    assert status == "local_archive_refreshed"
    assert sorted(str(r["settlement_date"]) for r in rows) == ["2026-05-14", "2026-05-29"]


def test_ftd_empty_archive_uses_full_fetch_path():
    fetched = [_ftd_row("BBB", "2026-06-01")]
    rows, status, _ = sec.refresh_sec_ftd_archive(
        existing_rows=[],
        tickers={"BBB"},
        as_of="2026-06-11",
        fetch_fn=lambda **kw: (list(fetched), []),
        save=False,
    )
    assert status == "network_fetch"
    assert len(rows) == 1


def test_ftd_refresh_lookback_is_bounded():
    seen = {}
    sec.refresh_sec_ftd_archive(
        existing_rows=[_ftd_row("BBB", "2026-05-14")],
        tickers={"BBB"},
        as_of="2026-06-11",
        fetch_fn=lambda **kw: seen.update(kw) or ([], []),
        save=False,
    )
    assert seen["lookback_days"] <= 28 + 75
