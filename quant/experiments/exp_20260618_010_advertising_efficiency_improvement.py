"""exp-20260618-010: advertising efficiency improvement candidate scout.

Replay-only alpha search. The single decision hypothesis is a PIT free SEC
Companyfacts candidate source: production-universe names whose latest filed
annual advertising / selling-marketing expense intensity is falling versus
revenue while gross profit and revenue remain healthy may be improving customer
acquisition efficiency; liquid SPY-relative price confirmation may identify
10-day continuation candidates.

This intentionally uses explicit advertising / marketing Companyfacts tags,
not generic SG&A. No production code, shared adapter, live/default orders,
ranking, sizing, exits, LLM/news path, or watchlist behavior is changed. A
positive replay is only a lead until a shared historical/daily helper
reproduces the exact PIT field mapping. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260616_010_sga_operating_expense_leverage as template


EXPERIMENT_ID = "exp-20260618-010"
STEM = "advertising_efficiency_improvement"
TRIAL_FAMILY = "raw_sec_companyfacts_advertising_efficiency_candidate_pool"
TRIAL_VARIANT_ID = "advertising_efficiency_improvement_top1_next_open_10d_v1"
CHANGED_VARIABLE = "advertising_efficiency_improvement_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "codex-alpha-search"

base = template.base
rd = template.rd

REPO_ROOT = template.REPO_ROOT
RAW_COMPANYFACTS_CACHE = template.RAW_COMPANYFACTS_CACHE
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260618_010_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = template.BASE_NOTIONAL_USD
HOLD_DAYS = template.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = template.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = template.SAME_TICKER_COOLDOWN_DAYS

FY_DURATION_MIN = template.FY_DURATION_MIN
FY_DURATION_MAX = template.FY_DURATION_MAX
MAX_ANNUAL_FACT_AGE_DAYS = 430
MIN_CURRENT_REVENUE = 250_000_000.0
MIN_CURRENT_AD_EXPENSE = 5_000_000.0
MIN_CURRENT_GROSS_PROFIT = 20_000_000.0
MIN_GROSS_MARGIN = 0.12
MIN_PRIOR_AD_TO_REVENUE = 0.005
MAX_CURRENT_AD_TO_REVENUE = 0.40
MIN_AD_RATIO_IMPROVEMENT = 0.003
MIN_REVENUE_GROWTH = -0.05
MIN_GROSS_PROFIT_GROWTH = -0.10

ADVERTISING_TAGS = (
    "AdvertisingExpense",
    "AdvertisingExpenseExcludingCostsOfSales",
    "MarketingAndAdvertisingExpense",
    "SellingAndMarketingExpense",
    "MarketingExpense",
    "SellingExpense",
    "OtherSellingAndMarketingExpense",
    "CooperativeAdvertisingExpense",
)
REVENUE_TAGS = rd.REVENUE_TAGS
GROSS_PROFIT_TAGS = ("GrossProfit",)

PREDICTION = {
    "success_probability": 0.17,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "tag_coverage_sparse",
        "advertising_cut_is_demand_warning",
        "window_regression",
        "accepted_distribution_comparator_not_beaten",
        "companyfacts_family_saturated",
    ],
    "confidence_reason": (
        "Advertising / selling-marketing intensity is a raw SEC Companyfacts "
        "customer-acquisition efficiency field, distinct from prior SG&A, SBC, "
        "inventory, DPO, cash-conversion, and generic profitability trials. "
        "The main risk is economic ambiguity: lower advertising intensity can "
        "signal better acquisition efficiency, but can also mean demand is "
        "softening or management is cutting growth spend."
    ),
    "recorded_at": "2026-06-18T08:07:01+00:00",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "uses_free_sec_companyfacts": True,
    "uses_raw_companyfacts_cache": True,
    "execution_envelope": {
        **base.PRODUCTION_IMPACT["execution_envelope"],
        "failure_handling": (
            "missing raw SEC annual advertising/selling-marketing expense, "
            "revenue, or gross-profit facts, missing prior comparison period, "
            "stale facts, missing CIK mapping, missing OHLCV, missing next open, "
            "or missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same raw "
        "SEC advertising / selling-marketing tag mapping, filed-date PIT "
        "ad/revenue improvement gate, liquid SPY-relative confirmation, "
        "cooldown, next-open paper entry, 10-day exit, costs, and concentration "
        "controls in both historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: PIT raw SEC Companyfacts advertising / selling-marketing "
        "expense intensity falling versus revenue, while revenue and gross "
        "profit remain healthy, can identify improving customer-acquisition "
        "efficiency; liquid SPY-relative confirmation may reveal that the market "
        "is rewarding the improvement before a 10-trading-day continuation leg."
    ),
    "2_history_check": {
        "exp-20260616-010": (
            "Rejected generic SG&A / operating-expense leverage. This run "
            "deliberately excludes broad SG&A tags and tests explicit "
            "advertising / selling-marketing expense as customer-acquisition "
            "efficiency."
        ),
        "exp-20260615-016": (
            "Rejected operating-leverage acceleration. This run tests a specific "
            "sales/marketing input cost intensity, not the operating-income "
            "outcome."
        ),
        "exp-20260615-010": (
            "Rejected gross profitability quality. Gross profit is only a guard "
            "against demand collapse here; the decision field is advertising "
            "efficiency improvement."
        ),
        "exp-20260616-014/015": (
            "SBC burden improvement produced a positive shared default-off "
            "helper. This run uses a different customer-acquisition expense "
            "line and remains replay-only unless the numeric result later "
            "justifies shared helper work."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL must "
        "be positive, no window EV/PnL regression, at least two EV-improved "
        "windows, at least 20 paper trades across all 3 windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration pass, and accepted compression/"
        "distribution candidate-pool comparators must be beaten. Replay-only "
        "positives are leads until shared daily/backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260618_010_advertising_efficiency_improvement.py"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return base._round(value, digits)


def _build_quality_index(
    companyfacts_rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]]:
    index, summary = template._load_raw_companyfacts_index()
    return index, {
        **summary,
        "advertising_tags": list(ADVERTISING_TAGS),
        "selected_companyfacts_rows_ignored": len(companyfacts_rows),
        "field_source": "raw_sec_companyfacts_cache_not_selected_sidecar",
    }


def _advertising_efficiency_observation(
    ticker: str,
    asof: str,
    facts: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    current_ad = template._latest_expense_fact(facts["expense"], asof=asof)
    if current_ad is None:
        return None
    if base._days_between(asof, current_ad["filed"]) > MAX_ANNUAL_FACT_AGE_DAYS:
        return None

    current_revenue = rd._latest_period_fact(facts["revenue"], asof=asof, end=current_ad["end"])
    current_gross_profit = rd._latest_period_fact(
        facts["gross_profit"], asof=asof, end=current_ad["end"]
    )
    prior_ad = template._latest_expense_fact(
        facts["expense"],
        asof=asof,
        before_end=current_ad["end"],
        tag=str(current_ad.get("tag") or ""),
    )
    if current_revenue is None or current_gross_profit is None or prior_ad is None:
        return None
    prior_revenue = rd._latest_period_fact(facts["revenue"], asof=asof, end=prior_ad["end"])
    prior_gross_profit = rd._latest_period_fact(
        facts["gross_profit"], asof=asof, end=prior_ad["end"]
    )
    if prior_revenue is None or prior_gross_profit is None:
        return None

    current_ad_value = abs(float(current_ad["value"]))
    prior_ad_value = abs(float(prior_ad["value"]))
    current_revenue_value = float(current_revenue["value"])
    prior_revenue_value = float(prior_revenue["value"])
    current_gross_profit_value = float(current_gross_profit["value"])
    prior_gross_profit_value = float(prior_gross_profit["value"])
    if (
        current_ad_value < MIN_CURRENT_AD_EXPENSE
        or current_revenue_value < MIN_CURRENT_REVENUE
        or prior_revenue_value <= 0.0
        or current_gross_profit_value < MIN_CURRENT_GROSS_PROFIT
        or prior_gross_profit_value <= 0.0
    ):
        return None

    current_ratio = current_ad_value / current_revenue_value
    prior_ratio = prior_ad_value / prior_revenue_value
    ratio_improvement = prior_ratio - current_ratio
    gross_margin = current_gross_profit_value / current_revenue_value
    revenue_growth = (current_revenue_value - prior_revenue_value) / abs(prior_revenue_value)
    gross_profit_growth = (current_gross_profit_value - prior_gross_profit_value) / abs(
        prior_gross_profit_value
    )
    if prior_ratio < MIN_PRIOR_AD_TO_REVENUE:
        return None
    if current_ratio > MAX_CURRENT_AD_TO_REVENUE:
        return None
    if ratio_improvement < MIN_AD_RATIO_IMPROVEMENT:
        return None
    if gross_margin < MIN_GROSS_MARGIN:
        return None
    if revenue_growth < MIN_REVENUE_GROWTH:
        return None
    if gross_profit_growth < MIN_GROSS_PROFIT_GROWTH:
        return None

    return {
        "ticker": ticker,
        "current_period_end": current_ad["end"],
        "current_ad_filed": current_ad["filed"],
        "current_ad_tag": current_ad.get("tag"),
        "current_ad_expense_value": _round(current_ad_value, 2),
        "current_revenue_value": _round(current_revenue_value, 2),
        "current_gross_profit_value": _round(current_gross_profit_value, 2),
        "prior_period_end": prior_ad["end"],
        "prior_ad_expense_value": _round(prior_ad_value, 2),
        "prior_revenue_value": _round(prior_revenue_value, 2),
        "prior_gross_profit_value": _round(prior_gross_profit_value, 2),
        "current_ad_to_revenue": _round(current_ratio, 6),
        "prior_ad_to_revenue": _round(prior_ratio, 6),
        "ad_ratio_improvement": _round(ratio_improvement, 6),
        "gross_margin": _round(gross_margin, 6),
        "revenue_growth": _round(revenue_growth, 6),
        "gross_profit_growth": _round(gross_profit_growth, 6),
        "fact_age_days": base._days_between(asof, current_ad["filed"]),
        "known_at": "raw_annual_companyfacts_filed_and_signal_close_before_next_open_paper_entry",
        "rule_version": RULE_VERSION,
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, dict[str, list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indices = {
        ticker: base.framework.shadow._row_index(base.framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    dates = base.framework.shadow._trading_dates(snapshot)
    window_dates = [day for day in dates if str(cfg["start"]) <= day <= str(cfg["end"])]
    eligible = sorted(set(quality_index) & set(snapshot))
    scan: Counter[str] = Counter()
    scan["scanned_trading_days"] = len(window_dates)
    scan["eligible_quality_tickers"] = len(eligible)
    candidates: list[dict[str, Any]] = []

    for signal_date in window_dates:
        for ticker in eligible:
            scan["ticker_day_evaluations"] += 1
            observation = _advertising_efficiency_observation(ticker, signal_date, quality_index[ticker])
            if observation is None:
                scan["failed_advertising_efficiency_gate"] += 1
                continue
            confirm = base._price_confirmation(
                snapshot=snapshot,
                indices=indices,
                ticker=ticker,
                signal_date=signal_date,
            )
            if confirm is None:
                scan["failed_price_confirmation"] += 1
                continue
            scan["qualified_candidate_rows"] += 1
            meta = sector_entries.get(ticker, {})
            improvement = float(observation["ad_ratio_improvement"] or 0.0)
            revenue_growth = float(observation["revenue_growth"] or 0.0)
            gross_growth = float(observation["gross_profit_growth"] or 0.0)
            score = (
                6.0 * min(improvement, 0.08)
                + 0.20 * max(min(revenue_growth, 0.60), -0.05)
                + 0.18 * max(min(gross_growth, 0.60), -0.10)
                + 0.55 * float(confirm["candidate_ret20_excess_spy"])
                + 0.14 * float(confirm["candidate_ret60_excess_spy"])
                + 0.10 * float(confirm["candidate_close_location"])
                + 0.035
                * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
            )
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "ADVERTISING_EFFICIENCY_IMPROVEMENT_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_companyfacts": True,
                    "uses_raw_companyfacts_cache": True,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    **{f"ad_efficiency_{key}": value for key, value in observation.items()},
                    **confirm,
                }
            )

    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in candidates:
        key = (row["date"], row["ticker"])
        existing = deduped.get(key)
        if existing is None or float(row["candidate_score"]) > float(existing["candidate_score"]):
            deduped[key] = row
    rows = list(deduped.values())
    rows.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"] or 0.0),
            -float(row["ad_efficiency_ad_ratio_improvement"] or 0.0),
            -float(row["ad_efficiency_revenue_growth"] or 0.0),
            -float(row["candidate_ret20_excess_spy"] or 0.0),
            -float(row["candidate_avg_dollar_volume_20d"] or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(rows)
    scan["candidate_signal_days"] = len({row["date"] for row in rows})
    scan["candidate_tickers"] = len({row["ticker"] for row in rows})
    return rows, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "max_annual_fact_age_days": MAX_ANNUAL_FACT_AGE_DAYS,
        "min_current_revenue": MIN_CURRENT_REVENUE,
        "min_current_ad_expense": MIN_CURRENT_AD_EXPENSE,
        "min_current_gross_profit": MIN_CURRENT_GROSS_PROFIT,
        "min_gross_margin": MIN_GROSS_MARGIN,
        "min_prior_ad_to_revenue": MIN_PRIOR_AD_TO_REVENUE,
        "max_current_ad_to_revenue": MAX_CURRENT_AD_TO_REVENUE,
        "min_ad_ratio_improvement": MIN_AD_RATIO_IMPROVEMENT,
        "min_revenue_growth": MIN_REVENUE_GROWTH,
        "min_gross_profit_growth": MIN_GROSS_PROFIT_GROWTH,
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = base.framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    ev_delta = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if ev_delta <= base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_compression_ev_not_beaten")
    if pnl_delta <= base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_compression_pnl_not_beaten")
    if ev_delta <= base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_distribution_ev_not_beaten")
    if pnl_delta <= base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_distribution_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["accepted_compression_comparator"] = base.COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = base.DISTRIBUTION_COMPARATOR
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_not_promoted_advertising_efficiency_improvement"
        if gate["passed"]
        else "rejected_advertising_efficiency_improvement_candidate_pool"
    )
    return gate


def _interpretation(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    if gate4["passed"]:
        return (
            "The advertising efficiency improvement source cleared the numeric "
            "three-window replay screen, but remains only a replay lead because "
            "no shared daily/backtest helper was promoted."
        )
    return (
        "The advertising efficiency improvement source did not clear Gate 4 "
        f"(failed: {', '.join(gate4['failed_reasons']) or 'none'}). The fixed "
        "bundle tested explicit raw SEC advertising / selling-marketing "
        "intensity improvement plus liquid SPY-relative confirmation. It is "
        "not retained or promoted."
    )


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    interpretation = _interpretation(payload)
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": _utc_now(),
            "lane": "alpha_search",
            "status": status,
            "decision": gate4["decision"],
            "accepted": False,
            "accepted_alpha": False,
            "numeric_gate4_passed": gate4["passed"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "default_off_paper_candidate_pool_replay_scout",
            "implementation_mode": "private_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_sec_companyfacts_customer_acquisition_efficiency_candidate_pool",
            "new_evidence_type": "raw_sec_companyfacts_advertising_selling_marketing_expense_pit_field",
            "nearby_prior_experiments": [
                "exp-20260616-010",
                "exp-20260615-016",
                "exp-20260615-010",
                "exp-20260616-014",
                "exp-20260616-015",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "interpretation": interpretation,
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": 1 if gate4["passed"] else 0,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
    }
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "fy_duration_min": FY_DURATION_MIN,
        "fy_duration_max": FY_DURATION_MAX,
        "max_annual_fact_age_days": MAX_ANNUAL_FACT_AGE_DAYS,
        "min_current_revenue": MIN_CURRENT_REVENUE,
        "min_current_ad_expense": MIN_CURRENT_AD_EXPENSE,
        "min_current_gross_profit": MIN_CURRENT_GROSS_PROFIT,
        "min_gross_margin": MIN_GROSS_MARGIN,
        "min_prior_ad_to_revenue": MIN_PRIOR_AD_TO_REVENUE,
        "max_current_ad_to_revenue": MAX_CURRENT_AD_TO_REVENUE,
        "min_ad_ratio_improvement": MIN_AD_RATIO_IMPROVEMENT,
        "min_revenue_growth": MIN_REVENUE_GROWTH,
        "min_gross_profit_growth": MIN_GROSS_PROFIT_GROWTH,
        "advertising_tags": list(ADVERTISING_TAGS),
        "revenue_tags": list(REVENUE_TAGS),
        "gross_profit_tags": list(GROSS_PROFIT_TAGS),
        "min_price": base.MIN_PRICE,
        "min_avg_dollar_volume_20d": base.MIN_AVG_DOLLAR_VOLUME_20D,
        "min_ret20_excess_spy": base.MIN_RET20_EXCESS_SPY,
        "min_ret60_excess_spy": base.MIN_RET60_EXCESS_SPY,
        "min_signal_return": base.MIN_SIGNAL_RETURN,
        "max_signal_return": base.MAX_SIGNAL_RETURN,
        "min_close_location": base.MIN_CLOSE_LOCATION,
        "max_realized_vol_20d": base.MAX_REALIZED_VOL_20D,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["execution_model"] = (
        "Annual advertising / selling-marketing expense, revenue, and "
        "gross-profit facts are read from raw SEC Companyfacts tags and are "
        "known only by filed date (<= signal date). Current advertising "
        "intensity is compared with the prior annual period using the same "
        "expense tag. Price confirmation uses only signal-date OHLCV. Paper "
        "entry is the next available open with existing entry slippage; exit is "
        "the close 10 trading days after the signal with target-side sell "
        "slippage and ROUND_TRIP_COST_PCT."
    )
    payload["backtest_protocol"]["companyfacts_source"] = _repo_rel(RAW_COMPANYFACTS_CACHE)
    payload["gate2"]["runtime_fields"] = [
        "raw SEC companyfacts advertising / selling-marketing annual facts",
        "raw SEC companyfacts annual revenue facts",
        "raw SEC companyfacts annual gross-profit facts",
        "raw SEC companyfacts filed date and period end",
        "warehouse ticker_universe CIK mapping",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A retry needs materially different PIT customer-acquisition efficiency "
        "evidence such as unit economics, segment-level sales productivity, "
        "new customer count, paid channel mix, or closed forward replacement "
        "rows. Do not sweep advertising tags, intensity thresholds, annual fact "
        "freshness, price guards, top-N, hold, cooldown, or notional on these "
        "frozen windows."
    )
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
            "Do not retry by sweeping advertising / selling-marketing tag lists, "
            "expense/revenue thresholds, gross-margin floors, annual fact "
            "freshness, RS/close/volume/vol guards, top-N, hold days, cooldown, "
            "or notional on these frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Eligible | Raw | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {elig} | {raw} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                elig=scan.get("eligible_quality_tickers", 0),
                raw=scan.get("deduped_candidate_rows", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Advertising Efficiency Improvement",
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
            "- Accepted compression comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"],
                base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Accepted distribution comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"],
                base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"],
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
    return base._build_log_record(payload)


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
            _repo_rel(Path(__file__)): base.framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): base.framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): base.framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): base.framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): base.framework._sha256(CARD_MD),
        },
    }
    base.framework._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    base.framework._write_json(OUT_JSON, payload)
    base.framework._write_json(LOG_JSON, payload)
    base.framework._write_text(CARD_MD, _build_card(payload))
    base.framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
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
    base.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )
    _write_manifest(payload)


def _install() -> None:
    template.EXPERIMENT_ID = EXPERIMENT_ID
    template.STEM = STEM
    template.TRIAL_FAMILY = TRIAL_FAMILY
    template.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    template.CHANGED_VARIABLE = CHANGED_VARIABLE
    template.RULE_VERSION = RULE_VERSION
    template.OWNER = OWNER
    template.OUT_DIR = OUT_DIR
    template.OUT_JSON = OUT_JSON
    template.LOG_JSON = LOG_JSON
    template.TICKET_JSON = TICKET_JSON
    template.CARD_MD = CARD_MD
    template.MANIFEST_JSON = MANIFEST_JSON
    template.EXPERIMENT_LOG = EXPERIMENT_LOG
    template.REGISTRY_JSON = REGISTRY_JSON
    template.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    template.HOLD_DAYS = HOLD_DAYS
    template.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    template.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    template.FY_DURATION_MIN = FY_DURATION_MIN
    template.FY_DURATION_MAX = FY_DURATION_MAX
    template.MAX_ANNUAL_FACT_AGE_DAYS = MAX_ANNUAL_FACT_AGE_DAYS
    template.MIN_CURRENT_REVENUE = MIN_CURRENT_REVENUE
    template.MIN_CURRENT_EXPENSE = MIN_CURRENT_AD_EXPENSE
    template.MIN_CURRENT_GROSS_PROFIT = MIN_CURRENT_GROSS_PROFIT
    template.MIN_GROSS_MARGIN = MIN_GROSS_MARGIN
    template.MAX_CURRENT_EXPENSE_TO_REVENUE = MAX_CURRENT_AD_TO_REVENUE
    template.MIN_EXPENSE_RATIO_IMPROVEMENT = MIN_AD_RATIO_IMPROVEMENT
    template.MIN_GROSS_PROFIT_GROWTH = MIN_GROSS_PROFIT_GROWTH
    template.EXPENSE_TAGS = ADVERTISING_TAGS
    template.REVENUE_TAGS = REVENUE_TAGS
    template.GROSS_PROFIT_TAGS = GROSS_PROFIT_TAGS
    template.PREDICTION = PREDICTION
    template.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    template.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    template._RAW_INDEX_CACHE = None
    template._build_quality_index = _build_quality_index
    template._candidate_rows_for_window = _candidate_rows_for_window
    template._gate4 = _gate4
    template._postprocess_payload = _postprocess_payload
    template._build_card = _build_card
    template._build_log_record = _build_log_record
    template._write_manifest = _write_manifest
    template._persist = _persist


def main() -> None:
    _install()
    template.main()


if __name__ == "__main__":
    main()
