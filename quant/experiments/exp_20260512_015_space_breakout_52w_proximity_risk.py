"""exp-20260512-015: Space breakout 52-week-high proximity risk.

Tests whether official Space breakout signals that fail the existing
near-52-week-high quality boundary deserve less risk after the accepted
exp-20260512-013 default-off Space stack. Candidate pool, accepted Space
scalars, targets, stops, ranking, add-ons, LLM/news replay, and live slots stay
fixed; only the not-near-52w Space breakout risk scalar changes.
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
import signal_engine


logging.basicConfig(level=logging.WARNING)

EXPERIMENT_ID = "exp-20260512-015"
STEM = "space_breakout_52w_proximity_risk"
ACCEPTED_SPACE_PEER_NONLEADER_BREAKOUT_RISK_SCALAR = 0.0
SPACE_BREAKOUT_NEAR_52W_HIGH_FLOOR = -0.05
SPACE_BREAKOUT_NOT_NEAR_52W_SCALARS = (0.0, 0.25, 0.5, 0.75)


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


def _pct_from_52w_high(signal: dict[str, Any]) -> float | None:
    conditions = signal.get("conditions_met") or {}
    value = signal.get("pct_from_52w_high")
    if value is None:
        value = conditions.get("pct_from_52w_high")
    return _round(value, 6)


def _space_breakout_52w_state(signal: dict[str, Any]) -> dict[str, Any]:
    ticker = str(signal.get("ticker") or "").upper()
    strategy = str(signal.get("strategy") or "").lower()
    pct = _pct_from_52w_high(signal)
    if ticker not in OFFICIAL_SPACE_TICKERS or strategy != "breakout_long":
        return {"state": "not_space_breakout", "pct_from_52w_high": pct}
    if pct is None:
        return {"state": "missing", "pct_from_52w_high": None}
    if pct > SPACE_BREAKOUT_NEAR_52W_HIGH_FLOOR:
        return {"state": "near_52w_high", "pct_from_52w_high": pct}
    return {"state": "not_near_52w_high", "pct_from_52w_high": pct}


def _is_space_breakout_not_near_52w(signal: dict[str, Any]) -> bool:
    return _space_breakout_52w_state(signal)["state"] == "not_near_52w_high"


def _proximity_adjustment_row(
    signal: dict[str, Any],
    sizing: dict[str, Any],
    shares_before: int,
    scalar: float,
) -> dict[str, Any]:
    state = _space_breakout_52w_state(signal)
    return {
        "ticker": str(signal.get("ticker") or "").upper(),
        "strategy": str(signal.get("strategy") or "").lower(),
        "marker": "space_breakout_not_near_52w_risk",
        "space_breakout_52w_state": state["state"],
        "pct_from_52w_high": state["pct_from_52w_high"],
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


def _install_space_policy(breakout_not_near_52w_scalar: float):
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
    proximity_adjustments: list[dict[str, Any]] = []
    proximity_counts = Counter()

    def size_wrapper(signals, portfolio_value, risk_pct=None):
        sized = accepted_size(signals, portfolio_value, risk_pct=risk_pct)
        out = []
        for signal in sized:
            ticker = str(signal.get("ticker") or "").upper()
            strategy = str(signal.get("strategy") or "").lower()
            if ticker in OFFICIAL_SPACE_TICKERS and strategy == "breakout_long":
                state = _space_breakout_52w_state(signal)
                proximity_counts[state["state"]] += 1
            sizing = deepcopy(signal.get("sizing") or {})
            if (
                _is_space_breakout_not_near_52w(signal)
                and breakout_not_near_52w_scalar != 1.0
                and sizing
            ):
                shares_before = int(sizing.get("shares_to_buy") or 0)
                if shares_before > 0:
                    _scale_sizing(
                        sizing,
                        breakout_not_near_52w_scalar,
                        portfolio_value,
                        "space_breakout_not_near_52w_risk",
                    )
                    proximity_adjustments.append(
                        _proximity_adjustment_row(
                            signal,
                            sizing,
                            shares_before,
                            breakout_not_near_52w_scalar,
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
        proximity_adjustments,
        proximity_counts,
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


def _run_variant(name: str, breakout_not_near_52w_scalar: float) -> dict[str, Any]:
    universe = sorted(set(get_universe()) | set(OFFICIAL_SPACE_TICKERS))
    (
        original_generate,
        original_enrich,
        original_size,
        proximity_adjustments,
        proximity_counts,
        peer_nonleader_breakout_adjustments,
        near_perfect_adjustments,
        perfect_adjustments,
        basket_adjustments,
        peer_counts,
        near_perfect_counts,
        perfect_counts,
        basket_counts,
        day_counts,
    ) = _install_space_policy(breakout_not_near_52w_scalar)
    try:
        by_window = {}
        for label, window in WINDOWS.items():
            before_proximity = len(proximity_adjustments)
            before_peer = len(peer_nonleader_breakout_adjustments)
            before_near = len(near_perfect_adjustments)
            before_perfect = len(perfect_adjustments)
            before_basket = len(basket_adjustments)
            result = _run_window(window, universe, "space_snapshot")
            metrics = _metrics(result)
            by_window[label] = {
                "metrics": metrics,
                "space_trade_attribution": _space_trade_attribution(result),
                "space_breakout_not_near_52w_adjustment": _adjustment_summary(
                    proximity_adjustments[before_proximity:]
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
                "space_breakout_52w_state_counts": dict(
                    sorted(proximity_counts.items())
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
        "space_breakout_not_near_52w_scalar": breakout_not_near_52w_scalar,
        "by_window": by_window,
        "aggregate": _aggregate(metrics_by_window),
    }


def _field_check(variant: dict[str, Any]) -> dict[str, Any]:
    missing = sum(
        row["space_breakout_52w_state_counts"].get("missing", 0)
        for row in variant["by_window"].values()
    )
    not_near = sum(
        row["space_breakout_52w_state_counts"].get("not_near_52w_high", 0)
        for row in variant["by_window"].values()
    )
    near = sum(
        row["space_breakout_52w_state_counts"].get("near_52w_high", 0)
        for row in variant["by_window"].values()
    )
    return {
        "field": "conditions_met.pct_from_52w_high",
        "source": "feature_layer.compute_trend_features -> signal_engine strategy_b",
        "near_52w_high_count": near,
        "not_near_52w_high_count": not_near,
        "missing_count": missing,
        "passed": missing == 0 and (near + not_near) > 0,
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
        row["space_breakout_not_near_52w_adjustment"]["adjusted_signal_count"]
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
        "space_breakout_not_near_52w_adjusted_signal_count": adjusted_count,
        "field_check": field_check,
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    lines = [
        f"# {EXPERIMENT_ID} Space breakout 52w proximity risk",
        "",
        f"- Decision: `{payload['decision']}`",
        (
            "- Single variable: risk scalar for official Space breakout_long signals "
            "with pct_from_52w_high <= -5%."
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
            f"| {name} | {variant['space_breakout_not_near_52w_scalar']:.2f} | "
            f"{'pass' if gate['passed'] else 'fail'} | "
            f"{delta['expected_value_score_sum']:+.4f} | "
            f"{delta['total_pnl_sum']:+,.2f} | "
            f"{gate['windows_ev_improved_vs_before']} | "
            f"{gate['windows_ev_regressed_vs_before']} | "
            f"{gate['space_breakout_not_near_52w_adjusted_signal_count']} |"
        )
    lines.extend(
        [
            "",
            "## Best Three-Window Comparison",
            "",
            "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Trades | Max DD | Survival | Not-near 52w signals |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        adjusted = best["by_window"][label][
            "space_breakout_not_near_52w_adjustment"
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
            json.dumps(payload["gate2"]["pct_from_52w_high"], sort_keys=True),
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
    for scalar in SPACE_BREAKOUT_NOT_NEAR_52W_SCALARS:
        name = f"breakout_not_near_52w_{str(scalar).replace('.', '_')}"
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
        "accepted_default_off_space_breakout_52w_proximity_risk"
        if accepted
        else "rejected_space_breakout_52w_proximity_risk"
    )
    interpretation = (
        "Official Space breakouts that are more than 5% below their 52-week high "
        "improved the accepted exp-20260512-013 default-off Space stack under the "
        "three-window gate. Promotion must remain default-off metadata/helper only "
        "because Space live slots remain zero."
        if accepted
        else (
            "The existing near-52w-high quality boundary did not identify a robust "
            "Space breakout risk haircut on top of exp-20260512-013. Do not add a "
            "Space-specific pct_from_52w_high breakout scalar on the frozen Space "
            "snapshots; future breakout work needs a different catalyst-quality or "
            "candidate-replacement variable."
        )
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "risk_allocation_shadow_sweep",
        "changed_variable": "space_breakout_not_near_52w_risk_scalar",
        "single_causal_variable": (
            "risk scalar for official Space breakout_long signals whose "
            "conditions_met.pct_from_52w_high is <= -5%"
        ),
        "hypothesis": (
            "After exp-20260512-013 removed peer-nonleader breakout risk, the "
            "remaining Space breakout alpha question is whether leader breakouts "
            "that fail the existing near-52w-high quality boundary should receive "
            "less risk. This uses an existing runtime field instead of LLM soft "
            "ranking, which remains sample-limited."
        ),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation: haircut only official Space breakout_long signals "
                "with pct_from_52w_high <= -5%, using the existing _near_52w_high "
                "quality boundary."
            ),
            "2_history_check": {
                "exp-20260511-019": "Accepted PL/BKSY breakout 0.1x haircut.",
                "exp-20260511-037": "Rejected Space breakout target extension.",
                "exp-20260511-110": "Rejected Space breakout stop widening.",
                "exp-20260512-009": "Rejected peer-leader top-up due old_thin drawdown.",
                "exp-20260512-010": "Rejected near-perfect TQS breakout scalar.",
                "exp-20260512-013": "Accepted peer-nonleader Space breakout 0.0x risk.",
                "prior_52w_work": (
                    "Broad breakout 52w ranking/proximity work existed outside this "
                    "Space-sleeve risk allocation question; do not infer Space-specific "
                    "risk from those global ranking tests."
                ),
            },
            "3_single_causal_variable": (
                "space_breakout_not_near_52w_risk_scalar; candidate pool, accepted "
                "Space stack, targets, stops, ranking, add-ons, LLM/news, and live "
                "slots stay fixed."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; require positive aggregate "
                "EV/PnL, at least 2/3 improved EV windows, no EV-regressed window, "
                "max drawdown drift <= 0.5 pp, survival >= 5%, valid pct_from_52w_high "
                "field, and nonzero adjusted signals."
            ),
            "5_reproducibility": (
                "This script reruns core, accepted exp-20260512-013 Space stack, "
                "and each not-near-52w breakout scalar across the canonical augmented snapshots."
            ),
        },
        "parameters": {
            "official_space_tickers": list(OFFICIAL_SPACE_TICKERS),
            "accepted_before_experiment": "exp-20260512-013",
            "space_breakout_near_52w_high_floor": SPACE_BREAKOUT_NEAR_52W_HIGH_FLOOR,
            "not_near_52w_definition": "pct_from_52w_high <= -0.05",
            "tested_not_near_52w_scalars": list(SPACE_BREAKOUT_NOT_NEAR_52W_SCALARS),
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
            "pct_from_52w_high": _field_check(before),
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
                "closed-decision gate; this run uses deterministic OHLCV proximity "
                "with an existing production feature."
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
            "If rejected, do not retry nearby Space pct_from_52w_high breakout "
            "scalars on the same frozen snapshots. Future Space breakout work "
            "should use forward catalyst replacement value, a fresh event-quality "
            "field, or a candidate-pool change with replacement evidence."
        ),
        "related_files": [
            "quant/experiments/exp_20260512_015_space_breakout_52w_proximity_risk.py",
            "data/experiments/exp-20260512-015/space_breakout_52w_proximity_risk.json",
            "docs/experiments/logs/exp-20260512-015.json",
            "docs/experiments/tickets/exp-20260512-015.json",
            "docs/experiments/artifacts/exp-20260512-015_space_breakout_52w_proximity_risk.md",
            "docs/experiment_log.jsonl",
        ],
        "why_not_other_changes": (
            "LLM soft-ranking and event-bucket scoring are still sample-limited; "
            "mature satcom breadth, theme ETF timing, one-slot capacity, breakout "
            "target/stop geometry, data-vendor trend targets, perfect-TQS target "
            "broadening, near-perfect TQS breakout risk, peer-leader top-ups, and "
            "lunar/manufacturing target broadening already failed or are fixed "
            "accepted context."
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
