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
    ATTENTION_SEMANTIC_BUCKET,
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

EXPERIMENT_ID = "exp-20260513-035"
STEM = "space_breakout_risk_haircut"
ACCEPTED_ATTENTION_OVERLAY_RISK_SCALAR = 1.25
SPACE_BREAKOUT_RISK_SCALARS = (0.25, 0.50, 0.65, 0.75, 0.90, 1.00)
MAX_DRAWDOWN_DAMAGE_VS_BEFORE = 0.005
MIN_SURVIVAL_RATE = 0.05
MIN_TRADE_COUNT = 50


def _append_jsonl_for_this_experiment(path: Path, entry: dict[str, Any]) -> None:
    lines: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                if json.loads(line).get("experiment_id") == EXPERIMENT_ID:
                    continue
            except json.JSONDecodeError:
                pass
            lines.append(line)
    lines.append(json.dumps(_safe(entry), sort_keys=True))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_breakout_variant(
    label: str,
    breakout_scalar: float,
    *,
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
    breakout_adjustments: list[dict[str, Any]] = []
    breakout_counts: Counter[str] = Counter()

    def size_with_breakout_haircut(
        signals: list[dict[str, Any]],
        portfolio_value: float,
        risk_pct: float | None = None,
    ) -> list[dict[str, Any]]:
        sized = accepted_size_signals(signals, portfolio_value, risk_pct=risk_pct)
        adjusted: list[dict[str, Any]] = []
        for signal in sized:
            sizing = deepcopy(signal.get("sizing") or {})
            strategy = str(signal.get("strategy") or "").lower()
            ticker = str(signal.get("ticker") or "").upper()
            is_space_breakout = ticker in OFFICIAL_SPACE_TICKERS and strategy == "breakout_long"
            if is_space_breakout and sizing:
                shares_before = int(sizing.get("shares_to_buy") or 0)
                _scale_sizing(sizing, breakout_scalar, portfolio_value, "space_breakout_risk_haircut")
                shares_after = int(sizing.get("shares_to_buy") or 0)
                breakout_counts["eligible"] += 1
                if shares_after != shares_before:
                    breakout_counts["changed"] += 1
                    breakout_adjustments.append(
                        {
                            "ticker": ticker,
                            "strategy": strategy,
                            "shares_before": shares_before,
                            "shares_after": shares_after,
                            "scalar": breakout_scalar,
                            "confidence": signal.get("confidence"),
                            "trend_quality_score": signal.get("trend_quality_score"),
                            "event_types": signal.get("space_event_types"),
                            "source_types": signal.get("space_source_types"),
                            "semantic_buckets": signal.get("space_semantic_buckets"),
                        }
                    )
                signal = {
                    **signal,
                    "sizing": sizing,
                    "space_breakout_risk_haircut_eligible": True,
                    "space_breakout_risk_scalar": breakout_scalar,
                }
            adjusted.append(signal)
        return adjusted

    portfolio_engine.size_signals = size_with_breakout_haircut
    try:
        by_window: dict[str, Any] = {}
        for name, window in WINDOWS.items():
            before_breakout = len(breakout_adjustments)
            result = _run_window(window, universe, "space_snapshot")
            by_window[name] = {
                "metrics": _metrics(result),
                "space_trade_attribution": _space_trade_attribution(result),
                "space_breakout_risk_adjustment": _adjustment_summary(
                    breakout_adjustments[before_breakout:]
                ),
            }
        metrics_by_window = {name: row["metrics"] for name, row in by_window.items()}
        return {
            "label": label,
            "parameters": {
                "accepted_attention_overlay_risk_scalar": ACCEPTED_ATTENTION_OVERLAY_RISK_SCALAR,
                "space_breakout_risk_scalar": breakout_scalar,
            },
            "by_window": by_window,
            "aggregate": _aggregate(metrics_by_window),
            "breakout_adjustment_summary": _adjustment_summary(breakout_adjustments),
            "breakout_adjustment_counts": dict(breakout_counts),
            "breakout_adjustment_sample": breakout_adjustments[:20],
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
    adjusted_count = int(variant["breakout_adjustment_counts"].get("changed", 0))
    scalar = float(variant["parameters"]["space_breakout_risk_scalar"])
    gate = {
        "aggregate_delta_vs_before": aggregate_delta,
        "by_window_delta_vs_before": by_window_delta,
        "ev_improvements": ev_improvements,
        "ev_regressions": ev_regressions,
        "max_drawdown_damage_vs_before": max_drawdown_damage,
        "min_survival_rate": min_survival_rate,
        "trade_count": trade_count,
        "adjusted_breakout_signal_count": adjusted_count,
        "accepted": bool(
            scalar != 1.0
            and adjusted_count > 0
            and aggregate_delta["expected_value_score_sum"] > 0
            and aggregate_delta["total_pnl_sum"] > 0
            and len(ev_improvements) >= 2
            and not ev_regressions
            and max_drawdown_damage <= MAX_DRAWDOWN_DAMAGE_VS_BEFORE
            and min_survival_rate >= MIN_SURVIVAL_RATE
            and trade_count >= MIN_TRADE_COUNT
        ),
    }
    return gate


def _artifact_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID} Space breakout risk haircut",
        "",
        "## Hypothesis",
        (
            "Space sleeve PnL in the accepted exp-032 stack is dominated by trend_long. "
            "A single additional risk scalar on official Space breakout_long signals may improve "
            "expected value by reducing lower-quality breakout exposure without changing the pool, "
            "event labels, ranking, targets, stops, or LLM boundary."
        ),
        "",
        "## Single changed variable",
        "`space_breakout_risk_scalar` applied after the accepted exp-032 attention overlay stack.",
        "",
        "## Gate 4 summary",
        f"- Decision: `{payload['decision']}`",
        f"- Best scalar: `{payload['best_variant']['parameters']['space_breakout_risk_scalar']}`",
        (
            "- Aggregate delta vs exp-032: "
            f"EV `{payload['best_variant_gate']['aggregate_delta_vs_before']['expected_value_score_sum']:.6f}`, "
            f"PnL `{payload['best_variant_gate']['aggregate_delta_vs_before']['total_pnl_sum']:.2f}`"
        ),
        "",
        "## Three-window deltas vs exp-032",
        "| window | EV delta | PnL delta | max DD delta | trades | survival |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name, delta in payload["best_variant_gate"]["by_window_delta_vs_before"].items():
        metrics = payload["best_variant"]["by_window"][name]["metrics"]
        lines.append(
            "| {name} | {ev:.6f} | {pnl:.2f} | {dd:.6f} | {trades} | {survival:.6f} |".format(
                name=name,
                ev=delta["expected_value_score"],
                pnl=delta["total_pnl"],
                dd=delta["max_drawdown_pct"],
                trades=metrics["trade_count"],
                survival=metrics["survival_rate"],
            )
        )
    lines.extend(
        [
            "",
            "## Production impact",
            "No shared production policy was changed by this experiment artifact. If accepted, the scalar must be promoted into `quant/space_catalyst_sleeve.py` and covered by parity tests before live use.",
        ]
    )
    return "\n".join(lines) + "\n"


def _ticket(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["decision"],
        "title": "Space breakout risk scalar on exp-032 attention stack",
        "hypothesis": payload["hypothesis"],
        "changed_variable": payload["changed_variable"],
        "best_parameters": payload["best_variant"]["parameters"],
        "aggregate_delta_vs_before": payload["best_variant_gate"]["aggregate_delta_vs_before"],
        "next_action": payload["next_evidence_needed"],
    }


def run() -> dict[str, Any]:
    run_started_at = datetime.now(timezone.utc).isoformat()
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
    government_contract_gate = _field_check_government_contract_profile()
    if not government_contract_gate["passed"]:
        raise RuntimeError(
            f"Government-contract profile field check failed: {government_contract_gate}"
        )
    single_event_gate = _field_check_single_event_defense_profile()
    if not single_event_gate["passed"]:
        raise RuntimeError(
            f"Single-event defense profile field check failed: {single_event_gate}"
        )
    attention_gate = _field_check_attention_overlay_profile()
    if not attention_gate["passed"]:
        raise RuntimeError(f"Attention-overlay field check failed: {attention_gate}")

    core = _run_core_baseline()
    before = _run_exp032_variant(
        "accepted_exp032_attention_overlay_stack",
        ACCEPTED_ATTENTION_OVERLAY_RISK_SCALAR,
        attention_gate,
        single_event_gate,
        government_contract_gate,
        source_gate,
        multi_event_gate,
        liquidity_gate,
        company_release_gate,
        financing_gate,
    )
    peer_state_gate = _field_check_peer_leader_state(before)
    if not peer_state_gate["passed"]:
        raise RuntimeError(f"Peer momentum state field check failed: {peer_state_gate}")
    iwm_peer_leader_gate = _field_check_iwm_peer_leader_trend(before)
    if not iwm_peer_leader_gate["passed"]:
        raise RuntimeError(
            f"IWM peer-leader trend field check failed: {iwm_peer_leader_gate}"
        )

    gate2 = {
        "open_positions": gate2_open,
        "official_customer_source_profile": source_gate,
        "attention_overlay_profile": attention_gate,
        "single_event_defense_profile": single_event_gate,
        "peer_momentum_state": peer_state_gate,
        "iwm_peer_leader_trend_state": iwm_peer_leader_gate,
        "accepted_financing_dilution_profiles": financing_gate,
        "accepted_company_release_source_profile": company_release_gate,
        "watch_liquidity_tier_registry": liquidity_gate,
        "accepted_multi_event_depth": multi_event_gate,
        "government_contract_profile": government_contract_gate,
        "runtime_fields": [
            "operator_inputs/open_positions.json entry_date",
            "operator_inputs/open_positions.json target_price",
            "data/space_catalyst_event_seeds.jsonl event_fields",
            "data/space_catalyst_event_seeds.jsonl semantic_bucket",
            "data/space_catalyst_event_seeds.jsonl source_type",
            "sizing.shares_to_buy from shared sizing engine",
            "signal.strategy breakout_long",
        ],
        "passed": (
            gate2_open["passed"]
            and source_gate["passed"]
            and attention_gate["passed"]
            and single_event_gate["passed"]
            and peer_state_gate["passed"]
            and iwm_peer_leader_gate["passed"]
            and financing_gate["passed"]
            and company_release_gate["passed"]
            and liquidity_gate["passed"]
            and multi_event_gate["passed"]
            and government_contract_gate["passed"]
        ),
    }

    variants = [
        _run_breakout_variant(
            f"{STEM}_{str(scalar).replace('.', '_')}",
            scalar,
            attention_gate=attention_gate,
            single_event_gate=single_event_gate,
            government_contract_gate=government_contract_gate,
            source_gate=source_gate,
            multi_event_gate=multi_event_gate,
            liquidity_gate=liquidity_gate,
            company_release_gate=company_release_gate,
            financing_gate=financing_gate,
        )
        for scalar in SPACE_BREAKOUT_RISK_SCALARS
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
            "No tested Space breakout risk scalar improved aggregate EV/PnL across the three standard windows "
            "without a window-level EV regression and risk/trade-count violation."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "run_started_at": run_started_at,
        "run_finished_at": datetime.now(timezone.utc).isoformat(),
        "hypothesis": (
            "On top of accepted exp-032 Space attention overlay stack, reducing official Space breakout_long "
            "risk may improve EV because current Space attribution is trend-dominated and mid_weak breakouts "
            "were net losers."
        ),
        "change_type": "alpha_search",
        "changed_variable": "space_breakout_risk_scalar",
        "backtest_protocol": {
            "source": "docs/backtesting.md core multi-window protocol",
            "windows": WINDOWS,
        },
        "gate_questions": {
            "q1_alpha_hypothesis": "risk allocation: apply one extra scalar only to official Space breakout_long signals on accepted exp-032 stack",
            "q2_prior_experiments": [
                "exp-20260512-013 accepted peer-nonleader breakout zero-risk scalar in an older stack",
                "exp-20260512-021 rejected 52-week breakout volume scaler",
                "exp-20260513-025 rejected peer-leader breakout risk scalar",
                "exp-20260513-032 accepted attention overlay risk scalar and is the baseline for this run",
            ],
            "q3_single_causal_variable": "Only space_breakout_risk_scalar changes; pool, labels, ranking, targets, stops, LLM, and live slots remain fixed.",
            "q4_acceptance_standard": (
                "Aggregate EV and PnL vs exp-032 must improve, at least two windows improve EV, no window regresses EV, "
                "drawdown damage <= 0.5pp, survival >= 5%, aggregate trades >= 50, and the scalar must touch real breakout signals."
            ),
            "q5_reproducibility": f"Run .\\.venv\\Scripts\\python.exe quant\\experiments\\{Path(__file__).name}",
        },
        "gate2_field_checks": gate2,
        "locked_variables": {
            "candidate_pool": "unchanged accepted Space universe",
            "event_labels": "unchanged data/space_catalyst_event_seeds.jsonl",
            "ranking": "unchanged",
            "targets_and_stops": "unchanged",
            "llm_boundary": "unchanged",
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
        },
        "core_baseline": core,
        "before": before,
        "variants": variants,
        "best_variant": best_variant,
        "best_variant_gate": best_variant["gate"],
        "decision": decision,
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "If rejected, do not keep tuning broad Space breakout risk. Prefer a different alpha axis such as "
            "trend continuation sizing by catalyst durability or candidate-pool quality expansion with production-visible metadata."
            if decision == "rejected"
            else "Promote scalar into the shared Space policy and add parity tests before enabling in live routing."
        ),
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "promotion_required_if_accepted": decision == "accepted",
        },
        "why_not_other_changes": (
            "LLM soft-ranking remains label-thin; adding noisy tickers was avoided. "
            "This run isolates one production-visible risk allocation axis already supported by historical Space attribution."
        ),
        "known_risks": [
            "Breakout sample count is small; broad scalar decisions can be noisy.",
            "Experiment artifact alone does not change production behavior.",
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
            "parameters": payload["best_variant"]["parameters"],
            "date_range": [
                f"{label}:{window['start']}..{window['end']}"
                for label, window in WINDOWS.items()
            ],
            "backtest_protocol": payload["backtest_protocol"],
            "before_metrics": payload["before"]["aggregate"],
            "after_metrics": payload["best_variant"]["aggregate"],
            "expected_value_score_delta": payload["best_variant_gate"]["aggregate_delta_vs_before"]["expected_value_score_sum"],
            "decision": payload["decision"],
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
        "decision": result["decision"],
        "best_scalar": result["best_variant"]["parameters"]["space_breakout_risk_scalar"],
        "aggregate_before": result["before"]["aggregate"],
        "aggregate_after": result["best_variant"]["aggregate"],
        "aggregate_delta_vs_before": result["best_variant_gate"]["aggregate_delta_vs_before"],
        "by_window_delta_vs_before": result["best_variant_gate"]["by_window_delta_vs_before"],
        "adjusted_breakout_signal_count": result["best_variant_gate"]["adjusted_breakout_signal_count"],
        "production_impact": result["production_impact"],
    }
    print(json.dumps(_safe(summary), indent=2, sort_keys=True))
