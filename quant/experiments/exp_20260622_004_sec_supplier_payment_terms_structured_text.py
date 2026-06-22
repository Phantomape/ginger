"""exp-20260622-004: SEC supplier payment-terms structured text scout.

Alpha-search replay scout. The single decision hypothesis is that PIT SEC
filing text disclosures of supplier-finance programs, reverse factoring,
confirming arrangements, or extended supplier payment terms are tradable only
when the local evidence span contains a quantified obligation, payment-days
term, or named bank/counterparty. This tests a working-capital provenance field
that is distinct from the accepted DPO/debt ratio helper and from generic SEC
contract-text phrase scouts.

This is replay-only/default-off. It changes no production strategy code,
shared helper, daily snapshot, live/default orders, ranking, sizing, exits,
watchlist, LLM, or news path. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260622_002_sec_share_repurchase_authorization as prior


EXPERIMENT_ID = "exp-20260622-004"
STEM = "sec_supplier_payment_terms_structured_text"
TRIAL_FAMILY = "sec_supplier_payment_terms_structured_text_candidate_pool"
TRIAL_VARIANT_ID = "sec_supplier_payment_terms_structured_text_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_supplier_payment_terms_structured_text_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

base = prior.base
REPO_ROOT = prior.REPO_ROOT
TEXT_DIR = prior.TEXT_DIR
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260622_004_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = prior.BASE_NOTIONAL_USD
HOLD_DAYS = prior.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = prior.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = prior.SAME_TICKER_COOLDOWN_DAYS

MIN_PAYMENT_VALUE_USD = 1_000_000.0
MAX_PAYMENT_VALUE_USD = 50_000_000_000.0
MIN_TEXT_WORDS = 120
MAX_TEXT_CHARS_SCANNED = 160_000
EVIDENCE_SPAN_CHARS = 900

ALLOWED_FORM_BASES = {"10-K", "10-Q", "8-K", "6-K"}

PAYMENT_TRIGGER_RE = re.compile(
    r"\b(supplier finance(?: program| arrangement| facility)?|"
    r"supplier financing(?: program| arrangement| facility)?|"
    r"supply chain financ(?:e|ing)(?: program| arrangement| facility)?|"
    r"supply-chain financ(?:e|ing)(?: program| arrangement| facility)?|"
    r"reverse factoring|confirming arrangement|payables? financ(?:e|ing)|"
    r"vendor financ(?:e|ing)(?: program| arrangement| facility)?|"
    r"structured payable|accounts payable program|third[- ]party "
    r"financial institution|extended payment terms|payment terms|"
    r"days payable outstanding|DPO)\b",
    re.IGNORECASE,
)
SUPPLIER_CONTEXT_RE = re.compile(
    r"\b(supplier|suppliers|vendor|vendors|trade payable|trade payables|"
    r"accounts payable|payables?|supply chain|confirmed invoices?|"
    r"participating suppliers?)\b",
    re.IGNORECASE,
)
STRUCTURE_RE = re.compile(
    r"\b(program|arrangement|facility|platform|agreement|obligations?|"
    r"outstanding|balance|classified as accounts payable|settle directly|"
    r"financial institutions?|third[- ]party|confirmed invoices?|"
    r"participating suppliers?)\b",
    re.IGNORECASE,
)
DAY_TERM_RE = re.compile(
    r"\b(?:net\s*)?(30|45|60|75|90|120|150|180)\s*(?:-| )?"
    r"(?:day|days|dpo)\b|\bpayment terms? (?:of|to|were|are|was|is|"
    r"extended to|increased to)\s*(30|45|60|75|90|120|150|180)\b",
    re.IGNORECASE,
)
BANK_RE = re.compile(
    r"\b(J\.?\s?P\.?\s?Morgan|JPMorgan|Citibank|Citi|Bank of America|"
    r"BofA|Wells Fargo|HSBC|Barclays|BNP Paribas|Santander|MUFG|Mizuho|"
    r"TD Bank|Royal Bank|Deutsche Bank|ING|PNC|Truist|U\.?S\.? Bank|"
    r"financial institution|third[- ]party bank)\b",
    re.IGNORECASE,
)
OBLIGATION_RE = re.compile(
    r"\b(obligations?|outstanding|balance|accounts payable|trade payables|"
    r"confirmed invoices?|supplier finance program obligations?|"
    r"payables? finance obligations?|classified as accounts payable)\b",
    re.IGNORECASE,
)
VALUE_RE = re.compile(
    r"\$\s?([0-9][0-9,]*(?:\.[0-9]+)?)\s?"
    r"(billion|bn|million|mm|m)?",
    re.IGNORECASE,
)
EXCLUDE_RE = re.compile(
    r"\b(customer financing|customer finance|customer payment terms|"
    r"credit agreement|loan agreement|underwriting agreement|at-the-market|"
    r"ATM offering|common stock offering|preferred stock|warrant|convertible|"
    r"indenture|securities purchase|equity line|private placement|"
    r"tender offer|merger agreement|settlement agreement|employee benefit|"
    r"tax withholding|risk factors?)\b",
    re.IGNORECASE,
)

KIND_SCORE = {
    "supplier_finance_program": 1.25,
    "reverse_factoring_or_confirming": 1.20,
    "bank_supported_payables": 1.10,
    "extended_supplier_payment_terms": 0.95,
    "days_payable_context": 0.85,
}

_LAST_LOAD_SCAN_SUMMARY: dict[str, Any] = {}

PREDICTION = {
    "success_probability": 0.12,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "thin_sample",
        "text_false_positive",
        "sec_phrase_family_frozen",
        "window_regression",
        "accepted_distribution_comparator_not_beaten",
        "no_shared_daily_parser",
    ],
    "confidence_reason": (
        "The playbook points to supplier/payment-term/covenant/counterparty "
        "provenance as one of the few remaining non-frozen free-data lanes. "
        "This field is distinct from accepted DPO/debt ratios, but SEC text "
        "sample risk is high and prior generic SEC text scouts were sparse."
    ),
    "recorded_at": "2026-06-22T03:07:12+00:00",
}

PRODUCTION_IMPACT = {
    **prior.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "uses_free_sec_filing_text": True,
    "uses_free_sec_companyfacts": False,
    "uses_raw_companyfacts_cache": False,
    "execution_envelope": {
        **prior.PRODUCTION_IMPACT["execution_envelope"],
        "failure_handling": (
            "missing SEC filing text, missing local supplier/payables context, "
            "missing supplier-finance/payment-term structure, missing local "
            "obligation value/payment-days/bank evidence, financing/offering/"
            "customer-payment false-positive text, missing OHLCV, missing next "
            "open, or missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper parses the same SEC "
        "filing text fields, supplier/payables context, local evidence spans, "
        "obligation value/payment-days/bank extraction, exclusion rules, "
        "same-day OHLCV confirmation, cooldown, next-open paper entry, 10-day "
        "exit, costs, and concentration controls in both historical replay and "
        "daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: PIT SEC filing text that explicitly discloses supplier "
        "finance, reverse factoring, confirming arrangements, or extended "
        "supplier payment terms with a local quantified obligation, payment-days "
        "term, or named bank/counterparty may expose working-capital financing "
        "provenance distinct from accepted DPO/debt ratio helpers and generic "
        "SEC text phrase scouts."
    ),
    "2_history_check": {
        "novelty_gate": (
            "experiment.py new blocked the first reservation near SEC contract/"
            "counterparty text families. Override is recorded because the new "
            "evidence axis is supplier-finance/payment-term program provenance "
            "requiring local obligation amount, days-payable term, or named "
            "bank/counterparty, not customer contract economics, public awards, "
            "accepted DPO/debt thresholds, SEC item metadata, or raw phrase/"
            "value sweeps."
        ),
        "exp-20260620-009": (
            "Accepted default-off supplier-financing/debt-relief helper uses "
            "Companyfacts DPO extension plus annual debt-burden relief. This "
            "run does not tune those thresholds or notional; it tests filed "
            "text provenance for supplier-finance/payment-term programs."
        ),
        "exp-20260620-006": (
            "Rejected refinancing/covenant text. This run targets supplier/"
            "payables financing provenance, not borrower debt-refinancing text."
        ),
        "exp-20260617-011": (
            "Rejected generic SEC contract economics. This run requires local "
            "supplier/payables context and structured payment-term evidence."
        ),
        "exp-20260622-003": (
            "Blocked candidate-pool surface readiness after finding no obvious "
            "non-frozen free surface. This run deliberately tests the playbook's "
            "remaining structured supplier/payment provenance lane."
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
        "exp_20260622_004_sec_supplier_payment_terms_structured_text.py"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return prior._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return prior._round(value, digits)


def _clean_excerpt(text: str) -> str:
    return " ".join(str(text or "").split())[:430]


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
    if value < MIN_PAYMENT_VALUE_USD or value > MAX_PAYMENT_VALUE_USD:
        return None
    return value


def _day_values(span: str) -> list[int]:
    values: list[int] = []
    for match in DAY_TERM_RE.finditer(span):
        raw = match.group(1) or match.group(2)
        if raw:
            values.append(int(raw))
    return values


def _payment_kind(span: str) -> str:
    lowered = span.lower()
    if "reverse factoring" in lowered or "confirming arrangement" in lowered:
        return "reverse_factoring_or_confirming"
    if "supplier finance" in lowered or "supplier financing" in lowered:
        return "supplier_finance_program"
    if "supply chain financ" in lowered or "payables financ" in lowered:
        return "supplier_finance_program"
    if BANK_RE.search(span) and ("payable" in lowered or "supplier" in lowered):
        return "bank_supported_payables"
    if "extended payment terms" in lowered or "payment terms" in lowered:
        return "extended_supplier_payment_terms"
    return "days_payable_context"


def _supplier_payment_event(text: str, stats: Counter[str] | None = None) -> dict[str, Any] | None:
    if not text or len(text.split()) < MIN_TEXT_WORDS:
        return None
    scanned = text[:MAX_TEXT_CHARS_SCANNED]
    best: dict[str, Any] | None = None
    for trigger in PAYMENT_TRIGGER_RE.finditer(scanned):
        if stats is not None:
            stats["trigger_spans"] += 1
        start = max(0, trigger.start() - EVIDENCE_SPAN_CHARS)
        end = min(len(scanned), trigger.end() + EVIDENCE_SPAN_CHARS)
        span = scanned[start:end]
        if EXCLUDE_RE.search(span):
            if stats is not None:
                stats["rejected_excluded_span"] += 1
            continue
        if not SUPPLIER_CONTEXT_RE.search(span):
            if stats is not None:
                stats["rejected_missing_supplier_context"] += 1
            continue
        if not STRUCTURE_RE.search(span):
            if stats is not None:
                stats["rejected_missing_structure_context"] += 1
            continue
        values = [_money_value(value_match) for value_match in VALUE_RE.finditer(span)]
        values = [value for value in values if value is not None]
        days = _day_values(span)
        bank_matches = sorted({match.group(0) for match in BANK_RE.finditer(span)})
        has_obligation = bool(OBLIGATION_RE.search(span))
        if not values and not days and not bank_matches:
            if stats is not None:
                stats["rejected_missing_local_value_days_or_bank"] += 1
            continue
        kind = _payment_kind(span)
        max_value = max(values) if values else None
        max_days = max(days) if days else None
        value_component = (
            min(math.log10(max(max_value or 1.0, 1.0) / MIN_PAYMENT_VALUE_USD), 4.0)
            if max_value is not None
            else 0.0
        )
        day_component = min(float(max_days or 0) / 120.0, 1.5)
        bank_component = 0.30 if bank_matches else 0.0
        obligation_component = 0.20 if has_obligation else 0.0
        strength = (
            KIND_SCORE[kind]
            + 0.18 * value_component
            + 0.20 * day_component
            + bank_component
            + obligation_component
        )
        event = {
            "supplier_payment_kind": kind,
            "supplier_payment_strength": _round(strength, 6),
            "supplier_payment_value_usd": _round(max_value, 2) if max_value is not None else None,
            "supplier_payment_days": max_days,
            "supplier_payment_named_banks": bank_matches,
            "supplier_payment_has_obligation_language": has_obligation,
            "supplier_payment_trigger": trigger.group(0),
            "supplier_payment_evidence_excerpt": _clean_excerpt(span),
            "text_word_count_scanned": len(scanned.split()),
        }
        if stats is not None:
            stats["accepted_structured_spans"] += 1
        if best is None or float(event["supplier_payment_strength"] or 0.0) > float(
            best["supplier_payment_strength"] or 0.0
        ):
            best = event
    return best


def _load_sec_text_rows(*, max_filed: str, tickers: list[str] | None = None, **_: Any) -> list[dict[str, Any]]:
    global _LAST_LOAD_SCAN_SUMMARY
    allowed = {ticker.upper() for ticker in tickers or []}
    stats: Counter[str] = Counter()
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
                    stats["json_decode_errors"] += 1
                    continue
                stats["filings_seen"] += 1
                ticker = str(raw.get("ticker") or "").upper()
                if allowed and ticker not in allowed:
                    stats["skipped_not_allowed_ticker"] += 1
                    continue
                form_base = str(raw.get("form_base") or raw.get("form_type") or "").upper()
                if form_base not in ALLOWED_FORM_BASES:
                    stats["skipped_form_base"] += 1
                    continue
                stats["allowed_form_filings"] += 1
                usable_date = str(raw.get("usable_trade_date") or "")[:10]
                if not usable_date or usable_date > max_filed:
                    stats["skipped_date"] += 1
                    continue
                accession = str(raw.get("accession_number") or "")
                key = accession or f"{ticker}:{usable_date}:{raw.get('primary_document')}"
                if key in seen:
                    stats["skipped_duplicate_accession"] += 1
                    continue
                seen.add(key)
                text = str(raw.get("combined_text") or "")
                if not PAYMENT_TRIGGER_RE.search(text[:MAX_TEXT_CHARS_SCANNED]):
                    stats["no_trigger_text"] += 1
                    continue
                stats["trigger_filings"] += 1
                event = _supplier_payment_event(text, stats)
                if event is None:
                    stats["trigger_filings_without_structured_event"] += 1
                    continue
                stats["structured_event_filings"] += 1
                rows.append(
                    {
                        "ticker": ticker,
                        "date": usable_date,
                        "filing_date": str(raw.get("filing_date") or "")[:10],
                        "accepted_at": str(raw.get("accepted_at") or "")[:19],
                        "accession_number": accession,
                        "form_type": raw.get("form_type"),
                        "form_base": form_base,
                        "eight_k_item_codes": raw.get("eight_k_item_codes") or [],
                        "primary_document": raw.get("primary_document"),
                        "text_char_count": raw.get("text_char_count"),
                        "text_word_count": raw.get("text_word_count"),
                        "pit_source": raw.get("pit_source"),
                        "pit_caveat": raw.get("pit_caveat"),
                        **event,
                    }
                )
    _LAST_LOAD_SCAN_SUMMARY = {
        "max_filed": max_filed,
        "allowed_ticker_count": len(allowed),
        **dict(stats),
    }
    return rows


def _build_quality_index(
    text_rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    kind_counts: Counter[str] = Counter()
    form_counts: Counter[str] = Counter()
    stats: Counter[str] = Counter()
    for row in text_rows:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            stats["missing_ticker"] += 1
            continue
        by_ticker[ticker].append(row)
        kind_counts[str(row.get("supplier_payment_kind") or "unknown")] += 1
        form_counts[str(row.get("form_base") or "unknown")] += 1
        stats["rows_with_value"] += 1 if row.get("supplier_payment_value_usd") else 0
        stats["rows_with_days"] += 1 if row.get("supplier_payment_days") else 0
        stats["rows_with_named_bank"] += 1 if row.get("supplier_payment_named_banks") else 0
    for rows in by_ticker.values():
        rows.sort(
            key=lambda row: (
                row["date"],
                -float(row.get("supplier_payment_strength") or 0.0),
                -float(row.get("supplier_payment_value_usd") or 0.0),
                -(row.get("supplier_payment_days") or 0),
                row.get("accession_number") or "",
            )
        )
    index = {ticker: {"events": rows} for ticker, rows in by_ticker.items()}
    return index, {
        "sec_text_rows_loaded": len(text_rows),
        "tickers_with_supplier_payment_terms": len(by_ticker),
        "source_scan_summary": _LAST_LOAD_SCAN_SUMMARY,
        "supplier_payment_kind_counts": dict(kind_counts),
        "form_counts": dict(form_counts),
        "text_source": _repo_rel(TEXT_DIR),
        "allowed_form_bases": sorted(ALLOWED_FORM_BASES),
        "min_payment_value_usd": MIN_PAYMENT_VALUE_USD,
        "max_payment_value_usd": MAX_PAYMENT_VALUE_USD,
        "evidence_span_chars": EVIDENCE_SPAN_CHARS,
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
        for event in list(quality_index[ticker].get("events") or []):
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
            meta = sector_entries.get(ticker, {})
            value = float(event.get("supplier_payment_value_usd") or 1.0)
            value_component = (
                min(math.log10(max(value, 1.0) / MIN_PAYMENT_VALUE_USD), 4.0)
                if event.get("supplier_payment_value_usd")
                else 0.0
            )
            days_component = min(float(event.get("supplier_payment_days") or 0) / 120.0, 1.5)
            score = (
                0.90 * float(event.get("supplier_payment_strength") or 0.0)
                + 0.20 * value_component
                + 0.16 * days_component
                + 0.55 * float(confirm["candidate_ret20_excess_spy"])
                + 0.16 * float(confirm["candidate_ret60_excess_spy"])
                + 0.12 * float(confirm["candidate_close_location"])
                + 0.025 * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
            )
            scan["qualified_candidate_rows"] += 1
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "SEC_SUPPLIER_PAYMENT_TERMS_STRUCTURED_TEXT_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "sec_filing_text_usable_trade_date_and_signal_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_filing_text": True,
                    "uses_free_sec_companyfacts": False,
                    "uses_raw_companyfacts_cache": False,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
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
            -float(row.get("text_supplier_payment_strength") or 0.0),
            -float(row.get("text_supplier_payment_value_usd") or 0.0),
            -(row.get("text_supplier_payment_days") or 0),
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
        "allowed_form_bases": sorted(ALLOWED_FORM_BASES),
        "min_payment_value_usd": MIN_PAYMENT_VALUE_USD,
        "max_payment_value_usd": MAX_PAYMENT_VALUE_USD,
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
        "positive_replay_lead_not_promoted_sec_supplier_payment_terms_structured_text"
        if gate["passed"]
        else "rejected_sec_supplier_payment_terms_structured_text_candidate_pool"
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
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | "
            "${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {events} | {trades} |".format(
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
            f"# {EXPERIMENT_ID} SEC Supplier Payment-Terms Structured Text",
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
                "adapter, backtester adapter, daily snapshot, production "
                "watchlist, order path, core entry, ranking, sizing, exit, LLM, "
                "or news behavior changed."
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
            "The SEC supplier payment-terms structured text source cleared the "
            "numeric three-window replay screen, but remains only a replay "
            "lead because no shared daily/backtest parser was promoted."
        )
    else:
        interpretation = (
            "The SEC supplier payment-terms structured text source did not "
            f"clear Gate 4 (failed: {', '.join(gate4['failed_reasons']) or 'none'}). "
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
            "mechanism_family": "production_visible_sec_text_supplier_payment_terms_candidate_pool",
            "new_evidence_type": "sec_supplier_payment_terms_finance_program_quantified_text_tuple",
            "nearby_prior_experiments": [
                "exp-20260620-009",
                "exp-20260620-006",
                "exp-20260617-011",
                "exp-20260622-003",
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
        "brier_score": round((PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2, 6),
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
        "allowed_form_bases": sorted(ALLOWED_FORM_BASES),
        "min_payment_value_usd": MIN_PAYMENT_VALUE_USD,
        "max_payment_value_usd": MAX_PAYMENT_VALUE_USD,
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
        "payment_trigger_terms": PAYMENT_TRIGGER_RE.pattern,
        "supplier_context_terms": SUPPLIER_CONTEXT_RE.pattern,
        "structure_terms": STRUCTURE_RE.pattern,
        "day_term_pattern": DAY_TERM_RE.pattern,
        "bank_terms": BANK_RE.pattern,
        "exclude_terms": EXCLUDE_RE.pattern,
        "kind_score": KIND_SCORE,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"].pop("companyfacts_source", None)
    payload["backtest_protocol"]["sec_filing_text_source"] = _repo_rel(TEXT_DIR)
    payload["backtest_protocol"]["execution_model"] = (
        "10-K, 10-Q, 8-K, and 6-K SEC filing text is keyed by accepted_at and "
        "usable_trade_date. The parser admits rows only when a local evidence "
        "span contains supplier/payables context, supplier-finance/payment-term "
        "structure, and at least one local obligation value, payment-days term, "
        "or named bank/counterparty, while customer-financing, securities, "
        "offering, loan, tender, settlement, tax, and risk-factor false "
        "positives are excluded. Price confirmation uses only signal-date "
        "OHLCV. Paper entry is next available open; exit is the close 10 "
        "trading days after signal with existing costs."
    )
    payload["gate2"]["runtime_fields"] = [
        "SEC filing text combined_text",
        "SEC filing accepted_at and usable_trade_date",
        "SEC filing accession_number",
        "local evidence-span supplier/payables context",
        "local evidence-span supplier-finance/payment-term structure",
        "local evidence-span extracted obligation value, payment-days term, or named bank",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A valid retry needs materially richer PIT supplier/payment provenance "
        "such as normalized bank/program identifiers, signed supplier-finance "
        "program terms from exhibits, before/after payable-term changes, "
        "counterparty-level supplier exposure, covenant interaction, or closed "
        "forward replacement-value rows from a shared daily helper. Do not "
        "sweep phrase lists, dollar thresholds, day thresholds, RS/close/volume "
        "guards, form types, top-N, hold, cooldown, or notional on these frozen "
        "windows."
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
            "Do not retry by sweeping supplier-finance/payment-term phrase "
            "lists, dollar/day thresholds, form types, RS/close/volume/vol "
            "guards, top-N, hold days, cooldown, or notional on these frozen "
            "windows."
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


def _write_manifest(payload: dict[str, Any]) -> None:
    runner = Path(__file__)
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(runner),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(path): base.framework._sha256(path)
            for path in [runner, OUT_JSON, LOG_JSON, TICKET_JSON, CARD_MD]
            if path.exists()
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
    print(json.dumps(base.framework._safe(base._build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
