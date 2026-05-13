"""exp-20260513-038: Space official source-diversity risk.

Tests one causal variable on top of the accepted exp-20260513-032 default-off
Space stack: a risk scalar for official Space tickers whose non-attention event
seeds span multiple official source types and multiple semantic catalyst
families. This is intentionally not ticker-pool expansion, LLM soft-ranking, or
another event-count retune. It asks whether heterogeneous official evidence
earns different risk allocation than single-channel official evidence.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = PROJECT_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (str(QUANT_DIR), str(EXPERIMENTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import portfolio_engine
from data_layer import get_universe
from exp_20260513_032_space_attention_overlay_risk import (
    ACCEPTED_COMPANY_RELEASE_SOURCE_RISK_SCALAR,
    ACCEPTED_CUSTOMER_SOURCE_PEER_LEADER_RISK_SCALAR,
    ACCEPTED_FINANCING_DILUTION_PROFILE_RISK_SCALAR,
    ACCEPTED_GOVERNMENT_CONTRACT_PEER_LEADER_RISK_SCALAR,
    ACCEPTED_IWM_PEER_LEADER_TREND_RISK_SCALAR,
    ACCEPTED_MULTI_EVENT_DEPTH_RISK_SCALAR,
    ACCEPTED_SINGLE_EVENT_DEFENSE_RISK_SCALAR,
    EXCLUDED_SEMANTIC_BUCKETS,
    EXPERIMENT_ID as BEFORE_EXPERIMENT_ID,
    MULTI_EVENT_MIN_COUNT,
    OFFICIAL_NON_ATTENTION_SOURCE_TYPES,
    OFFICIAL_SPACE_TICKERS,
    TARGET_LIQUIDITY_TIER,
    WATCH_LIQUIDITY_RISK_SCALAR,
    WINDOWS,
    _accepted_financing_profile_gate,
    _adjustment_summary,
    _aggregate,
    _aggregate_delta,
    _delta,
    _event_seed_profiles,
    _field_check_attention_overlay_profile,
    _field_check_company_release_source,
    _field_check_government_contract_profile,
    _field_check_iwm_peer_leader_trend,
    _field_check_multi_event_depth,
    _field_check_peer_leader_state,
    _field_check_single_event_defense_profile,
    _field_check_watch_liquidity_tier,
    _gate2_open_positions,
    _install_space_policy,
    _is_non_attention_official_event,
    _metrics,
    _restore_policy,
    _run_core_baseline,
    _run_variant as _run_exp032_variant,
    _run_window,
    _safe,
    _scale_sizing,
    _space_trade_attribution,
    _write_json,
)


EXPERIMENT_ID = "exp-20260513-038"
STEM = "space_source_diversity_risk"
ACCEPTED_ATTENTION_OVERLAY_RISK_SCALAR = 1.25
SOURCE_DIVERSITY_RISK_SCALARS = (0.75, 0.90, 1.00, 1.025, 1.05, 1.075, 1.10, 1.15)
MIN_DISTINCT_SOURCE_TYPES = 2
MIN_DISTINCT_SEMANTIC_BUCKETS = 2
MAX_DRAWDOWN_DAMAGE_VS_BEFORE = 0.005
MIN_SURVIVAL_RATE = 0.05
MIN_TRADE_COUNT = 50


def _append_jsonl_for_this_experiment(path: Path, entry: dict[str, Any]) -> None:
    lines: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                if json.loads(line).get("experiment_id") == EXPERIMENT_ID:
                    continue
            except json.JSONDecodeError:
                pass
            lines.append(line)
    lines.append(json.dumps(_safe(entry), separators=(",", ":"), sort_keys=True))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _field_check_source_diversity_profile() -> dict[str, Any]:
    path = PROJECT_ROOT / "data" / "space_catalyst_event_seeds.jsonl"
    if not path.exists():
        return {
            "passed": False,
            "path": "data/space_catalyst_event_seeds.jsonl",
            "reason": "missing_event_seed_file",
        }

    required_fields = ("event_id", "event_fields", "semantic_bucket", "source_type", "tickers")
    missing_rows: list[dict[str, Any]] = []
    profiles: dict[str, dict[str, set[str]]] = {
        ticker: {
            "event_ids": set(),
            "event_fields": set(),
            "semantic_buckets": set(),
            "source_types": set(),
        }
        for ticker in OFFICIAL_SPACE_TICKERS
    }

    for row_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        missing = [field for field in required_fields if row.get(field) in (None, "", [])]
        if missing:
            missing_rows.append(
                {
                    "row": row_number,
                    "event_id": row.get("event_id"),
                    "missing_fields": missing,
                }
            )
            continue
        if not _is_non_attention_official_event(row):
            continue

        row_tickers = {str(ticker).upper() for ticker in row.get("tickers") or []}
        for ticker in sorted(row_tickers.intersection(OFFICIAL_SPACE_TICKERS)):
            profile = profiles[ticker]
            profile["event_ids"].add(str(row.get("event_id")))
            profile["semantic_buckets"].add(str(row.get("semantic_bucket")))
            profile["source_types"].add(str(row.get("source_type")))
            for field in row.get("event_fields") or []:
                profile["event_fields"].add(str(field))

    serialized = {
        ticker: {
            key: sorted(values)
            for key, values in profile.items()
        }
        for ticker, profile in profiles.items()
    }
    target_tickers = [
        ticker
        for ticker, profile in profiles.items()
        if len(profile["source_types"]) >= MIN_DISTINCT_SOURCE_TYPES
        and len(profile["semantic_buckets"]) >= MIN_DISTINCT_SEMANTIC_BUCKETS
    ]

    return {
        "passed": not missing_rows and bool(target_tickers),
        "path": "data/space_catalyst_event_seeds.jsonl",
        "required_fields": list(required_fields),
        "official_non_attention_source_types": sorted(OFFICIAL_NON_ATTENTION_SOURCE_TYPES),
        "excluded_semantic_buckets": sorted(EXCLUDED_SEMANTIC_BUCKETS),
        "min_distinct_source_types": MIN_DISTINCT_SOURCE_TYPES,
        "min_distinct_semantic_buckets": MIN_DISTINCT_SEMANTIC_BUCKETS,
        "target_tickers": sorted(target_tickers),
        "profiles": serialized,
        "missing_rows": missing_rows,
    }


def _run_source_diversity_variant(
    label: str,
    source_diversity_scalar: float,
    *,
    source_diversity_gate: dict[str, Any],
    attention_gate: dict[str, Any],
    single_event_gate: dict[str, Any],
    government_contract_gate: dict[str, Any],
    source_gate: dict[str, Any],
    multi_event_gate: dict[str, Any],
    liquidity_gate: dict[str, Any],
    company_release_gate: dict[str, Any],
    financing_gate: dict[str, Any],
) -> dict[str, Any]:
    universe = sorted(set(get_universe()) | set(OFFICIAL_SPACE_TICKERS) | {"IWM", "SPY"})
    installed = _install_space_policy(
        ACCEPTED_ATTENTION_OVERLAY_RISK_SCALAR,
        attention_gate=attention_gate,
        single_event_gate=single_event_gate,
        government_contract_gate=government_contract_gate,
        source_gate=source_gate,
        multi_event_gate=multi_event_gate,
        liquidity_gate=liquidity_gate,
        company_release_gate=company_release_gate,
        financing_gate=financing_gate,
    )
    accepted_size_signals = portfolio_engine.size_signals
    target_tickers = set(source_diversity_gate["target_tickers"])
    profiles = source_diversity_gate["profiles"]
    diversity_adjustments: list[dict[str, Any]] = []
    diversity_counts: Counter[str] = Counter()

    def size_with_source_diversity_scalar(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        risk_pct: float | None = None,
    ) -> list[dict[str, Any]]:
        sized = accepted_size_signals(signals, portfolio_value, risk_pct=risk_pct)
        adjusted: list[dict[str, Any]] = []
        for signal in sized:
            ticker = str(signal.get("ticker") or "").upper()
            sizing = deepcopy(signal.get("sizing") or {})
            if ticker in target_tickers and sizing:
                diversity_counts["eligible_signal"] += 1
                diversity_counts[f"eligible_{ticker}"] += 1
                shares_before = int(sizing.get("shares_to_buy") or 0)
                dollars_before = float(sizing.get("position_size_dollars") or 0.0)
                _scale_sizing(
                    sizing,
                    source_diversity_scalar,
                    portfolio_value,
                    "space_source_diversity_risk",
                )
                shares_after = int(sizing.get("shares_to_buy") or 0)
                dollars_after = float(sizing.get("position_size_dollars") or 0.0)
                if shares_after != shares_before:
                    diversity_counts["changed_signal"] += 1
                    diversity_counts[f"changed_{ticker}"] += 1
                diversity_adjustments.append(
                    {
                        "ticker": ticker,
                        "strategy": signal.get("strategy"),
                        "marker": "space_source_diversity_risk",
                        "source_diversity_profile": profiles.get(ticker),
                        "scalar": source_diversity_scalar,
                        "shares_before_scalar": shares_before,
                        "shares_after_scalar": shares_after,
                        "dollars_before_scalar": dollars_before,
                        "dollars_after_scalar": dollars_after,
                        "trade_quality_score": signal.get("trade_quality_score"),
                        "confidence_score": signal.get("confidence_score"),
                        "space_peer_momentum_state": signal.get("space_peer_momentum_state"),
                        "space_basket_momentum_state": signal.get("space_basket_momentum_state"),
                        "space_iwm_relative_state": signal.get("space_iwm_relative_state"),
                    }
                )
                signal = {
                    **signal,
                    "sizing": sizing,
                    "space_source_diversity_eligible": True,
                    "space_source_diversity_scalar": source_diversity_scalar,
                    "space_source_diversity_profile": profiles.get(ticker),
                }
            adjusted.append(signal)
        return adjusted

    portfolio_engine.size_signals = size_with_source_diversity_scalar
    try:
        by_window: dict[str, Any] = {}
        for name, window in WINDOWS.items():
            before_adjustments = len(diversity_adjustments)
            before_counts = Counter(diversity_counts)
            result = _run_window(window, universe, "space_snapshot")
            window_adjustments = diversity_adjustments[before_adjustments:]
            count_delta = dict(sorted((diversity_counts - before_counts).items()))
            by_window[name] = {
                "metrics": _metrics(result),
                "space_trade_attribution": _space_trade_attribution(result),
                "space_source_diversity_adjustment": _adjustment_summary(
                    window_adjustments
                ),
                "space_source_diversity_counts": count_delta,
            }
        metrics_by_window = {name: row["metrics"] for name, row in by_window.items()}
        return {
            "label": label,
            "parameters": {
                "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
                "accepted_attention_overlay_risk_scalar": ACCEPTED_ATTENTION_OVERLAY_RISK_SCALAR,
                "space_source_diversity_scalar": source_diversity_scalar,
                "min_distinct_source_types": MIN_DISTINCT_SOURCE_TYPES,
                "min_distinct_semantic_buckets": MIN_DISTINCT_SEMANTIC_BUCKETS,
                "target_tickers": source_diversity_gate["target_tickers"],
            },
            "by_window": by_window,
            "aggregate": _aggregate(metrics_by_window),
            "source_diversity_adjustment_summary": _adjustment_summary(
                diversity_adjustments
            ),
            "source_diversity_adjustment_counts": dict(sorted(diversity_counts.items())),
            "source_diversity_adjustment_sample": diversity_adjustments[:25],
        }
    finally:
        _restore_policy(*installed["originals"])


def _gate_variant(variant: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    aggregate_delta = _aggregate_delta(variant["aggregate"], before["aggregate"])
    before_by_window = before["by_window"]
    by_window_delta = {
        name: _delta(payload["metrics"], before_by_window[name]["metrics"])
        for name, payload in variant["by_window"].items()
    }
    ev_regressions = {
        name: delta["expected_value_score"]
        for name, delta in by_window_delta.items()
        if delta["expected_value_score"] < -1e-9
    }
    ev_improvements = {
        name: delta["expected_value_score"]
        for name, delta in by_window_delta.items()
        if delta["expected_value_score"] > 1e-9
    }
    max_drawdown_damage = aggregate_delta["max_drawdown_pct_max"]
    min_survival_rate = variant["aggregate"]["min_survival_rate"]
    trade_count = variant["aggregate"]["trade_count_sum"]
    changed_count = int(
        variant["source_diversity_adjustment_counts"].get("changed_signal", 0)
    )
    eligible_count = int(
        variant["source_diversity_adjustment_counts"].get("eligible_signal", 0)
    )
    scalar = float(variant["parameters"]["space_source_diversity_scalar"])
    return {
        "aggregate_delta_vs_before": aggregate_delta,
        "by_window_delta_vs_before": by_window_delta,
        "ev_improvements": ev_improvements,
        "ev_regressions": ev_regressions,
        "max_drawdown_damage_vs_before": max_drawdown_damage,
        "min_survival_rate": min_survival_rate,
        "trade_count": trade_count,
        "eligible_source_diversity_signal_count": eligible_count,
        "changed_source_diversity_signal_count": changed_count,
        "accepted": bool(
            scalar != 1.0
            and changed_count > 0
            and aggregate_delta["expected_value_score_sum"] > 0
            and aggregate_delta["total_pnl_sum"] > 0
            and len(ev_improvements) >= 2
            and not ev_regressions
            and max_drawdown_damage <= MAX_DRAWDOWN_DAMAGE_VS_BEFORE
            and min_survival_rate >= MIN_SURVIVAL_RATE
            and trade_count >= MIN_TRADE_COUNT
        ),
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    gate = payload["best_variant_gate"]
    lines = [
        f"# {EXPERIMENT_ID} Space source-diversity risk",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Single Changed Variable",
        (
            "`space_source_diversity_scalar` applied after the accepted exp-032 "
            "attention-overlay stack to official Space tickers with at least two "
            "non-attention official source types and at least two semantic buckets."
        ),
        "",
        "## Gate 4 Summary",
        f"- Decision: `{payload['decision']}`",
        (
            "- Best scalar: "
            f"`{best['parameters']['space_source_diversity_scalar']}`"
        ),
        (
            "- Aggregate delta vs exp-032: "
            f"EV `{gate['aggregate_delta_vs_before']['expected_value_score_sum']:.6f}`, "
            f"PnL `{gate['aggregate_delta_vs_before']['total_pnl_sum']:.2f}`"
        ),
        (
            "- Source-diversity signals changed: "
            f"`{gate['changed_source_diversity_signal_count']}` of "
            f"`{gate['eligible_source_diversity_signal_count']}` eligible"
        ),
        "",
        "## Three-Window Deltas vs Exp-032",
        "| window | EV delta | PnL delta | max DD delta | trades | survival | source-diverse signals |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, delta in gate["by_window_delta_vs_before"].items():
        metrics = best["by_window"][name]["metrics"]
        adjusted = best["by_window"][name]["space_source_diversity_adjustment"][
            "adjusted_signal_count"
        ]
        lines.append(
            "| {name} | {ev:.6f} | {pnl:.2f} | {dd:.6f} | {trades} | {survival:.6f} | {adjusted} |".format(
                name=name,
                ev=delta["expected_value_score"],
                pnl=delta["total_pnl"],
                dd=delta["max_drawdown_pct"],
                trades=metrics["trade_count"],
                survival=metrics["survival_rate"],
                adjusted=adjusted,
            )
        )
    lines.extend(
        [
            "",
            "## Target Tickers",
            ", ".join(payload["parameters"]["target_tickers"]),
            "",
            "## Gate Checks",
            f"- Gate 2 passed: `{payload['gate2_field_checks']['passed']}`",
            f"- Gate 3 survival passed: `{payload['gate3']['passed']}`",
            "",
            "## Production Impact",
            "```text",
            "production_impact:",
            f"  shared_policy_changed: {payload['production_impact']['shared_policy_changed']}",
            f"  backtester_adapter_changed: {payload['production_impact']['backtester_adapter_changed']}",
            f"  run_adapter_changed: {payload['production_impact']['run_adapter_changed']}",
            f"  replay_only: {payload['production_impact']['replay_only']}",
            f"  parity_test_added: {payload['production_impact']['parity_test_added']}",
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "lane": payload["lane"],
        "status": payload["status"],
        "hypothesis": payload["hypothesis"],
        "changed_variable": payload["changed_variable"],
        "decision": payload["decision"],
        "best_parameters": payload["best_variant"]["parameters"],
        "aggregate_delta_vs_before": payload["best_variant_gate"][
            "aggregate_delta_vs_before"
        ],
        "next_evidence_needed": payload["next_evidence_needed"],
        "production_impact": payload["production_impact"],
    }


def run() -> dict[str, Any]:
    run_started_at = datetime.now(timezone.utc).isoformat()

    core = _run_core_baseline()
    attention_gate = _field_check_attention_overlay_profile()
    single_event_gate = _field_check_single_event_defense_profile()
    government_contract_gate = _field_check_government_contract_profile()
    source_gate = _event_seed_profiles()
    multi_event_gate = _field_check_multi_event_depth()
    liquidity_gate = _field_check_watch_liquidity_tier()
    company_release_gate = _field_check_company_release_source()
    financing_gate = _accepted_financing_profile_gate()
    source_diversity_gate = _field_check_source_diversity_profile()

    before = _run_exp032_variant(
        "accepted_exp032_attention_overlay_stack",
        ACCEPTED_ATTENTION_OVERLAY_RISK_SCALAR,
        attention_gate=attention_gate,
        single_event_gate=single_event_gate,
        government_contract_gate=government_contract_gate,
        source_gate=source_gate,
        multi_event_gate=multi_event_gate,
        liquidity_gate=liquidity_gate,
        company_release_gate=company_release_gate,
        financing_gate=financing_gate,
    )
    peer_state_gate = _field_check_peer_leader_state(before)
    iwm_peer_leader_gate = _field_check_iwm_peer_leader_trend(before)

    gate2 = {
        "open_positions": _gate2_open_positions(),
        "attention_overlay_profile": attention_gate,
        "single_event_defense_profile": single_event_gate,
        "government_contract_profile": government_contract_gate,
        "official_customer_source_profile": source_gate,
        "peer_momentum_state": peer_state_gate,
        "iwm_peer_leader_trend_state": iwm_peer_leader_gate,
        "multi_event_depth": multi_event_gate,
        "liquidity_tier": liquidity_gate,
        "company_release_source": company_release_gate,
        "financing_dilution_profile": financing_gate,
        "source_diversity_profile": source_diversity_gate,
    }
    gate2["passed"] = all(
        [
            gate2["open_positions"]["passed"],
            attention_gate["passed"],
            single_event_gate["passed"],
            government_contract_gate["passed"],
            source_gate["passed"],
            peer_state_gate["passed"],
            iwm_peer_leader_gate["passed"],
            multi_event_gate["passed"],
            liquidity_gate["passed"],
            company_release_gate["passed"],
            financing_gate["passed"],
            source_diversity_gate["passed"],
        ]
    )

    variants = [
        _run_source_diversity_variant(
            f"{STEM}_{str(scalar).replace('.', '_')}",
            scalar,
            source_diversity_gate=source_diversity_gate,
            attention_gate=attention_gate,
            single_event_gate=single_event_gate,
            government_contract_gate=government_contract_gate,
            source_gate=source_gate,
            multi_event_gate=multi_event_gate,
            liquidity_gate=liquidity_gate,
            company_release_gate=company_release_gate,
            financing_gate=financing_gate,
        )
        for scalar in SOURCE_DIVERSITY_RISK_SCALARS
    ]
    for variant in variants:
        variant["gate"] = _gate_variant(variant, before)

    best_variant = max(
        variants,
        key=lambda item: (
            item["gate"]["accepted"],
            item["gate"]["aggregate_delta_vs_before"]["expected_value_score_sum"],
            item["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
        ),
    )
    decision = "accepted" if best_variant["gate"]["accepted"] else "rejected"
    rejection_reason = ""
    if decision == "rejected":
        rejection_reason = (
            "No tested official source-diversity scalar improved aggregate EV/PnL "
            "across the three standard windows without a window-level EV regression."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "run_started_at": run_started_at,
        "run_finished_at": datetime.now(timezone.utc).isoformat(),
        "lane": "alpha_search",
        "hypothesis": (
            "On top of accepted exp-032 Space attention overlay stack, official Space "
            "signals backed by heterogeneous non-attention official evidence may have "
            "better catalyst durability than single-channel official evidence. A single "
            "risk scalar tests this source/family diversity without changing the Space "
            "pool, rankings, targets, stops, LLM boundary, or live slots."
        ),
        "change_type": "risk_allocation_shadow_sweep",
        "changed_variable": "space_source_diversity_risk_scalar",
        "single_causal_variable": (
            "risk scalar for official Space signals whose non-attention event seeds "
            "span at least two official source types and at least two semantic buckets"
        ),
        "backtest_protocol": {
            "source": "docs/backtesting.md core multi-window protocol",
            "windows": WINDOWS,
            "space_snapshots": {
                label: window["space_snapshot"] for label, window in WINDOWS.items()
            },
        },
        "gate_questions": {
            "q1_alpha_hypothesis": (
                "risk allocation: scale only official Space signals with diversified "
                "non-attention official catalyst source types and semantic families."
            ),
            "q2_prior_experiments": [
                "exp-20260513-012 accepted raw official non-attention event depth; this is not a count retune.",
                "exp-20260513-032 accepted attention overlay only when official non-attention catalysts exist.",
                "exp-20260513-037 rejected non-dilutive contract/revenue registry-profile scalar.",
                "Prior static ticker expansion and LLM soft-ranking remain low-priority or label-thin.",
            ],
            "q3_single_causal_variable": (
                "Only space_source_diversity_risk_scalar changes; candidate pool, event labels, "
                "ranking, targets, stops, LLM/news, accepted exp-032 stack, and live slots stay fixed."
            ),
            "q4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; require positive aggregate EV/PnL, "
                "at least two EV-improved windows, no EV-regressed window, max drawdown damage <= 0.5pp, "
                "survival >= 5%, >=50 aggregate trades, and real adjusted source-diverse signals."
            ),
            "q5_reproducibility": (
                f"Run .\\.venv\\Scripts\\python.exe quant\\experiments\\{Path(__file__).name}"
            ),
        },
        "gate1": {
            "core_baseline": core["aggregate"],
            "accepted_before_metrics": before["aggregate"],
            "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
            "known_bias": (
                "Space candidate snapshots are frozen historical replay copies built from a "
                "2026-05-10 research universe. Event-seed source type and semantic bucket "
                "metadata are production-visible, but the accepted Space helper policy remains "
                "default-off with live Space slots at zero until forward evidence supports promotion."
            ),
        },
        "gate2_field_checks": gate2,
        "gate3": {
            "new_filter_added": False,
            "new_risk_scalar_added": True,
            "min_survival_rate_after": best_variant["aggregate"]["min_survival_rate"],
            "passed": best_variant["aggregate"]["min_survival_rate"] >= MIN_SURVIVAL_RATE,
        },
        "parameters": {
            "official_space_tickers": list(OFFICIAL_SPACE_TICKERS),
            "min_distinct_source_types": MIN_DISTINCT_SOURCE_TYPES,
            "min_distinct_semantic_buckets": MIN_DISTINCT_SEMANTIC_BUCKETS,
            "target_tickers": source_diversity_gate["target_tickers"],
            "source_diversity_profiles": source_diversity_gate["profiles"],
            "tested_source_diversity_scalars": list(SOURCE_DIVERSITY_RISK_SCALARS),
            "accepted_exp032_attention_overlay_risk_scalar": ACCEPTED_ATTENTION_OVERLAY_RISK_SCALAR,
            "accepted_stack_scalars": {
                "multi_event_depth": ACCEPTED_MULTI_EVENT_DEPTH_RISK_SCALAR,
                "customer_source_peer_leader": ACCEPTED_CUSTOMER_SOURCE_PEER_LEADER_RISK_SCALAR,
                "government_contract_peer_leader": ACCEPTED_GOVERNMENT_CONTRACT_PEER_LEADER_RISK_SCALAR,
                "iwm_peer_leader_trend": ACCEPTED_IWM_PEER_LEADER_TREND_RISK_SCALAR,
                "single_event_defense": ACCEPTED_SINGLE_EVENT_DEFENSE_RISK_SCALAR,
                "watch_liquidity": WATCH_LIQUIDITY_RISK_SCALAR,
                "company_release_source": ACCEPTED_COMPANY_RELEASE_SOURCE_RISK_SCALAR,
                "financing_dilution_profile": ACCEPTED_FINANCING_DILUTION_PROFILE_RISK_SCALAR,
            },
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
                "accepted liquidity_tier=ok/watch scalars",
                "accepted official source scalars",
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
        "core_baseline": core,
        "before": before,
        "variants": variants,
        "best_variant": best_variant,
        "best_variant_gate": best_variant["gate"],
        "decision": decision,
        "status": (
            "accepted_default_off_space_source_diversity_risk"
            if decision == "accepted"
            else "rejected_space_source_diversity_risk"
        ),
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "Collect forward replacement-value evidence before enabling live Space slots."
            if decision == "accepted"
            else (
                "Do not keep tuning Space source-diversity scalars on these frozen snapshots. "
                "Prefer forward replacement-value evidence or a different production-visible "
                "official-catalyst coverage improvement."
            )
        ),
        "production_impact": {
            "alters_candidate_ranking": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_sizing": True,
            "shared_policy_changed": decision == "accepted",
            "backtester_adapter_changed": False,
            "daily_report_metadata_changed": decision == "accepted",
            "run_adapter_changed": decision == "accepted",
            "replay_only": True,
            "parity_test_added": decision == "accepted",
            "live_slots": 0,
            "live_slots_changed": False,
            "promotion_required_if_accepted": False,
        },
        "why_not_other_changes": (
            "LLM soft-ranking remains label-thin, naive ticker expansion recently failed, "
            "and broad breakout/profile retunes were rejected. This run isolates one "
            "production-visible source/family diversity axis inside the official Space pool."
        ),
        "known_risks": [
            "The Space sleeve remains default-off and based on frozen historical replay snapshots.",
            "Source-diverse samples are small; accepted evidence would still need shared-policy promotion and forward validation before live slots.",
        ],
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    exp_dir = PROJECT_ROOT / "data" / "experiments" / EXPERIMENT_ID
    exp_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = PROJECT_ROOT / "docs" / "experiments" / "logs"
    tickets_dir = PROJECT_ROOT / "docs" / "experiments" / "tickets"
    artifacts_dir = PROJECT_ROOT / "docs" / "experiments" / "artifacts"
    for directory in (logs_dir, tickets_dir, artifacts_dir):
        directory.mkdir(parents=True, exist_ok=True)

    _write_json(exp_dir / f"{STEM}.json", payload)
    _write_json(logs_dir / f"{EXPERIMENT_ID}.json", payload)
    _write_json(tickets_dir / f"{EXPERIMENT_ID}.json", _ticket(payload))
    (artifacts_dir / f"{EXPERIMENT_ID}_{STEM}.md").write_text(
        _artifact_markdown(payload),
        encoding="utf-8",
    )
    _append_jsonl_for_this_experiment(
        PROJECT_ROOT / "docs" / "experiment_log.jsonl",
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "changed_variable": payload["changed_variable"],
            "single_causal_variable": payload["single_causal_variable"],
            "parameters": payload["best_variant"]["parameters"],
            "date_range": [
                f"{label}:{window['start']}..{window['end']}"
                for label, window in WINDOWS.items()
            ],
            "backtest_protocol": payload["backtest_protocol"],
            "before_metrics": payload["before"]["aggregate"],
            "after_metrics": payload["best_variant"]["aggregate"],
            "expected_value_score_delta": payload["best_variant_gate"][
                "aggregate_delta_vs_before"
            ]["expected_value_score_sum"],
            "decision": payload["status"],
            "rejection_reason": payload["rejection_reason"],
            "next_evidence_needed": payload["next_evidence_needed"],
            "production_impact": payload["production_impact"],
        },
    )


if __name__ == "__main__":
    result = run()
    persist(result)
    summary = {
        "experiment_id": result["experiment_id"],
        "decision": result["status"],
        "best_scalar": result["best_variant"]["parameters"][
            "space_source_diversity_scalar"
        ],
        "target_tickers": result["parameters"]["target_tickers"],
        "aggregate_before": result["before"]["aggregate"],
        "aggregate_after": result["best_variant"]["aggregate"],
        "aggregate_delta_vs_before": result["best_variant_gate"][
            "aggregate_delta_vs_before"
        ],
        "by_window_delta_vs_before": result["best_variant_gate"][
            "by_window_delta_vs_before"
        ],
        "changed_source_diversity_signal_count": result["best_variant_gate"][
            "changed_source_diversity_signal_count"
        ],
        "production_impact": result["production_impact"],
    }
    print(json.dumps(_safe(summary), indent=2, sort_keys=True))
