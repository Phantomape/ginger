"""exp-20260428-021 upside gap entry-cancel sweep.

Hypothesis:
    The current next-open upside gap cancel may be mis-sized. A tighter cancel
    may avoid overextended fills, while a looser cancel may preserve momentum
    confirmation. Sweep only CANCEL_GAP_PCT on the fixed snapshots and leave
    signal generation, exits, sizing, add-ons, scarce-slot routing, LLM/news
    replay, and earnings unchanged.

This runner is experiment-only. Production defaults should change separately
only if a variant passes the fixed-window Gate 4 check.
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

import backtester  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260428-021"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260428_021_upside_gap_cancel_sweep.json"

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
    ("upside_gap_cancel_1pct", 0.01),
    ("baseline_upside_gap_cancel_1_5pct", 0.015),
    ("upside_gap_cancel_2pct", 0.02),
    ("upside_gap_cancel_3pct", 0.03),
    ("upside_gap_cancel_5pct", 0.05),
    ("upside_gap_cancel_disabled", None),
])


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
    }


def _run_window(universe: list[str], cfg: dict, upside_gap_pct: float | None) -> dict:
    original_cancel_gap_pct = backtester.CANCEL_GAP_PCT
    backtester.CANCEL_GAP_PCT = upside_gap_pct
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
        backtester.CANCEL_GAP_PCT = original_cancel_gap_pct

    if "error" in result:
        raise RuntimeError(result["error"])
    decision_counts = result.get("entry_execution_attribution", {}).get("reason_counts", {})
    return {
        "metrics": _metrics(result),
        "gap_cancel_count": int(decision_counts.get("gap_cancel", 0) or 0),
        "adverse_gap_down_cancel_count": int(
            decision_counts.get("adverse_gap_down_cancel", 0) or 0
        ),
        "entry_reason_counts": decision_counts,
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


def run_experiment() -> dict:
    universe = get_universe()
    rows = []
    for label, cfg in WINDOWS.items():
        for variant, upside_gap_pct in VARIANTS.items():
            result = _run_window(universe, cfg, upside_gap_pct)
            rows.append({
                "window": label,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "state_note": cfg["state_note"],
                "variant": variant,
                "cancel_gap_pct": upside_gap_pct,
                **result,
            })
            m = result["metrics"]
            print(
                f"[{label} {variant}] EV={m['expected_value_score']} "
                f"PnL={m['total_pnl']} SharpeD={m['sharpe_daily']} "
                f"DD={m['max_drawdown_pct']} trades={m['trade_count']} "
                f"gap_cancels={result['gap_cancel_count']}"
            )

    baseline_name = "baseline_upside_gap_cancel_1_5pct"
    summary = OrderedDict()
    for variant in VARIANTS:
        if variant == baseline_name:
            continue
        by_window = OrderedDict()
        for label in WINDOWS:
            baseline = next(
                r for r in rows
                if r["window"] == label and r["variant"] == baseline_name
            )
            candidate = next(
                r for r in rows
                if r["window"] == label and r["variant"] == variant
            )
            by_window[label] = {
                "before": baseline["metrics"],
                "after": candidate["metrics"],
                "delta": _delta(candidate["metrics"], baseline["metrics"]),
                "gap_cancel_count": candidate["gap_cancel_count"],
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
                "gap_cancel_count": sum(v["gap_cancel_count"] for v in by_window.values()),
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
        "change_type": "entry_execution_cancel_sweep",
        "single_causal_variable": "upside next-open gap cancel threshold",
        "hypothesis": (
            "The 1.5% upside next-open cancel may be mis-sized; tuning only this "
            "execution threshold may improve expected value without touching the "
            "signal, exit, add-on, scarce-slot, LLM/news, or earnings layers."
        ),
        "history_guardrails": {
            "does_not_repeat_adverse_gap_down_thresholds": True,
            "does_not_repeat_addon_threshold_tuning": True,
            "does_not_use_llm_soft_ranking_sample": True,
            "does_not_promote_price_only_weak_hold_exit": True,
            "production_strategy_changed": False,
        },
        "parameters": {
            "baseline_cancel_gap_pct": 0.015,
            "tested_cancel_gap_pct": list(VARIANTS.values()),
            "locked_variables": [
                "signal generation",
                "risk sizing",
                "exits",
                "day-2 follow-through add-on settings",
                "adverse gap-down cancel threshold",
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
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
