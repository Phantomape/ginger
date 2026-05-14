"""exp-20260513-110: Space source-diversity peer+IWM leader risk.

Tests one causal variable on top of the accepted exp-20260513-108 default-off
Space stack: an additional risk scalar for source-diverse official Space
signals only when the ticker is also a Space peer leader and IWM 20-day
momentum is above SPY 20-day momentum.

This avoids LLM soft-ranking, ticker-pool expansion, target/stop changes, and
nearby single-axis source-diversity scalar retunes. The alpha question is
whether triple-confirmed official catalyst quality plus relative-strength plus
small-cap risk appetite deserves extra risk.
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


EXPERIMENT_ID = "exp-20260513-110"
STEM = "space_source_diversity_peer_iwm_leader_risk"
BEFORE_EXPERIMENT_ID = "exp-20260513-108"
ACCEPTED_SOURCE_DIVERSITY_RISK_SCALAR = 1.075
ACCEPTED_SOURCE_DIVERSITY_PEER_LEADER_RISK_SCALAR = 1.15
ACCEPTED_SOURCE_DIVERSITY_IWM_LEADER_RISK_SCALAR = 1.05
SOURCE_DIVERSITY_PEER_IWM_LEADER_RISK_SCALARS = (
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
IWM_LEADER_STATE = "smallcap_leader"
PEER_LEADER_STATE = "leader"
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


def _runtime_state_gate(before: dict[str, Any]) -> dict[str, Any]:
    source_diverse = 0
    peer_leader = 0
    iwm_leader = 0
    peer_iwm_leader = 0
    samples: list[dict[str, Any]] = []
    for payload in before.get("by_window", {}).values():
        counts = payload.get("source_diversity_peer_iwm_leader_counts") or {}
        source_diverse += int(counts.get("source_diverse_eligible_signal", 0) or 0)
        peer_leader += int(
            counts.get("source_diverse_peer_leader_eligible_signal", 0) or 0
        )
        iwm_leader += int(
            counts.get("source_diverse_iwm_leader_eligible_signal", 0) or 0
        )
        peer_iwm_leader += int(
            counts.get("source_diverse_peer_iwm_leader_eligible_signal", 0) or 0
        )
        summary = payload.get("source_diversity_peer_iwm_leader_adjustment") or {}
        for row in summary.get("sample_adjusted") or []:
            samples.append(
                {
                    "ticker": row.get("ticker"),
                    "strategy": row.get("strategy"),
                    "space_iwm_relative_state": row.get("space_iwm_relative_state"),
                    "space_peer_momentum_state": row.get("space_peer_momentum_state"),
                    "source_types": (row.get("source_diversity_profile") or {}).get(
                        "source_types"
                    ),
                    "semantic_buckets": (
                        row.get("source_diversity_profile") or {}
                    ).get("semantic_buckets"),
                }
            )
            if len(samples) >= 12:
                break
    return {
        "passed": source_diverse > 0 and peer_iwm_leader > 0,
        "required_runtime_fields": [
            "signal.space_iwm_relative_state",
            "signal.space_peer_momentum_state",
            "source_diversity_profile.source_types",
            "source_diversity_profile.semantic_buckets",
            "sizing.shares_to_buy",
        ],
        "source_diverse_signal_count": source_diverse,
        "source_diverse_peer_leader_signal_count": peer_leader,
        "source_diverse_iwm_leader_signal_count": iwm_leader,
        "source_diverse_peer_iwm_leader_signal_count": peer_iwm_leader,
        "sample_source_diverse_peer_iwm_rows": samples,
    }


def _run_peer_iwm_leader_variant(
    label: str,
    peer_iwm_leader_scalar: float,
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
    target_tickers = set(source_diversity_gate["target_tickers"])
    profiles = source_diversity_gate["profiles"]
    diversity_adjustments: list[dict[str, Any]] = []
    peer_adjustments: list[dict[str, Any]] = []
    iwm_adjustments: list[dict[str, Any]] = []
    peer_iwm_adjustments: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()

    def size_with_source_diversity_peer_iwm_leader(
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
                counts["source_diverse_eligible_signal"] += 1
                counts[f"source_diverse_eligible_{ticker}"] += 1
                profile = profiles.get(ticker)

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
                        "shares_after_scalar": int(sizing.get("shares_to_buy") or 0),
                        "source_diversity_profile": profile,
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

                is_peer_leader = (
                    signal.get("space_peer_momentum_state") == PEER_LEADER_STATE
                )
                is_iwm_leader = (
                    signal.get("space_iwm_relative_state") == IWM_LEADER_STATE
                )

                if is_peer_leader:
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
                            "source_diversity_profile": profile,
                            "space_peer_momentum_state": signal.get(
                                "space_peer_momentum_state"
                            ),
                            "space_peer_excess_momentum_20d_pct": signal.get(
                                "space_peer_excess_momentum_20d_pct"
                            ),
                            "space_iwm_relative_state": signal.get(
                                "space_iwm_relative_state"
                            ),
                            "trade_quality_score": signal.get("trade_quality_score"),
                            "confidence_score": signal.get("confidence_score"),
                        }
                    )

                if is_iwm_leader:
                    counts["source_diverse_iwm_leader_eligible_signal"] += 1
                    counts[f"source_diverse_iwm_leader_eligible_{ticker}"] += 1
                    shares_before_iwm = int(sizing.get("shares_to_buy") or 0)
                    source_diversity_exp._scale_sizing(
                        sizing,
                        ACCEPTED_SOURCE_DIVERSITY_IWM_LEADER_RISK_SCALAR,
                        portfolio_value,
                        "space_source_diversity_iwm_leader_risk",
                    )
                    iwm_adjustments.append(
                        {
                            "ticker": ticker,
                            "strategy": signal.get("strategy"),
                            "marker": "space_source_diversity_iwm_leader_risk",
                            "scalar": ACCEPTED_SOURCE_DIVERSITY_IWM_LEADER_RISK_SCALAR,
                            "shares_before_scalar": shares_before_iwm,
                            "shares_after_scalar": int(sizing.get("shares_to_buy") or 0),
                            "source_diversity_profile": profile,
                            "space_iwm_relative_state": signal.get(
                                "space_iwm_relative_state"
                            ),
                            "space_iwm_excess_vs_spy_20d_pct": signal.get(
                                "space_iwm_excess_vs_spy_20d_pct"
                            ),
                            "space_peer_momentum_state": signal.get(
                                "space_peer_momentum_state"
                            ),
                            "space_peer_excess_momentum_20d_pct": signal.get(
                                "space_peer_excess_momentum_20d_pct"
                            ),
                            "trade_quality_score": signal.get("trade_quality_score"),
                            "confidence_score": signal.get("confidence_score"),
                        }
                    )

                if is_peer_leader and is_iwm_leader:
                    counts["source_diverse_peer_iwm_leader_eligible_signal"] += 1
                    counts[f"source_diverse_peer_iwm_leader_eligible_{ticker}"] += 1
                    shares_before_triple = int(sizing.get("shares_to_buy") or 0)
                    source_diversity_exp._scale_sizing(
                        sizing,
                        peer_iwm_leader_scalar,
                        portfolio_value,
                        "space_source_diversity_peer_iwm_leader_risk",
                    )
                    shares_after_triple = int(sizing.get("shares_to_buy") or 0)
                    if shares_after_triple != shares_before_triple:
                        counts["source_diverse_peer_iwm_leader_changed_signal"] += 1
                        counts[
                            f"source_diverse_peer_iwm_leader_changed_{ticker}"
                        ] += 1
                    peer_iwm_adjustments.append(
                        {
                            "ticker": ticker,
                            "strategy": signal.get("strategy"),
                            "marker": "space_source_diversity_peer_iwm_leader_risk",
                            "scalar": peer_iwm_leader_scalar,
                            "shares_before_scalar": shares_before_triple,
                            "shares_after_scalar": shares_after_triple,
                            "source_diversity_profile": profile,
                            "space_iwm_relative_state": signal.get(
                                "space_iwm_relative_state"
                            ),
                            "space_iwm_excess_vs_spy_20d_pct": signal.get(
                                "space_iwm_excess_vs_spy_20d_pct"
                            ),
                            "space_peer_momentum_state": signal.get(
                                "space_peer_momentum_state"
                            ),
                            "space_peer_excess_momentum_20d_pct": signal.get(
                                "space_peer_excess_momentum_20d_pct"
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
                    "space_source_diversity_peer_leader_scalar": (
                        ACCEPTED_SOURCE_DIVERSITY_PEER_LEADER_RISK_SCALAR
                        if is_peer_leader
                        else 1.0
                    ),
                    "space_source_diversity_iwm_leader_scalar": (
                        ACCEPTED_SOURCE_DIVERSITY_IWM_LEADER_RISK_SCALAR
                        if is_iwm_leader
                        else 1.0
                    ),
                    "space_source_diversity_peer_iwm_leader_scalar": (
                        peer_iwm_leader_scalar
                        if is_peer_leader and is_iwm_leader
                        else 1.0
                    ),
                    "space_source_diversity_profile": profile,
                }
            adjusted.append(signal)
        return adjusted

    portfolio_engine.size_signals = size_with_source_diversity_peer_iwm_leader
    try:
        by_window: dict[str, Any] = {}
        for name, window in source_diversity_exp.WINDOWS.items():
            before_diversity_count = len(diversity_adjustments)
            before_peer_count = len(peer_adjustments)
            before_iwm_count = len(iwm_adjustments)
            before_peer_iwm_count = len(peer_iwm_adjustments)
            before_counts = Counter(counts)
            result = source_diversity_exp._run_window(window, universe, "space_snapshot")
            window_diversity = diversity_adjustments[before_diversity_count:]
            window_peer = peer_adjustments[before_peer_count:]
            window_iwm = iwm_adjustments[before_iwm_count:]
            window_peer_iwm = peer_iwm_adjustments[before_peer_iwm_count:]
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
                "source_diversity_iwm_leader_adjustment": (
                    source_diversity_exp._adjustment_summary(window_iwm)
                ),
                "source_diversity_peer_iwm_leader_adjustment": (
                    source_diversity_exp._adjustment_summary(window_peer_iwm)
                ),
                "source_diversity_peer_iwm_leader_counts": count_delta,
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
                "accepted_source_diversity_iwm_leader_risk_scalar": (
                    ACCEPTED_SOURCE_DIVERSITY_IWM_LEADER_RISK_SCALAR
                ),
                "space_source_diversity_peer_iwm_leader_scalar": (
                    peer_iwm_leader_scalar
                ),
                "target_tickers": source_diversity_gate["target_tickers"],
            },
            "by_window": by_window,
            "aggregate": source_diversity_exp._aggregate(metrics_by_window),
            "source_diversity_adjustment_summary": (
                source_diversity_exp._adjustment_summary(diversity_adjustments)
            ),
            "source_diversity_peer_leader_adjustment_summary": (
                source_diversity_exp._adjustment_summary(peer_adjustments)
            ),
            "source_diversity_iwm_leader_adjustment_summary": (
                source_diversity_exp._adjustment_summary(iwm_adjustments)
            ),
            "source_diversity_peer_iwm_leader_adjustment_summary": (
                source_diversity_exp._adjustment_summary(peer_iwm_adjustments)
            ),
            "source_diversity_peer_iwm_leader_adjustment_counts": dict(
                sorted(counts.items())
            ),
            "source_diversity_peer_iwm_leader_adjustment_sample": (
                peer_iwm_adjustments[:25]
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
        variant["source_diversity_peer_iwm_leader_adjustment_counts"].get(
            "source_diverse_peer_iwm_leader_changed_signal", 0
        )
    )
    eligible_count = int(
        variant["source_diversity_peer_iwm_leader_adjustment_counts"].get(
            "source_diverse_peer_iwm_leader_eligible_signal", 0
        )
    )
    scalar = float(
        variant["parameters"]["space_source_diversity_peer_iwm_leader_scalar"]
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
        "eligible_source_diversity_peer_iwm_leader_signal_count": eligible_count,
        "changed_source_diversity_peer_iwm_leader_signal_count": changed_count,
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
        f"# {EXPERIMENT_ID} Space source-diversity peer+IWM-leader risk",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Single Changed Variable",
        (
            "`space_source_diversity_peer_iwm_leader_scalar` after the accepted "
            "exp-108 source-diversity peer-leader and IWM-leader stack. Candidate "
            "pool, event labels, ranking, targets, stops, LLM/news, and live Space "
            "slots stay fixed."
        ),
        "",
        "## Gate 4 Summary",
        f"- Decision: `{payload['decision']}`",
        (
            "- Best scalar: "
            f"`{best['parameters']['space_source_diversity_peer_iwm_leader_scalar']}`"
        ),
        (
            "- Aggregate delta vs exp-108: "
            f"EV `{gate['aggregate_delta_vs_before']['expected_value_score_sum']:.6f}`, "
            f"PnL `{gate['aggregate_delta_vs_before']['total_pnl_sum']:.2f}`"
        ),
        (
            "- Source-diverse peer+IWM-leader signals changed: "
            f"`{gate['changed_source_diversity_peer_iwm_leader_signal_count']}` of "
            f"`{gate['eligible_source_diversity_peer_iwm_leader_signal_count']}` eligible"
        ),
        "",
        "## Three-Window Deltas vs Exp-108",
        "| window | EV delta | PnL delta | max DD delta | trades | survival | adjusted |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, delta in gate["by_window_delta_vs_before"].items():
        metrics = best["by_window"][name]["metrics"]
        adjusted = best["by_window"][name][
            "source_diversity_peer_iwm_leader_adjustment"
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

    before = _run_peer_iwm_leader_variant(
        "accepted_exp108_source_diversity_peer_iwm_leader_stack",
        1.0,
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
    runtime_state_gate = _runtime_state_gate(before)

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
        "source_diversity_peer_iwm_runtime_state": runtime_state_gate,
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
            runtime_state_gate["passed"],
        ]
    )

    variants = [
        _run_peer_iwm_leader_variant(
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
        for scalar in SOURCE_DIVERSITY_PEER_IWM_LEADER_RISK_SCALARS
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
            "No tested source-diverse peer+IWM-leader scalar improved aggregate "
            "EV/PnL across the three standard windows without a window-level EV "
            "regression and risk/survival violation."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "run_started_at": run_started_at,
        "run_finished_at": datetime.now(timezone.utc).isoformat(),
        "lane": "alpha_search",
        "hypothesis": (
            "On top of accepted exp-108 Space source-diversity peer-leader and "
            "IWM-leader stack, source-diverse official Space signals may deserve "
            "extra risk only when both ticker-level peer leadership and small-cap "
            "risk appetite confirm. This tests a production-visible catalyst-quality "
            "plus relative-strength plus tape-state interaction without changing the "
            "Space pool, event metadata, ranking, targets, stops, LLM boundary, or "
            "live slots."
        ),
        "change_type": "risk_allocation_shadow_sweep",
        "changed_variable": "space_source_diversity_peer_iwm_leader_risk_scalar",
        "single_causal_variable": (
            "extra risk scalar for source-diverse official Space signals when "
            "space_peer_momentum_state == leader and "
            "space_iwm_relative_state == smallcap_leader"
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
                "risk allocation: scale source-diverse official Space signals only "
                "when peer leadership and IWM small-cap risk appetite both confirm."
            ),
            "q2_prior_experiments": [
                "exp-20260513-038 accepted source-diversity risk.",
                "exp-20260513-039 accepted source-diversity peer-leader risk.",
                "exp-20260513-108 accepted source-diversity IWM-leader risk.",
                "exp-20260513-026 rejected nearby IWM+peer trend target widening.",
                "exp-20260513-106 rejected regulatory customer-source risk because only mid_weak improved.",
            ],
            "q3_single_causal_variable": (
                "Only the source-diversity peer+IWM-leader scalar changes; accepted "
                "exp-108 risk stack and all entry/exit/ranking/candidate variables "
                "stay fixed."
            ),
            "q4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; require positive aggregate "
                "EV/PnL, at least two EV-improved windows, no EV-regressed window, "
                "max drawdown damage <= 0.5pp, survival >= 5%, >=50 aggregate trades, "
                "and real adjusted source-diverse peer+IWM-leader signals."
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
            "official_space_tickers": list(source_diversity_exp.OFFICIAL_SPACE_TICKERS),
            "target_tickers": source_diversity_gate["target_tickers"],
            "accepted_source_diversity_risk_scalar": (
                ACCEPTED_SOURCE_DIVERSITY_RISK_SCALAR
            ),
            "accepted_source_diversity_peer_leader_risk_scalar": (
                ACCEPTED_SOURCE_DIVERSITY_PEER_LEADER_RISK_SCALAR
            ),
            "accepted_source_diversity_iwm_leader_risk_scalar": (
                ACCEPTED_SOURCE_DIVERSITY_IWM_LEADER_RISK_SCALAR
            ),
            "tested_source_diversity_peer_iwm_leader_scalars": list(
                SOURCE_DIVERSITY_PEER_IWM_LEADER_RISK_SCALARS
            ),
            "locked_variables": [
                "official Space candidate pool",
                "accepted exp-108 source-diversity peer-leader and IWM-leader stack",
                "all prior accepted Space risk helpers",
                "Space trend targets",
                "entry filters",
                "candidate ranking",
                "MAX_POSITIONS",
                "add-ons",
                "LLM/news replay",
                "live Space slots",
            ],
            "anti_js": "No JavaScript was used.",
        },
        "core_baseline": core,
        "before": before,
        "variants": variants,
        "best_variant": best_variant,
        "best_variant_gate": best_variant["gate"],
        "decision": decision,
        "status": (
            "accepted_default_off_space_source_diversity_peer_iwm_leader_risk"
            if decision == "accepted"
            else "rejected_space_source_diversity_peer_iwm_leader_risk"
        ),
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "Promote only as shared default-off Space metadata/helper, then collect "
            "forward replacement value before any live Space slots."
            if decision == "accepted"
            else (
                "Do not keep tuning source-diversity peer+IWM-leader scalars on this "
                "frozen sample. Prefer forward replacement-value evidence or a "
                "different production-visible official catalyst discriminator."
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
        },
        "why_not_other_changes": (
            "LLM soft-ranking remains label-thin, noisy ticker expansion and mature "
            "satcom breadth have failed, regulatory customer-source was single-window "
            "ASTS-heavy, and recent broad Space breakout/profile retunes are exhausted. "
            "This isolates a production-visible catalyst quality plus dual tape "
            "confirmation axis."
        ),
        "known_risks": [
            "The Space sleeve remains default-off and historical Space snapshots are frozen research copies.",
            "This is an interaction on a small Space sample and still requires forward replacement-value validation before live routing.",
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
            "space_source_diversity_peer_iwm_leader_scalar"
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
        "changed_source_diversity_peer_iwm_leader_signal_count": result[
            "best_variant_gate"
        ]["changed_source_diversity_peer_iwm_leader_signal_count"],
        "production_impact": result["production_impact"],
    }
    print(json.dumps(_safe(summary), indent=2, sort_keys=True))
