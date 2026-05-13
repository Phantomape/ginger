"""exp-20260513-106: Space regulatory customer-source risk.

Tests one causal variable on top of the accepted exp-20260513-039 default-off
Space stack: an additional risk scalar for official Space tickers whose
customer-win catalyst comes from an official regulatory source. This avoids LLM
soft-ranking and ticker-pool expansion, and asks whether regulatory
authorization events deserve distinct risk allocation from broader customer
source events.
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
import exp_20260513_038_space_source_diversity_risk as source_diversity_exp


EXPERIMENT_ID = "exp-20260513-106"
STEM = "space_regulatory_customer_source_risk"
BEFORE_EXPERIMENT_ID = "exp-20260513-039"
ACCEPTED_SOURCE_DIVERSITY_RISK_SCALAR = 1.075
ACCEPTED_SOURCE_DIVERSITY_PEER_LEADER_RISK_SCALAR = 1.15
REGULATORY_CUSTOMER_SOURCE_RISK_SCALARS = (
    0.75,
    0.90,
    1.00,
    1.025,
    1.05,
    1.075,
    1.10,
    1.15,
    1.25,
)
REGULATORY_SOURCE_TYPE = "official_regulatory_release"
CUSTOMER_SOURCE_EVENT_FIELD = "customer_win"
EXCLUDED_SEMANTIC_BUCKETS = ("attention_only",)
MAX_DRAWDOWN_DAMAGE_VS_BEFORE = 0.005
MIN_SURVIVAL_RATE = 0.05
MIN_TRADE_COUNT = 50


def _safe(payload: Any) -> Any:
    return source_diversity_exp._safe(payload)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    source_diversity_exp._write_json(path, payload)


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


def _field_check_regulatory_customer_source_profile() -> dict[str, Any]:
    path = PROJECT_ROOT / "data" / "space_catalyst_event_seeds.jsonl"
    if not path.exists():
        return {
            "passed": False,
            "path": "data/space_catalyst_event_seeds.jsonl",
            "reason": "missing_event_seed_file",
        }

    required_fields = (
        "event_id",
        "event_fields",
        "semantic_bucket",
        "source_type",
        "tickers",
    )
    missing_rows: list[dict[str, Any]] = []
    profiles: dict[str, dict[str, set[str]]] = {
        ticker: {
            "event_ids": set(),
            "event_fields": set(),
            "semantic_buckets": set(),
            "source_types": set(),
        }
        for ticker in source_diversity_exp.OFFICIAL_SPACE_TICKERS
    }
    source_type_counts = Counter()
    semantic_bucket_counts = Counter()
    event_field_counts = Counter()

    for row_number, line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        if not line.strip():
            continue
        row = json.loads(line)
        missing = [
            field for field in required_fields if row.get(field) in (None, "", [])
        ]
        if missing:
            missing_rows.append(
                {
                    "row": row_number,
                    "event_id": row.get("event_id"),
                    "missing_fields": missing,
                }
            )
            continue

        source_type = str(row.get("source_type") or "")
        semantic_bucket = str(row.get("semantic_bucket") or "")
        fields = [str(item) for item in row.get("event_fields") or []]
        source_type_counts[source_type] += 1
        semantic_bucket_counts[semantic_bucket] += 1
        for field in fields:
            event_field_counts[field] += 1

        if source_type != REGULATORY_SOURCE_TYPE:
            continue
        if semantic_bucket in EXCLUDED_SEMANTIC_BUCKETS:
            continue
        if CUSTOMER_SOURCE_EVENT_FIELD not in fields:
            continue

        row_tickers = {str(ticker).upper() for ticker in row.get("tickers") or []}
        for ticker in sorted(
            row_tickers.intersection(source_diversity_exp.OFFICIAL_SPACE_TICKERS)
        ):
            profile = profiles[ticker]
            profile["event_ids"].add(str(row.get("event_id")))
            profile["event_fields"].update(fields)
            profile["semantic_buckets"].add(semantic_bucket)
            profile["source_types"].add(source_type)

    serialized = {
        ticker: {
            "event_count": len(profile["event_ids"]),
            "event_ids": sorted(profile["event_ids"]),
            "event_fields": sorted(profile["event_fields"]),
            "semantic_buckets": sorted(profile["semantic_buckets"]),
            "source_types": sorted(profile["source_types"]),
        }
        for ticker, profile in profiles.items()
    }
    target_tickers = sorted(
        ticker for ticker, profile in serialized.items() if profile["event_count"] > 0
    )
    return {
        "passed": not missing_rows and bool(target_tickers),
        "path": "data/space_catalyst_event_seeds.jsonl",
        "required_fields": list(required_fields),
        "target_definition": (
            "official Space ticker with customer_win event seed from "
            "official_regulatory_release and non-attention semantic bucket"
        ),
        "regulatory_source_type": REGULATORY_SOURCE_TYPE,
        "customer_source_event_field": CUSTOMER_SOURCE_EVENT_FIELD,
        "excluded_semantic_buckets": list(EXCLUDED_SEMANTIC_BUCKETS),
        "target_tickers": target_tickers,
        "profiles": serialized,
        "missing_rows": missing_rows,
        "source_type_counts": dict(sorted(source_type_counts.items())),
        "semantic_bucket_counts": dict(sorted(semantic_bucket_counts.items())),
        "event_field_counts": dict(sorted(event_field_counts.items())),
    }


def _run_regulatory_variant(
    label: str,
    regulatory_scalar: float,
    *,
    regulatory_gate: dict[str, Any],
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
    universe = sorted(
        set(get_universe())
        | set(source_diversity_exp.OFFICIAL_SPACE_TICKERS)
        | {"IWM", "SPY"}
    )
    installed = source_diversity_exp._install_space_policy(
        source_diversity_exp.ACCEPTED_ATTENTION_OVERLAY_RISK_SCALAR,
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
    source_diversity_tickers = set(source_diversity_gate["target_tickers"])
    source_diversity_profiles = source_diversity_gate["profiles"]
    regulatory_tickers = set(regulatory_gate["target_tickers"])
    regulatory_profiles = regulatory_gate["profiles"]
    diversity_adjustments: list[dict[str, Any]] = []
    peer_adjustments: list[dict[str, Any]] = []
    regulatory_adjustments: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()

    def size_with_regulatory_customer_source(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        risk_pct: float | None = None,
    ) -> list[dict[str, Any]]:
        sized = accepted_size_signals(signals, portfolio_value, risk_pct=risk_pct)
        adjusted: list[dict[str, Any]] = []
        for signal in sized:
            ticker = str(signal.get("ticker") or "").upper()
            sizing = deepcopy(signal.get("sizing") or {})
            if ticker in source_diversity_tickers and sizing:
                counts["source_diverse_eligible_signal"] += 1
                counts[f"source_diverse_eligible_{ticker}"] += 1
                source_profile = source_diversity_profiles.get(ticker)
                shares_before_source = int(sizing.get("shares_to_buy") or 0)
                source_diversity_exp._scale_sizing(
                    sizing,
                    ACCEPTED_SOURCE_DIVERSITY_RISK_SCALAR,
                    portfolio_value,
                    "space_source_diversity_risk",
                )
                diversity_adjustments.append(
                    {
                        "ticker": ticker,
                        "strategy": signal.get("strategy"),
                        "marker": "space_source_diversity_risk",
                        "scalar": ACCEPTED_SOURCE_DIVERSITY_RISK_SCALAR,
                        "shares_before_scalar": shares_before_source,
                        "shares_after_scalar": int(
                            sizing.get("shares_to_buy") or 0
                        ),
                        "source_diversity_profile": source_profile,
                        "space_peer_momentum_state": signal.get(
                            "space_peer_momentum_state"
                        ),
                        "space_iwm_relative_state": signal.get(
                            "space_iwm_relative_state"
                        ),
                        "trade_quality_score": signal.get("trade_quality_score"),
                        "confidence_score": signal.get("confidence_score"),
                    }
                )
                signal = {
                    **signal,
                    "sizing": sizing,
                    "space_source_diversity_eligible": True,
                    "space_source_diversity_scalar": (
                        ACCEPTED_SOURCE_DIVERSITY_RISK_SCALAR
                    ),
                    "space_source_diversity_profile": source_profile,
                }

                if signal.get("space_peer_momentum_state") == "leader":
                    counts["source_diverse_peer_leader_eligible_signal"] += 1
                    counts[f"source_diverse_peer_leader_eligible_{ticker}"] += 1
                    shares_before_peer = int(sizing.get("shares_to_buy") or 0)
                    source_diversity_exp._scale_sizing(
                        sizing,
                        ACCEPTED_SOURCE_DIVERSITY_PEER_LEADER_RISK_SCALAR,
                        portfolio_value,
                        "space_source_diversity_peer_leader_risk",
                    )
                    peer_adjustments.append(
                        {
                            "ticker": ticker,
                            "strategy": signal.get("strategy"),
                            "marker": "space_source_diversity_peer_leader_risk",
                            "scalar": (
                                ACCEPTED_SOURCE_DIVERSITY_PEER_LEADER_RISK_SCALAR
                            ),
                            "shares_before_scalar": shares_before_peer,
                            "shares_after_scalar": int(
                                sizing.get("shares_to_buy") or 0
                            ),
                            "source_diversity_profile": source_profile,
                            "space_peer_momentum_state": signal.get(
                                "space_peer_momentum_state"
                            ),
                            "space_peer_excess_momentum_20d_pct": signal.get(
                                "space_peer_excess_momentum_20d_pct"
                            ),
                            "space_iwm_relative_state": signal.get(
                                "space_iwm_relative_state"
                            ),
                            "trade_quality_score": signal.get(
                                "trade_quality_score"
                            ),
                            "confidence_score": signal.get("confidence_score"),
                        }
                    )
                    signal = {
                        **signal,
                        "sizing": sizing,
                        "space_source_diversity_peer_leader_scalar": (
                            ACCEPTED_SOURCE_DIVERSITY_PEER_LEADER_RISK_SCALAR
                        ),
                    }

            if ticker in regulatory_tickers and sizing:
                counts["regulatory_customer_source_eligible_signal"] += 1
                counts[f"regulatory_customer_source_eligible_{ticker}"] += 1
                shares_before = int(sizing.get("shares_to_buy") or 0)
                dollars_before = float(sizing.get("position_size_dollars") or 0.0)
                source_diversity_exp._scale_sizing(
                    sizing,
                    regulatory_scalar,
                    portfolio_value,
                    "space_regulatory_customer_source_risk",
                )
                shares_after = int(sizing.get("shares_to_buy") or 0)
                dollars_after = float(sizing.get("position_size_dollars") or 0.0)
                if shares_after != shares_before:
                    counts["regulatory_customer_source_changed_signal"] += 1
                    counts[f"regulatory_customer_source_changed_{ticker}"] += 1
                regulatory_adjustments.append(
                    {
                        "ticker": ticker,
                        "strategy": signal.get("strategy"),
                        "marker": "space_regulatory_customer_source_risk",
                        "scalar": regulatory_scalar,
                        "shares_before_scalar": shares_before,
                        "shares_after_scalar": shares_after,
                        "dollars_before_scalar": dollars_before,
                        "dollars_after_scalar": dollars_after,
                        "regulatory_customer_source_profile": (
                            regulatory_profiles.get(ticker)
                        ),
                        "space_peer_momentum_state": signal.get(
                            "space_peer_momentum_state"
                        ),
                        "space_iwm_relative_state": signal.get(
                            "space_iwm_relative_state"
                        ),
                        "trade_quality_score": signal.get("trade_quality_score"),
                        "confidence_score": signal.get("confidence_score"),
                    }
                )
                signal = {
                    **signal,
                    "sizing": sizing,
                    "space_regulatory_customer_source_eligible": True,
                    "space_regulatory_customer_source_scalar": regulatory_scalar,
                    "space_regulatory_customer_source_profile": (
                        regulatory_profiles.get(ticker)
                    ),
                }
            adjusted.append(signal)
        return adjusted

    portfolio_engine.size_signals = size_with_regulatory_customer_source
    try:
        by_window: dict[str, Any] = {}
        for name, window in source_diversity_exp.WINDOWS.items():
            before_diversity_count = len(diversity_adjustments)
            before_peer_count = len(peer_adjustments)
            before_regulatory_count = len(regulatory_adjustments)
            before_counts = Counter(counts)
            result = source_diversity_exp._run_window(window, universe, "space_snapshot")
            window_diversity = diversity_adjustments[before_diversity_count:]
            window_peer = peer_adjustments[before_peer_count:]
            window_regulatory = regulatory_adjustments[before_regulatory_count:]
            count_delta = dict(sorted((counts - before_counts).items()))
            by_window[name] = {
                "metrics": source_diversity_exp._metrics(result),
                "space_trade_attribution": (
                    source_diversity_exp._space_trade_attribution(result)
                ),
                "source_diversity_adjustment": (
                    source_diversity_exp._adjustment_summary(window_diversity)
                ),
                "source_diversity_peer_leader_adjustment": (
                    source_diversity_exp._adjustment_summary(window_peer)
                ),
                "regulatory_customer_source_adjustment": (
                    source_diversity_exp._adjustment_summary(window_regulatory)
                ),
                "regulatory_customer_source_counts": count_delta,
            }
        metrics_by_window = {name: row["metrics"] for name, row in by_window.items()}
        return {
            "label": label,
            "parameters": {
                "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
                "accepted_source_diversity_risk_scalar": (
                    ACCEPTED_SOURCE_DIVERSITY_RISK_SCALAR
                ),
                "accepted_source_diversity_peer_leader_risk_scalar": (
                    ACCEPTED_SOURCE_DIVERSITY_PEER_LEADER_RISK_SCALAR
                ),
                "space_regulatory_customer_source_scalar": regulatory_scalar,
                "regulatory_source_type": REGULATORY_SOURCE_TYPE,
                "customer_source_event_field": CUSTOMER_SOURCE_EVENT_FIELD,
                "target_tickers": regulatory_gate["target_tickers"],
            },
            "by_window": by_window,
            "aggregate": source_diversity_exp._aggregate(metrics_by_window),
            "source_diversity_adjustment_summary": (
                source_diversity_exp._adjustment_summary(diversity_adjustments)
            ),
            "source_diversity_peer_leader_adjustment_summary": (
                source_diversity_exp._adjustment_summary(peer_adjustments)
            ),
            "regulatory_customer_source_adjustment_summary": (
                source_diversity_exp._adjustment_summary(regulatory_adjustments)
            ),
            "regulatory_customer_source_adjustment_counts": dict(
                sorted(counts.items())
            ),
            "regulatory_customer_source_adjustment_sample": (
                regulatory_adjustments[:25]
            ),
        }
    finally:
        source_diversity_exp._restore_policy(*installed["originals"])


def _gate_variant(variant: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    aggregate_delta = source_diversity_exp._aggregate_delta(
        variant["aggregate"], before["aggregate"]
    )
    by_window_delta = {
        name: source_diversity_exp._delta(
            payload["metrics"], before["by_window"][name]["metrics"]
        )
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
    changed_count = int(
        variant["regulatory_customer_source_adjustment_counts"].get(
            "regulatory_customer_source_changed_signal", 0
        )
    )
    eligible_count = int(
        variant["regulatory_customer_source_adjustment_counts"].get(
            "regulatory_customer_source_eligible_signal", 0
        )
    )
    scalar = float(
        variant["parameters"]["space_regulatory_customer_source_scalar"]
    )
    max_drawdown_damage = aggregate_delta["max_drawdown_pct_max"]
    min_survival_rate = variant["aggregate"]["min_survival_rate"]
    trade_count = variant["aggregate"]["trade_count_sum"]
    return {
        "aggregate_delta_vs_before": aggregate_delta,
        "by_window_delta_vs_before": by_window_delta,
        "ev_improvements": ev_improvements,
        "ev_regressions": ev_regressions,
        "max_drawdown_damage_vs_before": max_drawdown_damage,
        "min_survival_rate": min_survival_rate,
        "trade_count": trade_count,
        "eligible_regulatory_customer_source_signal_count": eligible_count,
        "changed_regulatory_customer_source_signal_count": changed_count,
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
        f"# {EXPERIMENT_ID} Space regulatory customer-source risk",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Single Changed Variable",
        (
            "`space_regulatory_customer_source_scalar` after the accepted "
            "exp-039 Space source-diversity peer-leader stack. Candidate pool, "
            "event labels, ranking, targets, stops, LLM/news, and live Space "
            "slots stay fixed."
        ),
        "",
        "## Gate 4 Summary",
        f"- Decision: `{payload['decision']}`",
        (
            "- Best scalar: "
            f"`{best['parameters']['space_regulatory_customer_source_scalar']}`"
        ),
        (
            "- Aggregate delta vs exp-039: "
            f"EV `{gate['aggregate_delta_vs_before']['expected_value_score_sum']:.6f}`, "
            f"PnL `{gate['aggregate_delta_vs_before']['total_pnl_sum']:.2f}`"
        ),
        (
            "- Regulatory customer-source signals changed: "
            f"`{gate['changed_regulatory_customer_source_signal_count']}` of "
            f"`{gate['eligible_regulatory_customer_source_signal_count']}` eligible"
        ),
        "",
        "## Three-Window Deltas vs Exp-039",
        "| window | EV delta | PnL delta | max DD delta | trades | survival | regulatory adjusted |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, delta in gate["by_window_delta_vs_before"].items():
        metrics = best["by_window"][name]["metrics"]
        adjusted = best["by_window"][name][
            "regulatory_customer_source_adjustment"
        ]["adjusted_signal_count"]
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

    core = source_diversity_exp._run_core_baseline()
    attention_gate = source_diversity_exp._field_check_attention_overlay_profile()
    single_event_gate = source_diversity_exp._field_check_single_event_defense_profile()
    government_contract_gate = (
        source_diversity_exp._field_check_government_contract_profile()
    )
    source_gate = source_diversity_exp._event_seed_profiles()
    multi_event_gate = source_diversity_exp._field_check_multi_event_depth()
    liquidity_gate = source_diversity_exp._field_check_watch_liquidity_tier()
    company_release_gate = source_diversity_exp._field_check_company_release_source()
    financing_gate = source_diversity_exp._accepted_financing_profile_gate()
    source_diversity_gate = (
        source_diversity_exp._field_check_source_diversity_profile()
    )
    regulatory_gate = _field_check_regulatory_customer_source_profile()

    before = _run_regulatory_variant(
        "accepted_exp039_source_diversity_peer_leader_stack",
        1.0,
        regulatory_gate=regulatory_gate,
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
    peer_state_gate = source_diversity_exp._field_check_peer_leader_state(before)
    iwm_peer_leader_gate = (
        source_diversity_exp._field_check_iwm_peer_leader_trend(before)
    )

    gate2 = {
        "open_positions": source_diversity_exp._gate2_open_positions(),
        "attention_overlay_profile": attention_gate,
        "single_event_defense_profile": single_event_gate,
        "government_contract_profile": government_contract_gate,
        "official_customer_source_profile": source_gate,
        "multi_event_depth": multi_event_gate,
        "liquidity_tier": liquidity_gate,
        "company_release_source": company_release_gate,
        "financing_dilution_profile": financing_gate,
        "source_diversity_profile": source_diversity_gate,
        "regulatory_customer_source_profile": regulatory_gate,
        "inherited_exp039_diagnostics": {
            "peer_momentum_state": peer_state_gate,
            "iwm_peer_leader_trend_state": iwm_peer_leader_gate,
            "note": (
                "These diagnostics describe the already accepted exp-039 stack. "
                "The new causal variable in this experiment only depends on the "
                "regulatory customer-source event-seed profile."
            ),
        },
    }
    gate2["passed"] = all(
        [
            gate2["open_positions"]["passed"],
            attention_gate["passed"],
            single_event_gate["passed"],
            government_contract_gate["passed"],
            source_gate["passed"],
            multi_event_gate["passed"],
            liquidity_gate["passed"],
            company_release_gate["passed"],
            financing_gate["passed"],
            source_diversity_gate["passed"],
            regulatory_gate["passed"],
        ]
    )

    variants = [
        _run_regulatory_variant(
            f"{STEM}_{str(scalar).replace('.', '_')}",
            scalar,
            regulatory_gate=regulatory_gate,
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
        for scalar in REGULATORY_CUSTOMER_SOURCE_RISK_SCALARS
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
            "No tested regulatory customer-source scalar improved aggregate EV/PnL "
            "across the three standard windows without a window-level EV regression "
            "and risk/survival violation."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "run_started_at": run_started_at,
        "run_finished_at": datetime.now(timezone.utc).isoformat(),
        "lane": "alpha_search",
        "hypothesis": (
            "On top of accepted exp-039 Space source-diversity peer-leader stack, "
            "official Space signals backed by customer_win regulatory authorization "
            "may have more durable catalyst quality than generic customer-source "
            "events. A single risk scalar tests this without changing the Space "
            "pool, event metadata, ranking, targets, stops, LLM boundary, or live "
            "slots."
        ),
        "change_type": "risk_allocation_shadow_sweep",
        "changed_variable": "space_regulatory_customer_source_risk_scalar",
        "single_causal_variable": (
            "extra risk scalar for official Space signals whose customer_win event "
            "seed source_type is official_regulatory_release"
        ),
        "backtest_protocol": {
            "source": "docs/backtesting.md core multi-window protocol",
            "windows": source_diversity_exp.WINDOWS,
            "space_snapshots": {
                label: window["space_snapshot"]
                for label, window in source_diversity_exp.WINDOWS.items()
            },
        },
        "gate_questions": {
            "q1_alpha_hypothesis": (
                "risk allocation: distinguish official regulatory authorization "
                "customer_win events from the broader official customer-source bucket."
            ),
            "q2_prior_experiments": [
                "exp-20260512-038 accepted broad official customer-source risk.",
                "exp-20260513-014 accepted customer-source peer-leader risk.",
                "exp-20260513-038 accepted source-diversity risk.",
                "exp-20260513-039 accepted source-diversity peer-leader risk.",
                "LLM soft-ranking is label-thin, and noisy ticker expansion has failed.",
            ],
            "q3_single_causal_variable": (
                "Only the regulatory customer-source scalar changes; accepted "
                "exp-039 stack and all entry/exit/ranking/candidate variables stay fixed."
            ),
            "q4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; require positive aggregate "
                "EV/PnL, at least two EV-improved windows, no EV-regressed window, "
                "max drawdown damage <= 0.5pp, survival >= 5%, >=50 aggregate trades, "
                "and real adjusted regulatory-customer-source signals."
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
                "Space candidate snapshots are frozen historical replay copies built "
                "from a 2026-05-10 research universe. The policy remains default-off "
                "with live Space slots at zero pending forward replacement value."
            ),
        },
        "gate2_field_checks": gate2,
        "gate3": {
            "new_filter_added": False,
            "new_risk_scalar_added": True,
            "min_survival_rate_after": best_variant["aggregate"]["min_survival_rate"],
            "passed": best_variant["aggregate"]["min_survival_rate"]
            >= MIN_SURVIVAL_RATE,
        },
        "parameters": {
            "official_space_tickers": list(
                source_diversity_exp.OFFICIAL_SPACE_TICKERS
            ),
            "target_tickers": regulatory_gate["target_tickers"],
            "regulatory_customer_source_profiles": regulatory_gate["profiles"],
            "regulatory_source_type": REGULATORY_SOURCE_TYPE,
            "customer_source_event_field": CUSTOMER_SOURCE_EVENT_FIELD,
            "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
            "accepted_source_diversity_risk_scalar": (
                ACCEPTED_SOURCE_DIVERSITY_RISK_SCALAR
            ),
            "accepted_source_diversity_peer_leader_risk_scalar": (
                ACCEPTED_SOURCE_DIVERSITY_PEER_LEADER_RISK_SCALAR
            ),
            "tested_regulatory_customer_source_scalars": list(
                REGULATORY_CUSTOMER_SOURCE_RISK_SCALARS
            ),
            "locked_variables": [
                "official Space candidate pool",
                "accepted exp-039 source-diversity peer-leader stack",
                "all prior accepted Space risk helpers",
                "Space trend targets",
                "entry filters",
                "candidate ranking",
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
            "accepted_default_off_space_regulatory_customer_source_risk"
            if decision == "accepted"
            else "rejected_space_regulatory_customer_source_risk"
        ),
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "Promote only as shared default-off Space metadata/helper, then collect "
            "forward replacement value before any live Space slots."
            if decision == "accepted"
            else (
                "Do not keep tuning regulatory customer-source scalars on this "
                "single ASTS-heavy frozen sample. Prefer forward bucket evidence "
                "or another production-visible catalyst discriminator."
            )
        ),
        "production_impact": {
            "alters_candidate_ranking": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_sizing": True,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "daily_report_metadata_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_required_if_accepted": decision == "accepted",
            "live_slots": 0,
            "live_slots_changed": False,
        },
        "why_not_other_changes": (
            "LLM soft-ranking remains label-thin, noisy ticker expansion and mature "
            "satcom breadth have failed, and recent broad Space breakout/profile "
            "retunes are exhausted. This isolates a production-visible catalyst "
            "quality subtype already present in event seeds."
        ),
        "known_risks": [
            "The Space sleeve remains default-off and historical Space snapshots are frozen research copies.",
            "The regulatory customer-source bucket currently targets ASTS only, so any accepted result requires shared-policy promotion plus forward replacement-value validation before live routing.",
        ],
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    exp_dir = PROJECT_ROOT / "data" / "experiments" / EXPERIMENT_ID
    logs_dir = PROJECT_ROOT / "docs" / "experiments" / "logs"
    tickets_dir = PROJECT_ROOT / "docs" / "experiments" / "tickets"
    artifacts_dir = PROJECT_ROOT / "docs" / "experiments" / "artifacts"
    for directory in (exp_dir, logs_dir, tickets_dir, artifacts_dir):
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
                for label, window in source_diversity_exp.WINDOWS.items()
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
            "space_regulatory_customer_source_scalar"
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
        "changed_regulatory_customer_source_signal_count": result[
            "best_variant_gate"
        ]["changed_regulatory_customer_source_signal_count"],
        "production_impact": result["production_impact"],
    }
    print(json.dumps(_safe(summary), indent=2, sort_keys=True))
