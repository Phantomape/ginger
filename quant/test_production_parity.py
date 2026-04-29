import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

from production_parity import (  # noqa: E402
    build_followthrough_addon_actions,
    classify_entry_open_cancel,
    filter_entry_signal_candidates,
    plan_entry_candidates,
)
import backtester  # noqa: E402
import constants  # noqa: E402


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
    assert plan["signals_after_deferral"] == 1


def test_plan_entry_candidates_accepts_backtester_position_count():
    signals = [
        {"ticker": "AAPL", "strategy": "trend_long"},
        {"ticker": "NVDA", "strategy": "trend_long"},
    ]

    planned, plan = plan_entry_candidates(
        signals,
        open_positions=None,
        max_positions=3,
        active_positions_count=2,
    )

    assert [s["ticker"] for s in planned] == ["AAPL"]
    assert [s["ticker"] for s in plan["slot_sliced_signals"]] == ["NVDA"]
    assert plan["available_slots"] == 1


def test_filter_entry_signal_candidates_matches_shared_entry_gates():
    open_positions = {"positions": [{"ticker": "HELD", "shares": 10}]}
    signals = [
        {"ticker": "HELD", "sector": "Technology", "trade_quality_score": 0.95},
        {"ticker": "A", "sector": "Technology", "trade_quality_score": 0.95},
        {"ticker": "B", "sector": "Technology", "trade_quality_score": 0.90},
        {"ticker": "C", "sector": "Technology", "trade_quality_score": 0.85},
        {"ticker": "D", "sector": "Healthcare", "trade_quality_score": 0.80},
        {"ticker": "E", "sector": "Commodities", "trade_quality_score": 0.70},
    ]

    filtered, audit = filter_entry_signal_candidates(
        signals,
        open_positions=open_positions,
        market_regime="BEAR",
        spy_pct_from_ma=-0.03,
        qqq_pct_from_ma=-0.04,
        max_per_sector=2,
    )

    assert [s["ticker"] for s in filtered] == ["D"]
    assert [s["ticker"] for s in audit["already_held_dropped"]] == ["HELD"]
    assert [s["ticker"] for s in audit["sector_cap_dropped"]] == ["C"]
    assert [s["ticker"] for s in audit["bear_shallow_dropped"]] == ["A", "B", "E"]
    assert audit["bear_shallow_active"] is True


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


def test_classify_entry_open_cancel_uses_shared_gap_rules():
    assert classify_entry_open_cancel(
        102.0,
        100.0,
        stop_price=95.0,
        upside_gap_cancel_pct=0.015,
    ) == "gap_cancel"
    assert classify_entry_open_cancel(
        97.9,
        100.0,
        stop_price=95.0,
        upside_gap_cancel_pct=0.015,
        adverse_gap_cancel_pct=0.02,
    ) == "adverse_gap_down_cancel"
    assert classify_entry_open_cancel(
        94.9,
        100.0,
        stop_price=95.0,
        upside_gap_cancel_pct=0.015,
        adverse_gap_cancel_pct=None,
    ) == "stop_breach_cancel"


def test_backtester_addon_and_slot_defaults_share_constants():
    shared_keys = [
        "MAX_POSITION_PCT",
        "MAX_PER_SECTOR",
        "ADVERSE_GAP_CANCEL_PCT",
        "ADDON_ENABLED",
        "ADDON_CHECKPOINT_DAYS",
        "ADDON_MIN_UNREALIZED_PCT",
        "ADDON_MIN_RS_VS_SPY",
        "ADDON_FRACTION_OF_ORIGINAL_SHARES",
        "ADDON_MAX_POSITION_PCT",
        "SECOND_ADDON_ENABLED",
        "SECOND_ADDON_CHECKPOINT_DAYS",
        "SECOND_ADDON_MIN_UNREALIZED_PCT",
        "SECOND_ADDON_MIN_RS_VS_SPY",
        "SECOND_ADDON_FRACTION_OF_ORIGINAL_SHARES",
        "SECOND_ADDON_MAX_POSITION_PCT",
        "DEFER_BREAKOUT_WHEN_SLOTS_LTE",
        "DEFER_BREAKOUT_MAX_MIN_INDEX_PCT_FROM_MA",
    ]

    for key in shared_keys:
        assert backtester.DEFAULT_CONFIG[key] == getattr(constants, key)
