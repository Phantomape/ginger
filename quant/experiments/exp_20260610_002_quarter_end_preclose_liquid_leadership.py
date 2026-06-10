"""exp-20260610-002: quarter-end pre-close liquid leadership.

Replay-only alpha search. This tests one candidate-source variable: liquid,
sector-known common-stock-like tickers during the four trading days before a
calendar quarter's final trading day, using the accepted turn-of-month liquid
leadership gates held fixed before a top-1 next-open paper entry with a fixed
10-trading-day hold.

No production code, shared adapter, live/default orders, ranking, sizing, exits,
LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import exp_20260609_026_turn_of_month_liquid_leadership as base


framework = base.framework

EXPERIMENT_ID = "exp-20260610-002"
STEM = "quarter_end_preclose_liquid_leadership"
TRIAL_FAMILY = "quarter_end_preclose_liquid_leadership_candidate_pool"
TRIAL_VARIANT_ID = "quarter_end_preclose_liquid_leadership_top1_next_open_10d_v1"
CHANGED_VARIABLE = "quarter_end_preclose_liquid_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260610_002_{STEM}.json"
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

MIN_TARGET_TRADES = base.MIN_TARGET_TRADES
MIN_TARGET_WINDOWS = base.MIN_TARGET_WINDOWS
MAX_DRAWDOWN_WORSE = base.MAX_DRAWDOWN_WORSE
MAX_SINGLE_POSITIVE_SHARE = base.MAX_SINGLE_POSITIVE_SHARE
MAX_POSITIVE_HHI = base.MAX_POSITIVE_HHI

BASE_GATE4 = base.BASE_GATE4
BASE_BUILD_PAYLOAD = base.BASE_BUILD_PAYLOAD

ACCEPTED_COMPRESSION_COMPARATOR = base.ACCEPTED_COMPRESSION_COMPARATOR
ACCEPTED_TURN_OF_MONTH_COMPARATOR = {
    "experiment_id": "exp-20260609-027",
    "decision": "accepted_turn_of_month_liquid_leadership_shared_default_off_adapter",
    "expected_value_score_delta_sum": 0.2774,
    "total_pnl_delta_sum": 5287.69,
    "target_trade_count": 73,
}

PREDICTION = {
    "success_probability": 0.14,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "generic_momentum_not_quarter_end_edge",
        "window_regression",
        "drawdown_drift_too_high",
        "accepted_turn_of_month_comparator_not_beaten",
        "thin_quarter_sample",
    ],
    "confidence_reason": (
        "Turn-of-month calendar flow worked, OPEX failed, and quarter-end "
        "window dressing is a distinct PIT calendar mechanism; risk is that "
        "it is generic liquid momentum or too sparse."
    ),
    "recorded_at": "2026-06-10T01:04:46+00:00",
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
        "quarter-end pre-close trading-day labels, sector-known liquid stock "
        "universe, SPY-relative leadership gates, close-quality gates, "
        "same-ticker core-overlap exclusion, next-open paper entry, "
        "10-trading-day exit, costs, cooldown, accepted calendar/compression "
        "comparators, and concentration controls in both historical replay and "
        "daily production before any report queue, paper ledger, candidate "
        "priority, sizing, watchlist, or order surface could change."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "entry/candidate_pool: quarter-end pre-close window-dressing and "
        "institutional rebalance flow may make liquid sector-known stocks that "
        "already show SPY-relative leadership and high close quality continue "
        "after next-open entry. It uses only free calendar and OHLCV data."
    ),
    "2_history_check": {
        "no_exact_prior_found": (
            "Search found turn-of-month, OPEX-week, official macro-event, and "
            "price-formation candidate-pool experiments, but no exact "
            "quarter-end pre-close liquid leadership source."
        ),
        "nearby_calendar_trials": (
            "exp-20260609-027 accepted turn-of-month liquid leadership. "
            "exp-20260610-001 rejected OPEX-week liquid leadership. This run "
            "excludes the final quarter trading day so it does not simply reuse "
            "the accepted month-end route."
        ),
        "accepted_comparators": (
            "This run must beat accepted compression exp-20260608-013 and the "
            "closest accepted calendar comparator exp-20260609-027 before any "
            "promotion pressure."
        ),
        "frozen_lanes_avoided": (
            "No LLM soft ranking, revision proxy, Form4 sparse retry, "
            "Companyfacts scalar mining, state-surface notional/profile retune, "
            "OPEX retune, or turn-of-month threshold sweep is involved."
        ),
    },
    "3_single_causal_variable": (
        "One fixed policy bundle: the four trading days immediately before the "
        "final trading day of March, June, September, and December; liquid "
        "sector-known stock universe; accepted turn-of-month leadership gates "
        "held fixed; same-ticker core-overlap exclusion; top-1 next-open paper "
        "entry; 10-day hold; cost; cooldown; and concentration gates."
    ),
    "4_acceptance_standard": (
        "Use docs/backtesting.md three canonical windows. Accept only as a "
        "promotion lead if aggregate EV/PnL improve, no EV/PnL regression "
        "window appears, target sample >=20 across all 3 windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration guard passes, and accepted "
        "compression plus turn-of-month comparators are beaten."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260610_002_quarter_end_preclose_liquid_leadership.py"
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _quarter_end_preclose_labels(dates: list[str]) -> dict[str, str]:
    by_month: dict[str, list[str]] = {}
    for date_value in dates:
        by_month.setdefault(date_value[:7], []).append(date_value)

    labels: dict[str, str] = {}
    for month_key, month_dates in by_month.items():
        year, month = (int(part) for part in month_key.split("-"))
        if month not in {3, 6, 9, 12}:
            continue
        ordered = sorted(month_dates)
        if len(ordered) < 5:
            continue
        quarter_end_index = len(ordered) - 1
        start_index = max(0, quarter_end_index - 4)
        for idx in range(start_index, quarter_end_index):
            distance = quarter_end_index - idx
            labels[ordered[idx]] = f"quarter_end_minus_{distance}"
    return labels


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
    quarter_labels = _quarter_end_preclose_labels(all_dates)
    dates = [
        date_value
        for date_value in all_dates
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    candidates: list[dict[str, Any]] = []
    day_contexts: list[dict[str, Any]] = []
    label_distribution: dict[str, int] = {}
    scan = {
        "scanned_trading_days": len(dates),
        "quarter_end_preclose_days": 0,
        "days_with_raw_quarter_end_candidates": 0,
        "raw_quarter_end_candidates": 0,
    }

    for signal_date in dates:
        quarter_label = quarter_labels.get(signal_date)
        if quarter_label is None:
            continue
        scan["quarter_end_preclose_days"] += 1
        label_distribution[quarter_label] = label_distribution.get(quarter_label, 0) + 1
        day_rows: list[dict[str, Any]] = []
        for ticker in sorted(sector_entries):
            row = base._candidate_for_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                month_label=quarter_label,
            )
            if row is None:
                continue
            row["source"] = "QUARTER_END_PRECLOSE_LIQUID_LEADERSHIP_PAPER"
            row["candidate_quarter_end_label"] = row.pop(
                "candidate_month_label",
                quarter_label,
            )
            row["rule_version"] = RULE_VERSION
            row["known_at"] = "after_signal_day_close_before_next_open_paper_entry"
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
        scan["days_with_raw_quarter_end_candidates"] += 1
        scan["raw_quarter_end_candidates"] += len(day_rows)
        day_contexts.append(
            {
                "date": signal_date,
                "quarter_end_label": quarter_label,
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
            "quarter_end_label_distribution": dict(sorted(label_distribution.items())),
            "calendar_window": "four_trading_days_before_calendar_quarter_final_trading_day",
            "quarter_end_months": [3, 6, 9, 12],
            "quarter_final_trading_day_excluded": True,
            "leadership_gate_source": "exp-20260609-027 thresholds held fixed",
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
    if aggregate["expected_value_score_delta_sum"] <= ACCEPTED_TURN_OF_MONTH_COMPARATOR[
        "expected_value_score_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_turn_of_month_ev_not_beaten")
    if aggregate["total_pnl_delta_sum"] <= ACCEPTED_TURN_OF_MONTH_COMPARATOR[
        "total_pnl_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_turn_of_month_pnl_not_beaten")
    gate["accepted_comparators"] = {
        "compression": ACCEPTED_COMPRESSION_COMPARATOR,
        "turn_of_month": ACCEPTED_TURN_OF_MONTH_COMPARATOR,
    }
    gate["passed"] = not gate.get("failed_reasons")
    gate["decision"] = (
        "positive_replay_lead_not_promoted_quarter_end_preclose_liquid_leadership"
        if gate["passed"]
        else "rejected_quarter_end_preclose_liquid_leadership_candidate_pool"
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
                "production_visible_free_calendar_quarter_end_preclose_field"
            ),
            "nearby_prior_experiments": [
                "exp-20260609-027",
                "exp-20260610-001",
                "exp-20260608-013",
                "exp-20260606-020",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "minimal",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_comparators": {
                "compression": ACCEPTED_COMPRESSION_COMPARATOR,
                "turn_of_month": ACCEPTED_TURN_OF_MONTH_COMPARATOR,
            },
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that quarter-end pre-close "
                "leadership is generic liquid momentum or short-lived window-"
                "dressing that reverses after next-open execution, costs, "
                "cooldown, and same-ticker core-overlap exclusion. Do not "
                "answer by sweeping quarter-day count, ret20/ret60 thresholds, "
                "close-location, volume bounds, top-N, hold-day, cooldown, or "
                "notional on these frozen windows."
            ),
            "next_evidence_needed": (
                "A retry needs materially new PIT evidence that identifies real "
                "quarter-end flow beneficiaries, such as index rebalance rows, "
                "fund-flow/ownership changes, ETF constituent flow proxies, or "
                "closed forward daily-snapshot replacement value. Pure calendar "
                "or OHLCV threshold retunes stay frozen."
            ),
        }
    )
    payload["parameters"] = {
        **payload.get("parameters", {}),
        "calendar_window": "four_trading_days_before_quarter_final_trading_day",
        "quarter_months": [3, 6, 9, 12],
        "quarter_final_trading_day_excluded": True,
        "leadership_gate_source": "exp-20260609-027 fixed liquid leadership gates",
        "same_ticker_core_overlap_excluded": True,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["gate_questions"] = PRE_RUN_QUESTIONS
    payload["pre_run_questions"] = PRE_RUN_QUESTIONS
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The quarter-end pre-close liquid leadership bundle cleared the "
            "canonical three-window gates and beat the accepted calendar/"
            "compression comparators, suggesting pre-quarter-end flow added "
            "replacement value beyond generic liquid momentum. It remains only "
            "a replay lead because no shared daily adapter or production parity "
            "path was added."
            if passed
            else (
                "The quarter-end pre-close liquid leadership bundle failed "
                "Gate 4. The result implies quarter-end pre-close timing did "
                "not add enough distinct edge beyond liquid momentum and the "
                "accepted turn-of-month route after next-open execution, costs, "
                "cooldown, overlap, and concentration controls."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping quarter-end day count, quarter-start "
            "labels, ret20/ret60 relative-strength thresholds, signal-day "
            "return, close-location, volume-ratio bounds, top-N, hold-day, "
            "cooldown, or paper notional on the same frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["interpretation"] = (
        "The quarter-end pre-close liquid leadership source passed as a "
        "replay-only promotion lead, but no production surface changed and a "
        "shared default-off parity adapter is required before use."
        if passed
        else (
            "The quarter-end pre-close liquid leadership source was rejected; "
            "it did not establish a distinct free-calendar/OHLCV candidate-pool "
            "edge under the standard three-window protocol and accepted-"
            "comparator checks."
        )
    )
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Quarter days | Candidate days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {quarter_days} | {days} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                quarter_days=scan.get("quarter_end_preclose_days", 0),
                days=scan.get("days_with_raw_quarter_end_candidates", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Quarter-End Pre-Close Liquid Leadership",
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
            "- Turn-of-month comparator EV/PnL: `{}` / `${:,.2f}`".format(
                ACCEPTED_TURN_OF_MONTH_COMPARATOR["expected_value_score_delta_sum"],
                ACCEPTED_TURN_OF_MONTH_COMPARATOR["total_pnl_delta_sum"],
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
        "accepted_alpha": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
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
        "accepted_comparators": payload["accepted_comparators"],
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
                "quarter_end_preclose_day_count": payload["context_scan_by_window"][
                    label
                ].get("quarter_end_preclose_days"),
                "raw_candidate_count": payload["context_scan_by_window"][label].get(
                    "raw_quarter_end_candidates"
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
        "accepted_alpha": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
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
