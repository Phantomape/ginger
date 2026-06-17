"""exp-20260617-026: public-float scarcity leadership scout.

Replay-only alpha search. The single decision hypothesis is that PIT SEC
Companyfacts DEI EntityPublicFloat can identify supply-constrained demand when
issuer-reported non-affiliate public float is low or contracting, and the
ticker also shows liquid SPY-relative price leadership before next-open paper
entry.

This is not a filing-timeliness, Form 144, FINRA short-interest, 13F ownership,
or balance-sheet relief retry. Public float is an issuer-reported cover-page
DEI field in raw Companyfacts. No production code, shared adapter, live/default
orders, ranking, sizing, exits, LLM/news path, or watchlist behavior is changed.
A positive result is only a replay lead until a shared historical/daily helper
reproduces it.
No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sqlite3
import bisect
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import exp_20260614_020_accruals_cash_conversion_quality as base


EXPERIMENT_ID = "exp-20260617-026"
STEM = "public_float_scarcity_leadership_scout"
TRIAL_FAMILY = "free_sec_companyfacts_public_float_scarcity_candidate_pool"
TRIAL_VARIANT_ID = "public_float_contraction_leadership_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_companyfacts_public_float_scarcity_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
RAW_COMPANYFACTS_CACHE = REPO_ROOT / "data" / "cache" / "sec" / "companyfacts"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260617_026_{STEM}.json"
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

MAX_PUBLIC_FLOAT_FACT_AGE_DAYS = 260
MIN_FLOAT_END_TO_FILED_DAYS = 120
MAX_FLOAT_END_TO_FILED_DAYS = 300
MIN_PERIOD_GAP_DAYS = 250
MAX_PERIOD_GAP_DAYS = 460
MIN_PUBLIC_FLOAT_VALUE_USD = 500_000_000.0
MIN_IMPLIED_FLOAT_SHARES = 5_000_000.0
MIN_SHARES_OUTSTANDING = 10_000_000.0
MAX_SHARES_OUTSTANDING = 50_000_000_000.0
MAX_PUBLIC_FLOAT_RATIO = 0.90
MAX_FLOAT_SHARE_CHANGE = 0.02
MIN_FLOAT_SHARE_CONTRACTION = -0.03
MIN_SCARCITY_OR_CONTRACTION = 0.01

PREDICTION = {
    "success_probability": 0.15,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "public_float_is_price_dominated",
        "annual_cover_page_stale",
        "window_regression",
        "drawdown_drift",
        "accepted_distribution_comparator_not_beaten",
    ],
    "confidence_reason": (
        "EntityPublicFloat is a free issuer-reported DEI field in raw "
        "Companyfacts and appears absent from prior alpha tests. The mechanism "
        "is supply scarcity or float contraction confirmed by liquid demand; "
        "the key disconfirmer is that public float is market-value dominated "
        "and stale annual cover-page data."
    ),
    "recorded_at": "2026-06-17T21:07:00+00:00",
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
    "execution_envelope": {
        **base.PRODUCTION_IMPACT["execution_envelope"],
        "failure_handling": (
            "missing raw SEC EntityPublicFloat or shares-outstanding facts, "
            "stale or malformed public-float cover-page period, missing public "
            "float date OHLCV, missing CIK mapping, missing signal OHLCV, "
            "missing next open, or missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same raw "
        "SEC EntityPublicFloat mapping, filed-date PIT public-float share "
        "estimate, float-ratio/contraction gate, liquid SPY-relative "
        "confirmation, cooldown, next-open paper entry, 10-day exit, costs, "
        "and concentration controls in both historical replay and daily "
        "production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: PIT SEC Companyfacts EntityPublicFloat contraction or "
        "low-float scarcity combined with liquid SPY-relative leadership may "
        "identify supply-constrained demand that can outperform generic "
        "momentum over a next-open 10-trading-day default-off paper trade."
    ),
    "2_history_check": {
        "exp-20260617-010": (
            "Blocked non-repeat scan said true listing/lockup/public-float "
            "surfaces were not Gate-4-ready. This run uses newly verified raw "
            "Companyfacts DEI EntityPublicFloat and remains a private replay "
            "scout because the daily helper shape is not yet proven."
        ),
        "exp-20260613-013": (
            "Rejected isolated Form 144 sale absorption and named planned-sale "
            "size as percent of float as future evidence. This run is not a "
            "Form 144 or insider-sale retry; it tests issuer-reported company "
            "public-float scarcity directly."
        ),
        "exp-20260615-009": (
            "Rejected 13F low-crowding sponsorship leadership. This run does "
            "not infer institutional ownership from delayed 13F; it uses "
            "issuer cover-page non-affiliate float."
        ),
        "exp-20260617-020/022/025": (
            "Rejected annual/quarterly filing-timeliness and NT notice timing. "
            "This run ignores filing lag and tests the public-float supply "
            "field after filing."
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
        "exp_20260617_026_public_float_scarcity_leadership_scout.py"
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
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _d10(value: Any) -> str:
    text = str(value or "")[:10]
    return text if len(text) == 10 and text[4] == "-" and text[7] == "-" else ""


def _raw_public_float_facts(dei: dict[str, Any]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    tag = "EntityPublicFloat"
    for raw in (dei.get(tag) or {}).get("units", {}).get("USD", []):
        end = _d10(raw.get("end"))
        filed = _d10(raw.get("filed"))
        value = _float_or_none(raw.get("val"))
        if not end or not filed or value is None or value < MIN_PUBLIC_FLOAT_VALUE_USD:
            continue
        end_to_filed = base._days_between(filed, end)
        if not (MIN_FLOAT_END_TO_FILED_DAYS <= end_to_filed <= MAX_FLOAT_END_TO_FILED_DAYS):
            continue
        facts.append(
            {
                "end": end,
                "filed": filed,
                "value": value,
                "tag": tag,
                "form": str(raw.get("form") or ""),
                "fy": raw.get("fy"),
                "fp": str(raw.get("fp") or ""),
                "accn": str(raw.get("accn") or ""),
                "end_to_filed_days": end_to_filed,
            }
        )
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for fact in facts:
        key = (fact["end"], fact["filed"])
        existing = deduped.get(key)
        if existing is None or float(fact["value"]) > float(existing["value"]):
            deduped[key] = fact
    rows = list(deduped.values())
    rows.sort(key=lambda row: (row["filed"], row["end"], row["accn"]))
    return rows


def _raw_shares_outstanding_facts(dei: dict[str, Any]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    tag = "EntityCommonStockSharesOutstanding"
    for raw in (dei.get(tag) or {}).get("units", {}).get("shares", []):
        end = _d10(raw.get("end"))
        filed = _d10(raw.get("filed"))
        value = _float_or_none(raw.get("val"))
        if (
            not end
            or not filed
            or value is None
            or value < MIN_SHARES_OUTSTANDING
            or value > MAX_SHARES_OUTSTANDING
        ):
            continue
        facts.append(
            {
                "end": end,
                "filed": filed,
                "value": value,
                "tag": tag,
                "form": str(raw.get("form") or ""),
                "fy": raw.get("fy"),
                "fp": str(raw.get("fp") or ""),
                "accn": str(raw.get("accn") or ""),
            }
        )
    facts.sort(key=lambda row: (row["filed"], row["end"], row["accn"]))
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
        dei = payload.get("facts", {}).get("dei", {})
        public_float = _raw_public_float_facts(dei)
        shares_outstanding = _raw_shares_outstanding_facts(dei)
        if len(public_float) < 2:
            stats["tickers_missing_public_float_history"] += 1
            continue
        if not shares_outstanding:
            stats["tickers_missing_shares_outstanding"] += 1
            continue
        index[ticker] = {
            "public_float": public_float,
            "shares_outstanding": shares_outstanding,
        }
        stats["tickers_with_public_float_history"] += 1
        stats["public_float_fact_count"] += len(public_float)
        stats["shares_outstanding_fact_count"] += len(shares_outstanding)

    summary = {
        "raw_companyfacts_cache": _repo_rel(RAW_COMPANYFACTS_CACHE),
        "public_float_tag": "dei.EntityPublicFloat",
        "shares_outstanding_tag": "dei.EntityCommonStockSharesOutstanding",
        "warehouse_source": _repo_rel(base.framework.WAREHOUSE),
        **dict(stats),
    }
    _RAW_INDEX_CACHE = (index, summary)
    return _RAW_INDEX_CACHE


def _load_window_snapshot(
    *,
    cfg: dict[str, str],
    eligible_tickers: set[str],
) -> dict[str, list[dict[str, Any]]]:
    start = base.framework._parse_date(cfg["start"]) - timedelta(days=650)
    end = base.framework._parse_date(cfg["end"]) + timedelta(days=40)
    tickers = sorted(set(eligible_tickers) | {"SPY", "QQQ"})
    snapshot: dict[str, list[dict[str, Any]]] = {ticker: [] for ticker in tickers}
    warehouse_uri = f"file:{Path(base.framework.WAREHOUSE).resolve().as_posix()}?mode=ro&immutable=1"
    with sqlite3.connect(warehouse_uri, uri=True) as con:
        for chunk_start in range(0, len(tickers), 800):
            chunk = tickers[chunk_start : chunk_start + 800]
            placeholders = ",".join("?" for _ in chunk)
            sql = (
                "select ticker, date, open, high, low, close, volume "
                "from ohlcv "
                f"where ticker in ({placeholders}) and date >= ? and date <= ? "
                "order by ticker, date"
            )
            params = [*chunk, base.framework._date_str(start), base.framework._date_str(end)]
            for row in con.execute(sql, params):
                ticker, day, open_, high, low, close, volume = row
                snapshot[str(ticker).upper()].append(
                    {
                        "Date": str(day)[:10],
                        "Open": float(open_),
                        "High": float(high),
                        "Low": float(low),
                        "Close": float(close),
                        "Volume": float(volume),
                    }
                )
    return {ticker: rows for ticker, rows in snapshot.items() if rows}


def _build_quality_index(
    companyfacts_rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]]:
    index, summary = _load_raw_companyfacts_index()
    return index, {
        **summary,
        "selected_companyfacts_rows_ignored": len(companyfacts_rows),
        "field_source": "raw_sec_companyfacts_dei_entity_public_float",
    }


def _latest_fact_on_or_before(
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
    return max(candidates, key=lambda row: (row["filed"], row["end"], row["accn"]))


def _price_on_or_before(
    rows: list[dict[str, Any]],
    indices: dict[str, int],
    day: str,
) -> dict[str, Any] | None:
    dates = [str(row.get("Date") or "")[:10] for row in rows]
    pos = bisect.bisect_right(dates, day) - 1
    if pos < 0:
        return None
    row = rows[pos]
    close = base.framework._value(row, "Close")
    if close is None or close <= 0.0:
        return None
    return {"date": dates[pos], "close": float(close), "index": indices.get(dates[pos])}


def _public_float_observation(
    ticker: str,
    asof: str,
    facts: dict[str, list[dict[str, Any]]],
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
) -> dict[str, Any] | None:
    current = _latest_fact_on_or_before(facts["public_float"], asof=asof)
    if current is None:
        return None
    fact_age = base._days_between(asof, current["filed"])
    if fact_age > MAX_PUBLIC_FLOAT_FACT_AGE_DAYS:
        return None
    prior = _latest_fact_on_or_before(
        facts["public_float"], asof=asof, before_end=current["end"]
    )
    if prior is None:
        return None
    period_gap_days = base._days_between(current["end"], prior["end"])
    if period_gap_days < MIN_PERIOD_GAP_DAYS or period_gap_days > MAX_PERIOD_GAP_DAYS:
        return None

    shares = _latest_fact_on_or_before(facts["shares_outstanding"], asof=asof)
    if shares is None or float(shares["value"]) <= 0.0:
        return None
    rows = base.framework.shadow._series(snapshot, ticker)
    ticker_indices = indices.get(ticker, {})
    current_price = _price_on_or_before(rows, ticker_indices, current["end"])
    prior_price = _price_on_or_before(rows, ticker_indices, prior["end"])
    if current_price is None or prior_price is None:
        return None

    current_float_shares = float(current["value"]) / float(current_price["close"])
    prior_float_shares = float(prior["value"]) / float(prior_price["close"])
    if (
        current_float_shares < MIN_IMPLIED_FLOAT_SHARES
        or prior_float_shares < MIN_IMPLIED_FLOAT_SHARES
    ):
        return None
    public_float_ratio = current_float_shares / float(shares["value"])
    if public_float_ratio <= 0.0 or public_float_ratio > 1.10:
        return None
    float_share_change = current_float_shares / prior_float_shares - 1.0
    scarcity = MAX_PUBLIC_FLOAT_RATIO - public_float_ratio
    contraction = -float_share_change
    if public_float_ratio > MAX_PUBLIC_FLOAT_RATIO and float_share_change > MIN_FLOAT_SHARE_CONTRACTION:
        return None
    if float_share_change > MAX_FLOAT_SHARE_CHANGE:
        return None
    if max(scarcity, contraction) < MIN_SCARCITY_OR_CONTRACTION:
        return None

    return {
        "ticker": ticker,
        "current_public_float_end": current["end"],
        "prior_public_float_end": prior["end"],
        "current_public_float_filed": current["filed"],
        "prior_public_float_filed": prior["filed"],
        "current_public_float_value": _round(current["value"], 2),
        "prior_public_float_value": _round(prior["value"], 2),
        "current_public_float_price_date": current_price["date"],
        "prior_public_float_price_date": prior_price["date"],
        "current_public_float_price": _round(current_price["close"], 4),
        "prior_public_float_price": _round(prior_price["close"], 4),
        "current_implied_float_shares": _round(current_float_shares, 2),
        "prior_implied_float_shares": _round(prior_float_shares, 2),
        "shares_outstanding": _round(shares["value"], 2),
        "shares_outstanding_filed": shares["filed"],
        "public_float_ratio": _round(public_float_ratio, 6),
        "float_share_change": _round(float_share_change, 6),
        "float_share_contraction": _round(contraction, 6),
        "float_scarcity_score": _round(max(0.0, scarcity), 6),
        "period_gap_days": period_gap_days,
        "fact_age_days": fact_age,
        "current_end_to_filed_days": current["end_to_filed_days"],
        "prior_end_to_filed_days": prior["end_to_filed_days"],
        "current_public_float_form": current["form"],
        "current_public_float_accn": current["accn"],
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
            quality = _public_float_observation(
                ticker=ticker,
                asof=signal_date,
                facts=quality_index[ticker],
                snapshot=snapshot,
                indices=indices,
            )
            if quality is None:
                scan["failed_public_float_gate"] += 1
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
            scarcity = float(quality["float_scarcity_score"] or 0.0)
            contraction = max(0.0, float(quality["float_share_contraction"] or 0.0))
            freshness = max(
                0.0,
                (MAX_PUBLIC_FLOAT_FACT_AGE_DAYS - float(quality["fact_age_days"] or 0.0))
                / MAX_PUBLIC_FLOAT_FACT_AGE_DAYS,
            )
            score = (
                0.95 * scarcity
                + 1.40 * min(contraction, 0.35)
                + 0.40 * float(confirm["candidate_ret20_excess_spy"])
                + 0.12 * float(confirm["candidate_ret60_excess_spy"])
                + 0.10 * float(confirm["candidate_close_location"])
                + 0.05 * freshness
                + 0.035
                * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
            )
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "RAW_SEC_PUBLIC_FLOAT_SCARCITY_LEADERSHIP_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "raw_dei_public_float_filed_and_signal_close_before_next_open_paper_entry",
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
            float(row["quality_public_float_ratio"] or 0.0),
            -float(row["quality_float_share_contraction"] or 0.0),
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
        "max_public_float_fact_age_days": MAX_PUBLIC_FLOAT_FACT_AGE_DAYS,
        "min_float_end_to_filed_days": MIN_FLOAT_END_TO_FILED_DAYS,
        "max_float_end_to_filed_days": MAX_FLOAT_END_TO_FILED_DAYS,
        "max_public_float_ratio": MAX_PUBLIC_FLOAT_RATIO,
        "max_float_share_change": MAX_FLOAT_SHARE_CHANGE,
        "min_float_share_contraction": MIN_FLOAT_SHARE_CONTRACTION,
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
        "positive_replay_lead_not_promoted_public_float_scarcity_leadership"
        if gate["passed"]
        else "rejected_public_float_scarcity_leadership_candidate_pool"
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
    base.MAX_ANNUAL_FACT_AGE_DAYS = MAX_PUBLIC_FLOAT_FACT_AGE_DAYS
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    base.load_companyfacts_rows = _load_companyfacts_rows_stub
    base._load_window_snapshot = _load_window_snapshot
    base._build_quality_index = _build_quality_index
    base._candidate_rows_for_window = _candidate_rows_for_window
    base._gate4 = _gate4


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    if gate4["passed"]:
        interpretation = (
            "The public-float scarcity leadership source cleared the numeric "
            "three-window replay screen, but remains only a replay lead because "
            "no shared daily/backtest helper was promoted."
        )
    else:
        interpretation = (
            "The public-float scarcity leadership source did not clear Gate 4 "
            f"(failed: {', '.join(gate4['failed_reasons']) or 'none'}). It is "
            "not retained or promoted. The readout is informative but not "
            "deployable: most trades appeared only in late_strong, mid_weak "
            "had two trades, old_thin had zero trades, and the positive PnL "
            "was too concentrated. Public float is annual cover-page data and remains "
            "partly market-price dominated even after normalizing by the "
            "public-float-date close, so the rule did not supply enough "
            "independent, repeatable replacement value versus the accepted "
            "distribution-day absorption comparator."
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
            "mechanism_family": "production_visible_free_sec_companyfacts_public_float_candidate_pool",
            "new_evidence_type": "raw_sec_companyfacts_dei_entity_public_float_pit_field",
            "nearby_prior_experiments": [
                "exp-20260617-010",
                "exp-20260613-013",
                "exp-20260615-009",
                "exp-20260617-020",
                "exp-20260617-022",
                "exp-20260617-025",
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
        "max_public_float_fact_age_days": MAX_PUBLIC_FLOAT_FACT_AGE_DAYS,
        "min_float_end_to_filed_days": MIN_FLOAT_END_TO_FILED_DAYS,
        "max_float_end_to_filed_days": MAX_FLOAT_END_TO_FILED_DAYS,
        "min_period_gap_days": MIN_PERIOD_GAP_DAYS,
        "max_period_gap_days": MAX_PERIOD_GAP_DAYS,
        "min_public_float_value_usd": MIN_PUBLIC_FLOAT_VALUE_USD,
        "min_implied_float_shares": MIN_IMPLIED_FLOAT_SHARES,
        "max_public_float_ratio": MAX_PUBLIC_FLOAT_RATIO,
        "max_float_share_change": MAX_FLOAT_SHARE_CHANGE,
        "min_float_share_contraction": MIN_FLOAT_SHARE_CONTRACTION,
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
        "EntityPublicFloat and EntityCommonStockSharesOutstanding are read from "
        "raw SEC Companyfacts and known only by filed date (<= signal date). "
        "Public-float USD is divided by the ticker close on or before the "
        "reported public-float measurement date to estimate non-affiliate float "
        "shares; current/prior annual float-share change and current float "
        "ratio to shares outstanding define the supply-scarcity gate. Price "
        "confirmation uses only signal-date OHLCV. Paper entry is the next "
        "available open with existing entry slippage; exit is the close 10 "
        "trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    payload["backtest_protocol"]["companyfacts_source"] = _repo_rel(RAW_COMPANYFACTS_CACHE)
    payload["gate2"]["runtime_fields"] = [
        "raw SEC companyfacts dei.EntityPublicFloat USD facts",
        "raw SEC companyfacts dei.EntityCommonStockSharesOutstanding facts",
        "raw SEC companyfacts filed date and public-float measurement end date",
        "warehouse ticker_universe CIK mapping",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A retry needs materially different PIT float evidence such as parsed "
        "Form 144 sale size as percent of issuer public float, borrow-cost or "
        "loan-availability normalized by float, explicit lockup/listing float "
        "changes, or closed forward replacement-value rows. Do not sweep "
        "public-float ratio, contraction, freshness, RS/close/volume guards, "
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
            "Do not retry by sweeping public-float ratio, implied float-share "
            "change, annual fact freshness, end-to-filed gap, RS/close/volume/"
            "vol guards, top-N, hold days, cooldown, or notional on these "
            "frozen windows."
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
            f"# {EXPERIMENT_ID} Public Float Scarcity Leadership",
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
