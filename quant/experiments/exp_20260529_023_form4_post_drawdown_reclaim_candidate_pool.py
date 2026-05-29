"""exp-20260529-023: Form 4 post-drawdown reclaim candidate pool.

This alpha search tests one free-data candidate source: PIT-safe SEC Form 4
open-market purchase events where price is repairing from a controlled drawdown.
The sleeve is default-off paper only, admits at most one candidate per signal
day, enters at the next available open, and exits after ten trading days.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260528_037_ticker_accumulation_quality_breakout as framework
from form4_event_queue import (
    BASE_MEANINGFUL_PURCHASE_VALUE,
    aggregate_purchase_events,
    load_form4_transaction_rows,
    qualifies_meaningful_purchase,
)


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260529-023"
STEM = "form4_post_drawdown_reclaim_candidate_pool"
TRIAL_FAMILY = "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
CHANGED_VARIABLE = "form4_post_drawdown_reclaim_candidate_source_v1"
RULE_VERSION = "form4_open_market_purchase_post_drawdown_reclaim_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

FORM4_TRANSACTIONS_PATH = (
    REPO_ROOT / "data" / "non_ohlcv" / "form4_transactions_20241002_20260502.jsonl"
)

DRAWNDOWN_LOOKBACK_DAYS = 60
MOVING_AVERAGE_DAYS = 20
RELATIVE_STRENGTH_DAYS = 5
AVG_DOLLAR_VOLUME_DAYS = 20
MIN_CLOSE = 5.0
MIN_AVG_DOLLAR_VOLUME_20D = 5_000_000.0
MIN_TOTAL_PURCHASE_VALUE = BASE_MEANINGFUL_PURCHASE_VALUE
MIN_DRAWDOWN_FROM_60D_HIGH = -0.35
MAX_DRAWDOWN_FROM_60D_HIGH = -0.08
MIN_RECLAIM_ABOVE_MA20 = 0.0
MIN_RS5_VS_SPY = 0.0
MIN_SIGNAL_CLOSE_LOCATION = 0.55
MAX_PAPER_TRADES_PER_DAY = 1
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30

_FORM4_EVENTS_CACHE: list[dict[str, Any]] | None = None
_FORM4_ROW_COUNT = 0
_FORM4_PIT_ROW_COUNT = 0


def _patch_framework() -> None:
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.BEFORE_AGG_JSON = BEFORE_AGG_JSON
    framework.AFTER_AGG_JSON = AFTER_AGG_JSON
    framework.LOG_JSON = LOG_JSON
    framework.TICKET_JSON = TICKET_JSON
    framework.DOC_TICKET_JSON = DOC_TICKET_JSON
    framework.ARTIFACT_MD = ARTIFACT_MD
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._gate4 = _gate4
    framework._build_report = _build_report


def _load_form4_purchase_events() -> list[dict[str, Any]]:
    global _FORM4_EVENTS_CACHE, _FORM4_ROW_COUNT, _FORM4_PIT_ROW_COUNT
    if _FORM4_EVENTS_CACHE is not None:
        return _FORM4_EVENTS_CACHE

    if FORM4_TRANSACTIONS_PATH.exists():
        rows = load_form4_transaction_rows(FORM4_TRANSACTIONS_PATH)
    else:
        rows = []
        for path in sorted((REPO_ROOT / "data" / "non_ohlcv").glob("form4_transactions_*.jsonl")):
            rows.extend(load_form4_transaction_rows(path))

    _FORM4_ROW_COUNT = len(rows)
    pit_rows = [row for row in rows if row.get("pit_safe_flag") is True]
    _FORM4_PIT_ROW_COUNT = len(pit_rows)

    events = [
        event
        for event in aggregate_purchase_events(
            pit_rows,
            start="2024-10-02",
            end="2026-04-21",
        )
        if qualifies_meaningful_purchase(
            event,
            min_total_purchase_value=MIN_TOTAL_PURCHASE_VALUE,
        )
    ]
    _FORM4_EVENTS_CACHE = sorted(
        events,
        key=lambda row: (
            str(row.get("usable_trade_date") or ""),
            str(row.get("ticker") or ""),
        ),
    )
    return _FORM4_EVENTS_CACHE


def _avg_dollar_volume(rows: list[dict[str, Any]], idx: int, days: int) -> float | None:
    if idx < days:
        return None
    values: list[float] = []
    for row in rows[idx - days:idx]:
        close = framework.ohlcv_helper._value(row, "Close")
        volume = framework.ohlcv_helper._value(row, "Volume")
        if close is None or volume is None:
            return None
        values.append(float(close) * float(volume))
    return sum(values) / len(values) if values else None


def _close_location(row: dict[str, Any]) -> float | None:
    high = framework.ohlcv_helper._value(row, "High")
    low = framework.ohlcv_helper._value(row, "Low")
    close = framework.ohlcv_helper._value(row, "Close")
    if high is None or low is None or close is None or high <= low:
        return None
    return (float(close) - float(low)) / (float(high) - float(low))


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = framework.ohlcv_helper._baseline_entries(before_result)
    dates = {
        date
        for date in framework.ohlcv_helper._trading_dates(snapshot)
        if str(cfg["start"]) <= date <= str(cfg["end"])
    }
    spy_rows = framework.ohlcv_helper._series(snapshot, "SPY")
    spy_index = framework.ohlcv_helper._row_index(spy_rows)
    events = [
        event
        for event in _load_form4_purchase_events()
        if str(event.get("usable_trade_date") or "")[:10] in dates
    ]
    candidates: list[dict[str, Any]] = []
    audit: Counter[str] = Counter()
    seen_ticker_dates: set[tuple[str, str]] = set()

    for event in events:
        ticker = str(event.get("ticker") or "").upper()
        date = str(event.get("usable_trade_date") or "")[:10]
        if not ticker or not date:
            audit["missing_ticker_or_date"] += 1
            continue
        if ticker in framework.EXCLUDED_TICKERS:
            audit["excluded_ticker"] += 1
            continue
        rows = framework.ohlcv_helper._series(snapshot, ticker)
        idx = framework.ohlcv_helper._row_index(rows).get(date)
        spy_idx = spy_index.get(date)
        min_idx = max(
            DRAWNDOWN_LOOKBACK_DAYS,
            MOVING_AVERAGE_DAYS,
            RELATIVE_STRENGTH_DAYS,
            AVG_DOLLAR_VOLUME_DAYS,
        )
        if idx is None or spy_idx is None or idx < min_idx or spy_idx < RELATIVE_STRENGTH_DAYS:
            audit["missing_ohlcv_or_history"] += 1
            continue

        close = framework.ohlcv_helper._value(rows[idx], "Close")
        volume = framework.ohlcv_helper._value(rows[idx], "Volume")
        if close is None or volume is None or float(close) < MIN_CLOSE:
            audit["missing_or_low_price_volume"] += 1
            continue

        avg_dollar_volume = _avg_dollar_volume(rows, idx, AVG_DOLLAR_VOLUME_DAYS)
        if avg_dollar_volume is None or avg_dollar_volume < MIN_AVG_DOLLAR_VOLUME_20D:
            audit["low_avg_dollar_volume"] += 1
            continue

        prior_high_60d = framework._prior_high(rows, idx, DRAWNDOWN_LOOKBACK_DAYS, "High")
        ma20 = framework._prior_average(rows, idx, MOVING_AVERAGE_DAYS, "Close")
        if not prior_high_60d or not ma20:
            audit["missing_price_context"] += 1
            continue

        drawdown_from_60d_high = (float(close) / float(prior_high_60d)) - 1.0
        if drawdown_from_60d_high > MAX_DRAWDOWN_FROM_60D_HIGH:
            audit["not_enough_prior_drawdown"] += 1
            continue
        if drawdown_from_60d_high < MIN_DRAWDOWN_FROM_60D_HIGH:
            audit["drawdown_too_deep"] += 1
            continue

        reclaim_above_ma20 = (float(close) / float(ma20)) - 1.0
        if reclaim_above_ma20 < MIN_RECLAIM_ABOVE_MA20:
            audit["not_reclaimed_ma20"] += 1
            continue

        ret5 = framework._close_return(rows, idx - RELATIVE_STRENGTH_DAYS, idx)
        spy_ret5 = framework._close_return(
            spy_rows,
            spy_idx - RELATIVE_STRENGTH_DAYS,
            spy_idx,
        )
        if ret5 is None or spy_ret5 is None:
            audit["missing_rs5"] += 1
            continue
        rs5_vs_spy = ret5 - spy_ret5
        if rs5_vs_spy < MIN_RS5_VS_SPY:
            audit["weak_rs5_vs_spy"] += 1
            continue

        signal_close_location = _close_location(rows[idx])
        if (
            signal_close_location is None
            or signal_close_location < MIN_SIGNAL_CLOSE_LOCATION
        ):
            audit["weak_close_location"] += 1
            continue

        key = (ticker, date)
        if key in seen_ticker_dates:
            audit["duplicate_ticker_date_form4"] += 1
            continue
        seen_ticker_dates.add(key)

        total_purchase_value = float(event.get("total_purchase_value") or 0.0)
        owner_count = int(event.get("owner_count") or 0)
        ab_entries = entries_by_date.get(date, [])
        score = (
            min(math.log10(max(total_purchase_value, 1.0)) / 10.0, 0.80)
            + min(max(owner_count, 0) * 0.04, 0.16)
            + min(abs(drawdown_from_60d_high), 0.35) * 0.40
            + max(reclaim_above_ma20, 0.0)
            + rs5_vs_spy
            + (signal_close_location * 0.10)
        )
        candidates.append(
            {
                "date": date,
                "ticker": ticker,
                "strategy": STEM,
                "rule_version": RULE_VERSION,
                "form4_accessions": event.get("accessions") or [],
                "form4_sample_archive_urls": event.get("sample_archive_urls") or [],
                "form4_sample_owner_names": event.get("sample_owner_names") or [],
                "form4_sample_officer_titles": event.get("sample_officer_titles") or [],
                "form4_total_purchase_value": framework.base._round(
                    total_purchase_value,
                    2,
                ),
                "form4_max_purchase_value": framework.base._round(
                    float(event.get("max_purchase_value") or 0.0),
                    2,
                ),
                "form4_purchase_transaction_count": event.get(
                    "purchase_transaction_count"
                ),
                "form4_filing_count": event.get("filing_count"),
                "form4_owner_count": owner_count,
                "form4_any_officer": bool(event.get("any_officer")),
                "form4_any_director": bool(event.get("any_director")),
                "form4_any_10pct_owner": bool(event.get("any_10pct_owner")),
                "form4_meaningful_purchase_v1": bool(
                    event.get("meaningful_purchase_v1")
                ),
                "close": framework.base._round(close, 4),
                "volume": framework.base._round(volume, 2),
                "ma20": framework.base._round(ma20, 4),
                "prior_high_60d": framework.base._round(prior_high_60d, 4),
                "drawdown_from_60d_high": framework.base._round(
                    drawdown_from_60d_high,
                    6,
                ),
                "reclaim_above_ma20": framework.base._round(reclaim_above_ma20, 6),
                "avg_dollar_volume_20d": framework.base._round(
                    avg_dollar_volume,
                    2,
                ),
                "ret5": framework.base._round(ret5, 6),
                "spy_ret5": framework.base._round(spy_ret5, 6),
                "rs5_vs_spy": framework.base._round(rs5_vs_spy, 6),
                "signal_close_location": framework.base._round(
                    signal_close_location,
                    6,
                ),
                "form4_reclaim_candidate_score": framework.base._round(score, 6),
                "same_day_ab_entry_count": len(ab_entries),
                "same_day_ab_overlap": bool(ab_entries),
                "same_ticker_ab_overlap": any(
                    trade.get("ticker") == ticker for trade in ab_entries
                ),
                "known_at": (
                    "after_form4_usable_trade_date_close_before_next_open_paper_entry"
                ),
                "trade_enabled": False,
                "alters_orders": False,
            }
        )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["form4_reclaim_candidate_score"]),
            -float(row["form4_total_purchase_value"]),
            -float(row["rs5_vs_spy"]),
            -float(row["reclaim_above_ma20"]),
            row["ticker"],
        )
    )
    return candidates, {
        "dates_checked": len(dates),
        "form4_meaningful_purchase_events_in_window": len(events),
        "candidate_count": len(candidates),
        "candidate_days": len({row["date"] for row in candidates}),
        "unique_candidate_tickers": len({row["ticker"] for row in candidates}),
        "candidate_universe_argument_count": len(universe),
        "audit_reject_counts": dict(sorted(audit.items())),
        "rule_version": RULE_VERSION,
        "form4_events_source": framework.base._repo_rel(FORM4_TRANSACTIONS_PATH),
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
    if aggregate["windows_ev_regressed"]:
        failed.append("window_ev_regression")
    if aggregate["windows_pnl_regressed"]:
        failed.append("window_pnl_regression")
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if aggregate["max_drawdown_delta_max"] > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_guardrail_failed")
    if min_survival < 0.05:
        failed.append("survival_guardrail_failed")
    if not concentration_passed:
        failed.append("target_concentration_failed")
    return {
        "passed": passed,
        "failed_reasons": failed,
        "aggregate_ev_delta_positive": aggregate["expected_value_score_delta_sum"] > 0,
        "aggregate_pnl_delta_positive": aggregate["total_pnl_delta_sum"] > 0,
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "windows_pnl_improved": aggregate["windows_pnl_improved"],
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


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    decision = (
        "accepted_candidate_form4_post_drawdown_reclaim"
        if gate4["passed"]
        else "rejected_form4_post_drawdown_reclaim"
    )
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]
    actual_success = 1 if gate4["passed"] else 0
    prediction = {
        "success_probability": 0.22,
        "expected_ev_delta": 0.15,
        "expected_pnl_delta": 3000.0,
        "main_failure_modes": [
            "thin sample",
            "post_drawdown_reclaim_is_price_pattern_not_alpha",
            "late_window_only",
            "concentration",
        ],
        "confidence_reason": (
            "Free PIT Form4 data is production-visible and orthogonal to frozen "
            "SEC text, LLM, Companyfacts, and state-surface scalar retunes, but "
            "prior Form4 role/cluster tests were thin or not material."
        ),
        "recorded_at": "2026-05-29T20:11:46+00:00",
        "brier_score": round((0.22 - actual_success) ** 2, 6),
    }

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_discovery",
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "PIT-safe Form 4 meaningful open-market purchases followed by "
                "controlled drawdown repair and same-week price reclaim may expand "
                "the candidate pool with insider-validated reversal candidates."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": "insider_validated_reversal",
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 3,
            "nearby_prior_experiments": [
                "exp-20260512-017",
                "exp-20260512-901",
                "exp-20260529-002",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "new_production_visible_free_form4_price_context_field",
            "prediction": prediction,
            "parameters": {
                "base_universe_count": payload["parameters"]["base_universe_count"],
                "stock_excluded_tickers": sorted(framework.EXCLUDED_TICKERS),
                "paper_notional_usd": framework.base.BASE_NOTIONAL_USD,
                "hold_days": framework.base.HOLD_DAYS,
                "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
                "form4_transactions_path": framework.base._repo_rel(
                    FORM4_TRANSACTIONS_PATH
                ),
                "min_total_purchase_value": MIN_TOTAL_PURCHASE_VALUE,
                "drawdown_lookback_days": DRAWNDOWN_LOOKBACK_DAYS,
                "moving_average_days": MOVING_AVERAGE_DAYS,
                "relative_strength_days": RELATIVE_STRENGTH_DAYS,
                "avg_dollar_volume_days": AVG_DOLLAR_VOLUME_DAYS,
                "min_close": MIN_CLOSE,
                "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
                "min_drawdown_from_60d_high": MIN_DRAWDOWN_FROM_60D_HIGH,
                "max_drawdown_from_60d_high": MAX_DRAWDOWN_FROM_60D_HIGH,
                "min_reclaim_above_ma20": MIN_RECLAIM_ABOVE_MA20,
                "min_rs5_vs_spy": MIN_RS5_VS_SPY,
                "min_signal_close_location": MIN_SIGNAL_CLOSE_LOCATION,
                "source_definition": [
                    "Form 4 transaction rows must have pit_safe_flag true",
                    "aggregated event must qualify as meaningful_purchase_v1",
                    "total open-market purchase value must be at least USD 50k",
                    "ticker must have exact signal-date OHLCV in the fixed snapshot",
                    "close must be 8% to 35% below the prior 60-day high",
                    "close must reclaim the prior 20-day moving average",
                    "5-day return must beat SPY by at least 0 percentage points",
                    "20-day average dollar volume must be at least USD 5 million",
                    "signal-day close location must be at least 0.55",
                    "top-1 selected paper entry per signal date",
                ],
                "selection_rank": [
                    "signal_date",
                    "form4_reclaim_candidate_score desc",
                    "form4_total_purchase_value desc",
                    "rs5_vs_spy desc",
                    "reclaim_above_ma20 desc",
                    "ticker asc",
                ],
                "locked_variables": [
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
                "acceptance": {
                    "aggregate_ev_delta_gt": 0,
                    "aggregate_pnl_delta_gt": 0,
                    "max_ev_regressed_windows": 0,
                    "max_pnl_regressed_windows": 0,
                    "min_target_trades": MIN_TARGET_TRADES,
                    "min_target_windows": MIN_TARGET_WINDOWS,
                    "max_drawdown_worse": MAX_DRAWDOWN_WORSE,
                    "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
                    "max_positive_hhi": MAX_POSITIVE_HHI,
                },
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "candidate_pool / entry: meaningful insider buying after an "
                    "orderly drawdown, once price repairs above the 20-day average "
                    "and beats SPY over 5 days, may identify higher-quality reversal "
                    "entries without adding random tickers."
                ),
                "2_history_check": {
                    "exp-20260512-017": (
                        "Clustered PIT-safe Form4 meaningful purchases with prior "
                        "RS were positive but not material. This run changes the "
                        "causal discriminator to post-drawdown reclaim."
                    ),
                    "exp-20260512-901": (
                        "Single-owner Form4 was positive but not material. This run "
                        "does not use single-owner status as the selector."
                    ),
                    "exp-20260529-002": (
                        "Executive-role Form4 did not beat raw Form4 materiality and "
                        "concentration gates. This run avoids role quality and tests "
                        "price-context repair around meaningful purchases."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same three docs/backtesting.md windows; positive aggregate EV/PnL; "
                    "no EV- or PnL-regressed window; >=20 paper trades across all "
                    "3 windows; drawdown drift <=0.5pp; survival >=5%; concentration "
                    "inside guardrails."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260529_023_form4_post_drawdown_reclaim_candidate_pool.py"
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay attribution remains sparse. "
                "Skipped Companyfacts, VBB, VCP, state-surface, low-dilution, and "
                "SEC text threshold retunes per playbook freeze guidance. Options "
                "data is forward-only for these canonical windows. This run tests "
                "one free SEC Form4 plus OHLCV price-context source variable only."
            ),
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
                    "A retained result would still require a shared default-off Form4 "
                    "paper adapter and parity tests before any daily report or "
                    "live/default behavior changes."
                ),
            },
            "production_parity": {
                "alters_production_orders": False,
                "alters_live_watchlists": False,
                "alters_core_backtester": False,
                "default_enabled": False,
                "replay_only": True,
                "parity_note": (
                    "No production code path is changed. If this were accepted, "
                    "promotion would require shared Form4 event aggregation, as-of "
                    "OHLCV price-context parity, and next-open/10-day exit tests."
                ),
            },
            "interpretation": (
                "The Form4 post-drawdown reclaim candidate pool cleared Gate 4 as "
                "a default-off replay lead, but no production/shared policy was promoted."
                if gate4["passed"]
                else (
                    "The Form4 post-drawdown reclaim candidate pool did not clear "
                    "Gate 4. Do not promote it or retry nearby Form4 price-context "
                    "thresholds on the same frozen windows without new forward rows "
                    "or a materially sharper Form4 context field."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "next_evidence_needed": (
                "Forward replacement-value rows or a materially different Form4 "
                "context field such as first-buy-after-long-inactivity, insider "
                "ownership change, or multi-filer accumulation provenance."
            ),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Form4 events use PIT-safe accepted_at/usable_trade_date aggregation. "
        "OHLCV filters are observed through the signal-date close; paper entry "
        "is the next available open with production entry slippage; exit is ten "
        "trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    payload["gate2"]["runtime_field_coverage"] = {
        "form4_purchase_events": {
            "source": framework.base._repo_rel(FORM4_TRANSACTIONS_PATH),
            "required_transaction_fields": [
                "ticker",
                "usable_trade_date",
                "pit_safe_flag",
                "open_market_purchase_flag",
                "transaction_value",
                "10b5_1_flag",
                "option_exercise_flag",
                "owner_name",
                "issuer_name",
                "is_officer",
                "is_director",
                "is_10pct_owner",
            ],
            "transaction_rows_loaded": _FORM4_ROW_COUNT,
            "pit_safe_transaction_rows": _FORM4_PIT_ROW_COUNT,
            "meaningful_purchase_events_loaded": len(_load_form4_purchase_events()),
        }
    }
    payload["gate2"]["target_trade_field_coverage"] = framework._field_coverage(
        all_target_trades,
        [
            "ticker",
            "signal_date",
            "entry_date",
            "exit_date",
            "entry_price",
            "exit_price",
            "pnl",
            "known_at",
            "form4_total_purchase_value",
            "form4_owner_count",
            "drawdown_from_60d_high",
            "reclaim_above_ma20",
            "rs5_vs_spy",
            "avg_dollar_volume_20d",
        ],
    )
    payload["related_files"] = [
        framework.base._repo_rel(Path(__file__)),
        framework.base._repo_rel(OUT_JSON),
        framework.base._repo_rel(BEFORE_AGG_JSON),
        framework.base._repo_rel(AFTER_AGG_JSON),
        framework.base._repo_rel(LOG_JSON),
        framework.base._repo_rel(TICKET_JSON),
        framework.base._repo_rel(DOC_TICKET_JSON),
        framework.base._repo_rel(CARD_MD),
        framework.base._repo_rel(ARTIFACT_MD),
        framework.base._repo_rel(EXPERIMENT_LOG),
        framework.base._repo_rel(FORM4_TRANSACTIONS_PATH),
    ]
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Raw candidates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {raw} |".format(
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
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    return "\n".join(
        [
            "# exp-20260529-023 Form4 Post-Drawdown Reclaim Candidate Pool",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: a default-off paper candidate source admits PIT-safe Form 4 meaningful open-market purchases only when price is 8% to 35% below its prior 60-day high, has reclaimed the prior 20-day moving average, and has beaten SPY over five days. Selection is top-1 per day, next-open entry, ten-trading-day exit.",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}` across `{len(payload['target_trade_summary']['windows_with_target_trades'])}` windows",
            f"- max single positive share: `{payload['target_trade_summary']['max_single_positive_pnl_share']}`",
            f"- positive PnL HHI: `{payload['target_trade_summary']['positive_pnl_hhi']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(gate4, indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Replay-only and default-off paper only. No shared policy, run adapter, backtester adapter, production watchlist, order path, core entry, ranking, sizing, or exit behavior changed.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _persist(payload: dict[str, Any]) -> None:
    framework.base._write_json(OUT_JSON, payload)
    framework.base._write_json(BEFORE_AGG_JSON, payload["judge_before_aggregate"])
    framework.base._write_json(AFTER_AGG_JSON, payload["judge_after_aggregate"])
    framework.base._write_json(LOG_JSON, payload)
    ticket_payload = {
        "experiment_id": EXPERIMENT_ID,
        "title": "Form4 post-drawdown reclaim candidate pool",
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": framework.base._repo_rel(ARTIFACT_MD),
        "json": framework.base._repo_rel(OUT_JSON),
        "before_aggregate": framework.base._repo_rel(BEFORE_AGG_JSON),
        "after_aggregate": framework.base._repo_rel(AFTER_AGG_JSON),
        "summary": payload["interpretation"],
    }
    framework.base._write_json(TICKET_JSON, ticket_payload)
    framework.base._write_json(DOC_TICKET_JSON, ticket_payload)
    framework.base._write_text(ARTIFACT_MD, _build_report(payload))
    framework.base._write_text(CARD_MD, _build_report(payload))
    framework.base._upsert_jsonl(EXPERIMENT_LOG, payload)


def main() -> int:
    _patch_framework()
    payload = _postprocess_payload(framework._build_payload())
    _persist(payload)
    print(
        json.dumps(
            framework.base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "gate4": payload["gate4"],
                    "target_trade_summary": payload["target_trade_summary"],
                    "artifact": framework.base._repo_rel(ARTIFACT_MD),
                    "before_aggregate": framework.base._repo_rel(BEFORE_AGG_JSON),
                    "after_aggregate": framework.base._repo_rel(AFTER_AGG_JSON),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    if not math.isfinite(1.0):
        raise SystemExit("unexpected math failure")
    raise SystemExit(main())
