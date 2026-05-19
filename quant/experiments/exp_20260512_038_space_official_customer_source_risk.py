"""exp-20260512-038: Space official customer-source risk allocation.

Tests whether production-observable Space event-source metadata identifies a
better risk allocation pocket after the accepted exp-20260512-037 stack. The
single changed variable is the risk scalar for official Space signals whose
current event seed profile has ``event_fields`` containing ``customer_win`` and
whose ``source_type`` is an official, regulatory, or company primary source.
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
from exp_20260512_009_space_peer_momentum_leader_risk import (
    ACCEPTED_SPACE_BASKET_POSITIVE_SCALAR,
    ACCEPTED_SPACE_NEAR_PERFECT_TQS_SCORE_CEILING,
    ACCEPTED_SPACE_NEAR_PERFECT_TQS_SCORE_FLOOR,
    ACCEPTED_SPACE_NEAR_PERFECT_TQS_TREND_RISK_SCALAR,
    ACCEPTED_SPACE_PERFECT_TQS_RISK_SCALAR,
    _adjustment_row,
)
from exp_20260512_031_space_iwm_relative_momentum_risk import (
    ACCEPTED_PEER_NONLEADER_BREAKOUT_SCALAR,
    BENCHMARK_FIELD,
    _field_check_iwm_spy_snapshots,
)
from exp_20260512_032_space_launch_lunar_theme_risk import (
    ACCEPTED_IWM_RELATIVE_STATE_SCALARS,
    SPACE_THEME_SEGMENTS,
    TARGET_THEME_SEGMENT as ACCEPTED_THEME_SEGMENT,
    THEME_SEGMENT_RISK_SCALARS as ACCEPTED_THEME_SEGMENT_RISK_SCALARS,
    _field_check_theme_segments,
)
from exp_20260512_037_space_liquidity_tier_risk import (
    LIQUIDITY_TIER_RISK_SCALARS as ACCEPTED_LIQUIDITY_TIER_RISK_SCALARS,
    TARGET_LIQUIDITY_TIER as ACCEPTED_LIQUIDITY_TIER,
    _field_check_liquidity_tier,
    _install_space_policy as _install_accepted_exp037_policy,
    _run_variant as _run_accepted_exp037_variant,
)
from data_layer import get_universe
import portfolio_engine


logging.basicConfig(level=logging.WARNING)

EXPERIMENT_ID = "exp-20260512-038"
STEM = "space_official_customer_source_risk"
ACCEPTED_LAUNCH_LUNAR_THEME_SCALAR = 1.10
ACCEPTED_LIQUIDITY_TIER_RISK_SCALAR = 1.10
TARGET_EVENT_FIELD = "customer_win"
TARGET_SOURCE_TYPES = (
    "official_or_primary_release",
    "official_regulatory_release",
    "company_release",
)
OFFICIAL_CUSTOMER_SOURCE_RISK_SCALARS = (0.75, 0.90, 1.10, 1.25)


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


def _event_seed_profiles() -> dict[str, Any]:
    path = PROJECT_ROOT / "data" / "space_catalyst_event_seeds.jsonl"
    if not path.exists():
        return {
            "passed": False,
            "path": str(path.relative_to(PROJECT_ROOT)),
            "missing": "file",
        }

    rows = []
    missing_fields = []
    profiles: dict[str, dict[str, Any]] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        rows.append(row)
        required_missing = [
            field
            for field in ("event_id", "event_fields", "semantic_bucket", "source_type", "tickers")
            if not row.get(field)
        ]
        if required_missing:
            missing_fields.append(
                {
                    "line_number": line_number,
                    "event_id": row.get("event_id"),
                    "missing": required_missing,
                }
            )
        source_type = str(row.get("source_type") or "")
        fields = [str(item) for item in row.get("event_fields") or []]
        if source_type not in TARGET_SOURCE_TYPES or TARGET_EVENT_FIELD not in fields:
            continue
        for ticker in row.get("tickers") or []:
            ticker = str(ticker or "").upper()
            if ticker not in OFFICIAL_SPACE_TICKERS:
                continue
            profile = profiles.setdefault(
                ticker,
                {
                    "event_ids": [],
                    "event_fields": set(),
                    "semantic_buckets": set(),
                    "source_types": set(),
                },
            )
            profile["event_ids"].append(row.get("event_id"))
            profile["event_fields"].update(fields)
            profile["semantic_buckets"].add(row.get("semantic_bucket"))
            profile["source_types"].add(source_type)

    serialized_profiles = {}
    for ticker, profile in profiles.items():
        serialized_profiles[ticker] = {
            "event_ids": sorted(profile["event_ids"]),
            "event_fields": sorted(profile["event_fields"]),
            "semantic_buckets": sorted(profile["semantic_buckets"]),
            "source_types": sorted(profile["source_types"]),
        }

    target_tickers = sorted(serialized_profiles)
    return {
        "passed": not missing_fields and bool(target_tickers),
        "path": str(path.relative_to(PROJECT_ROOT)),
        "event_seed_count": len(rows),
        "target_event_field": TARGET_EVENT_FIELD,
        "target_source_types": list(TARGET_SOURCE_TYPES),
        "target_tickers": target_tickers,
        "profiles": serialized_profiles,
        "source_type_counts": dict(
            sorted(Counter(str(row.get("source_type") or "") for row in rows).items())
        ),
        "event_field_counts": dict(
            sorted(
                Counter(
                    field
                    for row in rows
                    for field in (row.get("event_fields") or [])
                ).items()
            )
        ),
        "missing_required_fields": missing_fields,
    }


def _install_space_policy(source_scalar: float, source_gate: dict[str, Any]):
    installed = _install_accepted_exp037_policy(ACCEPTED_LIQUIDITY_TIER_RISK_SCALAR)
    (
        original_generate,
        original_enrich,
        original_size,
        liquidity_adjustments,
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
    profiles = source_gate["profiles"]
    target_tickers = set(source_gate["target_tickers"])
    source_adjustments: list[dict[str, Any]] = []
    source_counts = Counter()

    def size_wrapper(signals, portfolio_value, risk_pct=None):
        sized = accepted_size(signals, portfolio_value, risk_pct=risk_pct)
        out = []
        for signal in sized:
            ticker = str(signal.get("ticker") or "").upper()
            sizing = deepcopy(signal.get("sizing") or {})
            if ticker in target_tickers and sizing:
                source_counts["eligible_signal"] += 1
                shares_before = int(sizing.get("shares_to_buy") or 0)
                _scale_sizing(
                    sizing,
                    source_scalar,
                    portfolio_value,
                    "space_official_customer_source_risk",
                )
                row = _adjustment_row(
                    signal,
                    sizing,
                    shares_before,
                    source_scalar,
                    "space_official_customer_source_risk",
                )
                row["space_event_source_profile"] = profiles.get(ticker)
                row["space_theme_segment"] = signal.get("space_theme_segment")
                source_adjustments.append(row)
                signal = {
                    **signal,
                    "sizing": sizing,
                    "space_event_source_profile": profiles.get(ticker),
                    "space_official_customer_source_eligible": True,
                }
            out.append(signal)
        return out

    portfolio_engine.size_signals = size_wrapper
    return (
        original_generate,
        original_enrich,
        original_size,
        source_adjustments,
        source_counts,
        liquidity_adjustments,
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
    source_scalar: float,
    source_gate: dict[str, Any],
) -> dict[str, Any]:
    universe = sorted(set(get_universe()) | set(OFFICIAL_SPACE_TICKERS) | {"IWM", "SPY"})
    (
        original_generate,
        original_enrich,
        original_size,
        source_adjustments,
        source_counts,
        liquidity_adjustments,
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
    ) = _install_space_policy(source_scalar, source_gate)
    try:
        by_window = {}
        for label, window in WINDOWS.items():
            before_source = len(source_adjustments)
            before_liquidity = len(liquidity_adjustments)
            before_theme = len(theme_adjustments)
            before_iwm = len(iwm_adjustments)
            before_peer = len(peer_nonleader_breakout_adjustments)
            before_near = len(near_perfect_adjustments)
            before_perfect = len(perfect_adjustments)
            before_basket = len(basket_adjustments)
            result = _run_window(window, universe, "space_snapshot")
            metrics = _metrics(result)
            by_window[label] = {
                "metrics": metrics,
                "space_trade_attribution": _space_trade_attribution(result),
                "space_official_customer_source_adjustment": _adjustment_summary(
                    source_adjustments[before_source:]
                ),
                "space_liquidity_tier_adjustment": _adjustment_summary(
                    liquidity_adjustments[before_liquidity:]
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
        "target_event_field": TARGET_EVENT_FIELD,
        "target_source_types": list(TARGET_SOURCE_TYPES),
        "target_tickers": source_gate["target_tickers"],
        "space_official_customer_source_scalar": source_scalar,
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
        row["space_official_customer_source_adjustment"]["adjusted_signal_count"]
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
        "space_official_customer_source_adjusted_signal_count": adjusted_count,
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    lines = [
        f"# {EXPERIMENT_ID} Space official customer-source risk",
        "",
        f"- Decision: `{payload['decision']}`",
        (
            "- Single variable: risk scalar for official Space signals whose event "
            "seed profile has `customer_win` from official/regulatory/company sources."
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
            f"| {name} | {variant['space_official_customer_source_scalar']:.2f} | "
            f"{'pass' if gate['passed'] else 'fail'} | "
            f"{delta['expected_value_score_sum']:+.4f} | "
            f"{delta['total_pnl_sum']:+,.2f} | "
            f"{gate['windows_ev_improved_vs_before']} | "
            f"{gate['windows_ev_regressed_vs_before']} | "
            f"{gate['space_official_customer_source_adjusted_signal_count']} |"
        )
    lines.extend(
        [
            "",
            "## Best Three-Window Comparison",
            "",
            (
                "| Window | Before EV | After EV | dEV | Before PnL | After PnL | "
                "dPnL | Trades | Max DD | Survival | Source signals |"
            ),
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        adjusted = best["by_window"][label][
            "space_official_customer_source_adjustment"
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
            json.dumps(payload["gate2"]["official_customer_source_profile"], sort_keys=True),
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
    source_gate = _event_seed_profiles()
    if not source_gate["passed"]:
        raise RuntimeError(f"Event source field check failed: {source_gate}")
    theme_gate = _field_check_theme_segments()
    if not theme_gate["passed"]:
        raise RuntimeError(f"Theme segment field check failed: {theme_gate}")
    liquidity_gate = _field_check_liquidity_tier()
    if not liquidity_gate["passed"]:
        raise RuntimeError(f"Liquidity field check failed: {liquidity_gate}")
    benchmark_gate = _field_check_iwm_spy_snapshots()
    if not benchmark_gate["passed"]:
        raise RuntimeError(f"IWM/SPY snapshot field check failed: {benchmark_gate}")

    core = _run_core_baseline()
    before = _run_accepted_exp037_variant(
        "accepted_exp037_liquidity_stack",
        ACCEPTED_LIQUIDITY_TIER_RISK_SCALAR,
    )
    variants = {}
    for scalar in OFFICIAL_CUSTOMER_SOURCE_RISK_SCALARS:
        name = f"official_customer_source_{str(scalar).replace('.', '_')}"
        variants[name] = _run_variant(name, scalar, source_gate)

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
        "accepted_default_off_space_official_customer_source_risk"
        if accepted
        else "rejected_space_official_customer_source_risk"
    )
    interpretation = (
        "The official customer-source risk scalar improved the accepted default-off "
        "Space stack under the three-window gate. Promotion must be wired through "
        "shared production-visible source metadata only; live Space slots remain zero."
        if accepted
        else (
            "The official customer-source risk scalar did not clear the three-window "
            "gate on top of exp-20260512-037. Do not retry adjacent source-quality "
            "risk scalars on these frozen snapshots; the next Space edge needs "
            "forward replacement value or a different non-overlapping catalyst field."
        )
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "risk_allocation_shadow_sweep",
        "changed_variable": "space_official_customer_source_risk_scalar",
        "single_causal_variable": (
            "risk scalar for official Space signals whose event seed profile has "
            "customer_win from official_or_primary_release, official_regulatory_release, "
            "or company_release source_type"
        ),
        "hypothesis": (
            "Recent Space retunes have exhausted ticker/theme/momentum micro-slices, "
            "while LLM soft-ranking and forward replacement ledgers remain too thin. "
            "A production-observable catalyst-quality pocket may still exist when "
            "the source is a primary customer/regulatory/company-win event rather "
            "than attention-only or broad defense-budget theme flow."
        ),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation: scale only official Space signals associated with "
                "customer_win event seeds from primary official/regulatory/company sources."
            ),
            "2_history_check": {
                "exp-20260512-037": (
                    "Accepted liquidity_tier=ok 1.10x scalar; this is the fixed "
                    "before state and includes earlier accepted Space scalars."
                ),
                "exp-20260512-035": (
                    "Rejected data/defense theme-segment scalar; this test avoids "
                    "theme_segment and uses source_type/event_fields instead."
                ),
                "exp-20260511-008": (
                    "Forward event-state attribution exists but is too immature for "
                    "live promotion; source metadata can only be tested default-off."
                ),
                "exp-20260512-023": (
                    "Rejected GSAT candidate-pool expansion; no ticker expansion here."
                ),
            },
            "3_single_causal_variable": (
                "space_official_customer_source_risk_scalar. Candidate pool, accepted "
                "Space risk scalars, targets, stops, ranking, add-ons, LLM/news, and "
                "live slots stay fixed."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; require positive aggregate "
                "EV/PnL, at least 2/3 improved EV windows, no EV-regressed window, "
                "max drawdown drift <= 0.5 pp, survival >= 5%, >=50 total trades, "
                "and nonzero adjusted source-qualified signals."
            ),
            "5_reproducibility": (
                "This script reruns core, accepted exp-20260512-037 Space stack, and "
                "each source-quality scalar across the canonical augmented Space snapshots."
            ),
        },
        "parameters": {
            "official_space_tickers": list(OFFICIAL_SPACE_TICKERS),
            "target_event_field": TARGET_EVENT_FIELD,
            "target_source_types": list(TARGET_SOURCE_TYPES),
            "target_tickers": source_gate["target_tickers"],
            "source_profiles": source_gate["profiles"],
            "tested_source_scalars": list(OFFICIAL_CUSTOMER_SOURCE_RISK_SCALARS),
            "theme_segments": SPACE_THEME_SEGMENTS,
            "accepted_before_experiment": "exp-20260512-037",
            "accepted_launch_lunar_theme_segment": ACCEPTED_THEME_SEGMENT,
            "accepted_launch_lunar_theme_scalar": ACCEPTED_LAUNCH_LUNAR_THEME_SCALAR,
            "accepted_launch_lunar_tested_scalars": list(ACCEPTED_THEME_SEGMENT_RISK_SCALARS),
            "accepted_liquidity_tier": ACCEPTED_LIQUIDITY_TIER,
            "accepted_liquidity_tier_risk_scalar": ACCEPTED_LIQUIDITY_TIER_RISK_SCALAR,
            "accepted_liquidity_tier_tested_scalars": list(
                ACCEPTED_LIQUIDITY_TIER_RISK_SCALARS
            ),
            "accepted_iwm_relative_state_scalars": ACCEPTED_IWM_RELATIVE_STATE_SCALARS,
            "accepted_iwm_benchmark_field": BENCHMARK_FIELD,
            "accepted_peer_nonleader_breakout_scalar": (
                ACCEPTED_PEER_NONLEADER_BREAKOUT_SCALAR
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
            "data_vendor_tickers": list(DATA_VENDOR_TICKERS),
            "launch_connectivity_tickers": list(LAUNCH_CONNECTIVITY_TICKERS),
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
                "accepted IWM-relative small-cap leader 1.10x scalar",
                "accepted launch/lunar theme 1.10x scalar",
                "accepted liquidity_tier=ok 1.10x scalar",
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
            "The accepted_before variant reproduces exp-20260512-037 policy semantics."
        ),
        "gate1": {
            "core_baseline": core["aggregate"],
            "accepted_before_metrics": before["aggregate"],
            "known_bias": (
                "Space candidate snapshots are frozen historical replay copies built "
                "from a 2026-05-10 research universe. Source metadata is production-"
                "observable in the event seed ledger, but any accepted change must "
                "remain default-off until forward evidence matures."
            ),
        },
        "gate2": {
            "open_positions": gate2,
            "official_customer_source_profile": source_gate,
            "theme_segment_registry": theme_gate,
            "liquidity_tier_registry": liquidity_gate,
            "iwm_spy_snapshot_coverage": benchmark_gate,
            "passed": gate2["passed"]
            and source_gate["passed"]
            and theme_gate["passed"]
            and liquidity_gate["passed"]
            and benchmark_gate["passed"],
        },
        "gate3": {
            "new_filter_added": False,
            "new_source_quality_scalar_added": True,
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
                "gate; this run uses deterministic event seed source metadata."
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
            "If rejected, do not retry adjacent official customer-source risk scalars "
            "on the same frozen snapshots. Future Space work should use forward "
            "event replacement value or a genuinely different production-observable "
            "catalyst-quality field."
        ),
        "related_files": [
            "quant/experiments/exp_20260512_038_space_official_customer_source_risk.py",
            "data/experiments/exp-20260512-038/space_official_customer_source_risk.json",
            "experiments/logs/exp-20260512-038.json",
            "experiments/tickets/exp-20260512-038.json",
            "experiments/artifacts/exp-20260512-038_space_official_customer_source_risk.md",
            "docs/experiment_log.jsonl",
        ],
        "why_not_other_changes": (
            "LLM soft-ranking is data-limited; GSAT and mature satcom candidate "
            "expansions are rejected; SEC paper work needs forward outcomes; recent "
            "Space TQS, IWM, peer, 52w, breadth, R/R, volume, launch/lunar, and "
            "data/defense variants are either accepted context or anti-repeat."
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
