"""exp-20260607-009: industry pullback leader resilience candidate pool.

Replay-only alpha search. It tests one broad, free-OHLCV relation source:
when a liquid industry group has 20-day relative strength but a short-term
pullback, select the liquid group leader that stays resilient versus the group
and SPY as a top-1 next-open default-off paper candidate with a fixed
10-trading-day hold.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework


EXPERIMENT_ID = "exp-20260607-009"
STEM = "industry_pullback_leader_resilience"
TRIAL_FAMILY = "industry_pullback_leader_resilience_candidate_pool"
TRIAL_VARIANT_ID = "industry_pullback_leader_resilience_top1_next_open_10d_v1"
CHANGED_VARIABLE = "industry_pullback_leader_resilience_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = framework.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260607_009_industry_pullback_leader_resilience.json"
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
PULLBACK_LOOKBACK_DAYS = 5
TREND_LOOKBACK_DAYS = 60

MIN_INDUSTRY_LIQUID_COUNT = 5
MIN_GROUP_MEDIAN_RET20_EXCESS_SPY = 0.025
MIN_GROUP_RET20_POSITIVE_FRACTION = 0.55
MIN_GROUP_MEDIAN_RET5_EXCESS_SPY = -0.060
MAX_GROUP_MEDIAN_RET5_EXCESS_SPY = -0.004
MIN_LEADER_RET20_EXCESS_OVER_GROUP = 0.018
MIN_LEADER_RET5_EXCESS_OVER_GROUP = 0.018
MIN_CANDIDATE_RET20_EXCESS_SPY = 0.020
MIN_CANDIDATE_RET60_EXCESS_SPY = 0.000
MIN_CANDIDATE_RET5_EXCESS_SPY = -0.020
MAX_CANDIDATE_RET5_EXCESS_SPY = 0.080
MIN_SIGNAL_RETURN = 0.002
MAX_SIGNAL_RETURN = 0.090
MIN_SIGNAL_RELATIVE_VS_SPY = 0.008
MIN_CLOSE_LOCATION = 0.65
MIN_VOLUME_RATIO_20D = 0.70
MAX_VOLUME_RATIO_20D = 3.00
MAX_REALIZED_VOL_20D = 0.085

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "window_regression",
        "drawdown_drift",
        "leader_exhaustion",
        "ohlcv_momentum_relabeling",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Recent relation-aware OHLCV sources worked when relation quality was "
        "explicit, but broad OHLCV momentum and short-horizon reversal often "
        "failed. This tests a different industry pullback-resilience relation "
        "with strict three-window gates."
    ),
    "recorded_at": "2026-06-07T07:04:57Z",
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
        "require a shared default-off adapter that computes the same broad "
        "warehouse liquid sector-known universe, PIT industry grouping, "
        "industry pullback context, leader resilience fields, same-ticker "
        "core-overlap exclusion, next-open paper entry, 10-trading-day exit, "
        "costs, cooldown, and concentration controls in both replay and daily "
        "production before any report queue, paper ledger, candidate priority, "
        "sizing, watchlist, or order surface could change."
    ),
}

BASE_GATE4 = framework._gate4
BASE_BUILD_PAYLOAD = framework._build_payload


def _repo_rel(path: Path | str) -> str:
    return framework._repo_rel(path)


def _group_key(meta: dict[str, Any]) -> str | None:
    industry = str(meta.get("industry") or "").strip()
    sector = str(meta.get("sector") or "").strip()
    if industry:
        return industry
    if sector:
        return f"Sector:{sector}"
    return None


def _ticker_day_metrics(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    rows = snapshot.get(ticker) or []
    spy_rows = snapshot.get("SPY") or []
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    min_idx = max(TREND_LOOKBACK_DAYS, GROUP_LOOKBACK_DAYS, PULLBACK_LOOKBACK_DAYS, 20)
    if idx is None or spy_idx is None or idx < min_idx or spy_idx < min_idx:
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
    ret5 = framework._ret(rows, idx, PULLBACK_LOOKBACK_DAYS)
    spy_ret5 = framework._ret(spy_rows, spy_idx, PULLBACK_LOOKBACK_DAYS)
    ret60 = framework._ret(rows, idx, TREND_LOOKBACK_DAYS)
    spy_ret60 = framework._ret(spy_rows, spy_idx, TREND_LOOKBACK_DAYS)
    signal_return = framework._daily_return(rows, idx)
    spy_signal_return = framework._daily_return(spy_rows, spy_idx)
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
    assert close_location is not None
    assert volume_ratio is not None
    assert realized_vol20 is not None

    meta = sector_entries[ticker]
    key = _group_key(meta)
    if key is None:
        return None
    return {
        "date": signal_date,
        "ticker": ticker,
        "group_key": key,
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
        "close_location": close_location,
        "volume_ratio_20d": volume_ratio,
        "realized_vol_20d": realized_vol20,
    }


def _candidate_from_metrics(
    *,
    metrics: dict[str, Any],
    group: dict[str, Any],
) -> dict[str, Any] | None:
    leader_ret20_excess_over_group = (
        metrics["ret20_excess_spy"] - group["median_ret20_excess_spy"]
    )
    leader_ret5_excess_over_group = (
        metrics["ret5_excess_spy"] - group["median_ret5_excess_spy"]
    )
    if leader_ret20_excess_over_group < MIN_LEADER_RET20_EXCESS_OVER_GROUP:
        return None
    if leader_ret5_excess_over_group < MIN_LEADER_RET5_EXCESS_OVER_GROUP:
        return None
    if metrics["ret20_excess_spy"] < MIN_CANDIDATE_RET20_EXCESS_SPY:
        return None
    if metrics["ret60_excess_spy"] < MIN_CANDIDATE_RET60_EXCESS_SPY:
        return None
    if metrics["ret5_excess_spy"] < MIN_CANDIDATE_RET5_EXCESS_SPY:
        return None
    if metrics["ret5_excess_spy"] > MAX_CANDIDATE_RET5_EXCESS_SPY:
        return None
    if metrics["signal_return"] < MIN_SIGNAL_RETURN:
        return None
    if metrics["signal_return"] > MAX_SIGNAL_RETURN:
        return None
    if metrics["signal_relative_vs_spy"] < MIN_SIGNAL_RELATIVE_VS_SPY:
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
        1.25 * group["median_ret20_excess_spy"]
        + 1.55 * leader_ret20_excess_over_group
        + 1.35 * leader_ret5_excess_over_group
        + 1.30 * metrics["signal_relative_vs_spy"]
        + 0.55 * metrics["close_location"]
        + 0.35 * metrics["ret60_excess_spy"]
        + 0.05 * math.log10(max(metrics["adv20"], 1.0) / 1_000_000.0)
        - 0.70 * metrics["realized_vol_20d"]
        - 0.04 * max(metrics["volume_ratio_20d"] - 1.6, 0.0)
    )
    return {
        "date": metrics["date"],
        "ticker": metrics["ticker"],
        "source": "INDUSTRY_PULLBACK_LEADER_RESILIENCE_PAPER",
        "candidate_score": round(score, 6),
        "candidate_group_key": metrics["group_key"],
        "leader_ret20_excess_over_group": round(leader_ret20_excess_over_group, 6),
        "leader_ret5_excess_over_group": round(leader_ret5_excess_over_group, 6),
        "candidate_ret20_excess_spy": round(metrics["ret20_excess_spy"], 6),
        "candidate_ret5_excess_spy": round(metrics["ret5_excess_spy"], 6),
        "candidate_ret60_excess_spy": round(metrics["ret60_excess_spy"], 6),
        "candidate_signal_day_return": round(metrics["signal_return"], 6),
        "candidate_signal_relative_vs_spy": round(metrics["signal_relative_vs_spy"], 6),
        "candidate_close_location": round(metrics["close_location"], 6),
        "candidate_volume_ratio_20d": round(metrics["volume_ratio_20d"], 6),
        "candidate_realized_vol_20d": round(metrics["realized_vol_20d"], 6),
        "candidate_avg_dollar_volume_20d": round(metrics["adv20"], 2),
        "industry_pullback_context": {
            "group_key": metrics["group_key"],
            "liquid_group_count": group["liquid_group_count"],
            "median_ret20_excess_spy": round(group["median_ret20_excess_spy"], 6),
            "median_ret5_excess_spy": round(group["median_ret5_excess_spy"], 6),
            "ret20_positive_fraction": round(group["ret20_positive_fraction"], 6),
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
    day_contexts: list[dict[str, Any]] = []
    context_scan = {
        "scanned_trading_days": len(dates),
        "days_with_pullback_groups": 0,
        "days_with_raw_candidates": 0,
        "pullback_group_rows": 0,
        "raw_candidate_rows": 0,
        "unique_candidate_tickers": 0,
        "rule_version": RULE_VERSION,
    }
    candidate_tickers: set[str] = set()

    for signal_date in dates:
        group_members: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for ticker in sector_entries:
            metrics = _ticker_day_metrics(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
            )
            if metrics is not None:
                group_members[metrics["group_key"]].append(metrics)

        group_summaries: dict[str, dict[str, Any]] = {}
        for group_key, rows in group_members.items():
            if len(rows) < MIN_INDUSTRY_LIQUID_COUNT:
                continue
            ret20_values = [float(row["ret20_excess_spy"]) for row in rows]
            ret5_values = [float(row["ret5_excess_spy"]) for row in rows]
            positive_fraction = sum(value > 0.0 for value in ret20_values) / len(ret20_values)
            group_median_ret20 = median(ret20_values)
            group_median_ret5 = median(ret5_values)
            if group_median_ret20 < MIN_GROUP_MEDIAN_RET20_EXCESS_SPY:
                continue
            if positive_fraction < MIN_GROUP_RET20_POSITIVE_FRACTION:
                continue
            if group_median_ret5 < MIN_GROUP_MEDIAN_RET5_EXCESS_SPY:
                continue
            if group_median_ret5 > MAX_GROUP_MEDIAN_RET5_EXCESS_SPY:
                continue
            group_summaries[group_key] = {
                "liquid_group_count": len(rows),
                "median_ret20_excess_spy": group_median_ret20,
                "median_ret5_excess_spy": group_median_ret5,
                "ret20_positive_fraction": positive_fraction,
            }

        if not group_summaries:
            continue
        context_scan["days_with_pullback_groups"] += 1
        context_scan["pullback_group_rows"] += len(group_summaries)
        day_rows: list[dict[str, Any]] = []
        for group_key, rows in group_members.items():
            group = group_summaries.get(group_key)
            if group is None:
                continue
            for metrics in rows:
                row = _candidate_from_metrics(metrics=metrics, group=group)
                if row is None:
                    continue
                ab_entries = entries_by_date.get(signal_date, [])
                row["same_day_ab_entry_count"] = len(ab_entries)
                row["same_day_ab_overlap"] = bool(ab_entries)
                row["same_ticker_ab_overlap"] = any(
                    trade.get("ticker") == row["ticker"] for trade in ab_entries
                )
                day_rows.append(row)
                candidate_tickers.add(str(row["ticker"]))

        if not day_rows:
            continue
        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_score"]),
                -float(row["leader_ret5_excess_over_group"]),
                -float(row["leader_ret20_excess_over_group"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        context_scan["days_with_raw_candidates"] += 1
        context_scan["raw_candidate_rows"] += len(day_rows)
        top = day_rows[0]
        day_contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(day_rows),
                "pullback_group_count": len(group_summaries),
                "top_candidate": top["ticker"],
                "top_group_key": top["candidate_group_key"],
                "top_score": top["candidate_score"],
                "top_leader_ret5_excess_over_group": top["leader_ret5_excess_over_group"],
                "top_leader_ret20_excess_over_group": top["leader_ret20_excess_over_group"],
                "top_signal_relative_vs_spy": top["candidate_signal_relative_vs_spy"],
            }
        )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["leader_ret5_excess_over_group"]),
            -float(row["leader_ret20_excess_over_group"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            row["ticker"],
        )
    )
    context_scan.update(
        {
            "unique_candidate_tickers": len(candidate_tickers),
            "group_lookback_days": GROUP_LOOKBACK_DAYS,
            "pullback_lookback_days": PULLBACK_LOOKBACK_DAYS,
            "trend_lookback_days": TREND_LOOKBACK_DAYS,
            "min_industry_liquid_count": MIN_INDUSTRY_LIQUID_COUNT,
            "min_group_median_ret20_excess_spy": MIN_GROUP_MEDIAN_RET20_EXCESS_SPY,
            "min_group_ret20_positive_fraction": MIN_GROUP_RET20_POSITIVE_FRACTION,
            "min_group_median_ret5_excess_spy": MIN_GROUP_MEDIAN_RET5_EXCESS_SPY,
            "max_group_median_ret5_excess_spy": MAX_GROUP_MEDIAN_RET5_EXCESS_SPY,
            "min_leader_ret20_excess_over_group": MIN_LEADER_RET20_EXCESS_OVER_GROUP,
            "min_leader_ret5_excess_over_group": MIN_LEADER_RET5_EXCESS_OVER_GROUP,
            "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
            "min_candidate_ret60_excess_spy": MIN_CANDIDATE_RET60_EXCESS_SPY,
            "min_candidate_ret5_excess_spy": MIN_CANDIDATE_RET5_EXCESS_SPY,
            "max_candidate_ret5_excess_spy": MAX_CANDIDATE_RET5_EXCESS_SPY,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "max_signal_return": MAX_SIGNAL_RETURN,
            "min_signal_relative_vs_spy": MIN_SIGNAL_RELATIVE_VS_SPY,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "max_volume_ratio_20d": MAX_VOLUME_RATIO_20D,
            "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
        }
    )
    return candidates, day_contexts, context_scan


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
        "positive_replay_lead_not_promoted_industry_pullback_leader_resilience"
        if gate["passed"]
        else "rejected_industry_pullback_leader_resilience_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Strong liquid industry groups that briefly pull back may "
                "produce continuation alpha in group leaders that stay "
                "resilient versus their group and SPY, without simply adding "
                "noisy broad momentum tickers."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
            "new_evidence_type": "free_ohlcv_industry_pullback_leader_resilience",
            "nearby_prior_experiments": [
                "exp-20260605-033",
                "exp-20260607-005",
                "exp-20260607-007",
                "exp-20260607-008",
            ],
            "prior_trial_count": 4,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "decision": gate4["decision"],
            "status": (
                "positive_replay_lead_not_promoted"
                if gate4["passed"]
                else "rejected"
            ),
            "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
            "total_pnl_delta": aggregate["total_pnl_delta_sum"],
            "interpretation": (
                "The industry pullback leader-resilience source cleared Gate "
                "4 as a replay-only/default-off lead, but no production "
                "surface was promoted."
                if gate4["passed"]
                else (
                    "The industry pullback leader-resilience source did not "
                    "clear Gate 4. Do not promote it or answer by retuning "
                    "group pullback, leader-resilience, close-location, "
                    "hold-day, cooldown, top-N, or notional thresholds on "
                    "these frozen windows."
                )
            ),
            "negative_reflection": (
                "If rejected, the likely reason is that leader resilience "
                "inside a group pullback is often late-stage exhaustion, not "
                "fresh continuation. A retry needs independent PIT relation "
                "or event evidence, not another OHLCV threshold sweep."
            ),
            "post_run_reflection": {
                "why_result_happened": (
                    "Pending run result. Replace with measured Gate 4 "
                    "behavior after the three-window replay."
                ),
                "forbidden_near_neighbor_retry": (
                    "Do not retry by sweeping group pullback, group strength, "
                    "leader ret20/ret5 excess, signal-day return, "
                    "close-location, volume, volatility, hold-day, top-N, "
                    "cooldown, or paper notional thresholds."
                ),
                "new_evidence_required": (
                    "A retry requires independent PIT confirmation such as "
                    "industry event/news context, earnings peer provenance, "
                    "borrow/options/ownership data with adequate historical "
                    "coverage, or closed forward replacement rows from a "
                    "shared default-off adapter."
                ),
            },
            "next_evidence_needed": (
                "Independent PIT context or a shared-adapter forward row set "
                "is required before retrying near-neighbor industry pullback "
                "leader-resilience variants."
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
    if gate4["passed"]:
        payload["post_run_reflection"]["why_result_happened"] = (
            "The source produced positive replacement value in all three "
            "canonical windows without breaching drawdown, survival, or "
            "concentration guardrails, suggesting industry group pullback "
            "plus leader resilience captured a distinct continuation relation."
        )
    else:
        payload["post_run_reflection"]["why_result_happened"] = (
            "The candidate source either failed to add aggregate replacement "
            "value, regressed at least one canonical window, or breached "
            "drawdown/concentration gates. That means leader resilience inside "
            "industry pullbacks did not reliably separate continuation from "
            "exhaustion under existing costs, slippage, and 10-day exit "
            "assumptions."
        )

    payload.setdefault("parameters", {}).clear()
    payload["parameters"].update(
        {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "group_lookback_days": GROUP_LOOKBACK_DAYS,
            "pullback_lookback_days": PULLBACK_LOOKBACK_DAYS,
            "trend_lookback_days": TREND_LOOKBACK_DAYS,
            "min_industry_liquid_count": MIN_INDUSTRY_LIQUID_COUNT,
            "min_group_median_ret20_excess_spy": MIN_GROUP_MEDIAN_RET20_EXCESS_SPY,
            "min_group_ret20_positive_fraction": MIN_GROUP_RET20_POSITIVE_FRACTION,
            "min_group_median_ret5_excess_spy": MIN_GROUP_MEDIAN_RET5_EXCESS_SPY,
            "max_group_median_ret5_excess_spy": MAX_GROUP_MEDIAN_RET5_EXCESS_SPY,
            "min_leader_ret20_excess_over_group": MIN_LEADER_RET20_EXCESS_OVER_GROUP,
            "min_leader_ret5_excess_over_group": MIN_LEADER_RET5_EXCESS_OVER_GROUP,
            "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
            "min_candidate_ret60_excess_spy": MIN_CANDIDATE_RET60_EXCESS_SPY,
            "min_candidate_ret5_excess_spy": MIN_CANDIDATE_RET5_EXCESS_SPY,
            "max_candidate_ret5_excess_spy": MAX_CANDIDATE_RET5_EXCESS_SPY,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "max_signal_return": MAX_SIGNAL_RETURN,
            "min_signal_relative_vs_spy": MIN_SIGNAL_RELATIVE_VS_SPY,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "max_volume_ratio_20d": MAX_VOLUME_RATIO_20D,
            "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only close-of-day OHLCV available on the signal date plus "
        "prior close history needed for 20-day industry relative strength, "
        "5-day group pullback, leader resilience, 60-day trend guard, ADV, "
        "volume ratio, and realized volatility. Paper entry is next available "
        "open with existing entry slippage; exit is the close 10 trading days "
        "after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: strong liquid industry groups with a brief "
            "5-day pullback may produce continuation candidates in leaders "
            "that remain resilient versus both the group and SPY."
        ),
        "2_history_check": {
            "exp-20260605-033": (
                "Cross-section pressure resilience failed; this uses "
                "industry-local pullback/resilience rather than broad market "
                "stress."
            ),
            "exp-20260607-005": (
                "Short-horizon reversal failed; this is not a raw selloff "
                "reclaim and requires strong 20-day group context."
            ),
            "exp-20260607-007/008": (
                "Industry-relative laggard repair was accepted; this tests the "
                "opposite relation, leader resilience during group pullback, "
                "and is not a lag/reclaim/top-N/notional retune."
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
            "exp_20260607_009_industry_pullback_leader_resilience.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["gate3"]["note"] = (
        "No new core filter or entry rule was added. The industry pullback "
        "leader-resilience source is additive default-off paper, so core "
        "signals generated/survived are unchanged from baseline."
    )
    payload["context_alias"] = "industry_pullback_leader_resilience_contexts"
    payload["industry_pullback_context_samples_by_window"] = {
        label: rows[:20]
        for label, rows in payload["pressure_contexts_by_window"].items()
    }
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Raw candidates | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {raw} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                raw=payload["raw_candidate_counts"][label],
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Industry Pullback Leader Resilience",
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
            "data/experiments/exp-20260602-003/"
            "exp_20260602_003_post_earnings_explicit_continuation.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate[
            "expected_value_score_delta_sum"
        ],
        "aggregate_expected_value_delta_pct": aggregate[
            "expected_value_score_delta_pct"
        ],
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
                "expected_value_delta": payload["delta_metrics"]["by_window"][
                    label
                ]["expected_value_score"],
                "strategy_total_pnl_delta": payload["delta_metrics"][
                    "by_window"
                ][label]["total_pnl"],
                "raw_candidate_count": payload["raw_candidate_counts"][label],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": {**payload["calibration"]},
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
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
