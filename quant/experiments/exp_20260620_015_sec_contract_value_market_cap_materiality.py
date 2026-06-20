"""exp-20260620-015: SEC contract-value market-cap materiality scout.

Replay-only alpha search. The single decision hypothesis is a PIT public SEC
filing text candidate source: 8-K filings with explicit local contract
economics should be tradable only when the extracted contract value is material
versus the issuer's PIT market cap. The new evidence axis versus the rejected
SEC contract-text scout is a filed-date shares-outstanding join, not a regex
phrase or raw dollar-value sweep. Candidates must also show same-day liquid
SPY-relative leadership and enter default-off paper at the next open with a
fixed 10-trading-day hold.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive replay is
only a lead until a shared historical/daily parser reproduces the same PIT text
semantics. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260614_020_accruals_cash_conversion_quality as base


EXPERIMENT_ID = "exp-20260620-015"
STEM = "sec_contract_value_market_cap_materiality"
TRIAL_FAMILY = "sec_text_contract_value_market_cap_materiality_candidate_pool"
TRIAL_VARIANT_ID = "sec_contract_value_to_market_cap_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_text_contract_value_to_market_cap_materiality_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
TEXT_DIR = REPO_ROOT / "data" / "non_ohlcv"
RAW_COMPANYFACTS_CACHE = REPO_ROOT / "data" / "cache" / "sec" / "companyfacts"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260620_015_{STEM}.json"
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

MIN_CONTRACT_VALUE_USD = 10_000_000.0
MAX_CONTRACT_VALUE_USD = 50_000_000_000.0
MIN_CONTRACT_VALUE_TO_MARKET_CAP = 0.04
MAX_CONTRACT_VALUE_TO_MARKET_CAP = 1.00
MAX_SHARES_OUTSTANDING_FACT_AGE_DAYS = 550
MIN_SHARES_OUTSTANDING = 10_000_000.0
MAX_SHARES_OUTSTANDING = 50_000_000_000.0
MIN_TEXT_WORDS = 250
MAX_TEXT_CHARS_SCANNED = 80_000
EVIDENCE_SPAN_CHARS = 650

CONTRACT_RE = re.compile(
    r"\b(customer|supplier|supply|contract|agreement|award|purchase order|"
    r"master services|strategic partnership|commercial partnership|"
    r"customer win|deployment|license agreement|distribution agreement|"
    r"manufacturing agreement)\b",
    re.IGNORECASE,
)
VALUE_RE = re.compile(
    r"\$\s?([0-9][0-9,]*(?:\.[0-9]+)?)\s?"
    r"(billion|bn|million|mm|m)?",
    re.IGNORECASE,
)
DURATION_RE = re.compile(
    r"\b(?:(\d+)|one|two|three|four|five|six|seven|eight|nine|ten)"
    r"[-\s]year\b|\bmulti[-\s]year\b",
    re.IGNORECASE,
)
EXCLUDE_RE = re.compile(
    r"\b(credit agreement|loan agreement|securities purchase agreement|"
    r"underwriting agreement|at-the-market|atm offering|common stock|"
    r"preferred stock|warrant|convertible|indenture|debt|tender offer|"
    r"stockholders should tender|merger agreement|employment agreement|"
    r"equity incentive|lease agreement|settlement agreement)\b",
    re.IGNORECASE,
)
WORD_NUMBERS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


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

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "thin_sample",
        "market_cap_join_sparse",
        "contract_text_false_positive",
        "window_regression",
        "accepted_distribution_comparator_not_beaten",
    ],
    "confidence_reason": (
        "Recent SEC text contract-economics and public-counterparty scouts "
        "failed because raw dollar values and named relations were not scaled "
        "by issuer size. PIT shares-outstanding from raw Companyfacts creates "
        "a materially new normalization axis explicitly requested by the prior "
        "reflection, but SEC text parsing remains noisy and positive replay "
        "would still need a shared default-off helper before acceptance."
    ),
    "recorded_at": "2026-06-20T14:04:48+00:00",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "uses_free_sec_filing_text": True,
    "uses_free_sec_companyfacts": True,
    "uses_raw_companyfacts_cache": True,
    "execution_envelope": {
        **base.PRODUCTION_IMPACT["execution_envelope"],
        "failure_handling": (
            "missing SEC filing text, missing explicit contract/customer/supplier "
            "language, missing numeric value/duration, stale or excluded "
            "financing/legal text, missing filed-date shares outstanding, "
            "missing OHLCV, missing next open, or missing 10d exit rejects the "
            "paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper parses the same SEC "
        "filing text fields, local evidence spans, exclusion rules, value/"
        "duration extraction, PIT shares-outstanding market-cap denominator, "
        "same-day OHLCV confirmation, cooldown, next-open paper entry, 10-day "
        "exit, costs, and concentration controls in both historical replay and "
        "daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: SEC 8-K contract-economics events may be tradable "
        "only when extracted contract value is material versus the issuer's "
        "PIT market cap, separating true demand/economic shock from generic "
        "earnings-presentations and press-release numerics."
    ),
    "2_history_check": {
        "novelty_gate": (
            "Initial reservation was blocked near SEC contract-text families; "
            "override is recorded because the new evidence axis is PIT issuer "
            "market-cap materiality from raw SEC shares outstanding, not a "
            "phrase/value threshold sweep."
        ),
        "exp-20260617-011": (
            "Rejected SEC text contract economics. Its own reflection required "
            "contract duration/value normalization by market cap before a "
            "valid retry; this run implements that denominator."
        ),
        "exp-20260619-017": (
            "Rejected public counterparty relation. This run trades the issuer "
            "and tests materiality of the issuer's own contract event."
        ),
        "exp-20260620-006": (
            "Rejected refinancing/covenant text. This run is demand/contract "
            "economics, not financing-term relief."
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
        "exp_20260620_015_sec_contract_value_market_cap_materiality.py"
    ),
}

_TEXT_INDEX_CACHE: tuple[dict[str, list[dict[str, Any]]], dict[str, Any]] | None = None
_SHARES_INDEX_CACHE: tuple[dict[str, list[dict[str, Any]]], dict[str, Any]] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return base._round(value, digits)


def _money_value(match: re.Match[str]) -> float | None:
    try:
        raw = float(match.group(1).replace(",", ""))
    except (TypeError, ValueError):
        return None
    unit = str(match.group(2) or "").lower()
    if unit in {"billion", "bn"}:
        value = raw * 1_000_000_000.0
    elif unit in {"million", "mm", "m"}:
        value = raw * 1_000_000.0
    else:
        value = raw
    if value < MIN_CONTRACT_VALUE_USD or value > MAX_CONTRACT_VALUE_USD:
        return None
    return value


def _duration_years(text: str) -> float | None:
    best: float | None = None
    for match in DURATION_RE.finditer(text):
        token = match.group(1)
        if token:
            years = float(token)
        else:
            word = match.group(0).split("-")[0].split()[0].lower()
            years = float(WORD_NUMBERS.get(word, 3 if "multi" in match.group(0).lower() else 0))
        if years > 0:
            best = years if best is None else max(best, years)
    return best


def _contract_economics(text: str) -> dict[str, Any] | None:
    if not text or len(text.split()) < MIN_TEXT_WORDS:
        return None
    scanned = text[:MAX_TEXT_CHARS_SCANNED]
    matches = list(CONTRACT_RE.finditer(scanned))
    if not matches:
        return None

    values: list[float] = []
    duration: float | None = None
    evidence_spans = 0
    for match in matches:
        start = max(0, match.start() - EVIDENCE_SPAN_CHARS)
        end = min(len(scanned), match.end() + EVIDENCE_SPAN_CHARS)
        span = scanned[start:end]
        if EXCLUDE_RE.search(span):
            continue
        span_values = [_money_value(value_match) for value_match in VALUE_RE.finditer(span)]
        span_values = [value for value in span_values if value is not None]
        span_duration = _duration_years(span)
        if not span_values and span_duration is None:
            continue
        values.extend(span_values)
        if span_duration is not None:
            duration = span_duration if duration is None else max(duration, span_duration)
        evidence_spans += 1

    if not values and duration is None:
        return None
    max_value = max(values) if values else None
    if max_value is None:
        return None
    return {
        "contract_value_usd": _round(max_value, 2) if max_value is not None else None,
        "contract_duration_years": _round(duration, 2) if duration is not None else None,
        "contract_value_count": len(values),
        "has_contract_value": bool(values),
        "has_contract_duration": duration is not None,
        "contract_evidence_span_count": evidence_spans,
        "text_word_count_scanned": len(scanned.split()),
    }


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


def _latest_shares_on_or_before(
    facts: list[dict[str, Any]],
    *,
    asof: str,
) -> dict[str, Any] | None:
    candidates = [fact for fact in facts if fact["filed"] <= asof]
    if not candidates:
        return None
    fact = max(candidates, key=lambda row: (row["filed"], row["end"], row["accn"]))
    age = base._days_between(asof, fact["filed"])
    if age > MAX_SHARES_OUTSTANDING_FACT_AGE_DAYS:
        return None
    return {**fact, "fact_age_days": age}


def _load_shares_outstanding_index(
    tickers: set[str],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    global _SHARES_INDEX_CACHE
    if _SHARES_INDEX_CACHE is not None:
        cached, summary = _SHARES_INDEX_CACHE
        return {ticker: rows for ticker, rows in cached.items() if ticker in tickers}, summary

    stats: Counter[str] = Counter()
    ticker_ciks: dict[str, int] = {}
    warehouse_uri = f"file:{Path(base.framework.WAREHOUSE).resolve().as_posix()}?mode=ro&immutable=1"
    with sqlite3.connect(warehouse_uri, uri=True) as con:
        rows = con.execute(
            """
            select ticker, cik
            from ticker_universe
            where cik is not null
            order by ticker
            """
        ).fetchall()
    for ticker, cik in rows:
        ticker_text = str(ticker or "").upper()
        if ticker_text not in tickers:
            continue
        try:
            ticker_ciks[ticker_text] = int(cik)
        except (TypeError, ValueError):
            stats["invalid_cik_rows"] += 1

    index: dict[str, list[dict[str, Any]]] = {}
    for ticker, cik in ticker_ciks.items():
        path = RAW_COMPANYFACTS_CACHE / f"CIK{cik:010d}.json"
        if not path.exists():
            stats["missing_companyfacts_cache_file"] += 1
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            stats["unreadable_companyfacts_cache_file"] += 1
            continue
        facts = _raw_shares_outstanding_facts(payload.get("facts", {}).get("dei", {}))
        if not facts:
            stats["tickers_missing_shares_outstanding"] += 1
            continue
        index[ticker] = facts
        stats["tickers_with_shares_outstanding"] += 1
        stats["shares_outstanding_fact_count"] += len(facts)

    summary = {
        "raw_companyfacts_cache": _repo_rel(RAW_COMPANYFACTS_CACHE),
        "shares_outstanding_tag": "dei.EntityCommonStockSharesOutstanding",
        "max_shares_outstanding_fact_age_days": MAX_SHARES_OUTSTANDING_FACT_AGE_DAYS,
        "warehouse_source": _repo_rel(base.framework.WAREHOUSE),
        **dict(stats),
    }
    _SHARES_INDEX_CACHE = (index, summary)
    return {ticker: rows for ticker, rows in index.items() if ticker in tickers}, summary


def _load_sec_text_rows(*, max_filed: str, tickers: list[str] | None = None, **_: Any) -> list[dict[str, Any]]:
    allowed = {ticker.upper() for ticker in tickers or []}
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in sorted(TEXT_DIR.glob("sec_filing_text_*.jsonl")):
        with path.open(encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ticker = str(raw.get("ticker") or "").upper()
                if allowed and ticker not in allowed:
                    continue
                if str(raw.get("form_base") or raw.get("form_type") or "").upper() != "8-K":
                    continue
                usable_date = str(raw.get("usable_trade_date") or "")[:10]
                if not usable_date or usable_date > max_filed:
                    continue
                accession = str(raw.get("accession_number") or "")
                key = accession or f"{ticker}:{usable_date}:{raw.get('primary_document')}"
                if key in seen:
                    continue
                seen.add(key)
                economics = _contract_economics(str(raw.get("combined_text") or ""))
                if economics is None:
                    continue
                rows.append(
                    {
                        "ticker": ticker,
                        "date": usable_date,
                        "filing_date": str(raw.get("filing_date") or "")[:10],
                        "accepted_at": str(raw.get("accepted_at") or "")[:19],
                        "accession_number": accession,
                        "form_type": raw.get("form_type"),
                        "eight_k_item_codes": raw.get("eight_k_item_codes") or [],
                        "primary_document": raw.get("primary_document"),
                        "text_char_count": raw.get("text_char_count"),
                        "text_word_count": raw.get("text_word_count"),
                        "pit_source": raw.get("pit_source"),
                        "pit_caveat": raw.get("pit_caveat"),
                        **economics,
                    }
                )
    return rows


def _build_quality_index(
    text_rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    stats: Counter[str] = Counter()
    for row in text_rows:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            stats["missing_ticker"] += 1
            continue
        by_ticker[ticker].append(row)
        stats["rows_with_value"] += 1 if row.get("has_contract_value") else 0
        stats["rows_with_duration"] += 1 if row.get("has_contract_duration") else 0
    for rows in by_ticker.values():
        rows.sort(
            key=lambda row: (
                row["date"],
                -(float(row.get("contract_value_usd") or 0.0)),
                -(float(row.get("contract_duration_years") or 0.0)),
                row.get("accession_number") or "",
            )
        )
    shares_index, shares_summary = _load_shares_outstanding_index(set(by_ticker))
    index: dict[str, dict[str, Any]] = {}
    for ticker, rows in by_ticker.items():
        shares = shares_index.get(ticker)
        if not shares:
            stats["tickers_dropped_missing_shares_outstanding"] += 1
            continue
        index[ticker] = {"events": rows, "shares_outstanding": shares}

    return index, {
        "sec_text_rows_loaded": len(text_rows),
        "tickers_with_contract_economics": len(by_ticker),
        "tickers_with_contract_economics_and_shares": len(index),
        "text_source": _repo_rel(TEXT_DIR),
        "shares_source": _repo_rel(RAW_COMPANYFACTS_CACHE),
        "min_contract_value_usd": MIN_CONTRACT_VALUE_USD,
        "max_contract_value_usd": MAX_CONTRACT_VALUE_USD,
        "min_contract_value_to_market_cap": MIN_CONTRACT_VALUE_TO_MARKET_CAP,
        "max_contract_value_to_market_cap": MAX_CONTRACT_VALUE_TO_MARKET_CAP,
        "evidence_span_chars": EVIDENCE_SPAN_CHARS,
        "shares_summary": shares_summary,
        **dict(stats),
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
    scan: Counter[str] = Counter()
    candidates: list[dict[str, Any]] = []
    for ticker in sorted(set(quality_index) & set(snapshot)):
        quality = quality_index[ticker]
        events = list(quality.get("events") or [])
        shares_facts = list(quality.get("shares_outstanding") or [])
        for event in events:
            signal_date = str(event.get("date") or "")[:10]
            if not (str(cfg["start"]) <= signal_date <= str(cfg["end"])):
                continue
            scan["event_rows_in_window"] += 1
            confirm = base._price_confirmation(
                snapshot=snapshot,
                indices=indices,
                ticker=ticker,
                signal_date=signal_date,
            )
            if confirm is None:
                scan["failed_price_confirmation"] += 1
                continue
            contract_value = _float_or_none(event.get("contract_value_usd"))
            if contract_value is None or contract_value <= 0.0:
                scan["missing_contract_value_after_span_parse"] += 1
                continue
            shares = _latest_shares_on_or_before(shares_facts, asof=signal_date)
            if shares is None:
                scan["missing_pit_shares_outstanding"] += 1
                continue
            rows = base.framework.shadow._series(snapshot, ticker)
            idx = indices.get(ticker, {}).get(signal_date)
            if idx is None:
                scan["missing_signal_idx_for_market_cap"] += 1
                continue
            close = base.framework._value(rows[idx], "Close")
            if close is None or close <= 0.0:
                scan["missing_signal_close_for_market_cap"] += 1
                continue
            market_cap = float(close) * float(shares["value"])
            if market_cap <= 0.0:
                scan["invalid_market_cap"] += 1
                continue
            value_to_market_cap = contract_value / market_cap
            if value_to_market_cap < MIN_CONTRACT_VALUE_TO_MARKET_CAP:
                scan["failed_min_value_to_market_cap"] += 1
                continue
            if value_to_market_cap > MAX_CONTRACT_VALUE_TO_MARKET_CAP:
                scan["failed_max_value_to_market_cap"] += 1
                continue
            meta = sector_entries.get(ticker, {})
            value_component = min(value_to_market_cap / MIN_CONTRACT_VALUE_TO_MARKET_CAP, 6.0)
            duration_component = min(float(event.get("contract_duration_years") or 0.0), 10.0) / 10.0
            score = (
                0.70 * value_component
                + 0.45 * duration_component
                + 0.50 * float(confirm["candidate_ret20_excess_spy"])
                + 0.15 * float(confirm["candidate_ret60_excess_spy"])
                + 0.12 * float(confirm["candidate_close_location"])
                + 0.025 * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
            )
            scan["qualified_candidate_rows"] += 1
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "SEC_TEXT_CONTRACT_ECONOMICS_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "sec_filing_text_usable_trade_date_and_signal_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_filing_text": True,
                    "uses_free_sec_companyfacts": True,
                    "uses_raw_companyfacts_cache": True,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    "text_contract_value_to_market_cap": _round(value_to_market_cap, 6),
                    "text_market_cap_usd": _round(market_cap, 2),
                    "text_signal_day_close_for_market_cap": _round(close, 4),
                    "text_shares_outstanding": _round(shares["value"], 2),
                    "text_shares_outstanding_filed": shares["filed"],
                    "text_shares_outstanding_end": shares["end"],
                    "text_shares_outstanding_fact_age_days": shares.get("fact_age_days"),
                    **{f"text_{key}": value for key, value in event.items() if key not in {"ticker", "date"}},
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
            -float(row.get("text_contract_value_to_market_cap") or 0.0),
            -float(row.get("text_contract_value_usd") or 0.0),
            -float(row.get("text_contract_duration_years") or 0.0),
            -float(row["candidate_ret20_excess_spy"] or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(rows)
    scan["candidate_signal_days"] = len({row["date"] for row in rows})
    scan["candidate_tickers"] = len({row["ticker"] for row in rows})
    return rows, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "min_contract_value_usd": MIN_CONTRACT_VALUE_USD,
        "min_contract_value_to_market_cap": MIN_CONTRACT_VALUE_TO_MARKET_CAP,
        "max_contract_value_to_market_cap": MAX_CONTRACT_VALUE_TO_MARKET_CAP,
        "min_text_words": MIN_TEXT_WORDS,
        "max_text_chars_scanned": MAX_TEXT_CHARS_SCANNED,
        "evidence_span_chars": EVIDENCE_SPAN_CHARS,
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
        "positive_replay_lead_not_promoted_sec_contract_value_market_cap_materiality"
        if gate["passed"]
        else "rejected_sec_contract_value_market_cap_materiality_candidate_pool"
    )
    return gate


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Text Events | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {events} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                events=scan.get("event_rows_in_window", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} SEC Contract Value Market-Cap Materiality",
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
    base.load_companyfacts_rows = _load_sec_text_rows
    base._build_quality_index = _build_quality_index
    base._candidate_rows_for_window = _candidate_rows_for_window
    base._gate4 = _gate4
    base._build_card = _build_card


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    if gate4["passed"]:
        interpretation = (
            "The SEC contract-value-to-market-cap materiality source cleared "
            "the numeric three-window replay screen, but remains only a replay "
            "lead because no shared daily/backtest parser was promoted."
        )
    else:
        interpretation = (
            "The SEC contract-value-to-market-cap materiality source did not clear Gate 4 "
            f"(failed: {', '.join(gate4['failed_reasons']) or 'none'}). "
            "It is not retained or promoted."
        )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": _utc_now(),
            "status": "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected",
            "decision": gate4["decision"],
            "accepted": False,
            "accepted_alpha": False,
            "numeric_gate4_passed": gate4["passed"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "default_off_paper_candidate_pool_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_sec_text_contract_materiality_candidate_pool",
            "new_evidence_type": "sec_contract_value_pit_market_cap_materiality_tuple",
            "nearby_prior_experiments": [
                "exp-20260617-011",
                "exp-20260619-017",
                "exp-20260620-006",
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
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "min_contract_value_usd": MIN_CONTRACT_VALUE_USD,
        "max_contract_value_usd": MAX_CONTRACT_VALUE_USD,
        "min_contract_value_to_market_cap": MIN_CONTRACT_VALUE_TO_MARKET_CAP,
        "max_contract_value_to_market_cap": MAX_CONTRACT_VALUE_TO_MARKET_CAP,
        "max_shares_outstanding_fact_age_days": MAX_SHARES_OUTSTANDING_FACT_AGE_DAYS,
        "min_text_words": MIN_TEXT_WORDS,
        "max_text_chars_scanned": MAX_TEXT_CHARS_SCANNED,
        "evidence_span_chars": EVIDENCE_SPAN_CHARS,
        "min_price": base.MIN_PRICE,
        "min_avg_dollar_volume_20d": base.MIN_AVG_DOLLAR_VOLUME_20D,
        "min_ret20_excess_spy": base.MIN_RET20_EXCESS_SPY,
        "min_ret60_excess_spy": base.MIN_RET60_EXCESS_SPY,
        "min_signal_return": base.MIN_SIGNAL_RETURN,
        "max_signal_return": base.MAX_SIGNAL_RETURN,
        "min_close_location": base.MIN_CLOSE_LOCATION,
        "max_realized_vol_20d": base.MAX_REALIZED_VOL_20D,
        "contract_terms": CONTRACT_RE.pattern,
        "exclude_terms": EXCLUDE_RE.pattern,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["companyfacts_source"] = _repo_rel(RAW_COMPANYFACTS_CACHE)
    payload["backtest_protocol"]["sec_filing_text_source"] = _repo_rel(TEXT_DIR)
    payload["backtest_protocol"]["execution_model"] = (
        "8-K SEC filing text is keyed by accepted_at and usable_trade_date. The "
        "parser admits rows only when contract/customer/supplier language has "
        "a local evidence span containing a numeric value, while financing/"
        "legal/tender/stock issuance false-positive spans are excluded. Raw SEC "
        "Companyfacts dei.EntityCommonStockSharesOutstanding facts are joined "
        "by filed date to signal-date close to compute PIT market cap, and the "
        "fixed rule requires contract value to be 4%-100% of that market cap. "
        "Price confirmation uses only signal-date OHLCV. Paper entry is the "
        "next available open with existing entry slippage; exit is the close "
        "10 trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    payload["gate2"]["runtime_fields"] = [
        "SEC filing text combined_text",
        "SEC filing accepted_at and usable_trade_date",
        "SEC filing accession_number",
        "local evidence-span extracted contract value",
        "raw SEC Companyfacts dei.EntityCommonStockSharesOutstanding filed date",
        "signal-date OHLCV close for PIT market-cap denominator",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A retry needs materially richer PIT relation provenance, such as "
        "normalized customer/supplier identity, contract duration/funding "
        "certainty, revenue exposure by named counterparty, or closed forward "
        "replacement-value rows from a shared daily helper. Do not sweep "
        "market-cap ratio, regex phrase lists, value thresholds, item codes, "
        "RS/close/volume guards, top-N, hold, cooldown, or notional on these "
        "frozen windows."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": interpretation,
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; "
            "max drawdown drift {:+.4f}; {} paper trades.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
                float(aggregate["max_drawdown_delta_max"] or 0.0),
                payload["target_trade_summary"]["total_trade_count"],
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping SEC contract phrase lists, value/"
            "market-cap thresholds, item codes, RS/close/volume/vol guards, "
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
    payload = _postprocess_payload(base._build_payload())
    _persist(payload)
    print(json.dumps(base.framework._safe(base._build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
