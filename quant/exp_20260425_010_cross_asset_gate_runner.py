"""exp-20260425-010 cross-asset gated macro defensive sleeve.

Hypothesis:
    The macro sleeve needs a macro information source, not another stock-local
    gate. The observed audit found one candidate state that separated old_thin
    macro winners from late/mid macro losers:

        gold_risk_off_proxy AND NOT rates_positive

    This runner keeps macro entries unchanged and changes only the activation
    source. ETF proxies are included in the experiment universe only as sensors;
    A+B signals are still generated from the original trading universe.
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
from constants import ATR_STOP_MULT  # noqa: E402
from data_layer import get_universe  # noqa: E402
from risk_engine import SECTOR_MAP  # noqa: E402
import signal_engine as se_module  # noqa: E402


DEFENSIVE_SECTORS = {"Commodities", "Healthcare", "Energy"}
PROXY_TICKERS = {"GLD", "SLV", "SPY", "QQQ", "TLT", "IEF", "UUP", "USO", "XLE", "XLU", "XLP", "XLV"}
SENSOR_TICKERS = PROXY_TICKERS - {"GLD", "SLV", "SPY", "QQQ"}

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
    ("static_macro_reference", {"mode": "static_macro_reference"}),
    ("cross_asset_gate", {"mode": "cross_asset_gate"}),
])

OUT_JSON = os.path.join(REPO_ROOT, "data", "exp_20260425_010_results.json")

_state = {
    "mode": "baseline_ab",
    "base_universe": set(),
    "proxy_frames": {},
    "spy_close_to_date": {},
    "macro_candidates": 0,
    "macro_added": 0,
    "cross_asset_state_days": 0,
}


def _safe_float(value, default=0.0):
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _load_proxy_frames(snapshot_path: str):
    with open(snapshot_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    frames = {}
    for ticker in PROXY_TICKERS:
        rows = (payload.get("ohlcv") or {}).get(ticker)
        if not rows:
            continue
        df = pd.DataFrame(rows)
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date").sort_index()
        frames[ticker] = df
    spy_map = {}
    spy = frames.get("SPY")
    if spy is not None:
        for idx, row in spy.iterrows():
            close = float(row["Close"])
            spy_map[round(close, 4)] = pd.Timestamp(idx)
            spy_map[round(close, 2)] = pd.Timestamp(idx)
    return frames, spy_map


def _ret(df: pd.DataFrame, asof: pd.Timestamp, lookback: int):
    if df is None or df.empty:
        return None
    hist = df.loc[:asof]
    if len(hist) <= lookback:
        return None
    close = float(hist["Close"].iloc[-1])
    prev = float(hist["Close"].iloc[-lookback - 1])
    if prev <= 0:
        return None
    return (close - prev) / prev


def _infer_asof_from_features(features_dict):
    spy_features = features_dict.get("SPY") or {}
    close = spy_features.get("close")
    if close is None:
        return None
    return _state["spy_close_to_date"].get(round(float(close), 4))


def _cross_asset_gate(features_dict):
    asof = _infer_asof_from_features(features_dict)
    if asof is None:
        return False
    frames = _state["proxy_frames"]
    gld = _ret(frames.get("GLD"), asof, 20)
    spy = _ret(frames.get("SPY"), asof, 20)
    qqq = _ret(frames.get("QQQ"), asof, 20)
    tlt = _ret(frames.get("TLT"), asof, 20)
    ief = _ret(frames.get("IEF"), asof, 20)
    rates_values = [x for x in (tlt, ief) if x is not None]
    rates_avg = sum(rates_values) / len(rates_values) if rates_values else None
    if None in (gld, spy, qqq) or rates_avg is None:
        return False
    gold_risk_off = gld > spy and gld > qqq and min(spy, qqq) < 0
    rates_positive = rates_avg > 0
    return bool(gold_risk_off and not rates_positive)


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
        "entry_note": "Execute next-day open; cross-asset gated macro candidate",
        "conditions_met": {
            "sector": sector,
            "above_200ma": above_200,
            "momentum_10d_pct": momentum_10d,
            "rs_vs_spy": rel_strength,
            "trend_score": trend_score,
            "cross_asset_gate": True,
        },
    }


def _macro_candidates(features_dict, market_context):
    signals = []
    for ticker, features in features_dict.items():
        if ticker in SENSOR_TICKERS or not features:
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
    base_features = {
        ticker: features
        for ticker, features in features_dict.items()
        if ticker in _state["base_universe"]
    }
    base = _original_generate_signals(
        base_features,
        market_context=market_context,
        enabled_strategies=enabled_strategies,
        breakout_max_pullback_from_52w_high=breakout_max_pullback_from_52w_high,
    )
    mode = _state["mode"]
    if mode == "baseline_ab":
        return base

    if mode == "cross_asset_gate" and not _cross_asset_gate(features_dict):
        return base
    if mode == "cross_asset_gate":
        _state["cross_asset_state_days"] += 1

    macro = _macro_candidates(base_features, market_context)
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
    _state["cross_asset_state_days"] = 0
    _state["proxy_frames"], _state["spy_close_to_date"] = _load_proxy_frames(
        os.path.join(REPO_ROOT, cfg["snapshot"])
    )

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
        "cross_asset_state_days": _state["cross_asset_state_days"],
        "macro_trade_count": macro_attr.get("trade_count", 0),
        "macro_total_pnl": macro_attr.get("total_pnl_usd"),
        "macro_profit_factor": macro_attr.get("profit_factor"),
    }


def main() -> int:
    base_universe = set(get_universe())
    _state["base_universe"] = base_universe
    experiment_universe = sorted(base_universe | PROXY_TICKERS)
    _install_patches()
    try:
        results = []
        for label, cfg in WINDOWS.items():
            for variant_name, variant_cfg in VARIANTS.items():
                summary = _run_window(experiment_universe, label, cfg, variant_name, variant_cfg)
                print(
                    f"[{label} {variant_name}] "
                    f"EV={summary['expected_value_score']} "
                    f"ret={summary['total_return_pct']} "
                    f"sharpe_d={summary['sharpe_daily']} "
                    f"dd={summary['max_drawdown_pct']} "
                    f"trades={summary['trade_count']} "
                    f"macro_trades={summary['macro_trade_count']} "
                    f"macro_added={summary['macro_added']} "
                    f"state_days={summary['cross_asset_state_days']}"
                )
                results.append(summary)
    finally:
        _remove_patches()

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(
            {
                "rule": {
                    "name": "cross_asset_gated_macro_defensive",
                    "definition": (
                        "Same macro defensive entries as exp-20260425-005, gated by "
                        "20-day GLD risk-off leadership with non-positive TLT/IEF "
                        "rates basket return."
                    ),
                },
                "variants": VARIANTS,
                "sensor_tickers": sorted(PROXY_TICKERS),
                "base_universe": sorted(base_universe),
                "results": results,
            },
            f,
            indent=2,
        )
    print(f"\nWrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
