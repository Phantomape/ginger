"""exp-20260618-020: forward intangible amortization relief scout.

Replay-only alpha search. The single decision hypothesis is a PIT free SEC
Companyfacts candidate source: production-universe names whose filed
finite-lived intangible amortization schedule shows a lower next-12-month
noncash expense burden than the prior filed schedule, while revenue and gross
profit remain healthy and price already confirms SPY-relative demand, may
identify near-term EPS-quality relief before a 10-trading-day continuation leg.

This is deliberately not a shared helper yet because the field is adjacent to
the rejected trailing D&A family and needs a data-shape scout. A positive replay
would be only a lead until a shared historical/daily helper reproduces it.
No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260617_005_depreciation_amortization_burden_relief as template


base = template.base

EXPERIMENT_ID = "exp-20260618-020"
STEM = "forward_intangible_amortization_relief"
TRIAL_FAMILY = "forward_intangible_amortization_relief_candidate_pool"
TRIAL_VARIANT_ID = "forward_intangible_amortization_relief_top1_next_open_10d_v1"
CHANGED_VARIABLE = "raw_sec_companyfacts_forward_intangible_amortization_relief_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "codex-alpha-search"

REPO_ROOT = base.REPO_ROOT
RAW_COMPANYFACTS_CACHE = REPO_ROOT / "data" / "cache" / "sec" / "companyfacts"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260618_020_{STEM}.json"
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
MAX_SCHEDULE_FACT_AGE_DAYS = 430
MAX_ANNUAL_FACT_AGE_DAYS = 430
MIN_CURRENT_REVENUE = 500_000_000.0
MIN_CURRENT_GROSS_PROFIT = 25_000_000.0
MIN_CURRENT_SCHEDULE_EXPENSE = 5_000_000.0
MIN_PRIOR_SCHEDULE_EXPENSE = 20_000_000.0
MIN_GROSS_MARGIN = 0.10
MIN_PRIOR_SCHEDULE_TO_REVENUE = 0.005
MAX_CURRENT_SCHEDULE_TO_REVENUE = 0.20
MIN_SCHEDULE_RATIO_IMPROVEMENT = 0.002
MIN_SCHEDULE_DECLINE_PCT = 0.05
MIN_REVENUE_GROWTH = -0.05
MAX_SCHEDULE_TO_ACTUAL_AMORTIZATION = 1.15

FORWARD_AMORTIZATION_TAGS = (
    "FiniteLivedIntangibleAssetsAmortizationExpenseNextTwelveMonths",
)
ACTUAL_AMORTIZATION_TAGS = (
    "AmortizationOfIntangibleAssets",
    "FiniteLivedIntangibleAssetsAmortizationExpense",
)
REVENUE_TAGS = template.REVENUE_TAGS
GROSS_PROFIT_TAGS = ("GrossProfit",)

PREDICTION = {
    "success_probability": 0.13,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "nearby_DA_family_saturated",
        "window_regression",
        "drawdown_drift",
        "accepted_comparator_not_beaten",
        "amortization_schedule_not_incremental",
    ],
    "confidence_reason": (
        "The field is adjacent to the rejected D&A/asset-productivity family but "
        "uses a materially different PIT disclosure: company-filed next-12-month "
        "finite-lived intangible amortization schedule known at filing time, not "
        "realized trailing D&A. The edge is plausible for EPS-quality relief in "
        "intangible-heavy/acquisitive firms, but recent raw Companyfacts relief "
        "families often fail old_thin or drawdown gates."
    ),
    "recorded_at": "2026-06-18T19:05:57+00:00",
}

PRODUCTION_IMPACT = {
    **template.PRODUCTION_IMPACT,
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
        **template.PRODUCTION_IMPACT["execution_envelope"],
        "failure_handling": (
            "missing raw SEC forward finite-lived intangible amortization "
            "schedule, missing annual revenue or gross-profit normalizer, "
            "missing prior schedule comparison point, stale facts, missing CIK "
            "mapping, missing OHLCV, missing next open, or missing 10d exit "
            "rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same raw "
        "SEC forward amortization schedule mapping, filed-date PIT schedule "
        "relief gate, liquid SPY-relative confirmation, cooldown, next-open "
        "paper entry, 10-day exit, costs, and concentration controls in both "
        "historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: raw SEC Companyfacts filed finite-lived intangible "
        "amortization schedule relief, where next-12-month disclosed "
        "amortization expense is lower versus the prior filed schedule while "
        "revenue and gross profit remain healthy and price shows liquid "
        "SPY-relative confirmation, may identify acquisition/intangible-heavy "
        "companies with a known near-term noncash EPS headwind easing before a "
        "10-day continuation leg."
    ),
    "2_history_check": {
        "exp-20260617-005": (
            "Rejected trailing D&A burden relief. This run uses filed forward "
            "finite-lived intangible amortization schedule relief, not trailing "
            "realized D&A/revenue."
        ),
        "exp-20260617-006": (
            "Rejected fixed-asset turnover improvement. This run is a disclosed "
            "noncash amortization headwind field, not PP&E productivity."
        ),
        "exp-20260617-007": (
            "Rejected CapEx/D&A reinvestment-cycle acceleration. This run does "
            "not use CapEx or replacement-cycle spending."
        ),
        "exp-20260617-008": (
            "Rejected impairment-overhang relief. This run is normal scheduled "
            "finite-lived intangible amortization, not impairment charges."
        ),
        "novelty_gate": (
            "Reservation override recorded the new evidence axis: "
            "raw_filed_forward_finite_lived_intangible_amortization_next_12_"
            "month_schedule_not_trailing_DA."
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
        "exp_20260618_020_forward_intangible_amortization_relief.py"
    ),
}

_RAW_INDEX_CACHE: tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return base._round(value, digits)


def _raw_instant_facts(usgaap: dict[str, Any], tags: tuple[str, ...]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for tag in tags:
        tag_payload = usgaap.get(tag) or {}
        for raw in tag_payload.get("units", {}).get("USD", []):
            start = str(raw.get("start") or "")[:10]
            end = str(raw.get("end") or "")[:10]
            filed = str(raw.get("filed") or "")[:10]
            value = template._float_or_none(raw.get("val"))
            if start or not end or not filed or value is None or value < 0.0:
                continue
            facts.append(
                {
                    "filed": filed,
                    "end": end,
                    "value": value,
                    "tag": tag,
                    "form": str(raw.get("form") or ""),
                    "fy": raw.get("fy"),
                    "fp": str(raw.get("fp") or ""),
                    "frame": raw.get("frame"),
                }
            )
    facts.sort(key=lambda row: (row["end"], row["filed"], row["tag"], row["value"]))
    return facts


def _load_raw_companyfacts_index() -> tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]]:
    global _RAW_INDEX_CACHE
    if _RAW_INDEX_CACHE is not None:
        return _RAW_INDEX_CACHE

    stats: Counter[str] = Counter()
    ticker_ciks: dict[str, int] = {}
    warehouse_uri = f"file:{Path(base.framework.WAREHOUSE).resolve().as_posix()}?mode=ro&immutable=1"
    with sqlite3.connect(warehouse_uri, uri=True) as con:
        rows = con.execute(
            """
            select u.ticker, u.cik
            from ticker_universe u
            join coverage_summary c on c.ticker = u.ticker
            where u.hygiene_pass = 1
              and c.all_windows_full_liquid = 1
              and u.cik is not null
            order by u.ticker
            """
        ).fetchall()
    for ticker, cik in rows:
        try:
            ticker_ciks[str(ticker).upper()] = int(cik)
        except (TypeError, ValueError):
            stats["invalid_cik_rows"] += 1

    index: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for ticker, cik in ticker_ciks.items():
        stats["warehouse_tickers_with_cik"] += 1
        path = RAW_COMPANYFACTS_CACHE / f"CIK{cik:010d}.json"
        if not path.exists():
            stats["missing_companyfacts_cache_file"] += 1
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            stats["unreadable_companyfacts_cache_file"] += 1
            continue
        usgaap = payload.get("facts", {}).get("us-gaap", {})
        schedule_facts = _raw_instant_facts(usgaap, FORWARD_AMORTIZATION_TAGS)
        revenue_facts = template._raw_annual_facts(usgaap, REVENUE_TAGS)
        gross_profit_facts = template._raw_annual_facts(usgaap, GROSS_PROFIT_TAGS)
        actual_amortization_facts = template._raw_annual_facts(usgaap, ACTUAL_AMORTIZATION_TAGS)
        if not schedule_facts:
            stats["tickers_missing_forward_amortization_schedule"] += 1
            continue
        if not revenue_facts:
            stats["tickers_missing_raw_annual_revenue"] += 1
            continue
        if not gross_profit_facts:
            stats["tickers_missing_raw_annual_gross_profit"] += 1
            continue
        index[ticker] = {
            "schedule": schedule_facts,
            "revenue": revenue_facts,
            "gross_profit": gross_profit_facts,
            "actual_amortization": actual_amortization_facts,
        }
        stats["tickers_with_forward_schedule_revenue_gross_profit"] += 1
        stats["raw_forward_schedule_fact_count"] += len(schedule_facts)
        stats["raw_annual_revenue_fact_count"] += len(revenue_facts)
        stats["raw_annual_gross_profit_fact_count"] += len(gross_profit_facts)
        stats["raw_actual_amortization_fact_count"] += len(actual_amortization_facts)

    summary = {
        "raw_companyfacts_cache": _repo_rel(RAW_COMPANYFACTS_CACHE),
        "forward_amortization_tags": list(FORWARD_AMORTIZATION_TAGS),
        "actual_amortization_tags": list(ACTUAL_AMORTIZATION_TAGS),
        "revenue_tags": list(REVENUE_TAGS),
        "gross_profit_tags": list(GROSS_PROFIT_TAGS),
        "warehouse_source": _repo_rel(base.framework.WAREHOUSE),
        **dict(stats),
    }
    _RAW_INDEX_CACHE = (index, summary)
    return _RAW_INDEX_CACHE


def _build_quality_index(
    companyfacts_rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]]:
    index, summary = _load_raw_companyfacts_index()
    return index, {
        **summary,
        "selected_companyfacts_rows_ignored": len(companyfacts_rows),
        "field_source": "raw_sec_companyfacts_cache_forward_amortization_schedule",
    }


def _latest_annual_pair(
    facts: dict[str, list[dict[str, Any]]],
    *,
    asof: str,
    before_end: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    revenue = template._latest_period_fact(facts["revenue"], asof=asof, before_end=before_end)
    if revenue is None:
        return None
    gross_profit = template._latest_period_fact(facts["gross_profit"], asof=asof, end=revenue["end"])
    if gross_profit is None:
        return None
    return revenue, gross_profit


def _forward_amortization_observation(
    ticker: str,
    asof: str,
    facts: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    current_schedule = template._latest_period_fact(facts["schedule"], asof=asof)
    if current_schedule is None:
        return None
    if base._days_between(asof, current_schedule["filed"]) > MAX_SCHEDULE_FACT_AGE_DAYS:
        return None
    prior_schedule = template._latest_period_fact(
        facts["schedule"], asof=asof, before_end=current_schedule["end"]
    )
    if prior_schedule is None:
        return None

    current_annual_pair = _latest_annual_pair(facts, asof=asof)
    if current_annual_pair is None:
        return None
    current_revenue, current_gross_profit = current_annual_pair
    if base._days_between(asof, current_revenue["filed"]) > MAX_ANNUAL_FACT_AGE_DAYS:
        return None
    prior_annual_pair = _latest_annual_pair(facts, asof=asof, before_end=current_revenue["end"])
    if prior_annual_pair is None:
        return None
    prior_revenue, prior_gross_profit = prior_annual_pair

    current_schedule_value = abs(float(current_schedule["value"]))
    prior_schedule_value = abs(float(prior_schedule["value"]))
    current_revenue_value = float(current_revenue["value"])
    prior_revenue_value = float(prior_revenue["value"])
    current_gross_profit_value = float(current_gross_profit["value"])
    prior_gross_profit_value = float(prior_gross_profit["value"])
    if min(current_revenue_value, prior_revenue_value, prior_gross_profit_value) <= 0.0:
        return None
    if current_revenue_value < MIN_CURRENT_REVENUE:
        return None
    if current_gross_profit_value < MIN_CURRENT_GROSS_PROFIT:
        return None
    if current_schedule_value < MIN_CURRENT_SCHEDULE_EXPENSE:
        return None
    if prior_schedule_value < MIN_PRIOR_SCHEDULE_EXPENSE:
        return None

    current_ratio = current_schedule_value / current_revenue_value
    prior_ratio = prior_schedule_value / prior_revenue_value
    ratio_improvement = prior_ratio - current_ratio
    schedule_decline_pct = (prior_schedule_value - current_schedule_value) / prior_schedule_value
    revenue_growth = current_revenue_value / prior_revenue_value - 1.0
    gross_profit_growth = current_gross_profit_value / prior_gross_profit_value - 1.0
    gross_margin = current_gross_profit_value / current_revenue_value
    if prior_ratio < MIN_PRIOR_SCHEDULE_TO_REVENUE:
        return None
    if current_ratio > MAX_CURRENT_SCHEDULE_TO_REVENUE:
        return None
    if ratio_improvement < MIN_SCHEDULE_RATIO_IMPROVEMENT:
        return None
    if schedule_decline_pct < MIN_SCHEDULE_DECLINE_PCT:
        return None
    if revenue_growth < MIN_REVENUE_GROWTH:
        return None
    if gross_margin < MIN_GROSS_MARGIN:
        return None

    actual_amortization = template._latest_period_fact(
        facts["actual_amortization"], asof=asof
    )
    actual_amortization_value = None
    schedule_to_actual = None
    if actual_amortization is not None:
        actual_amortization_value = abs(float(actual_amortization["value"]))
        if actual_amortization_value > 0.0:
            schedule_to_actual = current_schedule_value / actual_amortization_value
            if schedule_to_actual > MAX_SCHEDULE_TO_ACTUAL_AMORTIZATION:
                return None

    return {
        "current_schedule_end": current_schedule["end"],
        "prior_schedule_end": prior_schedule["end"],
        "current_schedule_filed": current_schedule["filed"],
        "prior_schedule_filed": prior_schedule["filed"],
        "current_revenue_filed": current_revenue["filed"],
        "prior_revenue_filed": prior_revenue["filed"],
        "current_schedule_tag": current_schedule["tag"],
        "current_revenue_tag": current_revenue["tag"],
        "current_gross_profit_tag": current_gross_profit["tag"],
        "current_schedule_expense": _round(current_schedule_value, 2),
        "prior_schedule_expense": _round(prior_schedule_value, 2),
        "actual_annual_amortization": _round(actual_amortization_value, 2),
        "schedule_to_actual_amortization": _round(schedule_to_actual, 6),
        "current_revenue": _round(current_revenue_value, 2),
        "prior_revenue": _round(prior_revenue_value, 2),
        "current_gross_profit": _round(current_gross_profit_value, 2),
        "current_schedule_to_revenue": _round(current_ratio, 6),
        "prior_schedule_to_revenue": _round(prior_ratio, 6),
        "schedule_ratio_improvement": _round(ratio_improvement, 6),
        "schedule_decline_pct": _round(schedule_decline_pct, 6),
        "revenue_growth": _round(revenue_growth, 6),
        "gross_profit_growth": _round(gross_profit_growth, 6),
        "gross_margin": _round(gross_margin, 6),
        "schedule_fact_age_days": base._days_between(asof, current_schedule["filed"]),
        "revenue_fact_age_days": base._days_between(asof, current_revenue["filed"]),
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
            quality = _forward_amortization_observation(ticker, signal_date, quality_index[ticker])
            if quality is None:
                scan["failed_forward_amortization_gate"] += 1
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
            score = (
                1.90 * min(float(quality["schedule_ratio_improvement"] or 0.0), 0.12)
                + 0.55 * min(float(quality["schedule_decline_pct"] or 0.0), 0.80)
                + 0.18 * min(float(quality["revenue_growth"] or 0.0), 1.0)
                + 0.16 * min(float(quality["gross_profit_growth"] or 0.0), 1.0)
                + 0.45 * float(confirm["candidate_ret20_excess_spy"])
                + 0.12 * float(confirm["candidate_ret60_excess_spy"])
                + 0.10 * float(confirm["candidate_close_location"])
                + 0.035
                * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
            )
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "RAW_SEC_FORWARD_INTANGIBLE_AMORTIZATION_RELIEF_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "raw_companyfacts_forward_amortization_schedule_filed_and_signal_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_companyfacts": True,
                    "uses_raw_sec_companyfacts_cache": True,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    **{f"amortization_{key}": value for key, value in quality.items()},
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
            -float(row["amortization_schedule_ratio_improvement"] or 0.0),
            -float(row["amortization_schedule_decline_pct"] or 0.0),
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
        "max_schedule_fact_age_days": MAX_SCHEDULE_FACT_AGE_DAYS,
        "max_annual_fact_age_days": MAX_ANNUAL_FACT_AGE_DAYS,
        "min_current_revenue": MIN_CURRENT_REVENUE,
        "min_current_gross_profit": MIN_CURRENT_GROSS_PROFIT,
        "min_current_schedule_expense": MIN_CURRENT_SCHEDULE_EXPENSE,
        "min_prior_schedule_expense": MIN_PRIOR_SCHEDULE_EXPENSE,
        "min_prior_schedule_to_revenue": MIN_PRIOR_SCHEDULE_TO_REVENUE,
        "max_current_schedule_to_revenue": MAX_CURRENT_SCHEDULE_TO_REVENUE,
        "min_schedule_ratio_improvement": MIN_SCHEDULE_RATIO_IMPROVEMENT,
        "min_schedule_decline_pct": MIN_SCHEDULE_DECLINE_PCT,
        "min_revenue_growth": MIN_REVENUE_GROWTH,
        "min_gross_margin": MIN_GROSS_MARGIN,
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
        "positive_replay_lead_not_promoted_forward_intangible_amortization_relief"
        if gate["passed"]
        else "rejected_forward_intangible_amortization_relief_candidate_pool"
    )
    return gate


def _load_companyfacts_rows_stub(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
    return []


def _configure_base() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = RULE_VERSION
    base.OWNER = OWNER
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.CARD_MD = CARD_MD
    base.MANIFEST_JSON = MANIFEST_JSON
    base.EXPERIMENT_LOG = EXPERIMENT_LOG
    base.REGISTRY_JSON = REGISTRY_JSON
    base.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    base.HOLD_DAYS = HOLD_DAYS
    base.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    base.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    base.FY_DURATION_MIN = FY_DURATION_MIN
    base.FY_DURATION_MAX = FY_DURATION_MAX
    base.MAX_ANNUAL_FACT_AGE_DAYS = MAX_ANNUAL_FACT_AGE_DAYS
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    base.load_companyfacts_rows = _load_companyfacts_rows_stub
    base._build_quality_index = _build_quality_index
    base._candidate_rows_for_window = _candidate_rows_for_window
    base._gate4 = _gate4


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    if gate4["passed"]:
        interpretation = (
            "The forward intangible amortization schedule relief source cleared "
            "the numeric three-window replay screen, but remains only a replay "
            "lead because no shared daily/backtest helper was promoted."
        )
    else:
        interpretation = (
            "The forward intangible amortization schedule relief source did not "
            f"clear Gate 4 (failed: {', '.join(gate4['failed_reasons']) or 'none'}). "
            "It is not retained or promoted."
        )

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": _utc_now(),
            "status": status,
            "decision": gate4["decision"],
            "accepted": False,
            "accepted_alpha": False,
            "numeric_gate4_passed": gate4["passed"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "default_off_paper_candidate_pool_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": (
                "production_visible_free_sec_companyfacts_forward_intangible_amortization_candidate_pool"
            ),
            "new_evidence_type": (
                "raw_filed_forward_finite_lived_intangible_amortization_next_12_month_schedule"
            ),
            "nearby_prior_experiments": [
                "exp-20260617-005",
                "exp-20260617-006",
                "exp-20260617-007",
                "exp-20260617-008",
                "exp-20260618-020_novelty_override",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "interpretation": interpretation,
            "negative_reflection": None if gate4["passed"] else interpretation,
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
        key: value
        for key, value in payload["parameters"].items()
        if key
        not in {
            "min_cash_conversion",
            "max_accruals_to_assets",
            "max_annual_fact_age_days",
        }
    }
    payload["parameters"].update(
        {
            "max_schedule_fact_age_days": MAX_SCHEDULE_FACT_AGE_DAYS,
            "max_annual_fact_age_days": MAX_ANNUAL_FACT_AGE_DAYS,
            "min_current_revenue": MIN_CURRENT_REVENUE,
            "min_current_gross_profit": MIN_CURRENT_GROSS_PROFIT,
            "min_current_schedule_expense": MIN_CURRENT_SCHEDULE_EXPENSE,
            "min_prior_schedule_expense": MIN_PRIOR_SCHEDULE_EXPENSE,
            "min_prior_schedule_to_revenue": MIN_PRIOR_SCHEDULE_TO_REVENUE,
            "max_current_schedule_to_revenue": MAX_CURRENT_SCHEDULE_TO_REVENUE,
            "min_schedule_ratio_improvement": MIN_SCHEDULE_RATIO_IMPROVEMENT,
            "min_schedule_decline_pct": MIN_SCHEDULE_DECLINE_PCT,
            "min_revenue_growth": MIN_REVENUE_GROWTH,
            "min_gross_margin": MIN_GROSS_MARGIN,
            "max_schedule_to_actual_amortization": MAX_SCHEDULE_TO_ACTUAL_AMORTIZATION,
            "forward_amortization_tags": list(FORWARD_AMORTIZATION_TAGS),
            "actual_amortization_tags": list(ACTUAL_AMORTIZATION_TAGS),
            "revenue_tags": list(REVENUE_TAGS),
            "gross_profit_tags": list(GROSS_PROFIT_TAGS),
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Forward finite-lived intangible amortization schedule, annual revenue, "
        "gross profit, and optional actual annual intangible amortization are "
        "read from raw SEC Companyfacts tags and known only by filed date "
        "(<= signal date). The rule requires next-12-month disclosed "
        "amortization/revenue burden to fall versus the prior filed schedule, "
        "with healthy gross margin and non-contracting revenue. Price "
        "confirmation uses only signal-date OHLCV. Paper entry is the next "
        "available open with existing entry slippage; exit is the close 10 "
        "trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    payload["backtest_protocol"]["companyfacts_source"] = _repo_rel(RAW_COMPANYFACTS_CACHE)
    payload["gate2"]["runtime_fields"] = [
        "raw SEC companyfacts finite-lived intangible amortization next-12-month schedule",
        "raw SEC companyfacts annual revenue facts",
        "raw SEC companyfacts annual gross-profit facts",
        "raw SEC companyfacts optional annual intangible amortization facts",
        "raw SEC companyfacts filed date and period end",
        "warehouse ticker_universe CIK mapping",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A retry needs materially different PIT intangible/liability provenance, "
        "such as parsed acquisition integration economics, maturity cliffs, "
        "segment/customer capacity disclosures, or closed forward "
        "replacement-value rows. Do not sweep schedule ratio, schedule decline, "
        "revenue/gross-margin, fact-age, price, top-N, hold, cooldown, or "
        "notional thresholds on these frozen windows."
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
            "Do not retry by sweeping forward amortization schedule ratio, "
            "schedule decline, actual-amortization guard, revenue/gross-profit "
            "floors, annual fact freshness, RS/close/volume/vol guards, top-N, "
            "hold days, cooldown, or notional on these frozen windows."
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Eligible | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {elig} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                elig=scan.get("eligible_quality_tickers", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Forward Intangible Amortization Relief",
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
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Accepted compression comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"],
                base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Accepted distribution comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"],
                base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
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
    log_record = base._build_log_record(payload)
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


def main() -> None:
    _configure_base()
    payload = _postprocess_payload(base._build_payload())
    _persist(payload)
    print(json.dumps(base.framework._safe(base._build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
