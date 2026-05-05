from __future__ import annotations

from sec_companyfacts_backfill import iter_selected_fact_rows


def test_iter_selected_fact_rows_normalizes_selected_concepts() -> None:
    payload = {
        "entityName": "Example Co",
        "facts": {
            "us-gaap": {
                "Revenues": {
                    "units": {
                        "USD": [
                            {
                                "start": "2025-01-01",
                                "end": "2025-03-31",
                                "val": 100.0,
                                "accn": "0000000000-25-000001",
                                "fy": 2025,
                                "fp": "Q1",
                                "form": "10-Q",
                                "filed": "2025-04-20",
                                "frame": "CY2025Q1",
                            },
                            {
                                "start": "2023-01-01",
                                "end": "2023-03-31",
                                "val": 50.0,
                                "accn": "old",
                                "fy": 2023,
                                "fp": "Q1",
                                "form": "10-Q",
                                "filed": "2023-04-20",
                            },
                        ],
                    },
                },
                "EarningsPerShareDiluted": {
                    "units": {
                        "USD/shares": [
                            {
                                "start": "2025-01-01",
                                "end": "2025-03-31",
                                "val": 1.23,
                                "accn": "0000000000-25-000001",
                                "fy": 2025,
                                "fp": "Q1",
                                "form": "10-Q",
                                "filed": "2025-04-20",
                            },
                        ],
                    },
                },
                "Assets": {
                    "units": {
                        "USD": [
                            {
                                "end": "2025-03-31",
                                "val": 500.0,
                                "accn": "0000000000-25-000001",
                                "fy": 2025,
                                "fp": "Q1",
                                "form": "10-Q",
                                "filed": "2025-04-20",
                            },
                        ],
                    },
                },
                "CommonStocksIncludingAdditionalPaidInCapital": {
                    "units": {
                        "USD": [
                            {
                                "end": "2025-03-31",
                                "val": 1.0,
                                "form": "10-Q",
                                "filed": "2025-04-20",
                            },
                        ],
                    },
                },
            },
        },
    }

    rows = iter_selected_fact_rows(
        payload,
        ticker="ABC",
        cik="123",
        forms={"10-Q"},
        min_period_end="2024-01-01",
        max_filed="2025-12-31",
    )

    assert sorted(row["canonical"] for row in rows) == ["assets", "eps_diluted", "revenue"]
    revenue = [row for row in rows if row["canonical"] == "revenue"][0]
    assert revenue["ticker"] == "ABC"
    assert revenue["cik"] == "0000000123"
    assert revenue["duration_days"] == 90
    assert revenue["accession_number"] == "0000000000-25-000001"


def test_iter_selected_fact_rows_filters_forms_and_filed_dates() -> None:
    payload = {
        "facts": {
            "us-gaap": {
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            {
                                "start": "2025-01-01",
                                "end": "2025-03-31",
                                "val": 10.0,
                                "form": "10-Q",
                                "filed": "2025-04-15",
                            },
                            {
                                "start": "2025-01-01",
                                "end": "2025-03-31",
                                "val": 11.0,
                                "form": "10-Q",
                                "filed": "2026-01-01",
                            },
                            {
                                "start": "2025-01-01",
                                "end": "2025-03-31",
                                "val": 12.0,
                                "form": "S-1",
                                "filed": "2025-04-15",
                            },
                        ],
                    },
                },
            },
        },
    }

    rows = iter_selected_fact_rows(
        payload,
        ticker="ABC",
        cik="123",
        forms={"10-Q"},
        min_period_end="2024-01-01",
        max_filed="2025-12-31",
    )

    assert len(rows) == 1
    assert rows[0]["value"] == 10.0
