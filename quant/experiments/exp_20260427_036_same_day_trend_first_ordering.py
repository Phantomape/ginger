"""exp-20260427-036: same-day trend-first sleeve ordering replay.

This tests a capital-allocation alpha: when same-day candidates compete for
entry slots, give `trend_long` candidates priority over `breakout_long`
candidates. It is experiment-only and does not change production defaults.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
import signal_engine  # noqa: E402


EXPERIMENT_ID = "exp-20260427-036"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260427_036_same_day_trend_first_ordering.json"

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


@contextmanager
def _trend_first_patch(enabled: bool):
    original_generate = signal_engine.generate_signals

    def generate_trend_first(*args, **kwargs):
        signals = original_generate(*args, **kwargs)
        if not enabled:
            return signals
        return sorted(
            signals,
            key=lambda sig: 0 if sig.get("strategy") == "trend_long" else 1,
        )

    signal_engine.generate_signals = generate_trend_first
    try:
        yield
    finally:
        signal_engine.generate_signals = original_generate


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    attribution = result.get("entry_execution_attribution") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "total_pnl": result.get("total_pnl"),
        "total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "win_rate": result.get("win_rate"),
        "trade_count": result.get("total_trades"),
        "survival_rate": result.get("survival_rate"),
        "entry_reason_counts": attribution.get("reason_counts"),
    }


def _run_window(universe: list[str], cfg: dict, enabled: bool) -> dict:
    with _trend_first_patch(enabled):
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
        baseline = _run_window(universe, cfg, enabled=False)
        candidate = _run_window(universe, cfg, enabled=True)
        before = _metrics(baseline)
        after = _metrics(candidate)
        row = {
            "window": label,
            "start": cfg["start"],
            "end": cfg["end"],
            "snapshot": cfg["snapshot"],
            "state_note": cfg["state_note"],
            "before_metrics": before,
            "after_metrics": after,
            "delta_metrics": _delta(after, before),
        }
        print(
            f"[{label}] EV {before['expected_value_score']} -> "
            f"{after['expected_value_score']} | PnL {before['total_pnl']} -> "
            f"{after['total_pnl']}"
        )
        rows.append(row)

    ev_delta_sum = round(
        sum(row["delta_metrics"]["expected_value_score"] for row in rows),
        6,
    )
    pnl_delta_sum = round(sum(row["delta_metrics"]["total_pnl"] for row in rows), 2)
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hypothesis": (
            "Same-day sleeve ordering may be a cleaner allocation lever than "
            "wider scarce-slot deferral: when candidates compete for entry "
            "slots, rank trend_long ahead of breakout_long without changing "
            "signal generation, exits, sizing, LLM/news replay, or earnings."
        ),
        "change_type": "capital_allocation_shadow",
        "parameters": {
            "single_causal_variable": "same-day candidate ordering by sleeve",
            "baseline_order": "native signal_engine order",
            "candidate_order": "stable sort trend_long before non-trend candidates",
            "unchanged": [
                "entries",
                "exits",
                "position sizing",
                "MAX_POSITIONS",
                "follow-through add-ons",
                "scarce-slot breakout defer default",
                "LLM/news replay",
                "earnings strategy",
            ],
        },
        "windows": WINDOWS,
        "results": rows,
        "summary": {
            "expected_value_score_delta_sum": ev_delta_sum,
            "total_pnl_delta_sum": pnl_delta_sum,
            "windows_improved": sum(
                1 for row in rows
                if row["delta_metrics"]["expected_value_score"] > 0
            ),
            "windows_regressed": sum(
                1 for row in rows
                if row["delta_metrics"]["expected_value_score"] < 0
            ),
            "max_drawdown_delta_max": max(
                row["delta_metrics"]["max_drawdown_pct"] for row in rows
            ),
        },
        "decision": "rejected",
        "rejection_reason": (
            "Trend-first same-day ordering regressed EV in late_strong and "
            "mid_weak and was inert in old_thin, so it behaves like broad "
            "breakout de-prioritization rather than useful sleeve routing."
        ),
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
