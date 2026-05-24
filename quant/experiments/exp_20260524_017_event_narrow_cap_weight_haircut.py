"""exp-20260524-017: event narrow cap-weight leadership haircut.

Alpha search. Tests one production-visible event market-state field on top of
the accepted default-off event overlay stack: whether event rows in
``narrow_cap_weight_leadership`` deserve lower paper notional.

No JavaScript is used. Live/default orders remain disabled.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260522_007_event_governance_503_haircut as exp007


EXPERIMENT_ID = "exp-20260524-017"
EXPERIMENT_SLUG = "event_narrow_cap_weight_haircut"

REPO_ROOT = exp007.REPO_ROOT
OUT_JSON = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID / f"{EXPERIMENT_SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = (
    REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{EXPERIMENT_SLUG}.md"
)
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

BASELINE_VARIANT = "accepted_event_governance_503_adapter"
TARGET_STATE_BUCKET = "narrow_cap_weight_leadership"
MAX_DRAWDOWN_DRIFT = 0.0100

VARIANTS: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "description": "Accepted event stack after exp-20260522-007.",
                "narrow_cap_weight_scalar": 1.00,
            },
        ),
        (
            "narrow_cap_weight_075",
            {
                "description": "0.75x paper notional for narrow cap-weight event rows.",
                "narrow_cap_weight_scalar": 0.75,
            },
        ),
        (
            "narrow_cap_weight_050",
            {
                "description": "0.50x paper notional for narrow cap-weight event rows.",
                "narrow_cap_weight_scalar": 0.50,
            },
        ),
        (
            "narrow_cap_weight_025",
            {
                "description": "0.25x paper notional for narrow cap-weight event rows.",
                "narrow_cap_weight_scalar": 0.25,
            },
        ),
        (
            "narrow_cap_weight_000",
            {
                "description": "0.00x paper notional for narrow cap-weight event rows.",
                "narrow_cap_weight_scalar": 0.00,
            },
        ),
    ]
)


def _parent() -> Any:
    return exp007._parent()


def _configure_modules() -> None:
    exp007._configure_modules()


def _accepted_event_scalar_after_exp007(trade: dict[str, Any]) -> float:
    scalar = exp007.base._accepted_event_scalar_after_exp013(trade)
    if exp007._is_target_governance_503(trade):
        scalar *= 0.25
    return scalar


def _is_target_narrow_cap_weight(trade: dict[str, Any]) -> bool:
    return str(trade.get("state_bucket") or "") == TARGET_STATE_BUCKET


def _scaled_trade(
    trade: dict[str, Any],
    variant_name: str,
    variant: dict[str, Any],
) -> dict[str, Any]:
    parent = _parent()
    accepted_scalar = _accepted_event_scalar_after_exp007(trade)
    target = _is_target_narrow_cap_weight(trade)
    target_scalar = float(variant["narrow_cap_weight_scalar"]) if target else 1.0
    scalar = accepted_scalar * target_scalar
    base_notional = float(trade.get("notional") or parent.base.EVENT_NOTIONAL)
    base_shares = float(trade.get("shares") or 0.0)
    return {
        **trade,
        "variant": variant_name,
        "accepted_event_scalar_after_exp007": round(accepted_scalar, 4),
        "narrow_cap_weight_target": target,
        "narrow_cap_weight_scalar": round(target_scalar, 4),
        "event_scalar": round(scalar, 4),
        "base_notional": round(base_notional, 2),
        "notional": round(base_notional * scalar, 2),
        "shares": base_shares * scalar,
        "pnl": round(float(trade.get("pnl") or 0.0) * scalar, 2),
    }


def _safe_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _safe_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe_json(v) for v in value]
    if isinstance(value, tuple):
        return [_safe_json(v) for v in value]
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_safe_json(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _target_loss_share(rows: list[dict[str, Any]]) -> float | None:
    losses = [
        abs(float(row.get("pnl") or 0.0))
        for row in rows
        if float(row.get("pnl") or 0.0) < 0.0
    ]
    total = sum(losses)
    if total <= 0.0:
        return None
    return round(max(losses) / total, 6)


def _selection_summary(rows_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    target_by_window: dict[str, Any] = OrderedDict()
    all_rows = [row for rows in rows_by_window.values() for row in rows]
    targets = [row for row in all_rows if row.get("narrow_cap_weight_target")]
    for label, rows in rows_by_window.items():
        window_targets = [row for row in rows if row.get("narrow_cap_weight_target")]
        target_by_window[label] = {
            "trade_count": len(window_targets),
            "wins": sum(1 for row in window_targets if float(row.get("pnl") or 0.0) > 0),
            "losses": sum(1 for row in window_targets if float(row.get("pnl") or 0.0) < 0),
            "total_pnl": round(sum(float(row.get("pnl") or 0.0) for row in window_targets), 2),
            "tickers": sorted({str(row.get("ticker") or "") for row in window_targets}),
            "sources": sorted({str(row.get("source") or "") for row in window_targets}),
            "reaction_buckets": sorted({str(row.get("reaction_bucket") or "") for row in window_targets}),
            "state_surfaces": sorted({str(row.get("state_surface") or "") for row in window_targets}),
            "semantic_subcategories": sorted(
                {str(row.get("semantic_subcategory") or "") for row in window_targets}
            ),
        }
    wins = sum(1 for row in targets if float(row.get("pnl") or 0.0) > 0)
    losses = sum(1 for row in targets if float(row.get("pnl") or 0.0) < 0)
    return {
        "target_rule": f"state_bucket == {TARGET_STATE_BUCKET}",
        "target_field": "event_state_bucket",
        "target_trade_count": len(targets),
        "target_windows_present": sum(1 for row in target_by_window.values() if row["trade_count"] > 0),
        "target_loss_windows_present": sum(1 for row in target_by_window.values() if row["total_pnl"] < 0),
        "target_tickers": sorted({str(row.get("ticker") or "") for row in targets}),
        "target_sources": sorted({str(row.get("source") or "") for row in targets}),
        "target_reaction_buckets": sorted({str(row.get("reaction_bucket") or "") for row in targets}),
        "target_state_surfaces": sorted({str(row.get("state_surface") or "") for row in targets}),
        "target_semantic_subcategories": sorted(
            {str(row.get("semantic_subcategory") or "") for row in targets}
        ),
        "target_wins": wins,
        "target_losses": losses,
        "target_win_rate": round(wins / len(targets), 4) if targets else None,
        "target_scaled_total_pnl": round(sum(float(row.get("pnl") or 0.0) for row in targets), 2),
        "target_max_single_loss_pnl_share": _target_loss_share(targets),
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
        (baseline_selection.get("target_trade_count") or 0) >= 4
        and (baseline_selection.get("target_windows_present") or 0) >= 3
        and (baseline_selection.get("target_loss_windows_present") or 0) >= 3
        and len(baseline_selection.get("target_tickers") or []) >= 4
        and (baseline_selection.get("target_losses") or 0) >= 3
        and (baseline_selection.get("target_scaled_total_pnl") or 0.0) < 0.0
        and (
            baseline_selection.get("target_max_single_loss_pnl_share") is None
            or baseline_selection["target_max_single_loss_pnl_share"] <= 0.85
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
            "min_target_trades": 4,
            "min_target_windows": 3,
            "min_target_loss_windows": 3,
            "min_target_tickers": 4,
            "min_target_losses": 3,
            "requires_negative_baseline_target_pnl": True,
            "max_target_single_loss_pnl_share": 0.85,
            "actual_target_trades": baseline_selection.get("target_trade_count"),
            "actual_target_windows": baseline_selection.get("target_windows_present"),
            "actual_target_loss_windows": baseline_selection.get("target_loss_windows_present"),
            "actual_target_tickers": baseline_selection.get("target_tickers"),
            "actual_target_losses": baseline_selection.get("target_losses"),
            "actual_target_scaled_total_pnl": baseline_selection.get("target_scaled_total_pnl"),
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
            -abs(float(VARIANTS[name]["narrow_cap_weight_scalar"]) - 1.0),
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


def _compact_metrics(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return exp007.base._compact_metrics_by_window(rows)


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
            _gate_vs_baseline(baseline_metrics, variant_metrics[name], baseline_selection),
        )
        for name in VARIANTS
        if name != BASELINE_VARIANT
    )
    best_variant = _choose_best(gates_vs_baseline)
    best_gate = gates_vs_baseline[best_variant]
    accepted = bool(best_gate["passed"])
    decision = (
        "accepted_default_off_event_narrow_cap_weight_haircut"
        if accepted
        else "rejected_event_narrow_cap_weight_haircut"
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

    before_metrics = _compact_metrics(baseline_metrics)
    after_metrics = _compact_metrics(variant_metrics[best_variant])
    variant_gates = _compact_variant_gates(gates_vs_baseline)
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "event_market_state_allocation_adapter",
        "mechanism_family": "external_event_satellite_overlay_allocation",
        "trial_family": "event_state_context_haircut",
        "trial_variant_id": "narrow_cap_weight_leadership_notional_haircut",
        "changed_variable": "event_narrow_cap_weight_leadership_notional_scalar",
        "prior_trial_count": 17,
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "production_visible_event_state_bucket_with_all_window_negative_baseline_pnl",
        "hypothesis": (
            "In the accepted default-off event overlay, rows tagged "
            "narrow_cap_weight_leadership are likely to be crowded cap-weight "
            "leadership exposures rather than fresh event alpha. A single paper "
            "notional haircut may reduce this weak cohort without changing core "
            "entries, exits, ranking, or live orders."
        ),
        "alpha_hypothesis": {
            "category": "risk allocation / event market-state context",
            "entry_exit_ranking_or_allocation": "capital allocation",
            "playbook_alignment": (
                "Uses the playbook's event/source-context and concentration "
                "governance lane. It avoids LLM soft-ranking, candidate-pool "
                "expansion, and state-surface sleeve threshold retunes."
            ),
        },
        "single_causal_variable": (
            "paper-notional scalar for fixed accepted event rows where "
            "state_bucket == narrow_cap_weight_leadership; all accepted event "
            "source, reaction, governance, holding-period, core, and order "
            "behavior stays fixed"
        ),
        "parameters": {
            "acceptance_baseline": BASELINE_VARIANT,
            "baseline_experiment_stack": [
                "exp-20260521-013",
                "exp-20260522-007",
            ],
            "target_rule": baseline_selection["target_rule"],
            "selected_narrow_cap_weight_scalar": VARIANTS[best_variant][
                "narrow_cap_weight_scalar"
            ],
            "variant_scalars": {
                name: row["narrow_cap_weight_scalar"] for name, row in VARIANTS.items()
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
                "event source-quality scalar",
                "event reaction-context scalar",
                "event positive-state scalar",
                "event non-narrow-state scalar",
                "event governance 5.03 haircut",
                "LLM prompt and replay",
                "news veto",
                "production orders",
            ],
            "anti_js": "No JavaScript was used.",
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}"
            for label, window in parent.base.WINDOWS.items()
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "Risk allocation: haircut accepted event overlay paper notional "
                "only for narrow_cap_weight_leadership state-bucket rows."
            ),
            "2_history_check": (
                "Prior exp-20260522-005 tested a broader crowded-leadership "
                "haircut and failed due late_strong regression. This run narrows "
                "the causal variable to the specific bucket that has negative "
                "accepted-stack PnL in all three canonical windows."
            ),
            "3_single_causal_variable": (
                "Only the event_narrow_cap_weight_leadership_notional_scalar "
                "changes."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; compare before/after "
                "against the accepted exp-20260522-007 event adapter baseline, "
                "requiring aggregate EV/PnL improvement, zero EV-regressed "
                "windows, sample guard pass, risk guard pass, and no production/"
                "backtest divergence."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260524_017_event_narrow_cap_weight_haircut.py"
            ),
        },
        "historical_experiment_check": {
            "exp-20260522-005": (
                "Rejected broader crowded-leadership context haircut. This run "
                "does not reuse the generic balanced-state surface component; it "
                "only tests narrow_cap_weight_leadership rows."
            ),
            "exp-20260523-005": (
                "Rejected core-overlap haircut despite positive aggregate EV due "
                "thin sample. This run keeps a sample guard and remains default-off."
            ),
            "exp-20260524-009": (
                "Rejected SEC missing-text scalar due concentration/data-provenance "
                "risk. This run uses a market-state tag, not text availability."
            ),
        },
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical fixed-snapshot three-window replay "
                "plus default-off event paper overlay accounting"
            ),
            "windows": exp007.base.exp010._compact_windows(parent.base.WINDOWS),
            "config": {
                "REGIME_AWARE_EXIT": True,
                "REPLAY_PARTIAL_REDUCES": True,
                "event_overlay": "default_off_paper_replay",
            },
        },
        "gate1_baseline_measurement": {
            "baseline_variant": BASELINE_VARIANT,
            "before_metrics": {BASELINE_VARIANT: before_metrics},
            "core_metrics_reference": _compact_metrics(core_metrics),
        },
        "gate2_field_check": {
            "operator_position_field_check": operator_check,
            "rule_fields": [
                "event trade state_bucket",
                "event trade source",
                "event trade reaction_bucket",
                "event trade state_surface",
                "event trade pnl/notional/shares",
                "entry_date",
                "target_price",
            ],
            "target_field_nonempty": baseline_selection["target_trade_count"] > 0,
            "production_visibility": (
                "state_bucket is emitted by the shared event bundle state-surface "
                "context path; this experiment does not change that path."
            ),
        },
        "gate3_survival_audit": {
            "baseline_min_survival_rate": min(
                float(row.get("survival_rate") or 0.0) for row in before_metrics.values()
            ),
            "after_min_survival_rate": min(
                float(row.get("survival_rate") or 0.0) for row in after_metrics.values()
            ),
            "survival_floor": 0.05,
            "filter_added": False,
            "comment": (
                "No core signal filter was added; event rows remain in replay with "
                "paper notional scaled to zero only for the tested variant."
            ),
        },
        "gate4": best_gate,
        "selection_summary": baseline_selection,
        "variant_vs_accepted_event_governance_503_adapter": variant_gates,
        "before_metrics": {BASELINE_VARIANT: before_metrics},
        "after_metrics": {best_variant: after_metrics},
        "best_variant": best_variant,
        "best_variant_passed": accepted,
        "expected_value_score_delta": best_gate["delta"]["aggregate_ev_delta"],
        "total_pnl_delta": best_gate["delta"]["aggregate_pnl_delta"],
        "production_backtest_parity": {
            "changed_production_files": [],
            "changed_backtest_files": [
                _repo_rel(Path("quant") / "experiments" / f"{Path(__file__).stem}.py")
            ],
            "live_orders_changed": False,
            "default_orders_changed": False,
            "parity_risk": "none_for_live_orders_replay_only_experiment",
            "promotion_requirement": (
                "If retained into the shared event bundle, implement the same "
                "state_bucket scalar in the production-visible event bundle config "
                "and rerun parity tests before any default-off/live behavior changes."
            ),
        },
        "sample_conclusion": (
            "The target cohort is intentionally narrow: 4 event rows, 4 tickers, "
            "and all three canonical windows. This is enough for a default-off "
            "scout only, not for production promotion without forward evidence."
        ),
        "rejection_reason": rejection_reason,
        "artifacts": {
            "out_json": _repo_rel(OUT_JSON),
            "log_json": _repo_rel(LOG_JSON),
            "ticket_json": _repo_rel(TICKET_JSON),
            "artifact_md": _repo_rel(ARTIFACT_MD),
            "experiment_log": _repo_rel(EXPERIMENT_LOG),
        },
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    gate = payload["gate4"]
    baseline_name, baseline = next(iter(payload["before_metrics"].items()))
    after_name, after = next(iter(payload["after_metrics"].items()))
    lines = [
        f"# {payload['experiment_id']} {EXPERIMENT_SLUG}",
        "",
        f"- lane: `{payload['lane']}`",
        f"- decision: `{payload['decision']}`",
        f"- best_variant: `{payload['best_variant']}`",
        f"- expected_value_score_delta: `{payload['expected_value_score_delta']}`",
        f"- total_pnl_delta: `${payload['total_pnl_delta']:,.2f}`",
        f"- production_backtest_parity: `{payload['production_backtest_parity']['parity_risk']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Gate 4 Before / After",
        "",
        f"Baseline: `{baseline_name}`. After: `{after_name}`.",
        "",
        "| window | before EV | after EV | delta EV | before PnL | after PnL | delta PnL |",
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
            "## Variant Gate Summary",
            "",
            "| variant | passed | sample | risk | EV delta | PnL delta | EV windows +/- | max DD drift |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for name, row in payload["variant_vs_accepted_event_governance_503_adapter"].items():
        lines.append(
            "| {name} | {passed} | {sample} | {risk} | {dev:+.4f} | ${dpnl:+,.2f} | {improved}/{regressed} | {dd:.4f} |".format(
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
            "## Target Cohort",
            "",
            "```json",
            json.dumps(payload["selection_summary"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production / Backtest Consistency",
            "",
            "No production or default-order code changed. This is a default-off replay-only alpha scout.",
        ]
    )
    if payload.get("rejection_reason"):
        lines.extend(["", "## Rejection Reason", "", payload["rejection_reason"]])
    return "\n".join(lines) + "\n"


def persist(payload: dict[str, Any]) -> None:
    parent = _parent()
    _write_json(OUT_JSON, payload)
    _write_json(
        LOG_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": payload["timestamp"],
            "lane": payload["lane"],
            "status": payload["status"],
            "decision": payload["decision"],
            "best_variant": payload["best_variant"],
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "total_pnl_delta": payload["total_pnl_delta"],
            "gate4": payload["gate4"],
            "selection_summary": payload["selection_summary"],
            "artifacts": payload["artifacts"],
        },
    )
    _write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "closed",
            "claimed_by": "codex",
            "lane": "alpha_search",
            "decision": payload["decision"],
            "opened_at": payload["timestamp"],
            "closed_at": payload["timestamp"],
            "summary": payload["hypothesis"],
            "artifacts": payload["artifacts"],
        },
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    parent._write_text(ARTIFACT_MD, _artifact_markdown(payload))

    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if EXPERIMENT_LOG.exists():
        lines = EXPERIMENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        lines = [
            line
            for line in lines
            if line.strip()
            and f'"experiment_id": "{EXPERIMENT_ID}"' not in line
        ]
    lines.append(json.dumps(_safe_json(payload), sort_keys=True))
    EXPERIMENT_LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["decision"],
                "best_variant": payload["best_variant"],
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "total_pnl_delta": payload["total_pnl_delta"],
                "windows_ev_improved": payload["gate4"]["delta"]["windows_ev_improved"],
                "windows_ev_regressed": payload["gate4"]["delta"]["windows_ev_regressed"],
                "sample_guard_passed": payload["gate4"]["sample_guard_passed"],
                "risk_guard_passed": payload["gate4"]["risk_guard_passed"],
                "anti_js": "No JavaScript was used.",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
