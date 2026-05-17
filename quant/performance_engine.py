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
               target_price=None, notes="", filepath=None, metadata=None):
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
    if metadata:
        trade["metadata"] = metadata

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
            _append_pilot_outcome_if_needed(trade)
            logger.info(f"Closed {trade_id}: P&L = ${pnl:,.2f}")
            return trade

    logger.warning(f"Trade '{trade_id}' not found or already closed")
    return None


def _append_pilot_outcome_if_needed(trade):
    metadata = trade.get("metadata") or {}
    pilot_meta = metadata.get("pilot_sleeve") or trade.get("pilot_sleeve") or {}
    decision_id = (
        pilot_meta.get("decision_id")
        or metadata.get("pilot_decision_id")
        or trade.get("pilot_decision_id")
    )
    if not decision_id:
        return

    planned_risk = None
    entry = trade.get("entry_price")
    stop = trade.get("stop_price")
    shares = trade.get("shares")
    if entry and stop and shares and entry > stop:
        planned_risk = round((entry - stop) * shares, 6)

    outcome = {
        "sleeve": pilot_meta.get("name") or metadata.get("sleeve"),
        "pilot_ticker": trade.get("ticker"),
        "pilot_pnl": trade.get("profit_loss"),
        "pilot_risk": planned_risk,
        "pilot_trade": {
            "trade_id": trade.get("trade_id"),
            "ticker": trade.get("ticker"),
            "strategy": trade.get("strategy"),
            "entry_date": trade.get("entry_date"),
            "exit_date": trade.get("exit_date"),
            "entry_price": trade.get("entry_price"),
            "exit_price": trade.get("exit_price"),
            "stop_price": trade.get("stop_price"),
            "shares": trade.get("shares"),
            "profit_loss": trade.get("profit_loss"),
            "planned_risk": planned_risk,
        },
        "counterfactual_outcomes": metadata.get("counterfactual_outcomes", []),
    }
    try:
        from candidate_competition_logger import append_decision_outcome

        decision_log_path = metadata.get("pilot_decision_log_path")
        if decision_log_path:
            append_decision_outcome(decision_id, outcome, path=decision_log_path)
        else:
            append_decision_outcome(decision_id, outcome)
    except Exception as exc:
        logger.error(f"Failed to append pilot outcome for {decision_id}: {exc}")


def _sample_std(values):
    import math as _math

    n = len(values)
    if n < 2:
        return None
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    return _math.sqrt(variance) if variance > 0 else 0.0


def _skewness(values):
    """Sample adjusted Fisher-Pearson skewness. None if insufficient history."""
    import math as _math

    n = len(values)
    if n < 3:
        return None
    mean = sum(values) / n
    std = _sample_std(values)
    if not std:
        return None
    m3 = sum((x - mean) ** 3 for x in values) / n
    g1 = m3 / (std ** 3)
    adjusted = (_math.sqrt(n * (n - 1)) / (n - 2)) * g1
    return round(adjusted, 4)


def _excess_kurtosis(values):
    """Sample adjusted excess kurtosis. 0 roughly means normal-like tails."""
    n = len(values)
    if n < 4:
        return None
    mean = sum(values) / n
    std = _sample_std(values)
    if not std:
        return None
    z4_sum = sum(((x - mean) / std) ** 4 for x in values)
    numerator = n * (n + 1) * z4_sum
    denominator = (n - 1) * (n - 2) * (n - 3)
    correction = 3 * ((n - 1) ** 2) / ((n - 2) * (n - 3))
    return round(numerator / denominator - correction, 4)


def _percentile(sorted_values, pct):
    """Linear-interpolated percentile for already-sorted values."""
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (len(sorted_values) - 1) * pct
    low = int(rank)
    high = min(low + 1, len(sorted_values) - 1)
    weight = rank - low
    return sorted_values[low] * (1 - weight) + sorted_values[high] * weight


def _tail_shape_metrics(values):
    """
    Distribution-shape diagnostics for trade/R-multiple returns.

    Designed to catch hidden short-vol / negative-skew profiles that Sharpe can miss:
      - skewness: positive is lottery-like, negative is crash-prone
      - excess_kurtosis: high values imply fat-tail / outlier dependence
      - tail_ratio: p95 gain magnitude divided by p5 loss magnitude
      - worst_5pct_avg: CVaR-style left-tail average
      - top_5_contribution_pct: how much total positive P&L depends on top 5 winners
      - hhi_concentration: Herfindahl concentration of positive contribution shares
    """
    clean = [float(v) for v in values if v is not None]
    n = len(clean)
    if n == 0:
        return {
            "skewness": None,
            "excess_kurtosis": None,
            "tail_ratio": None,
            "worst_5pct_avg": None,
            "top_5_contribution_pct": None,
            "hhi_concentration": None,
        }

    sorted_values = sorted(clean)
    p05 = _percentile(sorted_values, 0.05)
    p95 = _percentile(sorted_values, 0.95)
    tail_ratio = None
    if p05 is not None and p05 < 0 and p95 is not None:
        tail_ratio = round(abs(p95) / abs(p05), 4)

    tail_count = max(1, int(n * 0.05))
    worst_5pct_avg = round(sum(sorted_values[:tail_count]) / tail_count, 4)

    positives = sorted([x for x in clean if x > 0], reverse=True)
    positive_sum = sum(positives)
    if positive_sum > 0:
        top_5_contribution_pct = round(sum(positives[:5]) / positive_sum, 4)
        hhi_concentration = round(sum((x / positive_sum) ** 2 for x in positives), 4)
    else:
        top_5_contribution_pct = None
        hhi_concentration = None

    return {
        "skewness": _skewness(clean),
        "excess_kurtosis": _excess_kurtosis(clean),
        "tail_ratio": tail_ratio,
        "worst_5pct_avg": worst_5pct_avg,
        "top_5_contribution_pct": top_5_contribution_pct,
        "hhi_concentration": hhi_concentration,
    }


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
            sharpe_ratio, avg_r_multiple, total_pnl_usd, by_strategy,
            pnl_skewness, pnl_excess_kurtosis, pnl_tail_ratio,
            pnl_worst_5pct_avg, pnl_top_5_contribution_pct,
            pnl_hhi_concentration, r_skewness, r_excess_kurtosis,
            r_tail_ratio, r_worst_5pct_avg, r_top_5_contribution_pct,
            r_hhi_concentration
        }

    Shape fields:
        *_skewness                 - positive is right-tail convexity; negative is crash-prone
        *_excess_kurtosis          - high values flag fat-tail / outlier dependence
        *_tail_ratio               - p95 magnitude / p5 loss magnitude; >1 means right tail dominates
        *_worst_5pct_avg           - CVaR-style left-tail average
        *_top_5_contribution_pct   - top 5 winners / total positive contribution
        *_hhi_concentration        - positive contribution concentration, 0-1 scale
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

    pnl_series = [t["profit_loss"] for t in sorted_trades]
    pnl_shape = _tail_shape_metrics(pnl_series)
    r_shape = _tail_shape_metrics(r_series)

    # Per-strategy breakdown
    by_strategy = {}
    strategy_pnl = {}
    strategy_r = {}
    for t in closed:
        s = t["strategy"]
        if s not in by_strategy:
            by_strategy[s] = {"trades": 0, "wins": 0, "total_pnl": 0.0}
            strategy_pnl[s] = []
            strategy_r[s] = []
        by_strategy[s]["trades"]    += 1
        by_strategy[s]["total_pnl"]  = round(by_strategy[s]["total_pnl"] + t["profit_loss"], 2)
        strategy_pnl[s].append(t["profit_loss"])
        if t["profit_loss"] > 0:
            by_strategy[s]["wins"] += 1

        entry = t.get("entry_price")
        stop = t.get("stop_price")
        pnl = t.get("profit_loss")
        shares = t.get("shares")
        if entry and stop and pnl is not None and shares and entry > stop > 0:
            planned_risk = (entry - stop) * shares
            if planned_risk > 0:
                strategy_r[s].append(pnl / planned_risk)

    for s in by_strategy:
        n = by_strategy[s]["trades"]
        by_strategy[s]["win_rate"] = round(by_strategy[s]["wins"] / n, 4) if n else 0.0

        s_pnl_shape = _tail_shape_metrics(strategy_pnl[s])
        by_strategy[s].update({f"pnl_{k}": v for k, v in s_pnl_shape.items()})

        s_r_shape = _tail_shape_metrics(strategy_r[s])
        by_strategy[s].update({f"r_{k}": v for k, v in s_r_shape.items()})

    return {
        "total_trades":       len(closed),
        "open_trades":        len([t for t in trades if t["status"] == "open"]),
        "win_rate":           win_rate,
        "avg_win_usd":        avg_win,
        "avg_loss_usd":       avg_loss,
        "expected_value_usd": ev,
        "max_drawdown_usd":   round(max_dd, 2),
        "max_drawdown_pct":   max_dd_pct,
        "sharpe_ratio":       sharpe,
        "avg_r_multiple":     avg_r,
        "pnl_skewness":       pnl_shape["skewness"],
        "pnl_excess_kurtosis": pnl_shape["excess_kurtosis"],
        "pnl_tail_ratio":     pnl_shape["tail_ratio"],
        "pnl_worst_5pct_avg": pnl_shape["worst_5pct_avg"],
        "pnl_top_5_contribution_pct": pnl_shape["top_5_contribution_pct"],
        "pnl_hhi_concentration": pnl_shape["hhi_concentration"],
        "r_skewness":         r_shape["skewness"],
        "r_excess_kurtosis":   r_shape["excess_kurtosis"],
        "r_tail_ratio":       r_shape["tail_ratio"],
        "r_worst_5pct_avg":   r_shape["worst_5pct_avg"],
        "r_top_5_contribution_pct": r_shape["top_5_contribution_pct"],
        "r_hhi_concentration": r_shape["hhi_concentration"],
        "total_pnl_usd":      total_pnl,
        "by_strategy":        by_strategy,
    }
