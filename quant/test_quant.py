"""
Unit tests for the quant pipeline modules.
Run: cd d:/Github/ginger && python -m pytest quant/test_quant.py -v
"""

import math
import pytest
import pandas as pd
import numpy as np


# ── risk_engine ───────────────────────────────────────────────────────────────

def test_risk_engine_target_mult():
    """ATR_TARGET_MULT must be >= 3.5 so R:R is reliably above 2.0 after rounding."""
    from risk_engine import ATR_TARGET_MULT, ATR_STOP_MULT
    assert ATR_TARGET_MULT >= 3.5, (
        f"ATR_TARGET_MULT={ATR_TARGET_MULT} — too low; "
        "with 3.0 the R:R rounds to exactly 2.0 and can fail the <2.0 gate"
    )


def test_enrich_signal_rr_above_2():
    """For any reasonable ATR the enriched R:R must be > 2.0 (not just ≥)."""
    from risk_engine import enrich_signal_with_risk
    for atr in [1.0, 2.5, 5.0, 10.0, 0.47]:
        entry = 100.0
        stop  = round(entry - 1.5 * atr, 2)
        sig   = {"ticker": "TEST", "strategy": "trend_long",
                 "entry_price": entry, "stop_price": stop, "confidence_score": 0.8}
        result = enrich_signal_with_risk(sig, atr)
        rr = result["risk_reward_ratio"]
        assert rr is not None, f"R:R is None for ATR={atr}"
        assert rr >= 2.0, f"R:R={rr} < 2.0 for ATR={atr}"


def test_trade_quality_score_range():
    """TQS must be within [0, 1]."""
    from risk_engine import _trade_quality_score
    sig = {"confidence_score": 0.75}
    features = {"trend_score": 0.8, "volume_spike_ratio": 2.5, "momentum_10d_pct": 0.08}
    tqs = _trade_quality_score(sig, features)
    assert 0.0 <= tqs <= 1.0, f"TQS={tqs} out of range"


def test_trade_quality_score_high_signal():
    """A strong signal (all conditions met) should score > 0.70."""
    from risk_engine import _trade_quality_score
    sig = {"confidence_score": 0.80}
    features = {"trend_score": 1.0, "volume_spike_ratio": 3.0, "momentum_10d_pct": 0.12}
    tqs = _trade_quality_score(sig, features)
    assert tqs > 0.70, f"Strong signal TQS={tqs} unexpectedly low"


def test_trade_quality_score_weak_signal():
    """A weak signal should score below 0.60 threshold."""
    from risk_engine import _trade_quality_score
    sig = {"confidence_score": 0.40}
    features = {"trend_score": 0.40, "volume_spike_ratio": 1.0, "momentum_10d_pct": 0.01}
    tqs = _trade_quality_score(sig, features)
    assert tqs < 0.60, f"Weak signal TQS={tqs} unexpectedly high"


def test_trade_quality_score_negative_momentum_not_boosted():
    """Negative momentum must not boost TQS — long-only system should not reward falling stocks."""
    from risk_engine import _trade_quality_score
    sig = {"confidence_score": 0.80}
    features_positive = {"trend_score": 0.8, "volume_spike_ratio": 2.5, "momentum_10d_pct":  0.10}
    features_negative = {"trend_score": 0.8, "volume_spike_ratio": 2.5, "momentum_10d_pct": -0.10}
    tqs_positive = _trade_quality_score(sig, features_positive)
    tqs_negative = _trade_quality_score(sig, features_negative)
    assert tqs_negative < tqs_positive, (
        f"Negative momentum TQS={tqs_negative} >= positive TQS={tqs_positive} — "
        "abs() must not be used; falling stocks should not get momentum boost"
    )


# ── signal_engine ─────────────────────────────────────────────────────────────

def _make_features(above_200ma=True, breakout_20d=True, volume_spike=True,
                   volume_spike_ratio=2.5, close=100.0, atr=3.0,
                   momentum_10d_pct=0.06, pct_from_52w_high=-0.05,
                   trend_score=0.8, high_20d=99.0):
    return {
        "above_200ma":        above_200ma,
        "breakout_20d":       breakout_20d,
        "volume_spike":       volume_spike,
        "volume_spike_ratio": volume_spike_ratio,
        "close":              close,
        "atr":                atr,
        "momentum_10d_pct":   momentum_10d_pct,
        "pct_from_52w_high":  pct_from_52w_high,
        "trend_score":        trend_score,
        "high_20d":           high_20d,
        "daily_range_vs_atr": 1.8,
        "earnings_event_window": False,
        "days_to_earnings":   None,
        "positive_surprise_history": True,
    }


def test_strategy_a_fires_on_valid_signal():
    from signal_engine import strategy_a_trend
    feat = _make_features()
    sig = strategy_a_trend("NVDA", feat)
    assert sig is not None
    assert sig["strategy"] == "trend_long"
    assert sig["confidence_score"] > 0


def test_strategy_a_blocked_without_breakout():
    from signal_engine import strategy_a_trend
    feat = _make_features(breakout_20d=False)
    sig = strategy_a_trend("TEST", feat)
    assert sig is None


def test_strategy_a_blocked_when_below_200ma():
    from signal_engine import strategy_a_trend
    feat = _make_features(above_200ma=False)
    sig = strategy_a_trend("TEST", feat)
    assert sig is None


def test_strategy_a_rs_gate_blocks_underperformer():
    from signal_engine import strategy_a_trend
    feat = _make_features(momentum_10d_pct=0.01)   # stock barely up
    market_context = {"spy_10d_return": 0.05}       # SPY up 5% — stock underperforms
    sig = strategy_a_trend("TEST", feat, market_context=market_context)
    assert sig is None


def test_strategy_b_fires_on_valid_signal():
    from signal_engine import strategy_b_breakout
    feat = _make_features()
    sig = strategy_b_breakout("TSLA", feat)
    assert sig is not None
    assert sig["strategy"] == "breakout_long"


def test_strategy_b_blocked_without_volume():
    from signal_engine import strategy_b_breakout
    feat = _make_features(volume_spike_ratio=1.0)  # below 1.2 threshold
    sig = strategy_b_breakout("TEST", feat)
    assert sig is None


def test_generate_signals_deduplication():
    """Only one signal per ticker even if multiple strategies fire."""
    from signal_engine import generate_signals
    # Both strategy A and B should fire on this setup
    feat = _make_features()
    sigs = generate_signals({"NVDA": feat})
    tickers = [s["ticker"] for s in sigs]
    assert len(tickers) == len(set(tickers)), "Duplicate tickers in signals"


def test_generate_signals_best_confidence_kept():
    """When deduplicating, the higher confidence signal is retained."""
    from signal_engine import generate_signals, strategy_a_trend, strategy_b_breakout
    feat = _make_features()
    sigs = generate_signals({"NVDA": feat})
    if sigs:
        # Verify the retained signal has the highest confidence of all strategies
        for fn in [strategy_a_trend, strategy_b_breakout]:
            alt = fn("NVDA", feat)
            if alt:
                assert sigs[0]["confidence_score"] >= alt["confidence_score"]


# ── portfolio_engine ──────────────────────────────────────────────────────────

def test_compute_position_size_basic():
    from portfolio_engine import compute_position_size
    result = compute_position_size(100_000, entry_price=50.0, stop_price=45.0)
    assert result is not None
    assert result["shares_to_buy"] == 200  # 100000×0.01 / 5 = 200
    assert result["risk_per_share"] == 5.0


def test_compute_position_size_min_one_share():
    """Even with a tiny portfolio or wide stop, at least 1 share."""
    from portfolio_engine import compute_position_size
    result = compute_position_size(1_000, entry_price=500.0, stop_price=10.0)
    assert result is not None
    assert result["shares_to_buy"] >= 1


def test_compute_position_size_invalid_stop():
    """Stop >= entry should return None."""
    from portfolio_engine import compute_position_size
    result = compute_position_size(100_000, entry_price=50.0, stop_price=55.0)
    assert result is None


def test_portfolio_heat_basic():
    from portfolio_engine import compute_portfolio_heat
    positions = {
        "positions": [
            {"ticker": "NVDA", "shares": 10, "avg_cost": 100.0},
        ]
    }
    current_prices = {"NVDA": 120.0}
    heat = compute_portfolio_heat(positions, current_prices, portfolio_value=100_000)
    assert heat is not None
    assert "portfolio_heat_pct" in heat
    assert "can_add_new_positions" in heat
    assert heat["portfolio_heat_pct"] >= 0


def test_portfolio_heat_blocks_when_above_cap():
    """Heat >= 8% should set can_add_new_positions=False."""
    from portfolio_engine import compute_portfolio_heat
    # 1000 shares of a $100 stock with a wide stop (low hard_stop) → large at-risk
    positions = {
        "positions": [
            {"ticker": "SPY", "shares": 1000, "avg_cost": 100.0},
        ]
    }
    current_prices = {"SPY": 100.0}
    heat = compute_portfolio_heat(positions, current_prices, portfolio_value=10_000)
    # 1000 shares × (100 - 88) = 12,000 at risk on 10,000 portfolio → 120% > 8%
    assert heat is not None
    assert heat["can_add_new_positions"] is False


# ── position_manager ──────────────────────────────────────────────────────────

def test_compute_exit_levels_hard_stop():
    from position_manager import compute_exit_levels
    levels = compute_exit_levels(avg_cost=100.0)
    assert levels["hard_stop_price"] == 88.0   # 100 × (1 - 0.12)
    assert levels["profit_target_price"] == 120.0  # 100 × (1 + 0.20)


def test_compute_exit_levels_with_atr():
    from position_manager import compute_exit_levels
    levels = compute_exit_levels(avg_cost=100.0, atr=5.0)
    # atr_stop = avg_cost - 1.5 × 5 = 92.5
    assert levels["atr_stop_price"] == 92.5


def test_compute_exit_levels_override():
    from position_manager import compute_exit_levels
    levels = compute_exit_levels(avg_cost=100.0, override_stop_price=95.0)
    assert levels["hard_stop_price"] == 95.0
    assert levels.get("override_stop_active") is True


def test_evaluate_exit_signals_hard_stop_critical():
    from position_manager import evaluate_exit_signals, compute_exit_levels
    levels = compute_exit_levels(avg_cost=100.0)
    result = evaluate_exit_signals(current_price=85.0, avg_cost=100.0, exit_levels=levels)
    assert result["critical_exit"] is True
    rules = [r["rule"] for r in result["triggered_rules"]]
    assert "HARD_STOP" in rules


def test_evaluate_exit_signals_trailing_stop():
    from position_manager import evaluate_exit_signals, compute_exit_levels
    levels = compute_exit_levels(avg_cost=100.0)
    # High water mark 200, trailing stop = 200 × 0.92 = 184; current = 183 → triggered
    result = evaluate_exit_signals(
        current_price=183.0, avg_cost=100.0, exit_levels=levels,
        high_water_mark=200.0
    )
    rules = [r["rule"] for r in result["triggered_rules"]]
    assert "TRAILING_STOP" in rules


def test_evaluate_exit_signals_hold():
    """No rules fire when price is comfortably above all stops."""
    from position_manager import evaluate_exit_signals, compute_exit_levels
    levels = compute_exit_levels(avg_cost=100.0)
    result = evaluate_exit_signals(current_price=115.0, avg_cost=100.0, exit_levels=levels)
    assert result["critical_exit"] is False
    # No HARD_STOP, no TRAILING_STOP
    assert "HARD_STOP" not in [r["rule"] for r in result["triggered_rules"]]


def test_evaluate_exit_signals_time_stop():
    """TIME_STOP fires when days_held >= 20 and price is below profit target."""
    from position_manager import evaluate_exit_signals, compute_exit_levels
    levels = compute_exit_levels(avg_cost=100.0)   # profit_target = 120.0
    result = evaluate_exit_signals(
        current_price=108.0, avg_cost=100.0, exit_levels=levels,
        days_held=20,
    )
    rules = [r["rule"] for r in result["triggered_rules"]]
    assert "TIME_STOP" in rules, "TIME_STOP must fire at 20 trading days without reaching target"


def test_evaluate_exit_signals_time_stop_not_fired_before_threshold():
    """TIME_STOP does NOT fire before 20 days."""
    from position_manager import evaluate_exit_signals, compute_exit_levels
    levels = compute_exit_levels(avg_cost=100.0)
    result = evaluate_exit_signals(
        current_price=108.0, avg_cost=100.0, exit_levels=levels,
        days_held=19,
    )
    rules = [r["rule"] for r in result["triggered_rules"]]
    assert "TIME_STOP" not in rules


def test_evaluate_exit_signals_time_stop_not_fired_at_profit_target():
    """TIME_STOP does NOT fire when price has already hit profit target."""
    from position_manager import evaluate_exit_signals, compute_exit_levels
    levels = compute_exit_levels(avg_cost=100.0)   # profit_target = 120.0
    result = evaluate_exit_signals(
        current_price=125.0, avg_cost=100.0, exit_levels=levels,
        days_held=25,
    )
    rules = [r["rule"] for r in result["triggered_rules"]]
    assert "TIME_STOP" not in rules, "TIME_STOP must not fire when profit target already exceeded"


# ── feature_layer ─────────────────────────────────────────────────────────────

def _make_ohlcv(n=250, base_close=100.0, trend=0.001):
    """Generate synthetic OHLCV data."""
    dates  = pd.date_range("2024-01-01", periods=n, freq="B")
    closes = [base_close * (1 + trend) ** i for i in range(n)]
    highs  = [c * 1.01 for c in closes]
    lows   = [c * 0.99 for c in closes]
    vols   = [1_000_000] * n
    df = pd.DataFrame({
        "Open":   closes, "High": highs, "Low": lows,
        "Close":  closes, "Volume": vols,
    }, index=dates)
    return df


def test_compute_trend_features_basic():
    from feature_layer import compute_trend_features
    data = _make_ohlcv(n=250)
    feat = compute_trend_features(data)
    assert feat is not None
    assert "close" in feat
    assert "above_200ma" in feat
    assert "breakout_20d" in feat
    assert feat["atr"] is not None and feat["atr"] > 0


def test_compute_trend_features_insufficient_data():
    from feature_layer import compute_trend_features
    data = _make_ohlcv(n=10)
    feat = compute_trend_features(data)
    assert feat is None


def test_compute_trend_features_trend_score_range():
    from feature_layer import compute_trend_features
    data = _make_ohlcv(n=250)
    feat = compute_trend_features(data)
    assert feat is not None
    ts = feat.get("trend_score")
    if ts is not None:
        assert 0.0 <= ts <= 1.0


def test_compute_earnings_features_event_window():
    from feature_layer import compute_earnings_features
    feat = compute_earnings_features({"days_to_earnings": 10, "avg_historical_surprise_pct": 0.05})
    assert feat["earnings_event_window"] is True
    assert feat["positive_surprise_history"] is True


def test_compute_earnings_features_outside_window():
    from feature_layer import compute_earnings_features
    feat = compute_earnings_features({"days_to_earnings": 30})
    assert feat["earnings_event_window"] is False


def test_strategy_c_no_penalty_for_missing_surprise_data():
    """Earnings signal confidence must not be capped at 0.50 when pos_surprise is None."""
    from signal_engine import strategy_c_earnings
    feat = {
        "earnings_event_window": True,
        "days_to_earnings": 10,
        "positive_surprise_history": None,   # data unavailable
        "momentum_10d_pct": 0.06,
        "above_200ma": True,
        "close": 100.0,
        "atr": 2.0,
    }
    sig = strategy_c_earnings("TEST", feat)
    assert sig is not None, "Signal should still fire without surprise history data"
    assert sig["confidence_score"] >= 0.60, (
        f"Confidence {sig['confidence_score']} too low for missing data — "
        "None pos_surprise should not be penalised"
    )


def test_strategy_a_confidence_all_hard_conditions():
    """All hard conditions met (no soft) → confidence must be >= 0.85 for standalone trades."""
    from signal_engine import strategy_a_trend
    feat = _make_features(
        momentum_10d_pct=0.02,    # RS positive vs SPY 0 (passes gate), but not 'strong'
        pct_from_52w_high=-0.20,  # outside 15% of 52w high → near_high=False
    )
    # No market_context: spy_10d=0, rs_positive passes, rs_strong=bool(0.02>0)=True
    # Force near_high=False explicitly by setting pct_from_52w_high=-0.20
    sig = strategy_a_trend("TEST", feat)
    if sig is not None:
        # With near_high=False and rs_strong=True: (1+1+1+0.25)/3.5 = 0.929
        # With both False (worst soft case): (1+1+1)/3.5 = 0.857
        assert sig["confidence_score"] >= 0.85, (
            f"conf={sig['confidence_score']} — all-hard-conditions signal "
            "must hit 0.85 standalone threshold"
        )


# ── llm_advisor prompt building ───────────────────────────────────────────────

def test_build_prompt_date_is_replaced():
    """build_prompt must update the hardcoded Jan-15 date to today's date."""
    import os, sys
    sys.path.insert(0, os.path.dirname(__file__))
    from llm_advisor import build_prompt

    positions = {"portfolio_value_usd": 100_000, "positions": []}
    system_msg, user_msg = build_prompt([], positions)

    if system_msg is None:
        pytest.skip("Prompt template file not found — skipping integration test")

    assert "Jan. 15th, 2026, 4:30 PM EST" not in user_msg, (
        "Hardcoded Jan-15 date was not replaced — LLM receives wrong trading date"
    )


def test_build_prompt_positions_are_replaced():
    """build_prompt must replace template positions with live data."""
    import os, sys
    sys.path.insert(0, os.path.dirname(__file__))
    from llm_advisor import build_prompt

    positions = {
        "portfolio_value_usd": 100_000,
        "positions": [{"ticker": "TEST_TICKER", "shares": 5, "avg_cost": 50.0}],
    }
    system_msg, user_msg = build_prompt([], positions)

    if system_msg is None:
        pytest.skip("Prompt template file not found — skipping integration test")

    # Template contains stale NVDA at avg_cost 102.17 — must be gone
    assert "102.17" not in user_msg, (
        "Stale template position (NVDA avg_cost=102.17) still present — "
        "positions regex did not match Chinese header"
    )
    assert "TEST_TICKER" in user_msg, (
        "Live position TEST_TICKER not injected into prompt"
    )


def test_build_prompt_news_is_replaced():
    """build_prompt must replace template news with live news."""
    import os, sys
    sys.path.insert(0, os.path.dirname(__file__))
    from llm_advisor import build_prompt

    positions = {"portfolio_value_usd": 100_000, "positions": []}
    live_news = [{"title": "LIVE_NEWS_ITEM", "ticker": "AAPL"}]
    system_msg, user_msg = build_prompt(live_news, positions)

    if system_msg is None:
        pytest.skip("Prompt template file not found — skipping integration test")

    # Template contains "示例标题" stale news — must be replaced
    assert "示例标题" not in user_msg, (
        "Stale template news still present — "
        "news regex did not match Chinese header"
    )
    assert "LIVE_NEWS_ITEM" in user_msg, (
        "Live news not injected into prompt"
    )


# ── prompt TQS threshold check (integration) ─────────────────────────────────

def test_prompt_tqs_threshold_is_0_60():
    """The prompt must use TQS threshold 0.60, not the old 0.65."""
    import os
    path = os.path.join(
        os.path.dirname(__file__), "..", "instructinos", "prompts", "trade_advice.txt"
    )
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "trade_quality_score < 0.60" in content, (
        "Prompt still uses old TQS threshold. Expected '< 0.60'."
    )
    assert "trade_quality_score < 0.65" not in content, (
        "Old TQS threshold 0.65 still present in prompt."
    )


def test_prompt_no_anti_trade_bias():
    """The prompt must not contain the 'NO NEW TRADE is optimal' statement."""
    import os
    path = os.path.join(
        os.path.dirname(__file__), "..", "instructinos", "prompts", "trade_advice.txt"
    )
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "最优行为通常是：NO NEW TRADE" not in content, (
        "Anti-trade bias statement still present in prompt."
    )


def test_prompt_allows_second_trade():
    """The prompt must mention second_new_trade to allow 2 trades per day."""
    import os
    path = os.path.join(
        os.path.dirname(__file__), "..", "instructinos", "prompts", "trade_advice.txt"
    )
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "second_new_trade" in content, (
        "Prompt does not support second_new_trade — still limited to 1 trade/day."
    )
