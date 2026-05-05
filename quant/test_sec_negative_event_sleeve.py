from __future__ import annotations

import pytest

from sec_negative_event_sleeve import (
    build_sec_negative_event_sleeve_snapshot,
    empty_sec_negative_event_sleeve_state,
)


def _queue(*candidates: dict[str, object]) -> dict[str, object]:
    return {
        "queue_name": "SEC_NEGATIVE_REACTION_FORWARD_QUEUE",
        "enabled": False,
        "candidate_count": len(candidates),
        "data_source": {"status": "loaded"},
        "candidates": list(candidates),
    }


def _candidate(
    ticker: str = "LITE",
    accession: str = "0001",
    reaction: float = -0.03,
    date: str = "2026-05-04",
) -> dict[str, object]:
    return {
        "ticker": ticker,
        "usable_trade_date": date,
        "accession_number": accession,
        "language_bucket": "negative_language",
        "reaction_excess_return": reaction,
        "trade_enabled": False,
    }


def _state_from_snapshot(snapshot: dict[str, object]) -> dict[str, object]:
    state = empty_sec_negative_event_sleeve_state()
    state["pending_entries"] = list(snapshot.get("pending_entries") or [])
    state["open_positions"] = list(snapshot.get("open_positions") or [])
    state["closed_positions"] = list(snapshot.get("closed_positions") or [])
    state["skipped_entries"] = list(snapshot.get("skipped_entries") or [])
    return state


def test_sec_negative_sleeve_freezes_pending_then_paper_fills_and_closes() -> None:
    first = build_sec_negative_event_sleeve_snapshot(
        sec_event_queue=_queue(_candidate()),
        as_of="2026-05-04",
        state=empty_sec_negative_event_sleeve_state(),
        config={"hold_days": 1},
        persist=False,
    )

    assert first["enabled"] is False
    assert first["trade_enabled"] is False
    assert first["new_pending_count"] == 1
    assert first["pending_count"] == 1
    assert first["open_position_count"] == 0
    assert first["production_impact"]["alters_orders"] is False

    second = build_sec_negative_event_sleeve_snapshot(
        sec_event_queue=_queue(),
        as_of="2026-05-05",
        open_prices={"LITE": 100.0},
        current_prices={"LITE": 101.0},
        state=_state_from_snapshot(first),
        config={"hold_days": 1},
        persist=False,
    )

    assert second["filled_count"] == 1
    assert second["open_position_count"] == 1
    assert second["open_positions"][0]["trade_enabled"] is False

    third = build_sec_negative_event_sleeve_snapshot(
        sec_event_queue=_queue(),
        as_of="2026-05-06",
        current_prices={"LITE": 110.0},
        state=_state_from_snapshot(second),
        config={"hold_days": 1},
        persist=False,
    )

    assert third["closed_count_today"] == 1
    assert third["open_position_count"] == 0
    assert third["realized_pnl_to_date"] == pytest.approx(965.0)
    assert third["closed_positions_today"][0]["trade_enabled"] is False


def test_sec_negative_sleeve_prioritizes_most_negative_pending_when_capacity_full() -> None:
    first = build_sec_negative_event_sleeve_snapshot(
        sec_event_queue=_queue(
            _candidate("LOW", "0001", -0.01),
            _candidate("HIGH", "0002", -0.05),
        ),
        as_of="2026-05-04",
        state=empty_sec_negative_event_sleeve_state(),
        persist=False,
    )
    second = build_sec_negative_event_sleeve_snapshot(
        sec_event_queue=_queue(),
        as_of="2026-05-05",
        open_prices={"LOW": 20.0, "HIGH": 30.0},
        current_prices={"LOW": 20.0, "HIGH": 30.0},
        state=_state_from_snapshot(first),
        persist=False,
    )

    assert second["filled_count"] == 1
    assert second["open_positions"][0]["ticker"] == "HIGH"
    assert second["skipped_count_today"] == 1
    assert second["skipped_entries_today"][0]["ticker"] == "LOW"


def test_sec_negative_sleeve_deduplicates_existing_decision_ids() -> None:
    first = build_sec_negative_event_sleeve_snapshot(
        sec_event_queue=_queue(_candidate()),
        as_of="2026-05-04",
        state=empty_sec_negative_event_sleeve_state(),
        persist=False,
    )
    repeated = build_sec_negative_event_sleeve_snapshot(
        sec_event_queue=_queue(_candidate()),
        as_of="2026-05-04",
        state=_state_from_snapshot(first),
        persist=False,
    )

    assert repeated["new_pending_count"] == 0
    assert repeated["pending_count"] == 1


def test_report_generator_renders_sec_negative_sleeve_without_orders() -> None:
    from report_generator import generate_daily_report

    snapshot = build_sec_negative_event_sleeve_snapshot(
        sec_event_queue=_queue(_candidate()),
        as_of="2026-05-04",
        state=empty_sec_negative_event_sleeve_state(),
        persist=False,
    )
    report = generate_daily_report(
        signals=[],
        market_regime={"regime": "BULL"},
        sec_negative_event_sleeve=snapshot,
    )

    assert "SEC NEGATIVE-REACTION PAPER EVENT SLEEVE" in report
    assert "Trade enabled: False" in report
    assert "Pending: 1" in report
