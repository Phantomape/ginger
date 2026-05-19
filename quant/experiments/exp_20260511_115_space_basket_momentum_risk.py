"""exp-20260511-115: Space official-basket momentum risk.

Tests whether the accepted default-off Space sleeve should add or reduce risk
when the official operating Space basket itself has positive 20-day momentum.
This is deliberately different from the rejected UFO/ARKX theme ETF timing
gate: the state input is the tradable official-catalyst operating basket.
"""

from __future__ import annotations

import json
import logging
import math
import sys
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260511-115"
STEM = "space_basket_momentum_risk"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = PROJECT_ROOT / "quant"
if str(QUANT_DIR) not in sys.path:
    sys.path.insert(0, str(QUANT_DIR))

from backtester import BacktestEngine  # noqa: E402
from data_layer import get_universe  # noqa: E402
import portfolio_engine  # noqa: E402
import risk_engine  # noqa: E402
import signal_engine  # noqa: E402


logging.basicConfig(level=logging.WARNING)

WINDOWS = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "core_snapshot": "data/ohlcv_snapshot_20251023_20260421.json",
        "space_snapshot": (
            "data/experiments/exp-20260510-028/ohlcv/"
            "exp-20260510-028_late_strong_with_space_catalyst.json"
        ),
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "core_snapshot": "data/ohlcv_snapshot_20250423_20251022.json",
        "space_snapshot": (
            "data/experiments/exp-20260510-028/ohlcv/"
            "exp-20260510-028_mid_weak_with_space_catalyst.json"
        ),
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "core_snapshot": "data/ohlcv_snapshot_20241002_20250422.json",
        "space_snapshot": (
            "data/experiments/exp-20260510-028/ohlcv/"
            "exp-20260510-028_old_thin_with_space_catalyst.json"
        ),
    },
}

OFFICIAL_SPACE_TICKERS = ("ASTS", "BKSY", "LUNR", "PL", "RDW", "RKLB")
DATA_VENDOR_TICKERS = ("BKSY", "PL")
LAUNCH_CONNECTIVITY_TICKERS = ("ASTS", "RKLB")
BASE_SPACE_RISK_SCALAR = 0.75
DATA_VENDOR_BREAKOUT_RISK_SCALAR = 0.1
LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR = 1.25
BASE_SPACE_TREND_TARGET_ATR_MULT = 5.0
LAUNCH_CONNECTIVITY_TREND_TARGET_ATR_MULT = 7.0
SPACE_BASKET_MOMENTUM_FIELD = "momentum_20d_pct"
SPACE_BASKET_MOMENTUM_THRESHOLD = 0.0
SPACE_BASKET_POSITIVE_SCALARS = (0.75, 1.10, 1.25, 1.50)


def _round(value: Any, digits: int = 4) -> Any:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, set):
        return sorted(_safe(item) for item in value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl_once(path: Path, payload: dict) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=False, separators=(",", ":"))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        lines = [
            line
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
        ]
    else:
        lines = []
    lines.append(compact)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _metrics(result: dict) -> dict:
    benchmarks = result.get("benchmarks") or {}
    return {
        "expected_value_score": _round(result.get("expected_value_score"), 4),
        "strategy_total_return_pct": _round(
            benchmarks.get("strategy_total_return_pct"), 4
        ),
        "sharpe_daily": _round(result.get("sharpe_daily"), 4),
        "total_pnl": _round(result.get("total_pnl"), 2),
        "max_drawdown_pct": _round(result.get("max_drawdown_pct"), 4),
        "win_rate": _round(result.get("win_rate"), 4),
        "trade_count": int(result.get("total_trades") or 0),
        "signals_generated": int(result.get("signals_generated") or 0),
        "signals_survived": int(result.get("signals_survived") or 0),
        "survival_rate": _round(result.get("survival_rate"), 4),
        "worst_trade_pct": _round(result.get("worst_trade_pct"), 4),
        "max_consecutive_losses": result.get("max_consecutive_losses"),
        "tail_loss_share": _round(result.get("tail_loss_share"), 4),
    }


def _delta(after: dict, before: dict) -> dict:
    keys = (
        "expected_value_score",
        "strategy_total_return_pct",
        "sharpe_daily",
        "total_pnl",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "signals_generated",
        "signals_survived",
        "survival_rate",
        "worst_trade_pct",
        "tail_loss_share",
    )
    out = {}
    for key in keys:
        after_value = after.get(key)
        before_value = before.get(key)
        if isinstance(after_value, (int, float)) and isinstance(before_value, (int, float)):
            out[key] = _round(
                after_value - before_value,
                2 if key == "total_pnl" else 4,
            )
    return out


def _aggregate(metrics_by_window: dict[str, dict]) -> dict:
    rows = list(metrics_by_window.values())
    return {
        "expected_value_score_sum": _round(
            sum(row.get("expected_value_score") or 0 for row in rows), 4
        ),
        "total_pnl_sum": _round(sum(row.get("total_pnl") or 0 for row in rows), 2),
        "trade_count_sum": int(sum(row.get("trade_count") or 0 for row in rows)),
        "signals_generated_sum": int(
            sum(row.get("signals_generated") or 0 for row in rows)
        ),
        "signals_survived_sum": int(
            sum(row.get("signals_survived") or 0 for row in rows)
        ),
        "min_survival_rate": _round(
            min(row.get("survival_rate") or 0 for row in rows), 4
        ),
        "max_drawdown_pct_max": _round(
            max(row.get("max_drawdown_pct") or 0 for row in rows), 4
        ),
    }


def _aggregate_delta(after: dict, before: dict) -> dict:
    return {
        "expected_value_score_sum": _round(
            after["expected_value_score_sum"] - before["expected_value_score_sum"],
            4,
        ),
        "total_pnl_sum": _round(after["total_pnl_sum"] - before["total_pnl_sum"], 2),
        "trade_count_sum": after["trade_count_sum"] - before["trade_count_sum"],
        "signals_generated_sum": (
            after["signals_generated_sum"] - before["signals_generated_sum"]
        ),
        "signals_survived_sum": (
            after["signals_survived_sum"] - before["signals_survived_sum"]
        ),
        "min_survival_rate": _round(
            after["min_survival_rate"] - before["min_survival_rate"], 4
        ),
        "max_drawdown_pct_max": _round(
            after["max_drawdown_pct_max"] - before["max_drawdown_pct_max"], 4
        ),
    }


def _gate2_open_positions() -> dict:
    path = PROJECT_ROOT / "operator_inputs" / "open_positions.json"
    if not path.exists():
        return {"passed": False, "path": str(path.relative_to(PROJECT_ROOT)), "missing": "file"}
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    positions = list(payload.get("positions") or []) + list(payload.get("observations") or [])
    missing = [
        row.get("ticker") or "<unknown>"
        for row in positions
        if not row.get("entry_date") or row.get("target_price") in (None, "")
    ]
    return {
        "passed": not missing,
        "path": str(path.relative_to(PROJECT_ROOT)),
        "position_count": len(positions),
        "missing_entry_date_or_target_price": missing,
    }


def _scale_sizing(sizing: dict, scalar: float, portfolio_value: float, marker: str) -> None:
    old_shares = int(sizing.get("shares_to_buy") or 0)
    if old_shares <= 0:
        return
    new_shares = int(math.floor(old_shares * scalar))
    ratio = new_shares / old_shares if old_shares else 0.0
    old_risk_pct = float(sizing.get("risk_pct") or 0.0)
    old_risk_amount = float(
        sizing.get("risk_amount_usd") or (old_risk_pct * portfolio_value)
    )
    old_position_value = float(sizing.get("position_value_usd") or 0.0)
    sizing[f"{marker}_scalar_applied"] = scalar
    sizing[f"{marker}_baseline_shares"] = old_shares
    sizing[f"{marker}_scaled_shares"] = new_shares
    sizing[f"{marker}_risk_pct_before_scalar"] = old_risk_pct
    sizing[f"{marker}_risk_amount_before_scalar"] = round(old_risk_amount, 2)
    sizing["shares_to_buy"] = new_shares
    sizing["risk_pct"] = old_risk_pct * ratio
    sizing["risk_amount_usd"] = round(old_risk_amount * ratio, 2)
    sizing["position_value_usd"] = round(old_position_value * ratio, 2)
    sizing["position_pct_of_portfolio"] = (
        round((old_position_value * ratio) / portfolio_value, 4)
        if portfolio_value
        else 0.0
    )


def _space_basket_momentum(features_dict: dict[str, dict]) -> dict:
    values = {}
    for ticker in OFFICIAL_SPACE_TICKERS:
        raw = (features_dict.get(ticker) or {}).get(SPACE_BASKET_MOMENTUM_FIELD)
        value = _round(raw, 6)
        if value is not None:
            values[ticker] = value
    if not values:
        return {"state": "missing", "value": None, "values": {}}
    value = sum(values.values()) / len(values)
    state = "positive" if value > SPACE_BASKET_MOMENTUM_THRESHOLD else "nonpositive"
    return {
        "state": state,
        "value": _round(value, 6),
        "values": dict(sorted(values.items())),
    }


def _retarget_if_space_trend(signal: dict, features_dict: dict) -> dict:
    ticker = str(signal.get("ticker") or "").upper()
    strategy = str(signal.get("strategy") or "")
    if ticker not in OFFICIAL_SPACE_TICKERS or strategy != "trend_long":
        return signal
    atr = (features_dict.get(ticker) or {}).get("atr")
    if not atr:
        return signal
    target_mult = BASE_SPACE_TREND_TARGET_ATR_MULT
    if ticker in LAUNCH_CONNECTIVITY_TICKERS:
        target_mult = LAUNCH_CONNECTIVITY_TREND_TARGET_ATR_MULT
    updated = risk_engine._retarget_signal_with_atr_mult(signal, atr, target_mult)
    updated["space_trend_target_scope"] = "accepted_exp105_target_semantics"
    updated["space_trend_target_atr_mult"] = target_mult
    return updated


def _install_space_policy(space_basket_positive_scalar: float):
    original_generate = signal_engine.generate_signals
    original_enrich = risk_engine.enrich_signals
    original_size = portfolio_engine.size_signals
    adjustments = []
    state_counts = Counter()
    day_counts = Counter()

    def generate_wrapper(features_dict, *args, **kwargs):
        basket = _space_basket_momentum(features_dict)
        day_counts[basket["state"]] += 1
        signals = original_generate(features_dict, *args, **kwargs)
        for signal in signals:
            ticker = str(signal.get("ticker") or "").upper()
            if ticker not in OFFICIAL_SPACE_TICKERS:
                continue
            signal["space_basket_momentum_state"] = basket["state"]
            signal["space_basket_momentum_20d_pct"] = basket["value"]
            signal["space_basket_momentum_values"] = basket["values"]
            state_counts[basket["state"]] += 1
        return signals

    def enrich_wrapper(signals, features_dict, atr_target_mult=None):
        enriched = original_enrich(
            signals,
            features_dict,
            atr_target_mult=atr_target_mult,
        )
        return [_retarget_if_space_trend(signal, features_dict) for signal in enriched]

    def size_wrapper(signals, portfolio_value, risk_pct=None):
        sized = original_size(signals, portfolio_value, risk_pct=risk_pct)
        out = []
        for signal in sized:
            ticker = str(signal.get("ticker") or "").upper()
            strategy = str(signal.get("strategy") or "").lower()
            sizing = deepcopy(signal.get("sizing") or {})
            if ticker in OFFICIAL_SPACE_TICKERS and sizing:
                shares_before = int(sizing.get("shares_to_buy") or 0)
                _scale_sizing(
                    sizing,
                    BASE_SPACE_RISK_SCALAR,
                    portfolio_value,
                    "space_official_base_risk",
                )
                if ticker in DATA_VENDOR_TICKERS and strategy == "breakout_long":
                    _scale_sizing(
                        sizing,
                        DATA_VENDOR_BREAKOUT_RISK_SCALAR,
                        portfolio_value,
                        "space_data_vendor_breakout_risk",
                    )
                if ticker in LAUNCH_CONNECTIVITY_TICKERS and strategy == "trend_long":
                    _scale_sizing(
                        sizing,
                        LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR,
                        portfolio_value,
                        "space_launch_connectivity_trend_risk",
                    )
                basket_positive = signal.get("space_basket_momentum_state") == "positive"
                if basket_positive and space_basket_positive_scalar != 1.0:
                    _scale_sizing(
                        sizing,
                        space_basket_positive_scalar,
                        portfolio_value,
                        "space_basket_positive_risk",
                    )
                if basket_positive:
                    adjustments.append(
                        {
                            "ticker": ticker,
                            "strategy": strategy,
                            "basket_state": signal.get("space_basket_momentum_state"),
                            "basket_momentum_20d_pct": signal.get(
                                "space_basket_momentum_20d_pct"
                            ),
                            "basket_values": signal.get("space_basket_momentum_values"),
                            "space_basket_positive_scalar": (
                                space_basket_positive_scalar
                            ),
                            "shares_before_space_scalars": shares_before,
                            "shares_after_space_scalars": int(
                                sizing.get("shares_to_buy") or 0
                            ),
                            "trade_quality_score": _round(
                                signal.get("trade_quality_score"), 4
                            ),
                            "confidence_score": _round(
                                signal.get("confidence_score"), 4
                            ),
                        }
                    )
                signal = {**signal, "sizing": sizing}
            out.append(signal)
        return out

    signal_engine.generate_signals = generate_wrapper
    risk_engine.enrich_signals = enrich_wrapper
    portfolio_engine.size_signals = size_wrapper
    return original_generate, original_enrich, original_size, adjustments, state_counts, day_counts


def _restore_policy(original_generate, original_enrich, original_size) -> None:
    signal_engine.generate_signals = original_generate
    risk_engine.enrich_signals = original_enrich
    portfolio_engine.size_signals = original_size


def _run_window(window: dict, universe: list[str], snapshot_key: str) -> dict:
    engine = BacktestEngine(
        universe,
        start=window["start"],
        end=window["end"],
        ohlcv_snapshot_path=str(PROJECT_ROOT / window[snapshot_key]),
        config={"REPLAY_PARTIAL_REDUCES": True, "REGIME_AWARE_EXIT": True},
    )
    result = engine.run()
    if "error" in result:
        raise RuntimeError(result["error"])
    return result


def _run_core_baseline() -> dict:
    universe = get_universe()
    by_window = {}
    for label, window in WINDOWS.items():
        result = _run_window(window, universe, "core_snapshot")
        by_window[label] = _metrics(result)
    return {"by_window": by_window, "aggregate": _aggregate(by_window)}


def _run_variant(name: str, scalar: float) -> dict:
    core_universe = get_universe()
    universe = sorted(set(core_universe) | set(OFFICIAL_SPACE_TICKERS))
    (
        original_generate,
        original_enrich,
        original_size,
        adjustments,
        state_counts,
        day_counts,
    ) = _install_space_policy(scalar)
    try:
        by_window = {}
        for label, window in WINDOWS.items():
            before_adjustment_count = len(adjustments)
            result = _run_window(window, universe, "space_snapshot")
            window_adjustments = adjustments[before_adjustment_count:]
            metrics = _metrics(result)
            by_window[label] = {
                "metrics": metrics,
                "space_trade_attribution": _space_trade_attribution(result),
                "space_basket_positive_adjustment": _adjustment_summary(
                    window_adjustments
                ),
                "space_basket_signal_state_counts": dict(sorted(state_counts.items())),
                "space_basket_day_counts": dict(sorted(day_counts.items())),
            }
    finally:
        _restore_policy(original_generate, original_enrich, original_size)
    metrics_by_window = {label: row["metrics"] for label, row in by_window.items()}
    return {
        "variant": name,
        "space_basket_positive_scalar": scalar,
        "by_window": by_window,
        "aggregate": _aggregate(metrics_by_window),
    }


def _adjustment_summary(adjustments: list[dict]) -> dict:
    return {
        "adjusted_signal_count": len(adjustments),
        "by_ticker": dict(sorted(Counter(row["ticker"] for row in adjustments).items())),
        "by_strategy": dict(
            sorted(Counter(row["strategy"] for row in adjustments).items())
        ),
        "sample_adjusted": adjustments[:12],
    }


def _rounded_bucket(bucket: dict) -> dict:
    out = {}
    for key, row in bucket.items():
        out[key] = {**row, "pnl": _round(row.get("pnl"), 2)}
    return out


def _space_trade_attribution(result: dict) -> dict:
    trades = [
        trade
        for trade in result.get("trades") or []
        if str(trade.get("ticker") or "").upper() in OFFICIAL_SPACE_TICKERS
    ]
    by_ticker = {}
    by_strategy = {}
    by_exit_reason = {}
    for trade in trades:
        ticker = str(trade.get("ticker") or "").upper()
        strategy = str(trade.get("strategy") or "unknown")
        exit_reason = str(trade.get("exit_reason") or "unknown")
        pnl = float(trade.get("pnl") or 0.0)
        for bucket, key in (
            (by_ticker, ticker),
            (by_strategy, strategy),
            (by_exit_reason, exit_reason),
        ):
            row = bucket.setdefault(
                key,
                {"trade_count": 0, "wins": 0, "losses": 0, "pnl": 0.0},
            )
            row["trade_count"] += 1
            row["wins"] += int(pnl > 0)
            row["losses"] += int(pnl <= 0)
            row["pnl"] += pnl
    positive = [row["pnl"] for row in by_ticker.values() if row["pnl"] > 0]
    total_positive = sum(positive)
    return {
        "trade_count": len(trades),
        "wins": sum(1 for trade in trades if (trade.get("pnl") or 0) > 0),
        "losses": sum(1 for trade in trades if (trade.get("pnl") or 0) <= 0),
        "win_rate": (
            _round(sum(1 for trade in trades if (trade.get("pnl") or 0) > 0) / len(trades), 4)
            if trades
            else None
        ),
        "total_pnl": _round(sum(float(trade.get("pnl") or 0.0) for trade in trades), 2),
        "single_ticker_positive_share": _round(
            max(positive) / total_positive if total_positive else 0.0,
            4,
        ),
        "by_ticker": _rounded_bucket(by_ticker),
        "by_strategy": _rounded_bucket(by_strategy),
        "by_exit_reason": _rounded_bucket(by_exit_reason),
        "trades": [
            {
                "ticker": str(trade.get("ticker") or "").upper(),
                "strategy": trade.get("strategy"),
                "entry_date": trade.get("entry_date"),
                "exit_date": trade.get("exit_date"),
                "exit_reason": trade.get("exit_reason"),
                "pnl": _round(trade.get("pnl"), 2),
                "pnl_pct_net": _round(trade.get("pnl_pct_net"), 6),
                "shares": trade.get("shares"),
            }
            for trade in trades
        ],
    }


def _gate(variant: dict, before: dict, core: dict) -> dict:
    aggregate_delta = _aggregate_delta(variant["aggregate"], before["aggregate"])
    aggregate_delta_vs_core = _aggregate_delta(variant["aggregate"], core["aggregate"])
    by_window_delta = {
        label: _delta(row["metrics"], before["by_window"][label]["metrics"])
        for label, row in variant["by_window"].items()
    }
    windows_ev_improved = sum(
        1 for row in by_window_delta.values() if row.get("expected_value_score", 0) > 0
    )
    windows_ev_regressed = sum(
        1 for row in by_window_delta.values() if row.get("expected_value_score", 0) < 0
    )
    max_drawdown_change = aggregate_delta["max_drawdown_pct_max"]
    adjusted_count = sum(
        row["space_basket_positive_adjustment"]["adjusted_signal_count"]
        for row in variant["by_window"].values()
    )
    passed = (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and windows_ev_improved >= 2
        and windows_ev_regressed == 0
        and max_drawdown_change <= 0.005
        and variant["aggregate"]["min_survival_rate"] >= 0.05
        and variant["aggregate"]["trade_count_sum"] >= 50
        and adjusted_count > 0
    )
    return {
        "passed": passed,
        "aggregate_delta_vs_before": aggregate_delta,
        "aggregate_delta_vs_core": aggregate_delta_vs_core,
        "by_window_delta_vs_before": by_window_delta,
        "windows_ev_improved_vs_before": windows_ev_improved,
        "windows_ev_regressed_vs_before": windows_ev_regressed,
        "max_drawdown_change_vs_before": max_drawdown_change,
        "space_basket_positive_adjusted_signal_count": adjusted_count,
    }


def _artifact_markdown(payload: dict) -> str:
    best = payload["best_variant"]
    lines = [
        f"# {EXPERIMENT_ID} Space basket momentum risk",
        "",
        f"- Decision: `{payload['decision']}`",
        "- Single variable: extra risk scalar when official Space basket 20d momentum is positive.",
        f"- Best variant: `{best['variant']}`",
        f"- Aggregate EV delta vs accepted: `{payload['expected_value_score_delta']:+.4f}`",
        (
            "- Aggregate PnL delta vs accepted: "
            f"`${payload['delta_metrics']['aggregate']['total_pnl_sum']:+,.2f}`"
        ),
        "",
        "## Sweep",
        "",
        "| Variant | Scalar | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted signals |",
        "|---|---:|---|---:|---:|---:|---:|---:|",
    ]
    for name, variant in payload["variants"].items():
        gate = variant["gate"]
        delta = gate["aggregate_delta_vs_before"]
        lines.append(
            f"| {name} | {variant['space_basket_positive_scalar']:.2f} | "
            f"{'pass' if gate['passed'] else 'fail'} | "
            f"{delta['expected_value_score_sum']:+.4f} | "
            f"{delta['total_pnl_sum']:+,.2f} | "
            f"{gate['windows_ev_improved_vs_before']} | "
            f"{gate['windows_ev_regressed_vs_before']} | "
            f"{gate['space_basket_positive_adjusted_signal_count']} |"
        )
    lines.extend(
        [
            "",
            "## Best Three-Window Comparison",
            "",
            (
                "| Window | Before EV | After EV | dEV | Before PnL | After PnL | "
                "dPnL | Trades | Max DD | Survival | Basket-positive signals |"
            ),
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        adjusted = best["by_window"][label]["space_basket_positive_adjustment"][
            "adjusted_signal_count"
        ]
        lines.append(
            "| {label} | {before_ev:.4f} | {after_ev:.4f} | {delta_ev:+.4f} | "
            "{before_pnl:,.2f} | {after_pnl:,.2f} | {delta_pnl:+,.2f} | "
            "{trades} | {max_dd:.4f} | {survival:.4f} | {adjusted} |".format(
                label=label,
                before_ev=before["expected_value_score"],
                after_ev=after["expected_value_score"],
                delta_ev=delta.get("expected_value_score", 0),
                before_pnl=before["total_pnl"],
                after_pnl=after["total_pnl"],
                delta_pnl=delta.get("total_pnl", 0),
                trades=after["trade_count"],
                max_dd=after["max_drawdown_pct"],
                survival=after["survival_rate"],
                adjusted=adjusted,
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            payload["interpretation"],
            "",
            "## Production Impact",
            "",
            json.dumps(payload["production_impact"], sort_keys=True),
            "",
        ]
    )
    return "\n".join(lines)


def _ticket(payload: dict) -> dict:
    best = payload["best_variant"]
    return {
        "experiment_id": payload["experiment_id"],
        "status": payload["status"],
        "decision": payload["decision"],
        "changed_variable": payload["changed_variable"],
        "best_variant": best["variant"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["delta_metrics"]["aggregate"]["total_pnl_sum"],
        "gate4_passed": payload["gate4"]["passed"],
        "summary": payload["interpretation"],
        "artifact": str(
            Path("data") / "experiments" / EXPERIMENT_ID / f"{STEM}.json"
        ),
    }


def run() -> dict:
    gate2 = _gate2_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    core = _run_core_baseline()
    variants = {
        "accepted_exp105_stack": _run_variant("accepted_exp105_stack", 1.0)
    }
    for scalar in SPACE_BASKET_POSITIVE_SCALARS:
        name = f"basket_positive_{str(scalar).replace('.', '_')}"
        variants[name] = _run_variant(name, scalar)

    before = variants["accepted_exp105_stack"]
    for variant in variants.values():
        variant["gate"] = _gate(variant, before, core)

    candidates = [
        variant
        for name, variant in variants.items()
        if name != "accepted_exp105_stack"
    ]
    best_variant = max(
        candidates,
        key=lambda variant: (
            variant["gate"]["passed"],
            variant["gate"]["aggregate_delta_vs_before"]["expected_value_score_sum"],
            variant["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
        ),
    )
    accepted = best_variant["gate"]["passed"]
    decision = (
        "accepted_default_off_space_basket_momentum_risk"
        if accepted
        else "rejected_space_basket_momentum_risk"
    )
    interpretation = (
        "Official Space basket positive 20d momentum improved the accepted "
        "exp-105 default-off Space stack under the three-window gate. Shared "
        "production-visible observation metadata/helper wiring is default-off; "
        "live Space slots remain zero."
        if accepted
        else (
            "Official Space basket 20d momentum did not beat the accepted "
            "exp-105 Space stack. Space timing should not be solved by a broad "
            "internal basket momentum scalar on the frozen sample; the better "
            "next evidence is forward catalyst quality or replacement value."
        )
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "risk_allocation_shadow_sweep",
        "changed_variable": "space_official_basket_positive_momentum_risk_scalar",
        "single_causal_variable": (
            "extra risk scalar for official Space signals when the official "
            "operating Space basket equal-weight 20d momentum is positive"
        ),
        "hypothesis": (
            "When the official Space operating basket itself has positive 20d "
            "momentum, Space signals may have theme-internal breadth support; "
            "a bounded extra risk scalar could improve EV without adding noisy "
            "tickers or relying on underpowered LLM soft-ranking."
        ),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation: adjust only Space signals that occur while "
                "the official operating Space basket has positive 20d momentum."
            ),
            "2_history_check": {
                "exp-20260511-030": (
                    "Rejected UFO/ARKX theme ETF momentum timing; this uses "
                    "the official operating basket itself, not ETFs."
                ),
                "exp-20260511-105": (
                    "Accepted RKLB/ASTS launch-connectivity trend target 7 ATR; "
                    "this is the before state."
                ),
                "exp-20260511-110": "Rejected Space breakout stop widening.",
                "exp-20260511-113": "Rejected a simple Space one-slot cap.",
            },
            "3_single_causal_variable": (
                "space_official_basket_positive_momentum_risk_scalar; no target, "
                "stop, ticker pool, ranking, add-on, LLM/news, or live slot change."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; require positive "
                "aggregate EV and PnL, EV improvement in at least 2/3 windows "
                "with no EV regression, max drawdown drift <= 0.5 pp, survival "
                ">= 5%, at least 50 total trades, and nonzero adjusted signals."
            ),
            "5_reproducibility": (
                "This script reruns core, accepted exp-105 Space stack, and "
                "each basket-positive risk scalar across the three canonical "
                "augmented Space snapshots."
            ),
        },
        "historical_experiment_check": {
            "not_llm_soft_ranking": (
                "Space event-state forward ledger still lacks enough mature "
                "closed decisions for LLM/event soft ranking."
            ),
            "not_candidate_noise": (
                "No new ticker is added; the test uses only the accepted official "
                "Space operating pool."
            ),
            "not_nearby_retune": (
                "Accepted target, stop, PL/BKSY risk, RKLB/ASTS trend risk, "
                "entry filters, and ranking stay locked."
            ),
        },
        "parameters": {
            "official_space_tickers": list(OFFICIAL_SPACE_TICKERS),
            "space_basket_momentum_field": SPACE_BASKET_MOMENTUM_FIELD,
            "space_basket_momentum_threshold": SPACE_BASKET_MOMENTUM_THRESHOLD,
            "tested_space_basket_positive_scalars": list(
                SPACE_BASKET_POSITIVE_SCALARS
            ),
            "base_space_risk_scalar": BASE_SPACE_RISK_SCALAR,
            "data_vendor_breakout_risk_scalar": DATA_VENDOR_BREAKOUT_RISK_SCALAR,
            "launch_connectivity_trend_risk_scalar": (
                LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR
            ),
            "base_space_trend_target_atr_mult": BASE_SPACE_TREND_TARGET_ATR_MULT,
            "launch_connectivity_trend_target_atr_mult": (
                LAUNCH_CONNECTIVITY_TREND_TARGET_ATR_MULT
            ),
            "locked_variables": [
                "official Space candidate pool",
                "base Space risk scalar",
                "PL/BKSY breakout 0.1x haircut",
                "RKLB/ASTS trend 1.25x top-up",
                "all accepted Space trend targets",
                "breakout stop and target widths",
                "core production universe",
                "core signal generation",
                "entry filters",
                "ranking",
                "MAX_POSITIONS",
                "exits",
                "add-ons",
                "LLM/news replay",
                "live Space slots",
            ],
        },
        "date_range": {
            label: {
                "start": window["start"],
                "end": window["end"],
                "snapshot": window["space_snapshot"],
            }
            for label, window in WINDOWS.items()
        },
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows. Core uses "
            "canonical snapshots; Space variants use the same exp-20260510-028 "
            "augmented snapshots. The accepted_before variant reproduces "
            "exp-20260511-105 policy semantics."
        ),
        "gate1": {
            "core_baseline": core["aggregate"],
            "accepted_before_metrics": before["aggregate"],
            "known_bias": (
                "Space candidate snapshots are frozen historical replay copies "
                "built from a 2026-05-10 research universe; accepted changes "
                "remain default-off metadata until forward evidence matures."
            ),
        },
        "gate2": gate2,
        "gate3": {
            "new_core_filter_added": False,
            "space_basket_state_added": True,
            "min_survival_rate_after": best_variant["aggregate"]["min_survival_rate"],
            "passed": best_variant["aggregate"]["min_survival_rate"] >= 0.05,
        },
        "core_baseline_metrics": core["by_window"],
        "core_aggregate": core["aggregate"],
        "before_variant": before,
        "before_metrics": {
            "aggregate": before["aggregate"],
            **{label: row["metrics"] for label, row in before["by_window"].items()},
        },
        "after_metrics": {
            "aggregate": best_variant["aggregate"],
            **{
                label: row["metrics"]
                for label, row in best_variant["by_window"].items()
            },
        },
        "delta_metrics": {
            "aggregate": best_variant["gate"]["aggregate_delta_vs_before"],
            "by_window": best_variant["gate"]["by_window_delta_vs_before"],
        },
        "expected_value_score_delta": best_variant["gate"][
            "aggregate_delta_vs_before"
        ]["expected_value_score_sum"],
        "gate_results": best_variant["gate"],
        "gate4": best_variant["gate"],
        "variants": variants,
        "best_variant": best_variant,
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm_soft_ranking": (
                "Space event-state forward data is still below the closed-decision "
                "gate; this run uses deterministic OHLCV basket momentum."
            ),
        },
        "production_impact": {
            "shared_policy_changed": accepted,
            "backtester_adapter_changed": False,
            "run_adapter_changed": accepted,
            "replay_only": True,
            "parity_test_added": accepted,
            "daily_report_metadata_changed": accepted,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "live_slots_changed": False,
            "live_slots": 0,
        },
        "decision_rationale": interpretation,
        "interpretation": interpretation,
        "rejection_reason": None if accepted else interpretation,
        "next_evidence_needed": (
            "If rejected, do not retry broad Space basket momentum scalars on "
            "the same frozen snapshots. Future Space work needs forward event "
            "replacement value or a genuinely new catalyst-quality field."
        ),
        "related_files": [
            "quant/experiments/exp_20260511_115_space_basket_momentum_risk.py",
            "quant/space_catalyst_sleeve.py",
            "quant/report_generator.py",
            "quant/test_space_catalyst_sleeve.py",
            "data/experiments/exp-20260511-115/space_basket_momentum_risk.json",
            "experiments/logs/exp-20260511-115.json",
            "experiments/tickets/exp-20260511-115.json",
            "experiments/artifacts/exp-20260511-115_space_basket_momentum_risk.md",
            "docs/experiment_log.jsonl",
        ],
        "why_not_other_changes": (
            "LLM soft-ranking is data-limited; mature satcom breadth, theme ETF "
            "timing, breakout target/stop geometry, one-slot capacity, and "
            "nearby target bucket scopes have already failed on this sample."
        ),
    }
    return payload


def persist(payload: dict) -> None:
    out_dir = PROJECT_ROOT / "data" / "experiments" / EXPERIMENT_ID
    artifact_path = out_dir / f"{STEM}.json"
    log_path = PROJECT_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    ticket_path = PROJECT_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    md_path = (
        PROJECT_ROOT
        / "experiments"
        / "artifacts"
        / f"{EXPERIMENT_ID}_{STEM}.md"
    )
    jsonl_path = PROJECT_ROOT / "docs" / "experiment_log.jsonl"
    _write_json(artifact_path, payload)
    _write_json(log_path, payload)
    _write_json(ticket_path, _ticket(payload))
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_once(jsonl_path, payload)


if __name__ == "__main__":
    result = run()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": result["experiment_id"],
                "decision": result["decision"],
                "expected_value_score_delta": result["expected_value_score_delta"],
                "pnl_delta": result["delta_metrics"]["aggregate"]["total_pnl_sum"],
                "best_variant": result["best_variant"]["variant"],
                "gate4_passed": result["gate4"]["passed"],
            },
            indent=2,
            sort_keys=True,
        )
    )
