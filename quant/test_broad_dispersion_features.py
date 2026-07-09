"""Tests for broad-universe dispersion/correlation features (exp-20260709-004)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from broad_dispersion_features import (
    CORR_WINDOW,
    avg_pairwise_correlation,
    cross_sectional_dispersion,
    daily_returns,
    liquidity_mask,
    momentum_spread_next_day,
    quartile_means,
    reversal_spread_next_day,
    spearman,
)


def _dates(n: int) -> list[str]:
    return [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2025-01-01", periods=n)]


def test_liquidity_mask_filters_price_and_rank():
    dates = _dates(25)
    closes = pd.DataFrame(
        {"BIG": 100.0, "MID": 50.0, "PENNY": 2.0}, index=dates
    )
    dollar = pd.DataFrame(
        {"BIG": 1e9, "MID": 1e8, "PENNY": 1e10}, index=dates
    )
    mask = liquidity_mask(closes, dollar)
    last = mask.iloc[-1]
    assert bool(last["BIG"]) and bool(last["MID"])
    assert not bool(last["PENNY"])  # fails min price despite huge volume
    assert not mask.iloc[0].any()  # no ADV history yet


def test_dispersion_zero_when_all_returns_equal():
    dates = _dates(5)
    closes = pd.DataFrame({t: [100, 101, 102.01, 103, 104] for t in "ABCDE"}, index=dates)
    rets = daily_returns(closes)
    mask = pd.DataFrame(True, index=dates, columns=list("ABCDE"))
    disp = cross_sectional_dispersion(rets, mask)
    assert abs(float(disp.iloc[1])) < 1e-12


def test_avg_pairwise_correlation_identity_extremes():
    n_days = CORR_WINDOW * 3
    dates = _dates(n_days)
    rng = np.random.default_rng(11)
    common = rng.normal(0, 0.02, n_days)
    # 40 clones of one factor -> avg corr ~ 1
    clones = pd.DataFrame(
        {f"C{i}": 100 * np.cumprod(1 + common) for i in range(40)}, index=dates
    )
    mask = pd.DataFrame(True, index=dates, columns=clones.columns)
    corr_hi = avg_pairwise_correlation(daily_returns(clones), mask)
    assert float(corr_hi.iloc[-1]) > 0.95
    # 40 independent walks -> avg corr ~ 0
    indep = pd.DataFrame(
        {f"I{i}": 100 * np.cumprod(1 + rng.normal(0, 0.02, n_days)) for i in range(40)},
        index=dates,
    )
    mask_i = pd.DataFrame(True, index=dates, columns=indep.columns)
    corr_lo = avg_pairwise_correlation(daily_returns(indep), mask_i)
    assert abs(float(corr_lo.iloc[-1])) < 0.25


def test_reversal_spread_profits_on_constructed_reversal():
    """Yesterday's losers bounce, winners fade -> reversal spread positive."""
    n_days, n_names = 30, 60
    dates = _dates(n_days)
    rng = np.random.default_rng(3)
    prices = np.full((n_days, n_names), 100.0)
    shock = np.zeros(n_names)
    for i in range(1, n_days):
        new_shock = rng.normal(0, 0.02, n_names)
        # today's move = fresh shock minus half of yesterday's (mean reversion)
        prices[i] = prices[i - 1] * (1 + new_shock - 0.5 * shock)
        shock = new_shock
    closes = pd.DataFrame(prices, index=dates, columns=[f"T{i}" for i in range(n_names)])
    rets = daily_returns(closes)
    mask = pd.DataFrame(True, index=dates, columns=closes.columns)
    rev = reversal_spread_next_day(rets, mask)
    assert float(rev.mean()) > 0


def test_momentum_spread_shapes_and_nan_edges():
    n_days, n_names = 40, 60
    dates = _dates(n_days)
    rng = np.random.default_rng(5)
    closes = pd.DataFrame(
        100 * np.cumprod(1 + rng.normal(0, 0.01, (n_days, n_names)), axis=0),
        index=dates,
        columns=[f"T{i}" for i in range(n_names)],
    )
    rets = daily_returns(closes)
    mask = pd.DataFrame(True, index=dates, columns=closes.columns)
    mom = momentum_spread_next_day(rets, closes, mask)
    assert len(mom) == n_days
    assert np.isnan(mom.iloc[-1])  # no next-day return on the last row


def test_spearman_and_quartiles():
    x = list(range(50))
    y = [v * 2.0 for v in x]
    assert abs(spearman(x, y) - 1.0) < 1e-9
    feature = pd.Series(np.arange(100, dtype=float))
    outcome = pd.Series(np.arange(100, dtype=float) / 1e4)
    q = quartile_means(feature, outcome)
    assert q["n"] == 100
    assert q["q4_minus_q1_bps"] > 0
