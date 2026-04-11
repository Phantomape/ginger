"""
Walk-Forward Backtester — minimal execution loop for parameter validation.

Replays historical OHLCV data through the signal + risk pipeline day-by-day,
simulates fills at next-day open (with exec_lag), and tracks equity curve.

This is NOT an optimizer.  It provides a single-parameter sweep interface
so that heuristic values (ATR multipliers, TQS weights, lookback periods)
can be validated against observed data rather than pure guesswork.

Usage:
    from backtester import BacktestEngine

    engine = BacktestEngine(ohlcv_dict, start="2025-01-01", end="2025-12-31")
    results = engine.run()
    print(results["sharpe"], results["max_drawdown_pct"])

    # Single-parameter sweep
    sweep_results = engine.sweep("ATR_STOP_MULT", [1.0, 1.5, 2.0])
"""

import logging
import math
from datetime import datetime

import pandas as pd

logger = logging.getLogger(__name__)

# Default config — mirrors production values from risk_engine / portfolio_engine
DEFAULT_CONFIG = {
    "ATR_STOP_MULT":       1.5,
    "ATR_TARGET_MULT":     3.5,
    "ROUND_TRIP_COST_PCT": 0.0035,
    "EXEC_LAG_PCT":        0.005,
    "RISK_PER_TRADE_PCT":  0.01,
    "MAX_POSITIONS":       5,
    "INITIAL_CAPITAL":     100_000.0,
}


class Position:
    """Track a single open position."""

    __slots__ = ("ticker", "entry_price", "stop_price", "target_price",
                 "shares", "entry_date", "strategy")

    def __init__(self, ticker, entry_price, stop_price, target_price,
                 shares, entry_date, strategy):
        self.ticker       = ticker
        self.entry_price  = entry_price
        self.stop_price   = stop_price
        self.target_price = target_price
        self.shares       = shares
        self.entry_date   = entry_date
        self.strategy     = strategy


class BacktestEngine:
    """
    Minimal walk-forward backtester.

    Args:
        ohlcv_dict (dict[str, pd.DataFrame]): {ticker: DataFrame with OHLCV + DatetimeIndex}
        start      (str): Start date (YYYY-MM-DD)
        end        (str): End date   (YYYY-MM-DD)
        config     (dict): Override any key in DEFAULT_CONFIG
    """

    def __init__(self, ohlcv_dict, start=None, end=None, config=None):
        self.ohlcv    = ohlcv_dict
        self.config   = {**DEFAULT_CONFIG, **(config or {})}
        self.start    = pd.Timestamp(start) if start else None
        self.end      = pd.Timestamp(end)   if end   else None

    def run(self):
        """
        Execute the backtest over the date range.

        Returns:
            dict: {
                total_trades, wins, losses, win_rate,
                total_pnl, sharpe, max_drawdown_pct,
                equity_curve (list of (date_str, equity)),
            }
        """
        capital    = self.config["INITIAL_CAPITAL"]
        equity     = capital
        positions  = []          # list[Position]
        closed     = []          # list[dict] — closed trade records
        equity_curve = []

        # Build unified date index from all tickers
        all_dates = set()
        for df in self.ohlcv.values():
            if df is not None and not df.empty:
                all_dates.update(df.index)
        all_dates = sorted(all_dates)
        if self.start:
            all_dates = [d for d in all_dates if d >= self.start]
        if self.end:
            all_dates = [d for d in all_dates if d <= self.end]

        if len(all_dates) < 2:
            return {"error": "Insufficient data for backtest"}

        for i, today in enumerate(all_dates):
            # -- Check exits on today's prices --
            still_open = []
            for pos in positions:
                df = self.ohlcv.get(pos.ticker)
                if df is None or today not in df.index:
                    still_open.append(pos)
                    continue

                row  = df.loc[today]
                low  = float(row["Low"].item()  if hasattr(row["Low"],  "item") else row["Low"])
                high = float(row["High"].item() if hasattr(row["High"], "item") else row["High"])
                opn  = float(row["Open"].item() if hasattr(row["Open"], "item") else row["Open"])
                cls  = float(row["Close"].item() if hasattr(row["Close"], "item") else row["Close"])

                exit_price = None
                exit_reason = None

                # Stop hit
                if pos.stop_price and low <= pos.stop_price:
                    exit_price = opn if opn < pos.stop_price else pos.stop_price
                    exit_reason = "stop"
                # Target hit
                elif pos.target_price and high >= pos.target_price:
                    exit_price = pos.target_price
                    exit_reason = "target"

                if exit_price is not None:
                    cost = exit_price * self.config["ROUND_TRIP_COST_PCT"] * pos.shares
                    pnl  = (exit_price - pos.entry_price) * pos.shares - cost
                    equity += pnl
                    closed.append({
                        "ticker":      pos.ticker,
                        "strategy":    pos.strategy,
                        "entry_price": pos.entry_price,
                        "exit_price":  round(exit_price, 2),
                        "shares":      pos.shares,
                        "pnl":         round(pnl, 2),
                        "exit_reason": exit_reason,
                        "entry_date":  str(pos.entry_date.date()) if hasattr(pos.entry_date, 'date') else str(pos.entry_date),
                        "exit_date":   str(today.date()) if hasattr(today, 'date') else str(today),
                    })
                else:
                    still_open.append(pos)

            positions = still_open

            # -- Generate signals & enter new positions (simplified) --
            # Use a basic breakout heuristic: close > 20-day high & volume spike
            if i < 20 or len(positions) >= self.config["MAX_POSITIONS"]:
                equity_curve.append((str(today.date()) if hasattr(today, 'date') else str(today), round(equity, 2)))
                continue

            for ticker, df in self.ohlcv.items():
                if df is None or today not in df.index:
                    continue
                if any(p.ticker == ticker for p in positions):
                    continue  # already holding
                if len(positions) >= self.config["MAX_POSITIONS"]:
                    break

                lookback = df.loc[:today].tail(21)
                if len(lookback) < 21:
                    continue

                row   = df.loc[today]
                close = float(row["Close"].item() if hasattr(row["Close"], "item") else row["Close"])
                high_20d = float(lookback["High"].iloc[:-1].max())

                # Simple breakout condition
                if close <= high_20d:
                    continue

                # Compute ATR
                _lb = lookback.tail(15)
                if len(_lb) < 2:
                    continue
                _highs = _lb["High"].values.flatten()
                _lows  = _lb["Low"].values.flatten()
                _closes = _lb["Close"].values.flatten()
                _tr = []
                for j in range(1, len(_highs)):
                    h = float(_highs[j])
                    l = float(_lows[j])
                    pc = float(_closes[j-1])
                    _tr.append(max(h - l, abs(h - pc), abs(l - pc)))
                atr = sum(_tr) / len(_tr) if _tr else 0
                if atr <= 0:
                    continue

                stop   = round(close - self.config["ATR_STOP_MULT"] * atr, 2)
                target = round(close + self.config["ATR_TARGET_MULT"] * atr, 2)
                risk   = close - stop
                if risk <= 0:
                    continue

                # Next-day open fill with exec lag
                if i + 1 < len(all_dates):
                    next_day = all_dates[i + 1]
                    if next_day in df.index:
                        fill_row = df.loc[next_day]
                        fill_price = float(fill_row["Open"].item() if hasattr(fill_row["Open"], "item") else fill_row["Open"])
                    else:
                        fill_price = close * (1 + self.config["EXEC_LAG_PCT"])
                else:
                    fill_price = close * (1 + self.config["EXEC_LAG_PCT"])

                # Position sizing: risk 1% of equity
                risk_dollars = equity * self.config["RISK_PER_TRADE_PCT"]
                adj_risk     = fill_price - stop
                if adj_risk <= 0:
                    continue
                shares = max(1, int(risk_dollars / adj_risk))

                positions.append(Position(
                    ticker=ticker, entry_price=round(fill_price, 2),
                    stop_price=stop, target_price=target,
                    shares=shares, entry_date=next_day if i + 1 < len(all_dates) else today,
                    strategy="breakout_long",
                ))

            equity_curve.append((str(today.date()) if hasattr(today, 'date') else str(today), round(equity, 2)))

        # -- Compute metrics --
        wins   = [t for t in closed if t["pnl"] > 0]
        losses = [t for t in closed if t["pnl"] <= 0]
        total  = len(closed)

        # Max drawdown from equity curve
        peak   = 0.0
        max_dd = 0.0
        for _, eq in equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

        # Sharpe from trade P&L
        pnl_series = [t["pnl"] for t in closed]
        if len(pnl_series) >= 2:
            mean_pnl = sum(pnl_series) / len(pnl_series)
            var_pnl  = sum((x - mean_pnl) ** 2 for x in pnl_series) / (len(pnl_series) - 1)
            std_pnl  = math.sqrt(var_pnl) if var_pnl > 0 else 0
            sharpe   = round((mean_pnl / std_pnl) * math.sqrt(30), 2) if std_pnl > 0 else None
        else:
            sharpe = None

        return {
            "total_trades":    total,
            "wins":            len(wins),
            "losses":          len(losses),
            "win_rate":        round(len(wins) / total, 4) if total else 0,
            "total_pnl":       round(sum(t["pnl"] for t in closed), 2),
            "sharpe":          sharpe,
            "max_drawdown_pct": round(max_dd, 4),
            "equity_curve":    equity_curve,
            "trades":          closed,
        }

    def sweep(self, param_name, values):
        """
        Single-parameter sweep: run the backtest for each value of param_name.

        Args:
            param_name (str):   Key in DEFAULT_CONFIG to vary
            values     (list):  Values to test

        Returns:
            list[dict]: One result dict per value, with 'param_value' added
        """
        results = []
        for val in values:
            cfg = {**self.config, param_name: val}
            engine = BacktestEngine(self.ohlcv, start=str(self.start.date()) if self.start else None,
                                    end=str(self.end.date()) if self.end else None, config=cfg)
            result = engine.run()
            result["param_name"]  = param_name
            result["param_value"] = val
            results.append(result)
            logger.info(f"Sweep {param_name}={val}: trades={result.get('total_trades',0)} "
                        f"pnl={result.get('total_pnl',0):.2f} sharpe={result.get('sharpe')}")
        return results
