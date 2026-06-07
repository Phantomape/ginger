"""exp-20260607-016: QQQ/IWM risk-appetite tech laggard repair.

Replay-only alpha search. It tests one free-OHLCV candidate source:
when QQQ is firm and IWM outperforms SPY, select one liquid Technology or
semiconductor-related laggard that is reclaiming relative strength at the close
for a fixed next-open, 10-trading-day default-off paper hold.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import math
from pathlib import Path
from statistics import median
from typing import Any

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework


EXPERIMENT_ID = "exp-20260607-016"
STEM = "risk_appetite_tech_laggard_repair"
TRIAL_FAMILY = "risk_appetite_tech_laggard_repair_candidate_pool"
TRIAL_VARIANT_ID = "qqq_iwm_confirmed_tech_laggard_repair_top1_next_open_10d_v1"
CHANGED_VARIABLE = "risk_appetite_tech_laggard_repair_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = framework.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260607_016_risk_appetite_tech_laggard_repair.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
SCRIPT_PATH = Path(__file__)

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 15

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
GROUP_LOOKBACK_DAYS = 20
RECENT_LOOKBACK_DAYS = 5
TREND_LOOKBACK_DAYS = 60

MIN_TECH_LIQUID_COUNT = 45
MIN_QQQ_SIGNAL_RETURN = 0.002
MIN_QQQ_RET5 = -0.006
MIN_QQQ_CLOSE_LOCATION = 0.55
MIN_SPY_SIGNAL_RETURN = -0.006
MIN_IWM_RELATIVE_VS_SPY = 0.0025
MIN_IWM_RET5_EXCESS_SPY = -0.006
MIN_TECH_MEDIAN_RET20_EXCESS_SPY = -0.004
MIN_TECH_RET20_POSITIVE_FRACTION = 0.44

MIN_TECH_LAG_20D = 0.045
MAX_TECH_LAG_20D = 0.190
MIN_CANDIDATE_RET20_EXCESS_SPY = -0.110
MIN_CANDIDATE_RET60_EXCESS_SPY = -0.075
MIN_CANDIDATE_RET5_EXCESS_SPY = -0.020
MIN_SIGNAL_RETURN = 0.003
MAX_SIGNAL_RETURN = 0.085
MIN_SIGNAL_RELATIVE_VS_SPY = 0.005
MIN_SIGNAL_RELATIVE_VS_QQQ = -0.018
MIN_CLOSE_LOCATION = 0.58
MIN_VOLUME_RATIO_20D = 0.70
MAX_VOLUME_RATIO_20D = 2.90
MAX_REALIZED_VOL_20D = 0.090

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

TECH_INDUSTRY_KEYWORDS = (
    "semiconductor",
    "software",
    "information technology",
    "communication equipment",
    "computer hardware",
    "consumer electronics",
    "electronic components",
    "electronic gaming",
    "scientific",
    "solar",
)

PREDICTION = {
    "success_probability": 0.12,
    "expected_ev_delta": 0.12,
    "expected_pnl_delta": 2500.0,
    "main_failure_modes": [
        "near_neighbor_to_industry_laggard",
        "old_thin_regression",
        "small_sample",
        "tech_beta_chase",
        "drawdown_drift",
    ],
    "confidence_reason": (
        "The test uses only free OHLCV and available QQQ/IWM/SPY context, but "
        "recent industry/OHLCV relation variants failed old_thin or sample "
        "guards, so prior confidence is intentionally low."
    ),
    "recorded_at": "2026-06-07T14:08:54Z",
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
        "still require a shared default-off adapter that computes the same "
        "Technology/semiconductor universe, QQQ/IWM/SPY risk-appetite fields, "
        "20-day lag, same-day reclaim, next-open paper entry, 10-trading-day "
        "exit, costs, cooldown, core-overlap exclusion, and concentration "
        "controls in both replay and daily production before any report queue, "
        "paper ledger, candidate priority, sizing, watchlist, or order surface "
        "could change."
    ),
}

BASE_LOAD_SECTOR_ENTRIES = framework._load_sector_entries
BASE_LOAD_WINDOW_SNAPSHOT = framework._load_window_snapshot
BASE_GATE4 = framework._gate4
BASE_BUILD_PAYLOAD = framework._build_payload
BASE_BUILD_LOG_RECORD = framework._build_log_record


def _repo_rel(path: Path | str) -> str:
    return framework._repo_rel(path)


def _load_sector_entries() -> dict[str, dict[str, Any]]:
    entries = BASE_LOAD_SECTOR_ENTRIES()
    out: dict[str, dict[str, Any]] = {}
    for ticker, meta in entries.items():
        sector = str(meta.get("sector") or "")
        industry = str(meta.get("industry") or "")
        industry_l = industry.lower()
        is_tech = sector == "Technology"
        is_semiconductor_related = any(keyword in industry_l for keyword in TECH_INDUSTRY_KEYWORDS)
        if is_tech or is_semiconductor_related:
            out[ticker] = meta
    return out


def _load_window_snapshot(
    *,
    cfg: dict[str, str],
    eligible_tickers: set[str],
) -> dict[str, list[dict[str, Any]]]:
    return BASE_LOAD_WINDOW_SNAPSHOT(
        cfg=cfg,
        eligible_tickers=set(eligible_tickers) | {"IWM"},
    )


def _risk_context_for_day(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    signal_date: str,
) -> dict[str, Any] | None:
    spy_rows = snapshot.get("SPY") or []
    qqq_rows = snapshot.get("QQQ") or []
    iwm_rows = snapshot.get("IWM") or []
    spy_idx = indices.get("SPY", {}).get(signal_date)
    qqq_idx = indices.get("QQQ", {}).get(signal_date)
    iwm_idx = indices.get("IWM", {}).get(signal_date)
    if spy_idx is None or qqq_idx is None or iwm_idx is None:
        return None
    if min(spy_idx, qqq_idx, iwm_idx) < max(GROUP_LOOKBACK_DAYS, RECENT_LOOKBACK_DAYS):
        return None

    spy_signal = framework._daily_return(spy_rows, spy_idx)
    qqq_signal = framework._daily_return(qqq_rows, qqq_idx)
    iwm_signal = framework._daily_return(iwm_rows, iwm_idx)
    qqq_ret5 = framework._ret(qqq_rows, qqq_idx, RECENT_LOOKBACK_DAYS)
    spy_ret5 = framework._ret(spy_rows, spy_idx, RECENT_LOOKBACK_DAYS)
    iwm_ret5 = framework._ret(iwm_rows, iwm_idx, RECENT_LOOKBACK_DAYS)
    qqq_close_location = framework._close_location(qqq_rows[qqq_idx])
    required = [
        spy_signal,
        qqq_signal,
        iwm_signal,
        qqq_ret5,
        spy_ret5,
        iwm_ret5,
        qqq_close_location,
    ]
    if any(value is None for value in required):
        return None

    assert spy_signal is not None
    assert qqq_signal is not None
    assert iwm_signal is not None
    assert qqq_ret5 is not None
    assert spy_ret5 is not None
    assert iwm_ret5 is not None
    assert qqq_close_location is not None

    tech_returns: list[float] = []
    tech_ret20_excess: list[float] = []
    spy_ret20 = framework._ret(spy_rows, spy_idx, GROUP_LOOKBACK_DAYS)
    if spy_ret20 is None:
        return None
    for ticker in sector_entries:
        rows = snapshot.get(ticker) or []
        idx = indices.get(ticker, {}).get(signal_date)
        if idx is None or idx < GROUP_LOOKBACK_DAYS:
            continue
        close = framework._value(rows[idx], "Close")
        if close is None or close < MIN_PRICE:
            continue
        adv20 = framework._avg_dollar_volume(rows, idx)
        if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
            continue
        daily = framework._daily_return(rows, idx)
        ret20 = framework._ret(rows, idx, GROUP_LOOKBACK_DAYS)
        if daily is not None:
            tech_returns.append(daily)
        if ret20 is not None:
            tech_ret20_excess.append(ret20 - spy_ret20)

    if len(tech_ret20_excess) < MIN_TECH_LIQUID_COUNT:
        return None

    tech_median_ret20_excess = median(tech_ret20_excess)
    tech_positive_fraction = sum(value > 0.0 for value in tech_ret20_excess) / len(
        tech_ret20_excess
    )
    tech_median_signal_return = median(tech_returns) if tech_returns else None
    iwm_relative_vs_spy = iwm_signal - spy_signal
    iwm_ret5_excess_spy = iwm_ret5 - spy_ret5
    passed = (
        qqq_signal >= MIN_QQQ_SIGNAL_RETURN
        and qqq_ret5 >= MIN_QQQ_RET5
        and qqq_close_location >= MIN_QQQ_CLOSE_LOCATION
        and spy_signal >= MIN_SPY_SIGNAL_RETURN
        and iwm_relative_vs_spy >= MIN_IWM_RELATIVE_VS_SPY
        and iwm_ret5_excess_spy >= MIN_IWM_RET5_EXCESS_SPY
        and tech_median_ret20_excess >= MIN_TECH_MEDIAN_RET20_EXCESS_SPY
        and tech_positive_fraction >= MIN_TECH_RET20_POSITIVE_FRACTION
    )
    return {
        "date": signal_date,
        "passed": passed,
        "tech_liquid_count": len(tech_ret20_excess),
        "spy_signal_day_return": round(spy_signal, 6),
        "qqq_signal_day_return": round(qqq_signal, 6),
        "iwm_signal_day_return": round(iwm_signal, 6),
        "iwm_relative_vs_spy": round(iwm_relative_vs_spy, 6),
        "qqq_ret5": round(qqq_ret5, 6),
        "iwm_ret5_excess_spy": round(iwm_ret5_excess_spy, 6),
        "qqq_close_location": round(qqq_close_location, 6),
        "tech_median_signal_return": (
            None if tech_median_signal_return is None else round(tech_median_signal_return, 6)
        ),
        "tech_median_ret20_excess_spy": round(tech_median_ret20_excess, 6),
        "tech_ret20_positive_fraction": round(tech_positive_fraction, 6),
        "rule_version": RULE_VERSION,
    }


def _ticker_day_metrics(
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
    min_idx = max(TREND_LOOKBACK_DAYS, GROUP_LOOKBACK_DAYS, RECENT_LOOKBACK_DAYS, 20)
    if idx is None or spy_idx is None or qqq_idx is None:
        return None
    if idx < min_idx or spy_idx < min_idx or qqq_idx < min_idx:
        return None
    if idx + HOLD_DAYS >= len(rows):
        return None

    close = framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None

    ret20 = framework._ret(rows, idx, GROUP_LOOKBACK_DAYS)
    spy_ret20 = framework._ret(spy_rows, spy_idx, GROUP_LOOKBACK_DAYS)
    ret5 = framework._ret(rows, idx, RECENT_LOOKBACK_DAYS)
    spy_ret5 = framework._ret(spy_rows, spy_idx, RECENT_LOOKBACK_DAYS)
    ret60 = framework._ret(rows, idx, TREND_LOOKBACK_DAYS)
    spy_ret60 = framework._ret(spy_rows, spy_idx, TREND_LOOKBACK_DAYS)
    signal_return = framework._daily_return(rows, idx)
    spy_signal_return = framework._daily_return(spy_rows, spy_idx)
    qqq_signal_return = framework._daily_return(qqq_rows, qqq_idx)
    close_location = framework._close_location(rows[idx])
    volume_ratio = framework._volume_ratio(rows, idx)
    realized_vol20 = framework._realized_vol(rows, idx)
    required = [
        ret20,
        spy_ret20,
        ret5,
        spy_ret5,
        ret60,
        spy_ret60,
        signal_return,
        spy_signal_return,
        qqq_signal_return,
        close_location,
        volume_ratio,
        realized_vol20,
    ]
    if any(value is None for value in required):
        return None

    assert ret20 is not None
    assert spy_ret20 is not None
    assert ret5 is not None
    assert spy_ret5 is not None
    assert ret60 is not None
    assert spy_ret60 is not None
    assert signal_return is not None
    assert spy_signal_return is not None
    assert qqq_signal_return is not None
    assert close_location is not None
    assert volume_ratio is not None
    assert realized_vol20 is not None

    meta = sector_entries[ticker]
    return {
        "date": signal_date,
        "ticker": ticker,
        "sector": meta.get("sector"),
        "industry": meta.get("industry"),
        "sector_coverage_status": meta.get("sector_coverage_status"),
        "close": close,
        "adv20": adv20,
        "ret20_excess_spy": ret20 - spy_ret20,
        "ret5_excess_spy": ret5 - spy_ret5,
        "ret60_excess_spy": ret60 - spy_ret60,
        "signal_return": signal_return,
        "signal_relative_vs_spy": signal_return - spy_signal_return,
        "signal_relative_vs_qqq": signal_return - qqq_signal_return,
        "close_location": close_location,
        "volume_ratio_20d": volume_ratio,
        "realized_vol_20d": realized_vol20,
        "tech_median_ret20_excess_spy": context["tech_median_ret20_excess_spy"],
        "iwm_relative_vs_spy": context["iwm_relative_vs_spy"],
        "qqq_signal_day_return": context["qqq_signal_day_return"],
    }


def _candidate_from_metrics(metrics: dict[str, Any]) -> dict[str, Any] | None:
    tech_lag_20d = metrics["tech_median_ret20_excess_spy"] - metrics["ret20_excess_spy"]
    if tech_lag_20d < MIN_TECH_LAG_20D or tech_lag_20d > MAX_TECH_LAG_20D:
        return None
    if metrics["ret20_excess_spy"] < MIN_CANDIDATE_RET20_EXCESS_SPY:
        return None
    if metrics["ret60_excess_spy"] < MIN_CANDIDATE_RET60_EXCESS_SPY:
        return None
    if metrics["ret5_excess_spy"] < MIN_CANDIDATE_RET5_EXCESS_SPY:
        return None
    if metrics["signal_return"] < MIN_SIGNAL_RETURN:
        return None
    if metrics["signal_return"] > MAX_SIGNAL_RETURN:
        return None
    if metrics["signal_relative_vs_spy"] < MIN_SIGNAL_RELATIVE_VS_SPY:
        return None
    if metrics["signal_relative_vs_qqq"] < MIN_SIGNAL_RELATIVE_VS_QQQ:
        return None
    if metrics["close_location"] < MIN_CLOSE_LOCATION:
        return None
    if metrics["volume_ratio_20d"] < MIN_VOLUME_RATIO_20D:
        return None
    if metrics["volume_ratio_20d"] > MAX_VOLUME_RATIO_20D:
        return None
    if metrics["realized_vol_20d"] > MAX_REALIZED_VOL_20D:
        return None

    score = (
        1.65 * tech_lag_20d
        + 1.45 * metrics["signal_relative_vs_spy"]
        + 0.65 * metrics["signal_relative_vs_qqq"]
        + 0.75 * metrics["iwm_relative_vs_spy"]
        + 0.60 * metrics["qqq_signal_day_return"]
        + 0.48 * metrics["close_location"]
        + 0.20 * metrics["ret60_excess_spy"]
        + 0.04 * math.log10(max(metrics["adv20"], 1.0) / 1_000_000.0)
        - 0.58 * metrics["realized_vol_20d"]
        - 0.04 * abs(metrics["volume_ratio_20d"] - 1.15)
    )
    return {
        "date": metrics["date"],
        "ticker": metrics["ticker"],
        "source": "RISK_APPETITE_TECH_LAGGARD_REPAIR_PAPER",
        "candidate_score": round(score, 6),
        "candidate_tech_lag_20d": round(tech_lag_20d, 6),
        "candidate_ret20_excess_spy": round(metrics["ret20_excess_spy"], 6),
        "candidate_ret5_excess_spy": round(metrics["ret5_excess_spy"], 6),
        "candidate_ret60_excess_spy": round(metrics["ret60_excess_spy"], 6),
        "candidate_signal_day_return": round(metrics["signal_return"], 6),
        "candidate_signal_relative_vs_spy": round(metrics["signal_relative_vs_spy"], 6),
        "candidate_signal_relative_vs_qqq": round(metrics["signal_relative_vs_qqq"], 6),
        "candidate_close_location": round(metrics["close_location"], 6),
        "candidate_volume_ratio_20d": round(metrics["volume_ratio_20d"], 6),
        "candidate_realized_vol_20d": round(metrics["realized_vol_20d"], 6),
        "candidate_avg_dollar_volume_20d": round(metrics["adv20"], 2),
        "risk_appetite_context": {
            "qqq_signal_day_return": metrics["qqq_signal_day_return"],
            "iwm_relative_vs_spy": metrics["iwm_relative_vs_spy"],
            "tech_median_ret20_excess_spy": metrics["tech_median_ret20_excess_spy"],
            "rule_version": RULE_VERSION,
        },
        "sector": metrics.get("sector"),
        "industry": metrics.get("industry"),
        "sector_coverage_status": metrics.get("sector_coverage_status"),
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
    risk_contexts: list[dict[str, Any]] = []
    context_scan = {
        "scanned_trading_days": len(dates),
        "risk_appetite_days": 0,
        "non_risk_appetite_days": 0,
        "missing_context_days": 0,
        "raw_candidate_rows": 0,
        "unique_candidate_tickers": 0,
        "rule_version": RULE_VERSION,
    }
    candidate_tickers: set[str] = set()
    for signal_date in dates:
        context = _risk_context_for_day(
            snapshot=snapshot,
            indices=indices,
            sector_entries=sector_entries,
            signal_date=signal_date,
        )
        if context is None:
            context_scan["missing_context_days"] += 1
            continue
        if not context["passed"]:
            context_scan["non_risk_appetite_days"] += 1
            continue
        context_scan["risk_appetite_days"] += 1
        risk_contexts.append(context)
        day_rows: list[dict[str, Any]] = []
        for ticker in sector_entries:
            metrics = _ticker_day_metrics(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                context=context,
            )
            if metrics is None:
                continue
            row = _candidate_from_metrics(metrics)
            if row is None:
                continue
            ab_entries = entries_by_date.get(signal_date, [])
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = any(
                trade.get("ticker") == ticker for trade in ab_entries
            )
            day_rows.append(row)
            candidate_tickers.add(ticker)
        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_score"]),
                -float(row["candidate_tech_lag_20d"]),
                -float(row["candidate_signal_relative_vs_spy"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        context_scan["raw_candidate_rows"] += len(day_rows)
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["candidate_tech_lag_20d"]),
            -float(row["candidate_signal_relative_vs_spy"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            row["ticker"],
        )
    )
    context_scan.update(
        {
            "unique_candidate_tickers": len(candidate_tickers),
            "min_tech_liquid_count": MIN_TECH_LIQUID_COUNT,
            "min_qqq_signal_return": MIN_QQQ_SIGNAL_RETURN,
            "min_iwm_relative_vs_spy": MIN_IWM_RELATIVE_VS_SPY,
            "min_tech_lag_20d": MIN_TECH_LAG_20D,
            "max_tech_lag_20d": MAX_TECH_LAG_20D,
        }
    )
    return candidates, risk_contexts, context_scan


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
    gate["decision"] = (
        "positive_replay_lead_not_promoted_risk_appetite_tech_laggard_repair"
        if gate["passed"]
        else "rejected_risk_appetite_tech_laggard_repair_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    passed = bool(gate4["passed"])
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "When QQQ is firm and IWM outperforms SPY, broad risk appetite "
                "may pull forward delayed repair in liquid Technology and "
                "semiconductor-related laggards that are reclaiming relative "
                "strength into the close."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
            "new_evidence_type": "free_ohlcv_qqq_iwm_confirmed_tech_laggard_repair",
            "nearby_prior_experiments": [
                "exp-20260607-007",
                "exp-20260607-008",
                "exp-20260607-010",
                "exp-20260607-014",
                "exp-20260607-015",
            ],
            "prior_trial_count": 5,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "decision": gate4["decision"],
            "status": "positive_replay_lead_not_promoted" if passed else "rejected",
            "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
            "total_pnl_delta": aggregate["total_pnl_delta_sum"],
            "interpretation": (
                "The QQQ/IWM risk-appetite tech laggard source cleared Gate 4 "
                "as a replay-only/default-off lead, but no production surface "
                "was promoted."
                if passed
                else (
                    "The QQQ/IWM risk-appetite tech laggard source did not "
                    "clear Gate 4. Do not promote it or answer by retuning "
                    "QQQ/IWM thresholds, tech lag bands, reclaim, liquidity, "
                    "volatility, hold-day, cooldown, top-N, or notional on "
                    "these frozen windows."
                )
            ),
            "negative_reflection": (
                "If rejected, the likely reason is that QQQ/IWM confirmation "
                "is still mostly beta/risk-on timing, while liquid tech "
                "laggards are already repriced by next-open execution or "
                "remain weak for fundamental reasons. A retry needs a new PIT "
                "state field or forward replacement rows, not threshold edits."
            ),
            "post_run_reflection": {
                "why_result_happened": (
                    "The source produced positive replacement value in all "
                    "three canonical windows without breaching drawdown, "
                    "survival, sample, or concentration guardrails, suggesting "
                    "QQQ/IWM risk appetite plus delayed tech repair captured a "
                    "distinct rotation relation."
                    if passed
                    else (
                        "The source failed Gate 4 because at least one "
                        "canonical acceptance guard failed. That means the "
                        "QQQ/IWM risk-on context did not reliably separate "
                        "healthy delayed tech repair from beta chase or weak "
                        "laggards after next-open entry, slippage, costs, and "
                        "the fixed 10-day exit."
                    )
                ),
                "forbidden_near_neighbor_retry": (
                    "Do not retry by sweeping QQQ return/close-location, "
                    "IWM-vs-SPY, tech median, tech lag, signal-day reclaim, "
                    "volume, volatility, hold-day, top-N, cooldown, or paper "
                    "notional thresholds on these frozen windows."
                ),
                "new_evidence_required": (
                    "A retry needs materially new PIT evidence, such as "
                    "stock-level duration/beta, analyst estimate revision, "
                    "options/borrow/ownership context with full window "
                    "coverage, or closed forward replacement rows from a "
                    "shared default-off adapter."
                ),
            },
            "next_evidence_needed": (
                "Use materially new PIT context or forward shared-adapter "
                "replacement rows before revisiting risk-appetite tech "
                "laggard repair."
            ),
            "related_files": [
                _repo_rel(SCRIPT_PATH),
                _repo_rel(OUT_JSON),
                _repo_rel(LOG_JSON),
                _repo_rel(TICKET_JSON),
                _repo_rel(CARD_MD),
                _repo_rel(MANIFEST_JSON),
                _repo_rel(EXPERIMENT_LOG),
                _repo_rel(REGISTRY_JSON),
            ],
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "group_lookback_days": GROUP_LOOKBACK_DAYS,
        "recent_lookback_days": RECENT_LOOKBACK_DAYS,
        "trend_lookback_days": TREND_LOOKBACK_DAYS,
        "min_tech_liquid_count": MIN_TECH_LIQUID_COUNT,
        "min_qqq_signal_return": MIN_QQQ_SIGNAL_RETURN,
        "min_qqq_ret5": MIN_QQQ_RET5,
        "min_qqq_close_location": MIN_QQQ_CLOSE_LOCATION,
        "min_spy_signal_return": MIN_SPY_SIGNAL_RETURN,
        "min_iwm_relative_vs_spy": MIN_IWM_RELATIVE_VS_SPY,
        "min_iwm_ret5_excess_spy": MIN_IWM_RET5_EXCESS_SPY,
        "min_tech_median_ret20_excess_spy": MIN_TECH_MEDIAN_RET20_EXCESS_SPY,
        "min_tech_ret20_positive_fraction": MIN_TECH_RET20_POSITIVE_FRACTION,
        "min_tech_lag_20d": MIN_TECH_LAG_20D,
        "max_tech_lag_20d": MAX_TECH_LAG_20D,
        "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
        "min_candidate_ret60_excess_spy": MIN_CANDIDATE_RET60_EXCESS_SPY,
        "min_candidate_ret5_excess_spy": MIN_CANDIDATE_RET5_EXCESS_SPY,
        "min_signal_return": MIN_SIGNAL_RETURN,
        "max_signal_return": MAX_SIGNAL_RETURN,
        "min_signal_relative_vs_spy": MIN_SIGNAL_RELATIVE_VS_SPY,
        "min_signal_relative_vs_qqq": MIN_SIGNAL_RELATIVE_VS_QQQ,
        "min_close_location": MIN_CLOSE_LOCATION,
        "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
        "max_volume_ratio_20d": MAX_VOLUME_RATIO_20D,
        "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only close-of-day OHLCV available on the signal date plus "
        "prior close history needed for QQQ/IWM/SPY context, 20-day tech "
        "relative lag, 5-day repair, 60-day trend guard, ADV, volume ratio, "
        "and realized volatility. Paper entry is next available open with "
        "existing entry slippage; exit is the close 10 trading days after the "
        "signal with target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: QQQ firmness plus IWM-vs-SPY risk appetite "
            "may reveal liquid Technology laggards whose same-day reclaim "
            "precedes delayed catch-up."
        ),
        "2_history_check": {
            "exp-20260607-007/008": (
                "Industry-relative laggard repair worked and was promoted to "
                "shared default-off; this test does not retune it, and instead "
                "uses cross-asset QQQ/IWM risk appetite within a tech-focused "
                "universe."
            ),
            "exp-20260607-010/014": (
                "Industry breadth and volume-breadth repair near-neighbors "
                "were rejected due old_thin fragility; this avoids breadth "
                "confirmation and tests a different free-OHLCV context."
            ),
            "exp-20260607-015": (
                "Rates relief duration-growth laggard failed sample/old_thin; "
                "this removes TLT/rates and tests equity risk appetite through "
                "QQQ/IWM only."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Accept only if "
            "aggregate EV/PnL improve, no EV/PnL regression window, target "
            "sample >=20 across all 3 windows, survival >=5%, drawdown drift "
            "<=0.5pp, and concentration guard passes."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260607_016_risk_appetite_tech_laggard_repair.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["gate2"]["runtime_fields"] = [
        "warehouse ohlcv Date/Open/High/Low/Close/Volume",
        "SPY daily OHLCV",
        "QQQ daily OHLCV",
        "IWM daily OHLCV",
        "data/reference/broad_market_sector_map.json sector/industry/status",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["gate3"]["note"] = (
        "No new core filter or entry rule was added. The QQQ/IWM tech "
        "laggard repair source is additive default-off paper, so core signals "
        "generated/survived are unchanged from baseline."
    )
    payload["context_alias"] = "risk_appetite_contexts"
    payload["risk_appetite_contexts_by_window"] = payload["pressure_contexts_by_window"]
    payload["risk_appetite_context_samples_by_window"] = {
        label: rows[:20]
        for label, rows in payload["pressure_contexts_by_window"].items()
    }
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Risk days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {risk} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                risk=len(payload["pressure_contexts_by_window"][label]),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Risk-Appetite Tech Laggard Repair",
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
    record = BASE_BUILD_LOG_RECORD(payload)
    aggregate = payload["delta_metrics"]["aggregate"]
    record.update(
        {
            "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "hypothesis": payload["hypothesis"],
            "aggregate_expected_value_delta": aggregate[
                "expected_value_score_delta_sum"
            ],
            "aggregate_expected_value_delta_pct": aggregate[
                "expected_value_score_delta_pct"
            ],
            "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
            "production_impact": PRODUCTION_IMPACT,
            "post_run_reflection": payload["post_run_reflection"],
            "negative_reflection": payload["negative_reflection"],
            "anti_js": "No JavaScript was used.",
        }
    )
    record["windows"] = [
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
            "risk_appetite_day_count": len(payload["pressure_contexts_by_window"][label]),
            "target_trade_count": len(payload["target_trades_by_window"][label]),
        }
        for label in framework.WINDOWS
    ]
    return record


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(SCRIPT_PATH),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(SCRIPT_PATH): framework._sha256(SCRIPT_PATH),
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
    framework._load_sector_entries = _load_sector_entries
    framework._load_window_snapshot = _load_window_snapshot
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._gate4 = _gate4
    framework._build_payload = _build_payload
    framework._build_card = _build_card
    framework._build_log_record = _build_log_record
    framework._write_manifest = _write_manifest


_patch_framework()


def main() -> None:
    framework.main()


if __name__ == "__main__":
    main()
