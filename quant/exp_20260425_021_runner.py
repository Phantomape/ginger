"""exp-20260425-021 Healthcare breakout DTE residual probe.

Runtime-only alpha search after the accepted A+B residual sizing stack.

Hypothesis:
    The remaining Healthcare breakout leakage may be event-distance related,
    not another repeat of the rejected deep-pullback screen. If 20-65 DTE
    Healthcare breakouts keep losing across validation windows, de-risking that
    narrow sleeve may improve expected value without touching entries, exits,
    LLM, C strategy, or existing accepted sizing rules.

No production trading code is changed by this runner.
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
    ("baseline", {"dte_min": None, "dte_max": None, "multiplier": 1.0}),
    ("healthcare_breakout_dte_20_65_x025", {"dte_min": 20, "dte_max": 65, "multiplier": 0.25}),
    ("healthcare_breakout_dte_20_65_x000", {"dte_min": 20, "dte_max": 65, "multiplier": 0.0}),
    ("healthcare_breakout_dte_20_70_x025", {"dte_min": 20, "dte_max": 70, "multiplier": 0.25}),
    ("healthcare_breakout_dte_20_70_x000", {"dte_min": 20, "dte_max": 70, "multiplier": 0.0}),
    ("healthcare_breakout_dte_50_65_x025", {"dte_min": 50, "dte_max": 65, "multiplier": 0.25}),
    ("healthcare_breakout_dte_50_65_x000", {"dte_min": 50, "dte_max": 65, "multiplier": 0.0}),
])

OUT_JSON = os.path.join(REPO_ROOT, "data", "exp_20260425_021_results.json")

_state = {
    "variant": {},
    "eligible_signals": 0,
    "adjusted_signals": 0,
}


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


def _copy_sizing_metadata(old_sizing: dict, new_sizing: dict):
    for key, value in old_sizing.items():
        if key.endswith("_applied") or key in (
            "base_risk_pct",
            "trade_quality_score",
            "low_tqs_haircut_exempt_sector",
        ):
            new_sizing[key] = value


def _matches(sig: dict) -> bool:
    variant = _state["variant"]
    if variant.get("multiplier", 1.0) >= 1.0:
        return False
    if sig.get("strategy") != "breakout_long":
        return False
    if sig.get("sector") != "Healthcare":
        return False
    dte = sig.get("days_to_earnings")
    if dte is None:
        return False
    return variant["dte_min"] <= dte <= variant["dte_max"]


def _patched_size_signals(signals, portfolio_value, risk_pct=None):
    sized = _original_size_signals(signals, portfolio_value, risk_pct=risk_pct)
    multiplier = _state["variant"].get("multiplier", 1.0)

    for sig in sized:
        if not _matches(sig):
            continue

        _state["eligible_signals"] += 1
        sizing = sig.get("sizing")
        if not sizing:
            continue

        entry = sig.get("entry_price")
        stop = sig.get("stop_price")
        if entry is None or stop is None:
            continue

        current_signal_risk_pct = sizing.get("risk_pct", 0.0)
        if multiplier <= 0:
            new_sizing = _zero_risk_sizing(
                portfolio_value,
                entry,
                stop,
                sizing.get("base_risk_pct", current_signal_risk_pct),
            )
        else:
            new_sizing = pe_module.compute_position_size(
                portfolio_value,
                entry,
                stop,
                risk_pct=current_signal_risk_pct * multiplier,
            )
        if not new_sizing:
            continue

        _copy_sizing_metadata(sizing, new_sizing)
        new_sizing["exp_20260425_021_multiplier_applied"] = multiplier
        new_sizing["exp_20260425_021_rule"] = "breakout_healthcare_dte"
        sig["sizing"] = new_sizing
        _state["adjusted_signals"] += 1

    return sized


def _install_patches():
    global _original_size_signals
    _original_size_signals = pe_module.size_signals
    pe_module.size_signals = _patched_size_signals


def _remove_patches():
    pe_module.size_signals = _original_size_signals


def _eligible_trade_rows(result: dict) -> list[dict]:
    rows = []
    variant = _state["variant"]
    if variant.get("multiplier", 1.0) >= 1.0:
        return rows
    for trade in result.get("trades", []):
        if trade.get("strategy") != "breakout_long":
            continue
        if trade.get("sector") != "Healthcare":
            continue
        dte = trade.get("sig_days_to_earnings")
        if dte is None or not (variant["dte_min"] <= dte <= variant["dte_max"]):
            continue
        rows.append({
            "ticker": trade.get("ticker"),
            "entry_date": trade.get("entry_date"),
            "pnl": trade.get("pnl"),
            "dte": dte,
            "pct_from_52w_high": trade.get("sig_pct_from_52w_high"),
            "gap_vulnerability_pct": trade.get("sig_gap_vulnerability_pct"),
            "trade_quality_score": trade.get("sig_trade_quality_score"),
        })
    return rows


def _run_window(universe: list[str], label: str, cfg: dict, variant_name: str, variant_cfg: dict) -> dict:
    _state["variant"] = variant_cfg
    _state["eligible_signals"] = 0
    _state["adjusted_signals"] = 0

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
    return {
        "window": label,
        "start": cfg["start"],
        "end": cfg["end"],
        "snapshot": cfg["snapshot"],
        "variant": variant_name,
        "variant_cfg": variant_cfg,
        "eligible_signals": _state["eligible_signals"],
        "adjusted_signals": _state["adjusted_signals"],
        "eligible_trades": _eligible_trade_rows(result),
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "total_return_pct": (result.get("benchmarks") or {}).get(
            "strategy_total_return_pct"
        ),
        "trade_count": result.get("total_trades"),
        "win_rate": result.get("win_rate"),
    }


def main() -> int:
    universe = get_universe()
    results = []

    _install_patches()
    try:
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
                    f"eligible={summary['eligible_signals']} "
                    f"adjusted={summary['adjusted_signals']}"
                )
                results.append(summary)
    finally:
        _remove_patches()

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {
                "hypothesis": (
                    "Healthcare breakout residual leakage may be event-distance "
                    "related rather than another rejected deep-pullback screen"
                ),
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
