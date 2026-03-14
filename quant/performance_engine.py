"""
Performance Engine (Critical): Track realized P&L and evaluate strategies.

Trade diary stored in data/trades.json.

Each trade records:
  trade_id, ticker, strategy, entry_price, exit_price,
  position_size (shares), profit_loss, holding_period

Metrics computed:
  win_rate, average_win, average_loss, expected_value,
  max_drawdown, strategy_performance

The system must evaluate strategies using realized P&L, not prediction accuracy.
"""

import os
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

_DEFAULT_TRADES_FILE = os.path.join(
    os.path.dirname(__file__), '..', 'data', 'trades.json'
)


def _resolve_path(filepath):
    return filepath or _DEFAULT_TRADES_FILE


def load_trades(filepath=None):
    """Load all trades from the diary. Returns empty list if file not found."""
    path = _resolve_path(filepath)
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load trades: {e}")
        return []


def save_trades(trades, filepath=None):
    """Persist trades to JSON file."""
    path = _resolve_path(filepath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(trades, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Failed to save trades: {e}")
        return False


def open_trade(ticker, strategy, entry_price, stop_price, shares,
               target_price=None, notes="", filepath=None):
    """
    Record a new trade entry to the diary.

    Returns:
        str: trade_id  (e.g. "NVDA_20260312_143022")
    """
    trades = load_trades(filepath)

    trade_id = f"{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    trade = {
        "trade_id":     trade_id,
        "ticker":       ticker,
        "strategy":     strategy,
        "status":       "open",
        "entry_date":   datetime.now().strftime("%Y-%m-%d"),
        "entry_price":  round(entry_price, 2),
        "stop_price":   round(stop_price, 2),
        "target_price": round(target_price, 2) if target_price is not None else None,
        "shares":       shares,
        "exit_date":    None,
        "exit_price":   None,
        "profit_loss":  None,
        "holding_days": None,
        "notes":        notes,
    }

    trades.append(trade)
    save_trades(trades, filepath)
    logger.info(f"Opened trade {trade_id}: {ticker} {strategy} @ {entry_price}")
    return trade_id


def close_trade(trade_id, exit_price, notes="", filepath=None):
    """
    Mark a trade as closed and compute P&L.

    Args:
        trade_id   (str):   ID returned by open_trade()
        exit_price (float): Actual exit price

    Returns:
        dict: Closed trade record, or None if not found
    """
    trades = load_trades(filepath)

    for trade in trades:
        if trade["trade_id"] == trade_id and trade["status"] == "open":
            entry_dt = datetime.strptime(trade["entry_date"], "%Y-%m-%d")
            exit_dt  = datetime.now()

            pnl = (exit_price - trade["entry_price"]) * trade["shares"]

            trade["status"]       = "closed"
            trade["exit_date"]    = exit_dt.strftime("%Y-%m-%d")
            trade["exit_price"]   = round(exit_price, 2)
            trade["profit_loss"]  = round(pnl, 2)
            trade["holding_days"] = (exit_dt - entry_dt).days
            if notes:
                trade["notes"] = (trade["notes"] + " | " + notes).strip(" | ")

            save_trades(trades, filepath)
            logger.info(f"Closed {trade_id}: P&L = ${pnl:,.2f}")
            return trade

    logger.warning(f"Trade '{trade_id}' not found or already closed")
    return None


def compute_metrics(filepath=None):
    """
    Compute strategy performance metrics from closed trades.

    Returns:
        dict: {
            total_trades, open_trades, win_rate, avg_win_usd, avg_loss_usd,
            expected_value_usd, max_drawdown_usd, total_pnl_usd, by_strategy
        }
    """
    trades = load_trades(filepath)
    closed = [t for t in trades if t["status"] == "closed"
              and t.get("profit_loss") is not None]

    if not closed:
        return {
            "total_trades": 0,
            "open_trades":  len([t for t in trades if t["status"] == "open"]),
            "note":         "No closed trades yet. Record trades to start tracking P&L.",
        }

    wins   = [t["profit_loss"] for t in closed if t["profit_loss"] >  0]
    losses = [t["profit_loss"] for t in closed if t["profit_loss"] <= 0]

    win_rate  = round(len(wins) / len(closed), 4) if closed else 0.0
    avg_win   = round(sum(wins)   / len(wins),   2) if wins   else 0.0
    avg_loss  = round(sum(losses) / len(losses), 2) if losses else 0.0
    total_pnl = round(sum(t["profit_loss"] for t in closed), 2)

    # Expected value = win_rate × avg_win + loss_rate × avg_loss
    loss_rate = 1.0 - win_rate
    ev        = round(win_rate * avg_win + loss_rate * avg_loss, 2)

    # Max drawdown from cumulative P&L curve
    cumulative = 0.0
    peak       = 0.0
    max_dd     = 0.0
    for t in sorted(closed, key=lambda x: x.get("exit_date") or ""):
        cumulative += t["profit_loss"]
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd

    # Per-strategy breakdown
    by_strategy = {}
    for t in closed:
        s = t["strategy"]
        if s not in by_strategy:
            by_strategy[s] = {"trades": 0, "wins": 0, "total_pnl": 0.0}
        by_strategy[s]["trades"]    += 1
        by_strategy[s]["total_pnl"]  = round(by_strategy[s]["total_pnl"] + t["profit_loss"], 2)
        if t["profit_loss"] > 0:
            by_strategy[s]["wins"] += 1
    for s in by_strategy:
        n = by_strategy[s]["trades"]
        by_strategy[s]["win_rate"] = round(by_strategy[s]["wins"] / n, 4) if n else 0.0

    return {
        "total_trades":       len(closed),
        "open_trades":        len([t for t in trades if t["status"] == "open"]),
        "win_rate":           win_rate,
        "avg_win_usd":        avg_win,
        "avg_loss_usd":       avg_loss,
        "expected_value_usd": ev,
        "max_drawdown_usd":   round(max_dd, 2),
        "total_pnl_usd":      total_pnl,
        "by_strategy":        by_strategy,
    }
