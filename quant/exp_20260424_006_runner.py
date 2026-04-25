"""exp-20260424-006 candidate-day OMDB -> explicit two-sided sleeve routing.

Tests the doctrine-authorized follow-up to the rejected one-way trend boosts:
keep the same replayable healthy-tape proxy

    offense_minus_defense_breadth >= 0.15

but change the action family from "trend gets more risk" to an explicit
cross-sleeve routing rule:

    - reduce `breakout_long` risk on those candidate days
    - reallocate that budget toward `trend_long`

Entries, exits, ranking, and all accepted A+B cohort rules stay unchanged.
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
from feature_layer import compute_features  # noqa: E402
import portfolio_engine as pe_module  # noqa: E402
from risk_engine import SECTOR_MAP  # noqa: E402


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

OUT_JSON = os.path.join(REPO_ROOT, "data", "exp_20260424_006_results.json")

OFFENSE_SECTORS = {
    "Technology",
    "Communication Services",
    "Consumer Discretionary",
    "Industrials",
    "Financials",
}
DEFENSE_SECTORS = {
    "Commodities",
    "Healthcare",
    "Energy",
    "Consumer Staples",
    "Utilities",
}
OMDB_THRESHOLD = 0.15

VARIANTS = OrderedDict([
    ("rot_bk025_tr125", {"breakout_multiplier": 0.25, "trend_multiplier": 1.25}),
    ("rot_bk000_tr125", {"breakout_multiplier": 0.0,  "trend_multiplier": 1.25}),
    ("rot_bk025_tr150", {"breakout_multiplier": 0.25, "trend_multiplier": 1.5}),
])

_state = {
    "today_str": None,
    "sim_dates": [],
    "sim_index": -1,
    "trigger_days": set(),
    "variant_name": "baseline",
    "breakout_multiplier": 1.0,
    "trend_multiplier": 1.0,
    "trigger_hits": 0,
    "trend_signals_boosted": 0,
    "breakout_signals_haircut": 0,
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


def _compute_trigger_days(cfg: dict) -> tuple[set[str], list[str]]:
    ohlcv_all = _load_snapshot(cfg["snapshot"])
    sim_dates = ohlcv_all["SPY"].loc[cfg["start"]:cfg["end"]].index
    trigger_days = []
    for today in sim_dates:
        offense_total = defense_total = 0
        offense_pos = defense_pos = 0
        for ticker, df in ohlcv_all.items():
            feat = compute_features(ticker, df.loc[:today], {})
            if feat is None:
                continue
            sector = SECTOR_MAP.get(ticker, "Unknown")
            momentum = feat.get("momentum_10d_pct")
            if sector in OFFENSE_SECTORS:
                offense_total += 1
                if momentum is not None and momentum > 0:
                    offense_pos += 1
            elif sector in DEFENSE_SECTORS:
                defense_total += 1
                if momentum is not None and momentum > 0:
                    defense_pos += 1
        if offense_total and defense_total:
            omdb = offense_pos / offense_total - defense_pos / defense_total
            if omdb >= OMDB_THRESHOLD:
                trigger_days.append(str(today.date()))
    return set(trigger_days), [str(d.date()) for d in sim_dates]


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


def _copy_sizing_metadata(old_sizing: dict, new_sizing: dict, base_risk_pct):
    new_sizing["base_risk_pct"] = old_sizing.get("base_risk_pct", base_risk_pct)
    for key in [
        "trade_quality_score",
        "low_tqs_haircut_exempt_sector",
        "tqs_risk_multiplier_applied",
        "trend_industrials_risk_multiplier_applied",
        "trend_tech_gap_risk_multiplier_applied",
        "earnings_gap_risk_applied",
        "gap_risk_pct",
        "effective_stop_for_sizing",
    ]:
        if key in old_sizing:
            new_sizing[key] = old_sizing[key]


def _patched_size_signals(signals, portfolio_value, risk_pct=None):
    today_str = _state.get("today_str")
    trigger_days = _state.get("trigger_days") or set()
    if not today_str or today_str not in trigger_days:
        return _original_size_signals(signals, portfolio_value, risk_pct=risk_pct)

    breakout_multiplier = _state.get("breakout_multiplier", 1.0)
    trend_multiplier = _state.get("trend_multiplier", 1.0)
    patched = []
    breakout_seen = 0
    trend_seen = 0

    for sig in signals:
        sig2 = dict(sig)
        strategy = sig2.get("strategy")
        if strategy == "breakout_long":
            sig2["_rotation_multiplier"] = breakout_multiplier
            breakout_seen += 1
        elif strategy == "trend_long":
            sig2["_rotation_multiplier"] = trend_multiplier
            trend_seen += 1
        patched.append(sig2)

    sized = _original_size_signals(patched, portfolio_value, risk_pct=risk_pct)
    adjusted_any = False
    for sig in sized:
        mult = sig.pop("_rotation_multiplier", None)
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
            _copy_sizing_metadata(sizing, new_sizing, risk_pct)
            strategy = sig.get("strategy")
            if strategy == "breakout_long":
                new_sizing["omdb_rotation_breakout_multiplier_applied"] = mult
            elif strategy == "trend_long":
                new_sizing["omdb_rotation_trend_multiplier_applied"] = mult
            sig["sizing"] = new_sizing
            adjusted_any = True

    if adjusted_any:
        _state["trigger_hits"] += 1
        _state["trend_signals_boosted"] += trend_seen
        _state["breakout_signals_haircut"] += breakout_seen
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


def _run_window(universe: list[str], label: str, cfg: dict, variant_name: str, variant_cfg: dict) -> dict:
    trigger_days, sim_dates = _compute_trigger_days(cfg)
    _state["today_str"] = None
    _state["sim_dates"] = sim_dates
    _state["sim_index"] = -1
    _state["trigger_days"] = trigger_days
    _state["variant_name"] = variant_name
    _state["breakout_multiplier"] = variant_cfg["breakout_multiplier"]
    _state["trend_multiplier"] = variant_cfg["trend_multiplier"]
    _state["trigger_hits"] = 0
    _state["trend_signals_boosted"] = 0
    _state["breakout_signals_haircut"] = 0

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
        "breakout_multiplier": variant_cfg["breakout_multiplier"],
        "trend_multiplier": variant_cfg["trend_multiplier"],
        "trigger_days_available": len(trigger_days),
        "trigger_days_hit_during_sizing": _state["trigger_hits"],
        "trend_signals_boosted": _state["trend_signals_boosted"],
        "breakout_signals_haircut": _state["breakout_signals_haircut"],
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
            baseline_cfg = {"breakout_multiplier": 1.0, "trend_multiplier": 1.0}
            baseline = _run_window(universe, label, cfg, "baseline", baseline_cfg)
            print(
                f"[{label} baseline] "
                f"EV={baseline['expected_value_score']} "
                f"ret={baseline['total_return_pct']} "
                f"sharpe_d={baseline['sharpe_daily']} "
                f"dd={baseline['max_drawdown_pct']} "
                f"trades={baseline['trade_count']} "
                f"trigger_hits={baseline['trigger_days_hit_during_sizing']}"
            )
            results.append(baseline)
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
                    f"trend_boosted={summary['trend_signals_boosted']} "
                    f"breakout_haircut={summary['breakout_signals_haircut']}"
                )
                results.append(summary)
    finally:
        _remove_patches()

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {
                "rule": {
                    "name": "candidate_day_omdb_two_sided_rotation",
                    "definition": "offense_minus_defense_breadth >= 0.15",
                    "action": "on candidate days, de-risk breakout_long and re-route risk budget toward trend_long",
                },
                "offense_sectors": sorted(OFFENSE_SECTORS),
                "defense_sectors": sorted(DEFENSE_SECTORS),
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
