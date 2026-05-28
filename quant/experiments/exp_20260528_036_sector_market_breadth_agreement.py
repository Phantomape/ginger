"""exp-20260528-036: sector/market breadth agreement scout.

This alpha search keeps the rejected sector-breadth confirmed breakout source
fixed and changes one routing variable: a paper candidate is admitted only when
the same signal date also passes the existing market volume-breadth context.

The replay is default-off paper only. It does not alter live orders, core
entries, ranking, sizing, exits, LLM/news, or universe membership.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, OrderedDict
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

import exp_20260525_011_opening_range_top1_fixed_notional_sleeve as base  # noqa: E402
import exp_20260526_015_sector_breadth_breakout_sleeve as sector  # noqa: E402
import exp_20260510_007_low_deployment_dynamic_etf_overlay as overlay_helper  # noqa: E402
from data_layer import get_universe  # noqa: E402


EXPERIMENT_ID = "exp-20260528-036"
STEM = "sector_market_breadth_agreement"
TRIAL_FAMILY = "sector_breadth_market_breadth_agreement_candidate_pool"
CHANGED_VARIABLE = "sector_breadth_market_breadth_agreement_routing_v1"
RULE_VERSION = "sector_breadth_market_breadth_agreement_routing_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

MAX_DRAWDOWN_WORSE = 0.005
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30


def _configure_modules() -> None:
    sector._configure_base_module()
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.ARTIFACT_MD = ARTIFACT_MD
    base.EXPERIMENT_LOG = EXPERIMENT_LOG
    base.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    base.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    base.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    base.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    base.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    base.MAX_PAPER_TRADES_PER_DAY = sector.MAX_PAPER_TRADES_PER_DAY
    base.shadow = sector.ohlcv_helper


def _candidate_passes_agreement(row: dict[str, Any]) -> bool:
    return bool(row.get("market_breadth_already_passed"))


def _annotate_trade(trade: dict[str, Any]) -> dict[str, Any]:
    annotated = dict(trade)
    annotated["sector_market_breadth_agreement"] = {
        "rule_version": RULE_VERSION,
        "field": "market_breadth_already_passed",
        "passed": True,
        "known_at": "after_signal_date_close_before_next_open_paper_entry",
        "trade_enabled": False,
        "alters_orders": False,
        "why_production_visible": (
            "The market volume-breadth context is computed from same-day OHLCV "
            "rows already used by the default-off volume-breadth paper surface."
        ),
    }
    annotated["strategy"] = "sector_market_breadth_agreement"
    return annotated


def _select_trades(
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
    *,
    require_market_breadth: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    used_date_counts: Counter[str] = Counter()
    for row in candidates:
        date = str(row.get("date") or "")
        if require_market_breadth and not _candidate_passes_agreement(row):
            filtered.append({**row, "filter_reason": "market_breadth_not_passed"})
            continue
        if row.get("same_ticker_ab_overlap"):
            filtered.append({**row, "filter_reason": "same_ticker_core_overlap"})
            continue
        if used_date_counts[date] >= sector.MAX_PAPER_TRADES_PER_DAY:
            filtered.append({**row, "filter_reason": "daily_top1_limit"})
            continue
        trade = base._paper_trade_from_candidate(snapshot, row)
        if trade is None:
            filtered.append({**row, "filter_reason": "missing_next_open_or_exit"})
            continue
        if require_market_breadth:
            trade = _annotate_trade(trade)
        selected.append(trade)
        used_date_counts[date] += 1
    return selected, filtered


def _target_trade_summary(
    target_trades_by_window: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    by_ticker_count: Counter[str] = Counter()
    by_ticker_pnl: Counter[str] = Counter()
    by_window_pnl: dict[str, float] = {}
    for label, trades in target_trades_by_window.items():
        by_window_pnl[label] = round(sum(float(trade.get("pnl") or 0.0) for trade in trades), 2)
        for trade in trades:
            ticker = str(trade.get("ticker") or "").upper()
            pnl = float(trade.get("pnl") or 0.0)
            by_ticker_count[ticker] += 1
            by_ticker_pnl[ticker] += pnl

    positive = {ticker: pnl for ticker, pnl in by_ticker_pnl.items() if pnl > 0}
    positive_total = sum(positive.values())
    max_positive_share = (
        round(max(positive.values()) / positive_total, 6)
        if positive_total > 0 and positive
        else None
    )
    positive_hhi = (
        round(sum((pnl / positive_total) ** 2 for pnl in positive.values()), 6)
        if positive_total > 0 and positive
        else None
    )
    return {
        "total_trade_count": sum(by_ticker_count.values()),
        "windows_with_target_trades": [
            label for label, trades in target_trades_by_window.items() if trades
        ],
        "total_pnl": round(sum(by_ticker_pnl.values()), 2),
        "by_window_pnl": by_window_pnl,
        "by_ticker_count": dict(sorted(by_ticker_count.items())),
        "by_ticker_pnl": {
            ticker: round(pnl, 2) for ticker, pnl in sorted(by_ticker_pnl.items())
        },
        "positive_by_ticker_pnl": {
            ticker: round(pnl, 2) for ticker, pnl in sorted(positive.items())
        },
        "max_single_positive_pnl_share": max_positive_share,
        "positive_pnl_hhi": positive_hhi,
    }


def _aggregate_by_window(rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ev_before = sum(row["before"]["expected_value_score"] for row in rows.values())
    ev_after = sum(row["after"]["expected_value_score"] for row in rows.values())
    pnl_before = sum(row["before"]["total_pnl"] for row in rows.values())
    pnl_after = sum(row["after"]["total_pnl"] for row in rows.values())
    return {
        "baseline_expected_value_score_sum": base._round(ev_before, 6),
        "after_expected_value_score_sum": base._round(ev_after, 6),
        "expected_value_score_delta_sum": base._round(ev_after - ev_before, 6),
        "expected_value_score_delta_pct": base._round((ev_after - ev_before) / ev_before, 6)
        if ev_before
        else None,
        "baseline_total_pnl_sum": base._round(pnl_before, 2),
        "after_total_pnl_sum": base._round(pnl_after, 2),
        "total_pnl_delta_sum": base._round(pnl_after - pnl_before, 2),
        "total_pnl_delta_pct": base._round((pnl_after - pnl_before) / pnl_before, 6)
        if pnl_before
        else None,
        "windows_ev_improved": sum(
            1 for row in rows.values() if row["delta"]["expected_value_score"] > 0
        ),
        "windows_ev_regressed": sum(
            1 for row in rows.values() if row["delta"]["expected_value_score"] < 0
        ),
        "windows_pnl_improved": sum(
            1 for row in rows.values() if row["delta"]["total_pnl"] > 0
        ),
        "windows_pnl_regressed": sum(
            1 for row in rows.values() if row["delta"]["total_pnl"] < 0
        ),
        "max_drawdown_delta_max": base._round(
            max(row["delta"]["max_drawdown_pct"] for row in rows.values()), 6
        ),
        "target_trade_count_sum": sum(row["target_trade_count"] for row in rows.values()),
    }


def _gate4(
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    min_survival: float,
) -> dict[str, Any]:
    target_windows = target_summary["windows_with_target_trades"]
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    passed = (
        aggregate["expected_value_score_delta_sum"] > 0
        and aggregate["total_pnl_delta_sum"] > 0
        and aggregate["windows_ev_improved"] == len(base.WINDOWS)
        and aggregate["windows_ev_regressed"] == 0
        and aggregate["windows_pnl_regressed"] == 0
        and target_summary["total_trade_count"] >= MIN_TARGET_TRADES
        and len(target_windows) >= MIN_TARGET_WINDOWS
        and aggregate["max_drawdown_delta_max"] <= MAX_DRAWDOWN_WORSE
        and min_survival >= 0.05
        and concentration_passed
    )
    failed: list[str] = []
    if aggregate["expected_value_score_delta_sum"] <= 0:
        failed.append("aggregate_ev_not_positive")
    if aggregate["total_pnl_delta_sum"] <= 0:
        failed.append("aggregate_pnl_not_positive")
    if aggregate["windows_ev_improved"] != len(base.WINDOWS) or aggregate["windows_ev_regressed"]:
        failed.append("window_ev_regression")
    if aggregate["windows_pnl_regressed"]:
        failed.append("window_pnl_regression")
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if aggregate["max_drawdown_delta_max"] > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if not concentration_passed:
        failed.append("target_concentration_failed")
    return {
        "passed": passed,
        "failed_reasons": failed,
        "aggregate_ev_delta_positive": aggregate["expected_value_score_delta_sum"] > 0,
        "aggregate_pnl_delta_positive": aggregate["total_pnl_delta_sum"] > 0,
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
        "target_trade_count": target_summary["total_trade_count"],
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_windows,
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "max_drawdown_worse": aggregate["max_drawdown_delta_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "survival_guard_passed": min_survival >= 0.05,
        "target_concentration": {
            "passed": concentration_passed,
            "max_single_positive_pnl_share": target_summary[
                "max_single_positive_pnl_share"
            ],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
        },
    }


def _build_policy_payload(
    *,
    before_result: dict[str, Any],
    before_metrics: dict[str, Any],
    snapshot: dict[str, list[dict[str, Any]]],
    candidates: list[dict[str, Any]],
    require_market_breadth: bool,
) -> dict[str, Any]:
    selected, filtered = _select_trades(
        snapshot,
        candidates,
        require_market_breadth=require_market_breadth,
    )
    overlay = base._overlay_from_paper_trades(before_result, selected)
    after = overlay_helper._metrics_with_overlay(before_result, overlay)
    delta = overlay_helper._delta(after, before_metrics)
    return {
        "after": after,
        "delta": delta,
        "target_trades": selected,
        "filtered_candidates": filtered[:200],
        "overlay_total_pnl": overlay["overlay_total_pnl"],
        "overlay_day_count": overlay["overlay_day_count"],
    }


def _build_payload() -> dict[str, Any]:
    gate2_open_positions = base._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(get_universe())
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    before_results: dict[str, dict[str, Any]] = {}
    snapshots: dict[str, dict[str, list[dict[str, Any]]]] = {}
    candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    raw_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    market_confirmed_candidate_counts: "OrderedDict[str, int]" = OrderedDict()
    candidate_day_counts: "OrderedDict[str, int]" = OrderedDict()

    sector.SECTOR_BREADTH_AUDIT = OrderedDict()
    for label, cfg in base.WINDOWS.items():
        print(f"[{label}] baseline core replay")
        before_result = sector.ohlcv_helper._run_baseline(universe, cfg)
        before = overlay_helper._metrics(before_result)
        snapshot = sector.ohlcv_helper._load_snapshot(cfg["snapshot"])
        candidates = sector._candidate_rows_for_window(snapshot, cfg, universe, before_result)
        before_results[label] = before_result
        before_metrics[label] = before
        snapshots[label] = snapshot
        candidates_by_window[label] = candidates
        raw_candidate_counts[label] = len(candidates)
        market_confirmed_candidate_counts[label] = sum(
            1 for row in candidates if _candidate_passes_agreement(row)
        )
        candidate_day_counts[label] = len({row["date"] for row in candidates})

    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    raw_window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    filtered_candidates_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    raw_target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()

    for label in base.WINDOWS:
        raw_row = _build_policy_payload(
            before_result=before_results[label],
            before_metrics=before_metrics[label],
            snapshot=snapshots[label],
            candidates=candidates_by_window[label],
            require_market_breadth=False,
        )
        row = _build_policy_payload(
            before_result=before_results[label],
            before_metrics=before_metrics[label],
            snapshot=snapshots[label],
            candidates=candidates_by_window[label],
            require_market_breadth=True,
        )
        after_metrics[label] = row["after"]
        target_trades_by_window[label] = row["target_trades"]
        filtered_candidates_by_window[label] = row["filtered_candidates"]
        raw_target_trades_by_window[label] = raw_row["target_trades"]
        window_rows[label] = {
            "before": before_metrics[label],
            "after": row["after"],
            "delta": row["delta"],
            "target_trade_count": len(row["target_trades"]),
            "raw_candidate_count": raw_candidate_counts[label],
            "market_confirmed_candidate_count": market_confirmed_candidate_counts[label],
            "raw_candidate_days": candidate_day_counts[label],
            "overlay_total_pnl": row["overlay_total_pnl"],
            "overlay_day_count": row["overlay_day_count"],
        }
        raw_window_rows[label] = {
            "before": before_metrics[label],
            "after": raw_row["after"],
            "delta": raw_row["delta"],
            "target_trade_count": len(raw_row["target_trades"]),
            "raw_candidate_count": raw_candidate_counts[label],
            "market_confirmed_candidate_count": market_confirmed_candidate_counts[label],
            "raw_candidate_days": candidate_day_counts[label],
            "overlay_total_pnl": raw_row["overlay_total_pnl"],
            "overlay_day_count": raw_row["overlay_day_count"],
        }

    aggregate = _aggregate_by_window(window_rows)
    target_summary = _target_trade_summary(target_trades_by_window)
    raw_aggregate = _aggregate_by_window(raw_window_rows)
    raw_target_summary = _target_trade_summary(raw_target_trades_by_window)
    gate4 = _gate4(aggregate, target_summary, min_survival)
    decision = (
        "accepted_candidate_sector_market_breadth_agreement"
        if gate4["passed"]
        else "rejected_sector_market_breadth_agreement"
    )
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    prediction = {
        "success_probability": 0.29,
        "expected_ev_delta": 0.18,
        "expected_pnl_delta": 5500.0,
        "main_failure_modes": [
            "late_strong_regression",
            "target_sample_concentration",
            "target_sample_too_small",
        ],
        "confidence_reason": (
            "Raw sector-breadth had positive aggregate PnL but failed one window; "
            "market-breadth agreement is production-visible and may remove "
            "isolated sector churn, but nearby failures make confidence low."
        ),
        "recorded_at": "2026-05-28T22:07:20+00:00",
    }
    actual_success = 1 if gate4["passed"] else 0
    brier = round((prediction["success_probability"] - actual_success) ** 2, 6)
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": decision,
        "decision": decision,
        "hypothesis": (
            "Sector-breadth breakout paper candidates should add more robust "
            "replacement value when the same signal date also passes the existing "
            "market volume-breadth context, indicating broad participation "
            "instead of isolated sector churn."
        ),
        "change_type": "default_off_paper_candidate_pool_routing",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "prior_trial_count": 2,
        "nearby_prior_experiments": ["exp-20260526-015", "exp-20260528-032"],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "production_visible_free_ohlcv_cross_source_breadth_agreement",
        "mechanism_family": "free_ohlcv_candidate_pool_source_quality",
        "trial_variant_id": "market_breadth_confirmed_top1_v1",
        "backtest_protocol": {
            "source": "docs/backtesting.md canonical three-window replay",
            "windows": base.WINDOWS,
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Sector-breadth signal uses only close-of-day OHLCV available on "
                "the signal date; paper entry is next available open with "
                "production entry slippage; exit is ten trading days after the "
                "signal. The agreement field reads the same-day market breadth "
                "context already present in candidate rows."
            ),
        },
        "parameters": {
            "base_universe_count": len(universe),
            "source_experiment_id": "exp-20260526-015",
            "candidate_source_locked": "sector_breadth_confirmed_breakout_top1_v1",
            "paper_notional_usd": base.BASE_NOTIONAL_USD,
            "hold_days": base.HOLD_DAYS,
            "max_paper_trades_per_day": sector.MAX_PAPER_TRADES_PER_DAY,
            "required_market_field": "market_breadth_already_passed == true",
            "acceptance": {
                "aggregate_ev_delta_gt": 0,
                "aggregate_pnl_delta_gt": 0,
                "ev_improved_windows": 3,
                "max_ev_regressed_windows": 0,
                "max_pnl_regressed_windows": 0,
                "min_target_trades": MIN_TARGET_TRADES,
                "min_target_windows": MIN_TARGET_WINDOWS,
                "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
                "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                "max_positive_hhi": MAX_POSITIVE_HHI,
            },
            "locked_variables": [
                "sector breadth candidate definition",
                "core universe membership",
                "core signal generation",
                "core ranking",
                "core position sizing",
                "core exits",
                "portfolio heat",
                "slot rules",
                "LLM/news replay",
                "watchlists",
                "live/default orders",
            ],
        },
        "gate_questions": {
            "1_alpha_hypothesis": (
                "candidate_pool / entry: sector-breadth breakouts should be "
                "higher quality when confirmed by broad market volume-breadth "
                "participation on the same signal date."
            ),
            "2_history_check": {
                "exp-20260526-015": (
                    "Sector-breadth confirmed breakout was positive in aggregate "
                    "but rejected because late_strong regressed and Gate 4 did "
                    "not allow a window regression."
                ),
                "exp-20260528-032": (
                    "Closed-ledger sector-breadth governor improved aggregate "
                    "EV/PnL but still failed because late_strong regressed."
                ),
                "difference_this_run": (
                    "This run is not a governor or scalar. It tests cross-source "
                    "breadth agreement using an already produced market context "
                    "field."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Same three docs/backtesting.md windows; positive aggregate EV/PnL; "
                "3/3 EV-improved windows; no PnL-regressed window; >=20 paper "
                "trades across all 3 windows; drawdown drift <=0.5pp; survival "
                ">=5%; concentration inside guardrails."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260528_036_sector_market_breadth_agreement.py"
            ),
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": f"{base._repo_rel(OUT_JSON)}#before_metrics",
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "canonical OHLCV Date/Open/High/Low/Close/Volume rows",
                "sector-breadth candidate same-day/trailing OHLCV fields",
                "market_breadth_already_passed",
                "market_volume_breadth_context.passed",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "passed": True,
            "note": (
                "All candidate fields are known after signal-date close before "
                "next-open paper entry. No future outcome controls a trade."
            ),
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_routing_changed": True,
            "minimum_core_survival_rate": base._round(min_survival, 4),
            "passed": min_survival >= 0.05,
            "note": (
                "No core filter or live entry rule was added. The default-off "
                "paper source is additive research, so core survival is unchanged "
                "from baseline replay."
            ),
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "raw_sector_breadth_control": {
            "delta_metrics": {
                "by_window": OrderedDict(
                    (label, row["delta"]) for label, row in raw_window_rows.items()
                ),
                "aggregate": raw_aggregate,
            },
            "target_trade_summary": raw_target_summary,
        },
        "delta_vs_raw_sector_breadth_control": {
            "expected_value_score_delta_sum": base._round(
                aggregate["after_expected_value_score_sum"]
                - raw_aggregate["after_expected_value_score_sum"],
                6,
            ),
            "total_pnl_delta_sum": base._round(
                aggregate["after_total_pnl_sum"] - raw_aggregate["after_total_pnl_sum"],
                2,
            ),
            "max_drawdown_delta_max": base._round(
                aggregate["max_drawdown_delta_max"] - raw_aggregate["max_drawdown_delta_max"],
                6,
            ),
        },
        "raw_candidate_counts": raw_candidate_counts,
        "market_confirmed_candidate_counts": market_confirmed_candidate_counts,
        "candidate_day_counts": candidate_day_counts,
        "target_trades_by_window": target_trades_by_window,
        "filtered_candidates_sample_by_window": filtered_candidates_by_window,
        "target_trade_summary": target_summary,
        "sector_breadth_audit": sector.SECTOR_BREADTH_AUDIT,
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "prediction": prediction,
        "calibration": {
            "actual_decision": decision,
            "actual_success": actual_success,
            "predicted_success_probability": prediction["success_probability"],
            "brier_score": brier,
            "expected_ev_delta": prediction["expected_ev_delta"],
            "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
            "ev_prediction_error": base._round(
                aggregate["expected_value_score_delta_sum"] - prediction["expected_ev_delta"],
                6,
            ),
            "expected_pnl_delta": prediction["expected_pnl_delta"],
            "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
            "pnl_prediction_error": base._round(
                aggregate["total_pnl_delta_sum"] - prediction["expected_pnl_delta"],
                2,
            ),
            "predicted_failure_modes": prediction["main_failure_modes"],
            "realized_failure_mode": ";".join(gate4["failed_reasons"]),
            "predicted_failure_mode_hit": any(
                failure in gate4["failed_reasons"]
                for failure in prediction["main_failure_modes"]
            ),
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "replay_only": True,
            "parity_test_added": False,
            "default_off_paper_only": True,
            "production_watchlist_changed": False,
            "production_orders_changed": False,
            "trade_enabled": False,
            "promotion_requirement": (
                "A retained result would still require a shared default-off paper "
                "adapter, daily report exposure, forward replacement-value ledger, "
                "and parity tests before any live/default behavior changes."
            ),
        },
        "why_not_other_changes": (
            "Skipped LLM soft-ranking and PEAD activation because replay-safe "
            "coverage remains limited. Skipped Companyfacts, VBB/VCP, "
            "state-surface, AI optical close-location, industry-leadership, and "
            "sector-breadth closed-ledger retunes per playbook and recent Gate 4 "
            "failures. This tests one different free-OHLCV cross-source breadth "
            "agreement field."
        ),
        "interpretation": (
            "The sector/market breadth agreement route cleared Gate 4 as a "
            "replay-only default-off lead, but no shared production policy was "
            "promoted."
            if gate4["passed"]
            else (
                "The sector/market breadth agreement route did not clear Gate 4. "
                "Do not promote it or retry nearby sector-breadth agreement "
                "gates on the same frozen windows without forward paper rows or "
                "a materially orthogonal source-quality field."
            )
        ),
        "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
        "next_evidence_needed": (
            "Forward paper rows with replacement value and concentration evidence "
            "or a materially orthogonal production-visible source-quality field."
        ),
        "related_files": [
            base._repo_rel(Path(__file__)),
            base._repo_rel(OUT_JSON),
            base._repo_rel(LOG_JSON),
            base._repo_rel(TICKET_JSON),
            base._repo_rel(ARTIFACT_MD),
            base._repo_rel(EXPERIMENT_LOG),
        ],
        "anti_js": "No JavaScript was used.",
    }


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw | Confirmed |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | "
            "${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {raw} | "
            "{confirmed} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                raw=payload["raw_candidate_counts"][label],
                confirmed=payload["market_confirmed_candidate_counts"][label],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    raw = payload["raw_sector_breadth_control"]["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Sector/Market Breadth Agreement",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            (
                "Single variable: route locked sector-breadth breakout paper "
                "candidates only when same-day market volume breadth also passed."
            ),
            "",
            "## Gate Questions",
            "",
            f"- alpha_hypothesis: {payload['gate_questions']['1_alpha_hypothesis']}",
            f"- history_check: exp-20260526-015 and exp-20260528-032 were nearby rejected sector-breadth runs; this changes cross-source confirmation only.",
            f"- single_causal_variable: `{CHANGED_VARIABLE}`",
            f"- acceptance: {payload['gate_questions']['4_acceptance_standard']}",
            f"- reproducibility: `{payload['gate_questions']['5_reproducibility']}`",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta vs core: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta vs core: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- raw sector-breadth EV/PnL delta vs core: `{raw['expected_value_score_delta_sum']}` / `${raw['total_pnl_delta_sum']}`",
            f"- EV delta vs raw sector-breadth control: `{payload['delta_vs_raw_sector_breadth_control']['expected_value_score_delta_sum']}`",
            f"- PnL delta vs raw sector-breadth control: `${payload['delta_vs_raw_sector_breadth_control']['total_pnl_delta_sum']}`",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}` across `{len(payload['target_trade_summary']['windows_with_target_trades'])}` windows",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            (
                "Replay-only and default-off paper only. No shared policy, run "
                "adapter, backtester adapter, production watchlist, order path, "
                "core entry, ranking, sizing, or exit behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if f'"experiment_id": "{EXPERIMENT_ID}"' in line:
                    return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(base._safe(payload), ensure_ascii=True, sort_keys=True))
        handle.write("\n")


def _persist(payload: dict[str, Any]) -> None:
    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, payload)
    base._write_json(
        TICKET_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "title": "Sector/market breadth agreement",
            "status": payload["status"],
            "lane": payload["lane"],
            "owner": "codex-alpha-search",
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "changed_variable": payload["changed_variable"],
            "decision": payload["decision"],
            "completed_at": payload["timestamp"],
            "result": {
                "decision": payload["decision"],
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "total_pnl_delta": payload["total_pnl_delta"],
                "gate4_passed": payload["gate4"]["passed"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            "artifact": base._repo_rel(ARTIFACT_MD),
            "json": base._repo_rel(OUT_JSON),
            "summary": payload["interpretation"],
        },
    )
    base._write_text(ARTIFACT_MD, _build_report(payload))
    _append_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    _configure_modules()
    payload = _build_payload()
    _persist(payload)
    print(
        json.dumps(
            base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "delta_vs_raw_sector_breadth_control": payload[
                        "delta_vs_raw_sector_breadth_control"
                    ],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
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
