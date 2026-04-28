"""exp-20260428-025 initial position cap allocation sweep.

Experiment-only alpha search. Tests whether the accepted stack allocates too
much capital to initial fills and leaves too little room for follow-through
winner add-ons. This changes only the initial position cap used by sizing;
add-on trigger/cap, entries, exits, gap cancels, scarce-slot routing, LLM/news,
and earnings remain locked.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import portfolio_engine  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from constants import ADDON_MAX_POSITION_PCT, MAX_POSITION_PCT  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260428-025"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260428_025_initial_position_cap_allocation.json"

WINDOWS = OrderedDict([
    ("late_strong", {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "state_note": "slow-melt bull / accepted-stack dominant tape",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "state_note": "rotation-heavy bull where strategy makes money but lags indexes",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "state_note": "mixed-to-weak older tape with lower win rate",
    }),
])

VARIANTS = OrderedDict([
    ("baseline_initial_cap_25pct", 0.25),
    ("initial_cap_15pct", 0.15),
    ("initial_cap_20pct", 0.20),
    ("initial_cap_30pct", 0.30),
    ("initial_cap_35pct", 0.35),
    ("initial_cap_40pct", 0.40),
])


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    addon = result.get("addon_attribution") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "addon_scheduled": addon.get("scheduled"),
        "addon_executed": addon.get("executed"),
        "addon_skipped": addon.get("skipped"),
        "addon_checkpoint_rejected": addon.get("checkpoint_rejected"),
    }


def _delta(after: dict, before: dict) -> dict:
    out = {}
    for key, before_value in before.items():
        after_value = after.get(key)
        if isinstance(before_value, (int, float)) and isinstance(after_value, (int, float)):
            out[key] = round(after_value - before_value, 6)
        else:
            out[key] = None
    return out


def _run_window(universe: list[str], cfg: dict, initial_position_cap: float) -> dict:
    original_cap = portfolio_engine.MAX_POSITION_PCT
    portfolio_engine.MAX_POSITION_PCT = initial_position_cap
    try:
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
        result = engine.run()
    finally:
        portfolio_engine.MAX_POSITION_PCT = original_cap

    if "error" in result:
        raise RuntimeError(result["error"])
    return {
        "metrics": _metrics(result),
        "trades": result.get("trades", []),
        "entry_reason_counts": (
            result.get("entry_execution_attribution", {}).get("reason_counts", {})
        ),
        "addon_events": (result.get("addon_attribution") or {}).get("events", []),
    }


def run_experiment() -> dict:
    universe = get_universe()
    rows = []
    for label, cfg in WINDOWS.items():
        for variant, cap in VARIANTS.items():
            result = _run_window(universe, cfg, cap)
            rows.append({
                "window": label,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "state_note": cfg["state_note"],
                "variant": variant,
                "initial_position_cap_pct": cap,
                **result,
            })
            m = result["metrics"]
            print(
                f"[{label} {variant}] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                f"DD={m['max_drawdown_pct']} trades={m['trade_count']} "
                f"addons={m['addon_executed']}"
            )

    summary = OrderedDict()
    for variant in list(VARIANTS.keys())[1:]:
        by_window = OrderedDict()
        for label in WINDOWS:
            baseline = next(
                r for r in rows
                if r["window"] == label and r["variant"] == "baseline_initial_cap_25pct"
            )
            candidate = next(r for r in rows if r["window"] == label and r["variant"] == variant)
            by_window[label] = {
                "before": baseline["metrics"],
                "after": candidate["metrics"],
                "delta": _delta(candidate["metrics"], baseline["metrics"]),
                "entry_reason_counts": candidate["entry_reason_counts"],
            }
        baseline_total_pnl = round(sum(v["before"]["total_pnl"] for v in by_window.values()), 2)
        total_pnl_delta = round(sum(v["delta"]["total_pnl"] for v in by_window.values()), 2)
        summary[variant] = {
            "by_window": by_window,
            "aggregate": {
                "expected_value_score_delta_sum": round(
                    sum(v["delta"]["expected_value_score"] for v in by_window.values()),
                    6,
                ),
                "total_pnl_delta_sum": total_pnl_delta,
                "baseline_total_pnl_sum": baseline_total_pnl,
                "total_pnl_delta_pct": (
                    round(total_pnl_delta / baseline_total_pnl, 6)
                    if baseline_total_pnl else None
                ),
                "windows_improved": sum(
                    1 for v in by_window.values()
                    if v["delta"]["expected_value_score"] > 0
                ),
                "windows_regressed": sum(
                    1 for v in by_window.values()
                    if v["delta"]["expected_value_score"] < 0
                ),
                "max_drawdown_delta_max": max(
                    v["delta"]["max_drawdown_pct"] for v in by_window.values()
                ),
                "trade_count_delta_sum": sum(v["delta"]["trade_count"] for v in by_window.values()),
                "addon_executed_delta_sum": sum(
                    v["delta"]["addon_executed"] for v in by_window.values()
                ),
            },
        }

    best_variant, best = max(
        summary.items(),
        key=lambda item: item[1]["aggregate"]["expected_value_score_delta_sum"],
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "lane": "alpha_search",
        "change_type": "capital_allocation_initial_position_cap",
        "single_causal_variable": "initial position max position cap",
        "hypothesis": (
            "The accepted 50% day-2 add-on may make the old 25% initial cap too "
            "front-loaded. Lowering only the initial fill cap could reserve "
            "capacity for confirmed follow-through winners; raising it tests "
            "whether the stack is under-allocated at entry."
        ),
        "history_guardrails": {
            "not_llm_soft_ranking": True,
            "not_gap_threshold_sweep": True,
            "not_gap_context_exception": True,
            "not_addon_trigger_tuning": True,
            "production_strategy_changed": False,
        },
        "parameters": {
            "baseline_initial_position_cap_pct": MAX_POSITION_PCT,
            "tested_initial_position_cap_pct": [0.15, 0.20, 0.30, 0.35, 0.40],
            "addon_max_position_pct_locked": ADDON_MAX_POSITION_PCT,
            "locked_variables": [
                "signal generation",
                "risk multipliers",
                "all exits",
                "upside/adverse gap cancels",
                "day-2 add-on trigger and fraction",
                "add-on max position cap",
                "scarce-slot breakout routing",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "windows": WINDOWS,
        "rows": rows,
        "summary": summary,
        "best_variant": best_variant,
        "best_variant_summary": best,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    result = run_experiment()
    OUT_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "artifact": str(OUT_JSON),
        "best_variant": result["best_variant"],
        "best_aggregate": result["best_variant_summary"]["aggregate"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
