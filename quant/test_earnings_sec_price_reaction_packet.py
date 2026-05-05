from __future__ import annotations

from experiments.exp_20260504_002_earnings_sec_price_reaction_packet import (
    build_earnings_events,
    dedupe_event_packets,
    evaluate_event,
    match_sec_filings,
)


def test_build_earnings_events_uses_trading_day_dte() -> None:
    trading_dates = [
        "2025-10-23",
        "2025-10-24",
        "2025-10-27",
        "2025-10-28",
        "2025-10-29",
    ]
    snapshots = {
        "2025-10-23": {
            "ABC": {
                "days_to_earnings": 3,
                "eps_estimate": 1.0,
                "eps_actual_last": 0.8,
                "avg_historical_surprise_pct": 4.0,
            },
        },
        "2025-10-24": {
            "ABC": {
                "days_to_earnings": 2,
                "eps_estimate": 1.1,
                "eps_actual_last": 0.8,
                "avg_historical_surprise_pct": 5.0,
            },
        },
        "2025-10-29": {
            "ABC": {
                "days_to_earnings": 0,
                "eps_estimate": 1.1,
                "eps_actual_last": 1.3,
                "avg_historical_surprise_pct": 5.0,
            },
        },
    }

    events = build_earnings_events(snapshots, trading_dates, start="2025-10-23", end="2025-10-29")

    assert len(events) == 2
    first = events[0]
    assert first["event_date"] == "2025-10-28"
    assert first["source_snapshot_date"] == "2025-10-24"
    assert first["pre_event_snapshot_count"] == 2
    assert first["post_event_eps_actual"] == 1.3
    assert first["eps_surprise_pct"] == 18.1818


def test_match_sec_filings_categorizes_results_8k() -> None:
    trading_dates = [
        "2025-01-02",
        "2025-01-03",
        "2025-01-06",
        "2025-01-07",
        "2025-01-08",
        "2025-01-09",
        "2025-01-10",
        "2025-01-13",
        "2025-01-14",
        "2025-01-15",
        "2025-01-16",
        "2025-01-17",
        "2025-01-21",
    ]
    event = {"ticker": "ABC", "event_date": "2025-01-02"}
    sec_by_ticker = {
        "ABC": [
            {
                "ticker": "ABC",
                "usable_trade_date": "2025-01-03",
                "form_base": "8-K",
                "form_type": "8-K",
                "eight_k_item_codes": ["2.02", "9.01"],
                "accession_number": "one",
            },
            {
                "ticker": "ABC",
                "usable_trade_date": "2025-01-10",
                "form_base": "10-Q",
                "form_type": "10-Q",
                "eight_k_item_codes": [],
                "accession_number": "two",
            },
            {
                "ticker": "ABC",
                "usable_trade_date": "2025-01-10",
                "form_base": "8-K",
                "form_type": "8-K",
                "eight_k_item_codes": ["8.01"],
                "accession_number": "outside_8k_window",
            },
        ],
    }

    result = match_sec_filings(event, sec_by_ticker, trading_dates)

    assert result["sec_packet_type"] == "results_8k"
    assert result["has_results_8k"] is True
    assert result["has_periodic_10q_10k"] is True
    assert result["sec_match_count"] == 2
    assert result["eight_k_item_codes"] == ["2.02", "9.01"]


def test_evaluate_event_enters_after_reaction_close() -> None:
    event = {
        "ticker": "ABC",
        "event_date": "2025-01-02",
        "sec_usable_trade_dates": ["2025-01-03"],
        "avg_historical_surprise_pct": 5.0,
        "eps_surprise_pct": 12.0,
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

    row = evaluate_event(event, snapshot, [item["date"] for item in snapshot["SPY"]])

    assert row["price_status"] == "covered"
    assert row["reaction_date"] == "2025-01-03"
    assert row["entry_date"] == "2025-01-06"
    assert row["reaction_bucket"] == "positive_excess_ge_2pct"
    assert row["avg_hist_surprise_bucket"] == "avg_hist_surprise_3_to_10pct"
    assert row["current_surprise_bucket"] == "current_surprise_ge_10pct"
    assert row["horizons"]["5d"]["status"] == "valid"


def test_dedupe_event_packets_collapses_same_sec_shock() -> None:
    rows = [
        {
            "ticker": "ABC",
            "event_date": "2025-01-02",
            "source_snapshot_date": "2024-12-24",
            "days_to_earnings": 6,
            "shock_trade_date": "2025-01-03",
            "reaction_date": "2025-01-03",
            "price_status": "covered",
            "sec_packet_type": "results_8k",
            "sec_accessions": ["one"],
        },
        {
            "ticker": "ABC",
            "event_date": "2025-01-03",
            "source_snapshot_date": "2025-01-02",
            "days_to_earnings": 1,
            "shock_trade_date": "2025-01-03",
            "reaction_date": "2025-01-03",
            "price_status": "covered",
            "sec_packet_type": "results_8k",
            "sec_accessions": ["one"],
        },
    ]

    deduped, summary = dedupe_event_packets(rows)

    assert len(deduped) == 1
    assert deduped[0]["event_date"] == "2025-01-03"
    assert deduped[0]["deduped_from_event_count"] == 2
    assert summary["duplicate_packet_rows_removed"] == 1
