"""exp-20260425-033 single-position cap sweep.

Hypothesis:
    The accepted A+B stack may now be under-allocating to tight-stop winners
    because the 20% single-position cap binds before the risk budget is fully
    deployed. Sweep only MAX_POSITION_PCT on fixed OHLCV snapshots.

This runner is experiment-only. It monkeypatches portfolio_engine.MAX_POSITION_PCT
at runtime and does not change production strategy code.
"""

from __future__ import annotations

import json
import os
import sys
from collections import OrderedDict


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
import portfolio_engine as pe_module  # noqa: E402


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

VARIANTS = OrderedDict([
    ("cap_15", 0.15),
    ("baseline_cap_20", 0.20),
    ("cap_25", 0.25),
    ("cap_30", 0.30),
    ("cap_35", 0.35),
])

OUT_JSON = os.path.join(REPO_ROOT, "data", "exp_20260425_033_results.json")


def _summarize_result(label: str, cfg: dict, variant: str, cap: float,
                      result: dict) -> dict:
    by_strategy = result.get("by_strategy") or {}
    cap_eff = result.get("capital_efficiency") or {}
    return {
        "window": label,
        "start": cfg["start"],
        "end": cfg["end"],
        "snapshot": cfg["snapshot"],
        "variant": variant,
        "max_position_pct": cap,
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "total_return_pct": (result.get("benchmarks") or {}).get(
            "strategy_total_return_pct"
        ),
        "strategy_vs_spy_pct": (result.get("benchmarks") or {}).get(
            "strategy_vs_spy_pct"
        ),
        "strategy_vs_qqq_pct": (result.get("benchmarks") or {}).get(
            "strategy_vs_qqq_pct"
        ),
        "trade_count": result.get("total_trades"),
        "win_rate": result.get("win_rate"),
        "gross_slot_day_fraction": cap_eff.get("gross_slot_day_fraction"),
        "trend_long_pnl": (by_strategy.get("trend_long") or {}).get(
            "total_pnl_usd"
        ),
        "breakout_long_pnl": (by_strategy.get("breakout_long") or {}).get(
            "total_pnl_usd"
        ),
    }


def _run_window(universe: list[str], label: str, cfg: dict, variant: str,
                cap: float) -> dict:
    pe_module.MAX_POSITION_PCT = cap
    engine = BacktestEngine(
        universe=universe,
        start=cfg["start"],
        end=cfg["end"],
        config={"REGIME_AWARE_EXIT": True},
        replay_llm=False,
        replay_news=False,
        data_dir=os.path.join(REPO_ROOT, "data"),
        ohlcv_snapshot_path=os.path.join(REPO_ROOT, cfg["snapshot"]),
    )
    return _summarize_result(label, cfg, variant, cap, engine.run())


def main() -> int:
    universe = get_universe()
    original_cap = pe_module.MAX_POSITION_PCT
    results = []
    try:
        for label, cfg in WINDOWS.items():
            for variant, cap in VARIANTS.items():
                row = _run_window(universe, label, cfg, variant, cap)
                print(
                    f"[{label} {variant}] "
                    f"EV={row['expected_value_score']} "
                    f"ret={row['total_return_pct']} "
                    f"sharpe_d={row['sharpe_daily']} "
                    f"dd={row['max_drawdown_pct']} "
                    f"trades={row['trade_count']} "
                    f"win={row['win_rate']} "
                    f"slot={row['gross_slot_day_fraction']}"
                )
                results.append(row)
    finally:
        pe_module.MAX_POSITION_PCT = original_cap

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {
                "rule": {
                    "name": "single_position_cap_sweep",
                    "definition": (
                        "Sweep only portfolio_engine.MAX_POSITION_PCT while "
                        "keeping entries, exits, ranking, LLM, C strategy, "
                        "and existing sizing multipliers unchanged."
                    ),
                    "hypothesis": (
                        "The accepted A+B stack may under-allocate to tight-stop "
                        "winners when the 20% single-position cap binds before "
                        "the target risk budget is deployed."
                    ),
                },
                "variants": VARIANTS,
                "results": results,
            },
            f,
            indent=2,
        )
    print(f"\nWrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
