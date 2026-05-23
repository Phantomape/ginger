from pathlib import Path
from copy import deepcopy
import sys


QUANT_DIR = Path(__file__).resolve().parent
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtest_sentiment_attribution import (  # noqa: E402
    build_sentiment_report,
    infer_trade_market_state,
)
from backtester import build_market_state_sentiment_attribution  # noqa: E402


def test_market_state_prefers_entry_visible_state_bucket():
    trade = {
        "ticker": "ABC",
        "entry_date": "2026-01-02",
        "exit_date": "2026-01-10",
        "strategy": "breakout_long",
        "sector": "Technology",
        "state_bucket": "narrow_cap_weight_leadership",
        "regime_exit_bucket": "risk_on",
        "pnl": 1200.0,
    }

    state = infer_trade_market_state(trade)

    assert state["market_state"] == "narrow_theme_mania"
    assert state["market_state_source"] == "entry_visible_context"
    assert state["point_in_time_safe"] is True
    assert state["prediction_usable"] is True
    assert "state_bucket:narrow_cap_weight_leadership" in state["market_state_why"]


def test_market_state_marks_regime_exit_fallback_as_attribution_only():
    trade = {
        "ticker": "XYZ",
        "entry_date": "2026-01-02",
        "exit_date": "2026-01-10",
        "strategy": "trend_long",
        "sector": "Commodities",
        "regime_exit_bucket": "risk_on",
        "pnl": 300.0,
    }

    state = infer_trade_market_state(trade)

    assert state["market_state"] == "proxy_theme_mania_reflation_or_commodity"
    assert state["market_state_source"] == "regime_exit_proxy"
    assert state["point_in_time_safe"] is False
    assert state["prediction_usable"] is False
    assert "fallback_from_regime_exit_bucket" in state["market_state_why"]


def test_report_adds_market_state_attribution_and_readiness():
    result = {
        "period": "sample",
        "expected_value_score": 1.23,
        "trades": [
            {
                "ticker": "ABC",
                "entry_date": "2026-01-02",
                "exit_date": "2026-01-10",
                "strategy": "breakout_long",
                "sector": "Technology",
                "state_bucket": "broad_rotation",
                "pnl": 1000.0,
            },
            {
                "ticker": "XYZ",
                "entry_date": "2026-01-03",
                "exit_date": "2026-01-11",
                "strategy": "trend_long",
                "sector": "Financials",
                "regime_exit_bucket": "risk_on",
                "pnl": -250.0,
            },
        ],
    }

    report = build_sentiment_report(result, include_trades=True)

    assert report["schema_version"] == 2
    assert report["trade_count"] == 2
    assert report["prediction_readiness"]["status"] == "attribution_ready_policy_blocked"
    assert report["prediction_readiness"]["attribution_ready"] is True
    assert report["prediction_readiness"]["policy_research_ready"] is False
    assert report["prediction_readiness"]["point_in_time_safe_trades"] == 1
    assert report["state_policy_research_hints"]["status"] == "historical_attribution_only"
    assert report["state_policy_research_hints"]["attribution_ready"] is True
    states = {
        row["market_state"]: row
        for row in report["market_state_trade_attribution"]
    }
    assert states["rotation_high_dispersion"]["total_pnl"] == 1000.0
    assert states["proxy_theme_mania_financial_leadership"]["total_pnl"] == -250.0
    assert len(report["annotated_trades"]) == 2


def test_backtester_wrapper_attaches_read_only_market_state_attribution():
    result = {
        "period": "sample",
        "expected_value_score": 1.23,
        "trades": [
            {
                "ticker": "ABC",
                "entry_date": "2026-01-02",
                "exit_date": "2026-01-10",
                "strategy": "breakout_long",
                "sector": "Technology",
                "state_bucket": "broad_rotation",
                "pnl": 1000.0,
            },
        ],
    }
    before = deepcopy(result)

    report = build_market_state_sentiment_attribution(result)

    assert result == before
    assert report["read_only"] is True
    assert report["diagnostic_only"] is True
    assert report["source_expected_value_score"] == 1.23
    assert report["production_backtest_parity"]["strategy_behavior_changed"] is False
    assert report["prediction_readiness"]["point_in_time_safe_trades"] == 1
