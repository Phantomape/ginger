"""exp-20260425-007 macro defensive overlay budget research.

Hypothesis:
    The first macro sleeve may be useful as a small diversifying overlay, even
    though it failed when competing directly with A+B signals for the same main
    slots. This runner keeps macro entries unchanged and changes only the
    allocation shape: A+B keeps priority, while at most one macro signal is
    appended into an expanded spare overlay slot at reduced risk.

This runner is experiment-only. It monkeypatches signal generation and sizing
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
from constants import ATR_STOP_MULT, MAX_POSITIONS  # noqa: E402
from data_layer import get_universe  # noqa: E402
from risk_engine import SECTOR_MAP  # noqa: E402
import portfolio_engine as pe_module  # noqa: E402
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
    ("baseline_ab", {"mode": "baseline_ab", "macro_risk_multiplier": None}),
    ("overlay_025", {"mode": "overlay", "macro_risk_multiplier": 0.25}),
    ("overlay_050", {"mode": "overlay", "macro_risk_multiplier": 0.50}),
])

OUT_JSON = os.path.join(REPO_ROOT, "data", "exp_20260425_007_results.json")

_state = {
    "mode": "baseline_ab",
    "macro_risk_multiplier": None,
    "macro_candidates": 0,
    "macro_added": 0,
    "macro_sized": 0,
}


def _safe_float(value, default=0.0):
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _macro_defensive_signal(ticker: str, features: dict, market_context: dict | None):
    sector = SECTOR_MAP.get(ticker, "Unknown")
    if sector not in DEFENSIVE_SECTORS:
        return None

    close = features.get("close")
    atr = features.get("atr")
    if not close or not atr:
        return None

    above_200 = bool(features.get("above_200ma"))
    momentum_10d = _safe_float(features.get("momentum_10d_pct"))
    trend_score = _safe_float(features.get("trend_score"))
    spy_10d = _safe_float((market_context or {}).get("spy_10d_return"))
    spy_pct = (market_context or {}).get("spy_pct_from_ma")
    qqq_pct = (market_context or {}).get("qqq_pct_from_ma")

    index_pressure = (
        (spy_pct is not None and spy_pct < 0)
        or (qqq_pct is not None and qqq_pct < 0)
        or ((market_context or {}).get("market_regime") in {"NEUTRAL", "BEAR"})
    )
    if not index_pressure:
        return None

    if not above_200 or momentum_10d <= 0:
        return None
    if momentum_10d <= spy_10d:
        return None
    if trend_score < 0.55:
        return None

    dte = features.get("days_to_earnings")
    if dte is not None and dte <= 3:
        return None

    entry = close
    stop = round(entry - ATR_STOP_MULT * atr, 2)
    rel_strength = round(momentum_10d - spy_10d, 4)
    confidence = se_module._confidence([
        (above_200, 1.0),
        (momentum_10d > 0, 1.0),
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
        "entry_note": "Execute next-day open; macro defensive overlay candidate",
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


def _macro_candidates(features_dict, market_context):
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
    base = _original_generate_signals(
        features_dict,
        market_context=market_context,
        enabled_strategies=enabled_strategies,
        breakout_max_pullback_from_52w_high=breakout_max_pullback_from_52w_high,
    )
    if _state["mode"] == "baseline_ab":
        return base

    macro = _macro_candidates(features_dict, market_context)
    _state["macro_candidates"] += len(macro)
    base_tickers = {s.get("ticker") for s in base}
    additions = [s for s in macro if s.get("ticker") not in base_tickers][:1]
    for sig in additions:
        sig["macro_overlay_candidate"] = True
    _state["macro_added"] += len(additions)

    # A+B keeps priority. Macro only uses the extra experimental overlay slot
    # when the backtester has room after the normal candidate order.
    return list(base) + additions


def _patched_size_signals(signals, portfolio_value, risk_pct=None):
    sized = _original_size_signals(signals, portfolio_value, risk_pct=risk_pct)
    multiplier = _state["macro_risk_multiplier"]
    if multiplier is None:
        return sized

    adjusted = []
    for sig in sized:
        if sig.get("strategy") != "macro_defensive_long":
            adjusted.append(sig)
            continue
        sizing = dict(sig.get("sizing") or {})
        shares = sizing.get("shares_to_buy") or 0
        if shares > 0:
            new_shares = max(1, int(shares * multiplier))
            scale = new_shares / shares
            sizing["shares_to_buy"] = new_shares
            sizing["position_value_usd"] = round(
                (sizing.get("position_value_usd") or 0) * scale,
                2,
            )
            sizing["risk_amount_usd"] = round(
                (sizing.get("risk_amount_usd") or 0) * scale,
                2,
            )
            sizing["position_pct_of_portfolio"] = round(
                (sizing.get("position_pct_of_portfolio") or 0) * scale,
                4,
            )
            sizing["macro_overlay_risk_multiplier_applied"] = multiplier
            _state["macro_sized"] += 1
        adjusted.append({**sig, "sizing": sizing})
    return adjusted


def _install_patches():
    global _original_generate_signals, _original_size_signals
    _original_generate_signals = se_module.generate_signals
    _original_size_signals = pe_module.size_signals
    se_module.generate_signals = _patched_generate_signals
    pe_module.size_signals = _patched_size_signals


def _remove_patches():
    se_module.generate_signals = _original_generate_signals
    pe_module.size_signals = _original_size_signals


def _run_window(universe: list[str], label: str, cfg: dict, variant_name: str, variant_cfg: dict) -> dict:
    _state["mode"] = variant_cfg["mode"]
    _state["macro_risk_multiplier"] = variant_cfg["macro_risk_multiplier"]
    _state["macro_candidates"] = 0
    _state["macro_added"] = 0
    _state["macro_sized"] = 0

    engine_kwargs = {
        "universe": universe,
        "start": cfg["start"],
        "end": cfg["end"],
        "config": {
            "REGIME_AWARE_EXIT": True,
            "MAX_POSITIONS": MAX_POSITIONS + (1 if variant_cfg["mode"] == "overlay" else 0),
        },
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
        "macro_sized": _state["macro_sized"],
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
                    f"macro_added={summary['macro_added']} "
                    f"macro_sized={summary['macro_sized']}"
                )
                results.append(summary)
    finally:
        _remove_patches()

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {
                "rule": {
                    "name": "macro_defensive_overlay_budget",
                    "definition": (
                        "Same macro defensive entries as exp-20260425-005, but "
                        "A+B keeps priority and at most one macro signal is "
                        "appended into an expanded spare overlay slot at reduced risk."
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
