"""exp-20260617-012: SBC grant-value backlog relief scout.

Replay-only alpha search. The single decision hypothesis is a PIT free SEC
Companyfacts candidate source: production-universe names whose unrecognized
nonvested share-based-compensation award cost backlog is falling versus revenue
may be experiencing future dilution-cost relief after the accepted SBC expense
burden source.

This is deliberately not a shared helper yet because the grant-value backlog
tag is an instant Companyfacts item, frequently reported quarterly, while the
normalizers are annual revenue and gross profit. A positive replay is only a
lead until a shared historical/daily helper reproduces the same PIT field
alignment. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260616_010_sga_operating_expense_leverage as template
import exp_20260616_017_sbc_per_share_buyback_adjusted as sbc_ps


base = template.base
rd = template.rd

EXPERIMENT_ID = "exp-20260617-012"
STEM = "sbc_grant_value_backlog_relief"
TRIAL_FAMILY = "sbc_grant_value_backlog_relief_candidate_pool"
TRIAL_VARIANT_ID = "sbc_grant_value_backlog_relief_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sbc_unrecognized_grant_value_backlog_relief_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
RAW_COMPANYFACTS_CACHE = REPO_ROOT / "data" / "cache" / "sec" / "companyfacts"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260617_012_{STEM}.json"
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
MAX_BACKLOG_FACT_AGE_DAYS = 430
MIN_CURRENT_REVENUE = 250_000_000.0
MIN_CURRENT_GROSS_PROFIT = 20_000_000.0
MIN_CURRENT_BACKLOG = 20_000_000.0
MIN_GROSS_MARGIN = 0.12
MAX_CURRENT_BACKLOG_TO_REVENUE = 0.60
MIN_BACKLOG_RATIO_IMPROVEMENT = 0.005
MIN_BACKLOG_IMPROVEMENT_PCT = 0.05
MIN_BACKLOG_PERIOD_GAP_DAYS = 45
MAX_BACKLOG_PERIOD_GAP_DAYS = 460
MIN_REVENUE_GROWTH = -0.05
MIN_GROSS_PROFIT_GROWTH = -0.10

GRANT_BACKLOG_TAGS = (
    "EmployeeServiceShareBasedCompensationNonvestedAwardsTotalCompensationCostNotYetRecognized",
    "EmployeeServiceShareBasedCompensationUnrecognizedCompensationCostsOnNonvestedAwards",
)
REVENUE_TAGS = rd.REVENUE_TAGS
GROSS_PROFIT_TAGS = ("GrossProfit",)
ALLOWED_BACKLOG_FORMS = {
    "10-K",
    "10-K/A",
    "10-Q",
    "10-Q/A",
    "20-F",
    "20-F/A",
    "6-K",
}

ACCEPTED_SBC_COMPARATOR = sbc_ps.ACCEPTED_SBC_COMPARATOR

PREDICTION = {
    "success_probability": 0.14,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "field_coverage_too_thin",
        "window_regression",
        "accepted_sbc_comparator_not_beaten",
        "natural_vesting_decay_not_alpha",
        "software_growth_concentration",
    ],
    "confidence_reason": (
        "The playbook forbids nearby SBC threshold retunes but explicitly names "
        "grant-value normalization as valid new evidence. The local raw SEC "
        "Companyfacts cache exposes unrecognized nonvested award cost tags, but "
        "the item is instant/quarterly and may mostly capture normal vesting "
        "decay rather than a tradable future dilution relief edge."
    ),
    "recorded_at": "2026-06-17T10:06:24+00:00",
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
            "missing raw SEC unrecognized nonvested SBC award cost backlog, "
            "missing annual revenue or gross-profit normalizer, missing prior "
            "backlog comparison point, stale facts, missing CIK mapping, missing "
            "OHLCV, missing next open, or missing 10d exit rejects the paper "
            "candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same raw "
        "SEC instant grant-value backlog tag mapping, filed-date PIT annual "
        "revenue/gross-profit normalization, liquid SPY-relative confirmation, "
        "cooldown, next-open paper entry, 10-day exit, costs, and concentration "
        "controls in both historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: after the accepted SBC expense burden source, a "
        "material decline in unrecognized nonvested award compensation cost "
        "backlog relative to revenue may identify future dilution-cost relief "
        "when revenue/gross-profit health and liquid SPY-relative price "
        "confirmation are present."
    ),
    "2_history_check": {
        "exp-20260616-015": (
            "Accepted shared default-off recognized SBC/revenue burden "
            "improvement: aggregate EV +0.9438, PnL +$15,748.19, all three "
            "canonical windows positive."
        ),
        "exp-20260616-017": (
            "Rejected per-share buyback-adjusted SBC extension. This run tests "
            "unrecognized grant-value backlog relief, not recognized SBC per "
            "share or buyback offset."
        ),
        "exp-20260616-013/exp-20260613-026": (
            "Form 4 vesting/exercise near-neighbors were weak or zero-coverage. "
            "This run uses SEC Companyfacts grant-value backlog rows instead of "
            "insider transaction rows."
        ),
        "playbook_current_rule": (
            "SBC threshold/tag/fact-age/top-N/notional retunes are frozen; "
            "grant-value normalization is listed as valid new evidence."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL "
        "must be positive, no window EV/PnL regression, at least two "
        "EV-improved windows, at least 20 paper trades across all 3 windows, "
        "survival >=5%, drawdown drift <=0.5pp, concentration pass, and "
        "accepted compression, distribution, and accepted SBC burden standalone "
        "comparators must be beaten. Replay-only positives are leads until "
        "shared daily/backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260617_012_sbc_grant_value_backlog_relief.py"
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


def _raw_instant_backlog_facts(usgaap: dict[str, Any], tags: tuple[str, ...]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for tag in tags:
        tag_payload = usgaap.get(tag) or {}
        for raw in tag_payload.get("units", {}).get("USD", []):
            start = str(raw.get("start") or "")[:10]
            end = str(raw.get("end") or "")[:10]
            filed = str(raw.get("filed") or "")[:10]
            form = str(raw.get("form") or "")
            value = _float_or_none(raw.get("val"))
            if start:
                continue
            if form and form not in ALLOWED_BACKLOG_FORMS:
                continue
            if not filed or not end or value is None or value < 0.0:
                continue
            facts.append(
                {
                    "filed": filed,
                    "end": end,
                    "value": value,
                    "tag": tag,
                    "form": form,
                    "fy": raw.get("fy"),
                    "fp": str(raw.get("fp") or ""),
                    "frame": raw.get("frame"),
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
        backlog_facts = _raw_instant_backlog_facts(usgaap, GRANT_BACKLOG_TAGS)
        revenue_facts = rd._raw_annual_facts(usgaap, REVENUE_TAGS)
        gross_profit_facts = rd._raw_annual_facts(usgaap, GROSS_PROFIT_TAGS)
        if not backlog_facts:
            stats["tickers_missing_raw_instant_grant_backlog"] += 1
            continue
        if not revenue_facts:
            stats["tickers_missing_raw_annual_revenue"] += 1
            continue
        if not gross_profit_facts:
            stats["tickers_missing_raw_annual_gross_profit"] += 1
            continue
        index[ticker] = {
            "backlog": backlog_facts,
            "revenue": revenue_facts,
            "gross_profit": gross_profit_facts,
        }
        stats["tickers_with_raw_backlog_revenue_gross_profit"] += 1
        stats["raw_instant_grant_backlog_fact_count"] += len(backlog_facts)
        stats["raw_annual_revenue_fact_count"] += len(revenue_facts)
        stats["raw_annual_gross_profit_fact_count"] += len(gross_profit_facts)

    summary = {
        "raw_companyfacts_cache": _repo_rel(RAW_COMPANYFACTS_CACHE),
        "grant_backlog_tags": list(GRANT_BACKLOG_TAGS),
        "revenue_tags": list(REVENUE_TAGS),
        "gross_profit_tags": list(GROSS_PROFIT_TAGS),
        "allowed_backlog_forms": sorted(ALLOWED_BACKLOG_FORMS),
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


def _backlog_tag_priority(tag: str) -> int:
    try:
        return GRANT_BACKLOG_TAGS.index(tag)
    except ValueError:
        return len(GRANT_BACKLOG_TAGS)


def _latest_backlog_fact(
    facts: list[dict[str, Any]],
    *,
    asof: str,
    before_end: str | None = None,
    tag: str | None = None,
) -> dict[str, Any] | None:
    candidates = []
    for fact in facts:
        if fact["filed"] > asof:
            continue
        if before_end is not None and fact["end"] >= before_end:
            continue
        if tag is not None and fact.get("tag") != tag:
            continue
        candidates.append(fact)
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda row: (
            row["end"],
            row["filed"],
            -_backlog_tag_priority(str(row.get("tag") or "")),
            float(row.get("value") or 0.0),
        ),
    )


def _latest_annual_fact_before_or_at(
    facts: list[dict[str, Any]],
    *,
    asof: str,
    end_lte: str,
) -> dict[str, Any] | None:
    candidates = []
    for fact in facts:
        if fact["filed"] > asof:
            continue
        if fact["end"] > end_lte:
            continue
        candidates.append(fact)
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda row: (row["end"], row["filed"], float(row.get("value") or 0.0), row["tag"]),
    )


def _backlog_relief_observation(
    ticker: str,
    asof: str,
    facts: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    current_backlog = _latest_backlog_fact(facts["backlog"], asof=asof)
    if current_backlog is None:
        return None
    if base._days_between(asof, current_backlog["filed"]) > MAX_BACKLOG_FACT_AGE_DAYS:
        return None

    prior_backlog = _latest_backlog_fact(
        facts["backlog"],
        asof=asof,
        before_end=current_backlog["end"],
        tag=str(current_backlog.get("tag") or ""),
    )
    if prior_backlog is None:
        return None
    period_gap_days = base._days_between(current_backlog["end"], prior_backlog["end"])
    if period_gap_days < MIN_BACKLOG_PERIOD_GAP_DAYS or period_gap_days > MAX_BACKLOG_PERIOD_GAP_DAYS:
        return None

    current_revenue = _latest_annual_fact_before_or_at(
        facts["revenue"], asof=asof, end_lte=current_backlog["end"]
    )
    current_gross_profit = _latest_annual_fact_before_or_at(
        facts["gross_profit"], asof=asof, end_lte=current_backlog["end"]
    )
    prior_revenue = _latest_annual_fact_before_or_at(
        facts["revenue"], asof=asof, end_lte=prior_backlog["end"]
    )
    prior_gross_profit = _latest_annual_fact_before_or_at(
        facts["gross_profit"], asof=asof, end_lte=prior_backlog["end"]
    )
    previous_annual_revenue = None
    previous_annual_gross_profit = None
    if current_revenue is not None:
        previous_annual_revenue = rd._latest_period_fact(
            facts["revenue"], asof=asof, before_end=current_revenue["end"]
        )
    if current_gross_profit is not None:
        previous_annual_gross_profit = rd._latest_period_fact(
            facts["gross_profit"], asof=asof, before_end=current_gross_profit["end"]
        )
    if (
        current_revenue is None
        or current_gross_profit is None
        or prior_revenue is None
        or prior_gross_profit is None
        or previous_annual_revenue is None
        or previous_annual_gross_profit is None
    ):
        return None

    current_backlog_value = abs(float(current_backlog["value"]))
    prior_backlog_value = abs(float(prior_backlog["value"]))
    current_revenue_value = float(current_revenue["value"])
    prior_revenue_value = float(prior_revenue["value"])
    current_gross_profit_value = float(current_gross_profit["value"])
    prior_gross_profit_value = float(prior_gross_profit["value"])
    previous_annual_revenue_value = float(previous_annual_revenue["value"])
    previous_annual_gross_profit_value = float(previous_annual_gross_profit["value"])
    if (
        current_backlog_value < MIN_CURRENT_BACKLOG
        or prior_backlog_value <= 0.0
        or current_revenue_value < MIN_CURRENT_REVENUE
        or prior_revenue_value <= 0.0
        or current_gross_profit_value < MIN_CURRENT_GROSS_PROFIT
        or prior_gross_profit_value <= 0.0
        or previous_annual_revenue_value <= 0.0
        or previous_annual_gross_profit_value <= 0.0
    ):
        return None

    current_ratio = current_backlog_value / current_revenue_value
    prior_ratio = prior_backlog_value / prior_revenue_value
    ratio_improvement = prior_ratio - current_ratio
    backlog_improvement_pct = (prior_backlog_value - current_backlog_value) / prior_backlog_value
    gross_margin = current_gross_profit_value / current_revenue_value
    revenue_growth = (current_revenue_value - previous_annual_revenue_value) / abs(
        previous_annual_revenue_value
    )
    gross_profit_growth = (current_gross_profit_value - previous_annual_gross_profit_value) / abs(
        previous_annual_gross_profit_value
    )
    if current_ratio > MAX_CURRENT_BACKLOG_TO_REVENUE:
        return None
    if ratio_improvement < MIN_BACKLOG_RATIO_IMPROVEMENT:
        return None
    if backlog_improvement_pct < MIN_BACKLOG_IMPROVEMENT_PCT:
        return None
    if gross_margin < MIN_GROSS_MARGIN:
        return None
    if revenue_growth < MIN_REVENUE_GROWTH:
        return None
    if gross_profit_growth < MIN_GROSS_PROFIT_GROWTH:
        return None

    return {
        "ticker": ticker,
        "current_period_end": current_backlog["end"],
        "current_backlog_filed": current_backlog["filed"],
        "current_backlog_tag": current_backlog.get("tag"),
        "current_backlog_form": current_backlog.get("form"),
        "current_backlog_fp": current_backlog.get("fp"),
        "current_backlog_value": _round(current_backlog_value, 2),
        "prior_period_end": prior_backlog["end"],
        "prior_backlog_value": _round(prior_backlog_value, 2),
        "period_gap_days": period_gap_days,
        "current_revenue_period_end": current_revenue["end"],
        "current_revenue_value": _round(current_revenue_value, 2),
        "current_gross_profit_value": _round(current_gross_profit_value, 2),
        "prior_revenue_period_end": prior_revenue["end"],
        "prior_revenue_value": _round(prior_revenue_value, 2),
        "prior_gross_profit_value": _round(prior_gross_profit_value, 2),
        "previous_annual_revenue_period_end": previous_annual_revenue["end"],
        "previous_annual_revenue_value": _round(previous_annual_revenue_value, 2),
        "current_backlog_to_revenue": _round(current_ratio, 6),
        "prior_backlog_to_revenue": _round(prior_ratio, 6),
        "backlog_ratio_improvement": _round(ratio_improvement, 6),
        "backlog_improvement_pct": _round(backlog_improvement_pct, 6),
        "gross_margin": _round(gross_margin, 6),
        "revenue_growth": _round(revenue_growth, 6),
        "gross_profit_growth": _round(gross_profit_growth, 6),
        "fact_age_days": base._days_between(asof, current_backlog["filed"]),
        "known_at": "raw_instant_companyfacts_filed_and_signal_close_before_next_open_paper_entry",
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
            observation = _backlog_relief_observation(ticker, signal_date, quality_index[ticker])
            if observation is None:
                scan["failed_sbc_grant_value_backlog_gate"] += 1
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
            ratio_improvement = float(observation["backlog_ratio_improvement"] or 0.0)
            improvement_pct = float(observation["backlog_improvement_pct"] or 0.0)
            revenue_growth = float(observation["revenue_growth"] or 0.0)
            gross_growth = float(observation["gross_profit_growth"] or 0.0)
            score = (
                3.8 * min(ratio_improvement, 0.12)
                + 0.55 * min(improvement_pct, 0.70)
                + 0.18 * max(min(revenue_growth, 0.60), -0.05)
                + 0.16 * max(min(gross_growth, 0.60), -0.10)
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
                    "source": "SBC_GRANT_VALUE_BACKLOG_RELIEF_PAPER",
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
                    **{f"sbc_gv_{key}": value for key, value in observation.items()},
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
            -float(row["sbc_gv_backlog_ratio_improvement"] or 0.0),
            -float(row["sbc_gv_backlog_improvement_pct"] or 0.0),
            -float(row["sbc_gv_revenue_growth"] or 0.0),
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
        "max_backlog_fact_age_days": MAX_BACKLOG_FACT_AGE_DAYS,
        "min_current_revenue": MIN_CURRENT_REVENUE,
        "min_current_gross_profit": MIN_CURRENT_GROSS_PROFIT,
        "min_current_backlog": MIN_CURRENT_BACKLOG,
        "min_gross_margin": MIN_GROSS_MARGIN,
        "max_current_backlog_to_revenue": MAX_CURRENT_BACKLOG_TO_REVENUE,
        "min_backlog_ratio_improvement": MIN_BACKLOG_RATIO_IMPROVEMENT,
        "min_backlog_improvement_pct": MIN_BACKLOG_IMPROVEMENT_PCT,
        "min_backlog_period_gap_days": MIN_BACKLOG_PERIOD_GAP_DAYS,
        "max_backlog_period_gap_days": MAX_BACKLOG_PERIOD_GAP_DAYS,
        "min_revenue_growth": MIN_REVENUE_GROWTH,
        "min_gross_profit_growth": MIN_GROSS_PROFIT_GROWTH,
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
    if ev_delta <= ACCEPTED_SBC_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_sbc_ev_not_beaten")
    if pnl_delta <= ACCEPTED_SBC_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_sbc_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["accepted_compression_comparator"] = base.COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = base.DISTRIBUTION_COMPARATOR
    gate["accepted_sbc_comparator"] = ACCEPTED_SBC_COMPARATOR
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_not_promoted_sbc_grant_value_backlog_relief"
        if gate["passed"]
        else "rejected_sbc_grant_value_backlog_relief_candidate_pool"
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
    base.MAX_ANNUAL_FACT_AGE_DAYS = MAX_BACKLOG_FACT_AGE_DAYS
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
    old_thin_delta = payload["delta_metrics"]["by_window"].get("old_thin", {})
    concentration = gate4.get("target_concentration", {})
    interpretation = (
        "The SBC grant-value backlog relief source cleared the numeric "
        "three-window replay screen, but remains only a replay lead because no "
        "shared daily/backtest helper was promoted."
        if gate4["passed"]
        else (
            "The SBC grant-value backlog relief source had positive aggregate "
            "EV/PnL, but did not clear Gate 4 because the effect was narrow and "
            "unstable: old_thin regressed "
            f"{float(old_thin_delta.get('expected_value_score') or 0.0):+.4f} EV "
            f"and ${float(old_thin_delta.get('total_pnl') or 0.0):+,.2f}, while "
            "positive PnL was dominated by too few names "
            f"(max single positive share {float(concentration.get('max_single_positive_pnl_share') or 0.0):.2%}, "
            f"HHI {float(concentration.get('positive_pnl_hhi') or 0.0):.4f}). "
            "It also failed the accepted distribution and accepted SBC "
            "comparators, so the unrecognized backlog decline is more likely "
            "capturing sparse seasonal vesting decay in already-strong growth "
            "names than a robust incremental dilution-quality edge. Do not "
            "promote or tune this fixed grant-value normalization bundle on the "
            "same frozen windows."
        )
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
            "mechanism_family": "production_visible_free_sec_companyfacts_grant_value_dilution_candidate_pool",
            "new_evidence_type": "raw_sec_companyfacts_unrecognized_nonvested_sbc_backlog_pit_field",
            "nearby_prior_experiments": [
                "exp-20260616-015",
                "exp-20260616-017",
                "exp-20260616-013",
                "exp-20260613-026",
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
        "max_backlog_fact_age_days": MAX_BACKLOG_FACT_AGE_DAYS,
        "min_current_revenue": MIN_CURRENT_REVENUE,
        "min_current_gross_profit": MIN_CURRENT_GROSS_PROFIT,
        "min_current_backlog": MIN_CURRENT_BACKLOG,
        "min_gross_margin": MIN_GROSS_MARGIN,
        "max_current_backlog_to_revenue": MAX_CURRENT_BACKLOG_TO_REVENUE,
        "min_backlog_ratio_improvement": MIN_BACKLOG_RATIO_IMPROVEMENT,
        "min_backlog_improvement_pct": MIN_BACKLOG_IMPROVEMENT_PCT,
        "min_backlog_period_gap_days": MIN_BACKLOG_PERIOD_GAP_DAYS,
        "max_backlog_period_gap_days": MAX_BACKLOG_PERIOD_GAP_DAYS,
        "min_revenue_growth": MIN_REVENUE_GROWTH,
        "min_gross_profit_growth": MIN_GROSS_PROFIT_GROWTH,
        "grant_backlog_tags": list(GRANT_BACKLOG_TAGS),
        "revenue_tags": list(REVENUE_TAGS),
        "gross_profit_tags": list(GROSS_PROFIT_TAGS),
        "allowed_backlog_forms": sorted(ALLOWED_BACKLOG_FORMS),
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["execution_model"] = (
        "Instant unrecognized nonvested share-based-compensation award cost "
        "backlog facts are read from raw SEC Companyfacts tags and known only "
        "by filed date (<= signal date). The latest backlog/revenue ratio must "
        "fall versus the prior same-tag backlog point; annual revenue and "
        "gross-profit normalizers use the latest filed annual facts whose "
        "period end is <= the backlog period end. Price confirmation uses only "
        "signal-date OHLCV. Paper entry is the next available open with entry "
        "slippage; exit is the close 10 trading days after the signal with "
        "target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["backtest_protocol"]["companyfacts_source"] = _repo_rel(RAW_COMPANYFACTS_CACHE)
    payload["gate2"]["runtime_fields"] = [
        "raw SEC companyfacts instant unrecognized nonvested SBC award cost backlog facts",
        "raw SEC companyfacts annual revenue facts",
        "raw SEC companyfacts annual gross-profit facts",
        "raw SEC companyfacts filed date and period end",
        "warehouse ticker_universe CIK mapping",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A retry needs materially different PIT grant-value evidence such as "
        "closed forward replacement-value rows, option-exercise/vesting context "
        "joined to the same issuers, or a production-shared daily snapshot of "
        "grant backlog maturation. Do not sweep grant backlog tags, freshness, "
        "ratio thresholds, RS/close/volume guards, top-N, hold, cooldown, or "
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
            "Do not retry by sweeping grant backlog tag lists, backlog/revenue "
            "thresholds, improvement percentage, fact freshness, period gap, "
            "annual revenue/gross-profit floors, RS/close/volume/vol guards, "
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
            f"# {EXPERIMENT_ID} SBC Grant-Value Backlog Relief",
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
            "- Accepted SBC comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                ACCEPTED_SBC_COMPARATOR["aggregate_expected_value_delta"],
                ACCEPTED_SBC_COMPARATOR["aggregate_pnl_delta"],
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
        "accepted_sbc_comparator": ACCEPTED_SBC_COMPARATOR,
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
