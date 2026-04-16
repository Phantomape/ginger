"""
Feature Layer: Convert raw data into trading features.

Trend features:
  close, price_vs_200ma_pct, above_200ma, breakout_20d, breakdown_20d,
  momentum_10d_pct, atr, atr_expansion, volume_spike, volume_spike_ratio,
  daily_range_vs_atr, high_20d, low_20d

Earnings features:
  days_to_earnings, next_earnings_date, eps_estimate,
  avg_historical_surprise_pct, positive_surprise_history, earnings_event_window

Example output:
  {
    ticker:          "NVDA",
    trend_score:     0.82,
    breakout_20d:    True,
    days_to_earnings: 12,
    ...
  }
"""

import logging
import pandas as pd

from constants import ATR_PERIOD

logger = logging.getLogger(__name__)


def _scalar(x):
    """Safely convert a pandas scalar to a Python float."""
    if hasattr(x, 'item'):
        return float(x.item())
    return float(x)


def _compute_atr(data, period=ATR_PERIOD):
    """Compute ATR using Wilder's smoothing (alpha = 1/period).

    Wilder's original formula uses alpha = 1/period ≈ 0.071 for period=14,
    which is smoother than EWM(span=14) (alpha = 2/15 ≈ 0.133).  The slower
    decay means a single high-volatility day has less impact on the ATR,
    producing more stable stop prices and reducing position-sizing whipsaws.
    """
    if len(data) < period + 1:
        return None
    high  = data['High']
    low   = data['Low']
    close = data['Close']
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low  - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr_series = tr.ewm(alpha=1.0 / period, adjust=False).mean()
    return round(_scalar(atr_series.iloc[-1]), 4)


def compute_trend_features(data):
    """
    Compute trend-following features from OHLCV data.

    Args:
        data (pd.DataFrame): OHLCV with ≥21 rows

    Returns:
        dict or None
    """
    if data is None or len(data) < 21:
        return None

    try:
        close  = _scalar(data['Close'].iloc[-1])
        volume = _scalar(data['Volume'].iloc[-1])

        # 20-day avg volume (exclude today)
        avg_vol_20 = _scalar(data['Volume'].iloc[-21:-1].mean()) if len(data) >= 21 else None

        # 200-day MA
        above_200ma        = None
        price_vs_200ma_pct = None
        if len(data) >= 200:
            ma200 = _scalar(data['Close'].rolling(200).mean().iloc[-1])
            above_200ma        = bool(close > ma200)
            price_vs_200ma_pct = round((close - ma200) / ma200, 4)

        # 20-day high/low from the PREVIOUS 20 days (exclude today)
        prev20   = data.iloc[-21:-1]
        high_20d = _scalar(prev20['High'].max())
        low_20d  = _scalar(prev20['Low'].min())
        breakout_20d  = bool(close > high_20d)
        breakdown_20d = bool(close < low_20d)

        # 10-day momentum
        momentum_10d_pct = None
        if len(data) >= 11:
            close_10d_ago    = _scalar(data['Close'].iloc[-11])
            momentum_10d_pct = round((close - close_10d_ago) / close_10d_ago, 4)

        # ATR
        atr = _compute_atr(data)

        # 52-week high and distance from it (quality of breakout context)
        high_52w          = None
        pct_from_52w_high = None
        if len(data) >= 252:
            high_52w          = _scalar(data['High'].iloc[-252:].max())
            pct_from_52w_high = round((close - high_52w) / high_52w, 4)

        # ATR expansion: today's range vs 14-day avg range (excl today)
        today_range    = _scalar(data['High'].iloc[-1]) - _scalar(data['Low'].iloc[-1])
        prev14_ranges  = (data['High'] - data['Low']).iloc[-15:-1]
        avg_range_14d  = _scalar(prev14_ranges.mean()) if len(prev14_ranges) >= 14 else None
        atr_expansion  = (round(today_range / avg_range_14d, 4)
                          if avg_range_14d and avg_range_14d > 0 else None)

        # Volume spike: today vs 20-day avg.
        # Threshold 2.0× — research shows breakouts with ≥2× volume have
        # significantly better follow-through than the 1.5× used previously.
        # Strategy A docstring specifies "ratio > 2.0"; this matches.
        volume_spike_ratio = (round(volume / avg_vol_20, 4)
                              if avg_vol_20 and avg_vol_20 > 0 else None)
        volume_spike = bool(volume_spike_ratio is not None and volume_spike_ratio > 2.0)

        # Daily range vs ATR
        daily_range_vs_atr = (round(today_range / atr, 4)
                               if atr and atr > 0 else None)

        # Trend score: fraction of bullish conditions that are True.
        # None counts as False — stocks missing 200MA history (< 200 days) should NOT
        # receive an inflated score from a shrinking denominator.
        bullish_checks = [
            above_200ma,
            breakout_20d,
            volume_spike,
            (momentum_10d_pct or 0) > 0,
            (price_vs_200ma_pct or 0) > 0.03,
        ]
        trend_score = round(sum(1 for c in bullish_checks if c is True) / len(bullish_checks), 2)

        return {
            "close":               round(close, 2),
            "price_vs_200ma_pct":  price_vs_200ma_pct,
            "above_200ma":         above_200ma,
            "breakout_20d":        breakout_20d,
            "breakdown_20d":       breakdown_20d,
            "high_20d":            round(high_20d, 2),
            "low_20d":             round(low_20d, 2),
            "momentum_10d_pct":    momentum_10d_pct,
            "atr":                 atr,
            "atr_expansion":       atr_expansion,
            "volume_spike":        volume_spike,
            "volume_spike_ratio":  volume_spike_ratio,
            "daily_range_vs_atr":  daily_range_vs_atr,
            "trend_score":         trend_score,
            "high_52w":            round(high_52w, 2) if high_52w else None,
            "pct_from_52w_high":   pct_from_52w_high,
        }

    except Exception as e:
        logger.error(f"compute_trend_features failed: {e}")
        return None


def compute_earnings_features(earnings_data):
    """
    Derive earnings-related features from the raw earnings_data dict.

    Args:
        earnings_data (dict): Output of data_layer.get_earnings_data()

    Returns:
        dict: Earnings features (safe to merge with trend features)
    """
    if not earnings_data:
        return {}

    features = {
        "days_to_earnings":  earnings_data.get("days_to_earnings"),
        "next_earnings_date": earnings_data.get("next_earnings_date"),
        "eps_estimate":       earnings_data.get("eps_estimate"),
    }

    # Average historical EPS surprise
    avg_surprise = earnings_data.get("avg_historical_surprise_pct")
    features["avg_historical_surprise_pct"] = avg_surprise
    features["positive_surprise_history"]   = (
        bool(avg_surprise > 0) if avg_surprise is not None else None
    )

    # Is within earnings event window (6–8 days)?
    # Research (Frazzini & Lamont 2007, Bernard & Thomas 1989) shows pre-earnings
    # drift (PEAD) is most concentrated in the FINAL 5-7 days before the announcement.
    #
    # NOTE: days_to_earnings is in TRADING DAYS (np.busday_count in data_layer),
    # not calendar days.  This ensures weekend pipeline runs produce the same dte
    # as the preceding Friday (no phantom dte decrease on Saturday/Sunday).
    #
    # Execution lag correction:
    #   Signal fires after close → entry at next-day open → actual dte = dte - 1.
    #   Window 4-6 trading days at signal → 3-5 trading days at execution.
    #   - Lower bound 4 (was 6 calendar ≈ 4 trading): entry at dte=3 (safe minimum)
    #   - Upper bound 6 (was 8 calendar ≈ 6 trading): entry at dte=5
    #   - Beyond 6 trading days: too early for PEAD capture.
    dte = earnings_data.get("days_to_earnings")
    features["earnings_event_window"] = bool(dte is not None and 4 <= dte <= 6)

    return features


def compute_features(ticker, ohlcv_data, earnings_data):
    """
    Compute all features for a ticker (trend + earnings).

    Returns:
        dict or None
    """
    trend = compute_trend_features(ohlcv_data)
    if trend is None:
        logger.warning(f"{ticker}: insufficient data for features")
        return None

    earnings = compute_earnings_features(earnings_data or {})

    return {
        "ticker": ticker,
        **trend,
        **earnings,
    }
