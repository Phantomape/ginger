"""exp-20260618-008: Portfolio equity-curve adaptive sizing (anti-Martingale).

Risk allocation. When trailing portfolio equity is in drawdown >5% below its
20-trading-day high-water mark, scale new entry notional to 0.7x. This is the
mathematical inverse of Martingale: size proportional to recent edge, not
inverse to it.

The single changed decision is EQUITY_CURVE_ADAPTIVE_SIZING=True in the
backtester config. No entry/exit signals, ranking, universe, stop/target,
risk multiplier rules, or sleeve logic is changed.

Nearest prior: exp-20260524-002 (per-signal heat haircut, rejected, different
mechanism — that was per-signal static, this is portfolio-level dynamic).
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path

EXPERIMENT_ID = "exp-20260618-008"
STEM = "equity_curve_adaptive_sizing"
TRIAL_FAMILY = "portfolio_equity_curve_adaptive_sizing"
CHANGED_VARIABLE = "EQUITY_CURVE_ADAPTIVE_SIZING"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
DATA_DIR = REPO_ROOT / "data"
ARTIFACT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

for p in (QUANT_DIR, QUANT_DIR / "experiments"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23", "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
    }),
    ("mid_weak", {
        "start": "2025-04-23", "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
    }),
    ("old_thin", {
        "start": "2024-10-02", "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
    }),
])

WAREHOUSE = str(DATA_DIR / "experiments" / "exp-20260519-030" / "warehouse_main.sqlite")

ADAPTIVE_CONFIG = {
    "EQUITY_CURVE_ADAPTIVE_SIZING": True,
    "EQUITY_CURVE_LOOKBACK_DAYS": 20,
    "EQUITY_CURVE_DD_THRESHOLD": 0.05,
    "EQUITY_CURVE_SCALE_FACTOR": 0.7,
}


def _run_window(label: str, window: dict, config_overrides: dict | None = None):
    universe = get_universe()
    engine = BacktestEngine(
        universe,
        start=window["start"],
        end=window["end"],
        config=config_overrides or {},
        ohlcv_warehouse_path=WAREHOUSE,
        ohlcv_warehouse_snapshot_source=str(REPO_ROOT / window["snapshot"]),
    )
    return engine.run()


def _extract_metrics(result: dict) -> dict:
    return {
        "expected_value_score": result.get("expected_value_score"),
        "strategy_total_return_pct": result.get("strategy_total_return_pct"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "total_trades": result.get("total_trades"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": result.get("survival_rate"),
    }


def _delta(before: dict, after: dict) -> dict:
    d = {}
    for k in before:
        bv = before.get(k)
        av = after.get(k)
        if isinstance(bv, (int, float)) and isinstance(av, (int, float)):
            d[k] = round(av - bv, 6)
    return d


def run():
    print(f"\n{'='*60}")
    print(f"  {EXPERIMENT_ID}: equity-curve adaptive sizing (anti-Martingale)")
    print(f"{'='*60}\n")

    results = {"before": {}, "after": {}, "delta": {}}

    for label, window in WINDOWS.items():
        print(f"\n--- {label} BEFORE (baseline) ---")
        before = _run_window(label, window)
        bm = _extract_metrics(before)
        results["before"][label] = bm
        print(f"  EV={bm['expected_value_score']:.4f}  PnL=${bm['total_pnl']:,.2f}  "
              f"DD={bm['max_drawdown_pct']:.2f}%  Sharpe={bm['sharpe_daily']:.2f}  "
              f"Trades={bm['total_trades']}  WR={bm['win_rate']:.1f}%")

        print(f"\n--- {label} AFTER (adaptive sizing) ---")
        after = _run_window(label, window, config_overrides=ADAPTIVE_CONFIG)
        am = _extract_metrics(after)
        results["after"][label] = am
        print(f"  EV={am['expected_value_score']:.4f}  PnL=${am['total_pnl']:,.2f}  "
              f"DD={am['max_drawdown_pct']:.2f}%  Sharpe={am['sharpe_daily']:.2f}  "
              f"Trades={am['total_trades']}  WR={am['win_rate']:.1f}%")

        delta = _delta(bm, am)
        results["delta"][label] = delta
        print(f"  DELTA: EV={delta.get('expected_value_score', 0):+.4f}  "
              f"PnL=${delta.get('total_pnl', 0):+,.2f}  "
              f"DD={delta.get('max_drawdown_pct', 0):+.2f}%  "
              f"Sharpe={delta.get('sharpe_daily', 0):+.2f}")

    # Aggregate
    agg_before_ev = sum(r["expected_value_score"] or 0 for r in results["before"].values())
    agg_after_ev = sum(r["expected_value_score"] or 0 for r in results["after"].values())
    agg_before_pnl = sum(r["total_pnl"] or 0 for r in results["before"].values())
    agg_after_pnl = sum(r["total_pnl"] or 0 for r in results["after"].values())

    ev_improved = sum(
        1 for label in WINDOWS
        if (results["delta"][label].get("expected_value_score", 0) or 0) > 0
    )
    ev_regressed = sum(
        1 for label in WINDOWS
        if (results["delta"][label].get("expected_value_score", 0) or 0) < 0
    )

    summary = {
        "experiment_id": EXPERIMENT_ID,
        "hypothesis": "Portfolio equity-curve adaptive sizing (anti-Martingale)",
        "changed_variable": CHANGED_VARIABLE,
        "config": ADAPTIVE_CONFIG,
        "aggregate_before_ev": round(agg_before_ev, 4),
        "aggregate_after_ev": round(agg_after_ev, 4),
        "aggregate_ev_delta": round(agg_after_ev - agg_before_ev, 4),
        "aggregate_ev_delta_pct": round(
            (agg_after_ev - agg_before_ev) / agg_before_ev * 100, 2
        ) if agg_before_ev else None,
        "aggregate_before_pnl": round(agg_before_pnl, 2),
        "aggregate_after_pnl": round(agg_after_pnl, 2),
        "aggregate_pnl_delta": round(agg_after_pnl - agg_before_pnl, 2),
        "ev_improved_windows": ev_improved,
        "ev_regressed_windows": ev_regressed,
        "windows": results,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }

    # Gate 4 auto-judgment
    gate4_checks = []
    if agg_after_ev < agg_before_ev:
        gate4_checks.append("aggregate_ev_not_positive")
    if agg_after_pnl < agg_before_pnl:
        gate4_checks.append("aggregate_pnl_not_positive")
    if ev_regressed >= 2:
        gate4_checks.append("window_ev_regression")
    if ev_improved < 2:
        gate4_checks.append("fewer_than_two_ev_improved_windows")
    for label in WINDOWS:
        dd_delta = results["delta"][label].get("max_drawdown_pct", 0) or 0
        if dd_delta > 0.5:
            gate4_checks.append(f"drawdown_worse_{label}")

    summary["gate4_failures"] = gate4_checks
    summary["gate4_passed"] = len(gate4_checks) == 0

    print(f"\n{'='*60}")
    print(f"  AGGREGATE")
    print(f"{'='*60}")
    print(f"  Before EV: {agg_before_ev:.4f}   After EV: {agg_after_ev:.4f}   "
          f"Delta: {agg_after_ev - agg_before_ev:+.4f}")
    print(f"  Before PnL: ${agg_before_pnl:,.2f}   After PnL: ${agg_after_pnl:,.2f}   "
          f"Delta: ${agg_after_pnl - agg_before_pnl:+,.2f}")
    print(f"  Windows improved: {ev_improved}   Regressed: {ev_regressed}")
    print(f"  Gate 4 passed: {summary['gate4_passed']}")
    if gate4_checks:
        print(f"  Gate 4 failures: {gate4_checks}")

    artifact_path = ARTIFACT_DIR / f"exp_20260618_008_{STEM}.json"
    artifact_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\n  Artifact: {artifact_path}")

    return summary


if __name__ == "__main__":
    run()
