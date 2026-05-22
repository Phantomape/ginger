"""exp-20260522-001: event low-extension context.

Alpha search. Tests one production-visible event state-feature field on top of
the accepted exp-20260521-013 default-off event overlay adapter: whether event
rows with low short-term extension (`state_features.ret5 <= 0.02`) deserve a
paper-notional scalar.

No JavaScript is used. Live/default orders remain disabled.
"""

from __future__ import annotations

import json
import math
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260521_010_event_governance_semantic_cell as exp010
import exp_20260521_013_event_non_narrow_state_context as exp013


EXPERIMENT_ID = "exp-20260522-001"
EXPERIMENT_SLUG = "event_low_extension_context"

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
TARGET_FIELD = "state_features.ret5"
TARGET_RET5_MAX = 0.02
MAX_DRAWDOWN_DRIFT = 0.0200

VARIANTS: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "description": "Accepted exp-20260521-013 event adapter.",
                "low_extension_context_scalar": 1.0,
            },
        ),
        (
            "low_extension_context_080",
            {
                "description": "0.80x paper notional for ret5 <= 0.02 event rows.",
                "low_extension_context_scalar": 0.80,
            },
        ),
        (
            "low_extension_context_090",
            {
                "description": "0.90x paper notional for ret5 <= 0.02 event rows.",
                "low_extension_context_scalar": 0.90,
            },
        ),
        (
            "low_extension_context_105",
            {
                "description": "1.05x paper notional for ret5 <= 0.02 event rows.",
                "low_extension_context_scalar": 1.05,
            },
        ),
        (
            "low_extension_context_110",
            {
                "description": "1.10x paper notional for ret5 <= 0.02 event rows.",
                "low_extension_context_scalar": 1.10,
            },
        ),
        (
            "low_extension_context_115",
            {
                "description": "1.15x paper notional for ret5 <= 0.02 event rows.",
                "low_extension_context_scalar": 1.15,
            },
        ),
        (
            "low_extension_context_120",
            {
                "description": "1.20x paper notional for ret5 <= 0.02 event rows.",
                "low_extension_context_scalar": 1.20,
            },
        ),
        (
            "low_extension_context_125",
            {
                "description": "1.25x paper notional for ret5 <= 0.02 event rows.",
                "low_extension_context_scalar": 1.25,
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


def _safe(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {str(key): _safe(value) for key, value in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [_safe(value) for value in payload]
    if isinstance(payload, float):
        return payload if math.isfinite(payload) else None
    return payload


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


def _ret5_value(trade: dict[str, Any]) -> float | None:
    features = trade.get("state_features") or {}
    value = features.get("ret5")
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _is_target_low_extension(trade: dict[str, Any]) -> bool:
    value = _ret5_value(trade)
    return value is not None and value <= TARGET_RET5_MAX


def _accepted_event_scalar_after_exp013(trade: dict[str, Any]) -> float:
    scalar = exp013._accepted_event_scalar_after_exp012(trade)
    if exp013._is_target_non_narrow_state(trade):
        scalar *= 1.15
    return scalar


def _scaled_trade(
    trade: dict[str, Any],
    variant_name: str,
    variant: dict[str, Any],
) -> dict[str, Any]:
    parent = _parent()
    accepted_scalar = _accepted_event_scalar_after_exp013(trade)
    target = _is_target_low_extension(trade)
    context_scalar = (
        float(variant["low_extension_context_scalar"]) if target else 1.0
    )
    scalar = accepted_scalar * context_scalar
    base_notional = float(trade.get("notional") or parent.base.EVENT_NOTIONAL)
    base_shares = float(trade.get("shares") or 0.0)
    ret5 = _ret5_value(trade)
    return {
        **trade,
        "variant": variant_name,
        "accepted_event_scalar_after_exp013": round(accepted_scalar, 4),
        "low_extension_context_target": target,
        "low_extension_context_scalar": round(context_scalar, 4),
        "low_extension_ret5": round(ret5, 6) if ret5 is not None else None,
        "state_surface_scalar": round(scalar, 4),
        "base_notional": round(base_notional, 2),
        "notional": round(base_notional * scalar, 2),
        "shares": base_shares * scalar,
        "pnl": round(float(trade.get("pnl") or 0.0) * scalar, 2),
    }


def _selection_summary(rows_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    target_by_window: dict[str, Any] = OrderedDict()
    all_rows = [row for rows in rows_by_window.values() for row in rows]
    rows_with_field = [row for row in all_rows if _ret5_value(row) is not None]
    targets = [row for row in all_rows if row.get("low_extension_context_target")]
    for label, rows in rows_by_window.items():
        window_targets = [
            row for row in rows if row.get("low_extension_context_target")
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
            "reaction_buckets": sorted(
                {str(row.get("reaction_bucket") or "") for row in window_targets}
            ),
            "state_buckets": sorted(
                {str(row.get("state_bucket") or "") for row in window_targets}
            ),
            "state_surfaces": sorted(
                {str(row.get("state_surface") or "") for row in window_targets}
            ),
            "ret5_values": [
                row.get("low_extension_ret5") for row in window_targets[:10]
            ],
        }
    target_wins = sum(
        1 for row in targets if float(row.get("pnl") or 0.0) > 0
    )
    return {
        "target_field": TARGET_FIELD,
        "target_rule": f"ret5 <= {TARGET_RET5_MAX}",
        "rows_with_field_count": len(rows_with_field),
        "target_trade_count": len(targets),
        "target_windows_present": sum(
            1 for row in target_by_window.values() if row["trade_count"] > 0
        ),
        "target_tickers": sorted({str(row.get("ticker") or "") for row in targets}),
        "target_sources": sorted({str(row.get("source") or "") for row in targets}),
        "target_reaction_buckets": sorted(
            {str(row.get("reaction_bucket") or "") for row in targets}
        ),
        "target_state_buckets": sorted(
            {str(row.get("state_bucket") or "") for row in targets}
        ),
        "target_state_surfaces": sorted(
            {str(row.get("state_surface") or "") for row in targets}
        ),
        "target_wins": target_wins,
        "target_win_rate": round(target_wins / len(targets), 4) if targets else None,
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
        (selection.get("rows_with_field_count") or 0) >= 25
        and (selection.get("target_trade_count") or 0) >= 10
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
            "min_rows_with_field": 25,
            "min_target_trades": 10,
            "min_target_windows": 3,
            "min_target_tickers": 6,
            "max_target_positive_pnl_share": 0.45,
            "actual_rows_with_field": selection.get("rows_with_field_count"),
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
            -abs(VARIANTS[name]["low_extension_context_scalar"] - 1.0),
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
    exp013._configure_modules()
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
        "accepted_default_off_event_low_extension_context"
        if accepted
        else "rejected_event_low_extension_context"
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
        "target_rule": f"ret5 <= {TARGET_RET5_MAX}",
        "selected_low_extension_context_scalar": VARIANTS[best_variant][
            "low_extension_context_scalar"
        ],
        "variant_scalars": {
            name: row["low_extension_context_scalar"]
            for name, row in VARIANTS.items()
        },
        "base_event_notional_usd": parent.base.EVENT_NOTIONAL,
        "hold_days": parent.base.HOLD_DAYS,
        "round_trip_cost_pct": parent.base.ROUND_TRIP_COST_PCT,
        "sample_guard": {
            "min_rows_with_field": 25,
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
        "change_type": "event_state_feature_allocation_scout",
        "mechanism_family": "external_event_satellite_overlay_allocation",
        "trial_family": "event_short_term_extension_context",
        "trial_variant_id": "ret5_le_0p02_notional_scalar",
        "changed_variable": "event_low_extension_context_scalar",
        "prior_trial_count": 2,
        "nearby_prior_experiments": [
            "exp-20260520-001",
            "exp-20260520-002",
            "exp-20260521-013",
            "exp-20260521-024",
            "exp-20260521-025",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "new_event_short_term_extension_context_field",
        "hypothesis": (
            "Inside the accepted default-off event overlay, event rows with low "
            "short-term extension (`state_features.ret5 <= 0.02`) may carry "
            "cleaner replacement value than already-extended event rows. A single "
            "paper-notional scalar tests this production-visible extension field "
            "without changing core trades."
        ),
        "alpha_hypothesis": {
            "category": "capital allocation / event context scoring",
            "entry_exit_ranking_or_allocation": "capital allocation",
            "playbook_alignment": (
                "Uses one production-visible field in the event overlay lane, while "
                "avoiding LLM soft-ranking, SEC sparse text slices, source-capacity "
                "retries, and state-surface/broad-market threshold mining."
            ),
        },
        "single_causal_variable": (
            "paper-notional scalar for fixed event overlay rows whose "
            "state_features.ret5 is at most 0.02; event definitions, accepted "
            "source/reaction/state context scalars, hold period, source capacity, "
            "and core strategy stay fixed"
        ),
        "parameters": compact_parameters,
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
                "Event rows with low short-term extension may have better "
                "replacement value; this is event context scoring plus capital allocation."
            ),
            "2_history_check": (
                "Low-extension support was accepted in state-surface and broad-market "
                "paper sleeves, but not in the event overlay. Recent event benchmark "
                "momentum and volume context scouts failed drawdown risk."
            ),
            "3_single_causal_variable": (
                "Only the paper-notional scalar for fixed low-extension event rows changes."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; compare against the accepted "
                "exp-20260521-013 event adapter baseline, require aggregate EV/PnL "
                "improvement, no EV-regressed window, sample guard pass, risk guard "
                "pass, and no production/backtest divergence."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe "
                "quant\\experiments\\exp_20260522_001_event_low_extension_context.py"
            ),
        },
        "historical_experiment_check": {
            "exp-20260520-001": (
                "Accepted state-surface low-extension support; different sleeve and "
                "subject to strict state-surface anti-repeat going forward."
            ),
            "exp-20260520-002": (
                "Accepted broad-market low-extension paper notional; different sleeve."
            ),
            "exp-20260521-013": "Accepted event non-narrow state-bucket context; current event baseline.",
            "exp-20260521-024": (
                "Rejected event benchmark-momentum context because drawdown guard failed."
            ),
            "exp-20260521-025": (
                "Rejected event volume-confirmation context because drawdown guard failed."
            ),
        },
        "gate1": {
            "baseline_name": BASELINE_VARIANT,
            "baseline_artifact": "data/experiments/exp-20260521-013/event_non_narrow_state_context.json",
        },
        "gate2": {
            "passed": bool(
                operator_check["passed"]
                and all(
                    selection_by_variant[BASELINE_VARIANT].get("rows_with_field_count", 0)
                    > 0
                    for _ in [0]
                )
            ),
            "operator_position_field_check": operator_check,
            "required_fields": [
                "event source",
                "ticker",
                "entry_date",
                "exit_date",
                "pnl",
                TARGET_FIELD,
                "reaction_bucket",
                "state_bucket",
            ],
            "selection": selection_by_variant[best_variant],
        },
        "gate3": {
            "passed": True,
            "new_filter_added": False,
            "candidate_pool_changed": False,
            "survival_impact": (
                "not applicable to default-off event paper overlay; core signals "
                "and survival are unchanged"
            ),
        },
        "before_metrics": {
            BASELINE_VARIANT: _compact_metrics_by_window(baseline_metrics),
            "core": _compact_metrics_by_window(core_metrics),
        },
        "after_metrics": {
            best_variant: _compact_metrics_by_window(variant_metrics[best_variant])
        },
        "all_variant_after_metrics": compact_after_metrics,
        "delta_metrics": {
            "variant_vs_accepted_event_non_narrow_state_context_adapter": variant_gates
        },
        "expected_value_score_delta": best_gate["delta"]["aggregate_ev_delta"],
        "total_pnl_delta": best_gate["delta"]["aggregate_pnl_delta"],
        "best_variant": best_variant,
        "gate4": best_gate,
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
        "llm_metrics": {
            "used_llm": False,
            "llm_role_changed": False,
            "blocker_relation": (
                "LLM soft-ranking remains attribution/sample-limited; this uses "
                "deterministic state_features only."
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "parity_test_added": False,
            "replay_only": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "production_signal_path_changed": False,
            "live_orders_enabled": False,
        },
        "decision_rationale": (
            "Accepted as a shared default-off paper adapter change."
            if accepted
            else "Rejected: low-extension event context scalar did not clear Gate 4."
        ),
        "rejection_reason": rejection_reason,
        "next_action": (
            "Do not retry nearby event ret5 low-extension notional scalars on the "
            "frozen sample. Prefer forward replacement-value maturation, a distinct "
            "production-visible event quality field, or another alpha lane."
        ),
        "why_not_other_attractive_points": (
            "Skipped LLM soft-ranking due attribution limits; skipped SEC no-guidance/"
            "attention-persistence nearby fields due recent sample failures; skipped "
            "event ret20 and volume retries after exp-20260521-024/025 failed the "
            "drawdown guard; skipped state-surface and broad-market retunes due "
            "anti-repeat gates."
        ),
        "risk_of_change": (
            "Default-off paper attribution only. No live orders, ranking, core sizing, "
            "exits, source definitions, or source capacity changed."
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


def _write_artifact(payload: dict[str, Any]) -> None:
    rows = payload["delta_metrics"][
        "variant_vs_accepted_event_non_narrow_state_context_adapter"
    ]
    lines = [
        f"# {EXPERIMENT_ID} Event Low-Extension Context",
        "",
        f"Decision: `{payload['decision']}`",
        "",
        "## Hypothesis",
        "",
        payload["hypothesis"],
        "",
        "## Variant Deltas Vs Accepted Event Baseline",
        "",
        "| Variant | Passed | Sample | Risk | EV delta | PnL delta | EV + / - windows | Max DD drift |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, row in rows.items():
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
            "## Selection",
            "",
            "```json",
            json.dumps(payload["selection"], indent=2, sort_keys=True),
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
            "```",
            "",
            "No shared production policy was changed because Gate 4 failed.",
        ]
    )
    _write_text(ARTIFACT_MD, "\n".join(lines) + "\n")


def _write_ticket(payload: dict[str, Any]) -> None:
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "changed_variable": payload["changed_variable"],
        "expected_value_score_delta": payload["expected_value_score_delta"],
        "decision": payload["decision"],
        "artifact": _repo_rel(ARTIFACT_MD),
    }
    _write_json(TICKET_JSON, ticket)


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_ticket(payload)
    _write_artifact(payload)
    _append_jsonl_dedup(EXPERIMENT_LOG, payload)
    print(
        json.dumps(
            _safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "best_variant": payload["best_variant"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": {
                        "passed": payload["gate4"]["passed"],
                        "sample_guard_passed": payload["gate4"]["sample_guard_passed"],
                        "risk_guard_passed": payload["gate4"]["risk_guard_passed"],
                        "windows_ev_improved": payload["gate4"]["delta"][
                            "windows_ev_improved"
                        ],
                        "windows_ev_regressed": payload["gate4"]["delta"][
                            "windows_ev_regressed"
                        ],
                    },
                    "artifact": _repo_rel(ARTIFACT_MD),
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
