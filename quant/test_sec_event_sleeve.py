from __future__ import annotations

import pytest

from sec_event_sleeve import (
    build_sec_event_sleeve_snapshot,
    empty_sec_event_sleeve_state,
)


def _queue() -> dict[str, object]:
    return {
        "queue_name": "SEC_GOVERNANCE_PROCEDURAL_FORWARD_QUEUE",
        "enabled": False,
        "candidate_count": 1,
        "data_source": {"status": "loaded"},
        "candidates": [
            {
                "ticker": "CRDO",
                "usable_trade_date": "2026-05-04",
                "accession_number": "0002",
                "target_cell": "shareholder_vote|negative_excess_0_to_minus_2pct",
                "reaction_excess_return": -0.01,
                "trade_enabled": False,
            }
        ],
    }


def _state_from_snapshot(snapshot: dict[str, object]) -> dict[str, object]:
    state = empty_sec_event_sleeve_state()
    state["pending_entries"] = list(snapshot.get("pending_entries") or [])
    state["open_positions"] = list(snapshot.get("open_positions") or [])
    state["closed_positions"] = list(snapshot.get("closed_positions") or [])
    state["skipped_entries"] = list(snapshot.get("skipped_entries") or [])
    return state


def test_sec_event_sleeve_freezes_pending_then_paper_fills_and_closes() -> None:
    first = build_sec_event_sleeve_snapshot(
        sec_event_queue=_queue(),
        as_of="2026-05-04",
        state=empty_sec_event_sleeve_state(),
        config={"hold_days": 1},
        persist=False,
    )

    assert first["trade_enabled"] is False
    assert first["new_pending_count"] == 1
    assert first["pending_count"] == 1
    assert first["production_impact"]["alters_orders"] is False

    second = build_sec_event_sleeve_snapshot(
        sec_event_queue={"candidate_count": 0, "candidates": [], "data_source": {"status": "loaded"}},
        as_of="2026-05-05",
        open_prices={"CRDO": 100.0},
        current_prices={"CRDO": 101.0},
        state=_state_from_snapshot(first),
        config={"hold_days": 1},
        persist=False,
    )

    assert second["filled_count"] == 1
    assert second["open_position_count"] == 1
    assert second["open_positions"][0]["trade_enabled"] is False

    third = build_sec_event_sleeve_snapshot(
        sec_event_queue={"candidate_count": 0, "candidates": [], "data_source": {"status": "loaded"}},
        as_of="2026-05-06",
        current_prices={"CRDO": 110.0},
        state=_state_from_snapshot(second),
        config={"hold_days": 1},
        persist=False,
    )

    assert third["closed_count_today"] == 1
    assert third["open_position_count"] == 0
    assert third["realized_pnl_to_date"] == pytest.approx(965.0)
    assert third["closed_positions_today"][0]["trade_enabled"] is False


def test_sec_event_sleeve_ignores_stale_price_dates() -> None:
    first = build_sec_event_sleeve_snapshot(
        sec_event_queue=_queue(),
        as_of="2026-05-04",
        state=empty_sec_event_sleeve_state(),
        config={"hold_days": 1},
        persist=False,
    )
    state = _state_from_snapshot(first)
    state["open_positions"] = [
        {
            "decision_id": "open-crdo",
            "ticker": "CRDO",
            "entry_date": "2026-05-04",
            "entry_price": 100.0,
            "notional": 10_000.0,
            "observed_trading_days": 0,
            "last_seen_date": "2026-05-04",
            "trade_enabled": False,
        }
    ]

    snapshot = build_sec_event_sleeve_snapshot(
        sec_event_queue={"candidate_count": 0, "candidates": [], "data_source": {"status": "loaded"}},
        as_of="2026-05-05",
        open_prices={"CRDO": 100.0},
        current_prices={"CRDO": 110.0},
        open_price_dates={"CRDO": "2026-05-04"},
        current_price_dates={"CRDO": "2026-05-04"},
        state=state,
        config={"hold_days": 1, "max_positions": 2},
        persist=False,
    )

    assert snapshot["filled_count"] == 0
    assert snapshot["closed_count_today"] == 0
    assert snapshot["pending_count"] == 1
    assert snapshot["open_position_count"] == 1
    assert snapshot["open_positions"][0]["observed_trading_days"] == 0


def test_sec_event_sleeve_deduplicates_existing_decision_ids() -> None:
    first = build_sec_event_sleeve_snapshot(
        sec_event_queue=_queue(),
        as_of="2026-05-04",
        state=empty_sec_event_sleeve_state(),
        persist=False,
    )
    repeated = build_sec_event_sleeve_snapshot(
        sec_event_queue=_queue(),
        as_of="2026-05-04",
        state=_state_from_snapshot(first),
        persist=False,
    )

    assert repeated["new_pending_count"] == 0
    assert repeated["pending_count"] == 1
