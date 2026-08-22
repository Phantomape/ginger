"""Focused guards for finite, shared-input market-regime evaluation."""

from __future__ import annotations

import ast
import inspect
import json
import math
from pathlib import Path
import sys

import pandas as pd


QUANT_DIR = Path(__file__).resolve().parent
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import regime  # noqa: E402
import run as run_module  # noqa: E402


def _price_frame(*, rising: bool = True, trailing_placeholder: bool = False):
    periods = 220
    index = pd.bdate_range("2025-01-02", periods=periods)
    step = 0.2 if rising else -0.2
    close = [100.0 + step * offset for offset in range(periods)]
    frame = pd.DataFrame(
        {
            "Open": close,
            "High": [value + 1.0 for value in close],
            "Low": [value - 1.0 for value in close],
            "Close": close,
            "Volume": [1_000_000.0] * periods,
        },
        index=index,
    )
    if trailing_placeholder:
        frame.loc[index[-1] + pd.offsets.BDay(1)] = {
            "Open": float("nan"),
            "High": float("nan"),
            "Low": float("nan"),
            "Close": float("nan"),
            "Volume": 0.0,
        }
    return frame


def test_trailing_nonfinite_vendor_bar_uses_last_valid_close_and_strict_json():
    frame = _price_frame(trailing_placeholder=True)

    result = regime.compute_market_regime(
        ohlcv_override={"SPY": frame, "QQQ": frame}
    )

    assert result["regime"] == "BULL"
    assert result["indices"]["SPY"]["close"] == round(frame["Close"].dropna().iloc[-1], 2)
    assert result["indices"]["QQQ"]["above_ma"] is True
    json.dumps(result, allow_nan=False)
    for index_result in result["indices"].values():
        assert all(
            value is None or not isinstance(value, float) or math.isfinite(value)
            for value in index_result.values()
        )


def test_regime_accepts_both_yfinance_multiindex_column_orders():
    flat = _price_frame(trailing_placeholder=True)
    ticker_first = pd.concat({"SPY": flat}, axis=1)
    price_first = ticker_first.swaplevel(0, 1, axis=1)

    ticker_first_result = regime._compute_regime_from_ohlcv(
        "SPY", ticker_first, ma_period=200
    )
    price_first_result = regime._compute_regime_from_ohlcv(
        "SPY", price_first, ma_period=200
    )

    assert ticker_first_result == price_first_result
    assert ticker_first_result["above_ma"] is True


def test_override_missing_or_invalid_leg_fails_closed_without_download(monkeypatch):
    calls = []

    def _unexpected_download(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("override mode must not issue a fallback download")

    monkeypatch.setattr(regime, "download_with_rate_limit_retry", _unexpected_download)
    frame = _price_frame()

    missing = regime.compute_market_regime(ohlcv_override={"SPY": frame})
    invalid = regime.compute_market_regime(
        ohlcv_override={"SPY": frame, "QQQ": frame.assign(Close=float("nan"))}
    )

    assert missing["regime"] == "UNKNOWN"
    assert invalid["regime"] == "UNKNOWN"
    assert "QQQ" in missing["note"]
    assert calls == []


def test_live_fetch_path_also_trims_trailing_placeholder(monkeypatch):
    frame = _price_frame(trailing_placeholder=True)
    monkeypatch.setattr(
        regime,
        "download_with_rate_limit_retry",
        lambda *args, **kwargs: frame,
    )

    result = regime._fetch_index("SPY", ma_period=200)

    assert result is not None
    assert result["above_ma"] is True
    json.dumps(result, allow_nan=False)


def test_daily_wiring_loads_shared_batch_before_regime_and_passes_both_legs():
    tree = ast.parse(inspect.getsource(run_module.main))
    batch_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "get_ohlcv_many"
    ]
    regime_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and getattr(node.func, "id", None) == "_step2_market_regime"
    ]

    assert len(batch_calls) == 1
    assert len(regime_calls) == 1
    assert batch_calls[0].lineno < regime_calls[0].lineno
    assert len(regime_calls[0].args) == 1
    override = regime_calls[0].args[0]
    assert isinstance(override, ast.Dict)
    assert {key.value for key in override.keys} == {"SPY", "QQQ"}


def test_daily_regime_step_uses_override_without_second_vendor_download(monkeypatch):
    frame = _price_frame(trailing_placeholder=True)

    def _unexpected_download(*args, **kwargs):
        raise AssertionError("daily regime step must reuse the shared batch")

    monkeypatch.setattr(regime, "download_with_rate_limit_retry", _unexpected_download)

    result = run_module._step2_market_regime({"SPY": frame, "QQQ": frame})

    assert result["regime"] == "BULL"
