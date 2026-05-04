from __future__ import annotations

from pathlib import Path

from form4_event_queue import (
    FORWARD_QUEUE_MIN_PURCHASE_VALUE,
    aggregate_purchase_events,
    build_form4_event_queue,
    build_forward_queue_from_transactions,
    qualifies_forward_queue_event,
)


def _row(**overrides):
    row = {
        "ticker": "INTC",
        "usable_trade_date": "2026-05-04",
        "open_market_purchase_flag": True,
        "transaction_value": 300_000.0,
        "10b5_1_flag": False,
        "option_exercise_flag": False,
        "owner_name": "Example Director",
        "issuer_name": "Intel Corp.",
        "issuer_trading_symbol": "INTC",
        "is_officer": False,
        "is_director": True,
        "is_10pct_owner": False,
        "officer_title": None,
        "accession_number": "0001",
        "owner_cik": "123",
        "archive_url": "https://www.sec.gov/example",
    }
    row.update(overrides)
    return row


def test_aggregate_purchase_events_sums_event_day_and_marks_forward_candidate():
    events = aggregate_purchase_events([
        _row(transaction_value=300_000.0, accession_number="0001", owner_cik="123"),
        _row(transaction_value=250_000.0, accession_number="0002", owner_cik="456"),
    ])

    assert len(events) == 1
    event = events[0]
    assert event["total_purchase_value"] == 550_000.0
    assert event["meaningful_purchase_v1"] is True
    assert event["form4_forward_queue_candidate"] is True
    assert qualifies_forward_queue_event(event) is True


def test_10b5_1_flag_blocks_forward_queue_candidate():
    events = aggregate_purchase_events([
        _row(transaction_value=FORWARD_QUEUE_MIN_PURCHASE_VALUE + 1, **{"10b5_1_flag": True}),
    ])

    assert events[0]["meaningful_purchase_v1"] is False
    assert qualifies_forward_queue_event(events[0]) is False


def test_build_form4_event_queue_is_default_off_and_same_day_only():
    events = aggregate_purchase_events([
        _row(transaction_value=600_000.0, ticker="INTC", usable_trade_date="2026-05-04"),
        _row(transaction_value=900_000.0, ticker="MSFT", usable_trade_date="2026-05-05"),
    ])
    queue = build_form4_event_queue(
        events,
        as_of="2026-05-04",
        core_signals=[{"ticker": "NVDA", "strategy": "trend_long", "confidence_score": 0.91}],
    )

    assert queue["enabled"] is False
    assert queue["candidate_count"] == 1
    assert queue["candidates"][0]["ticker"] == "INTC"
    assert queue["candidates"][0]["trade_enabled"] is False
    assert queue["production_impact"]["alters_orders"] is False
    alternatives = queue["candidates"][0]["counterfactual"]["alternatives"]
    assert alternatives[0]["ticker"] == "NVDA"
    assert alternatives[1]["type"] == "cash"


def test_build_forward_queue_from_transactions_handles_missing_source(tmp_path: Path):
    queue = build_forward_queue_from_transactions(
        data_dir=tmp_path,
        as_of="2026-05-04",
        core_signals=[],
    )

    assert queue["enabled"] is False
    assert queue["candidate_count"] == 0
    assert queue["data_source"]["status"] == "missing_form4_transactions_jsonl"
