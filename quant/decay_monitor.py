"""Rolling decay monitor for live/backtest strategy health.

The goal is to catch slow strategy decay before it becomes a large drawdown.
This module works on closed trade dictionaries and produces compact diagnostics
that allocator/evaluator code can consume later.
"""

from __future__ import annotations

from datetime import datetime

from evaluator_gates import evaluate_metrics


DEFAULT_WINDOWS = (10, 20, 50)


def _float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _closed_trades(trades):
    out = []
    for trade in trades or []:
        if trade.get("status") != "closed":
            continue
        if trade.get("profit_loss") is None:
            continue
        out.append(trade)
    return sorted(out, key=lambda t: t.get("exit_date") or "")


def _r_multiple(trade):
    entry = _float(trade.get("entry_price"))
    stop = _float(trade.get("stop_price"))
    shares = _float(trade.get("shares"))
    pnl = trade.get("profit_loss")
    if pnl is None or entry <= stop or shares <= 0:
        return None
    risk = (entry - stop) * shares
    if risk <= 0:
        return None
    return _float(pnl) / risk


def _sample_std(values):
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return variance ** 0.5


def _simple_skew(values):
    if len(values) < 3:
        return None
    mean = sum(values) / len(values)
    std = _sample_std(values)
    if not std:
        return None
    return round(sum(((x - mean) / std) ** 3 for x in values) / len(values), 4)


def _percentile(sorted_values, pct):
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (len(sorted_values) - 1) * pct
    low = int(rank)
    high = min(low + 1, len(sorted_values) - 1)
    weight = rank - low
    return sorted_values[low] * (1 - weight) + sorted_values[high] * weight


def _tail_ratio(values):
    if len(values) < 5:
        return None
    ordered = sorted(values)
    p05 = _percentile(ordered, 0.05)
    p95 = _percentile(ordered, 0.95)
    if p05 is None or p95 is None or p05 >= 0:
        return None
    return round(abs(p95) / abs(p05), 4)


def _window_metrics(window_trades):
    pnl_values = [_float(t.get("profit_loss")) for t in window_trades]
    r_values = [r for r in (_r_multiple(t) for t in window_trades) if r is not None]
    wins = [x for x in pnl_values if x > 0]
    losses = [x for x in pnl_values if x <= 0]

    win_rate = len(wins) / len(pnl_values) if pnl_values else 0.0
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    ev = win_rate * avg_win + (1.0 - win_rate) * avg_loss

    mean_r = sum(r_values) / len(r_values) if r_values else None
    std_r = _sample_std(r_values)
    sharpe_like = mean_r / std_r if mean_r is not None and std_r and std_r > 0 else None

    return {
        "total_trades": len(window_trades),
        "win_rate": round(win_rate, 4),
        "expected_value_usd": round(ev, 2),
        "avg_r_multiple": round(mean_r, 4) if mean_r is not None else None,
        "sharpe_like": round(sharpe_like, 4) if sharpe_like is not None else None,
        "r_skewness": _simple_skew(r_values),
        "r_tail_ratio": _tail_ratio(r_values),
        "r_worst_trade": round(min(r_values), 4) if r_values else None,
        "pnl_worst_trade": round(min(pnl_values), 2) if pnl_values else None,
        "total_pnl_usd": round(sum(pnl_values), 2),
    }


def rolling_decay_report(
    trades,
    *,
    windows=DEFAULT_WINDOWS,
    baseline_metrics=None,
    min_live_r_gap=0.50,
):
    """Build rolling diagnostics from closed trades.

    baseline_metrics can include backtest_avg_r_multiple or avg_r_multiple.
    A large gap between baseline R and rolling live R is flagged as decay.
    """
    closed = _closed_trades(trades)
    baseline_metrics = baseline_metrics or {}
    baseline_r = baseline_metrics.get("backtest_avg_r_multiple")
    if baseline_r is None:
        baseline_r = baseline_metrics.get("avg_r_multiple")
    baseline_r = _float(baseline_r, None)

    by_window = {}
    flags = []

    for window in windows:
        sample = closed[-int(window):]
        metrics = _window_metrics(sample)
        by_window[str(window)] = metrics

        live_r = metrics.get("avg_r_multiple")
        if baseline_r is not None and live_r is not None:
            gap = baseline_r - live_r
            metrics["live_vs_baseline_r_gap"] = round(gap, 4)
            if gap > min_live_r_gap:
                flags.append(f"decay_r_gap_{window}")

        if metrics.get("avg_r_multiple") is not None and metrics["avg_r_multiple"] <= 0:
            flags.append(f"non_positive_rolling_r_{window}")
        if metrics.get("expected_value_usd") <= 0:
            flags.append(f"non_positive_rolling_ev_{window}")
        if metrics.get("r_skewness") is not None and metrics["r_skewness"] < -1.0:
            flags.append(f"negative_rolling_skew_{window}")
        if metrics.get("r_tail_ratio") is not None and metrics["r_tail_ratio"] < 0.8:
            flags.append(f"weak_rolling_tail_ratio_{window}")

    latest_gate_metrics = dict(baseline_metrics)
    if by_window:
        window_key = str(max(int(w) for w in by_window.keys()))
        latest = by_window[window_key]
        latest_gate_metrics.update({
            "total_trades": latest.get("total_trades"),
            "expected_value_usd": latest.get("expected_value_usd"),
            "avg_r_multiple": latest.get("avg_r_multiple"),
            "r_skewness": latest.get("r_skewness"),
            "r_tail_ratio": latest.get("r_tail_ratio"),
            "live_avg_r_multiple": latest.get("avg_r_multiple"),
            "backtest_avg_r_multiple": baseline_r,
        })

    gate_report = evaluate_metrics(latest_gate_metrics) if closed else None

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "closed_trades": len(closed),
        "baseline_avg_r_multiple": baseline_r,
        "windows": by_window,
        "decay_flags": sorted(set(flags)),
        "gate_report": gate_report,
    }
