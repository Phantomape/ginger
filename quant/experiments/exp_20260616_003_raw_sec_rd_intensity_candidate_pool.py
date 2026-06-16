"""exp-20260616-003: raw SEC R&D intensity acceleration candidate scout.

Replay-only alpha search. The single decision hypothesis is a PIT free SEC
Companyfacts candidate source: production-universe names whose latest filed
annual R&D expense intensity (R&D / revenue) is rising, whose R&D spend grows
faster than revenue, and whose price already shows liquid SPY-relative
leadership may identify innovation-investment leaders with 10-day continuation.

This intentionally reads the raw SEC Companyfacts cache because the selected
Companyfacts sidecar used by prior quality/profitability experiments does not
carry a canonical R&D field. No production code, shared adapter, live/default
orders, ranking, sizing, exits, LLM/news path, or watchlist behavior is changed.
A positive replay is only a lead until a shared historical/daily helper
reproduces the exact PIT field mapping. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260614_020_accruals_cash_conversion_quality as base


EXPERIMENT_ID = "exp-20260616-003"
STEM = "raw_sec_rd_intensity_candidate_pool"
TRIAL_FAMILY = "raw_sec_companyfacts_rd_intensity_candidate_pool"
TRIAL_VARIANT_ID = "rd_intensity_acceleration_top1_next_open_10d_v1"
CHANGED_VARIABLE = "raw_sec_companyfacts_rd_intensity_acceleration_rs_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search"

REPO_ROOT = base.REPO_ROOT
RAW_COMPANYFACTS_CACHE = REPO_ROOT / "data" / "cache" / "sec" / "companyfacts"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260616_003_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
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
MIN_RD_EXPENSE = 50_000_000.0
MIN_CURRENT_RD_INTENSITY = 0.04
MAX_CURRENT_RD_INTENSITY = 0.35
MIN_RD_INTENSITY_DELTA = 0.005
MIN_RD_EXPENSE_GROWTH = 0.08
MIN_REVENUE_GROWTH = -0.05
MIN_RD_GROWTH_SPREAD = 0.05

RD_TAGS = (
    "ResearchAndDevelopmentExpense",
    "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost",
    "ResearchAndDevelopmentExpenseSoftwareExcludingAcquiredInProcessCost",
    "ResearchAndDevelopmentExpenseSoftwareExcludingAcquiredInProcessCostAndDevelopmentCostOfSoftwareToBeSoldLeasedOrOtherwiseMarketed",
)
REVENUE_TAGS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
)

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "companyfacts_near_neighbor_comparator_failed",
        "window_regression",
        "concentration_failed",
        "rd_field_duration_noise",
        "innovation_spend_is_late_cycle_drag",
    ],
    "confidence_reason": (
        "Raw SEC R&D expense is genuinely new versus the selected Companyfacts "
        "sidecar used in recent quality/profitability trials. The economic edge "
        "is plausible when rising innovation intensity is already confirmed by "
        "relative strength, but the Companyfacts family is saturated and R&D can "
        "select expensive long-duration names, so success odds remain low."
    ),
    "recorded_at": "2026-06-16T01:11:46+00:00",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "execution_envelope": {
        **base.PRODUCTION_IMPACT["execution_envelope"],
        "failure_handling": (
            "missing raw SEC annual R&D/revenue pair, missing prior annual "
            "comparison pair, stale facts, missing CIK mapping, missing OHLCV, "
            "missing next open, or missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same raw "
        "SEC tag mapping, filed-date PIT annual R&D intensity acceleration gate, "
        "liquid SPY-relative confirmation, cooldown, next-open paper entry, "
        "10-day exit, costs, and concentration controls in both historical "
        "replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: raw SEC Companyfacts annual R&D intensity acceleration "
        "(R&D/revenue rising year over year, with R&D spend growing faster than "
        "revenue) paired with liquid SPY-relative leadership may identify "
        "innovation-investment winners whose underappreciated reinvestment shows "
        "10-day continuation beyond price-only and static profitability sources."
    ),
    "2_history_check": {
        "exp-20260602-007": (
            "Companyfacts growth/quality rejected R&D intensity because the "
            "selected sidecar had no research/development canonical field. This "
            "run uses raw SEC Companyfacts tags, which are new evidence."
        ),
        "exp-20260614-014/exp-20260615-010/exp-20260615-016": (
            "Kova capital efficiency, gross profitability, and operating "
            "leverage were rejected. This run is not another static "
            "profitability or margin-spread filter; it tests innovation "
            "investment intensity from a raw field unavailable to those trials."
        ),
        "exp-20260616-002": (
            "The prior blocker found no PIT analyst breadth/dispersion data. "
            "This run leaves analyst soft ranking aside and uses a free raw SEC "
            "field with verified cache coverage."
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
        "exp_20260616_003_raw_sec_rd_intensity_candidate_pool.py"
    ),
}

_RAW_INDEX_CACHE: tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return base._round(value, digits)


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _duration_days(raw: dict[str, Any]) -> int | None:
    start = str(raw.get("start") or "")[:10]
    end = str(raw.get("end") or "")[:10]
    if not start or not end:
        return None
    try:
        return (base.framework._parse_date(end) - base.framework._parse_date(start)).days
    except Exception:
        return None


def _raw_annual_facts(usgaap: dict[str, Any], tags: tuple[str, ...]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for tag in tags:
        tag_payload = usgaap.get(tag) or {}
        for raw in tag_payload.get("units", {}).get("USD", []):
            duration = _duration_days(raw)
            fp = str(raw.get("fp") or "")
            if duration is None or not (FY_DURATION_MIN <= duration <= FY_DURATION_MAX):
                continue
            if fp and fp != "FY":
                continue
            filed = str(raw.get("filed") or "")[:10]
            start = str(raw.get("start") or "")[:10]
            end = str(raw.get("end") or "")[:10]
            value = _float_or_none(raw.get("val"))
            if not filed or not start or not end or value is None:
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
                    "fp": fp,
                    "duration_days": duration,
                }
            )
    facts.sort(key=lambda row: (row["end"], row["filed"], row["tag"], row["value"]))
    return facts


def _latest_period_fact(
    facts: list[dict[str, Any]],
    *,
    asof: str,
    end: str | None = None,
    before_end: str | None = None,
) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for fact in facts:
        if fact["filed"] > asof:
            continue
        if end is not None and fact["end"] != end:
            continue
        if before_end is not None and fact["end"] >= before_end:
            continue
        candidates.append(fact)
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda fact: (
            str(fact["end"]),
            str(fact["filed"]),
            float(fact["value"] or 0.0),
            str(fact["tag"]),
        ),
    )


def _latest_rd_revenue_pair(
    facts: dict[str, list[dict[str, Any]]],
    *,
    asof: str,
    before_end: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    rd = _latest_period_fact(facts["rd_expense"], asof=asof, before_end=before_end)
    if rd is None:
        return None
    revenue = _latest_period_fact(facts["revenue"], asof=asof, end=rd["end"])
    if revenue is None:
        return None
    return rd, revenue


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
        rd_facts = _raw_annual_facts(usgaap, RD_TAGS)
        revenue_facts = _raw_annual_facts(usgaap, REVENUE_TAGS)
        if not rd_facts:
            stats["tickers_missing_raw_annual_rd"] += 1
            continue
        if not revenue_facts:
            stats["tickers_missing_raw_annual_revenue"] += 1
            continue
        index[ticker] = {
            "rd_expense": rd_facts,
            "revenue": revenue_facts,
        }
        stats["tickers_with_raw_annual_rd_and_revenue"] += 1
        stats["raw_annual_rd_fact_count"] += len(rd_facts)
        stats["raw_annual_revenue_fact_count"] += len(revenue_facts)

    summary = {
        "raw_companyfacts_cache": _repo_rel(RAW_COMPANYFACTS_CACHE),
        "rd_tags": list(RD_TAGS),
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


def _rd_intensity_observation(
    ticker: str,
    asof: str,
    facts: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    current_pair = _latest_rd_revenue_pair(facts, asof=asof)
    if current_pair is None:
        return None
    current_rd, current_revenue = current_pair
    if base._days_between(asof, current_rd["filed"]) > MAX_ANNUAL_FACT_AGE_DAYS:
        return None

    prior_pair = _latest_rd_revenue_pair(facts, asof=asof, before_end=current_rd["end"])
    if prior_pair is None:
        return None
    prior_rd, prior_revenue = prior_pair

    current_rd_value = float(current_rd["value"])
    current_revenue_value = float(current_revenue["value"])
    prior_rd_value = float(prior_rd["value"])
    prior_revenue_value = float(prior_revenue["value"])
    if min(current_rd_value, current_revenue_value, prior_rd_value, prior_revenue_value) <= 0.0:
        return None
    if current_revenue_value < MIN_CURRENT_REVENUE or current_rd_value < MIN_RD_EXPENSE:
        return None

    current_intensity = current_rd_value / current_revenue_value
    prior_intensity = prior_rd_value / prior_revenue_value
    intensity_delta = current_intensity - prior_intensity
    rd_growth = current_rd_value / prior_rd_value - 1.0
    revenue_growth = current_revenue_value / prior_revenue_value - 1.0
    growth_spread = rd_growth - revenue_growth

    if current_intensity < MIN_CURRENT_RD_INTENSITY:
        return None
    if current_intensity > MAX_CURRENT_RD_INTENSITY:
        return None
    if intensity_delta < MIN_RD_INTENSITY_DELTA:
        return None
    if rd_growth < MIN_RD_EXPENSE_GROWTH:
        return None
    if revenue_growth < MIN_REVENUE_GROWTH:
        return None
    if growth_spread < MIN_RD_GROWTH_SPREAD:
        return None

    return {
        "current_fiscal_year_end": current_rd["end"],
        "prior_fiscal_year_end": prior_rd["end"],
        "current_rd_filed": current_rd["filed"],
        "prior_rd_filed": prior_rd["filed"],
        "current_revenue_filed": current_revenue["filed"],
        "prior_revenue_filed": prior_revenue["filed"],
        "current_rd_tag": current_rd["tag"],
        "current_revenue_tag": current_revenue["tag"],
        "current_rd_expense": _round(current_rd_value, 2),
        "prior_rd_expense": _round(prior_rd_value, 2),
        "current_revenue": _round(current_revenue_value, 2),
        "prior_revenue": _round(prior_revenue_value, 2),
        "current_rd_intensity": _round(current_intensity, 6),
        "prior_rd_intensity": _round(prior_intensity, 6),
        "rd_intensity_delta": _round(intensity_delta, 6),
        "rd_expense_growth": _round(rd_growth, 6),
        "revenue_growth": _round(revenue_growth, 6),
        "rd_growth_spread": _round(growth_spread, 6),
        "fact_age_days": base._days_between(asof, current_rd["filed"]),
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
            quality = _rd_intensity_observation(ticker, signal_date, quality_index[ticker])
            if quality is None:
                scan["failed_rd_intensity_gate"] += 1
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
                1.15 * min(float(quality["rd_growth_spread"] or 0.0), 1.0)
                + 1.00 * min(float(quality["rd_intensity_delta"] or 0.0), 0.12)
                + 0.35 * min(float(quality["current_rd_intensity"] or 0.0), 0.35)
                + 0.20 * min(float(quality["revenue_growth"] or 0.0), 1.0)
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
                    "source": "RAW_SEC_RD_INTENSITY_ACCELERATION_PAPER",
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
            -float(row["quality_rd_growth_spread"] or 0.0),
            -float(row["quality_rd_intensity_delta"] or 0.0),
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
        "min_rd_expense": MIN_RD_EXPENSE,
        "min_current_rd_intensity": MIN_CURRENT_RD_INTENSITY,
        "max_current_rd_intensity": MAX_CURRENT_RD_INTENSITY,
        "min_rd_intensity_delta": MIN_RD_INTENSITY_DELTA,
        "min_rd_expense_growth": MIN_RD_EXPENSE_GROWTH,
        "min_revenue_growth": MIN_REVENUE_GROWTH,
        "min_rd_growth_spread": MIN_RD_GROWTH_SPREAD,
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
        "positive_replay_lead_not_promoted_raw_sec_rd_intensity"
        if gate["passed"]
        else "rejected_raw_sec_rd_intensity_candidate_pool"
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
            "The raw SEC R&D intensity acceleration source cleared the numeric "
            "three-window replay screen, but remains only a replay lead because "
            "no shared daily/backtest helper was promoted."
        )
    else:
        interpretation = (
            "The raw SEC R&D intensity acceleration source did not clear Gate 4 "
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
            "mechanism_family": (
                "production_visible_free_sec_companyfacts_investment_intensity_candidate_pool"
            ),
            "new_evidence_type": "raw_sec_companyfacts_research_and_development_expense_pit_field",
            "nearby_prior_experiments": [
                "exp-20260602-007",
                "exp-20260614-014",
                "exp-20260615-010",
                "exp-20260615-016",
                "exp-20260616-002",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "high",
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
            "min_rd_expense": MIN_RD_EXPENSE,
            "min_current_rd_intensity": MIN_CURRENT_RD_INTENSITY,
            "max_current_rd_intensity": MAX_CURRENT_RD_INTENSITY,
            "min_rd_intensity_delta": MIN_RD_INTENSITY_DELTA,
            "min_rd_expense_growth": MIN_RD_EXPENSE_GROWTH,
            "min_revenue_growth": MIN_REVENUE_GROWTH,
            "min_rd_growth_spread": MIN_RD_GROWTH_SPREAD,
            "rd_tags": list(RD_TAGS),
            "revenue_tags": list(REVENUE_TAGS),
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Annual R&D expense and revenue are read from raw SEC Companyfacts tags "
        "and are known only by their filed date (<= signal date). Current and "
        "prior annual R&D values are matched to same-period annual revenue by "
        "fiscal year end. Price confirmation uses only signal-date OHLCV. Paper "
        "entry is the next available open with existing entry slippage; exit is "
        "the close 10 trading days after the signal with target-side sell "
        "slippage and ROUND_TRIP_COST_PCT."
    )
    payload["backtest_protocol"]["companyfacts_source"] = _repo_rel(RAW_COMPANYFACTS_CACHE)
    payload["gate2"]["runtime_fields"] = [
        "raw SEC companyfacts ResearchAndDevelopmentExpense annual facts",
        "raw SEC companyfacts annual revenue facts",
        "raw SEC companyfacts filed date and period end",
        "warehouse ticker_universe CIK mapping",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A retry needs materially different PIT innovation evidence, such as "
        "same-period R&D efficiency tied to forward revenue revisions or "
        "product-launch/contract evidence. Do not sweep R&D intensity, growth, "
        "freshness, revenue floor, RS/close/volume/vol guards, top-N, hold, "
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
            "Do not retry by sweeping R&D intensity, R&D growth spread, revenue "
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
        _repo_rel(ARTIFACT_MD),
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
            f"# {EXPERIMENT_ID} Raw SEC R&D Intensity Acceleration",
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
            _repo_rel(ARTIFACT_MD),
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
            _repo_rel(ARTIFACT_MD): base.framework._sha256(ARTIFACT_MD),
        },
    }
    base.framework._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    log_record = base._build_log_record(payload)
    base.framework._write_json(OUT_JSON, payload)
    base.framework._write_json(LOG_JSON, payload)
    card = _build_card(payload)
    base.framework._write_text(CARD_MD, card)
    base.framework._write_text(ARTIFACT_MD, card)
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
