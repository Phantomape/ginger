"""exp-20260616-023: bad-debt allowance burden improvement scout.

Replay-only alpha search. The single decision hypothesis is a PIT free SEC
Companyfacts candidate source: production-universe names whose allowance for
doubtful accounts is falling as a share of receivables, while revenue is not
contracting and liquid SPY-relative leadership confirms demand. This tests
collection-quality normalization that is materially different from the rejected
raw receivables DSO scout.

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


EXPERIMENT_ID = "exp-20260616-023"
STEM = "allowance_doubtful_accounts_quality"
TRIAL_FAMILY = "allowance_doubtful_accounts_quality_candidate_pool"
TRIAL_VARIANT_ID = "allowance_doubtful_accounts_quality_top1_next_open_10d_v1"
CHANGED_VARIABLE = "allowance_for_doubtful_accounts_burden_improvement_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
RAW_COMPANYFACTS_CACHE = REPO_ROOT / "data" / "cache" / "sec" / "companyfacts"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260616_023_{STEM}.json"
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
MIN_CURRENT_RECEIVABLES = 25_000_000.0
MIN_CURRENT_ALLOWANCE = 1_000_000.0
MIN_CURRENT_ALLOWANCE_TO_RECEIVABLES = 0.002
MAX_CURRENT_ALLOWANCE_TO_RECEIVABLES = 0.12
MIN_ALLOWANCE_RATIO_IMPROVEMENT = 0.0015
MIN_REVENUE_GROWTH = 0.0
MAX_RECEIVABLES_GROWTH_VS_REVENUE_GROWTH = 0.50

ALLOWANCE_TAGS = (
    "AllowanceForDoubtfulAccountsReceivableCurrent",
    "AllowanceForDoubtfulAccountsReceivable",
    "FinancingReceivableAllowanceForCreditLosses",
)
RECEIVABLES_TAGS = (
    "AccountsReceivableNetCurrent",
    "AccountsReceivableCurrent",
    "AccountsReceivableNet",
)
REVENUE_TAGS = rd.REVENUE_TAGS

PREDICTION = {
    "success_probability": 0.12,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "field_coverage_too_thin",
        "window_ev_regression",
        "accepted_comparator_not_beaten",
        "receivables_family_still_noise",
        "reserve_reduction_underwriting_not_quality",
    ],
    "confidence_reason": (
        "exp-20260616-021 rejected raw annual DSO but explicitly required "
        "materially different collection-quality evidence such as allowance or "
        "write-off normalization. The raw Companyfacts coverage check found "
        "broad allowance tag availability, but the economic interpretation is "
        "low-confidence because falling reserves can also mean under-reserving."
    ),
    "recorded_at": "2026-06-16T20:04:38+00:00",
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
            "missing raw SEC allowance, receivables, or annual revenue facts; "
            "missing matching fiscal-year ends; stale facts; missing CIK "
            "mapping; missing OHLCV; missing next open; or missing 10d exit "
            "rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same raw "
        "SEC allowance, receivables, and revenue filed-date PIT mapping, "
        "allowance-burden improvement gate, liquid SPY-relative confirmation, "
        "cooldown, next-open paper entry, 10-day exit, costs, and concentration "
        "controls in both historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: raw SEC Companyfacts allowance for doubtful accounts "
        "falling as a share of receivables, with non-declining revenue and "
        "liquid SPY-relative leadership, may identify cleaner sales-quality "
        "candidates than raw DSO before a 10-trading-day continuation leg."
    ),
    "2_history_check": {
        "exp-20260616-021": (
            "Rejected raw annual receivables DSO improvement. Its closeout "
            "explicitly listed allowance/write-off normalization as materially "
            "different PIT collection-quality evidence required for a valid "
            "retry. This run tests that different evidence, not a DSO threshold."
        ),
        "exp-20260528-019": (
            "Rejected working-capital support scalar inside FGRS. This run is a "
            "standalone candidate-pool source using raw allowance burden, not a "
            "support scalar."
        ),
        "exp-20260616-018": (
            "Rejected inventory-to-revenue leanness. This run exits inventory "
            "and tests credit/collection quality."
        ),
        "exp-20260616-022": (
            "Rejected quarterly inventory DIO. It reinforces the need to avoid "
            "working-capital threshold sweeps without new evidence."
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
        "exp_20260616_023_allowance_doubtful_accounts_quality.py"
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
    allowance_tag_counts: Counter[str] = Counter()
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
        allowance_facts = _raw_instant_facts(usgaap, ALLOWANCE_TAGS)
        receivables_facts = _raw_instant_facts(usgaap, RECEIVABLES_TAGS)
        revenue_facts = rd._raw_annual_facts(usgaap, REVENUE_TAGS)
        if not allowance_facts:
            stats["tickers_missing_raw_allowance"] += 1
            continue
        if not receivables_facts:
            stats["tickers_missing_raw_receivables"] += 1
            continue
        if not revenue_facts:
            stats["tickers_missing_raw_annual_revenue"] += 1
            continue
        for fact in allowance_facts:
            allowance_tag_counts[fact["tag"]] += 1
        index[ticker] = {
            "allowance": allowance_facts,
            "receivables": receivables_facts,
            "revenue": revenue_facts,
        }
        stats["tickers_with_raw_allowance_receivables_and_revenue"] += 1
        stats["raw_allowance_fact_count"] += len(allowance_facts)
        stats["raw_receivables_fact_count"] += len(receivables_facts)
        stats["raw_annual_revenue_fact_count"] += len(revenue_facts)

    summary = {
        "raw_companyfacts_cache": _repo_rel(RAW_COMPANYFACTS_CACHE),
        "allowance_tags": list(ALLOWANCE_TAGS),
        "receivables_tags": list(RECEIVABLES_TAGS),
        "revenue_tags": list(REVENUE_TAGS),
        "allowance_tag_fact_counts": dict(allowance_tag_counts),
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


def _latest_same_tag_or_any(
    facts: list[dict[str, Any]],
    *,
    asof: str,
    end: str,
    preferred_tag: str | None = None,
) -> dict[str, Any] | None:
    same_tag = [fact for fact in facts if preferred_tag and fact["tag"] == preferred_tag]
    if same_tag:
        found = rd._latest_period_fact(same_tag, asof=asof, end=end)
        if found is not None:
            return found
    return rd._latest_period_fact(facts, asof=asof, end=end)


def _allowance_observation(
    ticker: str,
    asof: str,
    facts: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    current_revenue = rd._latest_period_fact(facts["revenue"], asof=asof)
    if current_revenue is None:
        return None
    if base._days_between(asof, current_revenue["filed"]) > MAX_ANNUAL_FACT_AGE_DAYS:
        return None
    current_receivables = rd._latest_period_fact(
        facts["receivables"], asof=asof, end=current_revenue["end"]
    )
    current_allowance = rd._latest_period_fact(
        facts["allowance"], asof=asof, end=current_revenue["end"]
    )
    if current_receivables is None or current_allowance is None:
        return None
    if base._days_between(asof, current_allowance["filed"]) > MAX_ANNUAL_FACT_AGE_DAYS:
        return None

    prior_revenue = rd._latest_period_fact(
        facts["revenue"], asof=asof, before_end=current_revenue["end"]
    )
    if prior_revenue is None:
        return None
    prior_receivables = rd._latest_period_fact(
        facts["receivables"], asof=asof, end=prior_revenue["end"]
    )
    prior_allowance = _latest_same_tag_or_any(
        facts["allowance"],
        asof=asof,
        end=prior_revenue["end"],
        preferred_tag=str(current_allowance["tag"]),
    )
    if prior_receivables is None or prior_allowance is None:
        return None

    current_revenue_value = float(current_revenue["value"])
    prior_revenue_value = float(prior_revenue["value"])
    current_receivables_value = abs(float(current_receivables["value"]))
    prior_receivables_value = abs(float(prior_receivables["value"]))
    current_allowance_value = abs(float(current_allowance["value"]))
    prior_allowance_value = abs(float(prior_allowance["value"]))
    if (
        current_revenue_value < MIN_CURRENT_REVENUE
        or current_receivables_value < MIN_CURRENT_RECEIVABLES
        or current_allowance_value < MIN_CURRENT_ALLOWANCE
        or prior_revenue_value <= 0.0
        or prior_receivables_value <= 0.0
        or prior_allowance_value <= 0.0
    ):
        return None

    current_ratio = current_allowance_value / current_receivables_value
    prior_ratio = prior_allowance_value / prior_receivables_value
    allowance_ratio_improvement = prior_ratio - current_ratio
    revenue_growth = (current_revenue_value - prior_revenue_value) / abs(prior_revenue_value)
    receivables_growth = (current_receivables_value - prior_receivables_value) / abs(
        prior_receivables_value
    )
    allowance_growth = (current_allowance_value - prior_allowance_value) / abs(
        prior_allowance_value
    )
    if not (MIN_CURRENT_ALLOWANCE_TO_RECEIVABLES <= current_ratio <= MAX_CURRENT_ALLOWANCE_TO_RECEIVABLES):
        return None
    if allowance_ratio_improvement < MIN_ALLOWANCE_RATIO_IMPROVEMENT:
        return None
    if revenue_growth < MIN_REVENUE_GROWTH:
        return None
    if receivables_growth > revenue_growth + MAX_RECEIVABLES_GROWTH_VS_REVENUE_GROWTH:
        return None

    return {
        "ticker": ticker,
        "current_period_end": current_revenue["end"],
        "current_allowance_filed": current_allowance["filed"],
        "current_receivables_filed": current_receivables["filed"],
        "current_revenue_filed": current_revenue["filed"],
        "current_allowance_tag": current_allowance["tag"],
        "prior_allowance_tag": prior_allowance["tag"],
        "current_allowance_value": _round(current_allowance_value, 2),
        "prior_allowance_value": _round(prior_allowance_value, 2),
        "current_receivables_value": _round(current_receivables_value, 2),
        "prior_receivables_value": _round(prior_receivables_value, 2),
        "current_revenue_value": _round(current_revenue_value, 2),
        "prior_revenue_value": _round(prior_revenue_value, 2),
        "prior_period_end": prior_revenue["end"],
        "current_allowance_to_receivables": _round(current_ratio, 6),
        "prior_allowance_to_receivables": _round(prior_ratio, 6),
        "allowance_ratio_improvement": _round(allowance_ratio_improvement, 6),
        "allowance_growth": _round(allowance_growth, 6),
        "revenue_growth": _round(revenue_growth, 6),
        "receivables_growth": _round(receivables_growth, 6),
        "receivables_growth_minus_revenue_growth": _round(
            receivables_growth - revenue_growth, 6
        ),
        "fact_age_days": base._days_between(asof, current_allowance["filed"]),
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
            observation = _allowance_observation(ticker, signal_date, quality_index[ticker])
            if observation is None:
                scan["failed_allowance_quality_gate"] += 1
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
            ratio_improvement = float(observation["allowance_ratio_improvement"] or 0.0)
            revenue_growth = float(observation["revenue_growth"] or 0.0)
            receivables_growth_spread = float(
                observation["receivables_growth_minus_revenue_growth"] or 0.0
            )
            current_ratio = float(observation["current_allowance_to_receivables"] or 0.0)
            score = (
                4.0 * min(ratio_improvement, 0.06)
                + 0.22 * max(min(revenue_growth, 0.60), 0.0)
                + 0.08 * max(min(-receivables_growth_spread, 0.25), -0.25)
                + 0.04 * max(min(0.04 - current_ratio, 0.04), -0.08)
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
                    "source": "ALLOWANCE_DOUBTFUL_ACCOUNTS_QUALITY_PAPER",
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
                    **{f"allowance_{k}": v for k, v in observation.items()},
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
            -float(row["allowance_allowance_ratio_improvement"] or 0.0),
            -float(row["allowance_revenue_growth"] or 0.0),
            float(row["allowance_receivables_growth_minus_revenue_growth"] or 0.0),
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
        "min_current_receivables": MIN_CURRENT_RECEIVABLES,
        "min_current_allowance": MIN_CURRENT_ALLOWANCE,
        "min_current_allowance_to_receivables": MIN_CURRENT_ALLOWANCE_TO_RECEIVABLES,
        "max_current_allowance_to_receivables": MAX_CURRENT_ALLOWANCE_TO_RECEIVABLES,
        "min_allowance_ratio_improvement": MIN_ALLOWANCE_RATIO_IMPROVEMENT,
        "min_revenue_growth": MIN_REVENUE_GROWTH,
        "max_receivables_growth_vs_revenue_growth": MAX_RECEIVABLES_GROWTH_VS_REVENUE_GROWTH,
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
        "positive_replay_lead_not_promoted_allowance_doubtful_accounts_quality"
        if gate["passed"]
        else "rejected_allowance_doubtful_accounts_quality_candidate_pool"
    )
    return gate


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
    base._build_quality_index = _build_quality_index
    base._candidate_rows_for_window = _candidate_rows_for_window
    base._gate4 = _gate4


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    if gate4["passed"]:
        interpretation = (
            "The allowance-for-doubtful-accounts burden improvement source "
            "cleared the numeric three-window replay screen, but remains only a "
            "replay lead because no shared daily/backtest helper was promoted."
        )
    else:
        interpretation = (
            "The allowance-for-doubtful-accounts burden improvement source did "
            "not clear Gate 4 (failed: "
            f"{', '.join(gate4['failed_reasons']) or 'none'}). Do not promote "
            "or tune this fixed allowance-quality bundle on the same frozen "
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
            "mechanism_family": "production_visible_free_sec_companyfacts_allowance_quality_candidate_pool",
            "new_evidence_type": "raw_sec_companyfacts_allowance_for_doubtful_accounts_pit_field",
            "nearby_prior_experiments": [
                "exp-20260616-021",
                "exp-20260528-019",
                "exp-20260616-018",
                "exp-20260616-022",
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
        "base_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "fy_duration_min": FY_DURATION_MIN,
        "fy_duration_max": FY_DURATION_MAX,
        "max_annual_fact_age_days": MAX_ANNUAL_FACT_AGE_DAYS,
        "min_current_revenue": MIN_CURRENT_REVENUE,
        "min_current_receivables": MIN_CURRENT_RECEIVABLES,
        "min_current_allowance": MIN_CURRENT_ALLOWANCE,
        "min_current_allowance_to_receivables": MIN_CURRENT_ALLOWANCE_TO_RECEIVABLES,
        "max_current_allowance_to_receivables": MAX_CURRENT_ALLOWANCE_TO_RECEIVABLES,
        "min_allowance_ratio_improvement": MIN_ALLOWANCE_RATIO_IMPROVEMENT,
        "min_revenue_growth": MIN_REVENUE_GROWTH,
        "max_receivables_growth_vs_revenue_growth": MAX_RECEIVABLES_GROWTH_VS_REVENUE_GROWTH,
        "allowance_tags": list(ALLOWANCE_TAGS),
        "receivables_tags": list(RECEIVABLES_TAGS),
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
        "Allowance and receivables are read as raw SEC Companyfacts balance-"
        "sheet INSTANT facts and matched to annual revenue ending the same "
        "fiscal-year date; all fields are known only by filed date <= signal "
        "date. The rule requires allowance/receivables burden to fall year over "
        "year while revenue is non-declining and receivables do not greatly "
        "outgrow revenue. Price confirmation uses only signal-date OHLCV. Paper "
        "entry is the next available open with existing entry slippage; exit is "
        "the close 10 trading days after the signal with target-side sell "
        "slippage and ROUND_TRIP_COST_PCT."
    )
    payload["backtest_protocol"]["companyfacts_source"] = _repo_rel(RAW_COMPANYFACTS_CACHE)
    payload["gate2"]["runtime_fields"] = [
        "raw SEC companyfacts allowance for doubtful accounts instant facts",
        "raw SEC companyfacts annual receivables instant facts",
        "raw SEC companyfacts annual revenue facts",
        "raw SEC companyfacts filed date and period end",
        "warehouse ticker_universe CIK mapping",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A retry needs materially different PIT collection-quality evidence such "
        "as quarterly allowance changes, write-off or allowance-build flow, "
        "customer concentration context, or forward replacement-value rows. Do "
        "not sweep allowance tags, allowance ratio thresholds, revenue-growth "
        "floor, annual fact freshness, price guards, top-N, hold, cooldown, or "
        "notional on these frozen windows."
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
            "Do not retry by sweeping the allowance tag list, allowance ratio "
            "improvement threshold, current allowance ratio bounds, revenue "
            "growth floor, annual fact freshness, RS/close/volume/vol guards, "
            "top-N, hold days, cooldown, or notional on these frozen windows."
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
            f"# {EXPERIMENT_ID} Allowance Doubtful Accounts Quality",
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
