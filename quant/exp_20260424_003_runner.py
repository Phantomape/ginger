"""exp-20260424-003 runtime-only two-stage stress -> trend haircut runner.

Keeps the strict weak-tape detector fixed from exp-20260423-014:
    stress_strict = breadth_above_200 <= 0.55 AND spy_pct_from_ma <= -0.02

Changes only the stage-two action:
    de-risk `trend_long` on stress_strict days
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

AUDIT_JSON = os.path.join(REPO_ROOT, "data", "exp_20260423_014_stress_audit.json")
OUT_JSON = os.path.join(REPO_ROOT, "data", "exp_20260424_003_results.json")


_current_day_holder: dict = {
    "today_str": None,
    "stress_days": set(),
    "sim_dates": [],
    "sim_index": -1,
    "trend_multiplier": 1.0,
    "trend_signals_haircut": 0,
    "stress_days_hit_during_sizing": 0,
}


def _load_stress_map() -> dict:
    with open(AUDIT_JSON, "r", encoding="utf-8") as f:
        payload = json.load(f)
    out = {}
    for window in payload["windows"]:
        out[window["label"]] = set(window.get("stress_dates") or [])
    return out


def _load_sim_dates(snapshot_relpath: str, start: str, end: str) -> list[str]:
    snapshot_path = os.path.join(REPO_ROOT, snapshot_relpath)
    with open(snapshot_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    spy_rows = payload["ohlcv"]["SPY"]
    dates = []
    for row in spy_rows:
        day = row["Date"][:10]
        if start <= day <= end:
            dates.append(day)
    return dates


def _patched_compute_portfolio_heat(open_positions, current_prices, portfolio_value, features_dict=None):
    _current_day_holder["sim_index"] += 1
    sim_dates = _current_day_holder.get("sim_dates") or []
    idx = _current_day_holder["sim_index"]
    if 0 <= idx < len(sim_dates):
        _current_day_holder["today_str"] = sim_dates[idx]
    return _original_compute_portfolio_heat(
        open_positions,
        current_prices,
        portfolio_value,
        features_dict=features_dict,
    )


def _patched_size_signals(signals, portfolio_value, risk_pct=None):
    today_str = _current_day_holder.get("today_str")
    stress_days = _current_day_holder.get("stress_days") or set()
    trend_multiplier = _current_day_holder.get("trend_multiplier", 1.0)
    if not today_str or today_str not in stress_days or trend_multiplier == 1.0:
        return _original_size_signals(signals, portfolio_value, risk_pct=risk_pct)

    patched_signals = []
    stress_hit = False
    trend_haircuts = 0
    for sig in signals:
        sig2 = dict(sig)
        if sig2.get("strategy") == "trend_long":
            sig2["_stress_trend_multiplier"] = trend_multiplier
            trend_haircuts += 1
            stress_hit = True
        patched_signals.append(sig2)

    sized = _original_size_signals(patched_signals, portfolio_value, risk_pct=risk_pct)
    for sig in sized:
        mult = sig.pop("_stress_trend_multiplier", None)
        if mult is None:
            continue
        sizing = sig.get("sizing")
        if not sizing:
            continue
        current_risk_pct = sizing.get("risk_pct", 0.0)
        new_risk_pct = current_risk_pct * mult
        entry = sig.get("entry_price")
        stop = sig.get("stop_price")
        if not entry or not stop:
            continue
        if new_risk_pct <= 0:
            sizing = {
                "portfolio_value_usd": round(portfolio_value, 2),
                "risk_pct": 0.0,
                "risk_amount_usd": 0.0,
                "entry_price": round(entry, 2),
                "stop_price": round(stop, 2),
                "risk_per_share": round(entry - stop, 2),
                "net_risk_per_share": round(
                    (entry - stop)
                    + entry * pe_module.ROUND_TRIP_COST_PCT
                    + entry * pe_module.EXEC_LAG_PCT,
                    4,
                ),
                "shares_to_buy": 0,
                "position_value_usd": 0.0,
                "position_pct_of_portfolio": 0.0,
                "base_risk_pct": sizing.get("base_risk_pct", risk_pct),
            }
        else:
            sizing = pe_module.compute_position_size(
                portfolio_value,
                entry,
                stop,
                risk_pct=new_risk_pct,
            )
            if sizing:
                sizing["base_risk_pct"] = sig.get("sizing", {}).get("base_risk_pct", risk_pct)
        if sizing:
            sizing["stress_trend_multiplier_applied"] = mult
            sig["sizing"] = sizing

    if stress_hit:
        _current_day_holder["stress_days_hit_during_sizing"] += 1
        _current_day_holder["trend_signals_haircut"] += trend_haircuts
    return sized


def _install_patches():
    global _original_compute_portfolio_heat, _original_size_signals
    _original_compute_portfolio_heat = pe_module.compute_portfolio_heat
    _original_size_signals = pe_module.size_signals
    pe_module.compute_portfolio_heat = _patched_compute_portfolio_heat
    pe_module.size_signals = _patched_size_signals


def _remove_patches():
    pe_module.compute_portfolio_heat = _original_compute_portfolio_heat
    pe_module.size_signals = _original_size_signals


def _run_window(label: str, cfg: dict, trend_multiplier: float, stress_days: set) -> dict:
    from data_layer import get_universe

    _current_day_holder["stress_days"] = stress_days
    _current_day_holder["sim_dates"] = _load_sim_dates(cfg["snapshot"], cfg["start"], cfg["end"])
    _current_day_holder["sim_index"] = -1
    _current_day_holder["trend_multiplier"] = trend_multiplier
    _current_day_holder["today_str"] = None
    _current_day_holder["stress_days_hit_during_sizing"] = 0
    _current_day_holder["trend_signals_haircut"] = 0

    engine = BacktestEngine(
        get_universe(),
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
        "trend_multiplier": trend_multiplier,
        "stress_days_available": len(stress_days),
        "stress_days_hit_during_sizing": _current_day_holder["stress_days_hit_during_sizing"],
        "trend_signals_haircut": _current_day_holder["trend_signals_haircut"],
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "total_return_pct": (result.get("benchmarks") or {}).get("strategy_total_return_pct"),
        "total_trades": result.get("total_trades"),
        "win_rate": result.get("win_rate"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
    }


def main() -> int:
    if not os.path.exists(AUDIT_JSON):
        print(f"ERROR: audit JSON missing: {AUDIT_JSON}", file=sys.stderr)
        return 1
    stress_map = _load_stress_map()
    multipliers = [1.0, 0.5, 0.25]

    _install_patches()
    try:
        results = []
        for label, cfg in WINDOWS.items():
            for mult in multipliers:
                summary = _run_window(label, cfg, mult, stress_map.get(label, set()))
                print(
                    f"[{label} trend_mult={mult}] "
                    f"EV={summary['expected_value_score']} "
                    f"sharpe_d={summary['sharpe_daily']} "
                    f"return={summary['total_return_pct']} "
                    f"dd={summary['max_drawdown_pct']} "
                    f"trades={summary['total_trades']} "
                    f"stress_hits={summary['stress_days_hit_during_sizing']} "
                    f"haircuts={summary['trend_signals_haircut']}"
                )
                results.append(summary)
    finally:
        _remove_patches()

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {
                "rule": {
                    "name": "stress_strict_two_stage_trend",
                    "definition": "breadth_above_200 <= 0.55 AND spy_pct_from_ma <= -0.02",
                    "action": "apply trend-specific multiplier on stress days only",
                },
                "trend_multipliers_tested": multipliers,
                "results": results,
            },
            f,
            indent=2,
        )
    print(f"\nWrote results -> {OUT_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
