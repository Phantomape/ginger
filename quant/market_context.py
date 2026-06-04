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


def build_readonly_market_state_context(
    base_context=None,
    ohlcv_by_ticker=None,
    vix_ohlcv=None,
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

    return context
