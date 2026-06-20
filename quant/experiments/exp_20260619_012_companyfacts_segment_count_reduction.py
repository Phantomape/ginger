"""exp-20260619-012: reportable segment count reduction candidate scout.

Replay-only alpha search. The single decision hypothesis is a PIT free SEC
Companyfacts candidate source: production-universe names whose latest filed
annual ``NumberOfReportableSegments`` count falls versus a comparable prior
annual filing, while revenue does not materially contract and price already
shows liquid SPY-relative leadership, may identify strategic simplification
or low-quality segment exits with 10-day continuation.

This intentionally reads the raw SEC Companyfacts cache because the selected
Companyfacts sidecar does not carry a canonical reportable-segment count
field. No production code, shared adapter, live/default orders, ranking,
sizing, exits, LLM/news path, or watchlist behavior is changed. A positive
replay is only a lead until a shared historical/daily helper reproduces the
exact PIT field mapping. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

import exp_20260617_005_depreciation_amortization_burden_relief as template


base = template.base

EXPERIMENT_ID = "exp-20260619-012"
STEM = "companyfacts_segment_count_reduction"
TRIAL_FAMILY = "companyfacts_segment_count_reduction_candidate_pool"
TRIAL_VARIANT_ID = "companyfacts_segment_count_reduction_top1_next_open_10d_v1"
CHANGED_VARIABLE = "raw_sec_companyfacts_reportable_segment_count_reduction_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
RAW_COMPANYFACTS_CACHE = REPO_ROOT / "data" / "cache" / "sec" / "companyfacts"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260619_012_{STEM}.json"
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
MAX_SEGMENT_FACT_AGE_DAYS = 500
COMPARABLE_PERIOD_MIN_GAP_DAYS = 250
COMPARABLE_PERIOD_MAX_GAP_DAYS = 500
MIN_CURRENT_REVENUE = 500_000_000.0
MIN_REVENUE_GROWTH = -0.10
MIN_PRIOR_SEGMENT_COUNT = 2
MIN_CURRENT_SEGMENT_COUNT = 1
MAX_SEGMENT_COUNT = 12
MIN_SEGMENT_REDUCTION_COUNT = 1

SEGMENT_TAG = "NumberOfReportableSegments"
SEGMENT_FORMS = {"10-K", "10-K/A", "10-KT", "20-F", "20-F/A", "40-F", "40-F/A"}
REVENUE_TAGS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
)

PREDICTION = {
    "success_probability": 0.12,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "companyfacts_family_saturated",
        "segment_count_semantics_noisy",
        "old_thin_regression",
        "accepted_distribution_comparator_not_beaten",
        "target_concentration_failed",
    ],
    "confidence_reason": (
        "NumberOfReportableSegments is a raw SEC structure field not used by "
        "recent Companyfacts burden, overhang, inventory, public-float, debt, "
        "or SBC experiments. The mechanism is business simplification or "
        "exiting lower-quality reportable segments, but raw Companyfacts "
        "candidate pools have recently failed old_thin, drawdown, sample, or "
        "accepted-comparator gates."
    ),
    "recorded_at": "2026-06-19T12:00:56Z",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "execution_envelope": {
        **base.PRODUCTION_IMPACT["execution_envelope"],
        "failure_handling": (
            "missing raw SEC annual reportable-segment count, missing "
            "comparable prior segment count, stale filed date, missing annual "
            "revenue pair, revenue contraction below threshold, missing CIK "
            "mapping, missing OHLCV, missing next open, or missing 10d exit "
            "rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same raw "
        "SEC tag mapping, filed-date PIT segment-count reduction gate, liquid "
        "SPY-relative confirmation, cooldown, next-open paper entry, 10-day "
        "exit, costs, and concentration controls in both historical replay and "
        "daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: raw SEC Companyfacts annual NumberOfReportableSegments "
        "falling versus the prior annual filing may identify companies "
        "simplifying business structure or exiting low-quality segments; with "
        "liquid SPY-relative confirmation, next-open 10-day default-off paper "
        "entries may improve replacement value."
    ),
    "2_history_check": {
        "novelty_gate": (
            "scripts/check_experiment_novelty.py returned a WARN near broad "
            "Companyfacts candidate-pool families, not a hard block. The "
            "reserved experiment used --novelty-override because this is a new "
            "raw SEC structure/complexity field rather than a financial burden "
            "ratio, overhang, ownership, float, inventory, or SBC axis."
        ),
        "exp-20260617-008": (
            "Rejected AOCI relief; same raw Companyfacts source class, but it "
            "tested a balance-sheet burden ratio, not reportable-segment count "
            "direction."
        ),
        "exp-20260617-016": (
            "Rejected fixed-asset impairment relief; this run does not use "
            "impairment, PP&E, or capex burden fields."
        ),
        "exp-20260618-020": (
            "Rejected low asset growth; this run tests organizational segment "
            "count simplification rather than asset-base growth."
        ),
        "exp-20260619-003": (
            "Rejected customer concentration anchor demand; this run uses a "
            "structure count field, not customer concentration percentage."
        ),
        "exp-20260618-021": (
            "SBC gap-fill allocator was positive but rejected versus the "
            "accepted allocator comparator and is frozen. This run avoids SBC "
            "threshold/ranking retries."
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
        "exp_20260619_012_companyfacts_segment_count_reduction.py"
    ),
}

_SEGMENT_INDEX_CACHE: tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]] | None = None


def _repo_rel(path: Path | str) -> str:
    return template._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return template._round(value, digits)


def _float_or_none(value: Any) -> float | None:
    return template._float_or_none(value)


def _duration_days(raw: dict[str, Any]) -> int | None:
    return template._duration_days(raw)


def _int_count_or_none(value: Any) -> int | None:
    as_float = _float_or_none(value)
    if as_float is None or not math.isfinite(as_float):
        return None
    as_int = int(round(as_float))
    if abs(as_float - as_int) > 1e-9:
        return None
    if as_int < MIN_CURRENT_SEGMENT_COUNT or as_int > MAX_SEGMENT_COUNT:
        return None
    return as_int


def _raw_segment_facts(usgaap: dict[str, Any]) -> list[dict[str, Any]]:
    tag_payload = usgaap.get(SEGMENT_TAG) or {}
    facts: list[dict[str, Any]] = []
    for unit, rows in (tag_payload.get("units") or {}).items():
        for raw in rows:
            duration = _duration_days(raw)
            fp = str(raw.get("fp") or "")
            form = str(raw.get("form") or "")
            if duration is None or not (FY_DURATION_MIN <= duration <= FY_DURATION_MAX):
                continue
            if fp and fp != "FY":
                continue
            if form and form not in SEGMENT_FORMS:
                continue
            filed = str(raw.get("filed") or "")[:10]
            start = str(raw.get("start") or "")[:10]
            end = str(raw.get("end") or "")[:10]
            count = _int_count_or_none(raw.get("val"))
            if not filed or not start or not end or count is None:
                continue
            facts.append(
                {
                    "filed": filed,
                    "start": start,
                    "end": end,
                    "value": count,
                    "tag": SEGMENT_TAG,
                    "unit": str(unit),
                    "form": form,
                    "fy": raw.get("fy"),
                    "fp": fp,
                    "accn": str(raw.get("accn") or ""),
                    "duration_days": duration,
                }
            )
    facts.sort(key=lambda row: (row["end"], row["filed"], row["value"], row["unit"], row["accn"]))
    return facts


def _latest_segment_fact(
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
            int(fact["value"] or 0),
            str(fact["unit"]),
            str(fact["accn"]),
        ),
    )


def _prior_comparable_segment(
    facts: list[dict[str, Any]],
    *,
    asof: str,
    current_end: str,
) -> dict[str, Any] | None:
    current_end_date = base.framework._parse_date(current_end)
    candidates: list[dict[str, Any]] = []
    for fact in facts:
        if fact["filed"] > asof or fact["end"] >= current_end:
            continue
        gap_days = (current_end_date - base.framework._parse_date(fact["end"])).days
        if COMPARABLE_PERIOD_MIN_GAP_DAYS <= gap_days <= COMPARABLE_PERIOD_MAX_GAP_DAYS:
            candidates.append({**fact, "_gap_days": gap_days})
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda fact: (
            abs(int(fact["_gap_days"]) - 365),
            -int(fact["_gap_days"]),
            str(fact["filed"]),
            int(fact["value"] or 0),
        ),
    )


def _load_segment_index() -> tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]]:
    global _SEGMENT_INDEX_CACHE
    if _SEGMENT_INDEX_CACHE is not None:
        return _SEGMENT_INDEX_CACHE

    stats: Counter[str] = Counter()
    ticker_ciks: dict[str, int] = {}
    uri = f"file:{Path(base.framework.WAREHOUSE).resolve().as_posix()}?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True) as con:
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
        segment_facts = _raw_segment_facts(usgaap)
        revenue_facts = template._raw_annual_facts(usgaap, REVENUE_TAGS)
        if not segment_facts:
            stats["tickers_missing_segment_count_facts"] += 1
            continue
        if not revenue_facts:
            stats["tickers_missing_raw_annual_revenue"] += 1
            continue
        index[ticker] = {
            "segments": segment_facts,
            "revenue": revenue_facts,
        }
        stats["tickers_with_segment_count_and_revenue"] += 1
        stats["raw_segment_count_fact_count"] += len(segment_facts)
        stats["raw_annual_revenue_fact_count"] += len(revenue_facts)

    summary = {
        "raw_companyfacts_cache": _repo_rel(RAW_COMPANYFACTS_CACHE),
        "segment_tag": SEGMENT_TAG,
        "segment_forms": sorted(SEGMENT_FORMS),
        "revenue_tags": list(REVENUE_TAGS),
        "warehouse_source": _repo_rel(base.framework.WAREHOUSE),
        **dict(stats),
    }
    _SEGMENT_INDEX_CACHE = (index, summary)
    return _SEGMENT_INDEX_CACHE


def _build_quality_index(
    companyfacts_rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]]:
    index, summary = _load_segment_index()
    return index, {
        **summary,
        "selected_companyfacts_rows_ignored": len(companyfacts_rows),
        "field_source": "raw_sec_companyfacts_number_of_reportable_segments",
    }


def _segment_reduction_observation(
    ticker: str,
    asof: str,
    facts: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    current = _latest_segment_fact(facts["segments"], asof=asof)
    if current is None:
        return None
    if base._days_between(asof, current["filed"]) > MAX_SEGMENT_FACT_AGE_DAYS:
        return None
    prior = _prior_comparable_segment(
        facts["segments"],
        asof=asof,
        current_end=current["end"],
    )
    if prior is None:
        return None

    current_count = int(current["value"])
    prior_count = int(prior["value"])
    reduction_count = prior_count - current_count
    if prior_count < MIN_PRIOR_SEGMENT_COUNT:
        return None
    if reduction_count < MIN_SEGMENT_REDUCTION_COUNT:
        return None

    current_revenue = template._latest_period_fact(
        facts["revenue"],
        asof=asof,
        end=current["end"],
    )
    prior_revenue = template._latest_period_fact(
        facts["revenue"],
        asof=asof,
        end=prior["end"],
    )
    if current_revenue is None or prior_revenue is None:
        return None
    current_revenue_value = float(current_revenue["value"])
    prior_revenue_value = float(prior_revenue["value"])
    if current_revenue_value < MIN_CURRENT_REVENUE or prior_revenue_value <= 0.0:
        return None
    revenue_growth = current_revenue_value / prior_revenue_value - 1.0
    if revenue_growth < MIN_REVENUE_GROWTH:
        return None

    reduction_pct = reduction_count / prior_count
    return {
        "ticker": ticker,
        "current_segment_end": current["end"],
        "prior_segment_end": prior["end"],
        "current_segment_filed": current["filed"],
        "prior_segment_filed": prior["filed"],
        "current_segment_count": current_count,
        "prior_segment_count": prior_count,
        "segment_reduction_count": reduction_count,
        "segment_reduction_pct": _round(reduction_pct, 6),
        "current_segment_unit": current["unit"],
        "prior_segment_unit": prior["unit"],
        "current_segment_form": current["form"],
        "prior_segment_form": prior["form"],
        "current_segment_accn": current["accn"],
        "prior_segment_accn": prior["accn"],
        "current_revenue_end": current_revenue["end"],
        "prior_revenue_end": prior_revenue["end"],
        "current_revenue_filed": current_revenue["filed"],
        "prior_revenue_filed": prior_revenue["filed"],
        "current_revenue_tag": current_revenue["tag"],
        "current_revenue": _round(current_revenue_value, 2),
        "prior_revenue": _round(prior_revenue_value, 2),
        "revenue_growth": _round(revenue_growth, 6),
        "comparable_period_gap_days": int(prior["_gap_days"]),
        "segment_fact_age_days": base._days_between(asof, current["filed"]),
        "known_at": "raw_companyfacts_segment_count_filed_and_signal_close_before_next_open_paper_entry",
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
            observation = _segment_reduction_observation(ticker, signal_date, quality_index[ticker])
            if observation is None:
                scan["failed_segment_reduction_gate"] += 1
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
            reduction_count = float(observation["segment_reduction_count"] or 0.0)
            reduction_pct = float(observation["segment_reduction_pct"] or 0.0)
            revenue_growth = float(observation["revenue_growth"] or 0.0)
            score = (
                0.55 * min(reduction_pct, 0.75)
                + 0.12 * min(reduction_count, 4.0)
                + 0.22 * min(revenue_growth, 1.0)
                + 0.55 * float(confirm["candidate_ret20_excess_spy"])
                + 0.14 * float(confirm["candidate_ret60_excess_spy"])
                + 0.10 * float(confirm["candidate_close_location"])
                + 0.030
                * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
            )
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "RAW_SEC_SEGMENT_COUNT_REDUCTION_PAPER",
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
                    **{f"segment_{key}": value for key, value in observation.items()},
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
            -float(row["segment_segment_reduction_pct"] or 0.0),
            -float(row["segment_segment_reduction_count"] or 0.0),
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
        "max_segment_fact_age_days": MAX_SEGMENT_FACT_AGE_DAYS,
        "comparable_period_min_gap_days": COMPARABLE_PERIOD_MIN_GAP_DAYS,
        "comparable_period_max_gap_days": COMPARABLE_PERIOD_MAX_GAP_DAYS,
        "min_current_revenue": MIN_CURRENT_REVENUE,
        "min_revenue_growth": MIN_REVENUE_GROWTH,
        "min_prior_segment_count": MIN_PRIOR_SEGMENT_COUNT,
        "min_current_segment_count": MIN_CURRENT_SEGMENT_COUNT,
        "max_segment_count": MAX_SEGMENT_COUNT,
        "min_segment_reduction_count": MIN_SEGMENT_REDUCTION_COUNT,
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
        "positive_replay_lead_not_promoted_companyfacts_segment_count_reduction"
        if gate["passed"]
        else "rejected_companyfacts_segment_count_reduction_candidate_pool"
    )
    return gate


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    if gate4["passed"]:
        interpretation = (
            "The raw SEC reportable-segment count reduction source cleared the "
            "numeric three-window replay screen, but remains only a replay lead "
            "because no shared daily/backtest helper was promoted."
        )
    else:
        interpretation = (
            "The raw SEC reportable-segment count reduction source did not "
            f"clear Gate 4 (failed: {', '.join(gate4['failed_reasons']) or 'none'}). "
            "It is not retained or promoted."
        )

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": template._utc_now(),
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
                "production_visible_free_sec_companyfacts_structure_simplification_candidate_pool"
            ),
            "new_evidence_type": "raw_sec_companyfacts_number_of_reportable_segments_direction",
            "nearby_prior_experiments": [
                "exp-20260617-008",
                "exp-20260617-016",
                "exp-20260618-020",
                "exp-20260619-003",
                "exp-20260618-021",
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
            "max_segment_fact_age_days": MAX_SEGMENT_FACT_AGE_DAYS,
            "comparable_period_min_gap_days": COMPARABLE_PERIOD_MIN_GAP_DAYS,
            "comparable_period_max_gap_days": COMPARABLE_PERIOD_MAX_GAP_DAYS,
            "min_current_revenue": MIN_CURRENT_REVENUE,
            "min_revenue_growth": MIN_REVENUE_GROWTH,
            "min_prior_segment_count": MIN_PRIOR_SEGMENT_COUNT,
            "min_current_segment_count": MIN_CURRENT_SEGMENT_COUNT,
            "max_segment_count": MAX_SEGMENT_COUNT,
            "min_segment_reduction_count": MIN_SEGMENT_REDUCTION_COUNT,
            "segment_tag": SEGMENT_TAG,
            "segment_forms": sorted(SEGMENT_FORMS),
            "revenue_tags": list(REVENUE_TAGS),
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Annual NumberOfReportableSegments and revenue are read from raw SEC "
        "Companyfacts and are known only by their filed date (<= signal date). "
        "The rule compares latest filed annual segment count with a comparable "
        "prior annual period 250-500 days earlier, requires at least one fewer "
        "reportable segment, prior count >=2, count <=12, and revenue not "
        "contracting more than 10%. Price confirmation uses only signal-date "
        "OHLCV. Paper entry is the next available open with existing entry "
        "slippage; exit is the close 10 trading days after the signal with "
        "target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["backtest_protocol"]["companyfacts_source"] = _repo_rel(RAW_COMPANYFACTS_CACHE)
    payload["gate2"]["runtime_fields"] = [
        "raw SEC companyfacts NumberOfReportableSegments annual facts",
        "raw SEC companyfacts annual revenue facts",
        "raw SEC companyfacts filed date and period end",
        "warehouse ticker_universe CIK mapping",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A retry needs materially different PIT structure-simplification "
        "evidence such as segment revenue/profit mix, divestiture completion "
        "events, IPO/spin-off linkage, or closed forward replacement-value "
        "rows. Do not sweep segment-count thresholds, freshness, revenue floor, "
        "RS/close/volume/vol guards, top-N, hold, cooldown, or notional on "
        "these frozen windows."
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
            "Do not retry by sweeping segment-count reduction, annual fact "
            "freshness, revenue floor/growth, RS/close/volume/vol guards, top-N, "
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
            f"# {EXPERIMENT_ID} Companyfacts Segment Count Reduction",
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


def _configure_modules() -> None:
    template.__file__ = __file__
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
    template.MAX_ANNUAL_FACT_AGE_DAYS = MAX_SEGMENT_FACT_AGE_DAYS
    template.PREDICTION = PREDICTION
    template.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    template.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    template._build_quality_index = _build_quality_index
    template._candidate_rows_for_window = _candidate_rows_for_window
    template._gate4 = _gate4
    template._build_card = _build_card
    template._configure_base()


def main() -> None:
    _configure_modules()
    payload = _postprocess_payload(base._build_payload())
    template._persist(payload)
    encoder = json.JSONEncoder(indent=2, sort_keys=True)
    print(encoder.encode(base.framework._safe(base._build_log_record(payload))))


if __name__ == "__main__":
    main()
