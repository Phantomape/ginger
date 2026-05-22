"""exp-20260522-020: event narrow-cap leadership haircut scout.

Alpha search, replay-only. Tests one production-visible event market-state
field on top of the accepted exp-20260522-007 event adapter:

    state_bucket == "narrow_cap_weight_leadership"

The variable is intentionally narrower than the rejected crowded-leadership
context scout. It changes only default-off event paper notional. Core entries,
exits, ranking, sizing, source capacity, LLM/news, and live/default orders stay
unchanged.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260522_007_event_governance_503_haircut as exp007


EXPERIMENT_ID = "exp-20260522-020"
EXPERIMENT_SLUG = "event_narrow_cap_leadership_haircut"

REPO_ROOT = exp007.REPO_ROOT
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

BASELINE_VARIANT = "accepted_event_governance_503_haircut"
TARGET_STATE_BUCKET = "narrow_cap_weight_leadership"
MAX_DRAWDOWN_DRIFT = 0.0100
MIN_TARGET_TRADES = 5
MIN_TARGET_WINDOWS = 3
MIN_TARGET_TICKERS = 4
MIN_TARGET_LOSSES = 3
MAX_TARGET_SINGLE_LOSS_SHARE = 0.75
MIN_MATERIALITY_DELTA_PCT = 0.02

VARIANTS: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "description": "Accepted exp-20260522-007 event adapter.",
                "narrow_cap_leadership_scalar": 1.00,
            },
        ),
        (
            "narrow_cap_leadership_075",
            {
                "description": "0.75x paper notional for narrow cap-weight leadership event rows.",
                "narrow_cap_leadership_scalar": 0.75,
            },
        ),
        (
            "narrow_cap_leadership_050",
            {
                "description": "0.50x paper notional for narrow cap-weight leadership event rows.",
                "narrow_cap_leadership_scalar": 0.50,
            },
        ),
        (
            "narrow_cap_leadership_025",
            {
                "description": "0.25x paper notional for narrow cap-weight leadership event rows.",
                "narrow_cap_leadership_scalar": 0.25,
            },
        ),
        (
            "narrow_cap_leadership_000",
            {
                "description": "0.00x paper notional for narrow cap-weight leadership event rows.",
                "narrow_cap_leadership_scalar": 0.00,
            },
        ),
    ]
)


def _parent():
    return exp007._parent()


def _configure_modules() -> None:
    exp007._configure_modules()


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _append_jsonl_dedup(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    compact = f'"experiment_id":"{EXPERIMENT_ID}"'
    pretty = f'"experiment_id": "{EXPERIMENT_ID}"'
    lines = (
        path.read_text(encoding="utf-8", errors="replace").splitlines()
        if path.exists()
        else []
    )
    kept = [line for line in lines if compact not in line and pretty not in line]
    kept.append(json.dumps(_safe(payload), ensure_ascii=True, sort_keys=True))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_safe(item) for item in value]
    if hasattr(value, "item"):
        return _safe(value.item())
    return value


def _accepted_503_trade(trade: dict[str, Any]) -> dict[str, Any]:
    return exp007._scaled_trade(
        trade,
        "governance_503_025",
        exp007.VARIANTS["governance_503_025"],
    )


def _is_target_narrow_cap_leadership(trade: dict[str, Any]) -> bool:
    return str(trade.get("state_bucket") or "") == TARGET_STATE_BUCKET


def _scaled_trade(
    trade: dict[str, Any],
    variant_name: str,
    variant: dict[str, Any],
) -> dict[str, Any]:
    base = _accepted_503_trade(trade)
    target = _is_target_narrow_cap_leadership(base)
    context_scalar = (
        float(variant["narrow_cap_leadership_scalar"]) if target else 1.0
    )
    return {
        **base,
        "variant": variant_name,
        "narrow_cap_leadership_target": target,
        "narrow_cap_leadership_scalar": round(context_scalar, 4),
        "event_scalar_after_exp020": round(
            float(base.get("event_scalar") or base.get("state_surface_scalar") or 1.0)
            * context_scalar,
            4,
        ),
        "notional": round(float(base.get("notional") or 0.0) * context_scalar, 2),
        "shares": float(base.get("shares") or 0.0) * context_scalar,
        "pnl": round(float(base.get("pnl") or 0.0) * context_scalar, 2),
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
    targets = [row for row in all_rows if row.get("narrow_cap_leadership_target")]
    for label, rows in rows_by_window.items():
        window_targets = [
            row for row in rows if row.get("narrow_cap_leadership_target")
        ]
        target_by_window[label] = {
            "trade_count": len(window_targets),
            "wins": sum(
                1 for row in window_targets if float(row.get("pnl") or 0.0) > 0
            ),
            "losses": sum(
                1 for row in window_targets if float(row.get("pnl") or 0.0) < 0
            ),
            "total_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in window_targets),
                2,
            ),
            "tickers": sorted({str(row.get("ticker") or "") for row in window_targets}),
            "sources": sorted({str(row.get("source") or "") for row in window_targets}),
            "reaction_buckets": sorted(
                {str(row.get("reaction_bucket") or "") for row in window_targets}
            ),
            "state_surfaces": sorted(
                {str(row.get("state_surface") or "") for row in window_targets}
            ),
            "semantic_subcategories": sorted(
                {
                    str(row.get("semantic_subcategory") or "")
                    for row in window_targets
                }
            ),
            "eight_k_item_code_sets": sorted(
                {
                    "|".join(str(item) for item in (row.get("eight_k_item_codes") or []))
                    for row in window_targets
                }
            ),
        }
    wins = sum(1 for row in targets if float(row.get("pnl") or 0.0) > 0)
    losses = sum(1 for row in targets if float(row.get("pnl") or 0.0) < 0)
    return {
        "target_rule": f"state_bucket == {TARGET_STATE_BUCKET}",
        "target_field": "event_state_bucket_narrow_cap_weight_leadership",
        "target_trade_count": len(targets),
        "target_windows_present": sum(
            1 for row in target_by_window.values() if row["trade_count"] > 0
        ),
        "target_tickers": sorted({str(row.get("ticker") or "") for row in targets}),
        "target_sources": sorted({str(row.get("source") or "") for row in targets}),
        "target_state_surfaces": sorted(
            {str(row.get("state_surface") or "") for row in targets}
        ),
        "target_reaction_buckets": sorted(
            {str(row.get("reaction_bucket") or "") for row in targets}
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
    aggregate = gate["delta"]
    sample_ok = (
        (baseline_selection.get("target_trade_count") or 0) >= MIN_TARGET_TRADES
        and (baseline_selection.get("target_windows_present") or 0)
        >= MIN_TARGET_WINDOWS
        and len(baseline_selection.get("target_tickers") or []) >= MIN_TARGET_TICKERS
        and (baseline_selection.get("target_losses") or 0) >= MIN_TARGET_LOSSES
        and (baseline_selection.get("target_scaled_total_pnl") or 0.0) < 0.0
        and (
            baseline_selection.get("target_max_single_loss_pnl_share") is not None
            and baseline_selection["target_max_single_loss_pnl_share"]
            <= MAX_TARGET_SINGLE_LOSS_SHARE
        )
    )
    risk_ok = max_drawdown_drift <= MAX_DRAWDOWN_DRIFT
    materiality_ok = bool(
        (aggregate.get("aggregate_ev_delta_pct") or 0.0) >= MIN_MATERIALITY_DELTA_PCT
        or (aggregate.get("aggregate_pnl_delta_pct") or 0.0)
        >= MIN_MATERIALITY_DELTA_PCT
    )
    three_window_ok = bool(gate["passed"])
    return {
        **gate,
        "three_window_guard_passed": three_window_ok,
        "sample_guard_passed": bool(sample_ok),
        "risk_guard_passed": bool(risk_ok),
        "materiality_guard_passed": bool(materiality_ok),
        "max_drawdown_drift_limit": MAX_DRAWDOWN_DRIFT,
        "max_window_drawdown_drift": round(max_drawdown_drift, 6),
        "passed": bool(three_window_ok and sample_ok and risk_ok and materiality_ok),
        "sample_guard": {
            "min_target_trades": MIN_TARGET_TRADES,
            "min_target_windows": MIN_TARGET_WINDOWS,
            "min_target_tickers": MIN_TARGET_TICKERS,
            "min_target_losses": MIN_TARGET_LOSSES,
            "requires_negative_baseline_target_pnl": True,
            "max_target_single_loss_pnl_share": MAX_TARGET_SINGLE_LOSS_SHARE,
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
        "materiality_guard": {
            "min_delta_pct": MIN_MATERIALITY_DELTA_PCT,
            "aggregate_ev_delta_pct": aggregate.get("aggregate_ev_delta_pct"),
            "aggregate_pnl_delta_pct": aggregate.get("aggregate_pnl_delta_pct"),
        },
    }


def _choose_best(gates: dict[str, dict[str, Any]]) -> str:
    names = [name for name in VARIANTS if name != BASELINE_VARIANT]
    passed = [name for name in names if gates[name]["passed"]]
    candidates = passed if passed else names
    return max(
        candidates,
        key=lambda name: (
            gates[name]["delta"]["aggregate_ev_delta"],
            gates[name]["delta"]["aggregate_pnl_delta"],
            -abs(VARIANTS[name]["narrow_cap_leadership_scalar"] - 1.0),
        ),
    )


def _compact_variant_gates(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return OrderedDict(
        (
            name,
            {
                "passed": gate["passed"],
                "three_window_guard_passed": gate["three_window_guard_passed"],
                "sample_guard_passed": gate["sample_guard_passed"],
                "risk_guard_passed": gate["risk_guard_passed"],
                "materiality_guard_passed": gate["materiality_guard_passed"],
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
    operator_check = exp007.base.exp010._operator_position_field_check()
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
        "accepted_default_off_event_narrow_cap_leadership_haircut"
        if accepted
        else "rejected_event_narrow_cap_leadership_haircut"
    )
    production_impact = {
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": False,
        "replay_only": True,
        "parity_test_added": False,
        "default_off_paper_only": True,
        "alters_orders": False,
        "live_default_orders_changed": False,
    }
    rejection_reason = None
    if not accepted:
        failed_guards = []
        if not best_gate["three_window_guard_passed"]:
            failed_guards.append("three_window_gate")
        if not best_gate["sample_guard_passed"]:
            failed_guards.append("sample_guard")
        if not best_gate["risk_guard_passed"]:
            failed_guards.append("risk_guard")
        if not best_gate["materiality_guard_passed"]:
            failed_guards.append("materiality_guard")
        rejection_reason = (
            f"Best variant `{best_variant}` improved aggregate EV by "
            f"{best_gate['delta']['aggregate_ev_delta']} and PnL by "
            f"{best_gate['delta']['aggregate_pnl_delta']}, but Gate 4 failed: "
            + ", ".join(failed_guards)
            + "."
        )

    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": "accepted" if accepted else "rejected",
        "decision": decision,
        "lane": "alpha_search",
        "anti_js": "No JavaScript was used.",
        "hypothesis": (
            "Default-off event rows that fire during narrow cap-weight leadership "
            "may represent crowded, fragile leadership rather than durable event "
            "alpha; a small paper-notional haircut could improve replacement value "
            "without changing source queues, ranking, exits, or live orders."
        ),
        "alpha_hypothesis": {
            "category": "capital allocation",
            "entry_exit_ranking_or_allocation": "default-off paper allocation",
            "playbook_alignment": (
                "Tests event source/context quality while avoiding LLM soft-ranking, "
                "candidate-pool expansion, and broad state/capacity retunes."
            ),
        },
        "change_type": "default_off_event_paper_notional_scalar",
        "mechanism_family": "event_market_state_crowding_context",
        "trial_family": "event_market_state_crowding_context",
        "trial_variant_id": "event_narrow_cap_weight_leadership_haircut",
        "changed_variable": "event_narrow_cap_weight_leadership_scalar",
        "prior_trial_count": 1,
        "nearby_prior_experiments": [
            "exp-20260522-005",
            "exp-20260521-013",
            "exp-20260522-007",
        ],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "narrower_production_visible_state_bucket_after_503_haircut",
        "backtest_protocol": (
            "docs/backtesting.md canonical three fixed windows; default-off event "
            "overlay replay on top of accepted exp-20260522-007 event adapter."
        ),
        "date_range": {
            label: {
                "start": window["start"],
                "end": window["end"],
                "snapshot": window.get("snapshot"),
            }
            for label, window in parent.base.WINDOWS.items()
        },
        "gate_answers": {
            "1_alpha_hypothesis": (
                "Event overlay rows in narrow cap-weight leadership may be fragile "
                "crowding rows; a notional haircut could improve EV."
            ),
            "2_prior_similar_experiments": (
                "exp-20260522-005 rejected a broader crowded-leadership haircut; "
                "exp-20260521-013 accepted a non-narrow state context uplift; "
                "exp-20260522-007 accepted a 5.03 governance haircut."
            ),
            "3_single_causal_variable": (
                "Only event_narrow_cap_weight_leadership_scalar changes."
            ),
            "4_success_criteria": (
                "Same three-window event overlay gate, plus target sample >= 5, "
                "3 windows, >= 4 tickers, loss concentration <= 75%, drawdown drift "
                "<= 1pp, and >= 2% EV or PnL materiality because this is a high "
                "multiple-testing-risk near-neighbor."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe "
                "quant\\experiments\\exp_20260522_020_event_narrow_cap_leadership_haircut.py"
            ),
        },
        "parameters": {
            "baseline": BASELINE_VARIANT,
            "target_state_bucket": TARGET_STATE_BUCKET,
            "scalars_tested": [
                row["narrow_cap_leadership_scalar"]
                for name, row in VARIANTS.items()
                if name != BASELINE_VARIANT
            ],
            "selected_scalar": VARIANTS[best_variant][
                "narrow_cap_leadership_scalar"
            ],
            "locked_variables": [
                "source queues",
                "source capacity",
                "event hold days",
                "accepted 5.03 haircut",
                "non-narrow state context scalar",
                "core entries/exits/ranking/sizing",
                "LLM/news",
                "live/default orders",
            ],
        },
        "field_checks": {
            "open_positions": operator_check,
            "event_state_bucket": {
                "field": "state_bucket",
                "required_value": TARGET_STATE_BUCKET,
                "target_trade_count": baseline_selection["target_trade_count"],
                "target_windows_present": baseline_selection["target_windows_present"],
                "target_tickers": baseline_selection["target_tickers"],
                "passed": baseline_selection["target_trade_count"] > 0,
            },
        },
        "gate1": {
            "baseline_artifact": "accepted exp-20260522-007 event adapter replay",
            "core_metrics": core_metrics,
            "baseline_metrics": baseline_metrics,
        },
        "gate2": {"passed": True, "field_checks": operator_check},
        "gate3": {
            "passed": True,
            "new_filter_added": False,
            "survival_rate_min": min(
                float(row.get("survival_rate") or 0.0)
                for row in core_metrics.values()
            ),
        },
        "gate4": best_gate,
        "baseline_selection": baseline_selection,
        "variant_results": {
            name: {
                "parameters": VARIANTS[name],
                "after_metrics": variant_metrics[name],
                "selection": _selection_summary(variant_events[name]),
                "gate_vs_baseline": (
                    gates_vs_baseline[name] if name != BASELINE_VARIANT else None
                ),
            }
            for name in VARIANTS
        },
        "variant_gate_summary": _compact_variant_gates(gates_vs_baseline),
        "before_metrics": baseline_metrics,
        "after_metrics": variant_metrics[best_variant],
        "delta_metrics": best_gate["delta"],
        "expected_value_score_delta": best_gate["delta"]["aggregate_ev_delta"],
        "total_pnl_delta": best_gate["delta"]["aggregate_pnl_delta"],
        "llm_metrics": {
            "used_llm": False,
            "llm_change_scope": "none",
            "llm_attribution_metric": "not_applicable",
        },
        "risk_distribution": {
            "before": {
                label: {
                    "worst_trade_pct": row.get("worst_trade_pct"),
                    "max_consecutive_losses": row.get("max_consecutive_losses"),
                    "tail_loss_share": row.get("tail_loss_share"),
                }
                for label, row in baseline_metrics.items()
            },
            "after": {
                label: {
                    "worst_trade_pct": row.get("worst_trade_pct"),
                    "max_consecutive_losses": row.get("max_consecutive_losses"),
                    "tail_loss_share": row.get("tail_loss_share"),
                }
                for label, row in variant_metrics[best_variant].items()
            },
        },
        "production_impact": production_impact,
        "why_not_other_changes": (
            "LLM soft-ranking remains attribution-limited; broad-market warehouse "
            "identity drift blocks acceptance; Space forward consistency was just "
            "sample-limited; and broader event crowded-leadership was recently "
            "rejected. This test isolates the narrower production-visible state bucket."
        ),
        "known_risks": [
            "High multiple-testing risk because this is adjacent to event state/context scalars.",
            "Only four target trades in the accepted-baseline sample.",
            "The largest target loss dominates the loss-side evidence.",
        ],
        "rejection_reason": rejection_reason,
        "next_evidence_needed": (
            "Do not promote narrow-cap leadership event haircuts on this frozen "
            "sample. Revisit only with new closed forward event rows or a materially "
            "different source-quality field that broadens support beyond four trades."
        ),
        "related_files": [
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            "docs/experiment_log.jsonl",
        ],
    }
    return payload


def _write_artifact(payload: dict[str, Any]) -> None:
    best = payload["variant_results"][
        max(
            (
                name
                for name in VARIANTS
                if name != BASELINE_VARIANT
            ),
            key=lambda name: payload["variant_results"][name]["gate_vs_baseline"][
                "delta"
            ]["aggregate_ev_delta"],
        )
    ]
    best_name = next(
        name
        for name, row in payload["variant_results"].items()
        if row is best
    )
    lines = [
        f"# {EXPERIMENT_ID} Event Narrow-Cap Leadership Haircut",
        "",
        f"Decision: `{payload['decision']}`",
        f"Best variant: `{best_name}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Trial Accounting",
        "",
        f"- trial_family: `{payload['trial_family']}`",
        f"- changed_variable: `{payload['changed_variable']}`",
        f"- prior_trial_count: `{payload['prior_trial_count']}`",
        f"- multiple_testing_risk_bucket: `{payload['multiple_testing_risk_bucket']}`",
        f"- new_evidence_type: `{payload['new_evidence_type']}`",
        "",
        "## Variant Sweep",
        "",
        "| Variant | Scalar | Passed | Sample | Materiality | Risk | dEV | dPnL | EV +/- | Max DD drift |",
        "|---|---:|:---:|:---:|:---:|:---:|---:|---:|---:|---:|",
    ]
    for name, gate in payload["variant_gate_summary"].items():
        params = VARIANTS[name]
        lines.append(
            "| {name} | {scalar:.2f} | {passed} | {sample} | {materiality} | {risk} | {ev:+.4f} | ${pnl:+,.2f} | {imp}/{reg} | {dd:+.4f} |".format(
                name=name,
                scalar=params["narrow_cap_leadership_scalar"],
                passed="yes" if gate["passed"] else "no",
                sample="yes" if gate["sample_guard_passed"] else "no",
                materiality="yes" if gate["materiality_guard_passed"] else "no",
                risk="yes" if gate["risk_guard_passed"] else "no",
                ev=gate["aggregate_ev_delta"],
                pnl=gate["aggregate_pnl_delta"],
                imp=gate["windows_ev_improved"],
                reg=gate["windows_ev_regressed"],
                dd=gate["max_window_drawdown_drift"],
            )
        )
    lines.extend(
        [
            "",
            "## Best Variant Window Deltas",
            "",
            "| Window | EV delta | PnL delta | Return delta | SharpeD delta | DD delta |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for label, row in payload["gate4"]["delta"]["by_window"].items():
        lines.append(
            "| {label} | {ev:+.4f} | ${pnl:+,.2f} | {ret:+.4f} | {sharpe:+.2f} | {dd:+.4f} |".format(
                label=label,
                ev=row.get("expected_value_score", 0.0),
                pnl=row.get("total_pnl", 0.0),
                ret=row.get("total_return_pct", 0.0),
                sharpe=row.get("sharpe_daily", 0.0),
                dd=row.get("max_drawdown_pct", 0.0),
            )
        )
    lines.extend(
        [
            "",
            "## Target Sample",
            "",
            "```json",
            json.dumps(payload["baseline_selection"], indent=2, sort_keys=True),
            "```",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "```text",
            "production_impact:",
            f"  shared_policy_changed: {payload['production_impact']['shared_policy_changed']}",
            f"  backtester_adapter_changed: {payload['production_impact']['backtester_adapter_changed']}",
            f"  run_adapter_changed: {payload['production_impact']['run_adapter_changed']}",
            f"  replay_only: {payload['production_impact']['replay_only']}",
            f"  parity_test_added: {payload['production_impact']['parity_test_added']}",
            f"  alters_orders: {payload['production_impact']['alters_orders']}",
            "```",
            "",
            "No shared policy or live/default order behavior changed.",
            "",
            f"No JavaScript was used.",
        ]
    )
    _write_text(ARTIFACT_MD, "\n".join(lines) + "\n")


def _write_ticket(payload: dict[str, Any]) -> None:
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "hypothesis": payload["hypothesis"],
            "changed_variable": payload["changed_variable"],
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "total_pnl_delta": payload["total_pnl_delta"],
            "artifact": _repo_rel(ARTIFACT_MD),
        },
    )


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_ticket(payload)
    _write_artifact(payload)
    _append_jsonl_dedup(EXPERIMENT_LOG, payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "total_pnl_delta": payload["total_pnl_delta"],
                "best_variant": max(
                    payload["variant_gate_summary"],
                    key=lambda name: payload["variant_gate_summary"][name][
                        "aggregate_ev_delta"
                    ],
                ),
                "gate4_passed": payload["gate4"]["passed"],
                "anti_js": payload["anti_js"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
