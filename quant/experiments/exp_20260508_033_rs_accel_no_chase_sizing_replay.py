"""exp-20260508-033: RS acceleration no-chase sizing replay.

This is an alpha-search replay experiment. It tests one causal variable:
increasing risk budget for existing A/B signals whose 20-day relative strength
versus SPY is positive, accelerating versus the prior 20-day window, and not
chasing a 3% signal-day gap.

The experiment is default-off and does not alter production behavior. If a
variant passes the fixed-window gate, the policy still needs a shared
production/backtest implementation before promotion.
"""

from __future__ import annotations

import json
import logging
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

import backtester  # noqa: E402
from backtester import BacktestEngine  # noqa: E402
from constants import MAX_POSITION_PCT  # noqa: E402
from data_layer import get_universe  # noqa: E402
import feature_layer  # noqa: E402
import portfolio_engine  # noqa: E402
import risk_engine  # noqa: E402


EXPERIMENT_ID = "exp-20260508-033"
STEM = "rs_accel_no_chase_sizing_replay"
CORE_STRATEGIES = {"trend_long", "breakout_long"}
GAP_CHASE_MAX = 0.03
MULTIPLIER_KEY = "rs_accel_no_chase_risk_multiplier_applied"

OUT_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / EXPERIMENT_ID
    / f"{EXPERIMENT_ID}_{STEM}.json"
)

WINDOWS = OrderedDict(
    [
        (
            "late_strong",
            {
                "start": "2025-10-23",
                "end": "2026-04-21",
                "snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
                "regime_note": "strong late accepted-stack tape",
            },
        ),
        (
            "mid_weak",
            {
                "start": "2025-04-23",
                "end": "2025-10-22",
                "snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
                "regime_note": "rotation-heavy weaker validation tape",
            },
        ),
        (
            "old_thin",
            {
                "start": "2024-10-02",
                "end": "2025-04-22",
                "snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
                "regime_note": "older thin mixed-to-weak tape",
            },
        ),
    ]
)

# Gate-1 current-worktree baseline measured before this experiment with the
# canonical docs/backtesting.md command shape.
BASELINE = {
    "late_strong": {
        "expected_value_score": 4.0674,
        "sharpe_daily": 4.48,
        "sharpe": 6.57,
        "max_drawdown_pct": 0.0539,
        "total_pnl": 90788.88,
        "total_return_pct": 0.9079,
        "win_rate": 0.7895,
        "total_trades": 19,
        "survival_rate": 0.8039,
    },
    "mid_weak": {
        "expected_value_score": 1.6195,
        "sharpe_daily": 2.72,
        "sharpe": 3.99,
        "max_drawdown_pct": 0.0879,
        "total_pnl": 59540.63,
        "total_return_pct": 0.5954,
        "win_rate": 0.5238,
        "total_trades": 21,
        "survival_rate": 0.7925,
    },
    "old_thin": {
        "expected_value_score": 0.3583,
        "sharpe_daily": 1.31,
        "sharpe": 2.09,
        "max_drawdown_pct": 0.0903,
        "total_pnl": 27347.42,
        "total_return_pct": 0.2735,
        "win_rate": 0.4091,
        "total_trades": 22,
        "survival_rate": 0.9167,
    },
}

VARIANTS = OrderedDict(
    [
        ("mult_1_25", {"risk_multiplier": 1.25}),
        ("mult_1_50", {"risk_multiplier": 1.50}),
    ]
)


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _round(value: Any, digits: int = 4) -> Any:
    number = _safe_float(value)
    if number is None:
        return None
    return round(number, digits)


def _df_scalar(value: Any) -> float | None:
    if hasattr(value, "item"):
        value = value.item()
    return _safe_float(value)


def _extract_metrics(result: dict[str, Any]) -> dict[str, Any]:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "sharpe_daily": _round(result.get("sharpe_daily"), 4),
        "sharpe": _round(result.get("sharpe"), 4),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "total_return_pct": _round(
            benchmarks.get("strategy_total_return_pct")
            if benchmarks.get("strategy_total_return_pct") is not None
            else result.get("total_return_pct"),
            4,
        ),
        "win_rate": _round(result.get("win_rate"), 4),
        "total_trades": result.get("total_trades"),
        "survival_rate": _round(result.get("survival_rate"), 4),
    }


def _deltas(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    out = {}
    for key, after_value in after.items():
        before_value = before.get(key)
        if isinstance(after_value, (int, float)) and isinstance(before_value, (int, float)):
            digits = 2 if key == "total_pnl" else 4
            out[key] = round(float(after_value) - float(before_value), digits)
    return out


def _add_rs_accel_features(features: dict[str, Any], ohlcv_data: Any) -> dict[str, Any]:
    if features is None:
        return features
    if ohlcv_data is None or len(ohlcv_data) < 41 or "Close" not in ohlcv_data:
        return features

    close_now = _df_scalar(ohlcv_data["Close"].iloc[-1])
    close_20d_ago = _df_scalar(ohlcv_data["Close"].iloc[-21])
    close_40d_ago = _df_scalar(ohlcv_data["Close"].iloc[-41])
    if close_now and close_20d_ago and close_40d_ago:
        features["prev_momentum_20d_pct"] = round(
            (close_20d_ago - close_40d_ago) / close_40d_ago,
            4,
        )

    if len(ohlcv_data) >= 2 and "Open" in ohlcv_data:
        open_now = _df_scalar(ohlcv_data["Open"].iloc[-1])
        prev_close = _df_scalar(ohlcv_data["Close"].iloc[-2])
        if open_now and prev_close:
            features["signal_day_gap_pct"] = round((open_now - prev_close) / prev_close, 4)
    return features


def _annotate_rs_accel_signals(
    signals: list[dict[str, Any]],
    features_dict: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    spy_features = (features_dict or {}).get("SPY") or {}
    spy_ret20 = _safe_float(spy_features.get("momentum_20d_pct"))
    spy_prev_ret20 = _safe_float(spy_features.get("prev_momentum_20d_pct"))

    for sig in signals or []:
        if sig.get("strategy") not in CORE_STRATEGIES:
            sig["rs_accel_no_chase"] = False
            continue
        ticker = sig.get("ticker")
        features = (features_dict or {}).get(ticker) or {}
        ticker_ret20 = _safe_float(features.get("momentum_20d_pct"))
        ticker_prev_ret20 = _safe_float(features.get("prev_momentum_20d_pct"))
        signal_day_gap = _safe_float(features.get("signal_day_gap_pct"))
        rel20 = None
        prev_rel20 = None
        accel = None
        if ticker_ret20 is not None and spy_ret20 is not None:
            rel20 = ticker_ret20 - spy_ret20
        if ticker_prev_ret20 is not None and spy_prev_ret20 is not None:
            prev_rel20 = ticker_prev_ret20 - spy_prev_ret20
        if rel20 is not None and prev_rel20 is not None:
            accel = rel20 - prev_rel20

        no_chase = signal_day_gap is None or signal_day_gap < GAP_CHASE_MAX
        tagged = bool(
            rel20 is not None
            and accel is not None
            and rel20 > 0
            and accel > 0
            and no_chase
        )
        sig["prev_ticker_ret20_minus_spy_pct"] = _round(prev_rel20, 4)
        sig["rs20_accel_vs_spy_pct"] = _round(accel, 4)
        sig["signal_day_gap_pct"] = _round(signal_day_gap, 4)
        sig["rs_accel_no_chase"] = tagged
    return signals


def _patch_modules(risk_multiplier: float) -> Callable[[], None]:
    original_compute_features = feature_layer.compute_features
    original_enrich_signals = risk_engine.enrich_signals
    original_size_signals = portfolio_engine.size_signals
    original_sizing_multiplier_keys = backtester.SIZING_MULTIPLIER_KEYS

    def patched_compute_features(ticker: str, ohlcv_data: Any, earnings_data: Any) -> Any:
        features = original_compute_features(ticker, ohlcv_data, earnings_data)
        if isinstance(features, dict):
            features = dict(features)
            _add_rs_accel_features(features, ohlcv_data)
        return features

    def patched_enrich_signals(
        signals: list[dict[str, Any]],
        features_dict: dict[str, dict[str, Any]],
        atr_target_mult: float | None = None,
    ) -> list[dict[str, Any]]:
        enriched = original_enrich_signals(
            signals,
            features_dict,
            atr_target_mult=atr_target_mult,
        )
        return _annotate_rs_accel_signals(enriched, features_dict)

    def patched_size_signals(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        risk_pct: float | None = None,
    ) -> list[dict[str, Any]]:
        sized = original_size_signals(signals, portfolio_value, risk_pct=risk_pct)
        adjusted = []
        for sig in sized:
            if sig.get("strategy") not in CORE_STRATEGIES or sig.get("rs_accel_no_chase") is not True:
                adjusted.append(sig)
                continue

            sizing = dict(sig.get("sizing") or {})
            current_risk_pct = _safe_float(sizing.get("risk_pct"))
            entry = _safe_float(sig.get("entry_price"))
            stop = _safe_float(sig.get("stop_price"))
            max_position_pct = _safe_float(
                sizing.get("max_position_pct_applied")
            ) or MAX_POSITION_PCT

            if not current_risk_pct or current_risk_pct <= 0 or not entry or not stop:
                sizing[MULTIPLIER_KEY] = 1.0
                sig = {**sig, "sizing": sizing}
                adjusted.append(sig)
                continue

            boosted_risk_pct = current_risk_pct * risk_multiplier
            recalculated = portfolio_engine.compute_position_size(
                portfolio_value,
                entry,
                stop,
                risk_pct=boosted_risk_pct,
                max_position_pct=max_position_pct,
            )
            if not recalculated:
                sizing[MULTIPLIER_KEY] = 1.0
                sig = {**sig, "sizing": sizing}
                adjusted.append(sig)
                continue

            merged = {**sizing, **recalculated}
            merged["base_risk_pct"] = sizing.get("base_risk_pct")
            merged["risk_pct_before_rs_accel_no_chase"] = current_risk_pct
            merged["max_position_pct_applied"] = max_position_pct
            merged[MULTIPLIER_KEY] = risk_multiplier
            merged["rs_accel_no_chase"] = True
            merged["rs20_accel_vs_spy_pct"] = sig.get("rs20_accel_vs_spy_pct")
            merged["signal_day_gap_pct"] = sig.get("signal_day_gap_pct")
            sig = {**sig, "sizing": merged}
            adjusted.append(sig)
        return adjusted

    feature_layer.compute_features = patched_compute_features
    risk_engine.enrich_signals = patched_enrich_signals
    portfolio_engine.size_signals = patched_size_signals
    if MULTIPLIER_KEY not in backtester.SIZING_MULTIPLIER_KEYS:
        backtester.SIZING_MULTIPLIER_KEYS = (
            tuple(backtester.SIZING_MULTIPLIER_KEYS) + (MULTIPLIER_KEY,)
        )

    def restore() -> None:
        feature_layer.compute_features = original_compute_features
        risk_engine.enrich_signals = original_enrich_signals
        portfolio_engine.size_signals = original_size_signals
        backtester.SIZING_MULTIPLIER_KEYS = original_sizing_multiplier_keys

    return restore


def _run_window(window: dict[str, Any]) -> dict[str, Any]:
    engine = BacktestEngine(
        get_universe(),
        start=window["start"],
        end=window["end"],
        ohlcv_snapshot_path=str(REPO_ROOT / window["snapshot"]),
    )
    return engine.run()


def _evaluate_variant(name: str, params: dict[str, Any]) -> dict[str, Any]:
    restore = _patch_modules(float(params["risk_multiplier"]))
    try:
        window_results = OrderedDict()
        for label, window in WINDOWS.items():
            result = _run_window(window)
            metrics = _extract_metrics(result)
            before = BASELINE[label]
            sizing_attr = result.get("sizing_rule_trade_attribution", {}).get(
                "rs_accel_no_chase_risk_multiplier_applied",
                {},
            )
            signal_attr = result.get("sizing_rule_signal_attribution", {}).get(
                "rs_accel_no_chase_risk_multiplier_applied",
                {},
            )
            window_results[label] = {
                "window": dict(window),
                "before": before,
                "after": metrics,
                "delta": _deltas(metrics, before),
                "sizing_signal_attribution": signal_attr,
                "sizing_trade_attribution": sizing_attr,
                "raw_result_summary": {
                    "period": result.get("period"),
                    "trading_days": result.get("trading_days"),
                    "convergence": result.get("convergence"),
                    "known_biases": result.get("known_biases"),
                },
            }
        return {
            "variant": name,
            "parameters": params,
            "windows": window_results,
            "aggregate": _aggregate(window_results),
        }
    finally:
        restore()


def _aggregate(window_results: dict[str, Any]) -> dict[str, Any]:
    total_before_ev = sum(
        float(row["before"].get("expected_value_score") or 0.0)
        for row in window_results.values()
    )
    total_after_ev = sum(
        float(row["after"].get("expected_value_score") or 0.0)
        for row in window_results.values()
    )
    total_before_pnl = sum(
        float(row["before"].get("total_pnl") or 0.0)
        for row in window_results.values()
    )
    total_after_pnl = sum(
        float(row["after"].get("total_pnl") or 0.0)
        for row in window_results.values()
    )
    ev_positive_windows = [
        label
        for label, row in window_results.items()
        if (row["delta"].get("expected_value_score") or 0.0) > 0
    ]
    pnl_positive_windows = [
        label
        for label, row in window_results.items()
        if (row["delta"].get("total_pnl") or 0.0) > 0
    ]
    worst_drawdown_delta = max(
        (row["delta"].get("max_drawdown_pct") or 0.0)
        for row in window_results.values()
    )
    trade_count_regressions = [
        label
        for label, row in window_results.items()
        if (row["delta"].get("total_trades") or 0) < 0
    ]
    win_rate_regressions = [
        label
        for label, row in window_results.items()
        if (row["delta"].get("win_rate") or 0.0) < 0
    ]
    return {
        "baseline_ev_sum": round(total_before_ev, 4),
        "after_ev_sum": round(total_after_ev, 4),
        "ev_delta": round(total_after_ev - total_before_ev, 4),
        "ev_delta_pct": (
            round((total_after_ev - total_before_ev) / total_before_ev, 4)
            if total_before_ev
            else None
        ),
        "baseline_pnl_sum": round(total_before_pnl, 2),
        "after_pnl_sum": round(total_after_pnl, 2),
        "pnl_delta": round(total_after_pnl - total_before_pnl, 2),
        "pnl_delta_pct": (
            round((total_after_pnl - total_before_pnl) / total_before_pnl, 4)
            if total_before_pnl
            else None
        ),
        "ev_positive_windows": ev_positive_windows,
        "pnl_positive_windows": pnl_positive_windows,
        "worst_drawdown_delta": round(worst_drawdown_delta, 4),
        "trade_count_regressions": trade_count_regressions,
        "win_rate_regressions": win_rate_regressions,
    }


def _gate_decision(variant: dict[str, Any]) -> dict[str, Any]:
    aggregate = variant["aggregate"]
    gate_reasons = []
    if aggregate["ev_delta_pct"] is not None and aggregate["ev_delta_pct"] > 0.10:
        gate_reasons.append("aggregate expected_value_score improved >10%")
    if aggregate["pnl_delta_pct"] is not None and aggregate["pnl_delta_pct"] > 0.05:
        gate_reasons.append("aggregate total PnL improved >5%")

    sharpe_windows = []
    drawdown_windows = []
    for label, row in variant["windows"].items():
        if (row["delta"].get("sharpe_daily") or 0.0) > 0.1:
            sharpe_windows.append(label)
        if (row["delta"].get("max_drawdown_pct") or 0.0) < -0.01:
            drawdown_windows.append(label)
    if len(sharpe_windows) >= 2:
        gate_reasons.append(f"daily Sharpe improved >0.1 in {len(sharpe_windows)} windows")
    if len(drawdown_windows) >= 2:
        gate_reasons.append(f"max drawdown improved >1pp in {len(drawdown_windows)} windows")

    majority_ev = len(aggregate["ev_positive_windows"]) >= 2
    no_win_rate_regression = not aggregate["win_rate_regressions"]
    no_trade_regression = not aggregate["trade_count_regressions"]
    accepted = bool(gate_reasons and majority_ev and no_win_rate_regression and no_trade_regression)
    if not majority_ev:
        gate_reasons.append("failed robustness: EV did not improve in a majority of windows")
    if aggregate["win_rate_regressions"]:
        gate_reasons.append(
            "failed guardrail: win rate regressed in "
            + ", ".join(aggregate["win_rate_regressions"])
        )
    if aggregate["trade_count_regressions"]:
        gate_reasons.append(
            "failed guardrail: trade count regressed in "
            + ", ".join(aggregate["trade_count_regressions"])
        )
    return {
        "decision": "accepted_for_productionization" if accepted else "rejected",
        "accepted": accepted,
        "gate_reasons": gate_reasons,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "note": (
                "Replay-only experiment. A positive result still requires a "
                "shared production/backtest policy before strategy promotion."
            ),
        },
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s:%(name)s:%(message)s")
    variants = OrderedDict()
    for name, params in VARIANTS.items():
        variants[name] = _evaluate_variant(name, params)
        variants[name]["gate"] = _gate_decision(variants[name])

    best_variant_name = max(
        variants,
        key=lambda name: variants[name]["aggregate"]["ev_delta"],
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "hypothesis": (
            "Existing A/B signals tagged rs_accel_no_chase are higher-quality "
            "continuation candidates; increasing only their post-existing-rule "
            "risk budget may improve EV without adding candidates."
        ),
        "change_type": "capital_allocation_sizing_replay",
        "single_causal_variable": "rs_accel_no_chase post-sizing risk multiplier",
        "parameters": {
            "gap_chase_max": GAP_CHASE_MAX,
            "variants": VARIANTS,
            "core_strategies": sorted(CORE_STRATEGIES),
        },
        "baseline": BASELINE,
        "windows": WINDOWS,
        "variants": variants,
        "best_variant": {
            "name": best_variant_name,
            "aggregate": variants[best_variant_name]["aggregate"],
            "gate": variants[best_variant_name]["gate"],
        },
    }
    _write_json(OUT_JSON, payload)
    print(json.dumps(payload["best_variant"], indent=2, sort_keys=True))
    print(f"Wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
