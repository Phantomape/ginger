"""exp-20260608-006: DIA/MDY real-economy leadership scout.

Replay-only alpha search. This tests one production-visible free-OHLCV
candidate-source variable: on days where DIA and MDY lead SPY, select liquid
stock leaders as next-open, 10-trading-day default-off paper candidates.

No production code, shared adapter, live/default orders, ranking, sizing, exits,
LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import exp_20260607_021_dollar_weakness_stock_leadership as base


framework = base.framework
macro_base = base.previous

EXPERIMENT_ID = "exp-20260608-006"
STEM = "dia_mdy_real_economy_leadership"
TRIAL_FAMILY = "dia_mdy_real_economy_leadership_candidate_pool"
TRIAL_VARIANT_ID = "dia_mdy_vs_spy_confirmed_stock_leadership_top2_10d_v1"
CHANGED_VARIABLE = "dia_mdy_real_economy_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260608_006_{STEM}.json"
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

MIN_DIA_RETURN = 0.000
MIN_MDY_RETURN = 0.001
MIN_SPY_RETURN = -0.003
MIN_DIA_RELATIVE_VS_SPY = 0.0015
MIN_MDY_RELATIVE_VS_SPY = 0.0015
MIN_DIA_CLOSE_LOCATION = 0.52
MIN_MDY_CLOSE_LOCATION = 0.55
MIN_SPY_CLOSE_LOCATION = 0.45

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_SIGNAL_RETURN = 0.006
MIN_RELATIVE_VS_SPY = 0.004
MIN_RELATIVE_VS_QQQ = -0.004
MIN_CLOSE_LOCATION = 0.62
MIN_VOLUME_RATIO_20D = 0.80
MIN_RET20_EXCESS_SPY = 0.005
MIN_RET60_EXCESS_SPY = -0.015
MIN_RET5 = -0.035
MAX_RET5 = 0.120
MAX_REALIZED_VOL_20D = 0.075

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

PREDICTION = {
    "success_probability": 0.14,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "broad_beta_relabel",
        "accepted_vixy_macro_overlap",
        "old_thin_regression",
        "drawdown_drift",
        "target_sample_too_small",
        "dia_mdy_context_missing",
    ],
    "confidence_reason": (
        "Accepted macro/VIXY and industry-relation adapters show free-OHLCV "
        "relation alpha can work, but recent IWM/rates/industry-stable "
        "neighbors failed. DIA+MDY leadership is a distinct real-economy "
        "confirmation source with high beta-relabel risk, so this is a "
        "low-probability replay scout."
    ),
    "recorded_at": "2026-06-08T05:20:00+00:00",
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
        "require a shared default-off adapter exposing the same DIA/MDY/SPY "
        "real-economy leadership context, sector-known liquid stock universe, "
        "stock leadership fields, same-ticker core-overlap exclusion, "
        "next-open paper entry, 10-trading-day exit, costs, cooldown, and "
        "concentration controls in both replay and daily production before "
        "any report queue, paper ledger, candidate priority, sizing, "
        "watchlist, or order surface could change."
    ),
}

BASE_GATE4 = base.BASE_GATE4
BASE_BUILD_PAYLOAD = base.BASE_BUILD_PAYLOAD
BASE_PERSIST = base.BASE_PERSIST
BASE_CANDIDATE_FOR_TICKER = base.BASE_CANDIDATE_FOR_TICKER
BASE_LOAD_WINDOW_SNAPSHOT = base.BASE_LOAD_WINDOW_SNAPSHOT


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
        eligible_tickers=set(eligible_tickers) | {"DIA", "MDY", "QQQ", "SPY"},
    )


def _real_economy_context_for_day(
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    signal_date: str,
) -> dict[str, Any] | None:
    dia_rows = snapshot.get("DIA") or []
    mdy_rows = snapshot.get("MDY") or []
    spy_rows = snapshot.get("SPY") or []
    dia_idx = indices.get("DIA", {}).get(signal_date)
    mdy_idx = indices.get("MDY", {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if dia_idx is None or mdy_idx is None or spy_idx is None:
        return None

    dia_return = framework._daily_return(dia_rows, dia_idx)
    mdy_return = framework._daily_return(mdy_rows, mdy_idx)
    spy_return = framework._daily_return(spy_rows, spy_idx)
    dia_close_location = _range_location(dia_rows[dia_idx])
    mdy_close_location = _range_location(mdy_rows[mdy_idx])
    spy_close_location = _range_location(spy_rows[spy_idx])
    context = {
        "date": signal_date,
        "dia_return": framework._round(dia_return, 6),
        "mdy_return": framework._round(mdy_return, 6),
        "spy_return": framework._round(spy_return, 6),
        "dia_relative_vs_spy": framework._round(
            None if dia_return is None or spy_return is None else dia_return - spy_return,
            6,
        ),
        "mdy_relative_vs_spy": framework._round(
            None if mdy_return is None or spy_return is None else mdy_return - spy_return,
            6,
        ),
        "dia_close_location": framework._round(dia_close_location, 6),
        "mdy_close_location": framework._round(mdy_close_location, 6),
        "spy_close_location": framework._round(spy_close_location, 6),
        "min_dia_return": MIN_DIA_RETURN,
        "min_mdy_return": MIN_MDY_RETURN,
        "min_spy_return": MIN_SPY_RETURN,
        "min_dia_relative_vs_spy": MIN_DIA_RELATIVE_VS_SPY,
        "min_mdy_relative_vs_spy": MIN_MDY_RELATIVE_VS_SPY,
        "min_dia_close_location": MIN_DIA_CLOSE_LOCATION,
        "min_mdy_close_location": MIN_MDY_CLOSE_LOCATION,
        "min_spy_close_location": MIN_SPY_CLOSE_LOCATION,
        "rule_version": RULE_VERSION,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }
    if dia_return is None or mdy_return is None or spy_return is None:
        return {**context, "passed": False, "reason": "missing_daily_return"}
    if (
        dia_close_location is None
        or mdy_close_location is None
        or spy_close_location is None
    ):
        return {**context, "passed": False, "reason": "missing_close_location"}
    if spy_return < MIN_SPY_RETURN:
        return {**context, "passed": False, "reason": "spy_return_too_low"}
    if dia_return < MIN_DIA_RETURN:
        return {**context, "passed": False, "reason": "dia_return_too_low"}
    if mdy_return < MIN_MDY_RETURN:
        return {**context, "passed": False, "reason": "mdy_return_too_low"}
    if dia_return - spy_return < MIN_DIA_RELATIVE_VS_SPY:
        return {**context, "passed": False, "reason": "dia_not_leading_spy"}
    if mdy_return - spy_return < MIN_MDY_RELATIVE_VS_SPY:
        return {**context, "passed": False, "reason": "mdy_not_leading_spy"}
    if dia_close_location < MIN_DIA_CLOSE_LOCATION:
        return {**context, "passed": False, "reason": "dia_close_location_too_low"}
    if mdy_close_location < MIN_MDY_CLOSE_LOCATION:
        return {**context, "passed": False, "reason": "mdy_close_location_too_low"}
    if spy_close_location < MIN_SPY_CLOSE_LOCATION:
        return {**context, "passed": False, "reason": "spy_close_location_too_low"}
    return {**context, "passed": True, "reason": "dia_mdy_real_economy_leadership_passed"}


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
    row["source"] = "DIA_MDY_REAL_ECONOMY_LEADERSHIP_PAPER"
    row["real_economy_leadership_context"] = row.pop("macro_relief_context", context)
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
        "real_economy_leadership_days": 0,
        "non_real_economy_days": 0,
        "days_with_raw_real_economy_candidates": 0,
        "raw_real_economy_candidates": 0,
    }
    for signal_date in dates:
        context = _real_economy_context_for_day(snapshot, indices, signal_date)
        if context is None:
            continue
        if not context.get("passed"):
            scan["non_real_economy_days"] += 1
            continue
        scan["real_economy_leadership_days"] += 1
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
        scan["days_with_raw_real_economy_candidates"] += 1
        scan["raw_real_economy_candidates"] += len(day_rows)
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
            "min_dia_return": MIN_DIA_RETURN,
            "min_mdy_return": MIN_MDY_RETURN,
            "min_spy_return": MIN_SPY_RETURN,
            "min_dia_relative_vs_spy": MIN_DIA_RELATIVE_VS_SPY,
            "min_mdy_relative_vs_spy": MIN_MDY_RELATIVE_VS_SPY,
            "min_dia_close_location": MIN_DIA_CLOSE_LOCATION,
            "min_mdy_close_location": MIN_MDY_CLOSE_LOCATION,
            "min_spy_close_location": MIN_SPY_CLOSE_LOCATION,
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
    failed = [
        reason for reason in gate["failed_reasons"] if reason != "target_sample_too_small"
    ]
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_summary["windows_with_target_trades"]) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    gate["failed_reasons"] = failed
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_not_promoted_dia_mdy_real_economy_leadership"
        if gate["passed"]
        else "rejected_dia_mdy_real_economy_leadership_candidate_pool"
    )
    gate["target_trade_count_min"] = MIN_TARGET_TRADES
    gate["target_window_count_min"] = MIN_TARGET_WINDOWS
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    gate4 = payload["gate4"]
    aggregate = payload["delta_metrics"]["aggregate"]
    accepted = bool(gate4["passed"])
    context_missing = all(
        (scan.get("real_economy_leadership_days") or 0) == 0
        and (scan.get("non_real_economy_days") or 0) == 0
        and (scan.get("scanned_trading_days") or 0) > 0
        for scan in (payload.get("context_scan_by_window") or {}).values()
    )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "DIA and MDY leadership versus SPY may identify real-economy "
                "risk appetite where liquid stock leaders continue over the "
                "next 10 trading days without simply adding random tickers."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_cross_asset_candidate_pool",
            "new_evidence_type": "free_ohlcv_dia_mdy_real_economy_relation",
            "nearby_prior_experiments": [
                "exp-20260607-016",
                "exp-20260607-024",
                "exp-20260608-003",
                "exp-20260608-004",
                "exp-20260608-005",
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
                "The DIA/MDY real-economy leadership source cleared Gate 4 as "
                "a replay-only/default-off lead, but no production surface was "
                "promoted."
                if accepted
                else (
                    "The DIA/MDY real-economy leadership source could not be "
                    "evaluated because DIA/MDY context is absent from the "
                    "canonical replay surface."
                    if context_missing
                    else (
                        "The DIA/MDY real-economy leadership source did not "
                        "clear Gate 4. Do not promote it or answer by retuning "
                        "DIA/MDY/SPY thresholds, stock leadership thresholds, "
                        "top-N, hold-day, cooldown, or notional on these "
                        "frozen windows."
                    )
                )
            ),
            "rejection_reason": (
                None
                if accepted
                else (
                    "dia_mdy_context_ohlcv_missing_in_canonical_warehouse"
                    if context_missing
                    else "; ".join(gate4["failed_reasons"])
                )
            ),
            "negative_reflection": (
                "If rejected, the likely reason is that DIA/MDY leadership is "
                "too close to broad risk beta or produces crowded cyclical "
                "continuation that does not survive next-open costs and "
                "drawdown guardrails."
            ),
            "post_run_reflection": {
                "why_result_happened": (
                    "The source produced positive replacement value in all "
                    "three windows without breaching drawdown, survival, or "
                    "concentration guardrails, suggesting DIA/MDY leadership "
                    "added a distinct real-economy relation."
                    if accepted
                    else (
                        "The source produced no target rows because DIA/MDY "
                        "context is absent from the canonical replay surface."
                        if context_missing
                        else (
                            "The source failed to add robust replacement value "
                            "after next-open entry and costs. That implies "
                            "DIA+MDY confirmation did not separate durable "
                            "single-stock leadership from ordinary broad "
                            "risk-on beta in these standard windows."
                        )
                    )
                ),
                "forbidden_near_neighbor_retry": (
                    "Do not retry by sweeping DIA/MDY return, DIA/MDY relative "
                    "vs SPY, close-location, stock return, stock relative "
                    "strength, volume, ret20/ret60, top-N, hold-day, cooldown, "
                    "or paper notional thresholds on the frozen windows."
                ),
                "new_evidence_required": (
                    "A retry requires materially new PIT evidence that real-"
                    "economy breadth is not broad beta, such as component-level "
                    "DIA/MDY breadth, sector-neutral peer propagation, or closed "
                    "forward rows from a shared default-off adapter."
                ),
            },
            "data_coverage": {
                "dia_mdy_context_missing": context_missing,
                "required_context_tickers": ["DIA", "MDY", "SPY", "QQQ"],
                "observed_result": (
                    "no DIA/MDY context rows in canonical replay"
                    if context_missing
                    else "DIA/MDY context available"
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
            "min_dia_return": MIN_DIA_RETURN,
            "min_mdy_return": MIN_MDY_RETURN,
            "min_spy_return": MIN_SPY_RETURN,
            "min_dia_relative_vs_spy": MIN_DIA_RELATIVE_VS_SPY,
            "min_mdy_relative_vs_spy": MIN_MDY_RELATIVE_VS_SPY,
            "min_dia_close_location": MIN_DIA_CLOSE_LOCATION,
            "min_mdy_close_location": MIN_MDY_CLOSE_LOCATION,
            "min_spy_close_location": MIN_SPY_CLOSE_LOCATION,
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
        "DIA, MDY, SPY, and QQQ daily return/range context plus stock "
        "leadership, liquidity, close-location, volume, ret5/ret20/ret60, "
        "and realized-vol fields. Paper entry is next available open with "
        "existing entry slippage; exit is the close 10 trading days after the "
        "signal with target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "candidate_pool: DIA and MDY leadership versus SPY may identify "
            "real-economy stock leaders before the next sessions fully price "
            "non-megacap risk appetite."
        ),
        "2_history_check": {
            "exp-20260607-016": (
                "IWM risk-appetite tech laggard failed; this uses DIA+MDY "
                "leadership and stock leaders, not laggard catch-up."
            ),
            "exp-20260607-024": (
                "IWM+QQQ broad leadership failed; this tests a different "
                "DIA/MDY real-economy confirmation source."
            ),
            "exp-20260608-003": (
                "IWM breadth thrust failed; this avoids IWM threshold retunes."
            ),
            "exp-20260608-004": (
                "Industry stable leadership was rejected despite positive EV "
                "because drawdown drift exceeded the guardrail; this is "
                "cross-asset real-economy confirmation, not industry stability."
            ),
            "exact_dia_mdy_prior": (
                "No exact DIA+MDY real-economy leadership candidate-pool "
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
            "exp_20260608_006_dia_mdy_real_economy_leadership.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["gate3"]["note"] = (
        "No new core filter or entry rule was added. The DIA/MDY leadership "
        "source is additive default-off paper, so core signals generated/"
        "survived are unchanged from baseline."
    )
    runtime_fields = payload.setdefault("gate2", {}).setdefault("runtime_fields", [])
    for field in ("DIA daily OHLCV", "MDY daily OHLCV"):
        if field not in runtime_fields:
            runtime_fields.insert(3, field)
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Real-econ days | Trades |",
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
                days=scan.get("real_economy_leadership_days", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} DIA/MDY Real-Economy Leadership",
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
            "- Target trades: `{}`".format(
                payload["target_trade_summary"]["total_trade_count"]
            ),
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
                "real_economy_leadership_day_count": payload["context_scan_by_window"][
                    label
                ].get("real_economy_leadership_days"),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": {**payload["calibration"]},
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


def _patch_threshold_module(module: Any) -> None:
    module.EXPERIMENT_ID = EXPERIMENT_ID
    module.STEM = STEM
    module.TRIAL_FAMILY = TRIAL_FAMILY
    module.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    module.CHANGED_VARIABLE = CHANGED_VARIABLE
    module.RULE_VERSION = RULE_VERSION
    module.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    module.HOLD_DAYS = HOLD_DAYS
    module.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    module.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    module.MIN_PRICE = MIN_PRICE
    module.MIN_AVG_DOLLAR_VOLUME_20D = MIN_AVG_DOLLAR_VOLUME_20D
    module.MIN_SIGNAL_RETURN = MIN_SIGNAL_RETURN
    module.MIN_RELATIVE_VS_SPY = MIN_RELATIVE_VS_SPY
    module.MIN_RELATIVE_VS_QQQ = MIN_RELATIVE_VS_QQQ
    module.MIN_CLOSE_LOCATION = MIN_CLOSE_LOCATION
    module.MIN_VOLUME_RATIO_20D = MIN_VOLUME_RATIO_20D
    module.MIN_RET20_EXCESS_SPY = MIN_RET20_EXCESS_SPY
    module.MIN_RET60_EXCESS_SPY = MIN_RET60_EXCESS_SPY
    module.MIN_RET5 = MIN_RET5
    module.MAX_RET5 = MAX_RET5
    module.MAX_REALIZED_VOL_20D = MAX_REALIZED_VOL_20D
    module.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    module.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    module.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    module.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    module.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    module.PREDICTION = PREDICTION
    module.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    module.OUT_DIR = OUT_DIR
    module.OUT_JSON = OUT_JSON
    module.LOG_JSON = LOG_JSON
    module.TICKET_JSON = TICKET_JSON
    module.CARD_MD = CARD_MD
    module.MANIFEST_JSON = MANIFEST_JSON
    module.EXPERIMENT_LOG = EXPERIMENT_LOG
    module.REGISTRY_JSON = REGISTRY_JSON


def _patch_framework() -> None:
    _patch_threshold_module(macro_base)
    _patch_threshold_module(base)
    base._candidate_for_ticker = _candidate_for_ticker

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
