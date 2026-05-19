"""exp-20260512-021: Space breakout volume-confirmation risk allocation.

Tests whether official Space breakout signals with the existing strong-volume
confirmation boundary deserve a different risk scalar after the accepted
exp-20260512-013 default-off Space stack. Candidate pool, accepted Space
scalars, targets, stops, ranking, add-ons, LLM/news replay, and live slots stay
fixed; only the strong-volume Space breakout risk scalar changes.
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
    _round,
    _run_core_baseline,
    _run_window,
    _safe,
    _scale_sizing,
    _space_trade_attribution,
    _write_json,
)
from exp_20260512_009_space_peer_momentum_leader_risk import (
    ACCEPTED_SPACE_BASKET_POSITIVE_SCALAR,
    ACCEPTED_SPACE_NEAR_PERFECT_TQS_SCORE_CEILING,
    ACCEPTED_SPACE_NEAR_PERFECT_TQS_SCORE_FLOOR,
    ACCEPTED_SPACE_NEAR_PERFECT_TQS_TREND_RISK_SCALAR,
    ACCEPTED_SPACE_PERFECT_TQS_RISK_SCALAR,
)
from exp_20260512_013_space_peer_nonleader_breakout_risk import (
    _install_space_policy as _install_accepted_exp013_space_policy,
)
from data_layer import get_universe
import portfolio_engine


logging.basicConfig(level=logging.WARNING)

EXPERIMENT_ID = "exp-20260512-021"
STEM = "space_breakout_volume_confirmation_risk"
ACCEPTED_SPACE_PEER_NONLEADER_BREAKOUT_RISK_SCALAR = 0.0
SPACE_BREAKOUT_STRONG_VOLUME_RATIO_MIN_EXCLUSIVE = 2.0
SPACE_BREAKOUT_STRONG_VOLUME_SCALARS = (0.75, 1.10, 1.25, 1.50)


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


def _volume_spike_ratio(signal: dict[str, Any]) -> float | None:
    conditions = signal.get("conditions_met") or {}
    value = signal.get("volume_spike_ratio")
    if value is None:
        value = conditions.get("volume_spike_ratio")
    return _round(value, 6)


def _space_breakout_volume_state(signal: dict[str, Any]) -> dict[str, Any]:
    ticker = str(signal.get("ticker") or "").upper()
    strategy = str(signal.get("strategy") or "").lower()
    ratio = _volume_spike_ratio(signal)
    if ticker not in OFFICIAL_SPACE_TICKERS or strategy != "breakout_long":
        return {"state": "not_space_breakout", "volume_spike_ratio": ratio}
    if ratio is None:
        return {"state": "missing", "volume_spike_ratio": None}
    if ratio > SPACE_BREAKOUT_STRONG_VOLUME_RATIO_MIN_EXCLUSIVE:
        return {"state": "strong_volume", "volume_spike_ratio": ratio}
    return {"state": "standard_volume", "volume_spike_ratio": ratio}


def _is_space_breakout_strong_volume(signal: dict[str, Any]) -> bool:
    return _space_breakout_volume_state(signal)["state"] == "strong_volume"


def _volume_adjustment_row(
    signal: dict[str, Any],
    sizing: dict[str, Any],
    shares_before: int,
    scalar: float,
) -> dict[str, Any]:
    state = _space_breakout_volume_state(signal)
    return {
        "ticker": str(signal.get("ticker") or "").upper(),
        "strategy": str(signal.get("strategy") or "").lower(),
        "marker": "space_breakout_strong_volume_risk",
        "space_breakout_volume_state": state["state"],
        "volume_spike_ratio": state["volume_spike_ratio"],
        "strong_volume_min_exclusive": SPACE_BREAKOUT_STRONG_VOLUME_RATIO_MIN_EXCLUSIVE,
        "space_basket_momentum_state": signal.get("space_basket_momentum_state"),
        "space_basket_momentum_20d_pct": signal.get("space_basket_momentum_20d_pct"),
        "space_peer_momentum_state": signal.get("space_peer_momentum_state"),
        "space_peer_momentum_20d_pct": signal.get("space_peer_momentum_20d_pct"),
        "space_peer_excess_momentum_20d_pct": signal.get(
            "space_peer_excess_momentum_20d_pct"
        ),
        "scalar": scalar,
        "shares_before_scalar": shares_before,
        "shares_after_scalar": int(sizing.get("shares_to_buy") or 0),
        "trade_quality_score": _round(signal.get("trade_quality_score"), 4),
        "confidence_score": _round(signal.get("confidence_score"), 4),
    }


def _install_space_policy(strong_volume_scalar: float):
    (
        original_generate,
        original_enrich,
        original_size,
        peer_nonleader_breakout_adjustments,
        near_perfect_adjustments,
        perfect_adjustments,
        basket_adjustments,
        peer_counts,
        near_perfect_counts,
        perfect_counts,
        basket_counts,
        day_counts,
    ) = _install_accepted_exp013_space_policy(
        ACCEPTED_SPACE_PEER_NONLEADER_BREAKOUT_RISK_SCALAR
    )
    accepted_size = portfolio_engine.size_signals
    volume_adjustments: list[dict[str, Any]] = []
    volume_counts = Counter()

    def size_wrapper(signals, portfolio_value, risk_pct=None):
        sized = accepted_size(signals, portfolio_value, risk_pct=risk_pct)
        out = []
        for signal in sized:
            ticker = str(signal.get("ticker") or "").upper()
            strategy = str(signal.get("strategy") or "").lower()
            if ticker in OFFICIAL_SPACE_TICKERS and strategy == "breakout_long":
                state = _space_breakout_volume_state(signal)
                volume_counts[state["state"]] += 1
            sizing = deepcopy(signal.get("sizing") or {})
            if (
                _is_space_breakout_strong_volume(signal)
                and strong_volume_scalar != 1.0
                and sizing
            ):
                shares_before = int(sizing.get("shares_to_buy") or 0)
                if shares_before > 0:
                    _scale_sizing(
                        sizing,
                        strong_volume_scalar,
                        portfolio_value,
                        "space_breakout_strong_volume_risk",
                    )
                    volume_adjustments.append(
                        _volume_adjustment_row(
                            signal,
                            sizing,
                            shares_before,
                            strong_volume_scalar,
                        )
                    )
                    signal = {**signal, "sizing": sizing}
            out.append(signal)
        return out

    portfolio_engine.size_signals = size_wrapper
    return (
        original_generate,
        original_enrich,
        original_size,
        volume_adjustments,
        volume_counts,
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


def _counter_delta(after: Counter, before: Counter) -> dict[str, int]:
    keys = sorted(set(after) | set(before))
    return {key: int(after.get(key, 0) - before.get(key, 0)) for key in keys}


def _run_variant(name: str, strong_volume_scalar: float) -> dict[str, Any]:
    universe = sorted(set(get_universe()) | set(OFFICIAL_SPACE_TICKERS))
    (
        original_generate,
        original_enrich,
        original_size,
        volume_adjustments,
        volume_counts,
        peer_nonleader_breakout_adjustments,
        near_perfect_adjustments,
        perfect_adjustments,
        basket_adjustments,
        peer_counts,
        near_perfect_counts,
        perfect_counts,
        basket_counts,
        day_counts,
    ) = _install_space_policy(strong_volume_scalar)
    try:
        by_window = {}
        for label, window in WINDOWS.items():
            before_volume = len(volume_adjustments)
            before_volume_counts = Counter(volume_counts)
            before_peer = len(peer_nonleader_breakout_adjustments)
            before_near = len(near_perfect_adjustments)
            before_perfect = len(perfect_adjustments)
            before_basket = len(basket_adjustments)
            result = _run_window(window, universe, "space_snapshot")
            metrics = _metrics(result)
            by_window[label] = {
                "metrics": metrics,
                "space_trade_attribution": _space_trade_attribution(result),
                "space_breakout_strong_volume_adjustment": _adjustment_summary(
                    volume_adjustments[before_volume:]
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
                "space_breakout_volume_state_counts": _counter_delta(
                    volume_counts,
                    before_volume_counts,
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
        "space_breakout_strong_volume_scalar": strong_volume_scalar,
        "space_breakout_strong_volume_ratio_min_exclusive": (
            SPACE_BREAKOUT_STRONG_VOLUME_RATIO_MIN_EXCLUSIVE
        ),
        "by_window": by_window,
        "aggregate": _aggregate(metrics_by_window),
    }


def _field_check(variant: dict[str, Any]) -> dict[str, Any]:
    missing = sum(
        row["space_breakout_volume_state_counts"].get("missing", 0)
        for row in variant["by_window"].values()
    )
    strong = sum(
        row["space_breakout_volume_state_counts"].get("strong_volume", 0)
        for row in variant["by_window"].values()
    )
    standard = sum(
        row["space_breakout_volume_state_counts"].get("standard_volume", 0)
        for row in variant["by_window"].values()
    )
    return {
        "field": "conditions_met.volume_spike_ratio",
        "source": "feature_layer.compute_trend_features -> signal_engine.strategy_b",
        "strong_volume_definition": (
            f"volume_spike_ratio > {SPACE_BREAKOUT_STRONG_VOLUME_RATIO_MIN_EXCLUSIVE}"
        ),
        "strong_volume_count": strong,
        "standard_volume_count": standard,
        "missing_count": missing,
        "passed": missing == 0 and (strong + standard) > 0,
    }


def _gate(
    variant: dict[str, Any],
    before: dict[str, Any],
    core: dict[str, Any],
) -> dict[str, Any]:
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
        row["space_breakout_strong_volume_adjustment"]["adjusted_signal_count"]
        for row in variant["by_window"].values()
    )
    field_check = _field_check(before)
    passed = (
        field_check["passed"]
        and aggregate_delta["expected_value_score_sum"] > 0
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
        "space_breakout_strong_volume_adjusted_signal_count": adjusted_count,
        "field_check": field_check,
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    lines = [
        f"# {EXPERIMENT_ID} Space breakout volume-confirmation risk",
        "",
        f"- Decision: `{payload['decision']}`",
        (
            "- Single variable: risk scalar for official Space breakout_long signals "
            "with `conditions_met.volume_spike_ratio > 2.0`."
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
            f"| {name} | {variant['space_breakout_strong_volume_scalar']:.2f} | "
            f"{'pass' if gate['passed'] else 'fail'} | "
            f"{delta['expected_value_score_sum']:+.4f} | "
            f"{delta['total_pnl_sum']:+,.2f} | "
            f"{gate['windows_ev_improved_vs_before']} | "
            f"{gate['windows_ev_regressed_vs_before']} | "
            f"{gate['space_breakout_strong_volume_adjusted_signal_count']} |"
        )
    lines.extend(
        [
            "",
            "## Best Three-Window Comparison",
            "",
            "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Strong-volume adjusted |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        adjusted = best["by_window"][label][
            "space_breakout_strong_volume_adjustment"
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
            "## Field Check",
            "",
            json.dumps(payload["gate2"]["volume_spike_ratio"], sort_keys=True),
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
    gate2_open_positions = _gate2_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2_open_positions}")

    core = _run_core_baseline()
    variants = {
        "accepted_exp013_stack": _run_variant("accepted_exp013_stack", 1.0)
    }
    for scalar in SPACE_BREAKOUT_STRONG_VOLUME_SCALARS:
        name = f"breakout_strong_volume_{str(scalar).replace('.', '_')}"
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
        "accepted_default_off_space_breakout_volume_confirmation_risk"
        if accepted
        else "rejected_space_breakout_volume_confirmation_risk"
    )
    interpretation = (
        "The existing strong-volume breakout boundary improved the accepted "
        "exp-20260512-013 default-off Space stack under the three-window gate. "
        "Promotion must remain default-off metadata/helper only because Space "
        "live slots remain zero."
        if accepted
        else (
            "The existing strong-volume breakout boundary did not identify a "
            "robust Space breakout risk scalar on top of exp-20260512-013. Do "
            "not retry nearby Space breakout volume-confirmation scalars on the "
            "same frozen snapshots; future Space work needs a different "
            "catalyst-quality field, forward replacement evidence, or a true "
            "candidate-pool improvement."
        )
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "risk_allocation_shadow_sweep",
        "changed_variable": "space_breakout_strong_volume_risk_scalar",
        "single_causal_variable": (
            "risk scalar for official Space breakout_long signals whose "
            "conditions_met.volume_spike_ratio is greater than the existing "
            "feature-layer strong-volume boundary of 2.0"
        ),
        "hypothesis": (
            "After exp-20260512-013 removed peer-nonleader breakout risk, the "
            "remaining Space breakout alpha question is whether leader-quality "
            "breakouts with unusually strong volume confirmation deserve a "
            "different risk scalar. This uses an existing runtime field instead "
            "of LLM soft ranking, which remains sample-limited."
        ),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation: calibrate only official Space breakout_long "
                "signals with conditions_met.volume_spike_ratio > 2.0."
            ),
            "2_history_check": {
                "exp-20260511-019": "Accepted PL/BKSY breakout 0.1x haircut.",
                "exp-20260511-037": "Rejected Space breakout target extension.",
                "exp-20260511-110": "Rejected Space breakout stop widening.",
                "exp-20260512-009": "Rejected peer-leader top-up due old_thin drawdown.",
                "exp-20260512-010": "Rejected near-perfect TQS breakout scalar.",
                "exp-20260512-013": "Accepted peer-nonleader Space breakout 0.0x risk.",
                "exp-20260512-015": "Rejected Space breakout 52w proximity scalar.",
                "exp-20260512-016": "Rejected Space basket breadth min-count gate.",
                "exp-20260512-019": "Rejected Space low execution-adjusted R/R scalar.",
            },
            "3_single_causal_variable": (
                "space_breakout_strong_volume_risk_scalar; candidate pool, "
                "accepted Space stack, targets, stops, ranking, add-ons, "
                "LLM/news, and live slots stay fixed."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; require positive "
                "aggregate EV/PnL, at least 2/3 improved EV windows, no "
                "EV-regressed window, max drawdown drift <= 0.5 pp, survival "
                ">= 5%, valid volume_spike_ratio field, and nonzero adjusted "
                "signals."
            ),
            "5_reproducibility": (
                "This script reruns core, accepted exp-20260512-013 Space "
                "stack, and each strong-volume breakout scalar across the "
                "canonical augmented snapshots."
            ),
        },
        "parameters": {
            "official_space_tickers": list(OFFICIAL_SPACE_TICKERS),
            "accepted_before_experiment": "exp-20260512-013",
            "space_breakout_strong_volume_ratio_min_exclusive": (
                SPACE_BREAKOUT_STRONG_VOLUME_RATIO_MIN_EXCLUSIVE
            ),
            "strong_volume_definition": "conditions_met.volume_spike_ratio > 2.0",
            "tested_strong_volume_scalars": list(SPACE_BREAKOUT_STRONG_VOLUME_SCALARS),
            "accepted_peer_nonleader_breakout_scalar": (
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
            "space_basket_momentum_field": SPACE_BASKET_MOMENTUM_FIELD,
            "locked_variables": [
                "official Space candidate pool",
                "base Space risk scalar",
                "PL/BKSY breakout 0.1x haircut",
                "RKLB/ASTS trend 1.25x top-up",
                "accepted Space basket-positive 1.10x scalar",
                "accepted perfect-TQS 1.50x risk scalar",
                "accepted near-perfect trend TQS 1.10x scalar",
                "accepted peer-nonleader breakout 0.0x scalar",
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
        "gate2": {
            "open_positions": gate2_open_positions,
            "volume_spike_ratio": _field_check(before),
        },
        "gate3": {
            "new_core_filter_added": False,
            "space_breakout_risk_scalar_added": True,
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
                "Space LLM soft-ranking/event-bucket data remains below the "
                "closed-decision gate; this run uses deterministic OHLCV volume "
                "confirmation with an existing production feature."
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
            "If rejected, do not retry nearby Space breakout volume-confirmation "
            "scalars on the same frozen snapshots. Future Space breakout work "
            "should use forward catalyst replacement value, a fresh event-quality "
            "field, or a candidate-pool change with replacement evidence."
        ),
        "related_files": [
            "quant/experiments/exp_20260512_021_space_breakout_volume_confirmation_risk.py",
            "data/experiments/exp-20260512-021/space_breakout_volume_confirmation_risk.json",
            "experiments/logs/exp-20260512-021.json",
            "experiments/tickets/exp-20260512-021.json",
            "experiments/artifacts/exp-20260512-021_space_breakout_volume_confirmation_risk.md",
            "docs/experiment_log.jsonl",
        ],
        "why_not_other_changes": (
            "LLM soft-ranking and event-bucket scoring are still sample-limited; "
            "mature satcom breadth, theme ETF timing, one-slot capacity, breakout "
            "target/stop geometry, data-vendor trend targets, 52w proximity, "
            "basket breadth, execution-adjusted R/R, perfect-TQS target broadening, "
            "near-perfect TQS breakout risk, peer-leader top-ups, and "
            "lunar/manufacturing target broadening already failed or are fixed "
            "accepted context."
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
    gate = result["gate4"]
    aggregate = result["delta_metrics"]["aggregate"]
    print(
        f"{EXPERIMENT_ID} {result['decision']} "
        f"best={result['best_variant']['variant']} "
        f"dEV={aggregate['expected_value_score_sum']:+.4f} "
        f"dPnL={aggregate['total_pnl_sum']:+.2f} "
        f"gate={'pass' if gate['passed'] else 'fail'}"
    )
