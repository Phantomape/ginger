"""exp-20260425-025 QQQ idle-capital beta sleeve research.

Hypothesis:
    The mid_weak window underperforms SPY/QQQ because the active A+B stack is
    under-exposed during a ripping growth tape. A QQQ sleeve that queues behind
    normal A+B signals and only uses spare slots may close part of that benchmark
    gap without changing stock selection, exits, or existing sizing rules.

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
from constants import ATR_STOP_MULT  # noqa: E402
from data_layer import get_universe  # noqa: E402
import portfolio_engine as pe_module  # noqa: E402
import signal_engine as se_module  # noqa: E402


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
    ("baseline", {"enabled": False, "risk_multiplier": None, "mom10_min": None}),
    ("qqq_idle_mom015_risk050", {"enabled": True, "risk_multiplier": 0.50, "mom10_min": 0.015}),
    ("qqq_idle_mom015_risk100", {"enabled": True, "risk_multiplier": 1.00, "mom10_min": 0.015}),
    ("qqq_idle_mom025_risk050", {"enabled": True, "risk_multiplier": 0.50, "mom10_min": 0.025}),
    ("qqq_idle_mom025_risk100", {"enabled": True, "risk_multiplier": 1.00, "mom10_min": 0.025}),
])

OUT_JSON = os.path.join(REPO_ROOT, "data", "exp_20260425_025_results.json")

_state = {
    "enabled": False,
    "risk_multiplier": None,
    "mom10_min": None,
    "candidates": 0,
    "added": 0,
    "sized": 0,
}


def _safe_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _qqq_beta_signal(features_dict: dict, market_context: dict | None):
    qqq = features_dict.get("QQQ")
    if not qqq:
        return None

    close = qqq.get("close")
    atr = qqq.get("atr")
    if not close or not atr:
        return None

    regime = (market_context or {}).get("market_regime")
    mom10 = _safe_float(qqq.get("momentum_10d_pct"))
    price_vs_200ma = _safe_float(qqq.get("price_vs_200ma_pct"))
    spy_mom10 = _safe_float((market_context or {}).get("spy_10d_return"))
    qqq_pct_from_ma = _safe_float((market_context or {}).get("qqq_pct_from_ma"))

    if regime != "BULL":
        return None
    if not qqq.get("above_200ma"):
        return None
    if mom10 is None or mom10 < _state["mom10_min"]:
        return None
    if price_vs_200ma is None or price_vs_200ma < 0.05:
        return None
    if qqq_pct_from_ma is None or qqq_pct_from_ma < 0.05:
        return None
    if spy_mom10 is not None and mom10 <= spy_mom10:
        return None

    entry = close
    stop = round(entry - ATR_STOP_MULT * atr, 2)
    return {
        "ticker": "QQQ",
        "strategy": "qqq_idle_beta_long",
        "sector": "ETF",
        "entry_price": round(entry, 2),
        "stop_price": stop,
        "confidence_score": 1.0,
        "entry_note": "Execute next-day open; QQQ idle-capital beta sleeve",
        "conditions_met": {
            "above_200ma": bool(qqq.get("above_200ma")),
            "momentum_10d_pct": mom10,
            "price_vs_200ma_pct": price_vs_200ma,
            "qqq_pct_from_ma": qqq_pct_from_ma,
            "spy_10d_return": spy_mom10,
            "mom10_min": _state["mom10_min"],
        },
    }


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
    if not _state["enabled"]:
        return base

    sig = _qqq_beta_signal(features_dict, market_context)
    if not sig:
        return base

    _state["candidates"] += 1
    base_tickers = {s.get("ticker") for s in base}
    if "QQQ" in base_tickers:
        return base
    _state["added"] += 1
    return list(base) + [sig]


def _patched_size_signals(signals, portfolio_value, risk_pct=None):
    sized = _original_size_signals(signals, portfolio_value, risk_pct=risk_pct)
    multiplier = _state["risk_multiplier"]
    if multiplier is None:
        return sized

    out = []
    for sig in sized:
        if sig.get("strategy") != "qqq_idle_beta_long":
            out.append(sig)
            continue
        sizing = sig.get("sizing") or {}
        entry = sig.get("entry_price")
        stop = sig.get("stop_price")
        if not sizing or entry is None or stop is None:
            out.append(sig)
            continue
        current_risk = sizing.get("risk_pct", 0.0)
        new_sizing = pe_module.compute_position_size(
            portfolio_value,
            entry,
            stop,
            risk_pct=current_risk * multiplier,
        )
        if not new_sizing:
            out.append(sig)
            continue
        for key, value in sizing.items():
            if key.endswith("_applied") or key in ("base_risk_pct", "trade_quality_score"):
                new_sizing[key] = value
        new_sizing["qqq_idle_beta_risk_multiplier_applied"] = multiplier
        sig = {**sig, "sizing": new_sizing}
        _state["sized"] += 1
        out.append(sig)
    return out


def _install_patches():
    global _original_generate_signals, _original_size_signals
    _original_generate_signals = se_module.generate_signals
    _original_size_signals = pe_module.size_signals
    se_module.generate_signals = _patched_generate_signals
    pe_module.size_signals = _patched_size_signals


def _remove_patches():
    se_module.generate_signals = _original_generate_signals
    pe_module.size_signals = _original_size_signals


def _summary(result: dict, label: str, cfg: dict, variant: str, variant_cfg: dict) -> dict:
    by_strategy = result.get("by_strategy") or {}
    beta_attr = by_strategy.get("qqq_idle_beta_long") or {}
    cap_eff = result.get("capital_efficiency") or {}
    return {
        "window": label,
        "start": cfg["start"],
        "end": cfg["end"],
        "snapshot": cfg["snapshot"],
        "variant": variant,
        "risk_multiplier": variant_cfg["risk_multiplier"],
        "mom10_min": variant_cfg["mom10_min"],
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "total_return_pct": (result.get("benchmarks") or {}).get("strategy_total_return_pct"),
        "strategy_vs_spy_pct": (result.get("benchmarks") or {}).get("strategy_vs_spy_pct"),
        "strategy_vs_qqq_pct": (result.get("benchmarks") or {}).get("strategy_vs_qqq_pct"),
        "trade_count": result.get("total_trades"),
        "win_rate": result.get("win_rate"),
        "gross_slot_day_fraction": cap_eff.get("gross_slot_day_fraction"),
        "qqq_candidates": _state["candidates"],
        "qqq_added": _state["added"],
        "qqq_sized": _state["sized"],
        "qqq_trade_count": beta_attr.get("trade_count", 0),
        "qqq_total_pnl": beta_attr.get("total_pnl_usd"),
        "qqq_profit_factor": beta_attr.get("profit_factor"),
    }


def _run_window(universe: list[str], label: str, cfg: dict,
                variant_name: str, variant_cfg: dict) -> dict:
    _state["enabled"] = variant_cfg["enabled"]
    _state["risk_multiplier"] = variant_cfg["risk_multiplier"]
    _state["mom10_min"] = variant_cfg["mom10_min"]
    _state["candidates"] = 0
    _state["added"] = 0
    _state["sized"] = 0

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
    return _summary(result, label, cfg, variant_name, variant_cfg)


def main() -> int:
    universe = list(dict.fromkeys(list(get_universe()) + ["QQQ"]))
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
                    f"vs_spy={summary['strategy_vs_spy_pct']} "
                    f"vs_qqq={summary['strategy_vs_qqq_pct']} "
                    f"sharpe_d={summary['sharpe_daily']} "
                    f"dd={summary['max_drawdown_pct']} "
                    f"trades={summary['trade_count']} "
                    f"qqq_trades={summary['qqq_trade_count']} "
                    f"qqq_added={summary['qqq_added']} "
                    f"slot_use={summary['gross_slot_day_fraction']}"
                )
                results.append(summary)
    finally:
        _remove_patches()

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {
                "rule": {
                    "name": "qqq_idle_capital_beta_sleeve",
                    "definition": (
                        "Append a QQQ long signal behind normal A+B candidates "
                        "when market_regime == BULL, QQQ is above its 200dma, "
                        "QQQ 10d momentum clears the variant threshold, QQQ is "
                        "at least 5% above its 200dma, and QQQ 10d momentum "
                        "exceeds SPY 10d momentum. It uses only spare normal "
                        "portfolio slots because it is appended after A+B."
                    ),
                    "goal": (
                        "test whether idle-capital beta exposure can close the "
                        "mid_weak SPY/QQQ benchmark gap without damaging other "
                        "fixed windows"
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
