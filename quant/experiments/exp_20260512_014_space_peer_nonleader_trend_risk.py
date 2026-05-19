"""exp-20260512-014: Space peer-nonleader trend risk allocation.

Tests whether official Space trend signals whose own 20-day momentum lags the
official Space basket average should receive a risk haircut. This starts from
the accepted exp-20260512-013 default-off Space stack and changes only the
trend peer-nonleader risk scalar.
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
    WINDOWS,
    _adjustment_summary,
    _aggregate,
    _aggregate_delta,
    _delta,
    _gate2_open_positions,
    _metrics,
    _restore_policy,
    _retarget_if_space_trend,
    _run_core_baseline,
    _run_window,
    _safe,
    _scale_sizing,
    _space_basket_momentum,
    _space_trade_attribution,
    _write_json,
)
from exp_20260512_009_space_peer_momentum_leader_risk import (
    ACCEPTED_SPACE_BASKET_POSITIVE_SCALAR,
    ACCEPTED_SPACE_NEAR_PERFECT_TQS_SCORE_CEILING,
    ACCEPTED_SPACE_NEAR_PERFECT_TQS_SCORE_FLOOR,
    ACCEPTED_SPACE_NEAR_PERFECT_TQS_TREND_RISK_SCALAR,
    ACCEPTED_SPACE_PERFECT_TQS_RISK_SCALAR,
    _adjustment_row,
    _is_near_perfect_tqs_trend,
    _is_perfect_tqs,
    _peer_momentum_state,
)
from data_layer import get_universe
import portfolio_engine
import risk_engine
import signal_engine


logging.basicConfig(level=logging.WARNING)

EXPERIMENT_ID = "exp-20260512-014"
STEM = "space_peer_nonleader_trend_risk"
ACCEPTED_SPACE_PEER_NONLEADER_BREAKOUT_RISK_SCALAR = 0.0
PEER_NONLEADER_TREND_SCALARS = (0.0, 0.25, 0.5, 0.75)


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


def _install_space_policy(peer_nonleader_trend_scalar: float):
    original_generate = signal_engine.generate_signals
    original_enrich = risk_engine.enrich_signals
    original_size = portfolio_engine.size_signals
    basket_adjustments: list[dict[str, Any]] = []
    perfect_adjustments: list[dict[str, Any]] = []
    near_perfect_adjustments: list[dict[str, Any]] = []
    peer_nonleader_breakout_adjustments: list[dict[str, Any]] = []
    peer_nonleader_trend_adjustments: list[dict[str, Any]] = []
    basket_counts = Counter()
    perfect_counts = Counter()
    near_perfect_counts = Counter()
    peer_counts = Counter()
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
            peer = _peer_momentum_state(signal)
            signal["space_peer_momentum_state"] = peer["state"]
            signal["space_peer_momentum_20d_pct"] = peer["own_momentum_20d_pct"]
            signal["space_peer_excess_momentum_20d_pct"] = peer[
                "excess_momentum_20d_pct"
            ]
            signal["space_perfect_tqs_bucket"] = _is_perfect_tqs(signal)
            signal["space_near_perfect_tqs_trend_bucket"] = (
                _is_near_perfect_tqs_trend(signal)
            )
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
                if _is_near_perfect_tqs_trend(signal):
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
                        ACCEPTED_SPACE_PEER_NONLEADER_BREAKOUT_RISK_SCALAR,
                        portfolio_value,
                        "space_peer_nonleader_breakout_risk",
                    )
                    peer_nonleader_breakout_adjustments.append(
                        _adjustment_row(
                            signal,
                            sizing,
                            shares_after_accepted,
                            ACCEPTED_SPACE_PEER_NONLEADER_BREAKOUT_RISK_SCALAR,
                            "space_peer_nonleader_breakout_risk",
                        )
                    )
                if (
                    strategy == "trend_long"
                    and signal.get("space_peer_momentum_state") == "nonleader"
                    and peer_nonleader_trend_scalar != 1.0
                ):
                    shares_after_accepted = int(sizing.get("shares_to_buy") or 0)
                    _scale_sizing(
                        sizing,
                        peer_nonleader_trend_scalar,
                        portfolio_value,
                        "space_peer_nonleader_trend_risk",
                    )
                    peer_nonleader_trend_adjustments.append(
                        _adjustment_row(
                            signal,
                            sizing,
                            shares_after_accepted,
                            peer_nonleader_trend_scalar,
                            "space_peer_nonleader_trend_risk",
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
        peer_nonleader_trend_adjustments,
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


def _run_variant(name: str, peer_nonleader_trend_scalar: float) -> dict[str, Any]:
    universe = sorted(set(get_universe()) | set(OFFICIAL_SPACE_TICKERS))
    (
        original_generate,
        original_enrich,
        original_size,
        peer_nonleader_trend_adjustments,
        peer_nonleader_breakout_adjustments,
        near_perfect_adjustments,
        perfect_adjustments,
        basket_adjustments,
        peer_counts,
        near_perfect_counts,
        perfect_counts,
        basket_counts,
        day_counts,
    ) = _install_space_policy(peer_nonleader_trend_scalar)
    try:
        by_window = {}
        for label, window in WINDOWS.items():
            before_trend = len(peer_nonleader_trend_adjustments)
            before_breakout = len(peer_nonleader_breakout_adjustments)
            before_near = len(near_perfect_adjustments)
            before_perfect = len(perfect_adjustments)
            before_basket = len(basket_adjustments)
            result = _run_window(window, universe, "space_snapshot")
            metrics = _metrics(result)
            by_window[label] = {
                "metrics": metrics,
                "space_trade_attribution": _space_trade_attribution(result),
                "space_peer_nonleader_trend_adjustment": _adjustment_summary(
                    peer_nonleader_trend_adjustments[before_trend:]
                ),
                "space_peer_nonleader_breakout_adjustment": _adjustment_summary(
                    peer_nonleader_breakout_adjustments[before_breakout:]
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
        "variant": name,
        "space_peer_nonleader_trend_scalar": peer_nonleader_trend_scalar,
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
    adjusted_count = sum(
        row["space_peer_nonleader_trend_adjustment"]["adjusted_signal_count"]
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
        and adjusted_count > 0
    )
    return {
        "passed": passed,
        "aggregate_delta_vs_before": aggregate_delta,
        "aggregate_delta_vs_core": aggregate_delta_vs_core,
        "by_window_delta_vs_before": by_window_delta,
        "windows_ev_improved_vs_before": windows_ev_improved,
        "windows_ev_regressed_vs_before": windows_ev_regressed,
        "max_drawdown_change_vs_before": aggregate_delta["max_drawdown_pct_max"],
        "space_peer_nonleader_trend_adjusted_signal_count": adjusted_count,
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    lines = [
        f"# {EXPERIMENT_ID} Space peer-nonleader trend risk",
        "",
        f"- Decision: `{payload['decision']}`",
        (
            "- Single variable: risk scalar for official Space trend_long signals "
            "whose own 20d momentum is not above the official Space basket average."
        ),
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
            f"| {name} | {variant['space_peer_nonleader_trend_scalar']:.2f} | "
            f"{'pass' if gate['passed'] else 'fail'} | "
            f"{delta['expected_value_score_sum']:+.4f} | "
            f"{delta['total_pnl_sum']:+,.2f} | "
            f"{gate['windows_ev_improved_vs_before']} | "
            f"{gate['windows_ev_regressed_vs_before']} | "
            f"{gate['space_peer_nonleader_trend_adjusted_signal_count']} |"
        )
    lines.extend(
        [
            "",
            "## Best Three-Window Comparison",
            "",
            "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Nonleader trend signals |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        adjusted = best["by_window"][label][
            "space_peer_nonleader_trend_adjustment"
        ]["adjusted_signal_count"]
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


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
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
        "artifact": str(Path("data") / "experiments" / EXPERIMENT_ID / f"{STEM}.json"),
    }


def run() -> dict[str, Any]:
    gate2 = _gate2_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    core = _run_core_baseline()
    variants = {
        "accepted_exp013_stack": _run_variant("accepted_exp013_stack", 1.0)
    }
    for scalar in PEER_NONLEADER_TREND_SCALARS:
        name = f"peer_nonleader_trend_{str(scalar).replace('.', '_')}"
        variants[name] = _run_variant(name, scalar)

    before = variants["accepted_exp013_stack"]
    for variant in variants.values():
        variant["gate"] = _gate(variant, before, core)

    candidates = [
        variant
        for name, variant in variants.items()
        if name != "accepted_exp013_stack"
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
        "accepted_default_off_space_peer_nonleader_trend_risk"
        if accepted
        else "rejected_space_peer_nonleader_trend_risk"
    )
    interpretation = (
        "Official Space peer-nonleader trend signals improved the accepted "
        "default-off Space stack under the three-window gate. Promotion should "
        "stay default-off metadata/helper only because Space live slots remain zero."
        if accepted
        else (
            "Peer-nonleader status did not identify a robust Space trend haircut "
            "on top of the accepted exp-20260512-013 stack. Keep the accepted "
            "trend risk ladder unchanged; future Space trend work needs forward "
            "catalyst replacement value or a genuinely new catalyst-quality field."
        )
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "risk_allocation_shadow_sweep",
        "changed_variable": "space_peer_nonleader_trend_risk_scalar",
        "single_causal_variable": (
            "risk scalar for official Space trend_long signals whose own 20d "
            "momentum is not above the official Space basket equal-weight 20d momentum"
        ),
        "hypothesis": (
            "After peer-relative leadership separated weak Space breakouts, the "
            "same ex-ante peer-nonleader state may also identify trend_long "
            "signals that should receive less risk without changing the Space "
            "candidate pool, targets, stops, ranking, or LLM boundary."
        ),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation: haircut only official Space trend_long signals "
                "whose own 20d momentum is <= the official Space basket average."
            ),
            "2_history_check": {
                "exp-20260512-013": (
                    "Accepted peer-nonleader breakout zero-risk metadata; this "
                    "tests trend_long only, not the breakout scalar."
                ),
                "exp-20260512-009": (
                    "Rejected peer-leader broad top-up due drawdown; this tests "
                    "a nonleader trend haircut instead of broad leader leverage."
                ),
                "exp-20260512-008": "Accepted near-perfect TQS trend risk top-up.",
                "exp-20260512-010": "Rejected near-perfect TQS breakout scalar.",
                "exp-20260511-106": "Rejected LUNR/RDW trend target widening.",
                "exp-20260511-111": "Rejected PL/BKSY trend target widening.",
            },
            "3_single_causal_variable": (
                "space_peer_nonleader_trend_risk_scalar; candidate pool, accepted "
                "Space risk scalars, targets, stops, ranking, add-ons, LLM/news, "
                "and live slots stay fixed."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; require positive aggregate "
                "EV/PnL, at least 2/3 improved EV windows, no EV-regressed window, "
                "max drawdown drift <= 0.5 pp, survival >= 5%, and nonzero adjusted signals."
            ),
            "5_reproducibility": (
                "This script reruns core, accepted exp-20260512-013 Space stack, "
                "and each peer-nonleader trend scalar across the canonical augmented snapshots."
            ),
        },
        "parameters": {
            "official_space_tickers": list(OFFICIAL_SPACE_TICKERS),
            "accepted_before_experiment": "exp-20260512-013",
            "space_peer_momentum_field": SPACE_BASKET_MOMENTUM_FIELD,
            "peer_nonleader_definition": (
                "ticker momentum_20d_pct <= equal-weight official Space basket momentum_20d_pct"
            ),
            "tested_peer_nonleader_trend_scalars": list(
                PEER_NONLEADER_TREND_SCALARS
            ),
            "accepted_space_peer_nonleader_breakout_risk_scalar": (
                ACCEPTED_SPACE_PEER_NONLEADER_BREAKOUT_RISK_SCALAR
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
                "official Space candidate pool",
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
                "from a 2026-05-10 research universe; any accepted change must remain "
                "default-off metadata until forward evidence matures."
            ),
        },
        "gate2": gate2,
        "gate3": {
            "new_core_filter_added": False,
            "space_peer_momentum_state_added": True,
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
                "Space event-state forward data remains below the closed-decision "
                "gate; this run uses deterministic OHLCV peer momentum."
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
            "If rejected, do not retry nearby peer-nonleader Space trend scalars "
            "on the same frozen snapshots. Future Space trend work should use "
            "forward event replacement value or a genuinely new catalyst-quality field."
        ),
        "related_files": [
            "quant/experiments/exp_20260512_014_space_peer_nonleader_trend_risk.py",
            "data/experiments/exp-20260512-014/space_peer_nonleader_trend_risk.json",
            "experiments/logs/exp-20260512-014.json",
            "experiments/tickets/exp-20260512-014.json",
            "experiments/artifacts/exp-20260512-014_space_peer_nonleader_trend_risk.md",
            "docs/experiment_log.jsonl",
        ],
        "why_not_other_changes": (
            "LLM soft-ranking and Space event-bucket scoring are still sample-limited; "
            "SEC financial-report nearby lifecycle/notional/cohort/entry-gap variants "
            "are now saturated or waiting on forward outcomes; mature satcom breadth, "
            "theme ETF timing, Space target/stop geometry, and TQS breakout variants "
            "already failed or were accepted as fixed context."
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
                "best_variant": result["best_variant"]["variant"],
                "gate4_passed": result["gate4"]["passed"],
            },
            indent=2,
            sort_keys=True,
        )
    )
