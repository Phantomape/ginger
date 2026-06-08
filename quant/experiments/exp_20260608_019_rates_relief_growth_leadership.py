"""exp-20260608-019: rates-relief growth-leadership candidate pool.

Replay-only alpha search. It tests one free-OHLCV relation source: when TLT
rallies and SPY/QQQ confirm rates relief, admit up to two liquid growth-stock
leaders that beat the equity indices into the close. Paper entry is next-open
with a fixed 10-trading-day hold.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import exp_20260606_029_sector_etf_lead_laggard_candidate_pool as base


EXPERIMENT_ID = "exp-20260608-019"
STEM = "rates_relief_growth_leadership"
TRIAL_FAMILY = "rates_relief_growth_leadership_candidate_pool"
TRIAL_VARIANT_ID = "tlt_up_spy_qqq_confirmed_growth_leadership_top2_10d_v1"
CHANGED_VARIABLE = "rates_relief_growth_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

framework = base.framework
REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260608_019_{STEM}.json"
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

RATE_CONTEXT_TICKERS = {"SPY", "QQQ", "TLT"}
GROWTH_SECTORS = {"Technology", "Communication Services", "Consumer Cyclical"}
GROWTH_INDUSTRY_KEYWORDS = (
    "software",
    "semiconductor",
    "internet",
    "computer",
    "electronic",
    "communication equipment",
    "information technology",
    "consumer electronics",
    "solar",
    "electronic gaming",
    "interactive media",
)
GROWTH_INDUSTRY_EXACT = {"Internet Retail"}

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_TLT_SIGNAL_RETURN = 0.0035
MIN_TLT_CLOSE_LOCATION = 0.55
MIN_TLT_RET5 = -0.015
MIN_SPY_SIGNAL_RETURN = -0.0025
MIN_SPY_CLOSE_LOCATION = 0.45
MIN_QQQ_SIGNAL_RETURN = 0.0025
MIN_QQQ_CLOSE_LOCATION = 0.54
MIN_QQQ_RELATIVE_VS_SPY = -0.003
MIN_CANDIDATE_SIGNAL_RETURN = 0.006
MIN_CANDIDATE_RELATIVE_VS_SPY = 0.004
MIN_CANDIDATE_RELATIVE_VS_QQQ = 0.002
MIN_CANDIDATE_RET20_EXCESS_QQQ = -0.020
MAX_CANDIDATE_RET20_EXCESS_QQQ = 0.180
MIN_CANDIDATE_RET20_EXCESS_SPY = -0.010
MIN_CANDIDATE_RET60_EXCESS_SPY = -0.040
MIN_CANDIDATE_RET5 = -0.030
MAX_CANDIDATE_RET5 = 0.150
MIN_CANDIDATE_CLOSE_LOCATION = 0.68
MIN_CANDIDATE_VOLUME_RATIO_20D = 1.05
MAX_CANDIDATE_REALIZED_VOL_20 = 0.090

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": None,
    "expected_pnl_delta": 2500.0,
    "main_failure_modes": [
        "macro_proxy_relabel",
        "window_regression",
        "thin_sample",
        "accepted_relief_overlap",
        "duration_beta_tail_risk",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Space catalyst/source/peer replacement value is the best Space idea "
        "but is blocked historically by missing PIT fields. Accepted macro and "
        "VIXY relief adapters show state-transfer leadership can work, while "
        "rates-relief growth laggards and rates-up financial leadership failed; "
        "this tests the opposite rates-relief leadership mechanism."
    ),
    "recorded_at": "2026-06-08T16:49:02+00:00",
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
        "require a shared default-off adapter that computes the same TLT/SPY/QQQ "
        "rates-relief context, high-duration growth-stock universe, leadership "
        "score, same-ticker core-overlap exclusion, next-open paper entry, "
        "10-trading-day exit, costs, cooldown, top-N limit, and concentration "
        "controls in both replay and daily production before any report queue, "
        "paper ledger, candidate priority, sizing, watchlist, or order surface "
        "could change."
    ),
}

BASE_LOAD_WINDOW_SNAPSHOT = base.BASE_LOAD_WINDOW_SNAPSHOT
BASE_BUILD_PAYLOAD = base.BASE_BUILD_PAYLOAD
BASE_GATE4 = base.BASE_GATE4


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _load_window_snapshot(
    *,
    cfg: dict[str, str],
    eligible_tickers: set[str],
) -> dict[str, list[dict[str, Any]]]:
    return BASE_LOAD_WINDOW_SNAPSHOT(
        cfg=cfg,
        eligible_tickers=set(eligible_tickers) | RATE_CONTEXT_TICKERS,
    )


def _is_duration_growth_candidate(meta: dict[str, Any]) -> bool:
    sector = str(meta.get("sector") or "")
    industry = str(meta.get("industry") or "")
    industry_lower = industry.lower()
    if sector not in GROWTH_SECTORS:
        return False
    return industry in GROWTH_INDUSTRY_EXACT or any(
        keyword in industry_lower for keyword in GROWTH_INDUSTRY_KEYWORDS
    )


def _rates_relief_context_for_day(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    signal_date: str,
) -> dict[str, Any] | None:
    spy_rows = snapshot.get("SPY") or []
    qqq_rows = snapshot.get("QQQ") or []
    tlt_rows = snapshot.get("TLT") or []
    spy_idx = indices.get("SPY", {}).get(signal_date)
    qqq_idx = indices.get("QQQ", {}).get(signal_date)
    tlt_idx = indices.get("TLT", {}).get(signal_date)
    if spy_idx is None or qqq_idx is None or tlt_idx is None:
        return None
    if spy_idx < 20 or qqq_idx < 20 or tlt_idx < 20:
        return None

    spy_return = framework._daily_return(spy_rows, spy_idx)
    qqq_return = framework._daily_return(qqq_rows, qqq_idx)
    tlt_return = framework._daily_return(tlt_rows, tlt_idx)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    qqq_ret20 = framework._ret(qqq_rows, qqq_idx, 20)
    tlt_ret5 = framework._ret(tlt_rows, tlt_idx, 5)
    tlt_close_location = framework._close_location(tlt_rows[tlt_idx])
    spy_close_location = framework._close_location(spy_rows[spy_idx])
    qqq_close_location = framework._close_location(qqq_rows[qqq_idx])
    if (
        spy_return is None
        or qqq_return is None
        or tlt_return is None
        or spy_ret20 is None
        or qqq_ret20 is None
        or tlt_ret5 is None
        or tlt_close_location is None
        or spy_close_location is None
        or qqq_close_location is None
    ):
        return None

    qqq_relative_vs_spy = qqq_return - spy_return
    if tlt_return < MIN_TLT_SIGNAL_RETURN:
        return None
    if tlt_close_location < MIN_TLT_CLOSE_LOCATION:
        return None
    if tlt_ret5 < MIN_TLT_RET5:
        return None
    if spy_return < MIN_SPY_SIGNAL_RETURN:
        return None
    if spy_close_location < MIN_SPY_CLOSE_LOCATION:
        return None
    if qqq_return < MIN_QQQ_SIGNAL_RETURN:
        return None
    if qqq_close_location < MIN_QQQ_CLOSE_LOCATION:
        return None
    if qqq_relative_vs_spy < MIN_QQQ_RELATIVE_VS_SPY:
        return None

    return {
        "date": signal_date,
        "passed": True,
        "reason": "tlt_qqq_rates_relief_passed",
        "tlt_signal_day_return": round(tlt_return, 6),
        "tlt_ret5": round(tlt_ret5, 6),
        "tlt_close_location": round(tlt_close_location, 6),
        "qqq_signal_day_return": round(qqq_return, 6),
        "qqq_relative_vs_spy": round(qqq_relative_vs_spy, 6),
        "qqq_close_location": round(qqq_close_location, 6),
        "qqq_ret20": round(qqq_ret20, 6),
        "spy_signal_day_return": round(spy_return, 6),
        "spy_close_location": round(spy_close_location, 6),
        "spy_ret20": round(spy_ret20, 6),
        "rule_version": RULE_VERSION,
    }


def _candidate_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    context: dict[str, Any],
) -> dict[str, Any] | None:
    if ticker in RATE_CONTEXT_TICKERS:
        return None
    sector_meta = sector_entries.get(ticker) or {}
    if not _is_duration_growth_candidate(sector_meta):
        return None
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    qqq_rows = snapshot.get("QQQ") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    qqq_idx = indices.get("QQQ", {}).get(signal_date)
    if idx is None or spy_idx is None or qqq_idx is None:
        return None
    if idx < 60 or spy_idx < 60 or qqq_idx < 20 or idx + HOLD_DAYS >= len(rows):
        return None

    row = rows[idx]
    close = framework._value(row, "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    signal_return = framework._daily_return(rows, idx)
    spy_return = framework._daily_return(spy_rows, spy_idx)
    qqq_return = framework._daily_return(qqq_rows, qqq_idx)
    if signal_return is None or spy_return is None or qqq_return is None:
        return None

    relative_vs_spy = signal_return - spy_return
    relative_vs_qqq = signal_return - qqq_return
    if signal_return < MIN_CANDIDATE_SIGNAL_RETURN:
        return None
    if relative_vs_spy < MIN_CANDIDATE_RELATIVE_VS_SPY:
        return None
    if relative_vs_qqq < MIN_CANDIDATE_RELATIVE_VS_QQQ:
        return None

    close_location = framework._close_location(row)
    ret5 = framework._ret(rows, idx, 5)
    ret20 = framework._ret(rows, idx, 20)
    ret60 = framework._ret(rows, idx, 60)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = framework._ret(spy_rows, spy_idx, 60)
    qqq_ret20 = framework._ret(qqq_rows, qqq_idx, 20)
    realized_vol = framework._realized_vol(rows, idx)
    if (
        close_location is None
        or ret5 is None
        or ret20 is None
        or ret60 is None
        or spy_ret20 is None
        or spy_ret60 is None
        or qqq_ret20 is None
        or realized_vol is None
    ):
        return None
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    ret20_excess_qqq = ret20 - qqq_ret20
    if ret20_excess_qqq < MIN_CANDIDATE_RET20_EXCESS_QQQ:
        return None
    if ret20_excess_qqq > MAX_CANDIDATE_RET20_EXCESS_QQQ:
        return None
    if ret20_excess_spy < MIN_CANDIDATE_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_CANDIDATE_RET60_EXCESS_SPY:
        return None
    if ret5 < MIN_CANDIDATE_RET5 or ret5 > MAX_CANDIDATE_RET5:
        return None
    if close_location < MIN_CANDIDATE_CLOSE_LOCATION:
        return None
    volume_ratio = framework._volume_ratio(rows, idx) or 0.0
    if volume_ratio < MIN_CANDIDATE_VOLUME_RATIO_20D:
        return None
    if realized_vol > MAX_CANDIDATE_REALIZED_VOL_20:
        return None

    score = (
        1.25 * float(context["tlt_signal_day_return"])
        + 1.35 * float(context["qqq_signal_day_return"])
        + 1.65 * relative_vs_qqq
        + 1.10 * relative_vs_spy
        + 0.42 * max(ret20_excess_qqq, 0.0)
        + 0.36 * max(ret20_excess_spy, 0.0)
        + 0.42 * close_location
        + 0.22 * ret60_excess_spy
        + 0.035 * math.log10(max(adv20, 1.0) / 1_000_000.0)
        - 0.62 * realized_vol
        - 0.10 * max(ret5 - 0.08, 0.0)
        - 0.04 * max(volume_ratio - 2.6, 0.0)
    )
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "RATES_RELIEF_GROWTH_LEADERSHIP_PAPER",
        "candidate_score": round(score, 6),
        "candidate_signal_day_return": round(signal_return, 6),
        "candidate_relative_vs_spy": round(relative_vs_spy, 6),
        "candidate_relative_vs_qqq": round(relative_vs_qqq, 6),
        "candidate_ret5": round(ret5, 6),
        "candidate_ret20": round(ret20, 6),
        "candidate_ret60": round(ret60, 6),
        "candidate_spy_ret20": round(spy_ret20, 6),
        "candidate_qqq_ret20": round(qqq_ret20, 6),
        "candidate_ret20_excess_spy": round(ret20_excess_spy, 6),
        "candidate_ret60_excess_spy": round(ret60_excess_spy, 6),
        "candidate_ret20_excess_qqq": round(ret20_excess_qqq, 6),
        "candidate_close_location": round(close_location, 6),
        "candidate_avg_dollar_volume_20d": round(adv20, 2),
        "candidate_volume_ratio_20d": round(volume_ratio, 6),
        "candidate_realized_vol_20d": round(realized_vol, 6),
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "sector_coverage_status": sector_meta.get("sector_coverage_status"),
        "rates_relief_context": context,
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
    stock_entries = {
        ticker: meta
        for ticker, meta in sector_entries.items()
        if _is_duration_growth_candidate(meta)
    }
    candidates: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    context_scan = {
        "scanned_trading_days": len(dates),
        "rates_relief_days": 0,
        "raw_candidate_rows": 0,
        "unique_candidate_tickers": 0,
        "candidate_universe_count": len(stock_entries),
        "context_tickers": sorted(RATE_CONTEXT_TICKERS),
        "growth_sectors": sorted(GROWTH_SECTORS),
        "growth_industry_keywords": list(GROWTH_INDUSTRY_KEYWORDS),
    }
    for signal_date in dates:
        context = _rates_relief_context_for_day(
            snapshot=snapshot,
            indices=indices,
            signal_date=signal_date,
        )
        if context is None:
            continue
        contexts.append(context)
        context_scan["rates_relief_days"] += 1
        for ticker in stock_entries:
            row = _candidate_for_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=stock_entries,
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
            candidates.append(row)
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["candidate_relative_vs_qqq"]),
            -float(row["candidate_relative_vs_spy"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            str(row.get("industry") or ""),
            row["ticker"],
        )
    )
    context_scan["raw_candidate_rows"] = len(candidates)
    context_scan["unique_candidate_tickers"] = len({row["ticker"] for row in candidates})
    return candidates, contexts, context_scan


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
        "positive_replay_lead_not_promoted_rates_relief_growth_leadership"
        if gate["passed"]
        else "rejected_rates_relief_growth_leadership_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    aggregate = payload["delta_metrics"]["aggregate"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "TLT rates-relief days with SPY/QQQ confirmation may identify "
                "liquid high-duration growth-stock leaders whose next-open "
                "10-day continuation has replacement value. This pivots from "
                "Space because official Space catalyst/source/peer fields are "
                "not available as PIT history inside the canonical windows."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_cross_asset_candidate_pool",
            "new_evidence_type": "production_visible_free_ohlcv_rates_relief_state",
            "nearby_prior_experiments": [
                "exp-20260606-020",
                "exp-20260607-015",
                "exp-20260607-019",
                "exp-20260607-024",
            ],
            "prior_trial_count": 2,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "anti_js": "No JavaScript was used.",
            "rates_relief_contexts_by_window": payload["pressure_contexts_by_window"],
            "rates_relief_context_samples_by_window": payload[
                "pressure_context_samples_by_window"
            ],
            "negative_reflection": (
                "If rejected, the likely reason is that TLT/SPY/QQQ relief is "
                "only a macro beta label, or that growth leaders have already "
                "repriced by next-open execution. Do not answer by sweeping "
                "TLT/SPY/QQQ relief, growth keywords, leadership thresholds, "
                "volume, volatility, hold-day, cooldown, top-N, or paper "
                "notional on the frozen windows."
            ),
            "next_evidence_needed": (
                "A positive replay lead still needs a shared default-off "
                "adapter and parity tests before production observation. A "
                "retry after rejection needs a materially new PIT rates source "
                "or forward replacement-value rows, not a threshold sweep."
            ),
        }
    )
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "rate_context_tickers": sorted(RATE_CONTEXT_TICKERS),
        "growth_sectors": sorted(GROWTH_SECTORS),
        "growth_industry_keywords": list(GROWTH_INDUSTRY_KEYWORDS),
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "min_tlt_signal_return": MIN_TLT_SIGNAL_RETURN,
        "min_tlt_close_location": MIN_TLT_CLOSE_LOCATION,
        "min_tlt_ret5": MIN_TLT_RET5,
        "min_spy_signal_return": MIN_SPY_SIGNAL_RETURN,
        "min_spy_close_location": MIN_SPY_CLOSE_LOCATION,
        "min_qqq_signal_return": MIN_QQQ_SIGNAL_RETURN,
        "min_qqq_close_location": MIN_QQQ_CLOSE_LOCATION,
        "min_qqq_relative_vs_spy": MIN_QQQ_RELATIVE_VS_SPY,
        "min_candidate_signal_return": MIN_CANDIDATE_SIGNAL_RETURN,
        "min_candidate_relative_vs_spy": MIN_CANDIDATE_RELATIVE_VS_SPY,
        "min_candidate_relative_vs_qqq": MIN_CANDIDATE_RELATIVE_VS_QQQ,
        "min_candidate_ret20_excess_qqq": MIN_CANDIDATE_RET20_EXCESS_QQQ,
        "max_candidate_ret20_excess_qqq": MAX_CANDIDATE_RET20_EXCESS_QQQ,
        "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
        "min_candidate_ret60_excess_spy": MIN_CANDIDATE_RET60_EXCESS_SPY,
        "min_candidate_ret5": MIN_CANDIDATE_RET5,
        "max_candidate_ret5": MAX_CANDIDATE_RET5,
        "min_candidate_close_location": MIN_CANDIDATE_CLOSE_LOCATION,
        "min_candidate_volume_ratio_20d": MIN_CANDIDATE_VOLUME_RATIO_20D,
        "max_candidate_realized_vol_20": MAX_CANDIDATE_REALIZED_VOL_20,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"].update(
        {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "replay-only rates-relief growth-leadership paper overlay"
            ),
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "rates_context_tickers": sorted(RATE_CONTEXT_TICKERS),
            "execution_model": (
                "Signal uses only close-of-day OHLCV available on signal date. "
                "TLT/SPY/QQQ relief context, growth-stock leadership, close "
                "location, liquidity, volume, volatility, and relative-return "
                "fields are known after the signal-day close before next-open "
                "paper entry. Paper entry is next available open with existing "
                "entry slippage; exit is the close 10 trading days after the "
                "signal with target-side sell slippage and ROUND_TRIP_COST_PCT."
            ),
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: if duration pressure releases and equity "
            "indices confirm, the strongest liquid growth-stock leaders may "
            "continue for 10 trading days because capital rotates first into "
            "high-beta leaders rather than laggards."
        ),
        "2_history_check": {
            "Space sleeve": (
                "The strongest Space direction is official catalyst/source/peer "
                "replacement value, but data/state/universe/universe_events.jsonl "
                "Space metadata begins 2026-05-10, after all canonical windows. "
                "Using it in the three windows would be non-PIT, so Space alpha "
                "is deferred rather than retuned."
            ),
            "exp-20260606-020": (
                "Macro relief leadership accepted as a shared default-off "
                "adapter. This is not an official macro-day threshold retune; "
                "it uses a different TLT rates-relief state."
            ),
            "exp-20260607-015": (
                "Rates-relief duration-growth laggards were rejected: aggregate "
                "was positive but old_thin regressed and sample was 18 trades. "
                "This tests the opposite leadership continuation mechanism, not "
                "laggard catch-up or threshold edits."
            ),
            "exp-20260607-019/024": (
                "VIXY relief stock leadership became a positive replay lead, "
                "while rates-up financial leadership failed. This makes rates "
                "relief plausible but low probability."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Accept only if "
            "aggregate EV/PnL improve, no EV/PnL regression window, target "
            "sample >=20 across all 3 windows, survival >=5%, drawdown drift "
            "<=0.5pp, and concentration guard passes. A positive replay still "
            "requires shared adapter parity before promotion."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260608_019_rates_relief_growth_leadership.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["gate2"]["runtime_fields"] = [
        "warehouse ohlcv Date/Open/High/Low/Close/Volume",
        "SPY daily OHLCV",
        "QQQ daily OHLCV",
        "TLT daily OHLCV",
        "data/reference/broad_market_sector_map.json sector/industry/status",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["gate3"]["note"] = (
        "No new core filter or entry rule was added. The rates-relief "
        "growth-leadership candidate source is additive default-off "
        "paper, so core signals generated/survived are unchanged from baseline."
    )
    payload["decision"] = payload["gate4"]["decision"]
    payload["status"] = (
        "positive_replay_lead_not_promoted"
        if payload["gate4"]["passed"]
        else "rejected"
    )
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_success": 1 if payload["gate4"]["passed"] else 0,
        "actual_gate4_passed": payload["gate4"]["passed"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
        "failure_modes_observed": payload["gate4"]["failed_reasons"],
        "brier_score": round(
            (
                PREDICTION["success_probability"]
                - (1.0 if payload["gate4"]["passed"] else 0.0)
            )
            ** 2,
            6,
        ),
    }
    payload["interpretation"] = (
        "The rates-relief growth-leadership source cleared Gate 4 as a "
        "replay-only/default-off lead. No production surface was promoted; a "
        "shared adapter plus parity tests are required before forward use."
        if payload["gate4"]["passed"]
        else (
            "The rates-relief growth-leadership source did not clear "
            "Gate 4; do not promote or locally retune this relation on the "
            "frozen windows."
        )
    )
    payload["rejection_reason"] = (
        None if payload["gate4"]["passed"] else "; ".join(payload["gate4"]["failed_reasons"])
    )
    old_thin_delta = payload["delta_metrics"]["by_window"]["old_thin"]
    target_count = payload["target_trade_summary"]["total_trade_count"]
    why_result = (
        "The fixed rates-relief leadership source produced {count} target "
        "trades. old_thin moved {ev:+.4f} EV and ${pnl:+,.2f}; the full Gate 4 "
        "decision records whether TLT/SPY/QQQ relief separated durable growth "
        "leadership from macro beta after next-open entry, costs, and the "
        "fixed 10-day exit."
    ).format(
        ev=old_thin_delta["expected_value_score"],
        pnl=old_thin_delta["total_pnl"],
        count=target_count,
    )
    payload["post_run_reflection"] = {
        "why_result_happened": why_result,
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping TLT/SPY/QQQ relief, close-location, "
            "growth industry keywords, leadership thresholds, ret20/ret60 "
            "excess, volume, volatility, hold-day, top-N, cooldown, or paper "
            "notional on the same frozen windows."
        ),
        "new_evidence_required": (
            "A retry requires a materially new PIT rates/curve source, "
            "stock-level duration proxy, event timestamp, or closed forward "
            "replacement-value rows from a shared default-off adapter."
        ),
    }
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Relief days | Trades |",
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
                days=scan.get("rates_relief_days", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Rates-Relief Growth Leadership",
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
                "rates_relief_day_count": payload["context_scan_by_window"][label].get(
                    "rates_relief_days"
                ),
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
    script_path = Path(__file__)
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(script_path),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(script_path): framework._sha256(script_path),
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
