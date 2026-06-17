"""exp-20260617-002: cash-conversion-cycle contraction scout.

Replay-only alpha search. The single decision hypothesis is a PIT free SEC
Companyfacts candidate source: production-universe names whose quarterly cash
conversion cycle is contracting versus the comparable prior-year quarter while
price action confirms liquid SPY-relative leadership.

This is not another single-leg DSO, DIO, or DPO threshold retune. The rule
requires at least one operating efficiency leg (customer collection or
inventory sell-through) to improve and requires supplier financing not to
collapse, then tests whether the combined DSO + DIO - DPO field is cleaner than
the separate working-capital legs.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive replay is
only a lead until a shared historical/daily helper reproduces it. No JavaScript
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

import exp_20260617_001_accounts_payable_dpo_extension as dpo


base = dpo.base
rd = dpo.rd

EXPERIMENT_ID = "exp-20260617-002"
STEM = "cash_conversion_cycle_contraction"
TRIAL_FAMILY = "cash_conversion_cycle_contraction_candidate_pool"
TRIAL_VARIANT_ID = "cash_conversion_cycle_contraction_top1_next_open_10d_v1"
CHANGED_VARIABLE = "raw_sec_companyfacts_cash_conversion_cycle_contraction_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
RAW_COMPANYFACTS_CACHE = REPO_ROOT / "data" / "cache" / "sec" / "companyfacts"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260617_002_{STEM}.json"
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

QUARTER_DURATION_MIN = 60
QUARTER_DURATION_MAX = 130
MAX_QUARTER_FACT_AGE_DAYS = 220
MAX_POINT_FACT_AGE_DAYS = 220
COMPARABLE_QUARTER_MIN_GAP_DAYS = 250
COMPARABLE_QUARTER_MAX_GAP_DAYS = 450
QUARTER_DAYS = 91.25

MIN_CURRENT_REVENUE = 250_000_000.0
MIN_CURRENT_COGS = 100_000_000.0
MIN_CURRENT_RECEIVABLES = 25_000_000.0
MIN_CURRENT_PAYABLES = 10_000_000.0
MIN_CURRENT_INVENTORY = 10_000_000.0
MAX_CURRENT_DSO_DAYS = 180.0
MAX_CURRENT_DIO_DAYS = 220.0
MAX_CURRENT_DPO_DAYS = 220.0
MAX_CURRENT_CCC_DAYS = 240.0
MIN_CCC_CONTRACTION_DAYS = 7.0
MIN_OPERATING_LEG_IMPROVEMENT_DAYS = 2.0
MIN_DPO_EXTENSION_DAYS = -2.0
MIN_REVENUE_GROWTH = -0.05
MIN_COGS_GROWTH = -0.05
MIN_GROSS_PROFIT_GROWTH = -0.05

RECEIVABLE_TAGS = (
    "AccountsReceivableNetCurrent",
    "AccountsReceivableCurrent",
    "AccountsReceivableNet",
)
INVENTORY_TAGS = ("InventoryNet",)
PAYABLE_TAGS = dpo.PAYABLE_TAGS
REVENUE_TAGS = rd.REVENUE_TAGS
COGS_TAGS = dpo.COGS_TAGS
GROSS_PROFIT_TAGS = dpo.GROSS_PROFIT_TAGS

PREDICTION = {
    "success_probability": 0.17,
    "expected_ev_delta": 0.25,
    "expected_pnl_delta": 3500.0,
    "main_failure_modes": [
        "thin_sample",
        "window_regression",
        "drawdown_drift",
        "accepted_distribution_comparator_not_beaten",
        "working_capital_field_relabels_momentum",
    ],
    "confidence_reason": (
        "Separate DSO, DIO, and DPO Companyfacts legs were directionally "
        "positive but failed old_thin, drawdown, or comparator gates. A "
        "combined cash-conversion-cycle contraction field is materially "
        "different because it requires collection or sell-through efficiency "
        "while avoiding supplier-financing deterioration, but sample and "
        "drawdown risk remain high."
    ),
    "recorded_at": "2026-06-17T01:04:11+00:00",
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
            "missing raw SEC quarterly revenue/COGS facts, missing receivables "
            "or payables point facts, missing comparable prior-year quarter, "
            "stale facts, missing CIK mapping, missing OHLCV, missing next "
            "open, or missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same raw "
        "SEC filed-date PIT revenue, COGS, receivables, payables, optional "
        "inventory, and gross-profit facts, the same cash-conversion-cycle "
        "contraction gate, liquid SPY-relative confirmation, cooldown, "
        "next-open paper entry, 10-day exit, costs, and concentration controls "
        "in both historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: raw SEC Companyfacts quarterly cash-conversion-cycle "
        "contraction (DSO + DIO - DPO falling versus the comparable prior-year "
        "quarter), with at least one operating efficiency leg improving, no "
        "supplier-financing collapse, non-collapsing revenue/COGS/gross-profit "
        "context, and liquid SPY-relative leadership, may identify working-"
        "capital efficiency leaders before a 10-trading-day continuation leg."
    ),
    "2_history_check": {
        "exp-20260616-021": (
            "Rejected receivables DSO collection improvement: late/mid positive "
            "but old_thin regressed and distribution PnL was not beaten."
        ),
        "exp-20260616-022": (
            "Rejected quarterly inventory DIO/turnover improvement: old_thin "
            "regressed, drawdown worsened, and concentration failed."
        ),
        "exp-20260617-001": (
            "Rejected accounts-payable DPO extension despite all-window EV/PnL "
            "improvement because old_thin drawdown drift exceeded the guardrail. "
            "This run is not a DPO threshold sweep; it requires customer or "
            "inventory efficiency plus DPO not collapsing."
        ),
        "exp-20260614-024": (
            "Rejected quarterly OCF/NI cash-conversion improvement; that was "
            "earnings-quality cash conversion, not working-capital cycle timing."
        ),
        "exp-20260528-019": (
            "Rejected working-capital discipline support inside FGRS. This run "
            "is a standalone cash-conversion-cycle candidate source with raw "
            "Companyfacts filed-date PIT facts."
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
        "exp_20260617_002_cash_conversion_cycle_contraction.py"
    ),
}

_RAW_INDEX_CACHE: tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return base._round(value, digits)


def _latest_point(
    facts: list[dict[str, Any]],
    *,
    asof: str,
    end: str | None = None,
    before_end: str | None = None,
) -> dict[str, Any] | None:
    return rd._latest_period_fact(facts, asof=asof, end=end, before_end=before_end)


def _prior_comparable_quarter_fact(
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
        if COMPARABLE_QUARTER_MIN_GAP_DAYS <= gap_days <= COMPARABLE_QUARTER_MAX_GAP_DAYS:
            candidates.append({**fact, "_gap_days": gap_days})
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda fact: (
            abs(int(fact["_gap_days"]) - 365),
            -int(fact["_gap_days"]),
            str(fact["filed"]),
            float(fact["value"] or 0.0),
        ),
    )


def _fact_age_ok(asof: str, fact: dict[str, Any] | None, max_age: int) -> bool:
    if fact is None:
        return False
    return base._days_between(asof, str(fact.get("filed") or "")) <= max_age


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
        revenue_facts = dpo._raw_quarterly_facts(usgaap, REVENUE_TAGS)
        cogs_facts = dpo._raw_quarterly_facts(usgaap, COGS_TAGS)
        receivable_facts = dpo._raw_instant_facts(usgaap, RECEIVABLE_TAGS)
        payable_facts = dpo._raw_instant_facts(usgaap, PAYABLE_TAGS)
        inventory_facts = dpo._raw_instant_facts(usgaap, INVENTORY_TAGS)
        gross_profit_facts = dpo._raw_quarterly_facts(usgaap, GROSS_PROFIT_TAGS)
        if not revenue_facts:
            stats["tickers_missing_raw_quarterly_revenue"] += 1
            continue
        if not cogs_facts:
            stats["tickers_missing_raw_quarterly_cogs"] += 1
            continue
        if not receivable_facts:
            stats["tickers_missing_raw_receivables"] += 1
            continue
        if not payable_facts:
            stats["tickers_missing_raw_payables"] += 1
            continue
        index[ticker] = {
            "revenue": revenue_facts,
            "cogs": cogs_facts,
            "receivables": receivable_facts,
            "payables": payable_facts,
            "inventory": inventory_facts,
            "gross_profit": gross_profit_facts,
        }
        stats["tickers_with_raw_ccc_inputs"] += 1
        stats["tickers_with_inventory_component"] += 1 if inventory_facts else 0
        stats["tickers_with_quarterly_gross_profit"] += 1 if gross_profit_facts else 0
        stats["raw_quarterly_revenue_fact_count"] += len(revenue_facts)
        stats["raw_quarterly_cogs_fact_count"] += len(cogs_facts)
        stats["raw_receivables_fact_count"] += len(receivable_facts)
        stats["raw_payables_fact_count"] += len(payable_facts)
        stats["raw_inventory_fact_count"] += len(inventory_facts)

    summary = {
        "raw_companyfacts_cache": _repo_rel(RAW_COMPANYFACTS_CACHE),
        "revenue_tags": list(REVENUE_TAGS),
        "cogs_tags": list(COGS_TAGS),
        "receivable_tags": list(RECEIVABLE_TAGS),
        "payable_tags": list(PAYABLE_TAGS),
        "inventory_tags": list(INVENTORY_TAGS),
        "gross_profit_tags": list(GROSS_PROFIT_TAGS),
        "warehouse_source": _repo_rel(base.framework.WAREHOUSE),
        "quarter_duration_min": QUARTER_DURATION_MIN,
        "quarter_duration_max": QUARTER_DURATION_MAX,
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


def _period_pair(
    *,
    facts: dict[str, list[dict[str, Any]]],
    asof: str,
) -> dict[str, Any] | None:
    current_revenue = rd._latest_period_fact(facts["revenue"], asof=asof)
    if current_revenue is None:
        return None
    if not _fact_age_ok(asof, current_revenue, MAX_QUARTER_FACT_AGE_DAYS):
        return None
    current_cogs = rd._latest_period_fact(
        facts["cogs"], asof=asof, end=current_revenue["end"]
    )
    if current_cogs is None:
        return None
    if not _fact_age_ok(asof, current_cogs, MAX_QUARTER_FACT_AGE_DAYS):
        return None
    prior_revenue = _prior_comparable_quarter_fact(
        facts["revenue"], asof=asof, current_end=current_revenue["end"]
    )
    if prior_revenue is None:
        return None
    prior_cogs = rd._latest_period_fact(
        facts["cogs"], asof=asof, end=prior_revenue["end"]
    )
    if prior_cogs is None:
        return None
    return {
        "current_revenue": current_revenue,
        "current_cogs": current_cogs,
        "prior_revenue": prior_revenue,
        "prior_cogs": prior_cogs,
    }


def _average_balance(
    point_facts: list[dict[str, Any]],
    *,
    asof: str,
    end: str,
) -> tuple[dict[str, Any], dict[str, Any], float] | None:
    current = _latest_point(point_facts, asof=asof, end=end)
    if current is None or not _fact_age_ok(asof, current, MAX_POINT_FACT_AGE_DAYS):
        return None
    previous = _latest_point(point_facts, asof=asof, before_end=current["end"])
    if previous is None:
        return None
    current_value = abs(float(current["value"]))
    previous_value = abs(float(previous["value"]))
    if current_value <= 0.0 or previous_value <= 0.0:
        return None
    return current, previous, (current_value + previous_value) / 2.0


def _cash_cycle_observation(
    ticker: str,
    asof: str,
    facts: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    periods = _period_pair(facts=facts, asof=asof)
    if periods is None:
        return None
    current_revenue = periods["current_revenue"]
    prior_revenue = periods["prior_revenue"]
    current_cogs = periods["current_cogs"]
    prior_cogs = periods["prior_cogs"]
    current_revenue_value = float(current_revenue["value"])
    prior_revenue_value = float(prior_revenue["value"])
    current_cogs_value = float(current_cogs["value"])
    prior_cogs_value = float(prior_cogs["value"])
    if (
        current_revenue_value < MIN_CURRENT_REVENUE
        or current_cogs_value < MIN_CURRENT_COGS
        or prior_revenue_value <= 0.0
        or prior_cogs_value <= 0.0
    ):
        return None

    current_receivables = _average_balance(
        facts["receivables"], asof=asof, end=current_revenue["end"]
    )
    prior_receivables = _average_balance(
        facts["receivables"], asof=asof, end=prior_revenue["end"]
    )
    current_payables = _average_balance(
        facts["payables"], asof=asof, end=current_cogs["end"]
    )
    prior_payables = _average_balance(
        facts["payables"], asof=asof, end=prior_cogs["end"]
    )
    if (
        current_receivables is None
        or prior_receivables is None
        or current_payables is None
        or prior_payables is None
    ):
        return None
    cur_ar, cur_ar_prev, current_avg_ar = current_receivables
    prior_ar, prior_ar_prev, prior_avg_ar = prior_receivables
    cur_ap, cur_ap_prev, current_avg_ap = current_payables
    prior_ap, prior_ap_prev, prior_avg_ap = prior_payables
    if current_avg_ar < MIN_CURRENT_RECEIVABLES or current_avg_ap < MIN_CURRENT_PAYABLES:
        return None

    current_dso = QUARTER_DAYS * current_avg_ar / current_revenue_value
    prior_dso = QUARTER_DAYS * prior_avg_ar / prior_revenue_value
    current_dpo = QUARTER_DAYS * current_avg_ap / current_cogs_value
    prior_dpo = QUARTER_DAYS * prior_avg_ap / prior_cogs_value

    current_dio = 0.0
    prior_dio = 0.0
    inventory_available = False
    current_inventory = _average_balance(
        facts["inventory"], asof=asof, end=current_cogs["end"]
    )
    prior_inventory = _average_balance(
        facts["inventory"], asof=asof, end=prior_cogs["end"]
    )
    cur_inv = cur_inv_prev = prior_inv = prior_inv_prev = None
    current_avg_inv = prior_avg_inv = None
    if current_inventory is not None and prior_inventory is not None:
        cur_inv, cur_inv_prev, current_avg_inv = current_inventory
        prior_inv, prior_inv_prev, prior_avg_inv = prior_inventory
        if current_avg_inv >= MIN_CURRENT_INVENTORY and prior_avg_inv > 0.0:
            current_dio = QUARTER_DAYS * current_avg_inv / current_cogs_value
            prior_dio = QUARTER_DAYS * prior_avg_inv / prior_cogs_value
            inventory_available = True

    revenue_growth = (current_revenue_value - prior_revenue_value) / abs(prior_revenue_value)
    cogs_growth = (current_cogs_value - prior_cogs_value) / abs(prior_cogs_value)
    dso_improvement = prior_dso - current_dso
    dio_improvement = prior_dio - current_dio
    dpo_extension = current_dpo - prior_dpo
    current_ccc = current_dso + current_dio - current_dpo
    prior_ccc = prior_dso + prior_dio - prior_dpo
    ccc_contraction = prior_ccc - current_ccc

    if current_dso > MAX_CURRENT_DSO_DAYS:
        return None
    if inventory_available and current_dio > MAX_CURRENT_DIO_DAYS:
        return None
    if current_dpo > MAX_CURRENT_DPO_DAYS or current_ccc > MAX_CURRENT_CCC_DAYS:
        return None
    if revenue_growth < MIN_REVENUE_GROWTH or cogs_growth < MIN_COGS_GROWTH:
        return None
    if ccc_contraction < MIN_CCC_CONTRACTION_DAYS:
        return None
    if max(dso_improvement, dio_improvement) < MIN_OPERATING_LEG_IMPROVEMENT_DAYS:
        return None
    if dpo_extension < MIN_DPO_EXTENSION_DAYS:
        return None

    current_gross_profit = rd._latest_period_fact(
        facts["gross_profit"], asof=asof, end=current_revenue["end"]
    )
    prior_gross_profit = rd._latest_period_fact(
        facts["gross_profit"], asof=asof, end=prior_revenue["end"]
    )
    gross_profit_growth = None
    if current_gross_profit is not None and prior_gross_profit is not None:
        current_gp_value = float(current_gross_profit["value"])
        prior_gp_value = float(prior_gross_profit["value"])
        if prior_gp_value > 0.0:
            gross_profit_growth = (current_gp_value - prior_gp_value) / abs(prior_gp_value)
            if gross_profit_growth < MIN_GROSS_PROFIT_GROWTH:
                return None

    return {
        "ticker": ticker,
        "current_period_end": current_revenue["end"],
        "prior_period_end": prior_revenue["end"],
        "current_revenue_value": _round(current_revenue_value, 2),
        "prior_revenue_value": _round(prior_revenue_value, 2),
        "current_cogs_value": _round(current_cogs_value, 2),
        "prior_cogs_value": _round(prior_cogs_value, 2),
        "current_avg_receivables": _round(current_avg_ar, 2),
        "prior_avg_receivables": _round(prior_avg_ar, 2),
        "current_avg_payables": _round(current_avg_ap, 2),
        "prior_avg_payables": _round(prior_avg_ap, 2),
        "current_avg_inventory": _round(current_avg_inv, 2),
        "prior_avg_inventory": _round(prior_avg_inv, 2),
        "inventory_component_available": inventory_available,
        "current_dso_days": _round(current_dso, 6),
        "prior_dso_days": _round(prior_dso, 6),
        "dso_improvement_days": _round(dso_improvement, 6),
        "current_dio_days": _round(current_dio, 6),
        "prior_dio_days": _round(prior_dio, 6),
        "dio_improvement_days": _round(dio_improvement, 6),
        "current_dpo_days": _round(current_dpo, 6),
        "prior_dpo_days": _round(prior_dpo, 6),
        "dpo_extension_days": _round(dpo_extension, 6),
        "current_ccc_days": _round(current_ccc, 6),
        "prior_ccc_days": _round(prior_ccc, 6),
        "ccc_contraction_days": _round(ccc_contraction, 6),
        "revenue_growth": _round(revenue_growth, 6),
        "cogs_growth": _round(cogs_growth, 6),
        "gross_profit_growth": _round(gross_profit_growth, 6),
        "gross_profit_context_available": gross_profit_growth is not None,
        "current_revenue_filed": current_revenue["filed"],
        "current_cogs_filed": current_cogs["filed"],
        "current_receivables_filed": cur_ar["filed"],
        "current_payables_filed": cur_ap["filed"],
        "current_inventory_filed": None if cur_inv is None else cur_inv["filed"],
        "current_receivables_start_point_end": cur_ar_prev["end"],
        "current_payables_start_point_end": cur_ap_prev["end"],
        "current_inventory_start_point_end": None if cur_inv_prev is None else cur_inv_prev["end"],
        "prior_receivables_start_point_end": prior_ar_prev["end"],
        "prior_payables_start_point_end": prior_ap_prev["end"],
        "prior_inventory_start_point_end": None if prior_inv_prev is None else prior_inv_prev["end"],
        "fact_age_days": base._days_between(asof, current_revenue["filed"]),
        "known_at": "raw_quarterly_companyfacts_filed_and_signal_close_before_next_open_paper_entry",
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
            observation = _cash_cycle_observation(ticker, signal_date, quality_index[ticker])
            if observation is None:
                scan["failed_cash_cycle_gate"] += 1
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
            ccc = float(observation["ccc_contraction_days"] or 0.0)
            dso = max(float(observation["dso_improvement_days"] or 0.0), 0.0)
            dio = max(float(observation["dio_improvement_days"] or 0.0), 0.0)
            dpo_ext = max(float(observation["dpo_extension_days"] or 0.0), 0.0)
            revenue_growth = float(observation["revenue_growth"] or 0.0)
            gp_growth = observation.get("gross_profit_growth")
            gp_component = max(min(float(gp_growth), 0.50), -0.05) if gp_growth is not None else 0.0
            current_ccc = float(observation["current_ccc_days"] or 0.0)
            no_inventory_penalty = 0.02 if not observation["inventory_component_available"] else 0.0
            score = (
                0.018 * min(ccc, 70.0)
                + 0.010 * min(dso, 40.0)
                + 0.010 * min(dio, 40.0)
                + 0.006 * min(dpo_ext, 40.0)
                + 0.18 * max(min(revenue_growth, 0.60), -0.05)
                + 0.14 * gp_component
                + 0.54 * float(confirm["candidate_ret20_excess_spy"])
                + 0.14 * float(confirm["candidate_ret60_excess_spy"])
                + 0.09 * float(confirm["candidate_close_location"])
                + 0.030
                * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
                - 0.0015 * max(current_ccc - 120.0, 0.0)
                - no_inventory_penalty
            )
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "CASH_CONVERSION_CYCLE_CONTRACTION_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": observation["known_at"],
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_companyfacts": True,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    **{f"ccc_{k}": v for k, v in observation.items()},
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
            -float(row["ccc_ccc_contraction_days"] or 0.0),
            float(row["ccc_current_ccc_days"] or 0.0),
            -float(row["candidate_ret20_excess_spy"] or 0.0),
            -float(row["candidate_avg_dollar_volume_20d"] or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(rows)
    scan["candidate_signal_days"] = len({row["date"] for row in rows})
    scan["candidate_tickers"] = len({row["ticker"] for row in rows})
    scan["inventory_component_candidates"] = sum(
        1 for row in rows if row.get("ccc_inventory_component_available")
    )
    return rows, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "max_quarter_fact_age_days": MAX_QUARTER_FACT_AGE_DAYS,
        "max_point_fact_age_days": MAX_POINT_FACT_AGE_DAYS,
        "min_current_revenue": MIN_CURRENT_REVENUE,
        "min_current_cogs": MIN_CURRENT_COGS,
        "min_current_receivables": MIN_CURRENT_RECEIVABLES,
        "min_current_payables": MIN_CURRENT_PAYABLES,
        "min_current_inventory_if_present": MIN_CURRENT_INVENTORY,
        "min_ccc_contraction_days": MIN_CCC_CONTRACTION_DAYS,
        "min_operating_leg_improvement_days": MIN_OPERATING_LEG_IMPROVEMENT_DAYS,
        "min_dpo_extension_days": MIN_DPO_EXTENSION_DAYS,
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
        "positive_replay_lead_not_promoted_cash_conversion_cycle_contraction"
        if gate["passed"]
        else "rejected_cash_conversion_cycle_contraction_candidate_pool"
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
    base.FY_DURATION_MIN = QUARTER_DURATION_MIN
    base.FY_DURATION_MAX = QUARTER_DURATION_MAX
    base.MAX_ANNUAL_FACT_AGE_DAYS = MAX_QUARTER_FACT_AGE_DAYS
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
            "The cash-conversion-cycle contraction source cleared the numeric "
            "three-window replay screen, but remains only a replay lead because "
            "no shared daily/backtest helper was promoted."
        )
    else:
        interpretation = (
            "The cash-conversion-cycle contraction source did not clear Gate 4 "
            f"(failed: {', '.join(gate4['failed_reasons']) or 'none'}). Do not "
            "promote or tune this fixed working-capital cycle bundle on the "
            "same frozen windows."
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
            "mechanism_family": "production_visible_free_sec_companyfacts_working_capital_cycle_candidate_pool",
            "new_evidence_type": "raw_sec_companyfacts_cash_conversion_cycle_pit_field",
            "nearby_prior_experiments": [
                "exp-20260528-019",
                "exp-20260614-024",
                "exp-20260616-021",
                "exp-20260616-022",
                "exp-20260617-001",
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
        "quarter_duration_min": QUARTER_DURATION_MIN,
        "quarter_duration_max": QUARTER_DURATION_MAX,
        "max_quarter_fact_age_days": MAX_QUARTER_FACT_AGE_DAYS,
        "max_point_fact_age_days": MAX_POINT_FACT_AGE_DAYS,
        "comparable_quarter_min_gap_days": COMPARABLE_QUARTER_MIN_GAP_DAYS,
        "comparable_quarter_max_gap_days": COMPARABLE_QUARTER_MAX_GAP_DAYS,
        "min_current_revenue": MIN_CURRENT_REVENUE,
        "min_current_cogs": MIN_CURRENT_COGS,
        "min_ccc_contraction_days": MIN_CCC_CONTRACTION_DAYS,
        "min_operating_leg_improvement_days": MIN_OPERATING_LEG_IMPROVEMENT_DAYS,
        "min_dpo_extension_days": MIN_DPO_EXTENSION_DAYS,
        "revenue_tags": list(REVENUE_TAGS),
        "cogs_tags": list(COGS_TAGS),
        "receivable_tags": list(RECEIVABLE_TAGS),
        "payable_tags": list(PAYABLE_TAGS),
        "inventory_tags": list(INVENTORY_TAGS),
        "gross_profit_tags": list(GROSS_PROFIT_TAGS),
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
        "Quarterly revenue and COGS flow facts plus receivables/payables/"
        "inventory balance-sheet instant facts are read from raw SEC "
        "Companyfacts only when filed date <= signal date. Current DSO, DIO, "
        "and DPO use average current/previous point balances over current "
        "quarterly revenue or COGS; prior values use the comparable prior-year "
        "quarter. The decision variable is CCC = DSO + DIO - DPO contracting "
        "while at least one operating leg improves and DPO does not collapse. "
        "Price confirmation uses only signal-date OHLCV. Paper entry is the "
        "next available open with existing entry slippage; exit is the close "
        "10 trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    payload["backtest_protocol"]["companyfacts_source"] = _repo_rel(RAW_COMPANYFACTS_CACHE)
    payload["gate2"]["runtime_fields"] = [
        "raw SEC companyfacts quarterly revenue and COGS facts",
        "raw SEC companyfacts receivables, payables, and optional inventory instant facts",
        "raw SEC companyfacts quarterly GrossProfit facts when available",
        "raw SEC companyfacts filed date and period end",
        "warehouse ticker_universe CIK mapping",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A retry needs materially different PIT working-capital evidence such "
        "as supplier/customer concentration, payment-term disclosure, channel "
        "inventory context, or closed forward replacement-value rows. Do not "
        "sweep CCC, DSO, DIO, DPO, fact-age, price, top-N, hold, cooldown, or "
        "notional thresholds on these frozen windows."
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
            "Do not retry by sweeping CCC, DSO, DIO, DPO, fact-age, revenue/"
            "COGS/gross-profit floors, RS/close/volume/vol guards, top-N, hold "
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
            f"# {EXPERIMENT_ID} Cash Conversion Cycle Contraction",
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
