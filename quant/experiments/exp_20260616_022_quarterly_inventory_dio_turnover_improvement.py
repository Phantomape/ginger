"""exp-20260616-022: quarterly inventory DIO/turnover improvement scout.

Replay-only alpha search. The single decision hypothesis is a PIT free SEC
Companyfacts candidate source: production-universe names whose latest reported
quarterly days-in-inventory outstanding (DIO) is improving versus the comparable
prior-year quarter because inventory is turning faster versus CostOfRevenue,
while COGS is not materially contracting. This should separate true sell-through
from the broader rejected annual inventory/revenue and annual DIO fields.

Why this is a materially new free-data edge: InventoryNet is a balance-sheet
INSTANT fact (no FY duration) while CostOfRevenue is a filed quarterly flow.
This runner matches InventoryNet to current and prior quarter ends, compares
current quarterly DIO against the comparable prior-year quarter, and only uses
facts known by filed date. The playbook explicitly required a sharper PIT
inventory discriminator such as quarterly inventory turnover after
exp-20260616-018 and exp-20260616-019 rejected annual inventory definitions on
old_thin regression and drawdown drift.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive replay is
only a lead until a shared historical/daily helper reproduces it. This is a
private scout because quarterly CostOfRevenue + required inventory-point
coverage is not yet proven sufficient across the three canonical windows.
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


EXPERIMENT_ID = "exp-20260616-022"
STEM = "quarterly_inventory_dio_turnover_improvement"
TRIAL_FAMILY = "quarterly_inventory_dio_turnover_improvement_candidate_pool"
TRIAL_VARIANT_ID = "quarterly_inventory_dio_turnover_improvement_top1_next_open_10d_v1"
CHANGED_VARIABLE = "quarterly_inventory_dio_turnover_improvement_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
RAW_COMPANYFACTS_CACHE = REPO_ROOT / "data" / "cache" / "sec" / "companyfacts"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260616_022_{STEM}.json"
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
MAX_INVENTORY_POINT_AGE_DAYS = 220
COMPARABLE_QUARTER_MIN_GAP_DAYS = 250
COMPARABLE_QUARTER_MAX_GAP_DAYS = 450
QUARTER_DIO_DAYS = 91.25
MIN_CURRENT_COGS = 250_000_000.0
MIN_CURRENT_INVENTORY = 50_000_000.0
MAX_CURRENT_DIO_DAYS = 180.0
MIN_DIO_IMPROVEMENT_DAYS = 3.0
MIN_COGS_GROWTH = -0.05

INVENTORY_TAGS = ("InventoryNet",)
COGS_TAGS = (
    "CostOfRevenue",
    "CostOfGoodsAndServicesSold",
    "CostOfGoodsSold",
    "CostOfGoodsSoldExcludingDepreciationDepletionAndAmortization",
)

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "quarterly_coverage_too_thin",
        "window_ev_regression",
        "accepted_comparator_not_beaten",
        "drawdown_drift",
        "sector_concentration",
    ],
    "confidence_reason": (
        "The annual inventory/revenue and annual DIO scouts were economically "
        "positive but failed old_thin and drawdown. The playbook explicitly "
        "requires a sharper PIT inventory discriminator such as quarterly "
        "turnover before any retry. This tests InventoryNet plus quarterly "
        "CostOfRevenue turnover rather than another annual threshold. Risk is "
        "high because standalone quarterly CostOfRevenue coverage may be thin "
        "and the field may still relabel liquid momentum."
    ),
    "recorded_at": "2026-06-16T19:10:00+00:00",
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
            "missing raw SEC InventoryNet instant facts, missing standalone "
            "quarterly CostOfRevenue, missing current/prior inventory points, "
            "missing comparable prior-year quarter, stale facts, missing CIK "
            "mapping, missing OHLCV, missing next open, or missing 10d exit "
            "rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same raw "
        "SEC InventoryNet instant mapping, filed-date PIT quarterly "
        "CostOfRevenue facts, comparable-quarter DIO/turnover improvement gate, "
        "liquid SPY-relative confirmation, cooldown, next-open paper entry, "
        "10-day exit, costs, and concentration controls in both historical "
        "replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: raw SEC Companyfacts quarterly DIO falling versus the "
        "comparable prior-year quarter (average InventoryNet / quarterly "
        "CostOfRevenue improving = faster sell-through), with non-collapsing "
        "COGS and liquid SPY-relative leadership, may identify demand-confirmed "
        "candidates before a 10-trading-day continuation leg."
    ),
    "2_history_check": {
        "exp-20260616-018": (
            "Rejected inventory-to-revenue leanness despite strong aggregate "
            "EV/PnL because old_thin regressed and drawdown drift was too high. "
            "Its closeout and the playbook explicitly requested a sharper PIT "
            "inventory discriminator such as quarterly inventory turnover."
        ),
        "exp-20260616-019": (
            "Rejected annual inventory DIO/turnover improvement despite positive "
            "aggregate EV/PnL because old_thin regressed and drawdown drift "
            "exceeded the guardrail. This run changes the evidence frequency to "
            "standalone quarterly COGS and comparable-quarter DIO, not thresholds."
        ),
        "exp-20260616-021": (
            "Rejected annual receivables DSO improvement; related working-"
            "capital family but different field. Avoid receivables retuning here."
        ),
        "exp-20260614-024": (
            "Rejected quarterly cash-conversion improvement; relevant only as "
            "evidence that quarterly PIT Companyfacts constructions can be "
            "tested, not as this inventory-turnover decision variable."
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
        "exp_20260616_022_quarterly_inventory_dio_turnover_improvement.py"
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
    """Read balance-sheet INSTANT facts (no FY duration) from raw companyfacts.

    InventoryNet et al. are reported as a point-in-time USD value keyed by an
    `end` date with no `start` (or start == end). The FY-duration reader used
    for income-statement flows would drop every one of these facts.
    """
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
                    "start": end,
                    "end": end,
                    "value": value,
                    "tag": tag,
                    "form": str(raw.get("form") or ""),
                    "fy": raw.get("fy"),
                    "fp": str(raw.get("fp") or ""),
                }
            )
    facts.sort(key=lambda row: (row["end"], row["filed"], row["tag"], row["value"]))
    return facts


def _raw_quarterly_facts(usgaap: dict[str, Any], tags: tuple[str, ...]) -> list[dict[str, Any]]:
    """Read standalone quarterly USD flow facts from raw companyfacts."""
    facts: list[dict[str, Any]] = []
    for tag in tags:
        tag_payload = usgaap.get(tag) or {}
        for raw in tag_payload.get("units", {}).get("USD", []):
            duration = rd._duration_days(raw)
            fp = str(raw.get("fp") or "")
            if duration is None or not (QUARTER_DURATION_MIN <= duration <= QUARTER_DURATION_MAX):
                continue
            if fp == "FY":
                continue
            filed = str(raw.get("filed") or "")[:10]
            start = str(raw.get("start") or "")[:10]
            end = str(raw.get("end") or "")[:10]
            value = rd._float_or_none(raw.get("val"))
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
        inventory_facts = _raw_instant_facts(usgaap, INVENTORY_TAGS)
        cogs_facts = _raw_quarterly_facts(usgaap, COGS_TAGS)
        if not inventory_facts:
            stats["tickers_missing_raw_inventory"] += 1
            continue
        if not cogs_facts:
            stats["tickers_missing_raw_quarterly_cogs"] += 1
            continue
        index[ticker] = {
            "inventory": inventory_facts,
            "cogs": cogs_facts,
        }
        stats["tickers_with_raw_inventory_and_cogs"] += 1
        stats["raw_inventory_fact_count"] += len(inventory_facts)
        stats["raw_quarterly_cogs_fact_count"] += len(cogs_facts)

    summary = {
        "raw_companyfacts_cache": _repo_rel(RAW_COMPANYFACTS_CACHE),
        "inventory_tags": list(INVENTORY_TAGS),
        "cogs_tags": list(COGS_TAGS),
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


def _previous_inventory_point(
    inventory_facts: list[dict[str, Any]],
    *,
    asof: str,
    before_end: str,
) -> dict[str, Any] | None:
    return rd._latest_period_fact(inventory_facts, asof=asof, before_end=before_end)


def _inventory_observation(
    ticker: str,
    asof: str,
    facts: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    current_cogs = rd._latest_period_fact(facts["cogs"], asof=asof)
    if current_cogs is None:
        return None
    if base._days_between(asof, current_cogs["filed"]) > MAX_QUARTER_FACT_AGE_DAYS:
        return None
    current_inventory = rd._latest_period_fact(
        facts["inventory"], asof=asof, end=current_cogs["end"]
    )
    if current_inventory is None:
        return None
    if base._days_between(asof, current_inventory["filed"]) > MAX_INVENTORY_POINT_AGE_DAYS:
        return None
    current_start_inventory = _previous_inventory_point(
        facts["inventory"], asof=asof, before_end=current_inventory["end"]
    )
    if current_start_inventory is None:
        return None

    prior_cogs = _prior_comparable_quarter_fact(
        facts["cogs"], asof=asof, current_end=current_cogs["end"]
    )
    if prior_cogs is None:
        return None
    if base._days_between(asof, prior_cogs["filed"]) > MAX_QUARTER_FACT_AGE_DAYS + 370:
        return None
    prior_inventory = rd._latest_period_fact(
        facts["inventory"], asof=asof, end=prior_cogs["end"]
    )
    if prior_inventory is None:
        return None
    prior_start_inventory = _previous_inventory_point(
        facts["inventory"], asof=asof, before_end=prior_inventory["end"]
    )
    if prior_start_inventory is None:
        return None

    current_inventory_value = abs(float(current_inventory["value"]))
    current_start_inventory_value = abs(float(current_start_inventory["value"]))
    prior_inventory_value = abs(float(prior_inventory["value"]))
    prior_start_inventory_value = abs(float(prior_start_inventory["value"]))
    current_cogs_value = float(current_cogs["value"])
    prior_cogs_value = float(prior_cogs["value"])
    if (
        current_inventory_value < MIN_CURRENT_INVENTORY
        or current_cogs_value < MIN_CURRENT_COGS
        or prior_cogs_value <= 0.0
        or current_start_inventory_value <= 0.0
        or prior_inventory_value <= 0.0
        or prior_start_inventory_value <= 0.0
    ):
        return None

    current_avg_inventory = (current_inventory_value + current_start_inventory_value) / 2.0
    prior_avg_inventory = (prior_inventory_value + prior_start_inventory_value) / 2.0
    if current_avg_inventory <= 0.0 or prior_avg_inventory <= 0.0:
        return None

    current_dio = QUARTER_DIO_DAYS * current_avg_inventory / current_cogs_value
    prior_dio = QUARTER_DIO_DAYS * prior_avg_inventory / prior_cogs_value
    dio_improvement_days = prior_dio - current_dio
    current_turnover = current_cogs_value / current_avg_inventory
    prior_turnover = prior_cogs_value / prior_avg_inventory
    turnover_improvement = current_turnover - prior_turnover
    cogs_growth = (current_cogs_value - prior_cogs_value) / abs(prior_cogs_value)
    inventory_growth = (current_inventory_value - prior_inventory_value) / abs(
        prior_inventory_value
    )
    if current_dio > MAX_CURRENT_DIO_DAYS:
        return None
    if dio_improvement_days < MIN_DIO_IMPROVEMENT_DAYS:
        return None
    if cogs_growth < MIN_COGS_GROWTH:
        return None

    return {
        "ticker": ticker,
        "current_period_end": current_inventory["end"],
        "current_cogs_period_start": current_cogs["start"],
        "current_inventory_filed": current_inventory["filed"],
        "current_cogs_filed": current_cogs["filed"],
        "current_inventory_value": _round(current_inventory_value, 2),
        "current_start_inventory_value": _round(current_start_inventory_value, 2),
        "prior_inventory_value": _round(prior_inventory_value, 2),
        "prior_start_inventory_value": _round(prior_start_inventory_value, 2),
        "current_cogs_value": _round(current_cogs_value, 2),
        "prior_cogs_value": _round(prior_cogs_value, 2),
        "prior_period_end": prior_inventory["end"],
        "prior_cogs_period_start": prior_cogs["start"],
        "current_inventory_start_point_end": current_start_inventory["end"],
        "prior_inventory_start_point_end": prior_start_inventory["end"],
        "comparable_quarter_gap_days": (
            base.framework._parse_date(current_cogs["end"])
            - base.framework._parse_date(prior_cogs["end"])
        ).days,
        "current_cogs_duration_days": current_cogs["duration_days"],
        "prior_cogs_duration_days": prior_cogs["duration_days"],
        "current_avg_inventory": _round(current_avg_inventory, 2),
        "prior_avg_inventory": _round(prior_avg_inventory, 2),
        "current_dio_days": _round(current_dio, 6),
        "prior_dio_days": _round(prior_dio, 6),
        "dio_improvement_days": _round(dio_improvement_days, 6),
        "current_turnover": _round(current_turnover, 6),
        "prior_turnover": _round(prior_turnover, 6),
        "turnover_improvement": _round(turnover_improvement, 6),
        "cogs_growth": _round(cogs_growth, 6),
        "inventory_growth": _round(inventory_growth, 6),
        "fact_age_days": base._days_between(asof, current_inventory["filed"]),
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
            observation = _inventory_observation(ticker, signal_date, quality_index[ticker])
            if observation is None:
                scan["failed_dio_turnover_gate"] += 1
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
            dio_improvement = float(observation["dio_improvement_days"] or 0.0)
            turnover_improvement = float(observation["turnover_improvement"] or 0.0)
            cogs_growth = float(observation["cogs_growth"] or 0.0)
            score = (
                0.025 * min(dio_improvement, 60.0)
                + 0.35 * max(min(turnover_improvement, 2.0), -0.25)
                + 0.20 * max(min(cogs_growth, 0.60), -0.05)
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
                    "source": "QUARTERLY_INVENTORY_DIO_TURNOVER_PAPER",
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
                    **{f"dio_{k}": v for k, v in observation.items()},
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
            -float(row["dio_dio_improvement_days"] or 0.0),
            -float(row["dio_turnover_improvement"] or 0.0),
            -float(row["dio_cogs_growth"] or 0.0),
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
        "quarter_duration_min": QUARTER_DURATION_MIN,
        "quarter_duration_max": QUARTER_DURATION_MAX,
        "max_quarter_fact_age_days": MAX_QUARTER_FACT_AGE_DAYS,
        "max_inventory_point_age_days": MAX_INVENTORY_POINT_AGE_DAYS,
        "comparable_quarter_min_gap_days": COMPARABLE_QUARTER_MIN_GAP_DAYS,
        "comparable_quarter_max_gap_days": COMPARABLE_QUARTER_MAX_GAP_DAYS,
        "quarter_dio_days": QUARTER_DIO_DAYS,
        "min_current_cogs": MIN_CURRENT_COGS,
        "min_current_inventory": MIN_CURRENT_INVENTORY,
        "max_current_dio_days": MAX_CURRENT_DIO_DAYS,
        "min_dio_improvement_days": MIN_DIO_IMPROVEMENT_DAYS,
        "min_cogs_growth": MIN_COGS_GROWTH,
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
        "positive_replay_lead_not_promoted_quarterly_inventory_dio_turnover_improvement"
        if gate["passed"]
        else "rejected_quarterly_inventory_dio_turnover_improvement_candidate_pool"
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
            "The quarterly inventory DIO/turnover-improvement source cleared "
            "the numeric three-window replay screen, but remains only a replay "
            "lead because no shared daily/backtest helper was promoted."
        )
    else:
        interpretation = (
            "The quarterly inventory DIO/turnover-improvement source did not "
            f"clear Gate 4 (failed: {', '.join(gate4['failed_reasons']) or 'none'}). "
            "Do not promote or tune this fixed comparable-quarter inventory "
            "turnover bundle on the same frozen windows."
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
            "mechanism_family": "production_visible_free_sec_companyfacts_quarterly_inventory_quality_candidate_pool",
            "new_evidence_type": "raw_sec_companyfacts_quarterly_inventory_dio_turnover_pit_field",
            "nearby_prior_experiments": [
                "exp-20260616-018",
                "exp-20260616-019",
                "exp-20260616-021",
                "exp-20260614-024",
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
        "max_inventory_point_age_days": MAX_INVENTORY_POINT_AGE_DAYS,
        "comparable_quarter_min_gap_days": COMPARABLE_QUARTER_MIN_GAP_DAYS,
        "comparable_quarter_max_gap_days": COMPARABLE_QUARTER_MAX_GAP_DAYS,
        "quarter_dio_days": QUARTER_DIO_DAYS,
        "min_current_cogs": MIN_CURRENT_COGS,
        "min_current_inventory": MIN_CURRENT_INVENTORY,
        "max_current_dio_days": MAX_CURRENT_DIO_DAYS,
        "min_dio_improvement_days": MIN_DIO_IMPROVEMENT_DAYS,
        "min_cogs_growth": MIN_COGS_GROWTH,
        "inventory_tags": list(INVENTORY_TAGS),
        "cogs_tags": list(COGS_TAGS),
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
        "InventoryNet is read as a raw SEC Companyfacts balance-sheet INSTANT "
        "fact and matched to standalone quarterly CostOfRevenue facts with "
        "60-130 day durations. Both inventory points and COGS flows are known "
        "only by filed date (<= signal date). Current DIO uses average current/"
        "previous inventory over current quarterly COGS; prior DIO uses average "
        "prior-year comparable-quarter inventory/previous inventory over "
        "prior-year comparable quarterly COGS. The rule requires DIO to improve "
        "versus that comparable quarter while COGS is not materially contracting. "
        "Price confirmation uses only signal-date OHLCV. Paper entry is the next "
        "available open with existing entry slippage; exit is the close 10 "
        "trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    payload["backtest_protocol"]["companyfacts_source"] = _repo_rel(RAW_COMPANYFACTS_CACHE)
    payload["gate2"]["runtime_fields"] = [
        "raw SEC companyfacts InventoryNet instant facts",
        "raw SEC companyfacts standalone quarterly CostOfRevenue facts",
        "raw SEC companyfacts filed date and period end",
        "warehouse ticker_universe CIK mapping",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A retry needs materially different PIT inventory-quality evidence such "
        "as finished-goods vs raw-materials decomposition, quarterly inventory "
        "turnover with richer segment detail, or closed forward replacement-"
        "value rows. Do not sweep the inventory/COGS tag list, quarterly DIO "
        "threshold, COGS-growth floor, fact freshness, price guards, top-N, "
        "hold, cooldown, or notional on these frozen windows."
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
            "Do not retry by sweeping the inventory/COGS tag list, quarterly "
            "DIO improvement threshold, COGS-growth floor, fact freshness, "
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
            f"# {EXPERIMENT_ID} Quarterly Inventory DIO Turnover Improvement",
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
