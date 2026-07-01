import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

from production_parity import (  # noqa: E402
    TRAILING_PARTIAL_REDUCE_ENABLED,
    build_entry_candidate_review,
    build_early_relative_weakness_exit_actions,
    build_followthrough_addon_actions,
    build_slot_accounting_summary,
    cap_followthrough_addon_shares,
    classify_entry_open_cancel,
    count_core_strategy_positions,
    filter_entry_signal_candidates,
    partial_reduce_shares,
    plan_entry_candidates,
    position_consumes_core_slot,
    production_trailing_stop_price,
    risk_pct_for_market_state,
    suggested_reduce_pct_for_rules,
)
import backtester  # noqa: E402
import constants  # noqa: E402
import production_parity  # noqa: E402
from portfolio_engine import size_signals  # noqa: E402
from risk_engine import enrich_signals  # noqa: E402
from report_generator import generate_daily_report  # noqa: E402


def _ohlcv(closes):
    idx = pd.bdate_range("2026-01-02", periods=len(closes))
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


def _feature_row(price_vs_200ma, momentum_20d=0.10, momentum_60d=0.20):
    return {
        "atr": 5.0,
        "trend_score": 0.8,
        "volume_spike_ratio": 1.5,
        "momentum_10d_pct": 0.05,
        "momentum_20d_pct": momentum_20d,
        "momentum_60d_pct": momentum_60d,
        "price_vs_200ma_pct": price_vs_200ma,
        "signal_day_ticker_open_close_return_pct": 0.01,
    }


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


def test_slot_accounting_counts_only_core_strategy_positions():
    open_positions = {
        "positions": [
            {"ticker": "NVDA", "shares": 10, "opened_by_strategy": "legacy"},
            {"ticker": "AMD", "shares": 5, "opened_by_strategy": "breakout_long"},
            {"ticker": "COHR", "shares": 3, "opened_by_strategy": "pilot_breakout_long"},
            {"ticker": "RKLB", "shares": 7, "opened_by_strategy": "fomo"},
            {"ticker": "CASH", "shares": 0, "opened_by_strategy": "trend_long"},
        ]
    }

    summary = build_slot_accounting_summary(open_positions, max_positions=5)

    assert count_core_strategy_positions(open_positions) == 1
    assert summary["live_active_positions"] == 4
    assert summary["live_available_slots"] == 1
    assert summary["strategy_active_positions"] == 1
    assert summary["strategy_available_slots"] == 4
    assert [row["ticker"] for row in summary["core_strategy_positions"]] == ["AMD"]
    assert [
        row["ticker"]
        for row in summary["non_strategy_positions_ignored_for_strategy_slots"]
    ] == ["NVDA", "COHR", "RKLB"]
    assert summary["capacity_policy"] == "core_strategy_slots_only"
    assert summary["core_slot_active_positions"] == 1
    assert summary["total_account_active_positions"] == 4


def test_core_slot_policy_honors_explicit_sleeve_and_slot_policy():
    assert position_consumes_core_slot(
        {"ticker": "AAPL", "shares": 1, "sleeve": "core"}
    )
    assert position_consumes_core_slot(
        {"ticker": "AAPL", "shares": 1, "slot_policy": "consumes_core_slot"}
    )
    assert not position_consumes_core_slot(
        {
            "ticker": "NVDA",
            "shares": 1,
            "opened_by_strategy": "breakout_long",
            "slot_policy": "does_not_consume_core_slot",
        }
    )
    assert not position_consumes_core_slot(
        {"ticker": "RKLB", "shares": 1, "sleeve": "fomo"}
    )


def test_slot_accounting_reads_core_positions_group_and_account_positions():
    open_positions = {
        "observations": [
            {"ticker": "APP", "shares": 17, "opened_by_strategy": "legacy"},
        ],
        "core_positions": [
            {"ticker": "MRVL", "shares": 24, "opened_by_strategy": "fomo"},
            {"ticker": "COHR", "shares": 16, "opened_by_strategy": "pilot_breakout_long"},
        ],
        "positions": [
            {"ticker": "SNXX", "shares": 48, "opened_by_strategy": "fomo"},
        ],
    }

    summary = build_slot_accounting_summary(open_positions, max_positions=5)

    assert count_core_strategy_positions(open_positions) == 2
    assert summary["live_active_positions"] == 4
    assert summary["strategy_active_positions"] == 2
    assert summary["strategy_available_slots"] == 3
    assert [row["ticker"] for row in summary["core_strategy_positions"]] == ["MRVL", "COHR"]
    assert [
        row["ticker"]
        for row in summary["non_strategy_positions_ignored_for_strategy_slots"]
    ] == ["SNXX", "APP"]


def test_entry_candidate_review_surfaces_backtest_buy_live_slot_deferred():
    open_positions = {
        "positions": [
            {"ticker": "LEG1", "shares": 10, "opened_by_strategy": "legacy"},
            {"ticker": "LEG2", "shares": 10, "opened_by_strategy": "legacy"},
            {"ticker": "FOMO", "shares": 10, "opened_by_strategy": "fomo"},
            {"ticker": "PILOT", "shares": 10, "opened_by_strategy": "pilot_breakout_long"},
            {"ticker": "CORE", "shares": 10, "opened_by_strategy": "trend_long"},
        ]
    }
    signals = [
        {"ticker": "GS", "strategy": "trend_long", "entry_price": 100.0},
        {"ticker": "SNOW", "strategy": "breakout_long", "entry_price": 50.0},
    ]

    live_selected, live_plan = plan_entry_candidates(
        signals,
        open_positions,
        max_positions=5,
    )
    strategy_selected, strategy_plan = plan_entry_candidates(
        signals,
        open_positions,
        max_positions=5,
        active_positions_count=count_core_strategy_positions(open_positions),
    )
    review = build_entry_candidate_review(
        signals,
        live_selected_signals=live_selected,
        live_entry_execution_plan=live_plan,
        strategy_selected_signals=strategy_selected,
        strategy_entry_execution_plan=strategy_plan,
        open_positions=open_positions,
        max_positions=5,
    )

    assert live_selected == []
    assert [row["ticker"] for row in strategy_selected] == ["GS", "SNOW"]
    assert review["operator_review_count"] == 2
    assert review["live_buy_count"] == 0
    assert review["backtest_accounting_buy_count"] == 2
    assert review["candidates"][0]["live_accounting"]["reason"] == "slot_sliced"
    assert review["candidates"][0]["backtest_accounting"]["decision"] == "buy"


def test_entry_candidate_review_surfaces_total_account_shadow_blocker():
    open_positions = {
        "positions": [
            {"ticker": "LEG1", "shares": 10, "opened_by_strategy": "legacy"},
            {"ticker": "LEG2", "shares": 10, "opened_by_strategy": "legacy"},
            {"ticker": "FOMO", "shares": 10, "opened_by_strategy": "fomo"},
            {"ticker": "PILOT", "shares": 10, "opened_by_strategy": "pilot_breakout_long"},
            {"ticker": "CORE", "shares": 10, "opened_by_strategy": "trend_long"},
        ]
    }
    signals = [
        {"ticker": "GS", "strategy": "trend_long", "entry_price": 100.0},
        {"ticker": "SNOW", "strategy": "trend_long", "entry_price": 50.0},
    ]
    core_count = count_core_strategy_positions(open_positions)

    total_selected, total_plan = plan_entry_candidates(
        signals,
        open_positions,
        max_positions=5,
        active_positions_scope="total_account_positive_positions_shadow",
    )
    live_selected, live_plan = plan_entry_candidates(
        signals,
        open_positions,
        max_positions=5,
        active_positions_count=core_count,
        active_positions_scope="core_strategy_slot_accounting",
    )
    review = build_entry_candidate_review(
        signals,
        live_selected_signals=live_selected,
        live_entry_execution_plan=live_plan,
        strategy_selected_signals=live_selected,
        strategy_entry_execution_plan=live_plan,
        total_account_selected_signals=total_selected,
        total_account_entry_execution_plan=total_plan,
        open_positions=open_positions,
        max_positions=5,
    )

    assert [row["ticker"] for row in live_selected] == ["GS", "SNOW"]
    assert total_selected == []
    assert review["live_buy_count"] == 2
    assert review["total_accounting_buy_count"] == 0
    assert review["operator_review_count"] == 2
    assert (
        review["candidates"][0]["operator_review_reason"]
        == "total_account_would_defer_but_core_capacity_allows"
    )
    assert review["candidates"][0]["total_accounting_shadow"]["reason"] == "slot_sliced"


def test_report_renders_core_slots_and_total_account_shadow():
    entry_plan = {
        "available_slots": 4,
        "active_positions_scope": "core_strategy_slot_accounting",
        "deferred_breakout_signals": [],
        "slot_sliced_signals": [],
    }
    review = {
        "candidate_count": 1,
        "slot_accounting": {
            "max_positions": 5,
            "live_active_positions": 11,
            "live_available_slots": 0,
            "strategy_active_positions": 1,
            "strategy_available_slots": 4,
            "non_strategy_positions_ignored_for_strategy_slots": [
                {"ticker": "NVDA"},
                {"ticker": "RKLB"},
            ],
        },
        "candidates": [
            {
                "rank": 1,
                "ticker": "SNOW",
                "strategy": "trend_long",
                "live_accounting": {
                    "decision": "buy",
                    "reason": "selected_by_entry_plan",
                },
                "backtest_accounting": {
                    "decision": "buy",
                    "reason": "selected_by_entry_plan",
                },
                "total_accounting_shadow": {
                    "decision": "deferred",
                    "reason": "slot_sliced",
                },
                "operator_review_reason": (
                    "total_account_would_defer_but_core_capacity_allows"
                ),
            }
        ],
    }

    report = generate_daily_report(
        [],
        portfolio_heat={"portfolio_heat_pct": 0.01, "can_add_new_positions": True},
        market_regime={"regime": "BULL", "note": "test"},
        entry_execution_plan=entry_plan,
        entry_candidate_review=review,
    )

    assert "ENTRY SLOTS (core strategy): 4 available" in report
    assert "Production core slots: 4/5 available (1 core active)" in report
    assert "Total-account shadow slots: 0/5 available (11 active)" in report
    assert "Non-core positions not consuming core slots: NVDA, RKLB" in report
    assert "total_shadow=deferred:slot_sliced" in report


def test_report_surfaces_addon_acceptable_open_guardrail():
    report = generate_daily_report(
        [],
        portfolio_heat={"portfolio_heat_pct": 0.01, "can_add_new_positions": True},
        market_regime={"regime": "BULL", "note": "test"},
        addon_actions=[
            {
                "ticker": "MRVL",
                "shares_to_buy": 12,
                "fill_timing": "next_session_open",
                "estimated_price": 316.43,
                "estimated_position_value_usd": 3797.16,
                "checkpoint_days": 2,
                "unrealized_pct": 0.0716,
                "rs_vs_spy": 0.0914,
                "cap_detail": {"effective_stop": 298.26},
                "reason": "day-2 follow-through",
            }
        ],
    )

    assert "MRVL: ADD 12 shares at next session open near $316.43" in report
    assert "Acceptable open guardrail: $310.10 - $321.18" in report
    assert "hard skip <= $298.26" in report
    assert "adverse open below range means skip" in report


def test_plan_entry_candidates_topups_rank1_when_single_slot(monkeypatch):
    monkeypatch.setattr(
        production_parity,
        "SCARCE_SLOT_RANK1_RISK_MULTIPLIER",
        1.10,
    )
    signals = [
        {
            "ticker": "AAPL",
            "strategy": "trend_long",
            "sector": "Technology",
            "sizing": {
                "shares_to_buy": 100,
                "entry_price": 100.0,
                "portfolio_value_usd": 100_000.0,
                "net_risk_per_share": 4.0,
                "max_position_pct_applied": 0.40,
            },
        },
        {
            "ticker": "NVDA",
            "strategy": "trend_long",
            "sizing": {
                "shares_to_buy": 50,
                "entry_price": 100.0,
                "portfolio_value_usd": 100_000.0,
                "net_risk_per_share": 5.0,
            },
        },
    ]

    planned, plan = plan_entry_candidates(
        signals,
        open_positions=None,
        max_positions=3,
        active_positions_count=2,
    )

    sizing = planned[0]["sizing"]
    assert [s["ticker"] for s in planned] == ["AAPL"]
    assert [s["ticker"] for s in plan["slot_sliced_signals"]] == ["NVDA"]
    assert sizing["shares_to_buy"] == 110
    assert sizing["risk_amount_usd"] == 440.0
    assert sizing["risk_pct"] == 0.0044
    assert sizing["scarce_slot_rank1_risk_multiplier_applied"] == 1.10
    assert plan["scarce_slot_rank1_topups"][0]["new_shares"] == 110


def test_plan_entry_candidates_does_not_topup_when_multiple_slots(monkeypatch):
    monkeypatch.setattr(
        production_parity,
        "SCARCE_SLOT_RANK1_RISK_MULTIPLIER",
        1.10,
    )
    signals = [
        {
            "ticker": "AAPL",
            "strategy": "trend_long",
            "sizing": {
                "shares_to_buy": 100,
                "entry_price": 100.0,
                "portfolio_value_usd": 100_000.0,
                "net_risk_per_share": 4.0,
            },
        }
    ]

    planned, plan = plan_entry_candidates(
        signals,
        open_positions=None,
        max_positions=3,
        active_positions_count=1,
    )

    assert plan["available_slots"] == 2
    assert planned[0]["sizing"]["shares_to_buy"] == 100
    assert plan["scarce_slot_rank1_topups"] == []


def test_plan_entry_candidates_topups_stock_rank1_when_slots_are_ample(monkeypatch):
    monkeypatch.setattr(
        production_parity,
        "AMPLE_SLOT_STOCK_RANK1_RISK_MULTIPLIER",
        1.10,
    )
    signals = [
        {
            "ticker": "AAPL",
            "strategy": "trend_long",
            "sector": "Technology",
            "sizing": {
                "shares_to_buy": 100,
                "entry_price": 100.0,
                "portfolio_value_usd": 100_000.0,
                "net_risk_per_share": 4.0,
                "max_position_pct_applied": 0.40,
            },
        }
    ]

    planned, plan = plan_entry_candidates(
        signals,
        open_positions=None,
        max_positions=5,
        active_positions_count=1,
    )

    sizing = planned[0]["sizing"]
    assert plan["available_slots"] == 4
    assert sizing["shares_to_buy"] == 110
    assert sizing["risk_amount_usd"] == 440.0
    assert sizing["risk_pct"] == 0.0044
    assert sizing["ample_slot_stock_rank1_state"] is True
    assert sizing["ample_slot_stock_rank1_risk_multiplier_applied"] == 1.10
    assert plan["ample_slot_stock_rank1_topups"][0]["new_shares"] == 110


def test_plan_entry_candidates_does_not_ample_topup_commodity_rank1(monkeypatch):
    monkeypatch.setattr(
        production_parity,
        "AMPLE_SLOT_STOCK_RANK1_RISK_MULTIPLIER",
        1.10,
    )
    signals = [
        {
            "ticker": "SLV",
            "strategy": "trend_long",
            "sector": "Commodities",
            "sizing": {
                "shares_to_buy": 100,
                "entry_price": 100.0,
                "portfolio_value_usd": 100_000.0,
                "net_risk_per_share": 4.0,
                "max_position_pct_applied": 0.50,
            },
        }
    ]

    planned, plan = plan_entry_candidates(
        signals,
        open_positions=None,
        max_positions=5,
        active_positions_count=1,
    )

    assert plan["available_slots"] == 4
    assert planned[0]["sizing"]["shares_to_buy"] == 100
    assert plan["ample_slot_stock_rank1_topups"] == []


def test_plan_entry_candidates_does_not_ample_topup_unknown_sector(monkeypatch):
    monkeypatch.setattr(
        production_parity,
        "AMPLE_SLOT_STOCK_RANK1_RISK_MULTIPLIER",
        1.10,
    )
    signals = [
        {
            "ticker": "AAPL",
            "strategy": "trend_long",
            "sizing": {
                "shares_to_buy": 100,
                "entry_price": 100.0,
                "portfolio_value_usd": 100_000.0,
                "net_risk_per_share": 4.0,
                "max_position_pct_applied": 0.50,
            },
        }
    ]

    planned, plan = plan_entry_candidates(
        signals,
        open_positions=None,
        max_positions=5,
        active_positions_count=1,
    )

    assert plan["available_slots"] == 4
    assert planned[0]["sizing"]["shares_to_buy"] == 100
    assert plan["ample_slot_stock_rank1_topups"] == []


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


def test_risk_pct_for_market_state_matches_shared_regime_sizing():
    assert risk_pct_for_market_state("BULL", 0.1, 0.1) is None
    assert risk_pct_for_market_state("NEUTRAL", 0.1, -0.01) == 0.0075
    assert risk_pct_for_market_state("BEAR", -0.03, -0.04) == 0.005
    assert risk_pct_for_market_state("BEAR", -0.03, -0.06) is None


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
    assert actions[0]["original_shares_source"] == "original_shares"
    assert any(row["status"] == "eligible" for row in audit)


def test_build_followthrough_addon_actions_uses_intended_shares_for_conservative_entry():
    open_positions = {
        "positions": [
            {
                "ticker": "NVDA",
                "shares": 6,
                "intended_shares": 10,
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
    assert actions[0]["shares_to_buy"] == 5
    assert actions[0]["requested_shares"] == 5
    assert actions[0]["original_shares"] == 10
    assert actions[0]["original_shares_source"] == "intended_shares"
    assert any(row["original_shares_source"] == "intended_shares" for row in audit)


def test_build_followthrough_addon_actions_uses_spy_leader_addon_cap():
    open_positions = {
        "positions": [
            {
                "ticker": "NVDA",
                "shares": 35,
                "original_shares": 35,
                "avg_cost": 120.0,
                "entry_date": "2026-01-30",
            }
        ]
    }
    nvda_prices = [100.0] * 20 + [120.0, 123.0, 126.0]
    spy_prices = [100.0] * 20 + [105.0, 105.0, 106.0]
    ohlcv = {
        "NVDA": _ohlcv(nvda_prices),
        "SPY": _ohlcv(spy_prices),
    }

    actions, _audit = build_followthrough_addon_actions(
        open_positions=open_positions,
        ohlcv_dict=ohlcv,
        portfolio_value=10_000,
        current_prices={"NVDA": 126.0},
    )

    assert len(actions) == 1
    assert actions[0]["spy_relative_leader_addon_cap"] is True
    assert actions[0]["addon_position_cap_pct"] == 0.60
    assert actions[0]["shares_to_buy"] == 12


def test_build_followthrough_addon_actions_skips_mismatched_latest_dates():
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
        "SPY": _ohlcv([100.0, 100.0, 101.0, 102.0]),
    }

    actions, audit = build_followthrough_addon_actions(
        open_positions=open_positions,
        ohlcv_dict=ohlcv,
        portfolio_value=10_000,
        current_prices={"NVDA": 104.0},
    )

    assert actions == []
    assert audit[0]["reason"] == "mismatched_latest_ohlcv_date"
    assert audit[0]["ticker_latest_date"] == "2026-01-06"
    assert audit[0]["spy_latest_date"] == "2026-01-07"


def test_build_followthrough_addon_actions_ignores_stale_current_price_dates():
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
        "NVDA": _ohlcv([100.0, 100.0, 101.0]),
        "SPY": _ohlcv([100.0, 100.0, 100.5]),
    }

    actions, audit = build_followthrough_addon_actions(
        open_positions=open_positions,
        ohlcv_dict=ohlcv,
        portfolio_value=10_000,
        current_prices={"NVDA": 104.0},
        current_price_dates={"NVDA": "2026-01-05"},
    )

    assert actions == []
    assert audit[0]["reason"] == "followthrough_threshold_not_met"
    assert audit[0]["unrealized_pct"] == 0.01


def test_build_early_relative_weakness_exit_actions_emits_day_three_exit():
    open_positions = {
        "positions": [
            {
                "ticker": "NVDA",
                "shares": 10,
                "avg_cost": 100.0,
                "entry_date": "2026-01-02",
            }
        ]
    }
    ohlcv = {
        "NVDA": _ohlcv([100.0, 99.0, 96.0]),
        "SPY": _ohlcv([100.0, 100.5, 101.0]),
    }

    actions, audit = build_early_relative_weakness_exit_actions(
        open_positions=open_positions,
        ohlcv_dict=ohlcv,
        current_prices={"NVDA": 96.0},
        enabled=True,
    )

    assert len(actions) == 1
    assert actions[0]["ticker"] == "NVDA"
    assert actions[0]["action"] == "EXIT"
    assert actions[0]["shares_to_sell"] == 10
    assert actions[0]["fill_timing"] == "next_session_open"
    assert actions[0]["triggered_rule"] == "EARLY_RELATIVE_WEAKNESS"
    assert any(row["status"] == "eligible" for row in audit)


def test_build_early_relative_weakness_exit_actions_filters_by_actual_risk():
    open_positions = {
        "positions": [
            {
                "ticker": "NVDA",
                "shares": 10,
                "avg_cost": 100.0,
                "entry_date": "2026-01-02",
                "actual_risk_pct": 0.025,
            },
            {
                "ticker": "MSFT",
                "shares": 10,
                "avg_cost": 100.0,
                "entry_date": "2026-01-02",
                "actual_risk_pct": 0.01,
            },
        ]
    }
    ohlcv = {
        "NVDA": _ohlcv([100.0, 99.0, 96.0]),
        "MSFT": _ohlcv([100.0, 99.0, 96.0]),
        "SPY": _ohlcv([100.0, 100.5, 101.0]),
    }

    actions, audit = build_early_relative_weakness_exit_actions(
        open_positions=open_positions,
        ohlcv_dict=ohlcv,
        current_prices={"NVDA": 96.0, "MSFT": 96.0},
        enabled=True,
        min_actual_risk_pct=0.02,
    )

    assert [action["ticker"] for action in actions] == ["NVDA"]
    assert actions[0]["actual_risk_pct"] == 0.025
    assert actions[0]["min_actual_risk_pct"] == 0.02
    assert any(
        row["ticker"] == "MSFT"
        and row["reason"] == "actual_risk_below_threshold"
        and row["actual_risk_pct"] == 0.01
        for row in audit
    )


def test_build_early_relative_weakness_exit_actions_waits_for_check_day():
    open_positions = {
        "positions": [
            {
                "ticker": "NVDA",
                "shares": 10,
                "avg_cost": 100.0,
                "entry_date": "2026-01-02",
            }
        ]
    }
    ohlcv = {
        "NVDA": _ohlcv([100.0, 96.0]),
        "SPY": _ohlcv([100.0, 101.0]),
    }

    actions, audit = build_early_relative_weakness_exit_actions(
        open_positions=open_positions,
        ohlcv_dict=ohlcv,
        current_prices={"NVDA": 96.0},
        enabled=True,
    )

    assert actions == []
    assert audit[0]["reason"] == "not_early_weakness_check_day"


def test_build_early_relative_weakness_exit_actions_skips_mismatched_latest_dates():
    open_positions = {
        "positions": [
            {
                "ticker": "NVDA",
                "shares": 10,
                "avg_cost": 100.0,
                "entry_date": "2026-01-02",
            }
        ]
    }
    ohlcv = {
        "NVDA": _ohlcv([100.0, 99.0, 96.0]),
        "SPY": _ohlcv([100.0, 100.5, 101.0, 102.0]),
    }

    actions, audit = build_early_relative_weakness_exit_actions(
        open_positions=open_positions,
        ohlcv_dict=ohlcv,
        current_prices={"NVDA": 96.0},
        enabled=True,
    )

    assert actions == []
    assert audit[0]["reason"] == "mismatched_latest_ohlcv_date"
    assert audit[0]["ticker_latest_date"] == "2026-01-06"
    assert audit[0]["spy_latest_date"] == "2026-01-07"


def test_build_early_relative_weakness_exit_actions_ignores_stale_current_price_dates():
    open_positions = {
        "positions": [
            {
                "ticker": "NVDA",
                "shares": 10,
                "avg_cost": 100.0,
                "entry_date": "2026-01-02",
            }
        ]
    }
    ohlcv = {
        "NVDA": _ohlcv([100.0, 99.0, 99.0]),
        "SPY": _ohlcv([100.0, 100.5, 101.0]),
    }

    actions, audit = build_early_relative_weakness_exit_actions(
        open_positions=open_positions,
        ohlcv_dict=ohlcv,
        current_prices={"NVDA": 96.0},
        current_price_dates={"NVDA": "2026-01-05"},
        enabled=True,
    )

    assert actions == []
    assert audit[0]["reason"] == "relative_weakness_threshold_not_met"
    assert audit[0]["ticker_return_pct"] == -0.01


def test_cap_followthrough_addon_shares_uses_effective_stop_heat_room():
    portfolio_heat = {
        "total_at_risk_usd": 7_900.0,
        "max_heat_pct": 0.08,
        "position_breakdown": [
            {
                "ticker": "NVDA",
                "effective_stop": 95.0,
                "effective_stop_source": "trailing",
            }
        ],
    }

    shares, detail = cap_followthrough_addon_shares(
        "NVDA",
        requested_shares=50,
        current_shares=10,
        price=100.0,
        portfolio_value=100_000.0,
        addon_position_cap=0.50,
        portfolio_heat=portfolio_heat,
    )

    assert shares == 20
    assert detail["heat_room_shares"] == 20
    assert detail["effective_stop"] == 95.0
    assert detail["cap_reason"] is None


def test_cap_followthrough_addon_shares_reports_portfolio_heat_cap():
    portfolio_heat = {
        "total_at_risk_usd": 8_000.0,
        "max_heat_pct": 0.08,
        "position_breakdown": [{"ticker": "NVDA", "effective_stop": 95.0}],
    }

    shares, detail = cap_followthrough_addon_shares(
        "NVDA",
        requested_shares=50,
        current_shares=10,
        price=100.0,
        portfolio_value=100_000.0,
        addon_position_cap=0.50,
        portfolio_heat=portfolio_heat,
    )

    assert shares == 0
    assert detail["heat_room_shares"] == 0
    assert detail["cap_reason"] == "portfolio_heat_cap"


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


def test_trailing_partial_reduce_policy_is_shared():
    rules = [{"rule": "TRAILING_STOP", "urgency": "HIGH"}]

    assert production_trailing_stop_price(100.0) == 92.0
    assert TRAILING_PARTIAL_REDUCE_ENABLED is False
    assert suggested_reduce_pct_for_rules(rules, 0.31) == 0
    assert suggested_reduce_pct_for_rules(
        rules,
        0.31,
        trailing_partial_reduce_enabled=True,
    ) == 25
    assert suggested_reduce_pct_for_rules(
        rules,
        0.10,
        trailing_partial_reduce_enabled=True,
    ) == 50
    assert partial_reduce_shares(5, 25) == 1
    assert partial_reduce_shares(25, 25) == 6


def test_approaching_hard_stop_no_longer_maps_to_reduce():
    rules = [{"rule": "APPROACHING_HARD_STOP", "urgency": "WARNING"}]

    assert suggested_reduce_pct_for_rules(rules, -0.02) == 0
    assert suggested_reduce_pct_for_rules(rules, 0.02) == 0


def test_atr_stop_no_longer_maps_to_partial_reduce():
    rules = [{"rule": "ATR_STOP", "urgency": "HIGH"}]

    assert suggested_reduce_pct_for_rules(rules, -0.06) == 0
    assert suggested_reduce_pct_for_rules(rules, -0.02) == 0


def test_profit_lock_rules_no_longer_map_to_partial_reduce():
    assert suggested_reduce_pct_for_rules(
        [{"rule": "SIGNAL_TARGET", "urgency": "HIGH"}],
        0.25,
    ) == 100
    assert suggested_reduce_pct_for_rules(
        [{"rule": "PROFIT_TARGET", "urgency": "MEDIUM"}],
        0.25,
    ) == 0
    assert suggested_reduce_pct_for_rules(
        [{"rule": "PROFIT_LADDER_50", "urgency": "MEDIUM"}],
        0.55,
    ) == 0


def test_exit_policy_replay_bias_discloses_advisory_gap():
    bias = backtester.build_exit_policy_replay_bias(
        partial_reduce_enabled=True,
        trailing_partial_reduce_enabled=False,
    )

    assert bias["gap_present"] is True
    assert "SIGNAL_TARGET" not in bias["production_advisory_actions_not_replayed"]
    assert "TIME_STOP" in bias["production_advisory_actions_not_replayed"]
    assert bias["target_price_semantic_gap"]["resolved"] is True
    assert bias["target_price_semantic_gap"]["backtester"].startswith(
        "Position.target_price is simulated as a hard full-position"
    )
    assert bias["partial_reduce_replay_scope"]["replay_container_enabled"] is True
    assert bias["partial_reduce_replay_scope"][
        "trailing_partial_reduce_enabled"
    ] is False
    assert bias["rejected_simple_replay"]["experiment_id"] == "exp-20260429-032"
    assert bias["rejected_simple_replay"]["decision"] == "rejected"


def test_exit_advisory_shadow_attribution_summarizes_without_execution():
    events = [
        {
            "date": "2026-01-05",
            "ticker": "AAA",
            "trade_key": "AAA:2026-01-02:100.0000",
            "rule": "SIGNAL_TARGET",
            "is_first_for_trade": True,
        },
        {
            "date": "2026-01-06",
            "ticker": "AAA",
            "trade_key": "AAA:2026-01-02:100.0000",
            "rule": "SIGNAL_TARGET",
            "is_first_for_trade": False,
        },
    ]
    trades = [
        {
            "trade_key": "AAA:2026-01-02:100.0000",
            "pnl": 250.0,
            "exit_reason": "target",
            "exit_advisory_rules_seen": ["SIGNAL_TARGET"],
        }
    ]

    attribution = backtester.build_exit_advisory_shadow_attribution(
        events,
        trades,
    )

    signal_target = attribution["by_rule"]["SIGNAL_TARGET"]
    assert attribution["mode"] == "shadow_only_no_trade_execution"
    assert signal_target["daily_triggers"] == 2
    assert signal_target["unique_trades"] == 1
    assert signal_target["first_trigger_trades"] == 1
    assert signal_target["outcome"]["closed_trades"] == 1
    assert signal_target["outcome"]["win_rate"] == 1.0
    assert signal_target["outcome"]["pnl"] == 250.0


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
        "ADDON_SPY_RELATIVE_LEADER_MAX_POSITION_PCT",
        "SECOND_ADDON_ENABLED",
        "SECOND_ADDON_CHECKPOINT_DAYS",
        "SECOND_ADDON_MIN_UNREALIZED_PCT",
        "SECOND_ADDON_MIN_RS_VS_SPY",
        "SECOND_ADDON_FRACTION_OF_ORIGINAL_SHARES",
        "SECOND_ADDON_MAX_POSITION_PCT",
        "DEFER_BREAKOUT_WHEN_SLOTS_LTE",
        "DEFER_BREAKOUT_MAX_MIN_INDEX_PCT_FROM_MA",
        "REPLAY_PARTIAL_REDUCES",
        "PRODUCTION_TRAILING_STOP_PCT",
        "TRAILING_PARTIAL_REDUCE_ENABLED",
    ]

    for key in shared_keys:
        if key == "REPLAY_PARTIAL_REDUCES":
            assert backtester.DEFAULT_CONFIG[key] is True
        elif key == "PRODUCTION_TRAILING_STOP_PCT":
            assert backtester.DEFAULT_CONFIG[key] == constants.TRAILING_STOP_PCT
        elif key == "TRAILING_PARTIAL_REDUCE_ENABLED":
            assert backtester.DEFAULT_CONFIG[key] == TRAILING_PARTIAL_REDUCE_ENABLED
        else:
            assert backtester.DEFAULT_CONFIG[key] == getattr(constants, key)


def test_commodity_near_high_trend_risk_boost_is_shared_sizing_policy():
    signals = [
        {
            "ticker": "SLV",
            "strategy": "trend_long",
            "sector": "Commodities",
            "entry_price": 100.0,
            "stop_price": 95.0,
            "trade_quality_score": 0.95,
            "conditions_met": {"pct_from_52w_high": -0.02},
        },
        {
            "ticker": "SLV",
            "strategy": "trend_long",
            "sector": "Commodities",
            "entry_price": 100.0,
            "stop_price": 95.0,
            "trade_quality_score": 0.95,
            "conditions_met": {"pct_from_52w_high": -0.04},
        },
    ]

    sized = size_signals(signals, portfolio_value=100_000, risk_pct=0.01)

    boosted = sized[0]["sizing"]
    unboosted = sized[1]["sizing"]
    assert boosted["trend_commodities_near_high_risk_multiplier_applied"] == 1.5
    assert unboosted["trend_commodities_near_high_risk_multiplier_applied"] == 1.0
    assert boosted["max_position_pct_applied"] == (
        constants.TREND_COMMODITIES_NEAR_HIGH_MAX_POSITION_PCT
    )
    assert unboosted["max_position_pct_applied"] == constants.MAX_POSITION_PCT
    assert boosted["trend_commodities_near_high_max_position_pct_applied"] == (
        constants.TREND_COMMODITIES_NEAR_HIGH_MAX_POSITION_PCT
    )
    assert boosted["risk_pct"] > unboosted["risk_pct"]


def test_commodity_breakout_cap_is_shared_sizing_policy():
    signals = [
        {
            "ticker": "GLD",
            "strategy": "breakout_long",
            "sector": "Commodities",
            "entry_price": 100.0,
            "stop_price": 99.5,
            "trade_quality_score": 0.95,
            "conditions_met": {},
        },
        {
            "ticker": "IAU",
            "strategy": "trend_long",
            "sector": "Commodities",
            "entry_price": 100.0,
            "stop_price": 99.5,
            "trade_quality_score": 0.95,
            "conditions_met": {"pct_from_52w_high": -0.04},
        },
    ]

    sized = size_signals(signals, portfolio_value=100_000, risk_pct=0.01)

    breakout = sized[0]["sizing"]
    trend = sized[1]["sizing"]
    assert breakout["max_position_pct_applied"] == (
        constants.BREAKOUT_COMMODITIES_MAX_POSITION_PCT
    )
    assert breakout["breakout_commodities_max_position_pct_applied"] == (
        constants.BREAKOUT_COMMODITIES_MAX_POSITION_PCT
    )
    assert trend["max_position_pct_applied"] == constants.MAX_POSITION_PCT
    assert "breakout_commodities_max_position_pct_applied" not in trend
    assert breakout["shares_to_buy"] == int(
        100_000 * constants.BREAKOUT_COMMODITIES_MAX_POSITION_PCT / 100.0
    )
    assert trend["shares_to_buy"] == int(
        100_000 * constants.MAX_POSITION_PCT / 100.0
    )


def test_gold_near_high_trend_cap_is_shared_sizing_policy():
    signals = [
        {
            "ticker": "GLD",
            "strategy": "trend_long",
            "sector": "Commodities",
            "entry_price": 100.0,
            "stop_price": 99.0,
            "trade_quality_score": 0.95,
            "conditions_met": {"pct_from_52w_high": -0.02},
        },
        {
            "ticker": "SLV",
            "strategy": "trend_long",
            "sector": "Commodities",
            "entry_price": 100.0,
            "stop_price": 99.0,
            "trade_quality_score": 0.95,
            "conditions_met": {"pct_from_52w_high": -0.02},
        },
    ]

    sized = size_signals(signals, portfolio_value=100_000, risk_pct=0.01)

    gold = sized[0]["sizing"]
    silver = sized[1]["sizing"]
    assert gold["max_position_pct_applied"] == (
        constants.TREND_GOLD_NEAR_HIGH_MAX_POSITION_PCT
    )
    assert gold["trend_gold_near_high_max_position_pct_applied"] == (
        constants.TREND_GOLD_NEAR_HIGH_MAX_POSITION_PCT
    )
    assert silver["max_position_pct_applied"] == (
        constants.TREND_COMMODITIES_NEAR_HIGH_MAX_POSITION_PCT
    )
    assert "trend_gold_near_high_max_position_pct_applied" not in silver
    assert gold["shares_to_buy"] == int(
        100_000 * constants.TREND_GOLD_NEAR_HIGH_MAX_POSITION_PCT / 100.0
    )
    assert silver["shares_to_buy"] == int(
        100_000
        * constants.TREND_COMMODITIES_NEAR_HIGH_MAX_POSITION_PCT
        / 100.0
    )


def test_financials_trend_risk_boost_is_shared_sizing_policy():
    signals = [
        {
            "ticker": "GS",
            "strategy": "trend_long",
            "sector": "Financials",
            "entry_price": 100.0,
            "stop_price": 95.0,
            "trade_quality_score": 0.95,
            "conditions_met": {},
        },
        {
            "ticker": "GS",
            "strategy": "breakout_long",
            "sector": "Financials",
            "entry_price": 100.0,
            "stop_price": 95.0,
            "trade_quality_score": 0.95,
            "conditions_met": {},
        },
    ]

    sized = size_signals(signals, portfolio_value=100_000, risk_pct=0.01)

    boosted = sized[0]["sizing"]
    unboosted = sized[1]["sizing"]
    assert boosted["trend_financials_risk_multiplier_applied"] == 1.5
    assert unboosted["trend_financials_risk_multiplier_applied"] == 1.0
    assert boosted["risk_pct"] > unboosted["risk_pct"]


def test_financials_sector_leader_cap_is_shared_sizing_policy():
    signals = [
        {
            "ticker": "GS",
            "strategy": "trend_long",
            "sector": "Financials",
            "entry_price": 100.0,
            "stop_price": 99.0,
            "trade_quality_score": 0.95,
            "financials_sector_leader": True,
            "conditions_met": {},
        },
        {
            "ticker": "MS",
            "strategy": "trend_long",
            "sector": "Financials",
            "entry_price": 100.0,
            "stop_price": 99.0,
            "trade_quality_score": 0.95,
            "financials_sector_leader": False,
            "conditions_met": {},
        },
    ]

    sized = size_signals(signals, portfolio_value=100_000, risk_pct=0.01)

    leader = sized[0]["sizing"]
    non_leader = sized[1]["sizing"]
    assert leader["max_position_pct_applied"] == (
        constants.TREND_FINANCIALS_SECTOR_LEADER_MAX_POSITION_PCT
    )
    assert non_leader["max_position_pct_applied"] == constants.MAX_POSITION_PCT
    assert leader["trend_financials_sector_leader_max_position_pct_applied"] == (
        constants.TREND_FINANCIALS_SECTOR_LEADER_MAX_POSITION_PCT
    )
    assert non_leader["trend_financials_sector_leader_max_position_pct_applied"] == (
        constants.MAX_POSITION_PCT
    )
    assert leader["position_pct_of_portfolio"] == (
        constants.TREND_FINANCIALS_SECTOR_LEADER_MAX_POSITION_PCT
    )
    assert non_leader["position_pct_of_portfolio"] == constants.MAX_POSITION_PCT


def test_financials_mid_dispersion_leader_cap_is_shared_sizing_policy():
    signals = [
        {
            "ticker": "COIN",
            "strategy": "trend_long",
            "sector": "Financials",
            "entry_price": 100.0,
            "stop_price": 99.0,
            "trade_quality_score": 0.95,
            "financials_sector_leader": True,
            "mid_sector_dispersion": True,
            "conditions_met": {},
        },
        {
            "ticker": "GS",
            "strategy": "trend_long",
            "sector": "Financials",
            "entry_price": 100.0,
            "stop_price": 99.0,
            "trade_quality_score": 0.95,
            "financials_sector_leader": True,
            "mid_sector_dispersion": False,
            "conditions_met": {},
        },
    ]

    sized = size_signals(signals, portfolio_value=100_000, risk_pct=0.01)

    mid_dispersion = sized[0]["sizing"]
    plain_leader = sized[1]["sizing"]
    assert mid_dispersion["max_position_pct_applied"] == (
        constants.TREND_FINANCIALS_MID_DISPERSION_LEADER_MAX_POSITION_PCT
    )
    assert plain_leader["max_position_pct_applied"] == (
        constants.TREND_FINANCIALS_SECTOR_LEADER_MAX_POSITION_PCT
    )
    assert mid_dispersion[
        "trend_financials_mid_dispersion_leader_max_position_pct_applied"
    ] == constants.TREND_FINANCIALS_MID_DISPERSION_LEADER_MAX_POSITION_PCT
    assert (
        "trend_financials_mid_dispersion_leader_max_position_pct_applied"
        not in plain_leader
    )
    assert mid_dispersion["shares_to_buy"] == 550
    assert plain_leader["shares_to_buy"] == 500


def test_mid_sector_dispersion_trend_boost_is_shared_sizing_policy():
    signals = [
        {
            "ticker": "AAPL",
            "strategy": "trend_long",
            "sector": "Technology",
            "entry_price": 100.0,
            "stop_price": 95.0,
            "trade_quality_score": 0.95,
            "mid_sector_dispersion": True,
            "sector_ret20_dispersion": 0.0482,
            "conditions_met": {},
        },
        {
            "ticker": "AAPL",
            "strategy": "breakout_long",
            "sector": "Technology",
            "entry_price": 100.0,
            "stop_price": 95.0,
            "trade_quality_score": 0.95,
            "mid_sector_dispersion": True,
            "sector_ret20_dispersion": 0.0482,
            "conditions_met": {},
        },
    ]

    sized = size_signals(signals, portfolio_value=100_000, risk_pct=0.01)

    boosted = sized[0]["sizing"]
    unboosted = sized[1]["sizing"]
    assert boosted["trend_mid_sector_dispersion_risk_multiplier_applied"] == 1.25
    assert unboosted["trend_mid_sector_dispersion_risk_multiplier_applied"] == 1.0
    assert boosted["risk_pct"] > unboosted["risk_pct"]


def test_price_vs_200ma_extension_state_is_shared_risk_enrichment():
    signals = [
        {
            "ticker": "AMD",
            "strategy": "trend_long",
            "entry_price": 100.0,
            "stop_price": 95.0,
            "confidence_score": 0.9,
        },
        {
            "ticker": "AAPL",
            "strategy": "trend_long",
            "entry_price": 100.0,
            "stop_price": 95.0,
            "confidence_score": 0.9,
        },
    ]
    features = {
        "AMD": _feature_row(0.40, momentum_60d=0.30),
        "NVDA": _feature_row(0.30, momentum_60d=0.25),
        "MSFT": _feature_row(0.20, momentum_60d=0.20),
        "AAPL": _feature_row(0.10, momentum_60d=0.15),
        "SPY": _feature_row(0.99, momentum_20d=0.05, momentum_60d=0.05),
    }

    enriched = enrich_signals(signals, features)

    by_ticker = {sig["ticker"]: sig for sig in enriched}
    assert by_ticker["AMD"]["price_vs_200ma_extension_cutoff"] == 0.3
    assert by_ticker["AMD"]["price_vs_200ma_extension_state"] is True
    assert by_ticker["AAPL"]["price_vs_200ma_extension_state"] is False


def test_price_vs_200ma_extension_topup_is_shared_sizing_policy():
    signals = [
        {
            "ticker": "UNH",
            "strategy": "breakout_long",
            "sector": "Healthcare",
            "entry_price": 100.0,
            "stop_price": 90.0,
            "trade_quality_score": 0.95,
            "price_vs_200ma_pct": 0.40,
            "price_vs_200ma_extension_cutoff": 0.30,
            "price_vs_200ma_extension_state": True,
            "conditions_met": {},
        }
    ]

    sized = size_signals(signals, portfolio_value=100_000, risk_pct=0.01)

    sizing = sized[0]["sizing"]
    assert sizing["price_vs_200ma_extension_risk_multiplier_applied"] == (
        constants.PRICE_VS_200MA_EXTENSION_RISK_MULTIPLIER
    )
    assert sizing["price_vs_200ma_extension_baseline_shares"] == 92
    assert sizing["price_vs_200ma_extension_desired_shares"] == 94
    assert sizing["price_vs_200ma_extension_new_shares"] == 94
    assert sizing["shares_to_buy"] == 94
    assert sizing["price_vs_200ma_extension_state"] is True


def test_trend_price_vs_200ma_extension_topup_is_shared_sizing_policy():
    signals = [
        {
            "ticker": "UNH",
            "strategy": "trend_long",
            "sector": "Healthcare",
            "entry_price": 100.0,
            "stop_price": 90.0,
            "trade_quality_score": 0.95,
            "price_vs_200ma_pct": 0.40,
            "price_vs_200ma_extension_cutoff": 0.30,
            "price_vs_200ma_extension_state": True,
            "conditions_met": {},
        },
        {
            "ticker": "PFE",
            "strategy": "breakout_long",
            "sector": "Healthcare",
            "entry_price": 100.0,
            "stop_price": 90.0,
            "trade_quality_score": 0.95,
            "price_vs_200ma_pct": 0.40,
            "price_vs_200ma_extension_cutoff": 0.30,
            "price_vs_200ma_extension_state": True,
            "conditions_met": {},
        },
    ]

    sized = size_signals(signals, portfolio_value=100_000, risk_pct=0.01)

    trend_sizing = sized[0]["sizing"]
    breakout_sizing = sized[1]["sizing"]
    assert trend_sizing["price_vs_200ma_extension_new_shares"] == 94
    assert trend_sizing["trend_price_vs_200ma_extension_baseline_shares"] == 94
    assert trend_sizing["trend_price_vs_200ma_extension_desired_shares"] == 105
    assert trend_sizing["trend_price_vs_200ma_extension_new_shares"] == 105
    assert trend_sizing["shares_to_buy"] == 105
    assert trend_sizing[
        "trend_price_vs_200ma_extension_risk_multiplier_applied"
    ] == constants.TREND_PRICE_VS_200MA_EXTENSION_RISK_MULTIPLIER

    assert breakout_sizing["price_vs_200ma_extension_new_shares"] == 94
    assert breakout_sizing["shares_to_buy"] == 94
    assert (
        breakout_sizing["trend_price_vs_200ma_extension_risk_multiplier_applied"]
        == 1.0
    )


def test_core_confirmed_quality_state_is_shared_risk_enrichment():
    signals = [
        {
            "ticker": "AMD",
            "strategy": "trend_long",
            "entry_price": 100.0,
            "stop_price": 97.0,
            "confidence_score": 1.0,
        },
        {
            "ticker": "MSFT",
            "strategy": "trend_long",
            "entry_price": 100.0,
            "stop_price": 97.0,
            "confidence_score": 1.0,
        },
    ]
    features = {
        "AMD": {
            "atr": 2.0,
            "trend_score": 1.0,
            "volume_spike_ratio": 2.0,
            "momentum_10d_pct": 0.10,
            "momentum_20d_pct": 0.12,
            "signal_day_ticker_open_close_return_pct": 0.01,
        },
        "MSFT": {
            "atr": 2.0,
            "trend_score": 1.0,
            "volume_spike_ratio": 2.0,
            "momentum_10d_pct": 0.10,
            "momentum_20d_pct": 0.12,
            "signal_day_ticker_open_close_return_pct": -0.01,
        },
        "SPY": {
            "atr": 2.0,
            "momentum_20d_pct": 0.05,
            "signal_day_ticker_open_close_return_pct": 0.0,
        },
    }

    enriched = enrich_signals(signals, features)

    by_ticker = {sig["ticker"]: sig for sig in enriched}
    assert by_ticker["AMD"]["trade_quality_score"] == 1.0
    assert by_ticker["AMD"]["rs20_entry_state_leader"] is True
    assert by_ticker["AMD"]["signal_day_ticker_green_candle"] is True
    assert by_ticker["AMD"]["core_confirmed_quality_tqs_min"] == (
        constants.CORE_CONFIRMED_QUALITY_TQS_MIN
    )
    assert by_ticker["AMD"]["core_confirmed_quality_state"] is True
    assert by_ticker["MSFT"]["core_confirmed_quality_state"] is False


def test_core_confirmed_quality_topup_is_shared_sizing_policy():
    signals = [
        {
            "ticker": "AMD",
            "strategy": "trend_long",
            "sector": "Technology",
            "entry_price": 100.0,
            "stop_price": 90.0,
            "trade_quality_score": 1.0,
            "rs20_entry_state_leader": True,
            "signal_day_ticker_green_candle": True,
            "core_confirmed_quality_state": True,
            "core_confirmed_quality_tqs_min": constants.CORE_CONFIRMED_QUALITY_TQS_MIN,
            "conditions_met": {},
        },
        {
            "ticker": "MSFT",
            "strategy": "trend_long",
            "sector": "Technology",
            "entry_price": 100.0,
            "stop_price": 90.0,
            "trade_quality_score": 1.0,
            "rs20_entry_state_leader": True,
            "signal_day_ticker_green_candle": True,
            "core_confirmed_quality_state": False,
            "core_confirmed_quality_tqs_min": constants.CORE_CONFIRMED_QUALITY_TQS_MIN,
            "conditions_met": {},
        },
    ]

    sized = size_signals(signals, portfolio_value=100_000, risk_pct=0.01)

    confirmed = sized[0]["sizing"]
    unconfirmed = sized[1]["sizing"]
    assert unconfirmed["shares_to_buy"] == 106
    assert confirmed["core_confirmed_quality_baseline_shares"] == 106
    assert confirmed["core_confirmed_quality_desired_shares"] == 113
    assert confirmed["core_confirmed_quality_new_shares"] == 113
    assert confirmed["shares_to_buy"] == 113
    assert confirmed["core_confirmed_quality_risk_multiplier_applied"] == (
        constants.CORE_CONFIRMED_QUALITY_RISK_MULTIPLIER
    )
    assert confirmed["core_confirmed_quality_state"] is True
    assert unconfirmed["core_confirmed_quality_risk_multiplier_applied"] == 1.0


def test_green_decel_quality_nonconsumer_state_is_shared_risk_enrichment():
    signals = [
        {
            "ticker": "AMD",
            "strategy": "trend_long",
            "entry_price": 100.0,
            "stop_price": 97.0,
            "confidence_score": 1.0,
        },
        {
            "ticker": "DIS",
            "strategy": "trend_long",
            "entry_price": 100.0,
            "stop_price": 97.0,
            "confidence_score": 1.0,
        },
    ]
    features = {
        "AMD": {
            "atr": 3.0,
            "trend_score": 1.0,
            "volume_spike_ratio": 2.0,
            "momentum_10d_pct": 0.10,
            "momentum_20d_pct": 0.20,
            "signal_day_ticker_open_close_return_pct": 0.01,
        },
        "DIS": {
            "atr": 3.0,
            "trend_score": 1.0,
            "volume_spike_ratio": 2.0,
            "momentum_10d_pct": 0.10,
            "momentum_20d_pct": 0.20,
            "signal_day_ticker_open_close_return_pct": 0.01,
        },
        "SPY": {
            "atr": 3.0,
            "momentum_20d_pct": 0.0,
            "signal_day_ticker_open_close_return_pct": 0.0,
        },
    }

    enriched = enrich_signals(signals, features)
    by_ticker = {sig["ticker"]: sig for sig in enriched}

    assert by_ticker["AMD"]["green_decel_quality_nonconsumer_state"] is True
    assert by_ticker["AMD"]["momentum_10d_minus_20d_pct"] == -0.10
    assert by_ticker["DIS"]["sector"] == "Communication Services"
    assert by_ticker["DIS"]["green_decel_quality_nonconsumer_state"] is False


def test_green_decel_quality_nonconsumer_topup_is_shared_sizing_policy():
    signals = [
        {
            "ticker": "AMD",
            "strategy": "trend_long",
            "sector": "Technology",
            "entry_price": 100.0,
            "stop_price": 90.0,
            "trade_quality_score": 1.0,
            "signal_day_ticker_green_candle": True,
            "green_decel_quality_nonconsumer_state": True,
            "green_decel_quality_nonconsumer_tqs_min": (
                constants.GREEN_DECEL_QUALITY_NONCONSUMER_TQS_MIN
            ),
            "conditions_met": {},
        },
        {
            "ticker": "MSFT",
            "strategy": "trend_long",
            "sector": "Technology",
            "entry_price": 100.0,
            "stop_price": 90.0,
            "trade_quality_score": 1.0,
            "signal_day_ticker_green_candle": True,
            "green_decel_quality_nonconsumer_state": False,
            "green_decel_quality_nonconsumer_tqs_min": (
                constants.GREEN_DECEL_QUALITY_NONCONSUMER_TQS_MIN
            ),
            "conditions_met": {},
        },
    ]

    sized = size_signals(signals, portfolio_value=100_000, risk_pct=0.01)

    confirmed = sized[0]["sizing"]
    unconfirmed = sized[1]["sizing"]
    assert unconfirmed["shares_to_buy"] == 96
    assert confirmed["green_decel_quality_nonconsumer_baseline_shares"] == 96
    assert confirmed["green_decel_quality_nonconsumer_desired_shares"] == 98
    assert confirmed["green_decel_quality_nonconsumer_new_shares"] == 98
    assert confirmed["shares_to_buy"] == 98
    assert confirmed["green_decel_quality_nonconsumer_risk_multiplier_applied"] == (
        constants.GREEN_DECEL_QUALITY_NONCONSUMER_RISK_MULTIPLIER
    )
    assert confirmed["green_decel_quality_nonconsumer_state"] is True
    assert (
        unconfirmed["green_decel_quality_nonconsumer_risk_multiplier_applied"]
        == 1.0
    )


def test_clean_spy_leader_signal_day_cap_is_shared_sizing_policy():
    signals = [
        {
            "ticker": "AMD",
            "strategy": "trend_long",
            "sector": "Technology",
            "entry_price": 100.0,
            "stop_price": 99.0,
            "trade_quality_score": 0.95,
            "regime_exit_bucket": "risk_on",
            "spy_relative_leader": True,
            "signal_day_ticker_outperformed_spy": True,
            "conditions_met": {"pct_from_52w_high": -0.10},
        },
        {
            "ticker": "NVDA",
            "strategy": "trend_long",
            "sector": "Technology",
            "entry_price": 100.0,
            "stop_price": 99.0,
            "trade_quality_score": 0.95,
            "regime_exit_bucket": "risk_on",
            "spy_relative_leader": True,
            "signal_day_ticker_outperformed_spy": False,
            "conditions_met": {"pct_from_52w_high": -0.10},
        },
    ]

    sized = size_signals(signals, portfolio_value=100_000, risk_pct=0.01)

    confirmed = sized[0]["sizing"]
    unconfirmed = sized[1]["sizing"]
    assert confirmed["spy_relative_leader_risk_on_multiplier_applied"] == 2.0
    assert unconfirmed["spy_relative_leader_risk_on_multiplier_applied"] == 2.0
    assert confirmed["max_position_pct_applied"] == (
        constants.CLEAN_SPY_CAP_ONLY_LEADER_MAX_POSITION_PCT
    )
    assert unconfirmed["max_position_pct_applied"] == (
        constants.RISK_ON_SPY_RELATIVE_LEADER_MAX_POSITION_PCT
    )
    assert confirmed["clean_spy_leader_signal_day_max_position_pct_applied"] == (
        constants.CLEAN_SPY_LEADER_SIGNAL_DAY_MAX_POSITION_PCT
    )
    assert confirmed["clean_spy_cap_only_leader_max_position_pct_applied"] == (
        constants.CLEAN_SPY_CAP_ONLY_LEADER_MAX_POSITION_PCT
    )
    assert "clean_spy_leader_signal_day_max_position_pct_applied" not in unconfirmed
    assert confirmed["shares_to_buy"] == 600
    assert unconfirmed["shares_to_buy"] == 500


def test_clean_spy_cap_only_rs20_leader_cap_is_shared_sizing_policy():
    signals = [
        {
            "ticker": "AMD",
            "strategy": "breakout_long",
            "sector": "Technology",
            "entry_price": 100.0,
            "stop_price": 99.0,
            "trade_quality_score": 0.95,
            "regime_exit_bucket": "risk_on",
            "spy_relative_leader": True,
            "signal_day_ticker_outperformed_spy": True,
            "rs20_entry_state_leader": True,
            "conditions_met": {"pct_from_52w_high": -0.10},
        },
        {
            "ticker": "NVDA",
            "strategy": "breakout_long",
            "sector": "Technology",
            "entry_price": 100.0,
            "stop_price": 99.0,
            "trade_quality_score": 0.95,
            "regime_exit_bucket": "risk_on",
            "spy_relative_leader": True,
            "signal_day_ticker_outperformed_spy": True,
            "rs20_entry_state_leader": False,
            "conditions_met": {"pct_from_52w_high": -0.10},
        },
    ]

    sized = size_signals(signals, portfolio_value=100_000, risk_pct=0.01)

    rs20_leader = sized[0]["sizing"]
    non_rs20 = sized[1]["sizing"]
    assert rs20_leader["clean_spy_cap_only_leader_max_position_pct_applied"] == (
        constants.CLEAN_SPY_CAP_ONLY_LEADER_MAX_POSITION_PCT
    )
    assert rs20_leader[
        "clean_spy_cap_only_rs20_leader_max_position_pct_applied"
    ] == constants.CLEAN_SPY_CAP_ONLY_RS20_LEADER_MAX_POSITION_PCT
    assert rs20_leader["max_position_pct_applied"] == (
        constants.CLEAN_SPY_CAP_ONLY_RS20_LEADER_MAX_POSITION_PCT
    )
    assert non_rs20["max_position_pct_applied"] == (
        constants.CLEAN_SPY_CAP_ONLY_LEADER_MAX_POSITION_PCT
    )
    assert "clean_spy_cap_only_rs20_leader_max_position_pct_applied" not in non_rs20
    assert rs20_leader["shares_to_buy"] == 700
    assert non_rs20["shares_to_buy"] == 600


def test_risk_on_unmodified_risk_lift_does_not_stack_on_other_sizing_rules():
    signals = [
        {
            "ticker": "XOM",
            "strategy": "breakout_long",
            "sector": "Energy",
            "entry_price": 100.0,
            "stop_price": 95.0,
            "trade_quality_score": 0.95,
            "regime_exit_bucket": "risk_on",
            "conditions_met": {},
        },
        {
            "ticker": "GLD",
            "strategy": "trend_long",
            "sector": "Commodities",
            "entry_price": 100.0,
            "stop_price": 95.0,
            "trade_quality_score": 0.95,
            "regime_exit_bucket": "risk_on",
            "conditions_met": {"pct_from_52w_high": -0.02},
        },
        {
            "ticker": "XOM",
            "strategy": "breakout_long",
            "sector": "Energy",
            "entry_price": 100.0,
            "stop_price": 95.0,
            "trade_quality_score": 0.95,
            "regime_exit_bucket": "balanced",
            "conditions_met": {},
        },
    ]

    sized = size_signals(signals, portfolio_value=100_000, risk_pct=0.01)

    risk_on_plain = sized[0]["sizing"]
    risk_on_already_boosted = sized[1]["sizing"]
    balanced_plain = sized[2]["sizing"]
    assert risk_on_plain["risk_on_unmodified_risk_multiplier_applied"] == 1.25
    assert risk_on_plain["risk_pct"] == 0.0125
    assert risk_on_already_boosted["trend_commodities_near_high_risk_multiplier_applied"] == 1.5
    assert risk_on_already_boosted["risk_on_unmodified_risk_multiplier_applied"] == 1.0
    assert balanced_plain["risk_on_unmodified_risk_multiplier_applied"] == 1.0
