"""exp-20260528-018: VBB breadth-intensity notional support scout.

This alpha search tests one free-OHLCV field on top of the accepted
VOLUME_BREADTH_BREAKOUT_PAPER adapter from exp-20260526-014: selected VBB
paper trades receive small default-off paper notional support when the already
persisted same-day volume-breadth fraction is strong.

The experiment is replay-only unless Gate 4 passes and the exact rule is later
promoted into the shared VBB adapter. It does not change core signals, ranking,
sizing, exits, LLM/news, watchlists, or live/default orders. No JavaScript is
used.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENT_DIR / "legacy"
for path in (QUANT_DIR, EXPERIMENT_DIR, LEGACY_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260526_014_volume_breadth_shared_adapter as exp014  # noqa: E402


EXPERIMENT_ID = "exp-20260528-018"
STEM = "vbb_breadth_intensity_support"
TRIAL_FAMILY = "volume_breadth_breakout_breadth_intensity_support"
CHANGED_VARIABLE = "vbb_selected_trade_volume_breadth_fraction_notional_support"
RULE_VERSION = "vbb_breadth_intensity_support_scout_v1"
SHARED_RULE_VERSION = "vbb_breadth_intensity_support_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

VARIANTS = [
    {
        "id": "breadth_fraction_gte_0p18_scalar_1p05",
        "min_volume_breadth_fraction": 0.18,
        "notional_scalar": 1.05,
    },
    {
        "id": "breadth_fraction_gte_0p20_scalar_1p05",
        "min_volume_breadth_fraction": 0.20,
        "notional_scalar": 1.05,
    },
    {
        "id": "breadth_fraction_gte_0p25_scalar_1p05",
        "min_volume_breadth_fraction": 0.25,
        "notional_scalar": 1.05,
    },
    {
        "id": "breadth_fraction_gte_0p25_scalar_1p10",
        "min_volume_breadth_fraction": 0.25,
        "notional_scalar": 1.10,
    },
    {
        "id": "breadth_fraction_gte_0p30_scalar_1p10",
        "min_volume_breadth_fraction": 0.30,
        "notional_scalar": 1.10,
    },
]

MIN_ADJUSTED_TRADES = 10
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30


def _configure() -> tuple[Any, Any]:
    exp014._configure_prior_module()
    return exp014.prior.base, exp014.prior.ohlcv_helper


def _breadth_fraction(trade: dict[str, Any]) -> float | None:
    context = trade.get("volume_breadth_context")
    if not isinstance(context, dict):
        context = trade.get("candidate", {}).get("volume_breadth_context")
    if not isinstance(context, dict):
        return None
    try:
        value = float(context.get("volume_breadth_fraction"))
    except (TypeError, ValueError):
        return None
    return value


def _applies(trade: dict[str, Any], variant: dict[str, Any]) -> bool:
    fraction = _breadth_fraction(trade)
    if fraction is None:
        return False
    return fraction >= float(variant["min_volume_breadth_fraction"])


def _force_exp014_baseline_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    row = dict(candidate)
    row["base_paper_notional_usd"] = 10_000.0
    row["intended_notional"] = 10_000.0
    row["breadth_intensity_support_rule_version"] = SHARED_RULE_VERSION
    row["breadth_intensity_support_pass_v1"] = False
    row["breadth_intensity_notional_scalar"] = 1.0
    row["breadth_intensity_trade_enabled"] = False
    row["breadth_intensity_alters_orders"] = False
    return row


def _scale_trade(trade: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
    base, _shadow = _BASE_SHADOW
    scalar = float(variant["notional_scalar"])
    notional = float(trade.get("paper_notional_usd") or 10_000.0)
    pnl = float(trade.get("pnl") or 0.0)
    return {
        **trade,
        "paper_notional_usd": base._round(notional * scalar, 2),
        "pnl": base._round(pnl * scalar, 2),
        "breadth_intensity_support_rule_version": RULE_VERSION,
        "breadth_intensity_variant_id": variant["id"],
        "breadth_intensity_min_volume_breadth_fraction": variant["min_volume_breadth_fraction"],
        "breadth_intensity_notional_scalar": scalar,
        "breadth_intensity_fraction": base._round(_breadth_fraction(trade), 6),
        "breadth_intensity_trade_enabled": False,
        "breadth_intensity_alters_orders": False,
    }


def _incremental_trade(trade: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
    base, _shadow = _BASE_SHADOW
    scalar = float(variant["notional_scalar"])
    increment = scalar - 1.0
    notional = float(trade.get("paper_notional_usd") or 10_000.0)
    pnl = float(trade.get("pnl") or 0.0)
    return {
        **trade,
        "paper_notional_usd": base._round(notional * increment, 2),
        "pnl": base._round(pnl * increment, 2),
        "breadth_intensity_support_increment": base._round(increment, 4),
        "breadth_intensity_support_rule_version": RULE_VERSION,
        "breadth_intensity_variant_id": variant["id"],
        "breadth_intensity_min_volume_breadth_fraction": variant["min_volume_breadth_fraction"],
        "breadth_intensity_notional_scalar": scalar,
        "breadth_intensity_fraction": base._round(_breadth_fraction(trade), 6),
    }


def _apply_variant(
    selected_trades: list[dict[str, Any]],
    variant: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    after_trades: list[dict[str, Any]] = []
    adjusted_increments: list[dict[str, Any]] = []
    unadjusted: list[dict[str, Any]] = []
    for trade in selected_trades:
        if _applies(trade, variant):
            after_trades.append(_scale_trade(trade, variant))
            adjusted_increments.append(_incremental_trade(trade, variant))
        else:
            after_trades.append(trade)
            unadjusted.append(trade)
    return after_trades, adjusted_increments, unadjusted


def _evaluate_variant(
    *,
    variant: dict[str, Any],
    core_metrics: OrderedDict[str, dict[str, Any]],
    before_metrics: OrderedDict[str, dict[str, Any]],
    before_trades_by_window: OrderedDict[str, list[dict[str, Any]]],
    snapshots_by_window: OrderedDict[str, dict[str, list[dict[str, Any]]]],
    baseline_results_by_window: OrderedDict[str, dict[str, Any]],
) -> dict[str, Any]:
    base, _shadow = _BASE_SHADOW
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    adjusted_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    unadjusted_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    intensity_audit: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label in base.WINDOWS:
        before_result = baseline_results_by_window[label]
        before_trades = before_trades_by_window[label]
        after_trades, adjusted_increments, unadjusted = _apply_variant(before_trades, variant)
        after_overlay = base._overlay_from_paper_trades(before_result, after_trades)
        after = base.overlay_helper._metrics_with_overlay(before_result, after_overlay)
        delta = base.overlay_helper._delta(after, before_metrics[label])

        after_metrics[label] = after
        adjusted_by_window[label] = adjusted_increments
        unadjusted_by_window[label] = unadjusted
        fractions = [
            _breadth_fraction(row)
            for row in before_trades
            if _breadth_fraction(row) is not None
        ]
        adjusted_fractions = [
            _breadth_fraction(row)
            for row in adjusted_increments
            if _breadth_fraction(row) is not None
        ]
        intensity_audit[label] = {
            "before_vbb_trade_count": len(before_trades),
            "adjusted_trade_count": len(adjusted_increments),
            "unadjusted_trade_count": len(unadjusted),
            "adjusted_incremental_pnl": base._round(
                sum(float(row.get("pnl") or 0.0) for row in adjusted_increments),
                2,
            ),
            "all_selected_breadth_fraction_min": base._round(min(fractions) if fractions else None, 6),
            "all_selected_breadth_fraction_max": base._round(max(fractions) if fractions else None, 6),
            "adjusted_breadth_fraction_min": base._round(
                min(adjusted_fractions) if adjusted_fractions else None,
                6,
            ),
            "adjusted_breadth_fraction_max": base._round(
                max(adjusted_fractions) if adjusted_fractions else None,
                6,
            ),
            "adjusted_dates": [row.get("signal_date") for row in adjusted_increments],
            "adjusted_tickers": sorted({str(row.get("ticker") or "") for row in adjusted_increments}),
            "snapshot_ticker_count": len(snapshots_by_window[label]),
        }
        window_rows[label] = {
            "before": before_metrics[label],
            "after": after,
            "delta": delta,
            "target_trade_count": len(adjusted_increments),
            "raw_candidate_count": len(before_trades),
            "raw_candidate_days": len({row.get("signal_date") or row.get("date") for row in before_trades}),
            "overlay_total_pnl": after_overlay["overlay_total_pnl"],
            "overlay_day_count": after_overlay["overlay_day_count"],
        }

    aggregate = base._aggregate(window_rows)
    target_summary = base._target_trade_summary(adjusted_by_window)
    target_windows = target_summary["windows_with_target_trades"]
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in core_metrics.values())
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    gate4_passed = (
        aggregate["expected_value_score_delta_sum"] > 0
        and aggregate["total_pnl_delta_sum"] > 0
        and aggregate["windows_ev_improved"] == len(base.WINDOWS)
        and aggregate["windows_ev_regressed"] == 0
        and aggregate["windows_pnl_regressed"] == 0
        and target_summary["total_trade_count"] >= MIN_ADJUSTED_TRADES
        and len(target_windows) >= MIN_TARGET_WINDOWS
        and aggregate["max_drawdown_delta_max"] <= MAX_DRAWDOWN_WORSE
        and min_survival >= 0.05
        and concentration_passed
    )
    failed: list[str] = []
    if aggregate["expected_value_score_delta_sum"] <= 0:
        failed.append("aggregate_ev_not_positive_vs_exp014")
    if aggregate["total_pnl_delta_sum"] <= 0:
        failed.append("aggregate_pnl_not_positive_vs_exp014")
    if aggregate["windows_ev_improved"] != len(base.WINDOWS) or aggregate["windows_ev_regressed"]:
        failed.append("window_ev_regression_vs_exp014")
    if aggregate["windows_pnl_regressed"]:
        failed.append("window_pnl_regression_vs_exp014")
    if target_summary["total_trade_count"] < MIN_ADJUSTED_TRADES:
        failed.append("target_sample_too_small")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if aggregate["max_drawdown_delta_max"] > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if not concentration_passed:
        failed.append("target_concentration_failed")

    return {
        "variant": variant,
        "gate4": {
            "passed": gate4_passed,
            "failed_reasons": failed,
            "aggregate": aggregate,
            "target_trade_summary": target_summary,
            "concentration_passed": concentration_passed,
            "drawdown_guard": {
                "max_allowed_worse": MAX_DRAWDOWN_WORSE,
                "observed_max_delta": aggregate["max_drawdown_delta_max"],
            },
        },
        "after_metrics": after_metrics,
        "delta_metrics": {
            "aggregate": aggregate,
            "by_window": OrderedDict(
                (label, window_rows[label]["delta"]) for label in base.WINDOWS
            ),
        },
        "target_trades_by_window": adjusted_by_window,
        "unadjusted_trades_by_window": unadjusted_by_window,
        "intensity_audit": intensity_audit,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
    }


def _variant_sort_key(row: dict[str, Any]) -> tuple[int, float, float, float]:
    gate = row["gate4"]
    aggregate = gate["aggregate"]
    return (
        1 if gate["passed"] else 0,
        float(aggregate.get("expected_value_score_delta_sum") or 0.0),
        float(aggregate.get("total_pnl_delta_sum") or 0.0),
        -float(aggregate.get("max_drawdown_delta_max") or 0.0),
    )


def _build_payload() -> dict[str, Any]:
    base, shadow = _BASE_SHADOW
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2}")

    universe = sorted(base.get_universe())
    core_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_vbb_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    snapshots_by_window: "OrderedDict[str, dict[str, list[dict[str, Any]]]]" = OrderedDict()
    baseline_results_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in base.WINDOWS.items():
        print(f"[{label}] exp014 VBB baseline for breadth-intensity support")
        before_result = shadow._run_baseline(universe, cfg)
        baseline_results_by_window[label] = before_result
        core_metrics[label] = base.overlay_helper._metrics(before_result)
        snapshot = shadow._load_snapshot(cfg["snapshot"])
        snapshots_by_window[label] = snapshot
        candidates = [
            _force_exp014_baseline_candidate(row)
            for row in exp014._candidate_rows_for_window(snapshot, cfg, universe, before_result)
        ]
        before_trades, filtered_candidates = base._select_paper_trades(snapshot, candidates)
        before_overlay = base._overlay_from_paper_trades(before_result, before_trades)
        before_metrics[label] = base.overlay_helper._metrics_with_overlay(before_result, before_overlay)
        before_vbb_trades_by_window[label] = before_trades
        filtered_candidates_by_window[label] = filtered_candidates[:200]

    variant_results = [
        _evaluate_variant(
            variant=variant,
            core_metrics=core_metrics,
            before_metrics=before_metrics,
            before_trades_by_window=before_vbb_trades_by_window,
            snapshots_by_window=snapshots_by_window,
            baseline_results_by_window=baseline_results_by_window,
        )
        for variant in VARIANTS
    ]
    best = sorted(variant_results, key=_variant_sort_key, reverse=True)[0]
    gate4_passed = bool(best["gate4"]["passed"])
    decision = (
        "accepted_shared_vbb_breadth_intensity_support"
        if gate4_passed
        else "rejected_vbb_breadth_intensity_support"
    )
    variant_summary = [
        {
            "variant_id": row["variant"]["id"],
            "min_volume_breadth_fraction": row["variant"]["min_volume_breadth_fraction"],
            "notional_scalar": row["variant"]["notional_scalar"],
            "gate4_passed": row["gate4"]["passed"],
            "failed_reasons": row["gate4"]["failed_reasons"],
            "aggregate": row["gate4"]["aggregate"],
            "target_trade_count": row["gate4"]["target_trade_summary"]["total_trade_count"],
            "max_single_positive_pnl_share": row["gate4"]["target_trade_summary"]["max_single_positive_pnl_share"],
            "positive_pnl_hhi": row["gate4"]["target_trade_summary"]["positive_pnl_hhi"],
        }
        for row in variant_results
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The accepted VOLUME_BREADTH_BREAKOUT_PAPER source may have better "
            "replacement value when selected trades occur on stronger breadth "
            "thrust days. Same-day volume_breadth_fraction is a free OHLCV "
            "market-internal field already produced by the accepted VBB helper."
        ),
        "change_type": "paper_notional_support_scout",
        "mechanism_family": "volume_breadth_breakout_default_off_candidate_pool",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": best["variant"]["id"],
        "prior_trial_count": 3,
        "nearby_prior_experiments": [
            "exp-20260526-013",
            "exp-20260526-014",
            "exp-20260526-017",
            "exp-20260526-018",
            "exp-20260526-019",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "free_ohlcv_breadth_intensity_field_on_accepted_vbb_adapter",
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": base.WINDOWS,
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "before_reference": "accepted exp-20260526-014 shared VBB paper adapter",
            "execution_model": (
                "Before uses the accepted exp014 VBB paper overlay. After uses "
                "the same selected VBB paper trades, but applies small default-off "
                "paper notional support to selected rows whose same-day "
                "volume_breadth_fraction clears the tested threshold. Entry "
                "remains next open and exit remains 10 trading days later."
            ),
        },
        "parameters": {
            "best_variant": best["variant"],
            "all_variants": VARIANTS,
            "before_adapter": "exp-20260526-014 VOLUME_BREADTH_BREAKOUT_PAPER",
            "support_condition": "selected VBB trade volume_breadth_context.volume_breadth_fraction >= threshold",
            "paper_notional_usd": 10_000.0,
            "hold_days": 10,
            "locked_variables": [
                "VBB candidate definition",
                "VBB top-1 selection",
                "VBB breadth pass thresholds",
                "VBB breakout thresholds",
                "VBB base paper notional",
                "next-open entry",
                "10-trading-day close exit",
                "core universe",
                "core signal generation",
                "core ranking",
                "core sizing",
                "core exits",
                "LLM/news replay",
                "live/default orders",
            ],
            "acceptance": {
                "aggregate_ev_delta_gt": 0,
                "aggregate_pnl_delta_gt": 0,
                "ev_improved_windows": 3,
                "max_ev_regressed_windows": 0,
                "max_pnl_regressed_windows": 0,
                "min_adjusted_trades": MIN_ADJUSTED_TRADES,
                "min_target_windows": MIN_TARGET_WINDOWS,
                "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
                "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                "max_positive_hhi": MAX_POSITIVE_HHI,
            },
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate_pool / capital allocation: already-selected VBB paper "
                "entries may deserve more notional when volume-breadth thrust "
                "intensity is materially above the accepted minimum. This matches "
                "the playbook's free breadth/internal-structure lane."
            ),
            "2_history_check": {
                "accepted_vbb": (
                    "exp-20260526-014 accepted the shared default-off VBB paper "
                    "adapter: EV +0.7124 and PnL +$13,225.50 vs core, 47 paper "
                    "trades, 3/3 windows."
                ),
                "nearby_failures": (
                    "exp-20260526-017 rejected IWM>SPY gating; exp-20260526-018 "
                    "found VBB rank monotonicity unstable; exp-20260526-019 "
                    "rejected same-day core activity support."
                ),
                "difference": (
                    "This does not expand ticker count, retune VBB pass thresholds, "
                    "change top-N, or add a live filter; it tests a production-visible "
                    "breadth-intensity support field on selected paper trades."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Same three docs/backtesting.md windows, before=exp014 VBB adapter, "
                "after=best predeclared breadth-intensity support variant; require "
                "positive aggregate EV/PnL, no EV/PnL-regressed window, >=10 "
                "adjusted trades across all windows, drawdown drift <=0.5pp, "
                "survival >=5%, and concentration inside guardrails."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260528_018_vbb_breadth_intensity_support.py"
            ),
        },
        "gate1": {
            "baseline_artifact": "data/experiments/exp-20260526-014/volume_breadth_shared_adapter.json",
            "before_metrics_are_exp014_vbb_adapter": True,
            "core_metrics": core_metrics,
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "selected exp014 VBB paper trade volume_breadth_context.volume_breadth_fraction",
                "selected exp014 VBB paper trade signal_date",
                "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": gate2["passed"],
            "note": (
                "The only tested strategy field is same-day volume_breadth_fraction, "
                "computed from OHLCV known after signal-date close and before "
                "next-open paper entry."
            ),
        },
        "gate3": {
            "core_survival_min": base._round(
                min(float(row.get("survival_rate") or 0.0) for row in core_metrics.values()),
                6,
            ),
            "core_survival_unchanged": True,
            "candidate_filter_added_to_live_core": False,
            "note": "Default-off paper notional support only; no core filter was added.",
        },
        "gate4": best["gate4"],
        "before_metrics": before_metrics,
        "after_metrics": best["after_metrics"],
        "delta_metrics": best["delta_metrics"],
        "before_vbb_trades_by_window": before_vbb_trades_by_window,
        "target_trades_by_window": best["target_trades_by_window"],
        "unadjusted_trades_by_window": best["unadjusted_trades_by_window"],
        "filtered_candidates_sample_by_window": filtered_candidates_by_window,
        "intensity_audit": best["intensity_audit"],
        "variant_results": variant_summary,
        "expected_value_score_delta": best["expected_value_score_delta"],
        "total_pnl_delta": best["total_pnl_delta"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": {
            "shared_policy_changed": gate4_passed,
            "backtester_adapter_changed": False,
            "run_adapter_changed": gate4_passed,
            "replay_only": not gate4_passed,
            "parity_test_added": gate4_passed,
            "default_off_paper_only": True,
            "production_signal_path_changed": False,
            "production_orders_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
        },
        "rejection_reason": None if gate4_passed else "; ".join(best["gate4"]["failed_reasons"]),
        "interpretation": (
            "Accepted: breadth-intensity support passed Gate 4 versus the accepted "
            "exp014 VBB adapter and is retained only in the shared default-off "
            "VBB paper adapter. Live/default orders remain disabled."
            if gate4_passed
            else (
                "Rejected: breadth-intensity support did not improve the accepted "
                "VBB adapter robustly enough across all three windows. Do not add "
                "this field as a VBB notional support rule on the frozen sample."
            )
        ),
        "next_retry_requires": [
            "new_forward_vbb_closed_outcomes",
            "materially_different_breadth_replacement_value_field",
            "not_a_nearby_volume_breadth_fraction_threshold_scalar_retry",
        ],
        "related_files": [
            base._repo_rel(Path(__file__)),
            "quant/volume_breadth_breakout_paper_sleeve.py",
            "quant/report_generator.py",
            "quant/default_off_alpha_attribution.py",
            "quant/test_volume_breadth_breakout_paper_sleeve.py",
            "docs/production_backtest_parity.md",
            base._repo_rel(OUT_JSON),
            base._repo_rel(LOG_JSON),
            base._repo_rel(TICKET_JSON),
            base._repo_rel(DOC_TICKET_JSON),
            base._repo_rel(ARTIFACT_MD),
            base._repo_rel(EXPERIMENT_LOG),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _build_report(payload: dict[str, Any]) -> str:
    base, _shadow = _BASE_SHADOW
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Adjusted / Before Trades | Incremental PnL |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["intensity_audit"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | "
            "${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | "
            "{adjusted}/{before_count} | ${incremental:+,.2f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                adjusted=audit["adjusted_trade_count"],
                before_count=audit["before_vbb_trade_count"],
                incremental=audit["adjusted_incremental_pnl"],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    lines = [
        f"# {EXPERIMENT_ID} VBB Breadth-Intensity Support",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        (
            "Single variable: on top of the accepted exp-20260526-014 VBB paper "
            "adapter, selected VBB paper trades receive small default-off paper "
            "notional support when same-day volume_breadth_fraction clears the "
            "best predeclared threshold."
        ),
        "",
        f"Best variant: `{payload['parameters']['best_variant']['id']}`.",
        "",
        "## Three-Window Result Versus Exp014",
        "",
        *rows,
        "",
        "## Aggregate",
        "",
        f"- EV delta vs exp014: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
        f"- PnL delta vs exp014: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
        f"- adjusted trades: `{payload['gate4']['target_trade_summary']['total_trade_count']}`",
        f"- max drawdown drift: `{aggregate['max_drawdown_delta_max']}`",
        "",
        "## Variant Sweep",
        "",
        "```json",
        json.dumps(payload["variant_results"], indent=2, sort_keys=True),
        "```",
        "",
        "## Gate 4",
        "",
        "```json",
        json.dumps(payload["gate4"], indent=2, sort_keys=True),
        "```",
        "",
        "## Breadth-Intensity Audit",
        "",
        "```json",
        json.dumps(payload["intensity_audit"], indent=2, sort_keys=True),
        "```",
        "",
        "## Production Impact",
        "",
        (
            "Replay-only/default-off paper scout. No shared policy, production "
            "adapter, run adapter, backtester adapter, watchlist, order path, "
            "core entry, ranking, sizing, or exit behavior changed."
        ),
        "",
        "No JavaScript was used.",
        "",
    ]
    return "\n".join(lines)


def _persist(payload: dict[str, Any]) -> None:
    base, _shadow = _BASE_SHADOW
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "VBB breadth-intensity support",
        "status": payload["status"],
        "lane": "alpha_search",
        "updated_at": payload["timestamp"],
        "artifacts": {
            "json": base._repo_rel(OUT_JSON),
            "log": base._repo_rel(LOG_JSON),
            "report": base._repo_rel(ARTIFACT_MD),
        },
        "summary": payload["interpretation"],
        "owner": "alpha-search",
    }
    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, payload)
    base._write_json(TICKET_JSON, ticket)
    base._write_json(DOC_TICKET_JSON, ticket)
    base._write_text(ARTIFACT_MD, _build_report(payload))
    base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    payload = _build_payload()
    _persist(payload)
    base, _shadow = _BASE_SHADOW
    print(
        json.dumps(
            base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "best_variant": payload["parameters"]["best_variant"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "artifact": base._repo_rel(ARTIFACT_MD),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


_BASE_SHADOW = _configure()


if __name__ == "__main__":
    raise SystemExit(main())
