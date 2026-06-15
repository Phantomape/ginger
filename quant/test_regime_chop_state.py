"""Parity / PIT / monotonicity tests for the shared regime_chop_state module."""

from __future__ import annotations

from datetime import date, timedelta

import regime_chop_state as rc


def _bars(n, start_close=100.0, step=0.4, start="2024-01-01"):
    d0 = date.fromisoformat(start)
    out = []
    c = start_close
    for i in range(n):
        c = c + step
        day = (d0 + timedelta(days=i)).isoformat()
        out.append({"Date": day, "Close": c, "High": c + 0.5, "Low": c - 0.5, "Open": c})
    return out


def test_core_deterministic():
    feats = {"trend_pct_from_ma": 0.03, "ret20": 0.02, "breadth": 0.7, "drawdown_from_high": -0.02, "vol_ratio": 1.0}
    a = rc.regime_chop_from_features(feats)
    b = rc.regime_chop_from_features(dict(feats))
    assert a == b
    assert a["rule_version"] == rc.RULE_VERSION


def test_missing_trend_is_unknown():
    out = rc.regime_chop_from_features({"ret20": 0.01})
    assert out["regime_label"] == "unknown"
    assert out["exposure_scalar"] == 1.0


def test_chop_gets_lower_exposure_than_trend():
    trend = rc.regime_chop_from_features(
        {"trend_pct_from_ma": 0.06, "ret20": 0.05, "breadth": 0.85, "index_agreement": 1.0, "drawdown_from_high": -0.02, "vol_ratio": 1.0}
    )
    chop = rc.regime_chop_from_features(
        {"trend_pct_from_ma": -0.01, "ret20": 0.0, "breadth": 0.4, "index_agreement": 0.33, "drawdown_from_high": -0.04, "vol_ratio": 1.0}
    )
    assert trend["regime_label"] == "risk_on_trend"
    assert chop["regime_label"] == "choppy_range"
    assert chop["exposure_scalar"] < trend["exposure_scalar"]
    assert rc.EXPOSURE_FLOOR <= chop["exposure_scalar"] <= 1.0


def test_stress_is_not_chop_and_keeps_exposure():
    stress = rc.regime_chop_from_features(
        {"trend_pct_from_ma": -0.05, "ret20": -0.08, "breadth": 0.3, "drawdown_from_high": -0.18, "vol_ratio": 1.9}
    )
    chop = rc.regime_chop_from_features(
        {"trend_pct_from_ma": -0.01, "ret20": 0.0, "breadth": 0.45, "drawdown_from_high": -0.03, "vol_ratio": 1.0}
    )
    assert stress["regime_label"] == "risk_off_stress"
    # the soft tilt cuts only chop: stress keeps higher exposure than chop.
    assert stress["exposure_scalar"] > chop["exposure_scalar"]


def test_exposure_monotonic_in_bull():
    low_bull = rc.regime_chop_from_features({"trend_pct_from_ma": -0.02, "ret20": -0.01, "drawdown_from_high": -0.03, "vol_ratio": 1.0})
    high_bull = rc.regime_chop_from_features({"trend_pct_from_ma": 0.05, "ret20": 0.04, "drawdown_from_high": -0.03, "vol_ratio": 1.0})
    # higher bull -> lower choppy probability -> higher exposure
    assert high_bull["p_choppy_range"] < low_bull["p_choppy_range"]
    assert high_bull["exposure_scalar"] >= low_bull["exposure_scalar"]


def test_graceful_degradation_without_breadth():
    with_b = rc.regime_chop_from_features({"trend_pct_from_ma": 0.02, "ret20": 0.01, "breadth": 0.6, "drawdown_from_high": -0.02, "vol_ratio": 1.0})
    without_b = rc.regime_chop_from_features({"trend_pct_from_ma": 0.02, "ret20": 0.01, "drawdown_from_high": -0.02, "vol_ratio": 1.0})
    assert with_b["regime_label"] in rc.REGIME_LABELS
    assert without_b["regime_label"] in rc.REGIME_LABELS
    assert "breadth" not in without_b["feature_keys_used"]


def test_no_stress_signal_low_confidence():
    out = rc.regime_chop_from_features({"trend_pct_from_ma": 0.0, "ret20": 0.0})
    assert out["stress_confident"] is False
    assert out["coverage"] == "no_stress_signal_low_confidence"


def test_pit_future_bars_do_not_change_asof_classification():
    bars = _bars(210)
    asof = bars[180]["Date"]
    full = rc.regime_chop_from_spy_universe(bars, asof, breadth=0.6, index_agreement=0.67)
    # append wild future bars AFTER asof; classification at asof must be identical.
    future = list(bars)
    cf = bars[-1]["Close"]
    for i in range(30):
        future.append({"Date": (date.fromisoformat(bars[-1]["Date"]) + timedelta(days=i + 1)).isoformat(),
                       "Close": cf * (2.0 + i), "High": cf * (2.0 + i), "Low": cf, "Open": cf})
    full_after = rc.regime_chop_from_spy_universe(future, asof, breadth=0.6, index_agreement=0.67)
    assert full["features"] == full_after["features"]
    assert full["exposure_scalar"] == full_after["exposure_scalar"]


def test_bar_adapter_matches_core_for_same_features():
    bars = _bars(210)
    asof = bars[200]["Date"]
    feats = rc.spy_features_at(bars, asof, breadth=0.55, index_agreement=0.67)
    via_core = rc.regime_chop_from_features(feats)
    via_adapter = rc.regime_chop_from_spy_universe(bars, asof, breadth=0.55, index_agreement=0.67)
    for key in ("regime_label", "p_choppy_range", "bull_score", "exposure_scalar"):
        assert via_core[key] == via_adapter[key]


def test_thin_market_context_adapter_flags_fidelity():
    out = rc.regime_chop_from_market_context({"spy_pct_from_ma": 0.02, "spy_20d_return": 0.01, "vix": 18.0})
    assert out["fidelity"] == "thin_market_context_no_breadth_no_drawdown"
    assert out["regime_label"] in rc.REGIME_LABELS
