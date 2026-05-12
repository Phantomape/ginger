"""exp-20260512-104: Space contract-sensitive profile risk allocation.

Tests one causal variable on top of the accepted exp-20260512-041 default-off
Space stack: an extra risk scalar for official Space signals whose production
universe-registry event_guard_profile mentions contract sensitivity but does
not mention financing or dilution.
"""

from __future__ import annotations

import json
import logging
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
    _install_space_policy as _install_accepted_exp041_policy,
    _run_variant as _run_accepted_exp041_variant,
)
from data_layer import get_universe  # noqa: E402
import portfolio_engine  # noqa: E402


logging.basicConfig(level=logging.WARNING)

EXPERIMENT_ID = "exp-20260512-104"
STEM = "space_contract_profile_risk"
ACCEPTED_FINANCING_DILUTION_PROFILE_RISK_SCALAR = 1.075
TARGET_PROFILE_TERM = "contract"
EXCLUDED_PROFILE_TERMS = ("financing", "dilution")
CONTRACT_PROFILE_RISK_SCALARS = (0.50, 0.75, 0.90, 1.00, 1.05, 1.075, 1.10, 1.25)


def _append_jsonl_for_this_experiment(path: Path, payload: dict[str, Any]) -> None:
    compact = json.dumps(_safe(payload), ensure_ascii=False, separators=(",", ":"))
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        lines = [
            line.lstrip("\ufeff")
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
        ]
    else:
        lines = []
    lines.append(compact)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _official_space_registry() -> dict[str, dict[str, Any]]:
    path = PROJECT_ROOT / "data" / "universe_registry.json"
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    records = payload.get("tickers") or {}
    return {ticker: records.get(ticker) or {} for ticker in OFFICIAL_SPACE_TICKERS}


def _field_check_contract_profiles() -> dict[str, Any]:
    records = _official_space_registry()
    missing = []
    profiles: dict[str, str] = {}
    target_tickers = []
    excluded_tickers = []
    for ticker, record in records.items():
        profile = str(record.get("event_guard_profile") or "")
        if not profile:
            missing.append(ticker)
            continue
        profile_lower = profile.lower()
        profiles[ticker] = profile
        if any(term in profile_lower for term in EXCLUDED_PROFILE_TERMS):
            excluded_tickers.append(ticker)
            continue
        if TARGET_PROFILE_TERM in profile_lower:
            target_tickers.append(ticker)
    return {
        "passed": not missing and bool(target_tickers),
        "path": "data/universe_registry.json",
        "field": "event_guard_profile",
        "target_profile_term": TARGET_PROFILE_TERM,
        "excluded_profile_terms": list(EXCLUDED_PROFILE_TERMS),
        "target_tickers": sorted(target_tickers),
        "excluded_financing_or_dilution_tickers": sorted(excluded_tickers),
        "profiles": dict(sorted(profiles.items())),
        "missing_event_guard_profile": sorted(missing),
    }


def _install_space_policy(
    contract_scalar: float,
    contract_gate: dict[str, Any],
    financing_gate: dict[str, Any],
    source_gate: dict[str, Any],
) -> tuple[Any, ...]:
    installed = _install_accepted_exp041_policy(
        ACCEPTED_FINANCING_DILUTION_PROFILE_RISK_SCALAR,
        financing_gate,
        source_gate,
    )
    (
        original_generate,
        original_enrich,
        original_size,
        financing_adjustments,
        financing_counts,
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
    ) = installed

    accepted_size = portfolio_engine.size_signals
    target_tickers = set(contract_gate["target_tickers"])
    profiles = contract_gate["profiles"]
    contract_adjustments: list[dict[str, Any]] = []
    contract_counts = Counter()

    def size_wrapper(signals, portfolio_value, risk_pct=None):
        sized = accepted_size(signals, portfolio_value, risk_pct=risk_pct)
        out = []
        for signal in sized:
            ticker = str(signal.get("ticker") or "").upper()
            sizing = deepcopy(signal.get("sizing") or {})
            if ticker in target_tickers and sizing:
                contract_counts["eligible_signal"] += 1
                shares_before = int(sizing.get("shares_to_buy") or 0)
                _scale_sizing(
                    sizing,
                    contract_scalar,
                    portfolio_value,
                    "space_contract_profile_risk",
                )
                contract_adjustments.append(
                    {
                        "ticker": ticker,
                        "strategy": signal.get("strategy"),
                        "marker": "space_contract_profile_risk",
                        "event_guard_profile": profiles.get(ticker),
                        "scalar": contract_scalar,
                        "shares_before_scalar": shares_before,
                        "shares_after_scalar": int(sizing.get("shares_to_buy") or 0),
                        "trade_quality_score": signal.get("trade_quality_score"),
                        "confidence_score": signal.get("confidence_score"),
                    }
                )
                signal = {
                    **signal,
                    "sizing": sizing,
                    "space_contract_profile": profiles.get(ticker),
                    "space_contract_profile_eligible": True,
                }
            out.append(signal)
        return out

    portfolio_engine.size_signals = size_wrapper
    return (
        original_generate,
        original_enrich,
        original_size,
        contract_adjustments,
        contract_counts,
        financing_adjustments,
        financing_counts,
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
    contract_scalar: float,
    contract_gate: dict[str, Any],
    financing_gate: dict[str, Any],
    source_gate: dict[str, Any],
) -> dict[str, Any]:
    universe = sorted(set(get_universe()) | set(OFFICIAL_SPACE_TICKERS) | {"IWM", "SPY"})
    (
        original_generate,
        original_enrich,
        original_size,
        contract_adjustments,
        contract_counts,
        financing_adjustments,
        financing_counts,
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
    ) = _install_space_policy(contract_scalar, contract_gate, financing_gate, source_gate)
    try:
        by_window = {}
        for label, window in WINDOWS.items():
            before_contract = len(contract_adjustments)
            before_financing = len(financing_adjustments)
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
                "space_contract_profile_adjustment": _adjustment_summary(
                    contract_adjustments[before_contract:]
                ),
                "space_financing_dilution_profile_adjustment": _adjustment_summary(
                    financing_adjustments[before_financing:]
                ),
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
                "space_contract_profile_signal_counts": dict(
                    sorted(contract_counts.items())
                ),
                "space_financing_profile_signal_counts": dict(
                    sorted(financing_counts.items())
                ),
                "space_source_signal_counts": dict(sorted(source_counts.items())),
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
        "target_profile_term": TARGET_PROFILE_TERM,
        "excluded_profile_terms": list(EXCLUDED_PROFILE_TERMS),
        "target_tickers": contract_gate["target_tickers"],
        "space_contract_profile_scalar": contract_scalar,
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
        row["space_contract_profile_adjustment"]["adjusted_signal_count"]
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
        and variant["space_contract_profile_scalar"] != 1.0
    )
    return {
        "passed": passed,
        "aggregate_delta_vs_before": aggregate_delta,
        "aggregate_delta_vs_core": aggregate_delta_vs_core,
        "by_window_delta_vs_before": by_window_delta,
        "windows_ev_improved_vs_before": windows_ev_improved,
        "windows_ev_regressed_vs_before": windows_ev_regressed,
        "max_drawdown_change_vs_before": aggregate_delta["max_drawdown_pct_max"],
        "space_contract_profile_adjusted_signal_count": adjusted_count,
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    lines = [
        f"# {EXPERIMENT_ID} Space contract-sensitive profile risk",
        "",
        f"- Decision: `{payload['decision']}`",
        (
            "- Single variable: risk scalar for official Space signals whose "
            "`event_guard_profile` contains `contract` but not `financing` or "
            "`dilution`."
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
            f"| {name} | {variant['space_contract_profile_scalar']:.3f} | "
            f"{'pass' if gate['passed'] else 'fail'} | "
            f"{delta['expected_value_score_sum']:+.4f} | "
            f"{delta['total_pnl_sum']:+,.2f} | "
            f"{gate['windows_ev_improved_vs_before']} | "
            f"{gate['windows_ev_regressed_vs_before']} | "
            f"{gate['space_contract_profile_adjusted_signal_count']} |"
        )
    lines.extend(
        [
            "",
            "## Best Three-Window Comparison",
            "",
            (
                "| Window | Before EV | After EV | dEV | Before PnL | After PnL | "
                "dPnL | Trades | Max DD | Survival | Contract signals |"
            ),
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        adjusted = best["by_window"][label]["space_contract_profile_adjustment"][
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
            "## Field Check",
            "",
            json.dumps(payload["gate2"]["contract_profiles"], sort_keys=True),
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
    financing_gate = _accepted_financing_profile_gate()
    if not financing_gate["passed"]:
        raise RuntimeError(f"Accepted financing profile field check failed: {financing_gate}")
    contract_gate = _field_check_contract_profiles()
    if not contract_gate["passed"]:
        raise RuntimeError(f"Contract profile field check failed: {contract_gate}")

    core = _run_core_baseline()
    before = _run_accepted_exp041_variant(
        "accepted_exp041_financing_dilution_stack",
        ACCEPTED_FINANCING_DILUTION_PROFILE_RISK_SCALAR,
        financing_gate,
        source_gate,
    )
    variants = {}
    for scalar in CONTRACT_PROFILE_RISK_SCALARS:
        name = f"contract_profile_{str(scalar).replace('.', '_')}"
        variants[name] = _run_variant(
            name,
            scalar,
            contract_gate,
            financing_gate,
            source_gate,
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
        "accepted_default_off_space_contract_profile_risk"
        if accepted
        else "rejected_space_contract_profile_risk"
    )
    interpretation = (
        "Contract-sensitive non-financing Space registry profiles improved the "
        "accepted default-off Space stack under the three-window gate. Promotion "
        "must stay shared and metadata-only with live Space slots at zero."
        if accepted
        else (
            "Contract-sensitive non-financing Space registry profiles did not "
            "clear the three-window gate on top of exp-20260512-041. This argues "
            "against more adjacent registry-profile scalar mining on the frozen "
            "Space snapshots without forward replacement-value evidence."
        )
    )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "risk_allocation_shadow_sweep",
        "changed_variable": "space_contract_event_guard_profile_risk_scalar",
        "single_causal_variable": (
            "risk scalar for official Space signals whose production registry "
            "event_guard_profile contains contract but excludes financing/dilution"
        ),
        "hypothesis": (
            "After accepted Space source, liquidity, theme, and financing/dilution "
            "allocation, the next testable production-visible catalyst-quality "
            "field is contract-sensitive registry profiles outside explicit "
            "financing/dilution risk. If customer or defense contracts create "
            "replacement value, a narrow scalar should improve EV without adding "
            "noise tickers or changing live slots."
        ),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "risk allocation: scale only official Space signals whose "
                "event_guard_profile includes contract but not financing/dilution."
            ),
            "2_history_check": {
                "exp-20260512-041": (
                    "Accepted financing/dilution event-guard profile 1.075x; this "
                    "is the fixed before state."
                ),
                "exp-20260512-043": (
                    "Mission-binary profile scalar was immaterial; this test uses "
                    "a broader contract-sensitive profile bucket with financing "
                    "and dilution explicitly excluded."
                ),
                "exp-20260512-040": (
                    "Broad defense-budget/government-contract source scalar was "
                    "rejected due drawdown; this test uses registry profile terms, "
                    "not broad source exposure."
                ),
                "exp-20260512-035": (
                    "Data/defense theme scalar was rejected; this test is not a "
                    "theme_segment scalar and changes no candidate pool."
                ),
                "exp-20260512-023": (
                    "GSAT candidate-pool expansion was rejected; no ticker expansion here."
                ),
            },
            "3_single_causal_variable": (
                "space_contract_event_guard_profile_risk_scalar. Candidate pool, "
                "accepted Space scalars, targets, stops, ranking, add-ons, "
                "LLM/news, and live slots stay fixed."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; require positive aggregate "
                "EV/PnL, at least 2/3 improved EV windows, no EV-regressed window, "
                "max drawdown drift <= 0.5 pp, survival >= 5%, >=50 total trades, "
                "and nonzero adjusted contract-profile signals."
            ),
            "5_reproducibility": (
                "Run .venv\\Scripts\\python.exe "
                "quant\\experiments\\exp_20260512_104_space_contract_profile_risk.py"
            ),
        },
        "parameters": {
            "official_space_tickers": list(OFFICIAL_SPACE_TICKERS),
            "target_profile_term": TARGET_PROFILE_TERM,
            "excluded_profile_terms": list(EXCLUDED_PROFILE_TERMS),
            "target_tickers": contract_gate["target_tickers"],
            "event_guard_profiles": contract_gate["profiles"],
            "tested_contract_profile_scalars": list(CONTRACT_PROFILE_RISK_SCALARS),
            "accepted_before_experiment": "exp-20260512-041",
            "accepted_financing_dilution_profile_risk_scalar": (
                ACCEPTED_FINANCING_DILUTION_PROFILE_RISK_SCALAR
            ),
            "locked_variables": [
                "official Space candidate pool",
                "base Space risk scalar",
                "PL/BKSY breakout haircut",
                "RKLB/ASTS trend top-up",
                "accepted Space basket-positive scalar",
                "accepted perfect-TQS risk scalar",
                "accepted near-perfect trend TQS scalar",
                "accepted peer-nonleader breakout scalar",
                "accepted IWM-relative small-cap leader scalar",
                "accepted launch/lunar theme scalar",
                "accepted liquidity_tier=ok scalar",
                "accepted official customer-source scalar",
                "accepted financing/dilution profile scalar",
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
            "The accepted_before variant reproduces exp-20260512-041 policy semantics."
        ),
        "gate1": {
            "core_baseline": core["aggregate"],
            "accepted_before_metrics": before["aggregate"],
            "known_bias": (
                "Space candidate snapshots are frozen historical replay copies built "
                "from a 2026-05-10 research universe. Registry event_guard_profile "
                "metadata is production-observable, but any accepted change must "
                "remain default-off until forward evidence matures."
            ),
        },
        "gate2": {
            "open_positions": gate2,
            "official_customer_source_profile": source_gate,
            "accepted_financing_profiles": financing_gate,
            "contract_profiles": contract_gate,
            "passed": (
                gate2["passed"]
                and source_gate["passed"]
                and financing_gate["passed"]
                and contract_gate["passed"]
            ),
        },
        "gate3": {
            "new_filter_added": False,
            "new_contract_profile_scalar_added": True,
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
                "gate; this run uses deterministic production registry metadata."
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
            "Do not retry adjacent contract/event-guard profile scalars on these "
            "frozen snapshots. Future Space profile work needs forward replacement "
            "value or a genuinely different production-observable catalyst field."
        ),
        "related_files": [
            "quant/experiments/exp_20260512_104_space_contract_profile_risk.py",
            "data/experiments/exp-20260512-104/space_contract_profile_risk.json",
            "docs/experiments/logs/exp-20260512-104.json",
            "docs/experiments/tickets/exp-20260512-104.json",
            "docs/experiments/artifacts/exp-20260512-104_space_contract_profile_risk.md",
            "docs/experiment_log.jsonl",
        ],
        "why_not_other_changes": (
            "LLM soft-ranking is data-limited; noisy Space ticker additions, GSAT, "
            "and mature satcom were rejected; broad defense-budget/government-contract "
            "source scaling failed drawdown; this test keeps the pool fixed and "
            "uses one production-visible registry field."
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
