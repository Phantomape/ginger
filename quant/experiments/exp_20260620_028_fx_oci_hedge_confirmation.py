"""exp-20260620-028: FX OCI tailwind with hedge confirmation.

Replay-only alpha search. The single decision hypothesis is a PIT free SEC
Companyfacts candidate source: the raw FX-translation OCI tailwind from
exp-20260620-026 should only enter the default-off paper queue when same-period
cash-flow/derivative hedge OCI evidence is non-adverse. The hedge component is
a new provenance axis, not a sweep of FX OCI thresholds, price guards, top-N,
hold, cooldown, or notional.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive result is
only a replay lead until shared daily/backtest parity reproduces the same PIT
field mapping. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260620_026_foreign_currency_oci_component_tailwind as prior


EXPERIMENT_ID = "exp-20260620-028"
STEM = "fx_oci_hedge_confirmation"
TRIAL_FAMILY = "raw_sec_fx_oci_hedge_confirmation_candidate_pool"
TRIAL_VARIANT_ID = "fx_oci_tailwind_cash_flow_hedge_confirmation_top1_next_open_10d_v1"
CHANGED_VARIABLE = "raw_sec_fx_oci_tailwind_with_cash_flow_hedge_confirmation_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = prior.REPO_ROOT
RAW_COMPANYFACTS_CACHE = prior.RAW_COMPANYFACTS_CACHE
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260620_028_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = prior.BASE_NOTIONAL_USD
HOLD_DAYS = prior.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = prior.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = prior.SAME_TICKER_COOLDOWN_DAYS

ANNUAL_DURATION_MIN = prior.ANNUAL_DURATION_MIN
ANNUAL_DURATION_MAX = prior.ANNUAL_DURATION_MAX
MAX_ANNUAL_FACT_AGE_DAYS = prior.MAX_ANNUAL_FACT_AGE_DAYS
MIN_CURRENT_REVENUE = prior.MIN_CURRENT_REVENUE
MIN_REVENUE_GROWTH = prior.MIN_REVENUE_GROWTH
MIN_CURRENT_FX_OCI_USD = prior.MIN_CURRENT_FX_OCI_USD
MIN_CURRENT_FX_OCI_TO_REVENUE = prior.MIN_CURRENT_FX_OCI_TO_REVENUE
MIN_FX_OCI_IMPROVEMENT_TO_REVENUE = prior.MIN_FX_OCI_IMPROVEMENT_TO_REVENUE

FX_OCI_TAGS = prior.FX_OCI_TAGS
REVENUE_TAGS = prior.REVENUE_TAGS
HEDGE_CONFIRMATION_TAGS = (
    "OtherComprehensiveIncomeLossCashFlowHedgeGainLossAfterReclassificationAndTax",
    "OtherComprehensiveIncomeLossCashFlowHedgeGainLossAfterReclassificationAfterTax",
    "OtherComprehensiveIncomeLossCashFlowHedgeGainLossAfterReclassificationAndTaxParent",
    "OtherComprehensiveIncomeLossCashFlowHedgeGainLossBeforeReclassificationAfterTax",
    "OtherComprehensiveIncomeLossCashFlowHedgeGainLossBeforeReclassificationAndTax",
    "OtherComprehensiveIncomeLossCashFlowHedgeGainLossReclassificationAfterTax",
    "OtherComprehensiveIncomeLossCashFlowHedgeGainLossReclassificationBeforeTax",
    "OtherComprehensiveIncomeLossDerivativesQualifyingAsHedgesNetOfTax",
    "OtherComprehensiveIncomeDerivativesQualifyingAsHedgesNetOfTaxPeriodIncreaseDecrease",
    "OtherComprehensiveIncomeUnrealizedGainLossOnDerivativesArisingDuringPeriodNetOfTax",
    "DerivativeInstrumentsGainLossRecognizedInOtherComprehensiveIncomeEffectivePortionNet",
    "DerivativeInstrumentsGainLossReclassifiedFromAccumulatedOCIIntoIncomeEffectivePortionNet",
    "OtherComprehensiveIncomeLossReclassificationAdjustmentFromAOCIOnDerivativesNetOfTax",
    "OtherComprehensiveIncomeLossReclassificationAdjustmentOnDerivativesIncludedInNetIncomeNetOfTax",
)
MIN_HEDGE_OCI_TO_REVENUE = 0.0

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "hedge_component_sparse",
        "old_thin_window_regression",
        "drawdown_drift",
        "accepted_distribution_comparator_not_beaten",
        "global_mega_cap_relabeling",
    ],
    "confidence_reason": (
        "exp-20260620-026 showed a real three-window FX OCI tailwind lead but "
        "failed only drawdown. Raw Companyfacts coverage scan found broad "
        "cash-flow/derivative hedge OCI fields, which are a materially different "
        "PIT provenance axis rather than a threshold sweep. The main risk is "
        "that hedge tags are noisy, sparse, or still relabel global mega-cap "
        "momentum."
    ),
    "recorded_at": "2026-06-20T21:05:52+00:00",
}

PRODUCTION_IMPACT = {
    **prior.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "execution_envelope": {
        **prior.PRODUCTION_IMPACT["execution_envelope"],
        "failure_handling": (
            "missing raw SEC FX-translation OCI component, missing same-period "
            "cash-flow/derivative hedge OCI component, missing matched annual "
            "revenue, stale facts, missing CIK mapping, missing OHLCV, missing "
            "next open, or missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same raw "
        "SEC FX OCI and cash-flow/derivative hedge OCI tag mapping, filed-date "
        "PIT annual component gates, revenue context, liquid SPY-relative "
        "confirmation, cooldown, next-open paper entry, 10-day exit, costs, and "
        "concentration controls in both historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: raw SEC FX-translation OCI tailwind candidates should "
        "only enter the default-off paper queue when the same filed annual "
        "period also shows non-adverse cash-flow/derivative hedge OCI "
        "confirmation, because hedge OCI/reclassification provenance "
        "distinguishes operating FX tailwind from noisy accounting translation."
    ),
    "2_history_check": {
        "novelty_gate": (
            "experiment.py new found no strong near-neighbor. The ticket records "
            "a novelty override/new-evidence axis: raw SEC cash-flow hedge and "
            "derivative OCI/reclassification component provenance paired with FX "
            "translation OCI tailwind; not AOCI balance overhang or FX OCI "
            "threshold/price/notional retuning."
        ),
        "exp-20260620-026": (
            "Rejected FX translation OCI tailwind only on drawdown drift after "
            "positive EV/PnL in all three windows. This run adds same-period "
            "hedge OCI provenance instead of changing FX thresholds or sizing."
        ),
        "exp-20260617-018": (
            "Rejected AOCI overhang relief. This run uses period OCI component "
            "flows and hedge/reclassification components, not aggregate AOCI."
        ),
        "exp-20260620-023": (
            "Rejected static SPY beta hedge. This run is a candidate source "
            "provenance gate, not a portfolio hedge overlay."
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
        "exp_20260620_028_fx_oci_hedge_confirmation.py"
    ),
}

_RAW_INDEX_CACHE: tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return prior._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return prior._round(value, digits)


def _raw_annual_facts(
    usgaap: dict[str, Any], tags: tuple[str, ...], *, unit: str
) -> list[dict[str, Any]]:
    return prior._raw_annual_facts(usgaap, tags, unit=unit)


def _load_raw_companyfacts_index() -> tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]]:
    global _RAW_INDEX_CACHE
    if _RAW_INDEX_CACHE is not None:
        return _RAW_INDEX_CACHE

    stats: Counter[str] = Counter()
    ticker_ciks: dict[str, int] = {}
    warehouse_uri = f"file:{Path(prior.base.framework.WAREHOUSE).resolve().as_posix()}?mode=ro&immutable=1"
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
        fx_oci_facts = _raw_annual_facts(usgaap, FX_OCI_TAGS, unit="USD")
        revenue_facts = _raw_annual_facts(usgaap, REVENUE_TAGS, unit="USD")
        hedge_facts = _raw_annual_facts(usgaap, HEDGE_CONFIRMATION_TAGS, unit="USD")
        if not fx_oci_facts:
            stats["tickers_missing_raw_annual_fx_oci"] += 1
            continue
        if not revenue_facts:
            stats["tickers_missing_raw_annual_revenue"] += 1
            continue
        if not hedge_facts:
            stats["tickers_missing_raw_annual_hedge_oci"] += 1
            continue
        index[ticker] = {
            "fx_oci": fx_oci_facts,
            "revenue": revenue_facts,
            "hedge_oci": hedge_facts,
        }
        stats["tickers_with_fx_revenue_and_hedge_oci"] += 1
        stats["raw_annual_fx_oci_fact_count"] += len(fx_oci_facts)
        stats["raw_annual_revenue_fact_count"] += len(revenue_facts)
        stats["raw_annual_hedge_oci_fact_count"] += len(hedge_facts)

    summary = {
        "raw_companyfacts_cache": _repo_rel(RAW_COMPANYFACTS_CACHE),
        "fx_oci_tags": list(FX_OCI_TAGS),
        "hedge_confirmation_tags": list(HEDGE_CONFIRMATION_TAGS),
        "revenue_tags": list(REVENUE_TAGS),
        "warehouse_source": _repo_rel(prior.base.framework.WAREHOUSE),
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


def _same_period_hedge_confirmation(
    *,
    asof: str,
    current_period_end: str,
    current_revenue: float,
    facts: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    hedge = prior._latest_period_fact(facts["hedge_oci"], asof=asof, end=current_period_end)
    if hedge is None:
        return None
    if prior.base._days_between(asof, hedge["filed"]) > MAX_ANNUAL_FACT_AGE_DAYS:
        return None
    hedge_value = float(hedge["value"])
    hedge_to_revenue = hedge_value / current_revenue if current_revenue else 0.0
    if hedge_to_revenue < MIN_HEDGE_OCI_TO_REVENUE:
        return None
    return {
        "hedge_oci_filed": hedge["filed"],
        "hedge_oci_tag": hedge["tag"],
        "hedge_oci": _round(hedge_value, 2),
        "hedge_oci_to_revenue": _round(hedge_to_revenue, 6),
        "hedge_oci_fact_age_days": prior.base._days_between(asof, hedge["filed"]),
    }


def _fx_oci_hedge_observation(
    ticker: str,
    asof: str,
    facts: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    fx = prior._fx_oci_observation(ticker, asof, facts)
    if fx is None:
        return None
    hedge = _same_period_hedge_confirmation(
        asof=asof,
        current_period_end=str(fx["current_fiscal_year_end"]),
        current_revenue=float(fx["current_revenue"] or 0.0),
        facts=facts,
    )
    if hedge is None:
        return None
    return {**fx, **hedge}


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, dict[str, list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indices = {
        ticker: prior.base.framework.shadow._row_index(prior.base.framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    dates = prior.base.framework.shadow._trading_dates(snapshot)
    window_dates = [day for day in dates if str(cfg["start"]) <= day <= str(cfg["end"])]
    eligible = sorted(set(quality_index) & set(snapshot))
    scan: Counter[str] = Counter()
    scan["scanned_trading_days"] = len(window_dates)
    scan["eligible_quality_tickers"] = len(eligible)
    candidates: list[dict[str, Any]] = []
    for signal_date in window_dates:
        for ticker in eligible:
            scan["ticker_day_evaluations"] += 1
            quality = _fx_oci_hedge_observation(ticker, signal_date, quality_index[ticker])
            if quality is None:
                scan["failed_fx_oci_or_hedge_gate"] += 1
                continue
            confirm = prior.base._price_confirmation(
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
                5.00 * min(float(quality["fx_oci_improvement_to_revenue"] or 0.0), 0.03)
                + 2.00 * min(float(quality["current_fx_oci_to_revenue"] or 0.0), 0.02)
                + 2.00 * min(float(quality["hedge_oci_to_revenue"] or 0.0), 0.02)
                + 0.25 * max(min(float(quality["revenue_growth"] or 0.0), 0.80), -0.05)
                + 0.50 * float(confirm["candidate_ret20_excess_spy"])
                + 0.13 * float(confirm["candidate_ret60_excess_spy"])
                + 0.10 * float(confirm["candidate_close_location"])
                + 0.035
                * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
            )
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "RAW_SEC_FX_OCI_HEDGE_CONFIRMED_PAPER",
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
            -float(row["quality_hedge_oci_to_revenue"] or 0.0),
            -float(row["quality_fx_oci_improvement_to_revenue"] or 0.0),
            -float(row["quality_current_fx_oci_to_revenue"] or 0.0),
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
        "min_revenue_growth": MIN_REVENUE_GROWTH,
        "min_current_fx_oci_usd": MIN_CURRENT_FX_OCI_USD,
        "min_current_fx_oci_to_revenue": MIN_CURRENT_FX_OCI_TO_REVENUE,
        "min_fx_oci_improvement_to_revenue": MIN_FX_OCI_IMPROVEMENT_TO_REVENUE,
        "min_hedge_oci_to_revenue": MIN_HEDGE_OCI_TO_REVENUE,
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = prior.base.framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    ev_delta = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if ev_delta <= prior.base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_compression_ev_not_beaten")
    if pnl_delta <= prior.base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_compression_pnl_not_beaten")
    if ev_delta <= prior.base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_distribution_ev_not_beaten")
    if pnl_delta <= prior.base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_distribution_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["accepted_compression_comparator"] = prior.base.COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = prior.base.DISTRIBUTION_COMPARATOR
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_not_promoted_fx_oci_hedge_confirmation"
        if gate["passed"]
        else "rejected_fx_oci_hedge_confirmation_candidate_pool"
    )
    return gate


def _configure_prior() -> None:
    prior.EXPERIMENT_ID = EXPERIMENT_ID
    prior.STEM = STEM
    prior.TRIAL_FAMILY = TRIAL_FAMILY
    prior.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    prior.CHANGED_VARIABLE = CHANGED_VARIABLE
    prior.RULE_VERSION = RULE_VERSION
    prior.OWNER = OWNER
    prior.OUT_DIR = OUT_DIR
    prior.OUT_JSON = OUT_JSON
    prior.LOG_JSON = LOG_JSON
    prior.TICKET_JSON = TICKET_JSON
    prior.CARD_MD = CARD_MD
    prior.MANIFEST_JSON = MANIFEST_JSON
    prior.EXPERIMENT_LOG = EXPERIMENT_LOG
    prior.REGISTRY_JSON = REGISTRY_JSON
    prior.PREDICTION = PREDICTION
    prior.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    prior.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    prior._RAW_INDEX_CACHE = None
    prior._build_quality_index = _build_quality_index
    prior._candidate_rows_for_window = _candidate_rows_for_window
    prior._gate4 = _gate4
    prior._configure_base()


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    status = "observed_only_positive_replay_lead" if gate4["passed"] else "rejected"
    failed_text = ", ".join(gate4.get("failed_reasons") or []) or "none"
    if gate4["passed"]:
        interpretation = (
            "The raw SEC FX OCI tailwind with cash-flow/derivative hedge "
            "confirmation cleared the numeric three-window replay screen, but "
            "remains only a replay lead because no shared daily/backtest helper "
            "was promoted."
        )
    else:
        interpretation = (
            "The raw SEC FX OCI tailwind with hedge confirmation did not clear "
            f"Gate 4 (failed: {failed_text}). It is not retained or promoted."
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
            "mechanism_family": "production_visible_free_sec_companyfacts_oci_component_candidate_pool",
            "new_evidence_type": "raw_sec_cash_flow_derivative_hedge_oci_confirmation_component",
            "nearby_prior_experiments": [
                "exp-20260620-026",
                "exp-20260617-018",
                "exp-20260620-023",
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
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "annual_duration_min": ANNUAL_DURATION_MIN,
        "annual_duration_max": ANNUAL_DURATION_MAX,
        "max_annual_fact_age_days": MAX_ANNUAL_FACT_AGE_DAYS,
        "min_current_revenue": MIN_CURRENT_REVENUE,
        "min_revenue_growth": MIN_REVENUE_GROWTH,
        "min_current_fx_oci_usd": MIN_CURRENT_FX_OCI_USD,
        "min_current_fx_oci_to_revenue": MIN_CURRENT_FX_OCI_TO_REVENUE,
        "min_fx_oci_improvement_to_revenue": MIN_FX_OCI_IMPROVEMENT_TO_REVENUE,
        "min_hedge_oci_to_revenue": MIN_HEDGE_OCI_TO_REVENUE,
        "fx_oci_tags": list(FX_OCI_TAGS),
        "hedge_confirmation_tags": list(HEDGE_CONFIRMATION_TAGS),
        "revenue_tags": list(REVENUE_TAGS),
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["execution_model"] = (
        "Annual FX-translation OCI, same-period cash-flow/derivative hedge OCI "
        "components, and annual revenue are read from raw SEC Companyfacts tags "
        "known only by filed date (<= signal date). The fixed exp-026 FX "
        "tailwind gate is retained, and the same annual period must also have "
        "non-adverse hedge OCI/reclassification confirmation. Price confirmation "
        "uses only signal-date OHLCV. Paper entry is next available open and "
        "exit is the close 10 trading days after the signal with standard costs."
    )
    payload["backtest_protocol"]["companyfacts_source"] = _repo_rel(RAW_COMPANYFACTS_CACHE)
    payload["gate2"]["runtime_fields"] = [
        "raw SEC companyfacts annual foreign-currency translation OCI component facts",
        "raw SEC companyfacts annual cash-flow/derivative hedge OCI component facts",
        "raw SEC companyfacts annual revenue facts",
        "raw SEC companyfacts filed date and period end",
        "warehouse ticker_universe CIK mapping",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
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
    payload["next_evidence_needed"] = (
        "Do not retry by sweeping hedge tag lists, hedge sign threshold, FX OCI "
        "ratio/improvement, revenue, fact freshness, RS/close/volume/vol guards, "
        "top-N, hold, cooldown, or notional on frozen windows. A valid retry "
        "needs segment/currency revenue mix, FX sensitivity disclosure, closed "
        "forward replacement-value rows, or a shared helper promotion if this "
        "lead remains positive."
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
            "Do not retry by sweeping hedge tag lists, hedge sign threshold, FX "
            "OCI ratio/improvement, revenue, fact freshness, RS/close/volume/"
            "vol guards, top-N, hold days, cooldown, or notional on these frozen "
            "windows."
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
    for label in prior.base.framework.WINDOWS:
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
            f"# {EXPERIMENT_ID} FX OCI Hedge Confirmation",
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
            "- Aggregate EV delta: `{:+.4f}`".format(aggregate["expected_value_score_delta_sum"]),
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Accepted compression comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                prior.base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"],
                prior.base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Accepted distribution comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                prior.base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"],
                prior.base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"],
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
        "accepted_compression_comparator": prior.base.COMPRESSION_COMPARATOR,
        "accepted_distribution_comparator": prior.base.DISTRIBUTION_COMPARATOR,
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label]["expected_value_score"],
                "expected_value_after": payload["after_metrics"][label]["expected_value_score"],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label]["expected_value_score"],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label]["total_pnl"],
                "eligible_quality_tickers": payload["context_scan_by_window"][label].get("eligible_quality_tickers"),
                "raw_candidate_count": payload["raw_candidate_counts"][label],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in prior.base.framework.WINDOWS
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
            _repo_rel(Path(__file__)): prior.base.framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): prior.base.framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): prior.base.framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): prior.base.framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): prior.base.framework._sha256(CARD_MD),
        },
    }
    prior.base.framework._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    prior.base.framework._write_json(OUT_JSON, payload)
    prior.base.framework._write_json(LOG_JSON, payload)
    prior.base.framework._write_text(CARD_MD, _build_card(payload))
    prior.base.framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
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
        "aggregate_strategy_total_pnl_delta": log_record["aggregate_strategy_total_pnl_delta"],
    }
    prior.base.persist_self_registered_result(
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
    _configure_prior()
    payload = _postprocess_payload(prior.base._build_payload())
    _persist(payload)
    print(json.dumps(prior.base.framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
