"""exp-20260607-011: precious metals ETF / producer lag candidate pool.

Replay-only alpha search. It tests one free-OHLCV relation source: when GLD or
SLV leads SPY and closes firm, admit one liquid precious-metals producer whose
equity has begun reacting but still lags the ETF move. Paper entry is next-open
with a fixed 10-trading-day hold.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import exp_20260606_029_sector_etf_lead_laggard_candidate_pool as base


EXPERIMENT_ID = "exp-20260607-011"
STEM = "precious_metals_etf_producer_lag"
TRIAL_FAMILY = "precious_metals_etf_producer_lag_candidate_pool"
TRIAL_VARIANT_ID = "gld_slv_precious_producer_lag_top1_next_open_10d_v1"
CHANGED_VARIABLE = "precious_metals_etf_to_producer_lag_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

framework = base.framework
REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260607_011_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 15

COMMODITY_ETF_TICKERS = {"GLD", "SLV"}
PRECIOUS_INDUSTRY_KEYWORDS = ("gold", "silver", "other precious metals")

MIN_PRICE = 5.0
MIN_AVG_DOLLAR_VOLUME_20D = 25_000_000.0
MIN_ETF_SIGNAL_RETURN = 0.0035
MIN_ETF_RELATIVE_VS_SPY = 0.0025
MIN_ETF_CLOSE_LOCATION = 0.55
MIN_ETF_RET20_EXCESS_SPY = -0.030
MIN_CANDIDATE_SIGNAL_RETURN = 0.0
MIN_CANDIDATE_LAG_GAP_VS_ETF = 0.002
MAX_CANDIDATE_LAG_GAP_VS_ETF = 0.055
MIN_CANDIDATE_RET20_EXCESS_SPY = -0.080
MIN_CANDIDATE_CLOSE_LOCATION = 0.55
MAX_CANDIDATE_RET5 = 0.145
MAX_CANDIDATE_REALIZED_VOL_20 = 0.120

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

PREDICTION = {
    "success_probability": 0.42,
    "expected_ev_delta": 0.12,
    "expected_pnl_delta": 3500.0,
    "main_failure_modes": [
        "commodity_etf_move_already_priced_in_producers",
        "thin_producer_universe_concentration",
        "late_strong_only_correlation",
        "old_thin_reversal_after_precious_metals_spikes",
    ],
    "confidence_reason": (
        "Commodity and gold allocation work has shown adjacent edge, while "
        "broad sector ETF laggards failed. This run narrows the relation to "
        "free-OHLCV precious-metals ETF thrusts and liquid producer laggards."
    ),
    "recorded_at": "2026-06-07T09:08:52+00:00",
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
        "require a shared default-off adapter that computes the same GLD/SLV "
        "context fields, precious-metals producer universe, lagging "
        "constructive-equity gates, same-ticker core-overlap exclusion, "
        "next-open paper entry, 10-trading-day exit, costs, cooldown, and "
        "concentration controls in both replay and daily production before "
        "any report queue, paper ledger, candidate priority, sizing, "
        "watchlist, or order surface could change."
    ),
}

BASE_LOAD_WINDOW_SNAPSHOT = base.BASE_LOAD_WINDOW_SNAPSHOT
BASE_BUILD_PAYLOAD = base.BASE_BUILD_PAYLOAD
BASE_GATE4 = base.BASE_GATE4


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _load_window_snapshot(
    *,
    cfg: dict[str, str],
    eligible_tickers: set[str],
) -> dict[str, list[dict[str, Any]]]:
    return BASE_LOAD_WINDOW_SNAPSHOT(
        cfg=cfg,
        eligible_tickers=set(eligible_tickers) | COMMODITY_ETF_TICKERS,
    )


def _is_precious_metals_producer(meta: dict[str, Any]) -> bool:
    if meta.get("sector") != "Basic Materials":
        return False
    industry = str(meta.get("industry") or "").lower()
    return any(keyword in industry for keyword in PRECIOUS_INDUSTRY_KEYWORDS)


def _commodity_contexts_for_day(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    signal_date: str,
) -> list[dict[str, Any]]:
    spy_rows = snapshot.get("SPY") or []
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if spy_idx is None or spy_idx < 20:
        return []
    spy_return = framework._daily_return(spy_rows, spy_idx)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    if spy_return is None or spy_ret20 is None:
        return []

    contexts: list[dict[str, Any]] = []
    for etf in sorted(COMMODITY_ETF_TICKERS):
        rows = snapshot.get(etf) or []
        idx = indices.get(etf, {}).get(signal_date)
        if idx is None or idx < 20:
            continue
        etf_return = framework._daily_return(rows, idx)
        etf_ret20 = framework._ret(rows, idx, 20)
        etf_close_location = framework._close_location(rows[idx])
        etf_volume_ratio = framework._volume_ratio(rows, idx) or 0.0
        if etf_return is None or etf_ret20 is None or etf_close_location is None:
            continue
        etf_relative_vs_spy = etf_return - spy_return
        etf_ret20_excess_spy = etf_ret20 - spy_ret20
        if etf_return < MIN_ETF_SIGNAL_RETURN:
            continue
        if etf_relative_vs_spy < MIN_ETF_RELATIVE_VS_SPY:
            continue
        if etf_close_location < MIN_ETF_CLOSE_LOCATION:
            continue
        if etf_ret20_excess_spy < MIN_ETF_RET20_EXCESS_SPY:
            continue
        contexts.append(
            {
                "date": signal_date,
                "commodity_etf_ticker": etf,
                "commodity_family": "gold" if etf == "GLD" else "silver",
                "passed": True,
                "reason": "precious_metals_etf_thrust_passed",
                "commodity_etf_signal_day_return": round(etf_return, 6),
                "spy_signal_day_return": round(spy_return, 6),
                "commodity_etf_relative_vs_spy": round(etf_relative_vs_spy, 6),
                "commodity_etf_ret20": round(etf_ret20, 6),
                "spy_ret20": round(spy_ret20, 6),
                "commodity_etf_ret20_excess_spy": round(etf_ret20_excess_spy, 6),
                "commodity_etf_close_location": round(etf_close_location, 6),
                "commodity_etf_volume_ratio_20d": round(etf_volume_ratio, 6),
                "rule_version": RULE_VERSION,
            }
        )
    return contexts


def _candidate_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    context: dict[str, Any],
) -> dict[str, Any] | None:
    if ticker in COMMODITY_ETF_TICKERS:
        return None
    sector_meta = sector_entries.get(ticker) or {}
    if not _is_precious_metals_producer(sector_meta):
        return None
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None:
        return None
    if idx < 20 or spy_idx < 20 or idx + HOLD_DAYS >= len(rows):
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
    etf_signal_return = float(context["commodity_etf_signal_day_return"])
    lag_gap_vs_etf = etf_signal_return - signal_return
    if signal_return < MIN_CANDIDATE_SIGNAL_RETURN:
        return None
    if lag_gap_vs_etf < MIN_CANDIDATE_LAG_GAP_VS_ETF:
        return None
    if lag_gap_vs_etf > MAX_CANDIDATE_LAG_GAP_VS_ETF:
        return None
    close_location = framework._close_location(row)
    if close_location is None or close_location < MIN_CANDIDATE_CLOSE_LOCATION:
        return None
    ret5 = framework._ret(rows, idx, 5)
    ret20 = framework._ret(rows, idx, 20)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    realized_vol = framework._realized_vol(rows, idx)
    if ret5 is None or ret20 is None or spy_ret20 is None or realized_vol is None:
        return None
    if ret5 > MAX_CANDIDATE_RET5:
        return None
    if realized_vol > MAX_CANDIDATE_REALIZED_VOL_20:
        return None
    ret20_excess_spy = ret20 - spy_ret20
    if ret20_excess_spy < MIN_CANDIDATE_RET20_EXCESS_SPY:
        return None
    volume_ratio = framework._volume_ratio(rows, idx) or 0.0
    relative_vs_spy = signal_return - spy_return
    score = (
        1.30 * float(context["commodity_etf_relative_vs_spy"])
        + 0.85 * lag_gap_vs_etf
        + 0.45 * ret20_excess_spy
        + 0.32 * close_location
        + 0.035 * math.log10(max(adv20, 1.0) / 1_000_000.0)
        - 0.38 * realized_vol
        - 0.03 * max(volume_ratio - 2.2, 0.0)
    )
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "PRECIOUS_METALS_ETF_PRODUCER_LAG_PAPER",
        "candidate_score": round(score, 6),
        "candidate_signal_day_return": round(signal_return, 6),
        "candidate_relative_vs_spy": round(relative_vs_spy, 6),
        "candidate_relative_vs_commodity_etf": round(signal_return - etf_signal_return, 6),
        "candidate_lag_gap_vs_commodity_etf": round(lag_gap_vs_etf, 6),
        "candidate_ret5": round(ret5, 6),
        "candidate_ret20": round(ret20, 6),
        "candidate_spy_ret20": round(spy_ret20, 6),
        "candidate_ret20_excess_spy": round(ret20_excess_spy, 6),
        "candidate_close_location": round(close_location, 6),
        "candidate_avg_dollar_volume_20d": round(adv20, 2),
        "candidate_volume_ratio_20d": round(volume_ratio, 6),
        "candidate_realized_vol_20d": round(realized_vol, 6),
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "sector_coverage_status": sector_meta.get("sector_coverage_status"),
        "commodity_etf_context": context,
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
        if _is_precious_metals_producer(meta)
    }
    candidates: list[dict[str, Any]] = []
    contexts: list[dict[str, Any]] = []
    context_scan = {
        "scanned_trading_days": len(dates),
        "commodity_etf_thrust_contexts": 0,
        "commodity_etf_thrust_days": 0,
        "commodity_etf_context_by_ticker": {},
        "candidate_producer_count": len(stock_entries),
        "commodity_etfs_used": sorted(COMMODITY_ETF_TICKERS),
        "candidate_industries": sorted(
            {str(meta.get("industry") or "") for meta in stock_entries.values()}
        ),
    }
    lead_dates: set[str] = set()
    etf_counts: dict[str, int] = {}
    for signal_date in dates:
        day_contexts = _commodity_contexts_for_day(
            snapshot=snapshot,
            indices=indices,
            signal_date=signal_date,
        )
        if not day_contexts:
            continue
        lead_dates.add(signal_date)
        for context in day_contexts:
            contexts.append(context)
            etf = str(context["commodity_etf_ticker"])
            etf_counts[etf] = etf_counts.get(etf, 0) + 1
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
            -float(row["candidate_lag_gap_vs_commodity_etf"]),
            -float(row["candidate_ret20_excess_spy"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            str(row.get("industry") or ""),
            row["ticker"],
        )
    )
    context_scan["commodity_etf_thrust_contexts"] = len(contexts)
    context_scan["commodity_etf_thrust_days"] = len(lead_dates)
    context_scan["commodity_etf_context_by_ticker"] = etf_counts
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
        "positive_replay_lead_not_promoted_precious_metals_etf_producer_lag"
        if gate["passed"]
        else "rejected_precious_metals_etf_producer_lag_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    aggregate = payload["delta_metrics"]["aggregate"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "entry/candidate_pool: GLD or SLV leadership may reveal "
                "liquid precious-metals producers whose operating-leverage "
                "equities have not fully repriced by the signal close."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
            "new_evidence_type": "free_ohlcv_commodity_etf_to_producer_relation",
            "nearby_prior_experiments": [
                "exp-20260514-018",
                "exp-20260514-049",
                "exp-20260514-050",
                "exp-20260606-029",
            ],
            "prior_trial_count": 1,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "anti_js": "No JavaScript was used.",
            "commodity_etf_contexts_by_window": payload["pressure_contexts_by_window"],
            "commodity_etf_context_samples_by_window": payload[
                "pressure_context_samples_by_window"
            ],
            "negative_reflection": (
                "If rejected, the likely reason is that precious-metals "
                "producer equities already price GLD/SLV thrusts intraday, "
                "or the producer universe is too concentrated for a robust "
                "candidate-pool sleeve. Do not locally retune GLD/SLV return, "
                "lag-gap, close-location, hold-day, cooldown, or notional "
                "thresholds on the same frozen windows; a retry needs new PIT "
                "relation evidence such as producer-specific realized "
                "commodity sensitivity, futures term structure, or forward "
                "out-of-sample replacement rows."
            ),
            "next_evidence_needed": (
                "A positive replay lead still needs a shared default-off "
                "adapter and parity tests before production observation. Live "
                "activation would require a separate Gate 1-4 execution "
                "envelope with liquidity, concentration, and sleeve "
                "displacement constraints."
            ),
        }
    )
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "commodity_etf_tickers": sorted(COMMODITY_ETF_TICKERS),
        "precious_industry_keywords": PRECIOUS_INDUSTRY_KEYWORDS,
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "min_etf_signal_return": MIN_ETF_SIGNAL_RETURN,
        "min_etf_relative_vs_spy": MIN_ETF_RELATIVE_VS_SPY,
        "min_etf_close_location": MIN_ETF_CLOSE_LOCATION,
        "min_etf_ret20_excess_spy": MIN_ETF_RET20_EXCESS_SPY,
        "min_candidate_signal_return": MIN_CANDIDATE_SIGNAL_RETURN,
        "min_candidate_lag_gap_vs_etf": MIN_CANDIDATE_LAG_GAP_VS_ETF,
        "max_candidate_lag_gap_vs_etf": MAX_CANDIDATE_LAG_GAP_VS_ETF,
        "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
        "min_candidate_close_location": MIN_CANDIDATE_CLOSE_LOCATION,
        "max_candidate_ret5": MAX_CANDIDATE_RET5,
        "max_candidate_realized_vol_20": MAX_CANDIDATE_REALIZED_VOL_20,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"].update(
        {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "replay-only GLD/SLV precious-metals producer lag paper overlay"
            ),
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "commodity_etf_context_tickers": sorted(COMMODITY_ETF_TICKERS),
            "execution_model": (
                "Signal uses only close-of-day OHLCV available on signal date. "
                "Paper entry is next available open with existing entry "
                "slippage; exit is the close 10 trading days after the signal "
                "with target-side sell slippage and ROUND_TRIP_COST_PCT."
            ),
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: after GLD or SLV leads SPY and closes firm, "
            "liquid precious-metals producer equities that are positive but "
            "still lag the ETF can catch up over the next 10 trading days."
        ),
        "2_history_check": {
            "exp-20260514-018": (
                "Accepted commodity near-high cap showed commodity sleeve edge "
                "inside core allocation, not an ETF-to-producer candidate pool."
            ),
            "exp-20260514-049": (
                "Accepted commodity breakout cap supported commodity exposure "
                "but did not rank producer equities from ETF context."
            ),
            "exp-20260514-050": (
                "Accepted GLD/IAU commodity near-high cap supports gold "
                "context value; this run uses GLD/SLV only as relation "
                "context, not traded ETF members."
            ),
            "exp-20260606-029": (
                "Broad sector ETF-to-stock laggards failed. This run narrows "
                "to precious-metals commodity beta and producer operating "
                "leverage rather than generic sector rotation."
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
            "exp_20260607_011_precious_metals_etf_producer_lag.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["gate2"]["runtime_fields"] = [
        "warehouse ohlcv Date/Open/High/Low/Close/Volume",
        "SPY daily OHLCV",
        "GLD/SLV daily OHLCV",
        "data/reference/broad_market_sector_map.json sector/industry/status",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["gate3"]["note"] = (
        "No new core filter or entry rule was added. The precious-metals "
        "producer lag source is additive default-off paper, so core signals "
        "generated/survived are unchanged from baseline."
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
    if payload["gate4"]["passed"]:
        payload["post_run_reflection"] = {
            "why_result_happened": (
                "The fixed GLD/SLV producer-lag policy found enough liquid "
                "producer catch-up trades across all three windows without "
                "creating drawdown or concentration failures. Because this "
                "runner is replay-only, the measured edge is not yet a "
                "production-visible accepted alpha."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune GLD/SLV return, lag-gap, close-location, "
                "hold-day, cooldown, or notional thresholds on these frozen "
                "windows. A replay lead must move to shared default-off "
                "adapter parity before any further parameter work."
            ),
            "new_evidence_required": (
                "A shared replay/daily helper with parity, forward "
                "replacement rows, and live-realistic execution envelope "
                "evidence are required before promotion."
            ),
        }
    else:
        payload["post_run_reflection"] = {
            "why_result_happened": (
                "Gate 4 failed even though the sleeve generated 76 trades and "
                "positive aggregate PnL, because expected_value_score fell and "
                "late_strong regressed on both EV and PnL. The GLD/SLV move "
                "appears to be priced into producer equities quickly enough "
                "that a next-open catch-up sleeve does not add robust "
                "replacement value."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry by nudging ETF-return, lag-gap, close-location, "
                "hold-day, cooldown, liquidity, or notional thresholds on "
                "these same windows. Also avoid re-labeling the same GLD/SLV "
                "producer lag relation as a commodity, miner, or precious "
                "metals breadth variant without new data."
            ),
            "new_evidence_required": (
                "A valid retry needs new PIT relation evidence such as "
                "producer-specific realized commodity beta, futures curve "
                "state, mine-region shock data, or forward out-of-sample rows "
                "showing the lag is not already priced by the next open."
            ),
        }
    payload["interpretation"] = (
        "The GLD/SLV producer-lag source cleared Gate 4 as a replay-only/"
        "default-off lead. No production surface was promoted; a shared "
        "adapter plus parity tests are required before forward use."
        if payload["gate4"]["passed"]
        else (
            "The GLD/SLV producer-lag source did not clear Gate 4; do not "
            "promote or locally retune this commodity ETF-to-producer "
            "relation on the frozen windows."
        )
    )
    payload["rejection_reason"] = (
        None if payload["gate4"]["passed"] else "; ".join(payload["gate4"]["failed_reasons"])
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | ETF days | Trades |",
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
                days=scan.get("commodity_etf_thrust_days", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Precious Metals ETF / Producer Lag",
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
        "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": "docs/backtesting.md accepted core baseline",
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
                "commodity_etf_thrust_day_count": payload["context_scan_by_window"][
                    label
                ].get("commodity_etf_thrust_days"),
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
