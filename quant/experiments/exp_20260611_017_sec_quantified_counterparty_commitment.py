"""exp-20260611-017: SEC quantified counterparty commitment candidate pool.

Replay-only alpha search. This tests one fixed candidate-source variable:
SEC 8-K / EX-99 text that contains a named customer, counterparty, partner, or
supplier plus a quantified value, term, or capacity commitment, paired with the
existing same-day liquid leadership envelope.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import exp_20260610_023_sec_contract_demand_text_leadership as previous


framework = previous.framework
base = previous.base

EXPERIMENT_ID = "exp-20260611-017"
STEM = "sec_quantified_counterparty_commitment"
TRIAL_FAMILY = "sec_quantified_counterparty_commitment_candidate_pool"
TRIAL_VARIANT_ID = "sec_quantified_counterparty_commitment_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_quantified_counterparty_commitment_text_absorption_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = previous.REPO_ROOT
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260611_017_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

SEC_TEXT_PATH = previous.SEC_TEXT_PATH

BASE_NOTIONAL_USD = previous.BASE_NOTIONAL_USD
HOLD_DAYS = previous.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = previous.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = previous.SAME_TICKER_COOLDOWN_DAYS

BUSINESS_UPDATE_EVENT_SUBTYPES = ("1.01", "7.01", "8.01")
ITEM_CODE_WEIGHTS = {"1.01": 1.25, "8.01": 1.00, "7.01": 0.95}
MIN_SEMANTIC_SCORE = 3.0

QUANTIFIED_COMMITMENT_PATTERNS: tuple[str, ...] = (
    r"\$\s?\d+(?:\.\d+)?\s?(?:billion|bn|million|m)\b",
    r"\b\d+(?:\.\d+)?\s?(?:billion|million)\s+dollars\b",
    r"\b\d+(?:\.\d+)?\s?(?:mw|megawatts?|gw|gigawatts?)\b",
    r"\b\d+\s?(?:year|years|yr|yrs)\b",
    r"\bmulti[- ]year\b",
)
COMMITMENT_ANCHOR_PATTERNS: tuple[str, ...] = (
    r"\bcontract value\b",
    r"\bestimated contract value\b",
    r"\blease agreement\b",
    r"\blong[- ]term (?:lease|agreement|contract|customer agreement)\b",
    r"\bcustomer agreements?\b",
    r"\bsupply agreement\b",
    r"\bservices agreement\b",
    r"\bmaster services agreement\b",
    r"\bpower purchase agreement\b",
    r"\bpurchase orders?\b",
    r"\bcontracted (?:to|with|capacity|hpc|critical it load)\b",
    r"\bcapacity\b",
    r"\bdata center\b",
    r"\bhpc\b",
    r"\bhyperscale(?:r|rs|)\b",
    r"\bhosting capacity\b",
)
COUNTERPARTY_PATTERNS: tuple[str, ...] = (
    r"\b(?:with|from|to|by|for|between|partner(?:ing)?(?: again)? with|agreement with|lease with|contracted to|selected by|awarded by)\s+([A-Z][A-Za-z0-9&.,\- ]{2,90}?)(?=,|\.|;|\sto\b|\sfor\b|\sunder\b|\swhich\b|\sthat\b|\swho\b|\s\(|\sInc\.?|\sCorp\.?|\sCorporation|\sLLC|\sLtd\.?|\sLimited|\sCompany|\sCo\.?|\sHoldings|\sGroup|\sTechnologies|\sTechnology|\sSystems|\sServices|\sEnergy|\sPower|\sCloud|\sAI|\sData|\sWeb Services)",
    r"\b(Amazon Web Services|AWS|Google|CoreWeave|Core42|Fluidstack|Cayuga Operating Company|Priority Power|Rhodium|Microsoft|Oracle|OpenAI|NVIDIA)\b",
)
EXCLUSION_PATTERNS: tuple[str, ...] = (
    r"\bshare repurchase\b",
    r"\brepurchase program\b",
    r"\bpublic offering\b",
    r"\bregistered direct\b",
    r"\bprivate placement\b",
    r"\bat[- ]the[- ]market\b",
    r"\batm offering\b",
    r"\bshelf registration\b",
    r"\bresale registration\b",
    r"\bsecurities purchase agreement\b",
    r"\bequity financing\b",
    r"\bconvertible (?:note|notes|debt|preferred)\b",
    r"\bsenior secured notes?\b",
    r"\bsenior notes?\b",
    r"\bcredit agreement\b",
    r"\bdebt offering\b",
    r"\bwarrants?\b",
    r"\bdilution\b",
    r"\bgoing concern\b",
    r"\bbankruptcy\b",
    r"\btermination\b",
    r"\bterminated\b",
    r"\bmerger agreement\b",
    r"\bemployment agreement\b",
    r"\blitigation\b",
    r"\bsettlement agreement\b",
)

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = previous.MAX_DRAWDOWN_WORSE
MAX_SINGLE_POSITIVE_SHARE = previous.MAX_SINGLE_POSITIVE_SHARE
MAX_POSITIVE_HHI = previous.MAX_POSITIVE_HHI

ACCEPTED_COMPRESSION_COMPARATOR = previous.ACCEPTED_COMPRESSION_COMPARATOR
ACCEPTED_DISTRIBUTION_COMPARATOR = {
    "experiment_id": "exp-20260611-007",
    "decision": "accepted_paper_pending_forward_distribution_day_absorption_leadership_shared_adapter",
    "expected_value_score_delta_sum": 0.5286,
    "total_pnl_delta_sum": 10432.91,
    "target_trade_count": 113,
}
BASE_GATE4 = previous.BASE_GATE4
BASE_BUILD_PAYLOAD = previous.BASE_BUILD_PAYLOAD

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": 0.25,
    "expected_pnl_delta": 3000.0,
    "main_failure_modes": [
        "thin_sample",
        "boilerplate_counterparty_context",
        "already_priced_event",
        "accepted_distribution_comparator_not_beaten",
        "old_thin_regression",
    ],
    "confidence_reason": (
        "Prior generic SEC contract-demand text failed with only two noisy DE "
        "trades. This run is materially narrower evidence requested by that "
        "failure: named counterparty/customer plus quantified value, term, or "
        "capacity. Success odds remain low because the field is sparse and "
        "still only replay-only unless promoted through a shared adapter."
    ),
    "recorded_at": "2026-06-11T14:07:12+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "uses_llm": False,
    "uses_free_sec_filing_text": True,
    "uses_free_ohlcv": True,
    "parity_note": (
        "This experiment changes no production code. A positive result would "
        "remain only a replay lead. Promotion would require one shared "
        "default-off adapter that loads the same PIT SEC filing text, applies "
        "the exact same named-counterparty and quantified-commitment semantic "
        "gate, uses the same signal-date OHLCV leadership envelope, overlap "
        "exclusion, next-open paper entry, 10-trading-day exit, costs, "
        "cooldown, comparator, and concentration guards in both historical "
        "replay and daily production before any report queue, paper ledger, "
        "candidate priority, sizing, watchlist, or order surface could change."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: SEC 8-K / EX-99 filing text with named customer, "
        "counterparty, partner, or supplier language plus quantified value, "
        "duration, or capacity commitment may identify stronger delayed "
        "absorption candidates than the rejected generic SEC contract-demand "
        "text bucket when same-day liquid leadership confirms the event."
    ),
    "2_history_check": {
        "exp-20260610-023": (
            "Rejected generic SEC contract-demand text leadership; only two "
            "DE trades, both negative. It explicitly required named relation, "
            "contract value, duration, or richer PIT semantic evidence before "
            "any retry."
        ),
        "exp-20260603-012": (
            "Rejected SEC customer-contract / demand-backlog source. This run "
            "does not sweep synonyms; it requires a counterparty and a numeric "
            "commitment in the same local text context."
        ),
        "exp-20260610-013": (
            "Rejected broad 8-K business-update labels; item-code labels alone "
            "were not enough."
        ),
        "exp-20260611-012": (
            "Rejected SEC periodic report absorption leadership. Broad SEC "
            "periodic text is not the mechanism here."
        ),
        "exp-20260611-013": (
            "Rejected delayed SEC filing confirmation; this run tests semantic "
            "strength, not delayed-price confirmation."
        ),
        "exp-20260611-007": (
            "Accepted distribution-day absorption shared adapter. A positive "
            "SEC text scout must beat this comparator before promotion pressure."
        ),
    },
    "3_single_causal_variable": (
        "One fixed policy bundle: PIT SEC filing text local context must have "
        "a quantified value/term/capacity token, a commitment anchor, and a "
        "named customer/counterparty/partner/supplier cue, with offering, debt, "
        "repurchase, litigation, bankruptcy, employment, termination, and "
        "merger exclusions. The OHLCV leadership envelope, top-1 next-open "
        "paper entry, 10-day hold, costs, cooldown, core-overlap exclusion, "
        "and concentration gates are inherited unchanged."
    ),
    "4_acceptance_standard": (
        "Use docs/backtesting.md three canonical windows. Treat as a positive "
        "replay lead only if aggregate EV/PnL improve, no EV/PnL regression "
        "window appears, target sample >=20 across all 3 windows, survival "
        ">=5%, drawdown drift <=0.5pp, concentration guard passes, and the "
        "accepted exp-20260611-007 distribution comparator is beaten. A shared "
        "default-off helper and daily parity path are required for retention."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260611_017_sec_quantified_counterparty_commitment.py"
    ),
}

_TEXT_EVENT_CACHE: dict[str, Any] | None = None


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _item_codes(row: dict[str, Any]) -> set[str]:
    raw = row.get("eight_k_item_codes")
    if isinstance(raw, list):
        return {str(item).strip() for item in raw if str(item).strip()}
    if raw:
        return {
            part.strip()
            for part in str(raw).replace(";", ",").split(",")
            if part.strip()
        }
    return set()


def _pattern_matches(text: str, patterns: tuple[str, ...]) -> list[re.Match[str]]:
    matches: list[re.Match[str]] = []
    for pattern in patterns:
        matches.extend(re.finditer(pattern, text, flags=re.IGNORECASE | re.DOTALL))
    return matches


def _compact_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _local_context(text: str, match: re.Match[str], *, radius: int = 340) -> str:
    start = max(match.start() - radius, 0)
    end = min(match.end() + radius, len(text))
    return text[start:end].strip()


def _clean_counterparty_name(raw: str) -> str:
    value = _compact_text(raw)
    value = re.sub(r"^(?:the|a|an)\s+", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+(?:and|or|to|for|under|which|that)$", "", value)
    return value.strip(" ,.;:()[]")


def _counterparties(context: str) -> list[str]:
    names: list[str] = []
    for pattern in COUNTERPARTY_PATTERNS:
        for match in re.finditer(pattern, context):
            captured = match.group(1) if match.lastindex else match.group(0)
            name = _clean_counterparty_name(captured)
            if not name:
                continue
            if name.lower() in {"company", "customer", "customers", "partner"}:
                continue
            if name not in names:
                names.append(name)
    return names[:6]


def _quantified_commitment_contexts(text: str) -> list[dict[str, Any]]:
    compact = _compact_text(text)
    contexts: list[dict[str, Any]] = []
    for pattern in QUANTIFIED_COMMITMENT_PATTERNS:
        for match in re.finditer(pattern, compact, flags=re.IGNORECASE):
            context = _local_context(compact, match)
            anchor_matches = _pattern_matches(context, COMMITMENT_ANCHOR_PATTERNS)
            if not anchor_matches:
                continue
            exclusion_matches = _pattern_matches(context, EXCLUSION_PATTERNS)
            if exclusion_matches:
                continue
            counterparties = _counterparties(context)
            if not counterparties:
                continue
            contexts.append(
                {
                    "quantified_term": match.group(0),
                    "counterparties": counterparties,
                    "anchors": sorted({m.group(0).lower() for m in anchor_matches})[:8],
                    "snippet": context[:700],
                }
            )
    return contexts


def _semantic_event_from_row(row: dict[str, Any]) -> dict[str, Any] | None:
    ticker = str(row.get("ticker") or "").upper().strip()
    usable_date = str(row.get("usable_trade_date") or row.get("filing_date") or "")[:10]
    if not ticker or not usable_date:
        return None
    if str(row.get("status") or "ok").lower() not in {"ok", ""}:
        return None
    form_type = str(row.get("form_type") or row.get("form_base") or "").upper()
    if "8-K" not in form_type:
        return None
    item_codes = _item_codes(row)
    if not item_codes.intersection(BUSINESS_UPDATE_EVENT_SUBTYPES):
        return None
    text = str(row.get("combined_text") or "")
    if not text:
        return None
    contexts = _quantified_commitment_contexts(text)
    if not contexts:
        return None
    unique_terms = {context["quantified_term"].lower() for context in contexts}
    unique_counterparties = {
        name for context in contexts for name in context["counterparties"]
    }
    unique_anchors = {anchor for context in contexts for anchor in context["anchors"]}
    semantic_score = 1.5 + len(unique_terms) * 0.55 + len(unique_counterparties) * 0.65
    semantic_score += len(unique_anchors) * 0.20
    semantic_score += max(ITEM_CODE_WEIGHTS.get(code, 0.0) for code in item_codes)
    if "1.01" in item_codes:
        semantic_score += 0.30
    if semantic_score < MIN_SEMANTIC_SCORE:
        return None
    source_hash = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]
    return {
        "ticker": ticker,
        "usable_trade_date": usable_date,
        "filing_date": str(row.get("filing_date") or "")[:10],
        "accepted_at": row.get("accepted_at"),
        "accession_number": row.get("accession_number"),
        "primary_document": row.get("primary_document"),
        "form_type": form_type,
        "item_codes": sorted(item_codes),
        "semantic_score": round(semantic_score, 6),
        "quantified_terms": sorted(unique_terms)[:12],
        "counterparties": sorted(unique_counterparties)[:12],
        "commitment_anchors": sorted(unique_anchors)[:12],
        "context_count": len(contexts),
        "evidence_snippets": [context["snippet"] for context in contexts[:3]],
        "text_word_count": row.get("text_word_count"),
        "text_char_count": row.get("text_char_count"),
        "source_text_hash": source_hash,
        "pit_source": row.get("pit_source"),
        "pit_caveat": row.get("pit_caveat"),
    }


def _load_text_events() -> dict[str, Any]:
    global _TEXT_EVENT_CACHE
    if _TEXT_EVENT_CACHE is not None:
        return _TEXT_EVENT_CACHE

    by_date_ticker: dict[str, dict[str, list[dict[str, Any]]]] = {}
    scan = Counter()
    examples: list[dict[str, Any]] = []
    if not SEC_TEXT_PATH.exists():
        _TEXT_EVENT_CACHE = {
            "by_date_ticker": by_date_ticker,
            "scan": {"text_file_missing": True, "path": _repo_rel(SEC_TEXT_PATH)},
            "examples": examples,
        }
        return _TEXT_EVENT_CACHE

    with SEC_TEXT_PATH.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            if not line.strip():
                continue
            scan["text_rows_loaded"] += 1
            row = json.loads(line)
            if "8-K" in str(row.get("form_type") or row.get("form_base") or "").upper():
                scan["eight_k_rows"] += 1
            item_codes = _item_codes(row)
            if item_codes.intersection(BUSINESS_UPDATE_EVENT_SUBTYPES):
                scan["item_code_passed_rows"] += 1
            event = _semantic_event_from_row(row)
            if event is None:
                continue
            scan["semantic_passed_rows"] += 1
            by_date_ticker.setdefault(event["usable_trade_date"], {}).setdefault(
                event["ticker"], []
            ).append(event)
            if len(examples) < 12:
                examples.append(
                    {
                        "date": event["usable_trade_date"],
                        "ticker": event["ticker"],
                        "semantic_score": event["semantic_score"],
                        "item_codes": event["item_codes"],
                        "quantified_terms": event["quantified_terms"][:5],
                        "counterparties": event["counterparties"][:5],
                        "accession_number": event["accession_number"],
                    }
                )

    _TEXT_EVENT_CACHE = {
        "by_date_ticker": by_date_ticker,
        "scan": {**dict(scan), "source_text_file": _repo_rel(SEC_TEXT_PATH)},
        "examples": examples,
    }
    return _TEXT_EVENT_CACHE


def _text_events_for_date(signal_date: str) -> dict[str, list[dict[str, Any]]]:
    return _load_text_events()["by_date_ticker"].get(signal_date, {})


def _candidate_for_quantified_commitment_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    events: list[dict[str, Any]],
) -> dict[str, Any] | None:
    row = base._candidate_for_ticker(
        snapshot=snapshot,
        indices=indices,
        sector_entries=sector_entries,
        ticker=ticker,
        signal_date=signal_date,
        month_label="sec_quantified_counterparty_commitment",
    )
    if row is None:
        return None

    top_event = sorted(
        events,
        key=lambda event: (
            -float(event.get("semantic_score") or 0.0),
            -int(event.get("context_count") or 0),
            str(event.get("accession_number") or ""),
        ),
    )[0]
    row["source"] = "SEC_QUANTIFIED_COUNTERPARTY_COMMITMENT_PAPER"
    row.pop("candidate_month_label", None)
    row["candidate_commitment_text_score"] = top_event["semantic_score"]
    row["candidate_commitment_text_event_count"] = len(events)
    row["candidate_commitment_text_quantified_terms"] = top_event["quantified_terms"]
    row["candidate_commitment_text_counterparties"] = top_event["counterparties"]
    row["candidate_commitment_text_anchors"] = top_event["commitment_anchors"]
    row["candidate_commitment_text_item_codes"] = top_event["item_codes"]
    row["candidate_commitment_text_accession"] = top_event["accession_number"]
    row["candidate_commitment_text_primary_document"] = top_event["primary_document"]
    row["candidate_commitment_text_evidence_snippets"] = top_event[
        "evidence_snippets"
    ][:3]
    row["candidate_commitment_text_source_hash"] = top_event["source_text_hash"]
    row["candidate_commitment_text_pit_source"] = top_event["pit_source"]
    row["uses_free_ohlcv_only"] = False
    row["uses_free_sec_filing_text"] = True
    row["known_at"] = (
        "signal_date_sec_quantified_counterparty_text_and_ohlcv_before_next_open"
    )
    row["rule_version"] = RULE_VERSION
    return row


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = framework.shadow._baseline_entries(before_result)
    indices = {
        ticker: framework.shadow._row_index(framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    all_dates = framework.shadow._trading_dates(snapshot)
    dates = [
        date_value
        for date_value in all_dates
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]
    candidates: list[dict[str, Any]] = []
    day_contexts: list[dict[str, Any]] = []
    quant_distribution: Counter[str] = Counter()
    counterparty_distribution: Counter[str] = Counter()
    anchor_distribution: Counter[str] = Counter()
    item_distribution: Counter[str] = Counter()
    scan = {
        "scanned_trading_days": len(dates),
        "days_with_commitment_text_tickers": 0,
        "commitment_text_tickers": 0,
        "days_with_raw_commitment_text_candidates": 0,
        "raw_commitment_text_candidates": 0,
        "same_ticker_core_overlap_rejections": 0,
        "source_text_scan": _load_text_events()["scan"],
        "source_text_examples": _load_text_events()["examples"][:12],
    }

    for signal_date in dates:
        events_by_ticker = _text_events_for_date(signal_date)
        if not events_by_ticker:
            continue
        scan["days_with_commitment_text_tickers"] += 1
        scan["commitment_text_tickers"] += len(events_by_ticker)

        ab_entries = entries_by_date.get(signal_date, [])
        ab_tickers = {trade.get("ticker") for trade in ab_entries}
        day_rows: list[dict[str, Any]] = []
        for ticker, events in sorted(events_by_ticker.items()):
            if ticker not in sector_entries:
                continue
            if ticker in ab_tickers:
                scan["same_ticker_core_overlap_rejections"] += 1
                continue
            row = _candidate_for_quantified_commitment_ticker(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
                events=events,
            )
            if row is None:
                continue
            for term in row["candidate_commitment_text_quantified_terms"]:
                quant_distribution[term] += 1
            for counterparty in row["candidate_commitment_text_counterparties"]:
                counterparty_distribution[counterparty] += 1
            for anchor in row["candidate_commitment_text_anchors"]:
                anchor_distribution[anchor] += 1
            for item_code in row["candidate_commitment_text_item_codes"]:
                item_distribution[item_code] += 1
            row["same_day_ab_entry_count"] = len(ab_entries)
            row["same_day_ab_overlap"] = bool(ab_entries)
            row["same_ticker_ab_overlap"] = False
            day_rows.append(row)
        if not day_rows:
            continue
        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_commitment_text_score"]),
                -float(row["candidate_score"]),
                -float(row["candidate_ret20_excess_spy"]),
                -float(row["candidate_close_location"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                str(row.get("sector") or ""),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        scan["days_with_raw_commitment_text_candidates"] += 1
        scan["raw_commitment_text_candidates"] += len(day_rows)
        top = day_rows[0]
        day_contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(day_rows),
                "top_candidate": top["ticker"],
                "top_candidate_score": top["candidate_score"],
                "top_candidate_commitment_text_score": top[
                    "candidate_commitment_text_score"
                ],
                "top_candidate_counterparties": top[
                    "candidate_commitment_text_counterparties"
                ][:5],
                "top_candidate_quantified_terms": top[
                    "candidate_commitment_text_quantified_terms"
                ][:5],
                "top_candidate_ret20_excess_spy": top["candidate_ret20_excess_spy"],
                "top_candidate_close_location": top["candidate_close_location"],
            }
        )
    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_commitment_text_score"]),
            -float(row["candidate_score"]),
            -float(row["candidate_ret20_excess_spy"]),
            -float(row["candidate_close_location"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            str(row.get("sector") or ""),
            row["ticker"],
        )
    )
    scan.update(
        {
            "rule_version": RULE_VERSION,
            "quantified_commitment_pattern_count": len(QUANTIFIED_COMMITMENT_PATTERNS),
            "commitment_anchor_pattern_count": len(COMMITMENT_ANCHOR_PATTERNS),
            "counterparty_pattern_count": len(COUNTERPARTY_PATTERNS),
            "exclusion_pattern_count": len(EXCLUSION_PATTERNS),
            "business_update_event_subtypes": list(BUSINESS_UPDATE_EVENT_SUBTYPES),
            "item_code_weights": ITEM_CODE_WEIGHTS,
            "quantified_term_distribution": dict(sorted(quant_distribution.items())),
            "counterparty_distribution": dict(sorted(counterparty_distribution.items())),
            "anchor_distribution": dict(sorted(anchor_distribution.items())),
            "item_distribution": dict(sorted(item_distribution.items())),
            "min_semantic_score": MIN_SEMANTIC_SCORE,
            "min_price": base.MIN_PRICE,
            "min_avg_dollar_volume_20d": base.MIN_AVG_DOLLAR_VOLUME_20D,
            "min_ret20_excess_spy": base.MIN_RET20_EXCESS_SPY,
            "min_ret60_excess_spy": base.MIN_RET60_EXCESS_SPY,
            "min_signal_return": base.MIN_SIGNAL_RETURN,
            "min_close_location": base.MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": base.MIN_VOLUME_RATIO_20D,
            "max_volume_ratio_20d": base.MAX_VOLUME_RATIO_20D,
            "min_ret5": base.MIN_RET5,
            "max_ret5": base.MAX_RET5,
            "max_ret20": base.MAX_RET20,
            "max_realized_vol_20d": base.MAX_REALIZED_VOL_20D,
        }
    )
    return candidates, day_contexts, scan


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = BASE_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    if aggregate["expected_value_score_delta_sum"] <= ACCEPTED_COMPRESSION_COMPARATOR[
        "expected_value_score_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_compression_ev_not_beaten")
    if aggregate["total_pnl_delta_sum"] <= ACCEPTED_COMPRESSION_COMPARATOR[
        "total_pnl_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append("accepted_compression_pnl_not_beaten")
    if aggregate["expected_value_score_delta_sum"] <= ACCEPTED_DISTRIBUTION_COMPARATOR[
        "expected_value_score_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append(
            "accepted_distribution_ev_not_beaten"
        )
    if aggregate["total_pnl_delta_sum"] <= ACCEPTED_DISTRIBUTION_COMPARATOR[
        "total_pnl_delta_sum"
    ]:
        gate.setdefault("failed_reasons", []).append(
            "accepted_distribution_pnl_not_beaten"
        )
    gate["accepted_compression_comparator"] = ACCEPTED_COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = ACCEPTED_DISTRIBUTION_COMPARATOR
    gate["passed"] = not gate.get("failed_reasons")
    gate["decision"] = (
        "positive_replay_lead_not_promoted_sec_quantified_counterparty_commitment"
        if gate["passed"]
        else "rejected_sec_quantified_counterparty_commitment_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only PIT SEC filing text usable_trade_date rows plus "
        "close-of-day OHLCV available on the signal date. Paper entry is next "
        "available open with existing entry slippage; exit is the close 10 "
        "trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    passed = bool(payload["gate4"]["passed"])
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "positive_replay_lead_not_promoted" if passed else "rejected",
            "decision": payload["gate4"]["decision"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "default_off_paper_candidate_pool_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_sec_event_ohlcv_candidate_pool",
            "new_evidence_type": (
                "named_counterparty_plus_quantified_value_duration_or_capacity_sec_text"
            ),
            "nearby_prior_experiments": [
                "exp-20260610-023",
                "exp-20260603-012",
                "exp-20260610-013",
                "exp-20260611-012",
                "exp-20260611-013",
                "exp-20260611-007",
            ],
            "prior_trial_count": 6,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
            "accepted_distribution_comparator": ACCEPTED_DISTRIBUTION_COMPARATOR,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that even named "
                "counterparty plus quantified contract/capacity language is "
                "too sparse, too concentrated in already-priced data-center "
                "names, or still captured by existing distribution absorption "
                "signals after next-open execution, costs, cooldown, and "
                "overlap controls. Do not answer by sweeping synonyms, item "
                "codes, price thresholds, top-N, hold days, cooldown, or "
                "notional on these frozen windows."
            ),
            "next_evidence_needed": (
                "A retry needs materially new PIT evidence outside this text "
                "field, such as a broader free data edge in customer/supplier "
                "relations, source-utility labels, or forward daily parity "
                "observations showing this semantic bucket displaces accepted "
                "distribution or allocator candidates."
            ),
        }
    )
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "sec_text_path": _repo_rel(SEC_TEXT_PATH),
        "business_update_event_subtypes": list(BUSINESS_UPDATE_EVENT_SUBTYPES),
        "item_code_weights": ITEM_CODE_WEIGHTS,
        "quantified_commitment_patterns": list(QUANTIFIED_COMMITMENT_PATTERNS),
        "commitment_anchor_patterns": list(COMMITMENT_ANCHOR_PATTERNS),
        "counterparty_patterns": list(COUNTERPARTY_PATTERNS),
        "exclusion_patterns": list(EXCLUSION_PATTERNS),
        "min_semantic_score": MIN_SEMANTIC_SCORE,
        "min_price": base.MIN_PRICE,
        "min_avg_dollar_volume_20d": base.MIN_AVG_DOLLAR_VOLUME_20D,
        "min_ret20_excess_spy": base.MIN_RET20_EXCESS_SPY,
        "min_ret60_excess_spy": base.MIN_RET60_EXCESS_SPY,
        "min_signal_return": base.MIN_SIGNAL_RETURN,
        "min_close_location": base.MIN_CLOSE_LOCATION,
        "min_volume_ratio_20d": base.MIN_VOLUME_RATIO_20D,
        "max_volume_ratio_20d": base.MAX_VOLUME_RATIO_20D,
        "min_ret5": base.MIN_RET5,
        "max_ret5": base.MAX_RET5,
        "max_ret20": base.MAX_RET20,
        "max_realized_vol_20d": base.MAX_REALIZED_VOL_20D,
        "same_ticker_core_overlap_excluded": True,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["gate_questions"] = PRE_RUN_QUESTIONS
    payload["pre_run_questions"] = PRE_RUN_QUESTIONS
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The fixed quantified counterparty commitment bundle cleared the "
            "canonical three-window gates and beat the accepted distribution "
            "comparator, suggesting named/value SEC text adds replacement "
            "value beyond generic SEC event labels. It remains only a replay "
            "lead because no shared daily adapter or production parity path "
            "was added."
            if passed
            else (
                "The fixed quantified counterparty commitment bundle failed "
                "Gate 4. This means the richer SEC text field was not enough "
                "to create stable replacement value after next-open execution, "
                "costs, 10-day hold, cooldown, core-overlap controls, sample "
                "guards, and accepted distribution comparison."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping SEC text synonyms, counterparty regexes, "
            "8-K item subsets, semantic-score threshold, ret20/ret60 relative "
            "strength thresholds, signal-day return, close-location, volume "
            "bounds, top-N, hold-day, cooldown, or paper notional on the same "
            "frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["interpretation"] = (
        "The SEC quantified counterparty commitment source passed as a replay-only "
        "promotion lead, but no production surface changed and a shared "
        "default-off parity adapter is required before use."
        if passed
        else (
            "The SEC quantified counterparty commitment source was rejected; "
            "the richer free SEC text field did not establish a distinct "
            "candidate-pool edge under the standard three-window protocol."
        )
    )
    payload["rejection_reason"] = (
        None if passed else "; ".join(payload["gate4"]["failed_reasons"])
    )
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} {STEM}",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            f"- Trial family: `{TRIAL_FAMILY}`",
            f"- Changed variable: `{CHANGED_VARIABLE}`",
            f"- Artifact: `{_repo_rel(OUT_JSON)}`",
            f"- Log: `{_repo_rel(LOG_JSON)}`",
            "",
            "## Hypothesis",
            "",
            PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "",
            "## Three-Window Result",
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target trades: `{}`".format(
                payload["target_trade_summary"]["total_trade_count"]
            ),
            "- Accepted distribution comparator EV/PnL: `{}` / `${:,.2f}`".format(
                ACCEPTED_DISTRIBUTION_COMPARATOR["expected_value_score_delta_sum"],
                ACCEPTED_DISTRIBUTION_COMPARATOR["total_pnl_delta_sum"],
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Production Impact",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
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
        "mechanism_family": "production_visible_free_sec_event_ohlcv_candidate_pool",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate[
            "expected_value_score_delta_pct"
        ],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
        "accepted_distribution_comparator": ACCEPTED_DISTRIBUTION_COMPARATOR,
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
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][
                    label
                ]["total_pnl"],
                "commitment_text_day_count": payload["context_scan_by_window"][
                    label
                ].get("days_with_commitment_text_tickers"),
                "raw_candidate_count": payload["context_scan_by_window"][label].get(
                    "raw_commitment_text_candidates"
                ),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": {**payload["calibration"]},
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "negative_reflection": payload["negative_reflection"],
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket_and_registry(
    payload: dict[str, Any],
    log_record: dict[str, Any],
) -> None:
    aggregate = payload["delta_metrics"]["aggregate"]
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
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
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
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
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )


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
            _repo_rel(Path(__file__)): framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def _patch_framework() -> None:
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = RULE_VERSION
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.LOG_JSON = LOG_JSON
    framework.TICKET_JSON = TICKET_JSON
    framework.CARD_MD = CARD_MD
    framework.MANIFEST_JSON = MANIFEST_JSON
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.REGISTRY_JSON = REGISTRY_JSON
    framework.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.HOLD_DAYS = HOLD_DAYS
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    framework.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    framework.PREDICTION = PREDICTION
    framework.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._gate4 = _gate4
    framework._build_payload = _build_payload
    framework._build_card = _build_card
    framework._build_log_record = _build_log_record
    framework._update_ticket_and_registry = _update_ticket_and_registry
    framework._write_manifest = _write_manifest


_patch_framework()


def main() -> None:
    framework.main()


if __name__ == "__main__":
    main()
