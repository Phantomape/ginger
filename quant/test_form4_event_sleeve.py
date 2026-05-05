import os
import sys


sys.path.insert(0, os.path.dirname(__file__))

from constants import ROUND_TRIP_COST_PCT  # noqa: E402
from form4_event_sleeve import (  # noqa: E402
    SLEEVE_NAME,
    build_form4_event_sleeve_snapshot,
    empty_form4_event_sleeve_state,
)


def _queue(*candidates):
    return {
        "candidate_count": len(candidates),
        "candidates": list(candidates),
        "data_source": {"status": "loaded", "path": "example.jsonl"},
    }


def _candidate(ticker="INTC", value=600_000.0, date="2026-05-04"):
    return {
        "ticker": ticker,
        "usable_trade_date": date,
        "total_purchase_value": value,
        "trade_enabled": False,
        "action": "observe_only",
    }


def test_form4_event_sleeve_is_default_off_and_opens_no_same_day_order():
    state = empty_form4_event_sleeve_state()
    snapshot = build_form4_event_sleeve_snapshot(
        form4_event_queue=_queue(_candidate()),
        as_of="2026-05-04",
        open_prices={"INTC": 30.0},
        current_prices={"INTC": 31.0},
        state=state,
        persist=False,
    )

    assert snapshot["enabled"] is False
    assert snapshot["trade_enabled"] is False
    assert snapshot["production_impact"]["alters_orders"] is False
    assert snapshot["candidate_count"] == 1
    assert snapshot["new_pending_count"] == 1
    assert snapshot["open_position_count"] == 0
    assert snapshot["pending_entries"][0]["trade_enabled"] is False


def test_form4_event_sleeve_fills_prior_pending_at_next_seen_open():
    first = build_form4_event_sleeve_snapshot(
        form4_event_queue=_queue(_candidate()),
        as_of="2026-05-04",
        open_prices={"INTC": 30.0},
        current_prices={"INTC": 31.0},
        state=empty_form4_event_sleeve_state(),
        persist=False,
    )
    state = {
        "schema_version": 1,
        "sleeve": SLEEVE_NAME,
        "pending_entries": first["pending_entries"],
        "open_positions": [],
        "closed_positions": [],
        "skipped_entries": [],
    }

    second = build_form4_event_sleeve_snapshot(
        form4_event_queue=_queue(),
        as_of="2026-05-05",
        open_prices={"INTC": 32.0},
        current_prices={"INTC": 33.0},
        state=state,
        persist=False,
    )

    assert second["filled_count"] == 1
    assert second["pending_count"] == 0
    assert second["open_position_count"] == 1
    position = second["open_positions"][0]
    assert position["entry_date"] == "2026-05-05"
    assert position["entry_price"] == 32.0
    assert position["trade_enabled"] is False


def test_form4_event_sleeve_closes_after_hold_days_with_cost():
    state = {
        "schema_version": 1,
        "sleeve": SLEEVE_NAME,
        "pending_entries": [],
        "open_positions": [
            {
                "decision_id": "paper-1",
                "sleeve": SLEEVE_NAME,
                "ticker": "INTC",
                "source_event_date": "2026-05-04",
                "entry_date": "2026-05-05",
                "entry_price": 100.0,
                "notional": 10_000.0,
                "shares": 100.0,
                "hold_days": 1,
                "observed_trading_days": 0,
                "last_seen_date": "2026-05-05",
                "trade_enabled": False,
                "paper_status": "open",
            }
        ],
        "closed_positions": [],
        "skipped_entries": [],
    }

    snapshot = build_form4_event_sleeve_snapshot(
        form4_event_queue=_queue(),
        as_of="2026-05-06",
        current_prices={"INTC": 110.0},
        state=state,
        config={"hold_days": 1},
        persist=False,
    )

    expected_pnl = round(10_000.0 * (0.10 - ROUND_TRIP_COST_PCT), 2)
    assert snapshot["closed_count_today"] == 1
    assert snapshot["open_position_count"] == 0
    assert snapshot["realized_pnl_to_date"] == expected_pnl
    assert snapshot["closed_positions_today"][0]["trade_enabled"] is False


def test_form4_event_sleeve_skips_fill_when_capacity_is_full():
    state = {
        "schema_version": 1,
        "sleeve": SLEEVE_NAME,
        "pending_entries": [
            {
                "decision_id": "paper-2",
                "sleeve": SLEEVE_NAME,
                "ticker": "MSFT",
                "created_asof": "2026-05-04",
                "source_event_date": "2026-05-04",
                "status": "pending_next_session_open",
                "candidate": _candidate("MSFT"),
                "trade_enabled": False,
            }
        ],
        "open_positions": [
            {
                "decision_id": "paper-1",
                "ticker": "INTC",
                "entry_date": "2026-05-04",
                "entry_price": 100.0,
                "notional": 10_000.0,
                "observed_trading_days": 0,
                "last_seen_date": "2026-05-04",
                "trade_enabled": False,
            }
        ],
        "closed_positions": [],
        "skipped_entries": [],
    }

    snapshot = build_form4_event_sleeve_snapshot(
        form4_event_queue=_queue(),
        as_of="2026-05-05",
        open_prices={"MSFT": 300.0},
        current_prices={"INTC": 101.0, "MSFT": 301.0},
        state=state,
        persist=False,
    )

    assert snapshot["filled_count"] == 0
    assert snapshot["skipped_count_today"] == 1
    assert snapshot["skipped_entries_today"][0]["status"] == "skipped_capacity_full"
