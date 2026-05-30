"""exp-20260530-015: SEC small event-family burst candidate pool.

This alpha search tests one free-data candidate source: PIT-safe SEC filings
that occur in exactly two-ticker, same-day, same-event-family bursts, with
basic OHLCV confirmation. The sleeve is default-off paper only, admits at most
one candidate per signal day, enters at the next available open, and exits
after ten trading days.

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
import exp_20260530_006_sec_event_family_burst_attribution as burst_helper


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260530-015"
STEM = "sec_small_event_family_burst_candidate_pool"
TRIAL_FAMILY = "sec_event_family_small_burst_candidate_pool"
CHANGED_VARIABLE = "sec_small_event_family_burst_candidate_source_v1"
RULE_VERSION = "sec_small_event_family_burst_candidate_source_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260530_015_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
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
AVG_DOLLAR_VOLUME_DAYS = 20
MIN_CLOSE = 5.0
MIN_AVG_DOLLAR_VOLUME_20D = 20_000_000.0
MIN_SIGNAL_EXCESS_RETURN_1D_VS_SPY = -0.01
MIN_SIGNAL_CLOSE_LOCATION = 0.45
TARGET_SAME_FAMILY_UNIQUE_TICKERS = 2
MAX_PAPER_TRADES_PER_DAY = 1
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.40
MAX_POSITIVE_HHI = 0.30

_SEC_EVENTS_CACHE: list[dict[str, Any]] | None = None


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


def _load_sec_events() -> list[dict[str, Any]]:
    global _SEC_EVENTS_CACHE
    if _SEC_EVENTS_CACHE is not None:
        return _SEC_EVENTS_CACHE

    rows = burst_helper._dedupe_events(burst_helper._read_jsonl(SEC_EVENTS_FILE))
    rows = [
        row
        for row in rows
        if row.get("pit_safe_flag") is True and not bool(row.get("is_amendment"))
    ]
    burst_counts = burst_helper._build_burst_counts(rows)
    out: list[dict[str, Any]] = []
    for row in rows:
        ticker = str(row.get("ticker") or "").upper().strip()
        date = str(row.get("usable_trade_date") or "").strip()[:10]
        accession = str(row.get("accession_number") or "").strip()
        if not ticker or not date or not accession:
            continue
        family = burst_helper._event_family_bucket(row)
        burst = burst_counts.get((date, family), {})
        out.append(
            {
                "ticker": ticker,
                "usable_trade_date": date,
                "accession_number": accession,
                "accepted_at": row.get("accepted_at"),
                "filing_date": str(row.get("filing_date") or "")[:10] or None,
                "form_base": row.get("form_base"),
                "form_type": row.get("form_type"),
                "eight_k_item_codes": row.get("eight_k_item_codes") or [],
                "items_raw": row.get("items_raw"),
                "archive_url": row.get("archive_url"),
                "pit_source": row.get("pit_source"),
                "event_family_bucket": family,
                "same_family_event_count": int(burst.get("same_family_event_count") or 1),
                "same_family_unique_ticker_count": int(
                    burst.get("same_family_unique_ticker_count") or 1
                ),
                "same_family_burst_bucket": burst.get(
                    "same_family_burst_bucket",
                    "singleton",
                ),
            }
        )

    _SEC_EVENTS_CACHE = sorted(
        out,
        key=lambda row: (
            str(row["usable_trade_date"]),
            str(row["event_family_bucket"]),
            str(row["ticker"]),
            str(row["accession_number"]),
        ),
    )
    return _SEC_EVENTS_CACHE


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
    events = [event for event in _load_sec_events() if event["usable_trade_date"] in dates]
    candidates: list[dict[str, Any]] = []
    audit: Counter[str] = Counter()
    seen_ticker_dates: set[tuple[str, str, str]] = set()

    for event in events:
        ticker = str(event["ticker"]).upper()
        date = str(event["usable_trade_date"])
        if ticker in framework.EXCLUDED_TICKERS:
            audit["excluded_ticker"] += 1
            continue
        if event["same_family_unique_ticker_count"] != TARGET_SAME_FAMILY_UNIQUE_TICKERS:
            audit["not_two_ticker_same_family_burst"] += 1
            continue

        rows = framework.ohlcv_helper._series(snapshot, ticker)
        idx = framework.ohlcv_helper._row_index(rows).get(date)
        spy_idx = spy_index.get(date)
        if idx is None or spy_idx is None or idx < MOVING_AVERAGE_DAYS or spy_idx < 1:
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

        key = (ticker, date, str(event["event_family_bucket"]))
        if key in seen_ticker_dates:
            audit["duplicate_ticker_date_family"] += 1
            continue
        seen_ticker_dates.add(key)

        ab_entries = entries_by_date.get(date, [])
        score = (
            signal_excess_return
            + (signal_close_location * 0.10)
            + min(math.log10(max(avg_dollar_volume, 1.0)) / 100.0, 0.10)
            + (event["same_family_event_count"] * 0.005)
        )
        candidates.append(
            {
                "date": date,
                "ticker": ticker,
                "strategy": STEM,
                "rule_version": RULE_VERSION,
                "sec_accession_number": event.get("accession_number"),
                "sec_accepted_at": event.get("accepted_at"),
                "sec_filing_date": event.get("filing_date"),
                "sec_form_base": event.get("form_base"),
                "sec_form_type": event.get("form_type"),
                "sec_items_raw": event.get("items_raw"),
                "sec_eight_k_item_codes": event.get("eight_k_item_codes"),
                "sec_archive_url": event.get("archive_url"),
                "sec_pit_source": event.get("pit_source"),
                "event_family_bucket": event["event_family_bucket"],
                "same_family_event_count": event["same_family_event_count"],
                "same_family_unique_ticker_count": event[
                    "same_family_unique_ticker_count"
                ],
                "same_family_burst_bucket": event["same_family_burst_bucket"],
                "close": framework.base._round(close, 4),
                "volume": framework.base._round(volume, 2),
                "ma50": framework.base._round(ma50, 4),
                "avg_dollar_volume_20d": framework.base._round(avg_dollar_volume, 2),
                "signal_return_1d": framework.base._round(signal_return_1d, 6),
                "spy_return_1d": framework.base._round(spy_return_1d, 6),
                "signal_excess_return_1d_vs_spy": framework.base._round(
                    signal_excess_return,
                    6,
                ),
                "signal_close_location": framework.base._round(
                    signal_close_location,
                    6,
                ),
                "small_burst_candidate_score": framework.base._round(score, 6),
                "same_day_ab_entry_count": len(ab_entries),
                "same_day_ab_overlap": bool(ab_entries),
                "same_ticker_ab_overlap": any(
                    trade.get("ticker") == ticker for trade in ab_entries
                ),
                "known_at": (
                    "after_sec_usable_trade_date_close_before_next_open_paper_entry"
                ),
                "trade_enabled": False,
                "alters_orders": False,
            }
        )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["small_burst_candidate_score"]),
            -float(row["signal_excess_return_1d_vs_spy"]),
            -float(row["signal_close_location"]),
            -float(row["avg_dollar_volume_20d"]),
            row["ticker"],
        )
    )
    return candidates, {
        "dates_checked": len(dates),
        "sec_events_in_window": len(events),
        "candidate_count": len(candidates),
        "candidate_days": len({row["date"] for row in candidates}),
        "unique_candidate_tickers": len({row["ticker"] for row in candidates}),
        "candidate_universe_argument_count": len(universe),
        "audit_reject_counts": dict(sorted(audit.items())),
        "rule_version": RULE_VERSION,
        "target_same_family_unique_tickers": TARGET_SAME_FAMILY_UNIQUE_TICKERS,
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


def _load_ticket() -> dict[str, Any]:
    if not TICKET_JSON.exists():
        return {}
    with TICKET_JSON.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    ticket = _load_ticket()
    gate4 = payload["gate4"]
    decision = (
        "accepted_candidate_sec_small_event_family_burst"
        if gate4["passed"]
        else "rejected_sec_small_event_family_burst"
    )
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]
    prediction = dict(ticket.get("prediction") or {})
    actual_success = 1 if gate4["passed"] else 0
    if prediction:
        prediction["brier_score"] = round(
            (float(prediction.get("success_probability") or 0.0) - actual_success) ** 2,
            6,
        )

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "hypothesis": (
                "SEC filings that occur in exactly two-ticker same-day "
                "same-event-family bursts may capture focused event attention "
                "without crowded high-burst reversal; with PIT SEC metadata and "
                "OHLCV confirmation they may provide a free-data default-off "
                "candidate-pool source."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": (
                "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
            ),
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 1,
            "nearby_prior_experiments": [
                "exp-20260530-006",
                "exp-20260530-012",
                "exp-20260529-010",
                "exp-20260529-011",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": (
                "production_visible_free_sec_event_graph_small_burst_field"
            ),
            "prediction": prediction,
            "parameters": {
                "base_universe_count": payload["parameters"]["base_universe_count"],
                "stock_excluded_tickers": sorted(framework.EXCLUDED_TICKERS),
                "paper_notional_usd": framework.base.BASE_NOTIONAL_USD,
                "hold_days": framework.base.HOLD_DAYS,
                "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
                "target_same_family_unique_tickers": TARGET_SAME_FAMILY_UNIQUE_TICKERS,
                "moving_average_days": MOVING_AVERAGE_DAYS,
                "avg_dollar_volume_days": AVG_DOLLAR_VOLUME_DAYS,
                "min_close": MIN_CLOSE,
                "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
                "min_signal_excess_return_1d_vs_spy": (
                    MIN_SIGNAL_EXCESS_RETURN_1D_VS_SPY
                ),
                "min_signal_close_location": MIN_SIGNAL_CLOSE_LOCATION,
                "source_definition": [
                    "SEC row must have pit_safe_flag true",
                    "amended rows are excluded",
                    "same usable_trade_date and same event_family_bucket must have exactly two unique tickers",
                    "ticker must have exact signal-date OHLCV in the fixed snapshot",
                    "close must be above prior 50-day moving average",
                    "20-day average dollar volume must be at least USD 20 million",
                    "signal-day ticker-minus-SPY return must be no worse than -1 percentage point",
                    "signal-day close location must be at least 0.45",
                    "top-1 selected paper entry per signal date",
                ],
                "selection_rank": [
                    "signal_date",
                    "small_burst_candidate_score desc",
                    "signal_excess_return_1d_vs_spy desc",
                    "signal_close_location desc",
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
                    "candidate_pool / entry: a same-event-family SEC burst of "
                    "exactly two tickers may represent focused sector/theme "
                    "attention rather than broad crowded filing days."
                ),
                "2_history_check": {
                    "exp-20260530-006": (
                        "Read-only event-family burst attribution rejected the "
                        "broad high-burst field, but its small_burst_2 bucket was "
                        "positive in all three windows. This run tests that "
                        "separate field as a formal paper candidate source."
                    ),
                    "exp-20260530-012": (
                        "SEC sector-event breadth candidate pool was rejected. "
                        "This run uses ticker-level event-family burst membership, "
                        "not sector breadth or peer transfer."
                    ),
                    "exp-20260529-010_and_011": (
                        "SEC Item 2.02 peer-transfer variants were rejected. This "
                        "run does not buy peers; it only evaluates the filing "
                        "issuer itself when the event-family burst is exactly two."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same three docs/backtesting.md windows; positive aggregate "
                    "EV/PnL; no EV- or PnL-regressed window; >=20 paper trades "
                    "across all 3 windows; drawdown drift <=0.5pp; survival >=5%; "
                    "concentration inside guardrails."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260530_015_sec_small_event_family_burst_candidate_pool.py"
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because candidate-level replay coverage "
                "remains sparse; skipped SEC structured financial-improvement "
                "fields because daily feature snapshots have zero populated "
                "same-accession financial-improvement rows in the fixed windows; "
                "skipped FINRA/state-surface/VCP scalar retunes per playbook "
                "freeze guidance. This tests one SEC event-graph candidate source."
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
                    "A retained result would still require a shared default-off "
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
                    "No production code path is changed. If accepted, promotion "
                    "requires a shared event-family burst adapter that uses the "
                    "same SEC PIT fields and signal-date OHLCV guards."
                ),
            },
            "interpretation": (
                "The SEC small event-family burst candidate pool cleared Gate 4 "
                "as a default-off replay lead, but no production/shared policy "
                "was promoted."
                if gate4["passed"]
                else (
                    "The SEC small event-family burst candidate pool did not "
                    "clear Gate 4. Do not promote it or retry nearby burst-count "
                    "thresholds on the same frozen windows without forward rows "
                    "or a materially sharper relation field."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "next_evidence_needed": (
                "Forward replacement-value rows or a materially sharper free SEC "
                "relation field such as customer/supplier, supply-chain, or "
                "source-overlap context."
            ),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "SEC event metadata uses PIT-safe usable_trade_date. Event-family burst "
        "membership is computed only from rows sharing the same usable_trade_date "
        "and event_family_bucket. OHLCV filters are observed through the "
        "signal-date close; paper entry is the next available open with "
        "production entry slippage; exit is ten trading days after the signal "
        "with target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["gate2"]["runtime_field_coverage"] = {
        "sec_events": {
            "source": framework.base._repo_rel(SEC_EVENTS_FILE),
            "required_fields": [
                "ticker",
                "usable_trade_date",
                "accession_number",
                "accepted_at",
                "form_base/form_type",
                "eight_k_item_codes/items_raw",
                "pit_safe_flag",
                "is_amendment",
            ],
            "events_loaded": len(_load_sec_events()),
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
            "event_family_bucket",
            "same_family_unique_ticker_count",
            "same_family_burst_bucket",
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
        framework.base._repo_rel(DOC_TICKET_JSON),
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
            "# exp-20260530-015 SEC Small Event-Family Burst Candidate Pool",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: a default-off paper candidate source that admits PIT-safe SEC filings from exactly two-ticker same-day same-event-family bursts with OHLCV confirmation, top-1 per day, next-open entry, ten-trading-day exit.",
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


def _build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            "---",
            f'experiment_id: "{EXPERIMENT_ID}"',
            f'status: "{payload["status"]}"',
            'lane: "alpha_search"',
            f'change_type: "{payload["change_type"]}"',
            f'trial_family: "{TRIAL_FAMILY}"',
            f'trial_variant_id: "{RULE_VERSION}"',
            f'changed_variable: "{CHANGED_VARIABLE}"',
            'new_evidence_type: "production_visible_free_sec_event_graph_small_burst_field"',
            f'updated_at: "{payload["timestamp"]}"',
            "---",
            "",
            f"# Experiment Card: {EXPERIMENT_ID}",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Aggregate EV delta: `{aggregate['expected_value_score_delta_sum']}`",
            f"- Aggregate PnL delta: `${aggregate['total_pnl_delta_sum']}`",
            f"- Target trades: `{payload['target_trade_summary']['total_trade_count']}`",
            "",
            "## Summary",
            "",
            payload["interpretation"],
            "",
        ]
    )


def _persist(payload: dict[str, Any]) -> None:
    framework.base._write_json(OUT_JSON, payload)
    framework.base._write_json(BEFORE_AGG_JSON, payload["judge_before_aggregate"])
    framework.base._write_json(AFTER_AGG_JSON, payload["judge_after_aggregate"])
    framework.base._write_json(LOG_JSON, payload)
    ticket_payload = {
        **_load_ticket(),
        "experiment_id": EXPERIMENT_ID,
        "title": "SEC small event-family burst candidate pool",
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact_file": framework.base._repo_rel(OUT_JSON),
        "artifact": framework.base._repo_rel(ARTIFACT_MD),
        "json": framework.base._repo_rel(OUT_JSON),
        "before_aggregate": framework.base._repo_rel(BEFORE_AGG_JSON),
        "after_aggregate": framework.base._repo_rel(AFTER_AGG_JSON),
        "result_file": framework.base._repo_rel(LOG_JSON),
        "report_file": framework.base._repo_rel(ARTIFACT_MD),
        "completed_at": payload["timestamp"],
        "updated_at": payload["timestamp"],
        "result": {
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "artifact": framework.base._repo_rel(ARTIFACT_MD),
            "json": framework.base._repo_rel(OUT_JSON),
            "expected_value_score_delta": payload["expected_value_score_delta"],
            "total_pnl_delta": payload["total_pnl_delta"],
        },
        "summary": payload["interpretation"],
    }
    framework.base._write_json(TICKET_JSON, ticket_payload)
    framework.base._write_json(DOC_TICKET_JSON, ticket_payload)
    framework.base._write_text(ARTIFACT_MD, _build_report(payload))
    framework.base._write_text(CARD_MD, _build_card(payload))
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
