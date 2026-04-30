import os
import sys


sys.path.insert(0, os.path.dirname(__file__))

from portfolio_engine import size_signals  # noqa: E402


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
