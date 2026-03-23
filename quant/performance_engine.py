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

            # Execution cost model:
            #   Entry side: slippage 0.15% of entry_price (buy at slight premium)
            #   Exit  side: slippage 0.15% + commission 0.05% = 0.20% of exit_price
            # Using exit_price for exit cost is more accurate than entry_price:
            # a +20% winner exits at entry×1.20, so exit slippage is 20% higher.
            # Total cost ≈ 0.35% weighted average of entry/exit price.
            ENTRY_COST_PCT = 0.0015   # buy slippage
            EXIT_COST_PCT  = 0.0020   # sell slippage + commission
            cost = (trade["entry_price"] * ENTRY_COST_PCT
                    + exit_price         * EXIT_COST_PCT) * trade["shares"]
            pnl = (exit_price - trade["entry_price"]) * trade["shares"] - cost

            trade["status"]           = "closed"
            trade["exit_date"]        = exit_dt.strftime("%Y-%m-%d")
            trade["exit_price"]       = round(exit_price, 2)
            trade["execution_cost"]   = round(cost, 2)
            trade["profit_loss"]      = round(pnl, 2)
            trade["holding_days"]     = (exit_dt - entry_dt).days
            if notes:
                trade["notes"] = (trade["notes"] + " | " + notes).strip(" | ")

            save_trades(trades, filepath)
            logger.info(f"Closed {trade_id}: P&L = ${pnl:,.2f}")
            return trade

    logger.warning(f"Trade '{trade_id}' not found or already closed")
    return None


def compute_metrics(filepath=None, portfolio_value=None):
    """
    Compute strategy performance metrics from closed trades.

    Args:
        filepath        (str):   Path to trades JSON (default: data/trades.json)
        portfolio_value (float): Current portfolio value for % drawdown calculation.
                                 If None, falls back to using peak cumulative P&L as denominator.

    Returns:
        dict: {
            total_trades, open_trades, win_rate, avg_win_usd, avg_loss_usd,
            expected_value_usd, max_drawdown_usd, max_drawdown_pct,
            sharpe_ratio, avg_r_multiple, total_pnl_usd, by_strategy
        }

    New fields vs previous version:
        max_drawdown_pct  - max drawdown as % of portfolio (requires portfolio_value or uses peak)
        sharpe_ratio      - annualized Sharpe using R-multiples, 30 trades/year assumed (not 252 — matches system's actual 2-3 trades/month cadence)
        avg_r_multiple    - avg P&L / planned risk per trade (requires stop_price and entry_price)
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

    # Max drawdown from cumulative P&L curve (dollar and %)
    sorted_trades = sorted(closed, key=lambda x: x.get("exit_date") or "")
    cumulative    = 0.0
    peak          = 0.0
    max_dd        = 0.0
    for t in sorted_trades:
        cumulative += t["profit_loss"]
        if cumulative > peak:
            peak = cumulative
        dd = peak - cumulative
        if dd > max_dd:
            max_dd = dd

    # % drawdown: use portfolio_value if provided; else peak cumulative P&L as proxy denominator
    dd_denominator  = portfolio_value if portfolio_value and portfolio_value > 0 else (peak if peak > 0 else None)
    max_dd_pct      = round(max_dd / dd_denominator, 4) if dd_denominator else None

    # Sharpe ratio using R-multiples (actual P&L / planned risk per trade).
    # R-multiples normalise for position size differences (1% risk rule), making
    # per-trade returns comparable regardless of capital deployed.
    #
    # Annualisation: derive trade frequency from actual observed date span rather
    # than a fixed assumption of 30/year.  Using a fixed value causes Sharpe to be
    # inflated by sqrt(30/actual) when true cadence is lower (e.g. 10 trades/year
    # → Sharpe inflated ×1.73), masking poor risk-adjusted performance.
    # Formula:
    #   actual_freq  = total_trades / observed_years   (min 1 trade, min 1 year)
    #   Sharpe = mean(R) / std(R) × sqrt(actual_freq)
    # Falls back to ANNUAL_TRADE_FREQ_FALLBACK (30) when date span < 30 days
    # (not enough history to estimate frequency reliably).
    # R > 1.0 = captured more than planned risk per trade; R < 0 = loss.
    ANNUAL_TRADE_FREQ_FALLBACK = 30   # used when history < 30 days
    _first_date = sorted_trades[0].get("exit_date") or "" if sorted_trades else ""
    _last_date  = sorted_trades[-1].get("exit_date") or "" if sorted_trades else ""
    try:
        _span_days = (datetime.strptime(_last_date, "%Y-%m-%d")
                      - datetime.strptime(_first_date, "%Y-%m-%d")).days
    except Exception:
        _span_days = 0
    if _span_days >= 30 and len(closed) >= 2:
        _observed_years   = max(_span_days / 365.25, 1 / 12)   # min 1 month
        ANNUAL_TRADE_FREQ = len(closed) / _observed_years
    else:
        ANNUAL_TRADE_FREQ = ANNUAL_TRADE_FREQ_FALLBACK

    import math as _math

    # Build R-multiple series (same loop as avg_r_multiple below, but keep it here
    # so Sharpe and avg_r use the same denominator).
    r_series = []
    for t in sorted_trades:
        entry  = t.get("entry_price")
        stop   = t.get("stop_price")
        pnl    = t.get("profit_loss")
        shares = t.get("shares")
        if entry and stop and pnl is not None and shares and entry > stop > 0:
            planned_risk = (entry - stop) * shares
            if planned_risk > 0:
                r_series.append(pnl / planned_risk)

    n = len(r_series)
    if n >= 2:
        mean_r    = sum(r_series) / n
        variance  = sum((x - mean_r) ** 2 for x in r_series) / (n - 1)
        std_r     = _math.sqrt(variance) if variance > 0 else 0.0
        sharpe    = round((mean_r / std_r) * _math.sqrt(ANNUAL_TRADE_FREQ), 2) if std_r > 0 else None
    else:
        sharpe = None

    # Average R-multiple: reuse r_series computed for Sharpe above.
    # R > 1 means you captured more than your initial risk amount on average.
    avg_r = round(sum(r_series) / len(r_series), 3) if r_series else None

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
        "max_drawdown_pct":   max_dd_pct,        # NEW: % of portfolio (requires portfolio_value)
        "sharpe_ratio":       sharpe,             # NEW: per-trade Sharpe (annualised proxy)
        "avg_r_multiple":     avg_r,              # NEW: actual P&L / planned risk per trade
        "total_pnl_usd":      total_pnl,
        "by_strategy":        by_strategy,
    }
