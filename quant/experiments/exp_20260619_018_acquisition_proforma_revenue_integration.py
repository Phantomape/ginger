"""exp-20260619-018: acquisition pro-forma revenue integration scout.

Replay-only alpha search. The single decision hypothesis is a PIT free SEC
Companyfacts candidate source: production-universe names whose filed business
acquisition pro-forma revenue is material versus current annual revenue while
the same pro-forma disclosure shows non-negative income, paired with liquid
SPY-relative price confirmation, may identify acquisition integration growth
candidates before a next-open 10-trading-day continuation leg.

This is deliberately private replay first because the raw acquisition pro-forma
field shape is not yet a shared historical/daily contract. A positive replay is
only a lead until a shared default-off helper reproduces the same filed-date PIT
mapping in both historical and daily production paths. No production code, run
adapter, backtester adapter, ranking, sizing, exits, orders, LLM/news path, or
watchlist behavior is changed. No JavaScript is used.
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

EXPERIMENT_ID = "exp-20260619-018"
STEM = "acquisition_proforma_revenue_integration"
TRIAL_FAMILY = "acquisition_proforma_revenue_integration_candidate_pool"
TRIAL_VARIANT_ID = "acquisition_proforma_revenue_integration_top1_next_open_10d_v1"
CHANGED_VARIABLE = "raw_sec_companyfacts_acquisition_proforma_revenue_integration_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
RAW_COMPANYFACTS_CACHE = REPO_ROOT / "data" / "cache" / "sec" / "companyfacts"
BASELINE_RESULT_JSON = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260619_018_{STEM}.json"
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

MIN_PROFORMA_DURATION_DAYS = 60
MAX_PROFORMA_DURATION_DAYS = 430
FY_DURATION_MIN = template.FY_DURATION_MIN
FY_DURATION_MAX = template.FY_DURATION_MAX
MAX_PROFORMA_FACT_AGE_DAYS = 540
MAX_REVENUE_FACT_AGE_DAYS = 500
MIN_CURRENT_REVENUE = 300_000_000.0
MIN_ANNUALIZED_PROFORMA_REVENUE = 150_000_000.0
MIN_PROFORMA_REVENUE_TO_CURRENT_REVENUE = 0.05
MAX_PROFORMA_REVENUE_TO_CURRENT_REVENUE = 3.00
MIN_PROFORMA_INCOME_MARGIN = 0.00
MIN_REVENUE_GROWTH = -0.10
MAX_OPTIONAL_DEAL_COST_TO_PROFORMA_REVENUE = 0.40

PROFORMA_REVENUE_TAGS = ("BusinessAcquisitionsProFormaRevenue",)
PROFORMA_INCOME_TAGS = ("BusinessAcquisitionsProFormaNetIncomeLoss",)
ACQUISITION_PAYMENT_TAGS = ("PaymentsToAcquireBusinessesNetOfCashAcquired",)
ACQUIRED_NET_ASSET_TAGS = (
    "BusinessCombinationRecognizedIdentifiableAssetsAcquiredAndLiabilitiesAssumedNet",
)
ACQUISITION_COST_TAGS = (
    "BusinessCombinationAcquisitionRelatedCosts",
    "BusinessAcquisitionCostOfAcquiredEntityTransactionCosts",
)
REVENUE_TAGS = template.REVENUE_TAGS

PREDICTION = {
    "success_probability": 0.15,
    "expected_ev_delta": 0.20,
    "expected_pnl_delta": 3000.0,
    "main_failure_modes": [
        "acquisition_tags_stale_or_noisy",
        "same_period_income_coverage_too_sparse",
        "window_regression",
        "drawdown_drift",
        "target_concentration_failed",
        "accepted_distribution_not_beaten",
    ],
    "confidence_reason": (
        "Recent raw Companyfacts scouts found positive but not accepted leads in "
        "financing relief and public-counterparty relation fields. The playbook "
        "requires materially new business context such as acquisition integration "
        "economics rather than another generic balance-sheet or profitability "
        "threshold. This uses structured pro-forma acquisition revenue and "
        "same-period pro-forma income, which is a distinct free SEC/XBRL data "
        "surface with enough liquid-universe coverage for a private scout."
    ),
    "recorded_at": "2026-06-19T19:45:00+00:00",
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
    "uses_free_ohlcv": True,
    "uses_llm": False,
    "execution_envelope": {
        **base.PRODUCTION_IMPACT["execution_envelope"],
        "failure_handling": (
            "missing raw SEC business-acquisition pro-forma revenue, missing "
            "same-period pro-forma net income/loss, missing annual revenue pair, "
            "stale facts, malformed duration, missing CIK mapping, missing "
            "OHLCV, missing next open, or missing 10d exit rejects the paper "
            "candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same raw "
        "SEC BusinessAcquisitionsProFormaRevenue and "
        "BusinessAcquisitionsProFormaNetIncomeLoss filed-date PIT mapping, "
        "annualized pro-forma revenue ratio, liquid SPY-relative confirmation, "
        "cooldown, next-open paper entry, 10-day exit, costs, and concentration "
        "controls in both historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: raw SEC Companyfacts business-acquisition pro-forma "
        "revenue that is material versus the issuer's latest annual revenue, "
        "paired with same-period non-negative pro-forma income and liquid "
        "SPY-relative leadership, may identify acquisition integration growth "
        "candidates before a 10-trading-day continuation leg."
    ),
    "2_history_check": {
        "exp-20260619-003": (
            "Rejected customer concentration anchor-demand with zero target "
            "trades. This run uses acquisition pro-forma financial statement "
            "facts, not customer/supplier concentration percentages."
        ),
        "exp-20260619-004": (
            "Rejected component-inventory mix despite positive aggregate result "
            "because window, drawdown, concentration, and comparator gates "
            "failed. This run is not inventory or working-capital quality."
        ),
        "exp-20260619-005": (
            "Rejected debt maturity cliff relief despite positive aggregate "
            "evidence because window/concentration/comparator gates failed. "
            "This run uses acquisition integration economics, not financing "
            "maturity relief."
        ),
        "exp-20260619-017": (
            "Rejected public-counterparty relation even with positive aggregate "
            "EV/PnL because mid_weak regressed and distribution comparator was "
            "not beaten. This run uses numeric acquisition pro-forma income "
            "statement facts rather than 8-K counterparty text."
        ),
        "novelty_gate": (
            "Reservation initially found generic Companyfacts near-neighbors; "
            "the override recorded the new evidence axis as structured SEC "
            "BusinessAcquisitionsProFormaRevenue plus same-period "
            "BusinessAcquisitionsProFormaNetIncomeLoss acquisition integration "
            "economics, not asset growth, debt, customer concentration, "
            "amortization, or generic Companyfacts threshold retuning."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL must "
        "be positive, no unacceptable drawdown/survival/concentration "
        "degradation, at least 20 paper trades with all three windows "
        "represented, and accepted compression/distribution candidate-pool "
        "comparators must be beaten. Replay-only positives are leads until "
        "shared daily/backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260619_018_acquisition_proforma_revenue_integration.py"
    ),
}

_RAW_INDEX_CACHE: tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return base._round(value, digits)


def _duration_usd_facts(
    usgaap: dict[str, Any],
    tags: tuple[str, ...],
    *,
    allow_negative: bool = False,
) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for tag in tags:
        tag_payload = usgaap.get(tag) or {}
        for raw in tag_payload.get("units", {}).get("USD", []):
            duration = template._duration_days(raw)
            if duration is None or not (MIN_PROFORMA_DURATION_DAYS <= duration <= MAX_PROFORMA_DURATION_DAYS):
                continue
            filed = str(raw.get("filed") or "")[:10]
            start = str(raw.get("start") or "")[:10]
            end = str(raw.get("end") or "")[:10]
            value = template._float_or_none(raw.get("val"))
            if not filed or not start or not end or value is None or not math.isfinite(value):
                continue
            if not allow_negative and value <= 0.0:
                continue
            annualized_value = float(value) * 365.25 / max(float(duration), 1.0)
            facts.append(
                {
                    "filed": filed,
                    "start": start,
                    "end": end,
                    "value": float(value),
                    "annualized_value": annualized_value,
                    "tag": tag,
                    "form": str(raw.get("form") or ""),
                    "fy": raw.get("fy"),
                    "fp": str(raw.get("fp") or ""),
                    "duration_days": duration,
                    "accn": str(raw.get("accn") or ""),
                }
            )
    facts.sort(key=lambda row: (row["end"], row["filed"], row["tag"], row["value"], row["accn"]))
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
        proforma_revenue = _duration_usd_facts(usgaap, PROFORMA_REVENUE_TAGS)
        proforma_income = _duration_usd_facts(
            usgaap,
            PROFORMA_INCOME_TAGS,
            allow_negative=True,
        )
        revenue = template._raw_annual_facts(usgaap, REVENUE_TAGS)
        if not proforma_revenue:
            stats["tickers_missing_proforma_revenue"] += 1
            continue
        if not proforma_income:
            stats["tickers_missing_proforma_income"] += 1
            continue
        if not revenue:
            stats["tickers_missing_raw_annual_revenue"] += 1
            continue
        acquisition_payment = _duration_usd_facts(usgaap, ACQUISITION_PAYMENT_TAGS)
        acquired_net_assets = _duration_usd_facts(
            usgaap,
            ACQUIRED_NET_ASSET_TAGS,
            allow_negative=True,
        )
        acquisition_cost = _duration_usd_facts(usgaap, ACQUISITION_COST_TAGS)
        for fact in proforma_revenue + proforma_income + acquisition_payment + acquisition_cost:
            tag_counts[fact["tag"]] += 1
        index[ticker] = {
            "proforma_revenue": proforma_revenue,
            "proforma_income": proforma_income,
            "revenue": revenue,
            "acquisition_payment": acquisition_payment,
            "acquired_net_assets": acquired_net_assets,
            "acquisition_cost": acquisition_cost,
        }
        stats["tickers_with_proforma_income_statement_and_revenue"] += 1
        stats["raw_proforma_revenue_fact_count"] += len(proforma_revenue)
        stats["raw_proforma_income_fact_count"] += len(proforma_income)
        stats["raw_annual_revenue_fact_count"] += len(revenue)
        stats["raw_acquisition_payment_fact_count"] += len(acquisition_payment)
        stats["raw_acquired_net_asset_fact_count"] += len(acquired_net_assets)
        stats["raw_acquisition_cost_fact_count"] += len(acquisition_cost)

    summary = {
        "raw_companyfacts_cache": _repo_rel(RAW_COMPANYFACTS_CACHE),
        "proforma_revenue_tags": list(PROFORMA_REVENUE_TAGS),
        "proforma_income_tags": list(PROFORMA_INCOME_TAGS),
        "acquisition_payment_tags": list(ACQUISITION_PAYMENT_TAGS),
        "acquired_net_asset_tags": list(ACQUIRED_NET_ASSET_TAGS),
        "acquisition_cost_tags": list(ACQUISITION_COST_TAGS),
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
        "field_source": "raw_sec_companyfacts_cache_acquisition_proforma_income_statement",
    }


def _latest_period_fact(
    facts: list[dict[str, Any]],
    *,
    asof: str,
    end: str | None = None,
    before_end: str | None = None,
) -> dict[str, Any] | None:
    candidates = [
        fact
        for fact in facts
        if fact["filed"] <= asof
        and (end is None or fact["end"] == end)
        and (before_end is None or fact["end"] < before_end)
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda fact: (
            str(fact["end"]),
            str(fact["filed"]),
            float(fact.get("annualized_value", fact["value"]) or 0.0),
            str(fact.get("accn") or ""),
            str(fact["tag"]),
        ),
    )


def _optional_latest_same_end(
    facts: list[dict[str, Any]],
    *,
    asof: str,
    end: str,
) -> dict[str, Any] | None:
    same_end = _latest_period_fact(facts, asof=asof, end=end)
    if same_end is not None:
        return same_end
    return None


def _annual_revenue_pair(
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


def _acquisition_observation(
    ticker: str,
    asof: str,
    facts: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    proforma_revenue = _latest_period_fact(facts["proforma_revenue"], asof=asof)
    if proforma_revenue is None:
        return None
    if base._days_between(asof, proforma_revenue["filed"]) > MAX_PROFORMA_FACT_AGE_DAYS:
        return None

    proforma_income = _optional_latest_same_end(
        facts["proforma_income"],
        asof=asof,
        end=proforma_revenue["end"],
    )
    if proforma_income is None:
        return None
    if base._days_between(asof, proforma_income["filed"]) > MAX_PROFORMA_FACT_AGE_DAYS:
        return None

    revenue_pair = _annual_revenue_pair(facts, asof=asof)
    if revenue_pair is None:
        return None
    current_revenue, prior_revenue = revenue_pair
    if base._days_between(asof, current_revenue["filed"]) > MAX_REVENUE_FACT_AGE_DAYS:
        return None

    proforma_revenue_value = float(proforma_revenue["value"])
    annualized_proforma_revenue = float(proforma_revenue["annualized_value"])
    annualized_proforma_income = float(proforma_income["annualized_value"])
    current_revenue_value = float(current_revenue["value"])
    prior_revenue_value = float(prior_revenue["value"])
    if (
        annualized_proforma_revenue < MIN_ANNUALIZED_PROFORMA_REVENUE
        or current_revenue_value < MIN_CURRENT_REVENUE
        or prior_revenue_value <= 0.0
        or annualized_proforma_revenue <= 0.0
    ):
        return None

    proforma_income_margin = annualized_proforma_income / annualized_proforma_revenue
    if proforma_income_margin < MIN_PROFORMA_INCOME_MARGIN:
        return None

    proforma_revenue_to_current_revenue = annualized_proforma_revenue / current_revenue_value
    if proforma_revenue_to_current_revenue < MIN_PROFORMA_REVENUE_TO_CURRENT_REVENUE:
        return None
    if proforma_revenue_to_current_revenue > MAX_PROFORMA_REVENUE_TO_CURRENT_REVENUE:
        return None

    revenue_growth = current_revenue_value / prior_revenue_value - 1.0
    if revenue_growth < MIN_REVENUE_GROWTH:
        return None

    acquisition_cost = _optional_latest_same_end(
        facts["acquisition_cost"],
        asof=asof,
        end=proforma_revenue["end"],
    )
    acquisition_cost_to_revenue = None
    if acquisition_cost is not None:
        acquisition_cost_to_revenue = (
            float(acquisition_cost["annualized_value"]) / annualized_proforma_revenue
        )
        if acquisition_cost_to_revenue > MAX_OPTIONAL_DEAL_COST_TO_PROFORMA_REVENUE:
            return None

    acquisition_payment = _optional_latest_same_end(
        facts["acquisition_payment"],
        asof=asof,
        end=proforma_revenue["end"],
    )
    acquired_net_assets = _optional_latest_same_end(
        facts["acquired_net_assets"],
        asof=asof,
        end=proforma_revenue["end"],
    )
    acquisition_payment_to_revenue = (
        None
        if acquisition_payment is None
        else float(acquisition_payment["annualized_value"]) / annualized_proforma_revenue
    )
    acquired_net_assets_to_revenue = (
        None
        if acquired_net_assets is None
        else float(acquired_net_assets["annualized_value"]) / annualized_proforma_revenue
    )
    proforma_duration_years = float(proforma_revenue["duration_days"]) / 365.25
    integration_score_component = (
        min(proforma_revenue_to_current_revenue, 1.25)
        + 0.75 * min(max(proforma_income_margin, 0.0), 0.30)
        + 0.35 * min(max(revenue_growth, -0.10), 0.75)
        + 0.08 * min(max(proforma_duration_years - 0.25, 0.0), 0.75)
    )

    return {
        "ticker": ticker,
        "proforma_period_start": proforma_revenue["start"],
        "proforma_period_end": proforma_revenue["end"],
        "proforma_revenue_filed": proforma_revenue["filed"],
        "proforma_income_filed": proforma_income["filed"],
        "proforma_revenue_tag": proforma_revenue["tag"],
        "proforma_income_tag": proforma_income["tag"],
        "proforma_form": proforma_revenue["form"],
        "proforma_fp": proforma_revenue["fp"],
        "proforma_duration_days": proforma_revenue["duration_days"],
        "proforma_revenue": _round(proforma_revenue_value, 2),
        "annualized_proforma_revenue": _round(annualized_proforma_revenue, 2),
        "annualized_proforma_income": _round(annualized_proforma_income, 2),
        "proforma_income_margin": _round(proforma_income_margin, 6),
        "proforma_revenue_to_current_revenue": _round(proforma_revenue_to_current_revenue, 6),
        "current_revenue_end": current_revenue["end"],
        "prior_revenue_end": prior_revenue["end"],
        "current_revenue_filed": current_revenue["filed"],
        "current_revenue_tag": current_revenue["tag"],
        "current_revenue": _round(current_revenue_value, 2),
        "prior_revenue": _round(prior_revenue_value, 2),
        "revenue_growth": _round(revenue_growth, 6),
        "proforma_fact_age_days": base._days_between(asof, proforma_revenue["filed"]),
        "revenue_fact_age_days": base._days_between(asof, current_revenue["filed"]),
        "acquisition_cost_to_proforma_revenue": _round(acquisition_cost_to_revenue, 6),
        "acquisition_payment_to_proforma_revenue": _round(acquisition_payment_to_revenue, 6),
        "acquired_net_assets_to_proforma_revenue": _round(acquired_net_assets_to_revenue, 6),
        "integration_score_component": _round(integration_score_component, 6),
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
            quality = _acquisition_observation(ticker, signal_date, quality_index[ticker])
            if quality is None:
                scan["failed_acquisition_integration_gate"] += 1
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
                1.00 * float(quality["integration_score_component"] or 0.0)
                + 0.30 * min(float(quality["proforma_revenue_to_current_revenue"] or 0.0), 1.5)
                + 0.20 * min(float(quality["proforma_income_margin"] or 0.0), 0.35)
                + 0.45 * float(confirm["candidate_ret20_excess_spy"])
                + 0.15 * float(confirm["candidate_ret60_excess_spy"])
                + 0.10 * float(confirm["candidate_close_location"])
                + 0.030
                * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
            )
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "RAW_SEC_ACQUISITION_PROFORMA_REVENUE_INTEGRATION_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": (
                        "raw_companyfacts_acquisition_proforma_filed_and_signal_"
                        "close_before_next_open_paper_entry"
                    ),
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_companyfacts": True,
                    "uses_raw_sec_companyfacts_cache": True,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    **{f"acq_{key}": value for key, value in quality.items()},
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
            -float(row["acq_proforma_revenue_to_current_revenue"] or 0.0),
            -float(row["acq_proforma_income_margin"] or 0.0),
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
        "min_proforma_duration_days": MIN_PROFORMA_DURATION_DAYS,
        "max_proforma_duration_days": MAX_PROFORMA_DURATION_DAYS,
        "max_proforma_fact_age_days": MAX_PROFORMA_FACT_AGE_DAYS,
        "max_revenue_fact_age_days": MAX_REVENUE_FACT_AGE_DAYS,
        "min_current_revenue": MIN_CURRENT_REVENUE,
        "min_annualized_proforma_revenue": MIN_ANNUALIZED_PROFORMA_REVENUE,
        "min_proforma_revenue_to_current_revenue": MIN_PROFORMA_REVENUE_TO_CURRENT_REVENUE,
        "max_proforma_revenue_to_current_revenue": MAX_PROFORMA_REVENUE_TO_CURRENT_REVENUE,
        "min_proforma_income_margin": MIN_PROFORMA_INCOME_MARGIN,
        "min_revenue_growth": MIN_REVENUE_GROWTH,
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
        "positive_replay_lead_not_promoted_acquisition_proforma_revenue_integration"
        if gate["passed"]
        else "rejected_acquisition_proforma_revenue_integration_candidate_pool"
    )
    return gate


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
            if key not in baseline:
                continue
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
            sum(float(row["expected_value_score"]) for row in dynamic_before.values()),
            4,
        ),
        "standard_baseline_ev_sum": baseline_ev,
        "dynamic_baseline_pnl_sum": round(
            sum(float(row["total_pnl"]) for row in dynamic_before.values()),
            2,
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
    payload = _normalize_payload_to_standard_baseline(payload)
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    if gate4["passed"]:
        interpretation = (
            "The acquisition pro-forma revenue integration source cleared the "
            "numeric three-window replay screen, but remains only a replay lead "
            "because no shared daily/backtest helper was promoted."
        )
    else:
        interpretation = (
            "The acquisition pro-forma revenue integration source did not clear "
            f"Gate 4 (failed: {', '.join(gate4['failed_reasons']) or 'none'}). "
            "It is not retained or promoted."
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
            "mechanism_family": "production_visible_free_sec_companyfacts_acquisition_integration_candidate_pool",
            "new_evidence_type": "raw_sec_companyfacts_acquisition_proforma_revenue_and_income",
            "nearby_prior_experiments": [
                "exp-20260619-003",
                "exp-20260619-004",
                "exp-20260619-005",
                "exp-20260619-017",
                "exp-20260619-018_novelty_override",
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
        "base_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "min_proforma_duration_days": MIN_PROFORMA_DURATION_DAYS,
        "max_proforma_duration_days": MAX_PROFORMA_DURATION_DAYS,
        "max_proforma_fact_age_days": MAX_PROFORMA_FACT_AGE_DAYS,
        "max_revenue_fact_age_days": MAX_REVENUE_FACT_AGE_DAYS,
        "min_current_revenue": MIN_CURRENT_REVENUE,
        "min_annualized_proforma_revenue": MIN_ANNUALIZED_PROFORMA_REVENUE,
        "min_proforma_revenue_to_current_revenue": MIN_PROFORMA_REVENUE_TO_CURRENT_REVENUE,
        "max_proforma_revenue_to_current_revenue": MAX_PROFORMA_REVENUE_TO_CURRENT_REVENUE,
        "min_proforma_income_margin": MIN_PROFORMA_INCOME_MARGIN,
        "min_revenue_growth": MIN_REVENUE_GROWTH,
        "max_optional_deal_cost_to_proforma_revenue": MAX_OPTIONAL_DEAL_COST_TO_PROFORMA_REVENUE,
        "proforma_revenue_tags": list(PROFORMA_REVENUE_TAGS),
        "proforma_income_tags": list(PROFORMA_INCOME_TAGS),
        "acquisition_payment_tags": list(ACQUISITION_PAYMENT_TAGS),
        "acquired_net_asset_tags": list(ACQUIRED_NET_ASSET_TAGS),
        "acquisition_cost_tags": list(ACQUISITION_COST_TAGS),
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
        "Business-acquisition pro-forma revenue and net income/loss are read "
        "from raw SEC Companyfacts duration facts and known only by filed date "
        "(<= signal date). Pro-forma values are annualized by their reported "
        "duration and compared against the latest annual revenue pair. The rule "
        "requires material annualized pro-forma revenue, same-period "
        "non-negative pro-forma income margin, non-contracting revenue, and "
        "signal-date liquid SPY-relative price confirmation. Paper entry is the "
        "next available open with existing entry slippage; exit is the close 10 "
        "trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    payload["backtest_protocol"]["companyfacts_source"] = _repo_rel(RAW_COMPANYFACTS_CACHE)
    payload["gate2"]["runtime_fields"] = [
        "raw SEC companyfacts BusinessAcquisitionsProFormaRevenue facts",
        "raw SEC companyfacts BusinessAcquisitionsProFormaNetIncomeLoss facts",
        "raw SEC companyfacts optional acquisition cost/payment/net asset facts",
        "raw SEC companyfacts annual revenue facts",
        "raw SEC companyfacts filed date and period end",
        "warehouse ticker_universe CIK mapping",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A retry needs materially richer PIT acquisition evidence such as parsed "
        "deal terms, purchase accounting fair-value marks, identifiable synergy "
        "realization, customer retention after acquisition, or closed forward "
        "replacement-value rows. Do not sweep pro-forma revenue ratio, income "
        "margin, fact freshness, duration buckets, revenue floor, price guards, "
        "top-N, hold, cooldown, or notional on these frozen windows."
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
            "Do not retry by sweeping acquisition pro-forma revenue/income "
            "thresholds, annualization duration, revenue floor, fact freshness, "
            "RS/close/volume/vol guards, top-N, hold days, cooldown, or notional "
            "on these frozen windows."
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
            f"# {EXPERIMENT_ID} Acquisition Pro-Forma Revenue Integration",
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
