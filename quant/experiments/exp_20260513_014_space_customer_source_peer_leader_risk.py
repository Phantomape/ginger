"""exp-20260513-014: Space customer-source peer-leader risk.

Tests one causal variable on top of the accepted exp-20260513-012 default-off
Space stack: an extra risk scalar only when an official customer-source Space
signal is also leading the official Space peer basket. This is a narrow
production-visible catalyst-quality plus relative-strength risk-allocation test,
not LLM soft-ranking, candidate-pool expansion, source retuning, or live-slot
promotion.
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

from exp_20260511_115_space_basket_momentum_risk import (  # noqa: E402
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
    _run_core_baseline,
    _run_window,
    _safe,
    _scale_sizing,
    _space_trade_attribution,
    _write_json,
)
from exp_20260512_038_space_official_customer_source_risk import (  # noqa: E402
    _event_seed_profiles,
)
from exp_20260512_041_space_financing_dilution_profile_risk import (  # noqa: E402
    _field_check_event_guard_profiles as _accepted_financing_profile_gate,
)
from exp_20260512_110_space_company_release_source_risk import (  # noqa: E402
    ACCEPTED_FINANCING_DILUTION_PROFILE_RISK_SCALAR,
    _field_check_company_release_source,
)
from exp_20260512_112_space_watch_liquidity_risk import (  # noqa: E402
    ACCEPTED_COMPANY_RELEASE_SOURCE_RISK_SCALAR,
    TARGET_LIQUIDITY_TIER,
    _field_check_watch_liquidity_tier,
)
from exp_20260513_012_space_multi_event_depth_risk import (  # noqa: E402
    MULTI_EVENT_MIN_COUNT,
    WATCH_LIQUIDITY_RISK_SCALAR,
    _field_check_multi_event_depth,
    _install_space_policy as _install_accepted_exp012_policy,
    _run_variant as _run_accepted_exp012_variant,
)
from data_layer import get_universe  # noqa: E402
import portfolio_engine  # noqa: E402


logging.basicConfig(level=logging.WARNING)

EXPERIMENT_ID = "exp-20260513-014"
STEM = "space_customer_source_peer_leader_risk"
ACCEPTED_MULTI_EVENT_DEPTH_RISK_SCALAR = 1.075
CUSTOMER_SOURCE_PEER_LEADER_RISK_SCALARS = (
    0.75,
    0.90,
    1.00,
    1.025,
    1.05,
    1.075,
    1.10,
    1.25,
)


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


def _as_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _is_peer_leader(signal: dict[str, Any]) -> bool:
    if str(signal.get("space_peer_momentum_state") or "") == "leader":
        return True
    excess = _as_float(signal.get("space_peer_excess_momentum_20d_pct"))
    return excess is not None and excess > 0


def _field_check_peer_leader_state(before: dict[str, Any]) -> dict[str, Any]:
    counts = Counter()
    samples = []
    for label, row in before.get("by_window", {}).items():
        counts.update(row.get("space_peer_momentum_state_counts") or {})
        for key in (
            "space_multi_event_depth_adjustment",
            "space_official_customer_source_adjustment",
            "space_basket_positive_adjustment",
            "space_near_perfect_tqs_trend_adjustment",
            "space_perfect_tqs_risk_adjustment",
        ):
            summary = row.get(key) or {}
            for sample in summary.get("sample_adjusted") or []:
                if "space_peer_momentum_state" in sample:
                    samples.append(
                        {
                            "window": label,
                            "ticker": sample.get("ticker"),
                            "strategy": sample.get("strategy"),
                            "space_peer_momentum_state": sample.get(
                                "space_peer_momentum_state"
                            ),
                            "space_peer_excess_momentum_20d_pct": sample.get(
                                "space_peer_excess_momentum_20d_pct"
                            ),
                        }
                    )
    return {
        "passed": sum(counts.values()) > 0 and counts.get("leader", 0) > 0,
        "field": "space_peer_momentum_state",
        "source": "accepted Space basket momentum enrichment from exp-20260511-115 stack",
        "state_counts": dict(sorted(counts.items())),
        "sample_runtime_values": samples[:12],
    }


def _install_space_policy(
    source_peer_leader_scalar: float,
    source_gate: dict[str, Any],
    multi_event_gate: dict[str, Any],
    liquidity_gate: dict[str, Any],
    company_release_gate: dict[str, Any],
    financing_gate: dict[str, Any],
) -> tuple[Any, ...]:
    installed = _install_accepted_exp012_policy(
        ACCEPTED_MULTI_EVENT_DEPTH_RISK_SCALAR,
        multi_event_gate,
        liquidity_gate,
        company_release_gate,
        financing_gate,
        source_gate,
    )
    (
        original_generate,
        original_enrich,
        original_size,
        multi_event_adjustments,
        multi_event_counts,
        watch_adjustments,
        watch_counts,
        company_release_adjustments,
        company_release_counts,
        financing_adjustments,
        financing_counts,
        source_adjustments,
        source_counts,
        liquidity_ok_adjustments,
        theme_adjustments,
        iwm_adjustments,
        peer_nonleader_breakout_adjustments,
        near_perfect_adjustments,
        perfect_adjustments,
        basket_adjustments,
        theme_counts,
        iwm_state_counts,
        peer_counts,
        near_perfect_counts,
        perfect_counts,
        basket_counts,
        day_counts,
    ) = installed

    accepted_size = portfolio_engine.size_signals
    target_tickers = set(source_gate["target_tickers"])
    profiles = source_gate["profiles"]
    source_peer_leader_adjustments: list[dict[str, Any]] = []
    source_peer_leader_counts = Counter()

    def size_wrapper(signals, portfolio_value, risk_pct=None):
        sized = accepted_size(signals, portfolio_value, risk_pct=risk_pct)
        out = []
        for signal in sized:
            ticker = str(signal.get("ticker") or "").upper()
            sizing = deepcopy(signal.get("sizing") or {})
            eligible = ticker in target_tickers and _is_peer_leader(signal)
            if eligible and sizing:
                source_peer_leader_counts["eligible_signal"] += 1
                shares_before = int(sizing.get("shares_to_buy") or 0)
                _scale_sizing(
                    sizing,
                    source_peer_leader_scalar,
                    portfolio_value,
                    "space_customer_source_peer_leader_risk",
                )
                source_peer_leader_adjustments.append(
                    {
                        "ticker": ticker,
                        "strategy": signal.get("strategy"),
                        "marker": "space_customer_source_peer_leader_risk",
                        "space_event_source_profile": profiles.get(ticker),
                        "space_peer_momentum_state": signal.get(
                            "space_peer_momentum_state"
                        ),
                        "space_peer_momentum_20d_pct": signal.get(
                            "space_peer_momentum_20d_pct"
                        ),
                        "space_peer_excess_momentum_20d_pct": signal.get(
                            "space_peer_excess_momentum_20d_pct"
                        ),
                        "scalar": source_peer_leader_scalar,
                        "shares_before_scalar": shares_before,
                        "shares_after_scalar": int(sizing.get("shares_to_buy") or 0),
                        "trade_quality_score": signal.get("trade_quality_score"),
                        "confidence_score": signal.get("confidence_score"),
                    }
                )
                signal = {
                    **signal,
                    "sizing": sizing,
                    "space_customer_source_peer_leader_profile": profiles.get(ticker),
                    "space_customer_source_peer_leader_eligible": True,
                }
            out.append(signal)
        return out

    portfolio_engine.size_signals = size_wrapper
    return (
        original_generate,
        original_enrich,
        original_size,
        source_peer_leader_adjustments,
        source_peer_leader_counts,
        multi_event_adjustments,
        multi_event_counts,
        watch_adjustments,
        watch_counts,
        company_release_adjustments,
        company_release_counts,
        financing_adjustments,
        financing_counts,
        source_adjustments,
        source_counts,
        liquidity_ok_adjustments,
        theme_adjustments,
        iwm_adjustments,
        peer_nonleader_breakout_adjustments,
        near_perfect_adjustments,
        perfect_adjustments,
        basket_adjustments,
        theme_counts,
        iwm_state_counts,
        peer_counts,
        near_perfect_counts,
        perfect_counts,
        basket_counts,
        day_counts,
    )


def _run_variant(
    name: str,
    source_peer_leader_scalar: float,
    source_gate: dict[str, Any],
    multi_event_gate: dict[str, Any],
    liquidity_gate: dict[str, Any],
    company_release_gate: dict[str, Any],
    financing_gate: dict[str, Any],
) -> dict[str, Any]:
    universe = sorted(set(get_universe()) | set(OFFICIAL_SPACE_TICKERS) | {"IWM", "SPY"})
    (
        original_generate,
        original_enrich,
        original_size,
        source_peer_leader_adjustments,
        source_peer_leader_counts,
        multi_event_adjustments,
        multi_event_counts,
        watch_adjustments,
        watch_counts,
        company_release_adjustments,
        company_release_counts,
        financing_adjustments,
        financing_counts,
        source_adjustments,
        source_counts,
        liquidity_ok_adjustments,
        theme_adjustments,
        iwm_adjustments,
        peer_nonleader_breakout_adjustments,
        near_perfect_adjustments,
        perfect_adjustments,
        basket_adjustments,
        theme_counts,
        iwm_state_counts,
        peer_counts,
        near_perfect_counts,
        perfect_counts,
        basket_counts,
        day_counts,
    ) = _install_space_policy(
        source_peer_leader_scalar,
        source_gate,
        multi_event_gate,
        liquidity_gate,
        company_release_gate,
        financing_gate,
    )
    try:
        by_window = {}
        for label, window in WINDOWS.items():
            before_source_peer_leader = len(source_peer_leader_adjustments)
            before_multi_event = len(multi_event_adjustments)
            before_watch = len(watch_adjustments)
            before_company = len(company_release_adjustments)
            before_financing = len(financing_adjustments)
            before_source = len(source_adjustments)
            before_liquidity_ok = len(liquidity_ok_adjustments)
            before_theme = len(theme_adjustments)
            before_iwm = len(iwm_adjustments)
            before_peer = len(peer_nonleader_breakout_adjustments)
            before_near = len(near_perfect_adjustments)
            before_perfect = len(perfect_adjustments)
            before_basket = len(basket_adjustments)
            result = _run_window(window, universe, "space_snapshot")
            by_window[label] = {
                "metrics": _metrics(result),
                "space_trade_attribution": _space_trade_attribution(result),
                "space_customer_source_peer_leader_adjustment": _adjustment_summary(
                    source_peer_leader_adjustments[before_source_peer_leader:]
                ),
                "space_multi_event_depth_adjustment": _adjustment_summary(
                    multi_event_adjustments[before_multi_event:]
                ),
                "space_watch_liquidity_tier_adjustment": _adjustment_summary(
                    watch_adjustments[before_watch:]
                ),
                "space_company_release_source_adjustment": _adjustment_summary(
                    company_release_adjustments[before_company:]
                ),
                "space_financing_dilution_profile_adjustment": _adjustment_summary(
                    financing_adjustments[before_financing:]
                ),
                "space_official_customer_source_adjustment": _adjustment_summary(
                    source_adjustments[before_source:]
                ),
                "space_liquidity_tier_adjustment": _adjustment_summary(
                    liquidity_ok_adjustments[before_liquidity_ok:]
                ),
                "space_launch_lunar_theme_adjustment": _adjustment_summary(
                    theme_adjustments[before_theme:]
                ),
                "space_iwm_relative_momentum_adjustment": _adjustment_summary(
                    iwm_adjustments[before_iwm:]
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
                "space_customer_source_peer_leader_signal_counts": dict(
                    sorted(source_peer_leader_counts.items())
                ),
                "space_multi_event_depth_signal_counts": dict(
                    sorted(multi_event_counts.items())
                ),
                "space_watch_liquidity_tier_signal_counts": dict(
                    sorted(watch_counts.items())
                ),
                "space_company_release_source_signal_counts": dict(
                    sorted(company_release_counts.items())
                ),
                "space_financing_dilution_profile_signal_counts": dict(
                    sorted(financing_counts.items())
                ),
                "space_source_eligible_signal_counts": dict(sorted(source_counts.items())),
                "space_theme_segment_signal_counts": dict(sorted(theme_counts.items())),
                "space_iwm_relative_state_counts": dict(sorted(iwm_state_counts.items())),
                "space_peer_momentum_state_counts": dict(sorted(peer_counts.items())),
                "space_near_perfect_tqs_trend_signal_counts": dict(
                    sorted(near_perfect_counts.items())
                ),
                "space_perfect_tqs_signal_counts": dict(sorted(perfect_counts.items())),
                "space_basket_signal_state_counts": dict(sorted(basket_counts.items())),
                "space_iwm_relative_day_counts": dict(sorted(day_counts.items())),
            }
    finally:
        _restore_policy(original_generate, original_enrich, original_size)
    metrics_by_window = {label: row["metrics"] for label, row in by_window.items()}
    return {
        "variant": name,
        "target_definition": (
            "official Space customer_win source profile and peer momentum leader"
        ),
        "target_tickers": source_gate["target_tickers"],
        "space_customer_source_peer_leader_risk_scalar": source_peer_leader_scalar,
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
        row["space_customer_source_peer_leader_adjustment"]["adjusted_signal_count"]
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
        and variant["space_customer_source_peer_leader_risk_scalar"] != 1.0
    )
    return {
        "passed": passed,
        "aggregate_delta_vs_before": aggregate_delta,
        "aggregate_delta_vs_core": aggregate_delta_vs_core,
        "by_window_delta_vs_before": by_window_delta,
        "windows_ev_improved_vs_before": windows_ev_improved,
        "windows_ev_regressed_vs_before": windows_ev_regressed,
        "max_drawdown_change_vs_before": aggregate_delta["max_drawdown_pct_max"],
        "space_customer_source_peer_leader_adjusted_signal_count": adjusted_count,
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    lines = [
        f"# {EXPERIMENT_ID} Space customer-source peer-leader risk",
        "",
        f"- Decision: `{payload['decision']}`",
        (
            "- Single variable: risk scalar for official Space customer_win source "
            "signals that are also peer momentum leaders."
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
        (
            "| Variant | Scalar | Gate | dEV | dPnL | Improved windows | "
            "Regressed windows | Adjusted signals |"
        ),
        "|---|---:|---|---:|---:|---:|---:|---:|",
    ]
    for name, variant in payload["variants"].items():
        gate = variant["gate"]
        delta = gate["aggregate_delta_vs_before"]
        lines.append(
            f"| {name} | {variant['space_customer_source_peer_leader_risk_scalar']:.3f} | "
            f"{'pass' if gate['passed'] else 'fail'} | "
            f"{delta['expected_value_score_sum']:+.4f} | "
            f"{delta['total_pnl_sum']:+,.2f} | "
            f"{gate['windows_ev_improved_vs_before']} | "
            f"{gate['windows_ev_regressed_vs_before']} | "
            f"{gate['space_customer_source_peer_leader_adjusted_signal_count']} |"
        )
    lines.extend(
        [
            "",
            "## Best Three-Window Comparison",
            "",
            (
                "| Window | Before EV | After EV | dEV | Before PnL | After PnL | "
                "dPnL | Trades | Max DD | Survival | Source-peer-leader signals |"
            ),
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        adjusted = best["by_window"][label][
            "space_customer_source_peer_leader_adjustment"
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
            "## Field Checks",
            "",
            json.dumps(payload["gate2"]["official_customer_source_profile"], sort_keys=True),
            "",
            json.dumps(payload["gate2"]["peer_momentum_state"], sort_keys=True),
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
    gate2_open = _gate2_open_positions()
    if not gate2_open["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2_open}")

    source_gate = _event_seed_profiles()
    if not source_gate["passed"]:
        raise RuntimeError(f"Accepted event source field check failed: {source_gate}")
    financing_gate = _accepted_financing_profile_gate()
    if not financing_gate["passed"]:
        raise RuntimeError(f"Accepted financing profile field check failed: {financing_gate}")
    company_release_gate = _field_check_company_release_source()
    if not company_release_gate["passed"]:
        raise RuntimeError(
            f"Accepted company-release source field check failed: {company_release_gate}"
        )
    liquidity_gate = _field_check_watch_liquidity_tier()
    if not liquidity_gate["passed"]:
        raise RuntimeError(f"Watch-liquidity field check failed: {liquidity_gate}")
    multi_event_gate = _field_check_multi_event_depth()
    if not multi_event_gate["passed"]:
        raise RuntimeError(f"Multi-event catalyst-depth field check failed: {multi_event_gate}")

    core = _run_core_baseline()
    before = _run_accepted_exp012_variant(
        "accepted_exp012_multi_event_depth_stack",
        ACCEPTED_MULTI_EVENT_DEPTH_RISK_SCALAR,
        multi_event_gate,
        liquidity_gate,
        company_release_gate,
        financing_gate,
        source_gate,
    )
    peer_state_gate = _field_check_peer_leader_state(before)
    if not peer_state_gate["passed"]:
        raise RuntimeError(f"Peer momentum state field check failed: {peer_state_gate}")

    variants = {}
    for scalar in CUSTOMER_SOURCE_PEER_LEADER_RISK_SCALARS:
        name = f"customer_source_peer_leader_{str(scalar).replace('.', '_')}"
        variants[name] = _run_variant(
            name,
            scalar,
            source_gate,
            multi_event_gate,
            liquidity_gate,
            company_release_gate,
            financing_gate,
        )

    for variant in variants.values():
        variant["gate"] = _gate(variant, before, core)

    best_variant = max(
        variants.values(),
        key=lambda variant: (
            variant["gate"]["passed"],
            variant["gate"]["aggregate_delta_vs_before"]["expected_value_score_sum"],
            variant["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
        ),
    )
    accepted = best_variant["gate"]["passed"]
    decision = (
        "accepted_default_off_space_customer_source_peer_leader_risk"
        if accepted
        else "rejected_space_customer_source_peer_leader_risk"
    )
    interpretation = (
        "The source-qualified peer-leader scalar improved the accepted default-off "
        "Space stack under the three-window gate. Promotion must stay shared and "
        "metadata-only with live Space slots at zero."
        if accepted
        else (
            "The source-qualified peer-leader scalar did not clear the three-window "
            "gate on top of exp-20260513-012. Do not promote this intersection as "
            "a shared helper on these frozen snapshots."
        )
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "risk_allocation_shadow_sweep",
        "changed_variable": "space_customer_source_peer_leader_risk_scalar",
        "single_causal_variable": (
            "risk scalar for official Space customer_win source signals whose "
            "own 20d momentum is above the official Space basket average"
        ),
        "hypothesis": (
            "The strongest near-term Space alpha should combine production-visible "
            "catalyst quality with in-basket relative strength. Generic peer-leader "
            "risk was too broad, while source-only retunes were unstable; this "
            "narrow scalar tests whether official customer-win signals deserve "
            "extra risk only when the ticker is already leading its Space peers."
        ),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation: scale only official customer_win Space signals "
                "that are also peer momentum leaders."
            ),
            "2_history_check": {
                "exp-20260512-009": (
                    "Rejected generic peer-momentum leader risk. This run is not "
                    "generic; it requires a production-visible customer-source "
                    "catalyst profile."
                ),
                "exp-20260512-038": (
                    "Accepted broad official customer-source scalar earlier in the "
                    "Space stack; this run does not retune that scalar."
                ),
                "exp-20260512-944": (
                    "Rejected primary-authority source split. This run does not "
                    "split source authority and adds peer leadership as the only "
                    "new discriminator."
                ),
                "exp-20260513-002": (
                    "Rejected customer-win pool hard pruning. This run keeps the "
                    "candidate pool fixed and only tests risk allocation."
                ),
                "exp-20260513-012": (
                    "Accepted multi-event catalyst-depth 1.075x risk helper; this "
                    "is the fixed before state."
                ),
            },
            "3_single_causal_variable": (
                "space_customer_source_peer_leader_risk_scalar. Candidate pool, "
                "accepted Space stack, targets, stops, ranking, add-ons, LLM/news, "
                "and live slots stay fixed."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; require positive aggregate "
                "EV/PnL versus exp-012 accepted stack, at least 2/3 improved EV "
                "windows, no EV-regressed window, max drawdown drift <= 0.5 pp, "
                "survival >= 5%, >=50 total trades, nonzero adjusted signals, and "
                "non-1.0 scalar."
            ),
            "5_reproducibility": (
                "Run .venv\\Scripts\\python.exe "
                "quant\\experiments\\exp_20260513_014_space_customer_source_peer_leader_risk.py"
            ),
        },
        "parameters": {
            "official_space_tickers": list(OFFICIAL_SPACE_TICKERS),
            "target_event_field": source_gate["target_event_field"],
            "target_source_types": source_gate["target_source_types"],
            "target_source_tickers": source_gate["target_tickers"],
            "target_source_profiles": source_gate["profiles"],
            "peer_leader_definition": (
                "ticker momentum_20d_pct > equal-weight official Space basket "
                "momentum_20d_pct"
            ),
            "tested_customer_source_peer_leader_scalars": list(
                CUSTOMER_SOURCE_PEER_LEADER_RISK_SCALARS
            ),
            "accepted_before_experiment": "exp-20260513-012",
            "accepted_multi_event_depth_risk_scalar": (
                ACCEPTED_MULTI_EVENT_DEPTH_RISK_SCALAR
            ),
            "accepted_multi_event_min_count": MULTI_EVENT_MIN_COUNT,
            "accepted_watch_liquidity_risk_scalar": WATCH_LIQUIDITY_RISK_SCALAR,
            "target_liquidity_tier": TARGET_LIQUIDITY_TIER,
            "accepted_company_release_source_risk_scalar": (
                ACCEPTED_COMPANY_RELEASE_SOURCE_RISK_SCALAR
            ),
            "accepted_financing_dilution_profile_risk_scalar": (
                ACCEPTED_FINANCING_DILUTION_PROFILE_RISK_SCALAR
            ),
            "locked_variables": [
                "official Space candidate pool",
                "base Space risk scalar",
                "accepted Space basket-positive scalar",
                "accepted perfect-TQS risk scalar",
                "accepted near-perfect trend TQS scalar",
                "accepted peer-nonleader breakout scalar",
                "accepted IWM-relative small-cap leader scalar",
                "accepted launch/lunar theme scalar",
                "accepted liquidity_tier=ok scalar",
                "accepted watch-liquidity scalar",
                "accepted broad official customer-source scalar",
                "accepted company-release customer-source scalar",
                "accepted financing/dilution profile scalar",
                "accepted multi-event catalyst-depth scalar",
                "accepted Space trend targets",
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
            "The accepted_before variant reproduces exp-20260513-012 policy semantics."
        ),
        "gate1": {
            "core_baseline": core["aggregate"],
            "accepted_before_metrics": before["aggregate"],
            "known_bias": (
                "Space candidate snapshots are frozen historical replay copies built "
                "from a 2026-05-10 research universe. Source and peer-state fields "
                "are production-visible, but any accepted Space change must remain "
                "default-off until forward evidence matures."
            ),
        },
        "gate2": {
            "open_positions": gate2_open,
            "official_customer_source_profile": source_gate,
            "peer_momentum_state": peer_state_gate,
            "accepted_financing_dilution_profiles": financing_gate,
            "accepted_company_release_source_profile": company_release_gate,
            "watch_liquidity_tier_registry": liquidity_gate,
            "accepted_multi_event_depth": multi_event_gate,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "data/space_catalyst_event_seeds.jsonl event_id",
                "data/space_catalyst_event_seeds.jsonl event_fields",
                "data/space_catalyst_event_seeds.jsonl semantic_bucket",
                "data/space_catalyst_event_seeds.jsonl source_type",
                "data/space_catalyst_event_seeds.jsonl tickers",
                "space_peer_momentum_state from accepted Space signal enrichment",
            ],
            "passed": (
                gate2_open["passed"]
                and source_gate["passed"]
                and peer_state_gate["passed"]
                and financing_gate["passed"]
                and company_release_gate["passed"]
                and liquidity_gate["passed"]
                and multi_event_gate["passed"]
            ),
        },
        "gate3": {
            "new_filter_added": False,
            "new_risk_scalar_added": True,
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
            **{label: row["metrics"] for label, row in best_variant["by_window"].items()},
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
                "Space soft-ranking remains label-limited; this run uses deterministic "
                "production-visible event source and peer-momentum metadata."
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
            "If rejected, do not promote source-qualified peer-leader risk scaling "
            "on these frozen snapshots. Future Space alpha should either wait for "
            "closed forward replacement value by source/peer bucket or test another "
            "production-visible catalyst-quality field with broader coverage."
        ),
        "related_files": [
            "quant/experiments/exp_20260513_014_space_customer_source_peer_leader_risk.py",
            "data/experiments/exp-20260513-014/space_customer_source_peer_leader_risk.json",
            "experiments/logs/exp-20260513-014.json",
            "experiments/tickets/exp-20260513-014.json",
            "experiments/artifacts/exp-20260513-014_space_customer_source_peer_leader_risk.md",
            "docs/experiment_log.jsonl",
            "quant/space_catalyst_sleeve.py",
            "quant/report_generator.py",
            "quant/test_space_catalyst_sleeve.py",
            "docs/alpha-optimization-playbook.md",
            "docs/current_state.md",
            "docs/production_backtest_parity.md",
        ],
        "why_not_other_changes": (
            "LLM soft-ranking is data-limited; noisy ticker additions, watch-liquidity "
            "TQS/peer/strategy scopes, broad defense-budget source scalars, "
            "primary-authority source scalars, contract-profile scalars, generic "
            "peer-leader risk, and cumulative risk caps were already rejected or "
            "underpowered. This tests one new source-quality plus peer-leadership "
            "intersection."
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
