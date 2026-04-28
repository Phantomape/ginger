"""Displacement audit for the trend Industrials risk-sleeve shadow.

exp-20260427-029 showed that restoring even a 0.10x trend Industrials sleeve
hurt weak windows more than the targeted trades' own small PnL explains. This
audit compares baseline 0x vs 0.10x trade sets to estimate which trades were
added and which were displaced by slot/cash/path dependence.
"""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import portfolio_engine  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
from exp_20260427_029_trend_industrials_risk_sweep import WINDOWS  # noqa: E402


BASELINE_MULTIPLIER = 0.0
CANDIDATE_MULTIPLIER = 0.10


@contextmanager
def _patched_trend_industrials_multiplier(multiplier):
    original = portfolio_engine.TREND_INDUSTRIALS_RISK_MULTIPLIER
    portfolio_engine.TREND_INDUSTRIALS_RISK_MULTIPLIER = float(multiplier)
    try:
        yield
    finally:
        portfolio_engine.TREND_INDUSTRIALS_RISK_MULTIPLIER = original


def _run_window(universe, cfg, multiplier):
    with _patched_trend_industrials_multiplier(multiplier):
        engine = BacktestEngine(
            universe=universe,
            start=cfg["start"],
            end=cfg["end"],
            config={"REGIME_AWARE_EXIT": True},
            replay_llm=False,
            replay_news=False,
            data_dir=str(REPO_ROOT / "data"),
            ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
        )
        return engine.run()


def _trade_key(trade):
    return "|".join([
        str(trade.get("ticker")),
        str(trade.get("entry_date")),
        str(trade.get("exit_date")),
        str(trade.get("strategy")),
    ])


def _compact_trade(trade):
    return {
        "ticker": trade.get("ticker"),
        "strategy": trade.get("strategy"),
        "sector": trade.get("sector"),
        "entry_date": trade.get("entry_date"),
        "exit_date": trade.get("exit_date"),
        "pnl": trade.get("pnl"),
        "return_pct": trade.get("return_pct"),
        "exit_reason": trade.get("exit_reason"),
        "actual_risk_pct": trade.get("actual_risk_pct"),
        "sizing_multipliers": trade.get("sizing_multipliers") or {},
    }


def _metric_snapshot(result):
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "total_pnl": result.get("total_pnl"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "trade_count": result.get("total_trades"),
        "win_rate": result.get("win_rate"),
    }


def _delta(after, before, key):
    a = after.get(key)
    b = before.get(key)
    if a is None or b is None:
        return None
    return round(float(a) - float(b), 6)


def _sum_pnl(trades):
    return round(sum(float(trade.get("pnl") or 0.0) for trade in trades), 2)


def _is_candidate_industrials_trade(trade):
    multipliers = trade.get("sizing_multipliers") or {}
    return multipliers.get("trend_industrials_risk_multiplier_applied") == CANDIDATE_MULTIPLIER


def _audit_window(universe, label, cfg):
    baseline = _run_window(universe, cfg, BASELINE_MULTIPLIER)
    candidate = _run_window(universe, cfg, CANDIDATE_MULTIPLIER)
    baseline_by_key = {_trade_key(trade): trade for trade in baseline.get("trades", [])}
    candidate_by_key = {_trade_key(trade): trade for trade in candidate.get("trades", [])}
    added = [candidate_by_key[key] for key in sorted(set(candidate_by_key) - set(baseline_by_key))]
    removed = [baseline_by_key[key] for key in sorted(set(baseline_by_key) - set(candidate_by_key))]
    added_industrials = [trade for trade in added if _is_candidate_industrials_trade(trade)]
    baseline_metrics = _metric_snapshot(baseline)
    candidate_metrics = _metric_snapshot(candidate)
    metric_delta = {
        key: _delta(candidate_metrics, baseline_metrics, key)
        for key in baseline_metrics
    }
    return {
        "window": label,
        "start": cfg["start"],
        "end": cfg["end"],
        "baseline_multiplier": BASELINE_MULTIPLIER,
        "candidate_multiplier": CANDIDATE_MULTIPLIER,
        "baseline_metrics": baseline_metrics,
        "candidate_metrics": candidate_metrics,
        "delta_metrics": metric_delta,
        "added_trade_count": len(added),
        "removed_trade_count": len(removed),
        "added_trade_pnl": _sum_pnl(added),
        "removed_trade_pnl": _sum_pnl(removed),
        "added_industrials_trade_count": len(added_industrials),
        "added_industrials_trade_pnl": _sum_pnl(added_industrials),
        "net_trade_set_pnl_delta": round(_sum_pnl(added) - _sum_pnl(removed), 2),
        "added_trades": [_compact_trade(trade) for trade in added],
        "removed_trades": [_compact_trade(trade) for trade in removed],
    }


def run_audit():
    universe = get_universe()
    windows = [_audit_window(universe, label, cfg) for label, cfg in WINDOWS.items()]
    return {
        "experiment_id": "exp-20260427-030",
        "experiment_type": "displacement_audit",
        "is_tradable_change": False,
        "source_experiment": "exp-20260427-029",
        "hypothesis": (
            "Trend Industrials restoration fails mainly because small Industrials "
            "entries displace stronger trades or alter portfolio path, not because "
            "their own small PnL is large enough to explain the regression."
        ),
        "windows": windows,
        "summary": {
            "aggregate_added_trade_pnl": _sum_pnl(
                trade
                for window in windows
                for trade in window["added_trades"]
            ),
            "aggregate_removed_trade_pnl": _sum_pnl(
                trade
                for window in windows
                for trade in window["removed_trades"]
            ),
            "aggregate_net_trade_set_pnl_delta": round(
                sum(window["net_trade_set_pnl_delta"] for window in windows),
                2,
            ),
            "windows_with_negative_net_trade_set_delta": [
                window["window"]
                for window in windows
                if window["net_trade_set_pnl_delta"] < 0
            ],
        },
    }


def main():
    result = run_audit()
    out = REPO_ROOT / "data" / "exp_20260427_030_industrials_displacement_audit.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, ensure_ascii=False))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
