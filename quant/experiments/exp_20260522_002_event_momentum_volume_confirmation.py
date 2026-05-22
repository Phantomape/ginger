"""exp-20260522-002: event momentum plus volume confirmation context.

Alpha search. Tests one production-visible event context field on top of the
accepted exp-20260521-013 default-off event overlay adapter: whether selected
event rows deserve extra paper notional only when both ticker benchmark
momentum and volume confirmation are present.

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
import exp_20260521_024_event_benchmark_momentum_context as exp024


EXPERIMENT_ID = "exp-20260522-002"
EXPERIMENT_SLUG = "event_momentum_volume_confirmation"

REPO_ROOT = exp024.REPO_ROOT
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
TARGET_RET20_FIELD = "ret20_excess_spy"
TARGET_VOLUME_FIELD = "volume_ratio_20"
TARGET_MIN_EXCESS = 0.0
TARGET_MIN_VOLUME_RATIO = 1.10
MAX_DRAWDOWN_DRIFT = 0.0200
MAX_TARGET_POSITIVE_PNL_SHARE = 0.40
MIN_ROWS_WITH_BOTH_FIELDS = 25
MIN_TARGET_TRADES = 10
MIN_TARGET_WINDOWS = 3
MIN_TARGET_TICKERS = 6

VARIANTS: "OrderedDict[str, dict[str, Any]]" = OrderedDict(
    [
        (
            BASELINE_VARIANT,
            {
                "description": "Accepted exp-20260521-013 event adapter.",
                "momentum_volume_confirmation_scalar": 1.0,
            },
        ),
        (
            "momentum_volume_confirmation_105",
            {
                "description": (
                    "1.05x paper notional for event rows with ret20_excess_spy > 0 "
                    "and volume_ratio_20 >= 1.10."
                ),
                "momentum_volume_confirmation_scalar": 1.05,
            },
        ),
        (
            "momentum_volume_confirmation_110",
            {
                "description": (
                    "1.10x paper notional for event rows with ret20_excess_spy > 0 "
                    "and volume_ratio_20 >= 1.10."
                ),
                "momentum_volume_confirmation_scalar": 1.10,
            },
        ),
        (
            "momentum_volume_confirmation_115",
            {
                "description": (
                    "1.15x paper notional for event rows with ret20_excess_spy > 0 "
                    "and volume_ratio_20 >= 1.10."
                ),
                "momentum_volume_confirmation_scalar": 1.15,
            },
        ),
        (
            "momentum_volume_confirmation_120",
            {
                "description": (
                    "1.20x paper notional for event rows with ret20_excess_spy > 0 "
                    "and volume_ratio_20 >= 1.10."
                ),
                "momentum_volume_confirmation_scalar": 1.20,
            },
        ),
    ]
)


def _parent():
    return exp024._parent()


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _configure_modules() -> None:
    exp024._configure_modules()


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


def _state_feature_float(trade: dict[str, Any], field: str) -> float | None:
    features = trade.get("state_features") or {}
    value = features.get(field)
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _has_both_confirmation_fields(trade: dict[str, Any]) -> bool:
    return (
        _state_feature_float(trade, TARGET_RET20_FIELD) is not None
        and _state_feature_float(trade, TARGET_VOLUME_FIELD) is not None
    )


def _is_target_momentum_volume_confirmation(trade: dict[str, Any]) -> bool:
    ret20_excess = _state_feature_float(trade, TARGET_RET20_FIELD)
    volume_ratio = _state_feature_float(trade, TARGET_VOLUME_FIELD)
    return (
        ret20_excess is not None
        and ret20_excess > TARGET_MIN_EXCESS
        and volume_ratio is not None
        and volume_ratio >= TARGET_MIN_VOLUME_RATIO
    )


def _scaled_trade(
    trade: dict[str, Any],
    variant_name: str,
    variant: dict[str, Any],
) -> dict[str, Any]:
    parent = _parent()
    accepted_scalar = exp024._accepted_event_scalar_after_exp013(trade)
    target = _is_target_momentum_volume_confirmation(trade)
    confirmation_scalar = (
        float(variant["momentum_volume_confirmation_scalar"]) if target else 1.0
    )
    scalar = accepted_scalar * confirmation_scalar
    base_notional = float(trade.get("notional") or parent.base.EVENT_NOTIONAL)
    base_shares = float(trade.get("shares") or 0.0)
    ret20_excess = _state_feature_float(trade, TARGET_RET20_FIELD)
    volume_ratio = _state_feature_float(trade, TARGET_VOLUME_FIELD)
    return {
        **trade,
        "variant": variant_name,
        "accepted_event_scalar_after_exp013": round(accepted_scalar, 4),
        "momentum_volume_confirmation_target": target,
        "momentum_volume_confirmation_scalar": round(confirmation_scalar, 4),
        "ret20_excess_spy": round(ret20_excess, 6) if ret20_excess is not None else None,
        "volume_ratio_20": round(volume_ratio, 6) if volume_ratio is not None else None,
        "state_surface_scalar": round(scalar, 4),
        "base_notional": round(base_notional, 2),
        "notional": round(base_notional * scalar, 2),
        "shares": base_shares * scalar,
        "pnl": round(float(trade.get("pnl") or 0.0) * scalar, 2),
    }


def _selection_summary(rows_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    target_by_window: dict[str, Any] = OrderedDict()
    all_rows = [row for rows in rows_by_window.values() for row in rows]
    rows_with_both_fields = [row for row in all_rows if _has_both_confirmation_fields(row)]
    targets = [
        row
        for row in rows_with_both_fields
        if row.get("momentum_volume_confirmation_target")
    ]
    for label, rows in rows_by_window.items():
        window_targets = [
            row for row in rows if row.get("momentum_volume_confirmation_target")
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
            "ret20_excess_spy_values": [
                row.get("ret20_excess_spy") for row in window_targets[:10]
            ],
            "volume_ratio_20_values": [
                row.get("volume_ratio_20") for row in window_targets[:10]
            ],
        }
    target_wins = sum(
        1 for row in targets if float(row.get("pnl") or 0.0) > 0
    )
    return {
        "target_fields": [TARGET_RET20_FIELD, TARGET_VOLUME_FIELD],
        "target_rule": (
            f"{TARGET_RET20_FIELD} > {TARGET_MIN_EXCESS} and "
            f"{TARGET_VOLUME_FIELD} >= {TARGET_MIN_VOLUME_RATIO}"
        ),
        "rows_with_both_fields_count": len(rows_with_both_fields),
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
        (selection.get("rows_with_both_fields_count") or 0) >= MIN_ROWS_WITH_BOTH_FIELDS
        and (selection.get("target_trade_count") or 0) >= MIN_TARGET_TRADES
        and (selection.get("target_windows_present") or 0) >= MIN_TARGET_WINDOWS
        and len(selection.get("target_tickers") or []) >= MIN_TARGET_TICKERS
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
            "min_rows_with_both_fields": MIN_ROWS_WITH_BOTH_FIELDS,
            "min_target_trades": MIN_TARGET_TRADES,
            "min_target_windows": MIN_TARGET_WINDOWS,
            "min_target_tickers": MIN_TARGET_TICKERS,
            "max_target_positive_pnl_share": MAX_TARGET_POSITIVE_PNL_SHARE,
            "actual_rows_with_both_fields": selection.get("rows_with_both_fields_count"),
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
            -abs(VARIANTS[name]["momentum_volume_confirmation_scalar"] - 1.0),
        ),
    )


def _compact_metrics_by_window(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return exp024._compact_metrics_by_window(rows)


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
        "accepted_default_off_event_momentum_volume_confirmation_context"
        if accepted
        else "rejected_event_momentum_volume_confirmation_context"
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
        "target_fields": [TARGET_RET20_FIELD, TARGET_VOLUME_FIELD],
        "target_rule": (
            f"{TARGET_RET20_FIELD} > {TARGET_MIN_EXCESS} and "
            f"{TARGET_VOLUME_FIELD} >= {TARGET_MIN_VOLUME_RATIO}"
        ),
        "selected_momentum_volume_confirmation_scalar": VARIANTS[best_variant][
            "momentum_volume_confirmation_scalar"
        ],
        "variant_scalars": {
            name: row["momentum_volume_confirmation_scalar"]
            for name, row in VARIANTS.items()
        },
        "base_event_notional_usd": parent.base.EVENT_NOTIONAL,
        "hold_days": parent.base.HOLD_DAYS,
        "round_trip_cost_pct": parent.base.ROUND_TRIP_COST_PCT,
        "sample_guard": {
            "min_rows_with_both_fields": MIN_ROWS_WITH_BOTH_FIELDS,
            "min_target_trades": MIN_TARGET_TRADES,
            "min_target_windows": MIN_TARGET_WINDOWS,
            "min_target_tickers": MIN_TARGET_TICKERS,
            "max_target_positive_pnl_share": MAX_TARGET_POSITIVE_PNL_SHARE,
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
        "trial_family": "event_momentum_volume_confirmation_context",
        "trial_variant_id": "ret20_positive_and_volume_ratio_ge_1p10_notional_scalar",
        "changed_variable": "event_momentum_volume_confirmation_scalar",
        "prior_trial_count": 2,
        "nearby_prior_experiments": [
            "exp-20260521-013",
            "exp-20260521-024",
            "exp-20260521-025",
            "exp-20260522-001",
        ],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "composite_event_participation_confirmation_field",
        "hypothesis": (
            "Inside the accepted default-off event overlay, rows with both positive "
            "20-day excess return versus SPY and 20-day volume confirmation may "
            "retain the replacement value seen in the single-field momentum and "
            "volume scouts while reducing drawdown from over-broad participation."
        ),
        "alpha_hypothesis": {
            "category": "capital allocation / event context scoring",
            "entry_exit_ranking_or_allocation": "capital allocation",
            "playbook_alignment": (
                "Uses production-visible event state features and avoids LLM "
                "soft-ranking, SEC sparse text slices, source-capacity retries, "
                "and state-surface threshold/profile mining."
            ),
        },
        "single_causal_variable": (
            "paper-notional scalar for fixed event overlay rows whose "
            "state_features.ret20_excess_spy is positive and "
            "state_features.volume_ratio_20 is at least 1.10; event definitions, "
            "accepted source/reaction/state context scalars, hold period, source "
            "capacity, and core strategy stay fixed"
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
        "gate_questions": {
            "1_alpha_hypothesis": (
                "Event rows with both benchmark momentum and volume confirmation "
                "may be stronger replacements; this is event context scoring plus "
                "capital allocation."
            ),
            "2_history_check": (
                "Momentum-only and volume-only event scouts both improved all "
                "windows but failed at higher scalars on drawdown. This tests their "
                "intersection, not a nearby single-field retry."
            ),
            "3_single_causal_variable": (
                "Only the paper-notional scalar for fixed dual-confirmation event "
                "rows changes."
            ),
            "4_acceptance_standard": (
                "docs/backtesting.md three fixed windows; compare against the "
                "accepted exp-20260521-013 event adapter baseline, require "
                "aggregate EV/PnL improvement, no EV-regressed window, sample "
                "guard pass, risk guard pass, and no production/backtest divergence."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe "
                "quant\\experiments\\exp_20260522_002_event_momentum_volume_confirmation.py"
            ),
        },
        "historical_experiment_check": {
            "exp-20260521-013": "Accepted event non-narrow state-bucket context; current event baseline.",
            "exp-20260521-024": (
                "Rejected event benchmark-momentum context because the best scalar "
                "failed the drawdown guard."
            ),
            "exp-20260521-025": (
                "Rejected event volume-confirmation context because the best scalar "
                "failed the drawdown guard."
            ),
            "exp-20260522-001": (
                "Rejected event low-extension context because the best scalar "
                "regressed two windows and failed sample guard."
            ),
        },
        "gate1": {
            "baseline_name": BASELINE_VARIANT,
            "baseline_artifact": "data/experiments/exp-20260521-013/event_non_narrow_state_context.json",
        },
        "gate2": {
            "passed": bool(
                operator_check["passed"]
                and selection_by_variant[BASELINE_VARIANT].get(
                    "rows_with_both_fields_count", 0
                )
                > 0
            ),
            "operator_position_field_check": operator_check,
            "required_fields": [
                "event source",
                "ticker",
                "entry_date",
                "exit_date",
                "pnl",
                f"state_features.{TARGET_RET20_FIELD}",
                f"state_features.{TARGET_VOLUME_FIELD}",
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
                "deterministic production-visible state_features only."
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
            else (
                "Rejected: dual confirmation event context scalar did not clear "
                "Gate 4 under high multiple-testing risk."
            )
        ),
        "rejection_reason": rejection_reason,
        "next_action": (
            "Do not retry nearby event ret20/volume context scalars on the frozen "
            "sample unless new forward rows arrive. Prefer a distinct event quality "
            "field, forward replacement-value maturation, or another alpha lane."
        ),
        "why_not_other_attractive_points": (
            "Skipped LLM soft-ranking due attribution limits; skipped SEC no-guidance/"
            "attention-persistence nearby fields due recent sample failures; skipped "
            "event low-extension after exp-20260522-001 failed; skipped state-surface "
            "and broad-market retunes due anti-repeat gates."
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
        f"# {EXPERIMENT_ID} Event Momentum Plus Volume Confirmation",
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
