from __future__ import annotations

from sec_filing_features import build_filing_feature_rows


def test_filing_features_do_not_treat_period_end_as_tradable_date() -> None:
    rows = build_filing_feature_rows(
        [
            {
                "ticker": "ACME",
                "form_type": "10-Q",
                "period_end_date": "2026-03-31",
                "accession_number": "0001-26-000001",
            }
        ],
        [],
    )

    assert rows[0]["pit_safe"] is False
    assert rows[0]["event_date"] is None
    assert "missing_accepted_datetime" in rows[0]["gap_reasons"]
    assert "missing_usable_trade_date" in rows[0]["gap_reasons"]


def test_filing_features_derive_same_accession_financial_shock_fields() -> None:
    filings = [
        {
            "ticker": "ACME",
            "form_type": "10-Q",
            "accession_number": "0001-26-000010",
            "accepted_at": "2026-04-20T17:05:00",
            "usable_trade_date": "2026-04-21",
        }
    ]
    facts = [
        _fact("ACME", "0001-26-000010", "revenue", 100.0, "2026-03-31", "2026-04-20"),
        _fact("ACME", "0001-26-000010", "gross_profit", 40.0, "2026-03-31", "2026-04-20"),
        _fact("ACME", "0001-26-000010", "operating_cash_flow", 30.0, "2026-03-31", "2026-04-20"),
        _fact("ACME", "0001-26-000010", "capex", 5.0, "2026-03-31", "2026-04-20"),
        _fact("ACME", "0001-26-000010", "net_income", 20.0, "2026-03-31", "2026-04-20"),
        _fact("ACME", "0001-26-000010", "inventory", 12.0, "2026-03-31", "2026-04-20"),
        _fact("ACME", "0001-26-000010", "receivables", 15.0, "2026-03-31", "2026-04-20"),
        _fact("ACME", "0001-25-000099", "revenue", 80.0, "2025-12-31", "2026-01-20"),
        _fact("ACME", "0001-25-000099", "gross_profit", 24.0, "2025-12-31", "2026-01-20"),
        _fact("ACME", "0001-25-000099", "inventory", 10.0, "2025-12-31", "2026-01-20"),
        _fact("ACME", "0001-25-000099", "receivables", 10.0, "2025-12-31", "2026-01-20"),
    ]

    row = build_filing_feature_rows(filings, facts)[0]

    assert row["pit_safe"] is True
    assert row["fiscal_period_end"] == "2026-03-31"
    assert row["gross_margin_delta"] == 0.1
    assert row["fcf_to_net_income_gap"] == 0.25
    assert row["inventory_growth"] == 0.2
    assert row["receivables_growth"] == 0.5
    assert row["field_availability"]["same_accession_facts"] == "derived"
    assert row["eps_surprise"] is None
    assert row["revenue_surprise"] is None


def _fact(ticker: str, accession: str, canonical: str, value: float, end: str, filed: str) -> dict:
    return {
        "ticker": ticker,
        "accession_number": accession,
        "canonical": canonical,
        "value": value,
        "end": end,
        "filed": filed,
    }
