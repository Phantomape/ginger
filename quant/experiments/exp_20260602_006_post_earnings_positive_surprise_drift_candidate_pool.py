"""exp-20260602-006: post-earnings positive-surprise drift candidate pool.

This alpha scout tests a stock-only, production-visible, free-data candidate
source. A ticker can enter a default-off paper sleeve after the canonical
daily earnings snapshot confirms a new positive EPS surprise, and OHLCV still
shows post-event price/RS strength.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import hashlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260528_037_ticker_accumulation_quality_breakout as framework
import exp_20260531_001_pre_earnings_surprise_revision_rs_candidate_pool as earnings_helper


REPO_ROOT = Path(__file__).resolve().parents[2]

EXPERIMENT_ID = "exp-20260602-006"
STEM = "post_earnings_positive_surprise_drift_candidate_pool"
TRIAL_FAMILY = "post_earnings_positive_surprise_drift_candidate_pool"
CHANGED_VARIABLE = "post_earnings_positive_surprise_drift_candidate_source_v1"
RULE_VERSION = "post_earnings_positive_surprise_drift_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260602_006_{STEM}.json"
BEFORE_AGG_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_AGG_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"

RECENT_SIGNAL_DAYS_MIN = 0
RECENT_SIGNAL_DAYS_MAX = 5
MIN_LATEST_SURPRISE_PCT = 3.0
MIN_AVG_HISTORICAL_SURPRISE_PCT = 0.0
MIN_POSITIVE_SURPRISE_COUNT = 2
MIN_SURPRISE_HISTORY_COUNT = 4
MIN_RESET_DTE = 20
MAX_PRE_RESET_DTE = 7
MOVING_AVERAGE_DAYS = 50
RELATIVE_STRENGTH_DAYS = 20
AVG_DOLLAR_VOLUME_DAYS = 20
MIN_AVG_DOLLAR_VOLUME_20D = 40_000_000.0
MIN_RS20_VS_SPY = 0.0
MIN_CLOSE_LOCATION = 0.55
MIN_EVENT_TO_SIGNAL_RETURN = 0.0
MIN_EVENT_TO_SIGNAL_EXCESS_VS_SPY = 0.0


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
    framework.MAX_PAPER_TRADES_PER_DAY = 1
    framework.MIN_TARGET_TRADES = 20
    framework.MIN_TARGET_WINDOWS = 3
    framework.MAX_SINGLE_POSITIVE_SHARE = 0.50
    framework.MAX_POSITIVE_HHI = 0.30
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._build_report = _build_report


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _surprise_tail(info: dict[str, Any]) -> float | None:
    context = earnings_helper._surprise_context(info)
    if context is None:
        return None
    history = context.get("historical_surprise_pct") or []
    return float(history[-1]) if history else None


def _event_is_confirmed(prev_info: dict[str, Any], info: dict[str, Any]) -> bool:
    prev_dte = earnings_helper._float_or_none(prev_info.get("days_to_earnings"))
    current_dte = earnings_helper._float_or_none(info.get("days_to_earnings"))
    prev_actual = earnings_helper._float_or_none(prev_info.get("eps_actual_last"))
    current_actual = earnings_helper._float_or_none(info.get("eps_actual_last"))
    prev_tail = _surprise_tail(prev_info)
    current_tail = _surprise_tail(info)
    if current_actual is None or current_dte is None:
        return False
    dte_reset = (
        prev_dte is not None
        and prev_dte <= MAX_PRE_RESET_DTE
        and current_dte >= MIN_RESET_DTE
    )
    actual_changed = prev_actual is not None and current_actual != prev_actual
    tail_changed = prev_tail is not None and current_tail is not None and current_tail != prev_tail
    return dte_reset and (actual_changed or tail_changed)


def _positive_surprise_events(
    ticker: str,
    cfg: dict[str, str],
    trading_dates: list[str],
) -> list[dict[str, Any]]:
    index_rows = earnings_helper._load_earnings_index().get(str(ticker).upper(), [])
    if not index_rows:
        return []
    trading_set = set(trading_dates)
    events: list[dict[str, Any]] = []
    for pos in range(1, len(index_rows)):
        snap_date, info = index_rows[pos]
        prev_snap_date, prev_info = index_rows[pos - 1]
        if snap_date not in trading_set or snap_date < cfg["start"] or snap_date > cfg["end"]:
            continue
        if not _event_is_confirmed(prev_info, info):
            continue
        surprise = earnings_helper._surprise_context(info)
        if surprise is None:
            continue
        latest_surprise = _surprise_tail(info)
        if latest_surprise is None or latest_surprise < MIN_LATEST_SURPRISE_PCT:
            continue
        if surprise["historical_surprise_count"] < MIN_SURPRISE_HISTORY_COUNT:
            continue
        if surprise["positive_historical_surprise_count"] < MIN_POSITIVE_SURPRISE_COUNT:
            continue
        if surprise["avg_historical_surprise_pct"] < MIN_AVG_HISTORICAL_SURPRISE_PCT:
            continue
        events.append(
            {
                "ticker": str(ticker).upper(),
                "event_confirmed_date": snap_date,
                "previous_snapshot_source_date": prev_snap_date,
                "earnings_snapshot_source_date": snap_date,
                "latest_surprise_pct": latest_surprise,
                "avg_historical_surprise_pct": surprise["avg_historical_surprise_pct"],
                "historical_surprise_count": surprise["historical_surprise_count"],
                "positive_historical_surprise_count": surprise[
                    "positive_historical_surprise_count"
                ],
                "historical_surprise_pct": surprise["historical_surprise_pct"],
                "eps_actual_last": earnings_helper._float_or_none(info.get("eps_actual_last")),
                "days_to_next_earnings_after_event": earnings_helper._float_or_none(
                    info.get("days_to_earnings")
                ),
            }
        )
    return events


def _candidate_rows_for_window(
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    universe: list[str],
    before_result: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = framework.ohlcv_helper._baseline_entries(before_result)
    trading_dates = [
        date_value
        for date_value in framework.ohlcv_helper._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    trading_pos = {date_value: idx for idx, date_value in enumerate(trading_dates)}
    spy_rows = framework.ohlcv_helper._series(snapshot, "SPY")
    spy_index = framework.ohlcv_helper._row_index(spy_rows)
    candidates: list[dict[str, Any]] = []
    audit: Counter[str] = Counter()
    event_count = 0
    min_idx = max(MOVING_AVERAGE_DAYS, RELATIVE_STRENGTH_DAYS, AVG_DOLLAR_VOLUME_DAYS)

    for ticker in sorted(set(universe).intersection(snapshot).difference(framework.EXCLUDED_TICKERS)):
        rows = framework.ohlcv_helper._series(snapshot, ticker)
        idx_by_date = framework.ohlcv_helper._row_index(rows)
        events = _positive_surprise_events(ticker, cfg, trading_dates)
        event_count += len(events)
        for event in events:
            event_date = str(event["event_confirmed_date"])
            event_trade_pos = trading_pos.get(event_date)
            event_idx = idx_by_date.get(event_date)
            event_spy_idx = spy_index.get(event_date)
            if event_trade_pos is None or event_idx is None or event_spy_idx is None:
                audit["missing_event_ohlcv"] += 1
                continue
            if event_idx <= 0 or event_spy_idx <= 0:
                audit["missing_event_prior_close"] += 1
                continue

            admitted_event = False
            for offset in range(RECENT_SIGNAL_DAYS_MIN, RECENT_SIGNAL_DAYS_MAX + 1):
                signal_pos = event_trade_pos + offset
                if signal_pos >= len(trading_dates):
                    audit["signal_window_out_of_range"] += 1
                    continue
                signal_date = trading_dates[signal_pos]
                idx = idx_by_date.get(signal_date)
                spy_idx = spy_index.get(signal_date)
                if idx is None or spy_idx is None or idx < min_idx or spy_idx < RELATIVE_STRENGTH_DAYS:
                    audit["insufficient_ohlcv_history"] += 1
                    continue

                close = framework.ohlcv_helper._value(rows[idx], "Close")
                volume = framework.ohlcv_helper._value(rows[idx], "Volume")
                if not close or volume is None:
                    audit["missing_close_or_volume"] += 1
                    continue
                avg_dollar_volume = earnings_helper._avg_dollar_volume(
                    rows,
                    idx,
                    AVG_DOLLAR_VOLUME_DAYS,
                )
                if avg_dollar_volume is None:
                    audit["missing_avg_dollar_volume"] += 1
                    continue
                if avg_dollar_volume < MIN_AVG_DOLLAR_VOLUME_20D:
                    audit["low_avg_dollar_volume"] += 1
                    continue

                ma50 = earnings_helper._prior_average(rows, idx, MOVING_AVERAGE_DAYS, "Close")
                if ma50 is None or float(close) <= ma50:
                    audit["below_50d_trend"] += 1
                    continue
                close_location = framework._close_location(rows[idx])
                if close_location is None or close_location < MIN_CLOSE_LOCATION:
                    audit["weak_close_location"] += 1
                    continue

                ret20 = earnings_helper._close_return(rows, idx - RELATIVE_STRENGTH_DAYS, idx)
                spy_ret20 = earnings_helper._close_return(
                    spy_rows,
                    spy_idx - RELATIVE_STRENGTH_DAYS,
                    spy_idx,
                )
                if ret20 is None or spy_ret20 is None:
                    audit["missing_relative_strength"] += 1
                    continue
                rs20_vs_spy = ret20 - spy_ret20
                if rs20_vs_spy <= MIN_RS20_VS_SPY:
                    audit["rs20_not_positive_vs_spy"] += 1
                    continue

                event_to_signal_return = earnings_helper._close_return(
                    rows,
                    event_idx - 1,
                    idx,
                )
                spy_event_to_signal_return = earnings_helper._close_return(
                    spy_rows,
                    event_spy_idx - 1,
                    spy_idx,
                )
                if event_to_signal_return is None or spy_event_to_signal_return is None:
                    audit["missing_event_to_signal_return"] += 1
                    continue
                event_to_signal_excess = event_to_signal_return - spy_event_to_signal_return
                if event_to_signal_return < MIN_EVENT_TO_SIGNAL_RETURN:
                    audit["negative_event_to_signal_return"] += 1
                    continue
                if event_to_signal_excess < MIN_EVENT_TO_SIGNAL_EXCESS_VS_SPY:
                    audit["negative_event_to_signal_excess_vs_spy"] += 1
                    continue

                ab_entries = entries_by_date.get(signal_date, [])
                score = (
                    (float(event["latest_surprise_pct"]) / 100.0)
                    + (float(event["avg_historical_surprise_pct"]) / 200.0)
                    + event_to_signal_excess
                    + rs20_vs_spy
                    + (close_location / 10.0)
                )
                candidates.append(
                    {
                        "ticker": ticker,
                        "date": signal_date,
                        "strategy": STEM,
                        "rule_version": RULE_VERSION,
                        "close": framework.base._round(close, 4),
                        "volume": framework.base._round(volume, 2),
                        "avg_dollar_volume_20d": framework.base._round(avg_dollar_volume, 2),
                        "ma50": framework.base._round(ma50, 4),
                        "close_location": framework.base._round(close_location, 6),
                        "ret20": framework.base._round(ret20, 6),
                        "spy_ret20": framework.base._round(spy_ret20, 6),
                        "rs20_vs_spy": framework.base._round(rs20_vs_spy, 6),
                        "event_confirmed_date": event_date,
                        "recent_signal_trading_day_offset": offset,
                        "latest_surprise_pct": framework.base._round(
                            event["latest_surprise_pct"],
                            6,
                        ),
                        "avg_historical_surprise_pct": framework.base._round(
                            event["avg_historical_surprise_pct"],
                            6,
                        ),
                        "historical_surprise_count": event["historical_surprise_count"],
                        "positive_historical_surprise_count": event[
                            "positive_historical_surprise_count"
                        ],
                        "eps_actual_last": framework.base._round(
                            event["eps_actual_last"],
                            6,
                        ),
                        "days_to_next_earnings_after_event": int(
                            event["days_to_next_earnings_after_event"]
                        ),
                        "earnings_snapshot_source_date": event[
                            "earnings_snapshot_source_date"
                        ],
                        "previous_snapshot_source_date": event[
                            "previous_snapshot_source_date"
                        ],
                        "event_to_signal_return": framework.base._round(
                            event_to_signal_return,
                            6,
                        ),
                        "spy_event_to_signal_return": framework.base._round(
                            spy_event_to_signal_return,
                            6,
                        ),
                        "event_to_signal_excess_vs_spy": framework.base._round(
                            event_to_signal_excess,
                            6,
                        ),
                        "post_earnings_positive_surprise_drift_score": framework.base._round(
                            score,
                            6,
                        ),
                        "same_day_ab_entry_count": len(ab_entries),
                        "same_day_ab_overlap": bool(ab_entries),
                        "same_ticker_ab_overlap": any(
                            trade.get("ticker") == ticker for trade in ab_entries
                        ),
                        "known_at": "after_earnings_snapshot_transition_and_signal_date_close_before_next_open_paper_entry",
                        "trade_enabled": False,
                        "alters_orders": False,
                    }
                )
                admitted_event = True
                break
            if not admitted_event:
                audit["event_without_qualifying_drift_signal"] += 1

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["post_earnings_positive_surprise_drift_score"]),
            int(row["recent_signal_trading_day_offset"]),
            -float(row["latest_surprise_pct"]),
            -float(row["event_to_signal_excess_vs_spy"]),
            -float(row["rs20_vs_spy"]),
            -float(row["avg_dollar_volume_20d"]),
            row["ticker"],
        )
    )
    return candidates, {
        "dates_checked": len(trading_dates),
        "positive_surprise_event_count": event_count,
        "candidate_count": len(candidates),
        "candidate_days": len({row["date"] for row in candidates}),
        "unique_candidate_tickers": len({row["ticker"] for row in candidates}),
        "earnings_snapshot_dates_loaded": earnings_helper._EARNINGS_DATE_COUNT,
        "audit_reject_counts": dict(sorted(audit.items())),
        "rule_version": RULE_VERSION,
        "earnings_snapshot_source": "data/daily/snapshots/earnings/earnings_snapshot_*.json",
    }


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    gate4 = payload["gate4"]
    decision = (
        "positive_replay_lead_not_promoted_requires_shared_adapter_and_forward_rows"
        if gate4["passed"]
        else "rejected_post_earnings_positive_surprise_drift_candidate_pool"
    )
    all_target_trades = [
        trade
        for trades in payload["target_trades_by_window"].values()
        for trade in trades
    ]
    actual_success = 1 if gate4["passed"] else 0
    prediction = {
        "success_probability": 0.30,
        "expected_ev_delta": None,
        "expected_pnl_delta": None,
        "main_failure_modes": [
            "event_sample_still_too_thin",
            "positive_surprise_drift_regresses_one_window",
            "overlay_concentrated_in_one_ticker_or_window",
        ],
        "confidence_reason": (
            "Accepted post-earnings continuation semantics improved all windows, "
            "but the DTE0 reaction source had zero selected trades. Snapshot "
            "transition-derived positive surprises should provide more sample "
            "while staying production-visible."
        ),
        "recorded_at": "2026-06-02T03:07:10+00:00",
        "brier_score": round((0.30 - actual_success) ** 2, 6),
    }

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lane": "alpha_search",
            "status": "completed",
            "decision": decision,
            "hypothesis": (
                "Recently confirmed positive EPS surprise events with retained "
                "post-event price/RS strength may add a production-visible "
                "default-off candidate pool beyond the accepted core."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "mechanism_family": "post_earnings_continuation",
            "trial_variant_id": RULE_VERSION,
            "prior_trial_count": 5,
            "nearby_prior_experiments": [
                "exp-20260426-037",
                "exp-20260531-003",
                "exp-20260602-002",
                "exp-20260602-003",
                "exp-20260602-004",
            ],
            "reservation_nearby_prior_note": (
                "The reserved ticket listed exp-20260528-037 from a meta-report "
                "label mismatch; the actual comparable earnings/post-earnings "
                "families are enumerated here."
            ),
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "production_visible_earnings_snapshot_transition_positive_surprise_plus_ohlcv_drift",
            "prediction": prediction,
            "parameters": {
                "base_universe_count": payload["parameters"]["base_universe_count"],
                "stock_excluded_tickers": sorted(framework.EXCLUDED_TICKERS),
                "paper_notional_usd": framework.base.BASE_NOTIONAL_USD,
                "hold_days": framework.base.HOLD_DAYS,
                "max_paper_trades_per_day": framework.MAX_PAPER_TRADES_PER_DAY,
                "recent_signal_days_min": RECENT_SIGNAL_DAYS_MIN,
                "recent_signal_days_max": RECENT_SIGNAL_DAYS_MAX,
                "min_latest_surprise_pct": MIN_LATEST_SURPRISE_PCT,
                "min_avg_historical_surprise_pct": MIN_AVG_HISTORICAL_SURPRISE_PCT,
                "min_positive_surprise_count": MIN_POSITIVE_SURPRISE_COUNT,
                "min_surprise_history_count": MIN_SURPRISE_HISTORY_COUNT,
                "min_reset_dte": MIN_RESET_DTE,
                "max_pre_reset_dte": MAX_PRE_RESET_DTE,
                "moving_average_days": MOVING_AVERAGE_DAYS,
                "relative_strength_days": RELATIVE_STRENGTH_DAYS,
                "avg_dollar_volume_days": AVG_DOLLAR_VOLUME_DAYS,
                "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
                "min_rs20_vs_spy": MIN_RS20_VS_SPY,
                "min_close_location": MIN_CLOSE_LOCATION,
                "min_event_to_signal_return": MIN_EVENT_TO_SIGNAL_RETURN,
                "min_event_to_signal_excess_vs_spy": MIN_EVENT_TO_SIGNAL_EXCESS_VS_SPY,
                "source_definition": [
                    "canonical daily earnings snapshot transition shows DTE reset from <=7 to >=20",
                    "eps_actual_last or latest historical_surprise_pct changes on the reset date",
                    "latest historical_surprise_pct >= 3",
                    "first qualifying signal within 0-5 trading days after event confirmation",
                    "ticker closes above prior 50-day moving average",
                    "20-day return exceeds SPY",
                    "event-to-signal return and excess return versus SPY are non-negative",
                    "20-day average dollar volume >= 40 million",
                    "signal-day close location >= 0.55",
                    "same-ticker core overlap is filtered by the shared framework",
                    "top-1 selected paper entry per signal date",
                ],
                "selection_rank": [
                    "signal_date",
                    "post_earnings_positive_surprise_drift_score desc",
                    "recent_signal_trading_day_offset asc",
                    "latest_surprise_pct desc",
                    "event_to_signal_excess_vs_spy desc",
                    "rs20_vs_spy desc",
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
                "acceptance": payload["parameters"]["acceptance"],
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "candidate_pool / entry: recently confirmed positive EPS "
                    "surprise plus retained post-event price/RS strength should "
                    "identify PEAD-like candidates beyond core entries."
                ),
                "2_history_check": {
                    "exp-20260426-037": (
                        "Older post-earnings shadow had zero candidates due sparse "
                        "DTE0 event coverage."
                    ),
                    "exp-20260531-003": (
                        "Pre-earnings imminent surprise/RS improved aggregate but "
                        "regressed late_strong and drawdown; this run is post-event "
                        "and requires 3/3 window improvement."
                    ),
                    "exp-20260602-003": (
                        "Accepted explicit post-earnings continuation semantics; "
                        "this run tests a separate candidate source using the same "
                        "production-visible snapshot lifecycle."
                    ),
                    "exp-20260602-004": (
                        "DTE0 reaction scout selected zero trades; this widens to "
                        "0-5 trading days after a confirmed positive surprise."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same three docs/backtesting.md windows; positive aggregate "
                    "EV/PnL; 3/3 EV-improved windows; no PnL-regressed window; "
                    ">=20 paper trades across all 3 windows; drawdown drift "
                    "<=0.5pp; survival >=5%; concentration inside guardrails."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                    "exp_20260602_006_post_earnings_positive_surprise_drift_candidate_pool.py"
                ),
            },
            "why_not_other_changes": (
                "Skipped LLM soft-ranking because event-outcome joins remain sparse. "
                "Skipped Companyfacts, FINRA, VBB, consensus, and state-surface "
                "threshold/scalar retunes because the playbook asks for forward "
                "replacement rows or materially new fields. This is a new "
                "production-visible free-data earnings lifecycle source."
            ),
            "production_parity": {
                "alters_production_orders": False,
                "alters_live_watchlists": False,
                "alters_core_backtester": False,
                "default_enabled": False,
                "replay_only": True,
                "parity_note": (
                    "No production code path is changed. If promoted later, the "
                    "source must be moved into a shared default-off adapter using "
                    "the same daily earnings snapshot lifecycle already documented "
                    "in docs/production_backtest_parity.md, with focused parity "
                    "tests before any live/report consumer uses it."
                ),
            },
            "interpretation": (
                "The post-earnings positive-surprise drift sleeve cleared Gate 4 "
                "as a replay lead, but no production/shared policy was promoted."
                if gate4["passed"]
                else (
                    "The post-earnings positive-surprise drift sleeve did not clear "
                    "Gate 4. Do not promote it or retry adjacent event-reaction/"
                    "surprise/RS thresholds on these frozen windows without forward "
                    "rows or a richer event-quality field."
                )
            ),
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "next_evidence_needed": (
                "If revisited, use closed forward replacement-value rows or a richer "
                "production-visible event-quality field such as guidance direction, "
                "same-event revenue/EPS mix, or audited filing/news tone."
            ),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Earnings event confirmation is derived from canonical daily earnings "
        "snapshot transitions dated at or before the signal date. OHLCV "
        "confirmation is observed through the signal-date close; paper entry is "
        "the next available open with production entry slippage; exit is ten "
        "trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    payload["gate2"]["runtime_field_coverage"] = {
        "earnings_snapshots": {
            "source": "data/daily/snapshots/earnings/earnings_snapshot_*.json",
            "snapshots_loaded": earnings_helper._EARNINGS_DATE_COUNT,
            "required_fields": [
                "days_to_earnings",
                "eps_actual_last",
                "historical_surprise_pct",
                "avg_historical_surprise_pct",
            ],
            "tickers_with_snapshot_rows": len(earnings_helper._load_earnings_index()),
            "event_confirmation_rule": (
                "DTE reset <=7 to >=20 plus eps_actual_last or latest "
                "historical_surprise_pct change."
            ),
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
            "event_confirmed_date",
            "latest_surprise_pct",
            "eps_actual_last",
            "event_to_signal_excess_vs_spy",
            "rs20_vs_spy",
            "avg_dollar_volume_20d",
        ],
    )
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Trades | Events | Raw candidates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        events = payload["candidate_audits"][label].get("positive_surprise_event_count", 0)
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {trades} | {events} | {raw} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                events=events,
                raw=payload["raw_candidate_counts"][label],
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    return "\n".join(
        [
            "# exp-20260602-006 Post-Earnings Positive-Surprise Drift Candidate Pool",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: a default-off paper source using PIT earnings snapshot transition-confirmed positive EPS surprise plus post-event OHLCV strength, top-1 per day, next-open entry, ten-trading-day exit.",
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
        "title": "Post-earnings positive-surprise drift candidate pool",
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
    _write_manifest()


def _write_manifest() -> None:
    files = {
        "runner": framework.base._repo_rel(Path(__file__)),
        "result": framework.base._repo_rel(OUT_JSON),
        "before_aggregate": framework.base._repo_rel(BEFORE_AGG_JSON),
        "after_aggregate": framework.base._repo_rel(AFTER_AGG_JSON),
        "log": framework.base._repo_rel(LOG_JSON),
        "ticket": framework.base._repo_rel(TICKET_JSON),
        "doc_ticket": framework.base._repo_rel(DOC_TICKET_JSON),
        "card": framework.base._repo_rel(CARD_MD),
        "artifact": framework.base._repo_rel(ARTIFACT_MD),
        "manifest": framework.base._repo_rel(MANIFEST_JSON),
        "experiment_log": framework.base._repo_rel(EXPERIMENT_LOG),
    }
    manifest = {
        "schema_version": 1,
        "manifest_type": "ginger_experiment_revision_manifest",
        "experiment_id": EXPERIMENT_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": {
            label: {
                "path": rel_path,
                "exists": (REPO_ROOT / rel_path).exists(),
                "sha256": _sha256(REPO_ROOT / rel_path),
            }
            for label, rel_path in files.items()
        },
    }
    framework.base._write_json(MANIFEST_JSON, manifest)


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
