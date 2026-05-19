"""exp-20260512-040: Space defense-budget source risk allocation.

Tests whether the production-observable Space event seed profile for
``defense_budget_theme`` + ``government_space_contract`` from an official
government source deserves extra default-off risk after the accepted
exp-20260512-038 customer-source stack.
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
)
from exp_20260512_038_space_official_customer_source_risk import (
    ACCEPTED_LIQUIDITY_TIER_RISK_SCALAR,
    OFFICIAL_CUSTOMER_SOURCE_RISK_SCALARS,
    TARGET_EVENT_FIELD as ACCEPTED_CUSTOMER_EVENT_FIELD,
    TARGET_SOURCE_TYPES as ACCEPTED_CUSTOMER_SOURCE_TYPES,
    _event_seed_profiles as _customer_event_seed_profiles,
    _install_space_policy as _install_accepted_exp038_policy,
    _run_variant as _run_accepted_exp038_variant,
)
from data_layer import get_universe
import portfolio_engine


logging.basicConfig(level=logging.WARNING)

EXPERIMENT_ID = "exp-20260512-040"
STEM = "space_defense_budget_source_risk"
ACCEPTED_CUSTOMER_SOURCE_RISK_SCALAR = 1.10
TARGET_EVENT_FIELD = "government_space_contract"
TARGET_SEMANTIC_BUCKET = "defense_budget_theme"
TARGET_SOURCE_TYPES = ("official_government_release",)
DEFENSE_BUDGET_SOURCE_RISK_SCALARS = (0.75, 0.90, 1.10, 1.25)


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


def _defense_event_seed_profiles() -> dict[str, Any]:
    path = PROJECT_ROOT / "data" / "space_catalyst_event_seeds.jsonl"
    if not path.exists():
        return {"passed": False, "path": str(path.relative_to(PROJECT_ROOT)), "missing": "file"}

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
        fields = [str(item) for item in row.get("event_fields") or []]
        source_type = str(row.get("source_type") or "")
        semantic_bucket = str(row.get("semantic_bucket") or "")
        if (
            TARGET_EVENT_FIELD not in fields
            or source_type not in TARGET_SOURCE_TYPES
            or semantic_bucket != TARGET_SEMANTIC_BUCKET
        ):
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
            profile["semantic_buckets"].add(semantic_bucket)
            profile["source_types"].add(source_type)

    serialized_profiles = {
        ticker: {
            "event_ids": sorted(profile["event_ids"]),
            "event_fields": sorted(profile["event_fields"]),
            "semantic_buckets": sorted(profile["semantic_buckets"]),
            "source_types": sorted(profile["source_types"]),
        }
        for ticker, profile in sorted(profiles.items())
    }
    target_tickers = sorted(serialized_profiles)
    return {
        "passed": not missing_fields and bool(target_tickers),
        "path": str(path.relative_to(PROJECT_ROOT)),
        "event_seed_count": len(rows),
        "target_event_field": TARGET_EVENT_FIELD,
        "target_semantic_bucket": TARGET_SEMANTIC_BUCKET,
        "target_source_types": list(TARGET_SOURCE_TYPES),
        "target_tickers": target_tickers,
        "profiles": serialized_profiles,
        "source_type_counts": dict(
            sorted(Counter(str(row.get("source_type") or "") for row in rows).items())
        ),
        "semantic_bucket_counts": dict(
            sorted(Counter(str(row.get("semantic_bucket") or "") for row in rows).items())
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


def _install_space_policy(defense_scalar: float, customer_gate: dict[str, Any], defense_gate: dict[str, Any]):
    installed = _install_accepted_exp038_policy(
        ACCEPTED_CUSTOMER_SOURCE_RISK_SCALAR,
        customer_gate,
    )
    (
        original_generate,
        original_enrich,
        original_size,
        customer_adjustments,
        customer_counts,
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
    profiles = defense_gate["profiles"]
    target_tickers = set(defense_gate["target_tickers"])
    defense_adjustments: list[dict[str, Any]] = []
    defense_counts = Counter()

    def size_wrapper(signals, portfolio_value, risk_pct=None):
        sized = accepted_size(signals, portfolio_value, risk_pct=risk_pct)
        out = []
        for signal in sized:
            ticker = str(signal.get("ticker") or "").upper()
            sizing = deepcopy(signal.get("sizing") or {})
            if ticker in target_tickers and sizing:
                defense_counts["eligible_signal"] += 1
                shares_before = int(sizing.get("shares_to_buy") or 0)
                _scale_sizing(
                    sizing,
                    defense_scalar,
                    portfolio_value,
                    "space_defense_budget_source_risk",
                )
                row = _adjustment_row(
                    signal,
                    sizing,
                    shares_before,
                    defense_scalar,
                    "space_defense_budget_source_risk",
                )
                row["space_event_defense_budget_profile"] = profiles.get(ticker)
                row["space_theme_segment"] = signal.get("space_theme_segment")
                defense_adjustments.append(row)
                signal = {
                    **signal,
                    "sizing": sizing,
                    "space_event_defense_budget_profile": profiles.get(ticker),
                    "space_defense_budget_source_eligible": True,
                }
            out.append(signal)
        return out

    portfolio_engine.size_signals = size_wrapper
    return (
        original_generate,
        original_enrich,
        original_size,
        defense_adjustments,
        defense_counts,
        customer_adjustments,
        customer_counts,
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
    defense_scalar: float,
    customer_gate: dict[str, Any],
    defense_gate: dict[str, Any],
) -> dict[str, Any]:
    universe = sorted(set(get_universe()) | set(OFFICIAL_SPACE_TICKERS) | {"IWM", "SPY"})
    (
        original_generate,
        original_enrich,
        original_size,
        defense_adjustments,
        defense_counts,
        customer_adjustments,
        customer_counts,
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
    ) = _install_space_policy(defense_scalar, customer_gate, defense_gate)
    try:
        by_window = {}
        for label, window in WINDOWS.items():
            before_defense = len(defense_adjustments)
            before_customer = len(customer_adjustments)
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
                "space_defense_budget_source_adjustment": _adjustment_summary(
                    defense_adjustments[before_defense:]
                ),
                "space_official_customer_source_adjustment": _adjustment_summary(
                    customer_adjustments[before_customer:]
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
                "space_defense_budget_source_counts": dict(sorted(defense_counts.items())),
                "space_source_eligible_signal_counts": dict(sorted(customer_counts.items())),
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
        "target_semantic_bucket": TARGET_SEMANTIC_BUCKET,
        "target_source_types": list(TARGET_SOURCE_TYPES),
        "target_tickers": defense_gate["target_tickers"],
        "space_defense_budget_source_scalar": defense_scalar,
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
        row["space_defense_budget_source_adjustment"]["adjusted_signal_count"]
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
        "space_defense_budget_source_adjusted_signal_count": adjusted_count,
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    lines = [
        f"# {EXPERIMENT_ID} Space defense-budget source risk",
        "",
        f"- Decision: `{payload['decision']}`",
        (
            "- Single variable: risk scalar for official Space signals whose event "
            "seed profile has `defense_budget_theme` + `government_space_contract` "
            "from an official government source."
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
            f"| {name} | {variant['space_defense_budget_source_scalar']:.2f} | "
            f"{'pass' if gate['passed'] else 'fail'} | "
            f"{delta['expected_value_score_sum']:+.4f} | "
            f"{delta['total_pnl_sum']:+,.2f} | "
            f"{gate['windows_ev_improved_vs_before']} | "
            f"{gate['windows_ev_regressed_vs_before']} | "
            f"{gate['space_defense_budget_source_adjusted_signal_count']} |"
        )
    lines.extend(
        [
            "",
            "## Best Three-Window Comparison",
            "",
            (
                "| Window | Before EV | After EV | dEV | Before PnL | After PnL | "
                "dPnL | Trades | Max DD | Survival | Defense signals |"
            ),
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        adjusted = best["by_window"][label][
            "space_defense_budget_source_adjustment"
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
            json.dumps(payload["gate2"]["defense_budget_source_profile"], sort_keys=True),
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
    customer_gate = _customer_event_seed_profiles()
    if not customer_gate["passed"]:
        raise RuntimeError(f"Customer source field check failed: {customer_gate}")
    defense_gate = _defense_event_seed_profiles()
    if not defense_gate["passed"]:
        raise RuntimeError(f"Defense source field check failed: {defense_gate}")
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
    before = _run_accepted_exp038_variant(
        "accepted_exp038_customer_source_stack",
        ACCEPTED_CUSTOMER_SOURCE_RISK_SCALAR,
        customer_gate,
    )
    variants = {}
    for scalar in DEFENSE_BUDGET_SOURCE_RISK_SCALARS:
        name = f"defense_budget_source_{str(scalar).replace('.', '_')}"
        variants[name] = _run_variant(name, scalar, customer_gate, defense_gate)

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
        "accepted_default_off_space_defense_budget_source_risk"
        if accepted
        else "rejected_space_defense_budget_source_risk"
    )
    interpretation = (
        "The official government defense-budget source scalar improved the accepted "
        "default-off Space stack under the three-window gate. Promotion must remain "
        "production-visible metadata/helper only with live Space slots at zero."
        if accepted
        else (
            "The official government defense-budget source scalar did not clear the "
            "three-window gate on top of exp-20260512-038. Do not retry adjacent "
            "defense-budget source scalars on these frozen snapshots; future Space "
            "work needs forward replacement value or a different catalyst-quality field."
        )
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "risk_allocation_shadow_sweep",
        "changed_variable": "space_defense_budget_source_risk_scalar",
        "single_causal_variable": (
            "risk scalar for official Space signals whose event seed profile has "
            "defense_budget_theme + government_space_contract from official_government_release"
        ),
        "hypothesis": (
            "After customer-source and liquidity/theme/momentum/TQS Space risk "
            "ladders, the next orthogonal production-observable catalyst-quality "
            "field is official government defense-budget validation. It may capture "
            "sector-wide budget-pull risk appetite without adding noisy tickers or "
            "asking the LLM to rank sparse forward events."
        ),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation: scale official Space signals tied to the "
                "defense_budget_theme government_space_contract event seed."
            ),
            "2_history_check": {
                "exp-20260512-038": (
                    "Accepted customer_win primary-source scalar; this run uses it "
                    "as the fixed before state and tests a different event field/source."
                ),
                "exp-20260512-035": (
                    "Rejected data/defense theme-segment scalar; this test avoids "
                    "universe-registry theme_segment and uses event seed semantics."
                ),
                "exp-20260512-023": "Rejected GSAT candidate-pool expansion; no ticker expansion here.",
                "exp-20260511-008": (
                    "Forward event ledger remains below the closed-decision live gate; "
                    "this stays default-off metadata only."
                ),
            },
            "3_single_causal_variable": (
                "space_defense_budget_source_risk_scalar. Candidate pool, accepted "
                "Space scalars, targets, stops, ranking, add-ons, LLM/news, and live "
                "slots stay fixed."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; require positive aggregate "
                "EV/PnL, at least 2/3 improved EV windows, no EV-regressed window, "
                "max drawdown drift <= 0.5 pp, survival >= 5%, >=50 total trades, "
                "and nonzero adjusted defense-source signals."
            ),
            "5_reproducibility": (
                "This script reruns core, accepted exp-20260512-038 Space stack, and "
                "each defense-budget source scalar across the canonical augmented Space snapshots."
            ),
        },
        "parameters": {
            "official_space_tickers": list(OFFICIAL_SPACE_TICKERS),
            "target_event_field": TARGET_EVENT_FIELD,
            "target_semantic_bucket": TARGET_SEMANTIC_BUCKET,
            "target_source_types": list(TARGET_SOURCE_TYPES),
            "target_tickers": defense_gate["target_tickers"],
            "defense_source_profiles": defense_gate["profiles"],
            "tested_defense_budget_source_scalars": list(DEFENSE_BUDGET_SOURCE_RISK_SCALARS),
            "accepted_before_experiment": "exp-20260512-038",
            "accepted_customer_event_field": ACCEPTED_CUSTOMER_EVENT_FIELD,
            "accepted_customer_source_types": list(ACCEPTED_CUSTOMER_SOURCE_TYPES),
            "accepted_customer_source_risk_scalar": ACCEPTED_CUSTOMER_SOURCE_RISK_SCALAR,
            "accepted_customer_source_tested_scalars": list(OFFICIAL_CUSTOMER_SOURCE_RISK_SCALARS),
            "theme_segments": SPACE_THEME_SEGMENTS,
            "accepted_launch_lunar_theme_segment": ACCEPTED_THEME_SEGMENT,
            "accepted_launch_lunar_theme_scalar": 1.10,
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
                "accepted customer-source 1.10x scalar",
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
            "The accepted_before variant reproduces exp-20260512-038 policy semantics."
        ),
        "gate1": {
            "core_baseline": core["aggregate"],
            "accepted_before_metrics": before["aggregate"],
            "known_bias": (
                "Space candidate snapshots are frozen historical replay copies built "
                "from a 2026-05-10 research universe. Event seed fields are production-"
                "observable, but any accepted change must remain default-off until "
                "forward replacement-value evidence matures."
            ),
        },
        "gate2": {
            "open_positions": gate2,
            "customer_source_profile": customer_gate,
            "defense_budget_source_profile": defense_gate,
            "theme_segment_registry": theme_gate,
            "liquidity_tier_registry": liquidity_gate,
            "iwm_spy_snapshot_coverage": benchmark_gate,
            "passed": gate2["passed"]
            and customer_gate["passed"]
            and defense_gate["passed"]
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
            "If rejected, do not retry adjacent defense-budget source risk scalars "
            "on the same frozen snapshots. Future Space work should use forward "
            "event replacement value or a genuinely different catalyst-quality field."
        ),
        "related_files": [
            "quant/experiments/exp_20260512_040_space_defense_budget_source_risk.py",
            "data/experiments/exp-20260512-040/space_defense_budget_source_risk.json",
            "experiments/logs/exp-20260512-040.json",
            "experiments/tickets/exp-20260512-040.json",
            "experiments/artifacts/exp-20260512-040_space_defense_budget_source_risk.md",
            "docs/experiment_log.jsonl",
        ],
        "why_not_other_changes": (
            "LLM soft-ranking is data-limited; GSAT and mature satcom candidate "
            "expansions are rejected; recent Space TQS, IWM, peer, 52w, breadth, "
            "R/R, volume, launch/lunar, data/defense theme, liquidity, and customer-"
            "source variants are either fixed accepted context or anti-repeat."
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
