"""exp-20260609-026: turn-of-month liquid leadership candidate pool.

Replay-only alpha search. This tests one candidate-source variable: liquid,
sector-known common-stock-like tickers during the last trading day through the
first three trading days of a month, requiring 20-day SPY-relative leadership
and strong signal-day close quality before a top-1 next-open default-off paper
entry with a fixed 10-trading-day hold.

No production code, shared adapter, live/default orders, ranking, sizing, exits,
LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import exp_20260609_008_low_turnover_rs_consolidation as previous


framework = previous.framework

EXPERIMENT_ID = "exp-20260609-026"
STEM = "turn_of_month_liquid_leadership"
TRIAL_FAMILY = "turn_of_month_liquid_leadership_candidate_pool"
TRIAL_VARIANT_ID = "turn_of_month_liquid_leadership_top1_next_open_10d_v1"
CHANGED_VARIABLE = "turn_of_month_liquid_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = previous.REPO_ROOT
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260609_026_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 10

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 75_000_000.0
MIN_RET20_EXCESS_SPY = 0.025
MIN_RET60_EXCESS_SPY = 0.000
MIN_SIGNAL_RETURN = 0.002
MIN_CLOSE_LOCATION = 0.70
MIN_VOLUME_RATIO_20D = 0.80
MAX_VOLUME_RATIO_20D = 3.00
MIN_RET5 = -0.020
MAX_RET5 = 0.080
MAX_RET20 = 0.300
MAX_REALIZED_VOL_20D = 0.080

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

EXCLUDED_TICKERS = previous.EXCLUDED_TICKERS

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "generic_momentum_not_calendar_edge",
        "window_regression",
        "drawdown_drift_too_high",
        "accepted_compression_comparator_not_beaten",
        "thin_month_turn_sample",
    ],
    "confidence_reason": (
        "The signal is point-in-time safe and free-data executable, but nearby "
        "macro rebalance, scheduled-event, and price-formation candidate pools "
        "often failed after costs. This tests a distinct fixed calendar-flow "
        "hypothesis rather than LLM soft ranking, Form4, or Companyfacts mining."
    ),
    "recorded_at": "2026-06-09T21:30:00+00:00",
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
    "parity_note": (
        "This experiment changes no production code. A positive result would "
        "require a shared default-off adapter that computes the same trading-day "
        "month labels, sector-known liquid stock universe, SPY-relative "
        "leadership gates, close-quality gates, same-ticker core-overlap "
        "exclusion, next-open paper entry, 10-trading-day exit, costs, cooldown, "
        "accepted compression comparator, and concentration controls in both "
        "historical replay and daily production before any report queue, paper "
        "ledger, candidate priority, sizing, watchlist, or order surface could change."
    ),
}

BASE_GATE4 = previous.BASE_GATE4
BASE_BUILD_PAYLOAD = previous.BASE_BUILD_PAYLOAD

ACCEPTED_COMPRESSION_COMPARATOR = {
    "experiment_id": "exp-20260608-013",
    "decision": "accepted_narrow_range_compression_breakout_shared_default_off_adapter",
    "expected_value_score_delta_sum": 0.1608,
    "total_pnl_delta_sum": 2248.98,
    "target_trade_count": 44,
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "entry/candidate_pool: turn-of-month institutional contribution and "
        "rebalance flow should make liquid sector-known stocks that already "
        "show 20-day SPY-relative leadership and a high signal-day close "
        "continue after next-open entry. It uses only free calendar and OHLCV data."
    ),
    "2_history_check": {
        "nearby_macro_rebalance_trials": (
            "exp-20260605-027, exp-20260605-030, and exp-20260605-032 tested "
            "macro/rates or scheduled-event timing and failed/thinned in nearby "
            "ways, but they were not fixed turn-of-month liquid stock leadership pools."
        ),
        "accepted_neighbors": (
            "exp-20260606-020 macro relief, exp-20260607-019 volatility relief, "
            "and exp-20260608-013 compression show production-visible free-data "
            "adapters can work, but this run must beat the accepted compression "
            "stock-candidate comparator before promotion pressure."
        ),
        "frozen_lanes_avoided": (
            "No LLM soft ranking, Form4 retry, Companyfacts scalar mining, or "
            "state-surface notional/profile retune is involved."
        ),
    },
    "3_single_causal_variable": (
        "One fixed policy bundle: last trading day through first three trading "
        "days of each month, liquid sector-known stock universe, 20d SPY-relative "
        "leadership, strong signal-day close/volume quality, same-ticker core "
        "overlap exclusion, top-1 next-open paper entry, 10-day hold, cost, "
        "cooldown, and concentration gates."
    ),
    "4_acceptance_standard": (
        "Use docs/backtesting.md three canonical windows. Accept only as a "
        "promotion lead if aggregate EV/PnL improve, no EV/PnL regression "
        "window appears, target sample >=20 across all 3 windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration guard passes, and the accepted "
        "exp-20260608-013 compression comparator is beaten."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260609_026_turn_of_month_liquid_leadership.py"
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _turn_of_month_labels(dates: list[str]) -> dict[str, str]:
    by_month: dict[str, list[str]] = {}
    for date_value in dates:
        by_month.setdefault(date_value[:7], []).append(date_value)

    labels: dict[str, str] = {}
    for month_dates in by_month.values():
        ordered = sorted(month_dates)
        if not ordered:
            continue
        labels[ordered[-1]] = "last_trading_day"
        for index, date_value in enumerate(ordered[:3], start=1):
            labels[date_value] = f"first_trading_day_{index}"
    return labels


def _return_between(rows: list[dict[str, Any]], start_idx: int, end_idx: int) -> float | None:
    if start_idx < 0 or end_idx < 0 or start_idx >= len(rows) or end_idx >= len(rows):
        return None
    start = framework._value(rows[start_idx], "Close")
    end = framework._value(rows[end_idx], "Close")
    if start is None or end is None or start <= 0:
        return None
    return (end / start) - 1.0


def _candidate_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    month_label: str,
) -> dict[str, Any] | None:
    if ticker in EXCLUDED_TICKERS:
        return None
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None:
        return None
    if idx < 65 or spy_idx < 65:
        return None

    close = framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None

    signal_return = framework._daily_return(rows, idx)
    ret5 = _return_between(rows, idx - 5, idx)
    ret20 = _return_between(rows, idx - 20, idx)
    ret60 = _return_between(rows, idx - 60, idx)
    spy_ret20 = _return_between(spy_rows, spy_idx - 20, spy_idx)
    spy_ret60 = _return_between(spy_rows, spy_idx - 60, spy_idx)
    close_location = framework._close_location(rows[idx])
    volume_ratio = framework._volume_ratio(rows, idx)
    realized_vol20 = framework._realized_vol(rows, idx)
    if None in (
        signal_return,
        ret5,
        ret20,
        ret60,
        spy_ret20,
        spy_ret60,
        close_location,
        volume_ratio,
        realized_vol20,
    ):
        return None

    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    if signal_return < MIN_SIGNAL_RETURN:
        return None
    if ret5 < MIN_RET5 or ret5 > MAX_RET5:
        return None
    if ret20 > MAX_RET20 or ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_RET60_EXCESS_SPY:
        return None
    if close_location < MIN_CLOSE_LOCATION:
        return None
    if volume_ratio < MIN_VOLUME_RATIO_20D or volume_ratio > MAX_VOLUME_RATIO_20D:
        return None
    if realized_vol20 > MAX_REALIZED_VOL_20D:
        return None

    log_liquidity = math.log10(max(adv20, 1.0)) - 7.0
    stability_bonus = max(0.0, 1.0 - abs(ret5) / MAX_RET5)
    score = (
        1.35 * ret20_excess_spy
        + 0.55 * ret60_excess_spy
        + 0.50 * signal_return
        + 0.40 * close_location
        + 0.08 * log_liquidity
        + 0.15 * stability_bonus
    )
    sector_meta = sector_entries.get(ticker, {})
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "TURN_OF_MONTH_LIQUID_LEADERSHIP_PAPER",
        "candidate_score": round(score, 6),
        "candidate_month_label": month_label,
        "candidate_signal_day_return": round(signal_return, 6),
        "candidate_ret5": round(ret5, 6),
        "candidate_ret20": round(ret20, 6),
        "candidate_ret60": round(ret60, 6),
        "candidate_spy_ret20": round(spy_ret20, 6),
        "candidate_spy_ret60": round(spy_ret60, 6),
        "candidate_ret20_excess_spy": round(ret20_excess_spy, 6),
        "candidate_ret60_excess_spy": round(ret60_excess_spy, 6),
        "candidate_close_location": round(close_location, 6),
        "candidate_avg_dollar_volume_20d": round(adv20, 2),
        "candidate_volume_ratio_20d": round(volume_ratio, 6),
        "candidate_realized_vol_20d": round(realized_vol20, 6),
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "sector_coverage_status": sector_meta.get("sector_coverage_status"),
        "rule_version": RULE_VERSION,
        "uses_free_ohlcv_only": True,
        "uses_llm": False,
        "trade_enabled": False,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }


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
    all_dates = framework.shadow._trading_dates(snapshot)
    turn_labels = _turn_of_month_labels(all_dates)
    dates = [
        date_value
        for date_value in all_dates
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    candidates: list[dict[str, Any]] = []
    day_contexts: list[dict[str, Any]] = []
    month_label_distribution: dict[str, int] = {}
    scan = {
        "scanned_trading_days": len(dates),
        "turn_of_month_days": 0,
        "days_with_raw_turn_of_month_candidates": 0,
        "raw_turn_of_month_candidates": 0,
    }

    for signal_date in dates:
        month_label = turn_labels.get(signal_date)
        if month_label is None:
            continue
        scan["turn_of_month_days"] += 1
        month_label_distribution[month_label] = month_label_distribution.get(month_label, 0) + 1
        day_rows: list[dict[str, Any]] = []
        for ticker in sorted(sector_entries):
            row = _candidate_for_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                month_label=month_label,
            )
            if row is None:
                continue
            ab_entries = entries_by_date.get(signal_date, [])
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = any(
                trade.get("ticker") == ticker for trade in ab_entries
            )
            day_rows.append(row)
        if not day_rows:
            continue
        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_score"]),
                -float(row["candidate_ret20_excess_spy"]),
                -float(row["candidate_close_location"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                str(row.get("sector") or ""),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        scan["days_with_raw_turn_of_month_candidates"] += 1
        scan["raw_turn_of_month_candidates"] += len(day_rows)
        day_contexts.append(
            {
                "date": signal_date,
                "month_label": month_label,
                "raw_candidate_count": len(day_rows),
                "top_candidate": day_rows[0]["ticker"],
                "top_candidate_score": day_rows[0]["candidate_score"],
                "top_candidate_ret20_excess_spy": day_rows[0][
                    "candidate_ret20_excess_spy"
                ],
                "top_candidate_close_location": day_rows[0][
                    "candidate_close_location"
                ],
            }
        )
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["candidate_ret20_excess_spy"]),
            -float(row["candidate_close_location"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            str(row.get("sector") or ""),
            row["ticker"],
        )
    )
    scan.update(
        {
            "rule_version": RULE_VERSION,
            "month_label_distribution": dict(sorted(month_label_distribution.items())),
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "max_volume_ratio_20d": MAX_VOLUME_RATIO_20D,
            "min_ret5": MIN_RET5,
            "max_ret5": MAX_RET5,
            "max_ret20": MAX_RET20,
            "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
        }
    )
    return candidates, day_contexts, scan


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
    gate["accepted_compression_comparator"] = ACCEPTED_COMPRESSION_COMPARATOR
    gate["passed"] = not gate.get("failed_reasons")
    gate["decision"] = (
        "positive_replay_lead_not_promoted_turn_of_month_liquid_leadership"
        if gate["passed"]
        else "rejected_turn_of_month_liquid_leadership_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    passed = bool(payload["gate4"]["passed"])
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "positive_replay_lead_not_promoted" if passed else "rejected",
            "decision": payload["gate4"]["decision"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_calendar_ohlcv_candidate_pool",
            "new_evidence_type": (
                "production_visible_free_calendar_turn_of_month_liquid_leadership_field"
            ),
            "nearby_prior_experiments": [
                "exp-20260605-027",
                "exp-20260605-030",
                "exp-20260605-032",
                "exp-20260606-020",
                "exp-20260607-019",
                "exp-20260608-013",
            ],
            "prior_trial_count": 6,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that fixed turn-of-month "
                "liquid leadership is generic momentum or crowded rebalance "
                "flow rather than a distinct replacement-value candidate pool "
                "after next-open execution, costs, cooldown, and same-ticker "
                "core-overlap exclusion. Do not answer by sweeping calendar "
                "day count, ret20/ret60 thresholds, close-location, volume "
                "bounds, top-N, hold-day, cooldown, or notional on these "
                "frozen windows without new evidence."
            ),
            "next_evidence_needed": (
                "A retry needs materially new evidence that identifies real "
                "month-flow beneficiaries, such as point-in-time ETF rebalance "
                "constituent deltas, ownership/flow proxies, or forward "
                "daily-snapshot replacement value. Pure threshold retunes stay frozen."
            ),
        }
    )
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "calendar_window": "last_trading_day_through_first_three_trading_days",
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
        "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
        "min_signal_return": MIN_SIGNAL_RETURN,
        "min_close_location": MIN_CLOSE_LOCATION,
        "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
        "max_volume_ratio_20d": MAX_VOLUME_RATIO_20D,
        "min_ret5": MIN_RET5,
        "max_ret5": MAX_RET5,
        "max_ret20": MAX_RET20,
        "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
        "same_ticker_core_overlap_excluded": True,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["gate_questions"] = PRE_RUN_QUESTIONS
    payload["pre_run_questions"] = PRE_RUN_QUESTIONS
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The fixed turn-of-month liquid leadership bundle cleared the "
            "canonical three-window gates and beat the accepted compression "
            "comparator, suggesting the calendar-flow timing contributed "
            "replacement value beyond generic OHLCV compression. It remains "
            "only a replay lead because no shared daily adapter or production "
            "parity path was added."
            if passed
            else (
                "The fixed turn-of-month liquid leadership bundle failed Gate 4. "
                "The result implies calendar timing did not add enough distinct "
                "edge beyond liquid momentum after next-open execution, costs, "
                "cooldown, and overlap/concentration controls. The useful lesson "
                "is to seek a richer point-in-time flow beneficiary field, not "
                "more turn-window threshold tuning."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping month-start/end day counts, ret20/ret60 "
            "relative-strength thresholds, signal-day return, close-location, "
            "volume-ratio bounds, top-N, hold-day, cooldown, or paper notional "
            "on the same frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["interpretation"] = (
        "The turn-of-month liquid leadership source passed as a replay-only "
        "promotion lead, but no production surface changed and a shared "
        "default-off parity adapter is required before use."
        if passed
        else (
            "The turn-of-month liquid leadership source was rejected; it did "
            "not establish a distinct free-calendar/OHLCV candidate-pool edge "
            "under the standard three-window protocol."
        )
    )
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Turn days | Candidate days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {turn_days} | {days} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                turn_days=scan.get("turn_of_month_days", 0),
                days=scan.get("days_with_raw_turn_of_month_candidates", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Turn-of-Month Liquid Leadership Candidate Pool",
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
            "- Comparator EV/PnL: `{}` / `${:,.2f}`".format(
                ACCEPTED_COMPRESSION_COMPARATOR["expected_value_score_delta_sum"],
                ACCEPTED_COMPRESSION_COMPARATOR["total_pnl_delta_sum"],
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Production Impact",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
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
        "mechanism_family": "production_visible_free_calendar_ohlcv_candidate_pool",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/experiments/exp-20260602-003/"
            "exp_20260602_003_post_earnings_explicit_continuation.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate[
            "expected_value_score_delta_pct"
        ],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
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
                "turn_of_month_day_count": payload["context_scan_by_window"][
                    label
                ].get("turn_of_month_days"),
                "raw_candidate_count": payload["context_scan_by_window"][label].get(
                    "raw_turn_of_month_candidates"
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
    aggregate = payload["delta_metrics"]["aggregate"]
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
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
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )


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
