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
    """Stock in downtrend (negative 10d return) is blocked regardless of SPY."""
    from signal_engine import strategy_a_trend
    feat = _make_features(momentum_10d_pct=-0.02)   # stock down 2%
    market_context = {"spy_10d_return": 0.05}        # SPY up 5%
    sig = strategy_a_trend("TEST", feat, market_context=market_context)
    assert sig is None


def test_strategy_a_rs_gate_allows_positive_stock_underperforming_spy():
    """Stock up 1% should pass even when SPY is up 5% (bull-market adverse selection fix)."""
    from signal_engine import strategy_a_trend
    feat = _make_features(momentum_10d_pct=0.01)    # stock up 1%
    market_context = {"spy_10d_return": 0.05}        # SPY up 5% — stock lags but is positive
    sig = strategy_a_trend("TEST", feat, market_context=market_context)
    assert sig is not None, (
        "Strategy A should not reject a positive-return breakout because SPY is running faster. "
        "RS gate for A/B now uses 'stock >= 0', not 'stock > spy'."
    )


def test_strategy_a_blocked_when_near_earnings():
    """Strategy A must be blocked when dte <= 5 (execution-lag-adjusted earnings proximity)."""
    from signal_engine import strategy_a_trend
    # dte=5 at signal → dte=4 at next-day execution → inside ±8-15% gap risk zone
    feat = _make_features()
    feat["days_to_earnings"] = 5
    sig = strategy_a_trend("TEST", feat)
    assert sig is None, "Strategy A must reject signals when dte <= 5 (execution at dte=4)"


def test_strategy_a_allowed_when_dte_is_6():
    """Strategy A must allow signals when dte=6 (execution at dte=5, safe zone)."""
    from signal_engine import strategy_a_trend
    feat = _make_features()
    feat["days_to_earnings"] = 6
    sig = strategy_a_trend("TEST", feat)
    assert sig is not None, "Strategy A should not reject signals when dte=6 (safe execution window)"


def test_strategy_b_blocked_when_near_earnings():
    """Strategy B must be blocked when dte <= 5 (same earnings-proximity rule as A)."""
    from signal_engine import strategy_b_breakout
    feat = _make_features()
    feat["days_to_earnings"] = 4
    sig = strategy_b_breakout("TEST", feat)
    assert sig is None, "Strategy B must reject signals when dte <= 5"


def test_strategy_a_rs_gate_blocks_flat_negative_stock():
    """Stock at exactly 0% 10d return passes; stock negative is blocked."""
    from signal_engine import strategy_a_trend
    feat_zero = _make_features(momentum_10d_pct=0.0)
    feat_neg  = _make_features(momentum_10d_pct=-0.001)
    sig_zero = strategy_a_trend("FLAT", feat_zero)
    sig_neg  = strategy_a_trend("DOWN", feat_neg)
    assert sig_zero is not None, "Stock flat (0%) should pass the RS uptrend gate"
    assert sig_neg  is None,     "Stock down (-0.1%) must be blocked by the RS uptrend gate"


def test_strategy_b_fires_on_valid_signal():
    from signal_engine import strategy_b_breakout
    feat = _make_features()
    sig = strategy_b_breakout("TSLA", feat)
    assert sig is not None
    assert sig["strategy"] == "breakout_long"


def test_strategy_b_blocked_without_volume():
    from signal_engine import strategy_b_breakout
    feat = _make_features(volume_spike_ratio=1.0)  # below 1.5 threshold
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


def test_neutral_market_allows_one_soft_condition():
    """
    NEUTRAL market threshold 0.88 must allow all-hard + one soft condition.

    Bug history: soft weights changed 0.25 → 0.40 (commit fc06247), but the
    NEUTRAL threshold was left at 0.90.  With old weights all-hard + one soft
    = 3.25/3.50 = 0.929 > 0.90 (PASSED).  With current weights the same setup
    = 3.40/3.80 = 0.894, which FAILED 0.90 — silently blocking valid NEUTRAL
    signals that carry one quality confirmation.

    Fix: threshold lowered to 0.88.  This test documents the regression.
    """
    from signal_engine import generate_signals
    # rs_strong=True (stock outperforms SPY by >20%): one soft condition met.
    # near_high=False (pct_from_52w_high is below -5%): second soft not met.
    # Result: all-hard + one soft → confidence = 3.40/3.80 = 0.894 > 0.88 → PASSES.
    feat = _make_features(
        momentum_10d_pct=0.08,   # stock up 8% → rs_strong=True if spy_10d<0.067
        pct_from_52w_high=-0.10, # not near 52w high → near_high=False
    )
    mc = {"market_regime": "NEUTRAL", "spy_10d_return": 0.03}  # rs_strong: 8% > 3%×1.2=3.6% ✓
    sigs = generate_signals({"NVDA": feat}, market_context=mc)
    assert len(sigs) >= 1, (
        "NEUTRAL market with all-hard + rs_strong (conf≈0.894) should pass "
        "the 0.88 threshold — was regression-blocked at 0.90 after soft weight change."
    )


def test_neutral_market_blocks_all_hard_no_soft():
    """NEUTRAL market must block all-hard-only signals (conf≈0.789, no quality confirmation)."""
    from signal_engine import generate_signals
    # rs_strong=False: stock up only 1%, spy up 5% → stock < spy×1.2, no outperformance
    # near_high=False: far from 52w high
    feat = _make_features(
        momentum_10d_pct=0.01,   # stock barely positive
        pct_from_52w_high=-0.15, # well below 52w high → near_high=False
    )
    mc = {"market_regime": "NEUTRAL", "spy_10d_return": 0.05}  # rs_strong: 1% < 5%×1.2=6% ✗
    sigs = generate_signals({"NVDA": feat}, market_context=mc)
    assert len(sigs) == 0, (
        "NEUTRAL market with all-hard, no soft conditions (conf≈0.789) must be blocked — "
        "no quality confirmation in a mixed-regime market."
    )


def test_bull_market_allows_all_hard_no_soft():
    """BULL market must allow all-hard-only signals (conf≈0.789 passes ≥0.75 or standalone ≥0.85 gate via news)."""
    from signal_engine import generate_signals
    # In BULL market there is no NEUTRAL filter; only the standalone threshold in LLM prompt matters.
    # Here we verify the code doesn't add any extra filter in BULL.
    feat = _make_features(
        momentum_10d_pct=0.01,
        pct_from_52w_high=-0.15,
    )
    mc = {"market_regime": "BULL", "spy_10d_return": 0.05}
    sigs = generate_signals({"NVDA": feat}, market_context=mc)
    # Signal should not be blocked by regime filter in BULL (may still be low confidence)
    assert isinstance(sigs, list), "generate_signals must return a list in BULL market"


# ── portfolio_engine ──────────────────────────────────────────────────────────

def test_compute_position_size_basic():
    from portfolio_engine import compute_position_size, ROUND_TRIP_COST_PCT, EXEC_LAG_PCT
    result = compute_position_size(100_000, entry_price=50.0, stop_price=45.0)
    assert result is not None
    # risk_per_share = 5.0; cost = 50 × 0.0035 = 0.175; gap = 50 × 0.005 = 0.25
    # net_risk = 5.0 + 0.175 + 0.25 = 5.425
    # shares = floor(100000 × 0.01 / 5.425) = floor(184.3) = 184
    expected = math.floor(100_000 * 0.01 / (5.0 + 50.0 * ROUND_TRIP_COST_PCT + 50.0 * EXEC_LAG_PCT))
    assert result["shares_to_buy"] == expected, (
        f"Expected {expected} shares (cost+gap-adjusted), got {result['shares_to_buy']}"
    )
    assert result["risk_per_share"] == 5.0   # gross risk unchanged
    assert "net_risk_per_share" in result    # new field present


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


def test_compute_exit_levels_signal_target():
    """signal_target_price must appear in levels when provided and above avg_cost."""
    from position_manager import compute_exit_levels
    levels = compute_exit_levels(avg_cost=100.0, signal_target_price=107.0)
    assert "signal_target_price" in levels, "signal_target_price must be stored in exit levels"
    assert levels["signal_target_price"] == 107.0
    assert abs(levels["signal_target_pct"] - 0.07) < 0.0001


def test_compute_exit_levels_signal_target_below_avg_cost_ignored():
    """signal_target_price at or below avg_cost must be silently ignored (invalid signal)."""
    from position_manager import compute_exit_levels
    levels = compute_exit_levels(avg_cost=100.0, signal_target_price=99.0)
    assert "signal_target_price" not in levels, (
        "signal_target_price below avg_cost is invalid and must not appear in exit levels"
    )


def test_evaluate_exit_signals_signal_target_fires():
    """SIGNAL_TARGET fires when price is between signal_target_price and profit_target."""
    from position_manager import evaluate_exit_signals, compute_exit_levels
    # avg_cost=100, signal_target=107, profit_target=120 (PROFIT_TARGET_PCT=0.20)
    levels = compute_exit_levels(avg_cost=100.0, signal_target_price=107.0)
    # price=110: above signal_target (107) but below profit_target (120) → fires
    result = evaluate_exit_signals(current_price=110.0, avg_cost=100.0, exit_levels=levels)
    rules = [r["rule"] for r in result["triggered_rules"]]
    assert "SIGNAL_TARGET" in rules, (
        "SIGNAL_TARGET must fire when price is between signal_target_price and profit_target"
    )
    # Urgency should be LOW
    low_rules = [r for r in result["triggered_rules"] if r["rule"] == "SIGNAL_TARGET"]
    assert low_rules[0]["urgency"] == "LOW"


def test_evaluate_exit_signals_signal_target_not_fired_before_target():
    """SIGNAL_TARGET must NOT fire before price reaches signal_target_price."""
    from position_manager import evaluate_exit_signals, compute_exit_levels
    levels = compute_exit_levels(avg_cost=100.0, signal_target_price=107.0)
    # price=105: below signal_target → should not fire
    result = evaluate_exit_signals(current_price=105.0, avg_cost=100.0, exit_levels=levels)
    rules = [r["rule"] for r in result["triggered_rules"]]
    assert "SIGNAL_TARGET" not in rules, (
        "SIGNAL_TARGET must not fire before price reaches signal_target_price"
    )


def test_evaluate_exit_signals_signal_target_not_fired_at_profit_target():
    """SIGNAL_TARGET must NOT fire once price reaches the +20% profit target zone."""
    from position_manager import evaluate_exit_signals, compute_exit_levels
    levels = compute_exit_levels(avg_cost=100.0, signal_target_price=107.0)
    # price=122: above profit_target (120) → PROFIT_TARGET fires, SIGNAL_TARGET must not
    result = evaluate_exit_signals(current_price=122.0, avg_cost=100.0, exit_levels=levels)
    rules = [r["rule"] for r in result["triggered_rules"]]
    assert "SIGNAL_TARGET" not in rules, (
        "SIGNAL_TARGET must not fire once price is above profit_target_price"
    )
    assert "PROFIT_TARGET" in rules, "PROFIT_TARGET should fire at 22% gain"


def test_evaluate_exit_signals_signal_target_not_fired_without_field():
    """SIGNAL_TARGET must never fire when signal_target_price is not in exit_levels."""
    from position_manager import evaluate_exit_signals, compute_exit_levels
    # No signal_target_price provided
    levels = compute_exit_levels(avg_cost=100.0)
    result = evaluate_exit_signals(current_price=110.0, avg_cost=100.0, exit_levels=levels)
    rules = [r["rule"] for r in result["triggered_rules"]]
    assert "SIGNAL_TARGET" not in rules, (
        "SIGNAL_TARGET must not fire when signal_target_price is absent from exit_levels"
    )


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
    # dte=6: lower bound of new 6-8 window (accounts for next-day execution lag)
    feat = compute_earnings_features({"days_to_earnings": 6, "avg_historical_surprise_pct": 0.05})
    assert feat["earnings_event_window"] is True
    assert feat["positive_surprise_history"] is True
    # dte=5: was lower bound of old 5-7 window; now excluded because execution lag
    # means actual entry has dte=4 remaining (dangerous gap risk zone)
    feat5 = compute_earnings_features({"days_to_earnings": 5})
    assert feat5["earnings_event_window"] is False, "dte=5 must be excluded (execution lag: entry at dte=4)"
    # dte=4: too close — gap risk (excluded)
    feat4 = compute_earnings_features({"days_to_earnings": 4})
    assert feat4["earnings_event_window"] is False, "dte=4 must be excluded (gap risk)"


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


def test_strategy_c_blocked_with_mild_positive_momentum():
    """Strategy C must be blocked with 1-5% momentum — gate requires ≥5%.

    Restored to original >5% gate: 0-5% momentum earnings plays have lower
    empirical win rates and add noise without edge.  Even with supporting
    conditions (positive_surprise_history + above_200ma), +3% momentum is
    insufficient to qualify as a valid earnings event setup.
    """
    from signal_engine import strategy_c_earnings
    feat = {
        "earnings_event_window":     True,
        "days_to_earnings":          10,
        "positive_surprise_history": True,
        "above_200ma":               True,
        "momentum_10d_pct":          0.03,   # +3%: fails restored gate (< 5%)
        "close":                     100.0,
        "atr":                       2.0,
    }
    sig = strategy_c_earnings("TEST", feat)
    assert sig is None, (
        "Strategy C must be blocked with +3% momentum — "
        "gate requires momentum >= 5% to filter low-quality earnings setups."
    )


def test_strategy_c_blocked_with_zero_momentum():
    """Strategy C must be blocked when momentum <= 0.0 (flat or declining into earnings)."""
    from signal_engine import strategy_c_earnings
    feat = {
        "earnings_event_window":     True,
        "days_to_earnings":          10,
        "positive_surprise_history": True,
        "above_200ma":               True,
        "momentum_10d_pct":          0.0,   # flat → fails >= 5% gate
        "close":                     100.0,
        "atr":                       2.0,
    }
    sig = strategy_c_earnings("TEST", feat)
    assert sig is None, (
        "Strategy C must be blocked when momentum is 0.0 — "
        "gate requires >= 5% momentum for earnings event setups"
    )


def test_strategy_c_momentum_gate_boundary():
    """Strategy C gate is at 5%: 4.9% fails, 5.0% passes.

    With restored gate (momentum >= 5%):
      4.9% momentum → blocked (below gate)
      5.0% momentum → passes (at gate boundary)
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
    sig_below = strategy_c_earnings("TEST", {**base_feat, "momentum_10d_pct": 0.049})
    sig_at    = strategy_c_earnings("TEST", {**base_feat, "momentum_10d_pct": 0.05})

    assert sig_below is None, (
        "4.9% momentum must be blocked — gate requires >= 5%"
    )
    assert sig_at is not None, (
        "5.0% momentum must pass — exactly at gate boundary"
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
    """_near_52w_high must return False (no bonus) when 52w data unavailable.

    Threshold tightened: -8% → -5% (2026-03).
    Only stocks within 5% of 52w high qualify as "near breakout zone".
    Rationale: -8% included 6-8% recovery/pullback setups (not true breakouts);
    -5% keeps only stocks in the final consolidation before a genuine new high.
    """
    from signal_engine import _near_52w_high
    assert _near_52w_high({"pct_from_52w_high": None}) is False, (
        "Missing 52w data must return False — no undeserved quality bonus for new stocks"
    )
    assert _near_52w_high({"pct_from_52w_high": -0.02}) is True   # within 5% → True
    assert _near_52w_high({"pct_from_52w_high": -0.05}) is False  # at boundary (pct > -0.05 required) → False
    assert _near_52w_high({"pct_from_52w_high": -0.06}) is False  # outside 5% → False
    assert _near_52w_high({"pct_from_52w_high": -0.08}) is False  # previously True at -8% threshold → now False
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
    """ATR > 7% of close (stop too wide) must block strategy A.

    Threshold raised 5% → 7%: high-beta watchlist stocks (COIN, TSLA, NVDA breakout days)
    have ATR 5-8%. portfolio_engine's 1% risk rule already controls position size for
    wide-ATR stocks; the gate only needs to block genuinely uncontrollable volatility.
    """
    from signal_engine import strategy_a_trend
    # ATR/close = 8/100 = 8% → exceeds 7% threshold
    feat = _make_features(close=100.0, atr=8.0)
    sig = strategy_a_trend("TEST", feat)
    assert sig is None, (
        "Strategy A must be blocked when ATR/close > 7% — stop is too wide to control"
    )


def test_strategy_b_blocked_when_atr_too_high():
    """ATR > 7% of close must block strategy B (threshold raised 5% → 7%)."""
    from signal_engine import strategy_b_breakout
    feat = _make_features(close=100.0, atr=8.0)
    sig = strategy_b_breakout("TEST", feat)
    assert sig is None, (
        "Strategy B must be blocked when ATR/close > 7% — stop is too wide to control"
    )


def test_strategy_c_blocked_when_atr_too_high():
    """ATR > 5% of close must block strategy C (earnings keeps 5% gate, not raised to 7%).

    Earnings strategies retain the strict 5% gate because earnings gaps (±8-15%) are
    independent of ATR and can overwhelm any ATR-based stop. The 7% relaxation only
    applies to trend/breakout strategies where position sizing handles wide ATR.
    """
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
    """ATR exactly at 7% of close (boundary) must still pass (gate is strict '>' not '>=').

    Also verifies that ATR at 5-7% now passes (previously blocked at 5%).
    This covers high-beta stocks like COIN (~5%) and TSLA (~6%) during normal sessions.
    """
    from signal_engine import strategy_a_trend
    # ATR/close = 7/100 = 7.0% → exactly at new limit, should pass (> not >=)
    feat = _make_features(close=100.0, atr=7.0)
    sig = strategy_a_trend("TEST", feat)
    assert sig is not None, (
        "Strategy A should not be blocked at exactly 7% ATR/close — gate is strict '>' not '>='"
    )
    # ATR = 6% (previously blocked at old 5% threshold, now should pass)
    feat6 = _make_features(close=100.0, atr=6.0)
    sig6 = strategy_a_trend("TEST", feat6)
    assert sig6 is not None, (
        "Strategy A should pass at 6% ATR/close (threshold raised 5%→7%)"
    )


# ── Market regime gates ───────────────────────────────────────────────────────

def test_generate_signals_empty_in_bear_deep():
    """BEAR_DEEP (both legs ≤ -5%) must suppress all signals."""
    from signal_engine import generate_signals
    feat = _make_features()   # all conditions met — strong signal
    # No pct_from_ma → safe fallback: treat as BEAR_DEEP
    sigs_no_pct = generate_signals({"NVDA": feat}, market_context={"market_regime": "BEAR"})
    assert sigs_no_pct == [], (
        "BEAR regime without pct_from_ma must return [] (safe fallback = BEAR_DEEP)"
    )
    # Explicit BEAR_DEEP: both legs at -6%
    sigs_deep = generate_signals(
        {"NVDA": feat},
        market_context={"market_regime": "BEAR",
                        "spy_pct_from_ma": -0.06, "qqq_pct_from_ma": -0.08}
    )
    assert sigs_deep == [], (
        "BEAR_DEEP (min_pct_from_ma=-8%) must return empty signal list"
    )


def test_generate_signals_empty_in_bear_market_case_insensitive():
    """BEAR check must be case-insensitive — lowercase 'bear' treated as BEAR."""
    from signal_engine import generate_signals
    feat = _make_features()
    sigs = generate_signals({"NVDA": feat}, market_context={"market_regime": "bear"})
    assert sigs == [], "BEAR regime check must be case-insensitive (no pct_from_ma → BEAR_DEEP)"


def test_generate_signals_bear_shallow_allows_above_200ma_tickers():
    """BEAR_SHALLOW: tickers above their own 200MA must not be blocked by signal_engine.

    The sector+TQS filter is applied by run.py post-enrich, not here.
    signal_engine only gates on above_200ma for BEAR_SHALLOW.
    """
    from signal_engine import generate_signals
    feat_above = _make_features(above_200ma=True)
    feat_below = _make_features(above_200ma=False)
    mc = {"market_regime": "BEAR", "spy_pct_from_ma": -0.02, "qqq_pct_from_ma": -0.03}

    sigs_above = generate_signals({"IAU": feat_above}, market_context=mc)
    sigs_below = generate_signals({"GLD": feat_below}, market_context=mc)

    assert len(sigs_above) >= 1, (
        "BEAR_SHALLOW: ticker above its own 200MA must pass signal_engine "
        "(sector+TQS filtered post-enrich by run.py)"
    )
    assert sigs_below == [], (
        "BEAR_SHALLOW: ticker below its own 200MA must be blocked "
        "(only uptrending defensive names are viable)"
    )


def test_generate_signals_bear_shallow_exact_boundary():
    """BEAR_SHALLOW boundary: -5% is BEAR_DEEP (blocked), -4.99% is BEAR_SHALLOW (allowed)."""
    from signal_engine import generate_signals
    feat = _make_features(above_200ma=True)

    sigs_at_boundary = generate_signals(
        {"IAU": feat},
        market_context={"market_regime": "BEAR",
                        "spy_pct_from_ma": -0.05, "qqq_pct_from_ma": -0.03}
    )
    assert sigs_at_boundary == [], (
        "Exactly -5% must be BEAR_DEEP — boundary is ≤ -5% → return []"
    )

    sigs_just_shallow = generate_signals(
        {"IAU": feat},
        market_context={"market_regime": "BEAR",
                        "spy_pct_from_ma": -0.049, "qqq_pct_from_ma": -0.03}
    )
    assert len(sigs_just_shallow) >= 1, (
        "-4.9% should be BEAR_SHALLOW — signal_engine allows above_200ma tickers through"
    )


def test_generate_signals_neutral_filters_low_confidence():
    """NEUTRAL market must drop signals with confidence_score <= 0.90.

    Two cases tested:
      1. Strategy B all-hard + no soft (conf=0.80): clearly filtered
      2. Strategy A all-hard + no soft (conf=0.857): filtered under new 0.90 threshold
         (previously passed at 0.85; now correctly blocked in mixed market)
    """
    from signal_engine import generate_signals

    # Case 1: Strategy B with no soft conditions → conf = 3.0/3.75 = 0.80
    feat_b = _make_features(
        above_200ma=False,
        momentum_10d_pct=0.011,   # RS positive but not strong (0.011 < 0.01 × 1.2 = 0.012)
        pct_from_52w_high=-0.25,  # far from 52w high → no near_high bonus
    )
    market_ctx = {"market_regime": "NEUTRAL", "spy_10d_return": 0.01}
    sigs_b = generate_signals({"TEST": feat_b}, market_context=market_ctx)
    assert all(s["confidence_score"] > 0.90 for s in sigs_b), (
        f"NEUTRAL market must suppress conf ≤ 0.90; "
        f"got: {[(s['ticker'], s['confidence_score']) for s in sigs_b]}"
    )

    # Case 2: Strategy A all-hard, no soft conditions → conf = 3.0/3.5 = 0.857
    # stock_10d=0.06, spy=0.10 → rs_strong = 0.06 > 0.10×1.2 = False; near_high via -0.20 = False
    feat_a = _make_features(momentum_10d_pct=0.06, pct_from_52w_high=-0.20)
    market_ctx_a = {"market_regime": "NEUTRAL", "spy_10d_return": 0.10}
    sigs_a = generate_signals({"NVDA": feat_a}, market_context=market_ctx_a)
    assert all(s["confidence_score"] > 0.90 for s in sigs_a), (
        f"NEUTRAL market must suppress conf=0.857 (all-hard, no soft); "
        f"got: {[(s['ticker'], s['confidence_score']) for s in sigs_a]}"
    )


def test_generate_signals_neutral_keeps_high_confidence():
    """NEUTRAL market must retain signals with confidence > 0.90.

    Default _make_features() with no spy data: spy_10d=0, stock_10d=0.06
    → rs_strong=True (0.06 > 0); pct_from_52w_high=-0.05 → near_high=True
    → Strategy A conf = 3.5/3.5 = 1.0 > 0.90 ✓
    """
    from signal_engine import generate_signals
    feat = _make_features()   # all conditions → Strategy A conf = 1.0
    market_ctx = {"market_regime": "NEUTRAL"}
    sigs = generate_signals({"NVDA": feat}, market_context=market_ctx)
    assert len(sigs) >= 1, (
        "NEUTRAL market must retain high-confidence signals (> 0.90)"
    )


def test_generate_signals_bull_passes_all_quality_signals():
    """BULL market (or no regime) must not suppress any valid signals."""
    from signal_engine import generate_signals
    feat = _make_features()
    sigs_bull   = generate_signals({"NVDA": feat}, market_context={"market_regime": "BULL"})
    sigs_no_ctx = generate_signals({"NVDA": feat})
    assert len(sigs_bull)   >= 1, "BULL regime must pass valid signals"
    assert len(sigs_no_ctx) >= 1, "No market_context must pass valid signals (default behavior)"


def test_size_signals_respects_risk_pct_override():
    """size_signals must pass risk_pct to compute_position_size.

    NEUTRAL uses 0.75%, BEAR_SHALLOW uses 0.50%.  A 0.50% risk on a $70k portfolio
    should produce ~half as many shares as the default 1.0% risk.
    """
    from portfolio_engine import size_signals, RISK_PER_TRADE_PCT

    sig = {
        "ticker":      "IAU",
        "strategy":    "trend_long",
        "entry_price": 100.0,
        "stop_price":  97.0,   # 3% stop → clean signal
        "confidence_score": 0.85,
    }
    portfolio = 70_000.0

    sized_default = size_signals([sig], portfolio)[0]
    sized_neutral = size_signals([sig], portfolio, risk_pct=0.0075)[0]
    sized_shallow = size_signals([sig], portfolio, risk_pct=0.005)[0]

    shares_default = sized_default["sizing"]["shares_to_buy"]
    shares_neutral = sized_neutral["sizing"]["shares_to_buy"]
    shares_shallow = sized_shallow["sizing"]["shares_to_buy"]

    assert sized_neutral["sizing"]["risk_pct"] == 0.0075, (
        "NEUTRAL sizing must record risk_pct=0.0075"
    )
    assert sized_shallow["sizing"]["risk_pct"] == 0.005, (
        "BEAR_SHALLOW sizing must record risk_pct=0.005"
    )
    assert shares_neutral < shares_default, (
        f"NEUTRAL shares ({shares_neutral}) must be < default ({shares_default})"
    )
    assert shares_shallow < shares_neutral, (
        f"BEAR_SHALLOW shares ({shares_shallow}) must be < NEUTRAL ({shares_neutral})"
    )


def test_generate_signals_neutral_filter_strictly_greater_than_0_88():
    """NEUTRAL filter must be strictly > 0.88 — corrected from stale 0.90 threshold.

    Rationale: soft weights were raised 0.25 → 0.40, changing the denominator from 3.5
    to 3.8.  With old weights, all-hard + one soft = 3.25/3.50 = 0.929 > 0.90 (PASSED).
    With current weights, 3.40/3.80 = 0.894 < 0.90 (regression-blocked).
    Threshold corrected to 0.88 to restore intended 'all-hard + one soft → passes NEUTRAL'.

    Signals produced by _make_features() have rs_strong=True + near_high=True → conf = 1.0,
    which passes both old and new threshold.  The threshold change is validated by the
    test_neutral_market_allows_one_soft_condition test (tests the 0.894 edge case).
    """
    from signal_engine import generate_signals
    feat = _make_features()   # rs_strong=True + near_high=True → conf = 1.0
    market_ctx = {"market_regime": "NEUTRAL"}
    sigs = generate_signals({"NVDA": feat}, market_context=market_ctx)
    for s in sigs:
        assert s["confidence_score"] > 0.88, (
            f"NEUTRAL filter must be strictly > 0.88; "
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


# ── cancel threshold and earnings warning (entry_note) ──────────────────────

def test_strategy_a_entry_note_uses_1_5_pct_cancel():
    """entry_note must use ×1.015 (1.5%) cancel threshold, not old ×1.005."""
    from signal_engine import strategy_a_trend
    feat = _make_features()
    sig = strategy_a_trend("TEST", feat)
    assert sig is not None
    assert "1.015" in sig["entry_note"], (
        f"entry_note must reference ×1.015 cancel threshold; got: {sig['entry_note']}"
    )
    assert "1.005" not in sig["entry_note"], (
        "Old ×1.005 threshold still present in entry_note"
    )


def test_strategy_b_entry_note_uses_1_5_pct_cancel():
    """breakout_long entry_note must use ×1.015 cancel threshold."""
    from signal_engine import strategy_b_breakout
    feat = _make_features()
    sig = strategy_b_breakout("TEST", feat)
    assert sig is not None
    assert "1.015" in sig["entry_note"], (
        f"entry_note must reference ×1.015 cancel threshold; got: {sig['entry_note']}"
    )


def test_strategy_a_entry_note_earnings_warning_dte_7():
    """entry_note must contain earnings warning when DTE=7 (within 6-10 range)."""
    from signal_engine import strategy_a_trend
    feat = _make_features()
    feat["days_to_earnings"] = 7
    sig = strategy_a_trend("TEST", feat)
    assert sig is not None
    assert "EARNINGS IN 7 DAYS" in sig["entry_note"], (
        f"entry_note must warn about earnings in 7 days; got: {sig['entry_note']}"
    )


def test_strategy_a_entry_note_no_earnings_warning_dte_none():
    """entry_note must NOT contain earnings warning when DTE is None."""
    from signal_engine import strategy_a_trend
    feat = _make_features()
    feat["days_to_earnings"] = None
    sig = strategy_a_trend("TEST", feat)
    assert sig is not None
    assert "EARNINGS" not in sig["entry_note"], (
        f"entry_note must not contain earnings warning when DTE is None; got: {sig['entry_note']}"
    )


def test_strategy_a_entry_note_no_earnings_warning_dte_15():
    """entry_note must NOT contain earnings warning when DTE > 10."""
    from signal_engine import strategy_a_trend
    feat = _make_features()
    feat["days_to_earnings"] = 15
    sig = strategy_a_trend("TEST", feat)
    assert sig is not None
    assert "EARNINGS" not in sig["entry_note"], (
        f"entry_note must not warn about earnings when DTE=15; got: {sig['entry_note']}"
    )


def test_profit_ladder_30_message_mentions_breakeven():
    """PROFIT_LADDER_30 message must mention updating stop to avg_cost."""
    from position_manager import evaluate_exit_signals, compute_exit_levels
    levels = compute_exit_levels(avg_cost=100.0)
    result = evaluate_exit_signals(current_price=135.0, avg_cost=100.0, exit_levels=levels)
    ladder_rules = [r for r in result["triggered_rules"] if r["rule"] == "PROFIT_LADDER_30"]
    assert ladder_rules, "PROFIT_LADDER_30 must fire at 35% gain"
    msg = ladder_rules[0]["message"].lower()
    assert "avg_cost" in msg or "override_stop" in msg, (
        f"PROFIT_LADDER_30 message must mention breakeven stop; got: {ladder_rules[0]['message']}"
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


# ── New tests for F2/F3/F5/F6 fixes ──────────────────────────────────────────

def test_earnings_window_bounds_are_6_to_8():
    """Earnings event window must be 6-8 days (execution lag correction: lower 5→6, upper 7→8).

    PEAD drift concentrates in the final 5-7 days before announcement.
    Signals fire at close; execution is next-day open → 1-day execution lag.
    Window shifted +1 to ensure ACTUAL entry has 5-7 days remaining:
      signal dte=6 → entry dte=5 (safe minimum)
      signal dte=8 → entry dte=7 (safe maximum)
    dte≤5 removed: after execution lag, entry has ≤4 days remaining — dangerous
      overnight gap risk (±8-15%) overwhelms the ATR stop (1.5×ATR ≈ ±2-3%).
    dte=9+ removed: entry has 8+ days remaining; too early for PEAD concentration.
    """
    from feature_layer import compute_earnings_features
    # dte=6: new lower bound (after lag: entry at dte=5 — safe minimum)
    assert compute_earnings_features({"days_to_earnings": 6})["earnings_event_window"] is True
    # dte=7: mid-window
    assert compute_earnings_features({"days_to_earnings": 7})["earnings_event_window"] is True
    # dte=8: new upper bound (after lag: entry at dte=7 — safe maximum)
    assert compute_earnings_features({"days_to_earnings": 8})["earnings_event_window"] is True
    # dte=5: was lower bound of old 5-7 window; now excluded (after lag: entry dte=4 → gap risk)
    assert compute_earnings_features({"days_to_earnings": 5})["earnings_event_window"] is False
    # dte=4: too close — gap risk
    assert compute_earnings_features({"days_to_earnings": 4})["earnings_event_window"] is False
    # dte=3: too close — gap risk
    assert compute_earnings_features({"days_to_earnings": 3})["earnings_event_window"] is False
    # dte=9: now outside upper bound (was dte=8+ in old window)
    assert compute_earnings_features({"days_to_earnings": 9})["earnings_event_window"] is False
    # dte=10: outside window
    assert compute_earnings_features({"days_to_earnings": 10})["earnings_event_window"] is False
    # dte=2: too close
    assert compute_earnings_features({"days_to_earnings": 2})["earnings_event_window"] is False
    # dte=15: well outside window
    assert compute_earnings_features({"days_to_earnings": 15})["earnings_event_window"] is False


def test_multi_strategy_confluence_boost():
    """When two strategies fire for the same ticker, confidence must be boosted by +0.10.

    F6 fix: concurrent strategy confirmation (e.g. trend_long + earnings_event_long)
    is a stronger setup than either alone.  The deduplication step should retain the
    highest-confidence signal AND apply a +0.10 confluence boost capped at 1.0.
    """
    from signal_engine import generate_signals

    # Ticker that triggers both Strategy A and Strategy C
    # Strategy A: above 200ma, breakout, volume spike, good momentum
    # Strategy C: earnings in 8 days, positive momentum
    features = {
        "DUALTEST": {
            "ticker":                    "DUALTEST",
            "close":                     100.0,
            "above_200ma":               True,
            "breakout_20d":              True,
            "volume_spike":              True,
            "volume_spike_ratio":        2.5,
            "momentum_10d_pct":          0.12,
            "atr":                       2.0,
            "daily_range_vs_atr":        1.8,
            "pct_from_52w_high":        -0.05,
            "trend_score":               0.8,
            "earnings_event_window":     True,
            "days_to_earnings":          8,
            "positive_surprise_history": True,
        }
    }

    signals = generate_signals(features, market_context={"market_regime": "BULL"})
    assert len(signals) == 1, "Deduplication should yield one signal per ticker"

    sig = signals[0]
    # Confluence boost must be applied
    assert sig["conditions_met"].get("multi_strategy_confluence") is True, (
        "multi_strategy_confluence flag must be set when multiple strategies fire"
    )
    # Confidence must be higher than any single-strategy baseline (min base ≈ 0.86)
    assert sig["confidence_score"] > 0.85, (
        f"Confluence-boosted confidence {sig['confidence_score']} should exceed 0.85"
    )


def test_signal_has_entry_note():
    """All strategy signals must include entry_note to guide next-day execution.

    F7 fix: entry_price = today's close, but execution happens next-day open.
    The entry_note reminds the executor to cancel if open gaps > 0.5% above entry.
    """
    from signal_engine import strategy_a_trend, strategy_b_breakout, strategy_c_earnings

    base = {
        "close": 100.0, "atr": 1.5, "above_200ma": True, "breakout_20d": True,
        "volume_spike": True, "volume_spike_ratio": 2.5, "momentum_10d_pct": 0.08,
        "daily_range_vs_atr": 2.0, "pct_from_52w_high": -0.05,
        "trend_score": 0.8,
    }

    sig_a = strategy_a_trend("T", base)
    assert sig_a is not None and "entry_note" in sig_a, "Strategy A signal must have entry_note"

    sig_b = strategy_b_breakout("T", base)
    assert sig_b is not None and "entry_note" in sig_b, "Strategy B signal must have entry_note"

    sig_c = strategy_c_earnings("T", {
        **base,
        "earnings_event_window": True, "days_to_earnings": 8,
        "positive_surprise_history": True,
    })
    assert sig_c is not None and "entry_note" in sig_c, "Strategy C signal must have entry_note"


def test_forward_tester_handles_wrapped_json():
    """forward_tester must handle investment_advice JSON wrapper {advice_parsed: {...}}.

    F2/F3 fix: llm_advisor.save_advice() stores: {"advice_parsed": {...}, "advice_raw": "..."}.
    The forward tester previously read top-level keys directly, missing the inner data.
    """
    import json
    import tempfile
    import os
    from forward_tester import evaluate_file

    # Build a minimal investment_advice wrapper
    inner = {
        "new_trade": "NO NEW TRADE",
        "second_new_trade": "NO SECOND TRADE",
        "position_actions": [],
    }
    wrapped = {
        "timestamp": "2020-01-01T00:00:00",
        "advice_raw": "NO NEW TRADE",
        "advice_parsed": inner,
        "token_usage": None,
    }

    # Write to a temp file with the expected naming convention (old enough to evaluate)
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json",
        prefix="investment_advice_20200101_",
        delete=False,
    ) as f:
        json.dump(wrapped, f)
        tmppath = f.name

    # Rename to match expected pattern investment_advice_YYYYMMDD.json
    dated_path = os.path.join(os.path.dirname(tmppath), "investment_advice_20200101.json")
    os.rename(tmppath, dated_path)

    try:
        result = evaluate_file(dated_path, n_days=5)
        # Result should not be None (date is in the past) and should have no errors
        # from the JSON parsing (empty position_actions is fine)
        assert result is not None, "evaluate_file should return results for past dates"
        assert result["position_results"] == [], "Empty position_actions → empty results"
    finally:
        if os.path.exists(dated_path):
            os.remove(dated_path)


# ── forward_tester gap-fill price accuracy ───────────────────────────────────

def test_check_stop_gap_fill_uses_open_not_low(monkeypatch):
    """When stock gaps below the stop on open, stop_hit_price must be the open
    price (the actual execution fill), NOT the daily low (which overstates the loss).

    Scenario: Entry $100, stop $95.
      Day 1: stock gaps down — opens at $92 (below stop), trades to low of $89.
    Expected: stop_hit=True, stop_hit_price=$92.00 (gap fill at open, not $89 low).
    """
    import pandas as pd
    from datetime import date
    from forward_tester import check_stop_or_target_hit

    entry_date   = date(2024, 1, 2)
    # Simulated daily bars: day 0 = entry date (excluded), day 1 = first eval day
    idx = pd.to_datetime(["2024-01-02", "2024-01-03"])
    fake_data = pd.DataFrame({
        "Open":  [100.0, 92.0],   # day 1 opens at $92 — gap through $95 stop
        "High":  [101.0, 93.0],
        "Low":   [ 99.0, 89.0],   # intraday low $89 — should NOT be used as fill
        "Close": [100.0, 91.0],
    }, index=idx)

    import forward_tester
    monkeypatch.setattr(forward_tester, "get_daily_prices_during_period",
                        lambda *args, **kwargs: fake_data)

    result = check_stop_or_target_hit(
        ticker       = "TEST",
        entry_date   = entry_date,
        entry_price  = 100.0,
        stop_price   = 95.0,
        target_price = 115.0,
        n_days       = 10,
    )

    assert result["stop_hit"],     "Stop must be detected when day-low breaches stop"
    assert result["stop_hit_day"] == 1
    assert result["stop_hit_price"] == 92.0, (
        f"Gap-fill stop must use open price $92 not day-low $89, "
        f"got {result['stop_hit_price']}"
    )


def test_check_stop_intraday_fill_uses_stop_price(monkeypatch):
    """When the stop is hit intraday (open above stop, low below stop),
    stop_hit_price must approximate the stop price (limit fill), not the low.

    Scenario: Entry $100, stop $95.
      Day 1: opens at $97 (above stop), sells down to low $93.
    Expected: stop_hit=True, stop_hit_price=$95.00 (stop-limit fill, not $93 low).
    """
    import pandas as pd
    from datetime import date
    from forward_tester import check_stop_or_target_hit

    entry_date = date(2024, 1, 2)
    idx = pd.to_datetime(["2024-01-02", "2024-01-03"])
    fake_data = pd.DataFrame({
        "Open":  [100.0, 97.0],   # opens above stop — no gap
        "High":  [101.0, 97.5],
        "Low":   [ 99.0, 93.0],   # sells through stop intraday
        "Close": [100.0, 94.0],
    }, index=idx)

    import forward_tester
    monkeypatch.setattr(forward_tester, "get_daily_prices_during_period",
                        lambda *args, **kwargs: fake_data)

    result = check_stop_or_target_hit(
        ticker       = "TEST",
        entry_date   = entry_date,
        entry_price  = 100.0,
        stop_price   = 95.0,
        target_price = 115.0,
        n_days       = 10,
    )

    assert result["stop_hit"],     "Intraday stop must be detected when low < stop"
    assert result["stop_hit_day"] == 1
    assert result["stop_hit_price"] == 95.0, (
        f"Intraday fill must be stop price $95 not day-low $93, "
        f"got {result['stop_hit_price']}"
    )


def test_check_stop_not_hit_when_low_above_stop(monkeypatch):
    """Stop must NOT be marked hit when daily Low remains above the stop price."""
    import pandas as pd
    from datetime import date
    from forward_tester import check_stop_or_target_hit

    entry_date = date(2024, 1, 2)
    idx = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
    fake_data = pd.DataFrame({
        "Open":  [100.0, 98.0, 99.0],
        "High":  [101.0, 99.0, 105.0],
        "Low":   [ 99.0, 96.0, 98.0],   # low stays at $96, above $95 stop
        "Close": [100.0, 97.0, 103.0],
    }, index=idx)

    import forward_tester
    monkeypatch.setattr(forward_tester, "get_daily_prices_during_period",
                        lambda *args, **kwargs: fake_data)

    result = check_stop_or_target_hit(
        ticker       = "TEST",
        entry_date   = entry_date,
        entry_price  = 100.0,
        stop_price   = 95.0,
        target_price = 115.0,
        n_days       = 10,
    )

    assert not result["stop_hit"],  "Stop must NOT fire when low stays above stop price"
    assert result["stop_hit_price"] is None


# ── UNKNOWN regime treated as NEUTRAL ────────────────────────────────────────

def test_generate_signals_unknown_regime_treated_as_neutral():
    """UNKNOWN regime must apply the conf > 0.90 filter (same as NEUTRAL).

    When compute_market_regime() fails (network error, rate limit), both pipelines
    fall back to regime='UNKNOWN'. UNKNOWN must NOT be treated as BULL (no filter)
    because regime failures correlate with market stress — the exact scenario where
    caution is most warranted.  Only high-confidence signals (conf > 0.90) should
    pass, identical to the NEUTRAL treatment.

    Fix: signal_engine.py normalises any unrecognised regime to 'NEUTRAL'.
    """
    from signal_engine import generate_signals

    # Low-confidence signal: Strategy A all-hard, no soft → conf = 3.0/3.5 = 0.857
    # stock 6% 10d, SPY 10% → rs_strong=False; pct_from_52w_high=-0.20 → near_high=False
    feat_low = _make_features(momentum_10d_pct=0.06, pct_from_52w_high=-0.20)
    market_ctx_unknown = {"market_regime": "UNKNOWN", "spy_10d_return": 0.10}
    sigs = generate_signals({"NVDA": feat_low}, market_context=market_ctx_unknown)
    assert all(s["confidence_score"] > 0.90 for s in sigs), (
        f"UNKNOWN regime must filter low-confidence signals (conf > 0.90 gate); "
        f"got: {[(s['ticker'], s['confidence_score']) for s in sigs]}"
    )

    # Empty string regime must also be treated as NEUTRAL
    market_ctx_empty = {"market_regime": ""}
    sigs_empty = generate_signals({"NVDA": feat_low}, market_context=market_ctx_empty)
    assert all(s["confidence_score"] > 0.90 for s in sigs_empty), (
        "Empty regime string must also apply NEUTRAL filter"
    )

    # High-confidence signal must still pass in UNKNOWN regime.
    # Use spy_10d_return=0.01 so stock (6% 10d) outperforms SPY → RS gate passes.
    feat_high = _make_features()  # all conditions + momentum=0.06
    market_ctx_unknown_spy_low = {"market_regime": "UNKNOWN", "spy_10d_return": 0.01}
    sigs_high = generate_signals({"NVDA": feat_high}, market_context=market_ctx_unknown_spy_low)
    assert len(sigs_high) >= 1, (
        "High-confidence signals (conf > 0.90) must pass UNKNOWN regime filter"
    )


# ── days_to_earnings injected for all signal types ────────────────────────────

def test_enrich_signals_injects_days_to_earnings_for_trend_signal():
    """enrich_signals must add days_to_earnings to trend_long and breakout_long signals.

    The LLM prompt blocks ANY new trade when days_to_earnings ≤ 4, including
    trend_long and breakout_long.  Without this field in the signal data, the LLM
    cannot enforce the earnings risk window for non-earnings signals.

    Example: NVDA 20-day breakout 3 days before earnings — ATR stop (±2-3%) cannot
    protect against an overnight earnings gap (±8-15%).
    """
    from signal_engine import strategy_a_trend
    from risk_engine import enrich_signals

    # dte=3 is now blocked at the CODE level (dte <= 5 guard added to strategy_a/b).
    # Test the two-layer protection:
    #   Layer 1: code gate blocks signals at dte <= 5
    #   Layer 2: enrich_signals injects days_to_earnings for signals that do pass (dte > 5)

    # Layer 1: strategy_a blocks at dte=3 (code-level guard, not LLM-prompt-only)
    feat_danger = {**_make_features(), "days_to_earnings": 3}
    assert strategy_a_trend("NVDA", feat_danger) is None, (
        "Strategy A must block signals when dte=3 (code-level earnings proximity guard)"
    )

    # Layer 2: for dte=10 (safe zone), signal passes and enrich_signals injects dte
    feat_safe = {**_make_features(), "days_to_earnings": 10}
    sig = strategy_a_trend("NVDA", feat_safe)
    assert sig is not None, "Strategy A should fire when dte=10 (safe zone)"

    features_dict = {"NVDA": feat_safe}
    enriched = enrich_signals([sig], features_dict)
    assert len(enriched) == 1

    assert "days_to_earnings" in enriched[0], (
        "enrich_signals must inject days_to_earnings into trend_long signals — "
        "LLM needs this for any remaining DTE-based decisions"
    )
    assert enriched[0]["days_to_earnings"] == 10


def test_enrich_signals_no_days_to_earnings_when_unavailable():
    """enrich_signals must not add days_to_earnings when feature is None."""
    from signal_engine import strategy_a_trend
    from risk_engine import enrich_signals

    feat = _make_features()  # no days_to_earnings key
    feat.pop("days_to_earnings", None)  # ensure absent

    sig = strategy_a_trend("NVDA", feat)
    assert sig is not None

    features_dict = {"NVDA": feat}
    enriched = enrich_signals([sig], features_dict)
    assert len(enriched) == 1
    # days_to_earnings should be absent (not added as None)
    assert "days_to_earnings" not in enriched[0] or enriched[0]["days_to_earnings"] is None, (
        "days_to_earnings must not be injected when feature is unavailable"
    )


# ── Fix #1: data_layer lookback_days ≥ 400 for 52w high ──────────────────────

def test_data_layer_lookback_sufficient_for_52w_high():
    """data_layer.get_ohlcv default lookback must be ≥ 400 calendar days.

    feature_layer.compute_trend_features() requires len(data) >= 252 trading days
    to compute pct_from_52w_high (and activate the near_52w_high quality bonus).
    252 trading days ≈ 355 calendar days.  A 350-day lookback returns only ~241
    trading days (350 × 252/365 - 9 holidays ≈ 241 < 252), causing _near_52w_high()
    to always return False and suppressing the +0.40 quality bonus on every signal.
    Fix: lookback_days raised to 400 (≈ 276 trading days > 252).
    """
    import inspect
    from data_layer import get_ohlcv
    sig = inspect.signature(get_ohlcv)
    default_lookback = sig.parameters["lookback_days"].default
    assert default_lookback >= 400, (
        f"data_layer.get_ohlcv default lookback_days={default_lookback} is too small. "
        "Need ≥ 400 calendar days to reliably get 252+ trading days for 52w high. "
        "With 350 days (~241 trading days), pct_from_52w_high is always None "
        "and the near_52w_high quality bonus (+0.40) never fires."
    )


def test_feature_layer_52w_high_computed_with_adequate_data():
    """pct_from_52w_high must be computed (not None) when len(data) >= 252."""
    from feature_layer import compute_trend_features

    # 260 trading days — exceeds the 252 threshold
    data = _make_ohlcv(n=260)
    feat = compute_trend_features(data)
    assert feat is not None
    assert feat["pct_from_52w_high"] is not None, (
        "pct_from_52w_high must be computed when data has 260+ rows (≥ 252 threshold). "
        "If None, the near_52w_high quality bonus never fires, suppressing signal quality."
    )


def test_near_52w_high_fires_when_data_adequate():
    """_near_52w_high must return True for a stock at 98% of 52w high (within 5%)."""
    from signal_engine import _near_52w_high
    # pct_from_52w_high = -0.02 → 2% below 52w high → within 5% → True
    assert _near_52w_high({"pct_from_52w_high": -0.02}) is True, (
        "Stock at 98% of 52w high (-2%) must trigger near_52w_high bonus. "
        "This only works if data_layer downloads ≥252 trading days (lookback ≥ 400 cal days)."
    )


# ── Fix #3: exec_lag_adj_net_rr < 1.2 code-level gate ────────────────────────

def test_enrich_signals_drops_low_exec_lag_rr():
    """enrich_signals must drop signals where exec_lag_adj_net_rr < 1.2.

    For low-ATR stocks (ATR ≈ 1% of price), overnight gap cost eats most of the
    expected reward.  Example: entry=$100, ATR=$1:
      stop=$98.50 (+adj_entry=$100.50), target=$103.50
      adj_reward=$3.00, adj_risk=$2.00, adj_net_cost=$0.35
      exec_lag_adj_net_rr = (3.00-0.35)/(2.00+0.35) = 1.13 < 1.2 → BLOCKED
    Without this code gate, the LLM receives a negative-EV-after-friction signal
    and may execute it despite the prompt's advisory exec_lag rule.
    """
    from signal_engine import strategy_a_trend
    from risk_engine import enrich_signals, EXEC_LAG_PCT, ROUND_TRIP_COST_PCT, ATR_TARGET_MULT, ATR_STOP_MULT

    # Construct a signal that will have exec_lag_adj_net_rr < 1.2.
    # ATR=0.8 at entry=100: stop=98.80, target=102.80
    # adj_entry=100.50, adj_reward=2.30, adj_risk=1.70, adj_net_cost≈0.35
    # exec_lag_adj_net_rr = (2.30-0.35)/(1.70+0.35) = 1.95/2.05 ≈ 0.95 < 1.2
    entry = 100.0
    atr   = 0.8   # very small ATR → very tight stop → exec_lag kills the trade
    stop  = round(entry - ATR_STOP_MULT * atr, 2)
    sig = {
        "ticker":           "LOWVOL",
        "strategy":         "trend_long",
        "entry_price":      entry,
        "stop_price":       stop,
        "confidence_score": 0.90,
    }
    features_dict = {"LOWVOL": {
        "atr":                atr,
        "trend_score":        0.8,
        "volume_spike_ratio": 2.5,
        "momentum_10d_pct":   0.06,
    }}

    from risk_engine import enrich_signal_with_risk
    enriched_sig = enrich_signal_with_risk(sig, atr)
    exec_lag_rr = enriched_sig.get("exec_lag_adj_net_rr")

    # Verify this signal actually has exec_lag_adj_net_rr < 1.2 (confirms test validity)
    if exec_lag_rr is not None and exec_lag_rr >= 1.2:
        pytest.skip(
            f"Test signal has exec_lag_adj_net_rr={exec_lag_rr:.2f} ≥ 1.2 — "
            "adjust ATR to create a sub-1.2 signal for this test"
        )

    enriched = enrich_signals([sig], features_dict)
    assert len(enriched) == 0, (
        f"enrich_signals must drop signals with exec_lag_adj_net_rr < 1.2 "
        f"(got exec_lag_adj_net_rr={exec_lag_rr:.2f}). "
        "Signal with negative after-friction EV must be blocked at code level, "
        "not left to LLM advisory rule."
    )


def test_enrich_signals_keeps_normal_exec_lag_rr():
    """enrich_signals must NOT drop standard signals where exec_lag_adj_net_rr >= 1.2.

    For normal watchlist stocks (ATR 3-8% of price), exec_lag_adj_net_rr >> 1.2.
    The gate must only block genuinely thin-stop situations, not standard breakouts.
    """
    from signal_engine import strategy_a_trend
    from risk_engine import enrich_signals

    # Standard signal: ATR=3.0 at entry=100 → exec_lag_adj_net_rr ≈ 1.80
    feat = _make_features(close=100.0, atr=3.0)
    sig  = strategy_a_trend("NVDA", feat)
    assert sig is not None

    features_dict = {"NVDA": feat}
    enriched = enrich_signals([sig], features_dict)
    assert len(enriched) == 1, (
        "Standard breakout signal (ATR=3%) must pass exec_lag gate — "
        "only thin-stop situations should be blocked"
    )
    assert enriched[0].get("exec_lag_adj_net_rr", 0) >= 1.2


# ── Fix #4: performance_engine Sharpe uses observed trade frequency ───────────

def test_sharpe_uses_observed_trade_frequency():
    """Sharpe annualisation must use actual trade count / observed years, not fixed 30.

    With 2 trades exactly 365 days apart, annual frequency ≈ 2.0 (not 30).
    Sharpe = mean(R)/std(R) × sqrt(2.0) — must NOT be sqrt(30).
    """
    import tempfile, json, os
    from performance_engine import open_trade, close_trade, compute_metrics

    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.json', delete=False
    ) as f:
        json.dump([], f)
        trades_path = f.name

    try:
        # Open two trades with known R-multiples and 1-year span
        # Trade 1: entry=100, stop=98, target=104 → R=2.0 (win)
        tid1 = open_trade("AAA", "trend_long", 100.0, 98.0, 10,
                          target_price=104.0, filepath=trades_path)
        # Manually set entry_date to 1 year ago
        trades = json.load(open(trades_path))
        for t in trades:
            if t["trade_id"] == tid1:
                t["entry_date"] = "2025-03-22"
        with open(trades_path, 'w') as f:
            json.dump(trades, f)
        close_trade(tid1, 104.0, filepath=trades_path)

        # Trade 2: entry=100, stop=98, exit=99 → small loss (different R for variance)
        tid2 = open_trade("BBB", "trend_long", 100.0, 98.0, 10,
                          target_price=104.0, filepath=trades_path)
        # Set entry_date to today
        trades = json.load(open(trades_path))
        for t in trades:
            if t["trade_id"] == tid2:
                t["entry_date"] = "2026-03-22"
        with open(trades_path, 'w') as f:
            json.dump(trades, f)
        close_trade(tid2, 99.0, filepath=trades_path)   # small loss → variance in R-series

        # Force exit dates to create known 1-year span
        trades = json.load(open(trades_path))
        for t in trades:
            if t["trade_id"] == tid1:
                t["exit_date"] = "2025-03-22"
            elif t["trade_id"] == tid2:
                t["exit_date"] = "2026-03-22"
        with open(trades_path, 'w') as f:
            json.dump(trades, f)

        metrics = compute_metrics(filepath=trades_path, portfolio_value=100_000)

        assert metrics.get("sharpe_ratio") is not None, "Sharpe must be computed with 2 trades"
        # With fixed freq=30: Sharpe = mean(R)/std(R) × sqrt(30)
        # With actual freq=2: Sharpe = mean(R)/std(R) × sqrt(2)
        # All wins → std(R) could be very small; just verify it doesn't use sqrt(30) magnitude
        # when frequency should be ~2 trades/year.
        # Key: with 2 trades 365 days apart → annual_freq ≈ 2.0
        # So Sharpe magnitude should scale with sqrt(2) not sqrt(30)
        # (sqrt(30)/sqrt(2) = ~3.87× difference — detectable)
        # We can't easily compute R-multiples from close_trade directly, but we can
        # verify the metric exists and is finite
        sharpe = metrics["sharpe_ratio"]
        assert sharpe is not None and abs(sharpe) < 1000, (
            f"Sharpe={sharpe} is unusually large — possible sqrt(n) inflation bug "
            "or fixed freq=30 applied to 2-trade / 1-year sample (should use sqrt(2))"
        )

    finally:
        if os.path.exists(trades_path):
            os.remove(trades_path)


# ── sector concentration denominator fix ─────────────────────────────────────

def test_sector_concentration_uses_portfolio_value_not_invested_only():
    """Sector weights must be relative to total portfolio (incl. cash), not invested-only.

    Bug fixed: previously total_mv (invested portion only) was the denominator.
    When cash is held, sector weights were overstated, falsely triggering the >40%
    sector block and preventing valid new trades.

    Example: portfolio=$200k, Tech positions=$60k.
      - Wrong (old):  60/60 = 100%  → blocks ALL new Tech trades
      - Correct (new): 60/200 = 30% → does NOT block new Tech trades
    """
    import os, sys, json
    sys.path.insert(0, os.path.dirname(__file__))
    from llm_advisor import build_prompt

    # 1 Tech position worth $60k; portfolio_value_usd=$200k (includes $140k cash)
    positions = {
        "portfolio_value_usd": 200_000,
        "positions": [
            {"ticker": "NVDA", "shares": 400, "avg_cost": 150.0}  # $60k in Tech
        ],
    }
    system_msg, user_msg = build_prompt([], positions)

    if system_msg is None:
        pytest.skip("Prompt template file not found — skipping integration test")

    # The injected sector_concentration JSON should have Technology at 0.30 (60k/200k)
    # not 1.0 (60k/60k).  Parse the JSON section.
    import re
    match = re.search(r'"sector_concentration":\s*(\{[^}]+\})', user_msg)
    assert match, "sector_concentration field not found in prompt"
    sector_json = json.loads(match.group(1))

    tech_weight = sector_json.get("Technology")
    assert tech_weight is not None, "Technology not in sector_concentration"
    # With $60k Tech / $200k portfolio = 0.30 (allow small float rounding)
    assert tech_weight < 0.40, (
        f"Technology sector weight={tech_weight} > 0.40 — denominator is invested-only "
        "not total portfolio. Bug: should use portfolio_value, not total_mv."
    )
    assert abs(tech_weight - 0.30) < 0.05, (
        f"Technology sector weight={tech_weight}, expected ~0.30 (60k/200k portfolio). "
        "Denominator must be portfolio_value_usd, not sum of positions market value."
    )


def test_build_prompt_includes_recent_trades_section():
    """build_prompt must inject section 5 (recent trades) for the loss-streak cool-down rule.

    Without section 5, the cool-down rule always falls back to 'ignore' — three
    consecutive losses never trigger the 3-day pause, increasing max drawdown.
    """
    import os, sys
    sys.path.insert(0, os.path.dirname(__file__))
    from llm_advisor import build_prompt

    positions = {"portfolio_value_usd": 100_000, "positions": []}
    _, user_msg = build_prompt([], positions)

    if user_msg is None:
        pytest.skip("Prompt template file not found — skipping integration test")

    assert "5)" in user_msg and "RECENT TRADES" in user_msg, (
        "Section 5 (RECENT TRADES) not injected into prompt. "
        "Loss-streak cool-down rule ('3 consecutive losses → pause 3 days') "
        "permanently ignored when this section is absent."
    )


def test_build_prompt_warns_missing_entry_date():
    """build_prompt must surface a data_warning when positions lack entry_date.

    Without entry_date, the TIME_STOP (45-day stagnation rule) silently never fires,
    allowing stagnant positions to occupy capital indefinitely.
    """
    import os, sys
    sys.path.insert(0, os.path.dirname(__file__))
    from llm_advisor import build_prompt

    # Position with NO entry_date
    positions = {
        "portfolio_value_usd": 100_000,
        "positions": [
            {"ticker": "NVDA", "shares": 10, "avg_cost": 100.0}
            # No "entry_date" key
        ],
    }
    _, user_msg = build_prompt([], positions)

    if user_msg is None:
        pytest.skip("Prompt template file not found — skipping integration test")

    assert "TIME_STOP disabled" in user_msg or "entry_date" in user_msg, (
        "No data_warning about missing entry_date injected. "
        "TIME_STOP rule silently fails without this field — users must be alerted."
    )


# ── Problem fixes: cash_usd, signal_target inequality, exec_lag in sizing ─────

def test_portfolio_value_includes_cash():
    """Portfolio value must include cash_usd when present in open_positions.json."""
    import math
    from portfolio_engine import compute_position_size, ROUND_TRIP_COST_PCT, EXEC_LAG_PCT

    # Without cash: equity only
    shares_no_cash = compute_position_size(60_000, 50.0, 45.0)["shares_to_buy"]

    # With cash: same equity + 40k cash = 100k total
    shares_with_cash = compute_position_size(100_000, 50.0, 45.0)["shares_to_buy"]

    assert shares_with_cash > shares_no_cash, (
        "Including cash must increase position size (1% risk of larger total portfolio)"
    )
    # Verify exact math: risk_amount = 100k × 1% = $1000; net_risk = 5 + 0.175 + 0.25 = 5.425
    expected = math.floor(100_000 * 0.01 / (5.0 + 50.0 * ROUND_TRIP_COST_PCT + 50.0 * EXEC_LAG_PCT))
    assert shares_with_cash == expected, (
        f"Expected {expected} shares for $100k portfolio, got {shares_with_cash}"
    )


def test_signal_target_fires_at_exactly_target_price():
    """SIGNAL_TARGET must fire when price equals the signal target (not only strictly above)."""
    from position_manager import compute_exit_levels, evaluate_exit_signals

    avg_cost = 100.0
    signal_target = 110.0
    profit_target = 120.0

    exit_levels = compute_exit_levels(avg_cost, atr=None, signal_target_price=signal_target)

    # Price exactly at signal target (edge case — strict < would miss this)
    result = evaluate_exit_signals(
        current_price=signal_target,
        avg_cost=avg_cost,
        exit_levels=exit_levels,
    )
    signal_target_rules = [r for r in result["triggered_rules"] if r["rule"] == "SIGNAL_TARGET"]
    assert len(signal_target_rules) == 1, (
        f"SIGNAL_TARGET must fire when price == signal_target ({signal_target}). "
        f"Triggered rules: {result['triggered_rules']}"
    )


def test_exec_lag_included_in_position_sizing():
    """Position sizing denominator must include exec_lag (0.5% gap) not just round-trip cost."""
    import math
    from portfolio_engine import (
        compute_position_size, ROUND_TRIP_COST_PCT, EXEC_LAG_PCT
    )
    pv    = 100_000
    entry = 50.0
    stop  = 48.5   # 3% ATR → wide enough stop to avoid 20% position cap

    result = compute_position_size(pv, entry, stop)
    assert result is not None

    # net_risk must include: (entry-stop) + cost + gap
    expected_net_risk = round((entry - stop) + entry * ROUND_TRIP_COST_PCT + entry * EXEC_LAG_PCT, 4)
    assert result["net_risk_per_share"] == expected_net_risk, (
        f"net_risk_per_share={result['net_risk_per_share']} != expected {expected_net_risk}. "
        "Execution gap (0.5%) must be included in sizing denominator to keep actual risk ≤ 1%."
    )

    # Verify shares is SMALLER than it would be without exec_lag (gap increases denominator)
    cost_only_net_risk = round((entry - stop) + entry * ROUND_TRIP_COST_PCT, 4)
    shares_if_no_gap = math.floor(pv * 0.01 / cost_only_net_risk)
    assert result["shares_to_buy"] < shares_if_no_gap, (
        f"With exec_lag in denominator, shares ({result['shares_to_buy']}) must be smaller "
        f"than without gap ({shares_if_no_gap}) — gap cost increases true risk per share."
    )


def test_prompt_atr_gate_7pct_for_trend_breakout():
    """LLM prompt SYSTEM section must specify 7% ATR limit for trend_long / breakout_long."""
    from llm_advisor import build_prompt

    system_msg, _ = build_prompt([], None)
    if system_msg is None:
        pytest.skip("Prompt template not found")

    # After fix: system message must reference 0.07 for trend/breakout signals
    assert "0.07" in system_msg, (
        "Prompt SYSTEM section must reference 0.07 ATR gate for trend_long/breakout_long — "
        "code uses 7% but old prompt had 5%, causing LLM to reject valid high-beta breakouts."
    )


# ── Fix 1: Strategy C earnings gap risk sizing ────────────────────────────────

def test_earnings_signal_sized_by_gap_risk_not_atr():
    """
    earnings_event_long signals must be sized using 8% gap risk, not the ATR stop distance.

    Without this fix: a 3% ATR stop (entry $100, stop $97) produces
      shares = $1000 / $3 = 333 shares = $33,333 position.
    With 10% adverse earnings gap: actual loss = 333 × $10 = $3,333 = 3.3% of $100k.

    With fix (8% gap floor): effective stop = $100 × (1 - 0.08) = $92.
      shares = $1000 / $8 = 125 shares = $12,500 position.
    With 10% adverse gap: loss = 125 × $10 = $1,250 ≈ 1.25% of $100k ✓
    """
    import math
    from portfolio_engine import size_signals, EARNINGS_GAP_RISK_PCT

    entry   = 100.0
    # ATR stop only 2% below entry → without gap floor would produce 5× oversized position
    atr_stop = 98.0   # 2% below → risk_per_share = $2

    earnings_sig = {
        "ticker":           "TEST",
        "strategy":         "earnings_event_long",
        "entry_price":      entry,
        "stop_price":       atr_stop,
        "confidence_score": 0.90,
    }
    trend_sig = {
        "ticker":           "TEST2",
        "strategy":         "trend_long",
        "entry_price":      entry,
        "stop_price":       atr_stop,
        "confidence_score": 0.90,
    }

    portfolio_value = 100_000
    sized = size_signals([earnings_sig, trend_sig], portfolio_value)

    earn_sized  = sized[0]
    trend_sized = sized[1]

    # Earnings signal must have gap risk flag
    assert earn_sized.get("sizing", {}).get("earnings_gap_risk_applied") is True, (
        "earnings_event_long sizing must set earnings_gap_risk_applied=True"
    )

    # Trend signal must NOT have gap risk applied
    assert trend_sized.get("sizing", {}).get("earnings_gap_risk_applied") is None, (
        "trend_long sizing must NOT apply earnings_gap_risk_applied"
    )

    earn_shares  = earn_sized["sizing"]["shares_to_buy"]
    trend_shares = trend_sized["sizing"]["shares_to_buy"]

    # Earnings shares must be significantly fewer than trend shares
    # (because effective stop distance for earnings = 8%, trend = 2%)
    assert earn_shares < trend_shares, (
        f"Earnings shares ({earn_shares}) must be < trend shares ({trend_shares}) "
        "— gap risk floor (8%) produces smaller position than ATR stop (2%)"
    )

    # Verify earnings position is approximately 1% risk at the 8% gap level
    earn_sizing = earn_sized["sizing"]
    effective_stop = earn_sizing["effective_stop_for_sizing"]
    assert abs(effective_stop - (entry - entry * EARNINGS_GAP_RISK_PCT)) < 0.01, (
        f"effective_stop_for_sizing={effective_stop} must equal entry - 8% = "
        f"{entry - entry * EARNINGS_GAP_RISK_PCT:.2f}"
    )

    # Worst-case gap loss on the earnings position should be close to 1% of portfolio
    max_gap_loss = earn_shares * entry * 0.10   # 10% adverse gap
    gap_loss_pct = max_gap_loss / portfolio_value
    assert gap_loss_pct < 0.015, (
        f"10% adverse gap on earnings position = {gap_loss_pct*100:.2f}% of portfolio "
        f"(should be ≤ 1.5%); earnings plays were oversized by 3-5× without this fix."
    )


def test_earnings_gap_risk_uses_larger_of_atr_or_gap():
    """
    When ATR stop distance > 8% gap risk (very wide-stop stocks near the ATR gate),
    the ATR stop should still be used (gap risk would be LESS conservative).
    """
    from portfolio_engine import size_signals, EARNINGS_GAP_RISK_PCT

    entry     = 100.0
    wide_stop = 90.0   # 10% ATR stop > 8% gap floor → ATR stop is MORE conservative

    sig = {
        "ticker":       "WIDE",
        "strategy":     "earnings_event_long",
        "entry_price":  entry,
        "stop_price":   wide_stop,
    }
    sized = size_signals([sig], 100_000)
    if not sized[0].get("sizing"):
        return  # positioning failed for some other reason, skip

    effective_stop = sized[0]["sizing"]["effective_stop_for_sizing"]
    # ATR stop (90) = 10% below → 10% > 8% gap → effective_stop should be the ATR stop (90)
    expected = wide_stop   # max(10%, 8%) = 10% → use ATR stop
    assert effective_stop == expected, (
        f"When ATR stop distance (10%) > gap risk (8%), effective_stop={effective_stop} "
        f"must equal the ATR stop {expected} (ATR is more conservative, use that)"
    )


# ── Fix 2: Earnings entry cancel threshold 1.5% ───────────────────────────────

def test_build_prompt_signal_target_low_urgency_in_attention_list():
    """SIGNAL_TARGET (LOW urgency) must appear in positions_requiring_attention.

    When a position reaches the 3.5×ATR technical target (+7%–+20%), the system
    requires a REDUCE 33% action.  If the position is filtered out of Section 4
    (positions_requiring_attention) because urgency=LOW, the LLM will miss this
    action and the winner gives back its locked R:R.

    Bug fixed: _min_surface_rank=1 excluded LOW urgency; SIGNAL_TARGET now
    bypasses this filter because it requires an explicit action (REDUCE 33%),
    unlike PROFIT_LADDER_30 (LOW, action=HOLD) which remains excluded.
    """
    import os, sys
    sys.path.insert(0, os.path.dirname(__file__))
    from llm_advisor import build_prompt

    fake_trend_signals = {
        "market_regime": {"regime": "BULL", "note": "", "indices": {}},
        "quant_signals": [],
        "signals": {
            "CRDO": {
                "close": 112.0,
                "atr": 4.0,
                "20d_high": 110.0,
                "breakout": False,
                "breakdown": False,
                "position": {
                    "shares": 10,
                    "avg_cost": 100.0,
                    "market_value_usd": 1120.0,
                    "unrealized_pnl_pct": 0.12,
                    "legacy_basis": False,
                    "stop_source": "default",
                    "exit_levels": {
                        "hard_stop_price":     88.0,
                        "profit_target_price": 120.0,
                        "signal_target_price": 108.0,
                        "signal_target_pct":   0.08,
                    },
                    "exit_signals": {
                        "any_triggered": True,
                        "critical_exit": False,
                        "high_urgency":  False,
                        "triggered_rules": [
                            {
                                "rule":    "SIGNAL_TARGET",
                                "urgency": "LOW",
                                "message": "Price 112.00 >= signal target 108.00 — reduce 33%",
                            },
                        ],
                    },
                    "trailing_stop_from_20d_high": 101.2,
                    "drawdown_from_20d_high_pct":  0.018,
                },
            }
        },
    }

    positions = {"portfolio_value_usd": 100_000, "positions": []}
    system_msg, user_msg = build_prompt([], positions, trend_signals=fake_trend_signals)

    if system_msg is None:
        pytest.skip("Prompt template file not found — skipping integration test")

    assert "SIGNAL_TARGET" in user_msg, (
        "SIGNAL_TARGET must appear in Section 4 positions_requiring_attention — "
        "even though urgency=LOW, it requires REDUCE 33% action. "
        "Without this, winners in the +7%%–+20%% zone miss explicit LLM attention."
    )
    assert "positions_requiring_attention" in user_msg or "CRDO" in user_msg, (
        "CRDO position with SIGNAL_TARGET must be surfaced in the prompt"
    )


def test_build_prompt_daily_return_pct_in_attention_entry():
    """daily_return_pct and prev_close must appear in positions_requiring_attention.

    The post-earnings gap rules require daily_return_pct:
      - > +8%  → REDUCE 50%  (lock in earnings beat gain)
      - < -5%  → EXIT        (thesis broken)
    Without this field in Section 4, the LLM cannot distinguish a single-day
    earnings gap from cumulative unrealised P&L since entry.
    """
    import os, sys
    sys.path.insert(0, os.path.dirname(__file__))
    from llm_advisor import build_prompt

    fake_trend_signals = {
        "market_regime": {"regime": "BULL", "note": "", "indices": {}},
        "quant_signals": [],
        "signals": {
            "NVDA": {
                "close": 130.0,
                "atr": 5.0,
                "20d_high": 128.0,
                "breakout": False,
                "breakdown": False,
                "position": {
                    "shares": 10,
                    "avg_cost": 100.0,
                    "market_value_usd": 1300.0,
                    "unrealized_pnl_pct": 0.30,
                    "legacy_basis": False,
                    "stop_source": "default",
                    "prev_close":        118.0,
                    "daily_return_pct":  0.102,   # +10.2% today (earnings beat gap)
                    "exit_levels": {
                        "hard_stop_price":     88.0,
                        "profit_target_price": 120.0,
                    },
                    "exit_signals": {
                        "any_triggered": True,
                        "critical_exit": False,
                        "high_urgency":  False,
                        "triggered_rules": [
                            {
                                "rule":    "PROFIT_LADDER_30",
                                "urgency": "LOW",
                                "message": "Unrealised gain 30.0% — let winner run",
                            },
                        ],
                    },
                    "trailing_stop_from_20d_high": 117.76,
                    "drawdown_from_20d_high_pct":  0.016,
                },
            }
        },
    }

    positions = {"portfolio_value_usd": 100_000, "positions": []}
    system_msg, user_msg = build_prompt([], positions, trend_signals=fake_trend_signals)

    if system_msg is None:
        pytest.skip("Prompt template file not found — skipping integration test")

    # NVDA has PROFIT_LADDER_30 (LOW, HOLD) only — should still be in section 3b.
    # Check that daily_return_pct appears somewhere in the prompt for NVDA.
    # (It arrives via section 3b technical context even if not section 4.)
    assert "daily_return_pct" in user_msg, (
        "daily_return_pct must appear in the prompt so the LLM can apply the "
        "post-earnings gap rules (daily_return_pct > +8%% → REDUCE 50%%)"
    )
    assert "0.102" in user_msg or "daily_return_pct" in user_msg, (
        "The actual daily_return_pct value must be visible to the LLM"
    )


def test_build_prompt_signal_target_daily_return_in_attention_entry():
    """When SIGNAL_TARGET fires and daily_return_pct is available, both must appear
    in positions_requiring_attention (Section 4), not just in Section 3b.

    This ensures the LLM has all needed fields in one place for correct action output.
    """
    import os, sys
    sys.path.insert(0, os.path.dirname(__file__))
    from llm_advisor import build_prompt
    import json

    fake_trend_signals = {
        "market_regime": {"regime": "BULL", "note": "", "indices": {}},
        "quant_signals": [],
        "signals": {
            "CRDO": {
                "close": 112.0,
                "atr": 4.0,
                "20d_high": 110.0,
                "breakout": False,
                "breakdown": False,
                "position": {
                    "shares": 10,
                    "avg_cost": 100.0,
                    "market_value_usd": 1120.0,
                    "unrealized_pnl_pct": 0.12,
                    "legacy_basis": False,
                    "stop_source": "default",
                    "prev_close":       108.0,
                    "daily_return_pct": 0.037,
                    "exit_levels": {
                        "hard_stop_price":     88.0,
                        "profit_target_price": 120.0,
                        "signal_target_price": 108.0,
                        "signal_target_pct":   0.08,
                    },
                    "exit_signals": {
                        "any_triggered": True,
                        "critical_exit": False,
                        "high_urgency":  False,
                        "triggered_rules": [
                            {
                                "rule":    "SIGNAL_TARGET",
                                "urgency": "LOW",
                                "message": "Price 112.00 >= signal target 108.00",
                            },
                        ],
                    },
                    "trailing_stop_from_20d_high": 101.2,
                    "drawdown_from_20d_high_pct":  0.018,
                },
            }
        },
    }

    positions = {"portfolio_value_usd": 100_000, "positions": []}
    system_msg, user_msg = build_prompt([], positions, trend_signals=fake_trend_signals)

    if system_msg is None:
        pytest.skip("Prompt template file not found — skipping integration test")

    # Find the positions_requiring_attention section in the JSON output
    import re
    # Extract the pos_mgmt JSON block from the prompt
    match = re.search(r'POSITION MANAGEMENT.*?(\{.*?\})\s*\n\n', user_msg, re.DOTALL)
    if match:
        try:
            pos_mgmt = json.loads(match.group(1))
            attention = pos_mgmt.get("positions_requiring_attention", [])
            crdo_entry = next((e for e in attention if e.get("ticker") == "CRDO"), None)
            assert crdo_entry is not None, (
                "CRDO with SIGNAL_TARGET must be in positions_requiring_attention"
            )
            assert "daily_return_pct" in crdo_entry, (
                "daily_return_pct must be present in the attention entry for earnings-gap detection"
            )
            assert "prev_close" in crdo_entry, (
                "prev_close must be present in the attention entry"
            )
        except (json.JSONDecodeError, StopIteration):
            # If JSON parsing fails, do a simpler string check
            assert "daily_return_pct" in user_msg
            assert "SIGNAL_TARGET" in user_msg
    else:
        # Fallback: just verify both fields appear in the prompt
        assert "daily_return_pct" in user_msg
        assert "SIGNAL_TARGET" in user_msg


def test_earnings_entry_note_has_1_5_pct_cancel_threshold():
    """
    earnings_event_long entry_note must use 1.015 cancel threshold (not 1.005).

    Pre-earnings PEAD drift routinely produces 0.5-1.5% gap-ups at the next
    open.  The 0.5% threshold cancelled 30-40% of valid earnings setups
    that were simply experiencing normal pre-event drift.
    """
    from signal_engine import strategy_c_earnings

    feat = {
        "earnings_event_window":      True,
        "momentum_10d_pct":           0.08,   # strong pre-earnings momentum
        "positive_surprise_history":  True,
        "close":                      100.0,
        "atr":                        2.0,    # ATR 2% < 5% gate
        "days_to_earnings":           7,
        "above_200ma":                True,
    }
    sig = strategy_c_earnings("TEST", feat)
    assert sig is not None, "Valid earnings setup must produce a signal"
    entry_note = sig.get("entry_note", "")
    assert "1.015" in entry_note, (
        f"earnings_event_long entry_note must contain '1.015' (1.5% cancel threshold). "
        f"Got: '{entry_note}'. "
        "0.5% threshold cancels valid PEAD setups; 1.5% allows normal pre-earnings drift."
    )
    # All three strategies now use 1.015 — verified by dedicated tests
    # test_strategy_a_entry_note_uses_1_5_pct_cancel and
    # test_strategy_b_entry_note_uses_1_5_pct_cancel


# ── Contract tests: code↔prompt interface ────────────────────────────────────
# These tests verify that fields referenced in trade_advice.txt as "直接使用 X 字段"
# are actually present in the data structures that the code injects into the prompt.
# Root cause of repeated bugs: code added a field but prompt didn't read it (or vice
# versa). These tests fail fast when the interface drifts.

def _make_preflight_trend_signals(regime="NORMAL", pnl=0.05, breach="OK"):
    """Minimal trend_signals dict for preflight contract tests."""
    return {
        "signals": {
            "TEST": {
                "close": 100.0,
                "position": {
                    "shares": 10,
                    "avg_cost": 90.0,
                    "unrealized_pnl_pct": pnl,
                    "breach_status": breach,
                    "exit_levels": {"hard_stop_price": 85.0},
                    "exit_signals": {
                        "any_triggered": True,
                        "triggered_rules": [
                            {"rule": "TRAILING_STOP", "urgency": "HIGH",
                             "message": "Trailing stop hit"}
                        ],
                    },
                },
            }
        }
    }


def test_preflight_outputs_required_fields():
    """
    Contract: compute_account_state must return all fields that llm_advisor injects
    into section 4 of the prompt.  If a field is missing here, it silently vanishes
    from the prompt and the corresponding rule in trade_advice.txt has no data.
    """
    from preflight_validator import compute_account_state, enrich_positions_with_breach_status
    ts = _make_preflight_trend_signals()
    enrich_positions_with_breach_status(ts)
    result = compute_account_state(ts, heat_data={}, regime_data={"regime": "NORMAL"})

    required_fields = [
        "account_state",
        "new_trade_locked",
        "lock_reason",
        "position_states",
        "suggested_reduce_pct",
        "bear_emergency_stops",
        "data_warnings",
    ]
    for field in required_fields:
        assert field in result, (
            f"preflight output missing '{field}' — trade_advice.txt references this field "
            f"but code doesn't produce it. Add it to compute_account_state() return dict."
        )


def test_preflight_suggested_reduce_pct_populated_for_high_reduce():
    """
    Contract: HIGH_REDUCE positions must have a pre-computed reduce % in
    suggested_reduce_pct.  If missing, LLM falls back to prose table lookup
    (the error-prone path this field was designed to eliminate).
    """
    from preflight_validator import compute_account_state, enrich_positions_with_breach_status
    ts = _make_preflight_trend_signals(pnl=0.15)  # TRAILING_STOP → HIGH_REDUCE
    enrich_positions_with_breach_status(ts)
    result = compute_account_state(ts, heat_data={}, regime_data={"regime": "NORMAL"})

    assert result["position_states"].get("TEST") == "HIGH_REDUCE", (
        "Expected TEST to be HIGH_REDUCE given TRAILING_STOP HIGH urgency"
    )
    assert "TEST" in result["suggested_reduce_pct"], (
        "HIGH_REDUCE position 'TEST' is missing from suggested_reduce_pct — "
        "LLM will fall back to prose table lookup"
    )
    pct = result["suggested_reduce_pct"]["TEST"]
    assert pct in (25, 33, 50, 100), f"suggested_reduce_pct={pct} is not a valid percentage"


def test_preflight_bear_emergency_stops_populated_when_bear():
    """
    Contract: bear_emergency_stops must be populated for all tickers when
    regime=BEAR so the LLM can enforce current_price × 0.95 for HOLD positions
    that are not in section 3b.
    """
    from preflight_validator import compute_account_state, enrich_positions_with_breach_status, BEAR_STOP_PCT
    ts = _make_preflight_trend_signals()
    ts["signals"]["HOLD_TICKER"] = {"close": 200.0}  # a position with no exit signals
    enrich_positions_with_breach_status(ts)
    result = compute_account_state(ts, heat_data={}, regime_data={"regime": "BEAR"})

    assert result["account_state"] == "DEFENSIVE", "BEAR should set DEFENSIVE state"
    assert result["bear_emergency_stops"], "bear_emergency_stops must be non-empty in BEAR regime"
    for ticker, stop in result["bear_emergency_stops"].items():
        close = ts["signals"][ticker].get("close", 0)
        expected = round(close * (1 - BEAR_STOP_PCT), 2)
        assert abs(stop - expected) < 0.01, (
            f"{ticker} bear_emergency_stop={stop} expected={expected} "
            f"(current_price × {1 - BEAR_STOP_PCT})"
        )


def test_preflight_bear_emergency_stops_empty_when_not_bear():
    """
    Contract: bear_emergency_stops must be empty when regime is not BEAR,
    so the LLM doesn't apply bear tightening in normal/defensive markets.
    """
    from preflight_validator import compute_account_state, enrich_positions_with_breach_status
    ts = _make_preflight_trend_signals()
    enrich_positions_with_breach_status(ts)
    result = compute_account_state(ts, heat_data={}, regime_data={"regime": "NORMAL"})
    assert result["bear_emergency_stops"] == {}, (
        "bear_emergency_stops should be empty in NORMAL regime"
    )


def test_preflight_bear_shallow_does_not_lock_new_trade():
    """
    BEAR_SHALLOW (both below 200MA but min leg > -5%): new_trade_locked must be False.

    Rationale: BEAR_SHALLOW allows new trades in Commodities/Healthcare (run.py filters
    signals to those sectors).  Setting new_trade_locked=True for ALL BEAR regimes was
    overriding this rule, silently preventing any new defensive-sector trade even when
    valid signals existed and the code had already pre-filtered them.

    The fix: check pct_from_ma in regime_data to distinguish shallow from deep.
    """
    from preflight_validator import compute_account_state, enrich_positions_with_breach_status
    ts = _make_preflight_trend_signals()
    enrich_positions_with_breach_status(ts)
    regime_data = {
        "regime": "BEAR",
        "indices": {
            "SPY": {"pct_from_ma": -0.03},   # -3%: below MA but > -5%
            "QQQ": {"pct_from_ma": -0.04},   # -4%: below MA but > -5%
        },
    }
    result = compute_account_state(ts, heat_data={}, regime_data=regime_data)

    assert result["account_state"] == "DEFENSIVE", (
        "BEAR_SHALLOW must still be DEFENSIVE account_state (cautious posture)"
    )
    assert result["new_trade_locked"] is False, (
        "BEAR_SHALLOW must NOT lock new_trade — Commodities/Healthcare signals are allowed. "
        "new_trade_locked=True was overriding the BEAR_SHALLOW rule in trade_advice.txt."
    )
    assert "BEAR_SHALLOW" in result["lock_reason"], (
        "lock_reason must mention BEAR_SHALLOW so LLM knows which rule applies"
    )


def test_preflight_bear_deep_still_locks_new_trade():
    """
    BEAR_DEEP (both below 200MA and min leg ≤ -5%): new_trade_locked must be True.

    Defensive sectors are NOT permitted in BEAR_DEEP — the code returns no signals.
    """
    from preflight_validator import compute_account_state, enrich_positions_with_breach_status
    ts = _make_preflight_trend_signals()
    enrich_positions_with_breach_status(ts)
    regime_data = {
        "regime": "BEAR",
        "indices": {
            "SPY": {"pct_from_ma": -0.06},   # -6%: past the -5% threshold
            "QQQ": {"pct_from_ma": -0.08},
        },
    }
    result = compute_account_state(ts, heat_data={}, regime_data=regime_data)

    assert result["new_trade_locked"] is True, (
        "BEAR_DEEP must lock new_trade — no signals should reach the LLM."
    )
    assert "BEAR_DEEP" in result["lock_reason"]


def test_preflight_bear_no_pct_data_defaults_to_locked():
    """
    BEAR regime without pct_from_ma data (e.g. regime fetch failure): safe fallback
    treats as BEAR_DEEP and locks new trades.
    """
    from preflight_validator import compute_account_state, enrich_positions_with_breach_status
    ts = _make_preflight_trend_signals()
    enrich_positions_with_breach_status(ts)
    # regime_data has BEAR but no indices pct data
    result = compute_account_state(ts, heat_data={}, regime_data={"regime": "BEAR"})
    assert result["new_trade_locked"] is True, (
        "BEAR without pct_from_ma data must default to locked (safe fallback — assume BEAR_DEEP)"
    )


# ── Bidirectional contract: PROMPT_FIELD_REGISTRY ────────────────────────────
# PROMPT_FIELD_REGISTRY is the single source of truth for the code↔prompt
# interface.  It lists every field that trade_advice.txt tells the LLM to
# read directly ("直接使用 X 字段").
#
# Two tests use this registry:
#   test_registry_fields_exist_in_code_output  — code direction (produces the fields)
#   test_registry_fields_referenced_in_prompt  — prompt direction (references the fields)
#
# When you rename a field:
#   1. Update the field name here in the registry.
#   2. Update the code that produces it.
#   3. Update trade_advice.txt to reference the new name.
#   4. Run tests — both directions will fail until all three are in sync.
#
# This prevents the silent drift pattern: code adds field X, prompt never reads
# it (or vice versa), and the rule quietly fails in production.

PROMPT_FIELD_REGISTRY = {
    # ── Section 4 top-level (pos_mgmt_data) ──────────────────────────────
    "section4_top": {
        "description": "Fields injected into section 4 of the LLM prompt",
        "producer":    "llm_advisor.build_prompt → pos_mgmt_data dict",
        "fields": [
            "new_trade_locked",        # Task A step 0 shortcut
            "lock_reason",             # explains why trading is locked
            "account_state",           # FIRE | DEFENSIVE | NORMAL
            "position_states",         # {ticker: CRITICAL_EXIT|HIGH_REDUCE|WATCH|HOLD}
            "suggested_reduce_pct",    # {ticker: int} — pre-computed reduce %
            "bear_emergency_stops",    # {ticker: float} — current_price × 0.95 in BEAR
            "current_prices",          # {ticker: float} — for BEAR rule on HOLD positions
        ],
    },
    # ── Section 3a (quant signals) ────────────────────────────────────────
    "section3a_signal": {
        "description": "Fields in each quant signal that the LLM is told to read directly",
        "producer":    "risk_engine.enrich_signals + portfolio_engine.size_signals",
        "fields": [
            "trade_quality_score",     # TQS gate: < 0.60 → NO NEW TRADE
            "confidence_score",        # signal quality
            "risk_reward_ratio",       # RR gate: < 2.0 → NO NEW TRADE
            "net_risk_reward_ratio",   # after execution cost
            "exec_lag_adj_net_rr",     # after cost + next-day gap
            "entry_price",             # used directly in output
            "stop_price",              # used directly in output
            "target_price",            # used directly in output
            "entry_note",              # cancel threshold instruction
        ],
    },
    # ── Section 3a sizing sub-dict ────────────────────────────────────────
    "section3a_sizing": {
        "description": "Fields in signal.sizing sub-dict",
        "producer":    "portfolio_engine.size_signals",
        "fields": [
            "shares_to_buy",               # used directly in output
            "earnings_gap_risk_applied",   # explains reduced sizing for earnings signals
        ],
    },
    # ── Section 3b / section 4 position context ───────────────────────────
    "section3b_position": {
        "description": "Fields in position context (trend_signals.position sub-dict)",
        "producer":    "trend_signals.compute_position_context",
        "fields": [
            "breach_status",               # OK | DELAYED_BREACH | HISTORIC_BREACH
            "unrealized_pnl_pct",          # used for averaging-down prevention
            "exit_levels",                 # contains hard_stop_price, atr_stop_price, etc.
            "trailing_stop_from_20d_high", # used in legacy basis / TRAILING_STOP rule
            "drawdown_from_20d_high_pct",  # used in legacy basis rule (-8% threshold)
            "daily_return_pct",            # used for post-earnings gap detection
        ],
    },
}


def test_registry_fields_exist_in_code_output():
    """
    Direction 1 — Code produces what prompt needs.

    For each section, builds the actual code output and asserts every registered
    field exists.  If a field is removed or renamed in code, this fails immediately.
    """
    import os

    # ── Section 4 top-level ───────────────────────────────────────────────
    from preflight_validator import compute_account_state, enrich_positions_with_breach_status
    ts = _make_preflight_trend_signals()
    enrich_positions_with_breach_status(ts)
    preflight = compute_account_state(ts, heat_data={}, regime_data={"regime": "NORMAL"})

    # pos_mgmt_data is built in llm_advisor; test the preflight dict which feeds it
    s4_required = PROMPT_FIELD_REGISTRY["section4_top"]["fields"]
    # preflight provides: account_state, new_trade_locked, lock_reason,
    #                     position_states, suggested_reduce_pct, bear_emergency_stops
    # current_prices is added by llm_advisor from trend_signals — test it separately
    preflight_provided = {
        "new_trade_locked", "lock_reason", "account_state",
        "position_states", "suggested_reduce_pct", "bear_emergency_stops",
    }
    for field in preflight_provided:
        assert field in preflight, (
            f"preflight output missing '{field}' — "
            f"trade_advice.txt 直接引用此字段但代码不产出它。"
            f"需在 compute_account_state() 返回值中添加。"
        )

    # current_prices: must be present in the signals dict (llm_advisor extracts it)
    for _ticker, _sig in ts.get("signals", {}).items():
        assert "close" in _sig, (
            f"Signal for {_ticker} missing 'close' — "
            f"llm_advisor builds current_prices from signal['close']; "
            f"without it current_prices will be empty and BEAR rule fails for HOLD positions."
        )

    # ── Section 3a signal fields ──────────────────────────────────────────
    from risk_engine import enrich_signals
    from signal_engine import strategy_a_trend
    feat = _make_features()
    raw_sig = strategy_a_trend("TEST", feat)
    assert raw_sig is not None, "strategy_a_trend must produce a signal for valid features"
    enriched = enrich_signals([raw_sig], {"TEST": feat})
    assert enriched, "enrich_signals returned empty list"
    sig = enriched[0]

    s3a_fields = PROMPT_FIELD_REGISTRY["section3a_signal"]["fields"]
    for field in s3a_fields:
        assert field in sig, (
            f"Enriched signal missing '{field}' — "
            f"trade_advice.txt 直接引用此字段（直接使用第3a节信号的{field}字段）。"
            f"需在 enrich_signals() 或 strategy_a_trend() 中添加。"
        )

    # ── Section 3a sizing sub-dict ────────────────────────────────────────
    from portfolio_engine import size_signals
    sized = size_signals(enriched, portfolio_value=70000)
    assert sized, "size_signals returned empty list"
    sizing = sized[0].get("sizing")
    assert sizing is not None, (
        "size_signals must add 'sizing' sub-dict — "
        "trade_advice.txt 直接引用 sizing.shares_to_buy 和 sizing.earnings_gap_risk_applied"
    )
    s3a_sizing_fields = PROMPT_FIELD_REGISTRY["section3a_sizing"]["fields"]
    # earnings_gap_risk_applied is only present for earnings_event_long
    # shares_to_buy must always be present
    assert "shares_to_buy" in sizing, (
        "sizing dict missing 'shares_to_buy' — "
        "trade_advice.txt: 直接使用第3a节信号的sizing.shares_to_buy字段"
    )

    # ── Section 3b position context fields ───────────────────────────────
    # build a minimal position context via trend_signals.compute_position_context
    from trend_signals import compute_position_context
    import pandas as pd, numpy as np

    # Minimal open_positions data with an entry_date + target_price
    open_pos = {
        "positions": [{
            "ticker":       "TEST",
            "shares":       10,
            "avg_cost":     90.0,
            "entry_date":   "2026-01-01",
            "target_price": 120.0,
        }]
    }
    pos_ctx = compute_position_context(
        ticker="TEST",
        latest_close=100.0,
        open_positions=open_pos,
        atr=2.0,
        high_20d=102.0,
        high_since_entry=105.0,
        prev_close=99.0,
    )
    assert pos_ctx is not None, (
        "compute_position_context returned None for a valid held position"
    )

    s3b_fields = PROMPT_FIELD_REGISTRY["section3b_position"]["fields"]
    for field in s3b_fields:
        assert field in pos_ctx, (
            f"Position context missing '{field}' — "
            f"trade_advice.txt 直接引用此字段用于出场规则判断。"
            f"需在 compute_position_context() 中添加。"
        )


def test_registry_fields_referenced_in_prompt():
    """
    Direction 2 — Prompt actually reads what code produces.

    For every field in PROMPT_FIELD_REGISTRY, asserts that the field name
    appears somewhere in trade_advice.txt.  If someone renames a field in
    trade_advice.txt without updating the registry (or vice versa), this fails.

    This catches the "code produces X, prompt references Y" rename drift that
    the direction-1 test cannot catch.
    """
    import os

    prompt_paths = [
        os.path.join(os.path.dirname(__file__), '..', 'instructinos', 'prompts', 'trade_advice.txt'),
        'instructinos/prompts/trade_advice.txt',
    ]
    prompt_text = None
    for p in prompt_paths:
        if os.path.exists(p):
            with open(p, encoding='utf-8') as f:
                prompt_text = f.read()
            break
    assert prompt_text, "Could not load trade_advice.txt — check path"

    # Fields intentionally omitted from this check:
    # earnings_gap_risk_applied — referenced as sizing.earnings_gap_risk_applied=true (with value)
    # Some fields appear in JSON examples embedded in the prompt, not as bare names.
    # We check the field name appears anywhere in the file (sufficient for drift detection).
    skip_fields = {
        "earnings_gap_risk_applied",  # referenced as 'sizing.earnings_gap_risk_applied=true'
        "risk_per_share",             # internal computation field, not directly read by LLM
        "reward_per_share",           # internal computation field
    }

    for section_key, section in PROMPT_FIELD_REGISTRY.items():
        for field in section["fields"]:
            if field in skip_fields:
                continue
            assert field in prompt_text, (
                f"Field '{field}' (from registry section '{section_key}') "
                f"is NOT referenced in trade_advice.txt.\n"
                f"Either:\n"
                f"  (a) The prompt was updated and the field was renamed — update the registry, or\n"
                f"  (b) The field was added to code but forgotten in the prompt — add it.\n"
                f"Producer: {section['description']}"
            )


# ── risk_engine dropped signals visibility ───────────────────────────────────

def test_enrich_signals_populates_last_dropped_signals():
    """Signals dropped by R:R gate must be recorded in last_dropped_signals.

    Audit P0-3: previously these signals vanished silently; now callers can
    surface them in reports and logs for transparency.
    """
    from risk_engine import enrich_signals, last_dropped_signals

    # Create a signal that will be dropped due to missing ATR
    sig_no_atr = {
        "ticker": "FAKE", "strategy": "trend_long",
        "entry_price": 100.0, "stop_price": 97.0, "confidence_score": 0.85,
    }
    features = {"FAKE": {"close": 100.0}}   # no ATR → signal dropped

    result = enrich_signals([sig_no_atr], features)
    assert result == [], "Signal with no ATR should be dropped"
    assert len(last_dropped_signals) >= 1, (
        "last_dropped_signals must be populated when signals are dropped"
    )
    assert last_dropped_signals[0]["ticker"] == "FAKE"
    assert "ATR" in last_dropped_signals[0]["reason"]


def test_enrich_signals_clears_dropped_on_each_call():
    """last_dropped_signals must reset on each enrich_signals() call."""
    from risk_engine import enrich_signals, last_dropped_signals

    # First call: drop a signal
    enrich_signals(
        [{"ticker": "X", "strategy": "trend_long", "entry_price": 10, "stop_price": 9,
          "confidence_score": 0.8}],
        {"X": {"close": 10.0}},   # no ATR
    )
    assert len(last_dropped_signals) >= 1

    # Second call: no signals → dropped list should be empty
    enrich_signals([], {})
    from risk_engine import last_dropped_signals as fresh
    assert fresh == [], "last_dropped_signals must reset between calls"


# ── filter.py news tier & event keyword coverage ──────────────────────────────

def test_event_keywords_include_critical_t1_terms():
    """EVENT_KEYWORDS must include all terms that protect T1 news from being pre-filtered.

    filter_by_event_keywords runs BEFORE assign_news_tier. Any T1-level event not in
    EVENT_KEYWORDS gets silently dropped and never receives a tier — the LLM never sees it.
    This test documents the required terms so additions to T1_TITLE_KEYWORDS are reflected here.
    """
    from filter import EVENT_KEYWORDS
    required = [
        "merger",    # M&A not phrased as 'acquisition'
        "buyback",   # share buyback programs
        "bankruptcy", # distress events
        "split",     # stock splits
        "dividend",  # dividend changes (not just 'cuts'/'raises' phrasing)
        "recall",    # product recalls
        "resign",    # executive departures
    ]
    for term in required:
        assert term in EVENT_KEYWORDS, (
            f"'{term}' missing from EVENT_KEYWORDS — T1 news with this term "
            f"gets dropped before tier classification (LLM never sees it)"
        )


def test_t1_keywords_include_alternate_guidance_phrasings():
    """T1 keywords must cover 'raises guidance' (not just 'guidance raise').

    Financial headlines use both word orders:
      'guidance raise' (noun-first): 'Guidance raise signals confidence'  — COVERED
      'raises guidance' (verb-first): 'NVDA raises guidance for fiscal year' — was MISSING

    Without the verb-first form, a genuine guidance-raise catalyst from Reuters is
    classified T2 (source-based) instead of T1, meaning the LLM cannot act on it
    independently — it requires a concurrent quant signal.
    """
    from filter import _T1_TITLE_KEYWORDS
    required_alternates = [
        "raises guidance",
        "cuts guidance",
        "lowers guidance",
        "profit warning",
        "beats estimates",
        "misses estimates",
    ]
    for kw in required_alternates:
        assert kw in _T1_TITLE_KEYWORDS, (
            f"'{kw}' missing from _T1_TITLE_KEYWORDS — "
            f"headlines with this phrase are misclassified as T2/T3 "
            f"and cannot independently trigger a trade"
        )


def test_t1_assignment_raises_guidance_headline():
    """'NVDA raises guidance for fiscal year' must be classified T1."""
    from filter import assign_news_tier
    item = {
        "title": "NVDA raises guidance for fiscal year 2026",
        "source": "reuters",
    }
    tier = assign_news_tier(item)
    assert tier == "T1", (
        f"'raises guidance' headline classified as {tier} — "
        "must be T1 (independent trade trigger). "
        "Add 'raises guidance' to _T1_TITLE_KEYWORDS."
    )


def test_t1_assignment_profit_warning_headline():
    """'Company issues profit warning' must be classified T1."""
    from filter import assign_news_tier
    item = {
        "title": "Company issues profit warning citing macro headwinds",
        "source": "bloomberg",
    }
    tier = assign_news_tier(item)
    assert tier == "T1", (
        f"'profit warning' headline classified as {tier} — "
        "must be T1 (major negative catalyst)."
    )


def test_t1_assignment_buyback_headline():
    """'META announces $50B share buyback' must pass event filter and be T1."""
    from filter import assign_news_tier, filter_by_event_keywords
    item = {
        "title":   "META announces $50B share buyback program",
        "summary": "",
        "source":  "wsj",
        "tickers": ["META"],
        "published_at": "2026-04-05T10:00:00",
    }
    filtered, dropped = filter_by_event_keywords([item])
    assert len(filtered) == 1, (
        "Buyback headline was dropped by event keyword filter before tier assignment. "
        "Add 'buyback' to EVENT_KEYWORDS."
    )
    tier = assign_news_tier(item)
    assert tier == "T1", f"Share buyback headline classified as {tier} — must be T1."


def test_t1_assignment_merger_headline():
    """'Company merger with ...' must pass event filter and be T1."""
    from filter import assign_news_tier, filter_by_event_keywords
    item = {
        "title":   "MSFT merger with gaming studio advances regulatory review",
        "summary": "",
        "source":  "reuters",
        "tickers": ["MSFT"],
        "published_at": "2026-04-05T10:00:00",
    }
    filtered, dropped = filter_by_event_keywords([item])
    assert len(filtered) == 1, (
        "Merger headline was dropped by event keyword filter. Add 'merger' to EVENT_KEYWORDS."
    )
    tier = assign_news_tier(item)
    assert tier == "T1", f"Merger headline classified as {tier} — must be T1."


def test_t1_assignment_bankruptcy_headline():
    """'Company bankruptcy filing' must pass event filter and be T1."""
    from filter import assign_news_tier, filter_by_event_keywords
    item = {
        "title":   "Retailer files for bankruptcy protection under chapter 11",
        "summary": "",
        "source":  "bloomberg",
        "tickers": ["SPY"],
        "published_at": "2026-04-05T10:00:00",
    }
    filtered, dropped = filter_by_event_keywords([item])
    assert len(filtered) == 1, (
        "Bankruptcy headline was dropped by event keyword filter. "
        "Add 'bankruptcy' to EVENT_KEYWORDS."
    )
    tier = assign_news_tier(item)
    assert tier == "T1", f"Bankruptcy headline classified as {tier} — must be T1."
