"""
Data Layer: Collect structured market and event data.

Provides:
  - OHLCV price data (daily, 300 calendar days for 200-day MA)
  - Earnings event data (next date, EPS estimates, historical surprise)
  - Trading universe from watchlist
"""

import json
import logging
import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

try:
    from filter import WATCHLIST
except ImportError:
    logger.warning("Could not import WATCHLIST from filter.py — using fallback")
    WATCHLIST = ["NVDA", "META", "AMD", "QQQ", "TSLA", "MCD", "CRDO", "IAU", "NFLX", "APP", "GOOG", "COIN", "MU"]


def get_universe():
    """
    Return the trading universe: WATCHLIST + any tickers in open_positions.json.

    Mirrors the logic of trend_signals.get_universe() so no ticker is missed.
    """
    universe = set(WATCHLIST)

    for path in [
        os.path.join(os.path.dirname(__file__), '..', 'data', 'open_positions.json'),
        'data/open_positions.json',
    ]:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    positions = json.load(f)
                for pos in positions.get('positions', []):
                    ticker = pos.get('ticker')
                    if ticker:
                        universe.add(ticker)
            except Exception:
                pass
            break

    return sorted(universe)


def get_ohlcv(ticker, lookback_days=400):
    """
    Download daily OHLCV data for a ticker.

    400 calendar days ≈ 276 trading days.
    Raised from 350 (≈241 trading days) → 400 to ensure 52-week high
    computation works reliably.  feature_layer.py requires len(data) ≥ 252
    for pct_from_52w_high; at 350 calendar days only ~241 trading days were
    returned (241 < 252), causing _near_52w_high() to always return False and
    suppressing the +0.40 quality bonus on every signal.
    At 400 calendar days: ~276 trading days > 252 — 52w high computed correctly.

    Returns:
        pd.DataFrame with columns [Open, High, Low, Close, Volume], or None
    """
    try:
        end   = datetime.now()
        start = end - timedelta(days=lookback_days)

        data = yf.download(
            ticker, start=start, end=end,
            progress=False, auto_adjust=True
        )

        if data is None or data.empty:
            logger.warning(f"{ticker}: no OHLCV data returned")
            return None

        # Flatten MultiIndex columns (yfinance multi-ticker quirk)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        required = ['Open', 'High', 'Low', 'Close', 'Volume']
        missing  = [c for c in required if c not in data.columns]
        if missing:
            logger.warning(f"{ticker}: missing columns {missing}")
            return None

        logger.info(f"{ticker}: {len(data)} trading days downloaded")
        return data

    except Exception as e:
        logger.error(f"{ticker}: OHLCV download failed — {e}")
        return None


def get_earnings_data(ticker):
    """
    Get earnings event data from yfinance.

    Returns:
        dict: {
            next_earnings_date (str|None),
            days_to_earnings   (int|None),
            eps_estimate       (float|None),
            eps_actual_last    (float|None),
            historical_surprise_pct (list[float]),   # last ≤4 quarters
            avg_historical_surprise_pct (float|None),
        }
    """
    result = {
        "next_earnings_date":          None,
        "days_to_earnings":            None,
        "eps_estimate":                None,
        "eps_actual_last":             None,
        "historical_surprise_pct":     [],
        "avg_historical_surprise_pct": None,
    }

    try:
        t     = yf.Ticker(ticker)
        today = datetime.now().date()

        # ── Next earnings date ──────────────────────────────────────────────
        try:
            cal = t.calendar
            if cal is not None:
                # Older yfinance: DataFrame with rows like 'Earnings Date'
                if isinstance(cal, pd.DataFrame) and 'Earnings Date' in cal.index:
                    raw = cal.loc['Earnings Date'].iloc[0]
                    if pd.notna(raw):
                        ed = raw.date() if hasattr(raw, 'date') else raw
                        result["next_earnings_date"] = str(ed)
                        result["days_to_earnings"]   = int(np.busday_count(today, ed))
                # Newer yfinance: dict
                elif isinstance(cal, dict) and 'Earnings Date' in cal:
                    raw = cal['Earnings Date']
                    if isinstance(raw, (list, tuple)) and raw:
                        raw = raw[0]
                    if pd.notna(raw):
                        ed = raw.date() if hasattr(raw, 'date') else raw
                        result["next_earnings_date"] = str(ed)
                        result["days_to_earnings"]   = int(np.busday_count(today, ed))
        except Exception as e:
            logger.debug(f"{ticker}: calendar unavailable — {e}")

        # ── EPS estimate from info ──────────────────────────────────────────
        try:
            info = t.info
            for key in ('forwardEps', 'epsCurrentYear', 'trailingEps'):
                val = info.get(key)
                if val is not None and not (isinstance(val, float) and val != val):
                    result["eps_estimate"] = round(float(val), 4)
                    break
        except Exception as e:
            logger.debug(f"{ticker}: EPS estimate unavailable — {e}")

        # ── Historical earnings surprise ────────────────────────────────────
        try:
            dates_df = t.get_earnings_dates(limit=10)
            if dates_df is not None and not dates_df.empty:
                # Past earnings: 'Reported EPS' is filled in
                past = dates_df[dates_df['Reported EPS'].notna()].head(4)
                if not past.empty:
                    result["eps_actual_last"] = float(past['Reported EPS'].iloc[0])

                    if 'Surprise(%)' in past.columns:
                        surprises = [
                            round(float(s), 2)
                            for s in past['Surprise(%)'].dropna()
                        ]
                        result["historical_surprise_pct"] = surprises
                        if surprises:
                            result["avg_historical_surprise_pct"] = round(
                                sum(surprises) / len(surprises), 2
                            )

                # Upcoming (no Reported EPS): fill next_earnings_date if not yet set
                upcoming = dates_df[dates_df['Reported EPS'].isna()]
                if not upcoming.empty and result["next_earnings_date"] is None:
                    raw = upcoming.index[0]
                    ed  = raw.date() if hasattr(raw, 'date') else raw
                    result["next_earnings_date"] = str(ed)
                    result["days_to_earnings"]   = int(np.busday_count(today, ed))

                # EPS estimate from upcoming row
                if ('EPS Estimate' in upcoming.columns
                        and not upcoming.empty
                        and result["eps_estimate"] is None):
                    est = upcoming['EPS Estimate'].iloc[0]
                    if pd.notna(est):
                        result["eps_estimate"] = round(float(est), 4)

        except Exception as e:
            logger.debug(f"{ticker}: earnings dates unavailable — {e}")

    except Exception as e:
        logger.error(f"{ticker}: earnings data collection failed — {e}")

    return result
