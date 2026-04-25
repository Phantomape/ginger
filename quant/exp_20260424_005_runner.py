"""exp-20260424-005 candidate-day QQQ-SPY relative momentum -> trend boost.

Tests a second lightweight healthy-tape sleeve-routing candidate:
    qqq_minus_spy_mom10 > 0

Action:
    modestly boost `trend_long` sizing on those dates only.
"""

from __future__ import annotations

import json
import os
import sys
from collections import OrderedDict

import pandas as pd


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
QUANT_DIR = os.path.join(REPO_ROOT, "quant")
if QUANT_DIR not in sys.path:
    sys.path.insert(0, QUANT_DIR)

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
import portfolio_engine as pe_module  # noqa: E402
from regime import compute_market_regime  # noqa: E402


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

OUT_JSON = os.path.join(REPO_ROOT, "data", "exp_20260424_005_results.json")

_state = {
    "today_str": None,
    "sim_dates": [],
    "sim_index": -1,
    "trend_multiplier": 1.0,
    "boost_days": set(),
    "boost_hits": 0,
    "trend_signals_boosted": 0,
}


def _load_snapshot(snapshot_relpath: str) -> dict:
    with open(os.path.join(REPO_ROOT, snapshot_relpath), "r", encoding="utf-8") as f:
        payload = json.load(f)
    out = {}
    for ticker, rows in payload["ohlcv"].items():
        df = pd.DataFrame(rows)
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date").sort_index()
        out[ticker] = df[["Open", "High", "Low", "Close", "Volume"]]
    return out


def _compute_boost_days(cfg: dict) -> tuple[set[str], list[str]]:
    ohlcv_all = _load_snapshot(cfg["snapshot"])
    sim_dates = ohlcv_all["SPY"].loc[cfg["start"]:cfg["end"]].index
    boost_days = []
    for today in sim_dates:
        regime_ohlcv = {}
        for ticker in ["SPY", "QQQ"]:
            if ticker in ohlcv_all:
                regime_ohlcv[ticker] = ohlcv_all[ticker].loc[:today]
        regime_result = compute_market_regime(ohlcv_override=regime_ohlcv)
        spy_10d = regime_result.get("indices", {}).get("SPY", {}).get("momentum_10d_pct") or 0
        qqq_10d = regime_result.get("indices", {}).get("QQQ", {}).get("momentum_10d_pct") or 0
        if (qqq_10d - spy_10d) > 0:
            boost_days.append(str(today.date()))
    return set(boost_days), [str(d.date()) for d in sim_dates]


def _patched_compute_portfolio_heat(open_positions, current_prices, portfolio_value, features_dict=None):
    _state["sim_index"] += 1
    idx = _state["sim_index"]
    if 0 <= idx < len(_state["sim_dates"]):
        _state["today_str"] = _state["sim_dates"][idx]
    return _original_compute_portfolio_heat(
        open_positions,
        current_prices,
        portfolio_value,
        features_dict=features_dict,
    )


def _patched_size_signals(signals, portfolio_value, risk_pct=None):
    today_str = _state.get("today_str")
    boost_days = _state.get("boost_days") or set()
    trend_multiplier = _state.get("trend_multiplier", 1.0)
    if not today_str or today_str not in boost_days or trend_multiplier == 1.0:
        return _original_size_signals(signals, portfolio_value, risk_pct=risk_pct)

    patched = []
    boosted = 0
    for sig in signals:
        sig2 = dict(sig)
        if sig2.get("strategy") == "trend_long":
            sig2["_qqq_spy_trend_boost_multiplier"] = trend_multiplier
            boosted += 1
        patched.append(sig2)

    sized = _original_size_signals(patched, portfolio_value, risk_pct=risk_pct)
    for sig in sized:
        mult = sig.pop("_qqq_spy_trend_boost_multiplier", None)
        if mult is None:
            continue
        sizing = sig.get("sizing")
        if not sizing:
            continue
        entry = sig.get("entry_price")
        stop = sig.get("stop_price")
        new_sizing = pe_module.compute_position_size(
            portfolio_value,
            entry,
            stop,
            risk_pct=sizing.get("risk_pct", 0.0) * mult,
        )
        if new_sizing:
            new_sizing["base_risk_pct"] = sizing.get("base_risk_pct", risk_pct)
            for key in [
                "trade_quality_score",
                "low_tqs_haircut_exempt_sector",
                "tqs_risk_multiplier_applied",
                "trend_industrials_risk_multiplier_applied",
                "trend_tech_gap_risk_multiplier_applied",
            ]:
                if key in sizing:
                    new_sizing[key] = sizing[key]
            new_sizing["qqq_spy_trend_boost_multiplier_applied"] = mult
            sig["sizing"] = new_sizing

    if boosted:
        _state["boost_hits"] += 1
        _state["trend_signals_boosted"] += boosted
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


def _run_window(universe: list[str], label: str, cfg: dict, trend_multiplier: float) -> dict:
    boost_days, sim_dates = _compute_boost_days(cfg)
    _state["today_str"] = None
    _state["sim_dates"] = sim_dates
    _state["sim_index"] = -1
    _state["trend_multiplier"] = trend_multiplier
    _state["boost_days"] = boost_days
    _state["boost_hits"] = 0
    _state["trend_signals_boosted"] = 0

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
        "trend_multiplier": trend_multiplier,
        "boost_days_available": len(boost_days),
        "boost_days_hit_during_sizing": _state["boost_hits"],
        "trend_signals_boosted": _state["trend_signals_boosted"],
        "expected_value_score": result.get("expected_value_score"),
        "sharpe_daily": result.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "total_return_pct": (result.get("benchmarks") or {}).get("strategy_total_return_pct"),
        "trade_count": result.get("total_trades"),
        "win_rate": result.get("win_rate"),
    }


def main() -> int:
    universe = get_universe()
    multipliers = [1.0, 1.25, 1.5]

    _install_patches()
    try:
        results = []
        for label, cfg in WINDOWS.items():
            for mult in multipliers:
                summary = _run_window(universe, label, cfg, mult)
                print(
                    f"[{label} trend_mult={mult}] "
                    f"EV={summary['expected_value_score']} "
                    f"ret={summary['total_return_pct']} "
                    f"sharpe_d={summary['sharpe_daily']} "
                    f"dd={summary['max_drawdown_pct']} "
                    f"trades={summary['trade_count']} "
                    f"boost_hits={summary['boost_days_hit_during_sizing']} "
                    f"trend_boosted={summary['trend_signals_boosted']}"
                )
                results.append(summary)
    finally:
        _remove_patches()

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {
                "rule": {
                    "name": "candidate_day_qqq_spy_trend_boost",
                    "definition": "qqq_minus_spy_mom10 > 0",
                    "action": "boost trend_long risk only on candidate days that meet the state",
                },
                "trend_multipliers_tested": multipliers,
                "results": results,
            },
            f,
            indent=2,
        )
    print(f"\nWrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
