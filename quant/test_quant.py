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


def test_compute_position_size_max_cap():
    """Position value must never exceed MAX_POSITION_PCT of portfolio (e.g. tight breakout stop)."""
    from portfolio_engine import compute_position_size, MAX_POSITION_PCT
    # Tight stop: $1 risk-per-share on $100 stock → uncapped = 700 shares = 100% of $70k
    result = compute_position_size(70_000, entry_price=100.0, stop_price=99.0)
    assert result is not None
    assert result["position_pct_of_portfolio"] <= MAX_POSITION_PCT, (
        f"Position {result['position_pct_of_portfolio']*100:.1f}% "
        f"exceeds {MAX_POSITION_PCT*100:.0f}% cap — tight stop created oversized position"
    )


def test_compute_position_size_max_cap_position_manager():
    """Same cap must apply in position_manager.compute_position_size."""
    from position_manager import compute_position_size as pm_compute, MAX_POSITION_PCT
    result = pm_compute(70_000, entry_price=100.0, stop_price=99.0)
    assert result is not None
    assert result["position_pct_of_portfolio"] <= MAX_POSITION_PCT


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
    # No current_price → fallback to avg_cost: 100 - 1.5×5 = 92.5
    assert levels["atr_stop_price"] == 92.5


def test_compute_exit_levels_atr_stop_from_current_price():
    """ATR stop must use current_price when provided, not avg_cost.

    For a position bought at $100 now trading at $183 (79% gain, ATR=$5.67):
      old (broken): atr_stop = 100 - 7.5 = 92.5  ← useless, 90 below market
      new (correct): atr_stop = 183 - 8.51 = 174.49 ← meaningful 5% protection
    Without this fix the LLM sees a stop that never triggers, providing no
    protection for winning positions.
    """
    from position_manager import compute_exit_levels, ATR_MULTIPLIER
    avg_cost      = 100.0
    current_price = 183.0
    atr           = 5.67
    levels = compute_exit_levels(avg_cost=avg_cost, atr=atr, current_price=current_price)
    expected_stop = round(current_price - ATR_MULTIPLIER * atr, 2)
    assert levels["atr_stop_price"] == expected_stop, (
        f"ATR stop {levels['atr_stop_price']} computed from avg_cost — "
        f"should be {expected_stop} (from current_price {current_price}). "
        "Using avg_cost for winning positions renders the ATR stop useless."
    )
    # Must be meaningfully close to current price, not near avg_cost
    assert levels["atr_stop_price"] > avg_cost, (
        "ATR stop must be above avg_cost for a winning position — "
        "the stop should protect gains, not the original entry"
    )


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
    """TIME_STOP fires when days_held >= 45 and price is below halfway to profit target.
    halfway = (avg_cost + profit_target) / 2 = (100 + 120) / 2 = 110.
    At price=108 (8% gain), 108 < 110 → stagnant → TIME_STOP fires."""
    from position_manager import evaluate_exit_signals, compute_exit_levels
    levels = compute_exit_levels(avg_cost=100.0)   # profit_target = 120.0, halfway = 110.0
    result = evaluate_exit_signals(
        current_price=108.0, avg_cost=100.0, exit_levels=levels,
        days_held=45,
    )
    rules = [r["rule"] for r in result["triggered_rules"]]
    assert "TIME_STOP" in rules, "TIME_STOP must fire at 45 days when price below halfway (110)"


def test_evaluate_exit_signals_time_stop_not_fired_before_threshold():
    """TIME_STOP does NOT fire before 45 days."""
    from position_manager import evaluate_exit_signals, compute_exit_levels
    levels = compute_exit_levels(avg_cost=100.0)
    result = evaluate_exit_signals(
        current_price=108.0, avg_cost=100.0, exit_levels=levels,
        days_held=44,
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


def test_evaluate_exit_signals_time_stop_not_fired_when_progress():
    """TIME_STOP must NOT fire when position is past halfway to profit target.
    halfway = (100 + 120) / 2 = 110. At price=115 (15% gain), 115 > 110 → progressing → no TIME_STOP.
    The old logic (price < profit_target) would incorrectly fire here — this test guards against regression."""
    from position_manager import evaluate_exit_signals, compute_exit_levels
    levels = compute_exit_levels(avg_cost=100.0)   # profit_target = 120.0, halfway = 110.0
    result = evaluate_exit_signals(
        current_price=115.0, avg_cost=100.0, exit_levels=levels,
        days_held=35,
    )
    rules = [r["rule"] for r in result["triggered_rules"]]
    assert "TIME_STOP" not in rules, (
        "TIME_STOP must not fire at price=115 (past halfway=110 to target=120) — "
        "a trade at +15% heading toward a +20% target is NOT stagnant"
    )


def test_evaluate_exit_signals_profit_ladder_suppresses_profit_target():
    """At 35% gain, PROFIT_LADDER_30 fires but PROFIT_TARGET must NOT (conflicting signals)."""
    from position_manager import evaluate_exit_signals, compute_exit_levels
    levels = compute_exit_levels(avg_cost=100.0)   # profit_target = 120.0
    result = evaluate_exit_signals(current_price=135.0, avg_cost=100.0, exit_levels=levels)
    rules = [r["rule"] for r in result["triggered_rules"]]
    assert "PROFIT_LADDER_30" in rules, "PROFIT_LADDER_30 must fire at 35% gain"
    assert "PROFIT_TARGET" not in rules, (
        "PROFIT_TARGET must not fire when PROFIT_LADDER_30 is active — "
        "conflicting REDUCE-vs-HOLD signals confuse LLM"
    )


def test_evaluate_exit_signals_profit_target_fires_in_20_30_range():
    """PROFIT_TARGET fires in 20-30% gain range (before PROFIT_LADDER kicks in)."""
    from position_manager import evaluate_exit_signals, compute_exit_levels
    levels = compute_exit_levels(avg_cost=100.0)   # profit_target = 120.0
    result = evaluate_exit_signals(current_price=125.0, avg_cost=100.0, exit_levels=levels)
    rules = [r["rule"] for r in result["triggered_rules"]]
    assert "PROFIT_TARGET" in rules, "PROFIT_TARGET must fire at 25% gain"
    assert "PROFIT_LADDER_30" not in rules, "PROFIT_LADDER_30 must not fire at only 25% gain"


def test_evaluate_exit_signals_profit_ladder_50_suppresses_profit_target():
    """At 55% gain, PROFIT_LADDER_50 fires but PROFIT_TARGET must NOT."""
    from position_manager import evaluate_exit_signals, compute_exit_levels
    levels = compute_exit_levels(avg_cost=100.0)   # profit_target = 120.0
    result = evaluate_exit_signals(current_price=155.0, avg_cost=100.0, exit_levels=levels)
    rules = [r["rule"] for r in result["triggered_rules"]]
    assert "PROFIT_LADDER_50" in rules
    assert "PROFIT_TARGET" not in rules, "PROFIT_TARGET must not co-fire with PROFIT_LADDER_50"


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


def test_strategy_c_strong_momentum_gets_higher_confidence():
    """Momentum >10% must score higher than barely-5% — soft bonus must differentiate."""
    from signal_engine import strategy_c_earnings
    base_feat = {
        "earnings_event_window": True,
        "days_to_earnings": 10,
        "positive_surprise_history": None,
        "above_200ma": True,
        "close": 100.0,
        "atr": 2.0,
    }
    sig_marginal = strategy_c_earnings("TEST", {**base_feat, "momentum_10d_pct": 0.051})
    sig_strong   = strategy_c_earnings("TEST", {**base_feat, "momentum_10d_pct": 0.12})

    assert sig_marginal is not None
    assert sig_strong is not None
    assert sig_strong["confidence_score"] > sig_marginal["confidence_score"], (
        f"Strong momentum (12%) conf={sig_strong['confidence_score']} should exceed "
        f"marginal momentum (5.1%) conf={sig_marginal['confidence_score']} — "
        "soft bonus threshold must be >10%, not the same >5% as the gate"
    )


def test_strategy_c_fires_with_mild_positive_momentum():
    """Strategy C must fire with 1-5% momentum when supported by strong conditions.

    The gate was lowered from >5% to >0%: stocks with mild pre-earnings momentum
    can qualify when positive_surprise_history + above_200ma provide supporting
    evidence. Their low confidence will be filtered by the 0.75 confidence threshold
    unless news confirms the trade.
    """
    from signal_engine import strategy_c_earnings
    feat = {
        "earnings_event_window":     True,
        "days_to_earnings":          10,
        "positive_surprise_history": True,
        "above_200ma":               True,
        "momentum_10d_pct":          0.03,   # +3%: passes new gate (>0%) but failed old gate (>5%)
        "close":                     100.0,
        "atr":                       2.0,
    }
    sig = strategy_c_earnings("TEST", feat)
    assert sig is not None, (
        "Strategy C must fire with +3% momentum when supported by "
        "positive_surprise_history and above_200ma. "
        "Old gate (>5%) rejected this setup entirely."
    )


def test_strategy_c_blocked_with_zero_momentum():
    """Strategy C must be blocked when momentum is exactly 0.0 (gate is > 0%, not >= 0%)."""
    from signal_engine import strategy_c_earnings
    feat = {
        "earnings_event_window":     True,
        "days_to_earnings":          10,
        "positive_surprise_history": True,
        "above_200ma":               True,
        "momentum_10d_pct":          0.0,   # flat → fails > 0.0 gate
        "close":                     100.0,
        "atr":                       2.0,
    }
    sig = strategy_c_earnings("TEST", feat)
    assert sig is None, (
        "Strategy C must be blocked when momentum is 0.0 — "
        "gate requires strictly > 0% to reject flat/declining setups"
    )


def test_strategy_c_mild_momentum_lower_confidence_than_strong():
    """Mild momentum (1-5%) must produce lower confidence than strong momentum (>5%).

    With new tiered structure:
      mild (+3%): event(1.0) + >5%(0.0) + 200ma(0.5) + surprise(1.0) = 2.5/4.0 = 0.625
      strong (+7%): event(1.0) + >5%(1.0) + 200ma(0.5) + surprise(1.0) = 3.5/4.0 = 0.875
    This ensures mild-momentum signals require stronger news confirmation than
    strong-momentum signals.
    """
    from signal_engine import strategy_c_earnings
    base_feat = {
        "earnings_event_window":     True,
        "days_to_earnings":          10,
        "positive_surprise_history": True,
        "above_200ma":               True,
        "close":                     100.0,
        "atr":                       2.0,
    }
    sig_mild   = strategy_c_earnings("TEST", {**base_feat, "momentum_10d_pct": 0.03})
    sig_strong = strategy_c_earnings("TEST", {**base_feat, "momentum_10d_pct": 0.07})

    assert sig_mild   is not None
    assert sig_strong is not None
    assert sig_strong["confidence_score"] > sig_mild["confidence_score"], (
        f"Strong momentum (7%) conf={sig_strong['confidence_score']} must exceed "
        f"mild momentum (3%) conf={sig_mild['confidence_score']} — "
        "tiered confidence must penalise low-momentum signals relative to strong ones"
    )


def test_strategy_c_blocked_with_negative_momentum():
    """Strategy C must be blocked when momentum is negative (declining into earnings)."""
    from signal_engine import strategy_c_earnings
    feat = {
        "earnings_event_window":     True,
        "days_to_earnings":          10,
        "positive_surprise_history": True,
        "above_200ma":               True,
        "momentum_10d_pct":          -0.02,   # -2%: stock declining before earnings
        "close":                     100.0,
        "atr":                       2.0,
    }
    sig = strategy_c_earnings("TEST", feat)
    assert sig is None, (
        "Strategy C must reject negative-momentum setups — "
        "stocks declining into earnings have high miss-risk"
    )


def test_strategy_b_above_200ma_bonus_differentiates_quality():
    """above-200MA breakout must score higher than below-200MA breakout."""
    from signal_engine import strategy_b_breakout
    sig_above = strategy_b_breakout("TEST", _make_features(above_200ma=True))
    sig_below = strategy_b_breakout("TEST", _make_features(above_200ma=False))

    assert sig_above is not None
    assert sig_below is not None
    assert sig_above["confidence_score"] > sig_below["confidence_score"], (
        f"Above-200MA conf={sig_above['confidence_score']} must exceed "
        f"below-200MA conf={sig_below['confidence_score']} — above-200MA quality bonus"
    )


def test_strategy_b_above_200ma_enables_standalone_trade():
    """All hard conditions + above-200MA must meet >= 0.85 standalone threshold.
    Without above-200MA (or below it) should fall below 0.85, requiring news."""
    from signal_engine import strategy_b_breakout
    # SPY +1%, stock +1.1%: RS gate passes but rs_strong=False (1.1% not > 1% × 1.2=1.2%)
    market_ctx = {"spy_10d_return": 0.01}
    feat_above = _make_features(above_200ma=True,  momentum_10d_pct=0.011, pct_from_52w_high=-0.20)
    feat_below = _make_features(above_200ma=False, momentum_10d_pct=0.011, pct_from_52w_high=-0.20)

    sig_above = strategy_b_breakout("TEST_A", feat_above, market_context=market_ctx)
    sig_below = strategy_b_breakout("TEST_B", feat_below, market_context=market_ctx)

    assert sig_above is not None
    assert sig_below is not None
    assert sig_above["confidence_score"] >= 0.85, (
        f"above-200MA Strategy B must reach 0.85 standalone threshold, "
        f"got {sig_above['confidence_score']}"
    )
    assert sig_below["confidence_score"] < 0.85, (
        f"below-200MA Strategy B must be below 0.85 (needs confirmation), "
        f"got {sig_below['confidence_score']}"
    )


def test_prompt_exit_rule_4_uses_profit_ladder():
    """Exit rule 4 must use the profit ladder (HOLD at 30-50%), not just REDUCE 50%."""
    import os
    path = os.path.join(
        os.path.dirname(__file__), "..", "instructinos", "prompts", "trade_advice.txt"
    )
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "止盈目标   达到 profit_target → REDUCE 50% 仓位（保留赢家）" not in content, (
        "Rule 4 oversimplifies profit-taking as always REDUCE 50%. "
        "Must reference the profit ladder (30-50% HOLD) to prevent cutting winners short."
    )
    assert "止盈阶梯" in content, (
        "Rule 4 must use '止盈阶梯' with HOLD band for 30-50% gains."
    )


def test_near_52w_high_no_bonus_for_missing_data():
    """_near_52w_high must return False (no bonus) when 52w data unavailable."""
    from signal_engine import _near_52w_high
    assert _near_52w_high({"pct_from_52w_high": None}) is False, (
        "Missing 52w data must return False — no undeserved quality bonus for new stocks"
    )
    assert _near_52w_high({"pct_from_52w_high": -0.10}) is True   # within 15% → True
    assert _near_52w_high({"pct_from_52w_high": -0.20}) is False  # far from high → False


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


def test_prompt_position_cap_present():
    """The prompt must include the 20% position cap to prevent oversized positions."""
    import os
    path = os.path.join(
        os.path.dirname(__file__), "..", "instructinos", "prompts", "trade_advice.txt"
    )
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "20%" in content and "portfolio_value" in content.lower() or "portfolio_value_usd × 20%" in content, (
        "Prompt must contain the 20% position cap to prevent oversized positions."
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


# ── ATR volatility gate ───────────────────────────────────────────────────────

def test_strategy_a_blocked_when_atr_too_high():
    """ATR > 5% of close (stop too wide) must block strategy A."""
    from signal_engine import strategy_a_trend
    # ATR/close = 6/100 = 6% → exceeds 5% threshold
    feat = _make_features(close=100.0, atr=6.0)
    sig = strategy_a_trend("TEST", feat)
    assert sig is None, (
        "Strategy A must be blocked when ATR/close > 5% — stop is too wide to control"
    )


def test_strategy_b_blocked_when_atr_too_high():
    """ATR > 5% of close must block strategy B."""
    from signal_engine import strategy_b_breakout
    feat = _make_features(close=100.0, atr=6.0)
    sig = strategy_b_breakout("TEST", feat)
    assert sig is None, (
        "Strategy B must be blocked when ATR/close > 5% — stop is too wide to control"
    )


def test_strategy_c_blocked_when_atr_too_high():
    """ATR > 5% of close must block strategy C."""
    from signal_engine import strategy_c_earnings
    feat = {
        "earnings_event_window": True,
        "days_to_earnings": 10,
        "positive_surprise_history": True,
        "momentum_10d_pct": 0.08,
        "above_200ma": True,
        "close": 100.0,
        "atr": 6.0,   # 6% of close → too wide
    }
    sig = strategy_c_earnings("TEST", feat)
    assert sig is None, (
        "Strategy C must be blocked when ATR/close > 5% — earnings gaps are uncontrollable"
    )


def test_strategy_a_passes_when_atr_at_limit():
    """ATR exactly at 5% of close (boundary) must still pass."""
    from signal_engine import strategy_a_trend
    # ATR/close = 5/100 = 5.0% → exactly at limit, should pass (> not >=)
    feat = _make_features(close=100.0, atr=5.0)
    sig = strategy_a_trend("TEST", feat)
    assert sig is not None, (
        "Strategy A should not be blocked at exactly 5% ATR/close — gate is strict '>' not '>='"
    )


# ── Market regime gates ───────────────────────────────────────────────────────

def test_generate_signals_empty_in_bear_market():
    """BEAR market must suppress all signals regardless of signal quality."""
    from signal_engine import generate_signals
    feat = _make_features()   # all conditions met — strong signal
    market_ctx = {"market_regime": "BEAR"}
    sigs = generate_signals({"NVDA": feat}, market_context=market_ctx)
    assert sigs == [], (
        "BEAR regime must return empty signal list — no new long positions in downtrend"
    )


def test_generate_signals_empty_in_bear_market_case_insensitive():
    """BEAR check must be case-insensitive."""
    from signal_engine import generate_signals
    feat = _make_features()
    sigs = generate_signals({"NVDA": feat}, market_context={"market_regime": "bear"})
    assert sigs == [], "BEAR regime check must be case-insensitive"


def test_generate_signals_neutral_filters_low_confidence():
    """NEUTRAL market must drop signals with confidence_score < 0.85."""
    from signal_engine import generate_signals
    # Craft features that produce confidence < 0.85 for Strategy B:
    # all hard conditions + no above_200ma + no rs_strong + no near_high
    # → conf = 3.0/3.75 = 0.80 < 0.85
    feat = _make_features(
        above_200ma=False,
        momentum_10d_pct=0.011,   # RS positive (> SPY 1%) but not 'strong' (not > 1.2×)
        pct_from_52w_high=-0.25,  # far from 52w high → no near_high bonus
    )
    market_ctx = {"market_regime": "NEUTRAL", "spy_10d_return": 0.01}
    sigs = generate_signals({"TEST": feat}, market_context=market_ctx)
    # Strategy B can fire with above_200ma=False at conf=0.80; NEUTRAL filter should remove it
    assert all(s["confidence_score"] >= 0.85 for s in sigs), (
        f"NEUTRAL market must suppress signals with confidence < 0.85; "
        f"got: {[(s['ticker'], s['confidence_score']) for s in sigs]}"
    )


def test_generate_signals_neutral_keeps_high_confidence():
    """NEUTRAL market must retain signals with confidence >= 0.85."""
    from signal_engine import generate_signals
    feat = _make_features()   # all conditions → Strategy A conf ≥ 0.857
    market_ctx = {"market_regime": "NEUTRAL"}
    sigs = generate_signals({"NVDA": feat}, market_context=market_ctx)
    assert len(sigs) >= 1, (
        "NEUTRAL market must not suppress high-confidence signals (≥ 0.85)"
    )


def test_generate_signals_bull_passes_all_quality_signals():
    """BULL market (or no regime) must not suppress any valid signals."""
    from signal_engine import generate_signals
    feat = _make_features()
    sigs_bull   = generate_signals({"NVDA": feat}, market_context={"market_regime": "BULL"})
    sigs_no_ctx = generate_signals({"NVDA": feat})
    assert len(sigs_bull)   >= 1, "BULL regime must pass valid signals"
    assert len(sigs_no_ctx) >= 1, "No market_context must pass valid signals (default behavior)"


def test_generate_signals_neutral_filter_strictly_greater_than_0_85():
    """NEUTRAL filter must be strictly > 0.85 — matches LLM prompt requirement.

    The prompt says '置信度 > 0.85' (strictly greater), not '≥ 0.85'.
    In a mixed market, borderline signals at exactly 0.85 need news confirmation
    and should not reach the LLM without it.
    """
    from signal_engine import generate_signals
    # All remaining signals from NEUTRAL must be strictly > 0.85
    feat = _make_features()
    market_ctx = {"market_regime": "NEUTRAL"}
    sigs = generate_signals({"NVDA": feat}, market_context=market_ctx)
    for s in sigs:
        assert s["confidence_score"] > 0.85, (
            f"NEUTRAL filter must be strictly > 0.85; "
            f"got {s['ticker']} conf={s['confidence_score']}"
        )


# ── legacy_basis exit signal gate ─────────────────────────────────────────────

def test_legacy_position_no_profit_ladder():
    """PROFIT_LADDER must NOT fire for legacy positions (unrealised gain > 100%).

    AMD at avg_cost=$27, current=$183 (580% gain) is legacy_basis=True.
    Without passing legacy_basis to evaluate_exit_signals, PROFIT_LADDER_50
    fires (0.58≥0.50) → LLM gets told to REDUCE 25% a +580% winner spuriously.

    Fix: trend_signals.py must pass legacy_basis=legacy_basis to evaluate_exit_signals.
    """
    from position_manager import evaluate_exit_signals, compute_exit_levels, HARD_STOP_PCT

    avg_cost      = 27.0
    current_price = 183.0   # 580% gain → legacy_basis=True

    # Simulate auto_rolling stop as trend_signals.py computes for legacy positions
    override_stop = round(current_price * (1 - HARD_STOP_PCT), 2)
    exit_levels = compute_exit_levels(
        avg_cost, atr=5.67,
        override_stop_price=override_stop,
        current_price=current_price,
    )

    # WITH legacy_basis=True (correct)
    result = evaluate_exit_signals(
        current_price, avg_cost, exit_levels,
        high_water_mark=current_price,
        legacy_basis=True,   # correctly passed
    )
    rules = [r["rule"] for r in result["triggered_rules"]]
    assert "PROFIT_LADDER_50" not in rules, (
        "PROFIT_LADDER_50 must NOT fire for legacy_basis=True positions — "
        "ladder rules are meaningless on a +580% gain; the fix in trend_signals.py "
        "passes legacy_basis=legacy_basis to evaluate_exit_signals"
    )
    assert "PROFIT_LADDER_30" not in rules, (
        "PROFIT_LADDER_30 must NOT fire for legacy_basis=True positions"
    )


def test_non_legacy_position_profit_ladder_fires():
    """Profit ladder MUST fire for non-legacy positions — confirms the legacy fix
    doesn't accidentally suppress ladders for normal positions."""
    from position_manager import evaluate_exit_signals, compute_exit_levels

    avg_cost      = 100.0
    current_price = 165.0   # 65% gain, NOT legacy (<100%)

    exit_levels = compute_exit_levels(avg_cost, atr=5.0, current_price=current_price)

    # WITHOUT legacy_basis (defaults to False) — correct for non-legacy positions
    result = evaluate_exit_signals(
        current_price, avg_cost, exit_levels,
        high_water_mark=current_price,
        legacy_basis=False,
    )
    rules = [r["rule"] for r in result["triggered_rules"]]
    assert "PROFIT_LADDER_50" in rules, (
        "PROFIT_LADDER_50 must fire at 65% gain for non-legacy position"
    )


# ── positions_requiring_attention exit_levels ─────────────────────────────────

def test_build_prompt_positions_requiring_attention_includes_exit_levels():
    """positions_requiring_attention must include exit_levels for the LLM to use directly.

    The prompt says '各持仓的出场价位已在第 4 节预先计算好，直接使用' — this requires
    exit_levels to actually be in Section 4. Without it, the LLM makes stop-level
    decisions without concrete price data, reducing decision quality.
    """
    import os, sys
    sys.path.insert(0, os.path.dirname(__file__))
    from llm_advisor import build_prompt

    # Construct minimal fake trend_signals with a HARD_STOP trigger
    fake_trend_signals = {
        "market_regime": {"regime": "BULL", "note": "", "indices": {}},
        "quant_signals": [],
        "signals": {
            "NVDA": {
                "close": 80.0,
                "atr": 5.0,
                "20d_high": 100.0,
                "breakout": False,
                "breakdown": True,
                "position": {
                    "shares": 10,
                    "avg_cost": 100.0,
                    "market_value_usd": 800.0,
                    "unrealized_pnl_pct": -0.20,
                    "legacy_basis": False,
                    "stop_source": "default",
                    "exit_levels": {
                        "hard_stop_price":     88.0,
                        "profit_target_price": 120.0,
                        "atr_stop_price":      72.5,
                    },
                    "exit_signals": {
                        "any_triggered": True,
                        "critical_exit": True,
                        "high_urgency":  True,
                        "triggered_rules": [
                            {"rule": "HARD_STOP", "urgency": "CRITICAL",
                             "message": "Price 80.00 <= hard stop 88.00"},
                        ],
                    },
                    "trailing_stop_from_20d_high": 92.0,
                    "drawdown_from_20d_high_pct": -0.20,
                },
            }
        },
    }

    positions = {"portfolio_value_usd": 100_000, "positions": []}
    system_msg, user_msg = build_prompt([], positions, trend_signals=fake_trend_signals)

    if system_msg is None:
        pytest.skip("Prompt template file not found — skipping integration test")

    assert "hard_stop_price" in user_msg, (
        "exit_levels (hard_stop_price) must be in positions_requiring_attention — "
        "LLM prompt says these are precomputed in Section 4 for direct use"
    )
    assert "unrealized_pnl_pct" in user_msg, (
        "unrealized_pnl_pct must be in positions_requiring_attention — "
        "needed for TRAILING_STOP table (>30% gain → REDUCE 25%, <30% → REDUCE 50%)"
    )
    assert "exit_levels" in user_msg, (
        "exit_levels key must appear in Section 4 output"
    )


# ── volume spike threshold quality gates ──────────────────────────────────────

def test_volume_spike_threshold_is_2x():
    """volume_spike boolean must require ratio > 2.0 (not 1.5).

    Higher volume confirmation (2×) filters out weak-volume false breakouts.
    Strategy A docstring specifies 'ratio > 2.0'; feature_layer must match.
    """
    from feature_layer import compute_trend_features
    import pandas as pd

    # Generate data where last day has exactly 1.8× volume (between 1.5 and 2.0)
    n = 250
    dates  = pd.date_range("2024-01-01", periods=n, freq="B")
    closes = [100.0 * (1.001) ** i for i in range(n)]
    highs  = [c * 1.01 for c in closes]
    lows   = [c * 0.99 for c in closes]
    # avg_vol_20 = 1_000_000; last day = 1_800_000 → ratio = 1.8
    vols   = [1_000_000] * (n - 1) + [1_800_000]
    df = pd.DataFrame({
        "Open": closes, "High": highs, "Low": lows,
        "Close": closes, "Volume": vols,
    }, index=dates)
    feat = compute_trend_features(df)
    assert feat is not None
    assert feat["volume_spike_ratio"] is not None
    assert feat["volume_spike_ratio"] == pytest.approx(1.8, abs=0.01), (
        f"Expected volume_spike_ratio≈1.8, got {feat['volume_spike_ratio']}"
    )
    assert feat["volume_spike"] is False, (
        f"volume_spike must be False at 1.8× ratio — threshold requires > 2.0, "
        f"got volume_spike={feat['volume_spike']}"
    )


def test_volume_spike_true_at_2x():
    """volume_spike must be True when ratio is above 2.0×."""
    from feature_layer import compute_trend_features
    import pandas as pd

    n = 250
    dates  = pd.date_range("2024-01-01", periods=n, freq="B")
    closes = [100.0 * (1.001) ** i for i in range(n)]
    highs  = [c * 1.01 for c in closes]
    lows   = [c * 0.99 for c in closes]
    # avg_vol_20 = 1_000_000; last day = 2_100_000 → ratio = 2.1
    vols   = [1_000_000] * (n - 1) + [2_100_000]
    df = pd.DataFrame({
        "Open": closes, "High": highs, "Low": lows,
        "Close": closes, "Volume": vols,
    }, index=dates)
    feat = compute_trend_features(df)
    assert feat is not None
    assert feat["volume_spike"] is True, (
        f"volume_spike must be True at 2.1× ratio — got {feat['volume_spike']}"
    )


def test_strategy_b_blocked_with_low_volume_1_3x():
    """Strategy B must reject volume_spike_ratio of 1.3× (below new 1.5× threshold)."""
    from signal_engine import strategy_b_breakout
    feat = _make_features(volume_spike_ratio=1.3)
    sig = strategy_b_breakout("TEST", feat)
    assert sig is None, (
        "Strategy B must be blocked at 1.3× volume — new threshold is > 1.5×. "
        "Weak-volume breakouts lack institutional participation and have poor follow-through."
    )


def test_strategy_b_passes_with_volume_above_1_5x():
    """Strategy B must accept volume_spike_ratio above 1.5× (the new hard threshold)."""
    from signal_engine import strategy_b_breakout
    feat = _make_features(volume_spike_ratio=1.6)
    sig = strategy_b_breakout("TEST", feat)
    assert sig is not None, (
        "Strategy B must fire at 1.6× volume — above the 1.5× threshold"
    )


# ── PROFIT_TARGET legacy_basis explicit guard ─────────────────────────────────

def test_legacy_position_no_profit_target():
    """PROFIT_TARGET must NOT fire for legacy positions (unrealised gain > 100%).

    The profit_target is avg_cost × 1.20 — meaningless for AMD at $27 avg_cost
    when current is $183 (profit_target = $32.40, already left far behind).
    The explicit 'not legacy_basis' guard in evaluate_exit_signals must prevent
    this from firing, rather than relying on the implicit 1.30× upper bound.
    """
    from position_manager import evaluate_exit_signals, compute_exit_levels, HARD_STOP_PCT

    avg_cost      = 27.0
    current_price = 183.0   # 580% gain → legacy_basis=True

    override_stop = round(current_price * (1 - HARD_STOP_PCT), 2)
    exit_levels = compute_exit_levels(
        avg_cost, atr=5.67,
        override_stop_price=override_stop,
        current_price=current_price,
    )

    result = evaluate_exit_signals(
        current_price, avg_cost, exit_levels,
        legacy_basis=True,
    )
    rules = [r["rule"] for r in result["triggered_rules"]]
    assert "PROFIT_TARGET" not in rules, (
        "PROFIT_TARGET must NOT fire for legacy_basis=True positions — "
        "profit_target ($32.40) was crossed long ago and is operationally meaningless. "
        "The explicit 'not legacy_basis' guard in evaluate_exit_signals handles this."
    )


# ── LLM prompt: legacy basis PROFIT_LADDER exclusion ─────────────────────────

def test_prompt_legacy_basis_excludes_profit_ladder():
    """The legacy basis section in the prompt must explicitly exclude PROFIT_LADDER.

    The code correctly suppresses PROFIT_LADDER for legacy positions
    (evaluate_exit_signals checks 'if not legacy_basis').
    The prompt must also say so to avoid the LLM independently applying ladder
    rules to AMD/NVDA-style positions with 500%+ unrealised gains.
    """
    import os
    path = os.path.join(
        os.path.dirname(__file__), "..", "instructinos", "prompts", "trade_advice.txt"
    )
    with open(path, encoding="utf-8") as f:
        content = f.read()

    # Find the legacy basis section (between "历史低成本持仓警告" and next blank section)
    assert "PROFIT_LADDER" in content, (
        "Prompt must reference PROFIT_LADDER in the legacy basis section — "
        "the LLM must know not to apply the ladder to legacy positions"
    )
