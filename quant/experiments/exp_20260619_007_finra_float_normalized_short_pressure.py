"""exp-20260619-007: FINRA short interest normalized by SEC public float.

Replay-only alpha search. The single decision hypothesis is that FINRA reported
short interest is more useful when scaled by issuer-disclosed public float than
when treated as raw days-to-cover. A high short-interest/public-float ratio with
rising short interest and liquid SPY-relative confirmation may identify names
where crowding remains strong but demand is already winning.

This is not a FINRA days-to-cover threshold sweep and not the standalone
public-float scarcity/contraction rule. It combines two free, point-in-time
data surfaces: FINRA publication-date short-interest rows and SEC raw
Companyfacts DEI EntityPublicFloat cover-page facts. No production code, shared
adapter, live/default orders, ranking, sizing, exits, LLM/news path, or
watchlist behavior is changed. A positive result is only a replay lead until a
shared historical/daily helper reproduces it.
No JavaScript is used.
"""

from __future__ import annotations

import bisect
import json
import math
import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import exp_20260614_020_accruals_cash_conversion_quality as base
import exp_20260616_024_finra_borrow_pressure_three_window as finra
import exp_20260617_026_public_float_scarcity_leadership_scout as pf


EXPERIMENT_ID = "exp-20260619-007"
STEM = "finra_float_normalized_short_pressure"
TRIAL_FAMILY = "finra_public_float_normalized_short_pressure_candidate_pool"
TRIAL_VARIANT_ID = "finra_si_float_pct6_rising_liquid_leadership_top1_next_open_10d_v1"
CHANGED_VARIABLE = "finra_public_float_normalized_short_pressure_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260619_007_{STEM}.json"
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

# Annual cover-page public float is normally refreshed once per 10-K cycle.
MAX_PUBLIC_FLOAT_FACT_AGE_DAYS = 430
MAX_SHARES_OUTSTANDING_FACT_AGE_DAYS = 430
MIN_IMPLIED_FLOAT_SHARES = pf.MIN_IMPLIED_FLOAT_SHARES
MIN_SHORT_INTEREST_FLOAT_PCT = 0.06
MAX_SHORT_INTEREST_FLOAT_PCT = 0.75
MIN_FINRA_SHORT_INTEREST_CHANGE_PCT = 0.0
MAX_FINRA_PUBLICATION_AGE_DAYS = finra.MAX_FINRA_PUBLICATION_AGE_DAYS

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.20,
    "expected_pnl_delta": 2500.0,
    "main_failure_modes": [
        "thin_float_coverage",
        "old_window_regression",
        "sector_concentration",
        "accepted_distribution_not_beaten",
    ],
    "confidence_reason": (
        "Prior FINRA borrow-pressure and public-float scarcity tests were not "
        "enough separately, but exp-20260613-029 explicitly named "
        "float-normalized short interest as the missing evidence axis. The "
        "disconfirmer is that annual public-float facts may be too stale and "
        "price-linked to add independent replacement value."
    ),
    "recorded_at": "2026-06-19T08:22:41+00:00",
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
    "uses_free_finra_short_interest": True,
    "uses_free_sec_companyfacts": True,
    "uses_raw_companyfacts_cache": True,
    "uses_free_ohlcv": True,
    "execution_envelope": {
        **base.PRODUCTION_IMPACT["execution_envelope"],
        "failure_handling": (
            "missing FINRA row published on/before signal date, stale FINRA "
            "print, missing raw SEC EntityPublicFloat or shares-outstanding "
            "facts, stale public-float fact, missing public-float-date OHLCV, "
            "non-positive short-interest change, short-interest/public-float "
            "below the fixed 6% gate, missing signal OHLCV, missing next open, "
            "or missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "Replay-only private scout. No shared helper, production watchlist, "
        "live/default order path, ranking, sizing, or exits change. A positive "
        "result would require shared-paper-first historical replay, daily "
        "default-off snapshot, and parity tests before promotion."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: PIT FINRA short_interest divided by SEC "
        "EntityPublicFloat-implied float shares, with positive short-interest "
        "change and liquid SPY-relative price confirmation, may identify "
        "crowded but demand-confirmed equities better than raw days-to-cover."
    ),
    "2_history_check": {
        "exp-20260613-029": (
            "Rejected FINRA covering-relief leadership and explicitly said a "
            "valid retry needs float-normalized short-interest decline or "
            "richer borrow data. This run uses float-normalized short-interest "
            "pressure, not raw days-to-cover."
        ),
        "exp-20260616-024": (
            "Rejected core FINRA borrow-pressure three-window validation; this "
            "run removes the days-to-cover gate and scales reported short "
            "interest by public float."
        ),
        "exp-20260616-026": (
            "Rejected broad FINRA borrow-pressure; this run is a new "
            "cross-source field, not a broad-universe threshold retune."
        ),
        "exp-20260617-026": (
            "Rejected standalone public-float scarcity/contraction. This run "
            "uses public float only as the denominator for FINRA crowding."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL must "
        "be positive, no window EV/PnL regression, at least 20 paper trades "
        "across all 3 windows, survival >=5%, drawdown drift <=0.5pp, "
        "concentration pass, and accepted compression/distribution comparators "
        "must be beaten. Replay-only positives are leads until shared daily/"
        "backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260619_007_finra_float_normalized_short_pressure.py"
    ),
}

_PUBLIC_FLOAT_INDEX_CACHE: tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]] | None = None
_COMBINED_INDEX_CACHE: tuple[dict[str, dict[str, Any]], dict[str, Any]] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return base._round(value, digits)


def _load_public_float_index() -> tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]]:
    global _PUBLIC_FLOAT_INDEX_CACHE
    if _PUBLIC_FLOAT_INDEX_CACHE is not None:
        return _PUBLIC_FLOAT_INDEX_CACHE

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
        path = pf.RAW_COMPANYFACTS_CACHE / f"CIK{cik:010d}.json"
        if not path.exists():
            stats["missing_companyfacts_cache_file"] += 1
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            stats["unreadable_companyfacts_cache_file"] += 1
            continue
        dei = payload.get("facts", {}).get("dei", {})
        public_float = pf._raw_public_float_facts(dei)
        shares_outstanding = pf._raw_shares_outstanding_facts(dei)
        if not public_float:
            stats["tickers_missing_public_float"] += 1
            continue
        if not shares_outstanding:
            stats["tickers_missing_shares_outstanding"] += 1
            continue
        index[ticker] = {
            "public_float": public_float,
            "shares_outstanding": shares_outstanding,
        }
        stats["tickers_with_public_float"] += 1
        stats["public_float_fact_count"] += len(public_float)
        stats["shares_outstanding_fact_count"] += len(shares_outstanding)

    summary = {
        "raw_companyfacts_cache": _repo_rel(pf.RAW_COMPANYFACTS_CACHE),
        "public_float_tag": "dei.EntityPublicFloat",
        "shares_outstanding_tag": "dei.EntityCommonStockSharesOutstanding",
        "warehouse_source": _repo_rel(base.framework.WAREHOUSE),
        "requires_public_float_history": False,
        **dict(stats),
    }
    _PUBLIC_FLOAT_INDEX_CACHE = (index, summary)
    return _PUBLIC_FLOAT_INDEX_CACHE


def _combined_universe() -> set[str]:
    index, _summary = _load_combined_quality_index()
    return set(index)


def _load_window_snapshot(
    *,
    cfg: dict[str, str],
    eligible_tickers: set[str],
) -> dict[str, list[dict[str, Any]]]:
    start = base.framework._parse_date(cfg["start"]) - timedelta(days=650)
    end = base.framework._parse_date(cfg["end"]) + timedelta(days=40)
    tickers = sorted(set(eligible_tickers) | _combined_universe() | {"SPY", "QQQ"})
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


def _load_combined_quality_index() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    global _COMBINED_INDEX_CACHE
    if _COMBINED_INDEX_CACHE is not None:
        return _COMBINED_INDEX_CACHE

    finra_index, finra_summary = finra._load_finra_index()
    float_index, float_summary = _load_public_float_index()
    overlap = sorted(set(finra_index) & set(float_index))
    index = {
        ticker: {
            "finra_rows": finra_index[ticker],
            "float_facts": float_index[ticker],
        }
        for ticker in overlap
    }
    summary = {
        "finra_summary": finra_summary,
        "public_float_summary": float_summary,
        "overlap_tickers": len(overlap),
        "field_source": "finra_short_interest_divided_by_sec_entity_public_float",
        "min_short_interest_float_pct": MIN_SHORT_INTEREST_FLOAT_PCT,
        "max_public_float_fact_age_days": MAX_PUBLIC_FLOAT_FACT_AGE_DAYS,
    }
    _COMBINED_INDEX_CACHE = (index, summary)
    return _COMBINED_INDEX_CACHE


def _build_quality_index(
    companyfacts_rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    index, summary = _load_combined_quality_index()
    return index, {
        **summary,
        "selected_companyfacts_rows_ignored": len(companyfacts_rows),
    }


def _latest_finra_observation(
    ticker: str,
    asof: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    latest: dict[str, Any] | None = None
    for row in rows:
        if row["usable_trade_date"] > asof:
            break
        latest = row
    if latest is None:
        return None
    age = base._days_between(asof, latest["usable_trade_date"])
    if age is None or age > MAX_FINRA_PUBLICATION_AGE_DAYS:
        return None
    short_interest = latest["short_interest"]
    short_change_pct = latest["short_interest_change_pct"]
    if short_interest is None or short_interest <= 0.0 or short_change_pct is None:
        return None
    if short_change_pct <= MIN_FINRA_SHORT_INTEREST_CHANGE_PCT:
        return None
    return {
        "ticker": ticker,
        "publication_date": latest["publication_date"],
        "usable_trade_date": latest["usable_trade_date"],
        "settlement_date": latest["settlement_date"],
        "days_to_cover": _round(latest["days_to_cover"], 4),
        "short_interest": _round(short_interest, 2),
        "short_interest_change_pct": _round(short_change_pct, 4),
        "average_daily_volume": _round(latest["average_daily_volume"], 2),
        "publication_age_days": age,
        "known_at": "finra_publication_date_usable_trade_date_before_next_open_paper_entry",
    }


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
    current = pf._latest_fact_on_or_before(facts["public_float"], asof=asof)
    if current is None:
        return None
    fact_age = base._days_between(asof, current["filed"])
    if fact_age is None or fact_age > MAX_PUBLIC_FLOAT_FACT_AGE_DAYS:
        return None
    shares = pf._latest_fact_on_or_before(facts["shares_outstanding"], asof=asof)
    if shares is None or float(shares["value"]) <= 0.0:
        return None
    shares_age = base._days_between(asof, shares["filed"])
    if shares_age is None or shares_age > MAX_SHARES_OUTSTANDING_FACT_AGE_DAYS:
        return None
    rows = base.framework.shadow._series(snapshot, ticker)
    ticker_indices = indices.get(ticker, {})
    current_price = _price_on_or_before(rows, ticker_indices, current["end"])
    if current_price is None:
        return None
    implied_float_shares = float(current["value"]) / float(current_price["close"])
    if implied_float_shares < MIN_IMPLIED_FLOAT_SHARES:
        return None
    shares_outstanding = float(shares["value"])
    public_float_ratio = implied_float_shares / shares_outstanding
    if public_float_ratio <= 0.0 or public_float_ratio > 1.20:
        return None
    return {
        "ticker": ticker,
        "public_float_end": current["end"],
        "public_float_filed": current["filed"],
        "public_float_value": _round(current["value"], 2),
        "public_float_price_date": current_price["date"],
        "public_float_price": _round(current_price["close"], 4),
        "implied_public_float_shares": _round(implied_float_shares, 2),
        "shares_outstanding": _round(shares_outstanding, 2),
        "shares_outstanding_filed": shares["filed"],
        "public_float_ratio": _round(public_float_ratio, 6),
        "public_float_fact_age_days": fact_age,
        "shares_outstanding_fact_age_days": shares_age,
        "public_float_end_to_filed_days": current["end_to_filed_days"],
        "public_float_form": current["form"],
        "public_float_accn": current["accn"],
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, dict[str, Any]],
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
            finra_obs = _latest_finra_observation(
                ticker,
                signal_date,
                quality_index[ticker]["finra_rows"],
            )
            if finra_obs is None:
                scan["failed_finra_rising_short_interest_gate"] += 1
                continue
            float_obs = _public_float_observation(
                ticker=ticker,
                asof=signal_date,
                facts=quality_index[ticker]["float_facts"],
                snapshot=snapshot,
                indices=indices,
            )
            if float_obs is None:
                scan["failed_public_float_denominator_gate"] += 1
                continue
            short_interest_float_pct = float(finra_obs["short_interest"]) / float(
                float_obs["implied_public_float_shares"]
            )
            if short_interest_float_pct < MIN_SHORT_INTEREST_FLOAT_PCT:
                scan["failed_short_interest_float_pct_gate"] += 1
                continue
            if short_interest_float_pct > MAX_SHORT_INTEREST_FLOAT_PCT:
                scan["failed_short_interest_float_pct_sanity"] += 1
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
            short_change_pct = float(finra_obs["short_interest_change_pct"] or 0.0)
            days_to_cover = float(finra_obs["days_to_cover"] or 0.0)
            score = (
                2.00 * min(short_interest_float_pct, 0.25)
                + 0.012 * min(short_change_pct, 60.0)
                + 0.035 * min(days_to_cover, 15.0)
                + 0.48 * float(confirm["candidate_ret20_excess_spy"])
                + 0.12 * float(confirm["candidate_ret60_excess_spy"])
                + 0.10 * float(confirm["candidate_close_location"])
                + 0.030
                * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
            )
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "FINRA_PUBLIC_FLOAT_NORMALIZED_SHORT_PRESSURE_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": (
                        "finra_publication_and_sec_public_float_filed_before_"
                        "signal_close_next_open_paper_entry"
                    ),
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "short_interest_float_pct": _round(short_interest_float_pct, 6),
                    "uses_free_finra_short_interest": True,
                    "uses_free_sec_companyfacts": True,
                    "uses_raw_sec_companyfacts_cache": True,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    **{f"finra_{key}": value for key, value in finra_obs.items()},
                    **{f"float_{key}": value for key, value in float_obs.items()},
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
            -float(row["short_interest_float_pct"] or 0.0),
            -float(row["finra_short_interest_change_pct"] or 0.0),
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
        "min_short_interest_float_pct": MIN_SHORT_INTEREST_FLOAT_PCT,
        "max_short_interest_float_pct": MAX_SHORT_INTEREST_FLOAT_PCT,
        "min_finra_short_interest_change_pct": MIN_FINRA_SHORT_INTEREST_CHANGE_PCT,
        "max_finra_publication_age_days": MAX_FINRA_PUBLICATION_AGE_DAYS,
        "max_public_float_fact_age_days": MAX_PUBLIC_FLOAT_FACT_AGE_DAYS,
        "max_shares_outstanding_fact_age_days": MAX_SHARES_OUTSTANDING_FACT_AGE_DAYS,
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
        "positive_replay_lead_not_promoted_finra_float_normalized_short_pressure"
        if gate["passed"]
        else "rejected_finra_float_normalized_short_pressure_candidate_pool"
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
            "FINRA short interest normalized by SEC public float cleared the "
            "three-window replay screen, but remains only a replay lead because "
            "no shared daily/backtest helper or parity test was promoted."
        )
    else:
        interpretation = (
            "FINRA short interest normalized by SEC public float did not clear "
            f"Gate 4 (failed: {', '.join(gate4['failed_reasons']) or 'none'}). "
            "The crowding denominator was not enough to create robust "
            "replacement value beyond the accepted compression/distribution "
            "candidate-pool comparators. Do not retry by sweeping the 6% "
            "short-interest/public-float gate, FINRA freshness, public-float "
            "freshness, top-N, hold, cooldown, or notional on these windows."
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
            "mechanism_family": "production_visible_free_finra_sec_float_candidate_pool",
            "new_evidence_type": "free_finra_short_interest_sec_public_float_normalization",
            "nearby_prior_experiments": [
                "exp-20260613-029",
                "exp-20260616-024",
                "exp-20260616-026",
                "exp-20260617-026",
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
        "min_short_interest_float_pct": MIN_SHORT_INTEREST_FLOAT_PCT,
        "max_short_interest_float_pct": MAX_SHORT_INTEREST_FLOAT_PCT,
        "min_finra_short_interest_change_pct": MIN_FINRA_SHORT_INTEREST_CHANGE_PCT,
        "max_finra_publication_age_days": MAX_FINRA_PUBLICATION_AGE_DAYS,
        "max_public_float_fact_age_days": MAX_PUBLIC_FLOAT_FACT_AGE_DAYS,
        "max_shares_outstanding_fact_age_days": MAX_SHARES_OUTSTANDING_FACT_AGE_DAYS,
        "min_implied_float_shares": MIN_IMPLIED_FLOAT_SHARES,
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
        "FINRA biweekly rows are joined PIT by usable publication date "
        "(usable_trade_date <= signal date) and kept only while current within "
        "25 days. Raw SEC Companyfacts EntityPublicFloat is known only by filed "
        "date (<= signal date), converted from USD public-float value into "
        "implied float shares using the ticker close on or before the public "
        "float measurement end date, and used as the denominator for reported "
        "FINRA short_interest. The fixed signal gate requires short_interest/"
        "implied_public_float_shares >= 6% and positive short-interest change. "
        "Price confirmation uses only signal-date OHLCV. Paper entry is the "
        "next available open with existing entry slippage; exit is the close "
        "10 trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    payload["backtest_protocol"]["finra_source"] = _repo_rel(finra.FINRA_ROWS_PATH)
    payload["backtest_protocol"]["companyfacts_source"] = _repo_rel(pf.RAW_COMPANYFACTS_CACHE)
    payload["gate2"]["runtime_fields"] = [
        "FINRA short_interest, short_interest_change_pct, days_to_cover",
        "FINRA settlement_date, publication_date, usable_trade_date (PIT)",
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
        "If positive, build a shared-paper-first FINRA/public-float helper with "
        "historical replay, daily default-off snapshot, parity tests, and "
        "closed forward replacement-value rows before promotion. If negative, "
        "a valid retry needs materially different PIT borrow-cost, loan-"
        "availability, float-change, or forward replacement evidence rather "
        "than threshold retunes."
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
            "Do not retry by sweeping short-interest/public-float threshold, "
            "short-interest-change, FINRA freshness, public-float freshness, "
            "RS/close/volume guards, top-N, hold days, cooldown, or notional on "
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
            f"# {EXPERIMENT_ID} FINRA Float-Normalized Short Pressure",
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
            "- Min short-interest/public-float: `{:.2%}`".format(MIN_SHORT_INTEREST_FLOAT_PCT),
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
                "Replay-only private scout. No shared policy, daily snapshot, "
                "run/backtester adapter, watchlist, order path, ranking, sizing, "
                "or exit behavior changed."
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
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label]["total_pnl"],
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


def main() -> None:
    _configure_base()
    payload = _postprocess_payload(base._build_payload())
    _persist(payload)
    print(json.dumps(base.framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
