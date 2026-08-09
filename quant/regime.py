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
import math
from datetime import datetime, timedelta

import pandas as pd

from yfinance_bootstrap import (
    configure_yfinance_runtime,
    download_with_rate_limit_retry,
)

logger = logging.getLogger(__name__)

configure_yfinance_runtime()

REGIME_TICKERS = ["SPY", "QQQ"]
MA_PERIOD      = 200


def _scalar(val):
    """Extract a scalar float from a pandas value that may be a Series."""
    return float(val.item() if hasattr(val, "item") else val)


def _finite_close_series(ticker, ohlcv_data):
    """Return the ticker's finite Close observations from a vendor OHLCV frame.

    ``yfinance`` may return either flat columns or a two-level column index in
    ``ticker/price`` or ``price/ticker`` order. It can also append a partial
    current-session row whose OHLC values are NaN while Volume is populated.
    Regime classification must anchor on the last valid close, never let that
    placeholder turn comparisons into false values.
    """
    if ohlcv_data is None or not isinstance(ohlcv_data, pd.DataFrame):
        return None
    if ohlcv_data.empty:
        return None

    try:
        data = ohlcv_data
        if isinstance(data.columns, pd.MultiIndex):
            ticker_key = str(ticker).upper()
            level0_key = next(
                (
                    value
                    for value in data.columns.get_level_values(0)
                    if str(value).upper() == ticker_key
                ),
                None,
            )
            level1_key = next(
                (
                    value
                    for value in data.columns.get_level_values(1)
                    if str(value).upper() == ticker_key
                ),
                None,
            )
            if level0_key is not None:
                data = data[level0_key]
            elif level1_key is not None:
                data = data.xs(level1_key, axis=1, level=1)
            else:
                logger.warning("%s: no ticker slice in regime OHLCV frame", ticker)
                return None

        if "Close" not in data.columns:
            logger.warning("%s: Close column missing from regime OHLCV frame", ticker)
            return None
        close = data["Close"]
        if isinstance(close, pd.DataFrame):
            if close.shape[1] != 1:
                logger.warning("%s: ambiguous Close columns in regime OHLCV frame", ticker)
                return None
            close = close.iloc[:, 0]

        numeric = pd.to_numeric(close, errors="coerce")
        finite = numeric.map(
            lambda value: pd.notna(value) and math.isfinite(float(value))
        )
        numeric = numeric.loc[finite].astype(float)
        return numeric if not numeric.empty else None
    except Exception as exc:
        logger.error("Failed to normalize regime Close data for %s: %s", ticker, exc)
        return None


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

        data = download_with_rate_limit_retry(
            ticker, start=start, end=end, progress=False, retry_logger=logger
        )

        result = _compute_regime_from_ohlcv(ticker, data, ma_period)
        if result is None:
            row_count = len(data) if isinstance(data, pd.DataFrame) else 0
            logger.warning(
                "Insufficient or invalid data for %s (%s rows)", ticker, row_count
            )
        return result

    except Exception as e:
        logger.error(f"Failed to fetch regime data for {ticker}: {e}")
        return None


def _compute_regime_from_ohlcv(ticker, ohlcv_data, ma_period=MA_PERIOD):
    """
    Compute regime info for a single index from pre-loaded OHLCV data.

    Used by the backtester to avoid live API calls during historical replay.

    Args:
        ticker     (str):          Index ticker symbol (e.g. "SPY")
        ohlcv_data (pd.DataFrame): OHLCV with DatetimeIndex, sliced up to the
                                   target date (inclusive)
        ma_period  (int):          Moving average period (default 200)

    Returns:
        dict with close, ma200, above_ma, pct_from_ma — or None on failure
    """
    try:
        close = _finite_close_series(ticker, ohlcv_data)
        if close is None or len(close) < ma_period:
            return None
        ma = close.rolling(window=ma_period).mean()

        latest_close = _scalar(close.iloc[-1])
        latest_ma = _scalar(ma.iloc[-1])
        if not (
            math.isfinite(latest_close)
            and math.isfinite(latest_ma)
            and latest_ma != 0.0
        ):
            return None

        above_ma = bool(latest_close > latest_ma)
        pct_from_ma = (latest_close - latest_ma) / latest_ma

        momentum_10d_pct = None
        if len(close) >= 11:
            close_10d_ago = _scalar(close.iloc[-11])
            if math.isfinite(close_10d_ago) and close_10d_ago != 0.0:
                momentum_10d_pct = round(
                    (latest_close - close_10d_ago) / close_10d_ago, 4
                )

        return {
            "ticker": ticker,
            "close": round(latest_close, 2),
            f"ma{ma_period}": round(latest_ma, 2),
            "above_ma": above_ma,
            "pct_from_ma": round(pct_from_ma, 4),
            "momentum_10d_pct": momentum_10d_pct,
        }
    except Exception as e:
        logger.error(f"_compute_regime_from_ohlcv failed for {ticker}: {e}")
        return None


def compute_market_regime(ma_period=MA_PERIOD, ohlcv_override=None):
    """
    Compute overall market regime from SPY and QQQ.

    Args:
        ma_period      (int):  Moving average period (default 200)
        ohlcv_override (dict): Optional {ticker: DataFrame} for backtesting.
                               When provided, uses pre-loaded data instead of
                               live yfinance downloads.

    Returns:
        dict: {
            "regime":  "BULL" | "NEUTRAL" | "BEAR" | "UNKNOWN",
            "note":    str,
            "indices": { "SPY": {...}, "QQQ": {...} }
        }
    """
    indices = {}
    for ticker in REGIME_TICKERS:
        if ohlcv_override is not None:
            result = _compute_regime_from_ohlcv(
                ticker, ohlcv_override.get(ticker), ma_period
            )
        else:
            result = _fetch_index(ticker, ma_period)
        if result:
            indices[ticker] = result

    missing = [ticker for ticker in REGIME_TICKERS if ticker not in indices]
    if missing:
        return {
            "regime":  "UNKNOWN",
            "note":    (
                "Market regime requires finite SPY and QQQ data; "
                f"missing or invalid: {', '.join(missing)}."
            ),
            "indices": indices,
        }

    above_count = sum(1 for r in indices.values() if r.get("above_ma"))
    total       = len(REGIME_TICKERS)

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
