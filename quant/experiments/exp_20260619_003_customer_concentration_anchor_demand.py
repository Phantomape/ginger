"""exp-20260619-003: customer concentration anchor-demand scout.

Replay-only alpha search. The single decision hypothesis is that raw SEC
Companyfacts customer concentration percentages, when paired with non-contracting
revenue and liquid SPY-relative price confirmation, may identify issuers with
real anchor-customer demand pull before a next-open 10-trading-day continuation
leg.

This is not a deferred-revenue/RPO/backlog retry, not a DSO/allowance retune,
and not a generic SEC text expansion. No production code, shared adapter,
live/default orders, ranking, sizing, exits, LLM/news path, or watchlist
behavior is changed. A positive replay is only a lead until a shared
historical/daily helper reproduces the exact PIT field mapping. No JavaScript
is used.
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

EXPERIMENT_ID = "exp-20260619-003"
STEM = "customer_concentration_anchor_demand"
TRIAL_FAMILY = "customer_concentration_anchor_demand_candidate_pool"
TRIAL_VARIANT_ID = "customer_concentration_anchor_demand_top1_next_open_10d_v1"
CHANGED_VARIABLE = "raw_sec_companyfacts_customer_concentration_anchor_demand_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
RAW_COMPANYFACTS_CACHE = REPO_ROOT / "data" / "cache" / "sec" / "companyfacts"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260619_003_{STEM}.json"
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
MAX_CONCENTRATION_FACT_AGE_DAYS = 430
MAX_REVENUE_FACT_AGE_DAYS = 500
MIN_CURRENT_REVENUE = 250_000_000.0
MIN_REVENUE_GROWTH = -0.05
MIN_ANCHOR_CONCENTRATION = 0.10
MAX_ANCHOR_CONCENTRATION = 0.85
MIN_PRIOR_GAP_DAYS = 80
MAX_PRIOR_GAP_DAYS = 500

CONCENTRATION_TAGS = ("ConcentrationRiskPercentage1",)
REVENUE_TAGS = template.REVENUE_TAGS

PREDICTION = {
    "success_probability": 0.11,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "customer_concentration_semantics_noisy",
        "coverage_too_sparse",
        "window_regression",
        "target_concentration_failed",
        "accepted_comparator_not_beaten",
    ],
    "confidence_reason": (
        "Customer concentration percentages are a free SEC/XBRL PIT numeric "
        "surface explicitly named as a possible sharper context after DSO and "
        "working-capital failures, but coverage is likely sparse and the tag "
        "can mix customer, credit, and supplier concentration semantics."
    ),
    "recorded_at": "2026-06-19T01:12:35+00:00",
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
    "uses_free_ohlcv": True,
    "uses_llm": False,
    "execution_envelope": {
        **template.PRODUCTION_IMPACT["execution_envelope"],
        "failure_handling": (
            "missing raw SEC customer concentration percentage, missing annual "
            "revenue comparison pair, stale facts, malformed concentration "
            "value, missing CIK mapping, missing OHLCV, missing next open, or "
            "missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same raw "
        "SEC ConcentrationRiskPercentage1 filed-date PIT mapping, annual "
        "revenue context, liquid SPY-relative confirmation, cooldown, next-open "
        "paper entry, 10-day exit, costs, and concentration controls in both "
        "historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: raw SEC Companyfacts customer concentration numeric "
        "disclosures, where a material but not all-or-nothing concentration "
        "percentage is present and revenue is non-contracting while price "
        "confirms liquid SPY-relative demand, may identify issuers with a real "
        "anchor-customer demand pull rather than generic momentum."
    ),
    "2_history_check": {
        "exp-20260616-021": (
            "Rejected receivables DSO/collection improvement and named customer "
            "concentration context as possible new evidence. This run uses the "
            "customer concentration disclosure directly, not DSO thresholds."
        ),
        "exp-20260616-023": (
            "Rejected allowance/doubtful accounts quality and also requested "
            "customer concentration context. This run avoids allowance ratios."
        ),
        "exp-20260615-013": (
            "Rejected quantified SEC backlog/RPO text as sparse. This run uses "
            "structured Companyfacts numeric concentration facts, not expanded "
            "text regexes or backlog phrase lists."
        ),
        "exp-20260615-017": (
            "Rejected deferred-revenue/contract-liability/RPO demand "
            "acceleration. This run does not use contract liability or RPO."
        ),
        "novelty_gate": (
            "Reservation warned near deferred-revenue demand but override "
            "recorded the new evidence axis: raw SEC Companyfacts "
            "ConcentrationRiskPercentage1 numeric anchor-customer context."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL must "
        "be positive, no unacceptable drawdown/survival/concentration "
        "degradation, at least 20 paper trades, all target windows represented, "
        "and accepted compression/distribution comparators must be beaten. "
        "Replay-only positives are leads until shared daily/backtest parity "
        "exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260619_003_customer_concentration_anchor_demand.py"
    ),
}

_RAW_INDEX_CACHE: tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return base._round(value, digits)


def _concentration_facts(usgaap: dict[str, Any]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for tag in CONCENTRATION_TAGS:
        for unit, rows in (usgaap.get(tag) or {}).get("units", {}).items():
            if unit not in {"pure", "Rate"}:
                continue
            for raw in rows or []:
                duration = template._duration_days(raw)
                if duration is None or duration < 80 or duration > 640:
                    continue
                start = str(raw.get("start") or "")[:10]
                end = str(raw.get("end") or "")[:10]
                filed = str(raw.get("filed") or "")[:10]
                value = template._float_or_none(raw.get("val"))
                if not start or not end or not filed or value is None:
                    continue
                if not math.isfinite(value) or value <= 0.0 or value > 1.0:
                    continue
                facts.append(
                    {
                        "filed": filed,
                        "start": start,
                        "end": end,
                        "value": value,
                        "tag": tag,
                        "unit": unit,
                        "form": str(raw.get("form") or ""),
                        "fy": raw.get("fy"),
                        "fp": str(raw.get("fp") or ""),
                        "duration_days": duration,
                        "accn": str(raw.get("accn") or ""),
                    }
                )
    facts.sort(key=lambda row: (row["end"], row["filed"], row["value"], row["accn"]))
    return facts


def _latest_fact(
    facts: list[dict[str, Any]],
    *,
    asof: str,
    before_end: str | None = None,
) -> dict[str, Any] | None:
    candidates = [
        fact
        for fact in facts
        if fact["filed"] <= asof and (before_end is None or fact["end"] < before_end)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda row: (row["filed"], row["end"], row["value"], row["accn"]))


def _latest_revenue_pair(
    facts: dict[str, list[dict[str, Any]]],
    *,
    asof: str,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    current = template._latest_period_fact(facts["revenue"], asof=asof)
    if current is None:
        return None
    prior = template._latest_period_fact(
        facts["revenue"],
        asof=asof,
        before_end=current["end"],
    )
    if prior is None:
        return None
    return current, prior


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
        concentration = _concentration_facts(usgaap)
        revenue = template._raw_annual_facts(usgaap, REVENUE_TAGS)
        if not concentration:
            stats["tickers_missing_concentration_facts"] += 1
            continue
        if not revenue:
            stats["tickers_missing_raw_annual_revenue"] += 1
            continue
        index[ticker] = {
            "concentration": concentration,
            "revenue": revenue,
        }
        stats["tickers_with_concentration_and_revenue"] += 1
        stats["raw_concentration_fact_count"] += len(concentration)
        stats["raw_annual_revenue_fact_count"] += len(revenue)

    summary = {
        "raw_companyfacts_cache": _repo_rel(RAW_COMPANYFACTS_CACHE),
        "concentration_tags": list(CONCENTRATION_TAGS),
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
        "field_source": "raw_sec_companyfacts_concentration_risk_percentage",
    }


def _anchor_demand_observation(
    ticker: str,
    asof: str,
    facts: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    concentration = _latest_fact(facts["concentration"], asof=asof)
    if concentration is None:
        return None
    if base._days_between(asof, concentration["filed"]) > MAX_CONCENTRATION_FACT_AGE_DAYS:
        return None

    value = float(concentration["value"])
    if value < MIN_ANCHOR_CONCENTRATION or value > MAX_ANCHOR_CONCENTRATION:
        return None

    prior_concentration = _latest_fact(
        facts["concentration"],
        asof=asof,
        before_end=concentration["end"],
    )
    concentration_change = None
    concentration_gap_days = None
    if prior_concentration is not None:
        concentration_gap_days = base._days_between(concentration["end"], prior_concentration["end"])
        if MIN_PRIOR_GAP_DAYS <= concentration_gap_days <= MAX_PRIOR_GAP_DAYS:
            concentration_change = value - float(prior_concentration["value"])

    revenue_pair = _latest_revenue_pair(facts, asof=asof)
    if revenue_pair is None:
        return None
    current_revenue, prior_revenue = revenue_pair
    if base._days_between(asof, current_revenue["filed"]) > MAX_REVENUE_FACT_AGE_DAYS:
        return None
    current_revenue_value = float(current_revenue["value"])
    prior_revenue_value = float(prior_revenue["value"])
    if current_revenue_value < MIN_CURRENT_REVENUE or prior_revenue_value <= 0.0:
        return None
    revenue_growth = current_revenue_value / prior_revenue_value - 1.0
    if revenue_growth < MIN_REVENUE_GROWTH:
        return None

    anchor_score = min(value, 0.55) - MIN_ANCHOR_CONCENTRATION
    if concentration_change is not None:
        anchor_score += 0.25 * max(min(concentration_change, 0.25), -0.15)

    return {
        "ticker": ticker,
        "current_concentration_end": concentration["end"],
        "current_concentration_filed": concentration["filed"],
        "current_concentration_value": _round(value, 6),
        "current_concentration_tag": concentration["tag"],
        "current_concentration_unit": concentration["unit"],
        "current_concentration_form": concentration["form"],
        "current_concentration_fp": concentration["fp"],
        "prior_concentration_end": None if prior_concentration is None else prior_concentration["end"],
        "prior_concentration_value": None
        if prior_concentration is None
        else _round(prior_concentration["value"], 6),
        "concentration_change": _round(concentration_change, 6),
        "concentration_gap_days": concentration_gap_days,
        "current_revenue_end": current_revenue["end"],
        "prior_revenue_end": prior_revenue["end"],
        "current_revenue_filed": current_revenue["filed"],
        "prior_revenue_filed": prior_revenue["filed"],
        "current_revenue_tag": current_revenue["tag"],
        "current_revenue": _round(current_revenue_value, 2),
        "prior_revenue": _round(prior_revenue_value, 2),
        "revenue_growth": _round(revenue_growth, 6),
        "concentration_fact_age_days": base._days_between(asof, concentration["filed"]),
        "revenue_fact_age_days": base._days_between(asof, current_revenue["filed"]),
        "anchor_score_component": _round(anchor_score, 6),
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
            quality = _anchor_demand_observation(ticker, signal_date, quality_index[ticker])
            if quality is None:
                scan["failed_anchor_demand_gate"] += 1
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
                1.10 * float(quality["anchor_score_component"] or 0.0)
                + 0.30 * min(float(quality["revenue_growth"] or 0.0), 1.0)
                + 0.50 * float(confirm["candidate_ret20_excess_spy"])
                + 0.15 * float(confirm["candidate_ret60_excess_spy"])
                + 0.10 * float(confirm["candidate_close_location"])
                + 0.030
                * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
            )
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "RAW_SEC_CUSTOMER_CONCENTRATION_ANCHOR_DEMAND_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "raw_companyfacts_concentration_filed_and_signal_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_companyfacts": True,
                    "uses_raw_sec_companyfacts_cache": True,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    **{f"anchor_{key}": value for key, value in quality.items()},
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
            -float(row["anchor_current_concentration_value"] or 0.0),
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
        "max_concentration_fact_age_days": MAX_CONCENTRATION_FACT_AGE_DAYS,
        "max_revenue_fact_age_days": MAX_REVENUE_FACT_AGE_DAYS,
        "min_current_revenue": MIN_CURRENT_REVENUE,
        "min_revenue_growth": MIN_REVENUE_GROWTH,
        "min_anchor_concentration": MIN_ANCHOR_CONCENTRATION,
        "max_anchor_concentration": MAX_ANCHOR_CONCENTRATION,
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
        "positive_replay_lead_not_promoted_customer_concentration_anchor_demand"
        if gate["passed"]
        else "rejected_customer_concentration_anchor_demand_candidate_pool"
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
    base.MAX_ANNUAL_FACT_AGE_DAYS = MAX_REVENUE_FACT_AGE_DAYS
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
            "The customer concentration anchor-demand source cleared the "
            "numeric three-window replay screen, but remains only a replay lead "
            "because no shared daily/backtest helper was promoted."
        )
    else:
        interpretation = (
            "The customer concentration anchor-demand source did not clear Gate "
            f"4 (failed: {', '.join(gate4['failed_reasons']) or 'none'}). It is "
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
            "mechanism_family": "production_visible_free_sec_companyfacts_customer_concentration_candidate_pool",
            "new_evidence_type": "raw_sec_companyfacts_concentration_risk_percentage_customer_anchor_demand",
            "nearby_prior_experiments": [
                "exp-20260616-021",
                "exp-20260616-023",
                "exp-20260615-013",
                "exp-20260615-017",
                "exp-20260618-024",
                "exp-20260619-003_novelty_override",
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
            "max_concentration_fact_age_days": MAX_CONCENTRATION_FACT_AGE_DAYS,
            "max_revenue_fact_age_days": MAX_REVENUE_FACT_AGE_DAYS,
            "min_current_revenue": MIN_CURRENT_REVENUE,
            "min_revenue_growth": MIN_REVENUE_GROWTH,
            "min_anchor_concentration": MIN_ANCHOR_CONCENTRATION,
            "max_anchor_concentration": MAX_ANCHOR_CONCENTRATION,
            "min_prior_gap_days": MIN_PRIOR_GAP_DAYS,
            "max_prior_gap_days": MAX_PRIOR_GAP_DAYS,
            "concentration_tags": list(CONCENTRATION_TAGS),
            "revenue_tags": list(REVENUE_TAGS),
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Customer concentration percentage and annual revenue are read from raw "
        "SEC Companyfacts tags and are known only by filed date (<= signal "
        "date). The rule requires a material but not all-or-nothing "
        "ConcentrationRiskPercentage1 value, non-contracting annual revenue, "
        "and signal-date liquid SPY-relative price confirmation. Paper entry "
        "is the next available open with existing entry slippage; exit is the "
        "close 10 trading days after the signal with target-side sell slippage "
        "and ROUND_TRIP_COST_PCT."
    )
    payload["backtest_protocol"]["companyfacts_source"] = _repo_rel(RAW_COMPANYFACTS_CACHE)
    payload["gate2"]["runtime_fields"] = [
        "raw SEC companyfacts ConcentrationRiskPercentage1 facts",
        "raw SEC companyfacts annual revenue facts",
        "raw SEC companyfacts filed date and period end",
        "warehouse ticker_universe CIK mapping",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A retry needs materially richer PIT concentration evidence such as "
        "parsed footnote customer identity, contract duration/funding certainty, "
        "supplier/customer relationship graph context, or closed forward "
        "replacement-value rows. Do not sweep concentration thresholds, fact "
        "freshness, revenue floor, RS/close/volume guards, top-N, hold, "
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
            "Do not retry by sweeping customer concentration thresholds, "
            "period gap, revenue-growth floor, annual fact freshness, RS/close/"
            "volume/vol guards, top-N, hold days, cooldown, or notional on "
            "these frozen windows."
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
            f"# {EXPERIMENT_ID} Customer Concentration Anchor Demand",
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
