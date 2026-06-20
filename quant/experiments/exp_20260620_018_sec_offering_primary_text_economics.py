"""exp-20260620-018: SEC offering primary-text financing economics.

Replay-only alpha search. The single decision hypothesis is that issuer
financing events become less noisy when SEC filing primary text is parsed for
financing amount, security type, use-of-proceeds, and PIT market-cap materiality
before the usual liquid SPY-relative price confirmation.

This is not the rejected metadata-only offering absorption scout. It uses the
new local accession-level SEC filing text rows now present across the three
canonical windows. No production code, shared adapter, live/default orders,
ranking, sizing, exits, LLM/news path, or watchlist behavior is changed. No
JavaScript is used.
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
import exp_20260620_015_sec_contract_value_market_cap_materiality as contract_helper


EXPERIMENT_ID = "exp-20260620-018"
STEM = "sec_offering_primary_text_economics"
TRIAL_FAMILY = "sec_offering_primary_text_economics_candidate_pool"
TRIAL_VARIANT_ID = "sec_offering_primary_text_economics_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_offering_primary_text_economics_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
TEXT_DIR = REPO_ROOT / "data" / "non_ohlcv"
RAW_COMPANYFACTS_CACHE = REPO_ROOT / "data" / "cache" / "sec" / "companyfacts"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260620_018_{STEM}.json"
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

MIN_FINANCING_AMOUNT_USD = 50_000_000.0
MAX_FINANCING_AMOUNT_USD = 30_000_000_000.0
MIN_AMOUNT_TO_MARKET_CAP = 0.01
MAX_AMOUNT_TO_MARKET_CAP = 0.70
MAX_SHARES_OUTSTANDING_FACT_AGE_DAYS = 550
MIN_TEXT_WORDS = 250
MAX_TEXT_CHARS_SCANNED = 90_000
EVIDENCE_SPAN_CHARS = 850

STRICT_FINANCING_RE = re.compile(
    r"\b(announces? (?:proposed )?offering|proposed offering|"
    r"priced (?:an|the) offering|public offering|registered direct offering|"
    r"at[- ]the[- ]market offering|ATM offering|shelf registration|"
    r"prospectus supplement|underwritten offering|private placement|"
    r"securities purchase agreement|senior secured notes|"
    r"senior unsecured notes|convertible senior notes|"
    r"aggregate principal amount|gross proceeds|net proceeds|use of proceeds|"
    r"offering price|pre[- ]funded warrants?|common warrants?)\b",
    re.IGNORECASE,
)
ACTION_RE = re.compile(
    r"\b(announced|proposed|priced|completed|closed|issued|raised|offered|"
    r"commenced|intends to offer|entered into|gross proceeds|net proceeds|"
    r"use of proceeds|fund|repay|redeem|construct|develop|working capital|"
    r"general corporate purposes)\b",
    re.IGNORECASE,
)
MONEY_RE = re.compile(
    r"\$\s?([0-9][0-9,]*(?:\.[0-9]+)?)\s?(billion|bn|million|mm|m)?",
    re.IGNORECASE,
)
NOISE_RE = re.compile(
    r"\b(amortization of debt discount|fair value of the conversion option|"
    r"if-converted method|dilutive effect of the shares issuable|"
    r"statement of cash flows|balance sheet|quarter ended)\b",
    re.IGNORECASE,
)
DEBT_RE = re.compile(r"\b(senior secured notes|senior unsecured notes|notes due|indenture)\b", re.IGNORECASE)
CONVERTIBLE_RE = re.compile(r"\b(convertible senior notes|convertible notes)\b", re.IGNORECASE)
EQUITY_RE = re.compile(
    r"\b(common stock|common shares|ordinary shares|registered direct|"
    r"pre[- ]funded warrants?|common warrants?|securities purchase agreement)\b",
    re.IGNORECASE,
)
ATM_RE = re.compile(r"\b(at[- ]the[- ]market|ATM offering|ATM program)\b", re.IGNORECASE)
PROJECT_RE = re.compile(
    r"\b(construction|construct|data center|datacenter|project|campus|"
    r"development|capacity|growth|AI|HPC|pipeline|infrastructure)\b",
    re.IGNORECASE,
)
REFINANCE_RE = re.compile(r"\b(repay|redeem|refinance|existing debt|bridge loan|credit facility)\b", re.IGNORECASE)
GENERAL_RE = re.compile(r"\b(working capital|general corporate purposes)\b", re.IGNORECASE)

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "thin_sample",
        "offering_events_are_dilution_noise",
        "window_regression",
        "concentration_failed",
        "accepted_distribution_comparator_not_beaten",
    ],
    "confidence_reason": (
        "Raw SEC offering price absorption failed all windows and a June 18 "
        "readiness run blocked because primary-document economics were missing; "
        "the current repo now has accession-level SEC filing text rows across "
        "all three windows with proceeds/notes/offering terms, making parsed "
        "amount/use-of-proceeds/market-cap normalization a genuinely new but "
        "still noisy evidence axis."
    ),
    "recorded_at": "2026-06-20T16:14:45+00:00",
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
            "missing SEC filing text, missing financing action terms, missing "
            "usable amount/security/use-of-proceeds classification, stale or "
            "missing PIT shares outstanding, missing OHLCV, missing next open, "
            "or missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until one shared default-off helper computes the same "
        "SEC primary-text parser, financing amount/security/use-of-proceeds "
        "classification, PIT market-cap denominator, price confirmation, "
        "cooldown, next-open paper entry, 10-day exit, costs, and concentration "
        "controls in both historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: SEC offering/prospectus primary-document economics "
        "with parsed financing amount normalized by PIT market cap, security "
        "type, and use-of-proceeds may separate constructive capital raised for "
        "growth/project financing from raw dilution-noise offering events when "
        "price action absorbs the filing."
    ),
    "2_history_check": {
        "novelty_gate": (
            "The gate misclassified the text/economics hypothesis as a "
            "Companyfacts capital-efficiency neighbor. Override was recorded "
            "because the new evidence axis is accession-level SEC primary text "
            "plus parsed financing amount/security/use-of-proceeds and PIT "
            "market-cap materiality."
        ),
        "exp-20260617-023": (
            "Rejected metadata/form-based SEC offering price absorption across "
            "all windows. This run adds primary-document economics, not another "
            "form/price threshold sweep."
        ),
        "exp-20260618-013": (
            "Blocked offering financing-economics readiness because local "
            "primary text was missing then. Current sec_filing_text rows now "
            "provide the missing primary-document surface across all windows."
        ),
        "exp-20260619-020": (
            "Readiness snapshot still listed offering economics as missing or "
            "immature. This run uses the newly present local SEC text rows."
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
        "exp_20260620_018_sec_offering_primary_text_economics.py"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return base.framework._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return base.framework._round(value, digits)


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


def _money_value(match: re.Match[str]) -> float | None:
    number = float(match.group(1).replace(",", ""))
    unit = (match.group(2) or "").lower()
    if unit in {"billion", "bn"}:
        number *= 1_000_000_000.0
    elif unit in {"million", "mm", "m"}:
        number *= 1_000_000.0
    elif number < 1_000_000.0:
        return None
    if number < MIN_FINANCING_AMOUNT_USD or number > MAX_FINANCING_AMOUNT_USD:
        return None
    return number


def _classify_security(span: str) -> str:
    if ATM_RE.search(span):
        return "atm_equity"
    if CONVERTIBLE_RE.search(span):
        return "convertible_debt"
    if DEBT_RE.search(span):
        return "debt_notes"
    if EQUITY_RE.search(span):
        return "equity_or_warrants"
    return "financing_unspecified"


def _classify_use(span: str) -> str:
    if PROJECT_RE.search(span):
        return "growth_project_or_capacity"
    if REFINANCE_RE.search(span):
        return "debt_refinancing"
    if GENERAL_RE.search(span):
        return "general_corporate_or_working_capital"
    return "use_unspecified"


def _security_bonus(security_type: str) -> float:
    return {
        "debt_notes": 0.45,
        "convertible_debt": 0.25,
        "atm_equity": -0.10,
        "equity_or_warrants": -0.05,
        "financing_unspecified": 0.0,
    }.get(security_type, 0.0)


def _use_bonus(use_of_proceeds: str) -> float:
    return {
        "growth_project_or_capacity": 0.55,
        "debt_refinancing": 0.20,
        "general_corporate_or_working_capital": 0.05,
        "use_unspecified": 0.0,
    }.get(use_of_proceeds, 0.0)


def _financing_economics(text: str) -> dict[str, Any] | None:
    if not text or len(text.split()) < MIN_TEXT_WORDS:
        return None
    scan_text = text[:MAX_TEXT_CHARS_SCANNED]
    best: dict[str, Any] | None = None
    for term_match in STRICT_FINANCING_RE.finditer(scan_text):
        start = max(0, term_match.start() - EVIDENCE_SPAN_CHARS)
        end = min(len(scan_text), term_match.end() + EVIDENCE_SPAN_CHARS)
        span = scan_text[start:end]
        if not ACTION_RE.search(span):
            continue
        if NOISE_RE.search(span) and not re.search(r"\b(raised|completed|closed|issued|priced|proceeds)\b", span, re.IGNORECASE):
            continue
        amount_values = [
            parsed
            for parsed in (_money_value(m) for m in MONEY_RE.finditer(span))
            if parsed is not None
        ]
        if not amount_values:
            continue
        amount = max(amount_values)
        security_type = _classify_security(span)
        use_of_proceeds = _classify_use(span)
        term = term_match.group(1).lower()
        score_hint = (
            math.log10(max(amount, 1.0))
            + _security_bonus(security_type)
            + _use_bonus(use_of_proceeds)
        )
        candidate = {
            "financing_amount_usd": amount,
            "financing_term": term,
            "security_type": security_type,
            "use_of_proceeds": use_of_proceeds,
            "amount_mentions": len(amount_values),
            "max_local_amount_usd": amount,
            "evidence_start": start,
            "evidence_end": end,
            "evidence_excerpt": span[:700].encode("ascii", "ignore").decode("ascii"),
            "score_hint": score_hint,
            "has_project_use": use_of_proceeds == "growth_project_or_capacity",
            "has_debt_security": security_type in {"debt_notes", "convertible_debt"},
            "has_equity_security": security_type in {"atm_equity", "equity_or_warrants"},
        }
        if best is None or candidate["score_hint"] > best["score_hint"]:
            best = candidate
    return best


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
                usable_date = str(raw.get("usable_trade_date") or "")[:10]
                if not usable_date or usable_date > max_filed:
                    continue
                accession = str(raw.get("accession_number") or "")
                key = accession or f"{ticker}:{usable_date}:{raw.get('primary_document')}"
                if key in seen:
                    continue
                seen.add(key)
                economics = _financing_economics(str(raw.get("combined_text") or ""))
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
                        "form_base": raw.get("form_base"),
                        "eight_k_item_codes": raw.get("eight_k_item_codes") or [],
                        "primary_document": raw.get("primary_document"),
                        "text_char_count": raw.get("text_char_count"),
                        "text_word_count": raw.get("text_word_count"),
                        "pit_source": raw.get("pit_source"),
                        "pit_caveat": raw.get("pit_caveat"),
                        "source_file": _repo_rel(path),
                        **economics,
                    }
                )
    return rows


def _load_shares_outstanding_index(tickers: set[str]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    # The imported helper caches the first ticker subset, so reset it per window.
    contract_helper._SHARES_INDEX_CACHE = None
    return contract_helper._load_shares_outstanding_index(tickers)


def _build_quality_index(
    text_rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    stats: Counter[str] = Counter()
    security_counter: Counter[str] = Counter()
    use_counter: Counter[str] = Counter()
    amount_sum = 0.0
    for row in text_rows:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            stats["missing_ticker"] += 1
            continue
        by_ticker[ticker].append(row)
        security_counter[str(row.get("security_type") or "unknown")] += 1
        use_counter[str(row.get("use_of_proceeds") or "unknown")] += 1
        amount_sum += float(row.get("financing_amount_usd") or 0.0)
    for rows in by_ticker.values():
        rows.sort(
            key=lambda row: (
                row["date"],
                -float(row.get("score_hint") or 0.0),
                -float(row.get("financing_amount_usd") or 0.0),
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
        "tickers_with_financing_economics": len(by_ticker),
        "tickers_with_financing_economics_and_shares": len(index),
        "total_parsed_financing_amount_usd": round(amount_sum, 2),
        "security_type_counts": dict(security_counter),
        "use_of_proceeds_counts": dict(use_counter),
        "text_source": _repo_rel(TEXT_DIR),
        "shares_source": _repo_rel(RAW_COMPANYFACTS_CACHE),
        "min_financing_amount_usd": MIN_FINANCING_AMOUNT_USD,
        "max_financing_amount_usd": MAX_FINANCING_AMOUNT_USD,
        "min_amount_to_market_cap": MIN_AMOUNT_TO_MARKET_CAP,
        "max_amount_to_market_cap": MAX_AMOUNT_TO_MARKET_CAP,
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
            amount = _float_or_none(event.get("financing_amount_usd"))
            if amount is None or amount <= 0.0:
                scan["missing_financing_amount"] += 1
                continue
            shares = contract_helper._latest_shares_on_or_before(shares_facts, asof=signal_date)
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
            amount_to_market_cap = amount / market_cap
            if amount_to_market_cap < MIN_AMOUNT_TO_MARKET_CAP:
                scan["failed_min_amount_to_market_cap"] += 1
                continue
            if amount_to_market_cap > MAX_AMOUNT_TO_MARKET_CAP:
                scan["failed_max_amount_to_market_cap"] += 1
                continue
            security_type = str(event.get("security_type") or "financing_unspecified")
            use_of_proceeds = str(event.get("use_of_proceeds") or "use_unspecified")
            meta = sector_entries.get(ticker, {})
            materiality_component = min(amount_to_market_cap / MIN_AMOUNT_TO_MARKET_CAP, 6.0)
            amount_component = min(math.log10(max(amount, 1.0)) - 7.5, 3.0)
            score = (
                0.50 * materiality_component
                + 0.25 * amount_component
                + _security_bonus(security_type)
                + _use_bonus(use_of_proceeds)
                + 0.55 * float(confirm["candidate_ret20_excess_spy"])
                + 0.18 * float(confirm["candidate_ret60_excess_spy"])
                + 0.10 * float(confirm["candidate_close_location"])
                + 0.020 * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
            )
            scan["qualified_candidate_rows"] += 1
            scan[f"qualified_security_{security_type}"] += 1
            scan[f"qualified_use_{use_of_proceeds}"] += 1
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "SEC_OFFERING_PRIMARY_TEXT_ECONOMICS_PAPER",
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
                    "financing_amount_to_market_cap": _round(amount_to_market_cap, 6),
                    "financing_market_cap_usd": _round(market_cap, 2),
                    "financing_signal_day_close_for_market_cap": _round(close, 4),
                    "financing_shares_outstanding": _round(shares["value"], 2),
                    "financing_shares_outstanding_filed": shares["filed"],
                    "financing_shares_outstanding_end": shares["end"],
                    "financing_shares_outstanding_fact_age_days": shares.get("fact_age_days"),
                    **{f"financing_{key}": value for key, value in event.items() if key not in {"ticker", "date"}},
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
            -float(row.get("financing_amount_to_market_cap") or 0.0),
            -float(row.get("financing_financing_amount_usd") or 0.0),
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
        "min_financing_amount_usd": MIN_FINANCING_AMOUNT_USD,
        "max_financing_amount_usd": MAX_FINANCING_AMOUNT_USD,
        "min_amount_to_market_cap": MIN_AMOUNT_TO_MARKET_CAP,
        "max_amount_to_market_cap": MAX_AMOUNT_TO_MARKET_CAP,
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
        "positive_replay_lead_not_promoted_sec_offering_primary_text_economics"
        if gate["passed"]
        else "rejected_sec_offering_primary_text_economics_candidate_pool"
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
            f"# {EXPERIMENT_ID} SEC Offering Primary-Text Economics",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Aggregate EV delta: `{aggregate['expected_value_score_delta_sum']:+.4f}`",
            f"- Aggregate PnL delta: `${aggregate['total_pnl_delta_sum']:+,.2f}`",
            f"- Target trades: `{payload['target_trade_summary']['total_trade_count']}`",
            f"- Gate 4 passed: `{payload['gate4']['passed']}`",
            "- Production impact: none; replay-only/default-off scout.",
            "",
            "## Hypothesis",
            "",
            PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "",
            "## Three-window Gate 4",
            "",
            *rows,
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            payload["post_run_reflection"]["new_evidence_required"],
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
            "The SEC offering primary-text economics source cleared the numeric "
            "three-window replay screen, but remains only a replay lead because "
            "no shared daily/backtest parser was promoted."
        )
    else:
        interpretation = (
            "The SEC offering primary-text economics source did not clear Gate 4 "
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
            "mechanism_family": "production_visible_sec_offering_primary_text_economics_candidate_pool",
            "new_evidence_type": "sec_offering_primary_text_financing_amount_security_use_market_cap_tuple",
            "nearby_prior_experiments": [
                "exp-20260617-023",
                "exp-20260618-013",
                "exp-20260619-020",
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
        "min_financing_amount_usd": MIN_FINANCING_AMOUNT_USD,
        "max_financing_amount_usd": MAX_FINANCING_AMOUNT_USD,
        "min_amount_to_market_cap": MIN_AMOUNT_TO_MARKET_CAP,
        "max_amount_to_market_cap": MAX_AMOUNT_TO_MARKET_CAP,
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
        "strict_financing_terms": STRICT_FINANCING_RE.pattern,
        "action_terms": ACTION_RE.pattern,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["companyfacts_source"] = _repo_rel(RAW_COMPANYFACTS_CACHE)
    payload["backtest_protocol"]["sec_filing_text_source"] = _repo_rel(TEXT_DIR)
    payload["backtest_protocol"]["execution_model"] = (
        "SEC filing primary text is keyed by accepted_at and usable_trade_date. "
        "The parser admits only local spans containing financing/offering action "
        "terms plus a financing amount of at least $50M. It classifies debt, "
        "convertible, ATM/equity, and use-of-proceeds context, then joins raw "
        "SEC Companyfacts dei.EntityCommonStockSharesOutstanding by filed date "
        "to signal-date close to compute PIT market cap. The fixed rule requires "
        "amount/market-cap between 1% and 70%. Price confirmation uses only "
        "signal-date OHLCV. Paper entry is the next available open with existing "
        "entry slippage; exit is the close 10 trading days after the signal with "
        "target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["gate2"]["runtime_fields"] = [
        "SEC filing text combined_text",
        "SEC filing accepted_at and usable_trade_date",
        "SEC filing accession_number",
        "local financing evidence-span amount",
        "security type classifier",
        "use-of-proceeds classifier",
        "raw SEC Companyfacts dei.EntityCommonStockSharesOutstanding filed date",
        "signal-date OHLCV close for PIT market-cap denominator",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A retry needs materially richer PIT financing economics, such as "
        "actual takedown vs shelf capacity, share-count dilution normalized by "
        "float, lockup/hedging terms, underwriter quality, closed deal outcome, "
        "or closed forward replacement-value rows from a shared daily helper. "
        "Do not sweep offering text regexes, amount/market-cap thresholds, "
        "security-type weights, price/RS/volume guards, top-N, hold, cooldown, "
        "or notional on these frozen windows."
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
            "Do not retry by sweeping SEC offering primary-text regexes, "
            "amount/market-cap thresholds, security-type weights, use-of-proceeds "
            "labels, form lists, RS/close/volume/vol guards, top-N, hold days, "
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
