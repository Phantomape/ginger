"""exp-20260424-001 runtime-only monkeypatch runner for the strict stress haircut.

Plan: apply a gross risk multiplier of `0.5x` on trading days where the
conjunctive stress state fires:

    stress_strict = breadth_above_200 <= 0.55 AND spy_pct_from_ma <= -0.02

The trigger map was pre-computed by `exp_20260423_014_audit.py` and cached in
`data/exp_20260423_014_stress_audit.json`. This script:

1. Loads the audit JSON and builds a {date_str: bool} stress map per window.
2. Monkey-patches `BacktestEngine._earnings_dict_for` to record today's date.
3. Monkey-patches `quant.backtester.size_signals` to scale `risk_pct` by the
   multiplier on stress days.
4. Runs the accepted A+B stack three times (late/mid/old fixed snapshots) for
   each screened multiplier, and writes a consolidated result JSON to
   `data/exp_20260423_014_results.json`.

No repo trading logic is modified; the script is rolled back after measurement.
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

import pandas as pd  # noqa: E402

import backtester as bt_module  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
import portfolio_engine as pe_module  # noqa: E402


# The backtester imports `size_signals` locally inside run() from portfolio_engine.
# That means the live bound symbol is `portfolio_engine.size_signals`; patching
# `backtester.size_signals` does nothing. Keep a reference for both for safety.


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

AUDIT_JSON = os.path.join(REPO_ROOT, "data", "exp_20260423_014_stress_audit.json")
OUT_JSON   = os.path.join(REPO_ROOT, "data", "exp_20260423_014_results.json")


_current_day_holder: dict = {
    "today_str": None,
    "stress_days": set(),
    "multiplier": 1.0,
    "stress_hits_today": 0,
}


def _load_stress_map() -> dict:
    """Return {window_label: set(YYYY-MM-DD strings where stress_strict fired)}."""
    with open(AUDIT_JSON, "r", encoding="utf-8") as f:
        payload = json.load(f)
    out = {}
    for window in payload["windows"]:
        out[window["label"]] = set(window.get("stress_dates") or [])
    return out


def _patched_earnings_dict_for(self, today, *args, **kwargs):
    """Side-effect hook: record today's ISO date string before signals size."""
    try:
        day_str = today.strftime("%Y-%m-%d") if hasattr(today, "strftime") else str(today)
    except Exception:
        day_str = str(today)
    _current_day_holder["today_str"] = day_str
    return _original_earnings_dict_for(self, today, *args, **kwargs)


def _patched_size_signals(signals, portfolio_value, risk_pct=None):
    today_str = _current_day_holder.get("today_str")
    stress_days = _current_day_holder.get("stress_days") or set()
    multiplier = _current_day_holder.get("multiplier", 1.0)
    if today_str and today_str in stress_days and multiplier != 1.0:
        base = risk_pct if risk_pct is not None else pe_module.RISK_PER_TRADE_PCT
        effective = base * multiplier
        _current_day_holder["stress_hits_today"] += 1
        return _original_size_signals(
            signals, portfolio_value, risk_pct=effective
        )
    return _original_size_signals(signals, portfolio_value, risk_pct=risk_pct)


def _install_patches():
    global _original_earnings_dict_for, _original_size_signals
    _original_earnings_dict_for = BacktestEngine._earnings_dict_for
    _original_size_signals = pe_module.size_signals
    BacktestEngine._earnings_dict_for = _patched_earnings_dict_for
    pe_module.size_signals = _patched_size_signals


def _remove_patches():
    BacktestEngine._earnings_dict_for = _original_earnings_dict_for
    pe_module.size_signals = _original_size_signals


def _run_window(label: str, cfg: dict, multiplier: float, stress_days: set) -> dict:
    """Run the backtester for one window with the patched size function."""
    from data_layer import get_universe
    universe = get_universe()

    _current_day_holder["stress_days"] = stress_days
    _current_day_holder["multiplier"] = multiplier
    _current_day_holder["stress_hits_today"] = 0
    _current_day_holder["today_str"] = None

    snapshot_path = os.path.join(REPO_ROOT, cfg["snapshot"])
    engine = BacktestEngine(
        universe,
        start=cfg["start"],
        end=cfg["end"],
        config={"REGIME_AWARE_EXIT": True},
        replay_llm=False,
        replay_news=False,
        data_dir=os.path.join(REPO_ROOT, "data"),
        ohlcv_snapshot_path=snapshot_path,
    )
    result = engine.run()
    summary = {
        "window": label,
        "start": cfg["start"],
        "end":   cfg["end"],
        "snapshot": cfg["snapshot"],
        "multiplier": multiplier,
        "stress_days_available": len(stress_days),
        "stress_days_hit_during_sizing": _current_day_holder["stress_hits_today"],
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "total_return_pct": (
            (result.get("benchmarks") or {}).get("strategy_total_return_pct")
        ),
        "total_trades": result.get("total_trades"),
        "win_rate": result.get("win_rate"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
    }
    return summary


def main() -> int:
    if not os.path.exists(AUDIT_JSON):
        print(f"ERROR: audit JSON missing: {AUDIT_JSON}", file=sys.stderr)
        return 1
    stress_map = _load_stress_map()

    multipliers = [1.0, 0.5, 0.25]  # 1.0 = baseline check (no haircut at all)

    _install_patches()
    try:
        results = []
        for label, cfg in WINDOWS.items():
            for mult in multipliers:
                summary = _run_window(label, cfg, mult, stress_map.get(label, set()))
                print(
                    f"[{label} mult={mult}] "
                    f"EV={summary['expected_value_score']} "
                    f"sharpe_d={summary['sharpe_daily']} "
                    f"return={summary['total_return_pct']} "
                    f"dd={summary['max_drawdown_pct']} "
                    f"trades={summary['total_trades']} "
                    f"hits={summary['stress_days_hit_during_sizing']}"
                )
                results.append(summary)
    finally:
        _remove_patches()

    payload = {
        "rule": {
            "name": "stress_strict",
            "definition": (
                "breadth_above_200 <= 0.55 AND spy_pct_from_ma <= -0.02"
            ),
            "action": "multiply risk_pct by multiplier on stress days",
        },
        "multipliers_tested": multipliers,
        "results": results,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"\nWrote results -> {OUT_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
