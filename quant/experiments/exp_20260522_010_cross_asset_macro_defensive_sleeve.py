"""exp-20260522-010: cross-asset gated macro defensive sleeve scout.

This experiment revisits the April macro defensive sleeve with new PIT
cross-asset proxy coverage now present in the canonical OHLCV snapshots. The
only tested causal variable is the sleeve activation state:

    stock pressure
    + precious metal leadership
    + defensive sector ETF leadership
    + non-positive rates ETF basket

The macro entry definition itself stays inherited from exp-20260425-005. Proxy
tickers are context-only; they are added to the backtest universe so features
exist, then removed before base signal generation unless they are already in the
production universe.
"""

from __future__ import annotations

import json
import math
import os
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


EXPERIMENT_ID = "exp-20260522-010"
EXPERIMENT_SLUG = "cross_asset_macro_defensive_sleeve"

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester as backtester_module  # noqa: E402
import signal_engine as signal_engine_module  # noqa: E402
from constants import ATR_STOP_MULT  # noqa: E402
from data_layer import get_universe  # noqa: E402
from risk_engine import SECTOR_MAP  # noqa: E402


DEFENSIVE_SECTORS = {"Commodities", "Healthcare", "Energy"}
PROXY_TICKERS = {
    "GLD",
    "SLV",
    "SPY",
    "QQQ",
    "TLT",
    "IEF",
    "UUP",
    "USO",
    "XLE",
    "XLU",
    "XLP",
    "XLV",
}
STATE_LOOKBACK_DAYS = 20
MAX_DRAWDOWN_WORSE_GUARDRAIL = 0.005
MAX_POSITIVE_MACRO_TICKER_SHARE = 0.55
MIN_MACRO_TRADES = 6
MIN_MACRO_TRADE_WINDOWS = 2

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
            },
        ),
    ]
)

VARIANTS = OrderedDict(
    [
        ("baseline_core", {"mode": "baseline_core"}),
        ("cross_asset_macro_gate", {"mode": "cross_asset_macro_gate"}),
    ]
)

EXPERIMENT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
RESULTS_PATH = EXPERIMENT_DIR / "results.json"
ARTIFACT_PATH = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
TICKET_PATH = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
RUN_LOG_PATH = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_PATH = REPO_ROOT / "docs" / "experiment_log.jsonl"

STATE: dict[str, Any] = {
    "mode": "baseline_core",
    "base_universe": set(),
    "proxy_frames": {},
    "spy_close_to_date": {},
    "macro_candidates": 0,
    "macro_added": 0,
    "state_true_days": 0,
    "state_observed_days": 0,
    "state_fail_reasons": {},
    "macro_signal_tickers": {},
    "last_state": None,
}

ORIGINAL_GENERATE_SIGNALS = None


def _safe_float(value: Any, default: float | None = 0.0) -> float | None:
    if value is None:
        return default
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(out):
        return default
    return out


def _pct(value: Any) -> float | None:
    return _safe_float(value, default=None)


def _load_proxy_frames(snapshot_path: Path) -> tuple[dict[str, pd.DataFrame], dict[float, pd.Timestamp]]:
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    frames: dict[str, pd.DataFrame] = {}
    for ticker in PROXY_TICKERS:
        rows = (payload.get("ohlcv") or {}).get(ticker)
        if not rows:
            continue
        df = pd.DataFrame(rows)
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date").sort_index()
        frames[ticker] = df

    spy_close_to_date: dict[float, pd.Timestamp] = {}
    spy = frames.get("SPY")
    if spy is not None:
        for idx, row in spy.iterrows():
            close = _safe_float(row.get("Close"), default=None)
            if close is None:
                continue
            spy_close_to_date[round(close, 4)] = pd.Timestamp(idx)
            spy_close_to_date[round(close, 2)] = pd.Timestamp(idx)
    return frames, spy_close_to_date


def _return_over(df: pd.DataFrame | None, asof: pd.Timestamp, lookback: int) -> float | None:
    if df is None or df.empty:
        return None
    hist = df.loc[:asof]
    if len(hist) <= lookback:
        return None
    close = _safe_float(hist["Close"].iloc[-1], default=None)
    prev = _safe_float(hist["Close"].iloc[-lookback - 1], default=None)
    if close is None or prev is None or prev <= 0:
        return None
    return (close - prev) / prev


def _avg(values: list[float | None]) -> float | None:
    clean = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    if not clean:
        return None
    return sum(clean) / len(clean)


def _infer_asof_from_features(features_dict: dict[str, dict[str, Any]]) -> pd.Timestamp | None:
    spy_features = features_dict.get("SPY") or {}
    close = _safe_float(spy_features.get("close"), default=None)
    if close is None:
        return None
    return STATE["spy_close_to_date"].get(round(close, 4)) or STATE["spy_close_to_date"].get(
        round(close, 2)
    )


def _record_state_fail(reason: str) -> None:
    counts = STATE["state_fail_reasons"]
    counts[reason] = int(counts.get(reason, 0)) + 1


def _cross_asset_macro_state(features_dict: dict[str, dict[str, Any]]) -> bool:
    asof = _infer_asof_from_features(features_dict)
    if asof is None:
        _record_state_fail("asof_missing")
        STATE["last_state"] = {"asof": None, "passed": False, "reason": "asof_missing"}
        return False

    frames: dict[str, pd.DataFrame] = STATE["proxy_frames"]
    returns = {
        ticker: _return_over(frames.get(ticker), asof, STATE_LOOKBACK_DAYS)
        for ticker in PROXY_TICKERS
    }
    equity_avg = _avg([returns.get("SPY"), returns.get("QQQ")])
    precious_avg = _avg([returns.get("GLD"), returns.get("SLV")])
    rates_avg = _avg([returns.get("TLT"), returns.get("IEF")])
    defensive_avg = _avg([returns.get("XLU"), returns.get("XLP"), returns.get("XLV")])

    required = {
        "equity_avg": equity_avg,
        "precious_avg": precious_avg,
        "rates_avg": rates_avg,
        "defensive_avg": defensive_avg,
        "spy": returns.get("SPY"),
        "qqq": returns.get("QQQ"),
    }
    missing = [key for key, value in required.items() if value is None]
    if missing:
        _record_state_fail("missing_" + "_".join(sorted(missing)))
        STATE["last_state"] = {
            "asof": str(asof.date()),
            "passed": False,
            "reason": "missing_inputs",
            "missing": missing,
            "returns": returns,
        }
        return False

    stock_pressure = min(float(returns["SPY"]), float(returns["QQQ"])) < 0.0
    precious_leadership = float(precious_avg) > float(equity_avg)
    defensive_leadership = float(defensive_avg) > float(equity_avg)
    rates_not_positive = float(rates_avg) <= 0.0
    passed = bool(
        stock_pressure
        and precious_leadership
        and defensive_leadership
        and rates_not_positive
    )
    if not stock_pressure:
        _record_state_fail("no_stock_pressure")
    elif not precious_leadership:
        _record_state_fail("no_precious_leadership")
    elif not defensive_leadership:
        _record_state_fail("no_defensive_leadership")
    elif not rates_not_positive:
        _record_state_fail("rates_positive")

    STATE["state_observed_days"] += 1
    STATE["last_state"] = {
        "asof": str(asof.date()),
        "passed": passed,
        "stock_pressure": stock_pressure,
        "precious_leadership": precious_leadership,
        "defensive_leadership": defensive_leadership,
        "rates_not_positive": rates_not_positive,
        "returns": {k: round(v, 6) if v is not None else None for k, v in returns.items()},
        "equity_avg": round(float(equity_avg), 6),
        "precious_avg": round(float(precious_avg), 6),
        "defensive_avg": round(float(defensive_avg), 6),
        "rates_avg": round(float(rates_avg), 6),
    }
    return passed


def _macro_defensive_signal(
    ticker: str,
    features: dict[str, Any],
    market_context: dict[str, Any] | None,
) -> dict[str, Any] | None:
    sector = SECTOR_MAP.get(ticker, "Unknown")
    if sector not in DEFENSIVE_SECTORS:
        return None

    close = _safe_float(features.get("close"), default=None)
    atr = _safe_float(features.get("atr"), default=None)
    if close is None or atr is None or close <= 0 or atr <= 0:
        return None

    market_context = market_context or {}
    above_200ma = bool(features.get("above_200ma"))
    momentum_10d = _safe_float(features.get("momentum_10d_pct"), default=0.0) or 0.0
    trend_score = _safe_float(features.get("trend_score"), default=0.0) or 0.0
    spy_10d = _safe_float(market_context.get("spy_10d_return"), default=0.0) or 0.0
    spy_pct = _pct(market_context.get("spy_pct_from_ma"))
    qqq_pct = _pct(market_context.get("qqq_pct_from_ma"))

    index_pressure = (
        (spy_pct is not None and spy_pct < 0)
        or (qqq_pct is not None and qqq_pct < 0)
        or market_context.get("market_regime") in {"NEUTRAL", "BEAR"}
    )
    if not index_pressure:
        return None
    if not above_200ma or momentum_10d <= 0:
        return None
    if momentum_10d <= spy_10d:
        return None
    if trend_score < 0.55:
        return None

    dte = features.get("days_to_earnings")
    if dte is not None and dte <= 3:
        return None

    rel_strength = round(momentum_10d - spy_10d, 4)
    confidence = signal_engine_module._confidence(
        [
            (above_200ma, 1.0),
            (momentum_10d > 0, 1.0),
            (rel_strength > 0, 1.0),
            (trend_score >= 0.65, 0.5),
            (sector == "Commodities", 0.25),
        ]
    )
    stop = round(close - ATR_STOP_MULT * atr, 2)

    return {
        "ticker": ticker,
        "strategy": "macro_defensive_long",
        "entry_price": round(close, 2),
        "stop_price": stop,
        "confidence_score": confidence,
        "entry_note": "Execute next-day open; cross-asset gated macro defensive candidate",
        "conditions_met": {
            "sector": sector,
            "above_200ma": above_200ma,
            "momentum_10d_pct": round(momentum_10d, 6),
            "rs_vs_spy": rel_strength,
            "trend_score": round(trend_score, 6),
            "cross_asset_macro_state": STATE.get("last_state"),
        },
    }


def _macro_candidates(
    features_dict: dict[str, dict[str, Any]],
    market_context: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    for ticker, features in features_dict.items():
        if not features:
            continue
        sig = _macro_defensive_signal(ticker, features, market_context)
        if sig:
            signals.append(sig)
            STATE["macro_signal_tickers"][ticker] = int(
                STATE["macro_signal_tickers"].get(ticker, 0)
            ) + 1
    return sorted(signals, key=lambda s: s.get("confidence_score", 0.0), reverse=True)


def _patched_generate_signals(
    features_dict: dict[str, dict[str, Any]],
    *args: Any,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    market_context = kwargs.get("market_context")
    base_features = {
        ticker: features
        for ticker, features in (features_dict or {}).items()
        if ticker in STATE["base_universe"]
    }
    base = ORIGINAL_GENERATE_SIGNALS(base_features, *args, **kwargs)
    if STATE["mode"] == "baseline_core":
        return base

    if not _cross_asset_macro_state(features_dict):
        return base
    STATE["state_true_days"] += 1

    macro = _macro_candidates(base_features, market_context)
    STATE["macro_candidates"] += len(macro)
    base_tickers = {s.get("ticker") for s in base}
    additions = [s for s in macro if s.get("ticker") not in base_tickers]
    STATE["macro_added"] += len(additions)
    return sorted(base + additions, key=lambda s: s.get("confidence_score", 0.0), reverse=True)


def _install_patch() -> None:
    global ORIGINAL_GENERATE_SIGNALS
    ORIGINAL_GENERATE_SIGNALS = signal_engine_module.generate_signals
    signal_engine_module.generate_signals = _patched_generate_signals
    if hasattr(backtester_module, "generate_signals"):
        backtester_module.generate_signals = _patched_generate_signals


def _remove_patch() -> None:
    if ORIGINAL_GENERATE_SIGNALS is not None:
        signal_engine_module.generate_signals = ORIGINAL_GENERATE_SIGNALS
        if hasattr(backtester_module, "generate_signals"):
            backtester_module.generate_signals = ORIGINAL_GENERATE_SIGNALS


def _reset_run_state(mode: str, snapshot_path: Path) -> None:
    STATE["mode"] = mode
    STATE["proxy_frames"], STATE["spy_close_to_date"] = _load_proxy_frames(snapshot_path)
    STATE["macro_candidates"] = 0
    STATE["macro_added"] = 0
    STATE["state_true_days"] = 0
    STATE["state_observed_days"] = 0
    STATE["state_fail_reasons"] = {}
    STATE["macro_signal_tickers"] = {}
    STATE["last_state"] = None


def _macro_trade_diagnostics(result: dict[str, Any]) -> dict[str, Any]:
    trades = result.get("trades") or []
    macro_trades = [t for t in trades if t.get("strategy") == "macro_defensive_long"]
    ticker_pnl: dict[str, float] = {}
    positive_ticker_pnl: dict[str, float] = {}
    worst_trade_pct = None
    for trade in macro_trades:
        ticker = str(trade.get("ticker") or "")
        pnl = _safe_float(trade.get("pnl"), default=0.0) or 0.0
        ticker_pnl[ticker] = ticker_pnl.get(ticker, 0.0) + pnl
        if pnl > 0:
            positive_ticker_pnl[ticker] = positive_ticker_pnl.get(ticker, 0.0) + pnl
        pnl_pct = _safe_float(trade.get("pnl_pct_net"), default=None)
        if pnl_pct is not None:
            worst_trade_pct = pnl_pct if worst_trade_pct is None else min(worst_trade_pct, pnl_pct)

    total_positive = sum(v for v in positive_ticker_pnl.values() if v > 0)
    max_positive_share = None
    if total_positive > 0:
        max_positive_share = max(positive_ticker_pnl.values()) / total_positive

    return {
        "macro_closed_trades": len(macro_trades),
        "macro_ticker_pnl": {k: round(v, 2) for k, v in sorted(ticker_pnl.items())},
        "macro_positive_ticker_pnl": {
            k: round(v, 2) for k, v in sorted(positive_ticker_pnl.items())
        },
        "macro_max_positive_ticker_share": (
            round(max_positive_share, 4) if max_positive_share is not None else None
        ),
        "macro_worst_trade_pct": (
            round(worst_trade_pct, 6) if worst_trade_pct is not None else None
        ),
    }


def _metric_summary(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": result.get("expected_value_score"),
        "strategy_total_return_pct": benchmarks.get("strategy_total_return_pct"),
        "sharpe_daily": result.get("sharpe_daily"),
        "max_drawdown_pct": result.get("max_drawdown_pct"),
        "total_pnl": result.get("total_pnl"),
        "total_trades": result.get("total_trades"),
        "win_rate": result.get("win_rate"),
        "signals_generated": result.get("signals_generated"),
        "signals_survived": result.get("signals_survived"),
        "survival_rate": result.get("survival_rate"),
        "worst_trade_pct": result.get("worst_trade_pct"),
        "max_consecutive_losses": result.get("max_consecutive_losses"),
        "tail_loss_share": result.get("tail_loss_share"),
    }


def _run_window(
    universe: list[str],
    window_name: str,
    window_cfg: dict[str, str],
    variant_name: str,
    variant_cfg: dict[str, str],
) -> dict[str, Any]:
    snapshot_path = REPO_ROOT / window_cfg["snapshot"]
    _reset_run_state(variant_cfg["mode"], snapshot_path)
    engine = backtester_module.BacktestEngine(
        universe=universe,
        start=window_cfg["start"],
        end=window_cfg["end"],
        config={"REGIME_AWARE_EXIT": True},
        replay_llm=False,
        replay_news=False,
        data_dir=str(REPO_ROOT / "data"),
        ohlcv_snapshot_path=str(snapshot_path),
    )
    result = engine.run()
    by_strategy = result.get("by_strategy") or {}
    macro_attr = by_strategy.get("macro_defensive_long") or {}
    output = {
        "window": window_name,
        "start": window_cfg["start"],
        "end": window_cfg["end"],
        "snapshot": window_cfg["snapshot"],
        "variant": variant_name,
        "error": result.get("error"),
        "metrics": _metric_summary(result),
        "macro_candidates": STATE["macro_candidates"],
        "macro_added": STATE["macro_added"],
        "state_observed_days": STATE["state_observed_days"],
        "state_true_days": STATE["state_true_days"],
        "state_fail_reasons": dict(sorted(STATE["state_fail_reasons"].items())),
        "macro_signal_tickers": dict(sorted(STATE["macro_signal_tickers"].items())),
        "macro_by_strategy": {
            "trade_count": macro_attr.get("trade_count", 0),
            "total_pnl_usd": macro_attr.get("total_pnl_usd"),
            "profit_factor": macro_attr.get("profit_factor"),
            "win_rate": macro_attr.get("win_rate"),
        },
        "macro_trade_diagnostics": _macro_trade_diagnostics(result),
    }
    return output


def _field_gate_audit() -> dict[str, Any]:
    path = REPO_ROOT / "operator_inputs" / "open_positions.json"
    if not path.exists():
        return {
            "path": str(path),
            "exists": False,
            "positions": 0,
            "missing_entry_date": [],
            "missing_target_price": [],
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    positions = payload.get("positions") if isinstance(payload, dict) else payload
    if positions is None:
        positions = []
    missing_entry_date = []
    missing_target_price = []
    for idx, pos in enumerate(positions):
        ticker = (pos or {}).get("ticker") or f"idx_{idx}"
        if not (pos or {}).get("entry_date"):
            missing_entry_date.append(ticker)
        if (pos or {}).get("target_price") in (None, ""):
            missing_target_price.append(ticker)
    return {
        "path": str(path),
        "exists": True,
        "positions": len(positions),
        "missing_entry_date": missing_entry_date,
        "missing_target_price": missing_target_price,
    }


def _sum_metric(rows: list[dict[str, Any]], key: str) -> float:
    total = 0.0
    for row in rows:
        value = _safe_float((row.get("metrics") or {}).get(key), default=0.0)
        total += value or 0.0
    return round(total, 6)


def _aggregate_analysis(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_variant: dict[str, list[dict[str, Any]]] = {}
    for row in results:
        by_variant.setdefault(row["variant"], []).append(row)
    baseline = by_variant.get("baseline_core", [])
    after = by_variant.get("cross_asset_macro_gate", [])
    rows_by_window = {
        row["window"]: row
        for row in baseline
    }
    after_by_window = {
        row["window"]: row
        for row in after
    }

    window_deltas = []
    ev_positive_windows = 0
    ev_regressed_windows = 0
    drawdown_worse_windows = 0
    max_drawdown_worse = 0.0
    min_survival_rate = None
    for window, base_row in rows_by_window.items():
        after_row = after_by_window.get(window)
        if not after_row:
            continue
        base_metrics = base_row.get("metrics") or {}
        after_metrics = after_row.get("metrics") or {}
        ev_delta = (_safe_float(after_metrics.get("expected_value_score"), 0.0) or 0.0) - (
            _safe_float(base_metrics.get("expected_value_score"), 0.0) or 0.0
        )
        pnl_delta = (_safe_float(after_metrics.get("total_pnl"), 0.0) or 0.0) - (
            _safe_float(base_metrics.get("total_pnl"), 0.0) or 0.0
        )
        dd_delta = (_safe_float(after_metrics.get("max_drawdown_pct"), 0.0) or 0.0) - (
            _safe_float(base_metrics.get("max_drawdown_pct"), 0.0) or 0.0
        )
        survival = _safe_float(after_metrics.get("survival_rate"), default=None)
        if survival is not None:
            min_survival_rate = survival if min_survival_rate is None else min(min_survival_rate, survival)
        if ev_delta > 0:
            ev_positive_windows += 1
        elif ev_delta < 0:
            ev_regressed_windows += 1
        if dd_delta > MAX_DRAWDOWN_WORSE_GUARDRAIL:
            drawdown_worse_windows += 1
        max_drawdown_worse = max(max_drawdown_worse, dd_delta)
        window_deltas.append(
            {
                "window": window,
                "expected_value_score_delta": round(ev_delta, 6),
                "total_pnl_delta": round(pnl_delta, 2),
                "max_drawdown_pct_delta": round(dd_delta, 6),
                "macro_trades": after_row.get("macro_trade_diagnostics", {}).get(
                    "macro_closed_trades", 0
                ),
                "state_true_days": after_row.get("state_true_days", 0),
                "survival_rate_after": survival,
            }
        )

    baseline_ev = _sum_metric(baseline, "expected_value_score")
    after_ev = _sum_metric(after, "expected_value_score")
    baseline_pnl = _sum_metric(baseline, "total_pnl")
    after_pnl = _sum_metric(after, "total_pnl")
    ev_delta = round(after_ev - baseline_ev, 6)
    ev_delta_pct = round(ev_delta / abs(baseline_ev), 6) if baseline_ev else None
    pnl_delta = round(after_pnl - baseline_pnl, 2)
    macro_trade_count = sum(
        int(row.get("macro_trade_diagnostics", {}).get("macro_closed_trades", 0) or 0)
        for row in after
    )
    macro_trade_windows = sum(
        1
        for row in after
        if int(row.get("macro_trade_diagnostics", {}).get("macro_closed_trades", 0) or 0) > 0
    )
    positive_shares = [
        row.get("macro_trade_diagnostics", {}).get("macro_max_positive_ticker_share")
        for row in after
        if row.get("macro_trade_diagnostics", {}).get("macro_max_positive_ticker_share")
        is not None
    ]
    max_positive_macro_ticker_share = max(positive_shares) if positive_shares else None

    gate_checks = {
        "aggregate_expected_value_score_improved": ev_delta > 0,
        "aggregate_total_pnl_improved": pnl_delta > 0,
        "at_least_two_windows_ev_improved": ev_positive_windows >= 2,
        "no_window_ev_regressed": ev_regressed_windows == 0,
        "drawdown_worse_within_guardrail": drawdown_worse_windows == 0,
        "survival_rate_above_5pct": (
            min_survival_rate is not None and min_survival_rate >= 0.05
        ),
        "enough_macro_trades": macro_trade_count >= MIN_MACRO_TRADES,
        "macro_trades_in_multiple_windows": macro_trade_windows >= MIN_MACRO_TRADE_WINDOWS,
        "macro_concentration_guardrail": (
            max_positive_macro_ticker_share is not None
            and max_positive_macro_ticker_share <= MAX_POSITIVE_MACRO_TICKER_SHARE
        ),
    }
    passed = all(gate_checks.values())
    if passed:
        decision = "positive_replay_only_not_promoted_without_shared_adapter"
        rejection_reason = None
    else:
        decision = "rejected"
        failed = [name for name, ok in gate_checks.items() if not ok]
        rejection_reason = "; ".join(failed)

    return {
        "baseline_aggregate": {
            "expected_value_score": baseline_ev,
            "total_pnl": baseline_pnl,
        },
        "after_aggregate": {
            "expected_value_score": after_ev,
            "total_pnl": after_pnl,
        },
        "expected_value_score_delta": ev_delta,
        "expected_value_score_delta_pct": ev_delta_pct,
        "total_pnl_delta": pnl_delta,
        "window_deltas": window_deltas,
        "ev_positive_windows": ev_positive_windows,
        "ev_regressed_windows": ev_regressed_windows,
        "max_drawdown_worse": round(max_drawdown_worse, 6),
        "min_survival_rate_after": min_survival_rate,
        "macro_trade_count": macro_trade_count,
        "macro_trade_windows": macro_trade_windows,
        "max_positive_macro_ticker_share": max_positive_macro_ticker_share,
        "gate_checks": gate_checks,
        "decision": decision,
        "rejection_reason": rejection_reason,
    }


def _format_number(value: Any, digits: int = 4) -> str:
    if value is None:
        return "None"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def _markdown_report(payload: dict[str, Any]) -> str:
    analysis = payload["analysis"]
    lines = [
        f"# {EXPERIMENT_ID} {EXPERIMENT_SLUG}",
        "",
        "## Hypothesis",
        (
            "A defensive macro sleeve should only compete for slots when a "
            "cross-asset risk-off state is visible: stock pressure, precious "
            "metal leadership, defensive sector ETF leadership, and a "
            "non-positive TLT/IEF rates basket."
        ),
        "",
        "## Trial Accounting",
        f"- trial_family: {payload['trial_accounting']['trial_family']}",
        f"- changed_variable: {payload['trial_accounting']['changed_variable']}",
        f"- prior_trial_count: {payload['trial_accounting']['prior_trial_count']}",
        (
            "- nearby_prior_experiments: "
            + ", ".join(payload["trial_accounting"]["nearby_prior_experiments"])
        ),
        f"- multiple_testing_risk_bucket: {payload['trial_accounting']['multiple_testing_risk_bucket']}",
        f"- new_evidence_type: {payload['trial_accounting']['new_evidence_type']}",
        "",
        "## Three-Window Results",
        (
            "| window | baseline EV | after EV | EV delta | baseline PnL | "
            "after PnL | PnL delta | macro trades | state days |"
        ),
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    baseline_by_window = {
        row["window"]: row for row in payload["results"] if row["variant"] == "baseline_core"
    }
    after_by_window = {
        row["window"]: row
        for row in payload["results"]
        if row["variant"] == "cross_asset_macro_gate"
    }
    for delta in analysis["window_deltas"]:
        window = delta["window"]
        base = baseline_by_window[window]["metrics"]
        after = after_by_window[window]["metrics"]
        lines.append(
            "| {window} | {bev} | {aev} | {dev} | {bpnl} | {apnl} | {dpnl} | {trades} | {days} |".format(
                window=window,
                bev=_format_number(base.get("expected_value_score")),
                aev=_format_number(after.get("expected_value_score")),
                dev=_format_number(delta.get("expected_value_score_delta")),
                bpnl=_format_number(base.get("total_pnl"), 2),
                apnl=_format_number(after.get("total_pnl"), 2),
                dpnl=_format_number(delta.get("total_pnl_delta"), 2),
                trades=delta.get("macro_trades"),
                days=delta.get("state_true_days"),
            )
        )

    lines.extend(
        [
            "",
            "## Aggregate",
            f"- baseline_expected_value_score: {_format_number(analysis['baseline_aggregate']['expected_value_score'])}",
            f"- after_expected_value_score: {_format_number(analysis['after_aggregate']['expected_value_score'])}",
            f"- expected_value_score_delta: {_format_number(analysis['expected_value_score_delta'])}",
            f"- expected_value_score_delta_pct: {_format_number(analysis['expected_value_score_delta_pct'], 6)}",
            f"- total_pnl_delta: {_format_number(analysis['total_pnl_delta'], 2)}",
            f"- macro_trade_count: {analysis['macro_trade_count']}",
            f"- macro_trade_windows: {analysis['macro_trade_windows']}",
            "",
            "## Gate Checks",
        ]
    )
    for name, ok in analysis["gate_checks"].items():
        lines.append(f"- {name}: {ok}")
    lines.extend(
        [
            "",
            "## Decision",
            f"- decision: {analysis['decision']}",
            f"- rejection_reason: {analysis['rejection_reason']}",
            "",
            "## Production Impact",
            "- shared_policy_changed: false",
            "- backtester_adapter_changed: false",
            "- run_adapter_changed: false",
            "- replay_only: true",
            "- parity_test_added: false",
        ]
    )
    return "\n".join(lines) + "\n"


def _experiment_log_entry(payload: dict[str, Any]) -> dict[str, Any]:
    analysis = payload["analysis"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp_utc": payload["timestamp_utc"],
        "hypothesis": payload["hypothesis"],
        "change_type": "alpha_search",
        "changed_variable": payload["trial_accounting"]["changed_variable"],
        "trial_family": payload["trial_accounting"]["trial_family"],
        "trial_accounting": payload["trial_accounting"],
        "parameters": {
            "state_lookback_days": STATE_LOOKBACK_DAYS,
            "activation_state": [
                "min(SPY_20d, QQQ_20d) < 0",
                "avg(GLD_20d, SLV_20d) > avg(SPY_20d, QQQ_20d)",
                "avg(XLU_20d, XLP_20d, XLV_20d) > avg(SPY_20d, QQQ_20d)",
                "avg(TLT_20d, IEF_20d) <= 0",
            ],
            "macro_entry_definition": "exp-20260425-005 unchanged macro_defensive_long",
            "guardrails": {
                "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE_GUARDRAIL,
                "max_positive_macro_ticker_share": MAX_POSITIVE_MACRO_TICKER_SHARE,
                "min_macro_trades": MIN_MACRO_TRADES,
                "min_macro_trade_windows": MIN_MACRO_TRADE_WINDOWS,
            },
        },
        "date_range": WINDOWS,
        "backtest_protocol": "docs/backtesting.md standard 3 non-overlapping half-year windows, OHLCV snapshots, REGIME_AWARE_EXIT=true, replay_llm=false, replay_news=false",
        "before_metrics": analysis["baseline_aggregate"],
        "after_metrics": analysis["after_aggregate"],
        "expected_value_score_delta": analysis["expected_value_score_delta"],
        "expected_value_score_delta_pct": analysis["expected_value_score_delta_pct"],
        "window_deltas": analysis["window_deltas"],
        "risk_distribution": {
            "max_drawdown_worse": analysis["max_drawdown_worse"],
            "min_survival_rate_after": analysis["min_survival_rate_after"],
            "max_positive_macro_ticker_share": analysis["max_positive_macro_ticker_share"],
        },
        "decision": analysis["decision"],
        "rejection_reason": analysis["rejection_reason"],
        "next_evidence_needed": (
            "Do not promote this replay-only sleeve unless a shared production/backtest "
            "adapter is implemented and a future PIT run improves aggregate EV without "
            "window regression or macro concentration."
        ),
        "artifacts": {
            "results": str(RESULTS_PATH.relative_to(REPO_ROOT)),
            "artifact": str(ARTIFACT_PATH.relative_to(REPO_ROOT)),
            "ticket": str(TICKET_PATH.relative_to(REPO_ROOT)),
            "run_log": str(RUN_LOG_PATH.relative_to(REPO_ROOT)),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
        },
    }


def _write_outputs(payload: dict[str, Any]) -> None:
    for path in [EXPERIMENT_DIR, ARTIFACT_PATH.parent, TICKET_PATH.parent, RUN_LOG_PATH.parent]:
        path.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ARTIFACT_PATH.write_text(_markdown_report(payload), encoding="utf-8")
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Cross-asset macro defensive sleeve scout",
        "decision": payload["analysis"]["decision"],
        "summary": payload["analysis"]["rejection_reason"]
        or "Positive replay-only result requires shared adapter before promotion.",
        "artifact": str(ARTIFACT_PATH.relative_to(REPO_ROOT)),
        "results": str(RESULTS_PATH.relative_to(REPO_ROOT)),
    }
    TICKET_PATH.write_text(json.dumps(ticket, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    RUN_LOG_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    entry = _experiment_log_entry(payload)
    with EXPERIMENT_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")


def main() -> int:
    timestamp_utc = datetime.now(timezone.utc).isoformat()
    field_gate = _field_gate_audit()
    if field_gate["missing_entry_date"] or field_gate["missing_target_price"]:
        raise RuntimeError(f"Gate 2 failed: {field_gate}")

    base_universe = set(get_universe())
    STATE["base_universe"] = base_universe
    experiment_universe = sorted(base_universe | PROXY_TICKERS)
    sensor_coverage = {}
    for window_name, cfg in WINDOWS.items():
        frames, _ = _load_proxy_frames(REPO_ROOT / cfg["snapshot"])
        sensor_coverage[window_name] = {
            ticker: ticker in frames for ticker in sorted(PROXY_TICKERS)
        }

    results: list[dict[str, Any]] = []
    _install_patch()
    try:
        for window_name, cfg in WINDOWS.items():
            for variant_name, variant_cfg in VARIANTS.items():
                row = _run_window(experiment_universe, window_name, cfg, variant_name, variant_cfg)
                results.append(row)
                metrics = row.get("metrics") or {}
                print(
                    "[{window} {variant}] EV={ev} PnL={pnl} DD={dd} "
                    "trades={trades} survival={survival} macro_trades={macro_trades} "
                    "macro_added={macro_added} state_days={state_days}".format(
                        window=window_name,
                        variant=variant_name,
                        ev=metrics.get("expected_value_score"),
                        pnl=metrics.get("total_pnl"),
                        dd=metrics.get("max_drawdown_pct"),
                        trades=metrics.get("total_trades"),
                        survival=metrics.get("survival_rate"),
                        macro_trades=row.get("macro_trade_diagnostics", {}).get(
                            "macro_closed_trades"
                        ),
                        macro_added=row.get("macro_added"),
                        state_days=row.get("state_true_days"),
                    )
                )
    finally:
        _remove_patch()

    analysis = _aggregate_analysis(results)
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp_utc": timestamp_utc,
        "hypothesis": (
            "A macro defensive sleeve should improve expected value only when "
            "activated by a PIT cross-asset risk-off state using now-available "
            "rates and defensive-sector ETF proxies."
        ),
        "alpha_hypothesis_category": "candidate_pool",
        "trial_accounting": {
            "trial_family": "cross_asset_macro_defensive_sleeve_activation",
            "changed_variable": "macro_defensive_long_activation_state",
            "prior_trial_count": 4,
            "nearby_prior_experiments": [
                "exp-20260425-005",
                "exp-20260425-008",
                "exp-20260425-010",
                "exp-20260515-017",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "new_pit_universe_proxy_ohlcv_rows",
        },
        "field_gate": field_gate,
        "sensor_coverage": sensor_coverage,
        "windows": WINDOWS,
        "variants": VARIANTS,
        "base_universe_count": len(base_universe),
        "experiment_universe_count": len(experiment_universe),
        "results": results,
        "analysis": analysis,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
        },
    }
    _write_outputs(payload)
    print(json.dumps(analysis, indent=2, sort_keys=True))
    print(f"Wrote {RESULTS_PATH}")
    print(f"Wrote {ARTIFACT_PATH}")
    print(f"Appended {EXPERIMENT_LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
