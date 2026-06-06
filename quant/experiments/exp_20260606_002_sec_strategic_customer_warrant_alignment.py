"""exp-20260606-002: SEC strategic customer warrant alignment.

Alpha search on one production-visible SEC text relation field. Prior SEC
business-win/source-span experiments explicitly excluded warrants as dilution
noise. This run tests the opposite narrow hypothesis: a warrant tied to a
strategic customer, partner, commercial agreement, or hyperscaler relationship
may be customer-validated demand optionality rather than generic financing.

No production adapter, live order path, ranking, sizing, exits, LLM/news path,
or shared sleeve code is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

import exp_20260603_012_sec_customer_contract_business_win as parent


_PARENT_GATE4_DECISION = parent._gate4_decision

EXP_ID = "exp-20260606-002"
STEM = "sec_strategic_customer_warrant_alignment"
TRIAL_FAMILY = "sec_strategic_customer_warrant_alignment_candidate_pool"
CHANGED_VARIABLE = "sec_strategic_customer_warrant_alignment_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

OUT_DIR = parent.REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = parent.REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = parent.REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
CARD_MD = parent.REPO_ROOT / "experiments" / "cards" / f"{EXP_ID}.md"
ARTIFACT_MD = (
    parent.REPO_ROOT
    / "experiments"
    / "artifacts"
    / f"{EXP_ID}_{STEM}.md"
)

WARRANT_PATTERNS: tuple[str, ...] = (
    r"\bwarrants?\b",
    r"\bequity[- ]linked\b",
    r"\bexercis(?:e|able|ed|ing)\b.{0,120}\bwarrants?\b",
)

STRATEGIC_ALIGNMENT_PATTERNS: tuple[str, ...] = (
    r"\bcustomer\b",
    r"\bcustomers\b",
    r"\bpartner(?:ship)?\b",
    r"\bstrategic\b",
    r"\bcommercial\b",
    r"\bsupply agreement\b",
    r"\bpurchase agreement\b",
    r"\bcontract(?:ed)? revenue\b",
    r"\bdata center\b",
    r"\bai compute\b",
    r"\bhpc\b",
    r"\bhyperscaler\b",
    r"\bofftake\b",
    r"\boracle\b",
    r"\bgoogle\b",
    r"\bfluidstack\b",
)

PURE_FINANCING_PATTERNS: tuple[str, ...] = (
    r"\bpublic offering\b",
    r"\bregistered direct\b",
    r"\bat[- ]the[- ]market\b",
    r"\batm offering\b",
    r"\bshelf registration\b",
    r"\bresale registration\b",
    r"\bconvertible (?:note|notes|debt|preferred)\b",
    r"\bsenior notes?\b",
    r"\bdebt offering\b",
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
        "This experiment changes no production code. A positive replay result "
        "would require a shared default-off SEC text adapter with the same "
        "warrant/alignment pattern set, PIT usable-date handling, financing "
        "audit fields, candidate ordering, and production/backtest parity tests "
        "before any daily report, candidate queue, or order surface could change."
    ),
}


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
        return {
            part.strip()
            for part in str(raw).replace(";", ",").split(",")
            if part.strip()
        }
    return set()


def _candidate_from_row(row: dict[str, Any]) -> dict[str, Any] | None:
    usable = str(row.get("usable_trade_date") or "")[:10]
    window = parent._window_name(usable)
    ticker = str(row.get("ticker") or "").upper()
    if not ticker or not usable or window is None:
        return None
    form_type = str(row.get("form_type") or row.get("form_base") or "").upper()
    if "8-K" not in form_type:
        return None

    text = parent.semantic_text(row)
    if not text:
        return None
    lowered = text.lower()
    warrant_hits = _pattern_count(lowered, WARRANT_PATTERNS)
    alignment_hits = _pattern_count(lowered, STRATEGIC_ALIGNMENT_PATTERNS)
    if warrant_hits <= 0 or alignment_hits <= 0:
        return None

    features = parent.language_features(row)
    pure_financing_hits = _pattern_count(lowered, PURE_FINANCING_PATTERNS)
    positive_hits = int(features.get("positive_phrase_hits") or 0)
    negative_hits = int(features.get("negative_phrase_hits") or 0)
    score = (
        2.0 * warrant_hits
        + alignment_hits
        + 0.25 * positive_hits
        - 0.25 * negative_hits
        - 0.50 * pure_financing_hits
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
        "status": "event_ready",
        "rule_version": RULE_VERSION,
        "strategy": STEM,
        "warrant_hits": warrant_hits,
        "strategic_alignment_hits": alignment_hits,
        "pure_financing_hits": pure_financing_hits,
        "business_win_hits": alignment_hits,
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
        "positive_sec_strategic_customer_warrant_alignment_requires_adapter"
        if passed
        else "rejected_sec_strategic_customer_warrant_alignment_candidate_pool"
    )
    gate4["status"] = "observed_only" if passed else "rejected"
    gate4["requires_parity_before_promotion"] = passed
    gate4["rationale"] = (
        "The strategic customer/partner warrant replay passed Gate 4, but "
        "remains replay-only. Retention would require a shared default-off SEC "
        "text adapter with identical pattern semantics and parity tests."
        if passed
        else "One or more Gate 4 checks failed, so the strategic customer/partner "
        "warrant alignment source is not retained."
    )
    return gate4


def _window_table(results: list[dict[str, Any]]) -> str:
    return parent._window_table(results)


def _write_artifact(payload: dict[str, Any]) -> None:
    comparison = payload["aggregate"]["comparison"]
    lines = [
        f"# {EXP_ID} SEC Strategic Customer Warrant Alignment",
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
            "## Negative Reflection",
            "",
            payload["negative_reflection"],
            "",
            "## Production / Backtest Parity",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reproducibility",
            "",
            (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260606_002_sec_strategic_customer_warrant_alignment.py"
            ),
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _patch_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload = _normalize_zero_trade_windows(payload)
    payload["experiment_id"] = EXP_ID
    payload["trial_family"] = TRIAL_FAMILY
    payload["changed_variable"] = CHANGED_VARIABLE
    payload["rule_version"] = RULE_VERSION
    payload["preflight"] = {
        "alpha_hypothesis": (
            "SEC 8-K filings where a strategic customer or partner receives "
            "equity-linked warrant alignment may identify customer-validated "
            "demand optionality that prior generic SEC business-win text "
            "deliberately excluded as dilution noise."
        ),
        "category": "entry / candidate_pool",
        "playbook_alignment": (
            "Uses a new free SEC text relation field. It avoids ETF, FINRA, "
            "Companyfacts, Space, Form 4, and alpha_score retunes that the "
            "current playbook marks as saturated or frozen."
        ),
        "nearby_prior_experiments": {
            "exp-20260603-012": (
                "SEC customer-contract/business-win long replay failed; its "
                "exclusion list explicitly removed warrants."
            ),
            "exp-20260605-006": (
                "SEC business-development source-span replay failed and also "
                "excluded warrants as dilution language."
            ),
            "exp-20260605-031": (
                "Inverse business-win replay did not stabilize; this run changes "
                "the causal field to customer/partner warrant alignment."
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
            "max_single_positive_share": parent.MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi_max": parent.MAX_POSITIVE_HHI,
            "promotion_parity": (
                "Positive replay cannot be promoted until implemented through "
                "a shared default-off production/backtest helper."
            ),
        },
        "reproducibility": (
            "The runner persists before/after metrics, selected SEC candidates, "
            "Gate 4 checks, ticket, card, artifact, and experiment_log.jsonl record."
        ),
    }
    payload["parameters"] = {
        "sec_text_path": parent._repo_rel(parent.SEC_TEXT_PATH),
        "warrant_patterns": WARRANT_PATTERNS,
        "strategic_alignment_patterns": STRATEGIC_ALIGNMENT_PATTERNS,
        "pure_financing_patterns_audited": PURE_FINANCING_PATTERNS,
        "event_notional": parent.EVENT_NOTIONAL,
        "hold_days": parent.HOLD_DAYS,
        "max_paper_trades_per_day": parent.MAX_PAPER_TRADES_PER_DAY,
        "round_trip_cost_pct": parent.ROUND_TRIP_COST_PCT,
        "selection_order": (
            "entry_date asc, candidate_selection_score desc, "
            "strategic_alignment_hits desc, ticker asc"
        ),
    }
    payload["prediction"] = {
        "success_probability": 0.18,
        "expected_ev_delta": None,
        "expected_pnl_delta": None,
        "main_failure_modes": [
            "sample_too_thin",
            "financing_false_positive",
            "window_regression",
            "concentration_failed",
        ],
        "confidence_reason": (
            "The field is genuinely distinct because prior SEC business-win "
            "experiments excluded warrants, but preflight scanning found only "
            "a few likely historical rows, so sample power is the main risk."
        ),
        "recorded_at": "2026-06-06T01:16:13Z",
    }
    payload["production_impact"] = PRODUCTION_IMPACT
    payload["llm_metrics"] = {
        "used_llm": False,
        "llm_change_scope": "none",
        "note": "No LLM soft-ranking was used; this is deterministic SEC text matching.",
    }
    payload["anti_js"] = "No JavaScript was used."
    payload["negative_reflection"] = (
        "If rejected, the likely reason is not that customer-aligned warrants "
        "are impossible alpha, but that the historical SEC text archive contains "
        "too few PIT rows and mixes strategic alignment with financing language. "
        "Do not retune nearby warrant phrase thresholds on this frozen sample; "
        "a valid retry needs broader forward rows or a richer source-span "
        "counterparty extraction."
    )
    payload["next_action"] = (
        "If positive, build a shared default-off SEC warrant-alignment adapter "
        "with parity tests before promotion; if rejected, do not retune nearby "
        "warrant phrase thresholds on this frozen sample."
        if payload["gate4"]["passed"]
        else "Do not retune nearby strategic-warrant SEC phrase thresholds on this frozen sample; move to a different free-data relation mechanism."
    )
    payload["data_availability"]["pit_safety_note"] = (
        "Rows are keyed by accepted_at and usable_trade_date. The SEC text "
        "backfill is replayable public-PIT proxy data; promotion would require "
        "a shared default-off adapter that observes the same fields live."
    )
    return payload


def _normalize_zero_trade_windows(payload: dict[str, Any]) -> dict[str, Any]:
    for row in payload.get("results", []):
        if int(row.get("target_trade_count") or 0) != 0:
            continue
        label = str(row.get("label") or "")
        before = dict(row.get("before") or {})
        row["after"] = dict(before)
        row["comparison"] = {
            "expected_value_score_delta": 0.0,
            "strategy_total_pnl_delta": 0.0,
            "max_drawdown_delta": 0.0,
        }
        if label:
            payload.setdefault("after_metrics", {})[label] = dict(before)

    before_aggregate = parent._aggregate_metrics(payload["before_metrics"])
    after_aggregate = parent._aggregate_metrics(payload["after_metrics"])
    payload["aggregate"] = {
        "before": before_aggregate,
        "after": after_aggregate,
        "comparison": parent._comparison(before_aggregate, after_aggregate),
    }
    payload["gate4"] = _gate4_decision(
        payload["aggregate"],
        payload["results"],
        payload["target_summary"],
    )
    return payload


def _candidate_field_summary(payload: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for detail in payload.get("event_candidate_details", {}).values():
        rows.extend(detail.get("selected_trades") or [])
    return {
        "selected_by_language_bucket": dict(
            sorted(Counter(str(row.get("language_bucket") or "missing") for row in rows).items())
        ),
        "selected_by_ticker": dict(
            sorted(Counter(str(row.get("ticker") or "missing") for row in rows).items())
        ),
        "selected_financing_hit_rows": sum(
            1 for row in rows if int(row.get("pure_financing_hits") or 0) > 0
        ),
    }


def main() -> int:
    _configure_parent()
    payload = parent.build_payload()
    payload = _patch_payload(payload)
    payload["candidate_field_summary"] = _candidate_field_summary(payload)
    parent.persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "decision": payload["gate4"]["decision"],
                "aggregate": payload["aggregate"]["comparison"],
                "target_summary": payload["target_summary"],
                "candidate_field_summary": payload["candidate_field_summary"],
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
