"""exp-20260610-010: holiday-adjacent liquid leadership candidate pool.

Replay-only alpha search. This tests one candidate-source variable: liquid,
sector-known common-stock-like tickers on trading days immediately before or
after an exchange holiday closure, requiring 20-day SPY-relative leadership and
strong signal-day close quality before a top-1 next-open default-off paper entry
with a fixed 10-trading-day hold.

No production code, shared adapter, live/default orders, ranking, sizing, exits,
LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import exp_20260609_026_turn_of_month_liquid_leadership as base


framework = base.framework

EXPERIMENT_ID = "exp-20260610-010"
STEM = "holiday_adjacent_liquid_leadership"
TRIAL_FAMILY = "holiday_adjacent_liquid_leadership_candidate_pool"
TRIAL_VARIANT_ID = "holiday_adjacent_liquid_leadership_top1_next_open_10d_v1"
CHANGED_VARIABLE = "holiday_adjacent_liquid_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260610_010_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = base.BASE_NOTIONAL_USD
HOLD_DAYS = base.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = base.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = base.SAME_TICKER_COOLDOWN_DAYS

MIN_TARGET_TRADES = 12
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = base.MAX_DRAWDOWN_WORSE
MAX_SINGLE_POSITIVE_SHARE = base.MAX_SINGLE_POSITIVE_SHARE
MAX_POSITIVE_HHI = base.MAX_POSITIVE_HHI

ACCEPTED_COMPRESSION_COMPARATOR = base.ACCEPTED_COMPRESSION_COMPARATOR
ACCEPTED_TURN_OF_MONTH_REFERENCE = {
    "experiment_id": "exp-20260609-026",
    "decision": "positive_replay_lead_not_promoted_turn_of_month_liquid_leadership",
    "expected_value_score_delta_sum": 0.2774,
    "total_pnl_delta_sum": 5287.69,
    "target_trade_count": 73,
    "note": "Nearest accepted calendar-flow liquid leadership reference; not a hard gate because holiday-adjacent flow can be additive but must still remain replay-only until shared parity exists.",
}

BASE_GATE4 = base.BASE_GATE4
BASE_BUILD_PAYLOAD = base.BASE_BUILD_PAYLOAD

PREDICTION = {
    "success_probability": 0.12,
    "expected_ev_delta": 0.18,
    "expected_pnl_delta": 3000.0,
    "main_failure_modes": [
        "calendar_flow_already_priced",
        "thin_holiday_sample",
        "generic_momentum_relabel",
        "window_regression",
        "accepted_compression_comparator_not_beaten",
    ],
    "confidence_reason": (
        "No exact holiday-adjacent stock leadership prior was found, but nearby "
        "calendar-flow and macro-event tests often failed or were thin. The "
        "event surface is still point-in-time safe and production-replayable "
        "from free trading-calendar/OHLCV data if it survives Gate 4."
    ),
    "recorded_at": "2026-06-10T08:06:19+00:00",
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
        "require a shared default-off adapter that computes the same "
        "holiday-adjacent trading-day labels from the production trading "
        "calendar, sector-known liquid stock universe, SPY-relative leadership "
        "gates, close-quality gates, same-ticker core-overlap exclusion, "
        "next-open paper entry, 10-trading-day exit, costs, cooldown, accepted "
        "compression comparator, and concentration controls in both historical "
        "replay and daily production before any report queue, paper ledger, "
        "candidate priority, sizing, watchlist, or order surface could change."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "entry/candidate_pool: before or after exchange holiday closures, risk "
        "budgets and liquidity can be repositioned in a way that lets already "
        "liquid sector-known leaders continue after next-open entry. It uses "
        "only free trading-calendar inference from OHLCV and OHLCV features."
    ),
    "2_history_check": {
        "exact_prior": (
            "rg over docs/experiment_log.jsonl, experiments/logs, docs/experiments, "
            "and quant/experiments found no holiday-adjacent liquid leadership "
            "candidate pool. The only holiday hit was OPEX expiry-day handling."
        ),
        "nearby_calendar_trials": (
            "exp-20260609-026 turn-of-month liquid leadership passed as a "
            "replay lead/shared follow-up; exp-20260610-001 OPEX and "
            "exp-20260610-002 quarter-end pre-close were rejected. This test "
            "uses exchange-holiday adjacency instead of month/option/quarter "
            "calendar thresholds."
        ),
        "nearby_macro_trials": (
            "exp-20260606-017 was rejected for thin macro relief top-1 sample; "
            "exp-20260606-019 accepted macro relief top-2. This run does not "
            "use macro release calendars or ETF beta actions."
        ),
        "frozen_lanes_avoided": (
            "No LLM soft ranking, Form4 sparse retry, Companyfacts scalar "
            "mining, 52-week source extension, or state-surface notional/profile "
            "retune is involved."
        ),
    },
    "3_single_causal_variable": (
        "One fixed policy bundle: signal dates are only trading days directly "
        "before or after a non-standard market-closure gap, with the existing "
        "liquid sector-known leadership gates, same-ticker core-overlap "
        "exclusion, top-1 next-open paper entry, 10-day hold, cost, cooldown, "
        "and concentration gates."
    ),
    "4_acceptance_standard": (
        "Use docs/backtesting.md three canonical windows. Treat as a positive "
        "replay lead only if aggregate EV/PnL improve, no EV/PnL regression "
        "window appears, target sample >=12 across all 3 windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration guard passes, and the accepted "
        "exp-20260608-013 compression comparator is beaten. It is not accepted "
        "into production without a shared default-off helper."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260610_010_holiday_adjacent_liquid_leadership.py"
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _parse_iso_date(value: str) -> date:
    return date.fromisoformat(value)


def _normal_market_gap_days(left: date, right: date) -> int:
    if left.weekday() == 4 and right.weekday() == 0:
        return 3
    return 1


def _merge_label(existing: str | None, new_label: str) -> str:
    if existing is None or existing == new_label:
        return new_label
    return "post_and_pre_holiday"


def _holiday_adjacent_labels(dates: list[str]) -> dict[str, str]:
    ordered = sorted(dates)
    labels: dict[str, str] = {}
    for index in range(len(ordered) - 1):
        left_text = ordered[index]
        right_text = ordered[index + 1]
        left = _parse_iso_date(left_text)
        right = _parse_iso_date(right_text)
        gap_days = (right - left).days
        normal_gap_days = _normal_market_gap_days(left, right)
        if gap_days <= normal_gap_days:
            continue
        labels[left_text] = _merge_label(labels.get(left_text), "pre_holiday_close")
        labels[right_text] = _merge_label(labels.get(right_text), "post_holiday_open")
    return labels


def _candidate_for_holiday_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    holiday_label: str,
) -> dict[str, Any] | None:
    row = base._candidate_for_ticker(
        snapshot=snapshot,
        indices=indices,
        sector_entries=sector_entries,
        ticker=ticker,
        signal_date=signal_date,
        month_label=holiday_label,
    )
    if row is None:
        return None
    row["source"] = "HOLIDAY_ADJACENT_LIQUID_LEADERSHIP_PAPER"
    row["candidate_holiday_adjacent_label"] = holiday_label
    row.pop("candidate_month_label", None)
    row["rule_version"] = RULE_VERSION
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
    all_dates = framework.shadow._trading_dates(snapshot)
    holiday_labels = _holiday_adjacent_labels(all_dates)
    dates = [
        date_value
        for date_value in all_dates
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    candidates: list[dict[str, Any]] = []
    day_contexts: list[dict[str, Any]] = []
    holiday_label_distribution: dict[str, int] = {}
    scan = {
        "scanned_trading_days": len(dates),
        "holiday_adjacent_days": 0,
        "days_with_raw_holiday_adjacent_candidates": 0,
        "raw_holiday_adjacent_candidates": 0,
    }

    for signal_date in dates:
        holiday_label = holiday_labels.get(signal_date)
        if holiday_label is None:
            continue
        scan["holiday_adjacent_days"] += 1
        holiday_label_distribution[holiday_label] = (
            holiday_label_distribution.get(holiday_label, 0) + 1
        )
        day_rows: list[dict[str, Any]] = []
        for ticker in sorted(sector_entries):
            row = _candidate_for_holiday_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                holiday_label=holiday_label,
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
        scan["days_with_raw_holiday_adjacent_candidates"] += 1
        scan["raw_holiday_adjacent_candidates"] += len(day_rows)
        day_contexts.append(
            {
                "date": signal_date,
                "holiday_adjacent_label": holiday_label,
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
            "holiday_label_distribution": dict(
                sorted(holiday_label_distribution.items())
            ),
            "holiday_label_rule": (
                "A date qualifies only when the adjacent trading-date gap is "
                "larger than a normal weekday gap or larger than a normal "
                "Friday-to-Monday weekend gap. Normal weekends are excluded."
            ),
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
        gate.setdefault("failed_reasons", []).append(
            "accepted_compression_pnl_not_beaten"
        )
    gate["accepted_compression_comparator"] = ACCEPTED_COMPRESSION_COMPARATOR
    gate["accepted_turn_of_month_reference"] = ACCEPTED_TURN_OF_MONTH_REFERENCE
    gate["passed"] = not gate.get("failed_reasons")
    gate["decision"] = (
        "positive_replay_lead_not_promoted_holiday_adjacent_liquid_leadership"
        if gate["passed"]
        else "rejected_holiday_adjacent_liquid_leadership_candidate_pool"
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
            "change_type": "replay_only_candidate_pool_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "free_trading_calendar_plus_ohlcv_candidate_pool",
            "new_evidence_type": "free_ohlcv_inferred_exchange_holiday_adjacency",
            "nearby_prior_experiments": [
                "exp-20260609-026",
                "exp-20260610-001",
                "exp-20260610-002",
                "exp-20260606-017",
                "exp-20260606-019",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
            "accepted_turn_of_month_reference": ACCEPTED_TURN_OF_MONTH_REFERENCE,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that exchange-holiday "
                "adjacency is too thin or already priced, and the leadership "
                "selection collapses into generic liquid momentum after "
                "next-open execution, costs, cooldown, and same-ticker "
                "core-overlap exclusion. Do not answer by sweeping holiday "
                "pre/post labels, ret20/ret60 thresholds, close-location, "
                "volume bounds, top-N, hold-day, cooldown, or notional on "
                "these frozen windows without new evidence."
            ),
            "next_evidence_needed": (
                "A retry needs materially new point-in-time evidence that "
                "identifies real holiday-flow beneficiaries, such as known "
                "rebalance constituents, ETF flow/ownership pressure, or "
                "forward daily-snapshot replacement value. Pure holiday-window "
                "threshold retunes should stay frozen."
            ),
        }
    )
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "calendar_window": "trading_day_before_or_after_non_standard_market_closure_gap",
        "holiday_label_rule": (
            "Compare adjacent trading dates. A signal day is pre/post holiday "
            "only when the gap is larger than the normal one-day weekday gap "
            "or the normal Friday-to-Monday weekend gap."
        ),
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
    }
    payload["gate_questions"] = PRE_RUN_QUESTIONS
    payload["pre_run_questions"] = PRE_RUN_QUESTIONS
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The fixed holiday-adjacent liquid leadership bundle cleared the "
            "canonical three-window gates and beat the accepted compression "
            "comparator, suggesting exchange-holiday timing may add replacement "
            "value beyond generic OHLCV compression. It remains only a replay "
            "lead because no shared daily adapter or production parity path was "
            "added."
            if passed
            else (
                "The fixed holiday-adjacent liquid leadership bundle failed "
                "Gate 4. The result implies that exchange-holiday timing did "
                "not add enough distinct edge beyond liquid momentum after "
                "next-open execution, costs, cooldown, overlap controls, and "
                "the accepted comparator. The useful lesson is to seek a richer "
                "point-in-time flow beneficiary field, not more holiday-window "
                "threshold tuning."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping pre/post holiday inclusion, holiday gap "
            "definitions, ret20/ret60 relative-strength thresholds, signal-day "
            "return, close-location, volume-ratio bounds, top-N, hold-day, "
            "cooldown, or paper notional on these frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["interpretation"] = (
        "The holiday-adjacent liquid leadership source passed as a replay-only "
        "promotion lead, but no production surface changed and a shared "
        "default-off parity adapter is required before use."
        if passed
        else (
            "The holiday-adjacent liquid leadership source was rejected; it "
            "did not establish a distinct free-calendar/OHLCV candidate-pool "
            "edge under the standard three-window protocol."
        )
    )
    payload["rejection_reason"] = (
        None if passed else "; ".join(payload["gate4"]["failed_reasons"])
    )
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Holiday days | Candidate days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {holiday_days} | {days} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                holiday_days=scan.get("holiday_adjacent_days", 0),
                days=scan.get("days_with_raw_holiday_adjacent_candidates", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Holiday-Adjacent Liquid Leadership Candidate Pool",
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
            "- Compression comparator EV/PnL: `{}` / `${:,.2f}`".format(
                ACCEPTED_COMPRESSION_COMPARATOR["expected_value_score_delta_sum"],
                ACCEPTED_COMPRESSION_COMPARATOR["total_pnl_delta_sum"],
            ),
            "- Turn-of-month reference EV/PnL: `{}` / `${:,.2f}`".format(
                ACCEPTED_TURN_OF_MONTH_REFERENCE["expected_value_score_delta_sum"],
                ACCEPTED_TURN_OF_MONTH_REFERENCE["total_pnl_delta_sum"],
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
        "mechanism_family": "free_trading_calendar_plus_ohlcv_candidate_pool",
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
        "accepted_turn_of_month_reference": ACCEPTED_TURN_OF_MONTH_REFERENCE,
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
                "holiday_adjacent_day_count": payload["context_scan_by_window"][
                    label
                ].get("holiday_adjacent_days"),
                "raw_candidate_count": payload["context_scan_by_window"][label].get(
                    "raw_holiday_adjacent_candidates"
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
