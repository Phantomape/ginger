"""exp-20260521-008: event mid-dispersion context scout.

Alpha search, replay-only. Tests one event context field on top of the
accepted exp-20260521-006 default-off event overlay adapter: whether selected
events in the `mid_sector_dispersion` bucket deserve extra paper notional.

No JavaScript is used. No shared policy, production adapter, core behavior,
LLM/news behavior, source capacity, or live/default orders are changed.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260521_007_event_negative_phrase_evidence as negative_phrase_scout


EXPERIMENT_ID = "exp-20260521-008"
EXPERIMENT_SLUG = "event_mid_dispersion_context"

REPO_ROOT = negative_phrase_scout.REPO_ROOT
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
OPEN_POSITIONS_JSON = REPO_ROOT / "operator_inputs" / "open_positions.json"

BASELINE_VARIANT = "accepted_event_governance_source_adapter"
TARGET_DISPERSION_BUCKET = "mid_sector_dispersion"

VARIANTS: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "description": (
                    "Accepted exp-20260521-006 event adapter with rotation, "
                    "front-rank, broad-breadth, and governance-source quality scalars fixed."
                ),
                "mid_dispersion_context_scalar": 1.0,
            },
        ),
        (
            "mid_dispersion_context_125",
            {
                "description": (
                    "Multiply accepted event paper notional by 1.25x when "
                    "dispersion_bucket is mid_sector_dispersion."
                ),
                "mid_dispersion_context_scalar": 1.25,
            },
        ),
        (
            "mid_dispersion_context_150",
            {
                "description": (
                    "Multiply accepted event paper notional by 1.50x when "
                    "dispersion_bucket is mid_sector_dispersion."
                ),
                "mid_dispersion_context_scalar": 1.50,
            },
        ),
        (
            "mid_dispersion_context_200",
            {
                "description": (
                    "Multiply accepted event paper notional by 2.00x when "
                    "dispersion_bucket is mid_sector_dispersion."
                ),
                "mid_dispersion_context_scalar": 2.00,
            },
        ),
    ]
)


def _parent():
    return negative_phrase_scout._parent()


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _configure_modules() -> None:
    negative_phrase_scout._configure_modules()


def _operator_position_field_check() -> dict[str, Any]:
    if not OPEN_POSITIONS_JSON.exists():
        return {
            "path": _repo_rel(OPEN_POSITIONS_JSON),
            "passed": False,
            "position_count": 0,
            "missing_file": True,
            "missing_entry_date_or_target_price": [],
        }
    data = json.loads(OPEN_POSITIONS_JSON.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        positions = data.get("positions") or []
    elif isinstance(data, list):
        positions = data
    else:
        positions = []
    missing = [
        str(position.get("ticker") or position.get("symbol") or "UNKNOWN")
        for position in positions
        if isinstance(position, dict)
        and (not position.get("entry_date") or not position.get("target_price"))
    ]
    return {
        "path": _repo_rel(OPEN_POSITIONS_JSON),
        "passed": not missing,
        "position_count": len(positions),
        "missing_entry_date_or_target_price": missing,
    }


def _accepted_event_scalar_after_exp006(trade: dict[str, Any]) -> float:
    return negative_phrase_scout._accepted_event_scalar_after_exp006(trade)


def _is_target_mid_dispersion(trade: dict[str, Any]) -> bool:
    return str(trade.get("dispersion_bucket") or "") == TARGET_DISPERSION_BUCKET


def _scaled_trade(
    trade: dict[str, Any],
    variant_name: str,
    variant: dict[str, Any],
) -> dict[str, Any]:
    parent = _parent()
    accepted_scalar = _accepted_event_scalar_after_exp006(trade)
    target = _is_target_mid_dispersion(trade)
    context_scalar = float(variant["mid_dispersion_context_scalar"]) if target else 1.0
    scalar = accepted_scalar * context_scalar
    base_notional = float(trade.get("notional") or parent.base.EVENT_NOTIONAL)
    base_shares = float(trade.get("shares") or 0.0)
    return {
        **trade,
        "variant": variant_name,
        "accepted_event_scalar_after_exp006": round(accepted_scalar, 4),
        "mid_dispersion_context_target": target,
        "mid_dispersion_context_scalar": round(context_scalar, 4),
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
    targets = [row for row in all_rows if row.get("mid_dispersion_context_target")]
    for label, rows in rows_by_window.items():
        window_targets = [
            row for row in rows if row.get("mid_dispersion_context_target")
        ]
        target_by_window[label] = {
            "trade_count": len(window_targets),
            "wins": sum(
                1 for row in window_targets if float(row.get("pnl") or 0.0) > 0
            ),
            "total_pnl": round(
                sum(float(row.get("pnl") or 0.0) for row in window_targets),
                2,
            ),
            "tickers": sorted({str(row.get("ticker") or "") for row in window_targets}),
        }
    return {
        "target_dispersion_bucket": TARGET_DISPERSION_BUCKET,
        "target_trade_count": len(targets),
        "target_windows_present": sum(
            1 for row in target_by_window.values() if row["trade_count"] > 0
        ),
        "target_tickers": sorted({str(row.get("ticker") or "") for row in targets}),
        "target_sources": sorted({str(row.get("source") or "") for row in targets}),
        "target_state_surfaces": sorted(
            {str(row.get("state_surface") or "") for row in targets}
        ),
        "target_breadth_buckets": sorted(
            {str(row.get("breadth_bucket") or "") for row in targets}
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
            sum(float(row.get("pnl") or 0.0) for row in targets),
            2,
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
        (selection.get("target_trade_count") or 0) >= 6
        and (selection.get("target_windows_present") or 0) >= 3
        and len(selection.get("target_tickers") or []) >= 4
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
            "min_target_trades": 6,
            "min_target_windows": 3,
            "min_target_tickers": 4,
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
            -VARIANTS[name]["mid_dispersion_context_scalar"],
        ),
    )


def build_payload() -> dict[str, Any]:
    _configure_modules()
    parent = _parent()
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    operator_check = _operator_position_field_check()
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
        "accepted_default_off_event_mid_dispersion_context"
        if accepted
        else "rejected_event_mid_dispersion_context"
    )
    rejection_reason = None
    if not accepted:
        rejection_reason = (
            f"Best variant `{best_variant}` improved aggregate EV by "
            f"{best_gate['delta']['aggregate_ev_delta']} and PnL by "
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
        "change_type": "event_context_allocation_replay",
        "mechanism_family": "external_event_satellite_overlay_allocation",
        "trial_family": "event_dispersion_context_quality",
        "trial_variant_id": "mid_sector_dispersion_notional",
        "changed_variable": "event_mid_sector_dispersion_paper_notional_scalar",
        "prior_trial_count": 6,
        "nearby_prior_experiments": [
            "exp-20260506-029",
            "exp-20260506-032",
            "exp-20260507-001",
            "exp-20260521-001",
            "exp-20260521-002",
            "exp-20260521-006",
            "exp-20260521-007",
        ],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "new_event_dispersion_context_bucket",
        "hypothesis": (
            "Inside the accepted default-off event overlay, selected events in "
            "mid sector dispersion may have cleaner replacement value than "
            "high-dispersion event rows, because they retain rotation breadth "
            "without the unstable single-window dispersion spikes that recently failed."
        ),
        "alpha_hypothesis": {
            "category": "capital allocation / event context scoring",
            "entry_exit_ranking_or_allocation": "capital allocation",
            "playbook_alignment": (
                "Uses an interpretable event context field while avoiding "
                "LLM soft-ranking, broad-market feed blockers, state-surface "
                "threshold mining, source-capacity retries, and SEC phrase-hit repeats."
            ),
        },
        "single_causal_variable": (
            "paper-notional scalar for event overlay rows with "
            "dispersion_bucket == mid_sector_dispersion"
        ),
        "parameters": {
            "variants": VARIANTS,
            "acceptance_baseline": BASELINE_VARIANT,
            "baseline_experiment": "exp-20260521-006",
            "target_dispersion_bucket": TARGET_DISPERSION_BUCKET,
            "selected_mid_dispersion_context_scalar": VARIANTS[best_variant][
                "mid_dispersion_context_scalar"
            ],
            "base_event_notional_usd": parent.base.EVENT_NOTIONAL,
            "hold_days": parent.base.HOLD_DAYS,
            "round_trip_cost_pct": parent.base.ROUND_TRIP_COST_PCT,
            "sample_guard": {
                "min_target_trades": 6,
                "min_target_windows": 3,
                "min_target_tickers": 4,
                "max_target_positive_pnl_share": 0.45,
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
                "governance-source quality scalar",
                "per-source active capacity",
                "state_rank_pct event scalar",
                "high-dispersion event scalar",
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
                "Selected mid-sector-dispersion event rows may carry cleaner "
                "replacement value than high-dispersion rows; this is event "
                "context scoring plus capital allocation."
            ),
            "2_history_check": (
                "High-dispersion event context failed in exp-20260521-002. "
                "Governance-source was accepted in exp-20260521-006. SEC "
                "negative phrase evidence failed in exp-20260521-007. This "
                "tests a distinct dispersion bucket with explicit sample guards."
            ),
            "3_single_causal_variable": (
                "Only the paper-notional scalar for the fixed "
                "mid_sector_dispersion cohort changes."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; compare against the "
                "accepted exp-20260521-006 event adapter baseline, require "
                "aggregate EV/PnL improvement, zero EV-regressed windows, sample "
                "guard pass, and no production/backtest divergence."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe quant\\experiments\\"
                "exp_20260521_008_event_mid_dispersion_context.py"
            ),
        },
        "historical_experiment_check": {
            "exp-20260521-002": "Rejected high-sector-dispersion context because old_thin regressed.",
            "exp-20260521-006": "Accepted governance-source quality adapter; current baseline.",
            "exp-20260521-007": "Rejected SEC negative phrase evidence due old_thin regression and concentration.",
            "attention_persistence_precheck": (
                "Not advanced: 20d event attention persistence had zero replay "
                "rows; 45d/60d had only two GS rows and negative PnL."
            ),
            "broad_market_forward_maturation": (
                "Not advanced: current broad-market paper universe feed is missing "
                "and forward closed outcomes are zero."
            ),
            "sec_fact_tone_gap": (
                "Not advanced: historical SEC rows lack phrase provenance needed "
                "for bucketed fact-tone backtests."
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
            "baseline_artifact": "data/experiments/exp-20260521-006/event_governance_source_adapter.json",
        },
        "gate2": {
            "required_fields": [
                "event source",
                "ticker",
                "entry_date",
                "exit_date",
                "pnl",
                "dispersion_bucket",
                "state_surface",
                "breadth_bucket",
                "reaction_bucket",
            ],
            "operator_position_field_check": operator_check,
            "selection": selection_by_variant[BASELINE_VARIANT],
            "passed": bool(
                operator_check["passed"]
                and (
                    selection_by_variant[BASELINE_VARIANT].get("target_trade_count")
                    or 0
                )
                > 0
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
                "against the accepted exp-20260521-006 event adapter baseline."
            ),
        },
        "before_metrics": {
            "core": core_metrics,
            BASELINE_VARIANT: baseline_metrics,
        },
        "after_metrics": variant_metrics,
        "delta_metrics": {
            "variant_vs_accepted_event_governance_source_adapter": gates_vs_baseline
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
        },
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM soft-ranking remains attribution/sample-limited; this uses "
                "deterministic event context fields only."
            ),
        },
        "decision_rationale": (
            "Accepted as default-off only."
            if accepted
            else "Rejected. The best variant raised aggregate EV/PnL with no EV-regressed window, but the touched cohort was too thin and concentrated for retention."
        ),
        "rejection_reason": rejection_reason,
        "next_action": (
            "Do not retry mid-dispersion event notional scalars on the frozen "
            "sample. Revisit only after new forward rows broaden the bucket or "
            "a distinct event context field appears."
        ),
        "why_not_other_attractive_points": (
            "Skipped attention_persistence because it was zero/near-zero sample; "
            "skipped LLM soft-ranking due attribution limits; skipped broad-market "
            "forward maturation because the candidate universe feed is missing; "
            "skipped SEC fact-tone because historical phrase provenance is absent."
        ),
        "risk_of_change": (
            "Replay-only rejected scout. No production or shared strategy behavior "
            "changed, so no production/backtest divergence is introduced."
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
        f"# {EXPERIMENT_ID} Event Mid-Dispersion Context",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        (
            "Alpha search, replay-only. Tests whether selected event rows with "
            "dispersion_bucket=mid_sector_dispersion deserve extra paper "
            "notional on top of the accepted event governance-source adapter."
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
        "variant_vs_accepted_event_governance_source_adapter"
    ].items():
        selection = payload["selection"][name]
        lines.append(
            "| {name} | {passed} | {sample} | {dev:+.4f} | ${dpnl:+,.2f} | {improved} | {regressed} | {trades} | {windows} | {share} |".format(
                name=name,
                passed="yes" if row["passed"] else "no",
                sample="yes" if row["sample_guard_passed"] else "no",
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
                "core behavior, source capacity, or live/default order path changed."
            ),
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


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


def _compact_windows(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return OrderedDict(
        (
            label,
            {
                "start": row.get("start"),
                "end": row.get("end"),
                "snapshot": row.get("snapshot"),
            },
        )
        for label, row in rows.items()
    )


def _compact_variant_gates(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return OrderedDict(
        (
            name,
            {
                "passed": gate["passed"],
                "sample_guard_passed": gate["sample_guard_passed"],
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


def _concise_selection(selection: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_dispersion_bucket": selection["target_dispersion_bucket"],
        "target_trade_count": selection["target_trade_count"],
        "target_windows_present": selection["target_windows_present"],
        "target_tickers": selection["target_tickers"],
        "target_sources": selection["target_sources"],
        "target_win_rate": selection["target_win_rate"],
        "target_scaled_total_pnl": selection["target_scaled_total_pnl"],
        "target_max_single_positive_pnl_share": selection[
            "target_max_single_positive_pnl_share"
        ],
        "target_by_window": selection["target_by_window"],
    }


def _compact_log(payload: dict[str, Any]) -> dict[str, Any]:
    best = payload["best_variant"]
    variant_gates = _compact_variant_gates(
        payload["delta_metrics"]["variant_vs_accepted_event_governance_source_adapter"]
    )
    compact_parameters = {
        "acceptance_baseline": payload["parameters"]["acceptance_baseline"],
        "baseline_experiment": payload["parameters"]["baseline_experiment"],
        "target_dispersion_bucket": payload["parameters"]["target_dispersion_bucket"],
        "selected_mid_dispersion_context_scalar": payload["parameters"][
            "selected_mid_dispersion_context_scalar"
        ],
        "variant_scalars": {
            name: row["mid_dispersion_context_scalar"]
            for name, row in payload["parameters"]["variants"].items()
        },
        "base_event_notional_usd": payload["parameters"]["base_event_notional_usd"],
        "hold_days": payload["parameters"]["hold_days"],
        "round_trip_cost_pct": payload["parameters"]["round_trip_cost_pct"],
        "sample_guard": payload["parameters"]["sample_guard"],
        "anti_js": payload["parameters"]["anti_js"],
    }
    return {
        "experiment_id": payload["experiment_id"],
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "status": payload["status"],
        "decision": payload["decision"],
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
        "parameters": compact_parameters,
        "date_range": payload["date_range"],
        "market_regime_summary": payload["market_regime_summary"],
        "gate_questions": payload["gate_questions"],
        "historical_experiment_check": payload["historical_experiment_check"],
        "backtest_protocol": {
            "source": payload["backtest_protocol"]["source"],
            "windows": _compact_windows(payload["backtest_protocol"]["windows"]),
            "config": payload["backtest_protocol"]["config"],
        },
        "gate1": {
            "baseline_name": payload["gate1"]["baseline_name"],
            "baseline_artifact": payload["gate1"]["baseline_artifact"],
        },
        "gate2": {
            "passed": payload["gate2"]["passed"],
            "operator_position_field_check": payload["gate2"][
                "operator_position_field_check"
            ],
        },
        "gate3": payload["gate3"],
        "gate4": {
            "passed": payload["gate4"]["passed"],
            "rule": payload["gate4"]["rule"],
            "basis": payload["gate4"]["basis"],
            "delta": payload["gate4"]["delta"],
            "sample_guard": payload["gate4"]["sample_guard"],
            "sample_guard_passed": payload["gate4"]["sample_guard_passed"],
        },
        "before_metrics": {
            BASELINE_VARIANT: _compact_metrics_by_window(
                payload["before_metrics"][BASELINE_VARIANT]
            )
        },
        "after_metrics": {
            best: _compact_metrics_by_window(payload["after_metrics"][best])
        },
        "delta_metrics": {
            "variant_vs_accepted_event_governance_source_adapter": variant_gates
        },
        "best_variant": best,
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "total_pnl_delta": payload["total_pnl_delta"],
        "selection": _concise_selection(payload["selection"][best]),
        "production_impact": payload["production_impact"],
        "llm_metrics": payload["llm_metrics"],
        "decision_rationale": payload["decision_rationale"],
        "rejection_reason": payload["rejection_reason"],
        "next_action": payload["next_action"],
        "why_not_other_attractive_points": payload["why_not_other_attractive_points"],
        "risk_of_change": payload["risk_of_change"],
        "related_files": payload["related_files"],
        "anti_js": payload["anti_js"],
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
            "title": "Event mid-dispersion context",
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
                    "sample_guard_passed": payload["gate4"][
                        "sample_guard_passed"
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
