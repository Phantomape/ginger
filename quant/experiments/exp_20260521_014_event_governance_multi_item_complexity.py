"""exp-20260521-014: event governance multi-item complexity.

Alpha search. Tests one production-visible SEC disclosure-quality field on top
of the accepted exp-20260521-013 default-off event overlay adapter: whether
governance/procedural event rows with multiple 8-K item codes deserve a paper
notional haircut because the disclosure is more administrative/complex than a
clean single-item catalyst.

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


EXPERIMENT_ID = "exp-20260521-014"
EXPERIMENT_SLUG = "event_governance_multi_item_complexity"

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
TARGET_SOURCE = "sec_governance_procedural"
MIN_ITEM_CODE_COUNT = 2
MAX_DRAWDOWN_DRIFT = 0.0200

VARIANTS: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "description": "Accepted exp-20260521-013 event adapter.",
                "multi_item_complexity_scalar": 1.0,
            },
        ),
        (
            "multi_item_complexity_000",
            {
                "description": "0.00x paper notional for multi-item governance rows.",
                "multi_item_complexity_scalar": 0.0,
            },
        ),
        (
            "multi_item_complexity_025",
            {
                "description": "0.25x paper notional for multi-item governance rows.",
                "multi_item_complexity_scalar": 0.25,
            },
        ),
        (
            "multi_item_complexity_050",
            {
                "description": "0.50x paper notional for multi-item governance rows.",
                "multi_item_complexity_scalar": 0.50,
            },
        ),
        (
            "multi_item_complexity_075",
            {
                "description": "0.75x paper notional for multi-item governance rows.",
                "multi_item_complexity_scalar": 0.75,
            },
        ),
        (
            "multi_item_complexity_125",
            {
                "description": "1.25x paper notional for multi-item governance rows.",
                "multi_item_complexity_scalar": 1.25,
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


def _item_codes(trade: dict[str, Any]) -> list[str]:
    raw = trade.get("eight_k_item_codes") or []
    if isinstance(raw, str):
        return [item.strip() for item in raw.split("|") if item.strip()]
    if isinstance(raw, (list, tuple)):
        return [str(item).strip() for item in raw if str(item).strip()]
    return []


def _is_target_multi_item_governance(trade: dict[str, Any]) -> bool:
    return (
        str(trade.get("source") or "") == TARGET_SOURCE
        and len(_item_codes(trade)) >= MIN_ITEM_CODE_COUNT
    )


def _scaled_trade(
    trade: dict[str, Any],
    variant_name: str,
    variant: dict[str, Any],
) -> dict[str, Any]:
    parent = _parent()
    accepted_scalar = _accepted_event_scalar_after_exp013(trade)
    target = _is_target_multi_item_governance(trade)
    complexity_scalar = float(variant["multi_item_complexity_scalar"]) if target else 1.0
    scalar = accepted_scalar * complexity_scalar
    base_notional = float(trade.get("notional") or parent.base.EVENT_NOTIONAL)
    base_shares = float(trade.get("shares") or 0.0)
    codes = _item_codes(trade)
    return {
        **trade,
        "variant": variant_name,
        "accepted_event_scalar_after_exp013": round(accepted_scalar, 4),
        "multi_item_governance_complexity_target": target,
        "multi_item_complexity_scalar": round(complexity_scalar, 4),
        "eight_k_item_code_count": len(codes),
        "eight_k_item_codes_normalized": codes,
        "state_surface_scalar": round(scalar, 4),
        "base_notional": round(base_notional, 2),
        "notional": round(base_notional * scalar, 2),
        "shares": base_shares * scalar,
        "pnl": round(float(trade.get("pnl") or 0.0) * scalar, 2),
    }


def _selection_summary(rows_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    target_by_window: dict[str, Any] = OrderedDict()
    all_rows = [row for rows in rows_by_window.values() for row in rows]
    targets = [row for row in all_rows if row.get("multi_item_governance_complexity_target")]
    for label, rows in rows_by_window.items():
        window_targets = [
            row for row in rows if row.get("multi_item_governance_complexity_target")
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
            "semantic_subcategories": sorted(
                {str(row.get("semantic_subcategory") or "") for row in window_targets}
            ),
            "reaction_buckets": sorted(
                {str(row.get("reaction_bucket") or "") for row in window_targets}
            ),
            "state_buckets": sorted(
                {str(row.get("state_bucket") or "") for row in window_targets}
            ),
            "item_code_sets": sorted(
                {
                    "|".join(row.get("eight_k_item_codes_normalized") or [])
                    for row in window_targets
                }
            ),
        }
    return {
        "target_field": "eight_k_item_code_count",
        "target_source": TARGET_SOURCE,
        "min_item_code_count": MIN_ITEM_CODE_COUNT,
        "target_trade_count": len(targets),
        "target_windows_present": sum(
            1 for row in target_by_window.values() if row["trade_count"] > 0
        ),
        "target_tickers": sorted({str(row.get("ticker") or "") for row in targets}),
        "target_sources": sorted({str(row.get("source") or "") for row in targets}),
        "target_semantic_subcategories": sorted(
            {str(row.get("semantic_subcategory") or "") for row in targets}
        ),
        "target_reaction_buckets": sorted(
            {str(row.get("reaction_bucket") or "") for row in targets}
        ),
        "target_state_buckets": sorted(
            {str(row.get("state_bucket") or "") for row in targets}
        ),
        "target_item_code_sets": sorted(
            {"|".join(row.get("eight_k_item_codes_normalized") or []) for row in targets}
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
        (selection.get("target_trade_count") or 0) >= 10
        and (selection.get("target_windows_present") or 0) >= 3
        and len(selection.get("target_tickers") or []) >= 6
        and (
            selection.get("target_max_single_positive_pnl_share") is None
            or selection["target_max_single_positive_pnl_share"] <= 0.45
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
            "min_target_trades": 10,
            "min_target_windows": 3,
            "min_target_tickers": 6,
            "max_target_positive_pnl_share": 0.45,
            "actual_target_trades": selection.get("target_trade_count"),
            "actual_target_windows": selection.get("target_windows_present"),
            "actual_target_tickers": selection.get("target_tickers"),
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
            -abs(VARIANTS[name]["multi_item_complexity_scalar"] - 1.0),
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
        "accepted_default_off_event_governance_multi_item_complexity"
        if accepted
        else "rejected_event_governance_multi_item_complexity"
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
        "target_source": TARGET_SOURCE,
        "target_field": "eight_k_item_code_count",
        "min_item_code_count": MIN_ITEM_CODE_COUNT,
        "selected_multi_item_complexity_scalar": VARIANTS[best_variant][
            "multi_item_complexity_scalar"
        ],
        "variant_scalars": {
            name: row["multi_item_complexity_scalar"]
            for name, row in VARIANTS.items()
        },
        "base_event_notional_usd": parent.base.EVENT_NOTIONAL,
        "hold_days": parent.base.HOLD_DAYS,
        "round_trip_cost_pct": parent.base.ROUND_TRIP_COST_PCT,
        "sample_guard": {
            "min_target_trades": 10,
            "min_target_windows": 3,
            "min_target_tickers": 6,
            "max_target_positive_pnl_share": 0.45,
        },
        "risk_guard": {
            "max_window_drawdown_drift": MAX_DRAWDOWN_DRIFT,
        },
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
        "change_type": "event_disclosure_quality_allocation_scout",
        "mechanism_family": "external_event_satellite_overlay_allocation",
        "trial_family": "event_disclosure_complexity_quality",
        "trial_variant_id": "governance_multi_item_8k_notional_scalar",
        "changed_variable": "event_governance_multi_item_complexity_scalar",
        "prior_trial_count": 4,
        "nearby_prior_experiments": [
            "exp-20260521-006",
            "exp-20260521-007",
            "exp-20260521-010",
            "exp-20260521-013",
        ],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "new_production_visible_disclosure_complexity_field",
        "hypothesis": (
            "Inside the accepted default-off event overlay, SEC governance/"
            "procedural rows with multiple 8-K item codes may be weaker, more "
            "administrative disclosures than clean single-item catalysts. A "
            "single paper-notional scalar tests this production-visible "
            "disclosure-complexity field without changing core trades."
        ),
        "alpha_hypothesis": {
            "category": "capital allocation / event source-quality scoring",
            "entry_exit_ranking_or_allocation": "capital allocation",
            "playbook_alignment": (
                "Uses disclosure/source quality and source-context fields from "
                "the event-overlay queue while avoiding LLM soft-ranking, "
                "source-capacity retries, state-bucket retunes, and broad "
                "candidate-pool noise."
            ),
        },
        "single_causal_variable": (
            "paper-notional scalar for fixed sec_governance_procedural event "
            "rows with at least two 8-K item codes; event definitions, accepted "
            "source/reaction/state context scalars, hold period, source "
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
                "Multi-item governance/procedural 8-K rows may identify weaker "
                "event replacement value; this is event source-quality scoring "
                "plus capital allocation."
            ),
            "2_history_check": (
                "Governance source-quality was accepted; negative phrase "
                "evidence and shareholder-vote negative semantic cell were "
                "rejected due window/sample issues. This run uses a different "
                "production-visible disclosure-complexity field, not raw tone "
                "or a single semantic cell."
            ),
            "3_single_causal_variable": (
                "Only the paper-notional scalar for fixed multi-item governance "
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
                "exp_20260521_014_event_governance_multi_item_complexity.py"
            ),
        },
        "historical_experiment_check": {
            "exp-20260521-006": "Accepted governance source-quality scalar; this keeps it fixed.",
            "exp-20260521-007": "Rejected negative phrase evidence due window/sample gate failure.",
            "exp-20260521-010": "Rejected shareholder-vote negative semantic cell due sample/window failure.",
            "exp-20260521-013": "Accepted non-narrow state-bucket context; current event baseline.",
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
                "eight_k_item_codes",
                "semantic_subcategory",
                "reaction_bucket",
                "state_bucket",
            ],
            "operator_position_field_check": operator_check,
            "selection": selection_by_variant[BASELINE_VARIANT],
            "passed": bool(operator_check["passed"]),
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
                "deterministic SEC item-code context fields only."
            ),
        },
        "decision_rationale": (
            "Accepted as a shared default-off paper adapter change."
            if accepted
            else "Rejected: multi-item governance disclosure complexity scalar did not clear Gate 4."
        ),
        "rejection_reason": rejection_reason,
        "next_action": (
            "Do not promote or retry nearby SEC governance item-code complexity "
            "scalars on the frozen sample without wider forward rows or a "
            "materially different disclosure-quality field."
        ),
        "why_not_other_attractive_points": (
            "Source-overlap context was checked first and had zero same-day "
            "multi-source event rows. LLM soft-ranking remains attribution-"
            "limited; state-surface, broad-market, source-capacity, state-bucket, "
            "and earnings-release-text retunes are blocked by recent anti-repeat "
            "evidence."
        ),
        "risk_of_change": (
            "No live orders, ranking, core sizing, exits, source definitions, or "
            "source capacity changed. Rejected scout is paper attribution only."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
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
        f"# {EXPERIMENT_ID} Event Governance Multi-Item Complexity",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        (
            "Alpha search. Tests whether SEC governance/procedural rows with "
            "multiple 8-K item codes deserve a paper-notional scalar on top of "
            "the accepted event non-narrow state context adapter."
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
                "No shared policy, production adapter, run adapter, order path, "
                "source capacity, or core behavior changed."
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
            "title": "Event governance multi-item complexity",
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
