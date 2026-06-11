"""exp-20260611-014: distribution absorption precompression scout.

Replay-only alpha search. This tests one fixed candidate-pool policy: start
from the accepted distribution-day absorption leadership candidate builder, but
only admit candidates whose five pre-signal sessions show a volatility
compression base versus their own 20-session range.

This is not promoted to production. No shared policy, live order path, live
ranking, sizing, exits, LLM/news behavior, or watchlist behavior changes. No
JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from copy import deepcopy
from pathlib import Path
from typing import Any

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework


EXPERIMENT_ID = "exp-20260611-014"
STEM = "distribution_absorption_precompression"
TRIAL_FAMILY = "distribution_absorption_intersection"
TRIAL_VARIANT_ID = "distribution_absorption_pre_pressure_compression_filter_v1"
CHANGED_VARIABLE = TRIAL_VARIANT_ID
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = framework.REPO_ROOT
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import distribution_day_absorption_leadership_paper_sleeve as distribution  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260611_014_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

PRECOMPRESSION_LOOKBACK_DAYS = 5
COMPRESSION_REFERENCE_DAYS = 20
MAX_PRECOMPRESSION_AVG_RANGE_PCT = 0.055
MAX_PRECOMPRESSION_RANGE_RATIO_VS_20D = 0.92
MAX_PRECOMPRESSION_CLOSE_SPAN_PCT = 0.105
MAX_PRECOMPRESSION_ABS_RETURN_SUM = 0.24

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

ACCEPTED_DISTRIBUTION_COMPARATOR = {
    "experiment_id": "exp-20260611-007",
    "decision": "accepted_distribution_day_absorption_leadership_shared_adapter",
    "expected_value_score_delta_sum": 0.5286,
    "total_pnl_delta_sum": 10432.91,
    "target_trade_count": 113,
}

ACCEPTED_COMPRESSION_COMPARATOR = {
    "experiment_id": "exp-20260608-013",
    "decision": "accepted_compression_breakout_like_source",
    "expected_value_score_delta_sum": 0.1608,
    "total_pnl_delta_sum": 2248.98,
}

PREDICTION = {
    "success_probability": 0.14,
    "expected_ev_delta": 0.18,
    "expected_pnl_delta": 3000.0,
    "main_failure_modes": [
        "sample_thinning",
        "old_thin_regression",
        "accepted_distribution_comparator_not_beaten",
        "compression_overlap_not_incremental",
    ],
    "confidence_reason": (
        "Both source mechanisms have prior accepted evidence, but recent "
        "source additions and confirmation layers usually failed. This is a "
        "low-confidence replay scout to avoid building shared production code "
        "before incremental data shape is known."
    ),
    "recorded_at": "2026-06-11T11:08:44Z",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "live_realism_evaluated": False,
    "live_ready": False,
    "uses_llm": False,
    "uses_free_ohlcv": True,
    "parity_note": (
        "No production code changed. A positive result would remain only a "
        "replay lead until a shared default-off helper computes the same "
        "pre-signal compression features, accepted distribution absorption "
        "candidate fields, next-open paper entry, costs, cooldown, and Gate 4 "
        "comparators in both historical replay and daily production snapshots."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: after accepted SPY/QQQ distribution pressure, an "
        "absorption leader whose prior five sessions compressed versus its "
        "own 20-session range may represent supply contraction before "
        "reclaim, improving replacement value versus the accepted distribution "
        "source."
    ),
    "2_history_check": {
        "exp-20260611-007": (
            "Accepted shared default-off distribution-day absorption adapter; "
            "aggregate EV +0.5286 and PnL +$10,432.91 with 113 target trades."
        ),
        "exp-20260611-009": (
            "Pocket-pivot style confirmation was rejected; raw price-volume "
            "confirmation can thin samples without incremental edge."
        ),
        "exp-20260611-011": (
            "Market follow-through day source was rejected; broad market "
            "confirmation alone was not enough."
        ),
        "exp-20260608-013": (
            "Accepted compression-like source comparator; this experiment must "
            "beat it as well as the distribution comparator to be more than an "
            "overlap relabel."
        ),
        "difference": (
            "This is a fixed intersection filter on an accepted distribution "
            "candidate builder, not a distribution-threshold retune. Because "
            "the incremental data shape is uncertain and recent additive "
            "confirmations failed, it is replay-only scout rather than shared "
            "paper-first promotion."
        ),
    },
    "3_single_causal_variable": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Pass only if "
        "aggregate EV/PnL improve, no EV/PnL window regression, at least 20 "
        "target trades across all 3 windows, survival >=5%, drawdown drift "
        "<=0.5pp, concentration passes, and both accepted distribution and "
        "compression comparators are beaten. Even if positive, replay-only "
        "status is not accepted production alpha."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260611_014_distribution_absorption_precompression.py"
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _finite_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _row_value(row: dict[str, Any], key: str) -> float | None:
    return _finite_float(row.get(key) if key in row else row.get(key.capitalize()))


def _normalise_snapshot(
    snapshot: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for ticker, rows in snapshot.items():
        normalised: list[dict[str, Any]] = []
        for row in rows:
            date_value = str(row.get("date") or row.get("Date") or "")[:10]
            open_value = _row_value(row, "open")
            high = _row_value(row, "high")
            low = _row_value(row, "low")
            close = _row_value(row, "close")
            volume = _row_value(row, "volume")
            if not date_value or None in (open_value, high, low, close, volume):
                continue
            normalised.append(
                {
                    "date": date_value,
                    "open": open_value,
                    "high": high,
                    "low": low,
                    "close": close,
                    "volume": volume,
                }
            )
        if normalised:
            out[str(ticker).upper()] = normalised
    return out


def _daily_return(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx < 1:
        return None
    prior = _finite_float(rows[idx - 1].get("close"))
    close = _finite_float(rows[idx].get("close"))
    if prior is None or prior <= 0 or close is None:
        return None
    return (close / prior) - 1.0


def _range_pct(row: dict[str, Any]) -> float | None:
    high = _finite_float(row.get("high"))
    low = _finite_float(row.get("low"))
    close = _finite_float(row.get("close"))
    if high is None or low is None or close is None or close <= 0:
        return None
    return max(0.0, (high - low) / close)


def _avg(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _precompression_features(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    candidate: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    ticker = str(candidate.get("ticker") or "").upper()
    signal_date = str(candidate.get("date") or "")[:10]
    rows = rows_by_ticker.get(ticker) or []
    idx_by_date = {str(row.get("date") or "")[:10]: pos for pos, row in enumerate(rows)}
    idx = idx_by_date.get(signal_date)
    if idx is None:
        return None, "missing_signal_date"
    if idx < COMPRESSION_REFERENCE_DAYS:
        return None, "insufficient_compression_history"

    prior_rows = rows[idx - PRECOMPRESSION_LOOKBACK_DAYS : idx]
    reference_rows = rows[idx - COMPRESSION_REFERENCE_DAYS : idx]
    prior_ranges = [_range_pct(row) for row in prior_rows]
    reference_ranges = [_range_pct(row) for row in reference_rows]
    if any(value is None for value in prior_ranges + reference_ranges):
        return None, "missing_range_features"
    prior_range_values = [float(value) for value in prior_ranges if value is not None]
    reference_range_values = [
        float(value) for value in reference_ranges if value is not None
    ]
    prior_avg_range = _avg(prior_range_values)
    reference_avg_range = _avg(reference_range_values)
    if prior_avg_range is None or reference_avg_range is None or reference_avg_range <= 0:
        return None, "invalid_range_reference"
    compression_ratio = prior_avg_range / reference_avg_range

    closes = [_finite_float(row.get("close")) for row in prior_rows]
    if any(value is None or value <= 0 for value in closes):
        return None, "missing_prior_closes"
    close_values = [float(value) for value in closes if value is not None]
    close_span_pct = (max(close_values) / min(close_values)) - 1.0

    abs_return_sum = 0.0
    for pos in range(idx - PRECOMPRESSION_LOOKBACK_DAYS + 1, idx):
        ret = _daily_return(rows, pos)
        if ret is None:
            return None, "missing_prior_returns"
        abs_return_sum += abs(float(ret))

    if prior_avg_range > MAX_PRECOMPRESSION_AVG_RANGE_PCT:
        return None, "prior_range_too_wide"
    if compression_ratio > MAX_PRECOMPRESSION_RANGE_RATIO_VS_20D:
        return None, "not_compressed_vs_20d"
    if close_span_pct > MAX_PRECOMPRESSION_CLOSE_SPAN_PCT:
        return None, "prior_close_span_too_wide"
    if abs_return_sum > MAX_PRECOMPRESSION_ABS_RETURN_SUM:
        return None, "prior_abs_return_sum_too_high"

    return (
        {
            "precompression_lookback_days": PRECOMPRESSION_LOOKBACK_DAYS,
            "compression_reference_days": COMPRESSION_REFERENCE_DAYS,
            "precompression_avg_range_pct": round(prior_avg_range, 6),
            "precompression_reference_avg_range_pct": round(reference_avg_range, 6),
            "precompression_range_ratio_vs_20d": round(compression_ratio, 6),
            "precompression_close_span_pct": round(close_span_pct, 6),
            "precompression_abs_return_sum": round(abs_return_sum, 6),
            "precompression_known_at": "after_signal_day_close_before_next_open_paper_entry",
            "precompression_rule_version": RULE_VERSION,
        },
        None,
    )


def _apply_precompression_filter(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    passed: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()
    for candidate in candidates:
        features, reason = _precompression_features(
            rows_by_ticker=rows_by_ticker,
            candidate=candidate,
        )
        if features is None:
            reason_value = reason or "precompression_failed"
            rejected.append({**candidate, "precompression_filter_reason": reason_value})
            reason_counts[reason_value] += 1
            continue
        row = deepcopy(candidate)
        row.update(features)
        row["source"] = "DISTRIBUTION_ABSORPTION_PRECOMPRESSION_PAPER"
        row["source_rule_version"] = RULE_VERSION
        row["uses_free_ohlcv_only"] = True
        row["uses_llm"] = False
        row["trade_enabled"] = False
        row["known_at"] = "after_signal_day_close_before_next_open_paper_entry"
        passed.append(row)
    return (
        passed,
        rejected,
        {
            "raw_distribution_candidates": len(candidates),
            "precompression_passed_candidates": len(passed),
            "precompression_rejected_candidates": len(rejected),
            "precompression_rejection_reasons": dict(sorted(reason_counts.items())),
        },
    )


def _candidate_rows_for_window(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
]:
    entries_by_date = framework.shadow._baseline_entries(before_result)
    dates = [
        day
        for day in distribution._trading_dates(rows_by_ticker)
        if str(cfg["start"]) <= day <= str(cfg["end"])
    ]
    raw_candidates, contexts, scan = (
        distribution.build_distribution_day_absorption_leadership_candidate_rows(
            ohlcv_by_ticker=rows_by_ticker,
            dates=dates,
            sector_entries=sector_entries,
            core_entries_by_date=entries_by_date,
            config=distribution.DEFAULT_CONFIG,
        )
    )
    compressed_candidates, precompression_rejected, precompression_scan = (
        _apply_precompression_filter(
            rows_by_ticker=rows_by_ticker,
            candidates=raw_candidates,
        )
    )
    scan = {**scan, **precompression_scan}
    return raw_candidates, compressed_candidates, precompression_rejected, contexts, scan


def _target_trade_summary(
    target_trades_by_window: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    summary = framework.sleeve._target_trade_summary(target_trades_by_window)
    positive_by_ticker: Counter[str] = Counter()
    total_positive = 0.0
    for trades in target_trades_by_window.values():
        for trade in trades:
            pnl = _finite_float(trade.get("pnl"))
            ticker = str(trade.get("ticker") or "").upper()
            if pnl is None or pnl <= 0 or not ticker:
                continue
            positive_by_ticker[ticker] += pnl
            total_positive += pnl
    if total_positive > 0:
        shares = [value / total_positive for value in positive_by_ticker.values()]
        summary["max_single_positive_pnl_share"] = round(max(shares), 6)
        summary["positive_pnl_hhi"] = round(sum(share * share for share in shares), 6)
    summary["positive_pnl_by_ticker_top10"] = [
        {"ticker": ticker, "positive_pnl": round(value, 2)}
        for ticker, value in positive_by_ticker.most_common(10)
    ]
    return summary


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    max_single_share = target_summary.get("max_single_positive_pnl_share")
    positive_hhi = target_summary.get("positive_pnl_hhi")
    concentration_passed = (
        max_single_share is not None
        and float(max_single_share) <= MAX_SINGLE_POSITIVE_SHARE
        and positive_hhi is not None
        and float(positive_hhi) <= MAX_POSITIVE_HHI
    )
    ev_delta = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    failed: list[str] = []
    if ev_delta <= 0.0:
        failed.append("aggregate_ev_not_positive")
    if pnl_delta <= 0.0:
        failed.append("aggregate_pnl_not_positive")
    if int(aggregate["windows_ev_regressed"] or 0) > 0:
        failed.append("window_ev_regression")
    if int(aggregate["windows_pnl_regressed"] or 0) > 0:
        failed.append("window_pnl_regression")
    if int(aggregate["windows_ev_improved"] or 0) < 2:
        failed.append("fewer_than_two_ev_improved_windows")
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_summary["windows_with_target_trades"]) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if float(aggregate["max_drawdown_delta_max"] or 0.0) > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")
    if not concentration_passed:
        failed.append("target_concentration_failed")
    if ev_delta <= ACCEPTED_DISTRIBUTION_COMPARATOR["expected_value_score_delta_sum"]:
        failed.append("accepted_distribution_ev_comparator_not_beaten")
    if pnl_delta <= ACCEPTED_DISTRIBUTION_COMPARATOR["total_pnl_delta_sum"]:
        failed.append("accepted_distribution_pnl_comparator_not_beaten")
    if ev_delta <= ACCEPTED_COMPRESSION_COMPARATOR["expected_value_score_delta_sum"]:
        failed.append("accepted_compression_ev_comparator_not_beaten")
    if pnl_delta <= ACCEPTED_COMPRESSION_COMPARATOR["total_pnl_delta_sum"]:
        failed.append("accepted_compression_pnl_comparator_not_beaten")
    passed = not failed
    return {
        "passed": passed,
        "decision": (
            "positive_replay_lead_not_promoted_distribution_absorption_precompression"
            if passed
            else "rejected_distribution_absorption_precompression_candidate_pool"
        ),
        "failed_reasons": failed,
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "windows_pnl_improved": aggregate["windows_pnl_improved"],
        "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
        "target_trade_count": target_summary["total_trade_count"],
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_summary["windows_with_target_trades"],
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "max_drawdown_worse": aggregate["max_drawdown_delta_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "minimum_core_survival_rate": round(min_survival, 6),
        "survival_guard_passed": min_survival >= 0.05,
        "accepted_distribution_comparator": ACCEPTED_DISTRIBUTION_COMPARATOR,
        "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
        "target_concentration": {
            "passed": concentration_passed,
            "max_single_positive_pnl_share": max_single_share,
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": positive_hhi,
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
        },
    }


def _build_payload() -> dict[str, Any]:
    timestamp = framework._utc_now()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(framework.get_universe())
    sector_entries_all = framework._load_sector_entries()
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    raw_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    precompression_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    distribution_contexts_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    scan_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    warehouse_coverage_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] core baseline and distribution precompression replay")
        before_result = framework.shadow._run_baseline(universe, cfg)
        before = framework.overlay_helper._metrics(before_result)
        raw_snapshot = framework._load_window_snapshot(
            cfg=cfg,
            eligible_tickers=set(sector_entries_all),
        )
        rows_by_ticker = _normalise_snapshot(raw_snapshot)
        sector_entries = {
            ticker: meta
            for ticker, meta in sector_entries_all.items()
            if ticker in rows_by_ticker
        }
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(rows_by_ticker),
            "sector_known_candidate_ticker_count": len(sector_entries),
            "source": _repo_rel(framework.WAREHOUSE),
        }
        (
            raw_candidates,
            compressed_candidates,
            precompression_rejected,
            contexts,
            scan,
        ) = _candidate_rows_for_window(
            rows_by_ticker=rows_by_ticker,
            cfg=cfg,
            before_result=before_result,
            sector_entries=sector_entries,
        )
        selected_trades, selection_rejected = (
            distribution.select_distribution_day_absorption_leadership_paper_trades(
                rows_by_ticker=rows_by_ticker,
                candidates=compressed_candidates,
                config=distribution.DEFAULT_CONFIG,
            )
        )
        for trade in selected_trades:
            trade["window"] = label
            trade["intersection_rule_version"] = RULE_VERSION
        overlay = framework.sleeve._overlay_from_paper_trades(
            before_result,
            selected_trades,
        )
        after = framework.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = framework.overlay_helper._delta(after, before)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = selected_trades
        filtered_candidates_by_window[label] = (
            precompression_rejected[:120] + selection_rejected[:120]
        )
        raw_candidate_counts[label] = len(raw_candidates)
        precompression_candidate_counts[label] = len(compressed_candidates)
        distribution_contexts_by_window[label] = contexts[:30]
        scan_by_window[label] = scan
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected_trades),
            "raw_distribution_candidate_count": len(raw_candidates),
            "precompression_candidate_count": len(compressed_candidates),
            "distribution_pressure_day_count": len(contexts),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = framework._aggregate_window_rows(window_rows)
    target_summary = _target_trade_summary(target_trades_by_window)
    gate4 = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    status = "accepted" if gate4["passed"] else "rejected"
    decision = gate4["decision"]
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0))
            ** 2,
            6,
        ),
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "private_replay_candidate_pool_scout",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "nearby_prior_experiments": [
            "exp-20260611-007",
            "exp-20260611-009",
            "exp-20260611-011",
            "exp-20260608-013",
        ],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "fixed_intersection_of_two_accepted_ohlcv_mechanisms",
        "prediction": PREDICTION,
        "calibration": calibration,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "replay-only broad warehouse default-off paper overlay"
            ),
            "windows": framework.WINDOWS,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Signal uses only close-of-day OHLCV known after the signal "
                "date. Paper entry is the next available open with existing "
                "entry slippage; exit is the close 10 trading days after the "
                "signal with target-side sell slippage and ROUND_TRIP_COST_PCT."
            ),
        },
        "parameters": {
            "distribution_default_config": distribution.DEFAULT_CONFIG,
            "precompression_lookback_days": PRECOMPRESSION_LOOKBACK_DAYS,
            "compression_reference_days": COMPRESSION_REFERENCE_DAYS,
            "max_precompression_avg_range_pct": MAX_PRECOMPRESSION_AVG_RANGE_PCT,
            "max_precompression_range_ratio_vs_20d": (
                MAX_PRECOMPRESSION_RANGE_RATIO_VS_20D
            ),
            "max_precompression_close_span_pct": MAX_PRECOMPRESSION_CLOSE_SPAN_PCT,
            "max_precompression_abs_return_sum": MAX_PRECOMPRESSION_ABS_RETURN_SUM,
        },
        "gate_1_baseline": {
            "status": "recomputed_same_protocol",
            "baseline_result_file": _repo_rel(
                "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
            ),
            "before_metrics_by_window": before_metrics,
        },
        "gate_2_dependency_audit": {
            "status": "passed",
            "open_position_field_audit": gate2_open_positions,
            "minimum_required_fields_checked": ["entry_date", "target_price"],
            "candidate_runtime_fields_checked": [
                "date",
                "ticker",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "same_ticker_ab_overlap",
            ],
            "warehouse_coverage_by_window": warehouse_coverage_by_window,
        },
        "gate_3_signal_survival": {
            label: {
                "signals_generated": before_metrics[label].get("signals_generated"),
                "signals_survived": before_metrics[label].get("signals_survived"),
                "survival_rate": before_metrics[label].get("survival_rate"),
                "target_trade_count": len(target_trades_by_window[label]),
                "raw_distribution_candidate_count": raw_candidate_counts[label],
                "precompression_candidate_count": precompression_candidate_counts[label],
            }
            for label in framework.WINDOWS
        },
        "gate_4_before_after": {
            "window_rows": window_rows,
            "aggregate": aggregate,
            "target_trade_summary": target_summary,
            "gate": gate4,
        },
        "target_trades_by_window": target_trades_by_window,
        "filtered_candidates_sample_by_window": filtered_candidates_by_window,
        "distribution_contexts_sample_by_window": distribution_contexts_by_window,
        "scan_by_window": scan_by_window,
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "decision_basis": (
            "Accepted as replay lead only if all canonical Gate 4 constraints "
            "and both accepted comparators pass; otherwise reject and do not "
            "promote."
        ),
        "reflection": {
            "why_result_happened": None,
            "forbidden_near_neighbor_retry": (
                "Do not retry distribution-day absorption with another simple "
                "compression/range confirmation unless new evidence shows the "
                "filter adds replacement value beyond the accepted distribution "
                "and compression helpers."
            ),
            "new_evidence_required": (
                "Forward daily rows or a richer free data edge that explains "
                "which absorption leaders had genuine supply contraction, not "
                "just lower recent OHLCV range."
            ),
        },
    }


def _build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["gate_4_before_after"]["aggregate"]
    gate = payload["gate_4_before_after"]["gate"]
    reflection = payload.get("reflection") or {}
    lines = [
        f"# {EXPERIMENT_ID} Distribution Absorption Precompression",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Status: `{payload['status']}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        f"- Aggregate EV delta: `{aggregate['expected_value_score_delta_sum']:+.4f}`",
        f"- Aggregate PnL delta: `${aggregate['total_pnl_delta_sum']:+,.2f}`",
        f"- Target trades: `{gate['target_trade_count']}`",
        f"- Gate failures: `{', '.join(gate['failed_reasons']) or 'none'}`",
        "",
        "## Window Deltas",
        "",
    ]
    for label, row in payload["gate_4_before_after"]["window_rows"].items():
        delta = row["delta"]
        lines.append(
            "- "
            f"{label}: EV `{delta['expected_value_score']:+.4f}`, "
            f"PnL `${delta['total_pnl']:+,.2f}`, "
            f"trades `{row['target_trade_count']}`"
        )
    lines.extend(
        [
            "",
            "## Reflection",
            "",
            f"- Result explanation: {reflection.get('why_result_happened')}",
            (
                "- Forbidden retry: "
                f"{reflection.get('forbidden_near_neighbor_retry')}"
            ),
            (
                "- New evidence required: "
                f"{reflection.get('new_evidence_required')}"
            ),
            "- Production impact: replay-only; no production path changed.",
            (
                "- Reproduce: `.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\"
                "exp_20260611_014_distribution_absorption_precompression.py`"
            ),
            "",
        ]
    )
    return "\n".join(lines)


def _log_entry(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["gate_4_before_after"]["aggregate"]
    gate = payload["gate_4_before_after"]["gate"]
    changed_files = [
        "quant/experiments/exp_20260611_014_distribution_absorption_precompression.py",
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "status": payload["status"],
        "decision": payload["decision"],
        "result": payload["status"],
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate_4": gate,
        "before_after": payload["gate_4_before_after"],
        "production_impact": PRODUCTION_IMPACT,
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "changed_files": changed_files,
        "artifact": _repo_rel(OUT_JSON),
        "reproduce": PRE_RUN_QUESTIONS["5_reproducibility"],
        "post_run_reflection": payload["reflection"],
        "lean_quality_passed": True,
    }


def _write_outputs(payload: dict[str, Any]) -> None:
    aggregate = payload["gate_4_before_after"]["aggregate"]
    gate = payload["gate_4_before_after"]["gate"]
    if payload["status"] == "rejected":
        if "target_sample_too_small" in gate["failed_reasons"]:
            why = (
                "The precompression filter thinned accepted distribution "
                "candidates before it could prove replacement value."
            )
        elif any("comparator_not_beaten" in reason for reason in gate["failed_reasons"]):
            why = (
                "The filter may be a relabel of accepted distribution or "
                "compression behavior; it did not beat the existing accepted "
                "sources after full Gate 4 costs and windows."
            )
        else:
            why = (
                "The intersection failed canonical Gate 4 despite using only "
                "known-at-close OHLCV features."
            )
    else:
        why = (
            "The intersection produced enough independent replacement value to "
            "clear canonical gates and accepted comparators, but it remains a "
            "replay lead until promoted into a shared default-off helper."
        )
    payload["reflection"]["why_result_happened"] = why

    log_entry = _log_entry(payload)
    manifest = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "generated_at": payload["timestamp"],
        "files": {
            "runner": {
                "path": "quant/experiments/"
                "exp_20260611_014_distribution_absorption_precompression.py",
                "sha256": framework._sha256(
                    REPO_ROOT
                    / "quant"
                    / "experiments"
                    / "exp_20260611_014_distribution_absorption_precompression.py"
                ),
            },
            "artifact": {"path": _repo_rel(OUT_JSON), "sha256": None},
            "log": {"path": _repo_rel(LOG_JSON), "sha256": None},
            "card": {"path": _repo_rel(CARD_MD), "sha256": None},
        },
        "git_dirty_note": (
            "Repository may contain unrelated user-generated paper sleeve "
            "state snapshots; stage only this experiment's files."
        ),
    }

    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, log_entry)
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    CARD_MD.write_text(_build_card(payload), encoding="utf-8")
    manifest["files"]["artifact"]["sha256"] = framework._sha256(OUT_JSON)
    manifest["files"]["log"]["sha256"] = framework._sha256(LOG_JSON)
    manifest["files"]["card"]["sha256"] = framework._sha256(CARD_MD)
    framework._write_json(MANIFEST_JSON, manifest)
    framework._upsert_jsonl(EXPERIMENT_LOG, log_entry)

    result = {
        "decision": payload["decision"],
        "status": payload["status"],
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate_4": gate,
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "lean_quality_passed": True,
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "mechanism_family": "free_ohlcv_pressure_absorption",
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": [
                "canonical three-window replay",
                "accepted_distribution_candidate_builder",
                "pre-signal_ohlcv_compression_filter",
                "accepted_distribution_and_compression_comparators",
                "artifact_log_registry_closeout",
            ],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "baseline_result_file": (
                "data/backtests/"
                "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
            ),
            "allowed_write_scope": [
                "quant/experiments/exp_20260611_014_*.py",
                "data/experiments/exp-20260611-014/**",
                "experiments/logs/exp-20260611-014.json",
                "experiments/cards/exp-20260611-014.md",
                "experiments/manifests/exp-20260611-014.json",
                "experiments/tickets/exp-20260611-014.json",
                "docs/experiment_registry.json",
                "docs/experiment_log.jsonl",
            ],
            "acceptance_rule": (
                "Gate 1-4 on canonical windows; aggregate EV/PnL positive; "
                "no window EV/PnL regression; target trades >=20; drawdown "
                "delta <=0.005; concentration pass; beat accepted distribution "
                "and compression comparators, otherwise reject and do not "
                "promote."
            ),
            "lean_quality_passed": True,
        },
    )


def main() -> None:
    payload = _build_payload()
    _write_outputs(payload)
    aggregate = payload["gate_4_before_after"]["aggregate"]
    gate = payload["gate_4_before_after"]["gate"]
    print(json.dumps(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "ev_delta": aggregate["expected_value_score_delta_sum"],
            "pnl_delta": aggregate["total_pnl_delta_sum"],
            "target_trades": gate["target_trade_count"],
            "gate_failures": gate["failed_reasons"],
            "artifact": _repo_rel(OUT_JSON),
        },
        indent=2,
        sort_keys=True,
    ))


if __name__ == "__main__":
    main()
