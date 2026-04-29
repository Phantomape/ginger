#!/usr/bin/env python
"""Fixed-window replay for production trailing partial-reduce parity."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "quant") not in sys.path:
    sys.path.insert(0, str(ROOT / "quant"))

from backtester import BacktestEngine  # noqa: E402
from filter import WATCHLIST  # noqa: E402


EXP_ID = "exp-20260429-017"
OUT = (
    ROOT
    / "data"
    / "experiments"
    / "exp-20260429-011"
    / "exp-20260429-011_trailing_partial_reduce_parity.json"
)

WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": ROOT / "data" / "ohlcv_snapshot_20251023_20260421.json",
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": ROOT / "data" / "ohlcv_snapshot_20250423_20251022.json",
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": ROOT / "data" / "ohlcv_snapshot_20241002_20250422.json",
    },
}

VARIANTS = {
    "before_trailing_partial_reduce_enabled": {
        "REGIME_AWARE_EXIT": True,
        "REPLAY_PARTIAL_REDUCES": True,
        "TRAILING_PARTIAL_REDUCE_ENABLED": True,
    },
    "after_trailing_partial_reduce_disabled": {
        "REGIME_AWARE_EXIT": True,
        "REPLAY_PARTIAL_REDUCES": True,
        "TRAILING_PARTIAL_REDUCE_ENABLED": False,
    },
}


def compact(result: dict) -> dict:
    trades = result.get("trades", []) or []
    partial = result.get("partial_reduce_attribution") or {}
    exit_counts = {}
    for trade in trades:
        reason = trade.get("exit_reason") or "unknown"
        exit_counts[reason] = exit_counts.get(reason, 0) + 1
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "sharpe": result.get("sharpe"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": (
            (result.get("benchmarks") or {}).get("strategy_total_return_pct")
        ),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": len(trades),
        "survival_rate": result.get("survival_rate"),
        "exit_reason_counts": exit_counts,
        "partial_reduce_scheduled": partial.get("scheduled"),
        "partial_reduce_executed": partial.get("executed"),
        "partial_reduce_skipped": partial.get("skipped"),
        "partial_reduce_events": partial.get("events", []),
    }


def run_one(window: dict, config: dict) -> dict:
    engine = BacktestEngine(
        list(WATCHLIST),
        start=window["start"],
        end=window["end"],
        config=config,
        ohlcv_snapshot_path=str(window["snapshot"]),
    )
    return compact(engine.run())


def delta(after: dict, before: dict) -> dict:
    keys = [
        "expected_value_score",
        "sharpe_daily",
        "sharpe",
        "total_pnl",
        "total_return_pct",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "survival_rate",
        "partial_reduce_scheduled",
        "partial_reduce_executed",
    ]
    out = {}
    for key in keys:
        a = after.get(key)
        b = before.get(key)
        out[key] = (
            round(a - b, 6)
            if isinstance(a, (int, float)) and isinstance(b, (int, float))
            else None
        )
    return out


def main() -> None:
    metrics: dict[str, dict] = {}
    for variant, config in VARIANTS.items():
        metrics[variant] = {}
        for label, window in WINDOWS.items():
            print(f"running {variant} {label}", flush=True)
            metrics[variant][label] = run_one(window, config)

    baseline = metrics["before_trailing_partial_reduce_enabled"]
    replay = metrics["after_trailing_partial_reduce_disabled"]
    deltas = {
        label: delta(replay[label], baseline[label])
        for label in WINDOWS
    }
    ev_deltas = [
        row["expected_value_score"]
        for row in deltas.values()
        if isinstance(row.get("expected_value_score"), (int, float))
    ]
    pnl_deltas = [
        row["total_pnl"]
        for row in deltas.values()
        if isinstance(row.get("total_pnl"), (int, float))
    ]
    aggregate = {
        "ev_delta_sum": round(sum(ev_deltas), 6),
        "pnl_delta_sum": round(sum(pnl_deltas), 2),
        "windows_ev_improved": sum(1 for x in ev_deltas if x > 0),
        "windows_pnl_improved": sum(1 for x in pnl_deltas if x > 0),
        "partial_reduce_events_before_enabled": sum(
            baseline[label].get("partial_reduce_executed") or 0 for label in WINDOWS
        ),
        "partial_reduce_events_after_disabled": sum(
            replay[label].get("partial_reduce_executed") or 0 for label in WINDOWS
        ),
    }
    accepted = (
        aggregate["windows_ev_improved"] >= 2
        or aggregate["windows_pnl_improved"] >= 2
    )

    result = {
        "experiment_id": EXP_ID,
        "status": "accepted" if accepted else "rejected",
        "hypothesis": (
            "Disabling production TRAILING_STOP partial-reduce actions avoids "
            "repeated winner trims and improves fixed-window EV/PnL."
        ),
        "single_causal_variable": (
            "disable trailing-stop partial-reduce actions"
        ),
        "production_impact": {
            "shared_policy_changed": True,
            "backtester_adapter_changed": True,
            "run_adapter_changed": False,
            "replay_only": False,
            "parity_test_added": True,
        },
        "windows": {
            label: {
                "start": window["start"],
                "end": window["end"],
                "snapshot": str(window["snapshot"]),
            }
            for label, window in WINDOWS.items()
        },
        "variants": VARIANTS,
        "metrics": metrics,
        "deltas_disabled_vs_enabled": deltas,
        "aggregate": aggregate,
        "decision_basis": (
            "Accepted if disabled improves EV or PnL in a majority of fixed "
            "windows without changing any non-trailing exit rules."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"artifact": str(OUT), "aggregate": aggregate}, indent=2))


if __name__ == "__main__":
    main()
