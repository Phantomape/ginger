"""exp-20260619-017: issuer 8-K public-counterparty relation scout.

Replay-only alpha search. The single decision hypothesis is a free SEC-text
candidate-pool expansion: when an issuer-filed 8-K names another public company
as the target/counterparty in a transaction, settlement, cooperation,
partnership, customer, supplier, license, or acquisition context, the named
public company can be a cleaner trade candidate than the filing issuer. This
tests cross-company relation provenance instead of another issuer-text phrase
screen.

The data shape is uncertain, so this is a private replay scout. No production
code, shared adapter, live/default orders, ranking, sizing, exits, LLM/news
path, or watchlist behavior is changed. A positive replay is only a lead until
a shared historical/daily helper reproduces the same PIT text semantics. No
JavaScript is used.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260614_020_accruals_cash_conversion_quality as base
import exp_20260617_011_sec_text_contract_economics as template
import exp_20260617_021_intraindustry_liquidity_leader_lead_lag_scout as broad_static


EXPERIMENT_ID = "exp-20260619-017"
STEM = "issuer_8k_public_counterparty_relation"
TRIAL_FAMILY = "issuer_8k_public_counterparty_relation_candidate_pool"
TRIAL_VARIANT_ID = "public_counterparty_relation_absorption_top1_next_open_10d_v1"
CHANGED_VARIABLE = "issuer_8k_public_counterparty_relation_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
TEXT_DIR = REPO_ROOT / "data" / "non_ohlcv"
SEC_TICKERS_JSON = REPO_ROOT / "data" / "reference" / "sec_company_tickers.json"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260619_017_{STEM}.json"
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

MIN_TEXT_WORDS = 250
MAX_TEXT_CHARS_SCANNED = 60_000
MATCH_CONTEXT_CHARS = 1_200
MAX_RELATION_WINDOWS_PER_FILING = 40

MNA_RE = re.compile(
    r"\b("
    r"MERGER AGREEMENT|AGREEMENT AND PLAN OF MERGER|BUSINESS COMBINATION|"
    r"ACQUISITION AGREEMENT|PROPOSED ACQUISITION|ACQUIRE|ACQUIRED|"
    r"TAKE OVER BID|TAKEOVER BID|TENDER OFFER|EXCHANGE OFFER|"
    r"PROPOSED COMBINATION|STRATEGIC TRANSACTION"
    r")\b"
)
GOVERNANCE_RE = re.compile(
    r"\b("
    r"SETTLEMENT AGREEMENT|COOPERATION AGREEMENT|STANDSTILL|BOARD SEAT|"
    r"NOMINATE|NOMINATION|PROXY|SPECIAL MEETING|SHAREHOLDER AGREEMENT|"
    r"RIGHTS PLAN"
    r")\b"
)
COMMERCIAL_RE = re.compile(
    r"\b("
    r"STRATEGIC PARTNERSHIP|COMMERCIAL PARTNERSHIP|COLLABORATION AGREEMENT|"
    r"SUPPLY AGREEMENT|CUSTOMER AGREEMENT|PURCHASE AGREEMENT|PURCHASE ORDER|"
    r"LICENSE AGREEMENT|DISTRIBUTION AGREEMENT|MANUFACTURING AGREEMENT|"
    r"MASTER SERVICES|JOINT VENTURE|AWARD|DEPLOYMENT"
    r")\b"
)
FINANCING_EXCLUDE_RE = re.compile(
    r"\b("
    r"CREDIT AGREEMENT|LOAN AGREEMENT|INDENTURE|NOTES DUE|SENIOR NOTES|"
    r"CONVERTIBLE NOTES|DEBENTURE|WARRANT|UNDERWRITING AGREEMENT|"
    r"AT THE MARKET|ATM OFFERING|SECURITIES PURCHASE AGREEMENT|"
    r"EMPLOYMENT AGREEMENT|EQUITY INCENTIVE|LEASE AGREEMENT"
    r")\b"
)
NORMALIZE_RE = re.compile(r"[^A-Z0-9]+")

LEGAL_SUFFIXES = {
    "INC",
    "INCORPORATED",
    "CORP",
    "CORPORATION",
    "CO",
    "COMPANY",
    "COS",
    "LTD",
    "LIMITED",
    "PLC",
    "LLC",
    "LP",
    "L P",
    "SA",
    "NV",
    "AG",
    "SE",
    "HOLDING",
    "HOLDINGS",
    "GROUP",
    "CLASS",
    "CL",
    "A",
    "B",
    "C",
    "COMMON",
    "STOCK",
}
BAD_ALIASES = {
    "THE",
    "INC",
    "CORP",
    "GROUP",
    "HOLDINGS",
    "GLOBAL",
    "TECHNOLOGIES",
    "INTERNATIONAL",
    "UNITED STATES",
    "NASDAQ",
    "NYSE",
    "NEW YORK STOCK EXCHANGE",
    "SECURITIES AND EXCHANGE COMMISSION",
}
BAD_SINGLE_TOKEN_ALIASES = {
    "APPLE",
    "UNITED",
    "FIRST",
    "NATIONAL",
    "FEDERAL",
    "BLACK",
    "SILVER",
    "GOLD",
    "GREEN",
    "BLUE",
    "ENERGY",
    "POWER",
    "HEALTH",
    "WESTERN",
    "EASTERN",
}

PREDICTION = {
    "success_probability": 0.13,
    "expected_ev_delta": 0.20,
    "expected_pnl_delta": 3000.0,
    "main_failure_modes": [
        "thin_target_sample",
        "public_company_name_false_positive",
        "counterparty_news_already_priced",
        "price_confirmation_selects_existing_momentum_only",
        "window_regression",
        "accepted_distribution_comparator_not_beaten",
    ],
    "confidence_reason": (
        "Prior generic SEC text/item-code families failed or froze, but the new "
        "evidence axis is relation provenance: trade the named public "
        "counterparty/target rather than the filing issuer. The first row in "
        "the local SEC text archive already shows the intended structure "
        "(issuer RIOT naming public target BITF in a settlement/standstill "
        "context). Failure risk is high because deterministic company-name "
        "matching can be sparse or noisy, and a positive private replay would "
        "still need a shared daily/backtest helper before promotion."
    ),
    "recorded_at": "2026-06-19T18:40:00Z",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "uses_free_sec_filing_text": True,
    "uses_free_sec_company_tickers": True,
    "uses_free_sec_companyfacts": False,
    "uses_free_ohlcv": True,
    "trade_enabled": False,
    "execution_envelope": {
        **base.PRODUCTION_IMPACT["execution_envelope"],
        "candidate_universe": "broad liquid warehouse names with SEC ticker-title aliases",
        "failure_handling": (
            "missing SEC filing text, missing public-company alias, self-issuer "
            "match, missing relation context, financing-only context, missing "
            "OHLCV, missing next open, or missing 10d exit rejects the paper "
            "candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper parses the same PIT "
        "issuer 8-K text, SEC ticker-title alias map, relation/exclusion rules, "
        "target-side OHLCV confirmation, cooldown, next-open paper entry, "
        "10-day exit, costs, and concentration controls in both historical "
        "replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: issuer-filed 8-K text that names another public "
        "company as a transaction, governance settlement, cooperation, "
        "partnership, customer, supplier, license, or acquisition counterparty "
        "can identify a tradable named-company information absorption event. "
        "The candidate is the named public counterparty, not the issuer; "
        "target-side same-day liquid SPY-relative confirmation is required."
    ),
    "2_history_check": {
        "novelty_gate": (
            "Initial reserve was blocked near issuer-text and peer-theme "
            "families; override was used because the new evidence axis is "
            "cross-company relation provenance from issuer 8-K text to a "
            "different public ticker."
        ),
        "exp-20260617-011": (
            "Rejected issuer SEC text contract-economics on the issuer itself; "
            "this run maps issuer text to a named public counterparty target."
        ),
        "exp-20260618-015": (
            "Peer theme propagation tested broad theme text; this run requires "
            "an explicit named public company and relation context."
        ),
        "exp-20260619-013": (
            "Issuer governance resolution text traded the issuer; this run "
            "tests the named counterpart/target company in the issuer filing."
        ),
        "exp-20260618-019": (
            "Private 13G/A governance catalyst traded subject/holder surfaces; "
            "this run is issuer 8-K text relation extraction, not Schedule "
            "13D/13G ownership status."
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
        "exp_20260619_017_issuer_8k_public_counterparty_relation.py"
    ),
}

_ALIAS_CACHE: tuple[dict[str, str], int, dict[str, Any]] | None = None
_TEXT_RELATION_CACHE: tuple[list[dict[str, Any]], dict[str, Any]] | None = None
SECOND_DOCUMENT_RE = re.compile(
    r"\s(?:SEC EDGAR SUBMISSION|<SEC-DOCUMENT>|DOCUMENT\s+0{6,}\d|"
    r"DOCUMENT\s+[0-9]{10}-[0-9]{2}-[0-9]{6}-INDEX)",
    re.IGNORECASE,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return base._round(value, digits)


def _normalize_text(text: str) -> str:
    return NORMALIZE_RE.sub(" ", str(text or "").upper()).strip()


def _alias_usable(alias: str) -> bool:
    if alias in BAD_ALIASES:
        return False
    tokens = alias.split()
    if not tokens:
        return False
    if len(tokens) == 1:
        token = tokens[0]
        return len(token) >= 6 and token not in BAD_SINGLE_TOKEN_ALIASES
    return len(alias) >= 8


def _company_aliases(title: str) -> set[str]:
    norm = _normalize_text(title)
    if norm.startswith("THE "):
        norm = norm[4:]
    aliases: set[str] = set()
    if _alias_usable(norm):
        aliases.add(norm)
    tokens = norm.split()
    while tokens and tokens[-1] in LEGAL_SUFFIXES:
        tokens.pop()
    stripped = " ".join(tokens)
    if _alias_usable(stripped):
        aliases.add(stripped)
    return aliases


def _load_public_company_aliases() -> tuple[dict[str, str], int, dict[str, Any]]:
    global _ALIAS_CACHE
    if _ALIAS_CACHE is not None:
        return _ALIAS_CACHE

    broad_tickers = broad_static._broad_liquid_tickers()
    raw = json.loads(SEC_TICKERS_JSON.read_text(encoding="utf-8"))
    entries = raw.values() if isinstance(raw, dict) else raw
    alias_targets: dict[str, set[str]] = defaultdict(set)
    title_by_ticker: dict[str, str] = {}
    for entry in entries:
        ticker = str(entry.get("ticker") or "").upper()
        if ticker not in broad_tickers:
            continue
        title = str(entry.get("title") or "")
        if not title:
            continue
        title_by_ticker[ticker] = title
        for alias in _company_aliases(title):
            alias_targets[alias].add(ticker)

    alias_to_ticker = {
        alias: next(iter(tickers))
        for alias, tickers in alias_targets.items()
        if len(tickers) == 1
    }
    if not alias_to_ticker:
        raise RuntimeError("No usable public-company aliases found for broad universe")
    max_alias_tokens = max(len(alias.split()) for alias in alias_to_ticker)
    summary = {
        "source": _repo_rel(SEC_TICKERS_JSON),
        "broad_liquid_tickers": len(broad_tickers),
        "sec_ticker_titles_in_broad_universe": len(title_by_ticker),
        "unique_aliases": len(alias_to_ticker),
        "max_alias_tokens": max_alias_tokens,
        "duplicate_aliases_dropped": sum(1 for tickers in alias_targets.values() if len(tickers) > 1),
    }
    _ALIAS_CACHE = (alias_to_ticker, max_alias_tokens, summary)
    return _ALIAS_CACHE


def _context_alias_matches(
    context: str,
    alias_to_ticker: dict[str, str],
    max_alias_tokens: int,
) -> list[tuple[str, str]]:
    tokens = context.split()
    matches: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    n = len(tokens)
    max_width = min(max_alias_tokens, 8)
    for start in range(n):
        limit = min(max_width, n - start)
        for width in range(limit, 0, -1):
            alias = " ".join(tokens[start : start + width])
            ticker = alias_to_ticker.get(alias)
            if not ticker:
                continue
            key = (alias, ticker)
            if key not in seen:
                seen.add(key)
                matches.append(key)
            break
    return matches


def _relation_terms(context: str) -> tuple[str | None, list[str], float]:
    matches: list[str] = []
    category: str | None = None
    strength = 0.0
    for label, regex, weight in (
        ("mna", MNA_RE, 1.6),
        ("governance_settlement", GOVERNANCE_RE, 1.45),
        ("commercial_relation", COMMERCIAL_RE, 1.25),
    ):
        found = sorted({m.group(0).lower() for m in regex.finditer(context)})
        if not found:
            continue
        matches.extend(found)
        if weight > strength:
            category = label
            strength = weight
    if not matches:
        return None, [], 0.0
    if FINANCING_EXCLUDE_RE.search(context) and category not in {"mna", "governance_settlement"}:
        return None, [], 0.0
    unique = sorted(set(matches))
    return category, unique, strength + min(len(unique), 5) * 0.04


def _main_document_text(text: str) -> str:
    scanned = str(text or "")[:MAX_TEXT_CHARS_SCANNED]
    match = SECOND_DOCUMENT_RE.search(scanned, 800)
    if match:
        return scanned[: match.start()]
    return scanned


def _extract_counterparty_rows(raw: dict[str, Any]) -> list[dict[str, Any]]:
    issuer_ticker = str(raw.get("ticker") or "").upper()
    if str(raw.get("form_base") or raw.get("form_type") or "").upper() != "8-K":
        return []
    usable_date = str(raw.get("usable_trade_date") or "")[:10]
    if not issuer_ticker or not usable_date:
        return []
    text = str(raw.get("combined_text") or "")
    if len(text.split()) < MIN_TEXT_WORDS:
        return []
    scanned = _main_document_text(text)
    norm = _normalize_text(scanned)
    alias_to_ticker, max_alias_tokens, _alias_summary = _load_public_company_aliases()

    best_by_ticker: dict[str, dict[str, Any]] = {}
    seen_windows: set[tuple[int, int]] = set()
    relation_spans = sorted(
        {
            (match.start(), match.end())
            for regex in (MNA_RE, GOVERNANCE_RE, COMMERCIAL_RE)
            for match in regex.finditer(norm)
        }
    )[:MAX_RELATION_WINDOWS_PER_FILING]
    if not relation_spans:
        return []
    for relation_start, relation_end in relation_spans:
        left = max(0, relation_start - MATCH_CONTEXT_CHARS)
        right = min(len(norm), relation_end + MATCH_CONTEXT_CHARS)
        window_key = (left, right)
        if window_key in seen_windows:
            continue
        seen_windows.add(window_key)
        context = norm[left:right]
        category, terms, strength = _relation_terms(context)
        if category is None:
            continue
        for alias, target_ticker in _context_alias_matches(context, alias_to_ticker, max_alias_tokens):
            if target_ticker == issuer_ticker:
                continue
            existing = best_by_ticker.get(target_ticker)
            row = {
                "ticker": target_ticker,
                "date": usable_date,
                "issuer_ticker": issuer_ticker,
                "filing_date": str(raw.get("filing_date") or "")[:10],
                "accepted_at": str(raw.get("accepted_at") or "")[:19],
                "accession_number": str(raw.get("accession_number") or ""),
                "form_type": raw.get("form_type"),
                "eight_k_item_codes": raw.get("eight_k_item_codes") or [],
                "primary_document": raw.get("primary_document"),
                "text_char_count": raw.get("text_char_count"),
                "text_word_count": raw.get("text_word_count"),
                "pit_source": raw.get("pit_source"),
                "pit_caveat": raw.get("pit_caveat"),
                "target_company_alias": alias,
                "relation_category": category,
                "relation_terms": terms,
                "relation_strength": _round(strength, 6),
                "context_excerpt_normalized": context[:360],
            }
            if existing is None or float(row["relation_strength"] or 0.0) > float(
                existing.get("relation_strength") or 0.0
            ):
                best_by_ticker[target_ticker] = row
    return list(best_by_ticker.values())


def _load_sec_text_rows(*, max_filed: str, tickers: list[str] | None = None, **_: Any) -> list[dict[str, Any]]:
    del tickers
    global _TEXT_RELATION_CACHE
    if _TEXT_RELATION_CACHE is None:
        rows: list[dict[str, Any]] = []
        scan: Counter[str] = Counter()
        seen: set[tuple[str, str]] = set()
        for path in sorted(TEXT_DIR.glob("sec_filing_text_*.jsonl")):
            with path.open(encoding="utf-8", errors="ignore") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    try:
                        raw = json.loads(line)
                    except json.JSONDecodeError:
                        scan["json_decode_errors"] += 1
                        continue
                    scan["raw_text_rows"] += 1
                    if str(raw.get("form_base") or raw.get("form_type") or "").upper() != "8-K":
                        scan["non_8k_rows"] += 1
                        continue
                    extracted = _extract_counterparty_rows(raw)
                    if not extracted:
                        scan["8k_rows_without_public_relation_target"] += 1
                        continue
                    for row in extracted:
                        key = (str(row.get("accession_number") or ""), str(row.get("ticker") or ""))
                        if key in seen:
                            scan["duplicate_accession_target"] += 1
                            continue
                        seen.add(key)
                        rows.append(row)
                        scan[f"category_{row['relation_category']}"] += 1
        rows.sort(
            key=lambda row: (
                row["date"],
                row["ticker"],
                row.get("issuer_ticker") or "",
                -(float(row.get("relation_strength") or 0.0)),
            )
        )
        _TEXT_RELATION_CACHE = (rows, dict(scan))
    rows, _scan = _TEXT_RELATION_CACHE
    return [row for row in rows if str(row.get("date") or "")[:10] <= max_filed]


def _build_quality_index(
    text_rows: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    stats: Counter[str] = Counter()
    for row in text_rows:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            stats["missing_target_ticker"] += 1
            continue
        by_ticker[ticker].append(row)
        stats[f"category_{row.get('relation_category') or 'unknown'}"] += 1
    for rows in by_ticker.values():
        rows.sort(
            key=lambda row: (
                row["date"],
                -(float(row.get("relation_strength") or 0.0)),
                row.get("issuer_ticker") or "",
                row.get("accession_number") or "",
            )
        )
    _alias_to_ticker, _max_alias_tokens, alias_summary = _load_public_company_aliases()
    _all_rows, raw_scan = _TEXT_RELATION_CACHE or ([], {})
    return dict(by_ticker), {
        "sec_text_rows_loaded": len(text_rows),
        "tickers_with_public_counterparty_relations": len(by_ticker),
        "unique_issuer_target_pairs": len(
            {(row.get("issuer_ticker"), row.get("ticker")) for row in text_rows}
        ),
        "text_source": _repo_rel(TEXT_DIR),
        "min_text_words": MIN_TEXT_WORDS,
        "max_text_chars_scanned": MAX_TEXT_CHARS_SCANNED,
        "max_relation_windows_per_filing": MAX_RELATION_WINDOWS_PER_FILING,
        "alias_summary": alias_summary,
        "raw_text_scan": raw_scan,
        **dict(stats),
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indices = {
        ticker: base.framework.shadow._row_index(base.framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    scan: Counter[str] = Counter()
    candidates: list[dict[str, Any]] = []
    for ticker in sorted(set(quality_index) & set(snapshot)):
        for event in quality_index[ticker]:
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
            relation_strength = float(event.get("relation_strength") or 0.0)
            score = (
                relation_strength
                + 0.50 * float(confirm["candidate_ret20_excess_spy"])
                + 0.15 * float(confirm["candidate_ret60_excess_spy"])
                + 0.12 * float(confirm["candidate_close_location"])
                + 0.025
                * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
            )
            scan["qualified_candidate_rows"] += 1
            scan[f"qualified_{event.get('relation_category') or 'unknown'}"] += 1
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "ISSUER_8K_PUBLIC_COUNTERPARTY_RELATION_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "issuer_8k_usable_trade_date_and_target_signal_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_filing_text": True,
                    "uses_free_sec_company_tickers": True,
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
            -float(row.get("text_relation_strength") or 0.0),
            -float(row["candidate_ret20_excess_spy"] or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(rows)
    scan["candidate_signal_days"] = len({row["date"] for row in rows})
    scan["candidate_tickers"] = len({row["ticker"] for row in rows})
    scan["eligible_quality_tickers"] = len(quality_index)
    return rows, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "min_text_words": MIN_TEXT_WORDS,
        "max_text_chars_scanned": MAX_TEXT_CHARS_SCANNED,
        "match_context_chars": MATCH_CONTEXT_CHARS,
        "max_relation_windows_per_filing": MAX_RELATION_WINDOWS_PER_FILING,
        "candidate_universe": "broad_liquid_warehouse_all_windows_full_liquid",
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
        "positive_replay_lead_not_promoted_issuer_8k_public_counterparty_relation"
        if gate["passed"]
        else "rejected_issuer_8k_public_counterparty_relation_candidate_pool"
    )
    return gate


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Relation Events | Trades |",
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
            f"# {EXPERIMENT_ID} Issuer 8-K Public Counterparty Relation",
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
    template.EXPERIMENT_ID = EXPERIMENT_ID
    template.STEM = STEM
    template.TRIAL_FAMILY = TRIAL_FAMILY
    template.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    template.CHANGED_VARIABLE = CHANGED_VARIABLE
    template.RULE_VERSION = RULE_VERSION
    template.OWNER = OWNER
    template.OUT_DIR = OUT_DIR
    template.OUT_JSON = OUT_JSON
    template.LOG_JSON = LOG_JSON
    template.TICKET_JSON = TICKET_JSON
    template.CARD_MD = CARD_MD
    template.MANIFEST_JSON = MANIFEST_JSON
    template.EXPERIMENT_LOG = EXPERIMENT_LOG
    template.REGISTRY_JSON = REGISTRY_JSON
    template.PREDICTION = PREDICTION
    template.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    template.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    template._load_sec_text_rows = _load_sec_text_rows
    template._build_quality_index = _build_quality_index
    template._candidate_rows_for_window = _candidate_rows_for_window
    template._gate4 = _gate4
    template._build_card = _build_card
    template._configure_base()
    base._load_window_snapshot = broad_static._broad_load_window_snapshot


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    total_relation_events = sum(
        int(scan.get("event_rows_in_window") or 0)
        for scan in payload["context_scan_by_window"].values()
    )
    total_trades = int(payload["target_trade_summary"]["total_trade_count"] or 0)
    if gate4["passed"]:
        interpretation = (
            "Issuer 8-K public-counterparty relation cleared the numeric "
            "three-window replay screen on the broad liquid universe, but "
            "remains only a replay lead because no shared daily/backtest parser "
            "was promoted."
        )
    elif total_trades == 0:
        interpretation = (
            "Issuer 8-K public-counterparty relation did not clear Gate 4 "
            f"(failed: {', '.join(gate4['failed_reasons']) or 'none'}). The "
            f"parser found {total_relation_events} in-window public-relation "
            "events, but none survived target-side liquidity/price confirmation "
            "and next-open/10d execution. The deterministic public-name axis is "
            "too sparse after tradability guards, so it is not retained."
        )
    else:
        interpretation = (
            "Issuer 8-K public-counterparty relation did not clear Gate 4 "
            f"(failed: {', '.join(gate4['failed_reasons']) or 'none'}). The "
            f"source produced {total_trades} paper trades from "
            f"{total_relation_events} in-window relation events, but the "
            "named-company relation did not beat the canonical three-window "
            "EV/PnL/risk/comparator screen."
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
            "mechanism_family": "production_visible_free_sec_text_public_counterparty_relation_candidate_pool",
            "new_evidence_type": "issuer_8k_public_company_relation_provenance_tuple",
            "nearby_prior_experiments": [
                "exp-20260617-011",
                "exp-20260618-015",
                "exp-20260619-013",
                "exp-20260618-019",
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
        "candidate_universe": "broad_liquid_warehouse_all_windows_full_liquid",
        "min_text_words": MIN_TEXT_WORDS,
        "max_text_chars_scanned": MAX_TEXT_CHARS_SCANNED,
        "match_context_chars": MATCH_CONTEXT_CHARS,
        "max_relation_windows_per_filing": MAX_RELATION_WINDOWS_PER_FILING,
        "min_price": base.MIN_PRICE,
        "min_avg_dollar_volume_20d": base.MIN_AVG_DOLLAR_VOLUME_20D,
        "min_ret20_excess_spy": base.MIN_RET20_EXCESS_SPY,
        "min_ret60_excess_spy": base.MIN_RET60_EXCESS_SPY,
        "min_signal_return": base.MIN_SIGNAL_RETURN,
        "max_signal_return": base.MAX_SIGNAL_RETURN,
        "min_close_location": base.MIN_CLOSE_LOCATION,
        "max_realized_vol_20d": base.MAX_REALIZED_VOL_20D,
        "mna_terms": MNA_RE.pattern,
        "governance_terms": GOVERNANCE_RE.pattern,
        "commercial_terms": COMMERCIAL_RE.pattern,
        "financing_exclude_terms": FINANCING_EXCLUDE_RE.pattern,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["companyfacts_source"] = None
    payload["backtest_protocol"]["sec_filing_text_source"] = _repo_rel(TEXT_DIR)
    payload["backtest_protocol"]["sec_company_tickers_source"] = _repo_rel(SEC_TICKERS_JSON)
    payload["backtest_protocol"]["candidate_ohlcv_source"] = _repo_rel(base.framework.WAREHOUSE)
    payload["backtest_protocol"]["execution_model"] = (
        "Issuer 8-K SEC filing text is keyed by accepted_at and usable_trade_date. "
        "The parser builds a broad-liquid SEC ticker-title alias map, skips the "
        "filing issuer, requires a named public company inside local M&A, "
        "governance settlement, cooperation, partnership, customer, supplier, "
        "license, distribution, or acquisition context, and excludes financing-"
        "only contexts. The candidate is the named public target/counterparty. "
        "Price confirmation uses only target ticker signal-date OHLCV. Paper "
        "entry is the next available open with existing entry slippage; exit is "
        "the close 10 trading days after the signal with target-side sell "
        "slippage and ROUND_TRIP_COST_PCT. The core baseline remains the "
        "canonical core replay; only the default-off paper candidate snapshot "
        "uses the broad liquid universe."
    )
    payload["gate2"]["runtime_fields"] = [
        "SEC filing text combined_text",
        "SEC filing accepted_at and usable_trade_date",
        "SEC filing accession_number",
        "SEC ticker-title reference alias map",
        "extracted issuer_ticker, target_ticker, relation_category, relation_terms",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume for target ticker",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A retry needs materially stronger relation identity evidence, such as "
        "CIK-level counterparty extraction from exhibits, a customer/supplier "
        "graph, deal target/holder role labels, or closed forward replacement "
        "rows. Do not sweep public-name alias lists, relation phrase lists, "
        "item codes, RS/close/volume guards, top-N, hold, cooldown, or notional "
        "on these frozen windows."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": interpretation,
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; "
            "max drawdown drift {:+.4f}; {} paper trades.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
                float(aggregate["max_drawdown_delta_max"] or 0.0),
                total_trades,
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping public-company alias length, relation "
            "phrase lists, item codes, RS/close/volume/vol guards, top-N, hold "
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
