"""exp-20260605-006: SEC business-development source-span candidate pool.

Alpha search on one free, production-visible SEC text relation field. The
experiment tests whether 8-K press-release / exhibit source spans containing
business-development language, while excluding offering and dilution language,
form a cleaner default-off event candidate pool.

No production adapter, live order path, ranking, sizing, exits, LLM/news path,
or shared sleeve code is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

import exp_20260603_012_sec_customer_contract_business_win as parent


_PARENT_GATE4_DECISION = parent._gate4_decision

EXP_ID = "exp-20260605-006"
STEM = "sec_business_development_ex99_candidate_pool"
TRIAL_FAMILY = "sec_text_business_development_source_span_candidate_pool"
CHANGED_VARIABLE = "sec_business_development_ex99_non_dilutive_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

OUT_DIR = parent.REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / "exp_20260605_006_sec_business_development_ex99_candidate_pool.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = parent.REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = parent.REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
CARD_MD = parent.REPO_ROOT / "experiments" / "cards" / f"{EXP_ID}.md"
ARTIFACT_MD = parent.REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"

EVENT_NOTIONAL = 4_000.0
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30

SOURCE_SPAN_DOC_PATTERNS: tuple[str, ...] = (
    r"\bex[-_]?99",
    r"\bexhibit[-_ ]?99",
    r"\bex99",
    r"\bex991",
    r"\bpress[-_ ]?release",
    r"\bnews[-_ ]?release",
    r"\binvestor[-_ ]?release",
    r"\bearnings[-_ ]?release",
)

SOURCE_SPAN_NAME_HINTS: tuple[str, ...] = (
    "press",
    "release",
    "investor",
    "news",
    "acquisition",
    "agreement",
    "contract",
    "award",
    "order",
    "customer",
    "partnership",
)

SOURCE_SPAN_SUFFIX_EXCLUDES: tuple[str, ...] = (
    ".css",
    ".js",
    ".json",
    ".xml",
    ".xsd",
    ".xlsx",
    ".zip",
)

BUSINESS_DEVELOPMENT_PATTERNS: tuple[str, ...] = (
    r"\bacquir(?:e|es|ed|ing|or|es?)\b",
    r"\bacquisition\b",
    r"\bstrategic partnership\b",
    r"\bpartnership\b",
    r"\bcollaboration\b",
    r"\bcollaborat(?:e|es|ed|ion|ive)\b",
    r"\bcustomer wins?\b",
    r"\bnew customers?\b",
    r"\bselected by\b",
    r"\bselects\b",
    r"\bagreement with\b",
    r"\bcommercial agreement\b",
    r"\bsupply agreement\b",
    r"\blicense agreement\b",
    r"\bdistribution agreement\b",
    r"\bmaster services agreement\b",
    r"\bcontract award(?:ed)?\b",
    r"\bawarded (?:a |an )?contract\b",
    r"\bpurchase orders?\b",
    r"\border backlog\b",
    r"\bbacklog\b",
    r"\bbookings\b",
    r"\bmulti[- ]year\b",
    r"\bexpands? (?:its |their |our )?(?:agreement|relationship|partnership)\b",
)

DILUTION_EXCLUSION_PATTERNS: tuple[str, ...] = (
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
    r"\bsenior notes?\b",
    r"\bdebt offering\b",
    r"\bwarrants?\b",
    r"\bdilution\b",
    r"\bgoing concern\b",
    r"\bbankruptcy\b",
)

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
    "parity_note": (
        "This experiment changes no production code. A retained result would "
        "need a shared default-off SEC source-span adapter with the same "
        "document-section extraction, business-development pattern set, "
        "dilution exclusions, and backtest/live parity tests before any daily "
        "report, candidate queue, or order surface could change."
    ),
}


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _configure_parent() -> None:
    parent.EXP_ID = EXP_ID
    parent.STEM = STEM
    parent.TRIAL_FAMILY = TRIAL_FAMILY
    parent.CHANGED_VARIABLE = CHANGED_VARIABLE
    parent.RULE_VERSION = RULE_VERSION
    parent.OUT_DIR = OUT_DIR
    parent.OUT_JSON = OUT_JSON
    parent.BEFORE_JSON = BEFORE_JSON
    parent.AFTER_JSON = AFTER_JSON
    parent.LOG_JSON = LOG_JSON
    parent.TICKET_JSON = TICKET_JSON
    parent.CARD_MD = CARD_MD
    parent.ARTIFACT_MD = ARTIFACT_MD
    parent.EVENT_NOTIONAL = EVENT_NOTIONAL
    parent.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    parent.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    parent.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    parent._candidate_from_row = _candidate_from_row
    parent._gate4_decision = _gate4_decision
    parent._write_artifact = _write_artifact


def _pattern_count(text: str, patterns: tuple[str, ...]) -> int:
    return sum(
        len(re.findall(pattern, text, flags=re.IGNORECASE | re.DOTALL))
        for pattern in patterns
    )


def _item_codes(row: dict[str, Any]) -> set[str]:
    raw = row.get("eight_k_item_codes")
    if isinstance(raw, list):
        return {str(item).strip() for item in raw if str(item).strip()}
    if raw:
        return {part.strip() for part in str(raw).replace(";", ",").split(",") if part.strip()}
    return set()


def _doc_names(row: dict[str, Any]) -> list[str]:
    documents = row.get("documents")
    if not isinstance(documents, list):
        return []
    names: list[str] = []
    for doc in documents:
        if isinstance(doc, dict):
            name = str(doc.get("name") or "").strip()
            if name:
                names.append(name)
    return names


def _is_source_span_name(name: str) -> bool:
    lowered = name.lower()
    if "index-headers" in lowered or re.fullmatch(r"r\d+\.htm", lowered):
        return False
    if lowered.endswith(SOURCE_SPAN_SUFFIX_EXCLUDES):
        return False
    if _pattern_count(lowered, SOURCE_SPAN_DOC_PATTERNS) > 0:
        return True
    return any(hint in lowered for hint in SOURCE_SPAN_NAME_HINTS)


def _document_sections(combined_text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    for match in re.finditer(r"(?:^| )DOCUMENT ([^ ]+) ", combined_text):
        start = match.end()
        end_match = re.search(r" DOCUMENT [^ ]+ ", combined_text[start:])
        end = start + end_match.start() if end_match else len(combined_text)
        sections.append((match.group(1), combined_text[start:end].strip()))
    return sections


def _source_span_text(row: dict[str, Any]) -> tuple[str, list[str]]:
    combined = str(row.get("combined_text") or row.get("text") or "")
    if not combined:
        return "", []
    source_names = [
        name
        for name in _doc_names(row)
        if _is_source_span_name(name)
    ]
    if not source_names:
        return "", []

    source_name_keys = {name.lower() for name in source_names}
    sections = [
        text
        for name, text in _document_sections(combined)
        if name.lower() in source_name_keys or _is_source_span_name(name)
    ]
    if not sections:
        sections = [parent.semantic_text(row)]
    return " ".join(section for section in sections if section)[:120000], source_names


def _candidate_from_row(row: dict[str, Any]) -> dict[str, Any] | None:
    usable = str(row.get("usable_trade_date") or "")[:10]
    window = parent._window_name(usable)
    ticker = str(row.get("ticker") or "").upper()
    if not ticker or not usable or window is None:
        return None
    form_type = str(row.get("form_type") or row.get("form_base") or "").upper()
    if "8-K" not in form_type:
        return None

    source_text, source_names = _source_span_text(row)
    if not source_text:
        return None
    lowered = source_text.lower()
    business_dev_hits = _pattern_count(lowered, BUSINESS_DEVELOPMENT_PATTERNS)
    dilution_hits = _pattern_count(lowered, DILUTION_EXCLUSION_PATTERNS)
    if business_dev_hits <= 0:
        return None
    if dilution_hits > 0:
        return None

    features = parent.language_features(row)
    if str(features.get("language_bucket") or "") == parent.NEGATIVE_LANGUAGE_BUCKET:
        return None
    if int(features.get("guidance_cut_hits") or 0) > 0:
        return None

    positive_hits = int(features.get("positive_phrase_hits") or 0)
    negative_hits = int(features.get("negative_phrase_hits") or 0)
    score = (
        business_dev_hits
        + 0.25 * positive_hits
        + 0.50 * int(features.get("guidance_raise_hits") or 0)
        - 0.25 * negative_hits
    )
    return {
        "ticker": ticker,
        "usable_trade_date": usable,
        "filing_date": str(row.get("filing_date") or "")[:10],
        "accepted_at": row.get("accepted_at"),
        "window": window,
        "form_type": form_type,
        "form_base": row.get("form_base"),
        "eight_k_item_codes": sorted(_item_codes(row)),
        "accession_number": row.get("accession_number"),
        "primary_document": row.get("primary_document"),
        "source_span_names": source_names,
        "source_span_count": len(source_names),
        "status": "event_ready",
        "rule_version": RULE_VERSION,
        "strategy": STEM,
        "business_win_hits": business_dev_hits,
        "business_development_hits": business_dev_hits,
        "dilution_exclusion_hits": dilution_hits,
        "candidate_selection_score": round(score, 6),
        "text_event_type": features.get("text_event_type"),
        "language_bucket": features.get("language_bucket"),
        "language_score": features.get("language_score"),
        "positive_phrase_hits": positive_hits,
        "negative_phrase_hits": negative_hits,
        "guidance_raise_hits": features.get("guidance_raise_hits"),
        "guidance_cut_hits": features.get("guidance_cut_hits"),
        "known_at": "after_sec_usable_trade_date_before_next_open_paper_entry",
        "trade_enabled": False,
        "alters_orders": False,
    }


def _gate4_decision(
    aggregate: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    gate4 = _PARENT_GATE4_DECISION(aggregate, results, target_summary)
    passed = bool(gate4["passed"])
    gate4["decision"] = (
        "positive_sec_business_development_source_span_replay_lead_requires_adapter"
        if passed
        else "rejected_sec_business_development_source_span_candidate_pool"
    )
    gate4["status"] = "observed_only" if passed else "rejected"
    gate4["requires_parity_before_promotion"] = passed
    gate4["rationale"] = (
        "The SEC business-development source-span replay passed Gate 4, but "
        "remains replay-only. Retention requires a shared default-off "
        "production/backtest adapter with the same document-section extraction "
        "and dilution exclusions before any production surface can change."
        if passed
        else "One or more Gate 4 checks failed, so the SEC business-development "
        "source-span candidate source is not retained."
    )
    return gate4


def _window_table(results: list[dict[str, Any]]) -> str:
    return parent._window_table(results)


def _write_artifact(payload: dict[str, Any]) -> None:
    comparison = payload["aggregate"]["comparison"]
    lines = [
        f"# {EXP_ID} SEC Business-Development Source-Span Candidate Pool",
        "",
        f"- Trial family: `{TRIAL_FAMILY}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Aggregate EV delta: {float(comparison['expected_value_score_delta']):+.4f}",
        f"- Aggregate PnL delta: ${float(comparison['strategy_total_pnl_delta']):+,.2f}",
        f"- Target trades: {payload['target_summary']['target_trade_count']}",
        f"- Production impact: `{PRODUCTION_IMPACT['adapter_status']}`",
        "",
        "## Gate 1-4",
        "",
        _window_table(payload["results"]),
        "",
        "## Gate 4 Checks",
        "",
    ]
    for key, value in payload["gate4"]["gates"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(
        [
            "",
            "## Decision Rationale",
            "",
            payload["gate4"]["rationale"],
            "",
            "## Production / Backtest Parity",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reproducibility",
            "",
            (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260605_006_sec_business_development_ex99_candidate_pool.py"
            ),
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _patch_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload["experiment_id"] = EXP_ID
    payload["trial_family"] = TRIAL_FAMILY
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["rule_version"] = RULE_VERSION
    payload["preflight"] = {
        "alpha_hypothesis": (
            "PIT SEC 8-K press-release / exhibit source spans with "
            "business-development language and no offering or dilution language "
            "may identify a cleaner default-off candidate pool than generic SEC "
            "positive text."
        ),
        "category": "entry / candidate_pool",
        "playbook_alignment": (
            "Uses a free SEC source-span relation field, matching the playbook "
            "instruction that future SEC text retries need richer relation "
            "mechanisms instead of generic positive-tone variants."
        ),
        "nearby_prior_experiments": {
            "exp-20260604-003": (
                "Generic SEC text-price issuer continuation was rejected; this "
                "run changes the causal variable to business-development "
                "source-span semantics without a price-reaction filter."
            ),
            "exp-20260604-014": (
                "SEC same-sector peer propagation was rejected for one-window "
                "regression; this run keeps direct issuer events only."
            ),
            "exp-20260603-012": (
                "Customer-demand/backlog text failed; this run uses broader "
                "source-span business-development language plus explicit "
                "dilution exclusions."
            ),
        },
        "single_causal_variable": CHANGED_VARIABLE,
        "acceptance_criteria": {
            "canonical_windows": list(parent.WINDOWS.keys()),
            "aggregate_expected_value_delta": "> 0",
            "aggregate_pnl_delta": "> 0",
            "per_window_expected_value_delta": "3 of 3 windows > 0",
            "per_window_pnl_delta": "3 of 3 windows > 0",
            "minimum_target_trades": parent.MIN_TARGET_TRADES,
            "minimum_target_windows": parent.MIN_TARGET_WINDOWS,
            "max_drawdown_drift": parent.MAX_DRAWDOWN_WORSE,
            "survival_rate_floor": 0.05,
            "max_single_positive_share": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi_max": MAX_POSITIVE_HHI,
            "promotion_parity": (
                "Positive replay cannot be promoted until implemented through "
                "a shared default-off production/backtest helper."
            ),
        },
        "reproducibility": (
            "The runner persists canonical before/after metrics, selected SEC "
            "source-span candidates, Gate 4 checks, ticket, card, artifact, and "
            "experiment_log.jsonl record."
        ),
    }
    payload["parameters"] = {
        "sec_text_path": parent._repo_rel(parent.SEC_TEXT_PATH),
        "source_span_doc_patterns": SOURCE_SPAN_DOC_PATTERNS,
        "source_span_name_hints": SOURCE_SPAN_NAME_HINTS,
        "business_development_patterns": BUSINESS_DEVELOPMENT_PATTERNS,
        "dilution_exclusion_patterns": DILUTION_EXCLUSION_PATTERNS,
        "excluded_language_bucket": parent.NEGATIVE_LANGUAGE_BUCKET,
        "event_notional": EVENT_NOTIONAL,
        "hold_days": parent.HOLD_DAYS,
        "max_paper_trades_per_day": parent.MAX_PAPER_TRADES_PER_DAY,
        "selection_order": (
            "entry_date asc, candidate_selection_score desc, "
            "business_win_hits desc, ticker asc"
        ),
    }
    payload["prediction"] = {
        "success_probability": 0.27,
        "expected_ev_delta": None,
        "expected_pnl_delta": None,
        "main_failure_modes": [
            "window_regression",
            "concentration_failed",
            "sample_too_thin",
            "semantic_false_positive",
        ],
        "confidence_reason": (
            "SEC text-price alignment failed as generic issuer continuation, "
            "but the playbook calls for richer source-span relation fields. "
            "This uses replayable PIT SEC text and avoids recent FTD/FINRA, "
            "Form4, Companyfacts, and LLM soft-ranking retunes."
        ),
        "recorded_at": "2026-06-05T04:07:54Z",
    }
    payload["production_impact"] = PRODUCTION_IMPACT
    payload["llm_metrics"] = {
        "used_llm": False,
        "llm_change_scope": "none",
        "note": "No LLM soft-ranking was used; this is deterministic free-data SEC text.",
    }
    payload["anti_js"] = "No JavaScript was used."
    payload["next_action"] = (
        "If positive, build a shared default-off SEC source-span adapter with "
        "the same extraction and dilution exclusions before promotion; if "
        "rejected, do not retune nearby SEC business-development source-span "
        "phrases on this frozen sample."
        if payload["gate4"]["passed"]
        else "Do not retune nearby SEC business-development source-span phrases on this frozen sample; move to a different free-data relation mechanism."
    )
    payload["data_availability"]["pit_safety_note"] = (
        "Rows are keyed by accepted_at and usable_trade_date. The SEC text "
        "backfill is replayable public-PIT proxy data, not proof that a live "
        "adapter observed every document; positive replay therefore requires "
        "a shared default-off adapter and parity before promotion."
    )
    return payload


def main() -> int:
    _configure_parent()
    payload = parent.build_payload()
    payload = _patch_payload(payload)
    parent.persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["gate4"]["decision"],
                "aggregate": payload["aggregate"]["comparison"],
                "target_summary": payload["target_summary"],
                "gate4": payload["gate4"],
                "anti_js": payload["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
