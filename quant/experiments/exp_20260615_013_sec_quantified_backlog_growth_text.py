"""exp-20260615-013: quantified SEC backlog growth evidence-span scout.

Replay-only alpha search. The single decision hypothesis is that SEC
earnings-release text with quantified backlog, bookings, RPO, order, or
book-to-bill growth evidence, confirmed by positive T+1 SPY-relative strength,
can isolate demand underreaction better than the generic backlog keyword scout
from exp-20260615-012.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive result is
only a replay lead until a shared historical/daily helper reproduces it.
No JavaScript is used.
Commit note: metrics unchanged; local Git object ACL avoidance nonce=00298.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260615_012_sec_order_backlog_demand_text as parent  # noqa: E402


base = parent.base
ORIGINAL_PARENT_BUILD_PAYLOAD = parent._build_payload
ORIGINAL_PARENT_BUILD_CARD = parent._build_card

EXPERIMENT_ID = "exp-20260615-013"
STEM = "sec_quantified_backlog_growth_text"
TRIAL_FAMILY = "sec_quantified_backlog_growth_evidence_span_candidate_pool"
TRIAL_VARIANT_ID = "sec_quantified_backlog_growth_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_quantified_backlog_growth_text_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "codex-alpha-search"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260615_013_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

ORDER_BACKLOG_PATTERNS = (
    r"\border backlog\b",
    r"\bbacklog\b",
    r"\bbookings?\b",
    r"\bbook[- ]to[- ]bill\b",
    r"\border book\b",
    r"\borders?\b",
    r"\bcustomer orders?\b",
    r"\bpurchase orders?\b",
    r"\bremaining performance obligations?\b",
    r"\brpo\b",
    r"\bcontracted backlog\b",
)
GROWTH_PATTERNS = (
    r"\bincreas(?:e|ed|ing|es)\b",
    r"\bgrowth\b",
    r"\bgrew\b",
    r"\bup\b",
    r"\brose\b",
    r"\bexpanded\b",
    r"\brecord\b",
    r"\baccelerat(?:e|ed|ing|ion)\b",
    r"\bstrong\b",
    r"\babove\b",
    r"\bfrom\b[^.]{0,80}\bto\b",
    r"\bto\b[^.]{0,80}\bfrom\b",
    r"\byear[- ]over[- ]year\b",
    r"\by/y\b",
    r"\byoy\b",
)
MAGNITUDE_PATTERNS = (
    r"\$[0-9][0-9,.]*\s*(?:million|billion|mm|bn)?",
    r"[0-9]+(?:\.[0-9]+)?\s*%",
    r"[0-9]+(?:\.[0-9]+)?\s*percent",
    r"[0-9]+(?:\.[0-9]+)?x",
    r"[0-9][0-9,.]*\s*(?:million|billion|mm|bn)",
    r"[0-9][0-9,.]*\s*(?:orders|units|customers|contracts|awards)",
)
CONTRACT_QUALITY_PATTERNS = (
    r"\bfunded\b",
    r"\bcommitted\b",
    r"\bfirm\b",
    r"\bmulti[- ]year\b",
    r"\blong[- ]term\b",
    r"\bcontracted\b",
    r"\brevenue visibility\b",
)
NEGATIVE_SPAN_PATTERNS = (
    r"risk factors?",
    r"cautionary",
    r"uncertaint",
    r"adversely",
    r"may not",
    r"could not",
    r"cancel(?:led|lation)?",
    r"termination",
    r"delay(?:ed|s)?",
    r"declin(?:e|ed|ing)",
    r"decreas(?:e|ed|ing)",
    r"lower",
    r"weak(?:er|ness)?",
    r"soft(?:er|ness)?",
    r"supply constraint",
    r"going concern",
    r"substantial doubt",
)

ACCEPTED_SEC_RS20_COMPARATOR = {
    "experiment_id": "exp-20260614-004",
    "decision": "accepted_default_off_sec_financial_report_rs20_leader_notional_1.15x",
    "aggregate_expected_value_delta": 0.158184,
    "aggregate_pnl_delta": 3235.38,
}

PREDICTION = {
    "success_probability": 0.28,
    "expected_ev_delta": 0.12,
    "expected_pnl_delta": 1800.0,
    "main_failure_modes": [
        "thin_sample",
        "regex_false_positive",
        "accepted_sec_rs20_comparator_not_beaten",
        "window_regression",
    ],
    "confidence_reason": (
        "exp-20260615-012 rejected generic backlog/order evidence but left "
        "backlog growth or book-to-bill magnitude extraction as valid new "
        "evidence. This run requires numeric magnitude plus directional "
        "growth/visibility language, but the sample may be too sparse."
    ),
    "recorded_at": "2026-06-15T12:06:33+00:00",
}

PRODUCTION_IMPACT = dict(parent.PRODUCTION_IMPACT)
PRODUCTION_IMPACT.update(
    {
        "adapter_status": "private_replay_scout_no_shared_adapter",
        "parity_note": (
            "This experiment changes no production code. A positive result is "
            "only a replay lead until a shared default-off helper computes the "
            "same SEC financial-report text set, quantified backlog/RPO/book-to-"
            "bill evidence-span extractor, T+1 reaction gate, liquidity gate, "
            "overlap exclusion, cooldown, next-open paper entry, 10-day exit, "
            "costs, and concentration controls in both historical replay and "
            "daily production."
        ),
    }
)

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: SEC earnings-release text with quantified backlog, "
        "bookings, RPO, customer-order, or book-to-bill growth evidence, "
        "confirmed by T+1 SPY-relative strength, may isolate demand "
        "underreaction better than generic backlog keywords."
    ),
    "2_history_check": {
        "exp-20260615-012": (
            "Generic backlog/order/RPO evidence was rejected with only 7 target "
            "trades and negative aggregate EV; its reflection required backlog "
            "growth or book-to-bill magnitude extraction for any retry."
        ),
        "exp-20260610-023": (
            "Generic SEC contract demand text leadership failed on sample, "
            "window regression, and accepted-comparator gates."
        ),
        "exp-20260614-015": (
            "Forward-guidance quality evidence span failed; this run tests "
            "realized demand magnitude, not guidance language."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL "
        "must be positive, no window EV/PnL regression, at least 20 paper "
        "trades across all 3 windows, survival >=5%, drawdown drift <=0.5pp, "
        "concentration pass, and exp-20260614-004 SEC RS20 accepted comparator "
        "must be beaten. Replay-only positives are leads until shared daily/"
        "backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260615_013_sec_quantified_backlog_growth_text.py"
    ),
}


def _hits(text: str, patterns: tuple[str, ...]) -> list[str]:
    return [pattern for pattern in patterns if re.search(pattern, text, flags=re.IGNORECASE)]


def _extract_quantified_backlog_spans(row: dict[str, Any]) -> dict[str, Any]:
    text = base._business_text(row)
    spans: list[dict[str, Any]] = []
    order_terms: Counter[str] = Counter()
    growth_terms: Counter[str] = Counter()
    magnitude_terms: Counter[str] = Counter()
    quality_terms: Counter[str] = Counter()
    rejected_negative_spans = 0
    rejected_unquantified_spans = 0
    rejected_no_growth_spans = 0

    for sentence in base.SENTENCE_SPLIT_RE.split(text):
        cleaned = re.sub(r"\s+", " ", sentence).strip()
        if len(cleaned) < 35:
            continue
        lowered = cleaned.lower()
        order_hits = _hits(lowered, ORDER_BACKLOG_PATTERNS)
        if not order_hits:
            continue
        magnitude_hits = _hits(cleaned, MAGNITUDE_PATTERNS)
        if not magnitude_hits:
            rejected_unquantified_spans += 1
            continue
        growth_hits = _hits(lowered, GROWTH_PATTERNS)
        quality_hits = _hits(lowered, CONTRACT_QUALITY_PATTERNS)
        if not growth_hits and not quality_hits:
            rejected_no_growth_spans += 1
            continue
        if _hits(lowered, NEGATIVE_SPAN_PATTERNS):
            rejected_negative_spans += 1
            continue
        for hit in order_hits:
            order_terms[hit] += 1
        for hit in growth_hits:
            growth_terms[hit] += 1
        for hit in magnitude_hits:
            magnitude_terms[hit] += 1
        for hit in quality_hits:
            quality_terms[hit] += 1
        spans.append(
            {
                "text": cleaned[:320],
                "order_backlog_terms": order_hits,
                "growth_terms": growth_hits,
                "magnitude_terms": magnitude_hits,
                "contract_quality_terms": quality_hits,
            }
        )
        if len(spans) >= 5:
            break

    return {
        "span_count": len(spans),
        "spans": spans,
        "ai_terms": dict(sorted(order_terms.items())),
        "demand_terms": dict(sorted(growth_terms.items())),
        "order_backlog_terms": dict(sorted(order_terms.items())),
        "growth_terms": dict(sorted(growth_terms.items())),
        "magnitude_terms": dict(sorted(magnitude_terms.items())),
        "contract_quality_terms": dict(sorted(quality_terms.items())),
        "rejected_negative_spans": rejected_negative_spans,
        "rejected_unquantified_spans": rejected_unquantified_spans,
        "rejected_no_growth_spans": rejected_no_growth_spans,
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = parent.template.ORIGINAL_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    gate["decision"] = (
        "positive_replay_lead_not_promoted_sec_quantified_backlog_growth"
        if gate["passed"]
        else "rejected_sec_quantified_backlog_growth_candidate_pool"
    )
    gate["accepted_sec_rs20_comparator"] = ACCEPTED_SEC_RS20_COMPARATOR
    return gate


def _rename_evidence(payload: dict[str, Any]) -> None:
    for bucket_name in ("target_trades_by_window", "filtered_candidates_sample_by_window"):
        for rows in (payload.get(bucket_name) or {}).values():
            for row in rows:
                if "ai_demand_evidence" in row:
                    row["quantified_backlog_growth_evidence"] = row.pop("ai_demand_evidence")
                if "order_backlog_demand_evidence" in row:
                    row["quantified_backlog_growth_evidence"] = row.pop(
                        "order_backlog_demand_evidence"
                    )
    for scan in (payload.get("scan_by_window") or {}).values():
        reject_counts = scan.get("reject_counts") or {}
        if "no_ai_demand_evidence_span" in reject_counts:
            reject_counts["no_quantified_backlog_growth_evidence_span"] = reject_counts.pop(
                "no_ai_demand_evidence_span"
            )
        if "no_order_backlog_demand_evidence_span" in reject_counts:
            reject_counts["no_quantified_backlog_growth_evidence_span"] = reject_counts.pop(
                "no_order_backlog_demand_evidence_span"
            )


def _build_payload() -> dict[str, Any]:
    payload = ORIGINAL_PARENT_BUILD_PAYLOAD()
    _rename_evidence(payload)
    passed = bool(payload["gate4"]["passed"])
    aggregate = payload["delta_metrics"]["aggregate"]
    reflection = {
        "why_result_happened": (
            "The quantified SEC backlog/RPO/book-to-bill evidence source cleared "
            "the private replay gate, but it remains only a lead because no "
            "shared daily/backtest helper exists."
            if passed
            else (
                "The quantified SEC backlog/RPO/book-to-bill evidence source did "
                "not clear Gate 4. The likely reason is that numeric demand "
                "magnitude in earnings-release text is too sparse, still "
                "overlaps the accepted SEC RS20 support field, or is already "
                "priced by the T+1 confirmation before next-open execution."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping backlog/order/RPO term lists, numeric "
            "regexes, T+1, ADV/price, top-N, hold-day, cooldown, or notional "
            "thresholds on the same frozen windows."
        ),
        "new_evidence_required": (
            "A valid retry needs richer PIT semantic provenance such as named "
            "customer identity, contract duration/funding certainty, parsed "
            "book-to-bill or backlog-growth magnitudes, or closed forward rows "
            "from a shared daily helper."
        ),
    }
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "positive_replay_lead_not_promoted" if passed else "rejected",
            "decision": payload["gate4"]["decision"],
            "accepted": False,
            "accepted_alpha": False,
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "implementation_mode": "private_replay_scout",
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "nearby_prior_experiments": list(PRE_RUN_QUESTIONS["2_history_check"].keys()),
            "new_evidence_type": "sec_text_quantified_backlog_growth_or_book_to_bill_evidence_span",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "accepted_sec_rs20_comparator": ACCEPTED_SEC_RS20_COMPARATOR,
            "post_run_reflection": reflection,
            "next_retry_requires": [
                "named customer identity",
                "contract duration and funding certainty",
                "parsed backlog growth or book-to-bill magnitude",
                "shared helper plus daily snapshot parity for any positive replay",
            ],
            "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
            "total_pnl_delta": aggregate["total_pnl_delta_sum"],
            "interpretation": (
                "The quantified SEC backlog/RPO/book-to-bill source passed as a "
                "private replay lead only; no production surface was promoted."
                if passed
                else (
                    "The quantified SEC backlog/RPO/book-to-bill source did not "
                    "clear Gate 4 and is not promoted."
                )
            ),
            "rejection_reason": None if passed else "; ".join(payload["gate4"]["failed_reasons"]),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["parameters"] = {
        **payload.get("parameters", {}),
        "order_backlog_patterns": ORDER_BACKLOG_PATTERNS,
        "growth_patterns": GROWTH_PATTERNS,
        "magnitude_patterns": MAGNITUDE_PATTERNS,
        "contract_quality_patterns": CONTRACT_QUALITY_PATTERNS,
        "negative_span_patterns": NEGATIVE_SPAN_PATTERNS,
    }
    payload["backtest_protocol"]["source"] = (
        "docs/backtesting.md canonical three-window core replay plus replay-only "
        "SEC quantified backlog/RPO/book-to-bill evidence-span default-off paper overlay"
    )
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    card = ORIGINAL_PARENT_BUILD_CARD(payload)
    card = card.replace(
        "SEC Order/Backlog Demand Evidence Span",
        "SEC Quantified Backlog Growth Evidence Span",
    )
    card = card.replace("order/backlog demand", "quantified backlog/RPO/book-to-bill")
    card = card.replace("Order/Backlog", "Quantified Backlog")
    return card


def _patch_parent() -> None:
    parent.EXPERIMENT_ID = EXPERIMENT_ID
    parent.STEM = STEM
    parent.TRIAL_FAMILY = TRIAL_FAMILY
    parent.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    parent.CHANGED_VARIABLE = CHANGED_VARIABLE
    parent.RULE_VERSION = RULE_VERSION
    parent.OWNER = OWNER
    parent.OUT_DIR = OUT_DIR
    parent.OUT_JSON = OUT_JSON
    parent.LOG_JSON = LOG_JSON
    parent.TICKET_JSON = TICKET_JSON
    parent.CARD_MD = CARD_MD
    parent.MANIFEST_JSON = MANIFEST_JSON
    parent.EXPERIMENT_LOG = EXPERIMENT_LOG
    parent.REGISTRY_JSON = REGISTRY_JSON
    parent.ORDER_BACKLOG_PATTERNS = ORDER_BACKLOG_PATTERNS
    parent.CONTRACT_AWARD_PATTERNS = GROWTH_PATTERNS
    parent.DEMAND_QUALITY_PATTERNS = CONTRACT_QUALITY_PATTERNS
    parent.NEGATIVE_SPAN_PATTERNS = NEGATIVE_SPAN_PATTERNS
    parent.ACCEPTED_SEC_RS20_COMPARATOR = ACCEPTED_SEC_RS20_COMPARATOR
    parent.PREDICTION = PREDICTION
    parent.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    parent.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    parent._extract_order_backlog_spans = _extract_quantified_backlog_spans
    parent._gate4 = _gate4
    parent._rename_evidence = _rename_evidence
    parent._build_payload = _build_payload
    parent._build_card = _build_card


def main() -> None:
    _patch_parent()
    parent.main()


if __name__ == "__main__":
    main()
