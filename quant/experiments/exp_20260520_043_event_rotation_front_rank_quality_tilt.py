"""exp-20260520-043: event-rotation front-rank quality tilt.

Alpha search, replay-only. Tests one production-visible event-quality field
inside the current event-rotation replacement-value lane: whether top-quintile
state-ranked rotation_breakout_leadership event rows deserve extra paper
notional on top of the revalidated 3.0x rotation baseline.

No JavaScript is used. No live orders, default backtest behavior, core A/B
ranking, sizing, exits, add-ons, LLM, or news behavior are changed.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260520_042_event_rotation_alpha_direction_revalidation as current


EXPERIMENT_ID = "exp-20260520-043"
EXPERIMENT_SLUG = "event_rotation_front_rank_quality_tilt"

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

BASELINE_VARIANT = "event_rotation_300_baseline"
TARGET_SURFACE = "rotation_breakout_leadership"
FRONT_RANK_MAX_PCT = 0.20

VARIANTS: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "description": (
                    "Revalidated exp-20260520-042 event-rotation baseline: "
                    "3.0x for all eligible rotation-breakout leadership rows; "
                    "2.0x for other positive non-generic event surfaces."
                ),
                "default_scalar": 1.0,
                "eligible_non_rotation_scalar": 2.0,
                "rotation_other_rank_scalar": 3.0,
                "front_rank_rotation_scalar": 3.0,
            },
        ),
        (
            "front_rank_rotation_325",
            {
                "description": (
                    "3.25x only for top-quintile state-ranked rotation rows; "
                    "other eligible rotation rows stay at 3.0x."
                ),
                "default_scalar": 1.0,
                "eligible_non_rotation_scalar": 2.0,
                "rotation_other_rank_scalar": 3.0,
                "front_rank_rotation_scalar": 3.25,
            },
        ),
        (
            "front_rank_rotation_350",
            {
                "description": (
                    "3.50x only for top-quintile state-ranked rotation rows; "
                    "other eligible rotation rows stay at 3.0x."
                ),
                "default_scalar": 1.0,
                "eligible_non_rotation_scalar": 2.0,
                "rotation_other_rank_scalar": 3.0,
                "front_rank_rotation_scalar": 3.5,
            },
        ),
        (
            "front_rank_rotation_400",
            {
                "description": (
                    "4.00x only for top-quintile state-ranked rotation rows; "
                    "included to test materiality and concentration guardrails."
                ),
                "default_scalar": 1.0,
                "eligible_non_rotation_scalar": 2.0,
                "rotation_other_rank_scalar": 3.0,
                "front_rank_rotation_scalar": 4.0,
            },
        ),
    ]
)


def _parent():
    return current.prev.prior._parent()


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _round(value: Any, digits: int = 6) -> Any:
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _configure_modules() -> None:
    current._configure_modules()


def _is_front_rank_rotation(trade: dict[str, Any]) -> bool:
    parent = _parent()
    rank_pct = _round(trade.get("state_rank_pct"), 6)
    return (
        parent._eligible_non_generic_positive(trade)
        and str(trade.get("state_surface") or "") == TARGET_SURFACE
        and rank_pct is not None
        and rank_pct <= FRONT_RANK_MAX_PCT
    )


def _surface_scalar(trade: dict[str, Any], variant: dict[str, Any]) -> float:
    parent = _parent()
    if not parent._eligible_non_generic_positive(trade):
        return float(variant["default_scalar"])
    if str(trade.get("state_surface") or "") != TARGET_SURFACE:
        return float(variant["eligible_non_rotation_scalar"])
    if _is_front_rank_rotation(trade):
        return float(variant["front_rank_rotation_scalar"])
    return float(variant["rotation_other_rank_scalar"])


def _scaled_trade(
    trade: dict[str, Any],
    variant_name: str,
    variant: dict[str, Any],
) -> dict[str, Any]:
    parent = _parent()
    scalar = _surface_scalar(trade, variant)
    base_notional = float(trade.get("notional") or parent.base.EVENT_NOTIONAL)
    base_shares = float(trade.get("shares") or 0.0)
    return {
        **trade,
        "variant": variant_name,
        "front_rank_rotation_target": _is_front_rank_rotation(trade),
        "front_rank_max_pct": FRONT_RANK_MAX_PCT,
        "state_surface_scalar": round(scalar, 4),
        "base_notional": round(base_notional, 2),
        "notional": round(base_notional * scalar, 2),
        "shares": base_shares * scalar,
        "pnl": round(float(trade.get("pnl") or 0.0) * scalar, 2),
    }


def _max_positive_share(values: list[float]) -> float | None:
    positive = [value for value in values if value > 0]
    total = sum(positive)
    if total <= 0:
        return None
    return round(max(positive) / total, 4)


def _selection_summary(
    raw_by_window: dict[str, list[dict[str, Any]]],
    scaled_by_window: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    parent = _parent()
    raw_rows = [trade for trades in raw_by_window.values() for trade in trades]
    scaled_rows = [trade for trades in scaled_by_window.values() for trade in trades]
    target_raw = [trade for trade in raw_rows if _is_front_rank_rotation(trade)]
    target_scaled = [trade for trade in scaled_rows if trade.get("front_rank_rotation_target")]
    rotation_scaled = [
        trade
        for trade in scaled_rows
        if parent._eligible_non_generic_positive(trade)
        and str(trade.get("state_surface") or "") == TARGET_SURFACE
    ]

    by_window: dict[str, Any] = OrderedDict()
    for label, rows in raw_by_window.items():
        target = [trade for trade in rows if _is_front_rank_rotation(trade)]
        by_window[label] = {
            "trade_count": len(target),
            "wins": sum(1 for trade in target if float(trade.get("pnl") or 0.0) > 0),
            "total_pnl": round(
                sum(float(trade.get("pnl") or 0.0) for trade in target),
                2,
            ),
            "tickers": sorted({str(trade.get("ticker") or "") for trade in target}),
        }

    return {
        "target_surface": TARGET_SURFACE,
        "front_rank_max_pct": FRONT_RANK_MAX_PCT,
        "target_trade_count": len(target_raw),
        "target_windows_present": sum(1 for row in by_window.values() if row["trade_count"] > 0),
        "target_tickers": sorted({str(trade.get("ticker") or "") for trade in target_raw}),
        "target_wins": sum(1 for trade in target_raw if float(trade.get("pnl") or 0.0) > 0),
        "target_win_rate": round(
            sum(1 for trade in target_raw if float(trade.get("pnl") or 0.0) > 0)
            / len(target_raw),
            4,
        )
        if target_raw
        else None,
        "target_unscaled_total_pnl": round(
            sum(float(trade.get("pnl") or 0.0) for trade in target_raw),
            2,
        ),
        "target_scaled_total_pnl": round(
            sum(float(trade.get("pnl") or 0.0) for trade in target_scaled),
            2,
        ),
        "target_by_window": by_window,
        "target_max_single_positive_pnl_share": _max_positive_share(
            [float(trade.get("pnl") or 0.0) for trade in target_scaled]
        ),
        "rotation_surface_scaled_total_pnl": round(
            sum(float(trade.get("pnl") or 0.0) for trade in rotation_scaled),
            2,
        ),
        "rotation_max_single_positive_pnl_share": _max_positive_share(
            [float(trade.get("pnl") or 0.0) for trade in rotation_scaled]
        ),
    }


def _gate_vs_baseline(
    baseline_metrics: dict[str, dict[str, Any]],
    after_metrics: dict[str, dict[str, Any]],
    selection: dict[str, Any],
) -> dict[str, Any]:
    gate = _parent().base._gate_summary(baseline_metrics, after_metrics)
    sample_ok = (
        (selection.get("target_trade_count") or 0) >= 3
        and (selection.get("target_windows_present") or 0) >= 2
        and len(selection.get("target_tickers") or []) >= 3
        and (
            selection.get("target_max_single_positive_pnl_share") is None
            or selection["target_max_single_positive_pnl_share"] <= 0.60
        )
        and (
            selection.get("rotation_max_single_positive_pnl_share") is None
            or selection["rotation_max_single_positive_pnl_share"] <= 0.55
        )
    )
    return {
        **gate,
        "sample_guard_passed": bool(sample_ok),
        "passed": bool(gate["passed"] and sample_ok),
        "sample_guard": {
            "min_target_trades": 3,
            "min_target_windows": 2,
            "min_target_tickers": 3,
            "max_target_positive_pnl_share": 0.60,
            "max_rotation_positive_pnl_share": 0.55,
            "actual_target_trades": selection.get("target_trade_count"),
            "actual_target_windows": selection.get("target_windows_present"),
            "actual_target_tickers": selection.get("target_tickers"),
            "actual_target_max_single_positive_pnl_share": selection.get(
                "target_max_single_positive_pnl_share"
            ),
            "actual_rotation_max_single_positive_pnl_share": selection.get(
                "rotation_max_single_positive_pnl_share"
            ),
        },
    }


def _choose_best(
    gates: dict[str, dict[str, Any]],
    variant_metrics: dict[str, dict[str, dict[str, Any]]],
) -> str:
    names = [name for name in VARIANTS if name != BASELINE_VARIANT]
    passed = [name for name in names if gates[name]["passed"]]
    candidates = passed if passed else names
    return max(
        candidates,
        key=lambda name: (
            gates[name]["delta"]["after_ev_sum"],
            gates[name]["delta"]["after_pnl_sum"],
            variant_metrics[name]["late_strong"]["expected_value_score"],
        ),
    )


def build_payload() -> dict[str, Any]:
    _configure_modules()
    parent = _parent()
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    raw_event_trades, source_coverage, prices = parent.base._load_event_trades()
    event_trades = parent.base._enrich_event_trades(raw_event_trades)

    core_metrics: dict[str, dict[str, Any]] = OrderedDict()
    variant_metrics: dict[str, dict[str, dict[str, Any]]] = OrderedDict(
        (name, OrderedDict()) for name in VARIANTS
    )
    variant_events: dict[str, dict[str, list[dict[str, Any]]]] = OrderedDict(
        (name, OrderedDict()) for name in VARIANTS
    )

    for label, window in parent.base.WINDOWS.items():
        result = parent.base._load_core_result(window)
        core_metrics[label] = parent.base._core_metrics(result)
        for name, variant in VARIANTS.items():
            scaled = [_scaled_trade(trade, name, variant) for trade in event_trades[label]]
            curve = parent.base._event_equity_curve(
                scaled,
                prices=prices,
                start=window["start"],
                end=window["end"],
            )
            variant_metrics[name][label] = parent.base._combined_metrics(
                result,
                curve,
                scaled,
            )
            variant_events[name][label] = scaled

    baseline_metrics = variant_metrics[BASELINE_VARIANT]
    selection_by_variant = OrderedDict(
        (
            name,
            _selection_summary(event_trades, variant_events[name]),
        )
        for name in VARIANTS
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
    best_variant = _choose_best(gates_vs_baseline, variant_metrics)
    best_gate = gates_vs_baseline[best_variant]
    accepted = bool(best_gate["passed"])
    decision = (
        "promising_replay_only_front_rank_event_rotation_quality_tilt"
        if accepted
        else "rejected_front_rank_event_rotation_quality_tilt"
    )
    rejection_reason = None
    if not accepted:
        rejection_reason = (
            f"Best variant `{best_variant}` did not clear Gate 4 versus the "
            f"3.0x event-rotation baseline: EV delta "
            f"{best_gate['delta']['aggregate_ev_delta']}, PnL delta "
            f"{best_gate['delta']['aggregate_pnl_delta']}, EV improved/regressed "
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
        "change_type": "event_rotation_quality_allocation_replay",
        "mechanism_family": "external_event_satellite_overlay_allocation",
        "trial_family": "event_rotation_replacement_value_maturation",
        "trial_variant_id": "front_rank_quality_tilt",
        "changed_variable": "front_rank_rotation_event_paper_notional_tilt",
        "prior_trial_count": 9,
        "nearby_prior_experiments": [
            "exp-20260516-013",
            "exp-20260516-028",
            "exp-20260516-030",
            "exp-20260516-040",
            "exp-20260516-044",
            "exp-20260517-001",
            "exp-20260517-010",
            "exp-20260520-042",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_production_visible_field_on_event_rotation_rows",
        "hypothesis": (
            "Within the event-rotation replacement-value lane, "
            "rotation_breakout_leadership rows that rank in the top quintile of "
            "the same-day state surface may deserve more paper notional than "
            "lower-ranked rotation rows, because top-ranked rows express cleaner "
            "cross-sectional leadership rather than weaker event coincidence."
        ),
        "alpha_hypothesis": {
            "category": "capital allocation / event-quality",
            "entry_exit_ranking_or_allocation": "capital allocation",
            "playbook_alignment": (
                "Uses a production-visible field inside the preferred "
                "event-rotation replacement-value lane and avoids state-surface "
                "or broad-market nearby scalar retunes."
            ),
        },
        "single_causal_variable": (
            "extra paper-notional scalar for rotation_breakout_leadership event "
            "rows with state_rank_pct <= 0.20"
        ),
        "parameters": {
            "variants": VARIANTS,
            "acceptance_baseline": BASELINE_VARIANT,
            "baseline_experiment": "exp-20260520-042",
            "target_surface": TARGET_SURFACE,
            "front_rank_max_pct": FRONT_RANK_MAX_PCT,
            "base_event_notional_usd": parent.base.EVENT_NOTIONAL,
            "hold_days": parent.base.HOLD_DAYS,
            "round_trip_cost_pct": parent.base.ROUND_TRIP_COST_PCT,
            "sample_guard": {
                "min_target_trades": 3,
                "min_target_windows": 2,
                "min_target_tickers": 3,
                "max_target_positive_pnl_share": 0.60,
                "max_rotation_positive_pnl_share": 0.55,
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
                "non-rotation event surface scalar",
                "non-target rotation event scalar",
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
                "Event-rotation replacement value remains the best current alpha "
                "direction; this tests a top-quintile state-rank quality field "
                "inside that lane."
            ),
            "2_history_check": (
                "All-source rotation tilt repeatedly passed; source-specific "
                "negative-reaction tilt was rejected in exp-20260516-030 for "
                "thin/materiality risk. exp-20260520-042 revalidated the lane "
                "after recent LLM/SEC/broad-market/state-surface/core-pool "
                "failures."
            ),
            "3_single_causal_variable": (
                "Only the top-quintile state-rank event-rotation notional scalar "
                "changes; baseline rotation rows stay at 3.0x."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; compare to the 3.0x "
                "event-rotation baseline, require aggregate EV/PnL improvement, "
                "no EV-regressed windows, materiality under the event gate, and "
                "sample/concentration guards."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260520_043_event_rotation_front_rank_quality_tilt.py"
            ),
        },
        "historical_experiment_check": {
            "exp-20260520-042": (
                "Revalidated event rotation as the next alpha direction versus "
                "recent blocked/rejected lanes, with +0.5389 EV and +$7,987.90 "
                "versus the 2.0x non-generic event lead."
            ),
            "exp-20260516-030": (
                "Rejected source-specific sec_negative_reaction tilt; this run "
                "uses state-rank quality instead of source identity."
            ),
            "recent_avoided_branches": (
                "Skipped LLM soft-ranking, SEC fact-tone/buyback, broad-market "
                "forward, state-surface scalar/profile retunes, single-ticker "
                "core promotions, DTE risk patches, and ETF selector variants "
                "because recent logs mark those branches blocked or rejected."
            ),
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
            "baseline_artifact": "data/experiments/exp-20260520-042/event_rotation_alpha_direction_revalidation.json",
        },
        "gate2": {
            "required_fields": [
                "event source",
                "ticker",
                "entry_date",
                "exit_date",
                "pnl",
                "state_feature_available",
                "state_score_positive",
                "state_surface",
                "state_rank_pct",
            ],
            "selection": selection_by_variant[BASELINE_VARIANT],
            "passed": bool(
                (selection_by_variant[BASELINE_VARIANT].get("target_trade_count") or 0) >= 3
                and (
                    selection_by_variant[BASELINE_VARIANT].get("target_windows_present")
                    or 0
                )
                >= 2
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
                "against the exp-20260520-042 3.0x event-rotation baseline."
            ),
        },
        "before_metrics": {
            "core": core_metrics,
            BASELINE_VARIANT: baseline_metrics,
        },
        "after_metrics": variant_metrics,
        "delta_metrics": {
            "variant_vs_event_rotation_300": gates_vs_baseline,
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
            "promotion_blocker_if_positive": (
                "Before live/default capital, add the field to the shared "
                "default-off event adapter, add parity tests, and collect closed "
                "forward replacement-value evidence."
            ),
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM soft-ranking remains attribution/sample-limited; this uses "
                "deterministic PIT event and state-rank fields only."
            ),
        },
        "decision_rationale": (
            "Accepted as replay-only front-rank event-rotation quality evidence; "
            "no live/default orders change until shared adapter and forward "
            "replacement outcomes exist."
            if accepted
            else rejection_reason
        ),
        "rejection_reason": rejection_reason,
        "next_action": (
            "Keep replay-only; next valid step is shared adapter parity plus "
            "forward replacement-value evidence."
            if accepted
            else "Do not retry nearby front-rank event-rotation scalars on the frozen sample without new forward event evidence."
        ),
        "why_not_other_attractive_points": (
            "Skipped LLM/SEC/broad-market/state-surface/core-pool/DTE/ETF lanes "
            "because the latest log marks them blocked, sample-limited, or "
            "rejected; this is the narrowest production-visible event-quality "
            "test in the strongest remaining lane."
        ),
        "risk_of_change": (
            "The target set has only three historical paper trades across two "
            "windows, so any positive result remains replay-only and cannot "
            "justify live/default capital without forward outcomes."
        ),
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(EXPERIMENT_LOG),
        ],
    }


def _artifact_markdown(payload: dict[str, Any]) -> str:
    best = payload["best_variant"]
    gate = payload["delta_metrics"]["variant_vs_event_rotation_300"][best]
    baseline = payload["before_metrics"][BASELINE_VARIANT]
    after = payload["after_metrics"][best]
    lines = [
        f"# {EXPERIMENT_ID} Event-Rotation Front-Rank Quality Tilt",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        (
            "Alpha search, replay-only. Tests whether top-quintile "
            "`state_rank_pct` event-rotation rows deserve extra paper notional "
            "on top of the 3.0x event-rotation baseline."
        ),
        "",
        "## Gate 4 Result",
        "",
        "| Window | Baseline EV | Variant EV | Delta EV | Baseline PnL | Variant PnL | Delta PnL |",
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

    sweep_rows = [
        "| Variant | Passed | dEV | dPnL | Improved | Regressed | Target trades | Windows | Target max share | Rotation max share |",
        "|---|:---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, row in payload["delta_metrics"]["variant_vs_event_rotation_300"].items():
        selection = payload["selection"][name]
        sweep_rows.append(
            "| {name} | {passed} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {trades} | {windows} | {target_share} | {rotation_share} |".format(
                name=name,
                passed="yes" if row["passed"] else "no",
                dev=row["delta"]["aggregate_ev_delta"],
                dpnl=row["delta"]["aggregate_pnl_delta"],
                improved=row["delta"]["windows_ev_improved"],
                regressed=row["delta"]["windows_ev_regressed"],
                trades=selection["target_trade_count"],
                windows=selection["target_windows_present"],
                target_share=selection["target_max_single_positive_pnl_share"],
                rotation_share=selection["rotation_max_single_positive_pnl_share"],
            )
        )

    lines.extend(
        [
            "",
            "## Sweep",
            "",
            *sweep_rows,
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
                "Replay only. Core backtest behavior and production order paths "
                "are unchanged. A live/default version would require shared "
                "adapter parity plus closed forward replacement-value evidence."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def _compact_log(payload: dict[str, Any]) -> dict[str, Any]:
    best = payload["best_variant"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": payload["lane"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis": payload["alpha_hypothesis"],
        "single_causal_variable": payload["single_causal_variable"],
        "parameters": payload["parameters"],
        "date_range": payload["date_range"],
        "market_regime_summary": payload["market_regime_summary"],
        "gate_questions": payload["gate_questions"],
        "historical_experiment_check": payload["historical_experiment_check"],
        "backtest_protocol": payload["backtest_protocol"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": {best: payload["after_metrics"][best]},
        "delta_metrics": payload["delta_metrics"],
        "best_variant": best,
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "selection": payload["selection"][best],
        "production_impact": payload["production_impact"],
        "llm_metrics": payload["llm_metrics"],
        "decision_rationale": payload["decision_rationale"],
        "rejection_reason": payload["rejection_reason"],
        "next_action": payload["next_action"],
        "why_not_other_attractive_points": payload["why_not_other_attractive_points"],
        "risk_of_change": payload["risk_of_change"],
        "related_files": payload["related_files"],
        "anti_js": "No JavaScript was used.",
    }


def persist(payload: dict[str, Any]) -> None:
    parent = _parent()
    parent._write_json(OUT_JSON, payload)
    compact = _compact_log(payload)
    parent._write_json(LOG_JSON, compact)
    parent._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Event-rotation front-rank quality tilt",
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
    best = payload["best_variant"]
    gate = payload["delta_metrics"]["variant_vs_event_rotation_300"][best]
    print(
        json.dumps(
            _parent()._safe(
                {
                    "experiment_id": EXPERIMENT_ID,
                    "decision": payload["decision"],
                    "best_variant": best,
                    "ev_delta_vs_baseline": gate["delta"]["aggregate_ev_delta"],
                    "pnl_delta_vs_baseline": gate["delta"]["aggregate_pnl_delta"],
                    "windows_ev_improved": gate["delta"]["windows_ev_improved"],
                    "windows_ev_regressed": gate["delta"]["windows_ev_regressed"],
                    "sample_guard_passed": gate["sample_guard_passed"],
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
