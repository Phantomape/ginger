from __future__ import annotations

from experiments.exp_20260504_004_companyfacts_financial_quality_shadow import (
    evaluate_price,
    quality_features,
    select_current_fact,
)


def _fact(
    canonical: str,
    value: float,
    *,
    ticker: str = "ABC",
    end: str = "2025-03-31",
    filed: str = "2025-04-20",
    duration_days: int | None = 90,
    accession_number: str = "current",
    unit: str = "USD",
) -> dict:
    return {
        "ticker": ticker,
        "canonical": canonical,
        "value": value,
        "end": end,
        "filed": filed,
        "duration_days": duration_days,
        "accession_number": accession_number,
        "unit": unit,
    }


def test_select_current_fact_prefers_quarter_duration_for_10q() -> None:
    rows = [
        _fact("revenue", 300.0, duration_days=180),
        _fact("revenue", 120.0, duration_days=90),
    ]

    selected = select_current_fact(rows, "revenue", "10-Q")

    assert selected is not None
    assert selected["value"] == 120.0


def test_quality_features_scores_high_quality_packet() -> None:
    current_rows = [
        _fact("revenue", 120.0),
        _fact("gross_profit", 60.0),
        _fact("operating_income", 30.0),
        _fact("net_income", 20.0),
        _fact("eps_diluted", 2.0, unit="USD/shares"),
        _fact("operating_cash_flow", 25.0),
        _fact("capex", 5.0),
        _fact("inventory", 10.0, duration_days=None),
        _fact("receivables", 12.0, duration_days=None),
    ]
    prior_rows = [
        _fact("revenue", 100.0, end="2024-03-31", filed="2024-04-20", accession_number="prior"),
        _fact("gross_profit", 45.0, end="2024-03-31", filed="2024-04-20", accession_number="prior"),
        _fact("operating_income", 20.0, end="2024-03-31", filed="2024-04-20", accession_number="prior"),
        _fact("net_income", 10.0, end="2024-03-31", filed="2024-04-20", accession_number="prior"),
        _fact("eps_diluted", 1.0, end="2024-03-31", filed="2024-04-20", accession_number="prior", unit="USD/shares"),
        _fact("operating_cash_flow", 15.0, end="2024-03-31", filed="2024-04-20", accession_number="prior"),
        _fact("capex", 5.0, end="2024-03-31", filed="2024-04-20", accession_number="prior"),
        _fact("inventory", 9.0, end="2024-03-31", filed="2024-04-20", accession_number="prior", duration_days=None),
        _fact("receivables", 11.0, end="2024-03-31", filed="2024-04-20", accession_number="prior", duration_days=None),
    ]
    by_ticker_canonical = {}
    for row in current_rows + prior_rows:
        by_ticker_canonical.setdefault((row["ticker"], row["canonical"]), []).append(row)

    result = quality_features(current_rows, by_ticker_canonical, form_base="10-Q")

    assert result["financial_quality_bucket"] == "high_quality"
    assert result["financial_quality_score"] >= 3
    assert result["financial_metrics"]["revenue_yoy"] == 0.2
    assert result["financial_metrics"]["gross_margin_delta"] == 0.05


def test_evaluate_price_enters_after_reaction_close() -> None:
    event = {
        "ticker": "ABC",
        "usable_trade_date": "2025-01-03",
        "financial_quality_bucket": "high_quality",
    }
    snapshot = {
        "ABC": [
            {"date": "2025-01-02", "open": 100.0, "close": 100.0, "volume": 1000.0},
            {"date": "2025-01-03", "open": 101.0, "close": 106.0, "volume": 1000.0},
            {"date": "2025-01-06", "open": 107.0, "close": 108.0, "volume": 1000.0},
            {"date": "2025-01-07", "open": 108.0, "close": 109.0, "volume": 1000.0},
            {"date": "2025-01-08", "open": 109.0, "close": 110.0, "volume": 1000.0},
            {"date": "2025-01-09", "open": 110.0, "close": 111.0, "volume": 1000.0},
            {"date": "2025-01-10", "open": 111.0, "close": 112.0, "volume": 1000.0},
            {"date": "2025-01-13", "open": 112.0, "close": 113.0, "volume": 1000.0},
        ],
        "SPY": [
            {"date": "2025-01-02", "open": 100.0, "close": 100.0, "volume": 1000.0},
            {"date": "2025-01-03", "open": 100.0, "close": 101.0, "volume": 1000.0},
            {"date": "2025-01-06", "open": 101.0, "close": 101.0, "volume": 1000.0},
            {"date": "2025-01-07", "open": 101.0, "close": 101.0, "volume": 1000.0},
            {"date": "2025-01-08", "open": 101.0, "close": 101.0, "volume": 1000.0},
            {"date": "2025-01-09", "open": 101.0, "close": 101.0, "volume": 1000.0},
            {"date": "2025-01-10", "open": 101.0, "close": 101.0, "volume": 1000.0},
            {"date": "2025-01-13", "open": 101.0, "close": 101.0, "volume": 1000.0},
        ],
    }

    row = evaluate_price(event, snapshot, "test")

    assert row["price_status"] == "covered"
    assert row["reaction_date"] == "2025-01-03"
    assert row["entry_date"] == "2025-01-06"
    assert row["horizons"]["5d"]["status"] == "valid"
