from __future__ import annotations

from datetime import date

import sec_filing_backfill as backfill
from sec_filing_backfill import parse_acceptance_datetime, parse_filing_rows, usable_trade_date


def test_usable_trade_date_is_next_weekday_after_acceptance():
    accepted = parse_acceptance_datetime("20260501173151")

    assert accepted.isoformat(timespec="seconds") == "2026-05-01T17:31:51"
    assert usable_trade_date(accepted, "2026-05-01") == "2026-05-04"


def test_parse_filing_rows_filters_forms_and_window():
    payload = {
        "cik": "320193",
        "filings": {
            "recent": {
                "form": ["8-K", "4", "10-Q/A"],
                "filingDate": ["2025-01-02", "2025-01-03", "2025-03-04"],
                "reportDate": ["2025-01-01", "", "2025-02-28"],
                "acceptanceDateTime": ["20250102153000", "20250103120000", "20250304170000"],
                "accessionNumber": ["0000320193-25-000001", "skip", "0000320193-25-000010"],
                "primaryDocument": ["a.htm", "b.htm", "q.htm"],
                "items": ["2.02,9.01", "", ""],
                "isXBRL": [0, 0, 1],
                "isInlineXBRL": [0, 0, 1],
            }
        },
    }

    rows = parse_filing_rows(
        payload,
        ticker="aapl",
        cik="320193",
        forms={"8-K", "10-Q/A"},
        start=date(2025, 1, 1),
        end=date(2025, 12, 31),
        pit_source="test",
    )

    assert [row["form_type"] for row in rows] == ["8-K", "10-Q/A"]
    assert rows[0]["ticker"] == "AAPL"
    assert rows[0]["cik"] == "0000320193"
    assert rows[0]["eight_k_item_codes"] == ["2.02", "9.01"]
    assert rows[0]["usable_trade_date"] == "2025-01-03"
    assert rows[1]["is_amendment"] is True
    assert rows[1]["archive_url"].endswith("/000032019325000010/q.htm")


def test_ticker_to_cik_map_falls_back_to_shared_reference(tmp_path, monkeypatch):
    monkeypatch.setattr(backfill, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        backfill,
        "load_company_ticker_map",
        lambda: {
            "0000320193": {"ticker": "AAPL", "cik": "0000320193"},
            "0000789019": {"ticker": "MSFT", "cik": "0000789019"},
        },
    )

    mapping = backfill._ticker_to_cik_map()

    assert mapping["AAPL"] == "0000320193"
    assert mapping["MSFT"] == "0000789019"
