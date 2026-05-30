"""Tests for the liquidity-aware slippage model (fill_model)."""

import math

from fill_model import (
    SLIPPAGE_BPS_ENTRY, SLIPPAGE_BPS_STOP, MAX_LEG_BPS,
    liquidity_adjusted_bps, apply_slippage, apply_entry_fill, apply_stop_fill,
)


def test_no_context_is_unchanged():
    # Missing liquidity context => flat base bps (backward compatible).
    assert liquidity_adjusted_bps(5, None, None) == 5
    assert liquidity_adjusted_bps(5, 0, 100_000) == 5
    assert liquidity_adjusted_bps(5, 1e8, None) == 5
    # apply_* without context must equal the old flat behavior exactly.
    assert apply_entry_fill(100.0) == round(100.0 * (1 + SLIPPAGE_BPS_ENTRY / 1e4), 4)
    assert apply_slippage(100.0, 10, "sell") == round(100.0 * (1 - 10 / 1e4), 4)


def test_liquid_largecap_small_order_near_base():
    # A very liquid name with a tiny order should pay ~ the base bps.
    bps = liquidity_adjusted_bps(5, adv_dollar=1e9, notional=50_000)
    assert 5.0 <= bps < 6.0


def test_monotonic_decreasing_adv_increases_bps():
    notional = 100_000
    advs = [1e9, 2e8, 5e7, 1e7, 2e6]
    vals = [liquidity_adjusted_bps(5, a, notional) for a in advs]
    assert vals == sorted(vals)            # thinner ADV -> higher bps
    assert vals[0] < vals[-1]


def test_monotonic_increasing_order_increases_bps():
    adv = 5e7
    vals = [liquidity_adjusted_bps(5, adv, n) for n in (50_000, 250_000, 1_000_000)]
    assert vals == sorted(vals)            # bigger participation -> higher bps
    assert vals[0] < vals[-1]


def test_capped_at_max_leg_bps():
    # Ultra-thin name + huge order must not exceed the per-leg cap.
    assert liquidity_adjusted_bps(10, adv_dollar=1e5, notional=5_000_000) <= MAX_LEG_BPS


def test_context_fill_is_worse_than_flat():
    # On a thin name, the realized fill is strictly worse than the flat model.
    flat_buy = apply_entry_fill(100.0)
    liq_buy = apply_entry_fill(100.0, adv_dollar=1e7, notional=500_000)
    assert liq_buy > flat_buy              # buy: pay more
    flat_sell = apply_stop_fill(100.0, 100.0)
    liq_sell = apply_stop_fill(100.0, 100.0, adv_dollar=1e7, notional=500_000)
    assert liq_sell < flat_sell            # sell: receive less
