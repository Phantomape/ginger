from __future__ import annotations

from sec_event_queue import build_sec_leadership_change_queue
from sec_leadership_event_sleeve import (
    SLEEVE_NAME,
    build_sec_leadership_event_sleeve_snapshot,
    empty_sec_leadership_event_sleeve_state,
)


def _row(**overrides):
    row = {
        "status": "ok",
        "ticker": "CEOX",
        "accession_number": "0003",
        "form_type": "8-K",
        "filing_date": "2026-05-04",
        "usable_trade_date": "2026-05-04",
        "accepted_at": "2026-05-04T16:30:00",
        "eight_k_item_codes": ["5.02", "9.01"],
        "primary_document": "ceox-20260504.htm",
        "index_url": "https://www.sec.gov/example",
        "combined_text": "Departure of directors or certain officers. A new CEO was appointed.",
    }
    row.update(overrides)
    return row


def _ohlcv(open_price: float, close_price: float):
    return [{"date": "2026-05-04", "open": open_price, "close": close_price}]


def test_sec_leadership_event_sleeve_is_default_off_paper_only(tmp_path):
    queue = build_sec_leadership_change_queue(
        [_row()],
        as_of="2026-05-04",
        ohlcv_by_ticker={"CEOX": _ohlcv(100.0, 96.0)},
        spy_ohlcv=_ohlcv(100.0, 100.0),
    )
    state = empty_sec_leadership_event_sleeve_state()

    first = build_sec_leadership_event_sleeve_snapshot(
        sec_leadership_event_queue=queue,
        as_of="2026-05-04",
        open_prices={"CEOX": 96.0},
        current_prices={"CEOX": 96.0},
        state=state,
        persist=True,
        state_path=tmp_path / "state.json",
        snapshot_log_path=tmp_path / "snapshots.jsonl",
    )

    assert first["sleeve"] == SLEEVE_NAME
    assert first["paper_enabled"] is True
    assert first["trade_enabled"] is False
    assert first["candidate_count"] == 1
    assert first["new_pending_count"] == 1
    assert first["pending_count"] == 1
    assert first["open_position_count"] == 0
    assert first["production_impact"]["alters_orders"] is False

    second = build_sec_leadership_event_sleeve_snapshot(
        sec_leadership_event_queue={"candidates": [], "candidate_count": 0},
        as_of="2026-05-05",
        open_prices={"CEOX": 97.0},
        current_prices={"CEOX": 98.0},
        persist=True,
        state_path=tmp_path / "state.json",
        snapshot_log_path=tmp_path / "snapshots.jsonl",
    )

    assert second["filled_count"] == 1
    assert second["pending_count"] == 0
    assert second["open_position_count"] == 1
    assert second["open_positions"][0]["trade_enabled"] is False


def test_sec_leadership_event_sleeve_ignores_stale_price_dates():
    queue = build_sec_leadership_change_queue(
        [_row()],
        as_of="2026-05-04",
        ohlcv_by_ticker={"CEOX": _ohlcv(100.0, 96.0)},
        spy_ohlcv=_ohlcv(100.0, 100.0),
    )
    state = empty_sec_leadership_event_sleeve_state()
    first = build_sec_leadership_event_sleeve_snapshot(
        sec_leadership_event_queue=queue,
        as_of="2026-05-04",
        state=state,
        persist=False,
    )
    next_state = empty_sec_leadership_event_sleeve_state()
    next_state["pending_entries"] = first["pending_entries"]
    next_state["open_positions"] = [
        {
            "decision_id": "open-ceox",
            "ticker": "CEOX",
            "entry_date": "2026-05-04",
            "entry_price": 100.0,
            "notional": 10_000.0,
            "observed_trading_days": 0,
            "last_seen_date": "2026-05-04",
            "trade_enabled": False,
        }
    ]

    snapshot = build_sec_leadership_event_sleeve_snapshot(
        sec_leadership_event_queue={"candidates": [], "candidate_count": 0},
        as_of="2026-05-05",
        open_prices={"CEOX": 97.0},
        current_prices={"CEOX": 110.0},
        open_price_dates={"CEOX": "2026-05-04"},
        current_price_dates={"CEOX": "2026-05-04"},
        state=next_state,
        config={"hold_days": 1, "max_positions": 2},
        persist=False,
    )

    assert snapshot["filled_count"] == 0
    assert snapshot["closed_count_today"] == 0
    assert snapshot["pending_count"] == 1
    assert snapshot["open_position_count"] == 1
    assert snapshot["open_positions"][0]["observed_trading_days"] == 0
