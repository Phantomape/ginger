"""exp-20260619-005: debt maturity cliff relief scout.

Replay-only alpha search. The single decision hypothesis is a PIT free SEC
Companyfacts candidate source: production-universe names whose filed debt
maturity ladder shows near-term principal cliff relief versus the prior filed
schedule, optionally supported by filed line-of-credit capacity, while price
already confirms liquid SPY-relative demand.

This is deliberately not a shared helper yet because the raw maturity ladder
field needs a data-shape scout. A positive replay is only a lead until a shared
historical/daily helper reproduces it. No production code, run adapter,
backtester adapter, ranking, sizing, exits, orders, LLM/news path, or watchlist
behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260616_003_raw_sec_rd_intensity_candidate_pool as rd
import exp_20260616_022_quarterly_inventory_dio_turnover_improvement as q


base = q.base

EXPERIMENT_ID = "exp-20260619-005"
STEM = "debt_maturity_cliff_relief"
TRIAL_FAMILY = "debt_maturity_cliff_relief_candidate_pool"
TRIAL_VARIANT_ID = "debt_maturity_cliff_relief_top1_next_open_10d_v1"
CHANGED_VARIABLE = "raw_sec_companyfacts_debt_maturity_cliff_relief_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
RAW_COMPANYFACTS_CACHE = REPO_ROOT / "data" / "cache" / "sec" / "companyfacts"
BASELINE_RESULT_JSON = (
    REPO_ROOT / "data" / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260619_005_{STEM}.json"
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

FY_DURATION_MIN = q.QUARTER_DURATION_MIN
FY_DURATION_MAX = q.QUARTER_DURATION_MAX
MAX_SCHEDULE_FACT_AGE_DAYS = 430
MAX_ANNUAL_FACT_AGE_DAYS = 430
MIN_CURRENT_REVENUE = 500_000_000.0
MIN_PRIOR_NEXT_PERIOD_MATURITY = 25_000_000.0
MIN_PRIOR_WALL_TO_REVENUE = 0.010
MAX_CURRENT_WALL_TO_REVENUE = 0.350
MAX_UNCOVERED_CURRENT_WALL_TO_REVENUE = 0.120
MIN_WALL_RATIO_RELIEF = 0.003
MIN_WALL_DECLINE_PCT = 0.10
MIN_REVENUE_GROWTH = -0.05
MIN_CAPACITY_COVERAGE = 1.00

NEXT_TWELVE_TAGS = (
    "LongTermDebtMaturitiesRepaymentsOfPrincipalInNextTwelveMonths",
)
YEAR_TWO_TAGS = (
    "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearTwo",
)
OTHER_MATURITY_TAGS = (
    "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearThree",
    "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearFour",
    "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearFive",
    "LongTermDebtMaturitiesRepaymentsOfPrincipalAfterYearFive",
    "LongTermDebtMaturitiesRepaymentsOfPrincipalInYearSixAndThereafter",
    "LongTermDebtMaturitiesRepaymentsOfPrincipalAfterYearFiveAndThereafter",
)
CAPACITY_TAGS = (
    "LineOfCreditFacilityRemainingBorrowingCapacity",
    "LineOfCreditFacilityCurrentBorrowingCapacity",
    "LineOfCreditFacilityMaximumBorrowingCapacity",
    "DebtInstrumentAvailableBorrowings",
    "CreditFacilityRemainingBorrowingCapacity",
)
REVENUE_TAGS = rd.REVENUE_TAGS

PREDICTION = {
    "success_probability": 0.14,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "thin_maturity_schedule_coverage",
        "mid_window_coverage_gap",
        "window_regression",
        "drawdown_drift",
        "accepted_distribution_not_beaten",
    ],
    "confidence_reason": (
        "Prior raw debt and interest burden relief showed positive aggregate "
        "evidence but failed robustness. This uses a materially different PIT "
        "financing field explicitly requested by the prior debt closeout: filed "
        "maturity ladder and line-of-credit capacity, not debt/revenue or "
        "interest-expense thresholds."
    ),
    "recorded_at": "2026-06-19T03:12:03+00:00",
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
            "missing raw SEC debt maturity ladder, missing annual revenue "
            "normalizer, missing prior year-two schedule comparison point, "
            "stale facts, missing CIK mapping, missing OHLCV, missing next "
            "open, or missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same raw "
        "SEC debt maturity ladder and credit capacity filed-date PIT mapping, "
        "liquid SPY-relative confirmation, cooldown, next-open paper entry, "
        "10-day exit, costs, and concentration controls in both historical "
        "replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: raw SEC Companyfacts debt maturity cliff relief, where "
        "near-term filed principal maturities fall versus the prior filed debt "
        "maturity schedule or are covered by filed line-of-credit capacity, "
        "paired with liquid SPY-relative leadership, may identify refinancing/"
        "liquidity-risk relief candidates before a 10-trading-day continuation "
        "leg."
    ),
    "2_history_check": {
        "exp-20260616-029": (
            "Rejected principal debt burden relief despite positive aggregate "
            "EV/PnL because old_thin regressed and drawdown drift was too high. "
            "Its closeout explicitly required maturity cliff relief, covenant "
            "risk reduction, parsed refinancing terms, or forward replacement "
            "rows for any valid retry."
        ),
        "exp-20260616-004": (
            "Rejected interest-burden relief; valid retry required materially "
            "different PIT financing data such as borrow cost or debt maturity/"
            "refinancing terms. This run uses filed maturity schedules and "
            "credit capacity, not interest expense."
        ),
        "exp-20260615-001": (
            "Rejected generic deleveraging/liquidity text. This run uses "
            "structured Companyfacts maturity values, not phrase spans."
        ),
        "exp-20260616-025": (
            "Rejected operating lease burden relief. This run tests financing "
            "maturity-wall relief, not lease fixed-cost burden."
        ),
        "novelty_gate": (
            "Reservation override recorded the new evidence axis: raw SEC "
            "Companyfacts filed debt maturity ladder and line-of-credit "
            "capacity fields; not gross debt/revenue, interest burden, lease "
            "burden, or generic deleveraging text."
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
        "exp_20260619_005_debt_maturity_cliff_relief.py"
    ),
}

_RAW_INDEX_CACHE: tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return base._round(value, digits)


def _load_standard_baseline_metrics() -> dict[str, dict[str, Any]]:
    payload = json.loads(BASELINE_RESULT_JSON.read_text(encoding="utf-8"))
    return {str(row["label"]): dict(row) for row in payload["windows"]}


def _metric_digits(key: str) -> int:
    if key == "total_pnl":
        return 2
    if key in {"expected_value_score", "max_drawdown_pct", "strategy_total_return_pct"}:
        return 4
    if key in {"sharpe_daily", "win_rate", "survival_rate"}:
        return 4
    return 6


def _normalize_payload_to_standard_baseline(payload: dict[str, Any]) -> dict[str, Any]:
    standard = _load_standard_baseline_metrics()
    dynamic_before = {
        label: dict(metrics) for label, metrics in payload["before_metrics"].items()
    }
    dynamic_after = {
        label: dict(metrics) for label, metrics in payload["after_metrics"].items()
    }
    normalized_before: dict[str, dict[str, Any]] = {}
    normalized_after: dict[str, dict[str, Any]] = {}
    standard_metric_keys = (
        "expected_value_score",
        "sharpe_daily",
        "total_pnl",
        "max_drawdown_pct",
        "win_rate",
        "trade_count",
        "signals_generated",
        "signals_survived",
        "survival_rate",
    )
    for label in base.framework.WINDOWS:
        before = dict(dynamic_before[label])
        after = dict(dynamic_after[label])
        baseline = standard[label]
        delta = payload["delta_metrics"]["by_window"][label]
        for key in standard_metric_keys:
            if key in baseline:
                before[key] = baseline[key]
                change = delta.get(key, 0.0)
                if isinstance(baseline[key], (int, float)) and isinstance(change, (int, float)):
                    if isinstance(baseline[key], int) and key in {
                        "trade_count",
                        "signals_generated",
                        "signals_survived",
                    }:
                        after[key] = int(baseline[key] + change)
                    else:
                        after[key] = round(float(baseline[key]) + float(change), _metric_digits(key))
                else:
                    after[key] = baseline[key]
        before["baseline_metric_source"] = _repo_rel(BASELINE_RESULT_JSON)
        after["baseline_metric_source"] = _repo_rel(BASELINE_RESULT_JSON)
        normalized_before[label] = before
        normalized_after[label] = after

    aggregate = payload["delta_metrics"]["aggregate"]
    baseline_ev = round(
        sum(float(normalized_before[label]["expected_value_score"]) for label in base.framework.WINDOWS),
        4,
    )
    after_ev = round(
        sum(float(normalized_after[label]["expected_value_score"]) for label in base.framework.WINDOWS),
        4,
    )
    baseline_pnl = round(
        sum(float(normalized_before[label]["total_pnl"]) for label in base.framework.WINDOWS),
        2,
    )
    after_pnl = round(
        sum(float(normalized_after[label]["total_pnl"]) for label in base.framework.WINDOWS),
        2,
    )
    ev_delta = round(after_ev - baseline_ev, 4)
    pnl_delta = round(after_pnl - baseline_pnl, 2)
    aggregate.update(
        {
            "baseline_expected_value_score_sum": baseline_ev,
            "after_expected_value_score_sum": after_ev,
            "expected_value_score_delta_sum": ev_delta,
            "expected_value_score_delta_pct": round(ev_delta / baseline_ev, 6)
            if baseline_ev
            else None,
            "baseline_total_pnl_sum": baseline_pnl,
            "after_total_pnl_sum": after_pnl,
            "total_pnl_delta_sum": pnl_delta,
            "total_pnl_delta_pct": round(pnl_delta / baseline_pnl, 6)
            if baseline_pnl
            else None,
        }
    )
    payload["before_metrics"] = normalized_before
    payload["after_metrics"] = normalized_after
    payload["dynamic_framework_before_metrics"] = dynamic_before
    payload["dynamic_framework_after_metrics"] = dynamic_after
    payload["baseline_normalization"] = {
        "status": "applied",
        "reason": (
            "Official before/after metrics are anchored to docs/backtesting.md "
            "standard_windows_20260604 before metrics plus the replay overlay "
            "deltas. Dynamic framework before metrics are retained as a "
            "diagnostic guard against baseline drift."
        ),
        "standard_baseline_file": _repo_rel(BASELINE_RESULT_JSON),
        "dynamic_baseline_ev_sum": round(
            sum(float(row["expected_value_score"]) for row in dynamic_before.values()), 4
        ),
        "standard_baseline_ev_sum": baseline_ev,
        "dynamic_baseline_pnl_sum": round(
            sum(float(row["total_pnl"]) for row in dynamic_before.values()), 2
        ),
        "standard_baseline_pnl_sum": baseline_pnl,
    }
    payload["expected_value_score_delta"] = ev_delta
    payload["total_pnl_delta"] = pnl_delta
    payload["gate4"]["aggregate_ev_delta"] = ev_delta
    payload["gate4"]["aggregate_pnl_delta"] = pnl_delta
    payload["gate4"]["minimum_core_survival_rate"] = min(
        float(row["survival_rate"]) for row in normalized_before.values()
    )
    return payload


def _raw_instant_facts(usgaap: dict[str, Any], tags: tuple[str, ...]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for tag in tags:
        tag_payload = usgaap.get(tag) or {}
        for raw in tag_payload.get("units", {}).get("USD", []):
            start = str(raw.get("start") or "")[:10]
            end = str(raw.get("end") or "")[:10]
            filed = str(raw.get("filed") or "")[:10]
            value = rd._float_or_none(raw.get("val"))
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
    tag_counts: Counter[str] = Counter()
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
        next12_facts = _raw_instant_facts(usgaap, NEXT_TWELVE_TAGS)
        year2_facts = _raw_instant_facts(usgaap, YEAR_TWO_TAGS)
        other_facts = _raw_instant_facts(usgaap, OTHER_MATURITY_TAGS)
        capacity_facts = _raw_instant_facts(usgaap, CAPACITY_TAGS)
        revenue_facts = rd._raw_annual_facts(usgaap, REVENUE_TAGS)
        if not next12_facts:
            stats["tickers_missing_next12_maturity"] += 1
            continue
        if not year2_facts:
            stats["tickers_missing_year2_maturity"] += 1
            continue
        if not revenue_facts:
            stats["tickers_missing_raw_annual_revenue"] += 1
            continue
        for fact in next12_facts + year2_facts + other_facts + capacity_facts:
            tag_counts[fact["tag"]] += 1
        index[ticker] = {
            "next12": next12_facts,
            "year2": year2_facts,
            "other_maturities": other_facts,
            "capacity": capacity_facts,
            "revenue": revenue_facts,
        }
        stats["tickers_with_maturity_ladder_and_revenue"] += 1
        stats["raw_next12_maturity_fact_count"] += len(next12_facts)
        stats["raw_year2_maturity_fact_count"] += len(year2_facts)
        stats["raw_other_maturity_fact_count"] += len(other_facts)
        stats["raw_capacity_fact_count"] += len(capacity_facts)
        stats["raw_annual_revenue_fact_count"] += len(revenue_facts)

    summary = {
        "raw_companyfacts_cache": _repo_rel(RAW_COMPANYFACTS_CACHE),
        "next_twelve_tags": list(NEXT_TWELVE_TAGS),
        "year_two_tags": list(YEAR_TWO_TAGS),
        "other_maturity_tags": list(OTHER_MATURITY_TAGS),
        "capacity_tags": list(CAPACITY_TAGS),
        "revenue_tags": list(REVENUE_TAGS),
        "raw_tag_fact_counts": dict(tag_counts),
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
        "field_source": "raw_sec_companyfacts_cache_debt_maturity_ladder",
    }


def _latest_by_end(
    facts: list[dict[str, Any]],
    *,
    asof: str,
    end: str | None = None,
    before_end: str | None = None,
) -> dict[str, Any] | None:
    return rd._latest_period_fact(facts, asof=asof, end=end, before_end=before_end)


def _latest_capacity(
    facts: list[dict[str, Any]],
    *,
    asof: str,
    preferred_end: str,
) -> dict[str, Any] | None:
    same_end = _latest_by_end(facts, asof=asof, end=preferred_end)
    if same_end is not None:
        return same_end
    return _latest_by_end(facts, asof=asof)


def _maturity_observation(
    ticker: str,
    asof: str,
    facts: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    current_next12 = _latest_by_end(facts["next12"], asof=asof)
    if current_next12 is None:
        return None
    if base._days_between(asof, current_next12["filed"]) > MAX_SCHEDULE_FACT_AGE_DAYS:
        return None
    prior_year2 = _latest_by_end(
        facts["year2"], asof=asof, before_end=current_next12["end"]
    )
    if prior_year2 is None:
        return None
    if base._days_between(asof, prior_year2["filed"]) > MAX_SCHEDULE_FACT_AGE_DAYS + 370:
        return None
    current_revenue = _latest_by_end(
        facts["revenue"], asof=asof, end=current_next12["end"]
    )
    prior_revenue = _latest_by_end(facts["revenue"], asof=asof, end=prior_year2["end"])
    if current_revenue is None or prior_revenue is None:
        return None
    if base._days_between(asof, current_revenue["filed"]) > MAX_ANNUAL_FACT_AGE_DAYS:
        return None

    current_wall = abs(float(current_next12["value"]))
    prior_expected_wall = abs(float(prior_year2["value"]))
    current_revenue_value = float(current_revenue["value"])
    prior_revenue_value = float(prior_revenue["value"])
    if (
        current_revenue_value < MIN_CURRENT_REVENUE
        or prior_revenue_value <= 0.0
        or prior_expected_wall < MIN_PRIOR_NEXT_PERIOD_MATURITY
    ):
        return None

    current_wall_to_revenue = current_wall / current_revenue_value
    prior_wall_to_revenue = prior_expected_wall / prior_revenue_value
    wall_ratio_relief = prior_wall_to_revenue - current_wall_to_revenue
    wall_decline_pct = (prior_expected_wall - current_wall) / prior_expected_wall
    revenue_growth = (current_revenue_value - prior_revenue_value) / abs(prior_revenue_value)
    if prior_wall_to_revenue < MIN_PRIOR_WALL_TO_REVENUE:
        return None
    if current_wall_to_revenue > MAX_CURRENT_WALL_TO_REVENUE:
        return None
    if wall_ratio_relief < MIN_WALL_RATIO_RELIEF:
        return None
    if wall_decline_pct < MIN_WALL_DECLINE_PCT:
        return None
    if revenue_growth < MIN_REVENUE_GROWTH:
        return None

    capacity = _latest_capacity(
        facts["capacity"], asof=asof, preferred_end=current_next12["end"]
    )
    capacity_value = None
    capacity_coverage = None
    capacity_tag = None
    capacity_filed = None
    if capacity is not None:
        capacity_value = abs(float(capacity["value"]))
        capacity_tag = str(capacity["tag"])
        capacity_filed = str(capacity["filed"])
        if current_wall > 0.0:
            capacity_coverage = capacity_value / current_wall
    covered_by_capacity = (
        capacity_coverage is not None and capacity_coverage >= MIN_CAPACITY_COVERAGE
    )
    if current_wall_to_revenue > MAX_UNCOVERED_CURRENT_WALL_TO_REVENUE and not covered_by_capacity:
        return None

    return {
        "ticker": ticker,
        "current_schedule_end": current_next12["end"],
        "prior_schedule_end": prior_year2["end"],
        "current_next12_filed": current_next12["filed"],
        "prior_year2_filed": prior_year2["filed"],
        "current_revenue_filed": current_revenue["filed"],
        "prior_revenue_filed": prior_revenue["filed"],
        "current_next12_tag": current_next12["tag"],
        "prior_year2_tag": prior_year2["tag"],
        "capacity_tag": capacity_tag,
        "capacity_filed": capacity_filed,
        "current_next12_maturity": _round(current_wall, 2),
        "prior_year2_expected_maturity": _round(prior_expected_wall, 2),
        "capacity_value": _round(capacity_value, 2),
        "capacity_coverage": _round(capacity_coverage, 6),
        "covered_by_capacity": covered_by_capacity,
        "current_revenue_value": _round(current_revenue_value, 2),
        "prior_revenue_value": _round(prior_revenue_value, 2),
        "current_wall_to_revenue": _round(current_wall_to_revenue, 6),
        "prior_wall_to_revenue": _round(prior_wall_to_revenue, 6),
        "wall_ratio_relief": _round(wall_ratio_relief, 6),
        "wall_decline_pct": _round(wall_decline_pct, 6),
        "revenue_growth": _round(revenue_growth, 6),
        "schedule_fact_age_days": base._days_between(asof, current_next12["filed"]),
        "known_at": "raw_companyfacts_debt_maturity_schedule_filed_and_signal_close_before_next_open_paper_entry",
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
            quality = _maturity_observation(ticker, signal_date, quality_index[ticker])
            if quality is None:
                scan["failed_debt_maturity_gate"] += 1
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
            capacity_boost = 0.0
            if quality["capacity_coverage"] is not None:
                capacity_boost = min(float(quality["capacity_coverage"]), 3.0) / 3.0
            score = (
                2.00 * min(float(quality["wall_ratio_relief"] or 0.0), 0.20)
                + 0.60 * min(float(quality["wall_decline_pct"] or 0.0), 0.90)
                + 0.18 * max(min(float(quality["revenue_growth"] or 0.0), 1.0), -0.05)
                + 0.18 * capacity_boost
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
                    "source": "RAW_SEC_DEBT_MATURITY_CLIFF_RELIEF_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": quality["known_at"],
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_companyfacts": True,
                    "uses_raw_sec_companyfacts_cache": True,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    **{f"maturity_{key}": value for key, value in quality.items()},
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
            -float(row["maturity_wall_ratio_relief"] or 0.0),
            -float(row["maturity_wall_decline_pct"] or 0.0),
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
        "min_prior_next_period_maturity": MIN_PRIOR_NEXT_PERIOD_MATURITY,
        "min_prior_wall_to_revenue": MIN_PRIOR_WALL_TO_REVENUE,
        "max_current_wall_to_revenue": MAX_CURRENT_WALL_TO_REVENUE,
        "max_uncovered_current_wall_to_revenue": MAX_UNCOVERED_CURRENT_WALL_TO_REVENUE,
        "min_wall_ratio_relief": MIN_WALL_RATIO_RELIEF,
        "min_wall_decline_pct": MIN_WALL_DECLINE_PCT,
        "min_revenue_growth": MIN_REVENUE_GROWTH,
        "min_capacity_coverage": MIN_CAPACITY_COVERAGE,
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
        "positive_replay_lead_not_promoted_debt_maturity_cliff_relief"
        if gate["passed"]
        else "rejected_debt_maturity_cliff_relief_candidate_pool"
    )
    return gate


def _configure_base() -> None:
    q.__file__ = __file__
    for name in (
        "EXPERIMENT_ID",
        "STEM",
        "TRIAL_FAMILY",
        "TRIAL_VARIANT_ID",
        "CHANGED_VARIABLE",
        "RULE_VERSION",
        "OWNER",
        "OUT_DIR",
        "OUT_JSON",
        "LOG_JSON",
        "TICKET_JSON",
        "CARD_MD",
        "MANIFEST_JSON",
        "EXPERIMENT_LOG",
        "REGISTRY_JSON",
        "BASE_NOTIONAL_USD",
        "HOLD_DAYS",
        "MAX_PAPER_TRADES_PER_DAY",
        "SAME_TICKER_COOLDOWN_DAYS",
        "FY_DURATION_MIN",
        "FY_DURATION_MAX",
        "MAX_ANNUAL_FACT_AGE_DAYS",
        "PREDICTION",
        "PRODUCTION_IMPACT",
        "PRE_RUN_QUESTIONS",
    ):
        setattr(q, name, globals()[name])
    q._build_quality_index = _build_quality_index
    q._candidate_rows_for_window = _candidate_rows_for_window
    q._gate4 = _gate4
    q._configure_base()


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload = _normalize_payload_to_standard_baseline(payload)
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    if gate4["passed"]:
        interpretation = (
            "The debt maturity cliff relief source cleared the numeric "
            "three-window replay screen, but remains only a replay lead because "
            "no shared daily/backtest helper was promoted."
        )
    else:
        interpretation = (
            "The debt maturity cliff relief source did not clear Gate 4 "
            f"(failed: {', '.join(gate4['failed_reasons']) or 'none'}). It is "
            "not retained or promoted."
        )

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
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_sec_companyfacts_debt_maturity_candidate_pool",
            "new_evidence_type": "raw_sec_companyfacts_filed_debt_maturity_ladder_and_credit_capacity",
            "nearby_prior_experiments": [
                "exp-20260616-029",
                "exp-20260616-004",
                "exp-20260615-001",
                "exp-20260616-025",
                "exp-20260619-005_novelty_override",
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
            "min_prior_next_period_maturity": MIN_PRIOR_NEXT_PERIOD_MATURITY,
            "min_prior_wall_to_revenue": MIN_PRIOR_WALL_TO_REVENUE,
            "max_current_wall_to_revenue": MAX_CURRENT_WALL_TO_REVENUE,
            "max_uncovered_current_wall_to_revenue": MAX_UNCOVERED_CURRENT_WALL_TO_REVENUE,
            "min_wall_ratio_relief": MIN_WALL_RATIO_RELIEF,
            "min_wall_decline_pct": MIN_WALL_DECLINE_PCT,
            "min_revenue_growth": MIN_REVENUE_GROWTH,
            "min_capacity_coverage": MIN_CAPACITY_COVERAGE,
            "next_twelve_tags": list(NEXT_TWELVE_TAGS),
            "year_two_tags": list(YEAR_TWO_TAGS),
            "other_maturity_tags": list(OTHER_MATURITY_TAGS),
            "capacity_tags": list(CAPACITY_TAGS),
            "revenue_tags": list(REVENUE_TAGS),
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Debt maturity schedule, annual revenue, and optional line-of-credit "
        "capacity are read from raw SEC Companyfacts tags and known only by "
        "filed date (<= signal date). The rule compares current filed next-"
        "twelve-month principal maturities to the prior filed year-two "
        "maturity bucket, normalized by annual revenue, and requires a fixed "
        "maturity-wall relief threshold. Large remaining near-term walls must "
        "be covered by filed credit capacity. Price confirmation uses only "
        "signal-date OHLCV. Paper entry is the next available open with "
        "existing entry slippage; exit is the close 10 trading days after the "
        "signal with target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["backtest_protocol"]["companyfacts_source"] = _repo_rel(RAW_COMPANYFACTS_CACHE)
    payload["gate2"]["runtime_fields"] = [
        "raw SEC companyfacts next-12-month debt maturity schedule",
        "raw SEC companyfacts prior filed year-two debt maturity schedule",
        "raw SEC companyfacts optional line-of-credit capacity facts",
        "raw SEC companyfacts annual revenue facts",
        "raw SEC companyfacts filed date and period end",
        "warehouse ticker_universe CIK mapping",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A retry needs materially different PIT financing evidence, such as "
        "parsed refinancing transaction terms, covenant headroom, credit-rating "
        "changes, borrow-cost/availability, or closed forward replacement-value "
        "rows. Do not sweep maturity buckets, wall-relief thresholds, capacity "
        "coverage, annual fact freshness, price guards, top-N, hold, cooldown, "
        "or notional on these frozen windows."
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
            "Do not retry by sweeping debt maturity tags, wall-relief ratios, "
            "wall-decline thresholds, credit-capacity coverage, revenue floor, "
            "annual fact freshness, RS/close/volume/vol guards, top-N, hold "
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
            f"# {EXPERIMENT_ID} Debt Maturity Cliff Relief",
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
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_compression_comparator": base.COMPRESSION_COMPARATOR,
        "accepted_distribution_comparator": base.DISTRIBUTION_COMPARATOR,
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
                "eligible_quality_tickers": payload["context_scan_by_window"][label].get(
                    "eligible_quality_tickers"
                ),
                "raw_candidate_count": payload["raw_candidate_counts"][label],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in base.framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "negative_reflection": payload["post_run_reflection"]["why_result_happened"],
        "post_run_reflection": payload["post_run_reflection"],
        "pre_run_questions": PRE_RUN_QUESTIONS,
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
    print(json.dumps(base.framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
