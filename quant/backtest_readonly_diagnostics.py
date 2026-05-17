"""Read-only diagnostics for canonical backtest result JSON files.

This module deliberately does not change backtester execution. It consumes the
JSON artifacts produced by docs/backtesting.md canonical commands and writes a
sidecar diagnostics file with tail gates, decay health, allocator previews, and
regime coverage.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from allocation_engine import allocate
from decay_monitor import rolling_decay_report
from evaluator_gates import evaluate_metrics
from regime_engine import classify_market_regime


def _float(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _trade_to_performance_trade(trade):
    pnl = trade.get("pnl")
    if pnl is None:
        pnl = trade.get("profit_loss")
    return {
        "status": "closed",
        "ticker": trade.get("ticker"),
        "strategy": trade.get("strategy"),
        "entry_date": trade.get("entry_date"),
        "exit_date": trade.get("exit_date"),
        "entry_price": trade.get("entry_price"),
        "exit_price": trade.get("exit_price"),
        "stop_price": trade.get("stop_price"),
        "shares": trade.get("shares"),
        "profit_loss": pnl,
    }


def _sample_std(values):
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return variance ** 0.5


def _skew(values):
    if len(values) < 3:
        return None
    mean = sum(values) / len(values)
    std = _sample_std(values)
    if not std:
        return None
    return round(sum(((x - mean) / std) ** 3 for x in values) / len(values), 4)


def _excess_kurtosis(values):
    if len(values) < 4:
        return None
    mean = sum(values) / len(values)
    std = _sample_std(values)
    if not std:
        return None
    return round(sum(((x - mean) / std) ** 4 for x in values) / len(values) - 3, 4)


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


def _top5_contribution(values):
    positives = sorted([v for v in values if v > 0], reverse=True)
    total = sum(positives)
    if total <= 0:
        return None
    return round(sum(positives[:5]) / total, 4)


def _hhi(values):
    positives = [v for v in values if v > 0]
    total = sum(positives)
    if total <= 0:
        return None
    return round(sum((v / total) ** 2 for v in positives), 4)


def _r_multiple(trade):
    entry = _float(trade.get("entry_price"))
    stop = _float(trade.get("stop_price"))
    shares = _float(trade.get("shares"))
    pnl = _float(trade.get("profit_loss"))
    if entry is None or stop is None or shares is None or pnl is None:
        return None
    if entry <= stop or shares <= 0:
        return None
    risk = (entry - stop) * shares
    if risk <= 0:
        return None
    return pnl / risk


def _metrics_from_result(result):
    trades = [_trade_to_performance_trade(t) for t in result.get("trades", [])]
    pnl_values = [_float(t.get("profit_loss"), 0.0) for t in trades]
    r_values = [r for r in (_r_multiple(t) for t in trades) if r is not None]

    wins = [x for x in pnl_values if x > 0]
    losses = [x for x in pnl_values if x <= 0]
    win_rate = len(wins) / len(pnl_values) if pnl_values else 0.0
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    ev = win_rate * avg_win + (1.0 - win_rate) * avg_loss
    avg_r = sum(r_values) / len(r_values) if r_values else None

    return {
        "total_trades": result.get("total_trades", len(trades)),
        "win_rate": result.get("win_rate", round(win_rate, 4)),
        "expected_value_usd": round(ev, 2),
        "avg_r_multiple": round(avg_r, 4) if avg_r is not None else None,
        "sharpe_ratio": result.get("sharpe_daily") or result.get("sharpe"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "r_skewness": _skew(r_values),
        "r_excess_kurtosis": _excess_kurtosis(r_values),
        "r_tail_ratio": _tail_ratio(r_values),
        "r_top_5_contribution_pct": _top5_contribution(r_values),
        "r_hhi_concentration": _hhi(r_values),
        "pnl_skewness": _skew(pnl_values),
        "pnl_excess_kurtosis": _excess_kurtosis(pnl_values),
        "pnl_tail_ratio": _tail_ratio(pnl_values),
        "pnl_top_5_contribution_pct": _top5_contribution(pnl_values),
        "pnl_hhi_concentration": _hhi(pnl_values),
    }


def _regime_coverage_from_trades(result):
    buckets = {}
    for trade in result.get("trades", []):
        bucket = trade.get("regime_exit_bucket") or "unknown"
        buckets.setdefault(bucket, {"trades": 0, "pnl": 0.0})
        buckets[bucket]["trades"] += 1
        buckets[bucket]["pnl"] += _float(trade.get("pnl"), 0.0)
    for value in buckets.values():
        value["pnl"] = round(value["pnl"], 2)
    return buckets


def build_diagnostics(result, baseline_metrics=None):
    metrics = _metrics_from_result(result)
    trades = [_trade_to_performance_trade(t) for t in result.get("trades", [])]
    baseline_metrics = baseline_metrics or metrics

    pseudo_context = {
        "market_regime": None,
        "theme_signal_count": 0,
        "breakout_signal_count": sum(
            1 for t in result.get("trades", [])
            if "breakout" in str(t.get("strategy", "")).lower()
        ),
    }
    regime_report = classify_market_regime(pseudo_context)

    allocation_preview = allocate([
        {
            "name": "core_backtest_result",
            "state": "core",
            "metrics": metrics,
        }
    ])

    return {
        "schema_version": 1,
        "read_only": True,
        "source_period": result.get("period"),
        "source_expected_value_score": result.get("expected_value_score"),
        "source_total_pnl": result.get("total_pnl"),
        "metrics_for_gates": metrics,
        "tail_gate_report": evaluate_metrics(metrics),
        "decay_report": rolling_decay_report(
            trades,
            baseline_metrics=baseline_metrics,
        ),
        "allocation_preview": allocation_preview,
        "regime_report": regime_report,
        "regime_exit_bucket_coverage": _regime_coverage_from_trades(result),
        "notes": [
            "Sidecar diagnostics only; no canonical backtest execution path is changed.",
            "Regime report is conservative when only result JSON is available; full daily regime classification should be wired read-only inside backtester later.",
            "Allocation preview shows what the allocator would do with this completed result as one core sleeve; it does not affect trades.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("result_json", help="Path to canonical backtest result JSON")
    parser.add_argument("--output", help="Output diagnostics JSON path")
    args = parser.parse_args()

    path = Path(args.result_json)
    result = json.loads(path.read_text(encoding="utf-8-sig"))
    diagnostics = build_diagnostics(result)

    output = Path(args.output) if args.output else path.with_name(path.stem + "_diagnostics.json")
    output.write_text(json.dumps(diagnostics, indent=2, ensure_ascii=False), encoding="utf-8")
    print(str(output))


if __name__ == "__main__":
    main()
