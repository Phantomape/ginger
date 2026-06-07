"""exp-20260607-024: rates-up financial leadership candidate pool.

Replay-only alpha search. It tests one production-visible free-OHLCV relation
source: when TLT sells off and liquid financial stocks lead SPY/QQQ as a group,
admit up to two liquid financial leaders for next-open paper continuation with
a fixed 10-trading-day hold.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import math
from pathlib import Path
from statistics import median
from typing import Any

import exp_20260606_029_sector_etf_lead_laggard_candidate_pool as base


EXPERIMENT_ID = "exp-20260607-024"
STEM = "rates_up_financial_leadership"
TRIAL_FAMILY = "rates_up_financial_leadership_candidate_pool"
TRIAL_VARIANT_ID = "tlt_down_financial_leadership_top2_next_open_10d_v1"
CHANGED_VARIABLE = "rates_up_financial_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

framework = base.framework
REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260607_024_{STEM}.json"
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
FINANCIAL_SECTORS = {"Financial Services"}

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_FINANCIAL_CONTEXT_COUNT = 20
MAX_TLT_SIGNAL_RETURN = -0.0035
MAX_TLT_CLOSE_LOCATION = 0.45
MAX_SPY_SIGNAL_RETURN = 0.030
MIN_SPY_SIGNAL_RETURN = -0.0040
MIN_QQQ_SIGNAL_RETURN = -0.0060
MIN_FINANCIAL_MEDIAN_RETURN = 0.0020
MIN_FINANCIAL_POSITIVE_FRACTION = 0.55
MIN_FINANCIAL_MEDIAN_EXCESS_SPY = 0.0030
MIN_CANDIDATE_SIGNAL_RETURN = 0.0060
MIN_CANDIDATE_RELATIVE_VS_SPY = 0.0060
MIN_CANDIDATE_RELATIVE_VS_FINANCIAL_MEDIAN = 0.0030
MIN_CANDIDATE_CLOSE_LOCATION = 0.65
MIN_CANDIDATE_VOLUME_RATIO = 1.00
MIN_CANDIDATE_RET20_EXCESS_SPY = -0.020
MIN_CANDIDATE_RET60_EXCESS_SPY = -0.040
MAX_CANDIDATE_RET5 = 0.150
MAX_CANDIDATE_REALIZED_VOL_20 = 0.085

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

PREDICTION = {
    "success_probability": 0.15,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "financial_beta_relabel",
        "old_thin_regression",
        "drawdown_drift",
        "thin_rates_up_sample",
        "concentration_failed",
    ],
    "confidence_reason": (
        "TLT and financial sector rows are production-visible free OHLCV; "
        "macro/VIXY relief leadership shows event-state stock leadership can "
        "work, while rates-relief and sector-ETF laggard neighbors failed, so "
        "this is a low-probability but materially distinct relation test."
    ),
    "recorded_at": "2026-06-07T20:06:27+00:00",
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
        "require a shared default-off adapter that computes the same TLT "
        "selloff context, financial-sector breadth/leadership fields, "
        "same-ticker core-overlap exclusion, next-open paper entry, "
        "10-trading-day exit, costs, cooldown, top-N limit, and concentration "
        "controls in both replay and daily production before any report "
        "queue, paper ledger, candidate priority, sizing, watchlist, or order "
        "surface could change."
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


def _is_financial_candidate(meta: dict[str, Any]) -> bool:
    return str(meta.get("sector") or "") in FINANCIAL_SECTORS


def _financial_context_for_day(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    signal_date: str,
    financial_tickers: set[str],
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
    tlt_ret5 = framework._ret(tlt_rows, tlt_idx, 5)
    tlt_close_location = framework._close_location(tlt_rows[tlt_idx])
    if (
        spy_return is None
        or qqq_return is None
        or tlt_return is None
        or spy_ret20 is None
        or tlt_ret5 is None
        or tlt_close_location is None
    ):
        return None
    if tlt_return > MAX_TLT_SIGNAL_RETURN:
        return None
    if tlt_close_location > MAX_TLT_CLOSE_LOCATION:
        return None
    if spy_return < MIN_SPY_SIGNAL_RETURN or spy_return > MAX_SPY_SIGNAL_RETURN:
        return None
    if qqq_return < MIN_QQQ_SIGNAL_RETURN:
        return None

    financial_returns: list[float] = []
    financial_excess_spy: list[float] = []
    for ticker in financial_tickers:
        rows = snapshot.get(ticker) or []
        idx = indices.get(ticker, {}).get(signal_date)
        if idx is None or idx < 20:
            continue
        close = framework._value(rows[idx], "Close")
        if close is None or close < MIN_PRICE:
            continue
        adv20 = framework._avg_dollar_volume(rows, idx)
        if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
            continue
        daily_return = framework._daily_return(rows, idx)
        if daily_return is None:
            continue
        financial_returns.append(daily_return)
        financial_excess_spy.append(daily_return - spy_return)

    if len(financial_returns) < MIN_FINANCIAL_CONTEXT_COUNT:
        return None

    financial_median_return = median(financial_returns)
    financial_median_excess_spy = median(financial_excess_spy)
    financial_positive_fraction = sum(
        1 for value in financial_returns if value > 0.0
    ) / len(financial_returns)
    if financial_median_return < MIN_FINANCIAL_MEDIAN_RETURN:
        return None
    if financial_positive_fraction < MIN_FINANCIAL_POSITIVE_FRACTION:
        return None
    if financial_median_excess_spy < MIN_FINANCIAL_MEDIAN_EXCESS_SPY:
        return None

    return {
        "date": signal_date,
        "passed": True,
        "reason": "rates_up_financial_leadership_passed",
        "tlt_signal_day_return": round(tlt_return, 6),
        "tlt_ret5": round(tlt_ret5, 6),
        "tlt_close_location": round(tlt_close_location, 6),
        "spy_signal_day_return": round(spy_return, 6),
        "spy_ret20": round(spy_ret20, 6),
        "qqq_signal_day_return": round(qqq_return, 6),
        "financial_context_count": len(financial_returns),
        "financial_median_return": round(financial_median_return, 6),
        "financial_median_excess_spy": round(financial_median_excess_spy, 6),
        "financial_positive_fraction": round(financial_positive_fraction, 6),
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
    if not _is_financial_candidate(sector_meta):
        return None
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None:
        return None
    if idx < 60 or spy_idx < 60 or idx + HOLD_DAYS >= len(rows):
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
    if signal_return is None or spy_return is None:
        return None

    relative_vs_spy = signal_return - spy_return
    relative_vs_financial_median = (
        signal_return - float(context["financial_median_return"])
    )
    if signal_return < MIN_CANDIDATE_SIGNAL_RETURN:
        return None
    if relative_vs_spy < MIN_CANDIDATE_RELATIVE_VS_SPY:
        return None
    if relative_vs_financial_median < MIN_CANDIDATE_RELATIVE_VS_FINANCIAL_MEDIAN:
        return None

    close_location = framework._close_location(row)
    ret5 = framework._ret(rows, idx, 5)
    ret20 = framework._ret(rows, idx, 20)
    ret60 = framework._ret(rows, idx, 60)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = framework._ret(spy_rows, spy_idx, 60)
    realized_vol = framework._realized_vol(rows, idx)
    if (
        close_location is None
        or ret5 is None
        or ret20 is None
        or ret60 is None
        or spy_ret20 is None
        or spy_ret60 is None
        or realized_vol is None
    ):
        return None
    if close_location < MIN_CANDIDATE_CLOSE_LOCATION:
        return None
    if ret5 > MAX_CANDIDATE_RET5:
        return None
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60
    if ret20_excess_spy < MIN_CANDIDATE_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_CANDIDATE_RET60_EXCESS_SPY:
        return None
    if realized_vol > MAX_CANDIDATE_REALIZED_VOL_20:
        return None
    volume_ratio = framework._volume_ratio(rows, idx) or 0.0
    if volume_ratio < MIN_CANDIDATE_VOLUME_RATIO:
        return None

    score = (
        1.35 * abs(float(context["tlt_signal_day_return"]))
        + 1.25 * float(context["financial_median_excess_spy"])
        + 1.65 * relative_vs_spy
        + 1.00 * relative_vs_financial_median
        + 0.50 * ret20_excess_spy
        + 0.25 * ret60_excess_spy
        + 0.35 * close_location
        + 0.030 * math.log10(max(adv20, 1.0) / 1_000_000.0)
        + 0.020 * min(volume_ratio, 3.0)
        - 0.60 * realized_vol
    )
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "RATES_UP_FINANCIAL_LEADERSHIP_PAPER",
        "candidate_score": round(score, 6),
        "candidate_signal_day_return": round(signal_return, 6),
        "candidate_relative_vs_spy": round(relative_vs_spy, 6),
        "candidate_relative_vs_financial_median": round(
            relative_vs_financial_median, 6
        ),
        "candidate_ret5": round(ret5, 6),
        "candidate_ret20": round(ret20, 6),
        "candidate_ret60": round(ret60, 6),
        "candidate_spy_ret20": round(spy_ret20, 6),
        "candidate_ret20_excess_spy": round(ret20_excess_spy, 6),
        "candidate_ret60_excess_spy": round(ret60_excess_spy, 6),
        "candidate_close_location": round(close_location, 6),
        "candidate_avg_dollar_volume_20d": round(adv20, 2),
        "candidate_volume_ratio_20d": round(volume_ratio, 6),
        "candidate_realized_vol_20d": round(realized_vol, 6),
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "sector_coverage_status": sector_meta.get("sector_coverage_status"),
        "rates_up_financial_context": context,
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
    financial_entries = {
        ticker: meta
        for ticker, meta in sector_entries.items()
        if _is_financial_candidate(meta)
    }
    financial_tickers = set(financial_entries)
    candidates: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    context_scan = {
        "scanned_trading_days": len(dates),
        "rates_up_financial_days": 0,
        "raw_candidate_rows": 0,
        "unique_candidate_tickers": 0,
        "candidate_universe_count": len(financial_entries),
        "context_tickers": sorted(RATE_CONTEXT_TICKERS),
        "financial_sectors": sorted(FINANCIAL_SECTORS),
    }
    for signal_date in dates:
        context = _financial_context_for_day(
            snapshot=snapshot,
            indices=indices,
            signal_date=signal_date,
            financial_tickers=financial_tickers,
        )
        if context is None:
            continue
        contexts.append(context)
        context_scan["rates_up_financial_days"] += 1
        for ticker in financial_entries:
            row = _candidate_for_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=financial_entries,
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
            -float(row["candidate_relative_vs_financial_median"]),
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
        "positive_replay_lead_not_promoted_rates_up_financial_leadership"
        if gate["passed"]
        else "rejected_rates_up_financial_leadership_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    aggregate = payload["delta_metrics"]["aggregate"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Rates-up days where TLT sells off while liquid financial "
                "stocks lead broadly may identify financial leaders whose "
                "next-open continuation improves replacement value without "
                "requiring absent XLF/KRE warehouse rows."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_cross_asset_candidate_pool",
            "new_evidence_type": "production_visible_free_ohlcv_rates_to_financials_relation",
            "nearby_prior_experiments": [
                "exp-20260607-015",
                "exp-20260606-029",
                "exp-20260606-027",
                "exp-20260606-019",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "low",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "anti_js": "No JavaScript was used.",
            "rates_up_financial_contexts_by_window": payload[
                "pressure_contexts_by_window"
            ],
            "rates_up_financial_context_samples_by_window": payload[
                "pressure_context_samples_by_window"
            ],
            "negative_reflection": (
                "If rejected, the likely reason is that TLT selloff plus "
                "financial-sector breadth is just same-day financial beta, "
                "already repriced before next-open entry, or too sparse in "
                "old_thin. Do not retry by sweeping TLT, breadth, leader, "
                "hold-day, cooldown, top-N, or notional thresholds on the "
                "same frozen windows."
            ),
            "next_evidence_needed": (
                "A positive replay lead still needs a shared default-off "
                "adapter and parity tests before production observation. A "
                "retry after rejection needs a materially new PIT rates/curve, "
                "bank-specific earnings/NIM, credit-spread, or closed forward "
                "replacement-value source."
            ),
        }
    )
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "rate_context_tickers": sorted(RATE_CONTEXT_TICKERS),
        "financial_sectors": sorted(FINANCIAL_SECTORS),
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "min_financial_context_count": MIN_FINANCIAL_CONTEXT_COUNT,
        "max_tlt_signal_return": MAX_TLT_SIGNAL_RETURN,
        "max_tlt_close_location": MAX_TLT_CLOSE_LOCATION,
        "min_spy_signal_return": MIN_SPY_SIGNAL_RETURN,
        "max_spy_signal_return": MAX_SPY_SIGNAL_RETURN,
        "min_qqq_signal_return": MIN_QQQ_SIGNAL_RETURN,
        "min_financial_median_return": MIN_FINANCIAL_MEDIAN_RETURN,
        "min_financial_positive_fraction": MIN_FINANCIAL_POSITIVE_FRACTION,
        "min_financial_median_excess_spy": MIN_FINANCIAL_MEDIAN_EXCESS_SPY,
        "min_candidate_signal_return": MIN_CANDIDATE_SIGNAL_RETURN,
        "min_candidate_relative_vs_spy": MIN_CANDIDATE_RELATIVE_VS_SPY,
        "min_candidate_relative_vs_financial_median": (
            MIN_CANDIDATE_RELATIVE_VS_FINANCIAL_MEDIAN
        ),
        "min_candidate_close_location": MIN_CANDIDATE_CLOSE_LOCATION,
        "min_candidate_volume_ratio": MIN_CANDIDATE_VOLUME_RATIO,
        "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
        "min_candidate_ret60_excess_spy": MIN_CANDIDATE_RET60_EXCESS_SPY,
        "max_candidate_ret5": MAX_CANDIDATE_RET5,
        "max_candidate_realized_vol_20": MAX_CANDIDATE_REALIZED_VOL_20,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"].update(
        {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "replay-only rates-up financial leadership paper overlay"
            ),
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "rates_context_tickers": sorted(RATE_CONTEXT_TICKERS),
            "execution_model": (
                "Signal uses only close-of-day OHLCV available on signal date. "
                "TLT selloff context, financial breadth, financial leader "
                "relative return, close location, liquidity, volume ratio, "
                "volatility, and relative-return fields are known after the "
                "signal-day close before next-open paper entry. Paper entry is "
                "next available open with existing entry slippage; exit is the "
                "close 10 trading days after the signal with target-side sell "
                "slippage and ROUND_TRIP_COST_PCT."
            ),
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: when TLT sells off and liquid financial "
            "stocks lead broadly after the close, the strongest financial "
            "single names may have next-open continuation from rates-up "
            "repricing and net-interest-margin expectations."
        ),
        "2_history_check": {
            "exp-20260607-015": (
                "Rates-relief duration-growth laggard was rejected due "
                "old_thin regression and thin target sample. This tests the "
                "opposite rates-up channel in financial leaders, not growth "
                "laggards."
            ),
            "exp-20260606-029": (
                "Sector ETF lead/laggard failed. XLF/KRE are absent from the "
                "warehouse, so this uses broad financial-stock breadth rather "
                "than a missing ETF proxy."
            ),
            "exp-20260606-027": (
                "Macro stress resilience was rejected; this gates out broad "
                "equity stress and requires financial-sector leadership."
            ),
            "exp-20260606-019": (
                "Macro relief ETF leadership was accepted. This is a distinct "
                "rates-up-to-financials relation and remains replay-only."
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
            "exp_20260607_024_rates_up_financial_leadership.py"
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
        "No new core filter or entry rule was added. The rates-up financial "
        "leadership candidate source is additive default-off paper, so core "
        "signals generated/survived are unchanged from baseline."
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
        "The rates-up financial leadership source cleared Gate 4 as a "
        "replay-only/default-off lead. No production surface was promoted; a "
        "shared adapter plus parity tests are required before forward use."
        if payload["gate4"]["passed"]
        else (
            "The rates-up financial leadership source did not clear Gate 4; "
            "do not promote or locally retune this relation on the frozen "
            "windows."
        )
    )
    payload["rejection_reason"] = (
        None if payload["gate4"]["passed"] else "; ".join(payload["gate4"]["failed_reasons"])
    )
    old_thin_delta = payload["delta_metrics"]["by_window"]["old_thin"]
    target_count = payload["target_trade_summary"]["total_trade_count"]
    why_result = (
        "The relation likely measures same-day financial beta rather than "
        "durable delayed continuation. Gate 4 observed {count} target trades; "
        "old_thin changed by {ev:+.4f} EV and ${pnl:+,.2f}. If rejected, the "
        "after-cost next-open edge was either already repriced by the close, "
        "too dependent on a few large financial leaders, or missing a more "
        "specific bank/curve/credit catalyst."
    ).format(
        count=target_count,
        ev=old_thin_delta["expected_value_score"],
        pnl=old_thin_delta["total_pnl"],
    )
    payload["post_run_reflection"] = {
        "why_result_happened": why_result,
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping TLT selloff, TLT close-location, "
            "financial median/positive breadth, leader relative return, "
            "volume, volatility, hold-day, top-N, cooldown, or paper notional "
            "on the same frozen windows."
        ),
        "new_evidence_required": (
            "A retry requires a materially new PIT yield-curve proxy, bank "
            "earnings/NIM revision source, credit-spread source, regulatory "
            "event classification, or closed forward replacement-value rows."
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Rates-up fin days | Trades |",
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
                days=scan.get("rates_up_financial_days", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Rates-Up Financial Leadership",
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
            "data/backtests/"
            "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
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
                "rates_up_financial_day_count": payload["context_scan_by_window"][
                    label
                ].get("rates_up_financial_days"),
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
