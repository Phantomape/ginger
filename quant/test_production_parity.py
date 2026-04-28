import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

from production_parity import (  # noqa: E402
    build_followthrough_addon_actions,
    plan_entry_candidates,
)


def _ohlcv(closes):
    idx = pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"][:len(closes)])
    return pd.DataFrame(
        {
            "Open": closes,
            "High": closes,
            "Low": closes,
            "Close": closes,
            "Volume": [1_000_000] * len(closes),
        },
        index=idx,
    )


def test_plan_entry_candidates_defers_breakouts_when_slots_are_scarce():
    open_positions = {"positions": [{"ticker": "MSFT", "shares": 10}]}
    signals = [
        {"ticker": "AAPL", "strategy": "breakout_long"},
        {"ticker": "NVDA", "strategy": "trend_long"},
    ]

    planned, plan = plan_entry_candidates(
        signals,
        open_positions,
        max_positions=2,
        defer_breakout_when_slots_lte=1,
    )

    assert [s["ticker"] for s in planned] == ["NVDA"]
    assert [s["ticker"] for s in plan["deferred_breakout_signals"]] == ["AAPL"]
    assert plan["available_slots"] == 1


def test_build_followthrough_addon_actions_emits_day_two_add():
    open_positions = {
        "positions": [
            {
                "ticker": "NVDA",
                "shares": 10,
                "original_shares": 10,
                "avg_cost": 100.0,
                "entry_date": "2026-01-02",
            }
        ]
    }
    ohlcv = {
        "NVDA": _ohlcv([100.0, 101.0, 104.0]),
        "SPY": _ohlcv([100.0, 100.0, 101.0]),
    }

    actions, audit = build_followthrough_addon_actions(
        open_positions=open_positions,
        ohlcv_dict=ohlcv,
        portfolio_value=10_000,
        current_prices={"NVDA": 104.0},
    )

    assert len(actions) == 1
    assert actions[0]["ticker"] == "NVDA"
    assert actions[0]["shares_to_buy"] == 5
    assert actions[0]["fill_timing"] == "next_session_open"
    assert any(row["status"] == "eligible" for row in audit)
