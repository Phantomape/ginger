"""
Data Layer: Collect structured market and event data.

Provides:
  - OHLCV price data
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

from yfinance_bootstrap import configure_yfinance_runtime

logger = logging.getLogger(__name__)

configure_yfinance_runtime()

try:
    from filter import WATCHLIST
except ImportError:
    logger.warning("Could not import WATCHLIST from filter.py; using fallback")
    WATCHLIST = [
        "NVDA", "META", "AMD", "QQQ", "TSLA", "MCD", "CRDO",
        "IAU", "NFLX", "APP", "GOOG", "COIN", "MU",
    ]


def get_universe():
    """
    Return the trading universe: WATCHLIST + any tickers in open_positions.json.

    Mirrors the logic of trend_signals.get_universe() so no ticker is missed.
    """
    universe = set(WATCHLIST)

    for path in [
        os.path.join(os.path.dirname(__file__), "..", "data", "open_positions.json"),
        "data/open_positions.json",
    ]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    positions = json.load(f)
                for pos in positions.get("positions", []):
                    ticker = pos.get("ticker")
                    if ticker:
                        universe.add(ticker)
            except Exception:
                pass
            break

    return sorted(universe)


def get_ohlcv(ticker, lookback_days=400):
    """
    Download daily OHLCV data for a ticker.

    400 calendar days is enough for 200-day MA + 52-week-high features.
    Returns a DataFrame with [Open, High, Low, Close, Volume], or None.
    """
    try:
        end = datetime.now()
        start = end - timedelta(days=lookback_days)

        data = yf.download(
            ticker,
            start=start,
            end=end,
            progress=False,
            auto_adjust=True,
        )

        if data is None or data.empty:
            logger.warning("%s: no OHLCV data returned", ticker)
            return None

        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)

        required = ["Open", "High", "Low", "Close", "Volume"]
        missing = [c for c in required if c not in data.columns]
        if missing:
            logger.warning("%s: missing columns %s", ticker, missing)
            return None

        logger.info("%s: %s trading days downloaded", ticker, len(data))
        return data

    except Exception as e:
        logger.error("%s: OHLCV download failed - %s", ticker, e)
        return None


def _coerce_as_of_date(as_of):
    """Normalize supported as_of inputs to a date object."""
    if as_of is None:
        return datetime.now().date()
    if isinstance(as_of, str):
        return pd.Timestamp(as_of).date()
    if hasattr(as_of, "date"):
        return as_of.date()
    return as_of


def _round_or_none(value, digits=4):
    """Return a rounded float or None for NaN/invalid values."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
        return round(float(value), digits)
    except Exception:
        return None


def _extract_earnings_dates_df(ticker_obj, ticker):
    """Fetch the broader earnings timeline once so callers can reuse it."""
    try:
        return ticker_obj.get_earnings_dates(limit=20)
    except Exception as e:
        logger.debug("%s: earnings dates unavailable - %s", ticker, e)
        return None


def _populate_from_earnings_dates(result, dates_df, as_of_date):
    """Fill result using only rows that would be knowable on as_of_date."""
    if dates_df is None or dates_df.empty:
        return

    df = dates_df.copy()
    df["_earnings_date"] = [pd.Timestamp(idx).date() for idx in df.index]
    df = df.sort_values("_earnings_date")

    if "Reported EPS" in df.columns:
        past = df[(df["_earnings_date"] <= as_of_date) & df["Reported EPS"].notna()]
        if not past.empty:
            latest_past = past.iloc[-1]
            result["eps_actual_last"] = _round_or_none(latest_past.get("Reported EPS"))

            if "Surprise(%)" in past.columns:
                tail = past.tail(4)
                surprises = [
                    round(float(s), 2)
                    for s in tail["Surprise(%)"].tolist()
                    if not pd.isna(s)
                ]
                result["historical_surprise_pct"] = surprises
                if surprises:
                    result["avg_historical_surprise_pct"] = round(
                        sum(surprises) / len(surprises), 2
                    )

    future = df[df["_earnings_date"] > as_of_date]
    if future.empty:
        return

    next_row = future.iloc[0]
    next_date = next_row["_earnings_date"]
    result["next_earnings_date"] = str(next_date)
    result["days_to_earnings"] = int(np.busday_count(as_of_date, next_date))

    if "EPS Estimate" in next_row.index:
        result["eps_estimate"] = _round_or_none(next_row.get("EPS Estimate"))


def _populate_from_calendar(result, calendar, as_of_date):
    """Current-day fallback for next earnings date when earnings_dates lacks one."""
    if calendar is None:
        return

    if isinstance(calendar, pd.DataFrame) and "Earnings Date" in calendar.index:
        raw = calendar.loc["Earnings Date"].iloc[0]
    elif isinstance(calendar, dict) and "Earnings Date" in calendar:
        raw = calendar["Earnings Date"]
        if isinstance(raw, (list, tuple)) and raw:
            raw = raw[0]
    else:
        raw = None

    if raw is None or pd.isna(raw):
        return

    earnings_date = raw.date() if hasattr(raw, "date") else raw
    result["next_earnings_date"] = str(earnings_date)
    result["days_to_earnings"] = int(np.busday_count(as_of_date, earnings_date))


def _populate_from_info(result, info):
    """Current-day fallback for EPS estimate when no dated row is available."""
    if not isinstance(info, dict):
        return

    for key in ("forwardEps", "epsCurrentYear", "trailingEps"):
        value = _round_or_none(info.get(key))
        if value is not None:
            result["eps_estimate"] = value
            return


def get_earnings_data(
    ticker,
    as_of=None,
    *,
    ticker_obj=None,
    info=None,
    calendar=None,
    dates_df=None,
):
    """
    Get earnings event data from yfinance.

    When `as_of` is historical, only rows already knowable on that date are used.
    This avoids leaking future surprise history or future EPS estimates backward.
    """
    as_of_date = _coerce_as_of_date(as_of)
    current_mode = (as_of is None) or (as_of_date == datetime.now().date())
    result = {
        "next_earnings_date": None,
        "days_to_earnings": None,
        "eps_estimate": None,
        "eps_actual_last": None,
        "historical_surprise_pct": [],
        "avg_historical_surprise_pct": None,
    }

    try:
        ticker_obj = ticker_obj or yf.Ticker(ticker)
        if dates_df is None:
            dates_df = _extract_earnings_dates_df(ticker_obj, ticker)
        _populate_from_earnings_dates(result, dates_df, as_of_date)

        if current_mode and result["next_earnings_date"] is None:
            try:
                calendar = ticker_obj.calendar if calendar is None else calendar
                _populate_from_calendar(result, calendar, as_of_date)
            except Exception as e:
                logger.debug("%s: calendar unavailable - %s", ticker, e)

        if current_mode and result["eps_estimate"] is None:
            try:
                info = ticker_obj.info if info is None else info
                _populate_from_info(result, info)
            except Exception as e:
                logger.debug("%s: EPS estimate unavailable - %s", ticker, e)

    except Exception as e:
        logger.error("%s: earnings data collection failed - %s", ticker, e)

    return result
