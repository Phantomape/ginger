"""exp-20260424-010 candidate-cohort gap-difference -> breakout de-risk.

Hypothesis:
    After the cheap market/day-state routers were exhausted, the next credible
    meta-allocation branch should key off actual same-day candidate composition.
    Test a replayable candidate-day discriminator:

        avg_gap_vulnerability(breakout candidates)
        - avg_gap_vulnerability(trend candidates)

    If breakout candidates look materially more gap-fragile than trend
    candidates on the same sizing day, de-risk only `breakout_long`.

Expected acceptance shape:
    - triggers should occur on real candidate days across the fixed late / mid /
      old snapshot trio
    - the weaker windows should improve without harming the dominant late-strong
      tape
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
    ("baseline", {"gap_diff_threshold": None, "breakout_multiplier": 1.0}),
    ("bk_gapdiff_001_025", {"gap_diff_threshold": 0.01, "breakout_multiplier": 0.25}),
    ("bk_gapdiff_001_000", {"gap_diff_threshold": 0.01, "breakout_multiplier": 0.0}),
    ("bk_gapdiff_002_025", {"gap_diff_threshold": 0.02, "breakout_multiplier": 0.25}),
    ("bk_gapdiff_002_000", {"gap_diff_threshold": 0.02, "breakout_multiplier": 0.0}),
])

OUT_JSON = os.path.join(REPO_ROOT, "data", "exp_20260424_010_results.json")

_state = {
    "gap_diff_threshold": None,
    "breakout_multiplier": 1.0,
    "trigger_days_hit": 0,
    "breakout_signals_adjusted": 0,
}


def _copy_sizing_metadata(old_sizing: dict, new_sizing: dict, base_risk_pct):
    new_sizing["base_risk_pct"] = old_sizing.get("base_risk_pct", base_risk_pct)
    for key in [
        "trade_quality_score",
        "low_tqs_haircut_exempt_sector",
        "tqs_risk_multiplier_applied",
        "trend_industrials_risk_multiplier_applied",
        "trend_tech_gap_risk_multiplier_applied",
        "trend_tech_near_high_risk_multiplier_applied",
        "breakout_industrials_gap_risk_multiplier_applied",
        "earnings_gap_risk_applied",
        "gap_risk_pct",
        "effective_stop_for_sizing",
    ]:
        if key in old_sizing:
            new_sizing[key] = old_sizing[key]


def _zero_risk_sizing(portfolio_value, entry_price, stop_price, base_risk_pct):
    return {
        "portfolio_value_usd": round(portfolio_value, 2),
        "risk_pct": 0.0,
        "risk_amount_usd": 0.0,
        "entry_price": round(entry_price, 2),
        "stop_price": round(stop_price, 2),
        "risk_per_share": round(entry_price - stop_price, 2),
        "net_risk_per_share": round(
            (entry_price - stop_price)
            + entry_price * pe_module.ROUND_TRIP_COST_PCT
            + entry_price * pe_module.EXEC_LAG_PCT,
            4,
        ),
        "shares_to_buy": 0,
        "position_value_usd": 0.0,
        "position_pct_of_portfolio": 0.0,
        "base_risk_pct": base_risk_pct,
    }


def _patched_size_signals(signals, portfolio_value, risk_pct=None):
    sized = _original_size_signals(signals, portfolio_value, risk_pct=risk_pct)

    threshold = _state["gap_diff_threshold"]
    if threshold is None:
        return sized

    breakout_gaps = [
        sig.get("gap_vulnerability_pct")
        for sig in sized
        if sig.get("strategy") == "breakout_long"
        and sig.get("gap_vulnerability_pct") is not None
        and sig.get("sizing")
    ]
    trend_gaps = [
        sig.get("gap_vulnerability_pct")
        for sig in sized
        if sig.get("strategy") == "trend_long"
        and sig.get("gap_vulnerability_pct") is not None
        and sig.get("sizing")
    ]
    if not breakout_gaps or not trend_gaps:
        return sized

    breakout_avg_gap = sum(breakout_gaps) / len(breakout_gaps)
    trend_avg_gap = sum(trend_gaps) / len(trend_gaps)
    if breakout_avg_gap - trend_avg_gap < threshold:
        return sized

    _state["trigger_days_hit"] += 1
    multiplier = _state["breakout_multiplier"]

    for sig in sized:
        if sig.get("strategy") != "breakout_long":
            continue
        sizing = sig.get("sizing")
        if not sizing:
            continue

        entry = sig.get("entry_price")
        stop = sig.get("stop_price")
        if entry is None or stop is None:
            continue

        if multiplier <= 0:
            new_sizing = _zero_risk_sizing(
                portfolio_value,
                entry,
                stop,
                sizing.get("base_risk_pct", sizing.get("risk_pct", 0.0)),
            )
        else:
            new_sizing = pe_module.compute_position_size(
                portfolio_value,
                entry,
                stop,
                risk_pct=sizing.get("risk_pct", 0.0) * multiplier,
            )
            if not new_sizing:
                continue

        _copy_sizing_metadata(sizing, new_sizing, risk_pct)
        new_sizing["candidate_gapdiff_breakout_multiplier_applied"] = multiplier
        sig["sizing"] = new_sizing
        _state["breakout_signals_adjusted"] += 1

    return sized


def _install_patches():
    global _original_size_signals
    _original_size_signals = pe_module.size_signals
    pe_module.size_signals = _patched_size_signals


def _remove_patches():
    pe_module.size_signals = _original_size_signals


def _run_window(universe: list[str], label: str, cfg: dict, variant_name: str, variant_cfg: dict) -> dict:
    _state["gap_diff_threshold"] = variant_cfg["gap_diff_threshold"]
    _state["breakout_multiplier"] = variant_cfg["breakout_multiplier"]
    _state["trigger_days_hit"] = 0
    _state["breakout_signals_adjusted"] = 0

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
    return {
        "window": label,
        "start": cfg["start"],
        "end": cfg["end"],
        "snapshot": cfg["snapshot"],
        "variant": variant_name,
        "gap_diff_threshold": variant_cfg["gap_diff_threshold"],
        "breakout_multiplier": variant_cfg["breakout_multiplier"],
        "trigger_days_hit_during_sizing": _state["trigger_days_hit"],
        "breakout_signals_adjusted": _state["breakout_signals_adjusted"],
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "total_return_pct": (result.get("benchmarks") or {}).get("strategy_total_return_pct"),
        "trade_count": result.get("total_trades"),
        "win_rate": result.get("win_rate"),
    }


def main() -> int:
    universe = get_universe()

    _install_patches()
    try:
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
                    f"trigger_hits={summary['trigger_days_hit_during_sizing']} "
                    f"breakout_adjusted={summary['breakout_signals_adjusted']}"
                )
                results.append(summary)
    finally:
        _remove_patches()

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {
                "rule": {
                    "name": "candidate_cohort_gapdiff_breakout_derisk",
                    "definition": (
                        "if avg_gap_vulnerability(breakout candidates) - "
                        "avg_gap_vulnerability(trend candidates) exceeds a threshold "
                        "on a sizing day, de-risk breakout_long on that day"
                    ),
                    "goal": (
                        "test whether a candidate-cohort state tied directly to same-day "
                        "opportunity composition unlocks a non-vacuous breakout-allocation edge"
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
