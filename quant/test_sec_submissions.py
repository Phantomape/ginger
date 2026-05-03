from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent))

from sec_submissions import parse_recent_filings  # noqa: E402
from experiments.exp_20260503_006_filing_shadow_universe_scout import (  # noqa: E402
    build_latest_event_pool,
    evaluate_forward_event,
)


def test_parse_recent_filings_filters_forms_and_keeps_accession():
    payload = {
        "cik": "123",
        "filings": {
            "recent": {
                "form": ["8-K", "4", "10-Q"],
                "filingDate": ["2025-01-02", "2025-01-03", "2025-02-04"],
                "accessionNumber": ["0000000123-25-000001", "skip", "0000000123-25-000010"],
                "primaryDocument": ["a.htm", "b.htm", "q.htm"],
                "reportDate": ["2025-01-01", "", "2025-01-31"],
            }
        },
    }

    rows = parse_recent_filings(payload, ticker="abc", max_filings=5)

    assert [row["filing_type"] for row in rows] == ["8-K", "10-Q"]
    assert rows[0]["ticker"] == "ABC"
    assert rows[0]["cik"] == "0000000123"
    assert rows[0]["accession_number"] == "0000000123-25-000001"
    assert rows[0]["archive_url"].endswith("/000000012325000001/a.htm")


def test_parse_recent_filings_allows_missing_ticker():
    payload = {
        "cik": "456",
        "filings": {
            "recent": {
                "form": ["10-K"],
                "filingDate": ["2025-03-01"],
                "accessionNumber": ["0000000456-25-000001"],
                "primaryDocument": ["k.htm"],
            }
        },
    }

    rows = parse_recent_filings(payload)

    assert rows[0]["ticker"] is None
    assert rows[0]["cik"] == "0000000456"


def test_evaluate_forward_event_marks_insufficient_future_rows_pending():
    event = {"ticker": "ABC", "filing_date": "2025-01-01"}
    ticker_rows = [
        {"date": "2025-01-02", "close": 10.0, "volume": 1000},
        {"date": "2025-01-03", "close": 11.0, "volume": 1000},
        {"date": "2025-01-06", "close": 12.0, "volume": 1000},
    ]
    spy_rows = [
        {"date": "2025-01-02", "close": 100.0, "volume": 1000},
        {"date": "2025-01-03", "close": 101.0, "volume": 1000},
        {"date": "2025-01-06", "close": 102.0, "volume": 1000},
    ]

    result = evaluate_forward_event(event, ticker_rows, spy_rows, horizons=(5,))

    assert result["price_status"] == "covered"
    assert result["horizons"]["5d"]["status"] == "pending"


def test_latest_event_pool_tags_current_universe_without_mutating_it():
    universe = {"TSLA"}
    news_items = [
        {
            "source": "sec",
            "title": "10-K/A - Tesla, Inc. (0001318605) (Filer)",
            "url": "https://example.test/tsla",
            "published_at": "2026-05-02T00:00:00",
            "tickers": ["TSLA"],
            "sec_cik": "0001318605",
            "filing_type": "10-K",
            "source_metadata": {"sec_ticker": "TSLA"},
        },
        {
            "source": "sec",
            "title": "8-K - Example Corp (0000000001) (Filer)",
            "url": "https://example.test/abcd",
            "published_at": "2026-05-02T00:00:00",
            "tickers": ["ABCD"],
            "sec_cik": "0000000001",
            "filing_type": "8-K",
            "source_metadata": {"sec_ticker": "ABCD"},
        },
    ]

    pool = build_latest_event_pool(news_items, date_key="20260502", universe=universe)

    assert universe == {"TSLA"}
    assert len(pool) == 2
    assert {row["ticker"]: row["in_current_universe"] for row in pool} == {
        "ABCD": False,
        "TSLA": True,
    }
