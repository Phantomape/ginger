"""exp-20260615-017: deferred revenue / RPO demand acceleration scout.

Replay-only alpha search. The single decision hypothesis is a raw SEC
Companyfacts candidate source: production-universe names with materially
growing deferred revenue, contract liabilities, or remaining performance
obligations may contain paid-or-contracted demand not captured by generic SEC
backlog text or static profitability fields.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive replay is
only a lead until a shared selected-Companyfacts/daily helper reproduces it.
No JavaScript is used.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import exp_20260614_020_accruals_cash_conversion_quality as base


EXPERIMENT_ID = "exp-20260615-017"
STEM = "deferred_revenue_demand_acceleration"
TRIAL_FAMILY = "deferred_revenue_demand_acceleration_candidate_pool"
TRIAL_VARIANT_ID = "raw_companyfacts_deferred_revenue_rpo_top1_next_open_10d_v1"
CHANGED_VARIABLE = "deferred_revenue_demand_acceleration_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260615_017_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
SEC_TICKERS_JSON = REPO_ROOT / "data" / "reference" / "sec_company_tickers.json"
RAW_COMPANYFACTS_DIR = REPO_ROOT / "data" / "cache" / "sec" / "companyfacts"

BASE_NOTIONAL_USD = base.BASE_NOTIONAL_USD
HOLD_DAYS = base.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = base.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = base.SAME_TICKER_COOLDOWN_DAYS

MAX_FACT_AGE_DAYS = 430
MIN_PRIOR_GAP_DAYS = 250
MAX_PRIOR_GAP_DAYS = 460
MIN_DEMAND_GROWTH = 0.20
MIN_DEMAND_TO_REVENUE = 0.04
MIN_CURRENT_DEMAND_USD = 50_000_000.0

DEMAND_CONCEPT_GROUPS: dict[str, tuple[str, ...]] = {
    "rpo": ("RevenueRemainingPerformanceObligation",),
    "contract_liability_total": (
        "ContractWithCustomerLiability",
        "DeferredRevenue",
        "DeferredRevenueAndCredits",
    ),
    "contract_liability_current": (
        "ContractWithCustomerLiabilityCurrent",
        "DeferredRevenueCurrent",
        "DeferredRevenueAndCreditsCurrent",
    ),
    "contract_liability_noncurrent": (
        "ContractWithCustomerLiabilityNoncurrent",
        "DeferredRevenueNoncurrent",
        "DeferredRevenueAndCreditsNoncurrent",
    ),
}
REVENUE_CONCEPTS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
)

PREDICTION = {
    "success_probability": 0.14,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "raw_field_sparse",
        "stale_or_inconsistent_concepts",
        "window_regression",
        "drawdown_drift",
        "accepted_comparator_not_beaten",
    ],
    "confidence_reason": (
        "Backlog/order SEC text variants were too sparse and static Companyfacts "
        "profitability variants regressed windows; raw companyfacts contract "
        "liabilities and RPO are a materially different PIT demand field with "
        "broad raw-cache coverage, but the field is not yet in the selected "
        "daily surface and may be noisy across industries."
    ),
    "recorded_at": "2026-06-15T16:05:41+00:00",
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
            "missing raw companyfacts demand obligation, stale fact, missing "
            "prior comparable demand fact, missing annual revenue scaler, "
            "missing OHLCV, missing next open, or missing 10d exit rejects the "
            "paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper and selected "
        "Companyfacts surface compute the same deferred-revenue/RPO growth gate, "
        "liquid SPY-relative confirmation, cooldown, next-open paper entry, "
        "10-day exit, costs, and concentration controls in both historical "
        "replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: raw SEC Companyfacts deferred revenue, contract "
        "liability, or RPO growth, paired with liquid SPY-relative "
        "confirmation, may identify paid-or-contracted demand leaders whose "
        "next-open 10-day paper continuation beats generic SEC backlog text "
        "and static profitability variants."
    ),
    "2_history_check": {
        "exp-20260615-012/013": (
            "SEC backlog/order/RPO text variants were rejected as sparse and "
            "non-incremental. This run uses numeric XBRL facts from raw "
            "Companyfacts, not text phrases or regex spans."
        ),
        "exp-20260615-016": (
            "Operating leverage acceleration was rejected on old_thin/drawdown. "
            "This run tests contracted demand growth, not recognized revenue "
            "margin expansion."
        ),
        "exp-20260615-008/010": (
            "FCF/capex coverage and gross profitability were static quality "
            "fields. This run tests pre-revenue customer obligation growth."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL must "
        "be positive, no window EV/PnL regression, at least two EV-improved "
        "windows, at least 20 paper trades across all 3 windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration pass, and accepted compression/"
        "distribution comparators must be beaten. Replay-only positives are "
        "leads until shared daily/backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260615_017_deferred_revenue_demand_acceleration.py"
    ),
}

_RAW_ROWS_CACHE: dict[tuple[str, ...], tuple[list[dict[str, Any]], dict[str, Any]]] = {}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return base._round(value, digits)


def _parse_date(value: Any) -> datetime | None:
    text = str(value or "")[:10]
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d")
    except ValueError:
        return None


def _days_between(later: str, earlier: str) -> int:
    later_dt = _parse_date(later)
    earlier_dt = _parse_date(earlier)
    if later_dt is None or earlier_dt is None:
        return 999999
    return (later_dt - earlier_dt).days


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _ticker_to_cik() -> dict[str, str]:
    payload = json.loads(SEC_TICKERS_JSON.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    rows = payload.values() if isinstance(payload, dict) else payload
    for raw in rows:
        ticker = str(raw.get("ticker") or "").upper()
        cik = str(raw.get("cik_str") or "").strip()
        if ticker and cik:
            out[ticker] = cik.zfill(10)
    return out


def _raw_fact_rows_for_tickers(tickers: tuple[str, ...]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cached = _RAW_ROWS_CACHE.get(tickers)
    if cached is not None:
        return cached

    ticker_to_cik = _ticker_to_cik()
    concept_to_group = {
        concept: group
        for group, concepts in DEMAND_CONCEPT_GROUPS.items()
        for concept in concepts
    }
    revenue_concepts = set(REVENUE_CONCEPTS)
    rows: list[dict[str, Any]] = []
    stats: Counter[str] = Counter()
    for ticker in tickers:
        cik = ticker_to_cik.get(ticker)
        if not cik:
            stats["missing_cik"] += 1
            continue
        path = RAW_COMPANYFACTS_DIR / f"CIK{cik}.json"
        if not path.exists():
            stats["missing_cache_file"] += 1
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            stats["bad_cache_file"] += 1
            continue
        us_gaap = (payload.get("facts") or {}).get("us-gaap") or {}
        stats["cache_files_loaded"] += 1
        for concept, data in us_gaap.items():
            if concept in concept_to_group:
                canonical = "deferred_revenue_demand"
                concept_group = concept_to_group[concept]
            elif concept in revenue_concepts:
                canonical = "revenue"
                concept_group = "revenue"
            else:
                continue
            units = (data or {}).get("units") or {}
            for unit, facts in units.items():
                if unit != "USD" or not isinstance(facts, list):
                    continue
                for fact in facts:
                    value = _float_or_none(fact.get("val"))
                    filed = str(fact.get("filed") or "")[:10]
                    end = str(fact.get("end") or "")[:10]
                    if value is None or not filed or not end:
                        continue
                    row = {
                        "ticker": ticker,
                        "cik": cik,
                        "canonical": canonical,
                        "concept": concept,
                        "concept_group": concept_group,
                        "filed": filed,
                        "end": end,
                        "start": str(fact.get("start") or "")[:10] or None,
                        "form": fact.get("form"),
                        "fp": fact.get("fp"),
                        "fy": fact.get("fy"),
                        "duration_days": None,
                        "value": value,
                        "unit": unit,
                        "pit_source": "raw_sec_companyfacts_cache",
                    }
                    start_dt = _parse_date(row["start"])
                    end_dt = _parse_date(end)
                    if start_dt is not None and end_dt is not None:
                        row["duration_days"] = (end_dt - start_dt).days + 1
                    rows.append(row)
                    stats[f"rows_{canonical}"] += 1
                    stats[f"group_{concept_group}"] += 1
    result = (rows, {"raw_companyfacts_rows_loaded": len(rows), **dict(stats)})
    _RAW_ROWS_CACHE[tickers] = result
    return result


def load_raw_companyfacts_rows(
    *,
    max_filed: str | None = None,
    tickers: list[str] | tuple[str, ...] | None = None,
    **_: Any,
) -> list[dict[str, Any]]:
    ticker_tuple = tuple(sorted({str(t).upper() for t in (tickers or []) if str(t or "").strip()}))
    rows, _stats = _raw_fact_rows_for_tickers(ticker_tuple)
    if max_filed:
        return [row for row in rows if str(row.get("filed") or "")[:10] <= str(max_filed)[:10]]
    return list(rows)


def _annual_revenue_facts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for raw in rows:
        if raw.get("canonical") != "revenue":
            continue
        dur = raw.get("duration_days")
        if dur is None or not (base.FY_DURATION_MIN <= int(dur) <= base.FY_DURATION_MAX):
            continue
        value = _float_or_none(raw.get("value"))
        filed = str(raw.get("filed") or "")[:10]
        end = str(raw.get("end") or "")[:10]
        if value is not None and value > 0 and filed and end:
            facts.append(
                {
                    "filed": filed,
                    "end": end,
                    "value": value,
                    "concept": raw.get("concept"),
                    "concept_group": "revenue",
                }
            )
    facts.sort(key=lambda fact: (fact["filed"], fact["end"]))
    return facts


def _demand_facts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for raw in rows:
        if raw.get("canonical") != "deferred_revenue_demand":
            continue
        value = _float_or_none(raw.get("value"))
        filed = str(raw.get("filed") or "")[:10]
        end = str(raw.get("end") or "")[:10]
        if value is not None and value > 0 and filed and end:
            facts.append(
                {
                    "filed": filed,
                    "end": end,
                    "value": value,
                    "concept": raw.get("concept"),
                    "concept_group": raw.get("concept_group"),
                }
            )
    facts.sort(key=lambda fact: (fact["filed"], fact["end"], fact["concept"]))
    return facts


def _build_quality_index(
    companyfacts_rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]]:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in companyfacts_rows:
        ticker = str(raw.get("ticker") or "").upper()
        if ticker:
            by_ticker[ticker].append(raw)
    index: dict[str, dict[str, list[dict[str, Any]]]] = {}
    stats: Counter[str] = Counter()
    for ticker, rows in by_ticker.items():
        demand = _demand_facts(rows)
        revenue = _annual_revenue_facts(rows)
        if not demand or not revenue:
            stats["tickers_missing_required_facts"] += 1
            continue
        index[ticker] = {"demand": demand, "revenue": revenue}
        stats["tickers_with_deferred_revenue_demand_facts"] += 1
        for fact in demand:
            stats[f"tickers_group_{fact['concept_group']}"] += 0
    return index, {
        "raw_companyfacts_rows_loaded": len(companyfacts_rows),
        "tickers_seen": len(by_ticker),
        **dict(stats),
    }


def _latest_on_or_before(facts: list[dict[str, Any]], asof: str) -> dict[str, Any] | None:
    chosen: dict[str, Any] | None = None
    for fact in facts:
        if fact["filed"] <= asof:
            chosen = fact
        else:
            break
    return chosen


def _latest_revenue_on_or_before(facts: list[dict[str, Any]], asof: str) -> dict[str, Any] | None:
    candidates = [fact for fact in facts if fact["filed"] <= asof]
    if not candidates:
        return None
    return max(candidates, key=lambda fact: (fact["filed"], fact["end"]))


def _prior_comparable_demand(
    facts: list[dict[str, Any]],
    *,
    asof: str,
    current: dict[str, Any],
) -> dict[str, Any] | None:
    current_end = _parse_date(current["end"])
    if current_end is None:
        return None
    candidates: list[dict[str, Any]] = []
    for fact in facts:
        if fact["filed"] > asof or fact["end"] >= current["end"]:
            continue
        if fact.get("concept_group") != current.get("concept_group"):
            continue
        gap = (current_end - (_parse_date(fact["end"]) or current_end)).days
        if MIN_PRIOR_GAP_DAYS <= gap <= MAX_PRIOR_GAP_DAYS:
            candidates.append(fact)
    if not candidates:
        return None
    return max(candidates, key=lambda fact: (fact["end"], fact["filed"]))


def _demand_observation(ticker: str, asof: str, facts: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    revenue = _latest_revenue_on_or_before(facts["revenue"], asof)
    if revenue is None or float(revenue["value"]) <= 0:
        return None
    for group in ("rpo", "contract_liability_total", "contract_liability_current", "contract_liability_noncurrent"):
        group_facts = [fact for fact in facts["demand"] if fact.get("concept_group") == group]
        current = _latest_on_or_before(group_facts, asof)
        if current is None:
            continue
        if _days_between(asof, current["filed"]) > MAX_FACT_AGE_DAYS:
            continue
        prior = _prior_comparable_demand(group_facts, asof=asof, current=current)
        if prior is None or float(prior["value"]) <= 0:
            continue
        demand_growth = float(current["value"]) / float(prior["value"]) - 1.0
        demand_to_revenue = float(current["value"]) / float(revenue["value"])
        if float(current["value"]) < MIN_CURRENT_DEMAND_USD:
            continue
        if demand_growth < MIN_DEMAND_GROWTH:
            continue
        if demand_to_revenue < MIN_DEMAND_TO_REVENUE:
            continue
        row = {
            "demand_group": group,
            "demand_concept": current.get("concept"),
            "current_demand_end": current["end"],
            "prior_demand_end": prior["end"],
            "current_demand_filed": current["filed"],
            "prior_demand_filed": prior["filed"],
            "current_demand_value": _round(current["value"], 2),
            "prior_demand_value": _round(prior["value"], 2),
            "demand_growth": _round(demand_growth, 6),
            "demand_to_revenue": _round(demand_to_revenue, 6),
            "revenue_value": _round(revenue["value"], 2),
            "revenue_filed": revenue["filed"],
            "fact_age_days": _days_between(asof, current["filed"]),
        }
        if best is None or float(row["demand_growth"] or 0.0) > float(best["demand_growth"] or 0.0):
            best = row
    return best


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
            quality = _demand_observation(ticker, signal_date, quality_index[ticker])
            if quality is None:
                scan["failed_demand_gate"] += 1
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
                0.95 * min(float(quality["demand_growth"] or 0.0), 2.0)
                + 0.55 * min(float(quality["demand_to_revenue"] or 0.0), 1.0)
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
                    "source": "DEFERRED_REVENUE_DEMAND_ACCELERATION_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "raw_companyfacts_filed_and_signal_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_companyfacts": True,
                    "uses_raw_companyfacts_cache": True,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    **{f"demand_{key}": value for key, value in quality.items()},
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
            -float(row["demand_demand_growth"] or 0.0),
            -float(row["demand_demand_to_revenue"] or 0.0),
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
        "max_fact_age_days": MAX_FACT_AGE_DAYS,
        "min_prior_gap_days": MIN_PRIOR_GAP_DAYS,
        "max_prior_gap_days": MAX_PRIOR_GAP_DAYS,
        "min_demand_growth": MIN_DEMAND_GROWTH,
        "min_demand_to_revenue": MIN_DEMAND_TO_REVENUE,
        "min_current_demand_usd": MIN_CURRENT_DEMAND_USD,
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
        "positive_replay_lead_not_promoted_deferred_revenue_demand_acceleration"
        if gate["passed"]
        else "rejected_deferred_revenue_demand_acceleration_candidate_pool"
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
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    base.load_companyfacts_rows = load_raw_companyfacts_rows
    base._build_quality_index = _build_quality_index
    base._candidate_rows_for_window = _candidate_rows_for_window
    base._gate4 = _gate4


def _patch_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    interpretation = (
        "The raw Companyfacts deferred-revenue/RPO demand acceleration source "
        "cleared the numeric three-window replay screen, but remains only a "
        "replay lead because no selected daily Companyfacts surface or shared "
        "helper was promoted."
        if gate4["passed"]
        else (
            "The raw Companyfacts deferred-revenue/RPO demand acceleration "
            "source did not clear Gate 4 (failed: "
            + (", ".join(gate4["failed_reasons"]) or "none")
            + "). It is not retained or promoted."
        )
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
            "mechanism_family": "production_visible_raw_sec_companyfacts_demand_candidate_pool",
            "new_evidence_type": "raw_sec_companyfacts_deferred_revenue_rpo_plus_ohlcv",
            "nearby_prior_experiments": [
                "exp-20260615-012",
                "exp-20260615-013",
                "exp-20260615-016",
                "exp-20260615-008",
                "exp-20260615-010",
            ],
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
        "predicted_failure_mode_hit": bool(gate4["failed_reasons"]),
        "brier_score": round((PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2, 6),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
    }
    payload["parameters"] = {
        **payload.get("parameters", {}),
        "max_fact_age_days": MAX_FACT_AGE_DAYS,
        "min_prior_gap_days": MIN_PRIOR_GAP_DAYS,
        "max_prior_gap_days": MAX_PRIOR_GAP_DAYS,
        "min_demand_growth": MIN_DEMAND_GROWTH,
        "min_demand_to_revenue": MIN_DEMAND_TO_REVENUE,
        "min_current_demand_usd": MIN_CURRENT_DEMAND_USD,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["companyfacts_source"] = _repo_rel(RAW_COMPANYFACTS_DIR)
    payload["backtest_protocol"]["execution_model"] = (
        "Raw SEC Companyfacts deferred revenue, contract-liability, and RPO "
        "facts are known by filed date (<= signal date). Current demand "
        "obligation value is compared with a same-group prior fact roughly one "
        "year earlier, scaled by latest filed annual revenue. Price confirmation "
        "uses only signal-date OHLCV. Paper entry is the next available open "
        "with existing entry slippage; exit is the close 10 trading days after "
        "signal with target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["gate2"]["runtime_fields"] = [
        "raw SEC companyfacts deferred revenue / contract liability / RPO facts",
        "raw SEC companyfacts annual revenue facts",
        "SEC companyfacts filed date and period end",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A retry needs a selected PIT Companyfacts daily surface for deferred "
        "revenue/RPO, cleaner concept taxonomy, or closed forward replacement "
        "rows. Do not sweep demand-growth, demand/revenue, fact-age, RS/close/"
        "volume, top-N, hold, cooldown, or notional thresholds on these frozen "
        "windows."
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
            "Do not retry by sweeping demand-growth, demand/revenue, "
            "current-demand, concept priority, fact-age, prior-gap, RS/close/"
            "volume, top-N, hold days, cooldown, or notional thresholds on "
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
            f"# {EXPERIMENT_ID} Deferred Revenue Demand Acceleration",
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
                "expected_value_before": payload["before_metrics"][label]["expected_value_score"],
                "expected_value_after": payload["after_metrics"][label]["expected_value_score"],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label]["expected_value_score"],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label]["total_pnl"],
                "eligible_quality_tickers": payload["context_scan_by_window"][label].get("eligible_quality_tickers"),
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
        "aggregate_strategy_total_pnl_delta": log_record["aggregate_strategy_total_pnl_delta"],
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


def main() -> None:
    _configure_base()
    payload = _patch_payload(base._build_payload())
    _persist(payload)
    print(json.dumps(base.framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
