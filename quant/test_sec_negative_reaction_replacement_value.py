from __future__ import annotations

import pytest

from experiments.exp_20260504_011_sec_negative_reaction_replacement_value import (
    forward_return,
    summarize_snapshots,
)


def _row(date: str, open_price: float, close_price: float) -> dict[str, float | str]:
    return {"date": date, "open": open_price, "close": close_price}


def test_forward_return_uses_tenth_trading_day_close_and_costs() -> None:
    prices = {
        "SPY": [
            _row("2026-01-02", 100.0, 100.0),
            _row("2026-01-05", 100.0, 101.0),
            _row("2026-01-06", 100.0, 102.0),
        ],
        "AAA": [
            _row("2026-01-02", 100.0, 101.0),
            _row("2026-01-05", 101.0, 110.0),
            _row("2026-01-06", 110.0, 120.0),
        ],
    }

    result = forward_return(prices, "AAA", "2026-01-02", 2, round_trip_cost_pct=0.01)

    assert result is not None
    assert result["entry_date"] == "2026-01-02"
    assert result["exit_date"] == "2026-01-05"
    assert result["gross_return_pct"] == pytest.approx(10.0)
    assert result["net_return_pct"] == pytest.approx(8.9)
    assert result["net_excess_vs_spy_pct"] == pytest.approx(7.9)


def test_summarize_snapshots_keeps_replacement_counts_separate() -> None:
    snapshots = [
        {
            "status": "closed_primary_outcome",
            "capacity": {"capacity_state": "full_before_core_entries", "same_day_accepted_entries": 1, "slots_before_core_entries": 0},
            "candidate_primary_outcome": {"net_return_pct": 5.0, "net_excess_vs_spy_pct": 4.0},
            "replacement_value": {
                "vs_same_day_accepted_avg_spy_excess_pct": 2.0,
                "vs_active_slot_avg_spy_excess_pct": 1.5,
            },
        },
        {
            "status": "closed_primary_outcome",
            "capacity": {"capacity_state": "spare_slot_after_core_entries", "same_day_accepted_entries": 0, "slots_before_core_entries": 2},
            "candidate_primary_outcome": {"net_return_pct": -1.0, "net_excess_vs_spy_pct": -2.0},
            "replacement_value": {
                "vs_active_slot_avg_spy_excess_pct": -3.0,
            },
        },
    ]

    summary = summarize_snapshots(snapshots)

    assert summary["candidate_count"] == 2
    assert summary["same_day_accepted_conflict_count"] == 1
    assert summary["active_slot_full_count"] == 1
    assert summary["candidate_10d"]["avg_net_excess_vs_spy_pct"] == pytest.approx(1.0)
    assert summary["replacement_vs_same_day_accepted"]["avg_spy_excess"]["count"] == 1
    assert summary["replacement_vs_active_slots"]["avg_spy_excess"]["count"] == 2
