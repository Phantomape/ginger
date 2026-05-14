"""exp-20260514-044: Space benchmark-breadth peer-nonleader trend risk.

Tests one causal variable on top of accepted exp-20260514-041: whether an
official Space trend signal that has broad closed 10d benchmark confirmation
but is still a peer nonleader deserves a small extra default-off allocation.

This is a risk-allocation test, not a ticker expansion, LLM change, ranking
change, lifecycle change, or live Space slot change.
"""

from __future__ import annotations

import json
import logging
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = PROJECT_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for path in (str(QUANT_DIR), str(EXPERIMENTS_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import exp_20260514_041_space_benchmark_breadth_trend_risk as exp041


logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("portfolio_engine").setLevel(logging.ERROR)

EXPERIMENT_ID = "exp-20260514-044"
STEM = "space_benchmark_breadth_peer_nonleader_trend_risk"
BEFORE_EXPERIMENT_ID = "exp-20260514-041"

ACCEPTED_BENCHMARK_BREADTH_SCALAR = 1.025
PEER_NONLEADER_TREND_SCALARS = (1.0, 1.025, 1.05, 1.075, 1.10)
TARGET_STRATEGY = "trend_long"
TARGET_PEER_STATE = "nonleader"
MARKER = "space_benchmark_breadth_peer_nonleader_trend_risk"

MAX_DRAWDOWN_DAMAGE_VS_BEFORE = 0.005
MIN_SURVIVAL_RATE = 0.05
MIN_TRADE_COUNT = 50


def _safe(payload: Any) -> Any:
    return exp041._safe(payload)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    exp041._write_json(path, payload)


def _append_jsonl_for_this_experiment(path: Path, entry: dict[str, Any]) -> None:
    lines: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
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


def _extra_scale_and_record(
    *,
    signal: dict[str, Any],
    sizing: dict[str, Any],
    scalar: float,
    portfolio_value: float,
    counts: Counter[str],
    adjustments: list[dict[str, Any]],
    profile: dict[str, Any] | None,
) -> None:
    ticker = str(signal.get("ticker") or "").upper()
    shares_before = int(sizing.get("shares_to_buy") or 0)
    dollars_before = float(sizing.get("position_size_dollars") or 0.0)
    exp041.source_diversity_exp._scale_sizing(
        sizing,
        scalar,
        portfolio_value,
        MARKER,
    )
    shares_after = int(sizing.get("shares_to_buy") or 0)
    dollars_after = float(sizing.get("position_size_dollars") or 0.0)
    counts[f"{MARKER}_eligible_signal"] += 1
    counts[f"{MARKER}_eligible_{ticker}"] += 1
    if shares_after != shares_before:
        counts[f"{MARKER}_changed_signal"] += 1
        counts[f"{MARKER}_changed_{ticker}"] += 1
    adjustments.append(
        {
            "ticker": ticker,
            "strategy": signal.get("strategy"),
            "marker": MARKER,
            "scalar": scalar,
            "shares_before_scalar": shares_before,
            "shares_after_scalar": shares_after,
            "dollars_before_scalar": dollars_before,
            "dollars_after_scalar": dollars_after,
            "profile": profile,
            "space_peer_momentum_state": signal.get("space_peer_momentum_state"),
            "space_iwm_relative_state": signal.get("space_iwm_relative_state"),
            "trade_quality_score": signal.get("trade_quality_score"),
            "confidence_score": signal.get("confidence_score"),
        }
    )


def _run_exp041_stack_variant(
    label: str,
    *,
    peer_nonleader_scalar: float,
    gates: dict[str, Any],
) -> dict[str, Any]:
    original_extra = exp041._scale_and_record_extra
    peer_nonleader_adjustments: list[dict[str, Any]] = []

    def patched_extra(
        *,
        signal: dict[str, Any],
        sizing: dict[str, Any],
        scalar: float,
        portfolio_value: float,
        marker: str,
        counts: Counter[str],
        adjustments: list[dict[str, Any]],
        profile: dict[str, Any] | None,
    ) -> None:
        original_extra(
            signal=signal,
            sizing=sizing,
            scalar=scalar,
            portfolio_value=portfolio_value,
            marker=marker,
            counts=counts,
            adjustments=adjustments,
            profile=profile,
        )
        if marker != "space_benchmark_breadth_trend_risk":
            return
        if str(signal.get("strategy") or "") != TARGET_STRATEGY:
            return
        if str(signal.get("space_peer_momentum_state") or "") != TARGET_PEER_STATE:
            return
        if not sizing:
            return
        _extra_scale_and_record(
            signal=signal,
            sizing=sizing,
            scalar=peer_nonleader_scalar,
            portfolio_value=portfolio_value,
            counts=counts,
            adjustments=peer_nonleader_adjustments,
            profile=profile,
        )
        signal["space_benchmark_breadth_peer_nonleader_trend_bucket"] = True
        signal["space_benchmark_breadth_peer_nonleader_trend_scalar"] = (
            peer_nonleader_scalar
        )

    exp041._scale_and_record_extra = patched_extra
    try:
        variant = exp041._run_exp030_stack_variant(
            label,
            benchmark_breadth_scalar=ACCEPTED_BENCHMARK_BREADTH_SCALAR,
            benchmark_breadth_gate=gates["benchmark_breadth_gate"],
            delayed_gate=gates["delayed_gate"],
            forward_gate=gates["forward_gate"],
            source_diversity_gate=gates["source_diversity_gate"],
            attention_gate=gates["attention_gate"],
            single_event_gate=gates["single_event_gate"],
            government_contract_gate=gates["government_contract_gate"],
            source_gate=gates["source_gate"],
            multi_event_gate=gates["multi_event_gate"],
            liquidity_gate=gates["liquidity_gate"],
            company_release_gate=gates["company_release_gate"],
            financing_gate=gates["financing_gate"],
        )
    finally:
        exp041._scale_and_record_extra = original_extra

    counts = Counter(variant.get("source_diversity_trend_counts") or {})
    peer_counts = {
        key: value for key, value in sorted(counts.items()) if MARKER in key
    }
    by_window_counts = {
        name: {
            key: value
            for key, value in sorted(
                (row.get("source_diversity_trend_counts") or {}).items()
            )
            if MARKER in key
        }
        for name, row in variant["by_window"].items()
    }
    variant["parameters"] = {
        **variant["parameters"],
        "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
        "accepted_benchmark_breadth_trend_scalar": (
            ACCEPTED_BENCHMARK_BREADTH_SCALAR
        ),
        "space_benchmark_breadth_peer_nonleader_trend_scalar": (
            peer_nonleader_scalar
        ),
        "target_strategy": TARGET_STRATEGY,
        "target_peer_momentum_state": TARGET_PEER_STATE,
    }
    variant["peer_nonleader_benchmark_breadth_counts"] = peer_counts
    variant["peer_nonleader_benchmark_breadth_counts_by_window"] = by_window_counts
    variant["peer_nonleader_benchmark_breadth_adjustment_summary"] = (
        exp041.source_diversity_exp._adjustment_summary(peer_nonleader_adjustments)
    )
    variant["peer_nonleader_benchmark_breadth_adjustment_sample"] = (
        peer_nonleader_adjustments[:25]
    )
    return variant


def _gate_variant(variant: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    aggregate_delta = exp041.source_diversity_exp._aggregate_delta(
        variant["aggregate"],
        before["aggregate"],
    )
    by_window_delta = {
        name: exp041.source_diversity_exp._delta(
            payload["metrics"],
            before["by_window"][name]["metrics"],
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
    counts = variant.get("peer_nonleader_benchmark_breadth_counts") or {}
    changed_count = int(counts.get(f"{MARKER}_changed_signal", 0))
    eligible_count = int(counts.get(f"{MARKER}_eligible_signal", 0))
    scalar = float(
        variant["parameters"]["space_benchmark_breadth_peer_nonleader_trend_scalar"]
    )
    return {
        "aggregate_delta_vs_before": aggregate_delta,
        "by_window_delta_vs_before": by_window_delta,
        "ev_improved_windows": ev_improvements,
        "ev_regressed_windows": ev_regressions,
        "eligible_peer_nonleader_signal_count": eligible_count,
        "changed_peer_nonleader_signal_count": changed_count,
        "accepted": bool(
            scalar != 1.0
            and changed_count > 0
            and aggregate_delta["expected_value_score_sum"] > 0
            and aggregate_delta["total_pnl_sum"] > 0
            and len(ev_improvements) >= 2
            and not ev_regressions
            and aggregate_delta["max_drawdown_pct_max"]
            <= MAX_DRAWDOWN_DAMAGE_VS_BEFORE
            and variant["aggregate"]["min_survival_rate"] >= MIN_SURVIVAL_RATE
            and variant["aggregate"]["trade_count_sum"] >= MIN_TRADE_COUNT
        ),
    }


def _collect_gates() -> dict[str, Any]:
    source = exp041.source_diversity_exp
    same_theme = exp041.same_theme_exp
    delayed = exp041.delayed_exp
    attention_gate = source._field_check_attention_overlay_profile()
    single_event_gate = source._field_check_single_event_defense_profile()
    government_contract_gate = source._field_check_government_contract_profile()
    source_gate = source._event_seed_profiles()
    multi_event_gate = source._field_check_multi_event_depth()
    liquidity_gate = source._field_check_watch_liquidity_tier()
    company_release_gate = source._field_check_company_release_source()
    financing_gate = source._accepted_financing_profile_gate()
    source_diversity_gate = source._field_check_source_diversity_profile()
    forward_gate = same_theme._forward_replacement_profile_gate()
    delayed_gate = delayed._delayed_absorption_profile_gate(forward_gate)
    benchmark_breadth_gate = exp041._benchmark_breadth_profile_gate()
    return {
        "attention_gate": attention_gate,
        "single_event_gate": single_event_gate,
        "government_contract_gate": government_contract_gate,
        "source_gate": source_gate,
        "multi_event_gate": multi_event_gate,
        "liquidity_gate": liquidity_gate,
        "company_release_gate": company_release_gate,
        "financing_gate": financing_gate,
        "source_diversity_gate": source_diversity_gate,
        "forward_gate": forward_gate,
        "delayed_gate": delayed_gate,
        "benchmark_breadth_gate": benchmark_breadth_gate,
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    gate = payload["best_variant_gate"]
    lines = [
        f"# {EXPERIMENT_ID} Space benchmark-breadth peer-nonleader trend risk",
        "",
        "## Hypothesis",
        payload["hypothesis"],
        "",
        "## Single Changed Variable",
        (
            "`space_benchmark_breadth_peer_nonleader_trend_scalar` for official "
            "Space `trend_long` signals whose accepted benchmark-breadth profile "
            "is true and whose Space peer momentum state is `nonleader`. "
            "Candidate pool, ranking, targets, stops, LLM/news, accepted exp041 "
            "stack, and live Space slots stay fixed."
        ),
        "",
        "## Gate 4 Summary",
        f"- Decision: `{payload['decision']}`",
        f"- Best scalar: `{best['parameters']['space_benchmark_breadth_peer_nonleader_trend_scalar']}`",
        (
            "- Aggregate delta vs exp041: "
            f"EV `{gate['aggregate_delta_vs_before']['expected_value_score_sum']:.6f}`, "
            f"PnL `{gate['aggregate_delta_vs_before']['total_pnl_sum']:.2f}`"
        ),
        (
            "- Peer-nonleader benchmark-breadth signals changed: "
            f"`{gate['changed_peer_nonleader_signal_count']}` of "
            f"`{gate['eligible_peer_nonleader_signal_count']}` eligible"
        ),
        "",
        "## Three-Window Deltas vs Exp041",
        "| window | EV delta | PnL delta | max DD delta | trades | survival | adjusted |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, delta in gate["by_window_delta_vs_before"].items():
        metrics = best["by_window"][name]["metrics"]
        counts = best["peer_nonleader_benchmark_breadth_counts_by_window"][name]
        adjusted = counts.get(f"{MARKER}_changed_signal", 0)
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
    core = exp041.source_diversity_exp._run_core_baseline()
    gates = _collect_gates()
    variants = [
        _run_exp041_stack_variant(
            f"{STEM}_{str(scalar).replace('.', '_')}",
            peer_nonleader_scalar=scalar,
            gates=gates,
        )
        for scalar in PEER_NONLEADER_TREND_SCALARS
    ]
    before = variants[0]
    for variant in variants:
        variant["gate"] = _gate_variant(variant, before)

    accepted_variants = [variant for variant in variants if variant["gate"]["accepted"]]
    if accepted_variants:
        best = max(
            accepted_variants,
            key=lambda variant: (
                variant["gate"]["aggregate_delta_vs_before"][
                    "expected_value_score_sum"
                ],
                variant["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
            ),
        )
    else:
        best = max(
            variants,
            key=lambda variant: (
                variant["gate"]["aggregate_delta_vs_before"][
                    "expected_value_score_sum"
                ],
                variant["gate"]["aggregate_delta_vs_before"]["total_pnl_sum"],
            ),
        )

    runtime_gate = {
        "passed": best["gate"]["eligible_peer_nonleader_signal_count"] > 0,
        "eligible_signal_count": best["gate"]["eligible_peer_nonleader_signal_count"],
        "required_runtime_fields": [
            "data/space_catalyst_event_state_shadow_ledger.jsonl horizons.10d",
            "signal.strategy",
            "signal.space_peer_momentum_state",
            "signal.sizing.shares_to_buy",
        ],
        "sample_rows": best.get(
            "peer_nonleader_benchmark_breadth_adjustment_sample",
            [],
        )[:10],
    }
    gate2 = {
        "open_positions": exp041.source_diversity_exp._gate2_open_positions(),
        "benchmark_breadth_profile": gates["benchmark_breadth_gate"],
        "peer_nonleader_runtime_state": runtime_gate,
    }
    gate2["passed"] = all(
        [
            gate2["open_positions"]["passed"],
            gates["benchmark_breadth_gate"]["passed"],
            runtime_gate["passed"],
        ]
    )

    decision = "accepted" if best["gate"]["accepted"] else "rejected"
    status = (
        "accepted_default_off_space_benchmark_breadth_peer_nonleader_trend_risk"
        if decision == "accepted"
        else "rejected_space_benchmark_breadth_peer_nonleader_trend_risk"
    )
    rejection_reason = ""
    if decision == "rejected":
        rejection_reason = (
            "The peer-nonleader benchmark-breadth trend interaction did not "
            "clear Gate 4 versus the accepted exp041 stack. Do not retry this "
            "interaction on frozen snapshots without new closed forward rows "
            "or a different catalyst-quality field."
        )

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "run_started_at": run_started_at,
        "run_finished_at": datetime.now(timezone.utc).isoformat(),
        "lane": "alpha_search",
        "hypothesis": (
            "Space peer-nonleader trend signals may represent delayed catch-up "
            "rather than weakness when the closed 10d event-state profile is "
            "positive versus cash, SPY, QQQ, UFO, and ARKX. A conservative "
            "extra allocation should improve the default-off Space replay "
            "without changing entries, exits, ranking, LLM/news, ticker pool, "
            "or live slots."
        ),
        "change_type": "risk_allocation_shadow_sweep",
        "changed_variable": "space_benchmark_breadth_peer_nonleader_trend_scalar",
        "single_causal_variable": (
            "extra risk scalar for benchmark-breadth trend signals whose peer "
            "state is nonleader; accepted exp041 stack stays fixed"
        ),
        "backtest_protocol": {
            "source": "docs/backtesting.md core multi-window protocol plus Space frozen snapshots",
            "windows": exp041.source_diversity_exp.WINDOWS,
            "space_snapshots": {
                label: window["space_snapshot"]
                for label, window in exp041.source_diversity_exp.WINDOWS.items()
            },
        },
        "gate_questions": {
            "q1_alpha_hypothesis": (
                "risk allocation: benchmark-confirmed Space trend candidates "
                "that are still peer nonleaders may be delayed-absorption "
                "catch-up candidates."
            ),
            "q2_prior_experiments": [
                "exp-20260512-013 accepted zero extra risk for peer-nonleader breakouts.",
                "exp-20260513-020 accepted IWM-plus-peer-leader trend risk.",
                "exp-20260514-041 accepted benchmark-breadth trend risk at 1.025x.",
                "exp-20260514-042 rejected 20d durability because it had too little changed coverage.",
            ],
            "q3_single_causal_variable": (
                "Only this peer-nonleader benchmark-breadth trend scalar changes."
            ),
            "q4_acceptance_standard": (
                "Same three Space windows; require positive aggregate EV/PnL, "
                "at least two EV-improved windows, no EV-regressed windows, max "
                "DD damage <= 0.5pp, survival >= 5%, >=50 trades, and nonzero "
                "changed target signals."
            ),
            "q5_reproducibility": (
                f"Run .\\.venv\\Scripts\\python.exe quant\\experiments\\{Path(__file__).name}"
            ),
        },
        "gate1": {
            "core_baseline": core["aggregate"],
            "accepted_before_metrics": before["aggregate"],
            "accepted_before_experiment": BEFORE_EXPERIMENT_ID,
        },
        "gate2_field_checks": gate2,
        "gate3": {
            "new_filter_added": False,
            "new_risk_scalar_added": True,
            "min_survival_rate_after": best["aggregate"]["min_survival_rate"],
            "passed": best["aggregate"]["min_survival_rate"] >= MIN_SURVIVAL_RATE,
        },
        "parameters": {
            "tested_scalars": list(PEER_NONLEADER_TREND_SCALARS),
            "selected_scalar": best["parameters"][
                "space_benchmark_breadth_peer_nonleader_trend_scalar"
            ],
            "target_strategy": TARGET_STRATEGY,
            "target_peer_momentum_state": TARGET_PEER_STATE,
            "accepted_benchmark_breadth_trend_scalar": (
                ACCEPTED_BENCHMARK_BREADTH_SCALAR
            ),
            "anti_js": "No JavaScript was used.",
            "locked_variables": [
                "official Space candidate pool",
                "all accepted Space scalars through exp041",
                "entry filters",
                "candidate ranking",
                "targets/stops",
                "MAX_POSITIONS",
                "LLM/news replay",
                "live Space slots",
            ],
        },
        "core_baseline": core,
        "before": before,
        "variants": variants,
        "best_variant": best,
        "best_variant_gate": best["gate"],
        "decision": decision,
        "status": status,
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "Promote only with shared Space metadata/helper and parity tests; "
            "live Space slots remain zero."
            if decision == "accepted"
            else "Needs new closed Space forward rows or a different catalyst-quality field."
        ),
        "production_impact": {
            "alters_candidate_ranking": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_sizing": decision == "accepted",
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
            "LLM soft-ranking remains sparse; VSAT/IRDM expansion and 5d/20d "
            "forward timing branches were already rejected or sample-limited. "
            "This tests one peer-state allocation interaction inside the "
            "accepted benchmark-breadth trend cohort."
        ),
        "known_risks": [
            "Space remains default-off; this does not authorize live Space slots.",
            "The current peer-nonleader benchmark-breadth slice may be narrow.",
        ],
        "llm_metrics": {"used_llm": False},
    }
    return payload


def persist(payload: dict[str, Any]) -> None:
    exp_dir = PROJECT_ROOT / "data" / "experiments" / EXPERIMENT_ID
    logs_dir = PROJECT_ROOT / "docs" / "experiments" / "logs"
    tickets_dir = PROJECT_ROOT / "docs" / "experiments" / "tickets"
    artifacts_dir = PROJECT_ROOT / "docs" / "experiments" / "artifacts"
    for directory in (exp_dir, logs_dir, tickets_dir, artifacts_dir):
        directory.mkdir(parents=True, exist_ok=True)

    artifact = _artifact_markdown(payload)
    payload["artifact_markdown"] = artifact
    _write_json(exp_dir / f"{STEM}.json", payload)
    _write_json(logs_dir / f"{EXPERIMENT_ID}.json", payload)
    _write_json(tickets_dir / f"{EXPERIMENT_ID}.json", _ticket(payload))
    (artifacts_dir / f"{EXPERIMENT_ID}_{STEM}.md").write_text(
        artifact,
        encoding="utf-8",
    )
    _append_jsonl_for_this_experiment(
        PROJECT_ROOT / "docs" / "experiment_log.jsonl",
        {
            "experiment_id": payload["experiment_id"],
            "timestamp": payload["run_finished_at"],
            "lane": payload["lane"],
            "status": payload["status"],
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "changed_variable": payload["changed_variable"],
            "parameters": payload["parameters"],
            "date_range": payload["backtest_protocol"]["windows"],
            "before_metrics": payload["before"]["by_window"],
            "after_metrics": payload["best_variant"]["by_window"],
            "delta_metrics": payload["best_variant_gate"],
            "expected_value_score_delta": payload["best_variant_gate"][
                "aggregate_delta_vs_before"
            ]["expected_value_score_sum"],
            "total_pnl_delta": payload["best_variant_gate"][
                "aggregate_delta_vs_before"
            ]["total_pnl_sum"],
            "production_impact": payload["production_impact"],
            "decision": payload["decision"],
            "rejection_reason": payload["rejection_reason"],
            "next_evidence_needed": payload["next_evidence_needed"],
            "related_files": [
                f"quant/experiments/{Path(__file__).name}",
                f"data/experiments/{EXPERIMENT_ID}/{STEM}.json",
                f"docs/experiments/logs/{EXPERIMENT_ID}.json",
                f"docs/experiments/tickets/{EXPERIMENT_ID}.json",
                f"docs/experiments/artifacts/{EXPERIMENT_ID}_{STEM}.md",
                "docs/experiment_log.jsonl",
            ],
        },
    )


if __name__ == "__main__":
    result = run()
    persist(result)
    summary = {
        "experiment_id": result["experiment_id"],
        "status": result["status"],
        "decision": result["decision"],
        "selected_scalar": result["parameters"]["selected_scalar"],
        "aggregate_delta_vs_before": result["best_variant_gate"][
            "aggregate_delta_vs_before"
        ],
        "eligible_peer_nonleader_signal_count": result["best_variant_gate"][
            "eligible_peer_nonleader_signal_count"
        ],
        "changed_peer_nonleader_signal_count": result["best_variant_gate"][
            "changed_peer_nonleader_signal_count"
        ],
    }
    print(json.dumps(_safe(summary), indent=2, sort_keys=True))
