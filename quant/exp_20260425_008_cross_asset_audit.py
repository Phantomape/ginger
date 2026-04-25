"""exp-20260425-008 cross-asset macro state audit.

This is a read-only alpha audit. It does not change production strategy code.

Question:
    The defensive-stock macro sleeve failed under entry/gate/overlay variants.
    Before adding more strategy rules, check whether already available
    cross-asset proxies (GLD/SLV vs SPY/QQQ) explain which macro trades worked.
"""

from __future__ import annotations

import json
import os
import sys
from collections import OrderedDict, defaultdict

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
DESIRED_PROXIES = ["GLD", "SLV", "TLT", "IEF", "UUP", "USO", "XLE", "XLU", "XLP", "XLV", "SPY", "QQQ"]
AVAILABLE_PROXY_SET = set(DESIRED_PROXIES)

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

OUT_JSON = os.path.join(REPO_ROOT, "data", "exp_20260425_008_cross_asset_audit.json")

_state = {
    "macro_candidates": 0,
    "macro_added": 0,
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
        "entry_note": "Execute next-day open; cross-asset audit macro candidate",
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
    macro = _macro_candidates(features_dict, market_context)
    _state["macro_candidates"] += len(macro)
    base_tickers = {s.get("ticker") for s in base}
    additions = [s for s in macro if s.get("ticker") not in base_tickers]
    _state["macro_added"] += len(additions)
    return sorted(base + additions, key=lambda s: s.get("confidence_score", 0), reverse=True)


def _load_proxy_frames(snapshot_path: str):
    with open(snapshot_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    ohlcv = payload.get("ohlcv") or {}
    frames = {}
    for ticker in AVAILABLE_PROXY_SET:
        rows = ohlcv.get(ticker)
        if not rows:
            continue
        df = pd.DataFrame(rows)
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date").sort_index()
        frames[ticker] = df
    return frames, sorted(set(DESIRED_PROXIES) - set(ohlcv.keys())), sorted(set(DESIRED_PROXIES) & set(ohlcv.keys()))


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
    return round((close - prev) / prev, 4)


def _cross_asset_state(frames: dict, asof_date: str):
    asof = pd.Timestamp(asof_date)
    r20 = {ticker: _ret(frames.get(ticker), asof, 20) for ticker in AVAILABLE_PROXY_SET}
    gld = r20.get("GLD")
    slv = r20.get("SLV")
    spy = r20.get("SPY")
    qqq = r20.get("QQQ")
    precious_values = [x for x in (gld, slv) if x is not None]
    precious_avg = round(sum(precious_values) / len(precious_values), 4) if precious_values else None
    defensive_values = [r20.get(t) for t in ("XLU", "XLP", "XLV") if r20.get(t) is not None]
    defensive_avg = round(sum(defensive_values) / len(defensive_values), 4) if defensive_values else None
    rates_values = [r20.get(t) for t in ("TLT", "IEF") if r20.get(t) is not None]
    rates_avg = round(sum(rates_values) / len(rates_values), 4) if rates_values else None
    xle = r20.get("XLE")
    uso = r20.get("USO")
    uup = r20.get("UUP")
    return {
        "returns_20d": r20,
        "precious_avg_20d": precious_avg,
        "defensive_avg_20d": defensive_avg,
        "rates_avg_20d": rates_avg,
        "gold_leads_spy": bool(gld is not None and spy is not None and gld > spy),
        "gold_leads_qqq": bool(gld is not None and qqq is not None and gld > qqq),
        "silver_leads_spy": bool(slv is not None and spy is not None and slv > spy),
        "precious_leads_spy": bool(precious_avg is not None and spy is not None and precious_avg > spy),
        "precious_leads_qqq": bool(precious_avg is not None and qqq is not None and precious_avg > qqq),
        "rates_positive": bool(rates_avg is not None and rates_avg > 0),
        "rates_lead_spy": bool(rates_avg is not None and spy is not None and rates_avg > spy),
        "dollar_positive": bool(uup is not None and uup > 0),
        "dollar_not_strong": bool(uup is not None and uup < 0.02),
        "energy_leads_spy": bool(xle is not None and spy is not None and xle > spy),
        "oil_leads_spy": bool(uso is not None and spy is not None and uso > spy),
        "defensive_leads_qqq": bool(defensive_avg is not None and qqq is not None and defensive_avg > qqq),
        "defensive_leads_spy": bool(defensive_avg is not None and spy is not None and defensive_avg > spy),
        "stock_pressure_20d": bool(spy is not None and qqq is not None and min(spy, qqq) < 0),
        "gold_risk_off_proxy": bool(gld is not None and spy is not None and qqq is not None and gld > spy and gld > qqq and min(spy, qqq) < 0),
        "precious_risk_off_proxy": bool(precious_avg is not None and spy is not None and qqq is not None and precious_avg > spy and precious_avg > qqq and min(spy, qqq) < 0),
        "cross_asset_risk_off_v2": bool(
            gld is not None
            and rates_avg is not None
            and spy is not None
            and qqq is not None
            and uup is not None
            and gld > spy
            and rates_avg > 0
            and uup < 0.02
            and min(spy, qqq) < 0
        ),
        "commodity_inflation_proxy": bool(
            xle is not None
            and uso is not None
            and spy is not None
            and xle > spy
            and uso > spy
            and (uup is None or uup < 0.03)
        ),
    }


def _summarize_group(trades):
    total = len(trades)
    pnl = sum(t.get("pnl", 0) for t in trades)
    wins = sum(1 for t in trades if t.get("pnl", 0) > 0)
    losses = [abs(t.get("pnl", 0)) for t in trades if t.get("pnl", 0) < 0]
    gains = [t.get("pnl", 0) for t in trades if t.get("pnl", 0) > 0]
    return {
        "trade_count": total,
        "win_rate": round(wins / total, 4) if total else None,
        "total_pnl": round(pnl, 2),
        "avg_pnl": round(pnl / total, 2) if total else None,
        "profit_factor": round(sum(gains) / sum(losses), 3) if losses else (None if not gains else 999.0),
    }


def _run_window(universe, label, cfg):
    _state["macro_candidates"] = 0
    _state["macro_added"] = 0
    frames, missing_proxies, present_proxies = _load_proxy_frames(os.path.join(REPO_ROOT, cfg["snapshot"]))

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
    macro_trades = [t for t in result.get("trades", []) if t.get("strategy") == "macro_defensive_long"]
    annotated = []
    for trade in macro_trades:
        state = _cross_asset_state(frames, trade.get("entry_date"))
        annotated.append({
            "ticker": trade.get("ticker"),
            "entry_date": trade.get("entry_date"),
            "exit_date": trade.get("exit_date"),
            "pnl": trade.get("pnl"),
            "pnl_pct_net": trade.get("pnl_pct_net"),
            "exit_reason": trade.get("exit_reason"),
            "cross_asset_state": state,
        })

    grouped = {}
    for key in [
        "gold_leads_spy",
        "gold_leads_qqq",
        "precious_leads_spy",
        "precious_leads_qqq",
        "rates_positive",
        "rates_lead_spy",
        "dollar_positive",
        "dollar_not_strong",
        "energy_leads_spy",
        "oil_leads_spy",
        "defensive_leads_qqq",
        "defensive_leads_spy",
        "stock_pressure_20d",
        "gold_risk_off_proxy",
        "precious_risk_off_proxy",
        "cross_asset_risk_off_v2",
        "commodity_inflation_proxy",
    ]:
        grouped[key] = {
            "true": _summarize_group([t for t in annotated if t["cross_asset_state"].get(key)]),
            "false": _summarize_group([t for t in annotated if not t["cross_asset_state"].get(key)]),
        }

    return {
        "window": label,
        "start": cfg["start"],
        "end": cfg["end"],
        "snapshot": cfg["snapshot"],
        "present_proxies": present_proxies,
        "missing_proxies": missing_proxies,
        "macro_candidates": _state["macro_candidates"],
        "macro_added": _state["macro_added"],
        "macro_trade_summary": _summarize_group(annotated),
        "grouped_by_cross_asset_state": grouped,
        "macro_trades": annotated,
        "baseline_metrics_with_static_macro": {
            "expected_value_score": result.get("expected_value_score"),
            "sharpe_daily": result.get("sharpe_daily"),
            "total_return_pct": (result.get("benchmarks") or {}).get("strategy_total_return_pct"),
            "max_drawdown_pct": result.get("max_drawdown_pct"),
            "trade_count": result.get("total_trades"),
            "win_rate": result.get("win_rate"),
        },
    }


def _install_patches():
    global _original_generate_signals
    _original_generate_signals = se_module.generate_signals
    se_module.generate_signals = _patched_generate_signals


def _remove_patches():
    se_module.generate_signals = _original_generate_signals


def main() -> int:
    universe = get_universe()
    _install_patches()
    try:
        windows = []
        for label, cfg in WINDOWS.items():
            summary = _run_window(universe, label, cfg)
            windows.append(summary)
            macro = summary["macro_trade_summary"]
            print(
                f"[{label}] macro_trades={macro['trade_count']} "
                f"pnl={macro['total_pnl']} pf={macro['profit_factor']} "
                f"present={summary['present_proxies']} missing={summary['missing_proxies']}"
            )
    finally:
        _remove_patches()

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "experiment_id": "exp-20260425-008",
            "rule": {
                "name": "cross_asset_macro_state_audit",
                "definition": "Annotate static macro defensive trades with available GLD/SLV vs SPY/QQQ 20-day cross-asset states.",
            },
            "desired_proxies": DESIRED_PROXIES,
            "available_proxy_set_used": sorted(AVAILABLE_PROXY_SET),
            "windows": windows,
        }, f, indent=2)
    print(f"\nWrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
