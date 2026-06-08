"""exp-20260608-004: industry stable-leadership scout.

Replay-only alpha search. This tests one production-visible free-OHLCV
candidate-source variable: in already-strong liquid industry groups, select the
stable low-volatility leader rather than generic broad momentum names.

No production code, shared adapter, live/default orders, ranking, sizing, exits,
LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any

import exp_20260607_018_volatility_relief_stock_leadership as previous


framework = previous.framework

EXPERIMENT_ID = "exp-20260608-004"
STEM = "industry_stable_leadership"
TRIAL_FAMILY = "industry_stable_leadership_candidate_pool"
TRIAL_VARIANT_ID = "strong_industry_low_vol_leader_top1_10d_v1"
CHANGED_VARIABLE = "industry_stable_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = previous.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260608_004_{STEM}.json"
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

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_INDUSTRY_LIQUID_COUNT = 6
MIN_GROUP_MEDIAN_RET20_EXCESS_SPY = 0.020
MIN_GROUP_RET20_POSITIVE_FRACTION = 0.62
MIN_GROUP_SIGNAL_POSITIVE_FRACTION = 0.50
MIN_GROUP_SIGNAL_RELATIVE_VS_SPY_MEDIAN = -0.002
MAX_GROUP_RET20_DISPERSION = 0.180
MAX_GROUP_MEDIAN_REALIZED_VOL_20D = 0.055
MIN_CANDIDATE_RET20_EXCESS_SPY = 0.025
MIN_CANDIDATE_RET20_LEAD_VS_GROUP = 0.005
MIN_CANDIDATE_RET60_EXCESS_SPY = 0.000
MIN_SIGNAL_RETURN = 0.002
MIN_SIGNAL_RELATIVE_VS_SPY = 0.000
MIN_CLOSE_LOCATION = 0.58
MIN_VOLUME_RATIO_20D = 0.65
MAX_VOLUME_RATIO_20D = 2.60
MIN_RET5 = -0.030
MAX_RET5 = 0.100
MAX_REALIZED_VOL_20D = 0.070
MAX_CANDIDATE_VOL_VS_GROUP_MULTIPLE = 1.20

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

PREDICTION = {
    "success_probability": 0.17,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "broad_momentum_relabel",
        "old_thin_regression",
        "drawdown_drift",
        "industry_beta_relabel",
        "target_sample_too_small",
    ],
    "confidence_reason": (
        "Accepted industry-relative laggard repair shows industry relations can "
        "work, but recent industry breadth and broad low-beta neighbors failed. "
        "This tests a distinct stable low-vol leader relation, not a threshold "
        "retune of the accepted laggard adapter."
    ),
    "recorded_at": "2026-06-08T03:04:40+00:00",
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
        "require a shared default-off adapter exposing the same industry "
        "strength/stability context, broad-market sector-known liquid stock "
        "universe, stable-leadership fields, same-ticker core-overlap "
        "exclusion, next-open paper entry, 10-trading-day exit, costs, "
        "cooldown, and concentration controls in both replay and daily "
        "production before any report queue, paper ledger, candidate priority, "
        "sizing, watchlist, or order surface could change."
    ),
}

BASE_GATE4 = previous.BASE_GATE4
BASE_BUILD_PAYLOAD = previous.BASE_BUILD_PAYLOAD
BASE_PERSIST = previous.BASE_PERSIST
BASE_LOAD_WINDOW_SNAPSHOT = previous.BASE_LOAD_WINDOW_SNAPSHOT

EXCLUDED_TICKERS = {
    "ARKX",
    "BIL",
    "CPER",
    "DIA",
    "GLD",
    "IAU",
    "IBIT",
    "IEF",
    "IWM",
    "QQQ",
    "SHY",
    "SLV",
    "SPY",
    "TLT",
    "UFO",
    "UUP",
    "USO",
    "VIXM",
    "VIXY",
    "VXX",
    "XLB",
    "XLE",
    "XLF",
    "XLI",
    "XLK",
    "XLP",
    "XLU",
    "XLV",
    "XLY",
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _p90_minus_p10(values: list[float]) -> float | None:
    if len(values) < 3:
        return None
    ordered = sorted(values)
    p10 = ordered[max(0, int((len(ordered) - 1) * 0.10))]
    p90 = ordered[min(len(ordered) - 1, int((len(ordered) - 1) * 0.90))]
    return p90 - p10


def _group_key(meta: dict[str, Any]) -> str:
    industry = str(meta.get("industry") or "").strip()
    if industry and industry.lower() != "unknown":
        return industry
    return str(meta.get("sector") or "unknown").strip() or "unknown"


def _candidate_stats(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    if ticker in EXCLUDED_TICKERS:
        return None
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None or idx < 60 or spy_idx < 60:
        return None
    if idx + HOLD_DAYS >= len(rows):
        return None
    close = framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    signal_return = framework._daily_return(rows, idx)
    spy_signal_return = framework._daily_return(spy_rows, spy_idx)
    ret5 = framework._ret(rows, idx, 5)
    ret20 = framework._ret(rows, idx, 20)
    ret60 = framework._ret(rows, idx, 60)
    spy_ret20 = framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = framework._ret(spy_rows, spy_idx, 60)
    close_location = framework._close_location(rows[idx])
    volume_ratio = framework._volume_ratio(rows, idx)
    realized_vol20 = framework._realized_vol(rows, idx, 20)
    required = [
        signal_return,
        spy_signal_return,
        ret5,
        ret20,
        ret60,
        spy_ret20,
        spy_ret60,
        close_location,
        volume_ratio,
        realized_vol20,
    ]
    if any(value is None for value in required):
        return None
    assert signal_return is not None
    assert spy_signal_return is not None
    assert ret5 is not None
    assert ret20 is not None
    assert ret60 is not None
    assert spy_ret20 is not None
    assert spy_ret60 is not None
    assert close_location is not None
    assert volume_ratio is not None
    assert realized_vol20 is not None
    return {
        "ticker": ticker,
        "signal_return": signal_return,
        "spy_signal_return": spy_signal_return,
        "signal_relative_vs_spy": signal_return - spy_signal_return,
        "ret5": ret5,
        "ret20": ret20,
        "ret60": ret60,
        "ret20_excess_spy": ret20 - spy_ret20,
        "ret60_excess_spy": ret60 - spy_ret60,
        "close_location": close_location,
        "volume_ratio_20d": volume_ratio,
        "avg_dollar_volume_20d": adv20,
        "realized_vol_20d": realized_vol20,
    }


def _industry_contexts_for_day(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    signal_date: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    stats_by_ticker: dict[str, dict[str, Any]] = {}
    for ticker, meta in sector_entries.items():
        stats = _candidate_stats(
            snapshot=snapshot,
            indices=indices,
            ticker=ticker,
            signal_date=signal_date,
        )
        if stats is None:
            continue
        group = _group_key(meta)
        stats["group_key"] = group
        stats_by_ticker[ticker] = stats
        groups[group].append(stats)

    contexts: dict[str, dict[str, Any]] = {}
    for group, rows in groups.items():
        if len(rows) < MIN_INDUSTRY_LIQUID_COUNT:
            continue
        ret20_values = [float(row["ret20_excess_spy"]) for row in rows]
        signal_values = [float(row["signal_relative_vs_spy"]) for row in rows]
        vol_values = [float(row["realized_vol_20d"]) for row in rows]
        dispersion = _p90_minus_p10(ret20_values)
        if dispersion is None:
            continue
        median_ret20 = median(ret20_values)
        median_signal = median(signal_values)
        median_vol = median(vol_values)
        positive_fraction = sum(1 for value in ret20_values if value > 0.0) / len(rows)
        signal_positive_fraction = (
            sum(1 for value in signal_values if value > 0.0) / len(rows)
        )
        context = {
            "date": signal_date,
            "group_key": group,
            "liquid_group_count": len(rows),
            "median_ret20_excess_spy": round(median_ret20, 6),
            "ret20_positive_fraction": round(positive_fraction, 6),
            "median_signal_relative_vs_spy": round(median_signal, 6),
            "signal_positive_fraction": round(signal_positive_fraction, 6),
            "ret20_dispersion_p90_minus_p10": round(dispersion, 6),
            "median_realized_vol_20d": round(median_vol, 6),
            "rule_version": RULE_VERSION,
            "known_at": "after_signal_day_close_before_next_open_paper_entry",
        }
        if median_ret20 < MIN_GROUP_MEDIAN_RET20_EXCESS_SPY:
            continue
        if positive_fraction < MIN_GROUP_RET20_POSITIVE_FRACTION:
            continue
        if signal_positive_fraction < MIN_GROUP_SIGNAL_POSITIVE_FRACTION:
            continue
        if median_signal < MIN_GROUP_SIGNAL_RELATIVE_VS_SPY_MEDIAN:
            continue
        if dispersion > MAX_GROUP_RET20_DISPERSION:
            continue
        if median_vol > MAX_GROUP_MEDIAN_REALIZED_VOL_20D:
            continue
        contexts[group] = {**context, "passed": True}
    return contexts, stats_by_ticker


def _candidate_for_ticker(
    *,
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    context: dict[str, Any],
    stats: dict[str, Any],
) -> dict[str, Any] | None:
    group_median = float(context["median_ret20_excess_spy"])
    group_median_vol = float(context["median_realized_vol_20d"])
    if float(stats["ret20_excess_spy"]) < MIN_CANDIDATE_RET20_EXCESS_SPY:
        return None
    ret20_lead_vs_group = float(stats["ret20_excess_spy"]) - group_median
    if ret20_lead_vs_group < MIN_CANDIDATE_RET20_LEAD_VS_GROUP:
        return None
    if float(stats["ret60_excess_spy"]) < MIN_CANDIDATE_RET60_EXCESS_SPY:
        return None
    if float(stats["signal_return"]) < MIN_SIGNAL_RETURN:
        return None
    if float(stats["signal_relative_vs_spy"]) < MIN_SIGNAL_RELATIVE_VS_SPY:
        return None
    if float(stats["close_location"]) < MIN_CLOSE_LOCATION:
        return None
    if not (MIN_VOLUME_RATIO_20D <= float(stats["volume_ratio_20d"]) <= MAX_VOLUME_RATIO_20D):
        return None
    if not (MIN_RET5 <= float(stats["ret5"]) <= MAX_RET5):
        return None
    max_vol = min(
        MAX_REALIZED_VOL_20D,
        max(0.015, group_median_vol * MAX_CANDIDATE_VOL_VS_GROUP_MULTIPLE),
    )
    if float(stats["realized_vol_20d"]) > max_vol:
        return None
    meta = sector_entries[ticker]
    liquidity_score = math.log10(max(float(stats["avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
    score = (
        1.55 * ret20_lead_vs_group
        + 1.20 * float(stats["ret20_excess_spy"])
        + 0.65 * float(stats["ret60_excess_spy"])
        + 0.60 * float(stats["signal_relative_vs_spy"])
        + 0.24 * float(stats["close_location"])
        + 0.05 * min(float(stats["volume_ratio_20d"]), 2.6)
        + 0.04 * liquidity_score
        - 0.90 * float(stats["realized_vol_20d"])
        - 0.20 * max(float(stats["ret5"]), 0.0)
    )
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "INDUSTRY_STABLE_LEADERSHIP_PAPER",
        "candidate_score": round(score, 6),
        "candidate_group_key": context["group_key"],
        "candidate_ret20_lead_vs_group": round(ret20_lead_vs_group, 6),
        "candidate_signal_day_return": round(float(stats["signal_return"]), 6),
        "candidate_signal_relative_vs_spy": round(
            float(stats["signal_relative_vs_spy"]),
            6,
        ),
        "candidate_close_location": round(float(stats["close_location"]), 6),
        "candidate_volume_ratio_20d": round(float(stats["volume_ratio_20d"]), 6),
        "candidate_avg_dollar_volume_20d": round(
            float(stats["avg_dollar_volume_20d"]),
            2,
        ),
        "candidate_ret5": round(float(stats["ret5"]), 6),
        "candidate_ret20_excess_spy": round(float(stats["ret20_excess_spy"]), 6),
        "candidate_ret60_excess_spy": round(float(stats["ret60_excess_spy"]), 6),
        "candidate_realized_vol_20d": round(float(stats["realized_vol_20d"]), 6),
        "sector": meta.get("sector"),
        "industry": meta.get("industry"),
        "sector_coverage_status": meta.get("sector_coverage_status"),
        "industry_stable_leadership_context": context,
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
        "days_with_stable_industry_groups": 0,
        "stable_industry_group_rows": 0,
        "days_with_raw_candidates": 0,
        "raw_candidate_rows": 0,
        "unique_candidate_tickers": 0,
    }
    unique_tickers: set[str] = set()
    for signal_date in dates:
        group_contexts, stats_by_ticker = _industry_contexts_for_day(
            snapshot=snapshot,
            indices=indices,
            sector_entries=sector_entries,
            signal_date=signal_date,
        )
        if not group_contexts:
            continue
        scan["days_with_stable_industry_groups"] += 1
        scan["stable_industry_group_rows"] += len(group_contexts)
        day_rows: list[dict[str, Any]] = []
        for ticker, stats in stats_by_ticker.items():
            context = group_contexts.get(str(stats.get("group_key") or ""))
            if context is None:
                continue
            row = _candidate_for_ticker(
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                context=context,
                stats=stats,
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
            contexts.append(
                {
                    "date": signal_date,
                    "stable_industry_group_count": len(group_contexts),
                    "raw_candidate_count": 0,
                    "rule_version": RULE_VERSION,
                }
            )
            continue
        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_score"]),
                -float(row["candidate_ret20_lead_vs_group"]),
                -float(row["candidate_ret20_excess_spy"]),
                float(row["candidate_realized_vol_20d"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                str(row.get("candidate_group_key") or ""),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        unique_tickers.update(row["ticker"] for row in day_rows)
        scan["days_with_raw_candidates"] += 1
        scan["raw_candidate_rows"] += len(day_rows)
        contexts.append(
            {
                "date": signal_date,
                "stable_industry_group_count": len(group_contexts),
                "raw_candidate_count": len(day_rows),
                "top_candidate": day_rows[0]["ticker"],
                "top_group_key": day_rows[0]["candidate_group_key"],
                "top_score": day_rows[0]["candidate_score"],
                "top_ret20_lead_vs_group": day_rows[0][
                    "candidate_ret20_lead_vs_group"
                ],
                "top_ret20_excess_spy": day_rows[0]["candidate_ret20_excess_spy"],
                "top_realized_vol_20d": day_rows[0]["candidate_realized_vol_20d"],
            }
        )
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["candidate_ret20_lead_vs_group"]),
            -float(row["candidate_ret20_excess_spy"]),
            float(row["candidate_realized_vol_20d"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            str(row.get("candidate_group_key") or ""),
            row["ticker"],
        )
    )
    scan.update(
        {
            "rule_version": RULE_VERSION,
            "unique_candidate_tickers": len(unique_tickers),
            "min_industry_liquid_count": MIN_INDUSTRY_LIQUID_COUNT,
            "min_group_median_ret20_excess_spy": MIN_GROUP_MEDIAN_RET20_EXCESS_SPY,
            "min_group_ret20_positive_fraction": MIN_GROUP_RET20_POSITIVE_FRACTION,
            "min_group_signal_positive_fraction": MIN_GROUP_SIGNAL_POSITIVE_FRACTION,
            "min_group_signal_relative_vs_spy_median": (
                MIN_GROUP_SIGNAL_RELATIVE_VS_SPY_MEDIAN
            ),
            "max_group_ret20_dispersion": MAX_GROUP_RET20_DISPERSION,
            "max_group_median_realized_vol_20d": MAX_GROUP_MEDIAN_REALIZED_VOL_20D,
            "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
            "min_candidate_ret20_lead_vs_group": MIN_CANDIDATE_RET20_LEAD_VS_GROUP,
            "min_candidate_ret60_excess_spy": MIN_CANDIDATE_RET60_EXCESS_SPY,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "min_signal_relative_vs_spy": MIN_SIGNAL_RELATIVE_VS_SPY,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "max_volume_ratio_20d": MAX_VOLUME_RATIO_20D,
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
        "positive_replay_lead_not_promoted_industry_stable_leadership"
        if gate["passed"]
        else "rejected_industry_stable_leadership_candidate_pool"
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
                "Stable low-volatility leaders inside already-strong liquid "
                "industry groups may add cleaner next-open 10-day default-off "
                "candidate-pool replacement value than broad momentum."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
            "new_evidence_type": "free_ohlcv_industry_stability_relation",
            "nearby_prior_experiments": [
                "exp-20260607-008",
                "exp-20260607-009",
                "exp-20260607-010",
                "exp-20260607-012",
                "exp-20260607-014",
                "exp-20260605-013",
            ],
            "prior_trial_count": 6,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "anti_js": "No JavaScript was used.",
            "decision": gate4["decision"],
            "status": "positive_replay_lead_not_promoted" if accepted else "rejected",
            "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
            "total_pnl_delta": aggregate["total_pnl_delta_sum"],
            "interpretation": (
                "The industry stable-leadership source cleared Gate 4 as a "
                "replay-only/default-off lead, but no production surface was "
                "promoted."
                if accepted
                else (
                    "The industry stable-leadership source improved EV and PnL "
                    "in all three windows, but it did not clear Gate 4 because "
                    "the drawdown drift exceeded the risk guardrail. Do not "
                    "promote it or answer by retuning industry strength, leader, "
                    "low-volatility, top-N, hold-day, cooldown, or notional "
                    "thresholds on these frozen windows."
                )
            ),
            "rejection_reason": None if accepted else "; ".join(gate4["failed_reasons"]),
            "negative_reflection": (
                "If rejected, the likely reason is that stable industry leaders "
                "do contain continuation alpha but still add too much crash-tail "
                "or synchronized industry beta for the current risk envelope."
            ),
            "post_run_reflection": {
                "why_result_happened": (
                    "The source produced positive replacement value in all three "
                    "windows without breaching drawdown, survival, or concentration "
                    "guardrails, suggesting stable leadership inside a strong "
                    "industry relation added independent information."
                    if accepted
                    else (
                        "The source produced positive EV and PnL in all three "
                        "canonical windows with broad sample and low positive-PnL "
                        "concentration, but the maximum drawdown drift breached "
                        "the +0.5pp guardrail. That suggests the relation has "
                        "some continuation value, but the current fixed package "
                        "does not control synchronized industry beta or crash-tail "
                        "well enough to retain."
                    )
                ),
                "forbidden_near_neighbor_retry": (
                    "Do not retry by sweeping industry ret20 strength, industry "
                    "positive fraction, dispersion, low-volatility, candidate "
                    "ret20 lead, close-location, volume, top-N, hold-day, "
                    "cooldown, or paper notional thresholds on the frozen windows."
                ),
                "new_evidence_required": (
                    "A retry requires materially new PIT relation evidence, such "
                    "as peer taxonomy quality, supplier/customer links, industry "
                    "earnings/revision propagation, or closed forward "
                    "replacement-value rows from a shared default-off adapter."
                ),
            },
            "next_evidence_needed": (
                "A positive replay lead still needs a shared default-off adapter "
                "and parity tests before forward observation; live activation "
                "would require closed forward replacement-value rows and a "
                "separate activation-envelope Gate 1-4."
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
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "min_industry_liquid_count": MIN_INDUSTRY_LIQUID_COUNT,
            "min_group_median_ret20_excess_spy": MIN_GROUP_MEDIAN_RET20_EXCESS_SPY,
            "min_group_ret20_positive_fraction": MIN_GROUP_RET20_POSITIVE_FRACTION,
            "min_group_signal_positive_fraction": MIN_GROUP_SIGNAL_POSITIVE_FRACTION,
            "min_group_signal_relative_vs_spy_median": (
                MIN_GROUP_SIGNAL_RELATIVE_VS_SPY_MEDIAN
            ),
            "max_group_ret20_dispersion": MAX_GROUP_RET20_DISPERSION,
            "max_group_median_realized_vol_20d": MAX_GROUP_MEDIAN_REALIZED_VOL_20D,
            "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
            "min_candidate_ret20_lead_vs_group": MIN_CANDIDATE_RET20_LEAD_VS_GROUP,
            "min_candidate_ret60_excess_spy": MIN_CANDIDATE_RET60_EXCESS_SPY,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "min_signal_relative_vs_spy": MIN_SIGNAL_RELATIVE_VS_SPY,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "max_volume_ratio_20d": MAX_VOLUME_RATIO_20D,
            "min_ret5": MIN_RET5,
            "max_ret5": MAX_RET5,
            "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
            "max_candidate_vol_vs_group_multiple": MAX_CANDIDATE_VOL_VS_GROUP_MULTIPLE,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only close-of-day OHLCV available on the signal date plus "
        "prior close history needed for industry 20-day relative strength, "
        "industry dispersion/stability, candidate low-volatility leadership, "
        "ADV, volume ratio, close-location, and 5/20/60-day returns. Paper "
        "entry is next available open with existing entry slippage; exit is "
        "the close 10 trading days after the signal with target-side sell "
        "slippage and ROUND_TRIP_COST_PCT."
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: stable low-volatility leaders inside a "
            "strong liquid industry group may represent institutional "
            "accumulation with less crash-tail than raw broad momentum."
        ),
        "2_history_check": {
            "exp-20260607-008": (
                "Accepted shared industry-relative laggard repair proves an "
                "industry relation can work when it identifies a specific "
                "replacement edge."
            ),
            "exp-20260607-009/010/012/014": (
                "Rejected industry pullback, breadth repair, dispersion, and "
                "volume-breadth variants warn that broad industry confirmation "
                "can become beta or retuned laggard repair."
            ),
            "exp-20260605-013": (
                "Broad low-beta residual momentum failed; this test requires "
                "strong industry context plus candidate leadership, not broad "
                "low-beta alone."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Aggregate EV/PnL "
            "must improve, no window may regress EV/PnL, target sample must be "
            ">=20 across all 3 windows, survival must stay >=5%, drawdown drift "
            "<=0.5pp, and concentration guard must pass."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260608_004_industry_stable_leadership.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["gate3"]["note"] = (
        "No new core filter or entry rule was added. The stable-leadership "
        "source is additive default-off paper, so core signals generated/"
        "survived are unchanged from baseline."
    )
    runtime_fields = payload.setdefault("gate2", {}).setdefault("runtime_fields", [])
    for field in (
        "industry/sector labels from data/reference/broad_market_sector_map.json",
        "signal-date OHLCV for broad-market tickers",
        "SPY OHLCV",
    ):
        if field not in runtime_fields:
            runtime_fields.append(field)
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Stable group days | Trades |",
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
                days=scan.get("days_with_stable_industry_groups", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Industry Stable Leadership",
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
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][
                    label
                ]["total_pnl"],
                "stable_industry_day_count": payload["context_scan_by_window"][
                    label
                ].get("days_with_stable_industry_groups"),
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
    framework._load_window_snapshot = BASE_LOAD_WINDOW_SNAPSHOT
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
