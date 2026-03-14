"""
Market regime detection based on SPY and QQQ vs 200-day moving average.

Regime classification:
  BULL:    Both SPY and QQQ above their 200-day SMA
           → New long positions permitted. Hold existing.
  NEUTRAL: One above, one below
           → Highly selective on new positions. Prefer holds.
  BEAR:    Both SPY and QQQ below their 200-day SMA
           → NO new long positions. Bias toward EXIT and REDUCE.
"""

import logging
from datetime import datetime, timedelta

import yfinance as yf
import pandas as pd

logger = logging.getLogger(__name__)

REGIME_TICKERS = ["SPY", "QQQ"]
MA_PERIOD      = 200


def _scalar(val):
    """Extract a scalar float from a pandas value that may be a Series."""
    return float(val.item() if hasattr(val, "item") else val)


def _fetch_index(ticker, ma_period=MA_PERIOD):
    """
    Download data and compute MA status for a single index ticker.

    Returns:
        dict with close, ma200, above_ma, pct_from_ma — or None on failure
    """
    try:
        lookback_days = ma_period * 2      # ~400 calendar days for 200 trading days
        end   = datetime.now()
        start = end - timedelta(days=lookback_days)

        data = yf.download(ticker, start=start, end=end, progress=False)

        if data.empty or len(data) < ma_period:
            logger.warning(f"Insufficient data for {ticker} ({len(data)} rows)")
            return None

        close  = data["Close"]
        ma     = close.rolling(window=ma_period).mean()

        latest_close = _scalar(close.iloc[-1])
        latest_ma    = _scalar(ma.iloc[-1])

        above_ma    = latest_close > latest_ma
        pct_from_ma = (latest_close - latest_ma) / latest_ma

        return {
            "ticker":      ticker,
            "close":       round(latest_close, 2),
            f"ma{ma_period}": round(latest_ma, 2),
            "above_ma":    above_ma,
            "pct_from_ma": round(pct_from_ma, 4),
        }

    except Exception as e:
        logger.error(f"Failed to fetch regime data for {ticker}: {e}")
        return None


def compute_market_regime(ma_period=MA_PERIOD):
    """
    Compute overall market regime from SPY and QQQ.

    Returns:
        dict: {
            "regime":  "BULL" | "NEUTRAL" | "BEAR" | "UNKNOWN",
            "note":    str,
            "indices": { "SPY": {...}, "QQQ": {...} }
        }
    """
    indices = {}
    for ticker in REGIME_TICKERS:
        result = _fetch_index(ticker, ma_period)
        if result:
            indices[ticker] = result

    if not indices:
        return {
            "regime":  "UNKNOWN",
            "note":    "Could not fetch index data — treat as NEUTRAL",
            "indices": {},
        }

    above_count = sum(1 for r in indices.values() if r.get("above_ma"))
    total       = len(indices)

    if above_count == total:
        regime = "BULL"
        note   = ("Both SPY and QQQ are above their 200-day MA. "
                  "Trend is bullish. New long positions are permitted.")
    elif above_count == 0:
        regime = "BEAR"
        note   = ("Both SPY and QQQ are BELOW their 200-day MA. "
                  "DO NOT open new long positions. "
                  "Bias all existing positions toward REDUCE or EXIT.")
    else:
        regime = "NEUTRAL"
        note   = ("Mixed signals: one index above MA, one below. "
                  "Be highly selective. Avoid new positions unless very high conviction.")

    logger.info(f"Market regime: {regime} | SPY above={indices.get('SPY', {}).get('above_ma')} "
                f"| QQQ above={indices.get('QQQ', {}).get('above_ma')}")

    return {
        "regime":  regime,
        "note":    note,
        "indices": indices,
    }
