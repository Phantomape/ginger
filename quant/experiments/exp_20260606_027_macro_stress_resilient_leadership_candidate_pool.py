"""exp-20260606-027: macro stress resilient leadership candidate pool.

Replay-only alpha search. This tests one production-visible free-data
candidate source: on official CPI/FOMC/NFP dates where SPY and QQQ sell off
and close weak, admit the two strongest liquid stock leaders that stayed
resilient versus both ETFs as next-open default-off paper candidates with a
fixed 10-trading-day hold.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework
import exp_20260605_032_scheduled_macro_selloff_next_open_risk_action as macro


EXPERIMENT_ID = "exp-20260606-027"
STEM = "macro_stress_resilient_leadership_candidate_pool"
TRIAL_FAMILY = "macro_stress_resilient_leadership_candidate_pool"
TRIAL_VARIANT_ID = "official_macro_stress_resilient_top2_next_open_10d_v1"
CHANGED_VARIABLE = "official_macro_stress_resilient_stock_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = framework.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260606_027_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = REPO_ROOT / "docs" / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 2
SAME_TICKER_COOLDOWN_DAYS = 10

MAX_SPY_STRESS_RETURN = -0.003
MAX_QQQ_STRESS_RETURN = -0.004
MAX_SPY_CLOSE_LOCATION = 0.55
MAX_QQQ_CLOSE_LOCATION = 0.55
MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_SIGNAL_RETURN = -0.002
MIN_RELATIVE_VS_SPY = 0.012
MIN_RELATIVE_VS_QQQ = 0.014
MIN_CLOSE_LOCATION = 0.55
MIN_VOLUME_RATIO_20D = 0.90
MIN_RET20_EXCESS_SPY = -0.01
MIN_RET60_EXCESS_SPY = -0.04
MIN_RET5 = -0.08
MAX_RET5 = 0.10
MAX_REALIZED_VOL_20D = 0.090

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": 0.08,
    "expected_pnl_delta": 1500.0,
    "main_failure_modes": [
        "target_sample_too_small",
        "window_regression",
        "drawdown_drift",
        "broad_pressure_relabeling",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Macro relief stock leadership was accepted in exp-20260606-020, "
        "but adjacent scheduled macro selloff and cross-section pressure "
        "tests produced mixed or rejected evidence. This tests the opposite "
        "official-event state without touching production."
    ),
    "recorded_at": "2026-06-06T21:08:16Z",
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
        "require a shared default-off adapter exposing the same official "
        "CPI/FOMC/NFP calendar, SPY/QQQ stress-day test, sector-known liquid "
        "stock universe, stock resilience fields, same-ticker core-overlap "
        "exclusion, next-open paper entry, 10-trading-day exit, costs, "
        "cooldown, and concentration controls in both replay and daily "
        "production before any report queue, paper ledger, candidate priority, "
        "sizing, watchlist, or order surface could change."
    ),
}

BASE_GATE4 = framework._gate4
BASE_BUILD_PAYLOAD = framework._build_payload
BASE_PERSIST = framework.persist


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _macro_event_map() -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for row in macro.MACRO_EVENTS:
        date_value = str(row.get("date") or "")[:10]
        if not date_value:
            continue
        out.setdefault(date_value, []).append(row)
    return out


MACRO_EVENTS_BY_DATE = _macro_event_map()


def _range_location(row: dict[str, Any]) -> float | None:
    high = framework._value(row, "High")
    low = framework._value(row, "Low")
    close = framework._value(row, "Close")
    if high is None or low is None or close is None or high <= low:
        return None
    return (close - low) / (high - low)


def _stress_context_for_day(
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    signal_date: str,
) -> dict[str, Any] | None:
    events = MACRO_EVENTS_BY_DATE.get(signal_date)
    if not events:
        return None
    spy_rows = snapshot.get("SPY") or []
    qqq_rows = snapshot.get("QQQ") or []
    spy_idx = indices.get("SPY", {}).get(signal_date)
    qqq_idx = indices.get("QQQ", {}).get(signal_date)
    if spy_idx is None or qqq_idx is None:
        return {
            "date": signal_date,
            "passed": False,
            "reason": "missing_spy_or_qqq_event_row",
            "events": events,
        }
    spy_return = framework._daily_return(spy_rows, spy_idx)
    qqq_return = framework._daily_return(qqq_rows, qqq_idx)
    spy_close_location = _range_location(spy_rows[spy_idx])
    qqq_close_location = _range_location(qqq_rows[qqq_idx])
    context = {
        "date": signal_date,
        "events": events,
        "event_families": sorted({str(row.get("family") or "") for row in events}),
        "spy_return": framework._round(spy_return, 6),
        "qqq_return": framework._round(qqq_return, 6),
        "spy_close_location": framework._round(spy_close_location, 6),
        "qqq_close_location": framework._round(qqq_close_location, 6),
        "max_spy_stress_return": MAX_SPY_STRESS_RETURN,
        "max_qqq_stress_return": MAX_QQQ_STRESS_RETURN,
        "max_spy_close_location": MAX_SPY_CLOSE_LOCATION,
        "max_qqq_close_location": MAX_QQQ_CLOSE_LOCATION,
    }
    if spy_return is None or qqq_return is None:
        return {**context, "passed": False, "reason": "missing_daily_return"}
    if spy_close_location is None or qqq_close_location is None:
        return {**context, "passed": False, "reason": "missing_close_location"}
    if spy_return > MAX_SPY_STRESS_RETURN:
        return {**context, "passed": False, "reason": "spy_stress_return_not_low_enough"}
    if qqq_return > MAX_QQQ_STRESS_RETURN:
        return {**context, "passed": False, "reason": "qqq_stress_return_not_low_enough"}
    if spy_close_location > MAX_SPY_CLOSE_LOCATION:
        return {**context, "passed": False, "reason": "spy_close_location_not_weak"}
    if qqq_close_location > MAX_QQQ_CLOSE_LOCATION:
        return {**context, "passed": False, "reason": "qqq_close_location_not_weak"}
    return {**context, "passed": True, "reason": "official_macro_stress_day_passed"}


def _candidate_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    context: dict[str, Any],
) -> dict[str, Any] | None:
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    qqq_rows = snapshot.get("QQQ") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    qqq_idx = indices.get("QQQ", {}).get(signal_date)
    if idx is None or spy_idx is None or qqq_idx is None:
        return None
    if idx < 60 or spy_idx < 60 or qqq_idx < 60 or idx + HOLD_DAYS >= len(rows):
        return None
    close = framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    signal_return = framework._daily_return(rows, idx)
    spy_return = framework._daily_return(spy_rows, spy_idx)
    qqq_return = framework._daily_return(qqq_rows, qqq_idx)
    close_location = framework._close_location(rows[idx])
    volume_ratio = framework._volume_ratio(rows, idx)
    ret5 = framework._ret(rows, idx, 5)
    ret20 = framework._ret(rows, idx, 20)
    ret60 = framework._ret(rows, idx, 60)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = framework._ret(spy_rows, spy_idx, 60)
    realized_vol20 = framework._realized_vol(rows, idx, 20)
    required = [
        signal_return,
        spy_return,
        qqq_return,
        close_location,
        volume_ratio,
        ret5,
        ret20,
        ret60,
        spy_ret20,
        spy_ret60,
        realized_vol20,
    ]
    if any(value is None for value in required):
        return None
    assert signal_return is not None
    assert spy_return is not None
    assert qqq_return is not None
    assert close_location is not None
    assert volume_ratio is not None
    assert ret5 is not None
    assert ret20 is not None
    assert ret60 is not None
    assert spy_ret20 is not None
    assert spy_ret60 is not None
    assert realized_vol20 is not None
    relative_vs_spy = signal_return - spy_return
    relative_vs_qqq = signal_return - qqq_return
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    if signal_return < MIN_SIGNAL_RETURN:
        return None
    if relative_vs_spy < MIN_RELATIVE_VS_SPY:
        return None
    if relative_vs_qqq < MIN_RELATIVE_VS_QQQ:
        return None
    if close_location < MIN_CLOSE_LOCATION:
        return None
    if volume_ratio < MIN_VOLUME_RATIO_20D:
        return None
    if ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_RET60_EXCESS_SPY:
        return None
    if ret5 < MIN_RET5 or ret5 > MAX_RET5:
        return None
    if realized_vol20 > MAX_REALIZED_VOL_20D:
        return None

    sector_meta = sector_entries[ticker]
    liquidity_score = math.log10(max(adv20, 1.0) / 1_000_000.0)
    score = (
        2.50 * relative_vs_spy
        + 2.00 * relative_vs_qqq
        + 0.65 * ret20_excess_spy
        + 0.25 * ret60_excess_spy
        + 0.35 * close_location
        + 0.08 * min(volume_ratio, 3.0)
        + 0.04 * liquidity_score
        - 0.55 * realized_vol20
        - 0.25 * max(ret5, 0.0)
    )
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "MACRO_STRESS_RESILIENT_LEADERSHIP_PAPER",
        "candidate_score": round(score, 6),
        "candidate_signal_day_return": round(signal_return, 6),
        "candidate_spy_signal_day_return": round(spy_return, 6),
        "candidate_qqq_signal_day_return": round(qqq_return, 6),
        "candidate_relative_vs_spy": round(relative_vs_spy, 6),
        "candidate_relative_vs_qqq": round(relative_vs_qqq, 6),
        "candidate_close_location": round(close_location, 6),
        "candidate_volume_ratio_20d": round(volume_ratio, 6),
        "candidate_avg_dollar_volume_20d": round(adv20, 2),
        "candidate_ret5": round(ret5, 6),
        "candidate_ret20": round(ret20, 6),
        "candidate_spy_ret20": round(spy_ret20, 6),
        "candidate_ret20_excess_spy": round(ret20_excess_spy, 6),
        "candidate_ret60": round(ret60, 6),
        "candidate_spy_ret60": round(spy_ret60, 6),
        "candidate_ret60_excess_spy": round(ret60_excess_spy, 6),
        "candidate_realized_vol_20d": round(realized_vol20, 6),
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "sector_coverage_status": sector_meta.get("sector_coverage_status"),
        "macro_stress_context": context,
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
    dates = [
        date_value
        for date_value in framework.shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    candidates: list[dict[str, Any]] = []
    stress_contexts: list[dict[str, Any]] = []
    scan = {
        "scanned_trading_days": len(dates),
        "official_macro_event_trading_days": 0,
        "macro_stress_days": 0,
        "non_stress_macro_days": 0,
        "days_with_raw_macro_stress_candidates": 0,
        "raw_macro_stress_candidates": 0,
    }
    for signal_date in dates:
        context = _stress_context_for_day(snapshot, indices, signal_date)
        if context is None:
            continue
        scan["official_macro_event_trading_days"] += 1
        if not context.get("passed"):
            scan["non_stress_macro_days"] += 1
            stress_contexts.append(context)
            continue
        scan["macro_stress_days"] += 1
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
            stress_contexts.append({**context, "raw_candidate_count": 0})
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
        scan["days_with_raw_macro_stress_candidates"] += 1
        scan["raw_macro_stress_candidates"] += len(day_rows)
        stress_contexts.append(
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
            "macro_event_families": ["CPI", "FOMC", "NFP"],
            "max_spy_stress_return": MAX_SPY_STRESS_RETURN,
            "max_qqq_stress_return": MAX_QQQ_STRESS_RETURN,
            "max_spy_close_location": MAX_SPY_CLOSE_LOCATION,
            "max_qqq_close_location": MAX_QQQ_CLOSE_LOCATION,
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
    return candidates, stress_contexts, scan


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
        "positive_replay_lead_not_promoted_macro_stress_resilient_leadership_candidate_pool"
        if gate["passed"]
        else "rejected_macro_stress_resilient_leadership_candidate_pool"
    )
    gate["target_trade_count_min"] = MIN_TARGET_TRADES
    gate["target_window_count_min"] = MIN_TARGET_WINDOWS
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
    }
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Official CPI/FOMC/NFP stress days where SPY and QQQ both "
                "sell off and close weak may identify resilient liquid stock "
                "leaders with cleaner next-open continuation than generic "
                "broad-pressure OHLCV filters."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "free_official_macro_calendar_plus_ohlcv_candidate_pool",
            "new_evidence_type": "official_macro_stress_state_plus_stock_resilience",
            "nearby_prior_experiments": [
                "exp-20260606-019",
                "exp-20260606-020",
                "exp-20260605-033",
                "exp-20260605-032",
                "exp-20260605-030",
            ],
            "prior_trial_count": 4,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "calibration": calibration,
            "production_impact": PRODUCTION_IMPACT,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that macro stress creates "
                "unstable relief/reversal dynamics rather than continuation, "
                "or that official-event stress is just a sparse relabeling of "
                "the rejected broad pressure-resilience setup. A retry would "
                "need materially new PIT macro surprise/consensus or forward "
                "replacement-value evidence, not threshold, top-N, hold-day, "
                "cooldown, or notional retuning."
            ),
        }
    )
    payload["backtest_protocol"] = {
        "source": (
            "docs/backtesting.md canonical three-window core replay plus "
            "replay-only official macro stress default-off paper overlay"
        ),
        "windows": framework.WINDOWS,
        "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
        "macro_calendar_source": "quant/experiments/exp_20260605_032_scheduled_macro_selloff_next_open_risk_action.py",
        "replay_llm": False,
        "replay_news": False,
        "REGIME_AWARE_EXIT": True,
        "execution_model": (
            "Signal uses only official macro-event dates and close-of-day "
            "OHLCV available on signal date. Paper entry is next available "
            "open with existing entry slippage; exit is the close 10 trading "
            "days after the signal with target-side sell slippage and "
            "ROUND_TRIP_COST_PCT."
        ),
    }
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "official_macro_event_families": ["CPI", "FOMC", "NFP"],
        "max_spy_stress_return": MAX_SPY_STRESS_RETURN,
        "max_qqq_stress_return": MAX_QQQ_STRESS_RETURN,
        "max_spy_close_location": MAX_SPY_CLOSE_LOCATION,
        "max_qqq_close_location": MAX_QQQ_CLOSE_LOCATION,
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
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: official macro stress days can force "
            "capital into resilient individual leaders; those leaders may "
            "continue after the next open if the stress day separated true "
            "relative demand from broad beta."
        ),
        "2_history_check": {
            "exp-20260606-019/020": (
                "Official macro relief stock leadership passed as a replay "
                "lead and then shared default-off adapter. This test flips "
                "only the official-event state to stress."
            ),
            "exp-20260605-033": (
                "Broad cross-section pressure resilience was rejected due "
                "aggregate and window issues; this test restricts pressure "
                "to official macro event days to avoid generic OHLCV stress."
            ),
            "exp-20260605-030/032": (
                "NFP and scheduled macro selloff ETF beta actions were too "
                "thin or weak. This test uses stock candidate-pool resilience, "
                "not ETF risk allocation."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Aggregate EV/PnL "
            "must improve, no EV/PnL regression window, target sample >=20 "
            "across all 3 windows, survival >=5%, drawdown drift <=0.5pp, and "
            "concentration guard must pass."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260606_027_macro_stress_resilient_leadership_candidate_pool.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["decision"] = payload["gate4"]["decision"]
    payload["status"] = "accepted" if payload["gate4"]["passed"] else "rejected"
    payload["interpretation"] = (
        "The official macro stress resilient leadership candidate pool cleared "
        "Gate 4 as a replay-only/default-off lead, but no production surface "
        "was promoted."
        if payload["gate4"]["passed"]
        else (
            "The official macro stress resilient leadership candidate pool did "
            "not clear Gate 4. Do not promote or retune this fixed macro-stress "
            "stock resilience definition on the frozen windows without "
            "materially new PIT macro surprise/consensus data or forward "
            "replacement-value evidence."
        )
    )
    payload["rejection_reason"] = (
        None if payload["gate4"]["passed"] else "; ".join(payload["gate4"]["failed_reasons"])
    )
    payload["next_evidence_needed"] = (
        "A retry needs a real PIT macro-surprise/consensus field or closed "
        "forward replacement-value rows; do not simply retune stress return "
        "thresholds, close-location thresholds, top-N, hold days, cooldown, "
        "or paper notional."
    )
    payload["expected_value_score_delta"] = aggregate["expected_value_score_delta_sum"]
    payload["total_pnl_delta"] = aggregate["total_pnl_delta_sum"]
    payload["macro_stress_contexts_by_window"] = payload.get("pressure_contexts_by_window", {})
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(DOC_TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(ARTIFACT_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Macro stress days | Trades |",
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
                days=scan.get("macro_stress_days", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Macro Stress Resilient Leadership Candidate Pool",
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
        "mechanism_family": "free_official_macro_calendar_plus_ohlcv_candidate_pool",
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
                "macro_stress_day_count": payload["context_scan_by_window"][label].get(
                    "macro_stress_days"
                ),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": {**payload["calibration"]},
        "production_impact": PRODUCTION_IMPACT,
        "negative_reflection": payload["negative_reflection"],
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
            _repo_rel(DOC_TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(ARTIFACT_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(DOC_TICKET_JSON): framework._sha256(DOC_TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
            _repo_rel(ARTIFACT_MD): framework._sha256(ARTIFACT_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    BASE_PERSIST(payload)
    card = _build_card(payload)
    framework._write_text(ARTIFACT_MD, card)
    if TICKET_JSON.exists():
        ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
        framework._write_json(DOC_TICKET_JSON, ticket)
    _write_manifest(payload)


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
    framework._write_manifest = _write_manifest
    framework.persist = persist


_patch_framework()


def main() -> None:
    framework.main()


if __name__ == "__main__":
    main()
