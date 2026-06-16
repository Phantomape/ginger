"""exp-20260616-029: principal debt burden relief candidate scout.

Replay-only alpha search. The single decision hypothesis is a PIT free SEC
Companyfacts candidate source: production-universe names whose annual gross
debt burden is falling versus revenue, while revenue is not contracting and
liquid SPY-relative leadership confirms demand. This tests principal balance
sheet repair from structured debt facts, distinct from recent debt-repair text,
interest-cost, lease, working-capital, SBC, FINRA, Form 4, and generic cost
experiments.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive replay is
only a lead until a shared historical/daily helper reproduces it.
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

import exp_20260614_020_accruals_cash_conversion_quality as base
import exp_20260616_003_raw_sec_rd_intensity_candidate_pool as rd


EXPERIMENT_ID = "exp-20260616-029"
STEM = "principal_debt_burden_relief"
TRIAL_FAMILY = "principal_debt_burden_relief_candidate_pool"
TRIAL_VARIANT_ID = "principal_debt_burden_relief_top1_next_open_10d_v1"
CHANGED_VARIABLE = "raw_sec_companyfacts_principal_debt_burden_relief_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
RAW_COMPANYFACTS_CACHE = REPO_ROOT / "data" / "cache" / "sec" / "companyfacts"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260616_029_{STEM}.json"
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
MIN_CURRENT_DEBT = 50_000_000.0
MIN_CURRENT_DEBT_TO_REVENUE = 0.03
MAX_CURRENT_DEBT_TO_REVENUE = 1.50
MIN_DEBT_RATIO_IMPROVEMENT = 0.03
MIN_REVENUE_GROWTH = 0.0
MAX_DEBT_GROWTH_MINUS_REVENUE_GROWTH = -0.08

DEBT_TOTAL_TAGS = (
    "LongTermDebt",
    "LongTermDebtAndFinanceLeaseObligations",
    "LongTermDebtAndFinanceLeaseObligationsIncludingCurrentMaturities",
)
DEBT_CURRENT_TAGS = (
    "LongTermDebtCurrent",
    "LongTermDebtAndFinanceLeaseObligationsCurrent",
    "DebtCurrent",
    "CurrentPortionOfLongTermDebt",
    "ShortTermBorrowings",
    "ShortTermDebt",
)
DEBT_NONCURRENT_TAGS = (
    "LongTermDebtNoncurrent",
    "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
)
REVENUE_TAGS = rd.REVENUE_TAGS

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.30,
    "expected_pnl_delta": 4500.0,
    "main_failure_modes": [
        "companyfacts_debt_tag_semantics_noisy",
        "old_window_coverage_gap",
        "accepted_distribution_comparator_not_beaten",
        "target_concentration_failed",
        "window_regression",
    ],
    "confidence_reason": (
        "Debt-repair text improved all three windows but was too weak, and "
        "interest-burden relief was strong in late/mid but lacked old-window "
        "coverage. A structured gross debt/revenue improvement field is distinct "
        "from text and interest-cost relief, but Companyfacts quality surfaces "
        "are saturated and debt tag semantics are noisy."
    ),
    "recorded_at": "2026-06-16T23:12:25+00:00",
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
            "missing raw SEC annual debt or revenue facts; missing matching "
            "fiscal-year ends; stale facts; missing CIK mapping; missing OHLCV; "
            "missing next open; or missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same raw "
        "SEC debt and revenue filed-date PIT mapping, principal debt-burden "
        "relief gate, liquid SPY-relative confirmation, cooldown, "
        "next-open paper entry, 10-day exit, costs, and concentration controls "
        "in both historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: raw SEC Companyfacts principal debt burden relief "
        "(gross debt/revenue falling year over year while revenue is not "
        "contracting), paired with liquid SPY-relative leadership, may identify "
        "balance-sheet repair candidates with broader three-window coverage than "
        "interest-burden text/cost relief."
    ),
    "2_history_check": {
        "exp-20260528-017": (
            "Accepted low-liability support inside the older Companyfacts+RS "
            "stack. This run is not a generic liabilities/assets scalar; it "
            "tests a standalone candidate source using explicit gross debt/"
            "revenue burden improvement."
        ),
        "exp-20260615-001": (
            "Rejected SEC deleveraging/liquidity repair text after it improved "
            "all three windows but failed the accepted SEC RS20 comparator. This "
            "run uses structured Companyfacts debt amounts rather than phrase "
            "spans."
        ),
        "exp-20260616-004": (
            "Raw interest-burden relief was positive in late/mid but had no "
            "old_thin coverage and failed concentration/distribution gates. This "
            "run tests principal debt balance reduction rather than interest "
            "expense."
        ),
        "exp-20260616-025": (
            "Rejected operating lease burden relief. This run excludes operating "
            "lease liability and tests principal gross debt burden, not a lease "
            "fixed-cost field."
        ),
        "exp-20260616-021/023/024": (
            "Rejected receivables/allowance and FINRA borrow-pressure variants. "
            "This run does not retune working-capital, borrow, FTD, or short-"
            "interest fields."
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
        "exp_20260616_029_principal_debt_burden_relief.py"
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
            end = str(raw.get("end") or "")[:10]
            filed = str(raw.get("filed") or "")[:10]
            value = rd._float_or_none(raw.get("val"))
            if not end or not filed or value is None:
                continue
            start = str(raw.get("start") or "")[:10]
            if start and start != end:
                continue
            facts.append(
                {
                    "filed": filed,
                    "start": start,
                    "end": end,
                    "value": value,
                    "tag": tag,
                    "form": str(raw.get("form") or ""),
                    "fy": raw.get("fy"),
                    "fp": raw.get("fp"),
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
    debt_total_tag_counts: Counter[str] = Counter()
    debt_current_tag_counts: Counter[str] = Counter()
    debt_noncurrent_tag_counts: Counter[str] = Counter()
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
        debt_total_facts = _raw_instant_facts(usgaap, DEBT_TOTAL_TAGS)
        debt_current_facts = _raw_instant_facts(usgaap, DEBT_CURRENT_TAGS)
        debt_noncurrent_facts = _raw_instant_facts(usgaap, DEBT_NONCURRENT_TAGS)
        revenue_facts = rd._raw_annual_facts(usgaap, REVENUE_TAGS)
        if not debt_total_facts and not (debt_current_facts and debt_noncurrent_facts):
            stats["tickers_missing_raw_debt_facts"] += 1
            continue
        if not revenue_facts:
            stats["tickers_missing_raw_annual_revenue"] += 1
            continue
        for fact in debt_total_facts:
            debt_total_tag_counts[fact["tag"]] += 1
        for fact in debt_current_facts:
            debt_current_tag_counts[fact["tag"]] += 1
        for fact in debt_noncurrent_facts:
            debt_noncurrent_tag_counts[fact["tag"]] += 1
        index[ticker] = {
            "debt_total": debt_total_facts,
            "debt_current": debt_current_facts,
            "debt_noncurrent": debt_noncurrent_facts,
            "revenue": revenue_facts,
        }
        stats["tickers_with_raw_debt_and_revenue"] += 1
        stats["raw_debt_total_fact_count"] += len(debt_total_facts)
        stats["raw_debt_current_fact_count"] += len(debt_current_facts)
        stats["raw_debt_noncurrent_fact_count"] += len(debt_noncurrent_facts)
        stats["raw_annual_revenue_fact_count"] += len(revenue_facts)

    summary = {
        "raw_companyfacts_cache": _repo_rel(RAW_COMPANYFACTS_CACHE),
        "debt_total_tags": list(DEBT_TOTAL_TAGS),
        "debt_current_tags": list(DEBT_CURRENT_TAGS),
        "debt_noncurrent_tags": list(DEBT_NONCURRENT_TAGS),
        "revenue_tags": list(REVENUE_TAGS),
        "debt_total_tag_fact_counts": dict(debt_total_tag_counts),
        "debt_current_tag_fact_counts": dict(debt_current_tag_counts),
        "debt_noncurrent_tag_fact_counts": dict(debt_noncurrent_tag_counts),
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


def _debt_value_for_end(
    facts: dict[str, list[dict[str, Any]]],
    *,
    asof: str,
    end: str,
) -> dict[str, Any] | None:
    current = rd._latest_period_fact(facts["debt_current"], asof=asof, end=end)
    noncurrent = rd._latest_period_fact(facts["debt_noncurrent"], asof=asof, end=end)
    if current is not None and noncurrent is not None:
        current_value = abs(float(current["value"]))
        noncurrent_value = abs(float(noncurrent["value"]))
        return {
            "value": current_value + noncurrent_value,
            "method": "current_plus_noncurrent",
            "tags": f"{current['tag']}+{noncurrent['tag']}",
            "filed": max(str(current["filed"]), str(noncurrent["filed"])),
            "current_value": current_value,
            "noncurrent_value": noncurrent_value,
            "total_tag_value": None,
        }

    total = rd._latest_period_fact(facts["debt_total"], asof=asof, end=end)
    if total is None:
        return None
    total_value = abs(float(total["value"]))
    return {
        "value": total_value,
        "method": "total_tag",
        "tags": str(total["tag"]),
        "filed": str(total["filed"]),
        "current_value": None,
        "noncurrent_value": None,
        "total_tag_value": total_value,
    }


def _debt_observation(
    ticker: str,
    asof: str,
    facts: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    current_revenue = rd._latest_period_fact(facts["revenue"], asof=asof)
    if current_revenue is None:
        return None
    if base._days_between(asof, current_revenue["filed"]) > MAX_ANNUAL_FACT_AGE_DAYS:
        return None
    current_debt = _debt_value_for_end(facts, asof=asof, end=current_revenue["end"])
    if current_debt is None:
        return None
    if base._days_between(asof, current_debt["filed"]) > MAX_ANNUAL_FACT_AGE_DAYS:
        return None

    prior_revenue = rd._latest_period_fact(
        facts["revenue"], asof=asof, before_end=current_revenue["end"]
    )
    if prior_revenue is None:
        return None
    prior_debt = _debt_value_for_end(facts, asof=asof, end=prior_revenue["end"])
    if prior_debt is None:
        return None

    current_revenue_value = float(current_revenue["value"])
    prior_revenue_value = float(prior_revenue["value"])
    current_debt_value = abs(float(current_debt["value"]))
    prior_debt_value = abs(float(prior_debt["value"]))
    if (
        current_revenue_value < MIN_CURRENT_REVENUE
        or current_debt_value < MIN_CURRENT_DEBT
        or prior_revenue_value <= 0.0
        or prior_debt_value <= 0.0
    ):
        return None

    current_ratio = current_debt_value / current_revenue_value
    prior_ratio = prior_debt_value / prior_revenue_value
    ratio_improvement = prior_ratio - current_ratio
    revenue_growth = (current_revenue_value - prior_revenue_value) / abs(prior_revenue_value)
    debt_growth = (current_debt_value - prior_debt_value) / abs(prior_debt_value)
    growth_spread = debt_growth - revenue_growth
    if not (MIN_CURRENT_DEBT_TO_REVENUE <= current_ratio <= MAX_CURRENT_DEBT_TO_REVENUE):
        return None
    if ratio_improvement < MIN_DEBT_RATIO_IMPROVEMENT:
        return None
    if revenue_growth < MIN_REVENUE_GROWTH:
        return None
    if growth_spread > MAX_DEBT_GROWTH_MINUS_REVENUE_GROWTH:
        return None

    return {
        "ticker": ticker,
        "current_period_end": current_revenue["end"],
        "prior_period_end": prior_revenue["end"],
        "current_debt_filed": current_debt["filed"],
        "prior_debt_filed": prior_debt["filed"],
        "current_revenue_filed": current_revenue["filed"],
        "prior_revenue_filed": prior_revenue["filed"],
        "current_debt_method": current_debt["method"],
        "prior_debt_method": prior_debt["method"],
        "current_debt_tags": current_debt["tags"],
        "prior_debt_tags": prior_debt["tags"],
        "current_debt": _round(current_debt_value, 2),
        "prior_debt": _round(prior_debt_value, 2),
        "current_debt_current_value": _round(current_debt["current_value"], 2),
        "prior_debt_current_value": _round(prior_debt["current_value"], 2),
        "current_debt_noncurrent_value": _round(current_debt["noncurrent_value"], 2),
        "prior_debt_noncurrent_value": _round(prior_debt["noncurrent_value"], 2),
        "current_debt_total_tag_value": _round(current_debt["total_tag_value"], 2),
        "prior_debt_total_tag_value": _round(prior_debt["total_tag_value"], 2),
        "current_revenue_value": _round(current_revenue_value, 2),
        "prior_revenue_value": _round(prior_revenue_value, 2),
        "current_debt_to_revenue": _round(current_ratio, 6),
        "prior_debt_to_revenue": _round(prior_ratio, 6),
        "debt_ratio_improvement": _round(ratio_improvement, 6),
        "debt_growth": _round(debt_growth, 6),
        "revenue_growth": _round(revenue_growth, 6),
        "debt_growth_minus_revenue_growth": _round(growth_spread, 6),
        "fact_age_days": base._days_between(asof, current_debt["filed"]),
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
            observation = _debt_observation(ticker, signal_date, quality_index[ticker])
            if observation is None:
                scan["failed_principal_debt_burden_gate"] += 1
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
            ratio_improvement = float(observation["debt_ratio_improvement"] or 0.0)
            revenue_growth = float(observation["revenue_growth"] or 0.0)
            debt_growth_spread = float(observation["debt_growth_minus_revenue_growth"] or 0.0)
            current_ratio = float(observation["current_debt_to_revenue"] or 0.0)
            score = (
                1.5 * min(ratio_improvement, 0.45)
                + 0.22 * max(min(revenue_growth, 0.60), 0.0)
                + 0.12 * max(min(-debt_growth_spread, 0.50), -0.25)
                + 0.03 * max(min(0.50 - current_ratio, 0.40), -0.50)
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
                    "source": "PRINCIPAL_DEBT_BURDEN_RELIEF_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_companyfacts": True,
                    "uses_raw_sec_companyfacts_cache": True,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    **{f"debt_{key}": value for key, value in observation.items()},
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
            -float(row["debt_debt_ratio_improvement"] or 0.0),
            float(row["debt_debt_growth_minus_revenue_growth"] or 0.0),
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
        "min_current_debt": MIN_CURRENT_DEBT,
        "min_current_debt_to_revenue": MIN_CURRENT_DEBT_TO_REVENUE,
        "max_current_debt_to_revenue": MAX_CURRENT_DEBT_TO_REVENUE,
        "min_debt_ratio_improvement": MIN_DEBT_RATIO_IMPROVEMENT,
        "min_revenue_growth": MIN_REVENUE_GROWTH,
        "max_debt_growth_minus_revenue_growth": MAX_DEBT_GROWTH_MINUS_REVENUE_GROWTH,
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
        "positive_replay_lead_not_promoted_principal_debt_burden_relief"
        if gate["passed"]
        else "rejected_principal_debt_burden_relief_candidate_pool"
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
            "The principal debt burden relief source cleared the numeric "
            "three-window replay screen, but remains only a replay lead because "
            "no shared daily/backtest helper was promoted."
        )
    else:
        interpretation = (
            "The principal debt burden relief source did not clear Gate 4 "
            f"(failed: {', '.join(gate4['failed_reasons']) or 'none'}). Do not "
            "promote or tune this fixed debt-burden bundle on the same frozen "
            "windows."
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
            "mechanism_family": "production_visible_free_sec_companyfacts_principal_debt_quality_candidate_pool",
            "new_evidence_type": "raw_sec_companyfacts_principal_debt_pit_field",
            "nearby_prior_experiments": [
                "exp-20260528-017",
                "exp-20260615-001",
                "exp-20260616-004",
                "exp-20260616-025",
                "exp-20260616-021",
                "exp-20260616-023",
                "exp-20260616-024",
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
        "base_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "fy_duration_min": FY_DURATION_MIN,
        "fy_duration_max": FY_DURATION_MAX,
        "max_annual_fact_age_days": MAX_ANNUAL_FACT_AGE_DAYS,
        "min_current_revenue": MIN_CURRENT_REVENUE,
        "min_current_debt": MIN_CURRENT_DEBT,
        "min_current_debt_to_revenue": MIN_CURRENT_DEBT_TO_REVENUE,
        "max_current_debt_to_revenue": MAX_CURRENT_DEBT_TO_REVENUE,
        "min_debt_ratio_improvement": MIN_DEBT_RATIO_IMPROVEMENT,
        "min_revenue_growth": MIN_REVENUE_GROWTH,
        "max_debt_growth_minus_revenue_growth": MAX_DEBT_GROWTH_MINUS_REVENUE_GROWTH,
        "debt_total_tags": list(DEBT_TOTAL_TAGS),
        "debt_current_tags": list(DEBT_CURRENT_TAGS),
        "debt_noncurrent_tags": list(DEBT_NONCURRENT_TAGS),
        "revenue_tags": list(REVENUE_TAGS),
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
        "Gross debt is read from raw SEC Companyfacts balance-sheet INSTANT "
        "facts and matched to annual revenue ending the same fiscal-year date; "
        "all fields are known only by filed date <= signal date. The rule "
        "prefers current-plus-noncurrent debt when both same-period facts exist "
        "and otherwise uses a total debt tag. It requires debt/revenue burden "
        "to fall year over year while revenue is non-declining and debt grows "
        "at least 8pp slower than revenue. Price confirmation uses only "
        "signal-date OHLCV. Paper entry is the next available open with "
        "existing entry slippage; exit is the close 10 trading days after the "
        "signal with target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["backtest_protocol"]["companyfacts_source"] = _repo_rel(RAW_COMPANYFACTS_CACHE)
    payload["gate2"]["runtime_fields"] = [
        "raw SEC companyfacts gross debt instant facts",
        "raw SEC companyfacts annual revenue facts",
        "raw SEC companyfacts filed date and period end",
        "warehouse ticker_universe CIK mapping",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A retry needs materially different PIT debt evidence, such as maturity "
        "cliff relief, covenant-risk reduction, parsed refinancing terms, or "
        "closed forward replacement-value rows. Do not sweep debt tags, debt/"
        "revenue thresholds, revenue-growth floor, annual fact freshness, price "
        "guards, top-N, hold, cooldown, or notional on these frozen windows."
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
            "Do not retry by sweeping the debt tag list, debt/revenue "
            "improvement threshold, current debt/revenue bounds, revenue growth "
            "floor, annual fact freshness, RS/close/volume/vol guards, top-N, "
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
            f"# {EXPERIMENT_ID} Principal Debt Burden Relief",
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
