"""Intraday quotes via yfinance for the advisory intraday risk review.

ADVISORY ONLY: this module is consumed exclusively by run_intraday.py and is
never used by the EOD pipeline (run.py), the backtester, or experiments.

Quote resolution chain, per ticker (each step independently guarded):
  1. yf.Ticker(t).fast_info       — near-real-time last price + day high/low
  2. 1-minute bars (period="1d")  — last bar close + session high/low
  3. caller-supplied last EOD close (is_stale=True)
  4. unavailable (price=None)     — caller must surface "manual check required"
"""

from __future__ import annotations

import logging

import yfinance as yf

try:
    from yfinance_bootstrap import configure_yfinance_runtime
except ImportError:  # pragma: no cover - package-style imports in tests
    from quant.yfinance_bootstrap import configure_yfinance_runtime

logger = logging.getLogger(__name__)

configure_yfinance_runtime()


def _safe_float(value) -> float | None:
    try:
        if value is None:
            return None
        result = float(value.item() if hasattr(value, "item") else value)
    except (TypeError, ValueError):
        return None
    if result != result or result <= 0:  # NaN or non-positive
        return None
    return result


def _quote_from_fast_info(ticker: str) -> dict | None:
    info = yf.Ticker(ticker).fast_info
    # fast_info fields are lazy properties — any single field access can raise.
    price = day_high = day_low = None
    try:
        price = _safe_float(info["last_price"])
    except Exception:
        price = None
    if price is None:
        return None
    try:
        day_high = _safe_float(info["day_high"])
    except Exception:
        day_high = None
    try:
        day_low = _safe_float(info["day_low"])
    except Exception:
        day_low = None
    return {
        "price": price,
        "day_high": day_high,
        "day_low": day_low,
        "source": "fast_info",
        "quote_time_et": None,
        "is_stale": False,
    }


def _quote_from_intraday_bars(ticker: str) -> dict | None:
    bars = yf.Ticker(ticker).history(
        period="1d", interval="1m", auto_adjust=False
    )
    if bars is None or bars.empty:
        return None
    price = _safe_float(bars["Close"].dropna().iloc[-1])
    if price is None:
        return None
    last_ts = bars.index[-1]
    quote_time_et = None
    try:
        quote_time_et = last_ts.tz_convert("America/New_York").strftime(
            "%Y-%m-%d %H:%M ET"
        )
    except Exception:
        quote_time_et = str(last_ts)
    return {
        "price": price,
        "day_high": _safe_float(bars["High"].max()),
        "day_low": _safe_float(bars["Low"].min()),
        "source": "intraday_1m",
        "quote_time_et": quote_time_et,
        "is_stale": False,
    }


def get_intraday_quote(ticker: str, daily_close_fallback: float | None = None) -> dict:
    """Best-effort intraday quote with explicit source labeling.

    Returns dict with keys: ticker, price, day_high, day_low, source,
    quote_time_et, is_stale. ``price`` is None only when every source failed
    (source="unavailable") — callers must flag those for manual checking.
    """
    ticker = str(ticker).upper()

    try:
        quote = _quote_from_fast_info(ticker)
    except Exception as e:
        logger.warning("%s: fast_info quote failed - %s", ticker, e)
        quote = None

    if quote is None:
        try:
            quote = _quote_from_intraday_bars(ticker)
        except Exception as e:
            logger.warning("%s: 1m intraday quote failed - %s", ticker, e)
            quote = None

    if quote is None:
        fallback = _safe_float(daily_close_fallback)
        if fallback is not None:
            quote = {
                "price": fallback,
                "day_high": None,
                "day_low": None,
                "source": "eod_close_fallback",
                "quote_time_et": None,
                "is_stale": True,
            }
        else:
            quote = {
                "price": None,
                "day_high": None,
                "day_low": None,
                "source": "unavailable",
                "quote_time_et": None,
                "is_stale": True,
            }

    quote["ticker"] = ticker
    return quote


def get_intraday_quotes(tickers, daily_closes: dict | None = None) -> dict[str, dict]:
    """Fetch quotes for a small ticker set (held positions + SPY/QQQ), serially."""
    daily_closes = daily_closes or {}
    quotes: dict[str, dict] = {}
    for raw in dict.fromkeys(str(t).upper() for t in tickers if t):
        quotes[raw] = get_intraday_quote(raw, daily_closes.get(raw))
    return quotes


def quote_source_summary(quotes: dict[str, dict]) -> dict[str, int]:
    """Count quotes by source for the report's DATA QUALITY section."""
    counts: dict[str, int] = {}
    for quote in quotes.values():
        source = quote.get("source", "unavailable")
        counts[source] = counts.get(source, 0) + 1
    return counts
