"""exp-20260521-024: event benchmark-momentum context.

Alpha search. Tests one production-visible event context field on top of the
accepted exp-20260521-013 default-off event overlay adapter: whether selected
event rows whose ticker already has positive 20-day excess return versus SPY
deserve modest extra paper notional.

No JavaScript is used. Live/default orders remain disabled.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260521_010_event_governance_semantic_cell as exp010
import exp_20260521_013_event_non_narrow_state_context as exp013


EXPERIMENT_ID = "exp-20260521-024"
EXPERIMENT_SLUG = "event_benchmark_momentum_context"

REPO_ROOT = exp013.REPO_ROOT
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

BASELINE_VARIANT = "accepted_event_non_narrow_state_context_adapter"
TARGET_FIELD = "ret20_excess_spy"
TARGET_MIN_EXCESS = 0.0
MAX_DRAWDOWN_DRIFT = 0.0200
MAX_TARGET_POSITIVE_PNL_SHARE = 0.40

VARIANTS: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "description": "Accepted exp-20260521-013 event adapter.",
                "benchmark_momentum_scalar": 1.0,
            },
        ),
        (
            "benchmark_momentum_105",
            {
                "description": "1.05x paper notional for event rows with ret20_excess_spy > 0.",
                "benchmark_momentum_scalar": 1.05,
            },
        ),
        (
            "benchmark_momentum_110",
            {
                "description": "1.10x paper notional for event rows with ret20_excess_spy > 0.",
                "benchmark_momentum_scalar": 1.10,
            },
        ),
        (
            "benchmark_momentum_115",
            {
                "description": "1.15x paper notional for event rows with ret20_excess_spy > 0.",
                "benchmark_momentum_scalar": 1.15,
            },
        ),
        (
            "benchmark_momentum_120",
            {
                "description": "1.20x paper notional for event rows with ret20_excess_spy > 0.",
                "benchmark_momentum_scalar": 1.20,
            },
        ),
        (
            "benchmark_momentum_125",
            {
                "description": "1.25x paper notional for event rows with ret20_excess_spy > 0.",
                "benchmark_momentum_scalar": 1.25,
            },
        ),
    ]
)


def _parent():
    return exp013._parent()


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _configure_modules() -> None:
    exp013._configure_modules()


def _accepted_event_scalar_after_exp013(trade: dict[str, Any]) -> float:
    scalar = exp013._accepted_event_scalar_after_exp012(trade)
    if exp013._is_target_non_narrow_state(trade):
        scalar *= 1.15
    return scalar


def _ret20_excess_spy(trade: dict[str, Any]) -> float | None:
    features = trade.get("state_features") or {}
    value = features.get(TARGET_FIELD)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_target_benchmark_momentum(trade: dict[str, Any]) -> bool:
    value = _ret20_excess_spy(trade)
    return value is not None and value > TARGET_MIN_EXCESS


def _scaled_trade(
    trade: dict[str, Any],
    variant_name: str,
    variant: dict[str, Any],
) -> dict[str, Any]:
    parent = _parent()
    accepted_scalar = _accepted_event_scalar_after_exp013(trade)
    target = _is_target_benchmark_momentum(trade)
    momentum_scalar = (
        float(variant["benchmark_momentum_scalar"]) if target else 1.0
    )
    scalar = accepted_scalar * momentum_scalar
    base_notional = float(trade.get("notional") or parent.base.EVENT_NOTIONAL)
    base_shares = float(trade.get("shares") or 0.0)
    return {
        **trade,
        "variant": variant_name,
        "accepted_event_scalar_after_exp013": round(accepted_scalar, 4),
        "benchmark_momentum_target": target,
        "benchmark_momentum_scalar": round(momentum_scalar, 4),
        "ret20_excess_spy": _ret20_excess_spy(trade),
        "state_surface_scalar": round(scalar, 4),
        "base_notional": round(base_notional, 2),
        "notional": round(base_notional * scalar, 2),
        "shares": base_shares * scalar,
        "pnl": round(float(trade.get("pnl") or 0.0) * scalar, 2),
    }


def _selection_summary(rows_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    target_by_window: dict[str, Any] = OrderedDict()
    all_rows = [row for rows in rows_by_window.values() for row in rows]
    rows_with_field = [row for row in all_rows if row.get("ret20_excess_spy") is not None]
    targets = [row for row in rows_with_field if row.get("benchmark_momentum_target")]
    for label, rows in rows_by_window.items():
        window_targets = [
            row for row in rows if row.get("benchmark_momentum_target")
        ]
        target_by_window[label] = {
            "trade_count": len(window_targets),
            "wins": sum(
                1 for row in window_targets if float(row.get("pnl") or 0.0) > 0
            ),
            "total_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in window_targets), 2
            ),
            "tickers": sorted({str(row.get("ticker") or "") for row in window_targets}),
            "sources": sorted({str(row.get("source") or "") for row in window_targets}),
            "state_buckets": sorted(
                {str(row.get("state_bucket") or "") for row in window_targets}
            ),
            "state_surfaces": sorted(
                {str(row.get("state_surface") or "") for row in window_targets}
            ),
            "reaction_buckets": sorted(
                {str(row.get("reaction_bucket") or "") for row in window_targets}
            ),
        }
    return {
        "target_field": TARGET_FIELD,
        "target_rule": f"{TARGET_FIELD} > {TARGET_MIN_EXCESS}",
        "rows_with_field_count": len(rows_with_field),
        "target_trade_count": len(targets),
        "target_windows_present": sum(
            1 for row in target_by_window.values() if row["trade_count"] > 0
        ),
        "target_tickers": sorted({str(row.get("ticker") or "") for row in targets}),
        "target_sources": sorted({str(row.get("source") or "") for row in targets}),
        "target_state_buckets": sorted(
            {str(row.get("state_bucket") or "") for row in targets}
        ),
        "target_state_surfaces": sorted(
            {str(row.get("state_surface") or "") for row in targets}
        ),
        "target_reaction_buckets": sorted(
            {str(row.get("reaction_bucket") or "") for row in targets}
        ),
        "target_wins": sum(1 for row in targets if float(row.get("pnl") or 0.0) > 0),
        "target_win_rate": round(
            sum(1 for row in targets if float(row.get("pnl") or 0.0) > 0)
            / len(targets),
            4,
        )
        if targets
        else None,
        "target_scaled_total_pnl": round(
            sum(float(row.get("pnl") or 0.0) for row in targets), 2
        ),
        "target_by_window": target_by_window,
        "target_max_single_positive_pnl_share": exp010._max_positive_share(targets),
    }


def _gate_vs_baseline(
    baseline_metrics: dict[str, dict[str, Any]],
    after_metrics: dict[str, dict[str, Any]],
    selection: dict[str, Any],
) -> dict[str, Any]:
    gate = _parent().base._gate_summary(baseline_metrics, after_metrics)
    max_drawdown_drift = max(
        (
            float(after_metrics[label].get("max_drawdown_pct") or 0.0)
            - float(baseline_metrics[label].get("max_drawdown_pct") or 0.0)
        )
        for label in baseline_metrics
    )
    sample_ok = (
        (selection.get("target_trade_count") or 0) >= 15
        and (selection.get("target_windows_present") or 0) >= 3
        and len(selection.get("target_tickers") or []) >= 8
        and (selection.get("rows_with_field_count") or 0) >= 25
        and (
            selection.get("target_max_single_positive_pnl_share") is None
            or selection["target_max_single_positive_pnl_share"]
            <= MAX_TARGET_POSITIVE_PNL_SHARE
        )
    )
    risk_ok = max_drawdown_drift <= MAX_DRAWDOWN_DRIFT
    return {
        **gate,
        "sample_guard_passed": bool(sample_ok),
        "risk_guard_passed": bool(risk_ok),
        "max_drawdown_drift_limit": MAX_DRAWDOWN_DRIFT,
        "max_window_drawdown_drift": round(max_drawdown_drift, 6),
        "passed": bool(gate["passed"] and sample_ok and risk_ok),
        "sample_guard": {
            "min_target_trades": 15,
            "min_target_windows": 3,
            "min_target_tickers": 8,
            "min_rows_with_field": 25,
            "max_target_positive_pnl_share": MAX_TARGET_POSITIVE_PNL_SHARE,
            "actual_target_trades": selection.get("target_trade_count"),
            "actual_target_windows": selection.get("target_windows_present"),
            "actual_target_tickers": selection.get("target_tickers"),
            "actual_rows_with_field": selection.get("rows_with_field_count"),
            "actual_target_max_single_positive_pnl_share": selection.get(
                "target_max_single_positive_pnl_share"
            ),
        },
    }


def _choose_best(gates: dict[str, dict[str, Any]]) -> str:
    names = [name for name in VARIANTS if name != BASELINE_VARIANT]
    passed = [name for name in names if gates[name]["passed"]]
    candidates = passed if passed else names
    return max(
        candidates,
        key=lambda name: (
            gates[name]["delta"]["after_ev_sum"],
            gates[name]["delta"]["after_pnl_sum"],
            -abs(VARIANTS[name]["benchmark_momentum_scalar"] - 1.0),
        ),
    )


def _compact_metrics_by_window(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    fields = [
        "expected_value_score",
        "total_pnl",
        "sharpe_daily",
        "max_drawdown_pct",
        "trade_count",
        "win_rate",
        "survival_rate",
        "worst_trade_pct",
        "max_consecutive_losses",
        "tail_loss_share",
    ]
    return OrderedDict(
        (
            label,
            {field: metrics.get(field) for field in fields if field in metrics},
        )
        for label, metrics in rows.items()
    )


def _compact_variant_gates(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return OrderedDict(
        (
            name,
            {
                "passed": gate["passed"],
                "sample_guard_passed": gate["sample_guard_passed"],
                "risk_guard_passed": gate["risk_guard_passed"],
                "max_window_drawdown_drift": gate["max_window_drawdown_drift"],
                "aggregate_ev_delta": gate["delta"]["aggregate_ev_delta"],
                "aggregate_pnl_delta": gate["delta"]["aggregate_pnl_delta"],
                "windows_ev_improved": gate["delta"]["windows_ev_improved"],
                "windows_ev_regressed": gate["delta"]["windows_ev_regressed"],
                "after_ev_sum": gate["delta"]["after_ev_sum"],
                "baseline_ev_sum": gate["delta"]["baseline_ev_sum"],
            },
        )
        for name, gate in rows.items()
    )


def build_payload() -> dict[str, Any]:
    _configure_modules()
    parent = _parent()
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    operator_check = exp010._operator_position_field_check()
    raw_event_trades, source_coverage, prices = parent.base._load_event_trades()
    event_trades = parent.base._enrich_event_trades(raw_event_trades)
    core_results = {
        label: parent.base._load_core_result(window)
        for label, window in parent.base.WINDOWS.items()
    }
    core_metrics = OrderedDict(
        (label, parent.base._core_metrics(result))
        for label, result in core_results.items()
    )

    variant_metrics: dict[str, dict[str, dict[str, Any]]] = OrderedDict(
        (name, OrderedDict()) for name in VARIANTS
    )
    variant_events: dict[str, dict[str, list[dict[str, Any]]]] = OrderedDict(
        (name, OrderedDict()) for name in VARIANTS
    )
    for label, window in parent.base.WINDOWS.items():
        for name, variant in VARIANTS.items():
            scaled = [_scaled_trade(trade, name, variant) for trade in event_trades[label]]
            curve = parent.base._event_equity_curve(
                scaled,
                prices=prices,
                start=window["start"],
                end=window["end"],
            )
            variant_metrics[name][label] = parent.base._combined_metrics(
                core_results[label],
                curve,
                scaled,
            )
            variant_events[name][label] = scaled

    baseline_metrics = variant_metrics[BASELINE_VARIANT]
    selection_by_variant = OrderedDict(
        (name, _selection_summary(variant_events[name])) for name in VARIANTS
    )
    gates_vs_baseline = OrderedDict(
        (
            name,
            _gate_vs_baseline(
                baseline_metrics,
                variant_metrics[name],
                selection_by_variant[name],
            ),
        )
        for name in VARIANTS
        if name != BASELINE_VARIANT
    )
    best_variant = _choose_best(gates_vs_baseline)
    best_gate = gates_vs_baseline[best_variant]
    accepted = bool(best_gate["passed"])
    decision = (
        "accepted_default_off_event_benchmark_momentum_context"
        if accepted
        else "rejected_event_benchmark_momentum_context"
    )
    rejection_reason = None
    if not accepted:
        rejection_reason = (
            f"Best variant `{best_variant}` changed aggregate EV by "
            f"{best_gate['delta']['aggregate_ev_delta']} and PnL by "
            f"{best_gate['delta']['aggregate_pnl_delta']}, but Gate 4 failed: "
            f"EV improved/regressed windows "
            f"{best_gate['delta']['windows_ev_improved']}/"
            f"{best_gate['delta']['windows_ev_regressed']}, "
            f"sample_guard_passed={best_gate['sample_guard_passed']}, "
            f"risk_guard_passed={best_gate['risk_guard_passed']}."
        )

    compact_after_metrics = OrderedDict(
        (name, _compact_metrics_by_window(metrics))
        for name, metrics in variant_metrics.items()
    )
    variant_gates = _compact_variant_gates(gates_vs_baseline)
    compact_parameters = {
        "acceptance_baseline": BASELINE_VARIANT,
        "baseline_experiment": "exp-20260521-013",
        "target_field": TARGET_FIELD,
        "target_rule": f"{TARGET_FIELD} > {TARGET_MIN_EXCESS}",
        "selected_benchmark_momentum_scalar": VARIANTS[best_variant][
            "benchmark_momentum_scalar"
        ],
        "variant_scalars": {
            name: row["benchmark_momentum_scalar"]
            for name, row in VARIANTS.items()
        },
        "base_event_notional_usd": parent.base.EVENT_NOTIONAL,
        "hold_days": parent.base.HOLD_DAYS,
        "round_trip_cost_pct": parent.base.ROUND_TRIP_COST_PCT,
        "sample_guard": {
            "min_target_trades": 15,
            "min_target_windows": 3,
            "min_target_tickers": 8,
            "min_rows_with_field": 25,
            "max_target_positive_pnl_share": MAX_TARGET_POSITIVE_PNL_SHARE,
        },
        "risk_guard": {"max_window_drawdown_drift": MAX_DRAWDOWN_DRIFT},
        "locked_variables": [
            "core universe",
            "core signal generation",
            "core candidate ranking",
            "core position sizing",
            "core exits",
            "event source definitions",
            "event source capacity",
            "event source thresholds",
            "event holding period",
            "front-rank rotation event scalar",
            "broad-breadth event scalar",
            "governance-source quality scalar",
            "negative-reaction context scalar",
            "positive-state context scalar",
            "non-narrow state-bucket context scalar",
            "LLM prompt and replay",
            "news veto",
            "production orders",
        ],
        "anti_js": "No JavaScript was used.",
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "event_benchmark_momentum_allocation_adapter",
        "mechanism_family": "external_event_satellite_overlay_allocation",
        "trial_family": "event_benchmark_momentum_context",
        "trial_variant_id": "ret20_excess_spy_positive_notional_scalar",
        "changed_variable": "event_benchmark_momentum_scalar",
        "prior_trial_count": 3,
        "nearby_prior_experiments": [
            "exp-20260517-016",
            "exp-20260519-006",
            "exp-20260521-013",
            "exp-20260521-019",
            "exp-20260521-022",
        ],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "new_event_state_feature_context_field",
        "hypothesis": (
            "Inside the accepted default-off event overlay, events whose ticker "
            "already has positive 20-day excess return versus SPY should have "
            "better replacement value because the event is aligned with an "
            "existing medium-term trend. A single paper-notional scalar tests "
            "that production-visible benchmark-momentum context field."
        ),
        "alpha_hypothesis": {
            "category": "capital allocation / event context scoring",
            "entry_exit_ranking_or_allocation": "capital allocation",
            "playbook_alignment": (
                "Uses the playbook preference for event-family x market-state "
                "decomposition and production-visible context fields. It avoids "
                "LLM soft-ranking, source-capacity retries, SEC sparse text "
                "slices, broad-market threshold retunes, and state-surface sleeve "
                "scalar mining."
            ),
        },
        "single_causal_variable": (
            "paper-notional scalar for fixed event overlay rows whose "
            "state_features.ret20_excess_spy is positive; event definitions, "
            "accepted source/reaction/state context scalars, hold period, source "
            "capacity, and core strategy stay fixed"
        ),
        "parameters": compact_parameters,
        "date_range": {
            label: f"{window['start']} -> {window['end']}"
            for label, window in parent.base.WINDOWS.items()
        },
        "market_regime_summary": {
            label: window["state_note"] for label, window in parent.base.WINDOWS.items()
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "Event rows with positive ticker-minus-SPY 20-day momentum may "
                "have better replacement value; this is event context scoring "
                "plus capital allocation."
            ),
            "2_history_check": (
                "State-surface ret20 participation was accepted in a different "
                "sleeve; event attention persistence and mild positive reaction "
                "were rejected; event non-narrow state remains the current "
                "accepted event baseline. This run tests the untried event-row "
                "benchmark-momentum context field."
            ),
            "3_single_causal_variable": (
                "Only the paper-notional scalar for fixed benchmark-momentum "
                "event rows changes."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; compare against the "
                "accepted exp-20260521-013 event adapter baseline, require "
                "aggregate EV/PnL improvement, zero EV-regressed windows, "
                "sample guard pass, risk guard pass, and no production/backtest "
                "divergence."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260521_024_event_benchmark_momentum_context.py"
            ),
        },
        "historical_experiment_check": {
            "exp-20260517-016": "Accepted state-surface ret20_excess_spy >= 0 gate; this does not change that sleeve.",
            "exp-20260521-013": "Accepted event non-narrow state-bucket context; current event baseline.",
            "exp-20260521-019": "Rejected event attention-persistence context.",
            "exp-20260521-022": "Rejected mild positive first-reaction context.",
            "exp-20260521-023": "Rejected core ample-slot rank1 scalar extension; avoid core slot retune.",
        },
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical fixed-snapshot three-window replay "
                "plus default-off event paper overlay accounting"
            ),
            "windows": exp010._compact_windows(parent.base.WINDOWS),
            "config": {
                "REGIME_AWARE_EXIT": True,
                "REPLAY_PARTIAL_REDUCES": True,
                "event_overlay": "default_off_paper_replay",
            },
        },
        "gate1": {
            "baseline_name": BASELINE_VARIANT,
            "baseline_artifact": "data/experiments/exp-20260521-013/event_non_narrow_state_context.json",
        },
        "gate2": {
            "required_fields": [
                "event source",
                "ticker",
                "entry_date",
                "exit_date",
                "pnl",
                "state_features.ret20_excess_spy",
                "reaction_bucket",
                "state_bucket",
            ],
            "operator_position_field_check": operator_check,
            "selection": selection_by_variant[BASELINE_VARIANT],
            "passed": bool(
                operator_check["passed"]
                and selection_by_variant[BASELINE_VARIANT]["rows_with_field_count"] >= 25
            ),
        },
        "gate3": {
            "new_filter_added": False,
            "candidate_pool_changed": False,
            "survival_impact": (
                "not applicable to default-off event paper overlay; core signals "
                "and survival are unchanged"
            ),
            "passed": True,
        },
        "gate4": {
            **best_gate,
            "basis": (
                "Three canonical docs/backtesting.md windows, primary comparison "
                "against the accepted exp-20260521-013 event adapter baseline."
            ),
        },
        "before_metrics": {
            BASELINE_VARIANT: _compact_metrics_by_window(baseline_metrics),
            "core": _compact_metrics_by_window(core_metrics),
        },
        "after_metrics": {best_variant: compact_after_metrics[best_variant]},
        "delta_metrics": {
            "variant_vs_accepted_event_non_narrow_state_context_adapter": variant_gates
        },
        "best_variant": best_variant,
        "expected_value_score_delta": best_gate["delta"]["aggregate_ev_delta"],
        "total_pnl_delta": best_gate["delta"]["aggregate_pnl_delta"],
        "selection": selection_by_variant[best_variant],
        "source_coverage": {
            "sec_negative_price_ready_candidates": source_coverage.get(
                "sec_negative_price_ready_candidates"
            ),
            "form4_price_ready_candidates": source_coverage.get(
                "form4_price_ready_candidates"
            ),
            "source_skipped_counts": source_coverage.get("source_skipped_counts"),
        },
        "production_impact": {
            "shared_policy_changed": accepted,
            "backtester_adapter_changed": False,
            "run_adapter_changed": accepted,
            "replay_only": False,
            "parity_test_added": accepted,
            "production_signal_path_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "live_orders_enabled": False,
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM soft-ranking remains attribution/sample-limited; this uses "
                "deterministic state_features only."
            ),
        },
        "decision_rationale": (
            "Accepted as a shared default-off paper adapter change."
            if accepted
            else "Rejected: benchmark-momentum context scalar did not clear Gate 4."
        ),
        "rejection_reason": rejection_reason,
        "next_action": (
            "If accepted, promote only through shared event_sleeve_bundle metadata "
            "and parity tests; do not retry nearby ret20 thresholds or broader "
            "state-feature scalars without forward rows."
        ),
        "why_not_other_attractive_points": (
            "Skipped source-collision because there were zero same ticker/date "
            "collisions; skipped LLM soft-ranking due attribution limits; skipped "
            "SEC no-guidance/special-call/mild-reaction/attention-persistence "
            "nearby fields due recent rejection or sample limits; skipped "
            "state-surface and broad-market retunes due anti-repeat gates."
        ),
        "risk_of_change": (
            "Default-off paper attribution only. No live orders, ranking, core "
            "sizing, exits, source definitions, or source capacity changed."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            "quant/event_sleeve_bundle.py",
            "quant/test_event_sleeve_bundle.py",
            "docs/production_backtest_parity.md",
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    gate = payload["gate4"]
    baseline = payload["before_metrics"][BASELINE_VARIANT]
    after = payload["after_metrics"][best]
    lines = [
        f"# {EXPERIMENT_ID} Event Benchmark Momentum Context",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        (
            "Alpha search. Tests whether selected event rows with positive "
            "20-day excess return versus SPY deserve a paper-notional scalar "
            "on top of the accepted event non-narrow state context adapter."
        ),
        "",
        "## Gate 4 Result",
        "",
        "| Window | Baseline EV | After EV | Delta EV | Baseline PnL | After PnL | Delta PnL |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label in _parent().base.WINDOWS:
        delta = gate["delta"]["by_window"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} |".format(
                label=label,
                bev=baseline[label]["expected_value_score"],
                aev=after[label]["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=baseline[label]["total_pnl"],
                apnl=after[label]["total_pnl"],
                dpnl=delta["total_pnl"],
            )
        )
    lines.extend(
        [
            "",
            "## Sweep",
            "",
            "| Variant | Passed | Sample | Risk | dEV | dPnL | Improved | Regressed | Max DD drift |",
            "|---|:---:|:---:|:---:|---:|---:|---:|---:|---:|",
        ]
    )
    for name, row in payload["delta_metrics"][
        "variant_vs_accepted_event_non_narrow_state_context_adapter"
    ].items():
        lines.append(
            "| {name} | {passed} | {sample} | {risk} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {dd:.4f} |".format(
                name=name,
                passed="yes" if row["passed"] else "no",
                sample="yes" if row["sample_guard_passed"] else "no",
                risk="yes" if row["risk_guard_passed"] else "no",
                dev=row["aggregate_ev_delta"],
                dpnl=row["aggregate_pnl_delta"],
                improved=row["windows_ev_improved"],
                regressed=row["windows_ev_regressed"],
                dd=row["max_window_drawdown_drift"],
            )
        )
    lines.extend(
        [
            "",
            "## Selection",
            "",
            "```json",
            json.dumps(payload["selection"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            (
                "Shared default-off event adapter/reporting changed only if the "
                "Gate 4 decision is accepted. Core behavior, source capacity, "
                "and live/default order paths are unchanged."
            ),
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def persist(payload: dict[str, Any]) -> None:
    parent = _parent()
    parent._write_json(OUT_JSON, payload)
    parent._write_json(LOG_JSON, payload)
    parent._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Event benchmark momentum context",
            "status": payload["status"],
            "decision": payload["decision"],
            "best_variant": payload["best_variant"],
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "total_pnl_delta": payload["total_pnl_delta"],
            "next_action": payload["next_action"],
        },
    )
    parent._write_text(ARTIFACT_MD, _artifact_markdown(payload))

    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if EXPERIMENT_LOG.exists():
        lines = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        lines = [
            line
            for line in lines
            if f'"experiment_id":"{EXPERIMENT_ID}"' not in line
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
        ]
    lines.append(json.dumps(parent._safe(payload), sort_keys=True))
    EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            _parent()._safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "best_variant": payload["best_variant"],
                    "ev_delta_vs_baseline": payload["expected_value_score_delta"],
                    "pnl_delta_vs_baseline": payload["total_pnl_delta"],
                    "windows_ev_improved": payload["gate4"]["delta"][
                        "windows_ev_improved"
                    ],
                    "windows_ev_regressed": payload["gate4"]["delta"][
                        "windows_ev_regressed"
                    ],
                    "sample_guard_passed": payload["gate4"]["sample_guard_passed"],
                    "risk_guard_passed": payload["gate4"]["risk_guard_passed"],
                    "max_window_drawdown_drift": payload["gate4"][
                        "max_window_drawdown_drift"
                    ],
                    "out_json": str(OUT_JSON),
                    "anti_js": "No JavaScript was used.",
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
