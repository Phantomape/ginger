"""exp-20260522-007: SEC governance item 5.03 event haircut.

Alpha search. Tests one production-visible SEC governance disclosure-quality
field on top of the accepted exp-20260521-013 default-off event overlay:
whether governance/procedural event rows that include 8-K item 5.03 deserve
lower paper notional.

No JavaScript is used. Live/default orders remain disabled.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260522_005_event_crowded_leadership_context as base


EXPERIMENT_ID = "exp-20260522-007"
EXPERIMENT_SLUG = "event_governance_503_haircut"

REPO_ROOT = base.REPO_ROOT
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

BASELINE_VARIANT = "accepted_event_non_narrow_state_context_adapter"
TARGET_SOURCE = "sec_governance_procedural"
TARGET_ITEM_CODE = "5.03"
MAX_DRAWDOWN_DRIFT = 0.0100

VARIANTS: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "description": "Accepted exp-20260521-013 event adapter.",
                "governance_503_scalar": 1.00,
            },
        ),
        (
            "governance_503_075",
            {
                "description": "0.75x paper notional for governance rows with item 5.03.",
                "governance_503_scalar": 0.75,
            },
        ),
        (
            "governance_503_050",
            {
                "description": "0.50x paper notional for governance rows with item 5.03.",
                "governance_503_scalar": 0.50,
            },
        ),
        (
            "governance_503_025",
            {
                "description": "0.25x paper notional for governance rows with item 5.03.",
                "governance_503_scalar": 0.25,
            },
        ),
        (
            "governance_503_000",
            {
                "description": "0.00x paper notional for governance rows with item 5.03.",
                "governance_503_scalar": 0.00,
            },
        ),
    ]
)


def _parent():
    return base._parent()


def _configure_modules() -> None:
    base._configure_modules()


def _item_codes(trade: dict[str, Any]) -> set[str]:
    return {str(item) for item in (trade.get("eight_k_item_codes") or [])}


def _is_target_governance_503(trade: dict[str, Any]) -> bool:
    return (
        str(trade.get("source") or "") == TARGET_SOURCE
        and TARGET_ITEM_CODE in _item_codes(trade)
    )


def _scaled_trade(
    trade: dict[str, Any],
    variant_name: str,
    variant: dict[str, Any],
) -> dict[str, Any]:
    parent = _parent()
    accepted_scalar = base._accepted_event_scalar_after_exp013(trade)
    target = _is_target_governance_503(trade)
    haircut_scalar = float(variant["governance_503_scalar"]) if target else 1.0
    scalar = accepted_scalar * haircut_scalar
    base_notional = float(trade.get("notional") or parent.base.EVENT_NOTIONAL)
    base_shares = float(trade.get("shares") or 0.0)
    return {
        **trade,
        "variant": variant_name,
        "accepted_event_scalar_after_exp013": round(accepted_scalar, 4),
        "governance_503_target": target,
        "governance_503_scalar": round(haircut_scalar, 4),
        "event_scalar": round(scalar, 4),
        "base_notional": round(base_notional, 2),
        "notional": round(base_notional * scalar, 2),
        "shares": base_shares * scalar,
        "pnl": round(float(trade.get("pnl") or 0.0) * scalar, 2),
    }


def _max_loss_share(rows: list[dict[str, Any]]) -> float | None:
    losses = [
        abs(float(row.get("pnl") or 0.0))
        for row in rows
        if float(row.get("pnl") or 0.0) < 0.0
    ]
    total = sum(losses)
    if total <= 0.0:
        return None
    return round(max(losses) / total, 4)


def _selection_summary(rows_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    target_by_window: dict[str, Any] = OrderedDict()
    all_rows = [row for rows in rows_by_window.values() for row in rows]
    targets = [row for row in all_rows if row.get("governance_503_target")]
    for label, rows in rows_by_window.items():
        window_targets = [row for row in rows if row.get("governance_503_target")]
        target_by_window[label] = {
            "trade_count": len(window_targets),
            "wins": sum(1 for row in window_targets if float(row.get("pnl") or 0.0) > 0),
            "losses": sum(
                1 for row in window_targets if float(row.get("pnl") or 0.0) < 0
            ),
            "total_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in window_targets),
                2,
            ),
            "tickers": sorted({str(row.get("ticker") or "") for row in window_targets}),
            "item_code_sets": sorted(
                {
                    "|".join(str(item) for item in (row.get("eight_k_item_codes") or []))
                    for row in window_targets
                }
            ),
            "semantic_subcategories": sorted(
                {str(row.get("semantic_subcategory") or "") for row in window_targets}
            ),
            "reaction_buckets": sorted(
                {str(row.get("reaction_bucket") or "") for row in window_targets}
            ),
            "state_buckets": sorted(
                {str(row.get("state_bucket") or "") for row in window_targets}
            ),
            "state_surfaces": sorted(
                {str(row.get("state_surface") or "") for row in window_targets}
            ),
        }
    wins = sum(1 for row in targets if float(row.get("pnl") or 0.0) > 0)
    losses = sum(1 for row in targets if float(row.get("pnl") or 0.0) < 0)
    return {
        "target_rule": f"source == {TARGET_SOURCE} AND item {TARGET_ITEM_CODE} present",
        "target_field": "governance_item_5_03_presence",
        "target_trade_count": len(targets),
        "target_windows_present": sum(
            1 for row in target_by_window.values() if row["trade_count"] > 0
        ),
        "target_tickers": sorted({str(row.get("ticker") or "") for row in targets}),
        "target_sources": sorted({str(row.get("source") or "") for row in targets}),
        "target_item_code_sets": sorted(
            {
                "|".join(str(item) for item in (row.get("eight_k_item_codes") or []))
                for row in targets
            }
        ),
        "target_semantic_subcategories": sorted(
            {str(row.get("semantic_subcategory") or "") for row in targets}
        ),
        "target_reaction_buckets": sorted(
            {str(row.get("reaction_bucket") or "") for row in targets}
        ),
        "target_state_buckets": sorted(
            {str(row.get("state_bucket") or "") for row in targets}
        ),
        "target_state_surfaces": sorted(
            {str(row.get("state_surface") or "") for row in targets}
        ),
        "target_wins": wins,
        "target_losses": losses,
        "target_win_rate": round(wins / len(targets), 4) if targets else None,
        "target_scaled_total_pnl": round(
            sum(float(row.get("pnl") or 0.0) for row in targets),
            2,
        ),
        "target_max_single_loss_pnl_share": _max_loss_share(targets),
        "target_by_window": target_by_window,
    }


def _gate_vs_baseline(
    baseline_metrics: dict[str, dict[str, Any]],
    after_metrics: dict[str, dict[str, Any]],
    baseline_selection: dict[str, Any],
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
        (baseline_selection.get("target_trade_count") or 0) >= 5
        and (baseline_selection.get("target_windows_present") or 0) >= 3
        and len(baseline_selection.get("target_tickers") or []) >= 4
        and (baseline_selection.get("target_losses") or 0) >= 3
        and (baseline_selection.get("target_scaled_total_pnl") or 0.0) < 0.0
        and (
            baseline_selection.get("target_max_single_loss_pnl_share") is None
            or baseline_selection["target_max_single_loss_pnl_share"] <= 0.75
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
            "min_target_trades": 5,
            "min_target_windows": 3,
            "min_target_tickers": 4,
            "min_target_losses": 3,
            "requires_negative_baseline_target_pnl": True,
            "max_target_single_loss_pnl_share": 0.75,
            "actual_target_trades": baseline_selection.get("target_trade_count"),
            "actual_target_windows": baseline_selection.get("target_windows_present"),
            "actual_target_tickers": baseline_selection.get("target_tickers"),
            "actual_target_losses": baseline_selection.get("target_losses"),
            "actual_target_scaled_total_pnl": baseline_selection.get(
                "target_scaled_total_pnl"
            ),
            "actual_target_max_single_loss_pnl_share": baseline_selection.get(
                "target_max_single_loss_pnl_share"
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
            -abs(VARIANTS[name]["governance_503_scalar"] - 1.0),
        ),
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
    operator_check = base.exp010._operator_position_field_check()
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
    baseline_selection = _selection_summary(variant_events[BASELINE_VARIANT])
    gates_vs_baseline = OrderedDict(
        (
            name,
            _gate_vs_baseline(
                baseline_metrics,
                variant_metrics[name],
                baseline_selection,
            ),
        )
        for name in VARIANTS
        if name != BASELINE_VARIANT
    )
    best_variant = _choose_best(gates_vs_baseline)
    best_gate = gates_vs_baseline[best_variant]
    accepted = bool(best_gate["passed"])
    decision = (
        "accepted_default_off_event_governance_503_haircut"
        if accepted
        else "rejected_event_governance_503_haircut"
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
        (name, base._compact_metrics_by_window(metrics))
        for name, metrics in variant_metrics.items()
    )
    variant_gates = _compact_variant_gates(gates_vs_baseline)
    compact_parameters = {
        "acceptance_baseline": BASELINE_VARIANT,
        "baseline_experiment": "exp-20260521-013",
        "target_rule": baseline_selection["target_rule"],
        "selected_governance_503_scalar": VARIANTS[best_variant][
            "governance_503_scalar"
        ],
        "variant_scalars": {
            name: row["governance_503_scalar"] for name, row in VARIANTS.items()
        },
        "base_event_notional_usd": parent.base.EVENT_NOTIONAL,
        "hold_days": parent.base.HOLD_DAYS,
        "round_trip_cost_pct": parent.base.ROUND_TRIP_COST_PCT,
        "sample_guard": best_gate["sample_guard"],
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
            "non-narrow state context scalar",
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
        "change_type": "event_disclosure_quality_allocation_adapter",
        "mechanism_family": "external_event_satellite_overlay_allocation",
        "trial_family": "event_governance_disclosure_quality",
        "trial_variant_id": "governance_item_5_03_notional_haircut",
        "changed_variable": "event_governance_item_5_03_disclosure_quality_scalar",
        "prior_trial_count": 10,
        "nearby_prior_experiments": [
            "exp-20260521-010",
            "exp-20260521-014",
            "exp-20260521-015",
            "exp-20260522-005",
            "exp-20260522-006",
        ],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "specific_item_code_presence_5_03_disclosure_quality_field",
        "hypothesis": (
            "Inside the accepted default-off event overlay, SEC governance/"
            "procedural rows containing item 5.03 are more likely to represent "
            "charter, securities, or vote mechanics than fresh operating alpha. "
            "A single paper-notional haircut can reduce this low-replacement-value "
            "cohort without changing core trades."
        ),
        "alpha_hypothesis": {
            "category": "capital allocation / event semantic field",
            "entry_exit_ranking_or_allocation": "capital allocation",
            "playbook_alignment": (
                "Follows the playbook's SEC/event disclosure-quality and "
                "concentration governance lane. It uses one production-visible "
                "item-code field instead of LLM soft-ranking, broad-market replay "
                "mining, or state-surface notional retunes."
            ),
        },
        "single_causal_variable": (
            "paper-notional scalar for fixed accepted event rows where source is "
            "sec_governance_procedural and item code 5.03 is present; all accepted "
            "event scalars and core strategy behavior stay fixed"
        ),
        "parameters": compact_parameters,
        "date_range": {
            label: f"{window['start']} -> {window['end']}"
            for label, window in parent.base.WINDOWS.items()
        },
        "market_regime_summary": {
            "late_strong": "slow-melt bull / accepted-stack dominant tape",
            "mid_weak": "rotation-heavy bull where strategy makes money but lags indexes",
            "old_thin": "mixed-to-weak older tape with lower win rate",
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "Capital allocation / event semantic field: haircut SEC governance "
                "paper rows only when item 5.03 is present."
            ),
            "2_history_check": (
                "Prior governance semantic-cell, multi-item complexity, and no-5.03 "
                "scouts were mixed or rejected. This tests the complement cohort "
                "as a risk-reducing disclosure-quality allocation variable."
            ),
            "3_single_causal_variable": (
                "Only the paper-notional scalar for the fixed 5.03 governance "
                "cohort changes."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; compare against the "
                "accepted exp-20260521-013 event adapter baseline, require "
                "aggregate EV/PnL improvement, no EV-regressed window, sample "
                "guard pass, risk guard pass, and no production/backtest divergence."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260522_007_event_governance_503_haircut.py"
            ),
        },
        "historical_experiment_check": {
            "exp-20260521-014": (
                "Rejected multi-item complexity scalar; this run does not use "
                "item-count, but remains high multiple-testing risk."
            ),
            "exp-20260522-005": (
                "Rejected crowded leadership haircut despite aggregate uplift "
                "because late_strong EV regressed."
            ),
            "exp-20260522-006": (
                "Rejected no-5.03 boost despite high aggregate uplift because "
                "late_strong EV regressed and drawdown drift failed the risk guard."
            ),
        },
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical fixed-snapshot three-window replay "
                "plus default-off event paper overlay accounting"
            ),
            "windows": base.exp010._compact_windows(parent.base.WINDOWS),
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
            ],
            "operator_position_field_check": operator_check,
            "selection": baseline_selection,
            "passed": bool(
                operator_check["passed"]
                and baseline_selection["target_trade_count"] >= 5
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
            BASELINE_VARIANT: base._compact_metrics_by_window(baseline_metrics),
            "core": base._compact_metrics_by_window(core_metrics),
        },
        "after_metrics": {best_variant: compact_after_metrics[best_variant]},
        "delta_metrics": {
            "variant_vs_accepted_event_non_narrow_state_context_adapter": variant_gates
        },
        "best_variant": best_variant,
        "expected_value_score_delta": best_gate["delta"]["aggregate_ev_delta"],
        "total_pnl_delta": best_gate["delta"]["aggregate_pnl_delta"],
        "selection": baseline_selection,
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
                "deterministic SEC item-code fields only."
            ),
        },
        "decision_rationale": (
            "Accepted and promoted as a shared default-off paper adapter change."
            if accepted
            else "Rejected: 5.03 governance disclosure haircut did not clear Gate 4."
        ),
        "rejection_reason": rejection_reason,
        "next_action": (
            "Keep the 5.03 governance paper haircut in the shared default-off "
            "event bundle; wait for new forward rows before nearby item-code retunes."
        )
        if accepted
        else (
            "Do not retry nearby SEC governance item-code scalars on the frozen "
            "sample without new forward rows or a materially different "
            "disclosure-quality field."
        ),
        "why_not_other_attractive_points": (
            "Skipped LLM soft-ranking due attribution limits; skipped "
            "broad-market because the latest replay identity control failed; "
            "skipped state-surface notional retunes because the sleeve now has "
            "a stricter same-family materiality gate; skipped ETF adjacent caps "
            "after the latest volatility-cap rejection."
        ),
        "risk_of_change": (
            "Default-off event paper attribution only. No live orders, core "
            "ranking, core sizing, exits, source definitions, source capacity, "
            "or event hold period changed."
        ),
        "related_files": [
            base._repo_rel(Path(__file__)),
            "quant/event_sleeve_bundle.py",
            "quant/test_event_sleeve_bundle.py",
            "docs/production_backtest_parity.md",
            base._repo_rel(OUT_JSON),
            base._repo_rel(LOG_JSON),
            base._repo_rel(TICKET_JSON),
            base._repo_rel(ARTIFACT_MD),
            base._repo_rel(EXPERIMENT_LOG),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    gate = payload["gate4"]
    baseline = payload["before_metrics"][BASELINE_VARIANT]
    after = payload["after_metrics"][best]
    lines = [
        f"# {EXPERIMENT_ID} Event Governance 5.03 Haircut",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        (
            "Alpha search. Tests whether SEC governance/procedural event rows "
            "containing 8-K item 5.03 should receive a paper-notional haircut "
            "on top of the accepted event non-narrow context adapter."
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
                "Shared default-off event adapter/reporting changes only because "
                "the experiment is accepted. Core behavior, source capacity, and "
                "live/default order paths are unchanged."
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
            "title": "Event governance 5.03 haircut",
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
                    "windows_ev_improved": payload["gate4"]["delta"]["windows_ev_improved"],
                    "windows_ev_regressed": payload["gate4"]["delta"]["windows_ev_regressed"],
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
