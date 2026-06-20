"""exp-20260620-024: SEC proxy pay-vs-performance alignment scout.

Replay-only alpha search. The single decision hypothesis is a PIT free SEC
proxy/ECD candidate source: production-universe names whose latest filed
pay-vs-performance facts show issuer TSR at or above peer TSR while CEO
actually-paid compensation is falling or controlled may indicate governance and
incentive alignment. With liquid SPY-relative leadership, those names may
produce 10-day continuation distinct from Form 4 transaction plumbing and
ordinary Companyfacts financial-statement ratios.

This intentionally reads the raw SEC Companyfacts cache because the proxy ECD
taxonomy fields are not loaded by the selected Companyfacts sidecar or the
accepted fundamental helpers. No production code, shared adapter, live/default
orders, ranking, sizing, exits, LLM/news path, or watchlist behavior is changed.
A positive replay is only a lead until a shared historical/daily helper
reproduces the exact PIT field mapping. No JavaScript is used.
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


EXPERIMENT_ID = "exp-20260620-024"
STEM = "sec_proxy_pay_performance_alignment"
TRIAL_FAMILY = "sec_proxy_pay_vs_performance_alignment_candidate_pool"
TRIAL_VARIANT_ID = "sec_proxy_pay_vs_performance_alignment_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_proxy_pay_vs_performance_alignment_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "codex-alpha-search"

REPO_ROOT = base.REPO_ROOT
RAW_COMPANYFACTS_CACHE = REPO_ROOT / "data" / "cache" / "sec" / "companyfacts"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260620_024_{STEM}.json"
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

ANNUAL_DURATION_MIN = 330
ANNUAL_DURATION_MAX = 400
MAX_ANNUAL_FACT_AGE_DAYS = 430
MAX_PEER_TSR_DISCOUNT = 0.00
MAX_PEO_PAY_GROWTH = 0.25
MAX_NEO_PAY_GROWTH = 0.35
MIN_PEO_PAY_DECLINE_FOR_WEAK_PEER = -0.05
MAX_ACTUAL_TO_SUMMARY_PAY = 1.75

PEO_ACTUAL_PAY_TAGS = ("PeoActuallyPaidCompAmt",)
PEO_TOTAL_PAY_TAGS = ("PeoTotalCompAmt",)
NEO_ACTUAL_PAY_TAGS = ("NonPeoNeoAvgCompActuallyPaidAmt",)
NEO_TOTAL_PAY_TAGS = ("NonPeoNeoAvgTotalCompAmt",)
ISSUER_TSR_TAGS = ("TotalShareholderRtnAmt",)
PEER_TSR_TAGS = ("PeerGroupTotalShareholderRtnAmt",)

PREDICTION = {
    "success_probability": 0.14,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "thin_sample",
        "old_thin_coverage_gap",
        "proxy_lag_not_incremental",
        "accepted_comparator_not_beaten",
        "target_concentration_failed",
    ],
    "confidence_reason": (
        "This uses a materially new free SEC proxy/ECD data surface named by "
        "prior Form 4 failures as needed executive-compensation context, not "
        "another Form 4 code list or Companyfacts financial-ratio threshold. "
        "The main risk is that proxy data lags too much, coverage is thin before "
        "2025, or governance context is not incremental to price leadership."
    ),
    "recorded_at": "2026-06-20T18:05:20+00:00",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "execution_envelope": {
        **base.PRODUCTION_IMPACT["execution_envelope"],
        "failure_handling": (
            "missing raw SEC proxy ECD pay-vs-performance facts, missing prior "
            "PEO actually-paid compensation, missing issuer/peer TSR facts, "
            "stale facts, missing CIK mapping, missing OHLCV, missing next open, "
            "or missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same raw "
        "SEC ECD tag mapping, filed-date PIT pay-vs-performance alignment gate, "
        "liquid SPY-relative confirmation, cooldown, next-open paper entry, "
        "10-day exit, costs, and concentration controls in both historical "
        "replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: PIT SEC proxy pay-vs-performance facts where CEO/NEO "
        "actually-paid compensation is falling or controlled while issuer TSR "
        "stays above peer TSR may identify governance-aligned leadership names; "
        "with liquid SPY-relative price confirmation, these candidates may "
        "produce next-open 10-day continuation distinct from Form 4 transaction "
        "plumbing and ordinary Companyfacts financial ratios."
    ),
    "2_history_check": {
        "exp-20260620-004": (
            "SBC + Form 4 equity-comp context was rejected and explicitly "
            "required parsed executive compensation or grant-value context for "
            "a valid retry. This run uses filed proxy pay-vs-performance facts, "
            "not Form 4 transaction codes or a lookback/scalar sweep."
        ),
        "exp-20260620-016": (
            "Form 4 multi-year equity-retention footnotes were rejected. This "
            "run uses issuer-level proxy compensation/TSR alignment, not "
            "insider footnote parsing."
        ),
        "exp-20260615-024": (
            "CEO/CFO open-market purchase context was rejected and named "
            "executive-compensation/holdings context as new evidence. This run "
            "uses proxy ECD facts instead of buy-size thresholds."
        ),
        "exp-20260616-013": (
            "Form 4 option-exercise retention had zero target trades. This run "
            "does not retry option-exercise filters; it tests issuer-level "
            "pay-vs-performance alignment."
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
        "exp_20260620_024_sec_proxy_pay_performance_alignment.py"
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


def _raw_annual_facts(
    usgaap: dict[str, Any], tags: tuple[str, ...], *, unit: str
) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for tag in tags:
        tag_payload = usgaap.get(tag) or {}
        for raw in tag_payload.get("units", {}).get(unit, []):
            duration = _duration_days(raw)
            fp = str(raw.get("fp") or "")
            if duration is None or not (ANNUAL_DURATION_MIN <= duration <= ANNUAL_DURATION_MAX):
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
        ecd = payload.get("facts", {}).get("ecd", {})
        peo_actual = _raw_annual_facts(ecd, PEO_ACTUAL_PAY_TAGS, unit="USD")
        peo_total = _raw_annual_facts(ecd, PEO_TOTAL_PAY_TAGS, unit="USD")
        neo_actual = _raw_annual_facts(ecd, NEO_ACTUAL_PAY_TAGS, unit="USD")
        neo_total = _raw_annual_facts(ecd, NEO_TOTAL_PAY_TAGS, unit="USD")
        issuer_tsr = _raw_annual_facts(ecd, ISSUER_TSR_TAGS, unit="USD")
        peer_tsr = _raw_annual_facts(ecd, PEER_TSR_TAGS, unit="USD")
        if not peo_actual:
            stats["tickers_missing_peo_actual_pay"] += 1
            continue
        if not issuer_tsr or not peer_tsr:
            stats["tickers_missing_tsr_facts"] += 1
            continue
        index[ticker] = {
            "peo_actual": peo_actual,
            "peo_total": peo_total,
            "neo_actual": neo_actual,
            "neo_total": neo_total,
            "issuer_tsr": issuer_tsr,
            "peer_tsr": peer_tsr,
        }
        stats["tickers_with_proxy_pay_performance_facts"] += 1
        stats["peo_actual_fact_count"] += len(peo_actual)
        stats["issuer_tsr_fact_count"] += len(issuer_tsr)
        stats["peer_tsr_fact_count"] += len(peer_tsr)

    summary = {
        "raw_companyfacts_cache": _repo_rel(RAW_COMPANYFACTS_CACHE),
        "ecd_namespace": "facts.ecd",
        "peo_actual_pay_tags": list(PEO_ACTUAL_PAY_TAGS),
        "peo_total_pay_tags": list(PEO_TOTAL_PAY_TAGS),
        "neo_actual_pay_tags": list(NEO_ACTUAL_PAY_TAGS),
        "issuer_tsr_tags": list(ISSUER_TSR_TAGS),
        "peer_tsr_tags": list(PEER_TSR_TAGS),
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
        "field_source": "raw_sec_proxy_ecd_companyfacts_cache_not_selected_sidecar",
    }


def _pay_alignment_observation(
    ticker: str,
    asof: str,
    facts: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    current_peo = _latest_period_fact(facts["peo_actual"], asof=asof)
    if current_peo is None:
        return None
    if base._days_between(asof, current_peo["filed"]) > MAX_ANNUAL_FACT_AGE_DAYS:
        return None

    prior_peo = _latest_period_fact(
        facts["peo_actual"], asof=asof, before_end=current_peo["end"]
    )
    if prior_peo is None:
        return None

    current_peo_value = float(current_peo["value"])
    prior_peo_value = float(prior_peo["value"])
    if current_peo_value <= 0.0 or prior_peo_value <= 0.0:
        return None

    peo_pay_growth = current_peo_value / prior_peo_value - 1.0
    if peo_pay_growth > MAX_PEO_PAY_GROWTH:
        return None

    current_issuer_tsr = _latest_period_fact(
        facts["issuer_tsr"], asof=asof, end=current_peo["end"]
    )
    current_peer_tsr = _latest_period_fact(
        facts["peer_tsr"], asof=asof, end=current_peo["end"]
    )
    if current_issuer_tsr is None or current_peer_tsr is None:
        return None
    issuer_tsr_value = float(current_issuer_tsr["value"])
    peer_tsr_value = float(current_peer_tsr["value"])
    if issuer_tsr_value <= 0.0 or peer_tsr_value <= 0.0:
        return None

    tsr_excess_peer = issuer_tsr_value / peer_tsr_value - 1.0
    if tsr_excess_peer < MAX_PEER_TSR_DISCOUNT and peo_pay_growth > MIN_PEO_PAY_DECLINE_FOR_WEAK_PEER:
        return None

    current_peo_total = _latest_period_fact(
        facts["peo_total"], asof=asof, end=current_peo["end"]
    )
    actual_to_summary = None
    if current_peo_total is not None and float(current_peo_total["value"]) > 0.0:
        actual_to_summary = current_peo_value / float(current_peo_total["value"])
        if actual_to_summary > MAX_ACTUAL_TO_SUMMARY_PAY:
            return None

    neo_pay_growth = None
    current_neo = _latest_period_fact(facts["neo_actual"], asof=asof, end=current_peo["end"])
    prior_neo = _latest_period_fact(facts["neo_actual"], asof=asof, before_end=current_peo["end"])
    if current_neo is not None and prior_neo is not None and float(prior_neo["value"]) > 0.0:
        neo_pay_growth = float(current_neo["value"]) / float(prior_neo["value"]) - 1.0
        if neo_pay_growth > MAX_NEO_PAY_GROWTH:
            return None

    alignment_score = tsr_excess_peer - max(peo_pay_growth, 0.0)
    if alignment_score < -0.20:
        return None

    return {
        "current_fiscal_year_end": current_peo["end"],
        "prior_fiscal_year_end": prior_peo["end"],
        "current_proxy_filed": current_peo["filed"],
        "prior_proxy_filed": prior_peo["filed"],
        "current_peo_actual_pay_tag": current_peo["tag"],
        "current_peo_actual_pay": _round(current_peo_value, 2),
        "prior_peo_actual_pay": _round(prior_peo_value, 2),
        "peo_actual_pay_growth": _round(peo_pay_growth, 6),
        "issuer_tsr": _round(issuer_tsr_value, 6),
        "peer_tsr": _round(peer_tsr_value, 6),
        "tsr_excess_peer": _round(tsr_excess_peer, 6),
        "peo_actual_to_summary_pay": _round(actual_to_summary, 6),
        "neo_actual_pay_growth": _round(neo_pay_growth, 6),
        "alignment_score": _round(alignment_score, 6),
        "fact_age_days": base._days_between(asof, current_peo["filed"]),
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
            quality = _pay_alignment_observation(ticker, signal_date, quality_index[ticker])
            if quality is None:
                scan["failed_pay_alignment_gate"] += 1
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
                0.95 * float(quality["alignment_score"] or 0.0)
                + 0.45 * max(-float(quality["peo_actual_pay_growth"] or 0.0), -0.25)
                + 0.40 * float(quality["tsr_excess_peer"] or 0.0)
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
                    "source": "RAW_SEC_PROXY_PAY_PERFORMANCE_ALIGNMENT_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "raw_sec_proxy_ecd_filed_and_signal_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_companyfacts": True,
                    "uses_raw_sec_companyfacts_cache": True,
                    "uses_raw_sec_proxy_ecd": True,
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
            -float(row["quality_alignment_score"] or 0.0),
            float(row["quality_peo_actual_pay_growth"] or 0.0),
            -float(row["quality_tsr_excess_peer"] or 0.0),
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
        "max_peer_tsr_discount": MAX_PEER_TSR_DISCOUNT,
        "max_peo_pay_growth": MAX_PEO_PAY_GROWTH,
        "max_neo_pay_growth": MAX_NEO_PAY_GROWTH,
        "min_peo_pay_decline_for_weak_peer": MIN_PEO_PAY_DECLINE_FOR_WEAK_PEER,
        "max_actual_to_summary_pay": MAX_ACTUAL_TO_SUMMARY_PAY,
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
        "positive_replay_lead_not_promoted_sec_proxy_pay_performance_alignment"
        if gate["passed"]
        else "rejected_sec_proxy_pay_performance_alignment_candidate_pool"
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
    base.FY_DURATION_MIN = ANNUAL_DURATION_MIN
    base.FY_DURATION_MAX = ANNUAL_DURATION_MAX
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
            "The raw SEC proxy pay-vs-performance alignment source cleared the numeric "
            "three-window replay screen, but remains only a replay lead because "
            "no shared daily/backtest helper was promoted."
        )
    else:
        interpretation = (
            "The raw SEC proxy pay-vs-performance alignment source did not clear Gate 4 "
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
                "production_visible_free_sec_proxy_compensation_candidate_pool"
            ),
            "new_evidence_type": "raw_sec_ecd_pay_vs_performance_proxy_context",
            "nearby_prior_experiments": [
                "exp-20260620-004",
                "exp-20260620-016",
                "exp-20260615-024",
                "exp-20260616-013",
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
            "max_annual_fact_age_days": MAX_ANNUAL_FACT_AGE_DAYS,
            "annual_duration_min": ANNUAL_DURATION_MIN,
            "annual_duration_max": ANNUAL_DURATION_MAX,
            "max_peer_tsr_discount": MAX_PEER_TSR_DISCOUNT,
            "max_peo_pay_growth": MAX_PEO_PAY_GROWTH,
            "max_neo_pay_growth": MAX_NEO_PAY_GROWTH,
            "min_peo_pay_decline_for_weak_peer": MIN_PEO_PAY_DECLINE_FOR_WEAK_PEER,
            "max_actual_to_summary_pay": MAX_ACTUAL_TO_SUMMARY_PAY,
            "peo_actual_pay_tags": list(PEO_ACTUAL_PAY_TAGS),
            "peo_total_pay_tags": list(PEO_TOTAL_PAY_TAGS),
            "neo_actual_pay_tags": list(NEO_ACTUAL_PAY_TAGS),
            "issuer_tsr_tags": list(ISSUER_TSR_TAGS),
            "peer_tsr_tags": list(PEER_TSR_TAGS),
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Annual proxy ECD pay-vs-performance facts are read from raw SEC "
        "Companyfacts and are known only by their filed date (<= signal date). "
        "The issuer must show current TSR not below peer TSR unless CEO "
        "actually-paid compensation is falling, and CEO/NEO actually-paid "
        "compensation growth must stay within the fixed controlled-pay envelope. "
        "Price confirmation uses only signal-date OHLCV. Paper entry is the next "
        "available open with existing entry slippage; exit is the close 10 "
        "trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    payload["backtest_protocol"]["companyfacts_source"] = _repo_rel(RAW_COMPANYFACTS_CACHE)
    payload["gate2"]["runtime_fields"] = [
        "raw SEC proxy ECD PeoActuallyPaidCompAmt annual facts",
        "raw SEC proxy ECD PeoTotalCompAmt annual facts",
        "raw SEC proxy ECD NonPeoNeoAvgCompActuallyPaidAmt annual facts",
        "raw SEC proxy ECD TotalShareholderRtnAmt annual facts",
        "raw SEC proxy ECD PeerGroupTotalShareholderRtnAmt annual facts",
        "raw SEC companyfacts filed date and period end",
        "warehouse ticker_universe CIK mapping",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A retry needs materially richer PIT executive-compensation evidence, "
        "such as grant-value normalization, ownership-retention context joined "
        "to the proxy, board/compensation committee change provenance, or closed "
        "forward replacement-value rows. Do not sweep pay-growth, TSR-relative, "
        "fact-age, RS/close/volume/vol, top-N, hold, cooldown, or notional "
        "thresholds on these frozen windows."
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
            "Do not retry by sweeping pay-growth, TSR-relative, actual-to-summary "
            "pay, fact-age, RS/close/volume/vol guards, top-N, hold days, "
            "cooldown, or notional on these frozen windows."
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
            f"# {EXPERIMENT_ID} SEC Proxy Pay-Vs-Performance Alignment",
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
    card = _build_card(payload)
    base.framework._write_text(CARD_MD, card)
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
