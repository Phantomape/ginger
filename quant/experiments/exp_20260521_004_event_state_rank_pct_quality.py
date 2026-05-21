"""exp-20260521-004: event state-rank quality scout.

Alpha search, replay-only. Tests one production-visible event quality field on
top of the accepted exp-20260521-001 default-off event overlay: whether event
rows in the top quartile of state_rank_pct deserve extra paper notional.

No JavaScript is used. No shared policy, production adapter, core behavior,
LLM/news behavior, or live/default orders are changed.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260521_001_event_broad_breadth_adapter as current


EXPERIMENT_ID = "exp-20260521-004"
EXPERIMENT_SLUG = "event_state_rank_pct_quality"

REPO_ROOT = current.REPO_ROOT
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

BASELINE_VARIANT = "accepted_broad_breadth_adapter"
TARGET_STATE_RANK_PCT_MAX = 0.25

VARIANTS: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "description": "Accepted exp-20260521-001 event adapter: front-rank rotation, broad-breadth, and non-generic positive event-state scalars fixed.",
                "state_rank_pct_quality_scalar": 1.0,
            },
        ),
        (
            "state_rank_pct_le_25_105",
            {
                "description": "Multiply accepted event paper notional by 1.05x when state_rank_pct <= 0.25.",
                "state_rank_pct_quality_scalar": 1.05,
            },
        ),
        (
            "state_rank_pct_le_25_110",
            {
                "description": "Multiply accepted event paper notional by 1.10x when state_rank_pct <= 0.25.",
                "state_rank_pct_quality_scalar": 1.10,
            },
        ),
        (
            "state_rank_pct_le_25_115",
            {
                "description": "Multiply accepted event paper notional by 1.15x when state_rank_pct <= 0.25.",
                "state_rank_pct_quality_scalar": 1.15,
            },
        ),
    ]
)


def _parent():
    return current._parent()


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _configure_modules() -> None:
    current._configure_modules()


def _accepted_event_scalar(trade: dict[str, Any]) -> float:
    scalar = current._accepted_event_scalar(trade)
    if current._is_broad_breadth_event(trade):
        scalar *= 1.25
    return scalar


def _state_rank_pct(trade: dict[str, Any]) -> float | None:
    value = trade.get("state_rank_pct")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_top_quartile_state_rank_event(trade: dict[str, Any]) -> bool:
    value = _state_rank_pct(trade)
    return value is not None and value <= TARGET_STATE_RANK_PCT_MAX


def _scaled_trade(
    trade: dict[str, Any],
    variant_name: str,
    variant: dict[str, Any],
) -> dict[str, Any]:
    parent = _parent()
    accepted_scalar = _accepted_event_scalar(trade)
    state_rank_pct_target = _is_top_quartile_state_rank_event(trade)
    quality_scalar = (
        float(variant["state_rank_pct_quality_scalar"])
        if state_rank_pct_target
        else 1.0
    )
    scalar = accepted_scalar * quality_scalar
    base_notional = float(trade.get("notional") or parent.base.EVENT_NOTIONAL)
    base_shares = float(trade.get("shares") or 0.0)
    return {
        **trade,
        "variant": variant_name,
        "accepted_event_scalar": round(accepted_scalar, 4),
        "state_rank_pct_quality_target": state_rank_pct_target,
        "state_rank_pct_quality_scalar": round(quality_scalar, 4),
        "state_surface_scalar": round(scalar, 4),
        "base_notional": round(base_notional, 2),
        "notional": round(base_notional * scalar, 2),
        "shares": base_shares * scalar,
        "pnl": round(float(trade.get("pnl") or 0.0) * scalar, 2),
    }


def _max_positive_share(rows: list[dict[str, Any]]) -> float | None:
    positive = [
        float(row.get("pnl") or 0.0)
        for row in rows
        if float(row.get("pnl") or 0.0) > 0
    ]
    total = sum(positive)
    if total <= 0:
        return None
    return round(max(positive) / total, 4)


def _selection_summary(rows_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    target_by_window: dict[str, Any] = OrderedDict()
    all_rows = [row for rows in rows_by_window.values() for row in rows]
    targets = [row for row in all_rows if row.get("state_rank_pct_quality_target")]
    for label, rows in rows_by_window.items():
        window_targets = [
            row for row in rows if row.get("state_rank_pct_quality_target")
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
        }
    return {
        "target_state_rank_pct_max": TARGET_STATE_RANK_PCT_MAX,
        "target_trade_count": len(targets),
        "target_windows_present": sum(
            1 for row in target_by_window.values() if row["trade_count"] > 0
        ),
        "target_tickers": sorted({str(row.get("ticker") or "") for row in targets}),
        "target_sources": sorted({str(row.get("source") or "") for row in targets}),
        "target_state_surfaces": sorted(
            {str(row.get("state_surface") or "") for row in targets}
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
        "target_max_single_positive_pnl_share": _max_positive_share(targets),
    }


def _gate_vs_baseline(
    baseline_metrics: dict[str, dict[str, Any]],
    after_metrics: dict[str, dict[str, Any]],
    selection: dict[str, Any],
) -> dict[str, Any]:
    gate = _parent().base._gate_summary(baseline_metrics, after_metrics)
    sample_ok = (
        (selection.get("target_trade_count") or 0) >= 10
        and (selection.get("target_windows_present") or 0) >= 3
        and len(selection.get("target_tickers") or []) >= 6
        and (
            selection.get("target_max_single_positive_pnl_share") is None
            or selection["target_max_single_positive_pnl_share"] <= 0.55
        )
    )
    return {
        **gate,
        "sample_guard_passed": bool(sample_ok),
        "passed": bool(gate["passed"] and sample_ok),
        "sample_guard": {
            "min_target_trades": 10,
            "min_target_windows": 3,
            "min_target_tickers": 6,
            "max_target_positive_pnl_share": 0.55,
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
            -VARIANTS[name]["state_rank_pct_quality_scalar"],
        ),
    )


def build_payload() -> dict[str, Any]:
    _configure_modules()
    parent = _parent()
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
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
        "accepted_default_off_event_state_rank_pct_quality"
        if accepted
        else "rejected_event_state_rank_pct_quality"
    )
    rejection_reason = None
    if not accepted:
        rejection_reason = (
            f"Best variant `{best_variant}` changed aggregate EV "
            f"{best_gate['delta']['aggregate_ev_delta']} and PnL "
            f"{best_gate['delta']['aggregate_pnl_delta']}, but Gate 4 failed: "
            f"EV improved/regressed windows "
            f"{best_gate['delta']['windows_ev_improved']}/"
            f"{best_gate['delta']['windows_ev_regressed']}, "
            f"sample_guard_passed={best_gate['sample_guard_passed']}."
        )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "event_quality_allocation_replay",
        "mechanism_family": "external_event_satellite_overlay_allocation",
        "trial_family": "event_rotation_replacement_value_maturation",
        "trial_variant_id": "state_rank_pct_top_quartile_quality",
        "changed_variable": "event_state_rank_pct_top_quartile_paper_notional_scalar",
        "prior_trial_count": 13,
        "nearby_prior_experiments": [
            "exp-20260516-013",
            "exp-20260516-028",
            "exp-20260516-030",
            "exp-20260516-040",
            "exp-20260516-044",
            "exp-20260517-001",
            "exp-20260517-010",
            "exp-20260520-042",
            "exp-20260520-043",
            "exp-20260520-044",
            "exp-20260521-001",
            "exp-20260521-002",
            "exp-20260521-003",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_production_visible_event_quality_field",
        "hypothesis": (
            "Inside the accepted default-off event overlay, event rows with "
            "state_rank_pct <= 0.25 may deserve extra paper notional because "
            "they express event replacement value while the state surface ranks "
            "their context near the top of the live-visible opportunity set."
        ),
        "alpha_hypothesis": {
            "category": "capital allocation / event-quality",
            "entry_exit_ranking_or_allocation": "capital allocation",
            "playbook_alignment": (
                "Uses a distinct production-visible event/state quality field in "
                "the event replacement-value lane; avoids LLM soft-ranking sample "
                "limits and does not change the state_surface_sleeve stack."
            ),
        },
        "single_causal_variable": (
            "paper-notional scalar for event overlay rows whose state_rank_pct is "
            "<= 0.25"
        ),
        "parameters": {
            "variants": VARIANTS,
            "acceptance_baseline": BASELINE_VARIANT,
            "baseline_experiment": "exp-20260521-001",
            "target_state_rank_pct_max": TARGET_STATE_RANK_PCT_MAX,
            "selected_state_rank_pct_quality_scalar": VARIANTS[best_variant][
                "state_rank_pct_quality_scalar"
            ],
            "base_event_notional_usd": parent.base.EVENT_NOTIONAL,
            "hold_days": parent.base.HOLD_DAYS,
            "round_trip_cost_pct": parent.base.ROUND_TRIP_COST_PCT,
            "sample_guard": {
                "min_target_trades": 10,
                "min_target_windows": 3,
                "min_target_tickers": 6,
                "max_target_positive_pnl_share": 0.55,
            },
            "anti_js": "No JavaScript was used.",
            "locked_variables": [
                "core universe",
                "core signal generation",
                "core candidate ranking",
                "core position sizing",
                "core exits",
                "core add-ons",
                "event source definitions",
                "event source thresholds",
                "event holding period",
                "front-rank rotation event scalar",
                "broad-breadth event scalar",
                "rotation event scalar",
                "non-rotation event scalar",
                "per-source active capacity",
                "LLM prompt and replay",
                "news veto",
                "production orders",
            ],
        },
        "date_range": {
            label: f"{window['start']} -> {window['end']}"
            for label, window in parent.base.WINDOWS.items()
        },
        "market_regime_summary": {
            label: window["state_note"] for label, window in parent.base.WINDOWS.items()
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "Top-quartile state_rank_pct event rows may carry cleaner "
                "replacement value; this is capital allocation/event-quality and "
                "matches the event replacement-value lane."
            ),
            "2_history_check": (
                "Event rotation, front-rank state quality, and broad-breadth "
                "context passed in exp042/043/044/021-001. High-dispersion "
                "context and source capacity did not clear in exp021-002/003. "
                "This tests state_rank_pct quality, not source identity, "
                "dispersion, or capacity."
            ),
            "3_single_causal_variable": (
                "Only top-quartile state_rank_pct event paper-notional scalar "
                "changes; core behavior, event sources, event hold, existing "
                "event state scalars, and source capacity stay fixed."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; compare against the "
                "accepted exp-20260521-001 baseline, require aggregate EV/PnL "
                "improvement, no EV-regressed window, sample guard pass, and no "
                "production/backtest divergence."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260521_004_event_state_rank_pct_quality.py"
            ),
        },
        "historical_experiment_check": {
            "exp-20260520-042": "Revalidated event rotation as the next alpha direction.",
            "exp-20260520-043": "Accepted replay-only front-rank event-rotation quality evidence.",
            "exp-20260520-044": "Promoted front-rank event-rotation into the shared default-off adapter.",
            "exp-20260521-001": "Accepted broad-breadth event context in the shared default-off adapter.",
            "exp-20260521-002": "Rejected high-dispersion event context because a window regressed.",
            "exp-20260521-003": "Rejected source capacity expansion because aggregate EV regressed.",
        },
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical fixed-snapshot three-window replay "
                "plus default-off event paper overlay accounting"
            ),
            "windows": parent.base.WINDOWS,
            "config": {
                "REGIME_AWARE_EXIT": True,
                "REPLAY_PARTIAL_REDUCES": True,
                "event_overlay": "default_off_paper_replay",
            },
        },
        "gate1": {
            "baseline_name": BASELINE_VARIANT,
            "baseline_metrics": baseline_metrics,
            "baseline_artifact": "data/experiments/exp-20260521-001/event_broad_breadth_adapter.json",
        },
        "gate2": {
            "required_fields": [
                "event source",
                "ticker",
                "entry_date",
                "exit_date",
                "pnl",
                "state_feature_available",
                "state_rank",
                "state_rank_pct",
                "state_surface",
                "breadth_bucket",
                "dispersion_bucket",
            ],
            "selection": selection_by_variant[BASELINE_VARIANT],
            "passed": bool(
                (selection_by_variant[BASELINE_VARIANT].get("target_trade_count") or 0)
                >= 10
                and (
                    selection_by_variant[BASELINE_VARIANT].get("target_windows_present")
                    or 0
                )
                >= 3
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
                "against the accepted exp-20260521-001 event broad-breadth baseline."
            ),
        },
        "before_metrics": {
            "core": core_metrics,
            BASELINE_VARIANT: baseline_metrics,
        },
        "after_metrics": variant_metrics,
        "delta_metrics": {
            "variant_vs_accepted_broad_breadth_adapter": gates_vs_baseline
        },
        "best_variant": best_variant,
        "expected_value_score_delta": best_gate["delta"]["aggregate_ev_delta"],
        "total_pnl_delta": best_gate["delta"]["aggregate_pnl_delta"],
        "selection": selection_by_variant,
        "source_coverage": source_coverage,
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "production_signal_path_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "live_orders_enabled": False,
            "promotion_blocker_if_positive": (
                "A positive result would still need shared adapter parity and "
                "closed forward replacement-value evidence before any live/default "
                "capital."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM soft-ranking remains attribution/sample-limited; this uses "
                "deterministic PIT event/state rank fields only."
            ),
        },
        "decision_rationale": (
            "Rejected. The best variant improved all three windows, but the move "
            "did not satisfy the repository Gate 4 materiality rule, so it is "
            "not promoted into shared strategy behavior."
            if not accepted
            else "Accepted as default-off paper attribution only."
        ),
        "rejection_reason": rejection_reason,
        "next_action": (
            "Do not retry nearby state_rank_pct event scalars on the frozen "
            "sample without new forward replacement-value evidence or a distinct "
            "context field with material Gate 4 strength."
            if not accepted
            else "Add shared adapter parity and collect closed forward outcomes."
        ),
        "why_not_other_attractive_points": (
            "Skipped LLM soft-ranking and SEC/buyback semantic fields due sample "
            "and provenance limits; skipped state-surface and broad-market nearby "
            "retunes due strict anti-repeat rules; tested state_rank_pct because "
            "it was already PIT, production-visible, and distinct from recent "
            "breadth/dispersion/source-capacity variables."
        ),
        "risk_of_change": (
            "Replay-only scout. No production or shared strategy behavior changed, "
            "so no production/backtest divergence is introduced."
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
        f"# {EXPERIMENT_ID} Event State-Rank Quality",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        (
            "Alpha search, replay-only. Tests whether top-quartile state_rank_pct "
            "is a useful event-quality allocation field on top of the accepted "
            "default-off event broad-breadth adapter."
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
            "| Variant | Passed | dEV | dPnL | Improved | Regressed | Target trades | Windows | Max positive share |",
            "|---|:---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for name, row in payload["delta_metrics"][
        "variant_vs_accepted_broad_breadth_adapter"
    ].items():
        selection = payload["selection"][name]
        lines.append(
            "| {name} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {trades} | {windows} | {share} |".format(
                name=name,
                passed="yes" if row["passed"] else "no",
                dev=row["delta"]["aggregate_ev_delta"],
                dpnl=row["delta"]["aggregate_pnl_delta"],
                improved=row["delta"]["windows_ev_improved"],
                regressed=row["delta"]["windows_ev_regressed"],
                trades=selection["target_trade_count"],
                windows=selection["target_windows_present"],
                share=selection["target_max_single_positive_pnl_share"],
            )
        )
    lines.extend(
        [
            "",
            "## Selection",
            "",
            "```json",
            json.dumps(payload["selection"][best], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            (
                "Replay only. No shared policy, adapter, production report, "
                "core behavior, or live/default order path changed."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def _compact_log(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "decision",
        "lane",
        "change_type",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "prior_trial_count",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "hypothesis",
        "alpha_hypothesis",
        "single_causal_variable",
        "parameters",
        "date_range",
        "market_regime_summary",
        "gate_questions",
        "historical_experiment_check",
        "backtest_protocol",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "best_variant",
        "expected_value_score_delta",
        "total_pnl_delta",
        "selection",
        "source_coverage",
        "production_impact",
        "llm_metrics",
        "decision_rationale",
        "rejection_reason",
        "next_action",
        "why_not_other_attractive_points",
        "risk_of_change",
        "related_files",
        "anti_js",
    ]
    compact = {key: payload[key] for key in keys}
    compact["after_metrics"] = {
        payload["best_variant"]: payload["after_metrics"][payload["best_variant"]]
    }
    compact["selection"] = payload["selection"][payload["best_variant"]]
    return compact


def persist(payload: dict[str, Any]) -> None:
    parent = _parent()
    parent._write_json(OUT_JSON, payload)
    compact = _compact_log(payload)
    parent._write_json(LOG_JSON, compact)
    parent._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Event state-rank quality",
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
    lines.append(json.dumps(parent._safe(compact), sort_keys=True))
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
