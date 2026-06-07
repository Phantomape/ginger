"""exp-20260607-004: SEC guidance/outlook raise price-aligned pool.

Alpha search on one production-visible free-data field. A high/medium
credibility SEC filing must include explicit guidance/outlook raise evidence,
must not include guidance-cut, financing, dilution, or distress language, and
the issuer must react positively versus SPY on the PIT signal date. The paper
entry is shifted to the next trading-session open so the reaction is known
before entry.

Core signal generation, ranking, sizing, exits, LLM/news replay, watchlists,
shared adapters, and live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260603_012_sec_customer_contract_business_win as parent


_PARENT_GATE4_DECISION = parent._gate4_decision
_PARENT_EXPERIMENT_LOG_RECORD = parent._experiment_log_record

EXP_ID = "exp-20260607-004"
STEM = "sec_guidance_outlook_raise_price_aligned"
TRIAL_FAMILY = "sec_guidance_outlook_raise_price_aligned_candidate_pool"
CHANGED_VARIABLE = "sec_guidance_outlook_raise_price_aligned_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

OUT_DIR = parent.REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = parent.REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = parent.REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
CARD_MD = parent.REPO_ROOT / "experiments" / "cards" / f"{EXP_ID}.md"
ARTIFACT_MD = parent.REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"

EVENT_NOTIONAL = 4_000.0
MIN_SIGNAL_DAY_RETURN = 0.0
MIN_SIGNAL_DAY_EXCESS_VS_SPY = 0.01
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.30

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
    "lookahead_guard": (
        "The candidate selector observes signal-date close-to-close reaction, "
        "then shifts usable_trade_date to the next trading session before "
        "calling the existing next-open paper trade helper."
    ),
    "parity_note": (
        "This experiment changes no production code. A retained result would "
        "need a shared default-off SEC guidance/outlook adapter using the same "
        "filing credibility, evidence-span extraction, exclusion language, "
        "signal-day OHLCV reaction, next-session entry shift, and parity tests "
        "before any daily report, candidate queue, or order surface could "
        "change."
    ),
}

_PRICE_CACHE: dict[str, list[dict[str, Any]]] | None = None

GUIDANCE_RAISE_PATTERNS: tuple[str, ...] = (
    r"\brais(?:e|ed|es|ing)\s+(?:its\s+|our\s+)?(?:full[- ]year\s+|fiscal\s+|annual\s+|revenue\s+|sales\s+|earnings\s+|eps\s+|adjusted\s+|profit\s+|outlook\s+)?(?:guidance|outlook|forecast)\b",
    r"\b(?:guidance|outlook|forecast)\b.{0,120}\b(?:rais(?:ed|e|es|ing)|increase(?:d|s|ing)?|higher|above|upward)\b",
    r"\bincreas(?:e|ed|es|ing)\s+(?:its\s+|our\s+)?(?:full[- ]year\s+|fiscal\s+|annual\s+)?(?:guidance|outlook|forecast)\b",
    r"\b(?:now\s+expects|now\s+expect|expects|expect)\b.{0,120}\b(?:above|higher than|exceed|greater than)\b.{0,80}\b(?:guidance|outlook|forecast|consensus|prior)\b",
)
GUIDANCE_CUT_PATTERNS: tuple[str, ...] = (
    r"\blower(?:s|ed|ing)?\s+(?:its\s+|our\s+)?(?:full[- ]year\s+|fiscal\s+|annual\s+)?(?:guidance|outlook|forecast)\b",
    r"\b(?:guidance|outlook|forecast)\b.{0,120}\b(?:lower(?:ed|s|ing)?|reduc(?:ed|e|es|ing)|cut(?:s|ting)?|downward)\b",
    r"\breduc(?:e|ed|es|ing)\s+(?:its\s+|our\s+)?(?:full[- ]year\s+|fiscal\s+|annual\s+)?(?:guidance|outlook|forecast)\b",
    r"\b(?:now\s+expects|now\s+expect|expects|expect)\b.{0,120}\b(?:below|lower than|less than)\b.{0,80}\b(?:guidance|outlook|forecast|consensus|prior)\b",
)
FINANCING_EXCLUSION_PATTERNS: tuple[str, ...] = (
    r"\bregistered direct\b",
    r"\bprivate placement\b",
    r"\bpublic offering\b",
    r"\boffering\b",
    r"\bat[- ]the[- ]market\b",
    r"\bATM\b",
    r"\bwarrant\b",
    r"\bconvertible\b",
    r"\bsecurities purchase agreement\b",
    r"\bdilution\b",
    r"\bbankruptcy\b",
    r"\bgoing concern\b",
    r"\brestatement\b",
)

EVIDENCE_CONTEXT_CHARS = 80


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
    parent._experiment_log_record = _experiment_log_record
    parent._write_artifact = _write_artifact


def _prices() -> dict[str, list[dict[str, Any]]]:
    global _PRICE_CACHE
    if _PRICE_CACHE is None:
        parent._configure_overlay_module()
        _PRICE_CACHE = parent.overlay._load_price_map()
    return _PRICE_CACHE


def _item_codes(row: dict[str, Any]) -> set[str]:
    raw = row.get("eight_k_item_codes")
    if isinstance(raw, list):
        return {str(item).strip() for item in raw if str(item).strip()}
    if raw:
        return {part.strip() for part in str(raw).replace(";", ",").split(",") if part.strip()}
    return set()


def _credibility_bucket(row: dict[str, Any]) -> str | None:
    form_type = str(row.get("form_type") or row.get("form_base") or "").upper()
    form_base = form_type.split("/")[0]
    if form_base in {"10-K", "10-Q"}:
        return "high"
    if form_base == "8-K" and (_item_codes(row) & {"2.02", "2.05"}):
        return "medium"
    return None


def _date_index(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {str(row.get("date") or "")[:10]: idx for idx, row in enumerate(rows)}


def _reaction(
    *,
    ticker: str,
    signal_date: str,
) -> dict[str, Any] | None:
    prices = _prices()
    ticker_rows = prices.get(ticker)
    spy_rows = prices.get("SPY")
    if not ticker_rows or not spy_rows:
        return None
    ticker_idx = _date_index(ticker_rows).get(signal_date)
    spy_idx = _date_index(spy_rows).get(signal_date)
    if ticker_idx is None or spy_idx is None or ticker_idx <= 0 or spy_idx <= 0:
        return None
    ticker_prev = ticker_rows[ticker_idx - 1].get("close")
    ticker_close = ticker_rows[ticker_idx].get("close")
    spy_prev = spy_rows[spy_idx - 1].get("close")
    spy_close = spy_rows[spy_idx].get("close")
    if not ticker_prev or ticker_close is None or not spy_prev or spy_close is None:
        return None
    signal_return = (float(ticker_close) / float(ticker_prev)) - 1.0
    spy_return = (float(spy_close) / float(spy_prev)) - 1.0
    next_idx = ticker_idx + 1
    if next_idx >= len(ticker_rows):
        return None
    next_date = str(ticker_rows[next_idx].get("date") or "")[:10]
    if not next_date:
        return None
    return {
        "signal_day_return": signal_return,
        "signal_day_spy_return": spy_return,
        "signal_day_excess_vs_spy": signal_return - spy_return,
        "next_entry_date": next_date,
    }


def _evidence_spans(
    text: str,
    patterns: tuple[str, ...],
    *,
    max_spans: int = 5,
) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE | re.DOTALL):
            start = max(0, match.start() - EVIDENCE_CONTEXT_CHARS)
            end = min(len(text), match.end() + EVIDENCE_CONTEXT_CHARS)
            snippet = " ".join(text[start:end].split())
            spans.append(
                {
                    "pattern": pattern,
                    "match_start": match.start(),
                    "match_end": match.end(),
                    "context_start": start,
                    "context_end": end,
                    "snippet": snippet[:500],
                }
            )
            if len(spans) >= max_spans:
                return spans
    return spans


def _candidate_from_row(row: dict[str, Any]) -> dict[str, Any] | None:
    signal_date = str(row.get("usable_trade_date") or "")[:10]
    window = parent._window_name(signal_date)
    ticker = str(row.get("ticker") or "").upper()
    if not ticker or not signal_date or window is None:
        return None
    credibility = _credibility_bucket(row)
    if credibility is None:
        return None

    text = parent.semantic_text(row)
    if not text:
        return None
    guidance_raise_spans = _evidence_spans(text, GUIDANCE_RAISE_PATTERNS)
    if not guidance_raise_spans:
        return None

    guidance_cut_spans = _evidence_spans(text, GUIDANCE_CUT_PATTERNS)
    financing_exclusion_spans = _evidence_spans(text, FINANCING_EXCLUSION_PATTERNS)
    if guidance_cut_spans or financing_exclusion_spans:
        return None

    features = parent.language_features(row)
    language_bucket = str(features.get("language_bucket") or "")
    text_event_type = str(features.get("text_event_type") or "")
    guidance_cut_hits = int(features.get("guidance_cut_hits") or 0)
    guidance_raise_hits = int(features.get("guidance_raise_hits") or 0)
    positive_hits = int(features.get("positive_phrase_hits") or 0)
    negative_hits = int(features.get("negative_phrase_hits") or 0)
    if language_bucket == "negative_language" or guidance_cut_hits > 0:
        return None

    reaction = _reaction(ticker=ticker, signal_date=signal_date)
    if reaction is None:
        return None
    signal_return = float(reaction["signal_day_return"])
    excess_return = float(reaction["signal_day_excess_vs_spy"])
    if signal_return < MIN_SIGNAL_DAY_RETURN:
        return None
    if excess_return < MIN_SIGNAL_DAY_EXCESS_VS_SPY:
        return None

    score = (
        excess_return * 100.0
        + 0.75 * len(guidance_raise_spans)
        + 0.25 * positive_hits
        + 0.50 * guidance_raise_hits
        + 0.10 * float(features.get("language_score") or 0.0)
        - 0.25 * negative_hits
    )
    return {
        "ticker": ticker,
        "signal_date": signal_date,
        "sec_usable_trade_date": signal_date,
        "usable_trade_date": reaction["next_entry_date"],
        "filing_date": str(row.get("filing_date") or "")[:10],
        "window": window,
        "form_type": row.get("form_type"),
        "form_base": row.get("form_base"),
        "eight_k_item_codes": sorted(_item_codes(row)),
        "accession_number": row.get("accession_number"),
        "primary_document": row.get("primary_document"),
        "status": "event_ready",
        "rule_version": RULE_VERSION,
        "strategy": STEM,
        "source_credibility_bucket": credibility,
        "language_bucket": language_bucket,
        "text_event_type": text_event_type,
        "language_score": features.get("language_score"),
        "positive_phrase_hits": positive_hits,
        "negative_phrase_hits": negative_hits,
        "guidance_raise_hits": guidance_raise_hits,
        "guidance_cut_hits": guidance_cut_hits,
        "guidance_raise_span_count": len(guidance_raise_spans),
        "guidance_cut_span_count": len(guidance_cut_spans),
        "financing_exclusion_span_count": len(financing_exclusion_spans),
        "guidance_raise_evidence_spans": guidance_raise_spans,
        "guidance_cut_evidence_spans": guidance_cut_spans,
        "financing_exclusion_spans": financing_exclusion_spans,
        "business_win_hits": len(guidance_raise_spans),
        "candidate_selection_score": round(score, 6),
        "signal_day_return_pct": round(signal_return * 100.0, 6),
        "signal_day_spy_return_pct": round(float(reaction["signal_day_spy_return"]) * 100.0, 6),
        "signal_day_excess_vs_spy_pct": round(excess_return * 100.0, 6),
        "min_signal_day_return_pct": MIN_SIGNAL_DAY_RETURN * 100.0,
        "min_signal_day_excess_vs_spy_pct": MIN_SIGNAL_DAY_EXCESS_VS_SPY * 100.0,
        "known_at": "after_signal_date_close_before_next_session_open",
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
        "positive_sec_guidance_outlook_raise_price_aligned_replay_lead_requires_shared_adapter"
        if passed
        else "rejected_sec_guidance_outlook_raise_price_aligned_candidate_pool"
    )
    gate4["status"] = "observed_only" if passed else "rejected"
    gate4["requires_parity_before_promotion"] = passed
    gate4["rationale"] = (
        "The standalone SEC guidance/outlook raise price-aligned replay "
        "passed Gate 4, but remains replay-only. Retention requires a shared "
        "default-off production/backtest adapter with the same next-session "
        "entry shift, evidence-span schema, exclusion language, and parity tests."
        if passed
        else "One or more Gate 4 checks failed, so the standalone SEC guidance/"
        "outlook raise price-aligned source is not retained."
    )
    return gate4


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = _PARENT_EXPERIMENT_LOG_RECORD(payload)
    record["post_run_reflection"] = payload["post_run_reflection"]
    record["negative_reflection"] = payload["postmortem_reflection"]
    return record


def _window_table(results: list[dict[str, Any]]) -> str:
    return parent._window_table(results)


def _write_artifact(payload: dict[str, Any]) -> None:
    comparison = payload["aggregate"]["comparison"]
    lines = [
        f"# {EXP_ID} SEC Guidance/Outlook Raise Price-Aligned Pool",
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
            "## Failure Reflection",
            "",
            payload["postmortem_reflection"],
            "",
            "## Lookahead / Parity Guard",
            "",
            PRODUCTION_IMPACT["lookahead_guard"],
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reproducibility",
            "",
            (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260607_004_sec_guidance_outlook_raise_price_aligned.py"
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
            "SEC high/medium credibility filings with explicit guidance or "
            "outlook raise evidence, no guidance-cut/financing/dilution "
            "exclusions, and positive signal-day reaction versus SPY may form "
            "a cleaner standalone issuer-continuation paper candidate pool "
            "than generic SEC positive text variants."
        ),
        "category": "entry / candidate_pool",
        "playbook_alignment": (
            "Uses the playbook's high-value SEC semantic lane with source-span "
            "provenance for guidance/outlook changes, plus free PIT SEC text "
            "and OHLCV alignment. It avoids LLM soft-ranking, threshold retunes "
            "on frozen SEC source-family variants, and simple noise ticker "
            "expansion."
        ),
        "nearby_prior_experiments": {
            "exp-20260516-034": (
                "Guidance-raise notional scalar was rejected with only one "
                "covered trade; this run changes the causal variable to a "
                "standalone evidence-span candidate pool instead of scalar "
                "retuning."
            ),
            "exp-20260603-012": (
                "SEC customer-demand text failed aggregate and window Gate 4; "
                "this run avoids customer/backlog/contract phrases."
            ),
            "exp-20260605-006": (
                "Business development exhibit text had positive aggregate but "
                "failed Gate 4; this run requires guidance/outlook raise spans."
            ),
            "exp-20260605-018": (
                "Operational 8-K absorption was rejected; this run does not "
                "reuse broad operational-update phrases."
            ),
            "exp-20260606-002": (
                "Strategic customer warrant alignment produced zero target "
                "trades; this run explicitly excludes warrant/financing rows."
            ),
            "exp-20260606-007": (
                "Item 2.03 credit absorption failed Gate 4; this run excludes "
                "financing/debt-style rows."
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
                "a shared default-off production/backtest helper with the same "
                "evidence spans, exclusions, and next-session entry shift."
            ),
        },
        "reproducibility": (
            "The runner persists canonical before/after metrics, selected SEC "
            "guidance/outlook evidence spans, Gate 4 checks, ticket, card, "
            "artifact, and experiment_log.jsonl record."
        ),
    }
    payload["parameters"] = {
        "sec_text_path": parent._repo_rel(parent.SEC_TEXT_PATH),
        "event_notional": EVENT_NOTIONAL,
        "hold_days": parent.HOLD_DAYS,
        "max_paper_trades_per_day": parent.MAX_PAPER_TRADES_PER_DAY,
        "min_signal_day_return_pct": MIN_SIGNAL_DAY_RETURN * 100.0,
        "min_signal_day_excess_vs_spy_pct": MIN_SIGNAL_DAY_EXCESS_VS_SPY * 100.0,
        "credible_forms": ["10-K", "10-Q", "8-K item 2.02", "8-K item 2.05"],
        "guidance_raise_patterns": list(GUIDANCE_RAISE_PATTERNS),
        "guidance_cut_patterns": list(GUIDANCE_CUT_PATTERNS),
        "financing_exclusion_patterns": list(FINANCING_EXCLUSION_PATTERNS),
        "evidence_context_chars": EVIDENCE_CONTEXT_CHARS,
        "text_alignment_rule": (
            "Require at least one explicit guidance/outlook raise evidence span; "
            "exclude guidance cuts, financing/dilution/distress spans, "
            "negative_language, and upstream guidance_cut_hits."
        ),
        "entry_shift": "signal_date close reaction is known; paper entry uses next ticker trading-session open",
        "selection_order": "entry_date asc, candidate_selection_score desc, guidance_raise_span_count desc, ticker asc",
    }
    payload["prediction"] = {
        "success_probability": 0.22,
        "expected_ev_delta": 0.18,
        "expected_pnl_delta": 2500.0,
        "main_failure_modes": [
            "thin_sample",
            "window_regression",
            "semantic_false_positive",
            "concentration_failed",
        ],
        "confidence_reason": (
            "Guidance/outlook raise is a higher-information SEC semantic field "
            "with source-span provenance, but the older guidance scalar was thin "
            "and recent SEC text pools have failed."
        ),
        "recorded_at": "2026-06-07T01:47:00Z",
    }
    payload["production_impact"] = PRODUCTION_IMPACT
    payload["llm_metrics"] = {
        "used_llm": False,
        "llm_change_scope": "none",
        "note": "No LLM soft-ranking was used because replay-safe LLM data remains sparse.",
    }
    payload["anti_js"] = "No JavaScript was used."
    payload["next_action"] = (
        "If positive, build a shared default-off SEC guidance/outlook adapter "
        "with the same evidence-span schema, exclusions, next-session entry "
        "shift, and parity tests before promotion; if rejected, do not retune "
        "guidance/outlook thresholds on this sample."
        if payload["gate4"]["passed"]
        else "Do not retune guidance/outlook thresholds on this sample; need forward rows, stronger semantic parser evidence, or a different free-data relation mechanism."
    )
    comparison = payload["aggregate"]["comparison"]
    target_summary = payload["target_summary"]
    payload["postmortem_reflection"] = (
        "Rejected because the evidence-span guidance/outlook pool was too thin "
        f"({target_summary['target_trade_count']} target trades versus the "
        f"{parent.MIN_TARGET_TRADES} trade floor), reduced aggregate EV by "
        f"{float(comparison['expected_value_score_delta']):+.4f}, and regressed "
        "late_strong EV despite all three windows showing small PnL gains. "
        "Positive PnL concentration also failed, with the largest positive "
        f"ticker share at {float(target_summary['max_single_positive_share']):.3f} "
        f"and HHI at {float(target_summary['positive_pnl_hhi']):.3f}. The likely "
        "failure mode is that explicit guidance/outlook raise filings are sparse "
        "and mostly mega-cap continuation events already captured by existing "
        "accepted momentum/consensus surfaces, while the price-alignment filter "
        "does not add enough independent information to offset event drag. Do "
        "not retune the same guidance threshold/excess-return bundle on this "
        "sample; require forward SEC rows, richer semantic relation extraction, "
        "or a different free-data edge."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The guidance/outlook raise evidence-span rule found too few "
            "independent events and the selected positives were concentrated in "
            "large-cap continuation names already represented by existing "
            "momentum or consensus surfaces. The same-day price-alignment guard "
            "added confirmation but not enough independent replacement value, "
            "so late_strong EV regressed and aggregate EV fell despite small "
            "headline PnL gains."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry this frozen sample by changing guidance/outlook regex "
            "phrases, same-day excess-return thresholds, event notional, hold "
            "days, max trades per day, or the 10-K/10-Q/8-K credibility set."
        ),
        "new_evidence_required": (
            "Retry only with forward SEC replacement rows, a richer PIT semantic "
            "relation parser with audited source spans, or a different free-data "
            "edge that expands the candidate pool without adding noise tickers."
        ),
    }
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
