"""exp-20260425-002 residual breakout pocket: Communication Services near-high.

Hypothesis:
    After the accepted A+B stack plus the recent residual trend-Tech rules, the
    remaining breakout drag sits in near-high Communication Services entries:

        strategy == breakout_long
        sector == Communication Services
        pct_from_52w_high >= -0.03

    De-risking only that cohort to 25% should leave the dominant late-strong
    tape unchanged while improving the weaker mid/old windows.
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
        "end":   "2026-04-21",
        "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
    }),
    ("mid_weak", {
        "start": "2025-04-23",
        "end":   "2025-10-22",
        "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
    }),
    ("old_thin", {
        "start": "2024-10-02",
        "end":   "2025-04-22",
        "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
    }),
    ("live_primary", {
        "start": "2025-10-27",
        "end":   "2026-04-24",
        "snapshot": None,
    }),
    ("live_secondary", {
        "start": "2025-04-26",
        "end":   "2025-10-25",
        "snapshot": None,
    }),
])

VARIANTS = OrderedDict([
    ("baseline", {"multiplier": 1.0}),
    ("breakout_comms_nearhigh_025", {"multiplier": 0.25}),
    ("breakout_comms_nearhigh_000", {"multiplier": 0.0}),
])

OUT_JSON = os.path.join(REPO_ROOT, "data", "exp_20260425_002_results.json")


def _run_window(
    universe: list[str], label: str, cfg: dict, variant_name: str, variant_cfg: dict
) -> dict:
    original_multiplier = pe_module.BREAKOUT_COMMS_NEAR_HIGH_RISK_MULTIPLIER
    pe_module.BREAKOUT_COMMS_NEAR_HIGH_RISK_MULTIPLIER = variant_cfg["multiplier"]

    try:
        engine_kwargs = {
            "universe": universe,
            "start": cfg["start"],
            "end": cfg["end"],
            "config": {"REGIME_AWARE_EXIT": True},
            "replay_llm": False,
            "replay_news": False,
            "data_dir": os.path.join(REPO_ROOT, "data"),
        }
        if cfg["snapshot"]:
            engine_kwargs["ohlcv_snapshot_path"] = os.path.join(REPO_ROOT, cfg["snapshot"])
        engine = BacktestEngine(**engine_kwargs)
        result = engine.run()
        eligible_trades = [
            t for t in result.get("trades", [])
            if t.get("strategy") == "breakout_long"
            and t.get("sector") == "Communication Services"
        ]
        adjusted_trades = len(eligible_trades) if variant_cfg["multiplier"] < 1.0 else 0
        return {
            "window": label,
            "start": cfg["start"],
            "end": cfg["end"],
            "snapshot": cfg["snapshot"],
            "variant": variant_name,
            "breakout_comms_near_high_multiplier": variant_cfg["multiplier"],
            "eligible_breakout_comms_near_high_signals": len(eligible_trades),
            "adjusted_breakout_comms_near_high_signals": adjusted_trades,
            "expected_value_score": result.get("expected_value_score"),
            "sharpe_daily": result.get("sharpe_daily"),
            "max_drawdown_pct": result.get("max_drawdown_pct"),
            "total_return_pct": (result.get("benchmarks") or {}).get("strategy_total_return_pct"),
            "trade_count": result.get("total_trades"),
            "win_rate": result.get("win_rate"),
            "cohort_pnl_usd": round(sum(t["pnl"] for t in eligible_trades), 2),
        }
    finally:
        pe_module.BREAKOUT_COMMS_NEAR_HIGH_RISK_MULTIPLIER = original_multiplier


def main() -> int:
    universe = get_universe()
    results = []
    for label, cfg in WINDOWS.items():
        for variant_name, variant_cfg in VARIANTS.items():
            summary = _run_window(universe, label, cfg, variant_name, variant_cfg)
            print(
                f"[{label} {variant_name}] "
                f"EV={summary['expected_value_score']} "
                f"ret={summary['total_return_pct']} "
                f"sharpe_d={summary['sharpe_daily']} "
                f"dd={summary['max_drawdown_pct']} "
                f"trades={summary['trade_count']} "
                f"eligible={summary['eligible_breakout_comms_near_high_signals']} "
                f"adjusted={summary['adjusted_breakout_comms_near_high_signals']}"
            )
            results.append(summary)

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {
                "rule": {
                    "name": "breakout_comms_near_high_de_risk",
                    "definition": (
                        "apply a sleeve-specific risk multiplier only when "
                        "strategy == breakout_long, sector == Communication Services, "
                        "and pct_from_52w_high >= -0.03"
                    ),
                    "goal": (
                        "test whether the remaining breakout drag now lives "
                        "in near-high Communication Services entries"
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
