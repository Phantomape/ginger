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
from position_manager import compute_atr, compute_exit_levels, evaluate_exit_signals
from regime import compute_market_regime


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

        # Compute ATR for volatility-adjusted stop sizing
        atr = compute_atr(data)

        return {
            "close": round(latest_close, 2),
            "20d_high": round(high_20d, 2),
            "20d_low": round(low_20d, 2),
            "breakout": breakout,
            "breakdown": breakdown,
            "atr": atr,
        }

    except Exception as e:
        logger.error(f"Failed to compute signals: {e}")
        return None


def compute_position_context(ticker, latest_close, open_positions, atr=None, high_20d=None,
                             high_since_entry=None, prev_close=None):
    """
    Compute position context if ticker is held, including exit levels and signals.

    Args:
        ticker (str): Ticker symbol
        latest_close (float): Current close price
        open_positions (dict): Open positions data
        atr (float): Optional ATR value for volatility-adjusted stop
        high_20d (float): 20-day high (for reporting and fallback trailing stop)
        high_since_entry (float): True highest price since entry date.
            When provided, used as the trailing stop high-water mark instead of
            high_20d.  This prevents missed trailing-stop triggers when the
            position peaked more than 20 trading days ago.
            Example: NVDA peaked at $150 (35 days ago), high_20d=$142,
            trailing stop should be $150×0.92=$138, not $142×0.92=$131.
        prev_close (float): Previous trading day's closing price.
            Used to compute daily_return_pct, which allows the LLM to detect
            single-day gap events (e.g. post-earnings gap > +8% or < -5%).
            Without this field the LLM cannot distinguish "position is up +20%
            since entry" from "position gapped up +10% today after earnings."

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
            market_value_usd = round(shares * latest_close, 2)

            # Positions with >100% gain from avg_cost: avg_cost-based stops are
            # historical artifacts. Risk management should focus on protecting
            # gains from recent highs, not from the original entry.
            legacy_basis = unrealized_pnl_pct > 1.0

            # Resolve stop price:
            # 1. Prefer manually set override_stop_price from open_positions.json
            # 2. For legacy positions (PnL > 100%) with no manual override,
            #    auto-compute a rolling stop at -12% from the current close.
            #    This is far more meaningful than -12% from an old avg_cost
            #    (e.g. AMD avg_cost $27 → default stop $24, useless at $200).
            manual_override = pos.get("override_stop_price")
            if manual_override:
                override_stop     = manual_override
                stop_source       = "manual"
            elif legacy_basis:
                from position_manager import HARD_STOP_PCT
                override_stop     = round(latest_close * (1 - HARD_STOP_PCT), 2)
                stop_source       = "auto_rolling"   # -12% from today's close
            else:
                override_stop     = None
                stop_source       = "default"        # -12% from avg_cost

            # Read signal_target_price from open_positions.json ("target_price" field).
            # When the user opens a trade they should record the signal's target_price
            # (entry + 3.5×ATR from the quant signal) in open_positions.json.
            # This enables the SIGNAL_TARGET exit rule which fires when price reaches
            # the R:R-calibrated target, closing the +7% to +20% dead zone.
            # Without this field, SIGNAL_TARGET is silently skipped.
            signal_target_price = pos.get("target_price")

            # Compute exit levels.
            # For legacy positions pass current_price so ATR stop = current_price - 2×ATR
            # instead of the meaningless avg_cost - 2×ATR (e.g. AMD: $27 - $21 = $6).
            exit_levels = compute_exit_levels(
                avg_cost, atr,
                override_stop_price=override_stop,
                current_price=latest_close if legacy_basis else None,
                signal_target_price=signal_target_price,
            )

            # Compute approximate trading days held (optional: requires entry_date in position).
            days_held = None
            entry_date_str = pos.get("entry_date")
            if entry_date_str:
                try:
                    entry_dt = datetime.strptime(entry_date_str, "%Y-%m-%d").date()
                    calendar_days = (datetime.now().date() - entry_dt).days
                    days_held = max(0, int(calendar_days * 5 / 7))  # calendar → approx trading days
                except Exception:
                    pass

            # Use true high since entry as high_water_mark for trailing stop.
            # Falls back to 20d high when entry_date is unavailable.
            # Bug fix: using only 20d high misses peaks from >20 days ago,
            # causing trailing stop to not trigger when it should.
            trailing_hwm = high_since_entry if high_since_entry is not None else high_20d

            exit_signals = evaluate_exit_signals(
                latest_close, avg_cost, exit_levels,
                high_water_mark=trailing_hwm,
                days_held=days_held,
                legacy_basis=legacy_basis,
            )

            # Classify breach status: is the hard stop already ABOVE the current price?
            # If so, the position is in a delayed/historic breach state — it should have
            # been exited when the stop was first breached, not treated as a new trigger.
            hard_stop_price = exit_levels.get("hard_stop_price", 0)
            if hard_stop_price <= 0 or latest_close > hard_stop_price:
                breach_status = "OK"
            else:
                gap_pct = (hard_stop_price - latest_close) / latest_close
                breach_status = "HISTORIC_BREACH" if gap_pct >= 0.20 else "DELAYED_BREACH"

            result = {
                "shares": shares,
                "avg_cost": round(avg_cost, 2),
                "market_value_usd": market_value_usd,
                "unrealized_pnl_pct": round(unrealized_pnl_pct, 4),
                "legacy_basis": legacy_basis,
                "stop_source": stop_source,
                "breach_status": breach_status,
                "exit_levels": exit_levels,
                "exit_signals": exit_signals,
            }

            # Today's price change vs yesterday — enables LLM to detect gap events.
            # Critical for post-earnings rules: "gap > +8% → REDUCE 50%",
            # "gap < -5% → EXIT".  Without prev_close the LLM cannot distinguish
            # a single-day gap from accumulated unrealised gain since entry.
            if prev_close and prev_close > 0:
                daily_return = round((latest_close - prev_close) / prev_close, 4)
                result["prev_close"]       = round(prev_close, 2)
                result["daily_return_pct"] = daily_return

            if trailing_hwm is not None:
                from position_manager import TRAILING_STOP_PCT
                # Field names kept as trailing_stop_from_20d_high / drawdown_from_20d_high_pct
                # for LLM prompt backwards-compatibility, but now computed from the
                # true high-water mark (max of high_since_entry vs high_20d).
                result["trailing_stop_from_20d_high"] = round(trailing_hwm * (1 - TRAILING_STOP_PCT), 2)
                result["drawdown_from_20d_high_pct"] = round((latest_close - trailing_hwm) / trailing_hwm, 4)
                if high_since_entry is not None and high_20d is not None:
                    result["high_water_mark_source"] = (
                        "entry_date_high" if high_since_entry >= high_20d else "20d_high"
                    )

            if override_stop:
                result["effective_stop_price"] = override_stop

            return result

    return None


def generate_trend_signals(universe=None, window=20, lookback_days=400):
    """
    Generate trend signals for all tickers in universe.

    Args:
        universe (list): List of tickers (default: get from WATCHLIST + positions)
        window (int): Breakout window in days (default: 20)
        lookback_days (int): Days of historical data to download (default: 400)
            Must be ≥ 400 to provide 276+ trading days for 52-week high computation.

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

            # Compute true high-water mark since entry date for accurate trailing stop.
            # Bug: using only 20d_high misses peaks from >20 days ago, causing trailing
            # stop to fail when position peaked more than 20 trading days back.
            # Example: bought NVDA at $102, peaked at $150 (35d ago), now $137 →
            #   20d_high=$142 → trailing=$130.64 (stop NOT triggered)
            #   high_since_entry=$150 → trailing=$138   (stop correctly triggered)
            high_since_entry = None
            if open_positions and "positions" in open_positions:
                for pos in open_positions["positions"]:
                    if pos.get("ticker") == ticker:
                        entry_date_str = pos.get("entry_date")
                        if entry_date_str:
                            try:
                                entry_dt = pd.Timestamp(entry_date_str)
                                data_since = data[data.index >= entry_dt]
                                if not data_since.empty:
                                    raw_high = data_since['High'].max()
                                    high_since_entry = float(
                                        raw_high.item() if hasattr(raw_high, 'item') else raw_high
                                    )
                            except Exception as exc:
                                logger.debug(f"{ticker}: could not compute high_since_entry: {exc}")
                        break

            # Compute previous trading day's close for daily_return_pct.
            # Required by LLM post-earnings gap rules: "gap > +8% → REDUCE 50%".
            prev_close = None
            if data is not None and len(data) >= 2:
                try:
                    prev_val = data['Close'].iloc[-2]
                    prev_close = float(prev_val.item() if hasattr(prev_val, 'item') else prev_val)
                except Exception:
                    pass

            # Add position context if ticker is held
            # Pass ATR for volatility-adjusted stop, high_since_entry for accurate
            # trailing stop high-water mark, and 20d_high as fallback.
            position_context = compute_position_context(
                ticker, signal["close"], open_positions,
                atr=signal.get("atr"),
                high_20d=signal.get("20d_high"),
                high_since_entry=high_since_entry,
                prev_close=prev_close,
            )
            if position_context:
                signal["position"] = position_context

            signals[ticker] = signal
            logger.info(f"{ticker}: close={signal['close']}, breakout={signal['breakout']}, breakdown={signal['breakdown']}")

        except Exception as e:
            logger.error(f"Failed to process {ticker}: {e}")
            continue

    # Compute market regime (SPY + QQQ vs 200-day MA)
    logger.info("Computing market regime (SPY/QQQ vs 200-day MA)...")
    try:
        regime = compute_market_regime()
        logger.info(f"Market regime: {regime['regime']}")
    except Exception as e:
        logger.error(f"Failed to compute market regime: {e}")
        regime = {"regime": "UNKNOWN", "note": f"Regime check failed: {e}", "indices": {}}

    return {
        "generated_at": datetime.now().isoformat(),
        "asof_date": today,
        "universe": universe,
        "window": window,
        "market_regime": regime,
        "signals": signals,
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
