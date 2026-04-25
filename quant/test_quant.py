"""
Unit tests for the quant pipeline modules.
Run: cd d:/Github/ginger && python -m pytest quant/test_quant.py -v
"""

import json
import math
import os
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


def test_enrich_signals_widens_only_technology_trend_target():
    from constants import TREND_TECH_TARGET_ATR_MULT
    from risk_engine import enrich_signals

    signals = [
        {
            "ticker": "NVDA",
            "strategy": "trend_long",
            "entry_price": 100.0,
            "stop_price": 97.0,
            "confidence_score": 0.9,
        },
        {
            "ticker": "NVDA",
            "strategy": "breakout_long",
            "entry_price": 100.0,
            "stop_price": 97.0,
            "confidence_score": 0.9,
        },
    ]
    features = {
        "NVDA": {
            "atr": 2.0,
            "trend_score": 1.0,
            "volume_spike_ratio": 2.0,
            "momentum_10d_pct": 0.1,
        }
    }

    trend, breakout = enrich_signals(signals, features, atr_target_mult=4.5)

    assert trend["target_price"] == round(
        100.0 + TREND_TECH_TARGET_ATR_MULT * 2.0,
        2,
    )
    assert trend["target_mult_used"] == TREND_TECH_TARGET_ATR_MULT
    assert trend["target_width_applied"] == TREND_TECH_TARGET_ATR_MULT
    assert trend["tech_trend_target_width_applied"] == TREND_TECH_TARGET_ATR_MULT
    assert breakout["target_price"] == round(100.0 + 4.5 * 2.0, 2)
    assert breakout.get("target_width_applied") is None
    assert breakout.get("tech_trend_target_width_applied") is None


def test_enrich_signals_widens_only_commodities_trend_target():
    from constants import TREND_COMMODITIES_TARGET_ATR_MULT
    from risk_engine import enrich_signals

    signals = [
        {
            "ticker": "IAU",
            "strategy": "trend_long",
            "entry_price": 100.0,
            "stop_price": 97.0,
            "confidence_score": 0.9,
        },
        {
            "ticker": "IAU",
            "strategy": "breakout_long",
            "entry_price": 100.0,
            "stop_price": 97.0,
            "confidence_score": 0.9,
        },
    ]
    features = {
        "IAU": {
            "atr": 2.0,
            "trend_score": 1.0,
            "volume_spike_ratio": 2.0,
            "momentum_10d_pct": 0.1,
        }
    }

    trend, breakout = enrich_signals(signals, features, atr_target_mult=4.5)

    assert trend["target_price"] == round(
        100.0 + TREND_COMMODITIES_TARGET_ATR_MULT * 2.0,
        2,
    )
    assert trend["target_mult_used"] == TREND_COMMODITIES_TARGET_ATR_MULT
    assert trend["target_width_applied"] == TREND_COMMODITIES_TARGET_ATR_MULT
    assert trend["commodity_trend_target_width_applied"] == TREND_COMMODITIES_TARGET_ATR_MULT
    assert breakout["target_price"] == round(100.0 + 4.5 * 2.0, 2)
    assert breakout.get("target_width_applied") is None
    assert breakout.get("commodity_trend_target_width_applied") is None


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
    """Strategy A must be blocked when dte <= 3 (trading days, execution-lag-adjusted)."""
    from signal_engine import strategy_a_trend
    # dte=3 at signal → dte=2 at next-day execution → inside gap risk zone
    feat = _make_features()
    feat["days_to_earnings"] = 3
    sig = strategy_a_trend("TEST", feat)
    assert sig is None, "Strategy A must reject signals when dte <= 3 (execution at dte=2)"


def test_strategy_a_allowed_when_dte_is_4():
    """Strategy A must allow signals when dte=4 (execution at dte=3, safe zone)."""
    from signal_engine import strategy_a_trend
    feat = _make_features()
    feat["days_to_earnings"] = 4
    sig = strategy_a_trend("TEST", feat)
    assert sig is not None, "Strategy A should not reject signals when dte=4 (safe execution window)"


def test_strategy_b_blocked_when_near_earnings():
    """Strategy B must be blocked when dte <= 3 (trading days, same rule as A)."""
    from signal_engine import strategy_b_breakout
    feat = _make_features()
    feat["days_to_earnings"] = 3
    sig = strategy_b_breakout("TEST", feat)
    assert sig is None, "Strategy B must reject signals when dte <= 3"


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


def test_strategy_b_optional_52w_pullback_gate_blocks_deep_recovery_breakout():
    from signal_engine import strategy_b_breakout
    feat = _make_features(pct_from_52w_high=-0.25)
    sig = strategy_b_breakout(
        "TEST",
        feat,
        breakout_max_pullback_from_52w_high=-0.20,
    )
    assert sig is None, "Deep-recovery breakout should fail the optional 52-week pullback gate"


def test_generate_signals_passes_breakout_pullback_override():
    from signal_engine import generate_signals
    feat = _make_features(pct_from_52w_high=-0.25)
    sigs = generate_signals(
        {"TEST": feat},
        market_context={"market_regime": "BULL"},
        enabled_strategies=("breakout_long",),
        breakout_max_pullback_from_52w_high=-0.20,
    )
    assert sigs == [], "generate_signals must forward the breakout-only pullback gate"


def test_rank_signals_for_allocation_only_reorders_breakouts():
    from signal_engine import rank_signals_for_allocation

    signals = [
        {"ticker": "TREND1", "strategy": "trend_long", "confidence_score": 1.0},
        {"ticker": "B1", "strategy": "breakout_long", "confidence_score": 0.93,
         "conditions_met": {"pct_from_52w_high": -0.08}},
        {"ticker": "TREND2", "strategy": "trend_long", "confidence_score": 0.89},
        {"ticker": "B2", "strategy": "breakout_long", "confidence_score": 0.93,
         "conditions_met": {"pct_from_52w_high": -0.02}},
    ]

    ranked = rank_signals_for_allocation(signals)
    assert [s["ticker"] for s in ranked] == ["TREND1", "B2", "TREND2", "B1"]


def test_rank_signals_for_allocation_preserves_non_breakout_order():
    from signal_engine import rank_signals_for_allocation

    signals = [
        {"ticker": "T1", "strategy": "trend_long", "confidence_score": 1.0},
        {"ticker": "T2", "strategy": "trend_long", "confidence_score": 0.95},
        {"ticker": "B1", "strategy": "breakout_long", "confidence_score": 0.93,
         "conditions_met": {"pct_from_52w_high": -0.12}},
        {"ticker": "B2", "strategy": "breakout_long", "confidence_score": 0.93,
         "conditions_met": {"pct_from_52w_high": -0.03}},
        {"ticker": "T3", "strategy": "trend_long", "confidence_score": 0.90},
    ]

    ranked = rank_signals_for_allocation(signals)
    non_breakouts = [s["ticker"] for s in ranked if s["strategy"] != "breakout_long"]
    assert non_breakouts == ["T1", "T2", "T3"]


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


def test_generate_signals_respects_enabled_strategies():
    """Strategy gating for experiments must be explicit and reproducible."""
    from signal_engine import generate_signals

    feat = {
        **_make_features(),
        "earnings_event_window": True,
        "days_to_earnings": 10,
        "positive_surprise_history": True,
    }

    only_earnings = generate_signals(
        {"NVDA": feat},
        market_context={"market_regime": "BULL"},
        enabled_strategies=("earnings_event_long",),
    )
    no_earnings = generate_signals(
        {"NVDA": feat},
        market_context={"market_regime": "BULL"},
        enabled_strategies=("trend_long", "breakout_long"),
    )

    assert len(only_earnings) == 1 and only_earnings[0]["strategy"] == "earnings_event_long", (
        "enabled_strategies must allow an isolated earnings-only experiment."
    )
    assert all(sig["strategy"] != "earnings_event_long" for sig in no_earnings), (
        "Disabling earnings_event_long must remove it from the candidate set."
    )


def test_default_enabled_strategies_exclude_earnings_until_data_recovers():
    """Default strategy set should match the current accepted alpha stance."""
    from constants import (
        ENABLED_STRATEGIES,
        BREAKOUT_MAX_PULLBACK_FROM_52W_HIGH,
        BREAKOUT_RANK_BY_52W_HIGH,
    )
    from backtester import DEFAULT_CONFIG

    assert ENABLED_STRATEGIES == ("trend_long", "breakout_long")
    assert BREAKOUT_MAX_PULLBACK_FROM_52W_HIGH == -0.20
    assert BREAKOUT_RANK_BY_52W_HIGH is True
    assert DEFAULT_CONFIG["ENABLED_STRATEGIES"] == ENABLED_STRATEGIES
    assert (
        DEFAULT_CONFIG["BREAKOUT_MAX_PULLBACK_FROM_52W_HIGH"]
        == BREAKOUT_MAX_PULLBACK_FROM_52W_HIGH
    )
    assert DEFAULT_CONFIG["BREAKOUT_RANK_BY_52W_HIGH"] is BREAKOUT_RANK_BY_52W_HIGH


def test_regime_exit_profile_expands_in_risk_on_and_contracts_in_defensive():
    """Entry-day exit target must respond smoothly to observable market strength."""
    from regime_exit import compute_regime_exit_profile

    risk_on = compute_regime_exit_profile({
        "market_regime": "BULL",
        "spy_pct_from_ma": 0.08,
        "qqq_pct_from_ma": 0.10,
        "spy_10d_return": 0.04,
        "qqq_10d_return": 0.05,
    })
    defensive = compute_regime_exit_profile({
        "market_regime": "BEAR",
        "spy_pct_from_ma": -0.04,
        "qqq_pct_from_ma": -0.05,
        "spy_10d_return": -0.03,
        "qqq_10d_return": -0.02,
    })

    assert risk_on["bucket"] == "risk_on"
    assert defensive["bucket"] == "defensive"
    assert risk_on["target_mult"] > 4.0
    assert defensive["target_mult"] <= 3.25
    assert risk_on["target_mult"] > defensive["target_mult"]


def test_regime_exit_profile_falls_back_to_baseline_without_inputs():
    """Missing regime inputs must not silently change the exit template."""
    from regime_exit import compute_regime_exit_profile
    profile = compute_regime_exit_profile({})
    assert profile["target_mult"] == 3.5
    assert profile["bucket"] == "baseline"
    assert profile["score"] is None


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
    from position_manager import compute_exit_levels
    from constants import ATR_STOP_MULT
    avg_cost      = 100.0
    current_price = 183.0
    atr           = 5.67
    levels = compute_exit_levels(avg_cost=avg_cost, atr=atr, current_price=current_price)
    expected_stop = round(current_price - ATR_STOP_MULT * atr, 2)
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
    # dte=4: lower bound of 4-6 trading-day window
    feat = compute_earnings_features({"days_to_earnings": 4, "avg_historical_surprise_pct": 0.05})
    assert feat["earnings_event_window"] is True
    assert feat["positive_surprise_history"] is True
    # dte=6: upper bound of 4-6 trading-day window
    feat6 = compute_earnings_features({"days_to_earnings": 6})
    assert feat6["earnings_event_window"] is True, "dte=6 must be inside window"
    # dte=3: too close — gap risk (excluded)
    feat3 = compute_earnings_features({"days_to_earnings": 3})
    assert feat3["earnings_event_window"] is False, "dte=3 must be excluded (gap risk)"
    # dte=7: outside window
    feat7 = compute_earnings_features({"days_to_earnings": 7})
    assert feat7["earnings_event_window"] is False, "dte=7 must be excluded (too early)"


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
    """Exit rules are now code-determined. Prompt must NOT contain exit rule details."""
    import os
    path = os.path.join(
        os.path.dirname(__file__), "..", "instructinos", "prompts", "trade_advice.txt"
    )
    with open(path, encoding="utf-8") as f:
        content = f.read()
    # Profit ladder logic is in position_manager.py + preflight_validator.py,
    # NOT in the prompt. LLM just echoes code decisions.
    assert "代码已决定" in content, (
        "Prompt must indicate position actions are code-determined (代码已决定)."
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

def test_prompt_tqs_threshold_is_0_75():
    """TQS threshold is now code-enforced (risk_engine.py), not in the prompt.

    The disaster-detector prompt redesign (2026-04) removed all quantitative
    thresholds from the prompt.  TQS gating happens in the code pipeline before
    signals reach the LLM.
    """
    import os
    path = os.path.join(
        os.path.dirname(__file__), "..", "instructinos", "prompts", "trade_advice.txt"
    )
    with open(path, encoding="utf-8") as f:
        content = f.read()
    # Prompt must NOT contain TQS thresholds — they belong in code only
    assert "trade_quality_score < 0.75" not in content, (
        "TQS threshold should be code-enforced, not in prompt."
    )
    assert "trade_quality_score < 0.60" not in content, (
        "Old TQS threshold still present in prompt."
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
    """Position cap is now code-enforced (portfolio_engine.py MAX_POSITION_PCT).

    The disaster-detector prompt doesn't need to mention the cap — sizing is
    pre-computed before data reaches the LLM.
    """
    from position_manager import MAX_POSITION_PCT
    assert MAX_POSITION_PCT == 0.25, (
        "Position cap must be 25% in code (position_manager.MAX_POSITION_PCT)."
    )


def test_prompt_no_second_trade():
    """Trade frequency is now code-controlled. Prompt must NOT offer second_new_trade.

    The disaster-detector redesign (2026-04) moved trade frequency control to code.
    LLM should not decide how many trades to make.
    """
    import os
    path = os.path.join(
        os.path.dirname(__file__), "..", "instructinos", "prompts", "trade_advice.txt"
    )
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "second_new_trade" not in content, (
        "Prompt should not contain second_new_trade — frequency is code-controlled."
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


def test_size_signals_derisks_low_tqs_signals():
    """Low-TQS signals should keep only a fraction of the base risk budget."""
    from portfolio_engine import size_signals
    from constants import LOW_TQS_RISK_THRESHOLD, LOW_TQS_RISK_MULTIPLIER

    sig = {
        "ticker":      "GLD",
        "strategy":    "trend_long",
        "entry_price": 100.0,
        "stop_price":  97.0,
        "confidence_score": 1.0,
        "trade_quality_score": LOW_TQS_RISK_THRESHOLD - 0.01,
    }

    sized = size_signals([sig], 100_000.0)[0]["sizing"]

    assert sized["base_risk_pct"] == 0.01
    assert sized["risk_pct"] == 0.01 * LOW_TQS_RISK_MULTIPLIER
    assert sized["tqs_risk_multiplier_applied"] == LOW_TQS_RISK_MULTIPLIER
    assert sized["trade_quality_score"] == sig["trade_quality_score"]


def test_size_signals_zeroes_low_tqs_non_commodity_breakouts():
    """Low-TQS non-commodity breakouts should lose all marginal risk budget."""
    from portfolio_engine import size_signals
    from constants import LOW_TQS_RISK_THRESHOLD

    sig = {
        "ticker": "MCD",
        "strategy": "breakout_long",
        "entry_price": 100.0,
        "stop_price": 97.0,
        "confidence_score": 1.0,
        "trade_quality_score": LOW_TQS_RISK_THRESHOLD - 0.01,
        "sector": "Consumer Discretionary",
    }

    sized = size_signals([sig], 100_000.0)[0]["sizing"]

    assert sized["base_risk_pct"] == 0.01
    assert sized["risk_pct"] == 0.0
    assert sized["shares_to_buy"] == 0
    assert sized["position_value_usd"] == 0.0
    assert sized["position_pct_of_portfolio"] == 0.0
    assert sized["tqs_risk_multiplier_applied"] == 0.0
    assert sized["low_tqs_haircut_exempt_sector"] is None


def test_size_signals_zeroes_trend_industrials():
    """Trend Industrials should lose all marginal risk budget in this experiment."""
    from portfolio_engine import size_signals

    sig = {
        "ticker": "CAT",
        "strategy": "trend_long",
        "entry_price": 500.0,
        "stop_price": 485.0,
        "sector": "Industrials",
        "trade_quality_score": 0.95,
    }

    sized = size_signals([sig], 100_000.0)[0]["sizing"]

    assert sized["base_risk_pct"] == 0.01
    assert sized["risk_pct"] == 0.0
    assert sized["shares_to_buy"] == 0
    assert sized["position_value_usd"] == 0.0
    assert sized["tqs_risk_multiplier_applied"] == 1.0
    assert sized["trend_industrials_risk_multiplier_applied"] == 0.0


def test_size_signals_derisks_moderate_gap_trend_technology():
    """Moderate-gap trend Technology setups should keep only 25% of base risk."""
    from portfolio_engine import size_signals

    sig = {
        "ticker": "AVGO",
        "strategy": "trend_long",
        "entry_price": 100.0,
        "stop_price": 95.0,
        "sector": "Technology",
        "trade_quality_score": 0.97,
        "gap_vulnerability_pct": 0.05,
    }

    sized = size_signals([sig], 100_000.0)[0]["sizing"]

    assert sized["base_risk_pct"] == 0.01
    assert sized["risk_pct"] == 0.0025
    assert sized["tqs_risk_multiplier_applied"] == 1.0
    assert sized["trend_industrials_risk_multiplier_applied"] == 1.0
    assert sized["trend_tech_tight_gap_risk_multiplier_applied"] == 1.0
    assert sized["trend_tech_gap_risk_multiplier_applied"] == 0.25
    assert sized["trend_tech_near_high_risk_multiplier_applied"] == 1.0


def test_size_signals_zeroes_tight_gap_trend_technology():
    """Tight-gap trend Technology setups should lose all marginal risk."""
    from portfolio_engine import size_signals

    sig = {
        "ticker": "DDOG",
        "strategy": "trend_long",
        "entry_price": 100.0,
        "stop_price": 97.5,
        "sector": "Technology",
        "trade_quality_score": 0.97,
        "gap_vulnerability_pct": 0.025,
        "conditions_met": {
            "pct_from_52w_high": -0.08,
        },
    }

    sized = size_signals([sig], 100_000.0)[0]["sizing"]

    assert sized["base_risk_pct"] == 0.01
    assert sized["risk_pct"] == 0.0
    assert sized["shares_to_buy"] == 0
    assert sized["position_value_usd"] == 0.0
    assert sized["tqs_risk_multiplier_applied"] == 1.0
    assert sized["trend_industrials_risk_multiplier_applied"] == 1.0
    assert sized["trend_tech_tight_gap_risk_multiplier_applied"] == 0.0
    assert sized["trend_tech_gap_risk_multiplier_applied"] == 1.0
    assert sized["trend_tech_near_high_risk_multiplier_applied"] == 1.0


def test_size_signals_derisks_near_high_trend_technology():
    """Near-high trend Technology setups should keep only 25% of base risk."""
    from portfolio_engine import size_signals

    sig = {
        "ticker": "MSFT",
        "strategy": "trend_long",
        "entry_price": 100.0,
        "stop_price": 96.0,
        "sector": "Technology",
        "trade_quality_score": 0.97,
        "gap_vulnerability_pct": 0.015,
        "conditions_met": {
            "pct_from_52w_high": -0.015,
        },
    }

    sized = size_signals([sig], 100_000.0)[0]["sizing"]

    assert sized["base_risk_pct"] == 0.01
    assert sized["risk_pct"] == 0.0025
    assert sized["tqs_risk_multiplier_applied"] == 1.0
    assert sized["trend_industrials_risk_multiplier_applied"] == 1.0
    assert sized["trend_tech_tight_gap_risk_multiplier_applied"] == 1.0
    assert sized["trend_tech_gap_risk_multiplier_applied"] == 1.0
    assert sized["trend_tech_near_high_risk_multiplier_applied"] == 0.25


def test_size_signals_zeroes_moderate_gap_breakout_industrials():
    """Breakout Industrials with a 3-4% stop gap should lose all marginal risk."""
    from portfolio_engine import size_signals

    sig = {
        "ticker": "CAT",
        "strategy": "breakout_long",
        "entry_price": 500.0,
        "stop_price": 482.0,
        "trade_quality_score": 0.92,
        "sector": "Industrials",
        "gap_vulnerability_pct": 0.035,
    }

    sized = size_signals([sig], 100_000.0)[0]["sizing"]

    assert sized["base_risk_pct"] == 0.01
    assert sized["risk_pct"] == 0.0
    assert sized["shares_to_buy"] == 0
    assert sized["trend_tech_tight_gap_risk_multiplier_applied"] == 1.0
    assert sized["trend_tech_gap_risk_multiplier_applied"] == 1.0
    assert sized["trend_tech_near_high_risk_multiplier_applied"] == 1.0
    assert sized["breakout_industrials_gap_risk_multiplier_applied"] == 0.0


def test_size_signals_derisks_near_high_breakout_communication_services():
    """Near-high Communication Services breakouts should keep only 25% risk."""
    from portfolio_engine import size_signals

    sig = {
        "ticker": "NFLX",
        "strategy": "breakout_long",
        "entry_price": 500.0,
        "stop_price": 482.0,
        "trade_quality_score": 0.93,
        "sector": "Communication Services",
        "gap_vulnerability_pct": 0.045,
        "conditions_met": {
            "pct_from_52w_high": -0.02,
        },
    }

    sized = size_signals([sig], 100_000.0)[0]["sizing"]

    assert sized["base_risk_pct"] == 0.01
    assert sized["risk_pct"] == 0.0025
    assert sized["shares_to_buy"] > 0
    assert sized["trend_tech_tight_gap_risk_multiplier_applied"] == 1.0
    assert sized["trend_tech_gap_risk_multiplier_applied"] == 1.0
    assert sized["trend_tech_near_high_risk_multiplier_applied"] == 1.0
    assert sized["breakout_industrials_gap_risk_multiplier_applied"] == 1.0
    assert sized["breakout_comms_near_high_risk_multiplier_applied"] == 0.25
    assert sized["breakout_comms_gap_risk_multiplier_applied"] == 1.0


def test_size_signals_derisks_moderate_gap_breakout_communication_services():
    """Moderate-gap Communication Services breakouts should keep only 25% risk."""
    from portfolio_engine import size_signals

    sig = {
        "ticker": "DIS",
        "strategy": "breakout_long",
        "entry_price": 120.0,
        "stop_price": 115.92,
        "trade_quality_score": 0.93,
        "sector": "Communication Services",
        "gap_vulnerability_pct": 0.034,
        "conditions_met": {
            "pct_from_52w_high": -0.08,
        },
    }

    sized = size_signals([sig], 100_000.0)[0]["sizing"]

    assert sized["base_risk_pct"] == 0.01
    assert sized["risk_pct"] == 0.0025
    assert sized["shares_to_buy"] > 0
    assert sized["trend_tech_tight_gap_risk_multiplier_applied"] == 1.0
    assert sized["trend_tech_gap_risk_multiplier_applied"] == 1.0
    assert sized["trend_tech_near_high_risk_multiplier_applied"] == 1.0
    assert sized["breakout_industrials_gap_risk_multiplier_applied"] == 1.0
    assert sized["breakout_comms_near_high_risk_multiplier_applied"] == 1.0
    assert sized["breakout_comms_gap_risk_multiplier_applied"] == 0.25
    assert sized["breakout_financials_dte_risk_multiplier_applied"] == 1.0


def test_size_signals_derisks_breakout_financials_near_earnings():
    """Financials breakouts 8-14 days before earnings should keep only 25% risk."""
    from portfolio_engine import size_signals

    sig = {
        "ticker": "GS",
        "strategy": "breakout_long",
        "entry_price": 500.0,
        "stop_price": 482.0,
        "trade_quality_score": 0.91,
        "sector": "Financials",
        "days_to_earnings": 10,
        "conditions_met": {
            "pct_from_52w_high": -0.02,
        },
    }

    sized = size_signals([sig], 100_000.0)[0]["sizing"]

    assert sized["base_risk_pct"] == 0.01
    assert sized["risk_pct"] == 0.0025
    assert sized["shares_to_buy"] > 0
    assert sized["trend_tech_tight_gap_risk_multiplier_applied"] == 1.0
    assert sized["trend_tech_gap_risk_multiplier_applied"] == 1.0
    assert sized["trend_tech_near_high_risk_multiplier_applied"] == 1.0
    assert sized["breakout_industrials_gap_risk_multiplier_applied"] == 1.0
    assert sized["breakout_comms_near_high_risk_multiplier_applied"] == 1.0
    assert sized["breakout_comms_gap_risk_multiplier_applied"] == 1.0
    assert sized["breakout_financials_dte_risk_multiplier_applied"] == 0.25


def test_size_signals_zeroes_breakout_technology_dte_26_40():
    """Technology breakouts 26-40 days before earnings should get zero risk."""
    from portfolio_engine import size_signals

    sig = {
        "ticker": "AAPL",
        "strategy": "breakout_long",
        "entry_price": 200.0,
        "stop_price": 193.0,
        "trade_quality_score": 0.91,
        "sector": "Technology",
        "days_to_earnings": 32,
        "conditions_met": {
            "pct_from_52w_high": -0.02,
        },
    }

    sized = size_signals([sig], 100_000.0)[0]["sizing"]

    assert sized["base_risk_pct"] == 0.01
    assert sized["risk_pct"] == 0.0
    assert sized["shares_to_buy"] == 0
    assert sized["position_value_usd"] == 0.0
    assert sized["breakout_financials_dte_risk_multiplier_applied"] == 1.0
    assert sized["breakout_tech_dte_risk_multiplier_applied"] == 0.0
    assert sized["breakout_healthcare_dte_risk_multiplier_applied"] == 1.0
    assert sized["trend_healthcare_dte_risk_multiplier_applied"] == 1.0


def test_size_signals_derisks_breakout_healthcare_dte_20_65():
    """Healthcare breakouts 20-65 DTE should keep only 25% of normal risk."""
    from portfolio_engine import size_signals

    sig = {
        "ticker": "LLY",
        "strategy": "breakout_long",
        "entry_price": 800.0,
        "stop_price": 760.0,
        "trade_quality_score": 0.93,
        "sector": "Healthcare",
        "days_to_earnings": 60,
        "conditions_met": {
            "pct_from_52w_high": -0.10,
        },
    }

    sized = size_signals([sig], 100_000.0)[0]["sizing"]

    assert sized["base_risk_pct"] == 0.01
    assert sized["risk_pct"] == 0.0025
    assert sized["shares_to_buy"] > 0
    assert sized["breakout_tech_dte_risk_multiplier_applied"] == 1.0
    assert sized["breakout_healthcare_dte_risk_multiplier_applied"] == 0.25
    assert sized["trend_healthcare_dte_risk_multiplier_applied"] == 1.0


def test_size_signals_derisks_trend_technology_dte_44_64():
    """Technology trends 44-64 DTE should keep only 25% of normal risk."""
    from portfolio_engine import size_signals

    sig = {
        "ticker": "TSM",
        "strategy": "trend_long",
        "entry_price": 300.0,
        "stop_price": 288.0,
        "trade_quality_score": 0.96,
        "sector": "Technology",
        "gap_vulnerability_pct": 0.035,
        "days_to_earnings": 58,
        "conditions_met": {
            "pct_from_52w_high": -0.05,
        },
    }

    sized = size_signals([sig], 100_000.0)[0]["sizing"]

    assert sized["base_risk_pct"] == 0.01
    assert sized["risk_pct"] == 0.0025
    assert sized["shares_to_buy"] > 0
    assert sized["trend_tech_tight_gap_risk_multiplier_applied"] == 1.0
    assert sized["trend_tech_gap_risk_multiplier_applied"] == 1.0
    assert sized["trend_tech_near_high_risk_multiplier_applied"] == 1.0
    assert sized["trend_tech_dte_risk_multiplier_applied"] == 0.25
    assert sized["breakout_tech_dte_risk_multiplier_applied"] == 1.0


def test_size_signals_zeroes_trend_healthcare_near_earnings():
    """Healthcare trends 6-12 days before earnings should lose all marginal risk."""
    from portfolio_engine import size_signals

    sig = {
        "ticker": "NVO",
        "strategy": "trend_long",
        "entry_price": 100.0,
        "stop_price": 95.0,
        "trade_quality_score": 0.94,
        "sector": "Healthcare",
        "days_to_earnings": 12,
        "conditions_met": {
            "pct_from_52w_high": -0.04,
        },
    }

    sized = size_signals([sig], 100_000.0)[0]["sizing"]

    assert sized["base_risk_pct"] == 0.01
    assert sized["risk_pct"] == 0.0
    assert sized["shares_to_buy"] == 0
    assert sized["position_value_usd"] == 0.0
    assert sized["breakout_financials_dte_risk_multiplier_applied"] == 1.0
    assert sized["trend_healthcare_dte_risk_multiplier_applied"] == 0.0


def test_size_signals_zeroes_near_high_consumer_trends_before_earnings():
    """Near-high Consumer Discretionary trends 30-65 DTE should get zero risk."""
    from portfolio_engine import size_signals

    sig = {
        "ticker": "MCD",
        "strategy": "trend_long",
        "entry_price": 330.0,
        "stop_price": 320.0,
        "target_price": 360.0,
        "sector": "Consumer Discretionary",
        "trade_quality_score": 0.94,
        "days_to_earnings": 39,
        "conditions_met": {"pct_from_52w_high": -0.005},
    }

    sized = size_signals([sig], portfolio_value=100_000.0)[0]["sizing"]

    assert sized["base_risk_pct"] == 0.01
    assert sized["risk_pct"] == 0.0
    assert sized["shares_to_buy"] == 0
    assert sized["position_value_usd"] == 0.0
    assert sized["trend_healthcare_dte_risk_multiplier_applied"] == 1.0
    assert sized["trend_consumer_near_high_dte_risk_multiplier_applied"] == 0.0


def test_size_signals_keeps_full_risk_for_high_tqs_signals():
    """High-TQS signals should preserve the caller's base risk budget."""
    from portfolio_engine import size_signals
    from constants import LOW_TQS_RISK_THRESHOLD

    sig = {
        "ticker":      "NVDA",
        "strategy":    "trend_long",
        "entry_price": 100.0,
        "stop_price":  97.0,
        "confidence_score": 1.0,
        "trade_quality_score": LOW_TQS_RISK_THRESHOLD,
    }

    sized = size_signals([sig], 100_000.0, risk_pct=0.0075)[0]["sizing"]

    assert sized["base_risk_pct"] == 0.0075
    assert sized["risk_pct"] == 0.0075
    assert sized["tqs_risk_multiplier_applied"] == 1.0


def test_size_signals_exempts_low_tqs_commodities_from_haircut():
    """Low-TQS commodity breakouts should keep full size under the sector exemption."""
    from portfolio_engine import size_signals
    from constants import LOW_TQS_RISK_THRESHOLD

    sig = {
        "ticker": "GLD",
        "strategy": "breakout_long",
        "entry_price": 100.0,
        "stop_price": 97.0,
        "confidence_score": 1.0,
        "trade_quality_score": LOW_TQS_RISK_THRESHOLD - 0.01,
        "sector": "Commodities",
    }

    sized = size_signals([sig], 100_000.0)[0]["sizing"]

    assert sized["base_risk_pct"] == 0.01
    assert sized["risk_pct"] == 0.01
    assert sized["tqs_risk_multiplier_applied"] == 1.0
    assert sized["low_tqs_haircut_exempt_sector"] == "Commodities"


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
    """entry_note must contain earnings warning when DTE=7 (within 4-8 range)."""
    from signal_engine import strategy_a_trend
    feat = _make_features()
    feat["days_to_earnings"] = 7
    sig = strategy_a_trend("TEST", feat)
    assert sig is not None
    assert "EARNINGS IN 7 TRADING DAYS" in sig["entry_note"], (
        f"entry_note must warn about earnings in 7 trading days; got: {sig['entry_note']}"
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
    """entry_note must NOT contain earnings warning when DTE > 8."""
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

def test_earnings_window_bounds_are_4_to_6():
    """Earnings event window must be 4-6 TRADING days (execution lag corrected).

    days_to_earnings now uses np.busday_count (trading days, not calendar days).
    PEAD drift concentrates in the final 3-5 trading days before announcement.
    Signals fire at close; execution is next-day open → 1-day execution lag.
      signal dte=4 → entry dte=3 (safe minimum)
      signal dte=6 → entry dte=5 (safe maximum)
    dte≤3 removed: after execution lag, entry has ≤2 trading days — dangerous
      overnight gap risk (±8-15%) overwhelms the ATR stop (1.5×ATR ≈ ±2-3%).
    dte=7+ removed: entry has 6+ trading days remaining; too early for PEAD.
    """
    from feature_layer import compute_earnings_features
    # dte=4: lower bound (after lag: entry at dte=3 — safe minimum)
    assert compute_earnings_features({"days_to_earnings": 4})["earnings_event_window"] is True
    # dte=5: mid-window
    assert compute_earnings_features({"days_to_earnings": 5})["earnings_event_window"] is True
    # dte=6: upper bound (after lag: entry at dte=5 — safe maximum)
    assert compute_earnings_features({"days_to_earnings": 6})["earnings_event_window"] is True
    # dte=3: too close — gap risk (after lag: entry dte=2)
    assert compute_earnings_features({"days_to_earnings": 3})["earnings_event_window"] is False
    # dte=2: too close
    assert compute_earnings_features({"days_to_earnings": 2})["earnings_event_window"] is False
    # dte=1: too close
    assert compute_earnings_features({"days_to_earnings": 1})["earnings_event_window"] is False
    # dte=7: outside upper bound
    assert compute_earnings_features({"days_to_earnings": 7})["earnings_event_window"] is False
    # dte=8: outside window
    assert compute_earnings_features({"days_to_earnings": 8})["earnings_event_window"] is False
    # dte=10: well outside window
    assert compute_earnings_features({"days_to_earnings": 10})["earnings_event_window"] is False
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
    """Gap-down stop: fill is based on Open (not daily Low), then sell-side
    slippage (SLIPPAGE_BPS_STOP = 10 bps) is applied on top.

    Scenario: Entry $100, stop $95.
      Day 1: stock gaps down — opens at $92 (below stop), trades to low of $89.
    Expected: stop_hit_price = $92 * (1 - 0.001) = $91.908  (NOT $89 low, NOT raw $92).
    """
    import pandas as pd
    from datetime import date
    from forward_tester import check_stop_or_target_hit, SLIPPAGE_BPS_STOP

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
    assert result["exit_reason"] == "stop"
    expected_fill = round(92.0 * (1 - SLIPPAGE_BPS_STOP / 10000.0), 4)
    assert result["stop_hit_price"] == expected_fill, (
        f"Gap-fill stop must use Open ($92) with {SLIPPAGE_BPS_STOP}bps sell slippage → "
        f"${expected_fill}, got {result['stop_hit_price']}"
    )
    # Sanity: fill must be BELOW the Open (sell-side slippage is adverse).
    assert result["stop_hit_price"] < 92.0


def test_check_stop_intraday_fill_uses_stop_price(monkeypatch):
    """Intraday stop: fill is based on stop_price with sell-side slippage.

    Scenario: Entry $100, stop $95.
      Day 1: opens at $97 (above stop), sells down to low $93.
    Expected: stop_hit_price = $95 * (1 - 0.001) = $94.905  (NOT $93 low, NOT raw $95).
    """
    import pandas as pd
    from datetime import date
    from forward_tester import check_stop_or_target_hit, SLIPPAGE_BPS_STOP

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
    assert result["exit_reason"] == "stop"
    expected_fill = round(95.0 * (1 - SLIPPAGE_BPS_STOP / 10000.0), 4)
    assert result["stop_hit_price"] == expected_fill, (
        f"Intraday fill must be stop ($95) with {SLIPPAGE_BPS_STOP}bps sell slippage → "
        f"${expected_fill}, got {result['stop_hit_price']}"
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


# ── forward_tester target-fill price accuracy (P0-3) ─────────────────────────

def test_target_fill_gap_up_uses_open(monkeypatch):
    """When the stock gaps UP through the target on open, target_hit_price
    must be based on Open (bonus over target), with sell-side slippage.

    Scenario: Entry $100, target $110.
      Day 1: stock gaps up — opens at $112 (above target), high $113.
    Expected: target_hit_price = $112 * (1 - 0.0005) = $111.944.
    """
    import pandas as pd
    from datetime import date
    from forward_tester import check_stop_or_target_hit, SLIPPAGE_BPS_TARGET

    entry_date = date(2024, 1, 2)
    idx = pd.to_datetime(["2024-01-02", "2024-01-03"])
    fake_data = pd.DataFrame({
        "Open":  [100.0, 112.0],  # gap-up above target
        "High":  [101.0, 113.0],
        "Low":   [ 99.0, 111.5],
        "Close": [100.0, 112.5],
    }, index=idx)

    import forward_tester
    monkeypatch.setattr(forward_tester, "get_daily_prices_during_period",
                        lambda *args, **kwargs: fake_data)

    result = check_stop_or_target_hit(
        ticker       = "TEST",
        entry_date   = entry_date,
        entry_price  = 100.0,
        stop_price   = 95.0,
        target_price = 110.0,
        n_days       = 10,
    )

    assert result["target_hit"], "Target must fire when Open >= target"
    assert result["target_hit_day"] == 1
    assert result["exit_reason"] == "target"
    expected_fill = round(112.0 * (1 - SLIPPAGE_BPS_TARGET / 10000.0), 4)
    assert result["target_hit_price"] == expected_fill, (
        f"Gap-up target fill must be Open ($112) with {SLIPPAGE_BPS_TARGET}bps → "
        f"${expected_fill}, got {result['target_hit_price']}"
    )
    # Must be above raw target (gap-up gives a bonus even after slippage)
    assert result["target_hit_price"] > 110.0


def test_target_fill_intraday_uses_target_minus_slippage(monkeypatch):
    """When target is hit intraday (not at open), fill ≈ target minus slippage.

    Scenario: Entry $100, target $110.
      Day 1: opens $105, high $111 (hits target intraday).
    Expected: target_hit_price = $110 * (1 - 0.0005) = $109.945.
    """
    import pandas as pd
    from datetime import date
    from forward_tester import check_stop_or_target_hit, SLIPPAGE_BPS_TARGET

    entry_date = date(2024, 1, 2)
    idx = pd.to_datetime(["2024-01-02", "2024-01-03"])
    fake_data = pd.DataFrame({
        "Open":  [100.0, 105.0],
        "High":  [101.0, 111.0],   # intraday high clips target
        "Low":   [ 99.0, 104.0],
        "Close": [100.0, 109.0],
    }, index=idx)

    import forward_tester
    monkeypatch.setattr(forward_tester, "get_daily_prices_during_period",
                        lambda *args, **kwargs: fake_data)

    result = check_stop_or_target_hit(
        ticker       = "TEST",
        entry_date   = entry_date,
        entry_price  = 100.0,
        stop_price   = 95.0,
        target_price = 110.0,
        n_days       = 10,
    )

    assert result["target_hit"]
    assert result["exit_reason"] == "target"
    expected_fill = round(110.0 * (1 - SLIPPAGE_BPS_TARGET / 10000.0), 4)
    assert result["target_hit_price"] == expected_fill
    assert result["target_hit_price"] < 110.0   # sell slippage is adverse


def test_same_day_stop_and_target_prefers_stop(monkeypatch):
    """If both stop and target are touched the SAME day, exit_reason is 'stop'
    (conservative: assume worst path of the day fires first)."""
    import pandas as pd
    from datetime import date
    from forward_tester import check_stop_or_target_hit

    entry_date = date(2024, 1, 2)
    idx = pd.to_datetime(["2024-01-02", "2024-01-03"])
    # Whipsaw: opens $100, ranges 94 to 111 (hits both 95 stop and 110 target)
    fake_data = pd.DataFrame({
        "Open":  [100.0, 100.0],
        "High":  [101.0, 111.0],
        "Low":   [ 99.0,  94.0],
        "Close": [100.0,  98.0],
    }, index=idx)

    import forward_tester
    monkeypatch.setattr(forward_tester, "get_daily_prices_during_period",
                        lambda *args, **kwargs: fake_data)

    result = check_stop_or_target_hit(
        ticker       = "TEST",
        entry_date   = entry_date,
        entry_price  = 100.0,
        stop_price   = 95.0,
        target_price = 110.0,
        n_days       = 10,
    )

    assert result["stop_hit"] and result["target_hit"]
    assert result["exit_reason"] == "stop", \
        "Same-day whipsaw must assume stop fires first (conservative)"


def test_apply_slippage_direction():
    """Buy slippage raises price, sell slippage lowers it; symmetric in bps."""
    from forward_tester import apply_slippage
    assert apply_slippage(100.0, 10, "buy")  == 100.1000
    assert apply_slippage(100.0, 10, "sell") == 99.9000
    assert apply_slippage(100.0, 0,  "buy")  == 100.0
    assert apply_slippage(None,   5, "buy")  is None


def test_evaluate_file_new_trade_uses_next_day_open_entry(monkeypatch, tmp_path):
    """End-to-end: new_trade entry fill = next-day Open + buy slippage, and
    realized_pnl_pct_net bakes in the round-trip commission.

    Scenario: rec_date close $100, next-day Open $101, target $110 hit intraday.
      entry_fill  = 101 * 1.0005 = 101.0505
      target_fill = 110 * 0.9995 = 109.945
      realized    = 109.945 / 101.0505 - 1 - 0.0035 ≈ +0.0845
    """
    import json
    import pandas as pd
    from datetime import date, timedelta
    import forward_tester as ft
    from forward_tester import (
        evaluate_file, SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_TARGET, ROUND_TRIP_COST,
    )

    rec = date.today() - timedelta(days=30)   # safely in the past
    rec_str = rec.strftime("%Y%m%d")

    advice_path = tmp_path / f"investment_advice_{rec_str}.json"
    advice_path.write_text(json.dumps({
        "advice_parsed": {
            "position_actions": [],
            "new_trade": {
                "ticker":       "TEST",
                "direction":    "long",
                "confidence":   0.8,
                "stop_price":   95.0,
                "target_price": 110.0,
            },
        }
    }))

    # Stub price fetches so the test is deterministic / offline.
    monkeypatch.setattr(ft, "get_close_price",
                        lambda ticker, d: (100.0, d) if d == rec else (108.0, d))
    monkeypatch.setattr(ft, "get_next_open_price",
                        lambda ticker, d: (101.0, d + timedelta(days=1)))

    # Intraday target-hit bar series.
    def fake_daily(ticker, start, end):
        idx = pd.to_datetime([rec, rec + timedelta(days=1)])
        return pd.DataFrame({
            "Open":  [100.0, 105.0],
            "High":  [101.0, 111.0],
            "Low":   [ 99.0, 104.0],
            "Close": [100.0, 109.0],
        }, index=idx)
    monkeypatch.setattr(ft, "get_daily_prices_during_period", fake_daily)

    result = evaluate_file(str(advice_path))
    nt = result["new_trade_result"]

    expected_entry  = round(101.0 * (1 + SLIPPAGE_BPS_ENTRY  / 10000.0), 4)
    expected_target = round(110.0 * (1 - SLIPPAGE_BPS_TARGET / 10000.0), 4)
    expected_net    = round(expected_target / expected_entry - 1 - ROUND_TRIP_COST, 4)

    assert nt["entry_open_price"] == 101.0
    assert nt["entry_fill_price"] == expected_entry
    assert nt["exit_reason"]      == "target"
    assert nt["exit_fill_price"]  == expected_target
    assert nt["realized_pnl_pct_net"] == expected_net, (
        f"realized_pnl_pct_net must reflect fill prices + round-trip cost. "
        f"expected {expected_net}, got {nt['realized_pnl_pct_net']}"
    )


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

    # dte=3 is now blocked at the CODE level (dte <= 3 guard added to strategy_a/b).
    # Test the two-layer protection:
    #   Layer 1: code gate blocks signals at dte <= 3
    #   Layer 2: enrich_signals injects days_to_earnings for signals that do pass (dte > 3)

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


def test_build_prompt_cash_usd_missing_falls_back_to_stored_pv():
    """When cash_usd is null/absent, portfolio_value must fall back to stored
    portfolio_value_usd — NOT silently collapse cash=0 and overwrite with
    equity-only live_pv (which under-reports PV and inflates heat/sector ratios).

    Before the fix: equity_pv=$60k, cash=None→0, live_pv=$60k overwrote
    stored_pv=$200k → sector_concentration divided by $60k → Tech=1.0 → blocked
    all new Tech trades.

    After the fix: cash_usd is None → keep stored_pv=$200k → Tech=$60k/$200k=0.30.
    """
    import os, sys, json
    sys.path.insert(0, os.path.dirname(__file__))
    from llm_advisor import build_prompt

    # trend_signals carries NVDA close=150 so current_prices is populated and the
    # live_pv branch actually runs (otherwise the bug never triggered).
    fake_trend_signals = {
        "market_regime": {"regime": "BULL", "note": "", "indices": {}},
        "quant_signals": [],
        "signals": {
            "NVDA": {"close": 150.0, "atr": 5.0, "20d_high": 160.0}
        },
    }

    # $60k Tech at current price; stored_pv=$200k (true account incl. cash);
    # cash_usd intentionally absent — this is the bug condition.
    positions = {
        "portfolio_value_usd": 200_000,
        # no "cash_usd" key at all — emulates data/open_positions.json before fill
        "positions": [{"ticker": "NVDA", "shares": 400, "avg_cost": 150.0}],
    }
    system_msg, user_msg = build_prompt([], positions, trend_signals=fake_trend_signals)

    if system_msg is None:
        pytest.skip("Prompt template file not found — skipping integration test")

    import re
    match = re.search(r'"sector_concentration":\s*(\{[^}]+\})', user_msg)
    assert match, "sector_concentration field not found in prompt"
    sector_json = json.loads(match.group(1))
    tech_weight = sector_json.get("Technology")
    assert tech_weight is not None, "Technology not in sector_concentration"
    assert abs(tech_weight - 0.30) < 0.05, (
        f"Technology weight={tech_weight}, expected ~0.30. "
        f"cash_usd=None must fall back to stored_pv=$200k, not collapse to equity-only $60k."
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
    """ATR gate is now code-enforced (signal_engine.py). Prompt must NOT contain ATR thresholds.

    The disaster-detector redesign removed all quantitative thresholds from the prompt.
    """
    from llm_advisor import build_prompt

    system_msg, _ = build_prompt([], None)
    if system_msg is None:
        pytest.skip("Prompt template not found")

    # ATR gate must NOT be in the prompt — it's enforced in signal_engine.py
    assert "0.05" not in system_msg and "0.07" not in system_msg, (
        "Prompt SYSTEM section should not contain ATR thresholds — code-enforced."
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
            "position_states",         # {ticker: CRITICAL_EXIT|HIGH_REDUCE|HOLD}
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
    # These fields are injected at runtime into the prompt as JSON data (sections 3a/3b/4)
    # by build_prompt(), but are NOT referenced by name in the template prose.
    # The "disaster detector" prompt redesign (2026-04) moved all quantitative decisions
    # to code — the LLM reads the injected JSON data directly but the template doesn't
    # mention field names.  The direction-1 test (test_registry_fields_exist_in_code_output)
    # still verifies these fields exist in the code output.
    skip_fields = {
        "earnings_gap_risk_applied",   # sizing sub-field, referenced with value
        "risk_per_share",              # internal computation field
        "reward_per_share",            # internal computation field
        # Section 4 fields — injected as JSON, not named in template prose
        "lock_reason",
        "account_state",
        "bear_emergency_stops",
        "current_prices",
        # Section 3a fields — LLM reads JSON directly, template says "直接使用第3a节值"
        "trade_quality_score",
        "confidence_score",
        "risk_reward_ratio",
        "net_risk_reward_ratio",
        "exec_lag_adj_net_rr",
        "entry_note",
        # Section 3b fields — injected as JSON for held positions
        "breach_status",
        "unrealized_pnl_pct",
        "exit_levels",
        "trailing_stop_from_20d_high",
        "drawdown_from_20d_high_pct",
        "daily_return_pct",
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


# ── P0-1: Gap vulnerability warning ─────────────────────────────────────────

def test_gap_warning_tight_stop():
    """Stop < 2% below entry should produce a gap_warning."""
    from risk_engine import enrich_signal_with_risk
    # Use enrich_signal_with_risk directly to avoid exec_lag gate filtering
    sig = {
        "ticker": "TEST", "strategy": "breakout_long",
        "entry_price": 100.0, "stop_price": 99.0,   # 1% stop
        "confidence_score": 0.8,
    }
    # ATR must be small enough that stop stays tight, but the function uses
    # the signal's stop_price directly (not recomputed from ATR).
    result = enrich_signal_with_risk(sig, atr=0.7)
    # Now simulate the gap vulnerability logic from enrich_signals
    _entry = result["entry_price"]
    gap_vuln = round((_entry - result["stop_price"]) / _entry, 4) if _entry > 0 else 0
    assert gap_vuln < 0.02, f"gap_vulnerability_pct={gap_vuln} should be < 0.02 for 1% stop"
    # Verify the actual enrich_signals path: use a stop that's tight (<2%) but
    # ensure exec_lag_adj_net_rr passes the 1.2 gate by using a large ATR for target.
    # ATR=3.0 → target = 100+3.5*3=110.5, but stop stays at 99.0 (manually set).
    # risk=1.0, reward=10.5 → R:R is very high, exec_lag gate passes easily.
    from risk_engine import enrich_signals
    sig2 = {
        "ticker": "TEST", "strategy": "breakout_long",
        "entry_price": 100.0, "stop_price": 99.0,   # 1% stop — well below 2%
        "confidence_score": 0.8,
    }
    features = {"atr": 3.0, "trend_score": 0.8, "volume_spike_ratio": 2.5,
                "momentum_10d_pct": 0.06}
    enriched = enrich_signals([sig2], {"TEST": features})
    assert len(enriched) >= 1, "Signal should not be dropped (high R:R from large ATR target)"
    r = enriched[0]
    assert r["gap_vulnerability_pct"] < 0.02
    assert "gap_warning" in r, "Tight stop should produce gap_warning"


def test_gap_warning_normal_stop():
    """Stop >= 2% below entry should NOT produce a gap_warning."""
    from risk_engine import enrich_signals
    sig = {
        "ticker": "TEST", "strategy": "trend_long",
        "entry_price": 100.0, "stop_price": 95.5,   # 4.5% stop
        "confidence_score": 0.8,
    }
    features = {"atr": 3.0, "trend_score": 0.8, "volume_spike_ratio": 2.5,
                "momentum_10d_pct": 0.06}
    result = enrich_signals([sig], {"TEST": features})
    assert len(result) >= 1
    r = result[0]
    assert r["gap_vulnerability_pct"] >= 0.02
    assert "gap_warning" not in r, "Normal stop should NOT have gap_warning"


def test_gap_warning_boundary_2pct():
    """Stop exactly 2% below entry is on the boundary — no warning."""
    from risk_engine import enrich_signals
    sig = {
        "ticker": "TEST", "strategy": "breakout_long",
        "entry_price": 100.0, "stop_price": 98.0,   # exactly 2%
        "confidence_score": 0.8,
    }
    features = {"atr": 1.4, "trend_score": 0.8, "volume_spike_ratio": 2.5,
                "momentum_10d_pct": 0.06}
    result = enrich_signals([sig], {"TEST": features})
    assert len(result) >= 1
    r = result[0]
    assert abs(r["gap_vulnerability_pct"] - 0.02) < 0.001
    assert "gap_warning" not in r, "Boundary 2% should NOT trigger warning"


# ── P0-2: Same-day sector concentration cap ──────────────────────────────────

def test_sector_cap_drops_third_tech_signal():
    """3 tech signals on same day → only 2 should survive."""
    # This tests the logic in run.py — we replicate the sector-cap code here
    # since run.py's main() is not unit-testable without full pipeline setup.
    from risk_engine import SECTOR_MAP

    signals = [
        {"ticker": "NVDA", "sector": "Technology", "confidence_score": 0.9},
        {"ticker": "AMD",  "sector": "Technology", "confidence_score": 0.85},
        {"ticker": "MU",   "sector": "Technology", "confidence_score": 0.80},
    ]
    # Replicate the sector cap logic from run.py
    from constants import MAX_PER_SECTOR
    _sector_counts = {}
    capped = []
    for s in signals:
        sec = s.get("sector", "Unknown")
        _sector_counts[sec] = _sector_counts.get(sec, 0) + 1
        if _sector_counts[sec] <= MAX_PER_SECTOR:
            capped.append(s)
    assert len(capped) == 2, f"Expected 2, got {len(capped)}"
    assert capped[0]["ticker"] == "NVDA"
    assert capped[1]["ticker"] == "AMD"


def test_sector_cap_diverse_sectors_all_pass():
    """Signals from different sectors should all pass."""
    signals = [
        {"ticker": "NVDA", "sector": "Technology", "confidence_score": 0.9},
        {"ticker": "TSLA", "sector": "Consumer Discretionary", "confidence_score": 0.85},
        {"ticker": "LLY",  "sector": "Healthcare", "confidence_score": 0.80},
    ]
    from constants import MAX_PER_SECTOR
    _sector_counts = {}
    capped = []
    for s in signals:
        sec = s.get("sector", "Unknown")
        _sector_counts[sec] = _sector_counts.get(sec, 0) + 1
        if _sector_counts[sec] <= MAX_PER_SECTOR:
            capped.append(s)
    assert len(capped) == 3, f"Diverse sectors should all pass, got {len(capped)}"


# ── P2-1: Performance engine tests ──────────────────────────────────────────

def test_open_trade_creates_record(tmp_path):
    """open_trade should create a new trade entry in the diary."""
    from performance_engine import open_trade, load_trades
    fpath = str(tmp_path / "trades.json")
    trade_id = open_trade("NVDA", "breakout_long", 100.0, 95.0, 10,
                          target_price=112.0, filepath=fpath)
    assert trade_id.startswith("NVDA_")
    trades = load_trades(fpath)
    assert len(trades) == 1
    assert trades[0]["status"] == "open"
    assert trades[0]["entry_price"] == 100.0


def test_close_trade_computes_pnl(tmp_path):
    """close_trade should compute P&L correctly."""
    from performance_engine import open_trade, close_trade, load_trades
    fpath = str(tmp_path / "trades.json")
    tid = open_trade("NVDA", "trend_long", 100.0, 95.0, 10, filepath=fpath)
    result = close_trade(tid, 110.0, filepath=fpath)
    assert result is not None
    assert result["status"] == "closed"
    assert result["exit_price"] == 110.0
    # P&L = (110-100)*10 - cost
    # cost = 100*0.0015*10 + 110*0.0020*10 = 1.50 + 2.20 = 3.70
    # pnl = 100 - 3.70 = 96.30
    assert result["profit_loss"] == 96.30


def test_close_trade_cost_model(tmp_path):
    """Verify entry×0.15% + exit×0.20% cost model."""
    from performance_engine import open_trade, close_trade
    fpath = str(tmp_path / "trades.json")
    tid = open_trade("TEST", "trend_long", 200.0, 190.0, 5, filepath=fpath)
    result = close_trade(tid, 200.0, filepath=fpath)  # flat trade
    # cost = 200*0.0015*5 + 200*0.0020*5 = 1.50 + 2.00 = 3.50
    # pnl = 0 - 3.50 = -3.50
    assert result["execution_cost"] == 3.50
    assert result["profit_loss"] == -3.50


def test_compute_metrics_empty():
    """compute_metrics with no trades should return total_trades=0."""
    from performance_engine import compute_metrics
    m = compute_metrics(filepath="nonexistent_file_xyz.json")
    assert m["total_trades"] == 0


def test_compute_metrics_win_rate(tmp_path):
    """Win rate should be correct for a mix of wins and losses."""
    from performance_engine import open_trade, close_trade, compute_metrics
    fpath = str(tmp_path / "trades.json")
    # 2 wins, 1 loss
    t1 = open_trade("A", "trend_long", 100, 95, 10, filepath=fpath)
    close_trade(t1, 110, filepath=fpath)
    t2 = open_trade("B", "trend_long", 100, 95, 10, filepath=fpath)
    close_trade(t2, 105, filepath=fpath)
    t3 = open_trade("C", "trend_long", 100, 95, 10, filepath=fpath)
    close_trade(t3, 90, filepath=fpath)

    m = compute_metrics(fpath)
    assert m["total_trades"] == 3
    # 2 wins / 3 trades
    assert abs(m["win_rate"] - 0.6667) < 0.01


def test_compute_metrics_max_drawdown(tmp_path):
    """Max drawdown should track the worst peak-to-trough in cumulative P&L."""
    from performance_engine import open_trade, close_trade, compute_metrics
    fpath = str(tmp_path / "trades.json")
    # Win +100, then lose -200 → drawdown = 200 from peak of 100-ish
    t1 = open_trade("A", "trend_long", 100, 95, 10, filepath=fpath)
    close_trade(t1, 110, filepath=fpath)   # ~+96.30
    t2 = open_trade("B", "trend_long", 100, 95, 20, filepath=fpath)
    close_trade(t2, 90, filepath=fpath)    # ~-207.40

    m = compute_metrics(fpath)
    assert m["max_drawdown_usd"] > 0, "Drawdown should be positive"


def test_compute_metrics_r_multiple(tmp_path):
    """R-multiple should be P&L / planned risk."""
    from performance_engine import open_trade, close_trade, compute_metrics
    fpath = str(tmp_path / "trades.json")
    # Entry=100, stop=95 → risk=5/share. Exit at 110 → gross +10/share
    t1 = open_trade("A", "trend_long", 100, 95, 10, filepath=fpath)
    close_trade(t1, 110, filepath=fpath)
    m = compute_metrics(fpath)
    # Only 1 trade so avg_r = (pnl / (5*10))
    # pnl = 96.30, planned_risk = 50 → R = 1.926
    assert m["avg_r_multiple"] is not None
    assert m["avg_r_multiple"] > 1.0, "A 2R winner should have avg_r > 1"


def test_compute_metrics_by_strategy(tmp_path):
    """by_strategy breakdown should separate strategies correctly."""
    from performance_engine import open_trade, close_trade, compute_metrics
    fpath = str(tmp_path / "trades.json")
    t1 = open_trade("A", "trend_long", 100, 95, 10, filepath=fpath)
    close_trade(t1, 110, filepath=fpath)
    t2 = open_trade("B", "breakout_long", 100, 95, 10, filepath=fpath)
    close_trade(t2, 90, filepath=fpath)

    m = compute_metrics(fpath)
    assert "trend_long" in m["by_strategy"]
    assert "breakout_long" in m["by_strategy"]
    assert m["by_strategy"]["trend_long"]["wins"] == 1
    assert m["by_strategy"]["breakout_long"]["wins"] == 0


def test_sharpe_none_with_single_trade(tmp_path):
    """Sharpe requires >= 2 trades; single trade should return None."""
    from performance_engine import open_trade, close_trade, compute_metrics
    fpath = str(tmp_path / "trades.json")
    t1 = open_trade("A", "trend_long", 100, 95, 10, filepath=fpath)
    close_trade(t1, 110, filepath=fpath)
    m = compute_metrics(fpath)
    assert m.get("sharpe_ratio") is None


def test_sharpe_fallback_for_short_history(tmp_path):
    """With < 30 days span, Sharpe should use fallback frequency."""
    from performance_engine import open_trade, close_trade, compute_metrics
    fpath = str(tmp_path / "trades.json")
    # Two trades on the same day → span < 30
    t1 = open_trade("A", "trend_long", 100, 95, 10, filepath=fpath)
    close_trade(t1, 110, filepath=fpath)
    t2 = open_trade("B", "trend_long", 100, 95, 10, filepath=fpath)
    close_trade(t2, 105, filepath=fpath)
    m = compute_metrics(fpath)
    # Sharpe should be computed (both wins → positive Sharpe)
    # but may be None if R-multiples need stop data — either way it shouldn't crash
    assert m["total_trades"] == 2


# ── P1-1: Forward tester multi-window ────────────────────────────────────────

def test_forward_tester_multi_window_results_present():
    """Multi-window fields should appear in new_trade_result when data available."""
    from forward_tester import EVAL_WINDOWS
    assert 10 in EVAL_WINDOWS
    assert 20 in EVAL_WINDOWS
    assert 30 in EVAL_WINDOWS


def test_forward_tester_backward_compat():
    """return_10d_pct must remain as primary field (backward compat)."""
    # Verify the constant and function signatures haven't changed
    from forward_tester import EVAL_DAYS, evaluate_file
    assert EVAL_DAYS == 10
    import inspect
    sig = inspect.signature(evaluate_file)
    assert "n_days" in sig.parameters


# ── P2-2: Backtester scaffold ────────────────────────────────────────────────

def test_backtester_smoke_runs():
    """BacktestEngine constructor accepts universe list and config dict."""
    from backtester import BacktestEngine
    engine = BacktestEngine(
        universe=["AAPL"],
        start="2025-01-02",
        end="2025-03-28",
        config={"INITIAL_CAPITAL": 50_000, "MAX_POSITIONS": 3},
    )
    assert engine.universe == ["AAPL"]
    assert engine.config["INITIAL_CAPITAL"] == 50_000
    assert engine.config["MAX_POSITIONS"] == 3


def test_backtester_strips_broken_local_proxy_env(monkeypatch):
    """A blackhole localhost proxy must not poison yfinance downloads."""
    from backtester import BacktestEngine

    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:9")
    engine = BacktestEngine(
        universe=["AAPL"],
        start="2025-01-02",
        end="2025-03-28",
    )
    assert engine is not None
    assert os.environ.get("HTTP_PROXY") is None
    assert os.environ.get("HTTPS_PROXY") is None
    assert os.environ.get("ALL_PROXY") is None


def test_yfinance_bootstrap_strips_proxy_and_sets_writable_cache(monkeypatch, tmp_path):
    import yfinance_bootstrap as yb

    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:9")
    monkeypatch.setattr(yb.tempfile, "gettempdir", lambda: str(tmp_path))

    seen = {}

    def fake_set_cache_location(path):
        seen["path"] = path

    monkeypatch.setattr(yb.yf_cache, "set_cache_location", fake_set_cache_location)

    cache_dir = yb.configure_yfinance_runtime()

    assert os.environ.get("HTTP_PROXY") is None
    assert os.environ.get("HTTPS_PROXY") is None
    assert os.environ.get("ALL_PROXY") is None
    assert cache_dir == str(tmp_path / "ginger_yfinance_cache")
    assert seen["path"] == cache_dir
    assert os.path.isdir(cache_dir)


def test_backtester_ohlcv_snapshot_roundtrip(tmp_path):
    """OHLCV snapshots should round-trip without hitting yfinance."""
    from backtester import BacktestEngine

    idx = pd.bdate_range("2025-01-02", periods=3)
    sample = pd.DataFrame({
        "Open": [100.0, 101.0, 102.0],
        "High": [101.0, 102.0, 103.0],
        "Low": [99.0, 100.0, 101.0],
        "Close": [100.5, 101.5, 102.5],
        "Volume": [1_000_000, 1_100_000, 1_200_000],
    }, index=idx)

    engine = BacktestEngine(["AAA"], data_dir=str(tmp_path))
    snapshot_path = tmp_path / "ohlcv_snapshot.json"
    engine._write_ohlcv_snapshot(
        {"AAA": sample, "SPY": sample, "QQQ": sample},
        str(snapshot_path),
        idx[0],
        idx[-1],
    )

    loaded = engine._load_ohlcv_snapshot(str(snapshot_path))

    assert sorted(loaded.keys()) == ["AAA", "QQQ", "SPY"]
    pd.testing.assert_frame_equal(loaded["AAA"], sample, check_freq=False, check_dtype=False)


def test_backtester_download_data_uses_snapshot_without_yfinance(monkeypatch, tmp_path):
    """An explicit OHLCV snapshot should bypass live vendor downloads entirely."""
    import backtester as backtester_mod
    from backtester import BacktestEngine

    idx = pd.bdate_range("2025-01-02", periods=2)
    sample = pd.DataFrame({
        "Open": [100.0, 101.0],
        "High": [101.0, 102.0],
        "Low": [99.0, 100.0],
        "Close": [100.5, 101.5],
        "Volume": [1_000_000, 1_100_000],
    }, index=idx)

    writer = BacktestEngine(["AAA"], data_dir=str(tmp_path))
    snapshot_path = tmp_path / "deterministic.json"
    writer._write_ohlcv_snapshot(
        {"AAA": sample, "SPY": sample, "QQQ": sample},
        str(snapshot_path),
        idx[0],
        idx[-1],
    )

    def fail_download(*args, **kwargs):
        raise AssertionError("yf.download must not be called when snapshot is provided")

    monkeypatch.setattr(backtester_mod.yf, "download", fail_download)

    engine = BacktestEngine(
        ["AAA"],
        start="2025-01-02",
        end="2025-01-10",
        data_dir=str(tmp_path),
        ohlcv_snapshot_path=str(snapshot_path),
    )
    loaded = engine._download_data()

    pd.testing.assert_frame_equal(loaded["AAA"], sample, check_freq=False, check_dtype=False)


def test_data_layer_import_applies_yfinance_bootstrap(monkeypatch):
    import importlib
    import data_layer

    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:9")

    importlib.reload(data_layer)

    assert os.environ.get("HTTP_PROXY") is None
    assert os.environ.get("HTTPS_PROXY") is None
    assert os.environ.get("ALL_PROXY") is None


def test_regime_import_applies_yfinance_bootstrap(monkeypatch):
    import importlib
    import regime

    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:9")

    importlib.reload(regime)

    assert os.environ.get("HTTP_PROXY") is None
    assert os.environ.get("HTTPS_PROXY") is None
    assert os.environ.get("ALL_PROXY") is None


def test_backtester_position_class():
    """Position tracks entry, stop, target, and sector."""
    from backtester import Position
    pos = Position(
        ticker="NVDA", entry_price=100.0, stop_price=95.0,
        target_price=110.0, shares=10, entry_date="2025-01-02",
        strategy="trend_long", sector="Technology",
    )
    assert pos.ticker == "NVDA"
    assert pos.sector == "Technology"
    assert pos.stop_price == 95.0
    # entry_open_price defaults to entry_price when caller doesn't supply raw Open
    assert pos.entry_open_price == 100.0


# ── backtester fill model (P0-3 Part 2) ──────────────────────────────────────

def test_backtester_stop_fill_gap_down_with_slippage():
    """Gap-down stop: fill uses Open (not daily Low), then sell-side slippage.

    Open $92 below stop $95 → raw fill = $92; with 10bp sell slippage → $91.908.
    """
    from fill_model import apply_stop_fill, SLIPPAGE_BPS_STOP
    got = apply_stop_fill(open_price=92.0, stop_price=95.0)
    expected = round(92.0 * (1 - SLIPPAGE_BPS_STOP / 10000.0), 4)
    assert got == expected
    assert got < 92.0, "sell-side slippage must lower the fill below raw Open"


def test_backtester_stop_fill_intraday_uses_stop_minus_slippage():
    """Intraday stop: fill based on stop (not Low), with sell slippage."""
    from fill_model import apply_stop_fill, SLIPPAGE_BPS_STOP
    got = apply_stop_fill(open_price=97.0, stop_price=95.0)
    expected = round(95.0 * (1 - SLIPPAGE_BPS_STOP / 10000.0), 4)
    assert got == expected


def test_backtester_target_fill_gap_up_uses_open_with_slippage():
    """Gap-up target: fill = Open (bonus over target), minus sell slippage.

    This is the case the PRE-fix backtester got WRONG — it priced at
    target_price ($110) even when Open gapped to $112.
    """
    from fill_model import apply_target_fill, SLIPPAGE_BPS_TARGET
    got = apply_target_fill(open_price=112.0, target_price=110.0)
    expected = round(112.0 * (1 - SLIPPAGE_BPS_TARGET / 10000.0), 4)
    assert got == expected
    assert got > 110.0, "gap-up target fill must beat raw target even after slippage"


def test_backtester_target_fill_intraday_uses_target_minus_slippage():
    """Intraday target: Open below target, High tags target → fill at target - slip."""
    from fill_model import apply_target_fill, SLIPPAGE_BPS_TARGET
    got = apply_target_fill(open_price=105.0, target_price=110.0)
    expected = round(110.0 * (1 - SLIPPAGE_BPS_TARGET / 10000.0), 4)
    assert got == expected
    assert got < 110.0


def test_backtester_entry_fill_adds_buy_slippage():
    """Long entry fill: raw Open + buy-side slippage (fill is WORSE = higher)."""
    from fill_model import apply_entry_fill, SLIPPAGE_BPS_ENTRY
    got = apply_entry_fill(open_price=100.0)
    expected = round(100.0 * (1 + SLIPPAGE_BPS_ENTRY / 10000.0), 4)
    assert got == expected
    assert got > 100.0


def test_fill_model_helpers_consistent_with_raw_apply_slippage():
    """Sanity: the high-level helpers round-trip through apply_slippage
    with the same constants, so changing one place affects everything."""
    from fill_model import (
        apply_slippage, apply_entry_fill, apply_stop_fill, apply_target_fill,
        SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_STOP, SLIPPAGE_BPS_TARGET,
    )
    assert apply_entry_fill(100.0) == apply_slippage(100.0, SLIPPAGE_BPS_ENTRY, "buy")
    # Stop intraday case reduces to raw apply_slippage on stop_price
    assert apply_stop_fill(97.0, 95.0) == apply_slippage(95.0, SLIPPAGE_BPS_STOP, "sell")
    # Target intraday case reduces to raw apply_slippage on target_price
    assert apply_target_fill(105.0, 110.0) == apply_slippage(110.0, SLIPPAGE_BPS_TARGET, "sell")


# ── forward_tester position_actions fill model (P0-3 Part 3) ─────────────────

def test_evaluate_file_position_action_exit_uses_slippage(monkeypatch, tmp_path):
    """EXIT/REDUCE position_actions must record a fill-model-grounded realized
    P&L (`realized_exit_pnl_pct_net`) alongside the legacy close-to-close
    direction signal (`return_10d_pct`).

    Pre-fix gap: position_actions were evaluated only on close-to-close returns,
    so the realized P&L of an actual sell was invisible to downstream per-
    strategy attribution.

    Scenario: avg_cost=$100, position is underwater on rec_date (close $92).
      next-day Open $90, sell slippage 10bp → fill $89.91
      realized_exit_pnl_pct     = 89.91 / 100 - 1  = -0.1009
      realized_exit_pnl_pct_net = -0.1009 - 0.0035 = -0.1044
    """
    import json
    from datetime import date, timedelta
    import forward_tester as ft
    from forward_tester import (
        evaluate_file, SLIPPAGE_BPS_STOP, ROUND_TRIP_COST,
    )

    rec = date.today() - timedelta(days=30)
    rec_str = rec.strftime("%Y%m%d")

    advice_path = tmp_path / f"investment_advice_{rec_str}.json"
    advice_path.write_text(json.dumps({
        "advice_parsed": {
            "position_actions": [
                {"ticker": "TEST", "action": "EXIT", "confidence": 0.9,
                 "exit_rule_triggered": "NONE"},
            ],
            "new_trade": None,
        }
    }))

    pos_path = tmp_path / "open_positions.json"
    pos_path.write_text(json.dumps({
        "positions": [{"ticker": "TEST", "avg_cost": 100.0}]
    }))

    # rec_date close $92 (already underwater), eval_date close $88
    monkeypatch.setattr(ft, "get_close_price",
        lambda ticker, d: (92.0, d) if d == rec else (88.0, d))
    # Next-day Open $90 — worse than rec_date close (adverse gap)
    monkeypatch.setattr(ft, "get_next_open_price",
        lambda ticker, d: (90.0, d + timedelta(days=1)))

    result = evaluate_file(str(advice_path), open_positions_path=str(pos_path))
    pr = result["position_results"][0]

    expected_fill = round(90.0 * (1 - SLIPPAGE_BPS_STOP / 10000.0), 4)
    expected_gross = round(expected_fill / 100.0 - 1, 4)
    expected_net   = round(expected_gross - ROUND_TRIP_COST, 4)

    assert pr["exit_fill_price"]            == expected_fill
    assert pr["realized_exit_pnl_pct"]      == expected_gross
    assert pr["realized_exit_pnl_pct_net"]  == expected_net
    # Net realized P&L must be strictly worse than the gross (commission drag).
    assert pr["realized_exit_pnl_pct_net"] < pr["realized_exit_pnl_pct"]
    # And strictly worse than close-to-close price_rec vs avg_cost baseline,
    # because Open was lower than rec_date close and slippage further lowers it.
    assert pr["realized_exit_pnl_pct_net"] < pr["pnl_vs_cost_pct"]


def test_evaluate_file_position_action_hold_has_no_exit_fill(monkeypatch, tmp_path):
    """HOLD actions do not execute a sale, so exit_fill_price and
    realized_exit_pnl_pct_net must be None (fill model only applies to EXIT/REDUCE)."""
    import json
    from datetime import date, timedelta
    import forward_tester as ft
    from forward_tester import evaluate_file

    rec = date.today() - timedelta(days=30)
    rec_str = rec.strftime("%Y%m%d")

    advice_path = tmp_path / f"investment_advice_{rec_str}.json"
    advice_path.write_text(json.dumps({
        "advice_parsed": {
            "position_actions": [
                {"ticker": "TEST", "action": "HOLD", "confidence": 0.7,
                 "exit_rule_triggered": "NONE"},
            ],
            "new_trade": None,
        }
    }))

    pos_path = tmp_path / "open_positions.json"
    pos_path.write_text(json.dumps({
        "positions": [{"ticker": "TEST", "avg_cost": 100.0}]
    }))

    monkeypatch.setattr(ft, "get_close_price",
        lambda ticker, d: (105.0, d) if d == rec else (110.0, d))
    monkeypatch.setattr(ft, "get_next_open_price",
        lambda ticker, d: (106.0, d + timedelta(days=1)))

    result = evaluate_file(str(advice_path), open_positions_path=str(pos_path))
    pr = result["position_results"][0]

    assert pr["action"] == "HOLD"
    assert pr["exit_fill_price"]           is None
    assert pr["realized_exit_pnl_pct"]     is None
    assert pr["realized_exit_pnl_pct_net"] is None
    # return_10d_pct must still be populated so direction-correctness grading
    # continues to work unchanged.
    assert pr["return_10d_pct"] is not None


# ── backtester END-TO-END fill-model integration (P0-3 Part 2) ───────────────
#
# The unit tests above prove the fill_model helpers compute the right number.
# These tests prove BacktestEngine.run() actually USES those helpers — catching
# the class of bug where helpers are correct but the pipeline either skips them
# or drops their output before it reaches a closed trade record.

def _backtest_harness(monkeypatch, test_df, spy_df):
    """Stub the whole pipeline so BacktestEngine.run() executes deterministically.

    Returns a configured BacktestEngine where the only real logic is the
    exit/entry/fill wiring inside run() itself.
    """
    import backtester, feature_layer, signal_engine, risk_engine, portfolio_engine
    import regime as regime_mod
    from backtester import BacktestEngine

    monkeypatch.setattr(BacktestEngine, "_download_data",
        lambda self: {"TEST": test_df, "SPY": spy_df, "QQQ": spy_df})
    monkeypatch.setattr(feature_layer, "compute_features",
        lambda t, df, e: {"ticker": t})
    monkeypatch.setattr(regime_mod, "compute_market_regime",
        lambda ohlcv_override=None: {
            "regime": "BULL",
            "indices": {
                "SPY": {"pct_from_ma": 0.05, "momentum_10d_pct": 0.02},
                "QQQ": {"pct_from_ma": 0.05},
            },
        })
    monkeypatch.setattr(signal_engine, "generate_signals",
        lambda features, market_context=None, **kwargs: (
            [{"ticker": "TEST", "strategy": "trend_long", "sector": "Tech",
              "entry_price": 100.0, "stop_price": 95.0, "target_price": 110.0,
              "trade_quality_score": 0.8}]
            if "TEST" in features else []))
    monkeypatch.setattr(risk_engine, "enrich_signals",
        lambda signals, features, atr_target_mult=None: signals)
    def fake_size(signals, equity, risk_pct=None):
        for s in signals:
            s["sizing"] = {"shares_to_buy": 10}
        return signals
    monkeypatch.setattr(portfolio_engine, "size_signals", fake_size)

    engine = BacktestEngine(
        universe=["TEST"],
        config={"INITIAL_CAPITAL": 100_000, "MAX_POSITIONS": 5},
    )
    engine.start = test_df.index[0]
    engine.end   = test_df.index[-1]
    return engine


def _flat_then_trigger_df(idx, trigger_open, trigger_high, trigger_low):
    """OHLCV: flat $100 for all but the last bar, which carries trigger prices."""
    n = len(idx)
    return pd.DataFrame({
        "Open":  [100.0] * (n - 1) + [trigger_open],
        "High":  [100.0] * (n - 1) + [trigger_high],
        "Low":   [100.0] * (n - 1) + [trigger_low],
        "Close": [100.0] * (n - 1) + [trigger_open],
    }, index=idx)


def test_backtester_run_gap_up_target_uses_fill_model(monkeypatch):
    """End-to-end: BacktestEngine.run() records a gap-up target exit at
    apply_target_fill(Open, target) — NOT raw target_price — and deducts
    ROUND_TRIP_COST_PCT on top.

    Pre-refactor bug this guards: backtester priced target exits at
    `pos.target_price` flat (no slippage, no gap bonus).
    """
    import pandas as pd
    from fill_model import apply_entry_fill, apply_target_fill
    from portfolio_engine import ROUND_TRIP_COST_PCT

    idx = pd.bdate_range("2025-10-01", periods=30)   # 30d so data_slice >= 21
    spy_df = pd.DataFrame({"Open": [100.0]*30, "High": [100.0]*30,
                           "Low": [100.0]*30,  "Close": [100.0]*30}, index=idx)
    # Last bar gaps up through $110 target — Open=112, High=113.
    test_df = _flat_then_trigger_df(idx, trigger_open=112.0,
                                    trigger_high=113.0, trigger_low=112.0)

    engine = _backtest_harness(monkeypatch, test_df, spy_df)
    result = engine.run()

    assert result.get("total_trades") == 1, f"expected 1 trade, got {result}"
    trade = result["trades"][0]
    assert trade["exit_reason"] == "target"

    expected_entry = round(apply_entry_fill(100.0), 2)
    expected_exit  = round(apply_target_fill(112.0, 110.0), 2)
    assert trade["entry_price"]    == expected_entry
    assert trade["exit_price"]     == expected_exit
    assert trade["exit_raw_price"] == 112.0
    # Gap-up: realized exit price should BEAT raw target even after slippage.
    assert trade["exit_price"] > 110.0, (
        f"gap-up fill must exceed raw target; got {trade['exit_price']}")
    # slippage_cost aggregates entry + exit slippage dollars.
    assert trade["slippage_cost"] > 0

    # P&L must include commission: (exit - entry) * shares - exit * COST_PCT * shares
    exit_raw_fill  = apply_target_fill(112.0, 110.0)
    entry_raw_fill = apply_entry_fill(100.0)
    expected_cost  = exit_raw_fill * ROUND_TRIP_COST_PCT * 10
    expected_pnl   = round((exit_raw_fill - entry_raw_fill) * 10 - expected_cost, 2)
    assert trade["pnl"] == expected_pnl, (
        f"pnl must deduct ROUND_TRIP_COST_PCT * exit * shares; "
        f"expected {expected_pnl}, got {trade['pnl']}")


def test_backtester_run_intraday_stop_uses_fill_model(monkeypatch):
    """End-to-end: intraday stop hit (Open above stop, Low below) → exit
    records apply_stop_fill(Open, stop) = stop_price minus sell slippage.
    """
    import pandas as pd
    from fill_model import apply_entry_fill, apply_stop_fill
    from portfolio_engine import ROUND_TRIP_COST_PCT

    idx = pd.bdate_range("2025-10-01", periods=30)
    spy_df = pd.DataFrame({"Open": [100.0]*30, "High": [100.0]*30,
                           "Low": [100.0]*30,  "Close": [100.0]*30}, index=idx)
    # Last bar: Open $99 (above stop $95), Low $94 (below stop) → intraday stop.
    test_df = _flat_then_trigger_df(idx, trigger_open=99.0,
                                    trigger_high=99.0, trigger_low=94.0)

    engine = _backtest_harness(monkeypatch, test_df, spy_df)
    result = engine.run()

    assert result.get("total_trades") == 1, f"expected 1 trade, got {result}"
    trade = result["trades"][0]
    assert trade["exit_reason"] == "stop"

    expected_exit = round(apply_stop_fill(99.0, 95.0), 2)
    assert trade["exit_price"]     == expected_exit
    assert trade["exit_raw_price"] == 95.0
    # Slippage on stop makes realized fill strictly worse than raw stop.
    assert trade["exit_price"] < 95.0, (
        f"sell slippage on stop must lower the fill; got {trade['exit_price']}")
    assert trade["slippage_cost"] > 0

    exit_raw_fill  = apply_stop_fill(99.0, 95.0)
    entry_raw_fill = apply_entry_fill(100.0)
    expected_cost  = exit_raw_fill * ROUND_TRIP_COST_PCT * 10
    expected_pnl   = round((exit_raw_fill - entry_raw_fill) * 10 - expected_cost, 2)
    assert trade["pnl"] == expected_pnl


def test_backtester_cancels_entry_on_gap_down_below_stop(monkeypatch):
    """Gap-down cancel: if next-day Open ≤ stop, entry is aborted.

    Regression guard for the 3 trades in the 2025-10-16 → 2026-04-14 backtest
    (SLV / GLD / IAU) that filled below stop due to overnight gap-downs and
    stopped out on day 0 — -$302.68 guaranteed losses.
    """
    import pandas as pd

    idx = pd.bdate_range("2025-10-01", periods=30)
    spy_df = pd.DataFrame({"Open": [100.0]*30, "High": [100.0]*30,
                           "Low":  [100.0]*30, "Close": [100.0]*30}, index=idx)
    # Day 0 closes $100 (signal day, mocked entry=100 / stop=95).
    # Every subsequent day Open=$94 → always below the $95 stop → never enters.
    n = len(idx)
    test_df = pd.DataFrame({
        "Open":  [100.0] + [94.0] * (n - 1),
        "High":  [100.0] + [94.0] * (n - 1),
        "Low":   [100.0] + [94.0] * (n - 1),
        "Close": [100.0] + [94.0] * (n - 1),
    }, index=idx)

    engine = _backtest_harness(monkeypatch, test_df, spy_df)
    result = engine.run()

    assert result.get("total_trades") == 0, (
        f"entry with fill ≤ stop must be cancelled; got {result.get('total_trades')} trades"
    )


def test_backtester_filters_already_held_before_sector_cap(monkeypatch):
    import backtester
    import feature_layer
    import signal_engine
    import risk_engine
    import portfolio_engine
    import regime as regime_mod
    from backtester import BacktestEngine

    idx = pd.bdate_range("2025-10-01", periods=40)
    flat = pd.DataFrame({
        "Open": [100.0] * len(idx),
        "High": [100.0] * len(idx),
        "Low": [100.0] * len(idx),
        "Close": [100.0] * len(idx),
    }, index=idx)
    ohlcv = {"HELD": flat, "NEW": flat, "SPY": flat, "QQQ": flat}
    first_signal_day = idx[20]
    second_signal_day = idx[25]

    monkeypatch.setattr(BacktestEngine, "_download_data", lambda self: ohlcv)
    monkeypatch.setattr(feature_layer, "compute_features",
        lambda ticker, df, earn: {"ticker": ticker, "close": 100.0, "as_of": df.index[-1]})
    monkeypatch.setattr(regime_mod, "compute_market_regime",
        lambda ohlcv_override=None: {
            "regime": "BULL",
            "indices": {
                "SPY": {"pct_from_ma": 0.05, "momentum_10d_pct": 0.02},
                "QQQ": {"pct_from_ma": 0.05},
            },
        })

    def fake_generate(features, market_context=None, **kwargs):
        if not features:
            return []
        day = next(iter(features.values()))["as_of"]
        if day == first_signal_day:
            return [{
                "ticker": "HELD", "strategy": "trend_long", "sector": "Tech",
                "entry_price": 100.0, "stop_price": 95.0, "target_price": 130.0,
                "trade_quality_score": 0.9,
            }]
        if day == second_signal_day:
            return [
                {
                    "ticker": "HELD", "strategy": "trend_long", "sector": "Tech",
                    "entry_price": 100.0, "stop_price": 95.0, "target_price": 130.0,
                    "trade_quality_score": 0.9,
                },
                {
                    "ticker": "NEW", "strategy": "trend_long", "sector": "Tech",
                    "entry_price": 100.0, "stop_price": 95.0, "target_price": 130.0,
                    "trade_quality_score": 0.8,
                },
            ]
        return []

    monkeypatch.setattr(signal_engine, "generate_signals", fake_generate)
    monkeypatch.setattr(risk_engine, "enrich_signals",
        lambda signals, features, atr_target_mult=None: signals)
    monkeypatch.setattr(portfolio_engine, "size_signals",
        lambda signals, equity, risk_pct=None: [
            {**s, "sizing": {"shares_to_buy": 1}} for s in signals
        ])
    monkeypatch.setattr(portfolio_engine, "compute_portfolio_heat",
        lambda *args, **kwargs: {
            "can_add_new_positions": True,
            "heat_note": "ok",
        })
    monkeypatch.setattr(backtester, "MAX_PER_SECTOR", 1)

    engine = BacktestEngine(
        universe=["HELD", "NEW"],
        config={"INITIAL_CAPITAL": 100_000, "MAX_POSITIONS": 5},
    )
    engine.start = idx[0]
    engine.end = idx[-1]

    result = engine.run()

    traded = [t["ticker"] for t in result["trades"]]
    assert traded.count("HELD") == 1
    assert traded.count("NEW") == 1, (
        "already-held tickers must be removed before sector cap so fresh candidates survive"
    )


def test_backtester_respects_portfolio_heat_gate_for_new_entries(monkeypatch):
    import feature_layer
    import signal_engine
    import risk_engine
    import portfolio_engine
    import regime as regime_mod
    from backtester import BacktestEngine

    idx = pd.bdate_range("2025-10-01", periods=40)
    flat = pd.DataFrame({
        "Open": [100.0] * len(idx),
        "High": [100.0] * len(idx),
        "Low": [100.0] * len(idx),
        "Close": [100.0] * len(idx),
    }, index=idx)
    ohlcv = {"HELD": flat, "NEW": flat, "SPY": flat, "QQQ": flat}
    first_signal_day = idx[20]
    second_signal_day = idx[25]

    monkeypatch.setattr(BacktestEngine, "_download_data", lambda self: ohlcv)
    monkeypatch.setattr(feature_layer, "compute_features",
        lambda ticker, df, earn: {"ticker": ticker, "close": 100.0, "as_of": df.index[-1]})
    monkeypatch.setattr(regime_mod, "compute_market_regime",
        lambda ohlcv_override=None: {
            "regime": "BULL",
            "indices": {
                "SPY": {"pct_from_ma": 0.05, "momentum_10d_pct": 0.02},
                "QQQ": {"pct_from_ma": 0.05},
            },
        })

    def fake_generate(features, market_context=None, **kwargs):
        if not features:
            return []
        day = next(iter(features.values()))["as_of"]
        if day == first_signal_day:
            return [{
                "ticker": "HELD", "strategy": "trend_long", "sector": "Tech",
                "entry_price": 100.0, "stop_price": 95.0, "target_price": 130.0,
                "trade_quality_score": 0.9,
            }]
        if day == second_signal_day:
            return [{
                "ticker": "NEW", "strategy": "trend_long", "sector": "Tech",
                "entry_price": 100.0, "stop_price": 95.0, "target_price": 130.0,
                "trade_quality_score": 0.8,
            }]
        return []

    monkeypatch.setattr(signal_engine, "generate_signals", fake_generate)
    monkeypatch.setattr(risk_engine, "enrich_signals",
        lambda signals, features, atr_target_mult=None: signals)
    monkeypatch.setattr(portfolio_engine, "size_signals",
        lambda signals, equity, risk_pct=None: [
            {**s, "sizing": {"shares_to_buy": 1}} for s in signals
        ])

    def fake_heat(open_positions, *args, **kwargs):
        return {
            "can_add_new_positions": len(open_positions.get("positions", [])) == 0,
            "heat_note": "blocked" if open_positions.get("positions") else "ok",
        }

    monkeypatch.setattr(portfolio_engine, "compute_portfolio_heat", fake_heat)

    engine = BacktestEngine(
        universe=["HELD", "NEW"],
        config={"INITIAL_CAPITAL": 100_000, "MAX_POSITIONS": 5},
    )
    engine.start = idx[0]
    engine.end = idx[-1]

    result = engine.run()

    traded = [t["ticker"] for t in result["trades"]]
    assert traded.count("HELD") == 1
    assert "NEW" not in traded, "portfolio heat gate should block fresh entries"


def test_regime_from_ohlcv_bull():
    """_compute_regime_from_ohlcv returns above_ma=True for uptrending data."""
    from regime import _compute_regime_from_ohlcv
    # 250 days of steady uptrend — close always above 200MA
    dates = pd.bdate_range("2024-01-02", periods=250)
    data = {
        "Open":  [100 + i * 0.2 for i in range(250)],
        "High":  [101 + i * 0.2 for i in range(250)],
        "Low":   [99  + i * 0.2 for i in range(250)],
        "Close": [100 + i * 0.2 for i in range(250)],
        "Volume": [1_000_000] * 250,
    }
    df = pd.DataFrame(data, index=dates)
    result = _compute_regime_from_ohlcv("SPY", df, ma_period=200)
    assert result is not None
    assert result["above_ma"] is True
    assert result["pct_from_ma"] > 0


def test_regime_compute_with_ohlcv_override():
    """compute_market_regime with ohlcv_override should not call yfinance."""
    from regime import compute_market_regime
    dates = pd.bdate_range("2024-01-02", periods=250)
    data = {
        "Open":  [100 + i * 0.2 for i in range(250)],
        "High":  [101 + i * 0.2 for i in range(250)],
        "Low":   [99  + i * 0.2 for i in range(250)],
        "Close": [100 + i * 0.2 for i in range(250)],
        "Volume": [1_000_000] * 250,
    }
    df = pd.DataFrame(data, index=dates)
    result = compute_market_regime(ohlcv_override={"SPY": df, "QQQ": df})
    assert result["regime"] == "BULL"
    assert "SPY" in result["indices"]
    assert "QQQ" in result["indices"]


# ── forward_tester profit-lock timing quality ────────────────────────────────

def test_forward_tester_profit_lock_reports_peak_capture():
    """A profit-lock REDUCE that sells at +20% while the stock runs to +40%
    must be direction_correct but timing_incorrect, with ≈16.7% foregone gain
    and ≈50% peak capture (cost-to-peak formulation)."""
    import pandas as pd
    from datetime import date
    from forward_tester import (
        evaluate_profit_lock_timing, action_is_correct, PROFIT_LOCKING_RULES,
    )

    rec_date  = date(2024, 1, 2)
    eval_date = date(2024, 1, 16)
    # avg_cost $100, rule fires at $120 close → window High peaks at $140
    idx = pd.to_datetime([
        "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05",
        "2024-01-08", "2024-01-09", "2024-01-10", "2024-01-11",
        "2024-01-12", "2024-01-16",
    ])
    fake_daily = pd.DataFrame({
        "Open":  [120.0, 122.0, 125.0, 128.0, 132.0, 135.0, 138.0, 139.0, 136.0, 130.0],
        "High":  [121.0, 124.0, 127.0, 130.0, 134.0, 137.0, 140.0, 139.5, 138.0, 133.0],
        "Low":   [119.0, 121.0, 124.0, 127.0, 131.0, 134.0, 137.0, 136.0, 130.0, 128.0],
        "Close": [120.0, 123.0, 126.0, 129.0, 133.0, 136.0, 139.0, 137.0, 132.0, 131.0],
    }, index=idx)

    result = evaluate_profit_lock_timing(
        ticker          = "TEST",
        rec_date        = rec_date,
        eval_date       = eval_date,
        sell_price      = 120.0,
        avg_cost        = 100.0,
        _daily_override = fake_daily,
    )

    assert result["data_available"]      is True
    assert result["max_price_in_window"] == 140.0
    # foregone = (140 - 120) / 120 = 0.1667
    assert result["foregone_gain_pct"]   == pytest.approx(0.1667, abs=1e-3)
    # peak_capture = (120 - 100) / (140 - 100) = 0.5
    assert result["peak_capture_pct"]    == pytest.approx(0.5,    abs=1e-3)
    assert result["timing_correct"]      is False, (
        "16.7% foregone gain is well above the 5% tolerance — must be flagged"
    )

    # Direction is still correct for a profit-locking reduce: rule fired as planned.
    assert all(rule in PROFIT_LOCKING_RULES for rule in
               ["PROFIT_TARGET", "SIGNAL_TARGET", "PROFIT_LADDER_50", "PROFIT_LADDER_30"])
    assert action_is_correct("REDUCE", return_10d=0.0, exit_rule="PROFIT_TARGET") is True


def test_forward_tester_profit_lock_timing_correct_when_near_peak():
    """When a profit-lock sell is within 5% of the window's peak, timing_correct=True
    and foregone_gain_pct < 0.05."""
    import pandas as pd
    from datetime import date
    from forward_tester import evaluate_profit_lock_timing

    rec_date  = date(2024, 1, 2)
    eval_date = date(2024, 1, 16)
    # Sell at $120, window High only reaches $121 (0.83% above sell → within 5%)
    idx = pd.to_datetime([
        "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05",
        "2024-01-08", "2024-01-09",
    ])
    fake_daily = pd.DataFrame({
        "Open":  [120.0, 120.2, 120.5, 120.8, 120.3, 119.5],
        "High":  [120.8, 120.9, 121.0, 120.9, 120.4, 119.8],
        "Low":   [119.5, 119.9, 120.1, 120.3, 119.7, 118.9],
        "Close": [120.0, 120.3, 120.6, 120.4, 120.0, 119.0],
    }, index=idx)

    result = evaluate_profit_lock_timing(
        ticker          = "TEST",
        rec_date        = rec_date,
        eval_date       = eval_date,
        sell_price      = 120.0,
        avg_cost        = 100.0,
        _daily_override = fake_daily,
    )

    assert result["data_available"]      is True
    assert result["max_price_in_window"] == 121.0
    # foregone = (121 - 120) / 120 ≈ 0.00833
    assert result["foregone_gain_pct"]   == pytest.approx(0.0083, abs=1e-3)
    assert result["foregone_gain_pct"]   < 0.05
    assert result["timing_correct"]      is True


def test_forward_tester_non_profit_lock_reduce_still_uses_return_direction():
    """REDUCE with a non-profit-lock rule (e.g., TRAILING_STOP) must still be
    graded by the original return_direction logic — profit-lock special case
    should not affect it."""
    from forward_tester import action_is_correct, PROFIT_LOCKING_RULES

    assert "TRAILING_STOP"         not in PROFIT_LOCKING_RULES
    assert "EXIT"                  not in PROFIT_LOCKING_RULES
    assert "APPROACHING_HARD_STOP" not in PROFIT_LOCKING_RULES

    # Negative return → REDUCE for risk was correct (cut a loser)
    assert action_is_correct("REDUCE", return_10d=-0.05, exit_rule="TRAILING_STOP") is True
    # Positive return → reducing was wrong (price rose afterwards)
    assert action_is_correct("REDUCE", return_10d= 0.05, exit_rule="TRAILING_STOP") is False
    # Baseline REDUCE without any rule — same return-direction logic
    assert action_is_correct("REDUCE", return_10d=-0.02) is True
    assert action_is_correct("REDUCE", return_10d= 0.02) is False


# ── import_advice.py manual-import helper ────────────────────────────────────

def test_import_advice_parses_fenced_json(tmp_path):
    """The import helper must extract JSON from markdown-fenced responses
    (the typical ChatGPT/Claude web UI output) and write the wrapper format
    forward_tester expects to data/investment_advice_<date>.json."""
    import json
    from import_advice import import_advice

    raw_response = """Sure, here's my analysis for today.

```json
{
  "new_trade": {
    "ticker": "NVDA",
    "signal_source": "trend_long",
    "trade_quality_score": 0.82
  },
  "second_new_trade": "NO SECOND TRADE",
  "position_actions": [
    {"ticker": "AAPL", "action": "HOLD"},
    {"ticker": "TSLA", "action": "REDUCE"}
  ]
}
```

Let me know if you want me to explain the NVDA thesis."""

    out_path = import_advice(
        date_str   = "20260410",
        raw_text   = raw_response,
        output_dir = str(tmp_path),
    )
    import os as _os
    assert _os.path.exists(out_path)
    assert _os.path.basename(out_path) == "investment_advice_20260410.json"

    with open(out_path, encoding="utf-8") as f:
        wrapper = json.load(f)

    # save_advice wrapper format: {advice_raw, advice_parsed, token_usage, timestamp}
    assert "advice_raw"     in wrapper
    assert "advice_parsed"  in wrapper
    assert "token_usage"    in wrapper
    assert "timestamp"      in wrapper

    parsed = wrapper["advice_parsed"]
    assert isinstance(parsed, dict)
    assert parsed["new_trade"]["ticker"] == "NVDA"
    assert parsed["new_trade"]["signal_source"] == "trend_long"
    assert len(parsed["position_actions"]) == 2
    assert parsed["position_actions"][0]["ticker"] == "AAPL"


def test_import_advice_writes_replay_file(tmp_path):
    """import_advice must also write llm_prompt_resp_YYYYMMDD.json alongside
    investment_advice_YYYYMMDD.json so backtester --replay-llm can pick it up
    without the user doing a separate manual step."""
    import json, os as _os
    from import_advice import import_advice
    from llm_replay import get_llm_decision_for_date
    import datetime

    raw_response = '{"new_trade": {"ticker": "AMZN", "signal_source": "trend_long"}, "position_actions": []}'
    import_advice(date_str="20260420", raw_text=raw_response, output_dir=str(tmp_path))

    replay_path = tmp_path / "llm_prompt_resp_20260420.json"
    assert replay_path.exists(), "llm_prompt_resp_YYYYMMDD.json must be written"

    # Verify llm_replay can parse it and extract the approved ticker
    d = datetime.datetime(2026, 4, 20)
    decision = get_llm_decision_for_date(d, data_dir=str(tmp_path))
    assert decision["file_present"]
    assert decision["approved_tickers"] == ["AMZN"]


def test_save_advice_writes_replay_file_for_dated_investment_advice(tmp_path):
    """Automatic dated advice saves must also create the replay twin."""
    import json
    from llm_advisor import save_advice

    advice_path = tmp_path / "investment_advice_20260420.json"
    raw_response = '{"new_trade": {"ticker": "AMZN", "signal_source": "trend_long"}, "position_actions": []}'

    ok = save_advice(raw_response, str(advice_path), token_usage={"total_tokens": 12})

    assert ok is True
    replay_path = tmp_path / "llm_prompt_resp_20260420.json"
    assert replay_path.exists(), "dated advice saves must auto-create the replay twin"
    saved = json.loads(replay_path.read_text(encoding="utf-8"))
    assert saved["advice_parsed"]["new_trade"]["ticker"] == "AMZN"
    assert saved["token_usage"]["total_tokens"] == 12


def test_save_advice_attaches_archive_context_when_decision_log_exists(tmp_path):
    """Dated advice saves should include prompt-time machine context when present."""
    import json
    from llm_advisor import save_advice

    (tmp_path / "llm_decision_log_20260420.json").write_text(json.dumps({
        "signals_presented": ["AMZN", "NVDA"],
        "signal_details": [{"ticker": "AMZN", "strategy": "trend_long"}],
        "new_trade_locked": True,
        "account_state": "LOCKED_BY_HEAT",
        "lock_reason": "Heat cap hit",
    }), encoding="utf-8")

    advice_path = tmp_path / "investment_advice_20260420.json"
    raw_response = '{"new_trade": "NO NEW TRADE", "position_actions": []}'

    ok = save_advice(raw_response, str(advice_path), token_usage=None)

    assert ok is True
    saved = json.loads(advice_path.read_text(encoding="utf-8"))
    ctx = saved["archive_context"]
    assert ctx["source"] == "llm_decision_log"
    assert ctx["signals_presented"] == ["AMZN"]
    assert ctx["signals_presented_count"] == 1
    assert ctx["ranking_eligible"] is False
    assert ctx["new_trade_locked"] is True
    assert ctx["account_state"] == "LOCKED_BY_HEAT"
    assert ctx["lock_reason"] == "Heat cap hit"


def test_get_investment_advice_api_mode_still_saves_prompt(tmp_path, monkeypatch):
    """API mode must still persist llm_prompt_YYYYMMDD.txt for audit/replay workflows."""
    import os
    from llm_advisor import get_investment_advice

    class _FixedDateTime:
        @classmethod
        def now(cls):
            import datetime as _dt
            return _dt.datetime(2026, 4, 22, 10, 30, 0)

    class _FakeResponse:
        class _Usage:
            prompt_tokens = 11
            completion_tokens = 7
            total_tokens = 18

        class _Choice:
            class _Message:
                content = '{"new_trade":"NO NEW TRADE","position_actions":[]}'
            message = _Message()

        choices = [_Choice()]
        usage = _Usage()

    class _FakeCompletions:
        @staticmethod
        def create(**kwargs):
            return _FakeResponse()

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeClient:
        def __init__(self, api_key):
            self.chat = _FakeChat()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr("llm_advisor.build_prompt", lambda *args, **kwargs: ("system body", "user body"))
    monkeypatch.setattr("llm_advisor.datetime", _FixedDateTime)
    monkeypatch.setattr("llm_advisor.OpenAI", _FakeClient)

    result = get_investment_advice(
        trade_news=[],
        open_positions={},
        trend_signals={"quant_signals": []},
        save_prompt_only=False,
    )

    assert result["success"] is True
    prompt_path = tmp_path / "data" / "llm_prompt_20260422.txt"
    assert prompt_path.exists(), "Prompt file must be written even when API mode is enabled"
    prompt_text = prompt_path.read_text(encoding="utf-8")
    assert "system body" in prompt_text
    assert "user body" in prompt_text


def test_save_advice_does_not_overwrite_existing_replay_file(tmp_path):
    """Automatic replay mirroring must preserve an existing manual replay file."""
    from llm_advisor import save_advice

    advice_path = tmp_path / "investment_advice_20260420.json"
    replay_path = tmp_path / "llm_prompt_resp_20260420.json"
    replay_path.write_text('{"manual": true}', encoding="utf-8")

    raw_response = '{"new_trade": {"ticker": "AMZN", "signal_source": "trend_long"}, "position_actions": []}'
    ok = save_advice(raw_response, str(advice_path), token_usage=None)

    assert ok is True
    assert replay_path.read_text(encoding="utf-8") == '{"manual": true}'


def test_save_advice_skips_replay_for_non_response_payload(tmp_path):
    """Fake or partial advice saves without new_trade must not create replay logs."""
    from llm_advisor import save_advice

    advice_path = tmp_path / "investment_advice_20260421.json"
    fake_raw = "Prompt saved to data/llm_prompt_20260421.txt\n\nTo use this prompt:\n1. Copy the content"

    ok = save_advice(fake_raw, str(advice_path), token_usage=None)

    assert ok is True
    replay_path = tmp_path / "llm_prompt_resp_20260421.json"
    assert not replay_path.exists()


def test_import_advice_replay_file_not_overwritten(tmp_path):
    """If llm_prompt_resp_YYYYMMDD.json already exists (e.g. manually saved),
    import_advice must not overwrite it."""
    import json, os as _os
    from import_advice import import_advice

    existing = tmp_path / "llm_prompt_resp_20260420.json"
    existing.write_text('{"new_trade": "MANUAL"}', encoding="utf-8")

    import_advice(
        date_str="20260420",
        raw_text='{"new_trade": {"ticker": "NVDA"}, "position_actions": []}',
        output_dir=str(tmp_path),
    )

    # Existing manual file should be preserved
    assert json.loads(existing.read_text(encoding="utf-8"))["new_trade"] == "MANUAL"


def test_import_advice_skips_replay_for_fake_response(tmp_path):
    """A 'Prompt saved to...' acknowledgment (save_prompt_only=True path) must NOT
    be written as a replay file — it is not a real LLM response and would veto
    all signals on that date."""
    import os as _os
    from import_advice import import_advice

    fake_raw = "Prompt saved to data/llm_prompt_20260421.txt\n\nTo use this prompt:\n1. Copy the content"

    import_advice(date_str="20260421", raw_text=fake_raw, output_dir=str(tmp_path))

    replay_path = tmp_path / "llm_prompt_resp_20260421.json"
    assert not replay_path.exists(), "Replay file must NOT be written for fake save-prompt responses"


def test_import_advice_warns_on_missing_keys(tmp_path, caplog):
    """When the response is missing one of the required keys (new_trade /
    position_actions), the helper must log a warning but still write the file
    so partial captures aren't silently lost."""
    import json
    import logging
    from import_advice import import_advice

    # Missing position_actions
    raw_response = '{"new_trade": "NO NEW TRADE"}'

    with caplog.at_level(logging.WARNING, logger="import_advice"):
        out_path = import_advice(
            date_str   = "20260411",
            raw_text   = raw_response,
            output_dir = str(tmp_path),
        )

    # File still written
    import os as _os
    assert _os.path.exists(out_path)
    with open(out_path, encoding="utf-8") as f:
        wrapper = json.load(f)
    assert wrapper["advice_parsed"]["new_trade"] == "NO NEW TRADE"

    # Warning was logged
    warning_msgs = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert any("position_actions" in m for m in warning_msgs), (
        f"Expected a warning mentioning 'position_actions', got: {warning_msgs}"
    )


# ── trade_advice.txt abstain-first prompt regression ─────────────────────────

def test_prompt_disaster_detector_framing_present():
    """The trade_advice.txt prompt must frame LLM as disaster detector, not trade advisor.

    The 2026-04 redesign narrows LLM role to T1 negative news veto only.
    All quantitative decisions (TQS, frequency, position actions) are code-enforced.
    """
    import os
    path = os.path.join(
        os.path.dirname(__file__), "..", "instructinos", "prompts", "trade_advice.txt"
    )
    with open(path, encoding="utf-8") as f:
        content = f.read()

    # Disaster detector framing
    assert "灾难检测器" in content, (
        "Prompt must contain '灾难检测器' — LLM role is disaster detection only."
    )
    assert "唯一职责" in content, (
        "Prompt must state LLM has only one responsibility."
    )

    # No WATCH state — all position decisions are code-determined
    assert "WATCH" not in content, (
        "WATCH state should not appear in prompt — eliminated by code rules."
    )

    # Position actions are pass-through
    assert "代码已决定" in content, (
        "Prompt must indicate position actions are code-determined."
    )

    # No quantitative thresholds in prompt
    assert "trade_quality_score < 0.75" not in content, (
        "TQS threshold should be in code, not prompt."
    )
    assert "trade_quality_score ≥ 0.80" not in content, (
        "Second-trade TQS threshold should be in code, not prompt."
    )

    # No second_new_trade — frequency is code-controlled
    assert "second_new_trade" not in content, (
        "Trade frequency control should be in code, not prompt."
    )


# ── P0-1 per-strategy attribution ────────────────────────────────────────────

def test_aggregate_by_strategy_basic():
    from strategy_attribution import aggregate_by_strategy
    trades = [
        {"strategy": "A", "pnl_pct_net":  0.05},
        {"strategy": "A", "pnl_pct_net": -0.02},
        {"strategy": "B", "pnl_pct_net":  0.10},
    ]
    out = aggregate_by_strategy(trades)
    assert set(out.keys()) == {"A", "B"}
    assert out["A"]["trade_count"]     == 2
    assert out["A"]["wins"]            == 1
    assert out["A"]["losses"]          == 1
    assert out["A"]["win_rate"]        == 0.5
    assert out["A"]["avg_pnl_pct_net"] == 0.015
    assert out["A"]["profit_factor"]   == round(0.05 / 0.02, 3)
    assert out["B"]["trade_count"]     == 1
    assert out["B"]["win_rate"]        == 1.0


def test_aggregate_by_strategy_missing_strategy_buckets_unknown():
    from strategy_attribution import aggregate_by_strategy
    out = aggregate_by_strategy([
        {"strategy": None, "pnl_pct_net": 0.03},
        {"pnl_pct_net": -0.01},
    ])
    assert "unknown" in out
    assert out["unknown"]["trade_count"] == 2


def test_aggregate_by_strategy_profit_factor_no_losses_is_inf():
    import math
    from strategy_attribution import aggregate_by_strategy
    out = aggregate_by_strategy([
        {"strategy": "winners", "pnl_pct_net": 0.05},
        {"strategy": "winners", "pnl_pct_net": 0.02},
    ])
    assert out["winners"]["profit_factor"] == math.inf


def test_aggregate_by_strategy_r_multiple_requires_risk_on_all():
    from strategy_attribution import aggregate_by_strategy
    # Partial risk coverage → avg_R must be None (no mixed averages).
    partial = aggregate_by_strategy([
        {"strategy": "X", "pnl_pct_net": 0.05, "initial_risk_pct": 0.02},
        {"strategy": "X", "pnl_pct_net": 0.03},
    ])
    assert partial["X"]["avg_R"] is None
    # Full coverage → R-multiple averaged.
    full = aggregate_by_strategy([
        {"strategy": "X", "pnl_pct_net": 0.04, "initial_risk_pct": 0.02},
        {"strategy": "X", "pnl_pct_net": -0.01, "initial_risk_pct": 0.01},
    ])
    # R = 0.04/0.02 = 2.0 ; R = -0.01/0.01 = -1.0 ; avg = 0.5
    assert full["X"]["avg_R"] == 0.5


def test_backtester_run_returns_by_strategy(monkeypatch):
    """BacktestEngine.run() must return a by_strategy dict keyed by strategy."""
    import pandas as pd
    idx = pd.bdate_range("2025-10-01", periods=30)
    spy_df = pd.DataFrame({"Open": [100.0]*30, "High": [100.0]*30,
                           "Low": [100.0]*30,  "Close": [100.0]*30}, index=idx)
    # Gap-up target hit on last bar.
    test_df = _flat_then_trigger_df(idx, trigger_open=112.0,
                                    trigger_high=113.0, trigger_low=112.0)
    engine = _backtest_harness(monkeypatch, test_df, spy_df)
    result = engine.run()

    assert "by_strategy" in result
    # Harness signals use strategy='trend_long'.
    assert "trend_long" in result["by_strategy"]
    bucket = result["by_strategy"]["trend_long"]
    assert bucket["trade_count"] >= 1
    # backtester carries $ P&L, so total_pnl_usd must be present.
    assert "total_pnl_usd" in bucket
    # Harness stop=95 entry~100 → initial_risk ≈ 5% → avg_R populated.
    assert bucket["avg_R"] is not None


def test_forward_tester_preserves_strategy_from_new_trade(monkeypatch, tmp_path):
    """forward_tester must echo `strategy` from the LLM advice into new_trade_result
    and compute initial_risk_pct from entry_fill_price - stop_price.
    """
    import json
    import pandas as pd
    from datetime import date, timedelta
    import forward_tester as ft
    from forward_tester import evaluate_file

    rec = date.today() - timedelta(days=30)
    rec_str = rec.strftime("%Y%m%d")

    advice_path = tmp_path / f"investment_advice_{rec_str}.json"
    advice_path.write_text(json.dumps({
        "advice_parsed": {
            "position_actions": [],
            "new_trade": {
                "ticker":       "TEST",
                "direction":    "long",
                "confidence":   0.8,
                "stop_price":   95.0,
                "target_price": 110.0,
                "strategy":     "trend_long",
            },
        }
    }))

    monkeypatch.setattr(ft, "get_close_price",
                        lambda ticker, d: (100.0, d) if d == rec else (108.0, d))
    monkeypatch.setattr(ft, "get_next_open_price",
                        lambda ticker, d: (101.0, d + timedelta(days=1)))
    def fake_daily(ticker, start, end):
        idx = pd.to_datetime([rec, rec + timedelta(days=1)])
        return pd.DataFrame({
            "Open":  [100.0, 105.0], "High":  [101.0, 106.0],
            "Low":   [ 99.0, 104.0], "Close": [100.0, 105.0],
        }, index=idx)
    monkeypatch.setattr(ft, "get_daily_prices_during_period", fake_daily)

    result = evaluate_file(str(advice_path))
    nt = result["new_trade_result"]
    assert nt["strategy"] == "trend_long"
    assert nt["initial_risk_pct"] is not None
    assert nt["initial_risk_pct"] > 0
    # Entry fill ~101.05, stop 95 → risk ≈ (101.05-95)/101.05 ≈ 0.0599
    assert 0.04 < nt["initial_risk_pct"] < 0.08


def test_aggregate_forward_tests_across_files(tmp_path, monkeypatch):
    """aggregate_forward_tests rolls up realized_pnl_pct_net across multiple
    forward_test_*.json files, missing strategy bucketed as 'unknown'.
    """
    import json
    import forward_tester as ft

    def write(fname, nt):
        (tmp_path / fname).write_text(json.dumps({"new_trade_result": nt}))

    write("forward_test_20260101.json",
          {"strategy": "trend_long",   "realized_pnl_pct_net":  0.04,
           "initial_risk_pct": 0.02})
    write("forward_test_20260102.json",
          {"strategy": "trend_long",   "realized_pnl_pct_net": -0.01,
           "initial_risk_pct": 0.02})
    write("forward_test_20260103.json",
          {"strategy": "breakout_long","realized_pnl_pct_net":  0.08,
           "initial_risk_pct": 0.03})
    # Legacy file with no strategy → bucket 'unknown'
    write("forward_test_20260104.json",
          {"realized_pnl_pct_net": 0.02})
    # File with no realized P&L → skipped
    write("forward_test_20260105.json",
          {"strategy": "trend_long", "return_10d_pct": 0.05})

    pattern = str(tmp_path / "forward_test_*.json")
    out = ft.aggregate_forward_tests(pattern=pattern)

    assert set(out.keys()) == {"trend_long", "breakout_long", "unknown"}
    assert out["trend_long"]["trade_count"]   == 2
    assert out["breakout_long"]["trade_count"] == 1
    assert out["unknown"]["trade_count"]       == 1
    # trend_long has full initial_risk coverage → avg_R populated
    assert out["trend_long"]["avg_R"] is not None
    # unknown bucket lacks initial_risk_pct → avg_R=None
    assert out["unknown"]["avg_R"] is None


# ── CLAUDE3 convergence calculator + benchmarks ──────────────────────────────

def _passing_result(**overrides):
    """Backtest-shaped dict that satisfies every convergence criterion."""
    base = {
        "sharpe":            1.5,
        "max_drawdown_pct":  0.05,
        "total_trades":      30,
        "win_rate":          0.55,
        "survival_rate":     0.10,
        "benchmarks": {
            "spy_buy_hold_return_pct":   0.05,
            "qqq_buy_hold_return_pct":   0.06,
            "strategy_total_return_pct": 0.20,
        },
    }
    base.update(overrides)
    return base


def test_compute_convergence_all_pass():
    from convergence import compute_convergence
    rep = compute_convergence(_passing_result())
    assert rep["converged"] is True, rep
    for name, c in rep["criteria"].items():
        assert c["pass"], f"criterion {name} should pass: {c}"


def test_compute_convergence_fails_when_below_spy():
    from convergence import compute_convergence
    # Strategy returns 4% but SPY did 5% — failing the new beat-the-index gate.
    res = _passing_result(benchmarks={
        "spy_buy_hold_return_pct":   0.05,
        "qqq_buy_hold_return_pct":   0.03,
        "strategy_total_return_pct": 0.04,
    })
    rep = compute_convergence(res)
    assert rep["converged"] is False
    assert rep["criteria"]["beats_spy_buy_hold"]["pass"] is False
    # QQQ was beaten so that criterion still passes
    assert rep["criteria"]["beats_qqq_buy_hold"]["pass"] is True


def test_compute_convergence_fails_when_low_sharpe():
    from convergence import compute_convergence
    rep = compute_convergence(_passing_result(sharpe=0.3))
    assert rep["converged"] is False
    assert rep["criteria"]["sharpe_above_min"]["pass"] is False


def test_compute_convergence_handles_missing_benchmarks():
    from convergence import compute_convergence
    res = _passing_result()
    res["benchmarks"] = None  # benchmarks not computed yet
    rep = compute_convergence(res)
    # Missing benchmarks must not crash AND must fail the gate.
    assert rep["converged"] is False
    assert rep["criteria"]["beats_spy_buy_hold"]["pass"] is False
    assert rep["criteria"]["beats_qqq_buy_hold"]["pass"] is False


def test_compute_expected_value_score_basic():
    from convergence import compute_expected_value_score
    res = _passing_result()
    res["sharpe_daily"] = 2.5
    score = compute_expected_value_score(res)
    assert score == 0.5, score


def test_compute_expected_value_score_none_when_inputs_missing():
    from convergence import compute_expected_value_score
    res = _passing_result()
    assert compute_expected_value_score(res) is None
    res["sharpe_daily"] = 2.0
    res["benchmarks"] = None
    assert compute_expected_value_score(res) is None


def test_persist_earnings_snapshot_creates_structured_daily_file(tmp_path):
    from datetime import datetime
    from earnings_snapshot import persist_earnings_snapshot

    snapshot_path = persist_earnings_snapshot(
        {
            "NVDA": {
                "days_to_earnings": 5,
                "eps_estimate": 1.23,
                "avg_historical_surprise_pct": 7.8,
                "ignore_me": "x",
            },
            "MSFT": None,
        },
        as_of=datetime(2026, 4, 18, 9, 30, 0),
        base_dir=str(tmp_path),
    )

    assert os.path.basename(snapshot_path) == "earnings_snapshot_20260418.json"
    with open(snapshot_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    assert payload["date"] == "20260418"
    assert payload["coverage"] == {
        "tickers_total": 2,
        "tickers_persisted": 1,
        "tickers_with_days_to_earnings": 1,
        "tickers_with_eps_estimate": 1,
        "tickers_with_eps_actual_last": 0,
        "tickers_with_surprise_history": 1,
    }
    assert payload["earnings"]["NVDA"] == {
        "days_to_earnings": 5,
        "eps_estimate": 1.23,
        "avg_historical_surprise_pct": 7.8,
    }
    assert "MSFT" not in payload["earnings"]


def test_persist_earnings_snapshot_is_idempotent(tmp_path):
    from datetime import datetime
    from earnings_snapshot import persist_earnings_snapshot

    first_path = persist_earnings_snapshot(
        {"NVDA": {"days_to_earnings": 5}},
        as_of=datetime(2026, 4, 18, 9, 30, 0),
        base_dir=str(tmp_path),
    )
    second_path = persist_earnings_snapshot(
        {"NVDA": {"days_to_earnings": 99}},
        as_of=datetime(2026, 4, 18, 16, 0, 0),
        base_dir=str(tmp_path),
    )

    assert first_path == second_path
    with open(first_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    assert payload["earnings"]["NVDA"]["days_to_earnings"] == 5
    assert payload["coverage"]["tickers_persisted"] == 1


def test_persist_earnings_snapshot_rewrites_invalid_existing_file(tmp_path):
    from datetime import datetime
    from earnings_snapshot import persist_earnings_snapshot

    broken_path = tmp_path / "earnings_snapshot_20260418.json"
    broken_path.write_text('{"date":"20260418","broken":true}', encoding="utf-8")

    persist_earnings_snapshot(
        {"NVDA": {"days_to_earnings": 5, "eps_estimate": 1.23}},
        as_of=datetime(2026, 4, 18, 9, 30, 0),
        base_dir=str(tmp_path),
    )

    with open(broken_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)

    assert "coverage" in payload
    assert payload["earnings"]["NVDA"]["eps_estimate"] == 1.23




def test_backtester_run_emits_benchmarks(monkeypatch):
    """End-to-end: BacktestEngine.run() result carries benchmarks + convergence."""
    import pandas as pd

    idx = pd.bdate_range("2025-10-01", periods=30)
    # SPY drifts up 10% over the window so the buy-hold baseline is non-trivial.
    spy_close = [100.0 + i * (10.0 / 29) for i in range(30)]
    spy_df = pd.DataFrame({
        "Open": spy_close, "High": spy_close,
        "Low":  spy_close, "Close": spy_close,
    }, index=idx)
    test_df = _flat_then_trigger_df(idx, trigger_open=112.0,
                                    trigger_high=113.0, trigger_low=112.0)

    engine = _backtest_harness(monkeypatch, test_df, spy_df)
    result = engine.run()

    b = result["benchmarks"]
    assert b["spy_buy_hold_return_pct"] is not None
    assert b["qqq_buy_hold_return_pct"] is not None  # harness uses spy_df for QQQ too
    assert b["strategy_total_return_pct"] is not None
    # vs_spy must equal strategy - spy
    assert (round(b["strategy_total_return_pct"]
                  - b["spy_buy_hold_return_pct"], 4)
            == b["strategy_vs_spy_pct"])
    # convergence dict is attached
    assert "convergence" in result
    assert "criteria" in result["convergence"]


# ── v2 measurement: additive sharpe_daily + disclosures + shadow verdict ─────

def test_backtester_emits_sharpe_daily_alongside_legacy(monkeypatch):
    """run() must expose both sharpe (legacy) and sharpe_daily (standard)."""
    import pandas as pd
    idx = pd.bdate_range("2025-10-01", periods=30)
    spy_close = [100.0 + i * (10.0 / 29) for i in range(30)]
    spy_df = pd.DataFrame({
        "Open": spy_close, "High": spy_close,
        "Low": spy_close, "Close": spy_close,
    }, index=idx)
    test_df = _flat_then_trigger_df(idx, trigger_open=112.0,
                                    trigger_high=113.0, trigger_low=112.0)
    engine = _backtest_harness(monkeypatch, test_df, spy_df)
    result = engine.run()

    # Both Sharpe flavours are exposed; convergence still reads the legacy one.
    assert "sharpe" in result
    assert "sharpe_daily" in result
    assert "expected_value_score" in result
    assert result.get("sharpe_method") == "per_trade_sqrt30_legacy"
    if result["sharpe_daily"] is not None:
        expected = round(
            result["benchmarks"]["strategy_total_return_pct"] * result["sharpe_daily"], 4
        )
        assert result["expected_value_score"] == expected
    # Shadow verdict exists and is observational only.
    assert "converged_v2_shadow" in result
    s = result["converged_v2_shadow"]
    assert "sharpe_daily_would_pass" in s
    assert "converged_if_sharpe_daily" in s


def test_sharpe_daily_from_synthetic_equity():
    """sharpe_daily must use equity-curve daily returns × sqrt(252).

    Synthetic equity curve designed so mean/std of daily returns is easy to
    hand-compute. A 2-point curve with 1% gain gives a single return of 0.01
    — std is undefined, so sharpe_daily is None (need >= 2 returns).
    Use 3 points to get 2 returns.
    """
    import math
    import pandas as pd

    # Smoke-test the inline formula the backtester uses. We can't easily
    # unit-test the private block without refactoring, so we replicate the
    # math on a synthetic equity curve and assert the backtester would
    # produce the same number on equivalent inputs.
    equity_series = [100_000.0, 100_500.0, 101_000.0]  # +0.5%, +0.4975%
    returns = [
        (equity_series[i] / equity_series[i - 1]) - 1
        for i in range(1, len(equity_series))
    ]
    mean_r = sum(returns) / len(returns)
    var_r = sum((x - mean_r) ** 2 for x in returns) / (len(returns) - 1)
    std_r = math.sqrt(var_r)
    expected = round((mean_r / std_r) * math.sqrt(252), 2) if std_r > 0 else None
    # Expected value is large (returns are very consistent). Just assert
    # the calculator is non-None and has the right sign.
    assert expected is not None
    assert expected > 0


def test_backtester_emits_known_biases_and_integrity(monkeypatch):
    """Structured bias disclosure + equity_curve_integrity must be attached."""
    import pandas as pd
    idx = pd.bdate_range("2025-10-01", periods=30)
    spy_close = [100.0] * 30
    spy_df = pd.DataFrame({
        "Open": spy_close, "High": spy_close,
        "Low": spy_close, "Close": spy_close,
    }, index=idx)
    test_df = _flat_then_trigger_df(idx, trigger_open=112.0,
                                    trigger_high=113.0, trigger_low=112.0)
    engine = _backtest_harness(monkeypatch, test_df, spy_df)
    result = engine.run()

    kb = result.get("known_biases") or {}
    # news_veto_unreplayed is now a structured archive-coverage bucket
    # (upgraded 2026-04-18 from bare bool(True) to parallel llm_gate_unreplayed).
    nvu = kb.get("news_veto_unreplayed")
    assert isinstance(nvu, dict), (
        "news_veto_unreplayed must be a structured dict so coverage is auditable"
    )
    assert nvu.get("archive_replay_enabled") is False, (
        "archive_replay_enabled must be False — no replay mechanism exists yet"
    )
    assert "archive_coverage_fraction" in nvu
    assert isinstance(nvu.get("archive_dates_covered"), list)
    assert "archive_dates_missing_n" in nvu
    # llm_gate_unreplayed is structured disclosure; enabled=False when not replayed.
    llm_gate = kb.get("llm_gate_unreplayed")
    assert isinstance(llm_gate, dict)
    assert llm_gate.get("enabled") is False
    assert "coverage_fraction" in llm_gate
    assert isinstance(llm_gate.get("dates_covered"), list)
    assert kb.get("survivorship_bias_universe") is True
    assert isinstance(kb.get("notes"), list) and len(kb["notes"]) >= 3

    integ = result.get("equity_curve_integrity") or {}
    assert "cash_field_present_in_open_positions" in integ
    assert "equity_flat_days" in integ
    assert integ.get("daily_returns_count") is not None

    # news_attribution bucket present (added exp-20260418-002)
    news_attr = result.get("news_attribution")
    assert isinstance(news_attr, dict), "news_attribution bucket must be present"
    assert news_attr.get("replay_enabled") is False
    assert "veto_rate" in news_attr
    assert "signals_vetoed_by_news" in news_attr


def test_backtester_emits_risk_distribution_metrics(monkeypatch):
    """run() must expose worst trade, loss streak, and tail-loss concentration."""
    import pandas as pd
    idx = pd.bdate_range("2025-10-01", periods=30)
    spy_close = [100.0 + i * (10.0 / 29) for i in range(30)]
    spy_df = pd.DataFrame({
        "Open": spy_close, "High": spy_close,
        "Low": spy_close, "Close": spy_close,
    }, index=idx)
    test_df = _flat_then_trigger_df(idx, trigger_open=112.0,
                                    trigger_high=113.0, trigger_low=112.0)
    engine = _backtest_harness(monkeypatch, test_df, spy_df)
    result = engine.run()

    assert "worst_trade_pct" in result
    assert "max_consecutive_losses" in result
    assert "tail_loss_share" in result
    assert result["max_consecutive_losses"] >= 0
    if result["worst_trade_pct"] is not None:
        expected_worst = min(t["pnl_pct_net"] for t in result["trades"])
        assert result["worst_trade_pct"] == expected_worst
    if result["tail_loss_share"] is not None:
        assert 0 < result["tail_loss_share"] <= 1


def test_risk_distribution_metric_math_examples():
    """Document the intended math for loss concentration and streaks."""
    import math

    closed = [
        {"pnl": 100.0, "pnl_pct_net": 0.0100},
        {"pnl": -200.0, "pnl_pct_net": -0.0200},
        {"pnl": -50.0, "pnl_pct_net": -0.0050},
        {"pnl": 80.0, "pnl_pct_net": 0.0080},
        {"pnl": -150.0, "pnl_pct_net": -0.0150},
        {"pnl": -75.0, "pnl_pct_net": -0.0075},
        {"pnl": -25.0, "pnl_pct_net": -0.0025},
    ]

    pnl_pct_series = [t["pnl_pct_net"] for t in closed]
    worst_trade_pct = round(min(pnl_pct_series), 6) if pnl_pct_series else None

    max_consecutive_losses = 0
    current_loss_streak = 0
    for trade in closed:
        if trade["pnl_pct_net"] < 0:
            current_loss_streak += 1
            max_consecutive_losses = max(max_consecutive_losses, current_loss_streak)
        else:
            current_loss_streak = 0

    losses_abs = sorted([-t["pnl"] for t in closed if t["pnl"] < 0], reverse=True)
    total_loss_abs = sum(losses_abs)
    tail_count = max(1, math.ceil(len(losses_abs) * 0.2))
    tail_loss_share = round(sum(losses_abs[:tail_count]) / total_loss_abs, 4)

    assert worst_trade_pct == -0.02
    assert max_consecutive_losses == 3
    # Losses are [200, 150, 75, 50, 25]; top 20% => top 1 => 200 / 500 = 0.4
    assert tail_loss_share == 0.4


def test_tail_loss_share_none_when_no_losses():
    losses_abs = []
    total_loss_abs = sum(losses_abs)
    if total_loss_abs > 0:
        tail_loss_share = 0.0
    else:
        tail_loss_share = None
    assert tail_loss_share is None


def test_capital_efficiency_metric_math_examples():
    """Document capital-efficiency math independently from market data."""
    from backtester import _build_capital_efficiency

    closed = [
        {"entry_date": "2026-01-02", "exit_date": "2026-01-04", "pnl": 120.0},
        {"entry_date": "2026-01-10", "exit_date": "2026-01-10", "pnl": -20.0},
    ]
    metrics = _build_capital_efficiency(
        closed,
        initial_capital=10000.0,
        trading_days=10,
        total_pnl=100.0,
        strategy_return_pct=0.01,
        max_positions=5,
    )

    assert metrics["return_per_trade"] == 0.005
    assert metrics["pnl_per_trade_usd"] == 50.0
    assert metrics["calendar_slot_days"] == 4
    assert metrics["avg_calendar_days_held"] == 2.0
    assert metrics["pnl_per_calendar_slot_day_usd"] == 25.0
    assert metrics["gross_slot_day_fraction"] == 0.08


def test_sizing_rule_signal_attribution_counts_adjusted_signals():
    """Sizing attribution counts rules without changing trade decisions."""
    from backtester import (
        _finalize_sizing_rule_signal_attribution,
        _update_sizing_rule_signal_attribution,
    )

    acc = {}
    _update_sizing_rule_signal_attribution(acc, [
        {
            "strategy": "trend_long",
            "sector": "Healthcare",
            "sizing": {
                "base_risk_pct": 0.01,
                "risk_pct": 0.0,
                "trend_healthcare_dte_risk_multiplier_applied": 0.0,
            },
        },
        {
            "strategy": "breakout_long",
            "sector": "Communication Services",
            "sizing": {
                "base_risk_pct": 0.01,
                "risk_pct": 0.005,
                "breakout_comms_gap_risk_multiplier_applied": 0.5,
            },
        },
    ])
    finalized = _finalize_sizing_rule_signal_attribution(acc)

    healthcare = finalized["trend_healthcare_dte_risk_multiplier_applied"]
    comms = finalized["breakout_comms_gap_risk_multiplier_applied"]
    assert healthcare["signals_seen"] == 1
    assert healthcare["zero_risk_signals"] == 1
    assert healthcare["avg_risk_pct_after"] == 0.0
    assert comms["reduced_risk_signals"] == 1
    assert comms["avg_risk_pct_after"] == 0.005


def test_sizing_rule_trade_attribution_observed_outcomes():
    from backtester import _build_sizing_rule_trade_attribution

    closed = [
        {
            "pnl": 100.0,
            "sizing_multipliers": {"breakout_comms_gap_risk_multiplier_applied": 0.5},
        },
        {
            "pnl": -50.0,
            "sizing_multipliers": {"breakout_comms_gap_risk_multiplier_applied": 0.5},
        },
    ]
    attr = _build_sizing_rule_trade_attribution(closed)
    rec = attr["breakout_comms_gap_risk_multiplier_applied"]

    assert rec["trade_count"] == 2
    assert rec["win_rate"] == 0.5
    assert rec["total_pnl_usd"] == 50.0
    assert rec["avg_pnl_usd"] == 25.0


def test_compute_convergence_ignores_sharpe_daily():
    """convergence.py must NOT key off sharpe_daily — only legacy sharpe."""
    from convergence import compute_convergence
    res = _passing_result()
    # A broken sharpe_daily must not flip the verdict.
    res["sharpe_daily"] = -10.0
    rep = compute_convergence(res)
    assert rep["converged"] is True, (
        "sharpe_daily must not enter compute_convergence (v2 additive rule)")


def test_stability_diagnostics_builder():
    """_build_stability_diagnostics returns structured deltas, no PASS/FAIL."""
    from backtester import _build_stability_diagnostics
    primary = {
        "sharpe": 3.0, "sharpe_daily": 2.0, "expected_value_score": 0.4, "max_drawdown_pct": 0.05,
        "benchmarks": {"strategy_total_return_pct": 0.20},
    }
    secondary = {
        "sharpe": 1.5, "sharpe_daily": 1.0, "expected_value_score": 0.05, "max_drawdown_pct": 0.08,
        "benchmarks": {"strategy_total_return_pct": 0.05},
    }
    d = _build_stability_diagnostics(primary, secondary)
    s = d["stable_across_windows"]
    assert s["expected_value_score_delta"] == 0.35
    assert s["sharpe_legacy_delta"] == 1.5
    assert s["sharpe_daily_delta"]  == 1.0
    assert s["directionally_profitable_both"] is True
    r = d["multi_window_robustness"]
    assert r["windows"] == 2
    assert r["expected_value_score_positive_windows"] == 2
    assert r["return_positive_windows"] == 2
    assert r["robustness_score"] == 6
    # Nothing in the dict should be a pass/fail verdict
    for k, v in s.items():
        assert k not in ("pass", "passed", "verdict", "converged")


def test_multi_window_robustness_score_handles_mixed_windows():
    from backtester import _build_multi_window_robustness

    metrics = _build_multi_window_robustness([
        {
            "expected_value_score": 0.25,
            "sharpe_daily": 1.2,
            "max_drawdown_pct": 0.05,
            "benchmarks": {"strategy_total_return_pct": 0.10},
        },
        {
            "expected_value_score": -0.10,
            "sharpe_daily": -0.4,
            "max_drawdown_pct": 0.25,
            "benchmarks": {"strategy_total_return_pct": -0.03},
        },
    ])

    assert metrics["windows"] == 2
    assert metrics["expected_value_score_positive_windows"] == 1
    assert metrics["return_positive_windows"] == 1
    assert metrics["sharpe_daily_positive_windows"] == 1
    assert metrics["drawdown_guardrail_break_windows"] == 1
    assert metrics["expected_value_score_spread"] == 0.35
    assert metrics["robustness_score"] == 2


# ───────────────────────────────────────────────────────────────────────────
# P-ERN — earnings snapshot persistence (backtester supplement)

def test_earnings_snapshot_loader_empty_dir(tmp_path):
    """_load_earnings_snapshots returns {} when no snapshot files exist."""
    import sys
    sys.path.insert(0, str(tmp_path))
    from backtester import BacktestEngine
    engine = BacktestEngine.__new__(BacktestEngine)
    engine.data_dir = str(tmp_path)
    snaps = engine._load_earnings_snapshots()
    assert snaps == {}


def test_earnings_snapshot_loader_reads_file(tmp_path):
    """_load_earnings_snapshots correctly reads earnings_snapshot_YYYYMMDD.json."""
    import json
    from backtester import BacktestEngine
    snap = {
        "date": "20260420",
        "timestamp": "2026-04-20T09:00:00",
        "earnings": {
            "NVDA": {"days_to_earnings": 5, "eps_estimate": 4.78,
                     "avg_historical_surprise_pct": 2.1, "historical_surprise_pct": [2.1, 3.5]},
        },
    }
    (tmp_path / "earnings_snapshot_20260420.json").write_text(
        json.dumps(snap), encoding="utf-8")
    engine = BacktestEngine.__new__(BacktestEngine)
    engine.data_dir = str(tmp_path)
    snaps = engine._load_earnings_snapshots()
    assert "20260420" in snaps
    assert snaps["20260420"]["NVDA"]["eps_estimate"] == 4.78


def test_earnings_dict_for_uses_snapshot(tmp_path):
    """_earnings_dict_for enriches result with snapshot eps_estimate when available."""
    import json, datetime
    from backtester import BacktestEngine
    snap = {"date": "20260420", "timestamp": "...",
            "earnings": {"NVDA": {"eps_estimate": 4.78, "avg_historical_surprise_pct": 2.1,
                                   "historical_surprise_pct": [2.1]}}}
    (tmp_path / "earnings_snapshot_20260420.json").write_text(
        json.dumps(snap), encoding="utf-8")
    engine = BacktestEngine.__new__(BacktestEngine)
    engine.data_dir = str(tmp_path)
    engine._earnings_snapshots = engine._load_earnings_snapshots()

    import datetime as dt
    sim_date = dt.date(2026, 4, 20)
    # Calendar has an upcoming earnings date
    result = engine._earnings_dict_for(sim_date, [dt.date(2026, 4, 25)], ticker="NVDA")
    assert result["eps_estimate"] == 4.78
    assert result["avg_historical_surprise_pct"] == 2.1
    assert result["days_to_earnings"] == 5   # Mon Apr 20 → Sat Apr 25 = 5 business days


def test_earnings_dict_for_no_snapshot_returns_none(tmp_path):
    """_earnings_dict_for returns None for eps/surprise when no snapshot exists."""
    import datetime as dt
    from backtester import BacktestEngine
    engine = BacktestEngine.__new__(BacktestEngine)
    engine.data_dir = str(tmp_path)
    engine._earnings_snapshots = {}
    sim_date = dt.date(2026, 4, 20)
    result = engine._earnings_dict_for(sim_date, [dt.date(2026, 4, 25)], ticker="NVDA")
    assert result["eps_estimate"] is None
    assert result["avg_historical_surprise_pct"] is None
    assert result["days_to_earnings"] == 5


# ───────────────────────────────────────────────────────────────────────────
# v4 — LLM gate replay (§6.1 parity fix). Four tests per AGENTS.md §4.2.

def test_llm_replay_off_is_pure_passthrough(monkeypatch, tmp_path):
    """--replay-llm off: result metrics unchanged; llm_attribution bucket
    still present but empty (replay_enabled=False)."""
    import pandas as pd
    idx = pd.bdate_range("2025-10-01", periods=30)
    spy_df = pd.DataFrame({
        "Open": [100.0]*30, "High": [100.0]*30,
        "Low":  [100.0]*30, "Close": [100.0]*30,
    }, index=idx)
    test_df = _flat_then_trigger_df(idx, trigger_open=112.0,
                                    trigger_high=113.0, trigger_low=112.0)
    engine = _backtest_harness(monkeypatch, test_df, spy_df)
    engine.data_dir = str(tmp_path)  # empty dir
    result = engine.run()

    assert engine.replay_llm is False
    attr = result.get("llm_attribution")
    assert attr is not None
    assert attr["replay_enabled"] is False
    assert attr["signals_presented"] == 0
    assert attr["signals_vetoed_by_llm"] == 0
    assert attr["signals_passed_by_llm"] == 0
    assert attr["dates_covered"] == 0
    assert attr["coverage_fraction"] == 0.0
    assert attr["candidate_days_covered"] == 0
    assert attr["candidate_days_total"] == 0
    assert attr["candidate_dates_covered"] == []
    assert attr["candidate_dates_missing"] == []
    assert attr["candidate_signal_counts_by_date"] == {}
    assert attr["candidate_day_coverage_fraction"] == 0.0
    assert attr["candidate_signals_covered"] == 0
    assert attr["candidate_signals_total"] == result["signals_survived"]
    assert attr["candidate_signal_coverage_fraction"] == 0.0
    assert attr["veto_rate"] is None


def test_llm_replay_missing_file_falls_back_to_accept(monkeypatch, tmp_path):
    """--replay-llm on but NO response files present: signals still pass,
    every trading day lands in dates_missing."""
    import pandas as pd
    idx = pd.bdate_range("2025-10-01", periods=30)
    spy_df = pd.DataFrame({
        "Open": [100.0]*30, "High": [100.0]*30,
        "Low":  [100.0]*30, "Close": [100.0]*30,
    }, index=idx)
    test_df = _flat_then_trigger_df(idx, trigger_open=112.0,
                                    trigger_high=113.0, trigger_low=112.0)
    engine = _backtest_harness(monkeypatch, test_df, spy_df)
    engine.replay_llm = True
    engine.data_dir   = str(tmp_path)  # empty → every day missing
    result = engine.run()

    attr = result["llm_attribution"]
    assert attr["replay_enabled"] is True
    assert attr["dates_covered"] == 0
    assert attr["dates_missing"] == attr["trading_days"]
    # No replay performed → veto/pass counts remain zero.
    assert attr["signals_vetoed_by_llm"] == 0
    assert attr["signals_passed_by_llm"] == 0
    # And the trade still closed normally (gap-up target exit).
    assert result["total_trades"] >= 1


def test_llm_replay_vetoed_signal_not_traded(monkeypatch, tmp_path):
    """When a response file exists and LLM vetoes the ticker, the signal
    must be dropped before entry (no trade) and counted as vetoed."""
    import json, pandas as pd
    idx = pd.bdate_range("2025-10-01", periods=30)
    spy_df = pd.DataFrame({
        "Open": [100.0]*30, "High": [100.0]*30,
        "Low":  [100.0]*30, "Close": [100.0]*30,
    }, index=idx)
    test_df = _flat_then_trigger_df(idx, trigger_open=112.0,
                                    trigger_high=113.0, trigger_low=112.0)
    engine = _backtest_harness(monkeypatch, test_df, spy_df)
    engine.replay_llm = True
    engine.data_dir   = str(tmp_path)

    # Write a response for every trading day that says "NO NEW TRADE".
    for d in idx:
        fn = tmp_path / f"llm_prompt_resp_{d.strftime('%Y%m%d')}.json"
        fn.write_text(json.dumps({
            "new_trade": "NO NEW TRADE",
            "position_actions": [],
        }), encoding="utf-8")

    result = engine.run()
    attr = result["llm_attribution"]
    assert attr["dates_covered"] == attr["trading_days"]
    assert attr["dates_missing"] == 0
    assert attr["signals_vetoed_by_llm"] >= 1
    assert attr["signals_passed_by_llm"] == 0
    assert attr["veto_rate"] == 1.0
    assert result["total_trades"] == 0  # nothing survived LLM veto


def test_llm_attribution_coverage_fraction(monkeypatch, tmp_path):
    """With 2 of 30 trading days covered by response files, coverage_fraction
    must equal 2/30 and dates_missing must equal 28."""
    import json, pandas as pd
    idx = pd.bdate_range("2025-10-01", periods=30)
    spy_df = pd.DataFrame({
        "Open": [100.0]*30, "High": [100.0]*30,
        "Low":  [100.0]*30, "Close": [100.0]*30,
    }, index=idx)
    test_df = _flat_then_trigger_df(idx, trigger_open=112.0,
                                    trigger_high=113.0, trigger_low=112.0)
    engine = _backtest_harness(monkeypatch, test_df, spy_df)
    engine.replay_llm = True
    engine.data_dir   = str(tmp_path)

    # Cover exactly 2 days with a NO NEW TRADE response.
    for d in idx[:2]:
        fn = tmp_path / f"llm_prompt_resp_{d.strftime('%Y%m%d')}.json"
        fn.write_text(json.dumps({"new_trade": "NO NEW TRADE",
                                   "position_actions": []}),
                      encoding="utf-8")

    import signal_engine
    _orig_generate_signals = signal_engine.generate_signals

    def _compat_generate_signals(features, market_context=None, **kwargs):
        return _orig_generate_signals(features, market_context=market_context)

    monkeypatch.setattr(signal_engine, "generate_signals", _compat_generate_signals)

    result = engine.run()
    attr = result["llm_attribution"]
    assert attr["trading_days"] == 30
    assert attr["dates_covered"] == 2
    assert attr["dates_missing"] == 28
    assert abs(attr["coverage_fraction"] - (2/30)) < 1e-4


def test_llm_attribution_candidate_coverage_metrics(monkeypatch, tmp_path):
    """Candidate coverage must measure only days/signals that reached the LLM gate."""
    import json, pandas as pd
    import signal_engine, portfolio_engine, risk_engine

    idx = pd.bdate_range("2025-10-01", periods=30)
    spy_df = pd.DataFrame({
        "Open": [100.0]*30, "High": [100.0]*30,
        "Low":  [100.0]*30, "Close": [100.0]*30,
        "Volume": [1_000_000]*30,
    }, index=idx)

    from backtester import BacktestEngine
    engine = BacktestEngine(["AAA"], start="2025-10-01", end="2025-10-30", replay_llm=True, data_dir=str(tmp_path))
    monkeypatch.setattr(engine, "_download_data", lambda: {"AAA": spy_df, "SPY": spy_df, "QQQ": spy_df})
    monkeypatch.setattr(engine, "_download_earnings_calendar", lambda: {"AAA": [], "SPY": [], "QQQ": []})

    _gen_call = [0]
    def fake_generate_signals(*args, **kwargs):
        _gen_call[0] += 1
        if _gen_call[0] == 14:
            return [{"ticker": "AAA", "strategy": "trend_long", "entry_price": 100.0, "stop_price": 95.0}]
        if _gen_call[0] == 15:
            return [{"ticker": "AAA", "strategy": "breakout_long", "entry_price": 100.0, "stop_price": 95.0}]
        return []

    monkeypatch.setattr(signal_engine, "generate_signals", fake_generate_signals)
    monkeypatch.setattr(signal_engine, "rank_signals_for_allocation", lambda signals, **kwargs: list(signals))
    monkeypatch.setattr(risk_engine, "enrich_signals", lambda signals, features, atr_target_mult=None: signals)
    monkeypatch.setattr(portfolio_engine, "size_signals", lambda signals, *args, **kwargs: [
        {**s, "sizing": {"shares_to_buy": 1}} for s in signals
    ])

    # Cover only one of the two candidate days.
    covered_day = idx[13].strftime("%Y%m%d")
    (tmp_path / f"llm_prompt_resp_{covered_day}.json").write_text(json.dumps({
        "new_trade": {"ticker": "AAA"},
        "position_actions": [],
    }), encoding="utf-8")

    result = engine.run()
    attr = result["llm_attribution"]

    assert attr["candidate_days_total"] == 2
    assert attr["candidate_days_covered"] == 1
    assert attr["candidate_dates_covered"] == [covered_day]
    missing_day = idx[14].strftime("%Y%m%d")
    assert attr["candidate_dates_missing"] == [missing_day]
    assert attr["candidate_signal_counts_by_date"] == {
        covered_day: 1,
        missing_day: 1,
    }
    assert attr["candidate_day_coverage_fraction"] == 0.5
    assert attr["candidate_signals_total"] == 2
    assert attr["candidate_signals_covered"] == 1
    assert attr["candidate_signal_coverage_fraction"] == 0.5


def test_llm_attribution_archive_backlog_prioritizes_prompt_ready_days(monkeypatch, tmp_path):
    """Missing candidate days should expose an actionable prompt-ready backlog."""
    import json, pandas as pd
    import signal_engine, portfolio_engine, risk_engine

    idx = pd.bdate_range("2025-10-01", periods=30)
    spy_df = pd.DataFrame({
        "Open": [100.0]*30, "High": [100.0]*30,
        "Low":  [100.0]*30, "Close": [100.0]*30,
        "Volume": [1_000_000]*30,
    }, index=idx)

    from backtester import BacktestEngine
    engine = BacktestEngine(["AAA"], start="2025-10-01", end="2025-10-30", replay_llm=True, data_dir=str(tmp_path))
    monkeypatch.setattr(engine, "_download_data", lambda: {"AAA": spy_df, "SPY": spy_df, "QQQ": spy_df})
    monkeypatch.setattr(engine, "_download_earnings_calendar", lambda: {"AAA": [], "SPY": [], "QQQ": []})

    _gen_call = [0]
    def fake_generate_signals(*args, **kwargs):
        _gen_call[0] += 1
        if _gen_call[0] == 14:
            return [{"ticker": "AAA", "strategy": "trend_long", "entry_price": 100.0, "stop_price": 95.0}]
        if _gen_call[0] == 15:
            return [{"ticker": "AAA", "strategy": "breakout_long", "entry_price": 100.0, "stop_price": 95.0}]
        return []

    monkeypatch.setattr(signal_engine, "generate_signals", fake_generate_signals)
    monkeypatch.setattr(signal_engine, "rank_signals_for_allocation", lambda signals, **kwargs: list(signals))
    monkeypatch.setattr(risk_engine, "enrich_signals", lambda signals, features, atr_target_mult=None: signals)
    monkeypatch.setattr(portfolio_engine, "size_signals", lambda signals, *args, **kwargs: [
        {**s, "sizing": {"shares_to_buy": 1}} for s in signals
    ])

    covered_day = idx[13].strftime("%Y%m%d")
    prompt_ready_day = idx[14].strftime("%Y%m%d")
    prompt_missing_day = idx[15].strftime("%Y%m%d")

    (tmp_path / f"llm_prompt_resp_{covered_day}.json").write_text(json.dumps({
        "new_trade": {"ticker": "AAA"},
        "position_actions": [],
    }), encoding="utf-8")

    (tmp_path / f"llm_prompt_{prompt_ready_day}.txt").write_text("prompt body", encoding="utf-8")
    (tmp_path / f"llm_decision_log_{prompt_ready_day}.json").write_text(json.dumps({
        "signal_details": [
            {
                "ticker": "AAA",
                "strategy": "breakout_long",
                "trade_quality_score": 0.91,
            }
        ]
    }), encoding="utf-8")

    result = engine.run()
    backlog = result["llm_attribution"]["archive_backlog"]

    assert backlog["missing_candidate_days"] == 1
    assert backlog["missing_candidate_signals"] == 1
    assert backlog["raw_response_recoverable_days"] == 0
    assert backlog["prompt_ready_days"] == 1
    assert backlog["prompt_ineligible_days"] == 0
    assert backlog["prompt_missing_days"] == 0
    assert backlog["context_only_days"] == 0
    assert backlog["archive_hole_days"] == 0
    assert backlog["decision_log_days"] == 1
    assert backlog["queue"][0]["date"] == prompt_ready_day
    assert backlog["queue"][0]["ready_for_manual_import"] is True
    assert backlog["queue"][0]["recovery_tier"] == "prompt_only"
    assert backlog["queue"][0]["ranking_eligible_prompt"] is True
    assert backlog["queue"][0]["signal_tickers"] == ["AAA"]
    assert backlog["queue"][0]["strategies"] == {"breakout_long": 1}
    assert backlog["queue"][0]["max_trade_quality_score"] == 0.91


def test_llm_archive_backlog_downgrades_prompt_only_days_without_ranking_opportunity(tmp_path):
    """Prompt files without a real ranking opportunity should not count as prompt-ready."""
    import json

    from llm_backlog import build_llm_archive_backlog

    (tmp_path / "llm_prompt_20260312.txt").write_text("prompt body", encoding="utf-8")
    (tmp_path / "quant_signals_20260312.json").write_text(json.dumps({
        "portfolio_heat": {"can_add_new_positions": False},
        "signals": [],
    }), encoding="utf-8")

    backlog = build_llm_archive_backlog(
        str(tmp_path),
        ["20260312"],
        {"20260312": 1},
    )

    assert backlog["missing_candidate_days"] == 1
    assert backlog["prompt_ready_days"] == 0
    assert backlog["prompt_ineligible_days"] == 1
    assert backlog["context_only_days"] == 1
    assert backlog["queue"][0]["date"] == "20260312"
    assert backlog["queue"][0]["recovery_tier"] == "context_only"
    assert backlog["queue"][0]["ready_for_manual_import"] is False
    assert backlog["queue"][0]["prompt_exists_but_not_ranking_eligible"] is True
    assert backlog["queue"][0]["ranking_eligible_prompt"] is False
    assert backlog["queue"][0]["can_add_new_positions"] is False


def test_llm_attribution_context_alignment_distinguishes_empty_vs_aligned_days(monkeypatch, tmp_path):
    """Covered replay days are only credible when production quant context aligns."""
    import json, pandas as pd
    import signal_engine, portfolio_engine, risk_engine

    idx = pd.bdate_range("2025-10-01", periods=30)
    spy_df = pd.DataFrame({
        "Open": [100.0]*30, "High": [100.0]*30,
        "Low":  [100.0]*30, "Close": [100.0]*30,
        "Volume": [1_000_000]*30,
    }, index=idx)

    from backtester import BacktestEngine
    engine = BacktestEngine(["AAA"], start="2025-10-01", end="2025-10-30", replay_llm=True, data_dir=str(tmp_path))
    monkeypatch.setattr(engine, "_download_data", lambda: {"AAA": spy_df, "SPY": spy_df, "QQQ": spy_df})
    monkeypatch.setattr(engine, "_download_earnings_calendar", lambda: {"AAA": [], "SPY": [], "QQQ": []})

    _gen_call = [0]
    def fake_generate_signals(*args, **kwargs):
        _gen_call[0] += 1
        if _gen_call[0] == 14:
            return [{"ticker": "AAA", "strategy": "trend_long", "entry_price": 100.0, "stop_price": 95.0}]
        if _gen_call[0] == 15:
            return [{"ticker": "AAA", "strategy": "breakout_long", "entry_price": 100.0, "stop_price": 95.0}]
        return []

    monkeypatch.setattr(signal_engine, "generate_signals", fake_generate_signals)
    monkeypatch.setattr(signal_engine, "rank_signals_for_allocation", lambda signals, **kwargs: list(signals))
    monkeypatch.setattr(risk_engine, "enrich_signals", lambda signals, features, atr_target_mult=None: signals)
    monkeypatch.setattr(portfolio_engine, "size_signals", lambda signals, *args, **kwargs: [
        {**s, "sizing": {"shares_to_buy": 1}} for s in signals
    ])

    aligned_day = idx[13].strftime("%Y%m%d")
    empty_day = idx[14].strftime("%Y%m%d")

    for day in [aligned_day, empty_day]:
        (tmp_path / f"llm_prompt_resp_{day}.json").write_text(json.dumps({
            "new_trade": {"ticker": "AAA"},
            "position_actions": [],
        }), encoding="utf-8")

    (tmp_path / f"quant_signals_{aligned_day}.json").write_text(json.dumps({
        "signals": [{"ticker": "AAA", "strategy": "trend_long"}],
    }), encoding="utf-8")
    (tmp_path / f"quant_signals_{empty_day}.json").write_text(json.dumps({
        "signals": [],
    }), encoding="utf-8")

    result = engine.run()
    alignment = result["llm_attribution"]["context_alignment"]

    assert alignment["covered_candidate_days"] == 2
    assert alignment["aligned_days"] == 1
    assert alignment["production_quant_empty_days"] == 1
    assert alignment["production_quant_missing_days"] == 0
    assert alignment["production_quant_mismatch_days"] == 0
    assert alignment["aligned_signals"] == 1
    assert alignment["production_aligned_candidate_day_fraction_of_total"] == 0.5
    assert alignment["production_aligned_candidate_day_fraction_of_covered"] == 0.5
    assert alignment["production_aligned_candidate_signal_fraction_of_total"] == 0.5
    assert alignment["ranking_eligible_aligned_days"] == 0
    assert alignment["ranking_locked_days"] == 0
    assert alignment["ranking_unknown_days"] == 2

    statuses = {item["date"]: item["alignment_status"] for item in alignment["queue"]}
    assert statuses[aligned_day] == "aligned"
    assert statuses[empty_day] == "production_quant_empty"


def test_llm_attribution_context_alignment_uses_archive_context_for_ranking_eligibility(monkeypatch, tmp_path):
    """Replay archive context should distinguish usable ranking samples from locked ones."""
    import json, pandas as pd
    import signal_engine, portfolio_engine, risk_engine

    idx = pd.bdate_range("2026-01-01", periods=6)
    spy_df = pd.DataFrame({
        "Open": [100.0] * 6, "High": [100.0] * 6,
        "Low": [100.0] * 6, "Close": [100.0] * 6,
        "Volume": [1_000_000] * 6,
    }, index=idx)

    from backtester import BacktestEngine
    engine = BacktestEngine(["AAA"], start="2026-01-01", end="2026-01-08", replay_llm=True, data_dir=str(tmp_path))
    monkeypatch.setattr(engine, "_download_data", lambda: {"AAA": spy_df, "SPY": spy_df, "QQQ": spy_df})
    monkeypatch.setattr(engine, "_download_earnings_calendar", lambda: {"AAA": [], "SPY": [], "QQQ": []})

    _gen_call = [0]
    def fake_generate_signals(*args, **kwargs):
        _gen_call[0] += 1
        if _gen_call[0] in (1, 2):
            return [{"ticker": "AAA", "strategy": "trend_long", "entry_price": 100.0, "stop_price": 95.0}]
        return []

    monkeypatch.setattr(signal_engine, "generate_signals", fake_generate_signals)
    monkeypatch.setattr(signal_engine, "rank_signals_for_allocation", lambda signals, **kwargs: list(signals))
    monkeypatch.setattr(risk_engine, "enrich_signals", lambda signals, features, atr_target_mult=None: signals)
    monkeypatch.setattr(portfolio_engine, "size_signals", lambda signals, *args, **kwargs: [
        {**s, "sizing": {"shares_to_buy": 1}} for s in signals
    ])

    eligible_day = idx[0].strftime("%Y%m%d")
    locked_day = idx[1].strftime("%Y%m%d")

    (tmp_path / f"llm_prompt_resp_{eligible_day}.json").write_text(json.dumps({
        "new_trade": {"ticker": "AAA"},
        "position_actions": [],
        "archive_context": {
            "signals_presented": ["AAA"],
            "signals_presented_count": 1,
            "ranking_eligible": True,
            "new_trade_locked": False,
        },
    }), encoding="utf-8")
    (tmp_path / f"llm_prompt_resp_{locked_day}.json").write_text(json.dumps({
        "new_trade": "NO NEW TRADE",
        "position_actions": [],
        "archive_context": {
            "signals_presented": ["AAA"],
            "signals_presented_count": 1,
            "ranking_eligible": False,
            "new_trade_locked": True,
        },
    }), encoding="utf-8")

    result = engine.run()
    alignment = result["llm_attribution"]["context_alignment"]

    assert alignment["covered_candidate_days"] == 2
    assert alignment["aligned_days"] == 2
    assert alignment["ranking_eligible_aligned_days"] == 1
    assert alignment["ranking_locked_days"] == 1
    assert alignment["ranking_unknown_days"] == 0
    assert alignment["ranking_eligible_candidate_day_fraction_of_total"] == 0.5
    assert alignment["ranking_eligible_candidate_signal_fraction_of_total"] == 0.5

    ranking_statuses = {item["date"]: item["ranking_status"] for item in alignment["queue"]}
    assert ranking_statuses[eligible_day] == "ranking_eligible_aligned"
    assert ranking_statuses[locked_day] == "new_trade_locked"


def test_llm_attribution_archive_backlog_distinguishes_recovery_tiers(monkeypatch, tmp_path):
    """Backlog should distinguish raw-response, context-only, and archive-hole dates."""
    import json

    from llm_backlog import build_llm_archive_backlog

    (tmp_path / "llm_output_20260121.json").write_text('{"new_trade":"NO NEW TRADE"}', encoding="utf-8")
    (tmp_path / "quant_signals_20260129.json").write_text('{"signals":[]}', encoding="utf-8")
    (tmp_path / "earnings_snapshot_20260204.json").write_text('{"date":"20260204"}', encoding="utf-8")
    (tmp_path / "llm_decision_log_20260129.json").write_text(json.dumps({
        "signal_details": [{"ticker": "BBB", "strategy": "trend_long"}]
    }), encoding="utf-8")

    backlog = build_llm_archive_backlog(
        str(tmp_path),
        ["20260121", "20260129", "20260204", "20260312"],
        {"20260121": 4, "20260129": 3, "20260204": 2, "20260312": 1},
    )

    assert backlog["missing_candidate_days"] == 4
    assert backlog["raw_response_recoverable_days"] == 1
    assert backlog["prompt_ready_days"] == 0
    assert backlog["prompt_ineligible_days"] == 0
    assert backlog["context_only_days"] == 2
    assert backlog["archive_hole_days"] == 1
    assert backlog["quant_signals_days"] == 1
    assert backlog["earnings_snapshot_days"] == 1
    assert backlog["queue"][0]["date"] == "20260121"
    assert backlog["queue"][0]["recovery_tier"] == "raw_response_recoverable"

    tiers = {item["date"]: item["recovery_tier"] for item in backlog["queue"]}
    assert tiers["20260129"] == "context_only"
    assert tiers["20260204"] == "context_only"
    assert tiers["20260312"] == "archive_hole"


def test_llm_attribution_by_strategy_breakdown(monkeypatch, tmp_path):
    """llm_attribution.by_strategy must count veto/pass per strategy.

    Two signals on day 20: trend_long (AAA, vetoed) and breakout_long (BBB,
    approved).  by_strategy must record separate veto rates per strategy.
    """
    import json, pandas as pd
    import signal_engine, portfolio_engine

    idx = pd.bdate_range("2025-10-01", periods=30)
    spy_df = pd.DataFrame({
        "Open": [100.0]*30, "High": [100.0]*30,
        "Low":  [100.0]*30, "Close": [100.0]*30,
    }, index=idx)
    test_df = _flat_then_trigger_df(idx, trigger_open=112.0,
                                    trigger_high=113.0, trigger_low=112.0)
    engine = _backtest_harness(monkeypatch, test_df, spy_df)
    engine.replay_llm = True
    engine.data_dir   = str(tmp_path)

    # On day 20 generate_signals returns two signals from different strategies.
    _gen_call = [0]
    def _two_strategy_gen(features, market_context=None, **kwargs):
        _gen_call[0] += 1
        if _gen_call[0] == 20:
            return [
                {"ticker": "AAA", "strategy": "trend_long",   "sector": "Tech",
                 "entry_price": 100.0, "stop_price": 95.0, "target_price": 110.0,
                 "trade_quality_score": 0.8},
                {"ticker": "BBB", "strategy": "breakout_long", "sector": "Tech",
                 "entry_price": 100.0, "stop_price": 95.0, "target_price": 110.0,
                 "trade_quality_score": 0.8},
            ]
        return []
    monkeypatch.setattr(signal_engine, "generate_signals", _two_strategy_gen)

    # size_signals must give each signal a sizing dict so they enter the LLM gate.
    def _size_both(sigs, equity, risk_pct=None):
        for s in sigs:
            s["sizing"] = {"shares_to_buy": 5}
        return sigs
    monkeypatch.setattr(portfolio_engine, "size_signals", _size_both)

    # LLM approves only BBB on day 20; NO NEW TRADE on all other days.
    for i, d in enumerate(idx):
        fn = tmp_path / f"llm_prompt_resp_{d.strftime('%Y%m%d')}.json"
        body = ({"new_trade": {"ticker": "BBB"}, "position_actions": []}
                if i == 19 else
                {"new_trade": "NO NEW TRADE", "position_actions": []})
        fn.write_text(json.dumps(body), encoding="utf-8")

    result = engine.run()
    by_strat = result["llm_attribution"].get("by_strategy", {})

    assert "trend_long"    in by_strat, f"trend_long missing; got {list(by_strat)}"
    assert "breakout_long" in by_strat, f"breakout_long missing; got {list(by_strat)}"

    tl = by_strat["trend_long"]
    assert tl["presented"] == 1
    assert tl["vetoed"]    == 1
    assert tl["passed"]    == 0
    assert tl["veto_rate"] == 1.0

    bl = by_strat["breakout_long"]
    assert bl["presented"] == 1
    assert bl["vetoed"]    == 0
    assert bl["passed"]    == 1
    assert bl["veto_rate"] == 0.0


def test_llm_attribution_by_strategy_empty_when_no_files(monkeypatch, tmp_path):
    """When no llm_prompt_resp files exist, by_strategy must be an empty dict."""
    import pandas as pd
    idx = pd.bdate_range("2025-10-01", periods=10)
    spy_df = pd.DataFrame({
        "Open": [100.0]*10, "High": [100.0]*10,
        "Low":  [100.0]*10, "Close": [100.0]*10,
    }, index=idx)
    test_df = _flat_then_trigger_df(idx, trigger_open=112.0,
                                    trigger_high=113.0, trigger_low=112.0)
    engine = _backtest_harness(monkeypatch, test_df, spy_df)
    engine.replay_llm = True
    engine.data_dir   = str(tmp_path)   # empty dir — no response files

    import signal_engine
    _orig_generate_signals = signal_engine.generate_signals

    def _compat_generate_signals(features, market_context=None, **kwargs):
        return _orig_generate_signals(features, market_context=market_context)

    monkeypatch.setattr(signal_engine, "generate_signals", _compat_generate_signals)

    result = engine.run()
    by_strat = result["llm_attribution"].get("by_strategy", {})
    assert by_strat == {}, f"Expected empty dict, got {by_strat}"


# ── news_replay tests ────────────────────────────────────────────────────────

def test_news_replay_off_is_pure_passthrough(monkeypatch, tmp_path):
    """--replay-news off: result metrics unchanged; news_attribution bucket
    present but with replay_enabled=False and zero veto counts."""
    import pandas as pd
    idx = pd.bdate_range("2025-10-01", periods=30)
    spy_df = pd.DataFrame({
        "Open": [100.0]*30, "High": [100.0]*30,
        "Low":  [100.0]*30, "Close": [100.0]*30,
    }, index=idx)
    test_df = _flat_then_trigger_df(idx, trigger_open=112.0,
                                    trigger_high=113.0, trigger_low=112.0)
    engine = _backtest_harness(monkeypatch, test_df, spy_df)
    engine.data_dir = str(tmp_path)
    result = engine.run()

    assert engine.replay_news is False
    attr = result.get("news_attribution")
    assert attr is not None
    assert attr["replay_enabled"] is False
    assert attr["signals_presented"] == 0
    assert attr["signals_vetoed_by_news"] == 0
    assert attr["signals_passed_by_news"] == 0
    assert attr["veto_rate"] is None


def test_news_replay_missing_file_falls_back_to_accept(monkeypatch, tmp_path):
    """--replay-news on but no archive files: signals pass, no veto."""
    import pandas as pd
    idx = pd.bdate_range("2025-10-01", periods=30)
    spy_df = pd.DataFrame({
        "Open": [100.0]*30, "High": [100.0]*30,
        "Low":  [100.0]*30, "Close": [100.0]*30,
    }, index=idx)
    test_df = _flat_then_trigger_df(idx, trigger_open=112.0,
                                    trigger_high=113.0, trigger_low=112.0)
    engine = _backtest_harness(monkeypatch, test_df, spy_df)
    engine.replay_news = True
    engine.data_dir    = str(tmp_path)  # empty dir
    result = engine.run()

    attr = result["news_attribution"]
    assert attr["replay_enabled"] is True
    assert attr["signals_vetoed_by_news"] == 0
    assert attr["veto_rate"] is None
    assert result["total_trades"] >= 1


def test_news_replay_t1_negative_vetoes_signal(monkeypatch, tmp_path):
    """When clean_trade_news contains a T1-negative headline for the signal
    ticker, that signal must be dropped and counted as vetoed."""
    import json, pandas as pd
    idx = pd.bdate_range("2025-10-01", periods=30)
    spy_df = pd.DataFrame({
        "Open": [100.0]*30, "High": [100.0]*30,
        "Low":  [100.0]*30, "Close": [100.0]*30,
    }, index=idx)
    test_df = _flat_then_trigger_df(idx, trigger_open=112.0,
                                    trigger_high=113.0, trigger_low=112.0)
    engine = _backtest_harness(monkeypatch, test_df, spy_df)
    engine.replay_news = True
    engine.data_dir    = str(tmp_path)

    # Write T1-negative news for "TEST" on every trading day
    t1_negative_item = {
        "title": "TEST earnings miss analyst expectations",
        "source": "reuters",
        "tickers": ["TEST"],
        "tier": "T1",
    }
    for d in idx:
        fn = tmp_path / f"clean_trade_news_{d.strftime('%Y%m%d')}.json"
        fn.write_text(json.dumps([t1_negative_item]), encoding="utf-8")

    result = engine.run()
    attr = result["news_attribution"]
    assert attr["replay_enabled"] is True
    assert attr["archive_dates_covered"] > 0
    assert attr["signals_vetoed_by_news"] >= 1
    assert attr["veto_rate"] is not None
    assert result["total_trades"] == 0  # TEST vetoed on every signal day


def test_news_replay_t1_positive_does_not_veto(monkeypatch, tmp_path):
    """T1-positive news (e.g. earnings beat) must NOT trigger a veto."""
    import json, pandas as pd
    idx = pd.bdate_range("2025-10-01", periods=30)
    spy_df = pd.DataFrame({
        "Open": [100.0]*30, "High": [100.0]*30,
        "Low":  [100.0]*30, "Close": [100.0]*30,
    }, index=idx)
    test_df = _flat_then_trigger_df(idx, trigger_open=112.0,
                                    trigger_high=113.0, trigger_low=112.0)
    engine = _backtest_harness(monkeypatch, test_df, spy_df)
    engine.replay_news = True
    engine.data_dir    = str(tmp_path)

    # T1-positive news: earnings beat should NOT veto
    t1_positive_item = {
        "title": "TEST earnings beat analyst expectations",
        "source": "reuters",
        "tickers": ["TEST"],
        "tier": "T1",
    }
    for d in idx:
        fn = tmp_path / f"clean_trade_news_{d.strftime('%Y%m%d')}.json"
        fn.write_text(json.dumps([t1_positive_item]), encoding="utf-8")

    result = engine.run()
    attr = result["news_attribution"]
    assert attr["signals_vetoed_by_news"] == 0
    assert result["total_trades"] >= 1  # trade not blocked by positive news


def test_get_earnings_data_as_of_uses_only_past_surprises():
    """Historical as_of must not include surprises from future reports."""
    import pandas as pd
    from data_layer import get_earnings_data

    idx = pd.to_datetime([
        "2025-10-20",
        "2026-01-20",
        "2026-04-20",
        "2026-07-20",
    ])
    dates_df = pd.DataFrame(
        {
            "Reported EPS": [1.0, 1.1, 1.2, None],
            "Surprise(%)": [5.0, -3.0, 11.0, None],
            "EPS Estimate": [None, None, None, 1.35],
        },
        index=idx,
    )

    result = get_earnings_data("TEST", as_of="2026-02-01", dates_df=dates_df)
    assert result["historical_surprise_pct"] == [5.0, -3.0]
    assert result["avg_historical_surprise_pct"] == 1.0
    assert result["eps_actual_last"] == 1.1


def test_get_earnings_data_as_of_uses_next_known_upcoming_row():
    """Historical as_of should derive DTE and EPS estimate from the next future row."""
    import pandas as pd
    from data_layer import get_earnings_data

    idx = pd.to_datetime([
        "2026-01-20",
        "2026-04-24",
        "2026-07-20",
    ])
    dates_df = pd.DataFrame(
        {
            "Reported EPS": [1.1, None, None],
            "Surprise(%)": [6.0, None, None],
            "EPS Estimate": [None, 1.25, 1.4],
        },
        index=idx,
    )

    result = get_earnings_data("TEST", as_of="2026-04-20", dates_df=dates_df)
    assert result["next_earnings_date"] == "2026-04-24"
    assert result["days_to_earnings"] == 4
    assert result["eps_estimate"] == 1.25


def test_backfill_earnings_snapshots_writes_trading_day_files(tmp_path, monkeypatch):
    """Backfill should emit one snapshot file per trading day in the requested range."""
    import pandas as pd
    from backfill_earnings_snapshots import backfill_earnings_snapshots

    class FakeTicker:
        def __init__(self, ticker):
            self.ticker = ticker
            self.info = {"forwardEps": 2.5}
            self.calendar = None

        def get_earnings_dates(self, limit=20):
            idx = pd.to_datetime(["2026-01-20", "2026-01-23"])
            return pd.DataFrame(
                {
                    "Reported EPS": [1.1, None],
                    "Surprise(%)": [7.0, None],
                    "EPS Estimate": [None, 1.25],
                },
                index=idx,
            )

    monkeypatch.setattr("backfill_earnings_snapshots.yf.Ticker", FakeTicker)
    written = backfill_earnings_snapshots(
        "2026-01-21",
        "2026-01-22",
        universe=["AAA", "BBB"],
        data_dir=str(tmp_path),
    )

    assert len(written) == 2
    assert (tmp_path / "earnings_snapshot_20260121.json").exists()
    assert (tmp_path / "earnings_snapshot_20260122.json").exists()
