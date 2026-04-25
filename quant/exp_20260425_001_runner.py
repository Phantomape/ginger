"""exp-20260425-001 residual trend pocket: Technology with a 2%-3% stop gap.

Hypothesis:
    After the accepted A+B stack plus the prior Technology residual rules, the
    remaining trend-Tech drag sits in a tighter stop-gap pocket:

        strategy == trend_long
        sector == Technology
        0.02 <= gap_vulnerability_pct < 0.03

    Zeroing only that cohort should stay a strict null in the dominant
    late-strong tape, while improving the weaker mid/old windows where the
    pocket repeatedly lost money.
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
])

VARIANTS = OrderedDict([
    ("baseline", {"multiplier": 1.0}),
    ("trend_tech_gap23_025", {"multiplier": 0.25}),
    ("trend_tech_gap23_000", {"multiplier": 0.0}),
])

OUT_JSON = os.path.join(REPO_ROOT, "data", "exp_20260425_001_results.json")

def _run_window(universe: list[str], label: str, cfg: dict, variant_name: str, variant_cfg: dict) -> dict:
    original_multiplier = pe_module.TREND_TECH_TIGHT_GAP_RISK_MULTIPLIER
    pe_module.TREND_TECH_TIGHT_GAP_RISK_MULTIPLIER = variant_cfg["multiplier"]

    try:
        engine = BacktestEngine(
            universe,
            start=cfg["start"],
            end=cfg["end"],
            config={"REGIME_AWARE_EXIT": True},
            replay_llm=False,
            replay_news=False,
            data_dir=os.path.join(REPO_ROOT, "data"),
            ohlcv_snapshot_path=os.path.join(REPO_ROOT, cfg["snapshot"]),
        )
        result = engine.run()
        eligible_trades = [
            t for t in result.get("trades", [])
            if t.get("strategy") == "trend_long"
            and t.get("sector") == "Technology"
            and t.get("entry_price")
            and t.get("stop_price")
            and 0.02 <= (t["entry_price"] - t["stop_price"]) / t["entry_price"] < 0.03
        ]
        adjusted_trades = len(eligible_trades) if variant_cfg["multiplier"] < 1.0 else 0
        return {
            "window": label,
            "start": cfg["start"],
            "end": cfg["end"],
            "snapshot": cfg["snapshot"],
            "variant": variant_name,
            "trend_tech_gap23_multiplier": variant_cfg["multiplier"],
            "eligible_trend_tech_gap23_signals": len(eligible_trades),
            "adjusted_trend_tech_gap23_signals": adjusted_trades,
            "expected_value_score": result.get("expected_value_score"),
            "sharpe_daily": result.get("sharpe_daily"),
            "max_drawdown_pct": result.get("max_drawdown_pct"),
            "total_return_pct": (result.get("benchmarks") or {}).get("strategy_total_return_pct"),
            "trade_count": result.get("total_trades"),
            "win_rate": result.get("win_rate"),
        }
    finally:
        pe_module.TREND_TECH_TIGHT_GAP_RISK_MULTIPLIER = original_multiplier


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
                f"eligible={summary['eligible_trend_tech_gap23_signals']} "
                f"adjusted={summary['adjusted_trend_tech_gap23_signals']}"
            )
            results.append(summary)

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {
                "rule": {
                    "name": "trend_tech_gap23_de_risk",
                    "definition": (
                        "apply a sleeve-specific risk multiplier only when "
                        "strategy == trend_long, sector == Technology, "
                        "and 0.02 <= gap_vulnerability_pct < 0.03"
                    ),
                    "goal": (
                        "test whether the remaining trend-Tech drag now lives "
                        "in the tighter 2%-3% stop-gap pocket"
                    ),
                },
                "variants": VARIANTS,
                "results": results,
            },
            f,
            indent=2,
        )
    print(f"\\nWrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
