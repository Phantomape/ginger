"""exp-20260607-022: crypto ETF thrust proxy-stock leadership scout.

Replay-only alpha search. This tests one production-visible free-OHLCV
candidate-source variable: on days where crypto ETFs thrust higher and the
broad tape is not hostile, select the strongest liquid crypto-proxy stocks as
next-open, 10-trading-day default-off paper candidates.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import exp_20260606_019_macro_relief_top2_leadership_candidate_pool as previous


framework = previous.framework

EXPERIMENT_ID = "exp-20260607-022"
STEM = "crypto_etf_thrust_proxy_stock_leadership"
TRIAL_FAMILY = "crypto_etf_thrust_proxy_stock_leadership_candidate_pool"
TRIAL_VARIANT_ID = "ibit_gbtc_ethe_confirmed_crypto_proxy_stock_leadership_top2_10d_v1"
CHANGED_VARIABLE = "crypto_etf_thrust_proxy_stock_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = previous.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260607_022_{STEM}.json"
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

CRYPTO_CONTEXT_TICKERS = {"IBIT", "GBTC", "ETHE", "SPY", "QQQ"}
CRYPTO_PROXY_TICKERS = {
    "BTDR",
    "CIFR",
    "CLSK",
    "COIN",
    "HOOD",
    "HUT",
    "IREN",
    "MARA",
    "MSTR",
    "RIOT",
    "WULF",
}

MIN_IBIT_THRUST_RETURN = 0.025
MIN_GBTC_CONFIRM_RETURN = 0.018
MIN_ETHE_CONFIRM_RETURN = 0.012
MIN_IBIT_CLOSE_LOCATION = 0.58
MIN_GBTC_CLOSE_LOCATION = 0.52
MIN_ETHE_CLOSE_LOCATION = 0.50
MIN_SPY_RETURN = -0.006
MIN_QQQ_RETURN = -0.006
MIN_QQQ_CLOSE_LOCATION = 0.35

MIN_PRICE = 5.0
MIN_AVG_DOLLAR_VOLUME_20D = 20_000_000.0
MIN_SIGNAL_RETURN = 0.025
MIN_RELATIVE_VS_SPY = 0.020
MIN_RELATIVE_VS_QQQ = 0.014
MIN_RELATIVE_VS_IBIT = -0.015
MIN_CLOSE_LOCATION = 0.62
MIN_VOLUME_RATIO_20D = 1.00
MIN_RET20_EXCESS_SPY = -0.08
MIN_RET60_EXCESS_SPY = -0.15
MAX_RET5 = 0.28
MAX_REALIZED_VOL_20D = 0.18

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

PREDICTION = {
    "success_probability": 0.11,
    "expected_ev_delta": 0.10,
    "expected_pnl_delta": 2000.0,
    "main_failure_modes": [
        "near_neighbor_crypto_beta_guard",
        "broad_momentum_relabel",
        "old_thin_regression",
        "drawdown_drift",
        "concentration_failed",
        "thin_sample",
    ],
    "confidence_reason": (
        "Prior IBIT regime-guarded crypto-beta pool failed, but this tests a "
        "narrower event-like ETF thrust plus individual proxy stock leadership "
        "using current canonical warehouse coverage; high concentration and "
        "beta relabel risk keep probability low."
    ),
    "recorded_at": "2026-06-07T17:58:40+00:00",
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
        "require a shared default-off adapter exposing the same IBIT/GBTC/ETHE "
        "crypto ETF thrust context, fixed crypto-proxy stock universe, stock "
        "leadership fields, same-ticker core-overlap exclusion, next-open paper "
        "entry, 10-trading-day exit, costs, cooldown, and concentration controls "
        "in both replay and daily production before any report queue, paper "
        "ledger, candidate priority, sizing, watchlist, or order surface could "
        "change."
    ),
}

BASE_GATE4 = previous.BASE_GATE4
BASE_BUILD_PAYLOAD = previous.BASE_BUILD_PAYLOAD
BASE_PERSIST = previous.BASE_PERSIST
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
        eligible_tickers=set(eligible_tickers)
        | CRYPTO_CONTEXT_TICKERS
        | CRYPTO_PROXY_TICKERS,
    )


def _crypto_context_for_day(
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    signal_date: str,
) -> dict[str, Any] | None:
    required = {
        ticker: (snapshot.get(ticker) or [], indices.get(ticker, {}).get(signal_date))
        for ticker in CRYPTO_CONTEXT_TICKERS
    }
    if any(idx is None for _, idx in required.values()):
        return None

    rows = {ticker: ticker_rows for ticker, (ticker_rows, _) in required.items()}
    idxs = {ticker: int(idx) for ticker, (_, idx) in required.items() if idx is not None}
    daily_returns = {
        ticker: framework._daily_return(rows[ticker], idxs[ticker])
        for ticker in CRYPTO_CONTEXT_TICKERS
    }
    close_locations = {
        ticker: _range_location(rows[ticker][idxs[ticker]])
        for ticker in CRYPTO_CONTEXT_TICKERS
    }
    context = {
        "date": signal_date,
        "ibit_return": framework._round(daily_returns["IBIT"], 6),
        "gbtc_return": framework._round(daily_returns["GBTC"], 6),
        "ethe_return": framework._round(daily_returns["ETHE"], 6),
        "spy_return": framework._round(daily_returns["SPY"], 6),
        "qqq_return": framework._round(daily_returns["QQQ"], 6),
        "ibit_close_location": framework._round(close_locations["IBIT"], 6),
        "gbtc_close_location": framework._round(close_locations["GBTC"], 6),
        "ethe_close_location": framework._round(close_locations["ETHE"], 6),
        "spy_close_location": framework._round(close_locations["SPY"], 6),
        "qqq_close_location": framework._round(close_locations["QQQ"], 6),
        "min_ibit_thrust_return": MIN_IBIT_THRUST_RETURN,
        "min_gbtc_confirm_return": MIN_GBTC_CONFIRM_RETURN,
        "min_ethe_confirm_return": MIN_ETHE_CONFIRM_RETURN,
        "min_ibit_close_location": MIN_IBIT_CLOSE_LOCATION,
        "min_gbtc_close_location": MIN_GBTC_CLOSE_LOCATION,
        "min_ethe_close_location": MIN_ETHE_CLOSE_LOCATION,
        "min_spy_return": MIN_SPY_RETURN,
        "min_qqq_return": MIN_QQQ_RETURN,
        "min_qqq_close_location": MIN_QQQ_CLOSE_LOCATION,
        "rule_version": RULE_VERSION,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }
    if any(value is None for value in daily_returns.values()):
        return {**context, "passed": False, "reason": "missing_daily_return"}
    if any(value is None for value in close_locations.values()):
        return {**context, "passed": False, "reason": "missing_close_location"}
    if daily_returns["IBIT"] < MIN_IBIT_THRUST_RETURN:
        return {**context, "passed": False, "reason": "ibit_thrust_too_low"}
    if daily_returns["GBTC"] < MIN_GBTC_CONFIRM_RETURN:
        return {**context, "passed": False, "reason": "gbtc_confirmation_too_low"}
    if daily_returns["ETHE"] < MIN_ETHE_CONFIRM_RETURN:
        return {**context, "passed": False, "reason": "ethe_confirmation_too_low"}
    if close_locations["IBIT"] < MIN_IBIT_CLOSE_LOCATION:
        return {**context, "passed": False, "reason": "ibit_close_location_too_low"}
    if close_locations["GBTC"] < MIN_GBTC_CLOSE_LOCATION:
        return {**context, "passed": False, "reason": "gbtc_close_location_too_low"}
    if close_locations["ETHE"] < MIN_ETHE_CLOSE_LOCATION:
        return {**context, "passed": False, "reason": "ethe_close_location_too_low"}
    if daily_returns["SPY"] < MIN_SPY_RETURN:
        return {**context, "passed": False, "reason": "spy_tape_too_hostile"}
    if daily_returns["QQQ"] < MIN_QQQ_RETURN:
        return {**context, "passed": False, "reason": "qqq_tape_too_hostile"}
    if close_locations["QQQ"] < MIN_QQQ_CLOSE_LOCATION:
        return {**context, "passed": False, "reason": "qqq_close_location_too_low"}
    return {**context, "passed": True, "reason": "crypto_etf_thrust_passed"}


def _candidate_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    context: dict[str, Any],
) -> dict[str, Any] | None:
    if ticker not in CRYPTO_PROXY_TICKERS:
        return None
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    qqq_rows = snapshot.get("QQQ") or []
    ibit_rows = snapshot.get("IBIT") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    qqq_idx = indices.get("QQQ", {}).get(signal_date)
    ibit_idx = indices.get("IBIT", {}).get(signal_date)
    if idx is None or spy_idx is None or qqq_idx is None or ibit_idx is None:
        return None
    if idx < 60 or spy_idx < 60 or qqq_idx < 60 or ibit_idx < 20:
        return None
    if idx + HOLD_DAYS >= len(rows):
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
    ibit_return = framework._daily_return(ibit_rows, ibit_idx)
    close_location = framework._close_location(row)
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
        ibit_return,
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
    assert ibit_return is not None
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
    relative_vs_ibit = signal_return - ibit_return
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60

    if signal_return < MIN_SIGNAL_RETURN:
        return None
    if relative_vs_spy < MIN_RELATIVE_VS_SPY:
        return None
    if relative_vs_qqq < MIN_RELATIVE_VS_QQQ:
        return None
    if relative_vs_ibit < MIN_RELATIVE_VS_IBIT:
        return None
    if close_location < MIN_CLOSE_LOCATION:
        return None
    if volume_ratio < MIN_VOLUME_RATIO_20D:
        return None
    if ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_RET60_EXCESS_SPY:
        return None
    if ret5 > MAX_RET5:
        return None
    if realized_vol20 > MAX_REALIZED_VOL_20D:
        return None

    sector_meta = sector_entries.get(ticker) or {}
    liquidity_score = math.log10(max(adv20, 1.0) / 1_000_000.0)
    score = (
        1.70 * relative_vs_spy
        + 1.10 * relative_vs_qqq
        + 0.80 * max(relative_vs_ibit, -0.01)
        + 0.70 * ret20_excess_spy
        + 0.28 * ret60_excess_spy
        + 0.28 * close_location
        + 0.06 * min(volume_ratio, 4.0)
        + 0.035 * liquidity_score
        - 0.40 * realized_vol20
        - 0.10 * max(ret5 - 0.18, 0.0)
    )
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "CRYPTO_ETF_THRUST_PROXY_STOCK_LEADERSHIP_PAPER",
        "candidate_score": round(score, 6),
        "candidate_signal_day_return": round(signal_return, 6),
        "candidate_spy_signal_day_return": round(spy_return, 6),
        "candidate_qqq_signal_day_return": round(qqq_return, 6),
        "candidate_ibit_signal_day_return": round(ibit_return, 6),
        "candidate_relative_vs_spy": round(relative_vs_spy, 6),
        "candidate_relative_vs_qqq": round(relative_vs_qqq, 6),
        "candidate_relative_vs_ibit": round(relative_vs_ibit, 6),
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
        "sector_coverage_status": sector_meta.get("status")
        or sector_meta.get("sector_coverage_status"),
        "crypto_etf_thrust_context": context,
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
    contexts: list[dict[str, Any]] = []
    scan = {
        "scanned_trading_days": len(dates),
        "crypto_thrust_days": 0,
        "non_thrust_days": 0,
        "days_with_raw_crypto_proxy_candidates": 0,
        "raw_crypto_proxy_candidates": 0,
        "crypto_context_tickers": sorted(CRYPTO_CONTEXT_TICKERS),
        "crypto_proxy_tickers": sorted(CRYPTO_PROXY_TICKERS),
    }
    for signal_date in dates:
        context = _crypto_context_for_day(snapshot, indices, signal_date)
        if context is None:
            continue
        if not context.get("passed"):
            scan["non_thrust_days"] += 1
            continue
        scan["crypto_thrust_days"] += 1
        day_rows: list[dict[str, Any]] = []
        for ticker in sorted(CRYPTO_PROXY_TICKERS):
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
                -float(row["candidate_relative_vs_ibit"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        scan["days_with_raw_crypto_proxy_candidates"] += 1
        scan["raw_crypto_proxy_candidates"] += len(day_rows)
        contexts.append(
            {
                **context,
                "raw_candidate_count": len(day_rows),
                "top_candidate": day_rows[0]["ticker"],
                "top_candidate_score": day_rows[0]["candidate_score"],
                "top_candidate_relative_vs_spy": day_rows[0]["candidate_relative_vs_spy"],
                "top_candidate_relative_vs_ibit": day_rows[0]["candidate_relative_vs_ibit"],
            }
        )
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["candidate_relative_vs_spy"]),
            -float(row["candidate_relative_vs_ibit"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            row["ticker"],
        )
    )
    scan.update(
        {
            "rule_version": RULE_VERSION,
            "min_ibit_thrust_return": MIN_IBIT_THRUST_RETURN,
            "min_gbtc_confirm_return": MIN_GBTC_CONFIRM_RETURN,
            "min_ethe_confirm_return": MIN_ETHE_CONFIRM_RETURN,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "min_relative_vs_spy": MIN_RELATIVE_VS_SPY,
            "min_relative_vs_qqq": MIN_RELATIVE_VS_QQQ,
            "min_relative_vs_ibit": MIN_RELATIVE_VS_IBIT,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
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
        "positive_replay_lead_not_promoted_crypto_etf_thrust_proxy_stock_leadership"
        if gate["passed"]
        else "rejected_crypto_etf_thrust_proxy_stock_leadership_candidate_pool"
    )
    gate["target_trade_count_min"] = MIN_TARGET_TRADES
    gate["target_window_count_min"] = MIN_TARGET_WINDOWS
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    gate4 = payload["gate4"]
    aggregate = payload["delta_metrics"]["aggregate"]
    accepted = bool(gate4["passed"])
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "IBIT/GBTC/ETHE crypto ETF thrust with SPY/QQQ confirmation "
                "may identify liquid crypto-proxy stock leaders whose next-open "
                "10-day paper continuation beats cash without raw crypto-beta "
                "regime-guard noise."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
            "new_evidence_type": "free_ohlcv_crypto_etf_thrust_relation",
            "nearby_prior_experiments": [
                "exp-20260506-012",
                "exp-20260606-004",
                "exp-20260607-018",
                "exp-20260607-021",
            ],
            "prior_trial_count": 1,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "anti_js": "No JavaScript was used.",
            "decision": gate4["decision"],
            "status": "positive_replay_lead_not_promoted" if accepted else "rejected",
            "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
            "total_pnl_delta": aggregate["total_pnl_delta_sum"],
            "interpretation": (
                "The crypto ETF thrust proxy-stock leadership source cleared "
                "Gate 4 as a replay-only/default-off lead, but no production "
                "surface was promoted."
                if accepted
                else (
                    "The crypto ETF thrust proxy-stock leadership source did "
                    "not clear Gate 4. Do not promote it or answer by retuning "
                    "IBIT/GBTC/ETHE thresholds, proxy ticker list, top-N, "
                    "hold-day, cooldown, or notional on these frozen windows."
                )
            ),
            "rejection_reason": None if accepted else "; ".join(gate4["failed_reasons"]),
            "negative_reflection": (
                "If rejected, the likely reason is that crypto ETF thrust is "
                "still a broad high-beta/momentum relabel, or crypto-proxy "
                "stocks are too concentrated and volatile after next-open "
                "execution costs."
            ),
            "post_run_reflection": {
                "why_result_happened": (
                    "The source produced positive replacement value in all "
                    "three windows without breaching drawdown, survival, or "
                    "concentration guardrails, suggesting same-day crypto ETF "
                    "thrust plus proxy-stock leadership is a distinct relation."
                    if accepted
                    else (
                        "The source failed to add robust replacement value "
                        "after next-open entry and costs. That suggests crypto "
                        "ETF thrust did not reliably separate durable proxy-stock "
                        "leadership from high-beta chase in the canonical windows."
                    )
                ),
                "forbidden_near_neighbor_retry": (
                    "Do not retry by sweeping IBIT/GBTC/ETHE return, close-location, "
                    "SPY/QQQ tape, crypto proxy ticker list, stock close-location, "
                    "volume, ret20/ret60, top-N, hold-day, cooldown, or paper "
                    "notional thresholds on the frozen windows."
                ),
                "new_evidence_required": (
                    "A retry requires materially new PIT crypto-flow evidence, "
                    "such as ETF creations/redemptions, futures basis, exchange "
                    "flow, borrow/option context, or closed forward replacement-value "
                    "rows from a shared default-off adapter."
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
            "crypto_context_tickers": sorted(CRYPTO_CONTEXT_TICKERS),
            "crypto_proxy_tickers": sorted(CRYPTO_PROXY_TICKERS),
            "min_ibit_thrust_return": MIN_IBIT_THRUST_RETURN,
            "min_gbtc_confirm_return": MIN_GBTC_CONFIRM_RETURN,
            "min_ethe_confirm_return": MIN_ETHE_CONFIRM_RETURN,
            "min_ibit_close_location": MIN_IBIT_CLOSE_LOCATION,
            "min_gbtc_close_location": MIN_GBTC_CLOSE_LOCATION,
            "min_ethe_close_location": MIN_ETHE_CLOSE_LOCATION,
            "min_spy_return": MIN_SPY_RETURN,
            "min_qqq_return": MIN_QQQ_RETURN,
            "min_qqq_close_location": MIN_QQQ_CLOSE_LOCATION,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "min_relative_vs_spy": MIN_RELATIVE_VS_SPY,
            "min_relative_vs_qqq": MIN_RELATIVE_VS_QQQ,
            "min_relative_vs_ibit": MIN_RELATIVE_VS_IBIT,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
            "max_ret5": MAX_RET5,
            "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only close-of-day OHLCV available on the signal date: "
        "IBIT, GBTC, ETHE, SPY, and QQQ daily return/range context plus fixed "
        "crypto-proxy stock leadership, liquidity, close-location, volume, "
        "ret5/ret20/ret60, and realized-vol fields. Paper entry is next "
        "available open with existing entry slippage; exit is the close 10 "
        "trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: event-like crypto ETF thrust should force "
            "fast repricing in liquid crypto-proxy equities, but only those "
            "already leading the ETF move by the close deserve next-open paper "
            "observation."
        ),
        "2_history_check": {
            "exp-20260506-012": (
                "Rejected raw crypto-beta candidate pool gated by IBIT above "
                "200MA and positive 20-day momentum. This run is narrower: "
                "same-day IBIT/GBTC/ETHE thrust plus stock-level leadership, "
                "not a regime guard or raw ticker-list promotion."
            ),
            "exp-20260606-004/005": (
                "Broad 5-day winner continuation was rejected for drawdown/tail. "
                "This fixed pool uses crypto ETF thrust as the relation source."
            ),
            "exp-20260607-018/019": (
                "VIXY relief leadership was accepted after shared reproduction; "
                "this tests a different external-asset state and stays replay-only."
            ),
            "exp-20260607-021": (
                "UUP dollar-weakness risk-on leadership failed old_thin/drawdown. "
                "This uses crypto ETF thrust rather than dollar-liquidity relief."
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
            "exp_20260607_022_crypto_etf_thrust_proxy_stock_leadership.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["gate3"]["note"] = (
        "No new core filter or entry rule was added. The crypto ETF thrust "
        "proxy-stock leadership source is additive default-off paper, so core "
        "signals generated/survived are unchanged from baseline."
    )
    runtime_fields = payload.setdefault("gate2", {}).setdefault("runtime_fields", [])
    for field in (
        "IBIT daily OHLCV",
        "GBTC daily OHLCV",
        "ETHE daily OHLCV",
        "fixed crypto-proxy ticker OHLCV",
    ):
        if field not in runtime_fields:
            runtime_fields.insert(3, field)
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Crypto thrust days | Trades |",
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
                days=scan.get("crypto_thrust_days", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Crypto ETF Thrust Proxy-Stock Leadership",
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
        "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
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
                "crypto_thrust_day_count": payload["context_scan_by_window"][label].get(
                    "crypto_thrust_days"
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
