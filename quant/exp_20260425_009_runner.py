"""exp-20260425-009 residual trend pocket: Consumer near-high 30-65 DTE.

Hypothesis:
    After the accepted A+B residual allocation stack, a remaining trend leak may
    sit in Consumer Discretionary names entering very near the 52-week high while
    still 30-65 trading days from earnings. The audited fixed-window trades map
    this to MCD-like entries that stopped out in late/old windows and had no mid
    exposure.

    This runner changes only runtime sizing for measurement:

        strategy == trend_long
        sector == Consumer Discretionary
        30 <= days_to_earnings <= 65
        pct_from_52w_high >= -0.01

    It screens 0.25x and 0.0x risk against the current accepted stack. No
    production trading code is changed by this experiment runner.
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
    ("baseline", {"multiplier": 1.0}),
    ("trend_consumer_near_high_dte3065_025", {"multiplier": 0.25}),
    ("trend_consumer_near_high_dte3065_000", {"multiplier": 0.0}),
])

OUT_JSON = os.path.join(REPO_ROOT, "data", "exp_20260425_009_results.json")

_state = {
    "multiplier": 1.0,
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


def _copy_sizing_metadata(old_sizing: dict, new_sizing: dict, base_risk_pct):
    new_sizing["base_risk_pct"] = old_sizing.get("base_risk_pct", base_risk_pct)
    for key in [
        "trade_quality_score",
        "low_tqs_haircut_exempt_sector",
        "tqs_risk_multiplier_applied",
        "trend_industrials_risk_multiplier_applied",
        "trend_tech_tight_gap_risk_multiplier_applied",
        "trend_tech_gap_risk_multiplier_applied",
        "trend_tech_near_high_risk_multiplier_applied",
        "breakout_industrials_gap_risk_multiplier_applied",
        "breakout_comms_near_high_risk_multiplier_applied",
        "breakout_comms_gap_risk_multiplier_applied",
        "breakout_financials_dte_risk_multiplier_applied",
        "trend_healthcare_dte_risk_multiplier_applied",
    ]:
        if key in old_sizing:
            new_sizing[key] = old_sizing[key]


def _patched_size_signals(signals, portfolio_value, risk_pct=None):
    original_multiplier = (
        pe_module.TREND_CONSUMER_NEAR_HIGH_DTE_RISK_MULTIPLIER
    )
    pe_module.TREND_CONSUMER_NEAR_HIGH_DTE_RISK_MULTIPLIER = 1.0
    try:
        sized = _original_size_signals(signals, portfolio_value, risk_pct=risk_pct)
    finally:
        pe_module.TREND_CONSUMER_NEAR_HIGH_DTE_RISK_MULTIPLIER = (
            original_multiplier
        )

    for sig in sized:
        if (
            sig.get("strategy") != "trend_long"
            or sig.get("sector") != "Consumer Discretionary"
        ):
            continue

        dte = sig.get("days_to_earnings")
        pct_from_52w_high = (sig.get("conditions_met") or {}).get(
            "pct_from_52w_high"
        )
        if (
            dte is None
            or pct_from_52w_high is None
            or not (30 <= dte <= 65)
            or pct_from_52w_high < -0.01
        ):
            continue

        _state["eligible_signals"] += 1
        multiplier = _state["multiplier"]
        if multiplier >= 1.0:
            continue

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

        _copy_sizing_metadata(sizing, new_sizing, risk_pct)
        new_sizing["trend_consumer_near_high_dte3065_multiplier_applied"] = multiplier
        sig["sizing"] = new_sizing
        _state["adjusted_signals"] += 1

    return sized


def _install_patches():
    global _original_size_signals
    _original_size_signals = pe_module.size_signals
    pe_module.size_signals = _patched_size_signals


def _remove_patches():
    pe_module.size_signals = _original_size_signals


def _run_window(
    universe: list[str], label: str, cfg: dict, variant_name: str, variant_cfg: dict
) -> dict:
    _state["multiplier"] = variant_cfg["multiplier"]
    _state["eligible_signals"] = 0
    _state["adjusted_signals"] = 0

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
    return {
        "window": label,
        "start": cfg["start"],
        "end": cfg["end"],
        "snapshot": cfg["snapshot"],
        "variant": variant_name,
        "trend_consumer_near_high_dte3065_multiplier": variant_cfg["multiplier"],
        "eligible_trend_consumer_near_high_dte3065_signals": (
            _state["eligible_signals"]
        ),
        "adjusted_trend_consumer_near_high_dte3065_signals": (
            _state["adjusted_signals"]
        ),
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
                    f"eligible={summary['eligible_trend_consumer_near_high_dte3065_signals']} "
                    f"adjusted={summary['adjusted_trend_consumer_near_high_dte3065_signals']}"
                )
                results.append(summary)
    finally:
        _remove_patches()

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {
                "rule": {
                    "name": "trend_consumer_near_high_dte3065_de_risk",
                    "definition": (
                        "apply a sleeve-specific risk multiplier only when "
                        "strategy == trend_long, sector == Consumer Discretionary, "
                        "30 <= days_to_earnings <= 65, and "
                        "pct_from_52w_high >= -0.01"
                    ),
                    "goal": (
                        "test whether residual Consumer Discretionary trend drag "
                        "is concentrated in the near-high 30-65 DTE pocket"
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
