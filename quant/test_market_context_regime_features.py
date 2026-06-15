"""Tests for the regime_chop stress/breadth fields in build_readonly_market_state_context."""

from __future__ import annotations

import pandas as pd

from market_context import build_readonly_market_state_context


def _frame(closes):
    return pd.DataFrame({"Close": closes, "High": [c + 1 for c in closes], "Low": [c - 1 for c in closes]})


def test_spy_drawdown_and_vol_ratio_added():
    # 300 rising bars then a pullback -> negative drawdown, finite vol ratio.
    closes = [100 + i * 0.3 for i in range(300)]
    closes = closes + [closes[-1] * (1 - 0.04 * (k + 1)) for k in range(5)]
    ctx = build_readonly_market_state_context(
        base_context={},
        ohlcv_by_ticker={"SPY": _frame(closes), "QQQ": _frame(closes)},
    )
    assert "spy_drawdown_from_high" in ctx
    assert ctx["spy_drawdown_from_high"] <= 0.0
    assert "spy_vol_ratio" in ctx
    assert ctx["spy_vol_ratio"] > 0.0


def test_breadth_computed_from_universe_frames_only():
    long_up = [10 + i * 0.1 for i in range(80)]      # above its 50d SMA
    long_down = [50 - i * 0.1 for i in range(80)]    # below its 50d SMA
    ctx = build_readonly_market_state_context(
        base_context={},
        ohlcv_by_ticker={"SPY": _frame(long_up)},
        universe_ohlcv_by_ticker={
            "AAA": _frame(long_up),
            "BBB": _frame(long_up),
            "CCC": _frame(long_down),
            "SPY": _frame(long_up),  # index excluded from breadth
        },
    )
    # 2 of 3 non-index names above their 50d SMA.
    assert ctx["breadth"] == round(2 / 3, 4)


def test_breadth_absent_without_universe_frames():
    ctx = build_readonly_market_state_context(
        base_context={},
        ohlcv_by_ticker={"SPY": _frame([100 + i * 0.2 for i in range(120)])},
    )
    assert "breadth" not in ctx


def test_backward_compatible_no_universe_param():
    # Calling exactly like the existing production call site still works.
    ctx = build_readonly_market_state_context(
        base_context={"spy_pct_from_ma": 0.02},
        ohlcv_by_ticker={"SPY": _frame([100 + i * 0.2 for i in range(120)]), "QQQ": _frame([100 + i * 0.2 for i in range(120)])},
        vix_ohlcv=_frame([18 + (i % 3) for i in range(40)]),
    )
    assert ctx["spy_pct_from_ma"] == 0.02
    assert "spy_20d_return" in ctx
