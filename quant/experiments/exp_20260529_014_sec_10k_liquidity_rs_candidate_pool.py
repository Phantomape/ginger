"""exp-20260529-014: SEC 10-K liquidity + RS candidate pool.

This alpha search tests one free-data candidate source: PIT-safe SEC 10-K
filings whose ticker is liquid, above trend, and showing relative strength.
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


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260529-014"
STEM = "sec_10k_liquidity_rs_candidate_pool"
TRIAL_FAMILY = "sec_10k_liquidity_rs_candidate_pool"
CHANGED_VARIABLE = "sec_10k_liquidity_rs_candidate_source_v1"
RULE_VERSION = "sec_10k_liquidity_rs_candidate_source_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260529_014_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"

SEC_EVENTS_FILE = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "sec_filing_events_20241002_20260421.jsonl"
)

MOVING_AVERAGE_DAYS = 50
RELATIVE_STRENGTH_DAYS = 20
AVG_DOLLAR_VOLUME_DAYS = 20
MIN_CLOSE = 5.0
MIN_AVG_DOLLAR_VOLUME_20D = 20_000_000.0
MIN_RS20_VS_SPY = 0.03
MIN_SIGNAL_EXCESS_RETURN_1D_VS_SPY = -0.01
MIN_SIGNAL_CLOSE_LOCATION = 0.45
MAX_PAPER_TRADES_PER_DAY = 1
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 2
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30

_SEC_10K_EVENTS_CACHE: list[dict[str, Any]] | None = None


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
    framework.DOC_TICKET_JSON = TICKET_JSON
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


def _is_10k(row: dict[str, Any]) -> bool:
    form = str(row.get("form_base") or row.get("form_type") or "").upper()
    return form == "10-K" or form.startswith("10-K/")


def _load_sec_10k_events() -> list[dict[str, Any]]:
    global _SEC_10K_EVENTS_CACHE
    if _SEC_10K_EVENTS_CACHE is not None:
        return _SEC_10K_EVENTS_CACHE

    paths = [SEC_EVENTS_FILE] if SEC_EVENTS_FILE.exists() else []
    if not paths:
        paths = sorted((REPO_ROOT / "data" / "non_ohlcv").glob("sec_filing_events_*.jsonl"))

    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ticker = str(row.get("ticker") or "").upper().strip()
                usable_trade_date = str(row.get("usable_trade_date") or "").strip()[:10]
                accession = str(row.get("accession_number") or "").strip()
                if not ticker or not usable_trade_date or not accession:
                    continue
                if not _is_10k(row):
                    continue
                if row.get("pit_safe_flag") is not True:
                    continue
                if bool(row.get("is_amendment")):
                    continue
                deduped[(ticker, accession, usable_trade_date)] = {
                    "ticker": ticker,
                    "usable_trade_date": usable_trade_date,
                    "accession_number": accession,
                    "accepted_at": row.get("accepted_at"),
                    "filing_date": str(row.get("filing_date") or "")[:10] or None,
                    "form_type": row.get("form_type"),
                    "form_base": row.get("form_base"),
                    "archive_url": row.get("archive_url"),
                    "pit_source": row.get("pit_source"),
                    "source_file": path.name,
                }

    _SEC_10K_EVENTS_CACHE = sorted(
        deduped.values(),
        key=lambda row: (
            str(row["usable_trade_date"]),
            str(row["ticker"]),
            str(row["accession_number"]),
        ),
    )
    return _SEC_10K_EVENTS_CACHE


def _avg_dollar_volume(
    rows: list[dict[str, Any]],
    idx: int,
    days: int,
) -> float | None:
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


def _daily_return(rows: list[dict[str, Any]], idx: int) -> float | None:
    if idx < 1:
        return None
    prior_close = framework.ohlcv_helper._value(rows[idx - 1], "Close")
    close = framework.ohlcv_helper._value(rows[idx], "Close")
    if not prior_close or close is None:
        return None
    return (float(close) / float(prior_close)) - 1.0


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
        event for event in _load_sec_10k_events() if event["usable_trade_date"] in dates
    ]
    candidates: list[dict[str, Any]] = []
    audit: Counter[str] = Counter()
    seen_ticker_dates: set[tuple[str, str]] = set()

    for event in events:
        ticker = str(event["ticker"]).upper()
        date = str(event["usable_trade_date"])
        if ticker in framework.EXCLUDED_TICKERS:
            audit["excluded_ticker"] += 1
            continue
        rows = framework.ohlcv_helper._series(snapshot, ticker)
        idx = framework.ohlcv_helper._row_index(rows).get(date)
        spy_idx = spy_index.get(date)
        if (
            idx is None
            or spy_idx is None
            or idx < max(MOVING_AVERAGE_DAYS, RELATIVE_STRENGTH_DAYS)
            or spy_idx < RELATIVE_STRENGTH_DAYS
        ):
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

        ma50 = framework._prior_average(rows, idx, MOVING_AVERAGE_DAYS, "Close")
        if ma50 is None or float(close) <= float(ma50):
            audit["below_50d_trend"] += 1
            continue

        ret20 = framework._close_return(rows, idx - RELATIVE_STRENGTH_DAYS, idx)
        spy_ret20 = framework._close_return(
            spy_rows,
            spy_idx - RELATIVE_STRENGTH_DAYS,
            spy_idx,
        )
        if ret20 is None or spy_ret20 is None:
            audit["missing_rs20"] += 1
            continue
        rs20_vs_spy = ret20 - spy_ret20
        if rs20_vs_spy < MIN_RS20_VS_SPY:
            audit["weak_rs20_vs_spy"] += 1
            continue

        signal_return_1d = _daily_return(rows, idx)
        spy_return_1d = _daily_return(spy_rows, spy_idx)
        if signal_return_1d is None or spy_return_1d is None:
            audit["missing_signal_return"] += 1
            continue
        signal_excess_return = signal_return_1d - spy_return_1d
        if signal_excess_return < MIN_SIGNAL_EXCESS_RETURN_1D_VS_SPY:
            audit["weak_signal_day_excess_return"] += 1
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
            audit["duplicate_ticker_date_10k"] += 1
            continue
        seen_ticker_dates.add(key)

        ab_entries = entries_by_date.get(date, [])
        score = (
            rs20_vs_spy
            + signal_excess_return
            + (signal_close_location * 0.10)
            + min(math.log10(max(avg_dollar_volume, 1.0)) / 100.0, 0.10)
        )
        candidates.append(
            {
                "date": date,
                "ticker": ticker,
                "strategy": "sec_10k_liquidity_rs_candidate_pool",
                "rule_version": RULE_VERSION,
                "sec_accession_number": event.get("accession_number"),
                "sec_accepted_at": event.get("accepted_at"),
                "sec_filing_date": event.get("filing_date"),
                "sec_form_type": event.get("form_type"),
                "sec_archive_url": event.get("archive_url"),
                "sec_pit_source": event.get("pit_source"),
                "sec_source_file": event.get("source_file"),
                "close": framework.base._round(close, 4),
                "volume": framework.base._round(volume, 2),
                "ma50": framework.base._round(ma50, 4),
                "avg_dollar_volume_20d": framework.base._round(avg_dollar_volume, 2),
                "ret20": framework.base._round(ret20, 6),
                "spy_ret20": framework.base._round(spy_ret20, 6),
                "rs20_vs_spy": framework.base._round(rs20_vs_spy, 6),
                "signal_return_1d": framework.base._round(signal_return_1d, 6),
                "spy_return_1d": framework.base._round(spy_return_1d, 6),
                "signal_excess_return_1d_vs_spy": framework.base._round(
                    signal_excess_return, 6
                ),
                "signal_close_location": framework.base._round(
                    signal_close_location, 6
                ),
                "sec_10k_candidate_score": framework.base._round(score, 6),
                "same_day_ab_entry_count": len(ab_entries),
                "same_day_ab_overlap": bool(ab_entries),
                "same_ticker_ab_overlap": any(
                    trade.get("ticker") == ticker for trade in ab_entries
                ),
                "known_at": "after_sec_10k_usable_trade_date_close_before_next_open_paper_entry",
                "trade_enabled": False,
                "alters_orders": False,
            }
        )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["sec_10k_candidate_score"]),
            -float(row["rs20_vs_spy"]),
            -float(row["signal_excess_return_1d_vs_spy"]),
            -float(row["avg_dollar_volume_20d"]),
            row["ticker"],
        )
    )
    return candidates, {
        "dates_checked": len(dates),
        "sec_10k_events_in_window": len(events),
        "candidate_count": len(candidates),
        "candidate_days": len({row["date"] for row in candidates}),
        "unique_candidate_tickers": len({row["ticker"] for row in candidates}),
        "candidate_universe_argument_count": len(universe),
        "audit_reject_counts": dict(sorted(audit.items())),
        "rule_version": RULE_VERSION,
        "sec_events_source": framework.base._repo_rel(SEC_EVENTS_FILE),
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
        failed.append("ev_regressed_window")
    if aggregate["windows_pnl_regressed"]:
        failed.append("pnl_regressed_window")
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_windows) < MIN_TARGET_WINDOWS:
        failed.append("target_window_count_too_small")
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
        "accepted_candidate_sec_10k_liquidity_rs"
        if gate4["passed"]
        else "rejected_sec_10k_liquidity_rs"
    )
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]
    actual_success = 1 if gate4["passed"] else 0
    prediction = {
        "success_probability": 0.22,
        "expected_ev_delta": 0.20,
        "expected_pnl_delta": 5000.0,
        "main_failure_modes": [
            "sample_too_thin",
            "late_strong_regression",
            "annual_report_not_immediate_catalyst",
            "concentration",
        ],
        "confidence_reason": (
            "10-K liquidity watch is production-visible and free, but annual-report "
            "timing may be slower than a 10d paper horizon."
        ),
        "recorded_at": "2026-05-29T12:06:22+00:00",
        "brier_score": round((0.22 - actual_success) ** 2, 6),
    }

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "PIT-safe SEC 10-K filings from liquid, above-trend stocks with "
                "positive 20-day relative strength may provide a free-data "
                "candidate-pool expansion source."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": (
                "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
            ),
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 0,
            "nearby_prior_experiments": [
                "exp-20260508-011",
                "exp-20260529-010",
                "exp-20260529-011",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": (
                "production_visible_free_sec_10k_filing_event_plus_ohlcv_rs"
            ),
            "prediction": prediction,
            "parameters": {
                "base_universe_count": payload["parameters"]["base_universe_count"],
                "stock_excluded_tickers": sorted(framework.EXCLUDED_TICKERS),
                "paper_notional_usd": framework.base.BASE_NOTIONAL_USD,
                "hold_days": framework.base.HOLD_DAYS,
                "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
                "moving_average_days": MOVING_AVERAGE_DAYS,
                "relative_strength_days": RELATIVE_STRENGTH_DAYS,
                "avg_dollar_volume_days": AVG_DOLLAR_VOLUME_DAYS,
                "min_close": MIN_CLOSE,
                "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
                "min_rs20_vs_spy": MIN_RS20_VS_SPY,
                "min_signal_excess_return_1d_vs_spy": (
                    MIN_SIGNAL_EXCESS_RETURN_1D_VS_SPY
                ),
                "min_signal_close_location": MIN_SIGNAL_CLOSE_LOCATION,
                "source_definition": [
                    "SEC filing event has form_base/form_type 10-K",
                    "event row must have pit_safe_flag true and usable_trade_date",
                    "amended 10-K rows are excluded",
                    "ticker must have exact signal-date OHLCV in the fixed snapshot",
                    "close must be above the prior 50-day moving average",
                    "20-day return must beat SPY by at least 3 percentage points",
                    "20-day average dollar volume must be at least USD 20 million",
                    "signal-day ticker-minus-SPY return must be no worse than -1 percentage point",
                    "signal-day close location must be at least 0.45",
                    "top-1 selected paper entry per signal date",
                ],
                "selection_rank": [
                    "signal_date",
                    "sec_10k_candidate_score desc",
                    "rs20_vs_spy desc",
                    "signal_excess_return_1d_vs_spy desc",
                    "avg_dollar_volume_20d desc",
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
                    "candidate_pool / entry: annual SEC 10-K filing availability, "
                    "when paired with same-day liquidity, trend, and relative strength, "
                    "may identify non-noisy continuation candidates."
                ),
                "2_history_check": {
                    "exp-20260508-011": (
                        "Identified liquidity-gated 10-K filing scouts as a "
                        "candidate-pool direction, but did not run a three-window "
                        "paper overlay acceptance test."
                    ),
                    "exp-20260529-010_and_011": (
                        "SEC Item 2.02 peer-transfer variants were rejected. This "
                        "run uses direct 10-K issuer filing events, not peer transfer."
                    ),
                    "recent_ohlcv_pattern_pools": (
                        "VWAP, long-base, OBV, and residual-leadership pullback "
                        "pools were rejected; this run adds a SEC filing event source "
                        "instead of renaming another price pattern."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same three docs/backtesting.md windows; positive aggregate EV/PnL; "
                    "no EV- or PnL-regressed window; >=20 paper trades across at least "
                    "2 windows; drawdown drift <=0.5pp; survival >=5%; concentration "
                    "inside guardrails."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260529_014_sec_10k_liquidity_rs_candidate_pool.py"
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because replay attribution remains sparse; "
                "skipped Companyfacts/VBB/VCP/state-surface scalar retunes because "
                "the playbook calls for forward rows or new fields. This tests one "
                "direct SEC filing candidate-source variable only."
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
                    "A retained result would still require a shared default-off paper "
                    "adapter and parity tests before any daily report or live/default "
                    "behavior changes."
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
                    "promotion would require extending the existing sec_10k_forward_watch "
                    "or a shared paper sleeve with exact as-of OHLCV guards and tests."
                ),
            },
            "interpretation": (
                "The SEC 10-K liquidity + RS candidate pool cleared Gate 4 as a "
                "default-off replay lead, but no production/shared policy was promoted."
                if gate4["passed"]
                else (
                    "The SEC 10-K liquidity + RS candidate pool did not clear Gate 4. "
                    "Do not promote it or retry nearby 10-K liquidity/RS thresholds "
                    "on the same frozen windows without forward rows or a sharper "
                    "10-K disclosure-quality field."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "next_evidence_needed": (
                "Forward replacement-value rows or a materially sharper free 10-K "
                "field, such as disclosure-quality/restatement/auditor-risk context."
            ),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "SEC 10-K event metadata uses pit_safe usable_trade_date. OHLCV filters "
        "are observed through the signal-date close; paper entry is the next "
        "available open with production entry slippage; exit is ten trading days "
        "after the signal with target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["gate2"]["runtime_field_coverage"] = {
        "sec_events": {
            "source": framework.base._repo_rel(SEC_EVENTS_FILE),
            "required_fields": [
                "ticker",
                "usable_trade_date",
                "accession_number",
                "form_base/form_type",
                "pit_safe_flag",
                "is_amendment",
            ],
            "events_loaded": len(_load_sec_10k_events()),
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
            "sec_accession_number",
            "sec_accepted_at",
            "rs20_vs_spy",
            "signal_excess_return_1d_vs_spy",
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
        framework.base._repo_rel(CARD_MD),
        framework.base._repo_rel(ARTIFACT_MD),
        framework.base._repo_rel(EXPERIMENT_LOG),
        framework.base._repo_rel(SEC_EVENTS_FILE),
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
            "# exp-20260529-014 SEC 10-K Liquidity + RS Candidate Pool",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: a default-off paper candidate source that admits PIT-safe SEC 10-K filings with liquidity, trend, and RS confirmation, top-1 per day, next-open entry, ten-trading-day exit.",
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
        "title": "SEC 10-K liquidity + RS candidate pool",
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": framework.base._repo_rel(ARTIFACT_MD),
        "json": framework.base._repo_rel(OUT_JSON),
        "before_aggregate": framework.base._repo_rel(BEFORE_AGG_JSON),
        "after_aggregate": framework.base._repo_rel(AFTER_AGG_JSON),
        "summary": payload["interpretation"],
    }
    framework.base._write_json(TICKET_JSON, ticket_payload)
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
