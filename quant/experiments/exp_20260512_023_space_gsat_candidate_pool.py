"""exp-20260512-023: Space GSAT candidate-pool admission.

Tests whether GSAT should enter the default-off official Space candidate pool.
This keeps the accepted exp-20260512-013 Space stack fixed for the existing
official tickers and changes only one causal variable: GSAT is allowed to
compete for Space trades under the same conservative risk ladder. The reference
Space basket remains the accepted six-name operating basket, so this does not
retune basket momentum, TQS, geometry, stops, ranking, or live slots.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from exp_20260511_115_space_basket_momentum_risk import (
    BASE_SPACE_RISK_SCALAR,
    BASE_SPACE_TREND_TARGET_ATR_MULT,
    DATA_VENDOR_BREAKOUT_RISK_SCALAR,
    DATA_VENDOR_TICKERS,
    LAUNCH_CONNECTIVITY_TICKERS,
    LAUNCH_CONNECTIVITY_TREND_RISK_SCALAR,
    LAUNCH_CONNECTIVITY_TREND_TARGET_ATR_MULT,
    OFFICIAL_SPACE_TICKERS,
    PROJECT_ROOT,
    SPACE_BASKET_MOMENTUM_FIELD,
    SPACE_BASKET_MOMENTUM_THRESHOLD,
    WINDOWS,
    _adjustment_summary,
    _aggregate,
    _aggregate_delta,
    _delta,
    _gate2_open_positions,
    _metrics,
    _restore_policy,
    _round,
    _run_core_baseline,
    _run_window,
    _safe,
    _scale_sizing,
    _write_json,
)
from exp_20260512_009_space_peer_momentum_leader_risk import (
    ACCEPTED_SPACE_BASKET_POSITIVE_SCALAR,
    ACCEPTED_SPACE_NEAR_PERFECT_TQS_SCORE_CEILING,
    ACCEPTED_SPACE_NEAR_PERFECT_TQS_SCORE_FLOOR,
    ACCEPTED_SPACE_NEAR_PERFECT_TQS_TREND_RISK_SCALAR,
    ACCEPTED_SPACE_PERFECT_TQS_RISK_SCALAR,
    _adjustment_row,
    _is_perfect_tqs,
)
from exp_20260512_013_space_peer_nonleader_breakout_risk import (
    _run_variant as _run_accepted_exp013_variant,
)
from data_layer import get_universe
import portfolio_engine
import risk_engine
import signal_engine


logging.basicConfig(level=logging.WARNING)

EXPERIMENT_ID = "exp-20260512-023"
STEM = "space_gsat_candidate_pool"
ADDED_TICKER = "GSAT"
REFERENCE_SPACE_TICKERS = tuple(OFFICIAL_SPACE_TICKERS)
CANDIDATE_SPACE_TICKERS = tuple(sorted(set(REFERENCE_SPACE_TICKERS) | {ADDED_TICKER}))
PEER_NONLEADER_BREAKOUT_SCALAR = 0.0


def _append_jsonl_for_this_experiment(path: Path, payload: dict[str, Any]) -> None:
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


def _reference_space_basket_momentum(features_dict: dict[str, dict]) -> dict[str, Any]:
    values = {}
    for ticker in REFERENCE_SPACE_TICKERS:
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


def _candidate_peer_momentum_state(
    signal: dict[str, Any],
    features_dict: dict[str, dict],
    basket: dict[str, Any],
) -> dict[str, Any]:
    ticker = str(signal.get("ticker") or "").upper()
    own = _round(
        (features_dict.get(ticker) or {}).get(SPACE_BASKET_MOMENTUM_FIELD),
        6,
    )
    basket_value = _round(basket.get("value"), 6)
    if own is None or basket_value is None:
        return {
            "state": "missing",
            "own_momentum_20d_pct": own,
            "basket_momentum_20d_pct": basket_value,
            "excess_momentum_20d_pct": None,
        }
    excess = _round(own - basket_value, 6)
    return {
        "state": "leader" if excess > 0 else "nonleader",
        "own_momentum_20d_pct": own,
        "basket_momentum_20d_pct": basket_value,
        "excess_momentum_20d_pct": excess,
    }


def _is_candidate_near_perfect_tqs_trend(signal: dict[str, Any]) -> bool:
    ticker = str(signal.get("ticker") or "").upper()
    strategy = str(signal.get("strategy") or "").lower()
    value = _round(signal.get("trade_quality_score"), 6)
    return (
        ticker in CANDIDATE_SPACE_TICKERS
        and strategy == "trend_long"
        and value is not None
        and ACCEPTED_SPACE_NEAR_PERFECT_TQS_SCORE_FLOOR
        <= value
        < ACCEPTED_SPACE_NEAR_PERFECT_TQS_SCORE_CEILING
    )


def _retarget_if_candidate_space_trend(
    signal: dict[str, Any],
    features_dict: dict[str, dict],
) -> dict[str, Any]:
    ticker = str(signal.get("ticker") or "").upper()
    strategy = str(signal.get("strategy") or "")
    if ticker not in CANDIDATE_SPACE_TICKERS or strategy != "trend_long":
        return signal
    atr = (features_dict.get(ticker) or {}).get("atr")
    if not atr:
        return signal
    target_mult = BASE_SPACE_TREND_TARGET_ATR_MULT
    if ticker in LAUNCH_CONNECTIVITY_TICKERS:
        target_mult = LAUNCH_CONNECTIVITY_TREND_TARGET_ATR_MULT
    updated = risk_engine._retarget_signal_with_atr_mult(signal, atr, target_mult)
    updated["space_trend_target_scope"] = "candidate_pool_gsat_reference_basket"
    updated["space_trend_target_atr_mult"] = target_mult
    return updated


def _candidate_signal_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "signal_count": len(rows),
        "by_ticker": dict(sorted(Counter(row["ticker"] for row in rows).items())),
        "by_strategy": dict(sorted(Counter(row["strategy"] for row in rows).items())),
        "by_peer_state": dict(
            sorted(Counter(row["space_peer_momentum_state"] for row in rows).items())
        ),
        "sample_signals": rows[:12],
    }


def _rounded_bucket(bucket: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out = {}
    for key, row in bucket.items():
        out[key] = {**row, "pnl": _round(row.get("pnl"), 2)}
    return out


def _space_trade_attribution_for(result: dict[str, Any], tickers: tuple[str, ...]) -> dict[str, Any]:
    ticker_set = set(tickers)
    trades = [
        trade
        for trade in result.get("trades") or []
        if str(trade.get("ticker") or "").upper() in ticker_set
    ]
    by_ticker: dict[str, dict[str, Any]] = {}
    by_strategy: dict[str, dict[str, Any]] = {}
    by_exit_reason: dict[str, dict[str, Any]] = {}
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
            _round(
                sum(1 for trade in trades if (trade.get("pnl") or 0) > 0)
                / len(trades),
                4,
            )
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


def _field_check_gsat_snapshot() -> dict[str, Any]:
    coverage = {}
    missing = []
    for label, window in WINDOWS.items():
        snapshot_path = PROJECT_ROOT / window["space_snapshot"]
        payload = json.loads(snapshot_path.read_text(encoding="utf-8-sig"))
        rows = list((payload.get("ohlcv") or {}).get(ADDED_TICKER) or [])
        row_count = len(rows)
        nonzero_volume = sum(1 for row in rows if (row.get("Volume") or 0) > 0)
        coverage[label] = {
            "snapshot": window["space_snapshot"],
            "row_count": row_count,
            "first_date": rows[0].get("Date") if rows else None,
            "last_date": rows[-1].get("Date") if rows else None,
            "nonzero_volume_rows": nonzero_volume,
        }
        if row_count < 120 or nonzero_volume < 120:
            missing.append(label)
    return {
        "passed": not missing,
        "added_ticker": ADDED_TICKER,
        "coverage": coverage,
        "missing_or_thin_windows": missing,
    }


def _install_gsat_candidate_policy():
    original_generate = signal_engine.generate_signals
    original_enrich = risk_engine.enrich_signals
    original_size = portfolio_engine.size_signals
    signal_rows: list[dict[str, Any]] = []
    basket_adjustments: list[dict[str, Any]] = []
    perfect_adjustments: list[dict[str, Any]] = []
    near_perfect_adjustments: list[dict[str, Any]] = []
    peer_nonleader_breakout_adjustments: list[dict[str, Any]] = []
    basket_counts = Counter()
    perfect_counts = Counter()
    near_perfect_counts = Counter()
    peer_counts = Counter()
    day_counts = Counter()

    def generate_wrapper(features_dict, *args, **kwargs):
        basket = _reference_space_basket_momentum(features_dict)
        day_counts[basket["state"]] += 1
        signals = original_generate(features_dict, *args, **kwargs)
        for signal in signals:
            ticker = str(signal.get("ticker") or "").upper()
            if ticker not in CANDIDATE_SPACE_TICKERS:
                continue
            peer = _candidate_peer_momentum_state(signal, features_dict, basket)
            signal["space_basket_momentum_state"] = basket["state"]
            signal["space_basket_momentum_20d_pct"] = basket["value"]
            signal["space_basket_momentum_values"] = basket["values"]
            signal["space_candidate_pool"] = "accepted_plus_gsat"
            signal["space_candidate_pool_added_ticker"] = ticker == ADDED_TICKER
            signal["space_peer_momentum_state"] = peer["state"]
            signal["space_peer_momentum_20d_pct"] = peer["own_momentum_20d_pct"]
            signal["space_peer_excess_momentum_20d_pct"] = peer[
                "excess_momentum_20d_pct"
            ]
            signal["space_perfect_tqs_bucket"] = _is_perfect_tqs(signal)
            signal["space_near_perfect_tqs_trend_bucket"] = (
                _is_candidate_near_perfect_tqs_trend(signal)
            )
            row = {
                "ticker": ticker,
                "strategy": str(signal.get("strategy") or "").lower(),
                "space_basket_momentum_state": basket["state"],
                "space_basket_momentum_20d_pct": basket["value"],
                "space_peer_momentum_state": peer["state"],
                "space_peer_momentum_20d_pct": peer["own_momentum_20d_pct"],
                "space_peer_excess_momentum_20d_pct": peer[
                    "excess_momentum_20d_pct"
                ],
                "trade_quality_score": _round(signal.get("trade_quality_score"), 4),
                "confidence_score": _round(signal.get("confidence_score"), 4),
            }
            signal_rows.append(row)
            basket_counts[basket["state"]] += 1
            peer_counts[peer["state"]] += 1
            perfect_counts[str(signal["space_perfect_tqs_bucket"])] += 1
            near_perfect_counts[
                str(signal["space_near_perfect_tqs_trend_bucket"])
            ] += 1
        return signals

    def enrich_wrapper(signals, features_dict, atr_target_mult=None):
        enriched = original_enrich(
            signals,
            features_dict,
            atr_target_mult=atr_target_mult,
        )
        return [
            _retarget_if_candidate_space_trend(signal, features_dict)
            for signal in enriched
        ]

    def size_wrapper(signals, portfolio_value, risk_pct=None):
        sized = original_size(signals, portfolio_value, risk_pct=risk_pct)
        out = []
        for signal in sized:
            ticker = str(signal.get("ticker") or "").upper()
            strategy = str(signal.get("strategy") or "").lower()
            sizing = deepcopy(signal.get("sizing") or {})
            if ticker in CANDIDATE_SPACE_TICKERS and sizing:
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
                if signal.get("space_basket_momentum_state") == "positive":
                    _scale_sizing(
                        sizing,
                        ACCEPTED_SPACE_BASKET_POSITIVE_SCALAR,
                        portfolio_value,
                        "space_basket_positive_risk",
                    )
                    basket_adjustments.append(
                        _adjustment_row(
                            signal,
                            sizing,
                            shares_before,
                            ACCEPTED_SPACE_BASKET_POSITIVE_SCALAR,
                            "space_basket_positive",
                        )
                    )
                if _is_perfect_tqs(signal):
                    shares_after_basket = int(sizing.get("shares_to_buy") or 0)
                    _scale_sizing(
                        sizing,
                        ACCEPTED_SPACE_PERFECT_TQS_RISK_SCALAR,
                        portfolio_value,
                        "space_perfect_tqs_risk",
                    )
                    perfect_adjustments.append(
                        _adjustment_row(
                            signal,
                            sizing,
                            shares_after_basket,
                            ACCEPTED_SPACE_PERFECT_TQS_RISK_SCALAR,
                            "space_perfect_tqs_risk",
                        )
                    )
                if _is_candidate_near_perfect_tqs_trend(signal):
                    shares_after_perfect = int(sizing.get("shares_to_buy") or 0)
                    _scale_sizing(
                        sizing,
                        ACCEPTED_SPACE_NEAR_PERFECT_TQS_TREND_RISK_SCALAR,
                        portfolio_value,
                        "space_near_perfect_tqs_trend_risk",
                    )
                    near_perfect_adjustments.append(
                        _adjustment_row(
                            signal,
                            sizing,
                            shares_after_perfect,
                            ACCEPTED_SPACE_NEAR_PERFECT_TQS_TREND_RISK_SCALAR,
                            "space_near_perfect_tqs_trend_risk",
                        )
                    )
                if (
                    strategy == "breakout_long"
                    and signal.get("space_peer_momentum_state") == "nonleader"
                ):
                    shares_after_accepted = int(sizing.get("shares_to_buy") or 0)
                    _scale_sizing(
                        sizing,
                        PEER_NONLEADER_BREAKOUT_SCALAR,
                        portfolio_value,
                        "space_peer_nonleader_breakout_risk",
                    )
                    peer_nonleader_breakout_adjustments.append(
                        _adjustment_row(
                            signal,
                            sizing,
                            shares_after_accepted,
                            PEER_NONLEADER_BREAKOUT_SCALAR,
                            "space_peer_nonleader_breakout_risk",
                        )
                    )
                signal = {**signal, "sizing": sizing}
            out.append(signal)
        return out

    signal_engine.generate_signals = generate_wrapper
    risk_engine.enrich_signals = enrich_wrapper
    portfolio_engine.size_signals = size_wrapper
    return (
        original_generate,
        original_enrich,
        original_size,
        signal_rows,
        peer_nonleader_breakout_adjustments,
        near_perfect_adjustments,
        perfect_adjustments,
        basket_adjustments,
        peer_counts,
        near_perfect_counts,
        perfect_counts,
        basket_counts,
        day_counts,
    )


def _run_gsat_candidate_variant() -> dict[str, Any]:
    universe = sorted(set(get_universe()) | set(CANDIDATE_SPACE_TICKERS))
    (
        original_generate,
        original_enrich,
        original_size,
        signal_rows,
        peer_nonleader_breakout_adjustments,
        near_perfect_adjustments,
        perfect_adjustments,
        basket_adjustments,
        peer_counts,
        near_perfect_counts,
        perfect_counts,
        basket_counts,
        day_counts,
    ) = _install_gsat_candidate_policy()
    try:
        by_window = {}
        for label, window in WINDOWS.items():
            before_signals = len(signal_rows)
            before_peer = len(peer_nonleader_breakout_adjustments)
            before_near = len(near_perfect_adjustments)
            before_perfect = len(perfect_adjustments)
            before_basket = len(basket_adjustments)
            result = _run_window(window, universe, "space_snapshot")
            metrics = _metrics(result)
            candidate_trades = _space_trade_attribution_for(
                result,
                CANDIDATE_SPACE_TICKERS,
            )
            by_window[label] = {
                "metrics": metrics,
                "space_trade_attribution": candidate_trades,
                "added_ticker_trade_attribution": _space_trade_attribution_for(
                    result,
                    (ADDED_TICKER,),
                ),
                "candidate_signal_summary": _candidate_signal_summary(
                    signal_rows[before_signals:]
                ),
                "space_peer_nonleader_breakout_adjustment": _adjustment_summary(
                    peer_nonleader_breakout_adjustments[before_peer:]
                ),
                "space_near_perfect_tqs_trend_adjustment": _adjustment_summary(
                    near_perfect_adjustments[before_near:]
                ),
                "space_perfect_tqs_risk_adjustment": _adjustment_summary(
                    perfect_adjustments[before_perfect:]
                ),
                "space_basket_positive_adjustment": _adjustment_summary(
                    basket_adjustments[before_basket:]
                ),
                "space_peer_momentum_state_counts": dict(sorted(peer_counts.items())),
                "space_near_perfect_tqs_trend_signal_counts": dict(
                    sorted(near_perfect_counts.items())
                ),
                "space_perfect_tqs_signal_counts": dict(sorted(perfect_counts.items())),
                "space_basket_signal_state_counts": dict(sorted(basket_counts.items())),
                "space_basket_day_counts": dict(sorted(day_counts.items())),
            }
    finally:
        _restore_policy(original_generate, original_enrich, original_size)
    metrics_by_window = {label: row["metrics"] for label, row in by_window.items()}
    return {
        "variant": "accepted_exp013_plus_gsat_candidate",
        "added_ticker": ADDED_TICKER,
        "reference_space_tickers": list(REFERENCE_SPACE_TICKERS),
        "candidate_space_tickers": list(CANDIDATE_SPACE_TICKERS),
        "by_window": by_window,
        "aggregate": _aggregate(metrics_by_window),
    }


def _gate(variant: dict[str, Any], before: dict[str, Any], core: dict[str, Any]) -> dict[str, Any]:
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
    added_signal_count = sum(
        row["candidate_signal_summary"]["by_ticker"].get(ADDED_TICKER, 0)
        for row in variant["by_window"].values()
    )
    added_trade_count = sum(
        row["added_ticker_trade_attribution"]["trade_count"]
        for row in variant["by_window"].values()
    )
    passed = (
        aggregate_delta["expected_value_score_sum"] > 0
        and aggregate_delta["total_pnl_sum"] > 0
        and windows_ev_improved >= 2
        and windows_ev_regressed == 0
        and aggregate_delta["max_drawdown_pct_max"] <= 0.005
        and variant["aggregate"]["min_survival_rate"] >= 0.05
        and variant["aggregate"]["trade_count_sum"] >= 50
        and added_signal_count > 0
        and added_trade_count > 0
    )
    return {
        "passed": passed,
        "aggregate_delta_vs_before": aggregate_delta,
        "aggregate_delta_vs_core": aggregate_delta_vs_core,
        "by_window_delta_vs_before": by_window_delta,
        "windows_ev_improved_vs_before": windows_ev_improved,
        "windows_ev_regressed_vs_before": windows_ev_regressed,
        "max_drawdown_change_vs_before": aggregate_delta["max_drawdown_pct_max"],
        "added_ticker_signal_count": added_signal_count,
        "added_ticker_trade_count": added_trade_count,
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    after = payload["after_variant"]
    lines = [
        f"# {EXPERIMENT_ID} Space GSAT candidate pool",
        "",
        f"- Decision: `{payload['decision']}`",
        "- Single variable: add `GSAT` to the default-off official Space candidate pool.",
        f"- Aggregate EV delta vs accepted: `{payload['expected_value_score_delta']:+.4f}`",
        (
            "- Aggregate PnL delta vs accepted: "
            f"`${payload['delta_metrics']['aggregate']['total_pnl_sum']:+,.2f}`"
        ),
        f"- GSAT signals / trades: `{payload['gate4']['added_ticker_signal_count']}` / `{payload['gate4']['added_ticker_trade_count']}`",
        "",
        "## Three-Window Comparison",
        "",
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | GSAT signals | GSAT trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before_metrics = payload["before_metrics"][label]
        after_metrics = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        gsat_signals = after["by_window"][label]["candidate_signal_summary"][
            "by_ticker"
        ].get(ADDED_TICKER, 0)
        gsat_trades = after["by_window"][label]["added_ticker_trade_attribution"][
            "trade_count"
        ]
        lines.append(
            "| {label} | {before_ev:.4f} | {after_ev:.4f} | {delta_ev:+.4f} | "
            "{before_pnl:,.2f} | {after_pnl:,.2f} | {delta_pnl:+,.2f} | "
            "{trades} | {max_dd:.4f} | {survival:.4f} | {gsat_signals} | {gsat_trades} |".format(
                label=label,
                before_ev=before_metrics["expected_value_score"],
                after_ev=after_metrics["expected_value_score"],
                delta_ev=delta.get("expected_value_score", 0),
                before_pnl=before_metrics["total_pnl"],
                after_pnl=after_metrics["total_pnl"],
                delta_pnl=delta.get("total_pnl", 0),
                trades=after_metrics["trade_count"],
                max_dd=after_metrics["max_drawdown_pct"],
                survival=after_metrics["survival_rate"],
                gsat_signals=gsat_signals,
                gsat_trades=gsat_trades,
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


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": payload["experiment_id"],
        "status": payload["status"],
        "decision": payload["decision"],
        "changed_variable": payload["changed_variable"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["delta_metrics"]["aggregate"]["total_pnl_sum"],
        "gate4_passed": payload["gate4"]["passed"],
        "summary": payload["interpretation"],
        "artifact": str(Path("data") / "experiments" / EXPERIMENT_ID / f"{STEM}.json"),
    }


def run() -> dict[str, Any]:
    gate2 = _gate2_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")
    gsat_snapshot_gate = _field_check_gsat_snapshot()
    if not gsat_snapshot_gate["passed"]:
        raise RuntimeError(f"GSAT snapshot field check failed: {gsat_snapshot_gate}")

    core = _run_core_baseline()
    before = _run_accepted_exp013_variant("accepted_exp013_stack", 0.0)
    after = _run_gsat_candidate_variant()
    after["gate"] = _gate(after, before, core)

    accepted = after["gate"]["passed"]
    decision = (
        "accepted_default_off_space_gsat_candidate_pool"
        if accepted
        else "rejected_space_gsat_candidate_pool"
    )
    interpretation = (
        "GSAT improved the accepted default-off Space stack under the three-window "
        "gate. Promotion cannot be a backtest-only change: GSAT would need shared "
        "Space sleeve metadata and production observe-only wiring while live slots "
        "remain zero."
        if accepted
        else (
            "Adding GSAT to the official Space candidate pool did not clear the "
            "three-window gate on top of the accepted exp-20260512-013 stack. "
            "Do not admit GSAT from the frozen Space snapshots; candidate-pool "
            "expansion should wait for forward catalyst replacement evidence or "
            "a cleaner non-noisy operating-name field."
        )
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "candidate_pool_shadow_test",
        "changed_variable": "space_official_candidate_pool_membership_plus_gsat",
        "single_causal_variable": (
            "admit GSAT as one additional default-off official Space candidate; "
            "accepted six-name reference basket and all risk/exit/ranking logic stay fixed"
        ),
        "hypothesis": (
            "After recent Space TQS, peer, volume, breadth, and geometry retunes "
            "were exhausted or rejected, the highest-value orthogonal alpha is "
            "candidate-pool quality. GSAT is the only available satellite-"
            "connectivity operating name in the augmented snapshots that is not "
            "a benchmark ETF, mature satcom breadth ticker, missing-data name, "
            "or quarantined meme ticker."
        ),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate pool: allow GSAT to compete for default-off Space trades "
                "under the accepted exp-20260512-013 risk ladder."
            ),
            "2_history_check": {
                "exp-20260511-026": "Rejected mature satcom breadth, so IRDM/VSAT/SATS stay excluded.",
                "exp-20260510-028": "HAWK failed OHLCV fetch; not eligible for candidate expansion.",
                "space_registry": "ARKX/UFO are benchmarks and SPCE is quarantined, not candidate trades.",
                "exp-20260512-014": "Rejected peer-nonleader trend haircut.",
                "exp-20260512-015": "Rejected 52w proximity scalar.",
                "exp-20260512-016": "Rejected basket breadth scalar.",
                "exp-20260512-019": "Rejected execution-adjusted R/R scalar.",
                "exp-20260512-020/021": "Rejected breakout volume-confirmation scalar.",
            },
            "3_single_causal_variable": (
                "Only GSAT membership changes. Reference basket, accepted Space "
                "risk scalars, TQS buckets, targets, stops, ranking, add-ons, "
                "LLM/news, and live slots stay fixed."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; require positive aggregate "
                "EV/PnL, at least 2/3 improved EV windows, no EV-regressed window, "
                "max drawdown drift <= 0.5 pp, survival >= 5%, >=50 total trades, "
                "and nonzero GSAT signals/trades."
            ),
            "5_reproducibility": (
                "This script reruns core, accepted exp-20260512-013 Space stack, "
                "and the GSAT candidate variant across the canonical augmented "
                "Space snapshots."
            ),
        },
        "parameters": {
            "added_ticker": ADDED_TICKER,
            "reference_space_tickers": list(REFERENCE_SPACE_TICKERS),
            "candidate_space_tickers": list(CANDIDATE_SPACE_TICKERS),
            "reference_basket_for_gsat": (
                "accepted six-name official Space basket; GSAT does not change "
                "basket state or peer average in this test"
            ),
            "accepted_before_experiment": "exp-20260512-013",
            "accepted_space_peer_nonleader_breakout_scalar": (
                PEER_NONLEADER_BREAKOUT_SCALAR
            ),
            "accepted_space_basket_positive_scalar": ACCEPTED_SPACE_BASKET_POSITIVE_SCALAR,
            "accepted_space_perfect_tqs_risk_scalar": (
                ACCEPTED_SPACE_PERFECT_TQS_RISK_SCALAR
            ),
            "accepted_space_near_perfect_tqs_trend_risk_scalar": (
                ACCEPTED_SPACE_NEAR_PERFECT_TQS_TREND_RISK_SCALAR
            ),
            "near_perfect_tqs_floor": ACCEPTED_SPACE_NEAR_PERFECT_TQS_SCORE_FLOOR,
            "near_perfect_tqs_ceiling": ACCEPTED_SPACE_NEAR_PERFECT_TQS_SCORE_CEILING,
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
                "accepted six-name reference Space basket",
                "base Space risk scalar",
                "PL/BKSY breakout 0.1x haircut",
                "RKLB/ASTS trend 1.25x top-up",
                "accepted Space basket-positive 1.10x scalar",
                "accepted perfect-TQS 1.50x risk scalar",
                "accepted near-perfect trend TQS 1.10x scalar",
                "accepted peer-nonleader breakout 0.00x scalar",
                "accepted Space trend targets",
                "breakout stop and target widths",
                "core production universe",
                "core signal generation",
                "entry filters",
                "ranking",
                "MAX_POSITIONS",
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
            "docs/backtesting.md canonical three fixed windows. Core uses canonical "
            "snapshots; Space variants use exp-20260510-028 augmented Space snapshots. "
            "The accepted_before variant reproduces exp-20260512-013 policy semantics."
        ),
        "gate1": {
            "core_baseline": core["aggregate"],
            "accepted_before_metrics": before["aggregate"],
            "known_bias": (
                "Space candidate snapshots are frozen historical replay copies built "
                "from a 2026-05-10 research universe; any accepted candidate-pool "
                "change must remain default-off/observe-only until forward evidence matures."
            ),
        },
        "gate2": {
            "open_positions": gate2,
            "gsat_snapshot_coverage": gsat_snapshot_gate,
            "passed": gate2["passed"] and gsat_snapshot_gate["passed"],
        },
        "gate3": {
            "new_filter_added": False,
            "candidate_pool_expanded": True,
            "min_survival_rate_after": after["aggregate"]["min_survival_rate"],
            "passed": after["aggregate"]["min_survival_rate"] >= 0.05,
        },
        "core_baseline_metrics": core["by_window"],
        "core_aggregate": core["aggregate"],
        "before_variant": before,
        "after_variant": after,
        "before_metrics": {
            "aggregate": before["aggregate"],
            **{label: row["metrics"] for label, row in before["by_window"].items()},
        },
        "after_metrics": {
            "aggregate": after["aggregate"],
            **{label: row["metrics"] for label, row in after["by_window"].items()},
        },
        "delta_metrics": {
            "aggregate": after["gate"]["aggregate_delta_vs_before"],
            "by_window": after["gate"]["by_window_delta_vs_before"],
        },
        "expected_value_score_delta": after["gate"]["aggregate_delta_vs_before"][
            "expected_value_score_sum"
        ],
        "gate_results": after["gate"],
        "gate4": after["gate"],
        "llm_metrics": {
            "used_llm": False,
            "why_not_llm_soft_ranking": (
                "Space event-state forward data remains below the closed-decision "
                "gate; this run uses deterministic candidate-pool replay instead."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "daily_report_metadata_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_orders": False,
            "live_slots_changed": False,
            "live_slots": 0,
            "promotion_requirement_if_accepted": (
                "Add GSAT through shared Space sleeve metadata/helpers and production "
                "observe-only wiring before retaining any positive variant."
            ),
        },
        "decision_rationale": interpretation,
        "interpretation": interpretation,
        "rejection_reason": None if accepted else interpretation,
        "next_evidence_needed": (
            "If rejected, do not add GSAT from this frozen snapshot sample. The "
            "next Space candidate-pool test should require new forward official "
            "catalyst evidence or a cleaner operating-name field, not adjacent ticker noise."
        ),
        "related_files": [
            "quant/experiments/exp_20260512_023_space_gsat_candidate_pool.py",
            "data/experiments/exp-20260512-023/space_gsat_candidate_pool.json",
            "experiments/logs/exp-20260512-023.json",
            "experiments/tickets/exp-20260512-023.json",
            "experiments/artifacts/exp-20260512-023_space_gsat_candidate_pool.md",
            "docs/experiment_log.jsonl",
        ],
        "why_not_other_changes": (
            "LLM soft-ranking/event scoring is underpowered by immature forward "
            "closed decisions. Recent Space retunes around peer trend, 52w proximity, "
            "basket breadth, execution-adjusted R/R, and breakout volume were rejected. "
            "Mature satcom, benchmarks, missing-data names, and quarantined tickers "
            "are intentionally excluded."
        ),
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
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
    _write_json(artifact_path, payload)
    _write_json(log_path, payload)
    _write_json(ticket_path, _ticket(payload))
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_for_this_experiment(
        PROJECT_ROOT / "docs" / "experiment_log.jsonl",
        payload,
    )


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
                "gsat_signals": result["gate4"]["added_ticker_signal_count"],
                "gsat_trades": result["gate4"]["added_ticker_trade_count"],
                "gate4_passed": result["gate4"]["passed"],
            },
            indent=2,
            sort_keys=True,
        )
    )
