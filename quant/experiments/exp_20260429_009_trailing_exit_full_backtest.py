#!/usr/bin/env python
"""
Full BacktestEngine replay for trailing-stop exit semantics.

This experiment intentionally uses BacktestEngine's existing trailing-stop
configuration.  It does not model production partial-reduce advice because
position_actions are explicitly not replayed by the backtester; that gap is
reported instead of papered over.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import mean


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "quant") not in sys.path:
    sys.path.insert(0, str(ROOT / "quant"))

from backtester import BacktestEngine  # noqa: E402
from filter import WATCHLIST  # noqa: E402


EXP_ID = "exp-20260429-009"
OUT = ROOT / "data" / "experiments" / EXP_ID / "exp_20260429_009_trailing_exit_full_backtest.json"

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
    "baseline_fixed_target": {
        "REGIME_AWARE_EXIT": True,
        "TRAIL_TRIGGER_ATR_MULT": 0,
        "TRAIL_OFFSET_ATR_MULT": 0,
    },
    # Historical exp-20260417-002 parameter cells, retested against the current
    # accepted stack and fixed snapshots.
    "trail_2_0_offset_1_5": {
        "REGIME_AWARE_EXIT": True,
        "TRAIL_TRIGGER_ATR_MULT": 2.0,
        "TRAIL_OFFSET_ATR_MULT": 1.5,
    },
    "trail_2_0_offset_2_0": {
        "REGIME_AWARE_EXIT": True,
        "TRAIL_TRIGGER_ATR_MULT": 2.0,
        "TRAIL_OFFSET_ATR_MULT": 2.0,
    },
    "trail_3_0_offset_2_0": {
        "REGIME_AWARE_EXIT": True,
        "TRAIL_TRIGGER_ATR_MULT": 3.0,
        "TRAIL_OFFSET_ATR_MULT": 2.0,
    },
    # Wider retest cells to check whether the current accepted stack changed the
    # conclusion enough to justify reopening the mechanism.
    "trail_3_0_offset_1_5": {
        "REGIME_AWARE_EXIT": True,
        "TRAIL_TRIGGER_ATR_MULT": 3.0,
        "TRAIL_OFFSET_ATR_MULT": 1.5,
    },
    "trail_4_0_offset_2_0": {
        "REGIME_AWARE_EXIT": True,
        "TRAIL_TRIGGER_ATR_MULT": 4.0,
        "TRAIL_OFFSET_ATR_MULT": 2.0,
    },
    "trail_4_0_offset_2_5": {
        "REGIME_AWARE_EXIT": True,
        "TRAIL_TRIGGER_ATR_MULT": 4.0,
        "TRAIL_OFFSET_ATR_MULT": 2.5,
    },
}


def compact(result: dict) -> dict:
    trades = result.get("trades", []) or []
    exits = {}
    for trade in trades:
        reason = trade.get("exit_reason") or "unknown"
        exits[reason] = exits.get(reason, 0) + 1
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "sharpe": result.get("sharpe"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": (result.get("benchmarks") or {}).get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": len(trades),
        "survival_rate": result.get("survival_rate"),
        "exit_reason_counts": exits,
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
    ]
    out = {}
    for key in keys:
        a = after.get(key)
        b = before.get(key)
        out[key] = round(a - b, 6) if isinstance(a, (int, float)) and isinstance(b, (int, float)) else None
    return out


def _sum_numbers(values: list[float | int | None]) -> float:
    return sum(x for x in values if isinstance(x, (int, float)))


def _count_positive(values: list[float | int | None]) -> int:
    return sum(1 for x in values if isinstance(x, (int, float)) and x > 0)


def _max_number(values: list[float | int | None]) -> float | None:
    nums = [x for x in values if isinstance(x, (int, float))]
    return max(nums) if nums else None


def main() -> None:
    metrics: dict[str, dict] = {}
    for variant, config in VARIANTS.items():
        metrics[variant] = {}
        for label, window in WINDOWS.items():
            print(f"running {variant} {label}", flush=True)
            metrics[variant][label] = run_one(window, config)

    baseline = metrics["baseline_fixed_target"]
    deltas = {
        variant: {
            label: delta(metrics[variant][label], baseline[label])
            for label in WINDOWS
        }
        for variant in VARIANTS
        if variant != "baseline_fixed_target"
    }

    aggregate = {}
    for variant, rows in deltas.items():
        ev_deltas = [rows[w]["expected_value_score"] for w in WINDOWS]
        pnl_deltas = [rows[w]["total_pnl"] for w in WINDOWS]
        dd_deltas = [rows[w]["max_drawdown_pct"] for w in WINDOWS]
        aggregate[variant] = {
            "ev_delta_sum": round(_sum_numbers(ev_deltas), 6),
            "pnl_delta_sum": round(_sum_numbers(pnl_deltas), 2),
            "windows_ev_improved": _count_positive(ev_deltas),
            "windows_pnl_improved": _count_positive(pnl_deltas),
            "max_drawdown_delta_max": (
                round(_max_number(dd_deltas), 6)
                if _max_number(dd_deltas) is not None
                else None
            ),
            "avg_ev_delta": round(mean([x for x in ev_deltas if isinstance(x, (int, float))]), 6),
        }

    best = max(aggregate, key=lambda k: aggregate[k]["ev_delta_sum"]) if aggregate else None
    result = {
        "experiment_id": EXP_ID,
        "status": "rejected",
        "hypothesis": (
            "Full BacktestEngine replay can determine whether trailing-stop exit "
            "semantics outperform the current fixed-target/stop accepted stack."
        ),
        "single_causal_variable": "backtested trailing-stop exit semantics",
        "production_parity_warning": (
            "BacktestEngine models full exits, not daily production partial-reduce "
            "position_actions. A profitable full-exit result would still need a "
            "shared production/backtest policy before promotion."
        ),
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
        "deltas_vs_baseline": deltas,
        "aggregate": aggregate,
        "best_variant_by_ev_delta_sum": best,
        "decision_basis": (
            "Accepted only if a trailing variant improves EV/PnL in a majority of "
            "fixed windows without unacceptable drawdown. Otherwise do not use "
            "trailing-stop profitability to justify repeated daily partial reduces."
        ),
    }
    if best:
        b = aggregate[best]
        result["status"] = (
            "accepted_candidate"
            if b["windows_ev_improved"] >= 2
            and b["pnl_delta_sum"] > 0
            and (
                b["max_drawdown_delta_max"] is None
                or b["max_drawdown_delta_max"] <= 0.01
            )
            else "rejected"
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "artifact": str(OUT),
        "baseline": baseline,
        "aggregate": aggregate,
        "best": best,
        "status": result["status"],
    }, indent=2))


if __name__ == "__main__":
    main()
