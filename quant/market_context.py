"""Read-only market context derived from broad-market OHLCV frames."""

from __future__ import annotations

import math


def _float_or_none(value):
    try:
        if value is None:
            return None
        raw = value.item() if hasattr(value, "item") else value
        number = float(raw)
        if not math.isfinite(number):
            return None
        return number
    except (TypeError, ValueError):
        return None


def _close_values(frame):
    if frame is None or getattr(frame, "empty", False):
        return None
    try:
        close = frame["Close"].dropna()
    except Exception:
        return None
    if close is None or len(close) == 0:
        return None
    return close


def _close_at(close, offset):
    try:
        return _float_or_none(close.iloc[offset])
    except AttributeError:
        return _float_or_none(close[offset])
    except (IndexError, KeyError):
        return None


def _latest_close(frame):
    close = _close_values(frame)
    if close is None:
        return None
    return _close_at(close, -1)


def _close_return(frame, lookback):
    close = _close_values(frame)
    if close is None or len(close) <= lookback:
        return None

    latest = _close_at(close, -1)
    prior = _close_at(close, -(lookback + 1))
    if latest is None or prior is None or prior <= 0:
        return None
    return round((latest / prior) - 1.0, 4)


_INDEX_TICKERS = {"SPY", "QQQ", "IWM", "DIA", "MDY"}


def _drawdown_from_high(frame, lookback=252):
    close = _close_values(frame)
    if close is None or len(close) == 0:
        return None
    window = close.iloc[-lookback:] if len(close) > lookback else close
    high = _float_or_none(window.max())
    latest = _close_at(close, -1)
    if high is None or latest is None or high <= 0:
        return None
    return round(latest / high - 1.0, 4)


def _vol_ratio(frame, vol_window=20, median_window=100):
    close = _close_values(frame)
    if close is None or len(close) < vol_window + 2:
        return None
    try:
        rets = close.pct_change().dropna()
    except Exception:
        return None
    if rets is None or len(rets) < vol_window:
        return None
    vol_now = _float_or_none(rets.iloc[-vol_window:].std())
    roll = rets.rolling(vol_window).std().dropna()
    if roll is None or len(roll) == 0 or vol_now is None:
        return None
    med = _float_or_none(roll.iloc[-median_window:].median())
    if med is None or med <= 0:
        return None
    return round(vol_now / med, 4)


def _breadth_above_sma(universe_frames, sma_window=50):
    if not universe_frames:
        return None
    total = 0
    above = 0
    for ticker, frame in universe_frames.items():
        if str(ticker).upper() in _INDEX_TICKERS:
            continue
        close = _close_values(frame)
        if close is None or len(close) < sma_window:
            continue
        sma = _float_or_none(close.iloc[-sma_window:].mean())
        latest = _close_at(close, -1)
        if sma is None or latest is None or sma <= 0:
            continue
        total += 1
        if latest > sma:
            above += 1
    if total == 0:
        return None
    return round(above / total, 4)


def build_readonly_market_state_context(
    base_context=None,
    ohlcv_by_ticker=None,
    vix_ohlcv=None,
    universe_ohlcv_by_ticker=None,
):
    """Add passive SPY/QQQ 20d and VIX context without mutating callers.

    The returned dict is intended for diagnostic market-state snapshots only.
    It should not be reused as executable signal, sizing, exit, or order input
    unless a separate strategy experiment validates that behavior change.
    """
    context = dict(base_context or {})
    frames = {
        str(ticker).upper(): frame
        for ticker, frame in (ohlcv_by_ticker or {}).items()
        if ticker
    }

    spy20 = _close_return(frames.get("SPY"), 20)
    qqq20 = _close_return(frames.get("QQQ"), 20)
    if context.get("spy_20d_return") is None and spy20 is not None:
        context["spy_20d_return"] = spy20
    if context.get("qqq_20d_return") is None and qqq20 is not None:
        context["qqq_20d_return"] = qqq20

    spy20 = _float_or_none(context.get("spy_20d_return"))
    qqq20 = _float_or_none(context.get("qqq_20d_return"))
    if context.get("qqq_minus_spy_ret20") is None and spy20 is not None and qqq20 is not None:
        context["qqq_minus_spy_ret20"] = round(qqq20 - spy20, 4)

    vix = _latest_close(vix_ohlcv)
    if context.get("vix") is None and vix is not None:
        context["vix"] = round(vix, 2)

    vix_change = _close_return(vix_ohlcv, 10)
    if context.get("vix_10d_change") is None and vix_change is not None:
        context["vix_10d_change"] = vix_change

    # Stress axis for the regime_chop construct (exp-20260615-019/025/028).
    # Derived from the SPY frame already supplied, so it reaches production with
    # no run.py change. Breadth needs the universe frames (optional) and is the
    # remaining wiring blocked behind exp-20260607-003's run.py claim.
    spy_frame = frames.get("SPY")
    dd = _drawdown_from_high(spy_frame)
    if context.get("spy_drawdown_from_high") is None and dd is not None:
        context["spy_drawdown_from_high"] = dd
    vr = _vol_ratio(spy_frame)
    if context.get("spy_vol_ratio") is None and vr is not None:
        context["spy_vol_ratio"] = vr

    universe_frames = {
        str(ticker).upper(): frame
        for ticker, frame in (universe_ohlcv_by_ticker or {}).items()
        if ticker
    }
    breadth = _breadth_above_sma(universe_frames)
    if context.get("breadth") is None and breadth is not None:
        context["breadth"] = breadth

    return context
