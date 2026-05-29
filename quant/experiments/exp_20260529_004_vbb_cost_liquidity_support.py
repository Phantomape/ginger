"""exp-20260529-004: VBB cost/liquidity notional support scout.

This alpha search tests one free-OHLCV cost/liquidity field on top of the
current accepted VOLUME_BREADTH_BREAKOUT_PAPER stack. It changes only
default-off paper notional for already selected VBB paper trades; core signals,
ranking, sizing, exits, LLM/news, watchlists, and live/default orders stay
fixed. No JavaScript is used.
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
import exp_20260528_018_vbb_breadth_intensity_support as exp018  # noqa: E402
import exp_20260528_022_vbb_signal_day_high_close_support as exp022  # noqa: E402


EXPERIMENT_ID = "exp-20260529-004"
STEM = "vbb_cost_liquidity_support"
TRIAL_FAMILY = "volume_breadth_breakout_cost_liquidity_support"
CHANGED_VARIABLE = "vbb_selected_trade_cost_liquidity_notional_support"
RULE_VERSION = "vbb_cost_liquidity_support_scout_v1"
ACCEPTED_BREADTH_RULE_VERSION = "vbb_breadth_intensity_support_v1"
ACCEPTED_HIGH_CLOSE_RULE_VERSION = "vbb_signal_day_high_close_support_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260529_004_vbb_cost_liquidity_support.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

VARIANTS = [
    {
        "id": "dvol_gte_100m_range_lte_0p08_scalar_1p05",
        "min_dollar_volume": 100_000_000.0,
        "max_range_pct": 0.08,
        "notional_scalar": 1.05,
    },
    {
        "id": "dvol_gte_100m_range_lte_0p08_scalar_1p10",
        "min_dollar_volume": 100_000_000.0,
        "max_range_pct": 0.08,
        "notional_scalar": 1.10,
    },
    {
        "id": "dvol_gte_150m_range_lte_0p08_scalar_1p05",
        "min_dollar_volume": 150_000_000.0,
        "max_range_pct": 0.08,
        "notional_scalar": 1.05,
    },
    {
        "id": "dvol_gte_100m_range_lte_0p06_scalar_1p05",
        "min_dollar_volume": 100_000_000.0,
        "max_range_pct": 0.06,
        "notional_scalar": 1.05,
    },
    {
        "id": "dvol_gte_200m_range_lte_0p10_scalar_1p05",
        "min_dollar_volume": 200_000_000.0,
        "max_range_pct": 0.10,
        "notional_scalar": 1.05,
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


def _float_or_none(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


def _row_value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row:
            return row.get(key)
    return None


def _signal_day_row(
    snapshot: dict[str, list[dict[str, Any]]],
    trade: dict[str, Any],
) -> dict[str, Any] | None:
    ticker = str(trade.get("ticker") or "").upper()
    signal_date = str(trade.get("signal_date") or trade.get("date") or "")[:10]
    if not ticker or not signal_date:
        return None
    rows = snapshot.get(ticker) or snapshot.get(ticker.upper()) or []
    for row in rows:
        row_date = str(_row_value(row, "date", "Date") or "")[:10]
        if row_date == signal_date:
            return row
    return None


def _signal_day_cost_liquidity(
    snapshot: dict[str, list[dict[str, Any]]],
    trade: dict[str, Any],
) -> dict[str, Any]:
    row = _signal_day_row(snapshot, trade)
    high = _float_or_none(_row_value(row or {}, "high", "High"))
    low = _float_or_none(_row_value(row or {}, "low", "Low"))
    close = _float_or_none(_row_value(row or {}, "close", "Close"))
    volume = _float_or_none(_row_value(row or {}, "volume", "Volume"))
    dollar_volume = _float_or_none(trade.get("dollar_volume"))
    if dollar_volume is None and close is not None and volume is not None:
        dollar_volume = close * volume
    range_pct = None
    if high is not None and low is not None and close and close > 0:
        range_pct = max(0.0, (high - low) / close)
    return {
        "dollar_volume": dollar_volume,
        "signal_day_range_pct": range_pct,
    }


def _accepted_current_vbb_trade(
    trade: dict[str, Any],
    snapshot: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    base, _shadow = _BASE_SHADOW
    row = dict(trade)
    if exp018._breadth_fraction(trade) is not None and exp018._breadth_fraction(trade) >= 0.25:
        scalar = 1.10
        row["paper_notional_usd"] = base._round(float(row.get("paper_notional_usd") or 10_000.0) * scalar, 2)
        row["pnl"] = base._round(float(row.get("pnl") or 0.0) * scalar, 2)
        row["breadth_intensity_support_rule_version"] = ACCEPTED_BREADTH_RULE_VERSION
        row["breadth_intensity_support_pass_v1"] = True
        row["breadth_intensity_min_volume_breadth_fraction"] = 0.25
        row["breadth_intensity_notional_scalar"] = scalar
        row["breadth_intensity_trade_enabled"] = False
        row["breadth_intensity_alters_orders"] = False
    close_location = exp022._close_location_value(snapshot, trade)
    if close_location is not None and close_location >= 0.70:
        scalar = 1.10
        row["paper_notional_usd"] = base._round(float(row.get("paper_notional_usd") or 10_000.0) * scalar, 2)
        row["pnl"] = base._round(float(row.get("pnl") or 0.0) * scalar, 2)
        row["high_close_support_rule_version"] = ACCEPTED_HIGH_CLOSE_RULE_VERSION
        row["high_close_support_pass_v1"] = True
        row["signal_day_close_location_value"] = base._round(close_location, 6)
        row["high_close_support_min_close_location"] = 0.70
        row["high_close_support_notional_scalar"] = scalar
        row["high_close_support_trade_enabled"] = False
        row["high_close_support_alters_orders"] = False
    return row


def _applies(
    trade: dict[str, Any],
    snapshot: dict[str, list[dict[str, Any]]],
    variant: dict[str, Any],
) -> bool:
    cost = _signal_day_cost_liquidity(snapshot, trade)
    dollar_volume = cost["dollar_volume"]
    range_pct = cost["signal_day_range_pct"]
    return (
        dollar_volume is not None
        and range_pct is not None
        and dollar_volume >= float(variant["min_dollar_volume"])
        and range_pct <= float(variant["max_range_pct"])
    )


def _scale_trade(
    trade: dict[str, Any],
    snapshot: dict[str, list[dict[str, Any]]],
    variant: dict[str, Any],
) -> dict[str, Any]:
    base, _shadow = _BASE_SHADOW
    scalar = float(variant["notional_scalar"])
    cost = _signal_day_cost_liquidity(snapshot, trade)
    return {
        **trade,
        "paper_notional_usd": base._round(float(trade.get("paper_notional_usd") or 10_000.0) * scalar, 2),
        "pnl": base._round(float(trade.get("pnl") or 0.0) * scalar, 2),
        "cost_liquidity_support_rule_version": RULE_VERSION,
        "cost_liquidity_support_variant_id": variant["id"],
        "cost_liquidity_min_dollar_volume": float(variant["min_dollar_volume"]),
        "cost_liquidity_max_range_pct": float(variant["max_range_pct"]),
        "cost_liquidity_notional_scalar": scalar,
        "cost_liquidity_dollar_volume": base._round(cost["dollar_volume"], 2),
        "cost_liquidity_signal_day_range_pct": base._round(cost["signal_day_range_pct"], 6),
        "cost_liquidity_trade_enabled": False,
        "cost_liquidity_alters_orders": False,
    }


def _incremental_trade(
    trade: dict[str, Any],
    snapshot: dict[str, list[dict[str, Any]]],
    variant: dict[str, Any],
) -> dict[str, Any]:
    base, _shadow = _BASE_SHADOW
    scalar = float(variant["notional_scalar"])
    increment = scalar - 1.0
    cost = _signal_day_cost_liquidity(snapshot, trade)
    return {
        **trade,
        "paper_notional_usd": base._round(float(trade.get("paper_notional_usd") or 10_000.0) * increment, 2),
        "pnl": base._round(float(trade.get("pnl") or 0.0) * increment, 2),
        "cost_liquidity_support_increment": base._round(increment, 4),
        "cost_liquidity_support_rule_version": RULE_VERSION,
        "cost_liquidity_support_variant_id": variant["id"],
        "cost_liquidity_min_dollar_volume": float(variant["min_dollar_volume"]),
        "cost_liquidity_max_range_pct": float(variant["max_range_pct"]),
        "cost_liquidity_notional_scalar": scalar,
        "cost_liquidity_dollar_volume": base._round(cost["dollar_volume"], 2),
        "cost_liquidity_signal_day_range_pct": base._round(cost["signal_day_range_pct"], 6),
    }


def _apply_variant(
    selected_trades: list[dict[str, Any]],
    snapshot: dict[str, list[dict[str, Any]]],
    variant: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    after_trades: list[dict[str, Any]] = []
    adjusted_increments: list[dict[str, Any]] = []
    unadjusted: list[dict[str, Any]] = []
    for trade in selected_trades:
        if _applies(trade, snapshot, variant):
            after_trades.append(_scale_trade(trade, snapshot, variant))
            adjusted_increments.append(_incremental_trade(trade, snapshot, variant))
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
    cost_audit: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label in base.WINDOWS:
        before_result = baseline_results_by_window[label]
        before_trades = before_trades_by_window[label]
        snapshot = snapshots_by_window[label]
        after_trades, adjusted_increments, unadjusted = _apply_variant(before_trades, snapshot, variant)
        after_overlay = base._overlay_from_paper_trades(before_result, after_trades)
        after = base.overlay_helper._metrics_with_overlay(before_result, after_overlay)
        delta = base.overlay_helper._delta(after, before_metrics[label])

        after_metrics[label] = after
        adjusted_by_window[label] = adjusted_increments
        unadjusted_by_window[label] = unadjusted
        cost_rows = [_signal_day_cost_liquidity(snapshot, row) for row in before_trades]
        adjusted_cost_rows = [_signal_day_cost_liquidity(snapshot, row) for row in adjusted_increments]
        ranges = [row["signal_day_range_pct"] for row in cost_rows if row["signal_day_range_pct"] is not None]
        dvols = [row["dollar_volume"] for row in cost_rows if row["dollar_volume"] is not None]
        adjusted_ranges = [
            row["signal_day_range_pct"]
            for row in adjusted_cost_rows
            if row["signal_day_range_pct"] is not None
        ]
        adjusted_dvols = [
            row["dollar_volume"]
            for row in adjusted_cost_rows
            if row["dollar_volume"] is not None
        ]
        cost_audit[label] = {
            "before_vbb_trade_count": len(before_trades),
            "adjusted_trade_count": len(adjusted_increments),
            "unadjusted_trade_count": len(unadjusted),
            "adjusted_incremental_pnl": base._round(
                sum(float(row.get("pnl") or 0.0) for row in adjusted_increments),
                2,
            ),
            "all_selected_range_pct_min": base._round(min(ranges) if ranges else None, 6),
            "all_selected_range_pct_max": base._round(max(ranges) if ranges else None, 6),
            "all_selected_dollar_volume_min": base._round(min(dvols) if dvols else None, 2),
            "all_selected_dollar_volume_max": base._round(max(dvols) if dvols else None, 2),
            "adjusted_range_pct_min": base._round(min(adjusted_ranges) if adjusted_ranges else None, 6),
            "adjusted_range_pct_max": base._round(max(adjusted_ranges) if adjusted_ranges else None, 6),
            "adjusted_dollar_volume_min": base._round(min(adjusted_dvols) if adjusted_dvols else None, 2),
            "adjusted_dollar_volume_max": base._round(max(adjusted_dvols) if adjusted_dvols else None, 2),
            "adjusted_dates": [row.get("signal_date") for row in adjusted_increments],
            "adjusted_tickers": sorted({str(row.get("ticker") or "") for row in adjusted_increments}),
            "snapshot_ticker_count": len(snapshot),
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
        failed.append("aggregate_ev_not_positive_vs_current_vbb")
    if aggregate["total_pnl_delta_sum"] <= 0:
        failed.append("aggregate_pnl_not_positive_vs_current_vbb")
    if aggregate["windows_ev_improved"] != len(base.WINDOWS) or aggregate["windows_ev_regressed"]:
        failed.append("window_ev_regression_vs_current_vbb")
    if aggregate["windows_pnl_regressed"]:
        failed.append("window_pnl_regression_vs_current_vbb")
    if target_summary["total_trade_count"] < MIN_ADJUSTED_TRADES:
        failed.append("target_sample_too_small")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if aggregate["max_drawdown_delta_max"] > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if min_survival < 0.05:
        failed.append("survival_rate_below_5pct")
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
        "cost_liquidity_audit": cost_audit,
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
        print(f"[{label}] current accepted VBB baseline for cost/liquidity support")
        before_result = shadow._run_baseline(universe, cfg)
        baseline_results_by_window[label] = before_result
        core_metrics[label] = base.overlay_helper._metrics(before_result)
        snapshot = shadow._load_snapshot(cfg["snapshot"])
        snapshots_by_window[label] = snapshot
        candidates = [
            exp018._force_exp014_baseline_candidate(row)
            for row in exp014._candidate_rows_for_window(snapshot, cfg, universe, before_result)
        ]
        raw_trades, filtered_candidates = base._select_paper_trades(snapshot, candidates)
        before_trades = [_accepted_current_vbb_trade(row, snapshot) for row in raw_trades]
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
        "accepted_shared_vbb_cost_liquidity_support"
        if gate4_passed
        else "rejected_vbb_cost_liquidity_support"
    )
    variant_summary = [
        {
            "variant_id": row["variant"]["id"],
            "min_dollar_volume": row["variant"]["min_dollar_volume"],
            "max_range_pct": row["variant"]["max_range_pct"],
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
    prediction = {
        "success_probability": 0.38,
        "expected_ev_delta": 0.08,
        "expected_pnl_delta": 1500.0,
        "main_failure_modes": [
            "window_regression",
            "small_increment",
            "late_strong_cost_proxy_inversion",
        ],
        "confidence_reason": (
            "VBB breadth and high-close support were accepted; VCP cost/liquidity "
            "was positive but narrowly below threshold. This is a distinct VBB "
            "cost/liquidity field with broader selected-trade coverage."
        ),
        "recorded_at": "2026-05-29T03:06:56+00:00",
    }
    actual_success = 1 if gate4_passed else 0
    calibration = {
        "actual_decision": decision,
        "actual_success": actual_success,
        "predicted_success_probability": prediction["success_probability"],
        "brier_score": round((prediction["success_probability"] - actual_success) ** 2, 6),
        "expected_ev_delta": prediction["expected_ev_delta"],
        "actual_ev_delta": best["expected_value_score_delta"],
        "ev_prediction_error": base._round(best["expected_value_score_delta"] - prediction["expected_ev_delta"], 6),
        "expected_pnl_delta": prediction["expected_pnl_delta"],
        "actual_pnl_delta": best["total_pnl_delta"],
        "pnl_prediction_error": base._round(best["total_pnl_delta"] - prediction["expected_pnl_delta"], 2),
        "predicted_failure_modes": prediction["main_failure_modes"],
        "realized_failure_mode": "; ".join(best["gate4"]["failed_reasons"]) or None,
        "predicted_failure_mode_hit": any(
            item in "; ".join(best["gate4"]["failed_reasons"])
            for item in ["window_regression", "small_increment"]
        ),
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "The accepted VOLUME_BREADTH_BREAKOUT_PAPER source may have better "
            "replacement value when selected trades combine large signal-day "
            "dollar volume with a contained daily range. This is a free OHLCV "
            "cost/liquidity field known before next-open paper entry."
        ),
        "change_type": "default_off_paper_allocation",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": best["variant"]["id"],
        "prior_trial_count": 1,
        "nearby_prior_experiments": [
            "exp-20260526-014",
            "exp-20260528-018",
            "exp-20260528-022",
            "exp-20260527-905",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "orthogonal_free_ohlcv_cost_liquidity_field_on_accepted_vbb_adapter",
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": base.WINDOWS,
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "before_reference": "current accepted VBB adapter after exp-20260528-018 and exp-20260528-022",
            "execution_model": (
                "Before uses the accepted VBB paper overlay including "
                "breadth-intensity and signal-day high-close support. After uses "
                "the same selected VBB paper trades and applies the tested "
                "cost/liquidity support scalar only to rows meeting the "
                "predeclared dollar-volume and daily-range bucket."
            ),
        },
        "parameters": {
            "best_variant": best["variant"],
            "all_variants": VARIANTS,
            "before_adapter": "current accepted VBB adapter through exp-20260528-022",
            "support_condition": (
                "selected VBB trade signal-day dollar_volume >= threshold and "
                "signal-day (high-low)/close <= threshold"
            ),
            "paper_notional_usd": 10_000.0,
            "hold_days": 10,
            "locked_variables": [
                "VBB candidate definition",
                "VBB top-1 selection",
                "VBB breadth pass thresholds",
                "accepted breadth-intensity support",
                "accepted high-close support",
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
                "entries may deserve more notional when expected execution cost "
                "is lower, proxied by high dollar volume and contained signal-day "
                "range. This follows the playbook's free-data candidate-pool "
                "direction and avoids LLM/state-surface retunes."
            ),
            "2_history_check": {
                "accepted_vbb": (
                    "exp-20260526-014 accepted the shared VBB paper adapter; "
                    "exp-20260528-018 accepted breadth-intensity support; "
                    "exp-20260528-022 accepted signal-day high-close support."
                ),
                "nearby_failures": (
                    "exp-20260527-905 rejected VCP cost/liquidity only because "
                    "the EV lift narrowly missed its source-EV threshold; this "
                    "run is VBB-specific and uses current accepted VBB trades."
                ),
                "difference": (
                    "This does not change VBB discovery, breadth thresholds, "
                    "top-N, hold, exits, or live filters; it tests one new "
                    "production-visible cost/liquidity capital allocation field."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Same three docs/backtesting.md windows; before=current accepted "
                "VBB adapter, after=best predeclared cost/liquidity support "
                "variant. Require positive aggregate EV/PnL, no EV/PnL-regressed "
                "window, >=10 adjusted trades across all windows, drawdown drift "
                "<=0.5pp, survival >=5%, and concentration inside guardrails."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260529_004_vbb_cost_liquidity_support.py"
            ),
        },
        "gate1": {
            "baseline_artifact": "data/experiments/exp-20260528-022/vbb_signal_day_high_close_support.json",
            "before_metrics_are_current_accepted_vbb_adapter": True,
            "core_metrics": core_metrics,
        },
        "gate2": {
            "open_positions": gate2,
            "runtime_fields": [
                "canonical OHLCV signal-day Date/Open/High/Low/Close/Volume rows",
                "selected VBB paper trade signal_date",
                "selected VBB paper trade dollar_volume",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": gate2["passed"],
            "note": (
                "The tested field is computed from OHLCV known after signal-date "
                "close and before next-open paper entry."
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
        "cost_liquidity_audit": best["cost_liquidity_audit"],
        "variant_results": variant_summary,
        "expected_value_score_delta": best["expected_value_score_delta"],
        "total_pnl_delta": best["total_pnl_delta"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "prediction": prediction,
        "calibration": calibration,
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
            "Accepted: cost/liquidity support passed Gate 4 versus the current "
            "accepted VBB adapter and is retained only in the shared default-off "
            "VBB paper adapter. Live/default orders remain disabled."
            if gate4_passed
            else (
                "Rejected: cost/liquidity support did not improve the accepted "
                "VBB adapter robustly enough across all three windows. Do not "
                "add this field as a VBB notional support rule on the frozen sample."
            )
        ),
        "next_retry_requires": [
            "new_forward_vbb_closed_outcomes",
            "materially_different_vbb_replacement_value_field",
            "not_a_nearby_cost_liquidity_threshold_scalar_retry",
        ],
        "related_files": [
            base._repo_rel(Path(__file__)),
            "quant/volume_breadth_breakout_paper_sleeve.py",
            "experiments/cards/exp-20260529-004.md",
            base._repo_rel(OUT_JSON),
            base._repo_rel(LOG_JSON),
            base._repo_rel(TICKET_JSON),
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
        audit = payload["cost_liquidity_audit"][label]
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
        f"# {EXPERIMENT_ID} VBB Cost/Liquidity Support",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        (
            "Single variable: on top of the current accepted VBB paper adapter, "
            "selected VBB paper trades receive small default-off paper notional "
            "support when signal-day dollar volume and daily range meet the best "
            "predeclared cost/liquidity bucket."
        ),
        "",
        f"Best variant: `{payload['parameters']['best_variant']['id']}`.",
        "",
        "## Three-Window Result Versus Current VBB",
        "",
        *rows,
        "",
        "## Aggregate",
        "",
        f"- EV delta vs current VBB: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
        f"- PnL delta vs current VBB: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
        f"- adjusted trades: `{payload['gate4']['target_trade_summary']['total_trade_count']}`",
        f"- max drawdown drift: `{aggregate['max_drawdown_delta_max']}`",
        "",
        "## Gate 4",
        "",
        "```json",
        json.dumps(payload["gate4"], indent=2, sort_keys=True),
        "```",
        "",
        "## Variant Sweep",
        "",
        "```json",
        json.dumps(payload["variant_results"], indent=2, sort_keys=True),
        "```",
        "",
        "## Cost/Liquidity Audit",
        "",
        "```json",
        json.dumps(payload["cost_liquidity_audit"], indent=2, sort_keys=True),
        "```",
        "",
        "## Production Impact",
        "",
        (
            "Replay-only/default-off paper scout unless accepted into shared "
            "VBB paper metadata. No live orders, core universe, core ranking, "
            "core sizing, exits, LLM/news, or trade-enabled behavior changed."
        ),
        "",
        "No JavaScript was used.",
        "",
    ]
    return "\n".join(lines)


def _update_ticket(payload: dict[str, Any]) -> None:
    base, _shadow = _BASE_SHADOW
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "VBB cost/liquidity support",
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
    base._write_json(TICKET_JSON, ticket)


def _persist(payload: dict[str, Any]) -> None:
    base, _shadow = _BASE_SHADOW
    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, payload)
    _update_ticket(payload)
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
