"""exp-20260425-035 breakout target-width screen.

Hypothesis:
    exp-20260425-034 found that target exits in breakout Energy and breakout
    Commodities often continued higher after the target was hit. The next
    clean test is not a new entry rule; it is whether these breakout sleeves
    need wider targets, analogous to the accepted Technology/Commodity trend
    winner-truncation repairs.

This runner is experiment-only. It monkeypatches risk_engine.enrich_signals at
runtime and does not change production strategy code.
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
import risk_engine  # noqa: E402


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
    ("baseline", None),
    ("breakout_energy_5", {"sector": "Energy", "target_mult": 5.0}),
    ("breakout_energy_6", {"sector": "Energy", "target_mult": 6.0}),
    ("breakout_energy_7", {"sector": "Energy", "target_mult": 7.0}),
    ("breakout_commodities_5", {"sector": "Commodities", "target_mult": 5.0}),
    ("breakout_commodities_6", {"sector": "Commodities", "target_mult": 6.0}),
    ("breakout_commodities_7", {"sector": "Commodities", "target_mult": 7.0}),
    ("breakout_energy_commodities_6", {
        "sector": {"Energy", "Commodities"},
        "target_mult": 6.0,
    }),
])

OUT_JSON = os.path.join(REPO_ROOT, "data", "exp_20260425_035_results.json")


def _summarize(label: str, cfg: dict, variant: str, rule: dict | None,
               result: dict) -> dict:
    by_strategy = result.get("by_strategy") or {}
    trades = result.get("trades") or []
    touched = [
        t for t in trades
        if t.get("strategy") == "breakout_long"
        and (
            rule is not None
            and (
                t.get("sector") == rule.get("sector")
                or (
                    isinstance(rule.get("sector"), set)
                    and t.get("sector") in rule.get("sector")
                )
            )
        )
    ]
    return {
        "window": label,
        "start": cfg["start"],
        "end": cfg["end"],
        "snapshot": cfg["snapshot"],
        "variant": variant,
        "rule": {
            "strategy": "breakout_long",
            "sector": sorted(rule["sector"]) if isinstance(rule, dict) and isinstance(rule.get("sector"), set)
            else (rule or {}).get("sector"),
            "target_mult": (rule or {}).get("target_mult"),
        } if rule else None,
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "total_return_pct": (result.get("benchmarks") or {}).get(
            "strategy_total_return_pct"
        ),
        "trade_count": result.get("total_trades"),
        "win_rate": result.get("win_rate"),
        "breakout_long_pnl": (by_strategy.get("breakout_long") or {}).get(
            "total_pnl_usd"
        ),
        "touched_trade_count": len(touched),
        "touched_pnl_usd": round(sum(t.get("pnl") or 0.0 for t in touched), 2),
        "touched_exit_reasons": {
            reason: sum(1 for t in touched if t.get("exit_reason") == reason)
            for reason in sorted({t.get("exit_reason") for t in touched})
        },
    }


def _patched_enricher(original, rule):
    def wrapped(signals, features_dict, atr_target_mult=None):
        enriched = original(
            signals,
            features_dict,
            atr_target_mult=atr_target_mult,
        )
        if rule is None:
            return enriched
        sectors = rule["sector"]
        if not isinstance(sectors, set):
            sectors = {sectors}
        out = []
        for sig in enriched:
            if (
                sig.get("strategy") == "breakout_long"
                and sig.get("sector") in sectors
            ):
                ticker = sig.get("ticker")
                atr = (features_dict.get(ticker) or {}).get("atr")
                if atr:
                    sig = risk_engine._retarget_signal_with_atr_mult(
                        sig,
                        atr,
                        rule["target_mult"],
                    )
                    sig["breakout_target_width_applied"] = rule["target_mult"]
                    sig["breakout_target_width_sector"] = sig.get("sector")
            out.append(sig)
        return out
    return wrapped


def _run_window(universe: list[str], label: str, cfg: dict,
                variant: str, rule: dict | None) -> dict:
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
    return _summarize(label, cfg, variant, rule, result)


def main() -> int:
    universe = get_universe()
    original_enrich = risk_engine.enrich_signals
    rows = []
    try:
        for variant, rule in VARIANTS.items():
            risk_engine.enrich_signals = _patched_enricher(original_enrich, rule)
            for label, cfg in WINDOWS.items():
                row = _run_window(universe, label, cfg, variant, rule)
                print(
                    f"[{label} {variant}] "
                    f"EV={row['expected_value_score']} "
                    f"ret={row['total_return_pct']} "
                    f"sharpe_d={row['sharpe_daily']} "
                    f"dd={row['max_drawdown_pct']} "
                    f"trades={row['trade_count']} "
                    f"touched={row['touched_trade_count']} "
                    f"touched_pnl={row['touched_pnl_usd']}"
                )
                rows.append(row)
    finally:
        risk_engine.enrich_signals = original_enrich

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {
                "experiment_id": "exp-20260425-035",
                "hypothesis": (
                    "Post-target audit suggests breakout Energy/Commodities "
                    "winners may be target-clipped; screen wider target widths "
                    "for each sleeve without changing entries, sizing, ranking, "
                    "LLM, C strategy, or other exits."
                ),
                "variants": {
                    name: (
                        {
                            "sector": sorted(rule["sector"]) if isinstance(rule, dict) and isinstance(rule.get("sector"), set)
                            else rule.get("sector"),
                            "target_mult": rule.get("target_mult"),
                        }
                        if rule else None
                    )
                    for name, rule in VARIANTS.items()
                },
                "results": rows,
            },
            f,
            indent=2,
        )
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
