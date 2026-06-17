"""exp-20260617-017: industry down-shock resilience leader scout.

Replay-only alpha search. The single decision hypothesis is that a liquid
stock which stays resilient while its own industry group is under a short-term
pullback may capture idiosyncratic sponsorship and rebound before generic
group momentum recovers.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive replay is
only a lead until a shared historical/daily helper reproduces the exact PIT
relation field. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

import exp_20260616_011_industry_breadth_expansion_leader as relation


_RELATION_GATE4 = relation._gate4

EXPERIMENT_ID = "exp-20260617-017"
STEM = "industry_downshock_resilience_leader"
TRIAL_FAMILY = "industry_downshock_resilience_leader_candidate_pool"
TRIAL_VARIANT_ID = "industry_downshock_resilience_leader_top1_next_open_10d_v1"
CHANGED_VARIABLE = "industry_downshock_resilience_leader_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = relation.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260617_017_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 10

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_INDUSTRY_LIQUID_MEMBERS = 5
MIN_GROUP_MEDIAN_RET20 = 0.0
MAX_GROUP_MEDIAN_RET20 = 0.16
MAX_GROUP_MEDIAN_RET5 = -0.015
MAX_GROUP_POSITIVE_RET5_FRACTION = 0.45
MIN_GROUP_RET5_DISPERSION = 0.014

MIN_LEADER_RET5_VS_GROUP = 0.040
MIN_LEADER_RET20_VS_GROUP = 0.020
MIN_RET20_EXCESS_SPY = -0.005
MIN_RET60_EXCESS_SPY = -0.030
MIN_SIGNAL_RETURN = 0.0
MAX_SIGNAL_RETURN = 0.080
MIN_CLOSE_LOCATION = 0.60
MIN_SMA20_RATIO = 0.98
MIN_SMA50_RATIO = 0.95
MIN_VOLUME_RATIO_20D = 0.50
MAX_VOLUME_RATIO_20D = 3.50
MAX_REALIZED_VOL_20D = 0.095

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

WINDOWS = relation.WINDOWS

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": 0.18,
    "expected_pnl_delta": 2800.0,
    "main_failure_modes": [
        "industry_pullback_is_falling_knife",
        "generic_relative_strength_relabel",
        "old_thin_regression",
        "drawdown_drift",
        "accepted_relation_comparator_not_beaten",
    ],
    "confidence_reason": (
        "Accepted relation alphas worked when the relation itself provided "
        "displacement value, especially industry-stable core flow and "
        "industry-relative laggard repair. Recent breadth-expansion and raw "
        "Companyfacts burden fields failed. This tests a distinct free OHLCV "
        "relation: individual resilience inside an industry pullback, with no "
        "new ticker noise and no production behavior change."
    ),
    "recorded_at": "2026-06-17T15:12:00+00:00",
}

ACCEPTED_COMPARATORS = {
    "accepted_industry_stable_core_flow": {
        "aggregate_expected_value_delta": 0.1459,
        "aggregate_pnl_delta": 3731.54,
        "note": "accepted shared industry-stable core-flow adapter",
    },
    "accepted_industry_relative_laggard_repair": {
        "aggregate_expected_value_delta": 0.2763,
        "aggregate_pnl_delta": 6208.99,
        "note": "accepted shared industry-relative laggard-repair adapter",
    },
    "accepted_distribution_day_absorption": {
        "aggregate_expected_value_delta": 0.5286,
        "aggregate_pnl_delta": 10432.91,
        "note": "accepted shared distribution-day absorption adapter",
    },
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "uses_llm": False,
    "uses_free_ohlcv_only": True,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": {
        "trade_enabled": False,
        "target_notional_per_paper_trade": BASE_NOTIONAL_USD,
        "daily_entry_slots": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "hold_days": HOLD_DAYS,
        "liquidity_source": "price >= $10 and ADV20 >= $50M from PIT OHLCV",
        "order_semantics": "observe-only next-session-open paper entry; no broker order",
        "portfolio_displacement": "none unless a later shared helper passes",
        "kill_switch": "trade_enabled remains false; no production adapter changes",
        "failure_handling": "missing OHLCV, sector map, next open, or 10d exit rejects the paper candidate",
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same "
        "industry pullback context, same-day resilience gates, cooldown, "
        "next-open paper entry, 10-trading-day exit, costs, and concentration "
        "controls in both historical replay and daily production observation."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool alpha: when a PIT industry cohort is in a short-term "
        "pullback but still has positive 20-day trend, a liquid stock with "
        "same-day resilient return, high close location, and strong relative "
        "5/20-day behavior versus that group may capture idiosyncratic demand "
        "before a 10-trading-day continuation leg."
    ),
    "2_history_check": {
        "exp-20260608-008": (
            "Accepted stable industry core-flow. This run does not retune "
            "stability thresholds or require same-day core flow; it tests "
            "resilience during industry pullbacks."
        ),
        "exp-20260607-008": (
            "Accepted industry-relative laggard repair. This run is not laggard "
            "catch-up inside a strong group; it tests leaders that resist a "
            "short-term group down-shock."
        ),
        "exp-20260616-011": (
            "Rejected industry breadth-expansion leader as generic momentum. "
            "This run tests the opposite group state: breadth/ret5 weakness "
            "with individual resilience."
        ),
        "exp-20260611-007": (
            "Accepted distribution-day absorption comparator. This run is more "
            "local than market distribution pressure and must beat that "
            "comparator before promotion pressure."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md three canonical windows. Aggregate EV/PnL must "
        "be positive, no window EV/PnL regression, at least 20 paper trades "
        "across all 3 windows, survival >=5%, drawdown drift <=0.5pp, "
        "concentration pass, and accepted industry/distribution relation "
        "comparators beaten. Replay-only positives are leads until shared "
        "daily/backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260617_017_industry_downshock_resilience_leader.py"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _repo_rel(path: Path | str) -> str:
    return relation.framework._repo_rel(path)


def _stdev(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean_value = sum(values) / len(values)
    variance = sum((value - mean_value) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(max(variance, 0.0))


def _member_features(
    *,
    rows: list[dict[str, Any]],
    idx: int,
) -> dict[str, Any] | None:
    close = relation.framework._value(rows[idx], "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = relation.framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    ret5 = relation.framework._ret(rows, idx, 5)
    ret20 = relation.framework._ret(rows, idx, 20)
    if ret5 is None or ret20 is None:
        return None
    return {"ret5": float(ret5), "ret20": float(ret20)}


def _industry_contexts_for_day(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    industry_groups: dict[str, list[str]],
    signal_date: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    contexts: dict[str, dict[str, Any]] = {}
    scan = {
        "industry_groups_scanned": len(industry_groups),
        "industry_groups_with_liquid_members": 0,
        "industry_groups_passing_downshock": 0,
    }
    for key, tickers in industry_groups.items():
        members: list[dict[str, Any]] = []
        for ticker in tickers:
            rows = snapshot.get(ticker) or []
            idx = indices.get(ticker, {}).get(signal_date)
            if idx is None or idx < 65:
                continue
            features = _member_features(rows=rows, idx=idx)
            if features is not None:
                members.append(features)
        if len(members) < MIN_INDUSTRY_LIQUID_MEMBERS:
            continue
        scan["industry_groups_with_liquid_members"] += 1
        ret5_values = [row["ret5"] for row in members]
        ret20_values = [row["ret20"] for row in members]
        median_ret5 = float(median(ret5_values))
        median_ret20 = float(median(ret20_values))
        positive_ret5_fraction = sum(1 for value in ret5_values if value > 0.0) / len(
            ret5_values
        )
        dispersion = _stdev(ret5_values)
        if dispersion is None:
            continue
        passed = (
            MIN_GROUP_MEDIAN_RET20 <= median_ret20 <= MAX_GROUP_MEDIAN_RET20
            and median_ret5 <= MAX_GROUP_MEDIAN_RET5
            and positive_ret5_fraction <= MAX_GROUP_POSITIVE_RET5_FRACTION
            and dispersion >= MIN_GROUP_RET5_DISPERSION
        )
        if not passed:
            continue
        scan["industry_groups_passing_downshock"] += 1
        sector = sector_entries[tickers[0]].get("sector")
        contexts[key] = {
            "date": signal_date,
            "industry_key": key,
            "sector": sector,
            "liquid_member_count": len(members),
            "industry_median_ret5": round(median_ret5, 6),
            "industry_median_ret20": round(median_ret20, 6),
            "industry_positive_ret5_fraction": round(positive_ret5_fraction, 6),
            "industry_ret5_dispersion": round(dispersion, 6),
            "downshock_score": round(
                abs(min(median_ret5, 0.0))
                + 0.45 * dispersion
                + 0.20 * max(median_ret20, 0.0),
                6,
            ),
            "rule_version": RULE_VERSION,
        }
    return contexts, scan


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
    idx = indices.get(ticker, {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if idx is None or spy_idx is None or idx < 65 or spy_idx < 65:
        return None
    row = rows[idx]
    close = relation.framework._value(row, "Close")
    if close is None or close < MIN_PRICE:
        return None
    adv20 = relation.framework._avg_dollar_volume(rows, idx)
    if adv20 is None or adv20 < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    ret5 = relation.framework._ret(rows, idx, 5)
    ret20 = relation.framework._ret(rows, idx, 20)
    ret60 = relation.framework._ret(rows, idx, 60)
    spy_ret20 = relation.framework._ret(spy_rows, spy_idx, 20)
    spy_ret60 = relation.framework._ret(spy_rows, spy_idx, 60)
    signal_return = relation.framework._daily_return(rows, idx)
    if None in (ret5, ret20, ret60, spy_ret20, spy_ret60, signal_return):
        return None

    ret5 = float(ret5)
    ret20 = float(ret20)
    ret60 = float(ret60)
    spy_ret20 = float(spy_ret20)
    spy_ret60 = float(spy_ret60)
    signal_return = float(signal_return)
    ret5_vs_industry = ret5 - float(context["industry_median_ret5"])
    ret20_vs_industry = ret20 - float(context["industry_median_ret20"])
    ret20_excess_spy = ret20 - spy_ret20
    ret60_excess_spy = ret60 - spy_ret60

    if ret5_vs_industry < MIN_LEADER_RET5_VS_GROUP:
        return None
    if ret20_vs_industry < MIN_LEADER_RET20_VS_GROUP:
        return None
    if ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None
    if ret60_excess_spy < MIN_RET60_EXCESS_SPY:
        return None
    if signal_return < MIN_SIGNAL_RETURN or signal_return > MAX_SIGNAL_RETURN:
        return None
    close_location = relation.framework._close_location(row)
    if close_location is None or close_location < MIN_CLOSE_LOCATION:
        return None
    sma20 = relation._sma(rows, idx, 20)
    sma50 = relation._sma(rows, idx, 50)
    if sma20 is None or sma50 is None or sma20 <= 0 or sma50 <= 0:
        return None
    sma20_ratio = float(close) / float(sma20)
    sma50_ratio = float(close) / float(sma50)
    if sma20_ratio < MIN_SMA20_RATIO or sma50_ratio < MIN_SMA50_RATIO:
        return None
    volume_ratio = relation.framework._volume_ratio(rows, idx)
    if (
        volume_ratio is None
        or volume_ratio < MIN_VOLUME_RATIO_20D
        or volume_ratio > MAX_VOLUME_RATIO_20D
    ):
        return None
    realized_vol = relation.framework._realized_vol(rows, idx)
    if realized_vol is None or realized_vol > MAX_REALIZED_VOL_20D:
        return None

    downshock_score = float(context["downshock_score"])
    score = (
        1.05 * ret5_vs_industry
        + 0.75 * ret20_vs_industry
        + 0.55 * ret20_excess_spy
        + 0.30 * ret60_excess_spy
        + 0.40 * downshock_score
        + 0.16 * float(close_location)
        + 0.035 * math.log10(max(adv20, 1.0) / 1_000_000.0)
        - 0.35 * float(realized_vol)
    )
    sector_meta = sector_entries[ticker]
    return {
        "date": signal_date,
        "ticker": ticker,
        "source": "INDUSTRY_DOWNSHOCK_RESILIENCE_LEADER_PAPER",
        "candidate_score": round(score, 6),
        "industry_context": context,
        "industry_key": context["industry_key"],
        "sector": sector_meta.get("sector"),
        "industry": sector_meta.get("industry"),
        "ret5": round(ret5, 6),
        "ret20": round(ret20, 6),
        "ret60": round(ret60, 6),
        "industry_median_ret5": context["industry_median_ret5"],
        "industry_median_ret20": context["industry_median_ret20"],
        "ret5_vs_industry_median": round(ret5_vs_industry, 6),
        "ret20_vs_industry_median": round(ret20_vs_industry, 6),
        "ret20_excess_spy": round(ret20_excess_spy, 6),
        "ret60_excess_spy": round(ret60_excess_spy, 6),
        "signal_return": round(signal_return, 6),
        "close_location": round(float(close_location), 6),
        "sma20_ratio": round(sma20_ratio, 6),
        "sma50_ratio": round(sma50_ratio, 6),
        "avg_dollar_volume_20d": round(float(adv20), 2),
        "volume_ratio_20d": round(float(volume_ratio), 6),
        "realized_vol_20d": round(float(realized_vol), 6),
        "uses_free_ohlcv": True,
        "uses_llm": False,
        "trade_enabled": False,
        "rule_version": RULE_VERSION,
    }


def _comparator_readout(aggregate: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    observed_ev = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    observed_pnl = float(aggregate["total_pnl_delta_sum"] or 0.0)
    for key, comparator in ACCEPTED_COMPARATORS.items():
        required_ev = float(comparator["aggregate_expected_value_delta"])
        required_pnl = float(comparator["aggregate_pnl_delta"])
        out[key] = {
            "note": comparator["note"],
            "required_ev_delta": required_ev,
            "required_pnl_delta": required_pnl,
            "observed_ev_delta": round(observed_ev, 6),
            "observed_pnl_delta": round(observed_pnl, 2),
            "passed": observed_ev >= required_ev and observed_pnl >= required_pnl,
        }
    return out


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
    comparator_readout: dict[str, Any],
) -> dict[str, Any]:
    gate = _RELATION_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
        comparator_readout=comparator_readout,
    )
    gate["decision"] = (
        "positive_replay_lead_not_promoted_industry_downshock_resilience_leader"
        if gate["passed"]
        else "rejected_industry_downshock_resilience_leader_candidate_pool"
    )
    return gate


def _configure_relation_module() -> None:
    relation.EXPERIMENT_ID = EXPERIMENT_ID
    relation.STEM = STEM
    relation.TRIAL_FAMILY = TRIAL_FAMILY
    relation.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    relation.CHANGED_VARIABLE = CHANGED_VARIABLE
    relation.RULE_VERSION = RULE_VERSION
    relation.OWNER = OWNER
    relation.OUT_DIR = OUT_DIR
    relation.OUT_JSON = OUT_JSON
    relation.LOG_JSON = LOG_JSON
    relation.TICKET_JSON = TICKET_JSON
    relation.CARD_MD = CARD_MD
    relation.MANIFEST_JSON = MANIFEST_JSON
    relation.REGISTRY_JSON = REGISTRY_JSON
    relation.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    relation.HOLD_DAYS = HOLD_DAYS
    relation.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    relation.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    relation.MIN_PRICE = MIN_PRICE
    relation.MIN_AVG_DOLLAR_VOLUME_20D = MIN_AVG_DOLLAR_VOLUME_20D
    relation.MIN_INDUSTRY_LIQUID_MEMBERS = MIN_INDUSTRY_LIQUID_MEMBERS
    relation.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    relation.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    relation.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    relation.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    relation.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    relation.PREDICTION = PREDICTION
    relation.ACCEPTED_COMPARATORS = ACCEPTED_COMPARATORS
    relation.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    relation.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    relation._industry_contexts_for_day = _industry_contexts_for_day
    relation._candidate_for_ticker = _candidate_for_ticker
    relation._comparator_readout = _comparator_readout
    relation._gate4 = _gate4


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    if gate4["passed"]:
        interpretation = (
            "Industry down-shock resilience added multi-window replacement "
            "value, but this remains only a replay lead because no shared daily "
            "helper or forward rows exist."
        )
        realized_failure_mode = "none_numeric_gate4_passed"
    else:
        interpretation = (
            "Industry down-shock resilience did not clear Gate 4 after "
            "next-open execution and accepted relation comparators. The likely "
            "cause is that local group weakness still created falling-knife "
            "risk, while the individual resilience gates mostly relabeled "
            "generic relative strength instead of a distinct displacement edge."
        )
        realized_failure_mode = "industry_downshock_resilience_not_incremental"

    for row in payload["window_rows"].values():
        row["industry_downshock_day_count"] = row.get("industry_breadth_expansion_day_count")
    for scan in payload["scan_by_window"].values():
        scan["industry_downshock_days"] = scan.get("industry_breadth_expansion_days")

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": _utc_now(),
            "lane": "alpha_search",
            "status": status,
            "decision": gate4["decision"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "default_off_paper_candidate_pool_replay_scout",
            "mechanism_family": "production_visible_free_ohlcv_relation_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "prior_trial_count": 4,
            "nearby_prior_experiments": [
                "exp-20260608-008",
                "exp-20260607-008",
                "exp-20260616-011",
                "exp-20260611-007",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "free_ohlcv_intra_industry_downshock_resilience_relation_field",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "interpretation": interpretation,
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "negative_reflection": interpretation if not gate4["passed"] else None,
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
        "min_industry_liquid_members": MIN_INDUSTRY_LIQUID_MEMBERS,
        "min_group_median_ret20": MIN_GROUP_MEDIAN_RET20,
        "max_group_median_ret20": MAX_GROUP_MEDIAN_RET20,
        "max_group_median_ret5": MAX_GROUP_MEDIAN_RET5,
        "max_group_positive_ret5_fraction": MAX_GROUP_POSITIVE_RET5_FRACTION,
        "min_group_ret5_dispersion": MIN_GROUP_RET5_DISPERSION,
        "min_leader_ret5_vs_group": MIN_LEADER_RET5_VS_GROUP,
        "min_leader_ret20_vs_group": MIN_LEADER_RET20_VS_GROUP,
        "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
        "min_ret60_excess_spy": MIN_RET60_EXCESS_SPY,
        "min_signal_return": MIN_SIGNAL_RETURN,
        "max_signal_return": MAX_SIGNAL_RETURN,
        "min_close_location": MIN_CLOSE_LOCATION,
        "min_sma20_ratio": MIN_SMA20_RATIO,
        "min_sma50_ratio": MIN_SMA50_RATIO,
        "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
        "max_volume_ratio_20d": MAX_VOLUME_RATIO_20D,
        "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only close-of-day OHLCV and sector-map industry membership "
        "available on the signal date. Industry down-shock context is defined "
        "by positive 20-day group trend with weak 5-day group returns; the "
        "candidate must show same-day resilience and 5/20-day relative strength "
        "versus that group. Paper entry is next available open; exit is the "
        "close 10 trading days after signal with existing cost assumptions."
    )
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": 1 if gate4["passed"] else 0,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0))
            ** 2,
            6,
        ),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
        "realized_failure_mode": realized_failure_mode,
    }
    payload["post_run_reflection"] = {
        "why_result_happened": interpretation,
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; max "
            "drawdown drift {:+.4f}; {} paper trades.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
                float(aggregate["max_drawdown_delta_max"] or 0.0),
                payload["target_trade_summary"]["total_trade_count"],
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping industry pullback thresholds, group "
            "ret5/ret20 cutoffs, leader relative-strength thresholds, "
            "close-location, volume, volatility, top-N, hold days, cooldown, "
            "or notional on these frozen windows."
        ),
        "new_evidence_required": (
            "A valid retry needs materially new PIT flow/ownership/borrow/"
            "options evidence, closed forward replacement-value rows, or a "
            "shared daily relation helper showing industry down-shock "
            "resilience beats accepted relation comparators after costs."
        ),
    }
    payload["next_evidence_needed"] = payload["post_run_reflection"][
        "new_evidence_required"
    ]
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


def _window_table(payload: dict[str, Any]) -> list[str]:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Down-shock days | Raw | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        row = payload["window_rows"][label]
        rows.append(
            "| {label} | {before_ev:.4f} | {after_ev:.4f} | {delta_ev:+.4f} | ${before_pnl:,.2f} | ${after_pnl:,.2f} | ${delta_pnl:+,.2f} | {dd:+.4f} | {days} | {raw} | {trades} |".format(
                label=label,
                before_ev=row["before"]["expected_value_score"],
                after_ev=row["after"]["expected_value_score"],
                delta_ev=row["delta"]["expected_value_score"],
                before_pnl=row["before"]["total_pnl"],
                after_pnl=row["after"]["total_pnl"],
                delta_pnl=row["delta"]["total_pnl"],
                dd=row["delta"]["max_drawdown_pct"],
                days=row.get("industry_downshock_day_count", 0),
                raw=row["raw_candidate_count"],
                trades=row["target_trade_count"],
            )
        )
    return rows


def _build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Industry Down-Shock Resilience Leader",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4 Three-Window Readout",
            "",
            *_window_table(payload),
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
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
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
        "accepted": False,
        "accepted_alpha": False,
        "production_accepted": False,
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": payload["gate1"]["baseline_artifact"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_comparators": ACCEPTED_COMPARATORS,
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
                "pnl_delta": payload["delta_metrics"]["by_window"][label]["total_pnl"],
                "target_trade_count": payload["window_rows"][label]["target_trade_count"],
                "raw_candidate_count": payload["raw_candidate_counts"][label],
                "industry_downshock_day_count": payload["window_rows"][label].get(
                    "industry_downshock_day_count"
                ),
                "passed_industry_context_count": payload["scan_by_window"][label][
                    "passed_industry_context_count"
                ],
            }
            for label in WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": PRE_RUN_QUESTIONS,
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
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): relation.framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): relation.framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): relation.framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): relation.framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): relation.framework._sha256(CARD_MD),
        },
    }
    relation.framework._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    relation.framework._write_json(OUT_JSON, payload)
    relation.framework._write_json(LOG_JSON, log_record)
    relation.framework._write_text(CARD_MD, _build_card(payload))
    relation.framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "numeric_gate4_passed": bool(payload.get("gate4", {}).get("passed")),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record[
            "aggregate_strategy_total_pnl_delta"
        ],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record[
            "aggregate_strategy_total_pnl_delta"
        ],
    }
    relation.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )
    _write_manifest(payload)


def main() -> None:
    _configure_relation_module()
    payload = _postprocess_payload(relation._build_payload())
    _persist(payload)
    print(
        json.dumps(
            relation.framework._safe(_build_log_record(payload)),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
