"""exp-20260425-027 Technology trend target-width screen.

Hypothesis:
    The mid_weak gap versus QQQ may come from cutting Technology trend winners
    too early, not from insufficient idle beta. Widen only trend_long Technology
    targets and leave entries, sizing, ranking, and all non-Tech exits unchanged.

This runner is experiment-only. It monkeypatches risk enrichment at runtime and
does not change production strategy code.
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
from constants import ATR_STOP_MULT  # noqa: E402
from data_layer import get_universe  # noqa: E402
import risk_engine as re_module  # noqa: E402


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
    ("baseline", {"target_mult": None}),
    ("tech_trend_target_4_5", {"target_mult": 4.5}),
    ("tech_trend_target_5_0", {"target_mult": 5.0}),
    ("tech_trend_target_6_0", {"target_mult": 6.0}),
    ("tech_trend_target_7_0", {"target_mult": 7.0}),
    ("tech_trend_target_8_0", {"target_mult": 8.0}),
])

OUT_JSON = os.path.join(REPO_ROOT, "data", "exp_20260425_027_results.json")

_state = {
    "target_mult": None,
    "eligible": 0,
    "adjusted": 0,
}


def _eligible(sig: dict) -> bool:
    return sig.get("strategy") == "trend_long" and sig.get("sector") == "Technology"


def _patched_enrich_signals(signals, features_dict, atr_target_mult=None):
    enriched = _original_enrich_signals(
        signals,
        features_dict,
        atr_target_mult=atr_target_mult,
    )
    target_mult = _state["target_mult"]
    if target_mult is None:
        return enriched

    out = []
    for sig in enriched:
        if not _eligible(sig):
            out.append(sig)
            continue
        _state["eligible"] += 1
        entry = sig.get("entry_price")
        stop = sig.get("stop_price")
        if entry is None or stop is None or entry <= stop:
            out.append(sig)
            continue
        atr = (entry - stop) / ATR_STOP_MULT
        target = round(entry + target_mult * atr, 2)
        sig = {
            **sig,
            "target_price": target,
            "target_mult_used": target_mult,
            "tech_trend_target_width_applied": target_mult,
        }
        _state["adjusted"] += 1
        out.append(sig)
    return out


def _install_patches():
    global _original_enrich_signals
    _original_enrich_signals = re_module.enrich_signals
    re_module.enrich_signals = _patched_enrich_signals


def _remove_patches():
    re_module.enrich_signals = _original_enrich_signals


def _run_window(universe: list[str], label: str, cfg: dict,
                variant_name: str, variant_cfg: dict) -> dict:
    _state["target_mult"] = variant_cfg["target_mult"]
    _state["eligible"] = 0
    _state["adjusted"] = 0
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
    result = engine.run()
    by_strategy = result.get("by_strategy") or {}
    tech_trades = [
        t for t in result.get("trades", [])
        if t.get("strategy") == "trend_long" and t.get("sector") == "Technology"
    ]
    return {
        "window": label,
        "start": cfg["start"],
        "end": cfg["end"],
        "snapshot": cfg["snapshot"],
        "variant": variant_name,
        "target_mult": variant_cfg["target_mult"],
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "total_return_pct": (result.get("benchmarks") or {}).get("strategy_total_return_pct"),
        "strategy_vs_spy_pct": (result.get("benchmarks") or {}).get("strategy_vs_spy_pct"),
        "strategy_vs_qqq_pct": (result.get("benchmarks") or {}).get("strategy_vs_qqq_pct"),
        "trade_count": result.get("total_trades"),
        "win_rate": result.get("win_rate"),
        "eligible_signals": _state["eligible"],
        "adjusted_signals": _state["adjusted"],
        "trend_long_pnl": (by_strategy.get("trend_long") or {}).get("total_pnl_usd"),
        "tech_trend_trade_count": len(tech_trades),
        "tech_trend_pnl": round(sum(t.get("pnl") or 0.0 for t in tech_trades), 2),
    }


def main() -> int:
    universe = get_universe()
    _install_patches()
    try:
        results = []
        for label, cfg in WINDOWS.items():
            for variant_name, variant_cfg in VARIANTS.items():
                row = _run_window(universe, label, cfg, variant_name, variant_cfg)
                print(
                    f"[{label} {variant_name}] "
                    f"EV={row['expected_value_score']} "
                    f"ret={row['total_return_pct']} "
                    f"vs_spy={row['strategy_vs_spy_pct']} "
                    f"vs_qqq={row['strategy_vs_qqq_pct']} "
                    f"sharpe_d={row['sharpe_daily']} "
                    f"dd={row['max_drawdown_pct']} "
                    f"trades={row['trade_count']} "
                    f"tech_pnl={row['tech_trend_pnl']} "
                    f"eligible={row['eligible_signals']}"
                )
                results.append(row)
    finally:
        _remove_patches()

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {
                "rule": {
                    "name": "technology_trend_target_width",
                    "definition": (
                        "After normal risk enrichment, widen target_price only "
                        "for strategy == trend_long and sector == Technology."
                    ),
                    "goal": (
                        "test whether secondary-window QQQ underperformance is "
                        "caused by cutting Technology trend winners too early"
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
