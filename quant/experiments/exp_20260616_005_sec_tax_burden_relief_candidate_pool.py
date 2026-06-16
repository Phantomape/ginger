"""exp-20260616-005: raw SEC tax-burden relief candidate scout.

Replay-only alpha search. The single decision hypothesis is a PIT free SEC
Companyfacts candidate source: production-universe names whose latest filed
annual effective tax burden (income tax expense / pretax income) is falling
year over year, with stable pretax income and revenue, may identify cleaner
after-tax earnings power when price already shows liquid SPY-relative
leadership.

This intentionally reads the raw SEC Companyfacts cache because selected
Companyfacts sidecars do not carry a canonical tax-burden field. No production
code, shared adapter, live/default orders, ranking, sizing, exits, LLM/news
path, or watchlist behavior is changed. A positive replay is only a lead until
a shared historical/daily helper reproduces the exact PIT field mapping. No
JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260614_020_accruals_cash_conversion_quality as base
import exp_20260616_003_raw_sec_rd_intensity_candidate_pool as rd


EXPERIMENT_ID = "exp-20260616-005"
STEM = "sec_tax_burden_relief_candidate_pool"
TRIAL_FAMILY = "raw_sec_companyfacts_tax_burden_relief_candidate_pool"
TRIAL_VARIANT_ID = "tax_burden_relief_top1_next_open_10d_v1"
CHANGED_VARIABLE = "raw_sec_companyfacts_tax_burden_relief_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search"

REPO_ROOT = base.REPO_ROOT
RAW_COMPANYFACTS_CACHE = REPO_ROOT / "data" / "cache" / "sec" / "companyfacts"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260616_005_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = base.BASE_NOTIONAL_USD
HOLD_DAYS = base.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = base.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = base.SAME_TICKER_COOLDOWN_DAYS

FY_DURATION_MIN = base.FY_DURATION_MIN
FY_DURATION_MAX = base.FY_DURATION_MAX
MAX_ANNUAL_FACT_AGE_DAYS = 430
MIN_CURRENT_REVENUE = 500_000_000.0
MIN_CURRENT_TAX_BURDEN = 0.02
MAX_CURRENT_TAX_BURDEN = 0.28
MIN_PRIOR_TAX_BURDEN = 0.12
MAX_PRIOR_TAX_BURDEN = 0.50
MIN_TAX_RELIEF_DELTA = 0.03
MIN_TAX_RELIEF_PCT = 0.15
MIN_PRETAX_GROWTH = -0.05
MIN_REVENUE_GROWTH = -0.02
MIN_AFTER_TAX_INCOME_GROWTH = 0.00

TAX_EXPENSE_TAGS = (
    "IncomeTaxExpenseBenefit",
)
PRETAX_INCOME_TAGS = (
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
)
REVENUE_TAGS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
)

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "tax_field_noisy_or_one_off",
        "window_regression",
        "old_thin_coverage_gap",
        "accepted_distribution_not_beaten",
    ],
    "confidence_reason": (
        "Mechanism: a lower GAAP tax burden with stable pretax income can raise "
        "after-tax earnings power and is a free filed-date bounded SEC field. "
        "Nearby raw Companyfacts tests were directionally positive but failed "
        "window/drawdown/comparator gates, so probability is low; this tests a "
        "different income-statement component, not R&D, interest, demand, cash "
        "conversion, asset growth, or operating leverage."
    ),
    "recorded_at": "2026-06-16T03:04:13+00:00",
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
            "missing raw SEC annual tax/pretax/revenue tuple, missing prior "
            "annual comparison tuple, stale facts, negative pretax income, "
            "missing CIK mapping, missing OHLCV, missing next open, or missing "
            "10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same raw "
        "SEC tag mapping, filed-date PIT annual tax-burden relief gate, stable "
        "pretax/revenue checks, liquid SPY-relative confirmation, cooldown, "
        "next-open paper entry, 10-day exit, costs, and concentration controls "
        "in both historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: raw SEC Companyfacts annual tax-burden relief "
        "(income tax expense / pretax income falling year over year) paired "
        "with stable pretax income, stable revenue, and liquid SPY-relative "
        "leadership may identify cleaner post-filing after-tax earnings power "
        "that price continues to recognize over the next 10 trading days."
    ),
    "2_history_check": {
        "exp-20260616-003": (
            "Raw SEC R&D intensity was rejected despite positive aggregate EV "
            "because late_strong/mid_weak regressed and concentration failed. "
            "This run uses tax burden relief, not innovation spend."
        ),
        "exp-20260616-004": (
            "Raw SEC interest-burden relief had positive aggregate EV/PnL but "
            "failed old_thin coverage, concentration, and distribution "
            "comparator gates. This run tests after-tax earnings power rather "
            "than financing-cost relief."
        ),
        "exp-20260615-016": (
            "Operating leverage acceleration was rejected on window/drawdown "
            "and accepted-comparator gates. This run avoids another revenue vs "
            "operating-income spread and uses a different filed tax field."
        ),
        "exp-20260615-008": (
            "FCF/capex coverage quality was rejected. This run is not another "
            "cash-conversion threshold; it tests tax-expense burden with "
            "pretax and revenue stability."
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
        "exp_20260616_005_sec_tax_burden_relief_candidate_pool.py"
    ),
}

_RAW_INDEX_CACHE: tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return base._round(value, digits)


def _tax_pretax_revenue_tuple(
    facts: dict[str, list[dict[str, Any]]],
    *,
    asof: str,
    before_end: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]] | None:
    tax = rd._latest_period_fact(facts["tax_expense"], asof=asof, before_end=before_end)
    if tax is None:
        return None
    pretax = rd._latest_period_fact(facts["pretax_income"], asof=asof, end=tax["end"])
    revenue = rd._latest_period_fact(facts["revenue"], asof=asof, end=tax["end"])
    if pretax is None or revenue is None:
        return None
    return tax, pretax, revenue


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
        tax_facts = rd._raw_annual_facts(usgaap, TAX_EXPENSE_TAGS)
        pretax_facts = rd._raw_annual_facts(usgaap, PRETAX_INCOME_TAGS)
        revenue_facts = rd._raw_annual_facts(usgaap, REVENUE_TAGS)
        if not tax_facts:
            stats["tickers_missing_raw_annual_tax_expense"] += 1
            continue
        if not pretax_facts:
            stats["tickers_missing_raw_annual_pretax_income"] += 1
            continue
        if not revenue_facts:
            stats["tickers_missing_raw_annual_revenue"] += 1
            continue
        index[ticker] = {
            "tax_expense": tax_facts,
            "pretax_income": pretax_facts,
            "revenue": revenue_facts,
        }
        stats["tickers_with_raw_annual_tax_pretax_and_revenue"] += 1
        stats["raw_annual_tax_fact_count"] += len(tax_facts)
        stats["raw_annual_pretax_fact_count"] += len(pretax_facts)
        stats["raw_annual_revenue_fact_count"] += len(revenue_facts)

    summary = {
        "raw_companyfacts_cache": _repo_rel(RAW_COMPANYFACTS_CACHE),
        "tax_expense_tags": list(TAX_EXPENSE_TAGS),
        "pretax_income_tags": list(PRETAX_INCOME_TAGS),
        "revenue_tags": list(REVENUE_TAGS),
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
        "field_source": "raw_sec_companyfacts_cache_not_selected_sidecar",
    }


def _tax_burden_observation(
    ticker: str,
    asof: str,
    facts: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    current_tuple = _tax_pretax_revenue_tuple(facts, asof=asof)
    if current_tuple is None:
        return None
    current_tax, current_pretax, current_revenue = current_tuple
    if base._days_between(asof, current_tax["filed"]) > MAX_ANNUAL_FACT_AGE_DAYS:
        return None

    prior_tuple = _tax_pretax_revenue_tuple(facts, asof=asof, before_end=current_tax["end"])
    if prior_tuple is None:
        return None
    prior_tax, prior_pretax, prior_revenue = prior_tuple

    current_tax_value = float(current_tax["value"])
    current_pretax_value = float(current_pretax["value"])
    current_revenue_value = float(current_revenue["value"])
    prior_tax_value = float(prior_tax["value"])
    prior_pretax_value = float(prior_pretax["value"])
    prior_revenue_value = float(prior_revenue["value"])
    if min(
        current_tax_value,
        current_pretax_value,
        current_revenue_value,
        prior_tax_value,
        prior_pretax_value,
        prior_revenue_value,
    ) <= 0.0:
        return None
    if current_revenue_value < MIN_CURRENT_REVENUE:
        return None

    current_burden = current_tax_value / current_pretax_value
    prior_burden = prior_tax_value / prior_pretax_value
    tax_relief = prior_burden - current_burden
    tax_relief_pct = tax_relief / prior_burden if prior_burden > 0.0 else 0.0
    pretax_growth = current_pretax_value / prior_pretax_value - 1.0
    revenue_growth = current_revenue_value / prior_revenue_value - 1.0
    current_after_tax_income = current_pretax_value - current_tax_value
    prior_after_tax_income = prior_pretax_value - prior_tax_value
    if current_after_tax_income <= 0.0 or prior_after_tax_income <= 0.0:
        return None
    after_tax_income_growth = current_after_tax_income / prior_after_tax_income - 1.0
    tax_expense_growth = current_tax_value / prior_tax_value - 1.0

    if current_burden < MIN_CURRENT_TAX_BURDEN:
        return None
    if current_burden > MAX_CURRENT_TAX_BURDEN:
        return None
    if prior_burden < MIN_PRIOR_TAX_BURDEN or prior_burden > MAX_PRIOR_TAX_BURDEN:
        return None
    if tax_relief < MIN_TAX_RELIEF_DELTA:
        return None
    if tax_relief_pct < MIN_TAX_RELIEF_PCT:
        return None
    if pretax_growth < MIN_PRETAX_GROWTH:
        return None
    if revenue_growth < MIN_REVENUE_GROWTH:
        return None
    if after_tax_income_growth < MIN_AFTER_TAX_INCOME_GROWTH:
        return None

    return {
        "current_fiscal_year_end": current_tax["end"],
        "prior_fiscal_year_end": prior_tax["end"],
        "current_tax_filed": current_tax["filed"],
        "prior_tax_filed": prior_tax["filed"],
        "current_pretax_filed": current_pretax["filed"],
        "prior_pretax_filed": prior_pretax["filed"],
        "current_revenue_filed": current_revenue["filed"],
        "prior_revenue_filed": prior_revenue["filed"],
        "current_tax_tag": current_tax["tag"],
        "current_pretax_tag": current_pretax["tag"],
        "current_revenue_tag": current_revenue["tag"],
        "current_tax_expense": _round(current_tax_value, 2),
        "prior_tax_expense": _round(prior_tax_value, 2),
        "current_pretax_income": _round(current_pretax_value, 2),
        "prior_pretax_income": _round(prior_pretax_value, 2),
        "current_revenue": _round(current_revenue_value, 2),
        "prior_revenue": _round(prior_revenue_value, 2),
        "current_after_tax_income": _round(current_after_tax_income, 2),
        "prior_after_tax_income": _round(prior_after_tax_income, 2),
        "current_tax_burden": _round(current_burden, 6),
        "prior_tax_burden": _round(prior_burden, 6),
        "tax_burden_relief": _round(tax_relief, 6),
        "tax_burden_relief_pct": _round(tax_relief_pct, 6),
        "tax_expense_growth": _round(tax_expense_growth, 6),
        "pretax_income_growth": _round(pretax_growth, 6),
        "revenue_growth": _round(revenue_growth, 6),
        "after_tax_income_growth": _round(after_tax_income_growth, 6),
        "fact_age_days": base._days_between(asof, current_tax["filed"]),
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
            quality = _tax_burden_observation(ticker, signal_date, quality_index[ticker])
            if quality is None:
                scan["failed_tax_burden_gate"] += 1
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
                1.20 * min(float(quality["tax_burden_relief_pct"] or 0.0), 1.0)
                + 1.05 * min(float(quality["tax_burden_relief"] or 0.0), 0.20)
                + 0.35 * min(float(quality["after_tax_income_growth"] or 0.0), 1.0)
                + 0.18 * min(float(quality["pretax_income_growth"] or 0.0), 1.0)
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
                    "source": "RAW_SEC_TAX_BURDEN_RELIEF_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "raw_annual_companyfacts_filed_and_signal_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_companyfacts": True,
                    "uses_raw_sec_companyfacts_cache": True,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    **{f"quality_{key}": value for key, value in quality.items()},
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
            -float(row["quality_tax_burden_relief_pct"] or 0.0),
            -float(row["quality_after_tax_income_growth"] or 0.0),
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
        "min_current_tax_burden": MIN_CURRENT_TAX_BURDEN,
        "max_current_tax_burden": MAX_CURRENT_TAX_BURDEN,
        "min_prior_tax_burden": MIN_PRIOR_TAX_BURDEN,
        "max_prior_tax_burden": MAX_PRIOR_TAX_BURDEN,
        "min_tax_relief_delta": MIN_TAX_RELIEF_DELTA,
        "min_tax_relief_pct": MIN_TAX_RELIEF_PCT,
        "min_pretax_growth": MIN_PRETAX_GROWTH,
        "min_revenue_growth": MIN_REVENUE_GROWTH,
        "min_after_tax_income_growth": MIN_AFTER_TAX_INCOME_GROWTH,
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
        "positive_replay_lead_not_promoted_raw_sec_tax_burden_relief"
        if gate["passed"]
        else "rejected_raw_sec_tax_burden_relief_candidate_pool"
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
    status = "observed_only_positive_replay_lead" if gate4["passed"] else "rejected"
    if gate4["passed"]:
        interpretation = (
            "The raw SEC tax-burden relief source cleared the numeric "
            "three-window replay screen, but remains only a replay lead because "
            "no shared daily/backtest helper was promoted."
        )
    else:
        interpretation = (
            "The raw SEC tax-burden relief source did not clear Gate 4 "
            f"(failed: {', '.join(gate4['failed_reasons']) or 'none'}). It is "
            "not retained or promoted."
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
            "mechanism_family": "production_visible_free_sec_companyfacts_tax_burden_candidate_pool",
            "new_evidence_type": "raw_sec_companyfacts_income_tax_expense_effective_rate_pit_field",
            "nearby_prior_experiments": [
                "exp-20260616-003",
                "exp-20260616-004",
                "exp-20260615-016",
                "exp-20260615-008",
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
            "max_annual_fact_age_days": MAX_ANNUAL_FACT_AGE_DAYS,
            "min_current_revenue": MIN_CURRENT_REVENUE,
            "min_current_tax_burden": MIN_CURRENT_TAX_BURDEN,
            "max_current_tax_burden": MAX_CURRENT_TAX_BURDEN,
            "min_prior_tax_burden": MIN_PRIOR_TAX_BURDEN,
            "max_prior_tax_burden": MAX_PRIOR_TAX_BURDEN,
            "min_tax_relief_delta": MIN_TAX_RELIEF_DELTA,
            "min_tax_relief_pct": MIN_TAX_RELIEF_PCT,
            "min_pretax_growth": MIN_PRETAX_GROWTH,
            "min_revenue_growth": MIN_REVENUE_GROWTH,
            "min_after_tax_income_growth": MIN_AFTER_TAX_INCOME_GROWTH,
            "tax_expense_tags": list(TAX_EXPENSE_TAGS),
            "pretax_income_tags": list(PRETAX_INCOME_TAGS),
            "revenue_tags": list(REVENUE_TAGS),
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Annual income tax expense, pretax income, and revenue are read from "
        "raw SEC Companyfacts tags and are known only by filed date (<= signal "
        "date). Current and prior annual tax values are matched to same-period "
        "annual pretax income and revenue by fiscal year end. Price "
        "confirmation uses only signal-date OHLCV. Paper entry is the next "
        "available open with existing entry slippage; exit is the close 10 "
        "trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    payload["backtest_protocol"]["companyfacts_source"] = _repo_rel(RAW_COMPANYFACTS_CACHE)
    payload["gate2"]["runtime_fields"] = [
        "raw SEC companyfacts IncomeTaxExpenseBenefit annual facts",
        "raw SEC companyfacts annual pretax income facts",
        "raw SEC companyfacts annual revenue facts",
        "raw SEC companyfacts filed date and period end",
        "warehouse ticker_universe CIK mapping",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A retry needs materially different PIT tax evidence such as durable "
        "cash-tax normalization, tax-credit provenance, or post-filing analyst "
        "estimate revisions confirming after-tax earnings power. Do not sweep "
        "tax-burden thresholds, pretax/revenue growth floors, annual fact "
        "freshness, tag lists, RS/close/volume/vol guards, top-N, hold, "
        "cooldown, or notional on these frozen windows."
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
            "Do not retry by sweeping tax-burden relief, current/prior effective "
            "tax-rate bounds, pretax/revenue/after-tax growth floors, annual "
            "fact freshness, tag lists, RS/close/volume/vol guards, top-N, hold "
            "days, cooldown, or notional on these frozen windows."
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
            f"# {EXPERIMENT_ID} Raw SEC Tax-Burden Relief",
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
