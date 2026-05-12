"""exp-20260512-005: Space perfect-TQS trend target width.

Tests whether the accepted default-off Space sleeve should give wider targets
only to official Space trend signals that already reached the capped
trade-quality-score bucket. This keeps the accepted perfect-TQS risk top-up and
does not add tickers, change stops, or touch LLM/news boundaries.
"""

from __future__ import annotations

import json
import logging
import math
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
    _space_basket_momentum,
    _space_trade_attribution,
)
from data_layer import get_universe
import portfolio_engine
import risk_engine
import signal_engine


logging.basicConfig(level=logging.WARNING)

EXPERIMENT_ID = "exp-20260512-005"
STEM = "space_perfect_tqs_trend_target"
ACCEPTED_SPACE_BASKET_POSITIVE_SCALAR = 1.10
ACCEPTED_SPACE_PERFECT_TQS_RISK_SCALAR = 1.50
PERFECT_TQS_TARGET_ATR_MULTS = (6.0, 7.0, 8.0)


def _is_perfect_tqs(signal: dict[str, Any]) -> bool:
    value = _round(signal.get("trade_quality_score"), 6)
    return value is not None and value >= 1.0


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl_once(path: Path, payload: dict[str, Any]) -> None:
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


def _target_adjustment_row(
    signal: dict[str, Any],
    *,
    target_mult: float,
    accepted_target_mult: float,
) -> dict[str, Any]:
    return {
        "ticker": str(signal.get("ticker") or "").upper(),
        "strategy": str(signal.get("strategy") or "").lower(),
        "space_basket_momentum_state": signal.get("space_basket_momentum_state"),
        "space_basket_momentum_20d_pct": signal.get("space_basket_momentum_20d_pct"),
        "accepted_target_atr_mult": accepted_target_mult,
        "perfect_tqs_target_atr_mult": target_mult,
        "trade_quality_score": _round(signal.get("trade_quality_score"), 4),
        "confidence_score": _round(signal.get("confidence_score"), 4),
    }


def _accepted_target_mult(ticker: str) -> float:
    if ticker in LAUNCH_CONNECTIVITY_TICKERS:
        return LAUNCH_CONNECTIVITY_TREND_TARGET_ATR_MULT
    return BASE_SPACE_TREND_TARGET_ATR_MULT


def _retarget_if_space_trend_with_perfect_tqs(
    signal: dict[str, Any],
    features_dict: dict[str, dict[str, Any]],
    perfect_tqs_target_mult: float | None,
    target_adjustments: list[dict[str, Any]],
) -> dict[str, Any]:
    ticker = str(signal.get("ticker") or "").upper()
    strategy = str(signal.get("strategy") or "")
    if ticker not in OFFICIAL_SPACE_TICKERS or strategy != "trend_long":
        return signal
    atr = (features_dict.get(ticker) or {}).get("atr")
    if not atr:
        return signal
    target_mult = _accepted_target_mult(ticker)
    scope = "accepted_exp004_target_semantics"
    if perfect_tqs_target_mult is not None and _is_perfect_tqs(signal):
        target_mult = perfect_tqs_target_mult
        scope = "perfect_tqs_trend_target_test"
        target_adjustments.append(
            _target_adjustment_row(
                signal,
                target_mult=perfect_tqs_target_mult,
                accepted_target_mult=_accepted_target_mult(ticker),
            )
        )
    updated = risk_engine._retarget_signal_with_atr_mult(signal, atr, target_mult)
    updated["space_trend_target_scope"] = scope
    updated["space_trend_target_atr_mult"] = target_mult
    return updated


def _install_space_policy(perfect_tqs_target_mult: float | None):
    original_generate = signal_engine.generate_signals
    original_enrich = risk_engine.enrich_signals
    original_size = portfolio_engine.size_signals
    target_adjustments: list[dict[str, Any]] = []
    risk_adjustments: list[dict[str, Any]] = []
    basket_adjustments: list[dict[str, Any]] = []
    perfect_tqs_signal_counts = Counter()
    basket_state_counts = Counter()
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
            signal["space_perfect_tqs_bucket"] = _is_perfect_tqs(signal)
            basket_state_counts[basket["state"]] += 1
            perfect_tqs_signal_counts[str(signal["space_perfect_tqs_bucket"])] += 1
        return signals

    def enrich_wrapper(signals, features_dict, atr_target_mult=None):
        enriched = original_enrich(
            signals,
            features_dict,
            atr_target_mult=atr_target_mult,
        )
        return [
            _retarget_if_space_trend_with_perfect_tqs(
                signal,
                features_dict,
                perfect_tqs_target_mult,
                target_adjustments,
            )
            for signal in enriched
        ]

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
                if basket_positive:
                    _scale_sizing(
                        sizing,
                        ACCEPTED_SPACE_BASKET_POSITIVE_SCALAR,
                        portfolio_value,
                        "space_basket_positive_risk",
                    )
                    basket_adjustments.append(
                        _sizing_adjustment_row(
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
                    risk_adjustments.append(
                        _sizing_adjustment_row(
                            signal,
                            sizing,
                            shares_after_basket,
                            ACCEPTED_SPACE_PERFECT_TQS_RISK_SCALAR,
                            "space_perfect_tqs_risk",
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
        target_adjustments,
        risk_adjustments,
        basket_adjustments,
        perfect_tqs_signal_counts,
        basket_state_counts,
        day_counts,
    )


def _sizing_adjustment_row(
    signal: dict[str, Any],
    sizing: dict[str, Any],
    shares_before: int,
    scalar: float,
    marker: str,
) -> dict[str, Any]:
    return {
        "ticker": str(signal.get("ticker") or "").upper(),
        "strategy": str(signal.get("strategy") or "").lower(),
        "marker": marker,
        "space_basket_momentum_state": signal.get("space_basket_momentum_state"),
        "space_basket_momentum_20d_pct": signal.get("space_basket_momentum_20d_pct"),
        "scalar": scalar,
        "shares_before_scalar": shares_before,
        "shares_after_scalar": int(sizing.get("shares_to_buy") or 0),
        "trade_quality_score": _round(signal.get("trade_quality_score"), 4),
        "confidence_score": _round(signal.get("confidence_score"), 4),
    }


def _target_adjustment_summary(adjustments: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "adjusted_signal_count": len(adjustments),
        "by_strategy": dict(
            sorted(Counter(row["strategy"] for row in adjustments).items())
        ),
        "by_ticker": dict(sorted(Counter(row["ticker"] for row in adjustments).items())),
        "sample_adjusted": adjustments[:12],
    }


def _run_variant(name: str, perfect_tqs_target_mult: float | None) -> dict[str, Any]:
    universe = sorted(set(get_universe()) | set(OFFICIAL_SPACE_TICKERS))
    (
        original_generate,
        original_enrich,
        original_size,
        target_adjustments,
        risk_adjustments,
        basket_adjustments,
        perfect_counts,
        basket_counts,
        day_counts,
    ) = _install_space_policy(perfect_tqs_target_mult)
    try:
        by_window = {}
        for label, window in WINDOWS.items():
            before_target = len(target_adjustments)
            before_risk = len(risk_adjustments)
            before_basket = len(basket_adjustments)
            result = _run_window(window, universe, "space_snapshot")
            metrics = _metrics(result)
            by_window[label] = {
                "metrics": metrics,
                "space_trade_attribution": _space_trade_attribution(result),
                "space_perfect_tqs_target_adjustment": _target_adjustment_summary(
                    target_adjustments[before_target:]
                ),
                "space_perfect_tqs_risk_adjustment": _adjustment_summary(
                    risk_adjustments[before_risk:]
                ),
                "space_basket_positive_adjustment": _adjustment_summary(
                    basket_adjustments[before_basket:]
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
        "space_perfect_tqs_trend_target_atr_mult": perfect_tqs_target_mult,
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
        row["space_perfect_tqs_target_adjustment"]["adjusted_signal_count"]
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
        "space_perfect_tqs_target_adjusted_signal_count": adjusted_count,
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    lines = [
        f"# {EXPERIMENT_ID} Space perfect-TQS trend target",
        "",
        f"- Decision: `{payload['decision']}`",
        "- Single variable: target ATR multiple for official Space trend signals whose TQS is capped at 1.0.",
        f"- Best variant: `{best['variant']}`",
        f"- Aggregate EV delta vs accepted: `{payload['expected_value_score_delta']:+.4f}`",
        (
            "- Aggregate PnL delta vs accepted: "
            f"`${payload['delta_metrics']['aggregate']['total_pnl_sum']:+,.2f}`"
        ),
        "",
        "## Sweep",
        "",
        "| Variant | Target ATR | Gate | dEV | dPnL | Improved windows | Regressed windows | Adjusted signals |",
        "|---|---:|---|---:|---:|---:|---:|---:|",
    ]
    for name, variant in payload["variants"].items():
        gate = variant["gate"]
        delta = gate["aggregate_delta_vs_before"]
        target = variant["space_perfect_tqs_trend_target_atr_mult"]
        target_text = "accepted" if target is None else f"{target:.1f}"
        lines.append(
            f"| {name} | {target_text} | {'pass' if gate['passed'] else 'fail'} | "
            f"{delta['expected_value_score_sum']:+.4f} | "
            f"{delta['total_pnl_sum']:+,.2f} | "
            f"{gate['windows_ev_improved_vs_before']} | "
            f"{gate['windows_ev_regressed_vs_before']} | "
            f"{gate['space_perfect_tqs_target_adjusted_signal_count']} |"
        )
    lines.extend(
        [
            "",
            "## Best Three-Window Comparison",
            "",
            "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Perfect-TQS target signals |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        adjusted = best["by_window"][label]["space_perfect_tqs_target_adjustment"][
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
    lines.extend(["", "## Interpretation", "", payload["interpretation"], ""])
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
        "accepted_exp004_stack": _run_variant("accepted_exp004_stack", None)
    }
    for target_mult in PERFECT_TQS_TARGET_ATR_MULTS:
        name = f"perfect_tqs_target_{str(target_mult).replace('.', '_')}"
        variants[name] = _run_variant(name, target_mult)

    before = variants["accepted_exp004_stack"]
    for variant in variants.values():
        variant["gate"] = _gate(variant, before, core)

    candidates = [
        variant
        for name, variant in variants.items()
        if name != "accepted_exp004_stack"
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
        "accepted_default_off_space_perfect_tqs_trend_target"
        if accepted
        else "rejected_space_perfect_tqs_trend_target"
    )
    interpretation = (
        "The capped/perfect TQS bucket supports a wider trend target inside the "
        "default-off Space stack. Keep it as metadata/helper only while Space "
        "live slots remain zero."
        if accepted
        else (
            "Wider trend targets for the capped/perfect TQS Space bucket did not "
            "beat the accepted exp-20260512-004 stack under the three-window gate. "
            "The current evidence supports quality-conditioned risk, not another "
            "same-sample target-width extension."
        )
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "exit_target_shadow_sweep",
        "changed_variable": "space_perfect_tqs_trend_target_atr_mult",
        "single_causal_variable": (
            "target ATR multiple for official Space trend_long signals whose "
            "trade_quality_score is capped at 1.0"
        ),
        "hypothesis": (
            "After exp-20260512-004 showed capped Space TQS supports more risk, "
            "the same high-quality trend bucket may also support a wider target "
            "without adding tickers, changing stops, or relying on LLM soft-ranking."
        ),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "exit/capital lifecycle alpha: widen only official Space trend "
                "targets when the existing trade_quality_score reaches 1.0."
            ),
            "2_history_check": {
                "exp-20260511-105": "Accepted RKLB/ASTS launch-connectivity 7 ATR trend target.",
                "exp-20260511-106": "Rejected LUNR/RDW lunar/manufacturing 7 ATR target.",
                "exp-20260511-111": "Rejected PL/BKSY data-vendor trend target widening.",
                "exp-20260512-004": "Accepted perfect-TQS risk top-up; this test changes target width instead of risk.",
            },
            "3_single_causal_variable": (
                "space_perfect_tqs_trend_target_atr_mult; candidate pool, risk "
                "scalars, stops, ranking, add-ons, LLM/news, and live slots stay fixed."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; require positive aggregate "
                "EV/PnL, at least 2/3 improved EV windows, no EV-regressed window, "
                "max drawdown drift <= 0.5 pp, survival >= 5%, and nonzero adjusted signals."
            ),
            "5_reproducibility": (
                "This script reruns core, accepted exp-20260512-004 Space stack, "
                "and each perfect-TQS target variant across the canonical augmented snapshots."
            ),
        },
        "parameters": {
            "official_space_tickers": list(OFFICIAL_SPACE_TICKERS),
            "accepted_before_experiment": "exp-20260512-004",
            "accepted_space_basket_positive_scalar": ACCEPTED_SPACE_BASKET_POSITIVE_SCALAR,
            "accepted_space_perfect_tqs_risk_scalar": (
                ACCEPTED_SPACE_PERFECT_TQS_RISK_SCALAR
            ),
            "tested_perfect_tqs_target_atr_mult": list(PERFECT_TQS_TARGET_ATR_MULTS),
            "trade_quality_score_bucket": "capped_score_equals_1_0",
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
            "The accepted_before variant reproduces exp-20260512-004 policy semantics."
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
            "space_quality_bucket_added": True,
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
                "gate; this run uses an existing deterministic quality-score field."
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
            "If rejected, do not retry nearby perfect-TQS Space target widths on the "
            "same frozen snapshots. Future Space lifecycle work should use forward "
            "event replacement value or a genuinely new catalyst-quality field."
        ),
        "related_files": [
            "quant/experiments/exp_20260512_005_space_perfect_tqs_trend_target.py",
            "data/experiments/exp-20260512-005/space_perfect_tqs_trend_target.json",
            "docs/experiments/logs/exp-20260512-005.json",
            "docs/experiments/tickets/exp-20260512-005.json",
            "docs/experiments/artifacts/exp-20260512-005_space_perfect_tqs_trend_target.md",
            "docs/experiment_log.jsonl",
        ],
        "why_not_other_changes": (
            "LLM soft-ranking and event-bucket scoring are still sample-limited; "
            "mature satcom breadth, theme ETF timing, one-slot capacity, breakout "
            "geometry, data-vendor trend targets, and lunar/manufacturing target "
            "broadening already failed."
        ),
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    out_dir = PROJECT_ROOT / "data" / "experiments" / EXPERIMENT_ID
    artifact_path = out_dir / f"{STEM}.json"
    log_path = PROJECT_ROOT / "docs" / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
    ticket_path = PROJECT_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
    md_path = (
        PROJECT_ROOT
        / "docs"
        / "experiments"
        / "artifacts"
        / f"{EXPERIMENT_ID}_{STEM}.md"
    )
    _write_json(artifact_path, payload)
    _write_json(log_path, payload)
    _write_json(ticket_path, _ticket(payload))
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_artifact_markdown(payload), encoding="utf-8")
    _append_jsonl_once(PROJECT_ROOT / "docs" / "experiment_log.jsonl", payload)


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
