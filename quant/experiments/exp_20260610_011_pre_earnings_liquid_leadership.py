"""exp-20260610-011: pre-earnings liquid leadership candidate pool.

Replay-only alpha search. This tests one candidate-source variable: liquid,
sector-known common-stock-like tickers with point-in-time earnings snapshot
days_to_earnings in the 6-12 calendar-day pre-event window, positive historical
surprise, and existing SPY-relative leadership. Paper entry is next available
open, with a fixed five-trading-day hold.

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

EXPERIMENT_ID = "exp-20260610-011"
STEM = "pre_earnings_liquid_leadership"
TRIAL_FAMILY = "pre_earnings_liquid_leadership_candidate_pool"
TRIAL_VARIANT_ID = "pre_earnings_liquid_leadership_top1_next_open_5d_v1"
CHANGED_VARIABLE = "pre_earnings_liquid_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260610_011_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EARNINGS_DIR = REPO_ROOT / "data" / "daily" / "snapshots" / "earnings"

BASE_NOTIONAL_USD = base.BASE_NOTIONAL_USD
HOLD_DAYS = 5
MAX_PAPER_TRADES_PER_DAY = base.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = 10

MIN_DAYS_TO_EARNINGS = 6
MAX_DAYS_TO_EARNINGS = 12
MIN_AVG_HISTORICAL_SURPRISE_PCT = 0.0

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = base.MAX_DRAWDOWN_WORSE
MAX_SINGLE_POSITIVE_SHARE = base.MAX_SINGLE_POSITIVE_SHARE
MAX_POSITIVE_HHI = base.MAX_POSITIVE_HHI

ACCEPTED_COMPRESSION_COMPARATOR = base.ACCEPTED_COMPRESSION_COMPARATOR
ACCEPTED_POST_EARNINGS_REFERENCE = {
    "experiment_id": "exp-20260602-026",
    "decision": "accepted_post_earnings_underpriced_shared_default_off_adapter",
    "expected_value_score_delta_sum": 0.3547,
    "total_pnl_delta_sum": 3557.15,
    "note": (
        "Nearest accepted earnings-event default-off paper adapter. This is a "
        "context reference, not a hard gate, because the current test is a "
        "direct pre-event positioning source rather than post-event drift."
    ),
}

BASE_GATE4 = base.BASE_GATE4
BASE_BUILD_PAYLOAD = base.BASE_BUILD_PAYLOAD

PREDICTION = {
    "success_probability": 0.14,
    "expected_ev_delta": 0.20,
    "expected_pnl_delta": 3500.0,
    "main_failure_modes": [
        "pre_event_drift_already_priced",
        "earnings_calendar_sparse_pool",
        "post_earnings_neighbor_overfit",
        "window_regression",
        "announcement_gap_risk",
    ],
    "confidence_reason": (
        "Earnings snapshots cover all three canonical windows and contain PIT "
        "days_to_earnings/surprise fields, but nearby post-earnings peer "
        "prewarm and revision/surprise retries were weak; this scout tests "
        "direct pre-event positioning with no production change."
    ),
    "recorded_at": "2026-06-10T09:10:17+00:00",
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
        "require a shared default-off adapter that loads the same point-in-time "
        "earnings snapshot for the signal date, applies the same days-to-"
        "earnings 6-12 and positive historical-surprise gates, sector-known "
        "liquid stock universe, SPY-relative leadership gates, close-quality "
        "gates, same-ticker core-overlap exclusion, next-open paper entry, "
        "five-trading-day exit, costs, cooldown, accepted compression "
        "comparator, and concentration controls in both historical replay and "
        "daily production before any report queue, paper ledger, candidate "
        "priority, sizing, watchlist, or order surface could change."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "entry/candidate_pool: stocks with a known upcoming earnings event in "
        "6-12 calendar days, positive historical earnings surprise, and current "
        "liquid SPY-relative leadership may experience pre-event positioning "
        "drift before the announcement. It uses only free earnings snapshots and "
        "OHLCV fields known by the signal date."
    ),
    "2_history_check": {
        "exact_prior": (
            "Targeted rg over docs/experiment_log.jsonl, experiments/logs, "
            "docs/lessons, docs/experiments, and quant/experiments found no "
            "direct pre-earnings liquid leadership candidate pool using "
            "days_to_earnings 6-12 plus OHLCV leadership."
        ),
        "nearby_event_trials": (
            "exp-20260602-026 accepted post-earnings underpriced drift, while "
            "exp-20260607-013 post-earnings peer upcoming prewarm and "
            "exp-20260609-024 early peer sympathy were rejected. This run does "
            "not use post-earnings issuer reaction or peer sympathy."
        ),
        "nearby_revision_trials": (
            "exp-20260605-029 and exp-20260606-016 revision/surprise variants "
            "were rejected or weak. This test avoids estimate-revision history "
            "because standard-window data is sparse outside late_strong."
        ),
        "dte_slot_history": (
            "exp-20260517-007 was a core breakout Financials 8-14 DTE risk "
            "multiplier and was rejected as a thin slot/ranking pocket. This "
            "experiment changes the candidate source, not a risk scalar."
        ),
        "frozen_lanes_avoided": (
            "No LLM soft ranking, Form4 retry, Companyfacts scalar mining, "
            "accepted helper source-priority extension, 52-week source "
            "extension, or state-surface notional/profile retune is involved."
        ),
    },
    "3_single_causal_variable": (
        "One fixed policy bundle: signal-date earnings snapshot days_to_earnings "
        "6-12, positive average historical surprise, liquid sector-known stock "
        "universe, existing 20d/60d SPY-relative leadership gates, same-ticker "
        "core-overlap exclusion, top-1 next-open paper entry, five-day hold, "
        "cost, cooldown, and concentration gates."
    ),
    "4_acceptance_standard": (
        "Use docs/backtesting.md three canonical windows. Treat as a positive "
        "replay lead only if aggregate EV/PnL improve, no EV/PnL regression "
        "window appears, target sample >=20 across all 3 windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration guard passes, and the accepted "
        "exp-20260608-013 compression comparator is beaten. It is not accepted "
        "into production without a shared default-off helper."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260610_011_pre_earnings_liquid_leadership.py"
    ),
}


_EARNINGS_CACHE: dict[str, dict[str, Any] | None] = {}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _snapshot_key(signal_date: str) -> str:
    return signal_date.replace("-", "")


def _load_earnings_snapshot(signal_date: str) -> dict[str, Any] | None:
    key = _snapshot_key(signal_date)
    if key not in _EARNINGS_CACHE:
        path = EARNINGS_DIR / f"earnings_snapshot_{key}.json"
        if not path.exists():
            _EARNINGS_CACHE[key] = None
        else:
            _EARNINGS_CACHE[key] = json.loads(path.read_text(encoding="utf-8"))
    return _EARNINGS_CACHE[key]


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _pre_earnings_rows_for_date(signal_date: str) -> dict[str, dict[str, Any]]:
    snapshot = _load_earnings_snapshot(signal_date)
    if not snapshot:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for ticker, row in (snapshot.get("earnings") or {}).items():
        days_to_earnings = _int_or_none(row.get("days_to_earnings"))
        surprise = _float_or_none(row.get("avg_historical_surprise_pct"))
        if days_to_earnings is None or surprise is None:
            continue
        if days_to_earnings < MIN_DAYS_TO_EARNINGS:
            continue
        if days_to_earnings > MAX_DAYS_TO_EARNINGS:
            continue
        if surprise <= MIN_AVG_HISTORICAL_SURPRISE_PCT:
            continue
        out[ticker] = row
    return out


def _candidate_for_pre_earnings_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    earnings_row: dict[str, Any],
) -> dict[str, Any] | None:
    row = base._candidate_for_ticker(
        snapshot=snapshot,
        indices=indices,
        sector_entries=sector_entries,
        ticker=ticker,
        signal_date=signal_date,
        month_label="pre_earnings_6_12d",
    )
    if row is None:
        return None
    days_to_earnings = _int_or_none(earnings_row.get("days_to_earnings"))
    surprise = _float_or_none(earnings_row.get("avg_historical_surprise_pct"))
    if days_to_earnings is None or surprise is None:
        return None
    row["source"] = "PRE_EARNINGS_LIQUID_LEADERSHIP_PAPER"
    row.pop("candidate_month_label", None)
    row["candidate_days_to_earnings"] = days_to_earnings
    row["candidate_earnings_window_label"] = "pre_earnings_6_12d"
    row["candidate_avg_historical_surprise_pct"] = round(surprise, 4)
    row["candidate_eps_estimate"] = earnings_row.get("eps_estimate")
    row["candidate_eps_actual_last"] = earnings_row.get("eps_actual_last")
    row["candidate_earnings_snapshot_date"] = _snapshot_key(signal_date)
    row["uses_free_ohlcv_only"] = False
    row["uses_free_earnings_snapshot"] = True
    row["known_at"] = "signal_date_earnings_snapshot_and_ohlcv_before_next_open_paper_entry"
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
    dates = [
        date_value
        for date_value in all_dates
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    candidates: list[dict[str, Any]] = []
    day_contexts: list[dict[str, Any]] = []
    dte_distribution: dict[str, int] = {}
    scan = {
        "scanned_trading_days": len(dates),
        "days_with_earnings_snapshot": 0,
        "days_without_earnings_snapshot": 0,
        "days_with_pre_earnings_window_tickers": 0,
        "pre_earnings_window_tickers": 0,
        "days_with_raw_pre_earnings_candidates": 0,
        "raw_pre_earnings_candidates": 0,
        "same_ticker_core_overlap_rejections": 0,
    }

    for signal_date in dates:
        earnings_snapshot = _load_earnings_snapshot(signal_date)
        if earnings_snapshot is None:
            scan["days_without_earnings_snapshot"] += 1
            continue
        scan["days_with_earnings_snapshot"] += 1
        earnings_rows = _pre_earnings_rows_for_date(signal_date)
        if not earnings_rows:
            continue
        scan["days_with_pre_earnings_window_tickers"] += 1
        scan["pre_earnings_window_tickers"] += len(earnings_rows)

        ab_entries = entries_by_date.get(signal_date, [])
        ab_tickers = {trade.get("ticker") for trade in ab_entries}
        day_rows: list[dict[str, Any]] = []
        for ticker, earnings_row in sorted(earnings_rows.items()):
            if ticker not in sector_entries:
                continue
            if ticker in ab_tickers:
                scan["same_ticker_core_overlap_rejections"] += 1
                continue
            row = _candidate_for_pre_earnings_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                earnings_row=earnings_row,
            )
            if row is None:
                continue
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = False
            day_rows.append(row)
            dte_key = str(row["candidate_days_to_earnings"])
            dte_distribution[dte_key] = dte_distribution.get(dte_key, 0) + 1
        if not day_rows:
            continue
        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_score"]),
                -float(row["candidate_avg_historical_surprise_pct"]),
                int(row["candidate_days_to_earnings"]),
                -float(row["candidate_ret20_excess_spy"]),
                -float(row["candidate_close_location"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                str(row.get("sector") or ""),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        scan["days_with_raw_pre_earnings_candidates"] += 1
        scan["raw_pre_earnings_candidates"] += len(day_rows)
        top = day_rows[0]
        day_contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(day_rows),
                "top_candidate": top["ticker"],
                "top_candidate_score": top["candidate_score"],
                "top_candidate_days_to_earnings": top["candidate_days_to_earnings"],
                "top_candidate_avg_historical_surprise_pct": top[
                    "candidate_avg_historical_surprise_pct"
                ],
                "top_candidate_ret20_excess_spy": top["candidate_ret20_excess_spy"],
                "top_candidate_close_location": top["candidate_close_location"],
            }
        )
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["candidate_avg_historical_surprise_pct"]),
            int(row["candidate_days_to_earnings"]),
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
            "dte_distribution": dict(sorted(dte_distribution.items())),
            "min_days_to_earnings": MIN_DAYS_TO_EARNINGS,
            "max_days_to_earnings": MAX_DAYS_TO_EARNINGS,
            "min_avg_historical_surprise_pct": MIN_AVG_HISTORICAL_SURPRISE_PCT,
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
    gate["accepted_post_earnings_reference"] = ACCEPTED_POST_EARNINGS_REFERENCE
    gate["passed"] = not gate.get("failed_reasons")
    gate["decision"] = (
        "positive_replay_lead_not_promoted_pre_earnings_liquid_leadership"
        if gate["passed"]
        else "rejected_pre_earnings_liquid_leadership_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only the signal-date earnings snapshot plus close-of-day "
        "OHLCV available on the signal date. Paper entry is next available open "
        "with existing entry slippage; exit is the close five trading days after "
        "the signal with target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    passed = bool(payload["gate4"]["passed"])
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
            "mechanism_family": (
                "production_visible_free_earnings_calendar_ohlcv_candidate_pool"
            ),
            "new_evidence_type": (
                "production_visible_free_earnings_snapshot_pre_event_window_plus_ohlcv_leadership"
            ),
            "nearby_prior_experiments": [
                "exp-20260607-013",
                "exp-20260609-024",
                "exp-20260602-026",
                "exp-20260605-029",
                "exp-20260606-016",
                "exp-20260517-007",
            ],
            "prior_trial_count": 5,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
            "accepted_post_earnings_reference": ACCEPTED_POST_EARNINGS_REFERENCE,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that pre-earnings drift in "
                "this narrow snapshot universe is already priced, too sparse, "
                "or dominated by announcement-gap risk after next-open entry. "
                "Do not answer by sweeping DTE window, surprise threshold, "
                "ret20/ret60 thresholds, top-N, hold-day, cooldown, or notional "
                "on these frozen windows without materially new PIT evidence."
            ),
            "next_evidence_needed": (
                "A retry needs materially new pre-event evidence such as "
                "point-in-time analyst-count/estimate-trajectory breadth, "
                "option-implied move where three-window data exists, verified "
                "event-time before/after close semantics, or closed forward "
                "replacement rows. Pure DTE/RS threshold tuning stays frozen."
            ),
        }
    )
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "min_days_to_earnings": MIN_DAYS_TO_EARNINGS,
        "max_days_to_earnings": MAX_DAYS_TO_EARNINGS,
        "min_avg_historical_surprise_pct": MIN_AVG_HISTORICAL_SURPRISE_PCT,
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
            "The fixed pre-earnings liquid leadership bundle cleared the "
            "canonical three-window gates and beat the accepted compression "
            "comparator, suggesting known event proximity plus liquid "
            "leadership contributed replacement value before announcements. It "
            "remains only a replay lead because no shared daily adapter or "
            "production parity path was added."
            if passed
            else (
                "The fixed pre-earnings liquid leadership bundle failed Gate 4. "
                "The result implies the direct DTE 6-12 plus positive-surprise "
                "snapshot field did not add enough distinct edge beyond liquid "
                "momentum after next-open execution, costs, five-day hold, "
                "cooldown, and overlap/concentration controls. The useful "
                "lesson is to seek richer PIT pre-event evidence, not DTE or "
                "momentum threshold tuning."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping days-to-earnings windows, historical "
            "surprise threshold, ret20/ret60 relative-strength thresholds, "
            "signal-day return, close-location, volume-ratio bounds, top-N, "
            "hold-day, cooldown, or paper notional on the same frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["interpretation"] = (
        "The pre-earnings liquid leadership source passed as a replay-only "
        "promotion lead, but no production surface changed and a shared "
        "default-off parity adapter is required before use."
        if passed
        else (
            "The pre-earnings liquid leadership source was rejected; it did not "
            "establish a distinct free earnings-calendar/OHLCV candidate-pool "
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | DTE days | Candidate days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {dte_days} | {days} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                dte_days=scan.get("days_with_pre_earnings_window_tickers", 0),
                days=scan.get("days_with_raw_pre_earnings_candidates", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Pre-Earnings Liquid Leadership Candidate Pool",
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
            "- Post-earnings reference EV/PnL: `{}` / `${:,.2f}`".format(
                ACCEPTED_POST_EARNINGS_REFERENCE["expected_value_score_delta_sum"],
                ACCEPTED_POST_EARNINGS_REFERENCE["total_pnl_delta_sum"],
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
        "mechanism_family": "production_visible_free_earnings_calendar_ohlcv_candidate_pool",
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
        "accepted_post_earnings_reference": ACCEPTED_POST_EARNINGS_REFERENCE,
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
                "pre_earnings_window_day_count": payload["context_scan_by_window"][
                    label
                ].get("days_with_pre_earnings_window_tickers"),
                "raw_candidate_count": payload["context_scan_by_window"][label].get(
                    "raw_pre_earnings_candidates"
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
