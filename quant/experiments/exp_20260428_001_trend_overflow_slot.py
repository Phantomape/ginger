"""exp-20260428-001: trend-only overflow slot replay.

Hypothesis:
    The rejected global MAX_POSITIONS=6 result may have failed because it gave
    the extra slot to all sleeves. A narrower capital-allocation policy can add
    one overflow slot while preserving breakout capacity discipline: keep
    breakouts out of the final two slots, so the 6th slot is effectively reserved
    for trend continuation candidates.

This runner is experiment-only. It changes no production defaults.
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

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260428-001"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260428_001_trend_overflow_slot.json"

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

BASELINE_CONFIG = {
    "REGIME_AWARE_EXIT": True,
}

TREND_OVERFLOW_CONFIG = {
    "REGIME_AWARE_EXIT": True,
    "MAX_POSITIONS": 6,
    "DEFER_BREAKOUT_WHEN_SLOTS_LTE": 2,
}


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    scarce = result.get("scarce_slot_attribution") or {}
    execution = result.get("entry_execution_attribution") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "breakout_deferred": scarce.get("breakout_deferred", 0),
        "entry_reason_counts": execution.get("reason_counts"),
    }


def _run_window(universe: list[str], cfg: dict, config: dict) -> dict:
    engine = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config=config,
        replay_llm=False,
        replay_news=False,
        data_dir=str(REPO_ROOT / "data"),
        ohlcv_snapshot_path=str(REPO_ROOT / cfg["snapshot"]),
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


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
        baseline_result = _run_window(universe, cfg, BASELINE_CONFIG)
        candidate_result = _run_window(universe, cfg, TREND_OVERFLOW_CONFIG)
        before = _metrics(baseline_result)
        after = _metrics(candidate_result)
        delta = _delta(after, before)
        rows.append({
            "window": label,
            "start": cfg["start"],
            "end": cfg["end"],
            "snapshot": cfg["snapshot"],
            "state_note": cfg["state_note"],
            "before_metrics": before,
            "after_metrics": after,
            "delta_metrics": delta,
            "candidate_trades": candidate_result.get("trades", []),
        })
        print(
            f"[{label}] EV {before['expected_value_score']} -> "
            f"{after['expected_value_score']} | PnL {before['total_pnl']} -> "
            f"{after['total_pnl']} | trades {before['trade_count']} -> "
            f"{after['trade_count']}"
        )

    ev_delta_sum = round(sum(row["delta_metrics"]["expected_value_score"] for row in rows), 6)
    pnl_delta_sum = round(sum(row["delta_metrics"]["total_pnl"] for row in rows), 2)
    summary = {
        "expected_value_score_delta_sum": ev_delta_sum,
        "total_pnl_delta_sum": pnl_delta_sum,
        "windows_improved": sum(
            1 for row in rows if row["delta_metrics"]["expected_value_score"] > 0
        ),
        "windows_regressed": sum(
            1 for row in rows if row["delta_metrics"]["expected_value_score"] < 0
        ),
        "max_drawdown_delta_max": max(
            row["delta_metrics"]["max_drawdown_pct"] for row in rows
        ),
        "trade_count_delta_sum": sum(row["delta_metrics"]["trade_count"] for row in rows),
        "breakout_deferred_delta_sum": sum(
            row["delta_metrics"]["breakout_deferred"] for row in rows
        ),
    }
    accepted = (
        summary["windows_improved"] >= 2
        and summary["windows_regressed"] == 0
        and (
            ev_delta_sum > 0.10
            or pnl_delta_sum > 0.05 * sum(row["before_metrics"]["total_pnl"] for row in rows)
            or any(row["delta_metrics"]["sharpe_daily"] > 0.1 for row in rows)
            or summary["trade_count_delta_sum"] > 0
        )
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "accepted_default_off_research_harness" if accepted else "rejected",
        "decision": "accepted_default_off_research_harness" if accepted else "rejected",
        "hypothesis": (
            "A trend-only overflow slot can recover the useful part of wider "
            "capacity without repeating global MAX_POSITIONS expansion: use "
            "MAX_POSITIONS=6 while deferring breakout_long whenever slots <= 2."
        ),
        "change_type": "capital_allocation_shadow",
        "parameters": {
            "single_causal_variable": "trend-only overflow slot policy",
            "baseline_config": BASELINE_CONFIG,
            "candidate_config": TREND_OVERFLOW_CONFIG,
            "locked_variables": [
                "entries",
                "exits",
                "position sizing",
                "day-2 follow-through add-on trigger",
                "LLM/news replay",
                "earnings strategy",
                "initial single-position cap",
            ],
        },
        "prior_related_results": [
            {
                "experiment_id": "exp-20260427-014",
                "decision": "rejected",
                "reason": "Global MAX_POSITIONS changes were unstable.",
            },
            {
                "experiment_id": "exp-20260427-036",
                "decision": "rejected",
                "reason": "Same-day trend-first ordering broadly damaged breakout allocation.",
            },
        ],
        "windows": WINDOWS,
        "results": rows,
        "summary": summary,
        "rejection_reason": (
            None if accepted else
            "No Gate 4 condition passed across the fixed three-window comparison."
        ),
        "llm_metrics": {
            "used_llm": False,
            "blocker_relation": (
                "LLM soft ranking remains sample-limited, so this deterministic "
                "capital-allocation alpha was tested instead."
            ),
        },
        "strategy_behavior_changed": False,
    }


def main() -> int:
    payload = run_experiment()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
