"""Shadow sweep for the trend Industrials zero-risk sleeve.

Hypothesis:
    Recent no-shares attribution shows `trend_industrials_risk_multiplier=0`
    missed several forward opportunities, including one large DE move. A small
    non-zero risk sleeve may recover some upside without fully reopening the
    old Industrials trend drag.

This runner is observation-only. It temporarily patches
`portfolio_engine.TREND_INDUSTRIALS_RISK_MULTIPLIER` in-process and runs fixed
snapshot backtests across non-overlapping windows.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import OrderedDict
from contextlib import contextmanager
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import portfolio_engine  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
    }),
])


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
        "survival_rate": result.get("survival_rate"),
        "entry_reason_counts": (
            (result.get("entry_execution_attribution") or {}).get("reason_counts")
        ),
    }


def _delta(after, before, key):
    a = after.get(key)
    b = before.get(key)
    if a is None or b is None:
        return None
    return round(float(a) - float(b), 6)


def _is_trend_industrials_trade(trade):
    return (
        trade.get("strategy") == "trend_long"
        and trade.get("sector") == "Industrials"
    )


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


def _window_rows(universe, label, cfg, multipliers):
    baseline = None
    rows = []
    for multiplier in multipliers:
        result = _run_window(universe, cfg, multiplier)
        metrics = _metric_snapshot(result)
        if baseline is None:
            baseline = metrics
        targeted_trades = [
            trade for trade in result.get("trades", [])
            if _is_trend_industrials_trade(trade)
        ]
        rows.append({
            "window": label,
            "start": cfg["start"],
            "end": cfg["end"],
            "snapshot": cfg["snapshot"],
            "trend_industrials_risk_multiplier": float(multiplier),
            "metrics": metrics,
            "delta_vs_0x": {
                key: _delta(metrics, baseline, key)
                for key in (
                    "expected_value_score",
                    "sharpe_daily",
                    "total_return_pct",
                    "total_pnl",
                    "max_drawdown_pct",
                    "trade_count",
                    "win_rate",
                    "survival_rate",
                )
            },
            "targeted_trade_count": len(targeted_trades),
            "targeted_trade_pnl_usd": round(
                sum(float(trade.get("pnl") or 0.0) for trade in targeted_trades),
                2,
            ),
            "targeted_trade_examples": [
                {
                    "ticker": trade.get("ticker"),
                    "entry_date": trade.get("entry_date"),
                    "exit_date": trade.get("exit_date"),
                    "pnl": trade.get("pnl"),
                    "actual_risk_pct": trade.get("actual_risk_pct"),
                    "sizing_multipliers": trade.get("sizing_multipliers") or {},
                }
                for trade in targeted_trades[:8]
            ],
        })
        print(
            f"[{label}] mult={multiplier:.2f} "
            f"EV={metrics['expected_value_score']} "
            f"PnL={metrics['total_pnl']} "
            f"trades={metrics['trade_count']} "
            f"targeted={len(targeted_trades)}"
        )
    return rows


def _decision_support(rows):
    by_multiplier = {}
    for row in rows:
        multiplier = row["trend_industrials_risk_multiplier"]
        if multiplier == 0.0:
            continue
        bucket = by_multiplier.setdefault(multiplier, {
            "windows": 0,
            "ev_improved_windows": 0,
            "pnl_improved_windows": 0,
            "material_ev_regressions": [],
            "ev_delta_sum": 0.0,
            "pnl_delta_sum": 0.0,
        })
        delta = row["delta_vs_0x"]
        ev_delta = delta.get("expected_value_score") or 0.0
        pnl_delta = delta.get("total_pnl") or 0.0
        bucket["windows"] += 1
        bucket["ev_delta_sum"] = round(bucket["ev_delta_sum"] + ev_delta, 6)
        bucket["pnl_delta_sum"] = round(bucket["pnl_delta_sum"] + pnl_delta, 2)
        if ev_delta > 0:
            bucket["ev_improved_windows"] += 1
        if pnl_delta > 0:
            bucket["pnl_improved_windows"] += 1
        if ev_delta <= -0.05:
            bucket["material_ev_regressions"].append(row["window"])

    candidates = []
    for multiplier, summary in sorted(by_multiplier.items()):
        promote = (
            summary["ev_improved_windows"] >= 2
            and not summary["material_ev_regressions"]
        )
        candidates.append({
            "trend_industrials_risk_multiplier": multiplier,
            **summary,
            "promote_candidate": promote,
        })

    best = None
    if candidates:
        best = max(
            candidates,
            key=lambda item: (
                item["promote_candidate"],
                item["ev_improved_windows"],
                item["ev_delta_sum"],
                item["pnl_delta_sum"],
            ),
        )
    return {
        "baseline_multiplier": 0.0,
        "candidate_summaries": candidates,
        "best_candidate": best,
        "decision": (
            "promote_to_real_backtest_candidate"
            if best and best["promote_candidate"]
            else "reject_shadow_sweep"
        ),
        "note": (
            "Promotion only means this shadow deserves a normal strategy-change "
            "backtest gate; it is not itself an accepted production rule."
        ),
    }


def run_sweep(multipliers):
    universe = get_universe()
    rows = []
    for label, cfg in WINDOWS.items():
        rows.extend(_window_rows(universe, label, cfg, multipliers))
    return {
        "experiment_id": "exp-20260427-029",
        "experiment_type": "shadow_multiplier_sweep",
        "is_tradable_change": False,
        "single_causal_variable": "TREND_INDUSTRIALS_RISK_MULTIPLIER",
        "hypothesis": (
            "A small non-zero trend Industrials risk sleeve may recover missed "
            "upside from no_shares events without reopening full-size drag."
        ),
        "windows": WINDOWS,
        "rows": rows,
        "decision_support": _decision_support(rows),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--multipliers",
        nargs="+",
        type=float,
        default=[0.0, 0.10, 0.25, 0.50, 1.0],
    )
    parser.add_argument(
        "--out",
        default=str(REPO_ROOT / "data" / "exp_20260427_029_trend_industrials_risk_sweep.json"),
    )
    args = parser.parse_args()

    result = run_sweep(args.multipliers)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result["decision_support"], indent=2, ensure_ascii=False))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
