from pathlib import Path
import sys

import pandas as pd


QUANT_DIR = Path(__file__).resolve().parent
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from market_context import build_readonly_market_state_context  # noqa: E402


def _ohlcv(closes):
    return pd.DataFrame(
        {
            "Open": closes,
            "High": closes,
            "Low": closes,
            "Close": closes,
            "Volume": [1000] * len(closes),
        },
        index=pd.date_range("2026-01-01", periods=len(closes), freq="B"),
    )


def test_build_readonly_market_state_context_adds_20d_and_vix_fields():
    base_context = {
        "market_regime": "BULL",
        "spy_10d_return": 0.02,
    }

    result = build_readonly_market_state_context(
        base_context,
        ohlcv_by_ticker={
            "SPY": _ohlcv([100] * 20 + [110]),
            "QQQ": _ohlcv([100] * 20 + [120]),
        },
        vix_ohlcv=_ohlcv([20] * 10 + [16]),
    )

    assert base_context == {
        "market_regime": "BULL",
        "spy_10d_return": 0.02,
    }
    assert result["spy_20d_return"] == 0.1
    assert result["qqq_20d_return"] == 0.2
    assert result["qqq_minus_spy_ret20"] == 0.1
    assert result["vix"] == 16.0
    assert result["vix_10d_change"] == -0.2


def test_build_readonly_market_state_context_preserves_existing_values():
    result = build_readonly_market_state_context(
        {
            "spy_20d_return": 0.03,
            "qqq_20d_return": 0.04,
            "vix": 18.5,
            "breadth": 0.25,
        },
        ohlcv_by_ticker={
            "SPY": _ohlcv([100] * 20 + [110]),
            "QQQ": _ohlcv([100] * 20 + [120]),
        },
        universe_ohlcv_by_ticker={
            "A": _ohlcv([100] * 49 + [110]),
            "B": _ohlcv([100] * 49 + [110]),
        },
        vix_ohlcv=_ohlcv([20] * 10 + [16]),
    )

    assert result["spy_20d_return"] == 0.03
    assert result["qqq_20d_return"] == 0.04
    assert result["qqq_minus_spy_ret20"] == 0.01
    assert result["vix"] == 18.5
    assert result["vix_10d_change"] == -0.2
    assert result["breadth"] == 0.25


def test_build_readonly_market_state_context_adds_universe_breadth():
    result = build_readonly_market_state_context(
        {},
        ohlcv_by_ticker={
            "SPY": _ohlcv([100] * 20 + [110]),
            "QQQ": _ohlcv([100] * 20 + [120]),
        },
        universe_ohlcv_by_ticker={
            "A": _ohlcv([100] * 49 + [110]),
            "B": _ohlcv([100] * 49 + [90]),
            "SPY": _ohlcv([100] * 49 + [110]),
        },
    )

    assert result["breadth"] == 0.5
