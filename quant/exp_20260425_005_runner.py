"""exp-20260425-005 macro defensive sleeve pre-research.

Hypothesis:
    The current A+B stack may be over-specialized for trend/breakout tapes.
    A separate macro defensive sleeve (commodities, healthcare, energy) could
    add a genuinely different alpha source during index-pressure windows.

This runner is experiment-only. It monkeypatches signal generation at runtime
and does not change production strategy code.
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
from risk_engine import SECTOR_MAP  # noqa: E402
import signal_engine as se_module  # noqa: E402


DEFENSIVE_SECTORS = {"Commodities", "Healthcare", "Energy"}

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
    ("baseline_ab", {"mode": "baseline_ab"}),
    ("macro_only", {"mode": "macro_only"}),
    ("ab_plus_macro", {"mode": "ab_plus_macro"}),
])

OUT_JSON = os.path.join(REPO_ROOT, "data", "exp_20260425_005_results.json")

_state = {
    "mode": "baseline_ab",
    "macro_candidates": 0,
    "macro_added": 0,
}


def _macro_defensive_signal(ticker: str, features: dict, market_context: dict | None):
    sector = SECTOR_MAP.get(ticker, "Unknown")
    if sector not in DEFENSIVE_SECTORS:
        return None

    close = features.get("close")
    atr = features.get("atr")
    if not close or not atr:
        return None

    above_200 = bool(features.get("above_200ma"))
    momentum_10d = features.get("momentum_10d_pct")
    trend_score = features.get("trend_score") or 0
    stock_10d = momentum_10d or 0
    spy_10d = (market_context or {}).get("spy_10d_return") or 0
    spy_pct = (market_context or {}).get("spy_pct_from_ma")
    qqq_pct = (market_context or {}).get("qqq_pct_from_ma")

    # This sleeve should only activate when broad beta is not cleanly supportive.
    index_pressure = (
        (spy_pct is not None and spy_pct < 0)
        or (qqq_pct is not None and qqq_pct < 0)
        or ((market_context or {}).get("market_regime") in {"NEUTRAL", "BEAR"})
    )
    if not index_pressure:
        return None

    # No knife catching: defensive assets must still be in their own uptrend.
    if not above_200 or stock_10d <= 0:
        return None
    if stock_10d <= spy_10d:
        return None
    if trend_score < 0.55:
        return None

    dte = features.get("days_to_earnings")
    if dte is not None and dte <= 3:
        return None

    entry = close
    stop = round(entry - ATR_STOP_MULT * atr, 2)
    rel_strength = round(stock_10d - spy_10d, 4)
    confidence = se_module._confidence([
        (above_200, 1.0),
        (stock_10d > 0, 1.0),
        (rel_strength > 0, 1.0),
        (trend_score >= 0.65, 0.5),
        (sector == "Commodities", 0.25),
    ])

    return {
        "ticker": ticker,
        "strategy": "macro_defensive_long",
        "entry_price": round(entry, 2),
        "stop_price": stop,
        "confidence_score": confidence,
        "entry_note": "Execute next-day open; macro defensive sleeve candidate",
        "conditions_met": {
            "sector": sector,
            "above_200ma": above_200,
            "momentum_10d_pct": momentum_10d,
            "rs_vs_spy": rel_strength,
            "trend_score": trend_score,
            "spy_pct_from_ma": spy_pct,
            "qqq_pct_from_ma": qqq_pct,
            "index_pressure": index_pressure,
        },
    }


def _macro_signals(features_dict, market_context):
    signals = []
    for ticker, features in features_dict.items():
        if not features:
            continue
        sig = _macro_defensive_signal(ticker, features, market_context)
        if sig:
            signals.append(sig)
    return sorted(signals, key=lambda s: s["confidence_score"], reverse=True)


def _patched_generate_signals(
    features_dict,
    market_context=None,
    enabled_strategies=None,
    breakout_max_pullback_from_52w_high=None,
):
    mode = _state["mode"]
    if mode == "macro_only":
        macro = _macro_signals(features_dict, market_context)
        _state["macro_candidates"] += len(macro)
        _state["macro_added"] += len(macro)
        return macro

    base = _original_generate_signals(
        features_dict,
        market_context=market_context,
        enabled_strategies=enabled_strategies,
        breakout_max_pullback_from_52w_high=breakout_max_pullback_from_52w_high,
    )
    if mode == "baseline_ab":
        return base

    macro = _macro_signals(features_dict, market_context)
    _state["macro_candidates"] += len(macro)
    base_tickers = {s.get("ticker") for s in base}
    additions = [s for s in macro if s.get("ticker") not in base_tickers]
    _state["macro_added"] += len(additions)
    return sorted(base + additions, key=lambda s: s.get("confidence_score", 0), reverse=True)


def _install_patches():
    global _original_generate_signals
    _original_generate_signals = se_module.generate_signals
    se_module.generate_signals = _patched_generate_signals


def _remove_patches():
    se_module.generate_signals = _original_generate_signals


def _run_window(universe: list[str], label: str, cfg: dict, variant_name: str, variant_cfg: dict) -> dict:
    _state["mode"] = variant_cfg["mode"]
    _state["macro_candidates"] = 0
    _state["macro_added"] = 0

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
    by_strategy = result.get("by_strategy") or {}
    macro_attr = by_strategy.get("macro_defensive_long") or {}
    return {
        "window": label,
        "start": cfg["start"],
        "end": cfg["end"],
        "snapshot": cfg["snapshot"],
        "variant": variant_name,
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "total_return_pct": (result.get("benchmarks") or {}).get("strategy_total_return_pct"),
        "trade_count": result.get("total_trades"),
        "win_rate": result.get("win_rate"),
        "macro_candidates": _state["macro_candidates"],
        "macro_added": _state["macro_added"],
        "macro_trade_count": macro_attr.get("trade_count", 0),
        "macro_total_pnl": macro_attr.get("total_pnl_usd"),
        "macro_profit_factor": macro_attr.get("profit_factor"),
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
                    f"macro_trades={summary['macro_trade_count']} "
                    f"macro_added={summary['macro_added']}"
                )
                results.append(summary)
    finally:
        _remove_patches()

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {
                "rule": {
                    "name": "macro_defensive_long_presearch",
                    "definition": (
                        "A separate defensive/macro sleeve for Commodities, "
                        "Healthcare, and Energy during index-pressure states. "
                        "Requires above_200ma, positive 10d momentum, positive "
                        "relative 10d momentum versus SPY, and trend_score >= 0.55."
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
