"""exp-20260612-011: post-earnings negative-surprise absorption scout.

Replay-only alpha search. This tests one fixed candidate-source variable:
negative EPS-surprise earnings snapshot transitions that are absorbed by
post-event liquid SPY-relative leadership before a top-1 next-open default-off
paper entry with a fixed 10-trading-day hold.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import exp_20260612_005_sec_periodic_filing_timing_surprise as previous
import post_earnings_underpriced_drift_paper_sleeve as pead


framework = previous.framework
base = previous.base

EXPERIMENT_ID = "exp-20260612-011"
STEM = "post_earnings_negative_surprise_absorption"
TRIAL_FAMILY = "post_earnings_negative_surprise_absorption_candidate_pool"
TRIAL_VARIANT_ID = "post_earnings_negative_surprise_absorption_top1_next_open_10d_v1"
CHANGED_VARIABLE = "post_earnings_negative_surprise_absorption_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "codex-alpha-search"

REPO_ROOT = previous.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260612_011_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = previous.BASE_NOTIONAL_USD
HOLD_DAYS = previous.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = previous.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = previous.SAME_TICKER_COOLDOWN_DAYS

MAX_LATEST_SURPRISE_PCT = -3.0
MIN_SURPRISE_HISTORY_COUNT = 4
RECENT_SIGNAL_DAYS_MIN = 0
RECENT_SIGNAL_DAYS_MAX = 5
MIN_EVENT_TO_SIGNAL_RETURN = 0.0
MIN_EVENT_TO_SIGNAL_EXCESS_VS_SPY = 0.0

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = previous.MAX_DRAWDOWN_WORSE
MAX_SINGLE_POSITIVE_SHARE = previous.MAX_SINGLE_POSITIVE_SHARE
MAX_POSITIVE_HHI = previous.MAX_POSITIVE_HHI

ACCEPTED_COMPRESSION_COMPARATOR = previous.ACCEPTED_COMPRESSION_COMPARATOR
ACCEPTED_DISTRIBUTION_COMPARATOR = previous.ACCEPTED_DISTRIBUTION_COMPARATOR
BASE_GATE4 = previous.BASE_GATE4
BASE_BUILD_PAYLOAD = previous.BASE_BUILD_PAYLOAD

EVENT_CONFIG = {
    **pead.DEFAULT_CONFIG,
    "max_pre_reset_dte": pead.DEFAULT_CONFIG["max_pre_reset_dte"],
    "min_reset_dte": pead.DEFAULT_CONFIG["min_reset_dte"],
}

PREDICTION = {
    "success_probability": 0.14,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "negative_surprise_is_bad_news",
        "thin_sample",
        "window_regression",
        "post_earnings_near_neighbor",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Positive post-earnings drift exists for underpriced positive surprises, "
        "but old earnings-event revival and earnings cadence scouts failed; this "
        "tests a distinct bad-news-absorption field using PIT earnings snapshots "
        "and OHLCV confirmation, with high risk of thin or genuinely negative "
        "sample."
    ),
    "recorded_at": "2026-06-12T07:05:51+00:00",
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
    "uses_llm": False,
    "uses_free_earnings_snapshots": True,
    "uses_free_ohlcv": True,
    "parity_note": (
        "This experiment changes no production code. A positive result remains "
        "only a replay lead. Promotion would require one shared default-off "
        "adapter that loads the same PIT earnings snapshot transitions, computes "
        "the same negative-surprise and post-event absorption fields, applies the "
        "same signal-date OHLCV leadership envelope, overlap exclusion, next-open "
        "paper entry, 10-trading-day exit, costs, cooldown, comparator, and "
        "concentration guards in historical replay and daily production before "
        "any report queue, paper ledger, candidate priority, sizing, watchlist, "
        "or order surface could change."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: negative EPS-surprise earnings events that are absorbed "
        "by event-to-signal nonnegative return, nonnegative SPY excess, liquid "
        "trend leadership, and high close-location may identify expectation-reset "
        "stocks with continuation value after next-open paper entry."
    ),
    "2_history_check": {
        "exp-20260421-004": (
            "Rejected broad earnings_event_long re-enable even after repaired "
            "earnings snapshots; this run is not re-enabling core C and uses a "
            "default-off paper source with explicit negative-surprise absorption."
        ),
        "exp-20260421-007": (
            "Rejected a simple above-200ma gate for earnings_event_long; this run "
            "uses event-transition surprise plus post-event price absorption, not "
            "a one-dimensional trend gate."
        ),
        "exp-20260602-026": (
            "Accepted positive-surprise underpriced drift shared adapter. This "
            "run does not retune that sleeve; it tests the opposite surprise sign "
            "as a separate replay scout."
        ),
        "exp-20260610-024": (
            "Rejected SEC earnings cadence surprise absorption. This run uses "
            "actual earnings snapshot surprise sign, not SEC Item 2.02 cadence."
        ),
        "exp-20260612-008": (
            "Rejected post-earnings event+1 exclusion due thin sample. This run "
            "does not change the accepted positive-surprise timing offsets."
        ),
    },
    "3_single_causal_variable": (
        "One fixed policy bundle: PIT earnings snapshot transition, latest "
        "surprise <= -3%, history count >=4, event-to-signal return and excess "
        "versus SPY >=0, existing liquid sector-known stock universe and OHLCV "
        "leadership/absorption gates, same-ticker core-overlap exclusion, top-1 "
        "next-open paper entry, 10-day hold, cost, cooldown, and concentration "
        "gates."
    ),
    "4_acceptance_standard": (
        "Use docs/backtesting.md three canonical windows. Treat as positive "
        "replay lead only if aggregate EV/PnL improve, no EV/PnL regression "
        "window appears, target sample >=20 across all 3 windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration guard passes, and accepted "
        "compression/distribution comparators are beaten. Production retention "
        "still requires a shared default-off helper."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260612_011_post_earnings_negative_surprise_absorption.py"
    ),
}

_EVENT_CACHE: dict[str, Any] | None = None


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _negative_surprise_events() -> dict[str, Any]:
    global _EVENT_CACHE
    if _EVENT_CACHE is not None:
        return _EVENT_CACHE

    earnings_index = pead.load_earnings_snapshot_index()
    events: list[dict[str, Any]] = []
    scan = Counter()
    examples: list[dict[str, Any]] = []
    for ticker, rows in sorted(earnings_index.items()):
        scan["tickers_with_earnings_rows"] += 1
        for pos in range(1, len(rows)):
            snap_date, info = rows[pos]
            prev_snap_date, prev_info = rows[pos - 1]
            scan["snapshot_transitions"] += 1
            if not pead._event_is_confirmed(prev_info, info, EVENT_CONFIG):
                continue
            scan["confirmed_earnings_events"] += 1
            surprise = pead._surprise_context(info)
            latest_surprise = pead._surprise_tail(info)
            if surprise is None or latest_surprise is None:
                scan["missing_surprise_context"] += 1
                continue
            if surprise["historical_surprise_count"] < MIN_SURPRISE_HISTORY_COUNT:
                scan["insufficient_surprise_history"] += 1
                continue
            if latest_surprise > MAX_LATEST_SURPRISE_PCT:
                scan["not_negative_surprise_event"] += 1
                continue
            days_to_next = pead._float_or_none(info.get("days_to_earnings"))
            if days_to_next is None:
                scan["missing_days_to_next_earnings"] += 1
                continue
            event = {
                "ticker": str(ticker).upper(),
                "event_confirmed_date": snap_date,
                "previous_snapshot_source_date": prev_snap_date,
                "earnings_snapshot_source_date": snap_date,
                "latest_surprise_pct": float(latest_surprise),
                "negative_surprise_abs_pct": abs(float(latest_surprise)),
                "avg_historical_surprise_pct": float(
                    surprise["avg_historical_surprise_pct"]
                ),
                "historical_surprise_count": int(
                    surprise["historical_surprise_count"]
                ),
                "positive_historical_surprise_count": int(
                    surprise["positive_historical_surprise_count"]
                ),
                "historical_surprise_pct": surprise["historical_surprise_pct"],
                "eps_actual_last": pead._float_or_none(info.get("eps_actual_last")),
                "days_to_next_earnings_after_event": days_to_next,
                "rule_version": RULE_VERSION,
            }
            events.append(event)
            scan["eligible_negative_surprise_events"] += 1
            if len(examples) < 12:
                examples.append(
                    {
                        "event_confirmed_date": snap_date,
                        "ticker": ticker,
                        "latest_surprise_pct": round(float(latest_surprise), 4),
                        "avg_historical_surprise_pct": round(
                            float(surprise["avg_historical_surprise_pct"]), 4
                        ),
                        "days_to_next_earnings_after_event": days_to_next,
                    }
                )

    by_date: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        by_date.setdefault(str(event["event_confirmed_date"]), []).append(event)
    _EVENT_CACHE = {
        "events": events,
        "by_date": by_date,
        "scan": dict(sorted(scan.items())),
        "examples": examples,
        "earnings_snapshot_dates_loaded": pead._earnings_date_count(earnings_index),
    }
    return _EVENT_CACHE


def _event_return_context(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    ticker: str,
    event_date: str,
    signal_date: str,
) -> dict[str, float] | None:
    rows = framework.shadow._series(snapshot, ticker)
    spy_rows = framework.shadow._series(snapshot, "SPY")
    idx = indices.get(ticker, {}).get(signal_date)
    event_idx = indices.get(ticker, {}).get(event_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    spy_event_idx = indices.get("SPY", {}).get(event_date)
    if None in {idx, event_idx, spy_idx, spy_event_idx}:
        return None
    if event_idx <= 0 or spy_event_idx <= 0:
        return None
    event_return = pead._close_return(rows, event_idx - 1, idx)
    spy_event_return = pead._close_return(spy_rows, spy_event_idx - 1, spy_idx)
    if event_return is None or spy_event_return is None:
        return None
    return {
        "event_to_signal_return": float(event_return),
        "spy_event_to_signal_return": float(spy_event_return),
        "event_to_signal_excess_vs_spy": float(event_return - spy_event_return),
    }


def _candidate_for_negative_absorption_event(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    event: dict[str, Any],
    offset: int,
    audit: Counter[str],
) -> dict[str, Any] | None:
    row = base._candidate_for_ticker(
        snapshot=snapshot,
        indices=indices,
        sector_entries=sector_entries,
        ticker=ticker,
        signal_date=signal_date,
        month_label="post_earnings_negative_surprise_absorption",
    )
    if row is None:
        return None

    event_context = _event_return_context(
        snapshot=snapshot,
        indices=indices,
        ticker=ticker,
        event_date=str(event["event_confirmed_date"]),
        signal_date=signal_date,
    )
    if event_context is None:
        audit["missing_event_to_signal_context"] += 1
        return None
    if event_context["event_to_signal_return"] < MIN_EVENT_TO_SIGNAL_RETURN:
        audit["negative_event_to_signal_return"] += 1
        return None
    if event_context["event_to_signal_excess_vs_spy"] < MIN_EVENT_TO_SIGNAL_EXCESS_VS_SPY:
        audit["negative_event_to_signal_excess_vs_spy"] += 1
        return None

    absorption_score = (
        float(row["candidate_score"])
        + float(event["negative_surprise_abs_pct"]) / 100.0
        + event_context["event_to_signal_excess_vs_spy"]
        + max(0.0, -float(event["avg_historical_surprise_pct"])) / 200.0
    )
    row.pop("candidate_month_label", None)
    row.update(
        {
            "source": "POST_EARNINGS_NEGATIVE_SURPRISE_ABSORPTION_PAPER",
            "rule_version": RULE_VERSION,
            "candidate_negative_absorption_score": round(absorption_score, 6),
            "event_confirmed_date": event["event_confirmed_date"],
            "earnings_snapshot_source_date": event["earnings_snapshot_source_date"],
            "previous_snapshot_source_date": event["previous_snapshot_source_date"],
            "recent_signal_trading_day_offset": offset,
            "latest_surprise_pct": round(float(event["latest_surprise_pct"]), 6),
            "negative_surprise_abs_pct": round(
                float(event["negative_surprise_abs_pct"]), 6
            ),
            "avg_historical_surprise_pct": round(
                float(event["avg_historical_surprise_pct"]), 6
            ),
            "historical_surprise_count": event["historical_surprise_count"],
            "positive_historical_surprise_count": event[
                "positive_historical_surprise_count"
            ],
            "eps_actual_last": event.get("eps_actual_last"),
            "days_to_next_earnings_after_event": event[
                "days_to_next_earnings_after_event"
            ],
            **{
                key: round(value, 6)
                for key, value in event_context.items()
            },
            "uses_free_earnings_snapshots": True,
            "uses_free_ohlcv": True,
            "uses_free_ohlcv_only": False,
            "known_at": "after_earnings_snapshot_transition_and_signal_date_close_before_next_open_paper_entry",
        }
    )
    return row


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = framework.shadow._baseline_entries(before_result)
    indices = {
        ticker: framework.shadow._row_index(framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    trading_dates = framework.shadow._trading_dates(snapshot)
    trading_pos = {date_value: idx for idx, date_value in enumerate(trading_dates)}
    wanted_dates = [
        date_value
        for date_value in trading_dates
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    wanted_set = set(wanted_dates)
    event_payload = _negative_surprise_events()
    candidates: list[dict[str, Any]] = []
    day_contexts: list[dict[str, Any]] = []
    scan = Counter(
        {
            "scanned_trading_days": len(wanted_dates),
            "total_negative_surprise_events": len(event_payload["events"]),
            "earnings_snapshot_dates_loaded": event_payload[
                "earnings_snapshot_dates_loaded"
            ],
        }
    )
    scan.update(
        {
            f"source_scan_{key}": value
            for key, value in event_payload["scan"].items()
            if isinstance(value, int)
        }
    )

    by_signal_date: dict[str, list[dict[str, Any]]] = {}
    for event in event_payload["events"]:
        ticker = str(event["ticker"])
        event_date = str(event["event_confirmed_date"])
        event_pos = trading_pos.get(event_date)
        if event_pos is None:
            scan["event_date_not_in_window_trading_calendar"] += 1
            continue
        admitted_event = False
        for offset in range(RECENT_SIGNAL_DAYS_MIN, RECENT_SIGNAL_DAYS_MAX + 1):
            signal_pos = event_pos + offset
            if signal_pos >= len(trading_dates):
                scan["signal_window_out_of_range"] += 1
                continue
            signal_date = trading_dates[signal_pos]
            if signal_date not in wanted_set:
                continue
            if ticker not in sector_entries:
                scan["missing_sector_entry"] += 1
                continue
            ab_entries = entries_by_date.get(signal_date, [])
            ab_tickers = {trade.get("ticker") for trade in ab_entries}
            if ticker in ab_tickers:
                scan["same_ticker_core_overlap_rejections"] += 1
                continue
            row = _candidate_for_negative_absorption_event(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                event=event,
                offset=offset,
                audit=scan,
            )
            if row is None:
                continue
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = False
            by_signal_date.setdefault(signal_date, []).append(row)
            admitted_event = True
            break
        if not admitted_event:
            scan["event_without_qualifying_absorption_signal"] += 1

    for signal_date, day_rows in sorted(by_signal_date.items()):
        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_negative_absorption_score"]),
                -float(row["candidate_score"]),
                -float(row["event_to_signal_excess_vs_spy"]),
                -float(row["candidate_ret20_excess_spy"]),
                -float(row["candidate_close_location"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                str(row.get("sector") or ""),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        scan["days_with_raw_negative_absorption_candidates"] += 1
        scan["raw_negative_absorption_candidates"] += len(day_rows)
        top = day_rows[0]
        day_contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(day_rows),
                "top_candidate": top["ticker"],
                "top_candidate_score": top["candidate_score"],
                "top_candidate_negative_absorption_score": top[
                    "candidate_negative_absorption_score"
                ],
                "top_candidate_latest_surprise_pct": top["latest_surprise_pct"],
                "top_candidate_event_to_signal_excess_vs_spy": top[
                    "event_to_signal_excess_vs_spy"
                ],
                "top_candidate_ret20_excess_spy": top["candidate_ret20_excess_spy"],
                "top_candidate_close_location": top["candidate_close_location"],
            }
        )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_negative_absorption_score"]),
            -float(row["candidate_score"]),
            -float(row["event_to_signal_excess_vs_spy"]),
            -float(row["candidate_ret20_excess_spy"]),
            -float(row["candidate_close_location"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            str(row.get("sector") or ""),
            row["ticker"],
        )
    )
    scan_payload = dict(sorted(scan.items()))
    scan_payload.update(
        {
            "rule_version": RULE_VERSION,
            "max_latest_surprise_pct": MAX_LATEST_SURPRISE_PCT,
            "min_surprise_history_count": MIN_SURPRISE_HISTORY_COUNT,
            "recent_signal_days_min": RECENT_SIGNAL_DAYS_MIN,
            "recent_signal_days_max": RECENT_SIGNAL_DAYS_MAX,
            "min_event_to_signal_return": MIN_EVENT_TO_SIGNAL_RETURN,
            "min_event_to_signal_excess_vs_spy": MIN_EVENT_TO_SIGNAL_EXCESS_VS_SPY,
            "source_event_examples": event_payload["examples"],
            "min_price": base.MIN_PRICE,
            "min_avg_dollar_volume_20d": base.MIN_AVG_DOLLAR_VOLUME_20D,
            "min_ret20_excess_spy": base.MIN_RET20_EXCESS_SPY,
            "min_ret60_excess_spy": base.MIN_RET60_EXCESS_SPY,
            "min_signal_return": base.MIN_SIGNAL_RETURN,
            "min_close_location": base.MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": base.MIN_VOLUME_RATIO_20D,
            "max_volume_ratio_20d": base.MAX_VOLUME_RATIO_20D,
            "min_ret5": base.MIN_RET5,
            "max_ret5": base.MAX_RET5,
            "max_ret20": base.MAX_RET20,
            "max_realized_vol_20d": base.MAX_REALIZED_VOL_20D,
        }
    )
    return candidates, day_contexts, scan_payload


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = BASE_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    if aggregate["expected_value_score_delta_sum"] <= ACCEPTED_COMPRESSION_COMPARATOR[
        "expected_value_score_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_compression_ev_not_beaten")
    if aggregate["total_pnl_delta_sum"] <= ACCEPTED_COMPRESSION_COMPARATOR[
        "total_pnl_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_compression_pnl_not_beaten")
    if aggregate["expected_value_score_delta_sum"] <= ACCEPTED_DISTRIBUTION_COMPARATOR[
        "expected_value_score_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_distribution_ev_not_beaten")
    if aggregate["total_pnl_delta_sum"] <= ACCEPTED_DISTRIBUTION_COMPARATOR[
        "total_pnl_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_distribution_pnl_not_beaten")
    gate["accepted_compression_comparator"] = ACCEPTED_COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = ACCEPTED_DISTRIBUTION_COMPARATOR
    gate["passed"] = not gate.get("failed_reasons")
    gate["decision"] = (
        "positive_replay_lead_not_promoted_post_earnings_negative_surprise_absorption"
        if gate["passed"]
        else "rejected_post_earnings_negative_surprise_absorption_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    for trades in payload["target_trades_by_window"].values():
        for trade in trades:
            trade.setdefault("target_price", trade.get("exit_price"))
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only PIT daily earnings snapshot transitions plus "
        "close-of-day OHLCV available on the signal date. Paper entry is next "
        "available open with existing entry slippage; exit is the close 10 "
        "trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    passed = bool(payload["gate4"]["passed"])
    aggregate = payload["delta_metrics"]["aggregate"]
    actual_success = 1 if passed else 0
    expected_probability = float(PREDICTION["success_probability"])
    failed_reasons = payload["gate4"].get("failed_reasons") or []
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "positive_replay_lead_not_promoted" if passed else "rejected",
            "decision": payload["gate4"]["decision"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "default_off_paper_candidate_pool_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_earnings_calendar_ohlcv_candidate_pool",
            "new_evidence_type": "pit_negative_earnings_surprise_absorption_field",
            "nearby_prior_experiments": [
                "exp-20260421-004",
                "exp-20260421-007",
                "exp-20260602-026",
                "exp-20260610-024",
                "exp-20260612-008",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "calibration": {
                "actual_decision": payload["gate4"]["decision"],
                "actual_success": actual_success,
                "predicted_success_probability": expected_probability,
                "brier_score": round((expected_probability - actual_success) ** 2, 6),
                "expected_ev_delta": PREDICTION["expected_ev_delta"],
                "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
                "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
                "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
                "predicted_failure_modes": PREDICTION["main_failure_modes"],
                "realized_failure_mode": None if passed else "; ".join(failed_reasons),
                "predicted_failure_mode_hit": (
                    False
                    if passed
                    else any(
                        token in "; ".join(failed_reasons)
                        for token in ("thin", "regression", "concentration", "pnl", "ev")
                    )
                ),
            },
            "production_impact": PRODUCTION_IMPACT,
            "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
            "accepted_distribution_comparator": ACCEPTED_DISTRIBUTION_COMPARATOR,
            "anti_js": "No JavaScript was used.",
            "parameters": {
                "paper_notional_usd": BASE_NOTIONAL_USD,
                "hold_days": HOLD_DAYS,
                "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
                "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
                "max_latest_surprise_pct": MAX_LATEST_SURPRISE_PCT,
                "min_surprise_history_count": MIN_SURPRISE_HISTORY_COUNT,
                "recent_signal_days_min": RECENT_SIGNAL_DAYS_MIN,
                "recent_signal_days_max": RECENT_SIGNAL_DAYS_MAX,
                "min_event_to_signal_return": MIN_EVENT_TO_SIGNAL_RETURN,
                "min_event_to_signal_excess_vs_spy": MIN_EVENT_TO_SIGNAL_EXCESS_VS_SPY,
                "min_price": base.MIN_PRICE,
                "min_avg_dollar_volume_20d": base.MIN_AVG_DOLLAR_VOLUME_20D,
                "min_ret20_excess_spy": base.MIN_RET20_EXCESS_SPY,
                "min_ret60_excess_spy": base.MIN_RET60_EXCESS_SPY,
                "min_signal_return": base.MIN_SIGNAL_RETURN,
                "min_close_location": base.MIN_CLOSE_LOCATION,
                "min_volume_ratio_20d": base.MIN_VOLUME_RATIO_20D,
                "max_volume_ratio_20d": base.MAX_VOLUME_RATIO_20D,
                "min_ret5": base.MIN_RET5,
                "max_ret5": base.MAX_RET5,
                "max_ret20": base.MAX_RET20,
                "max_realized_vol_20d": base.MAX_REALIZED_VOL_20D,
                "same_ticker_core_overlap_excluded": True,
                "single_causal_variable": CHANGED_VARIABLE,
            },
            "gate_questions": PRE_RUN_QUESTIONS,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "post_run_reflection": {
                "why_result_happened": (
                    "The fixed negative-surprise absorption source cleared the "
                    "canonical three-window gates and beat accepted comparators, "
                    "suggesting bad-news expectation reset plus price absorption "
                    "added replacement value. It remains only a replay lead "
                    "because no shared daily adapter or production parity path "
                    "was added."
                    if passed
                    else (
                        "The fixed negative-surprise absorption source failed "
                        "Gate 4. That means negative surprise plus post-event "
                        "price absorption did not create enough stable "
                        "replacement value after next-open execution, costs, "
                        "10-day hold, cooldown, overlap controls, and accepted "
                        "candidate-source comparator checks."
                    )
                ),
                "forbidden_near_neighbor_retry": (
                    "Do not retry by sweeping surprise threshold, event offset, "
                    "event-to-signal return/excess gates, ret20/ret60 relative "
                    "strength, signal-day return, close-location, volume-ratio "
                    "bounds, top-N, hold-day, cooldown, or paper notional on "
                    "the same frozen windows."
                ),
                "new_evidence_required": (
                    "A retry needs materially richer PIT expectation evidence "
                    "such as guidance direction, analyst revision trajectory, "
                    "option-implied move, or closed forward replacement-value "
                    "rows from a shared default-off earnings absorption adapter."
                ),
            },
            "negative_reflection": (
                "If rejected, the likely reason is that negative surprise "
                "remains genuine bad news even after short-term price absorption, "
                "or the post-event OHLCV gates mostly rediscover generic "
                "momentum with a thinner and noisier earnings sample."
            ),
        }
    )
    payload["interpretation"] = (
        "The negative-surprise absorption source passed as a replay-only lead, "
        "but no production surface changed and a shared default-off parity "
        "adapter is required before use."
        if passed
        else (
            "The negative-surprise absorption source was rejected; it did not "
            "establish a distinct free earnings-snapshot/OHLCV candidate-pool "
            "edge under the standard three-window protocol."
        )
    )
    payload["rejection_reason"] = None if passed else "; ".join(failed_reasons)
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Event count | Candidate days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {events} | {days} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                events=scan.get("total_negative_surprise_events", 0),
                days=scan.get("days_with_raw_negative_absorption_candidates", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Post-Earnings Negative-Surprise Absorption",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## History Check",
            "",
            json.dumps(PRE_RUN_QUESTIONS["2_history_check"], ensure_ascii=False, indent=2),
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target trades: `{}`".format(
                payload["target_trade_summary"]["total_trade_count"]
            ),
            "- Accepted compression comparator EV/PnL: `{}` / `${:,.2f}`".format(
                ACCEPTED_COMPRESSION_COMPARATOR["expected_value_score_delta_sum"],
                ACCEPTED_COMPRESSION_COMPARATOR["total_pnl_delta_sum"],
            ),
            "- Accepted distribution comparator EV/PnL: `{}` / `${:,.2f}`".format(
                ACCEPTED_DISTRIBUTION_COMPARATOR["expected_value_score_delta_sum"],
                ACCEPTED_DISTRIBUTION_COMPARATOR["total_pnl_delta_sum"],
            ),
            "- Gate 4 failures: `{}`".format(
                payload["gate4"].get("failed_reasons") or []
            ),
            "",
            "## Production Impact",
            "",
            json.dumps(PRODUCTION_IMPACT, indent=2, sort_keys=True),
            "",
            "## Reflection",
            "",
            json.dumps(payload["post_run_reflection"], indent=2, sort_keys=True),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate[
            "expected_value_score_delta_pct"
        ],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
        "accepted_distribution_comparator": ACCEPTED_DISTRIBUTION_COMPARATOR,
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_after": payload["after_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][
                    label
                ]["total_pnl"],
                "negative_surprise_event_count": payload["context_scan_by_window"][
                    label
                ].get("total_negative_surprise_events"),
                "raw_candidate_count": payload["context_scan_by_window"][label].get(
                    "raw_negative_absorption_candidates"
                ),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": {**payload["calibration"]},
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "negative_reflection": payload["negative_reflection"],
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket_and_registry(
    payload: dict[str, Any],
    log_record: dict[str, Any],
) -> None:
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record[
            "aggregate_strategy_total_pnl_delta"
        ],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record[
            "aggregate_strategy_total_pnl_delta"
        ],
    }
    try:
        previous.persist_self_registered_result(
            REGISTRY_JSON,
            experiment_id=EXPERIMENT_ID,
            lane="alpha_search",
            prediction=PREDICTION,
            result=result,
            status=payload["status"],
            fields=fields,
        )
    except PermissionError as exc:
        import experiment_registry

        original_save_ticket = experiment_registry.save_ticket
        original_save_registry = experiment_registry.save_registry

        def _save_ticket_without_atomic_replace(
            experiment: dict[str, Any],
            tickets_dir: Path,
        ) -> None:
            if experiment.get("experiment_id") != EXPERIMENT_ID:
                original_save_ticket(experiment, tickets_dir)
                return
            experiment = dict(experiment)
            experiment["registry_update_fallback"] = (
                "persist_self_registered_result failed on ticket atomic "
                f"replace: {type(exc).__name__}: {exc}"
            )
            framework._write_json(Path(tickets_dir) / f"{EXPERIMENT_ID}.json", experiment)

        def _save_registry_without_atomic_replace(
            registry: dict[str, Any],
            path: Path = REGISTRY_JSON,
        ) -> None:
            registry["updated_at"] = experiment_registry.utc_now_iso()
            persisted = {key: value for key, value in registry.items() if not key.startswith("_")}
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(persisted, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

        experiment_registry.save_ticket = _save_ticket_without_atomic_replace
        experiment_registry.save_registry = _save_registry_without_atomic_replace
        try:
            previous.persist_self_registered_result(
                REGISTRY_JSON,
                experiment_id=EXPERIMENT_ID,
                lane="alpha_search",
                prediction=PREDICTION,
                result=result,
                status=payload["status"],
                fields=fields,
            )
        finally:
            experiment_registry.save_ticket = original_save_ticket
            experiment_registry.save_registry = original_save_registry


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def _patch_framework() -> None:
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = RULE_VERSION
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.LOG_JSON = LOG_JSON
    framework.TICKET_JSON = TICKET_JSON
    framework.CARD_MD = CARD_MD
    framework.MANIFEST_JSON = MANIFEST_JSON
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.REGISTRY_JSON = REGISTRY_JSON
    framework.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.HOLD_DAYS = HOLD_DAYS
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    framework.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    framework.PREDICTION = PREDICTION
    framework.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._gate4 = _gate4
    framework._build_payload = _build_payload
    framework._build_card = _build_card
    framework._build_log_record = _build_log_record
    framework._update_ticket_and_registry = _update_ticket_and_registry
    framework._write_manifest = _write_manifest


_patch_framework()


def main() -> None:
    framework.main()


if __name__ == "__main__":
    main()
