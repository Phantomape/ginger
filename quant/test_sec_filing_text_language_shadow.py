from __future__ import annotations

from experiments.exp_20260504_007_sec_filing_text_language_shadow import (
    evaluate_price,
    language_features,
    semantic_text,
)


def test_semantic_text_keeps_exhibit_and_primary_only() -> None:
    row = {
        "primary_document": "abc-8k.htm",
        "combined_text": (
            "DOCUMENT ex99-1.htm Record revenue and strong demand. "
            "DOCUMENT abc-8k.htm Item 2.02 furnished exhibit. "
            "DOCUMENT abc-index-headers.html SEC header noise. "
            "DOCUMENT R1.htm XBRL cover page noise."
        ),
    }

    text = semantic_text(row)

    assert "Record revenue" in text
    assert "furnished exhibit" in text
    assert "SEC header noise" not in text
    assert "XBRL cover page noise" not in text


def test_language_features_classifies_deferred_operational_update() -> None:
    row = {
        "primary_document": "abc-8k.htm",
        "combined_text": (
            "DOCUMENT ex991.htm Production, deliveries and deployments. "
            "We produced approximately 1,000 units. Financial results will be announced next month. "
            "DOCUMENT abc-8k.htm Item 2.02."
        ),
    }

    features = language_features(row)

    assert features["text_event_type"] == "deferred_results_or_operational_update"
    assert features["language_bucket"] == "deferred_or_operational"


def test_language_features_scores_positive_earnings_language() -> None:
    row = {
        "primary_document": "abc-8k.htm",
        "combined_text": (
            "DOCUMENT ex99-1.htm ABC announces financial results. "
            "Record revenue, strong demand, margin expansion, and free cash flow exceeded expectations."
        ),
    }

    features = language_features(row)

    assert features["text_event_type"] == "earnings_release_text"
    assert features["language_bucket"] == "positive_language"
    assert features["language_score"] >= 2


def test_evaluate_price_enters_after_reaction_close() -> None:
    event = {
        "ticker": "ABC",
        "usable_trade_date": "2025-01-03",
        "language_bucket": "positive_language",
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
    assert row["reaction_excess_return"] == 0.039505
    assert row["horizons"]["5d"]["status"] == "valid"
