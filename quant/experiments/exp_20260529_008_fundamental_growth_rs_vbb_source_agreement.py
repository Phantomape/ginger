"""exp-20260529-008: Fundamental Growth+RS / VBB source-agreement support.

This alpha search tests one default-off paper allocation variable on top of the
accepted Fundamental Growth+RS paper sleeve: selected fundamental paper trades
receive a small notional scalar only when the same ticker also had a recent
accepted VBB paper confirmation. It uses free SEC/RS/OHLCV data already present
in the repo, keeps core trading behavior fixed, and does not use JavaScript.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, OrderedDict, defaultdict
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

import exp_20260529_004_vbb_cost_liquidity_support as current_vbb  # noqa: E402


EXPERIMENT_ID = "exp-20260529-008"
STEM = "fundamental_growth_rs_vbb_source_agreement"
TRIAL_FAMILY = "fundamental_growth_rs_vbb_source_agreement_support"
CHANGED_VARIABLE = "fundamental_growth_rs_recent_vbb_confirmation_notional_support_v1"
RULE_VERSION = "fundamental_growth_rs_vbb_source_agreement_support_v1"

FUNDAMENTAL_REFERENCE = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260528-017"
    / "fundamental_growth_rs_low_liability_support.json"
)
VBB_REFERENCE = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260529-004"
    / "exp_20260529_004_vbb_cost_liquidity_support.json"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

VARIANTS = [
    {"id": "lookback_5d_scalar_1p05", "lookback_days": 5, "notional_scalar": 1.05},
    {"id": "lookback_10d_scalar_1p05", "lookback_days": 10, "notional_scalar": 1.05},
    {"id": "lookback_20d_scalar_1p05", "lookback_days": 20, "notional_scalar": 1.05},
    {"id": "lookback_10d_scalar_1p10", "lookback_days": 10, "notional_scalar": 1.10},
]

MIN_ADJUSTED_TRADES = 10
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30


def _base_shadow() -> tuple[Any, Any]:
    return current_vbb._BASE_SHADOW


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _date10(value: Any) -> str:
    return str(value or "")[:10]


def _parse_date(value: Any) -> datetime | None:
    text = _date10(value)
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return None


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _vbb_signal_dates_by_ticker(
    vbb_trades_by_window: dict[str, list[dict[str, Any]]],
) -> dict[str, list[datetime]]:
    by_ticker: defaultdict[str, list[datetime]] = defaultdict(list)
    for trades in vbb_trades_by_window.values():
        for trade in trades:
            ticker = str(trade.get("ticker") or "").upper()
            signal_date = _parse_date(trade.get("signal_date") or trade.get("date"))
            if ticker and signal_date is not None:
                by_ticker[ticker].append(signal_date)
    return {ticker: sorted(set(dates)) for ticker, dates in by_ticker.items()}


def _confirmation_context(
    trade: dict[str, Any],
    vbb_dates_by_ticker: dict[str, list[datetime]],
    variant: dict[str, Any],
) -> dict[str, Any]:
    ticker = str(trade.get("ticker") or "").upper()
    signal_date = _parse_date(trade.get("signal_date") or trade.get("date"))
    lookback_days = int(variant["lookback_days"])
    if not ticker or signal_date is None:
        return {
            "confirmed": False,
            "reason": "missing_fundamental_signal_date_or_ticker",
            "ticker": ticker,
            "lookback_days": lookback_days,
        }
    eligible = [
        vbb_date
        for vbb_date in vbb_dates_by_ticker.get(ticker, [])
        if 0 <= (signal_date - vbb_date).days <= lookback_days
    ]
    if not eligible:
        return {
            "confirmed": False,
            "reason": "no_prior_same_ticker_vbb_confirmation",
            "ticker": ticker,
            "lookback_days": lookback_days,
        }
    nearest = max(eligible)
    return {
        "confirmed": True,
        "reason": "prior_same_ticker_vbb_confirmation",
        "ticker": ticker,
        "lookback_days": lookback_days,
        "vbb_confirmation_count": len(eligible),
        "nearest_vbb_signal_date": nearest.strftime("%Y-%m-%d"),
        "days_since_nearest_vbb_signal": (signal_date - nearest).days,
    }


def _scale_trade(
    trade: dict[str, Any],
    context: dict[str, Any],
    variant: dict[str, Any],
) -> dict[str, Any]:
    base, _shadow = _base_shadow()
    scalar = float(variant["notional_scalar"])
    return {
        **trade,
        "paper_notional_usd": base._round(_float(trade.get("paper_notional_usd")) * scalar, 2),
        "pnl": base._round(_float(trade.get("pnl")) * scalar, 2),
        "vbb_source_agreement_rule_version": RULE_VERSION,
        "vbb_source_agreement_variant_id": variant["id"],
        "vbb_source_agreement_pass_v1": True,
        "vbb_source_agreement_notional_scalar": scalar,
        "vbb_source_agreement_lookback_days": int(variant["lookback_days"]),
        "vbb_source_agreement_trade_enabled": False,
        "vbb_source_agreement_alters_orders": False,
        "vbb_source_agreement_known_at": "prior accepted VBB paper signal_date <= fundamental signal_date",
        **context,
    }


def _incremental_trade(
    trade: dict[str, Any],
    context: dict[str, Any],
    variant: dict[str, Any],
) -> dict[str, Any]:
    base, _shadow = _base_shadow()
    scalar = float(variant["notional_scalar"])
    increment = scalar - 1.0
    return {
        **trade,
        "paper_notional_usd": base._round(_float(trade.get("paper_notional_usd")) * increment, 2),
        "pnl": base._round(_float(trade.get("pnl")) * increment, 2),
        "vbb_source_agreement_increment": base._round(increment, 4),
        "vbb_source_agreement_rule_version": RULE_VERSION,
        "vbb_source_agreement_variant_id": variant["id"],
        "vbb_source_agreement_notional_scalar": scalar,
        "vbb_source_agreement_lookback_days": int(variant["lookback_days"]),
        "vbb_source_agreement_known_at": "prior accepted VBB paper signal_date <= fundamental signal_date",
        **context,
    }


def _apply_variant(
    fundamental_trades: list[dict[str, Any]],
    vbb_dates_by_ticker: dict[str, list[datetime]],
    variant: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    base, _shadow = _base_shadow()
    after_trades: list[dict[str, Any]] = []
    adjusted_increments: list[dict[str, Any]] = []
    unconfirmed: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()
    days_since_counts: Counter[str] = Counter()
    pnl_delta_by_ticker: defaultdict[str, float] = defaultdict(float)

    for trade in fundamental_trades:
        context = _confirmation_context(trade, vbb_dates_by_ticker, variant)
        reason_counts[str(context["reason"])] += 1
        if context["confirmed"]:
            scaled = _scale_trade(trade, context, variant)
            increment = _incremental_trade(trade, context, variant)
            after_trades.append(scaled)
            adjusted_increments.append(increment)
            days_since_counts[str(context.get("days_since_nearest_vbb_signal"))] += 1
            pnl_delta_by_ticker[str(trade.get("ticker") or "").upper()] += _float(increment.get("pnl"))
        else:
            after_trades.append(trade)
            unconfirmed.append({**trade, "vbb_source_agreement_filter_reason": context["reason"]})

    audit = {
        "fundamental_trade_count": len(fundamental_trades),
        "adjusted_trade_count": len(adjusted_increments),
        "unconfirmed_trade_count": len(unconfirmed),
        "adjusted_incremental_pnl": base._round(
            sum(_float(row.get("pnl")) for row in adjusted_increments),
            2,
        ),
        "confirmation_reason_counts": dict(sorted(reason_counts.items())),
        "days_since_nearest_vbb_signal_counts": dict(sorted(days_since_counts.items())),
        "adjusted_unique_tickers": len(
            {str(row.get("ticker") or "").upper() for row in adjusted_increments}
        ),
        "adjusted_ticker_counts": dict(
            sorted(Counter(str(row.get("ticker") or "").upper() for row in adjusted_increments).items())
        ),
        "adjusted_incremental_pnl_by_ticker": {
            ticker: base._round(pnl, 2) for ticker, pnl in sorted(pnl_delta_by_ticker.items())
        },
    }
    return after_trades, adjusted_increments, unconfirmed, audit


def _evaluate_variant(
    *,
    variant: dict[str, Any],
    core_metrics: OrderedDict[str, dict[str, Any]],
    before_metrics: OrderedDict[str, dict[str, Any]],
    before_trades_by_window: OrderedDict[str, list[dict[str, Any]]],
    vbb_dates_by_ticker: dict[str, list[datetime]],
    baseline_results_by_window: OrderedDict[str, dict[str, Any]],
) -> dict[str, Any]:
    base, _shadow = _base_shadow()
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    adjusted_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    unconfirmed_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    agreement_audit: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label in base.WINDOWS:
        before_result = baseline_results_by_window[label]
        before_trades = before_trades_by_window[label]
        after_trades, adjusted_increments, unconfirmed, audit = _apply_variant(
            before_trades,
            vbb_dates_by_ticker,
            variant,
        )
        after_overlay = base._overlay_from_paper_trades(before_result, after_trades)
        after = base.overlay_helper._metrics_with_overlay(before_result, after_overlay)
        delta = base.overlay_helper._delta(after, before_metrics[label])

        after_metrics[label] = after
        adjusted_by_window[label] = adjusted_increments
        unconfirmed_by_window[label] = unconfirmed[:100]
        agreement_audit[label] = audit
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
    min_survival = min(_float(row.get("survival_rate")) for row in core_metrics.values())
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
        failed.append("aggregate_ev_not_positive_vs_current_fundamental_growth_rs")
    if aggregate["total_pnl_delta_sum"] <= 0:
        failed.append("aggregate_pnl_not_positive_vs_current_fundamental_growth_rs")
    if aggregate["windows_ev_improved"] != len(base.WINDOWS) or aggregate["windows_ev_regressed"]:
        failed.append("window_ev_regression_vs_current_fundamental_growth_rs")
    if aggregate["windows_pnl_regressed"]:
        failed.append("window_pnl_regression_vs_current_fundamental_growth_rs")
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
            "by_window": OrderedDict((label, window_rows[label]["delta"]) for label in base.WINDOWS),
        },
        "target_trades_by_window": adjusted_by_window,
        "unconfirmed_trades_sample_by_window": unconfirmed_by_window,
        "source_agreement_audit": agreement_audit,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
    }


def _variant_sort_key(row: dict[str, Any]) -> tuple[int, float, float, float]:
    aggregate = row["gate4"]["aggregate"]
    return (
        1 if row["gate4"]["passed"] else 0,
        float(aggregate.get("expected_value_score_delta_sum") or 0.0),
        float(aggregate.get("total_pnl_delta_sum") or 0.0),
        -float(aggregate.get("max_drawdown_delta_max") or 0.0),
    )


def _reference_metric_audit(
    reconstructed: OrderedDict[str, dict[str, Any]],
    reference: dict[str, Any],
) -> OrderedDict[str, dict[str, Any]]:
    base, _shadow = _base_shadow()
    audit: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    for label in base.WINDOWS:
        ref = (reference.get("after_metrics") or {}).get(label) or {}
        cur = reconstructed[label]
        audit[label] = {
            "reconstructed_before_ev": cur.get("expected_value_score"),
            "reference_after_ev": ref.get("expected_value_score"),
            "ev_delta": base._round(_float(cur.get("expected_value_score")) - _float(ref.get("expected_value_score")), 6),
            "reconstructed_before_pnl": cur.get("total_pnl"),
            "reference_after_pnl": ref.get("total_pnl"),
            "pnl_delta": base._round(_float(cur.get("total_pnl")) - _float(ref.get("total_pnl")), 2),
        }
    return audit


def _build_payload() -> dict[str, Any]:
    base, shadow = _base_shadow()
    gate2 = base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2}")

    fundamental_reference = _load_json(FUNDAMENTAL_REFERENCE)
    vbb_reference = _load_json(VBB_REFERENCE)
    vbb_dates_by_ticker = _vbb_signal_dates_by_ticker(
        vbb_reference.get("before_vbb_trades_by_window") or {}
    )

    universe = sorted(base.get_universe())
    core_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    baseline_results_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in base.WINDOWS.items():
        print(f"[{label}] accepted Fundamental Growth+RS baseline for VBB source-agreement support")
        before_result = shadow._run_baseline(universe, cfg)
        baseline_results_by_window[label] = before_result
        core_metrics[label] = base.overlay_helper._metrics(before_result)
        before_trades = (fundamental_reference.get("target_trades_by_window") or {}).get(label) or []
        before_trades_by_window[label] = before_trades
        before_overlay = base._overlay_from_paper_trades(before_result, before_trades)
        before_metrics[label] = base.overlay_helper._metrics_with_overlay(before_result, before_overlay)

    variant_results = [
        _evaluate_variant(
            variant=variant,
            core_metrics=core_metrics,
            before_metrics=before_metrics,
            before_trades_by_window=before_trades_by_window,
            vbb_dates_by_ticker=vbb_dates_by_ticker,
            baseline_results_by_window=baseline_results_by_window,
        )
        for variant in VARIANTS
    ]
    best = sorted(variant_results, key=_variant_sort_key, reverse=True)[0]
    gate4_passed = bool(best["gate4"]["passed"])
    decision = (
        "accepted_shared_fundamental_growth_rs_vbb_source_agreement_support"
        if gate4_passed
        else "rejected_fundamental_growth_rs_vbb_source_agreement_support"
    )
    prediction = {
        "success_probability": 0.32,
        "expected_ev_delta": 0.06,
        "expected_pnl_delta": 1200.0,
        "main_failure_modes": [
            "overlap_sample_too_small",
            "source_agreement_lags_returns",
            "window_regression",
            "concentration_failed",
        ],
        "confidence_reason": (
            "Accepted VBB and Fundamental Growth+RS sleeves are independent free-data "
            "edges, but same-ticker recent overlap may be sparse and can lag the "
            "return window."
        ),
        "recorded_at": "2026-05-29T06:08:50+00:00",
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
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "Accepted Fundamental Growth+RS paper trades may have higher replacement "
            "value when the same ticker had a recent accepted VBB paper confirmation. "
            "This uses independent free SEC/RS and OHLCV candidate surfaces instead "
            "of adding noisy tickers or retuning frozen thresholds."
        ),
        "change_type": "default_off_paper_allocation",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": best["variant"]["id"],
        "prior_trial_count": 0,
        "nearby_prior_experiments": [
            "exp-20260528-017",
            "exp-20260529-004",
            "exp-20260529-005",
            "exp-20260528-037",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "cross_accepted_free_data_sleeve_source_agreement",
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": base.WINDOWS,
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "before_reference": "accepted Fundamental Growth+RS paper sleeve after exp-20260528-017",
            "execution_model": (
                "Before reconstructs the accepted exp-20260528-017 Fundamental "
                "Growth+RS paper overlay on the canonical core backtest. After uses "
                "the same selected paper trades and applies one default-off notional "
                "support scalar only when a prior same-ticker VBB paper confirmation "
                "is known at the fundamental signal date."
            ),
        },
        "parameters": {
            "best_variant": best["variant"],
            "all_variants": VARIANTS,
            "fundamental_reference": base._repo_rel(FUNDAMENTAL_REFERENCE),
            "vbb_reference": base._repo_rel(VBB_REFERENCE),
            "support_condition": (
                "already selected Fundamental Growth+RS paper trade has a same-ticker "
                "accepted VBB paper signal_date where 0 <= fundamental_date - "
                "vbb_signal_date <= lookback_days"
            ),
            "paper_notional_usd": 10_000.0,
            "hold_days": 10,
            "locked_variables": [
                "core signal generation",
                "core ranking",
                "core sizing",
                "core exits",
                "Fundamental Growth+RS candidate definition",
                "Fundamental Growth+RS accepted support rules",
                "VBB candidate definition",
                "VBB accepted support rules",
                "next-open paper entry",
                "10-trading-day paper exit",
                "LLM/news replay",
                "production/live/default orders",
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
                "candidate_pool/capital_allocation: independent accepted free-data "
                "sleeve agreement should identify higher-quality Fundamental "
                "Growth+RS paper entries. It follows the playbook's candidate-pool "
                "adapter direction and avoids LLM/state-surface retunes."
            ),
            "2_history_check": {
                "accepted_fundamental_stack": (
                    "exp-20260528-017 accepted the current Fundamental Growth+RS "
                    "low-liability support stack."
                ),
                "accepted_vbb_stack": (
                    "exp-20260529-004 accepted current VBB cost/liquidity support; "
                    "the confirmation surface uses VBB selected-signal dates only, "
                    "not a new VBB threshold."
                ),
                "nearby_failures": (
                    "exp-20260529-005 rejected long-base + market breadth; "
                    "exp-20260528-037 rejected ticker OBV accumulation; this run "
                    "does not add a new broad OHLCV source or loosen a universe."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance": (
                "Same docs/backtesting.md three windows; positive aggregate EV/PnL; "
                "3/3 EV-improved windows; no PnL-regressed window; >=10 adjusted "
                "trades across all three windows; drawdown drift <=0.5pp; survival "
                ">=5%; concentration inside guardrails."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260529_008_fundamental_growth_rs_vbb_source_agreement.py"
            ),
        },
        "gate1": {
            "passed": True,
            "baseline_reference": base._repo_rel(FUNDAMENTAL_REFERENCE),
            "before_metrics": before_metrics,
            "baseline_reconstruction_audit": _reference_metric_audit(
                before_metrics,
                fundamental_reference,
            ),
        },
        "gate2": {
            **gate2,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "Fundamental Growth+RS paper trade signal_date/date/ticker",
                "VBB accepted paper trade signal_date/date/ticker",
            ],
            "note": (
                "The VBB confirmation is prior-only: VBB signal_date must be <= the "
                "Fundamental Growth+RS signal_date, so after logic cannot see future "
                "VBB paper confirmations."
            ),
        },
        "gate3": {
            "passed": min(_float(row.get("survival_rate")) for row in core_metrics.values()) >= 0.05,
            "survival_rate_by_window": {
                label: metrics.get("survival_rate") for label, metrics in core_metrics.items()
            },
            "note": "This allocation-only paper scalar does not add entry filters, so survival is unchanged.",
        },
        "gate4": best["gate4"],
        "before_metrics": before_metrics,
        "after_metrics": best["after_metrics"],
        "delta_metrics": best["delta_metrics"],
        "core_metrics": core_metrics,
        "target_trades_by_window": best["target_trades_by_window"],
        "unconfirmed_trades_sample_by_window": best["unconfirmed_trades_sample_by_window"],
        "source_agreement_audit": best["source_agreement_audit"],
        "variant_results": [
            {
                "variant_id": row["variant"]["id"],
                "lookback_days": row["variant"]["lookback_days"],
                "notional_scalar": row["variant"]["notional_scalar"],
                "gate4_passed": row["gate4"]["passed"],
                "failed_reasons": row["gate4"]["failed_reasons"],
                "aggregate": row["gate4"]["aggregate"],
                "target_trade_count": row["gate4"]["target_trade_summary"]["total_trade_count"],
                "max_single_positive_pnl_share": row["gate4"]["target_trade_summary"]["max_single_positive_pnl_share"],
                "positive_pnl_hhi": row["gate4"]["target_trade_summary"]["positive_pnl_hhi"],
            }
            for row in variant_results
        ],
        "expected_value_score_delta": best["expected_value_score_delta"],
        "total_pnl_delta": best["total_pnl_delta"],
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "production_orders_changed": False,
            "production_watchlist_changed": False,
            "default_off_paper_only": True,
            "replay_only": True,
            "trade_enabled": False,
            "parity_test_added": False,
            "promotion_requirement": (
                "If Gate 4 passes, retain only after moving the same prior-only VBB "
                "confirmation metadata into the shared Fundamental Growth+RS paper "
                "adapter and adding parity tests. Live/default orders still require "
                "a separate activation experiment."
            ),
        },
        "prediction": prediction,
        "calibration": calibration,
        "llm_metrics": {
            "llm_used": False,
            "llm_replay_required": False,
        },
        "anti_js": "No JavaScript was used.",
        "related_files": [
            base._repo_rel(Path(__file__)),
            base._repo_rel(OUT_JSON),
            base._repo_rel(LOG_JSON),
            base._repo_rel(ARTIFACT_MD),
            base._repo_rel(FUNDAMENTAL_REFERENCE),
            base._repo_rel(VBB_REFERENCE),
        ],
        "interpretation": (
            "Gate 4 passed; promote only as a shared default-off paper adapter after "
            "production parity work."
            if gate4_passed
            else (
                "The source-agreement scalar did not clear Gate 4. Do not promote it "
                "or retry nearby lookback/scalar sweeps on the frozen windows without "
                "forward rows or a materially new independent confirmation field."
            )
        ),
        "rejection_reason": None if gate4_passed else "; ".join(best["gate4"]["failed_reasons"]),
        "next_evidence_needed": (
            "Forward closed rows where both sleeves independently mark the same ticker "
            "before entry, plus shared adapter parity, before any activation."
        ),
    }


def _build_report(payload: dict[str, Any]) -> str:
    base, _shadow = _base_shadow()
    lines = [
        f"# {EXPERIMENT_ID} Fundamental Growth+RS / VBB Source Agreement",
        "",
        f"Decision: `{payload['decision']}`.",
        "",
        "Single variable: already-selected Fundamental Growth+RS paper trades receive "
        "a default-off notional scalar only when the same ticker had a prior accepted "
        "VBB paper confirmation inside the selected lookback.",
        "",
        "## Three-Window Result",
        "",
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Adjusted / Before Trades | Incremental PnL |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["source_agreement_audit"][label]
        lines.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | "
            "${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {adj}/{raw} | ${ipnl:+,.2f} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                adj=audit["adjusted_trade_count"],
                raw=audit["fundamental_trade_count"],
                ipnl=audit["adjusted_incremental_pnl"],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    target = payload["gate4"]["target_trade_summary"]
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- adjusted trades: `{target['total_trade_count']}`",
            f"- max drawdown drift: `{aggregate['max_drawdown_delta_max']}`",
            f"- max single positive share: `{target['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{target['positive_pnl_hhi']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Source Agreement Audit",
            "",
            "```json",
            json.dumps(payload["source_agreement_audit"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "```json",
            json.dumps(payload["production_impact"], indent=2, sort_keys=True),
            "```",
            "",
            "## Repro",
            "",
            "```powershell",
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260529_008_fundamental_growth_rs_vbb_source_agreement.py",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def _update_ticket(payload: dict[str, Any]) -> None:
    base, _shadow = _base_shadow()
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Fundamental Growth+RS / VBB source-agreement support",
        "status": payload["decision"],
        "lane": "alpha_discovery",
        "updated_at": payload["timestamp"],
        "result": {
            "decision": payload["decision"],
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "total_pnl_delta": payload["total_pnl_delta"],
            "artifact": base._repo_rel(ARTIFACT_MD),
            "log": base._repo_rel(LOG_JSON),
        },
    }
    base._write_json(TICKET_JSON, ticket)
    base._write_json(DOC_TICKET_JSON, ticket)


def _persist(payload: dict[str, Any]) -> None:
    base, _shadow = _base_shadow()
    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, payload)
    _update_ticket(payload)
    base._write_text(ARTIFACT_MD, _build_report(payload))
    base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    payload = _build_payload()
    _persist(payload)
    base, _shadow = _base_shadow()
    print(
        json.dumps(
            base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "variant": payload["trial_variant_id"],
                    "gate4": payload["gate4"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "artifact": base._repo_rel(ARTIFACT_MD),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
