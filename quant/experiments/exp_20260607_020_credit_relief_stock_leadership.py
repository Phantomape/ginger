"""exp-20260607-020: credit-relief stock-leadership scout.

Replay-only alpha search. This tests one production-visible free-OHLCV
candidate-source variable: on days where HYG and JNK rally while SPY and QQQ
confirm risk-on, select the strongest liquid stock leaders as next-open,
10-trading-day default-off paper candidates.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import exp_20260606_019_macro_relief_top2_leadership_candidate_pool as previous


framework = previous.framework

EXPERIMENT_ID = "exp-20260607-020"
STEM = "credit_relief_stock_leadership"
TRIAL_FAMILY = "credit_relief_stock_leadership_candidate_pool"
TRIAL_VARIANT_ID = "hyg_jnk_spy_qqq_confirmed_stock_leadership_top2_10d_v1"
CHANGED_VARIABLE = "credit_relief_stock_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = previous.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260607_020_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 2
SAME_TICKER_COOLDOWN_DAYS = 10

MIN_HYG_RELIEF_RETURN = 0.004
MIN_JNK_RELIEF_RETURN = 0.004
MIN_HYG_CLOSE_LOCATION = 0.55
MIN_JNK_CLOSE_LOCATION = 0.55
MIN_SPY_RELIEF_RETURN = 0.002
MIN_QQQ_RELIEF_RETURN = 0.003
MIN_SPY_CLOSE_LOCATION = 0.55
MIN_QQQ_CLOSE_LOCATION = 0.55
MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_SIGNAL_RETURN = 0.010
MIN_RELATIVE_VS_SPY = 0.008
MIN_RELATIVE_VS_QQQ = 0.004
MIN_CLOSE_LOCATION = 0.70
MIN_VOLUME_RATIO_20D = 1.05
MIN_RET20_EXCESS_SPY = 0.0
MIN_RET60_EXCESS_SPY = -0.02
MIN_RET5 = -0.03
MAX_RET5 = 0.15
MAX_REALIZED_VOL_20D = 0.080

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

PREDICTION = {
    "success_probability": 0.13,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "thin_credit_relief_sample",
        "broad_momentum_relabel",
        "accepted_cross_asset_relief_overlap",
        "window_regression",
        "drawdown_drift",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Accepted macro and VIXY relief stock-leadership adapters show "
        "cross-asset risk-relief leadership can work, but rates-relief and "
        "broad momentum neighbors often failed; HYG/JNK credit relief is "
        "materially different and first needs replay sample validation."
    ),
    "recorded_at": "2026-06-07T17:07:32+00:00",
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
        "require a shared default-off adapter exposing the same HYG/JNK/SPY/QQQ "
        "credit-relief context, sector-known liquid stock universe, "
        "stock leadership fields, same-ticker core-overlap exclusion, "
        "next-open paper entry, 10-trading-day exit, costs, cooldown, and "
        "concentration controls in both replay and daily production before "
        "any report queue, paper ledger, candidate priority, sizing, "
        "watchlist, or order surface could change."
    ),
}

BASE_GATE4 = previous.BASE_GATE4
BASE_BUILD_PAYLOAD = previous.BASE_BUILD_PAYLOAD
BASE_PERSIST = previous.BASE_PERSIST
BASE_CANDIDATE_FOR_TICKER = previous._candidate_for_ticker
BASE_LOAD_WINDOW_SNAPSHOT = framework._load_window_snapshot


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _range_location(row: dict[str, Any]) -> float | None:
    high = framework._value(row, "High")
    low = framework._value(row, "Low")
    close = framework._value(row, "Close")
    if high is None or low is None or close is None or high <= low:
        return None
    return (close - low) / (high - low)


def _load_window_snapshot(
    *,
    cfg: dict[str, str],
    eligible_tickers: set[str],
) -> dict[str, list[dict[str, Any]]]:
    return BASE_LOAD_WINDOW_SNAPSHOT(
        cfg=cfg,
        eligible_tickers=set(eligible_tickers) | {"HYG", "JNK"},
    )


def _relief_context_for_day(
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    signal_date: str,
) -> dict[str, Any] | None:
    hyg_rows = snapshot.get("HYG") or []
    jnk_rows = snapshot.get("JNK") or []
    spy_rows = snapshot.get("SPY") or []
    qqq_rows = snapshot.get("QQQ") or []
    hyg_idx = indices.get("HYG", {}).get(signal_date)
    jnk_idx = indices.get("JNK", {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    qqq_idx = indices.get("QQQ", {}).get(signal_date)
    if hyg_idx is None or jnk_idx is None or spy_idx is None or qqq_idx is None:
        return None

    hyg_return = framework._daily_return(hyg_rows, hyg_idx)
    jnk_return = framework._daily_return(jnk_rows, jnk_idx)
    spy_return = framework._daily_return(spy_rows, spy_idx)
    qqq_return = framework._daily_return(qqq_rows, qqq_idx)
    hyg_close_location = _range_location(hyg_rows[hyg_idx])
    jnk_close_location = _range_location(jnk_rows[jnk_idx])
    spy_close_location = _range_location(spy_rows[spy_idx])
    qqq_close_location = _range_location(qqq_rows[qqq_idx])
    context = {
        "date": signal_date,
        "hyg_return": framework._round(hyg_return, 6),
        "jnk_return": framework._round(jnk_return, 6),
        "spy_return": framework._round(spy_return, 6),
        "qqq_return": framework._round(qqq_return, 6),
        "hyg_close_location": framework._round(hyg_close_location, 6),
        "jnk_close_location": framework._round(jnk_close_location, 6),
        "spy_close_location": framework._round(spy_close_location, 6),
        "qqq_close_location": framework._round(qqq_close_location, 6),
        "min_hyg_relief_return": MIN_HYG_RELIEF_RETURN,
        "min_jnk_relief_return": MIN_JNK_RELIEF_RETURN,
        "min_hyg_close_location": MIN_HYG_CLOSE_LOCATION,
        "min_jnk_close_location": MIN_JNK_CLOSE_LOCATION,
        "min_spy_relief_return": MIN_SPY_RELIEF_RETURN,
        "min_qqq_relief_return": MIN_QQQ_RELIEF_RETURN,
        "min_spy_close_location": MIN_SPY_CLOSE_LOCATION,
        "min_qqq_close_location": MIN_QQQ_CLOSE_LOCATION,
        "rule_version": RULE_VERSION,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }
    if (
        hyg_return is None
        or jnk_return is None
        or spy_return is None
        or qqq_return is None
    ):
        return {**context, "passed": False, "reason": "missing_daily_return"}
    if (
        hyg_close_location is None
        or jnk_close_location is None
        or spy_close_location is None
        or qqq_close_location is None
    ):
        return {**context, "passed": False, "reason": "missing_close_location"}
    if hyg_return < MIN_HYG_RELIEF_RETURN:
        return {**context, "passed": False, "reason": "hyg_relief_return_too_low"}
    if jnk_return < MIN_JNK_RELIEF_RETURN:
        return {**context, "passed": False, "reason": "jnk_relief_return_too_low"}
    if hyg_close_location < MIN_HYG_CLOSE_LOCATION:
        return {**context, "passed": False, "reason": "hyg_close_location_too_low"}
    if jnk_close_location < MIN_JNK_CLOSE_LOCATION:
        return {**context, "passed": False, "reason": "jnk_close_location_too_low"}
    if spy_return < MIN_SPY_RELIEF_RETURN:
        return {**context, "passed": False, "reason": "spy_relief_return_too_low"}
    if qqq_return < MIN_QQQ_RELIEF_RETURN:
        return {**context, "passed": False, "reason": "qqq_relief_return_too_low"}
    if spy_close_location < MIN_SPY_CLOSE_LOCATION:
        return {**context, "passed": False, "reason": "spy_close_location_too_low"}
    if qqq_close_location < MIN_QQQ_CLOSE_LOCATION:
        return {**context, "passed": False, "reason": "qqq_close_location_too_low"}
    return {**context, "passed": True, "reason": "hyg_jnk_spy_qqq_credit_relief_passed"}


def _candidate_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    context: dict[str, Any],
) -> dict[str, Any] | None:
    row = BASE_CANDIDATE_FOR_TICKER(
        snapshot=snapshot,
        indices=indices,
        sector_entries=sector_entries,
        ticker=ticker,
        signal_date=signal_date,
        context=context,
    )
    if row is None:
        return None
    row["source"] = "CREDIT_RELIEF_LEADERSHIP_PAPER"
    row["credit_relief_context"] = row.pop("macro_relief_context", context)
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
    dates = [
        date_value
        for date_value in framework.shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    candidates: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    scan = {
        "scanned_trading_days": len(dates),
        "credit_relief_days": 0,
        "non_relief_days": 0,
        "days_with_raw_credit_relief_candidates": 0,
        "raw_credit_relief_candidates": 0,
    }
    for signal_date in dates:
        context = _relief_context_for_day(snapshot, indices, signal_date)
        if context is None:
            continue
        if not context.get("passed"):
            scan["non_relief_days"] += 1
            continue
        scan["credit_relief_days"] += 1
        day_rows: list[dict[str, Any]] = []
        for ticker in sorted(sector_entries):
            row = _candidate_for_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                context=context,
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
            contexts.append({**context, "raw_candidate_count": 0})
            continue
        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_score"]),
                -float(row["candidate_relative_vs_spy"]),
                -float(row["candidate_ret20_excess_spy"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                str(row.get("sector") or ""),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        scan["days_with_raw_credit_relief_candidates"] += 1
        scan["raw_credit_relief_candidates"] += len(day_rows)
        contexts.append(
            {
                **context,
                "raw_candidate_count": len(day_rows),
                "top_candidate": day_rows[0]["ticker"],
                "top_candidate_score": day_rows[0]["candidate_score"],
                "top_candidate_relative_vs_spy": day_rows[0]["candidate_relative_vs_spy"],
                "top_candidate_ret20_excess_spy": day_rows[0][
                    "candidate_ret20_excess_spy"
                ],
            }
        )
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["candidate_relative_vs_spy"]),
            -float(row["candidate_ret20_excess_spy"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            str(row.get("sector") or ""),
            row["ticker"],
        )
    )
    scan.update(
        {
            "rule_version": RULE_VERSION,
            "min_hyg_relief_return": MIN_HYG_RELIEF_RETURN,
            "min_jnk_relief_return": MIN_JNK_RELIEF_RETURN,
            "min_hyg_close_location": MIN_HYG_CLOSE_LOCATION,
            "min_jnk_close_location": MIN_JNK_CLOSE_LOCATION,
            "min_spy_relief_return": MIN_SPY_RELIEF_RETURN,
            "min_qqq_relief_return": MIN_QQQ_RELIEF_RETURN,
            "min_spy_close_location": MIN_SPY_CLOSE_LOCATION,
            "min_qqq_close_location": MIN_QQQ_CLOSE_LOCATION,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "min_relative_vs_spy": MIN_RELATIVE_VS_SPY,
            "min_relative_vs_qqq": MIN_RELATIVE_VS_QQQ,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
            "min_ret5": MIN_RET5,
            "max_ret5": MAX_RET5,
            "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
        }
    )
    return candidates, contexts, scan


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
    failed = [reason for reason in gate["failed_reasons"] if reason != "target_sample_too_small"]
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_summary["windows_with_target_trades"]) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    gate["failed_reasons"] = failed
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_not_promoted_credit_relief_stock_leadership"
        if gate["passed"]
        else "rejected_credit_relief_stock_leadership_candidate_pool"
    )
    gate["target_trade_count_min"] = MIN_TARGET_TRADES
    gate["target_window_count_min"] = MIN_TARGET_WINDOWS
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    gate4 = payload["gate4"]
    aggregate = payload["delta_metrics"]["aggregate"]
    accepted = bool(gate4["passed"])
    credit_context_missing = all(
        (scan.get("credit_relief_days") or 0) == 0
        and (scan.get("non_relief_days") or 0) == 0
        and (scan.get("scanned_trading_days") or 0) > 0
        for scan in (payload.get("context_scan_by_window") or {}).values()
    )
    failure_interpretation = (
        "The credit-relief source could not be evaluated because the canonical "
        "warehouse has no HYG/JNK OHLCV rows in the fixed-window replay surface. "
        "Do not retune thresholds; retry only after adding PIT-safe HYG/JNK or "
        "another replay-visible credit-risk proxy."
        if credit_context_missing
        else (
            "The credit-relief stock-leadership source did not clear Gate 4. "
            "Do not promote it or answer by retuning HYG/JNK/SPY/QQQ thresholds, "
            "top-N, hold-day, cooldown, or notional on these frozen windows."
        )
    )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "HYG/JNK credit-relief days with SPY and QQQ confirmation "
                "may identify liquid stock leaders whose next-open "
                "continuation beats cash without adding noisy broad momentum."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_cross_asset_candidate_pool",
            "new_evidence_type": "free_ohlcv_credit_relief_cross_asset_state",
            "nearby_prior_experiments": [
                "exp-20260606-019",
                "exp-20260606-020",
                "exp-20260607-019",
                "exp-20260607-015",
                "exp-20260606-004",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "anti_js": "No JavaScript was used.",
            "decision": gate4["decision"],
            "status": "positive_replay_lead_not_promoted" if accepted else "rejected",
            "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
            "total_pnl_delta": aggregate["total_pnl_delta_sum"],
            "interpretation": (
                "The credit-relief stock-leadership source cleared Gate 4 "
                "as a replay-only/default-off lead, but no production surface "
                "was promoted."
                if accepted
                else failure_interpretation
            ),
            "rejection_reason": (
                None
                if accepted
                else (
                    "credit_etf_ohlcv_missing_in_canonical_warehouse"
                    if credit_context_missing
                    else "; ".join(gate4["failed_reasons"])
                )
            ),
            "negative_reflection": (
                "If rejected, the likely reason is that credit relief is still "
                "a broad beta/momentum relabel or arrives too late for "
                "next-open single-stock continuation after costs."
            ),
            "post_run_reflection": {
                "why_result_happened": (
                    "The source produced positive replacement value in all "
                    "three windows without breaching drawdown, survival, or "
                    "concentration guardrails, suggesting credit-risk "
                    "compression added a distinct cross-asset risk-relief "
                    "state."
                    if accepted
                    else (
                        "The source produced zero target rows because HYG and "
                        "JNK are absent from the canonical broad warehouse. "
                        "This is a data-coverage failure for the proposed "
                        "credit-risk proxy, not evidence that credit relief "
                        "thresholds should be tuned."
                        if credit_context_missing
                        else (
                            "The source failed to add robust replacement value "
                            "after next-open entry and costs. That suggests "
                            "HYG/JNK relief did not reliably separate durable stock "
                            "leadership from broad risk-on momentum in the "
                            "canonical windows."
                        )
                    )
                ),
                "forbidden_near_neighbor_retry": (
                    "Do not retry by sweeping HYG/JNK return, HYG/JNK "
                    "close-location, SPY/QQQ relief, stock close-location, "
                    "volume, ret20/ret60, top-N, hold-day, cooldown, or paper "
                    "notional thresholds "
                    "on the frozen windows."
                ),
                "new_evidence_required": (
                    "A retry requires materially new PIT credit evidence, "
                    "such as replay-visible HYG/JNK OHLCV, credit-spread, "
                    "credit-flow, ETF creation/redemption, or closed forward "
                    "replacement-value rows from a shared default-off adapter."
                ),
            },
            "data_coverage": {
                "credit_context_missing": credit_context_missing,
                "required_credit_tickers": ["HYG", "JNK"],
                "observed_result": (
                    "no HYG/JNK context rows in canonical warehouse replay"
                    if credit_context_missing
                    else "credit context available"
                ),
            },
            "next_evidence_needed": (
                "A positive replay lead still needs a shared default-off "
                "adapter and parity tests before forward observation; live "
                "activation would require closed forward replacement-value "
                "rows and a separate activation-envelope Gate 1-4."
            ),
            "related_files": [
                _repo_rel(Path(__file__)),
                _repo_rel(OUT_JSON),
                _repo_rel(LOG_JSON),
                _repo_rel(TICKET_JSON),
                _repo_rel(CARD_MD),
                _repo_rel(MANIFEST_JSON),
                _repo_rel(EXPERIMENT_LOG),
                _repo_rel(REGISTRY_JSON),
            ],
        }
    )
    payload.setdefault("parameters", {}).update(
        {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "min_hyg_relief_return": MIN_HYG_RELIEF_RETURN,
            "min_jnk_relief_return": MIN_JNK_RELIEF_RETURN,
            "min_hyg_close_location": MIN_HYG_CLOSE_LOCATION,
            "min_jnk_close_location": MIN_JNK_CLOSE_LOCATION,
            "min_spy_relief_return": MIN_SPY_RELIEF_RETURN,
            "min_qqq_relief_return": MIN_QQQ_RELIEF_RETURN,
            "min_spy_close_location": MIN_SPY_CLOSE_LOCATION,
            "min_qqq_close_location": MIN_QQQ_CLOSE_LOCATION,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "min_relative_vs_spy": MIN_RELATIVE_VS_SPY,
            "min_relative_vs_qqq": MIN_RELATIVE_VS_QQQ,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
            "min_ret5": MIN_RET5,
            "max_ret5": MAX_RET5,
            "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only close-of-day OHLCV available on the signal date: "
        "HYG, JNK, SPY, and QQQ daily return/range context plus stock leadership, "
        "liquidity, close-location, volume, ret5/ret20/ret60, and realized-vol "
        "fields. Paper entry is next available open with existing entry "
        "slippage; exit is the close 10 trading days after the signal with "
        "target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: credit-risk compression confirmed by "
            "SPY/QQQ relief may identify stock leaders before the next "
            "session fully reprices the risk-on move."
        ),
        "2_history_check": {
            "exp-20260605-033": (
                "Cross-section pressure resilience failed across all windows; "
                "this tests credit relief after risk compression, not stress "
                "resilience during selloff pressure."
            ),
            "exp-20260606-019/020": (
                "Official macro relief stock leadership was accepted as a "
                "shared adapter; this does not retune it and uses a different "
                "cross-asset credit state instead of event-calendar days."
            ),
            "exp-20260606-027": (
                "Macro stress resilient leadership failed with thin sample and "
                "negative EV; this tests risk relief rather than stress."
            ),
            "exp-20260606-004/005": (
                "Broad recent-winner continuation failed tail/drawdown; this "
                "requires explicit HYG/JNK/SPY/QQQ relief state."
            ),
            "exact_credit_relief_prior": (
                "No HYG/JNK credit-relief stock-leadership candidate-pool "
                "experiment was found in experiment_log/cards/log search."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Aggregate EV/PnL "
            "must improve, no window may regress EV/PnL, target sample must be "
            ">=20 across all 3 windows, survival must stay >=5%, drawdown "
            "drift <=0.5pp, and concentration guard must pass."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260607_020_credit_relief_stock_leadership.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["gate3"]["note"] = (
        "No new core filter or entry rule was added. The credit-relief "
        "leadership source is additive default-off paper, so core signals "
        "generated/survived are unchanged from baseline."
    )
    runtime_fields = payload.setdefault("gate2", {}).setdefault("runtime_fields", [])
    for field in ("HYG daily OHLCV", "JNK daily OHLCV"):
        if field not in runtime_fields:
            runtime_fields.insert(3, field)
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Credit relief days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {days} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                days=scan.get("credit_relief_days", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Credit Relief Stock Leadership",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
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
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "- Rejection reason: `{}`".format(payload.get("rejection_reason") or "none"),
            "- Data coverage: `{}`".format(
                (payload.get("data_coverage") or {}).get("observed_result", "n/a")
            ),
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


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["gate4"]["passed"],
        "mechanism_family": "production_visible_free_ohlcv_cross_asset_candidate_pool",
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
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
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
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "credit_relief_day_count": payload["context_scan_by_window"][label].get(
                    "credit_relief_days"
                ),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": {**payload["calibration"]},
        "data_coverage": payload.get("data_coverage"),
        "production_impact": PRODUCTION_IMPACT,
        "negative_reflection": payload["negative_reflection"],
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


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
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
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


def persist(payload: dict[str, Any]) -> None:
    BASE_PERSIST(payload)
    _write_manifest(payload)


def _patch_framework() -> None:
    previous.EXPERIMENT_ID = EXPERIMENT_ID
    previous.STEM = STEM
    previous.TRIAL_FAMILY = TRIAL_FAMILY
    previous.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    previous.CHANGED_VARIABLE = CHANGED_VARIABLE
    previous.RULE_VERSION = RULE_VERSION
    previous.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    previous.HOLD_DAYS = HOLD_DAYS
    previous.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    previous.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    previous.MIN_SPY_RELIEF_RETURN = MIN_SPY_RELIEF_RETURN
    previous.MIN_QQQ_RELIEF_RETURN = MIN_QQQ_RELIEF_RETURN
    previous.MIN_SPY_CLOSE_LOCATION = MIN_SPY_CLOSE_LOCATION
    previous.MIN_QQQ_CLOSE_LOCATION = MIN_QQQ_CLOSE_LOCATION
    previous.MIN_PRICE = MIN_PRICE
    previous.MIN_AVG_DOLLAR_VOLUME_20D = MIN_AVG_DOLLAR_VOLUME_20D
    previous.MIN_SIGNAL_RETURN = MIN_SIGNAL_RETURN
    previous.MIN_RELATIVE_VS_SPY = MIN_RELATIVE_VS_SPY
    previous.MIN_RELATIVE_VS_QQQ = MIN_RELATIVE_VS_QQQ
    previous.MIN_CLOSE_LOCATION = MIN_CLOSE_LOCATION
    previous.MIN_VOLUME_RATIO_20D = MIN_VOLUME_RATIO_20D
    previous.MIN_RET20_EXCESS_SPY = MIN_RET20_EXCESS_SPY
    previous.MIN_RET60_EXCESS_SPY = MIN_RET60_EXCESS_SPY
    previous.MIN_RET5 = MIN_RET5
    previous.MAX_RET5 = MAX_RET5
    previous.MAX_REALIZED_VOL_20D = MAX_REALIZED_VOL_20D
    previous.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    previous.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    previous.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    previous.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    previous.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    previous.PREDICTION = PREDICTION
    previous.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    previous.OUT_DIR = OUT_DIR
    previous.OUT_JSON = OUT_JSON
    previous.LOG_JSON = LOG_JSON
    previous.TICKET_JSON = TICKET_JSON
    previous.CARD_MD = CARD_MD
    previous.MANIFEST_JSON = MANIFEST_JSON
    previous.EXPERIMENT_LOG = EXPERIMENT_LOG
    previous.REGISTRY_JSON = REGISTRY_JSON
    previous._relief_context_for_day = _relief_context_for_day
    previous._candidate_for_ticker = _candidate_for_ticker

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
    framework._load_window_snapshot = _load_window_snapshot
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._gate4 = _gate4
    framework._build_payload = _build_payload
    framework._build_card = _build_card
    framework._build_log_record = _build_log_record
    framework._write_manifest = _write_manifest
    framework.persist = persist


_patch_framework()


def main() -> None:
    framework.main()


if __name__ == "__main__":
    main()
