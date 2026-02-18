"""
Minimal trend-following signal generator using 20-day breakout system.

This module is deterministic and does NOT use news or ML.
It only generates technical signals based on price action.
"""

import os
import json
import logging
from datetime import datetime, timedelta
import yfinance as yf
import pandas as pd

logger = logging.getLogger(__name__)

# Import the watchlist from filter module
from filter import WATCHLIST


def load_open_positions(filepath="../data/open_positions.json"):
    """Load open positions from JSON file."""
    try:
        if not os.path.exists(filepath):
            filepath = "data/open_positions.json"
        if not os.path.exists(filepath):
            return None

        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load open positions: {e}")
        return None


def get_universe():
    """
    Get the trading universe from WATCHLIST and open_positions.json.

    Returns:
        list: Unique list of ticker symbols
    """
    universe = set(WATCHLIST)

    # Add tickers from open positions
    positions = load_open_positions()
    if positions and "positions" in positions:
        for pos in positions["positions"]:
            ticker = pos.get("ticker")
            if ticker:
                universe.add(ticker)

    logger.info(f"Trading universe: {sorted(universe)}")
    return sorted(universe)


def download_ohlcv(ticker, lookback_days=60):
    """
    Download daily OHLCV data for a ticker.

    Args:
        ticker (str): Stock ticker symbol
        lookback_days (int): Number of calendar days to look back (default: 60)

    Returns:
        pd.DataFrame: OHLCV data or None if failed
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days)

        logger.info(f"Downloading data for {ticker} from {start_date.date()} to {end_date.date()}")

        data = yf.download(
            ticker,
            start=start_date,
            end=end_date,
            progress=False
        )

        if data.empty:
            logger.warning(f"No data returned for {ticker}")
            return None

        # Ensure we have the required columns
        required_cols = ['High', 'Low', 'Close']
        if not all(col in data.columns for col in required_cols):
            logger.warning(f"Missing required columns for {ticker}")
            return None

        logger.info(f"Downloaded {len(data)} days of data for {ticker}")
        return data

    except Exception as e:
        logger.error(f"Failed to download data for {ticker}: {e}")
        return None


def compute_breakout_signals(data, window=20):
    """
    Compute 20-day breakout signals.

    Args:
        data (pd.DataFrame): OHLCV data
        window (int): Lookback window for breakout (default: 20)

    Returns:
        dict: Signal data or None if insufficient data
    """
    if len(data) < window + 1:
        logger.warning(f"Insufficient data: {len(data)} days (need at least {window + 1})")
        return None

    try:
        # Get the most recent close (handle both Series and scalar)
        close_value = data['Close'].iloc[-1]
        latest_close = float(close_value.item() if hasattr(close_value, 'item') else close_value)

        # Compute 20-day high/low from the PREVIOUS 20 days (excluding today)
        lookback_data = data.iloc[-(window + 1):-1]

        high_value = lookback_data['High'].max()
        high_20d = float(high_value.item() if hasattr(high_value, 'item') else high_value)

        low_value = lookback_data['Low'].min()
        low_20d = float(low_value.item() if hasattr(low_value, 'item') else low_value)

        # Breakout: today's close > highest high of previous 20 days
        breakout = latest_close > high_20d

        # Breakdown: today's close < lowest low of previous 20 days
        breakdown = latest_close < low_20d

        return {
            "close": round(latest_close, 2),
            "20d_high": round(high_20d, 2),
            "20d_low": round(low_20d, 2),
            "breakout": breakout,
            "breakdown": breakdown
        }

    except Exception as e:
        logger.error(f"Failed to compute signals: {e}")
        return None


def compute_position_context(ticker, latest_close, open_positions):
    """
    Compute position context if ticker is held.

    Args:
        ticker (str): Ticker symbol
        latest_close (float): Current close price
        open_positions (dict): Open positions data

    Returns:
        dict: Position context or None
    """
    if not open_positions or "positions" not in open_positions:
        return None

    for pos in open_positions["positions"]:
        if pos.get("ticker") == ticker:
            shares = pos.get("shares", 0)
            avg_cost = pos.get("avg_cost", 0)

            if avg_cost <= 0:
                return None

            # Compute unrealized PnL %
            unrealized_pnl_pct = (latest_close - avg_cost) / avg_cost

            # Compute distance to hard stop (-12% from avg_cost)
            hard_stop_price = avg_cost * 0.88  # -12%
            distance_to_hard_stop_pct = (latest_close - hard_stop_price) / latest_close

            return {
                "shares": shares,
                "avg_cost": round(avg_cost, 2),
                "unrealized_pnl_pct": round(unrealized_pnl_pct, 4),
                "distance_to_hard_stop_pct": round(distance_to_hard_stop_pct, 4),
                "hard_stop_price": round(hard_stop_price, 2)
            }

    return None


def generate_trend_signals(universe=None, window=20, lookback_days=60):
    """
    Generate trend signals for all tickers in universe.

    Args:
        universe (list): List of tickers (default: get from WATCHLIST + positions)
        window (int): Breakout window in days (default: 20)
        lookback_days (int): Days of historical data to download (default: 60)

    Returns:
        dict: Trend signals data
    """
    if universe is None:
        universe = get_universe()

    open_positions = load_open_positions()

    signals = {}
    today = datetime.now().strftime("%Y-%m-%d")

    logger.info(f"Generating trend signals for {len(universe)} tickers")

    for ticker in universe:
        try:
            # Download OHLCV data
            data = download_ohlcv(ticker, lookback_days)
            if data is None or len(data) == 0:
                logger.warning(f"Skipping {ticker}: no data")
                continue

            # Compute breakout signals
            signal = compute_breakout_signals(data, window)
            if signal is None:
                logger.warning(f"Skipping {ticker}: insufficient data for signals")
                continue

            # Add position context if ticker is held
            position_context = compute_position_context(ticker, signal["close"], open_positions)
            if position_context:
                signal["position"] = position_context

            signals[ticker] = signal
            logger.info(f"{ticker}: close={signal['close']}, breakout={signal['breakout']}, breakdown={signal['breakdown']}")

        except Exception as e:
            logger.error(f"Failed to process {ticker}: {e}")
            continue

    return {
        "generated_at": datetime.now().isoformat(),
        "asof_date": today,
        "universe": universe,
        "window": window,
        "signals": signals
    }


def save_trend_signals(signals, filepath=None):
    """
    Save trend signals to JSON file.

    Args:
        signals (dict): Trend signals data
        filepath (str): Output file path (default: data/trend_signals_YYYYMMDD.json)

    Returns:
        str: Path to saved file
    """
    if filepath is None:
        today = datetime.now().strftime("%Y%m%d")
        filepath = f"data/trend_signals_{today}.json"

    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(signals, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved trend signals to {filepath}")
        return filepath

    except Exception as e:
        logger.error(f"Failed to save trend signals: {e}")
        return None


def main():
    """Main function for standalone execution."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger.info("Generating trend signals...")
    signals = generate_trend_signals()

    if signals["signals"]:
        filepath = save_trend_signals(signals)
        logger.info(f"Generated signals for {len(signals['signals'])} tickers")
        logger.info(f"Output: {filepath}")
    else:
        logger.warning("No signals generated")


if __name__ == "__main__":
    main()
