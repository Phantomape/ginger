"""exp-20260521-011: event mixed-breadth context scout.

Alpha search, replay-only. Tests one production-visible event context field on
top of the accepted exp-20260521-009 default-off event overlay adapter: whether
mixed-breadth event rows deserve a lower or higher paper-notional scalar.

No JavaScript is used. No shared policy, production adapter, core behavior,
LLM/news behavior, source capacity, or live/default orders are changed.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260521_010_event_governance_semantic_cell as exp010


EXPERIMENT_ID = "exp-20260521-011"
EXPERIMENT_SLUG = "event_mixed_breadth_context"

REPO_ROOT = exp010.REPO_ROOT
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

BASELINE_VARIANT = "accepted_event_negative_reaction_context_adapter"
TARGET_BREADTH_BUCKET = "mixed_breadth"

VARIANTS: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "description": "Accepted exp-20260521-009 event adapter.",
                "mixed_breadth_context_scalar": 1.0,
            },
        ),
        (
            "mixed_breadth_context_050",
            {
                "description": "0.50x paper notional for mixed-breadth event rows.",
                "mixed_breadth_context_scalar": 0.50,
            },
        ),
        (
            "mixed_breadth_context_075",
            {
                "description": "0.75x paper notional for mixed-breadth event rows.",
                "mixed_breadth_context_scalar": 0.75,
            },
        ),
        (
            "mixed_breadth_context_090",
            {
                "description": "0.90x paper notional for mixed-breadth event rows.",
                "mixed_breadth_context_scalar": 0.90,
            },
        ),
        (
            "mixed_breadth_context_110",
            {
                "description": "1.10x paper notional for mixed-breadth event rows.",
                "mixed_breadth_context_scalar": 1.10,
            },
        ),
        (
            "mixed_breadth_context_125",
            {
                "description": "1.25x paper notional for mixed-breadth event rows.",
                "mixed_breadth_context_scalar": 1.25,
            },
        ),
    ]
)


def _parent():
    return exp010._parent()


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _configure_modules() -> None:
    exp010._configure_modules()


def _is_target_mixed_breadth(trade: dict[str, Any]) -> bool:
    return str(trade.get("breadth_bucket") or "") == TARGET_BREADTH_BUCKET


def _scaled_trade(
    trade: dict[str, Any],
    variant_name: str,
    variant: dict[str, Any],
) -> dict[str, Any]:
    parent = _parent()
    accepted_scalar = exp010._accepted_event_scalar_after_exp009(trade)
    target = _is_target_mixed_breadth(trade)
    breadth_scalar = (
        float(variant["mixed_breadth_context_scalar"]) if target else 1.0
    )
    scalar = accepted_scalar * breadth_scalar
    base_notional = float(trade.get("notional") or parent.base.EVENT_NOTIONAL)
    base_shares = float(trade.get("shares") or 0.0)
    return {
        **trade,
        "variant": variant_name,
        "accepted_event_scalar_after_exp009": round(accepted_scalar, 4),
        "mixed_breadth_context_target": target,
        "mixed_breadth_context_scalar": round(breadth_scalar, 4),
        "state_surface_scalar": round(scalar, 4),
        "base_notional": round(base_notional, 2),
        "notional": round(base_notional * scalar, 2),
        "shares": base_shares * scalar,
        "pnl": round(float(trade.get("pnl") or 0.0) * scalar, 2),
    }


def _selection_summary(rows_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    target_by_window: dict[str, Any] = OrderedDict()
    all_rows = [row for rows in rows_by_window.values() for row in rows]
    targets = [row for row in all_rows if row.get("mixed_breadth_context_target")]
    for label, rows in rows_by_window.items():
        window_targets = [
            row for row in rows if row.get("mixed_breadth_context_target")
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
            "state_surfaces": sorted(
                {str(row.get("state_surface") or "") for row in window_targets}
            ),
            "dispersion_buckets": sorted(
                {str(row.get("dispersion_bucket") or "") for row in window_targets}
            ),
        }
    return {
        "target_breadth_bucket": TARGET_BREADTH_BUCKET,
        "target_trade_count": len(targets),
        "target_windows_present": sum(
            1 for row in target_by_window.values() if row["trade_count"] > 0
        ),
        "target_tickers": sorted({str(row.get("ticker") or "") for row in targets}),
        "target_sources": sorted({str(row.get("source") or "") for row in targets}),
        "target_state_surfaces": sorted(
            {str(row.get("state_surface") or "") for row in targets}
        ),
        "target_dispersion_buckets": sorted(
            {str(row.get("dispersion_bucket") or "") for row in targets}
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
    sample_ok = (
        (selection.get("target_trade_count") or 0) >= 10
        and (selection.get("target_windows_present") or 0) >= 3
        and len(selection.get("target_tickers") or []) >= 6
        and (
            selection.get("target_max_single_positive_pnl_share") is None
            or selection["target_max_single_positive_pnl_share"] <= 0.45
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
            -abs(VARIANTS[name]["mixed_breadth_context_scalar"] - 1.0),
        ),
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
        "accepted_default_off_event_mixed_breadth_context"
        if accepted
        else "rejected_event_mixed_breadth_context"
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
            f"sample_guard_passed={best_gate['sample_guard_passed']}."
        )

    compact_after_metrics = OrderedDict(
        (name, exp010._compact_metrics_by_window(metrics))
        for name, metrics in variant_metrics.items()
    )
    variant_gates = exp010._compact_variant_gates(gates_vs_baseline)
    compact_parameters = {
        "acceptance_baseline": BASELINE_VARIANT,
        "baseline_experiment": "exp-20260521-009",
        "target_breadth_bucket": TARGET_BREADTH_BUCKET,
        "selected_mixed_breadth_context_scalar": VARIANTS[best_variant][
            "mixed_breadth_context_scalar"
        ],
        "variant_scalars": {
            name: row["mixed_breadth_context_scalar"] for name, row in VARIANTS.items()
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
        "anti_js": "No JavaScript was used.",
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "change_type": "event_context_allocation_replay",
        "mechanism_family": "external_event_satellite_overlay_allocation",
        "trial_family": "event_breadth_context_quality",
        "trial_variant_id": "mixed_breadth_notional_scalar",
        "changed_variable": "event_mixed_breadth_context_scalar",
        "prior_trial_count": 9,
        "nearby_prior_experiments": [
            "exp-20260521-001",
            "exp-20260521-002",
            "exp-20260521-003",
            "exp-20260521-006",
            "exp-20260521-009",
            "exp-20260521-010",
        ],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "new_event_context_bucket_after_negative_reaction_adapter",
        "hypothesis": (
            "Inside the accepted default-off event overlay, mixed-breadth event "
            "rows may represent a lower-quality or concentration-prone context "
            "than broad-breadth rows. A single paper-notional scalar sweep can "
            "test whether de-emphasizing or modestly emphasizing this context "
            "improves replacement value without changing core trades."
        ),
        "alpha_hypothesis": {
            "category": "capital allocation / event context scoring",
            "entry_exit_ranking_or_allocation": "capital allocation",
            "playbook_alignment": (
                "Uses a production-visible event breadth context in the event "
                "replacement-value lane, after LLM soft-ranking and SEC fact-tone "
                "remain sample/provenance limited."
            ),
        },
        "single_causal_variable": (
            "paper-notional scalar for event overlay rows with breadth_bucket "
            "mixed_breadth; event definitions, source capacity, accepted reaction "
            "scalars, hold period, and core strategy stay fixed"
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
                "Mixed-breadth event rows may carry different replacement value "
                "than broad-breadth rows; this is event context scoring plus "
                "capital allocation."
            ),
            "2_history_check": (
                "Broad-breadth context was accepted in exp-20260521-001; high "
                "dispersion, source capacity, negative phrase, negative reaction, "
                "and governance semantic-cell scouts were already tested. This "
                "run uses a different production-visible breadth bucket on top "
                "of the accepted exp-20260521-009 baseline."
            ),
            "3_single_causal_variable": (
                "Only the paper-notional scalar for fixed mixed_breadth event "
                "rows changes."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; compare against the "
                "accepted exp-20260521-009 event adapter baseline, require "
                "aggregate EV/PnL improvement, zero EV-regressed windows, sample "
                "guard pass, and no production/backtest divergence."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260521_011_event_mixed_breadth_context.py"
            ),
        },
        "historical_experiment_check": {
            "exp-20260521-001": "Accepted broad-breadth event context adapter; this does not retune that scalar.",
            "exp-20260521-002": "Rejected high-dispersion context due old_thin regression.",
            "exp-20260521-003": "Rejected source capacity due EV regression and concentration guard.",
            "exp-20260521-009": "Accepted negative-reaction context adapter; current event baseline.",
            "exp-20260521-010": "Rejected governance shareholder-vote semantic-cell scout.",
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
            "baseline_artifact": "data/experiments/exp-20260521-009/event_negative_reaction_context_adapter.json",
        },
        "gate2": {
            "required_fields": [
                "event source",
                "ticker",
                "entry_date",
                "exit_date",
                "pnl",
                "breadth_bucket",
                "state_surface",
                "dispersion_bucket",
            ],
            "operator_position_field_check": operator_check,
            "selection": selection_by_variant[BASELINE_VARIANT],
            "passed": bool(
                operator_check["passed"]
                and selection_by_variant[BASELINE_VARIANT]["target_trade_count"] > 0
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
                "against the accepted exp-20260521-009 event adapter baseline."
            ),
        },
        "before_metrics": {
            BASELINE_VARIANT: exp010._compact_metrics_by_window(baseline_metrics),
            "core": exp010._compact_metrics_by_window(core_metrics),
        },
        "after_metrics": {best_variant: compact_after_metrics[best_variant]},
        "delta_metrics": {
            "variant_vs_accepted_event_negative_reaction_context_adapter": variant_gates
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
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM soft-ranking remains attribution/sample-limited; this uses "
                "deterministic event breadth context fields only."
            ),
        },
        "decision_rationale": (
            "Accepted as default-off only."
            if accepted
            else "Rejected: mixed-breadth scalar did not clear the three-window and sample guard."
        ),
        "rejection_reason": rejection_reason,
        "next_action": (
            "Do not retry mixed-breadth notional scalars on the frozen sample "
            "without new forward rows or a less concentrated target cohort."
        ),
        "why_not_other_attractive_points": (
            "Skipped LLM soft-ranking due attribution limits; skipped "
            "state-surface and broad-market nearby retunes due anti-repeat "
            "rules; skipped high-dispersion and source-capacity retests after "
            "recent Gate 4 failures; SEC fact-tone remains provenance-limited."
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
        f"# {EXPERIMENT_ID} Event Mixed-Breadth Context",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        (
            "Alpha search, replay-only. Tests whether selected mixed-breadth "
            "event rows deserve a different paper-notional scalar on top of "
            "the accepted event adapter."
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
            "| Variant | Passed | Sample Guard | dEV | dPnL | Improved | Regressed | Target trades | Windows | Max positive share |",
            "|---|:---:|:---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for name, row in payload["delta_metrics"][
        "variant_vs_accepted_event_negative_reaction_context_adapter"
    ].items():
        lines.append(
            "| {name} | {passed} | {sample} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {trades} | {windows} | {share} |".format(
                name=name,
                passed="yes" if row["passed"] else "no",
                sample="yes" if row["sample_guard_passed"] else "no",
                dev=row["aggregate_ev_delta"],
                dpnl=row["aggregate_pnl_delta"],
                improved=row["windows_ev_improved"],
                regressed=row["windows_ev_regressed"],
                trades=payload["selection"]["target_trade_count"],
                windows=payload["selection"]["target_windows_present"],
                share=payload["selection"]["target_max_single_positive_pnl_share"],
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
                "Replay only. No shared policy, adapter, production report, "
                "core behavior, source capacity, or live/default order path changed."
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
            "title": "Event mixed-breadth context scout",
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
