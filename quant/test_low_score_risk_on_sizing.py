import os
import sys


sys.path.insert(0, os.path.dirname(__file__))

from portfolio_engine import size_signals  # noqa: E402
from constants import (  # noqa: E402
    RS20_ENTRY_STATE_RISK_MULTIPLIER,
    SIGNAL_DAY_TICKER_GREEN_RISK_MULTIPLIER,
)


def test_low_score_plain_risk_on_uses_dedicated_non_stacking_lift():
    signals = [
        {
            "ticker": "CVX",
            "strategy": "breakout_long",
            "sector": "Energy",
            "entry_price": 100.0,
            "stop_price": 95.0,
            "trade_quality_score": 0.95,
            "regime_exit_bucket": "risk_on",
            "regime_exit_score": 0.08,
            "conditions_met": {},
        },
        {
            "ticker": "XOM",
            "strategy": "breakout_long",
            "sector": "Energy",
            "entry_price": 100.0,
            "stop_price": 95.0,
            "trade_quality_score": 0.95,
            "regime_exit_bucket": "risk_on",
            "regime_exit_score": 0.12,
            "conditions_met": {},
        },
        {
            "ticker": "XLU",
            "strategy": "breakout_long",
            "sector": "ETF",
            "entry_price": 100.0,
            "stop_price": 95.0,
            "trade_quality_score": 0.95,
            "regime_exit_bucket": "risk_on",
            "regime_exit_score": 0.22,
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
            "regime_exit_score": 0.08,
            "conditions_met": {"pct_from_52w_high": -0.02},
        },
    ]

    sized = size_signals(signals, portfolio_value=100_000, risk_pct=0.01)

    low_score_plain = sized[0]["sizing"]
    mid_score_plain = sized[1]["sizing"]
    higher_score_plain = sized[2]["sizing"]
    already_boosted = sized[3]["sizing"]

    assert low_score_plain["risk_on_unmodified_risk_multiplier_applied"] == 1.5
    assert low_score_plain["risk_pct"] == 0.015
    assert mid_score_plain["risk_on_unmodified_risk_multiplier_applied"] == 1.6
    assert mid_score_plain["risk_pct"] == 0.016
    assert higher_score_plain["risk_on_unmodified_risk_multiplier_applied"] == 1.25
    assert higher_score_plain["risk_pct"] == 0.0125
    assert already_boosted["trend_commodities_near_high_risk_multiplier_applied"] == 1.5
    assert already_boosted["risk_on_unmodified_risk_multiplier_applied"] == 1.0


def test_spy_relative_leader_overrides_plain_risk_on_score_lift_only():
    signals = [
        {
            "ticker": "CVX",
            "strategy": "breakout_long",
            "sector": "Energy",
            "entry_price": 100.0,
            "stop_price": 95.0,
            "trade_quality_score": 0.95,
            "regime_exit_bucket": "risk_on",
            "regime_exit_score": 0.08,
            "spy_relative_leader": True,
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
            "regime_exit_score": 0.08,
            "spy_relative_leader": True,
            "conditions_met": {"pct_from_52w_high": -0.02},
        },
    ]

    sized = size_signals(signals, portfolio_value=100_000, risk_pct=0.01)

    plain_leader = sized[0]["sizing"]
    already_boosted = sized[1]["sizing"]
    assert plain_leader["risk_on_unmodified_risk_multiplier_applied"] == 2.0
    assert plain_leader["spy_relative_leader_risk_on_multiplier_applied"] == 2.0
    assert plain_leader["risk_pct"] == 0.02
    assert already_boosted["trend_commodities_near_high_risk_multiplier_applied"] == 1.5
    assert already_boosted["risk_on_unmodified_risk_multiplier_applied"] == 1.0
    assert already_boosted["spy_relative_leader_risk_on_multiplier_applied"] == 1.0


def test_rs20_entry_state_leader_gets_cap_aware_post_sizing_top_up():
    signals = [
        {
            "ticker": "AMD",
            "strategy": "trend_long",
            "sector": "Technology",
            "entry_price": 100.0,
            "stop_price": 95.0,
            "trade_quality_score": 0.95,
            "regime_exit_bucket": "balanced",
            "conditions_met": {},
            "rs20_entry_state_leader": True,
        },
        {
            "ticker": "MSFT",
            "strategy": "trend_long",
            "sector": "Technology",
            "entry_price": 100.0,
            "stop_price": 95.0,
            "trade_quality_score": 0.95,
            "regime_exit_bucket": "balanced",
            "conditions_met": {},
            "rs20_entry_state_leader": False,
        },
    ]

    leader, non_leader = [
        item["sizing"] for item in size_signals(signals, portfolio_value=100_000)
    ]

    expected_shares = int(
        non_leader["shares_to_buy"] * RS20_ENTRY_STATE_RISK_MULTIPLIER
    )
    assert leader["rs20_entry_state_risk_multiplier_applied"] == (
        RS20_ENTRY_STATE_RISK_MULTIPLIER
    )
    assert leader["rs20_entry_state_baseline_shares"] == non_leader["shares_to_buy"]
    assert leader["shares_to_buy"] == expected_shares
    assert leader["position_value_usd"] == expected_shares * 100.0
    assert leader["position_pct_of_portfolio"] == round(
        expected_shares * 100.0 / 100_000,
        4,
    )
    assert leader["risk_pct"] > non_leader["risk_pct"]
    assert non_leader["rs20_entry_state_risk_multiplier_applied"] == 1.0


def test_signal_day_green_candle_gets_cap_aware_post_sizing_top_up():
    signals = [
        {
            "ticker": "AMD",
            "strategy": "trend_long",
            "sector": "Technology",
            "entry_price": 100.0,
            "stop_price": 95.0,
            "trade_quality_score": 0.95,
            "regime_exit_bucket": "balanced",
            "conditions_met": {},
            "signal_day_ticker_green_candle": True,
        },
        {
            "ticker": "MSFT",
            "strategy": "trend_long",
            "sector": "Technology",
            "entry_price": 100.0,
            "stop_price": 95.0,
            "trade_quality_score": 0.95,
            "regime_exit_bucket": "balanced",
            "conditions_met": {},
            "signal_day_ticker_green_candle": False,
        },
    ]

    green, not_green = [
        item["sizing"] for item in size_signals(signals, portfolio_value=100_000)
    ]

    expected_shares = int(
        not_green["shares_to_buy"] * SIGNAL_DAY_TICKER_GREEN_RISK_MULTIPLIER
    )
    assert green["signal_day_ticker_green_risk_multiplier_applied"] == (
        SIGNAL_DAY_TICKER_GREEN_RISK_MULTIPLIER
    )
    assert green["signal_day_ticker_green_baseline_shares"] == not_green["shares_to_buy"]
    assert green["shares_to_buy"] == expected_shares
    assert green["risk_pct"] > not_green["risk_pct"]
    assert not_green["signal_day_ticker_green_risk_multiplier_applied"] == 1.0


def test_signal_day_green_candle_top_up_respects_position_cap():
    signal = {
        "ticker": "AMD",
        "strategy": "trend_long",
        "sector": "Technology",
        "entry_price": 100.0,
        "stop_price": 99.0,
        "trade_quality_score": 0.95,
        "regime_exit_bucket": "balanced",
        "conditions_met": {},
        "signal_day_ticker_green_candle": True,
    }

    sizing = size_signals([signal], portfolio_value=100_000)[0]["sizing"]

    assert sizing["shares_to_buy"] == 400
    assert sizing["position_pct_of_portfolio"] == 0.4
    assert sizing["signal_day_ticker_green_risk_multiplier_applied"] == 1.0
