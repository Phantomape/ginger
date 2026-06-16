"""exp-20260615-026: SEC SaaS operating KPI evidence-span scout.

Replay-only alpha search. The single decision hypothesis is that PIT SEC
earnings-release text with concrete SaaS/subscription operating KPIs such as
ARR, NRR, product revenue, subscription revenue, RPO, or large-customer growth,
confirmed by positive T+1 SPY-relative strength, can expand the candidate pool
with higher-quality demand underreaction than generic backlog/RPO text.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive result is
only a replay lead until a shared historical/daily helper reproduces it.
No JavaScript is used.
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

EXPERIMENT_ID = "exp-20260615-026"
STEM = "sec_saas_operating_kpi_text"
TRIAL_FAMILY = "sec_saas_operating_kpi_evidence_span_candidate_pool"
TRIAL_VARIANT_ID = "sec_saas_operating_kpi_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_saas_operating_kpi_text_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260615_026_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = parent.BASE_NOTIONAL_USD
HOLD_DAYS = parent.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = parent.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = parent.SAME_TICKER_COOLDOWN_DAYS

MIN_PRICE = parent.MIN_PRICE
MIN_AVG_DOLLAR_VOLUME_20D = parent.MIN_AVG_DOLLAR_VOLUME_20D
MIN_T1_RETURN = parent.MIN_T1_RETURN
MIN_T1_EXCESS_SPY = parent.MIN_T1_EXCESS_SPY
MAX_T1_RETURN = parent.MAX_T1_RETURN

SAAS_KPI_PATTERNS = (
    r"\bannual recurring revenue\b",
    r"\barr\b",
    r"\brecurring revenue\b",
    r"\bsubscription revenue\b",
    r"\bproduct revenue\b",
    r"\bcloud revenue\b",
    r"\bsoftware revenue\b",
    r"\bsaas\b",
    r"\bnet revenue retention\b",
    r"\bdollar[- ]based net retention\b",
    r"\bdollar[- ]based retention\b",
    r"\bdbnr\b",
    r"\bdbner\b",
    r"\bnrr\b",
    r"\bgross retention\b",
    r"\bnet retention\b",
    r"\bcustomers?\b[^.]{0,90}\b(?:annual recurring revenue|arr|product revenue|subscription revenue|cloud revenue)\b",
    r"\b(?:annual recurring revenue|arr|product revenue|subscription revenue|cloud revenue)\b[^.]{0,90}\bcustomers?\b",
    r"\blarge customers?\b",
    r"\benterprise customers?\b",
    r"\bnet new customers?\b",
    r"\bcustomer count\b",
)
RPO_PATTERNS = (
    r"\bremaining performance obligations?\b",
    r"\bcurrent rpo\b",
    r"\brpo\b",
)
SAAS_CONTEXT_PATTERNS = (
    r"\bsubscription\b",
    r"\brecurring\b",
    r"\bsoftware\b",
    r"\bcloud\b",
    r"\bsaas\b",
    r"\bcustomers?\b",
)
GROWTH_PATTERNS = (
    r"\bincreas(?:e|ed|ing|es)\b",
    r"\bgrowth\b",
    r"\bgrew\b",
    r"\bup\b",
    r"\brose\b",
    r"\bexpanded\b",
    r"\baccelerat(?:e|ed|ing|ion)\b",
    r"\brecord\b",
    r"\badded\b",
    r"\bnet new\b",
    r"\bcrossed\b",
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
    r"[0-9][0-9,.]*\s*(?:customers|accounts|subscribers|users)",
)
QUALITY_PATTERNS = (
    r"\bnet revenue retention\b",
    r"\bdollar[- ]based net retention\b",
    r"\bdbnr\b",
    r"\bdbner\b",
    r"\bnrr\b",
    r"\bretention rate\b",
    r"\bgross retention\b",
    r"\blarge customers?\b",
    r"\benterprise customers?\b",
    r"\brecord\b",
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
    r"\blower\b",
    r"down\b",
    r"churn",
    r"weak(?:er|ness)?",
    r"soft(?:er|ness)?",
    r"macro",
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
    "success_probability": 0.12,
    "expected_ev_delta": 0.2,
    "expected_pnl_delta": 5000.0,
    "main_failure_modes": [
        "sparse_events",
        "software_concentration",
        "already_priced_by_t1_reaction",
        "accepted_sec_rs20_comparator_not_beaten",
        "late_strong_regression",
    ],
    "confidence_reason": (
        "Generic SEC backlog/RPO text was too sparse and not incremental. SaaS "
        "operating KPIs such as ARR, NRR, product revenue, subscription "
        "revenue, and large-customer growth may carry richer free SEC data "
        "edge, but the sample is likely thin and sector-concentrated."
    ),
    "recorded_at": "2026-06-15T20:18:00+00:00",
}

PRODUCTION_IMPACT = dict(parent.PRODUCTION_IMPACT)
PRODUCTION_IMPACT.update(
    {
        "adapter_status": "private_replay_scout_no_shared_adapter",
        "uses_free_sec_filing_text": True,
        "uses_free_ohlcv": True,
        "parity_note": (
            "This experiment changes no production code. A positive result is "
            "only a replay lead until a shared default-off helper computes the "
            "same SEC financial-report text set, SaaS operating KPI evidence-"
            "span extractor, T+1 reaction gate, liquidity gate, overlap "
            "exclusion, cooldown, next-open paper entry, 10-day exit, costs, "
            "and concentration controls in both historical replay and daily "
            "production."
        ),
    }
)

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: SEC earnings-release text with quantified SaaS/"
        "subscription operating KPI evidence such as ARR, NRR, product "
        "revenue, subscription revenue, RPO, or large-customer growth, "
        "confirmed by T+1 SPY-relative strength, may expand the candidate "
        "pool with better demand-underreaction quality than generic backlog/"
        "RPO text."
    ),
    "2_history_check": {
        "exp-20260615-012": (
            "Generic SEC order/backlog/RPO demand text was rejected; this run "
            "requires SaaS/subscription operating KPI semantics rather than "
            "generic order or contract language."
        ),
        "exp-20260615-013": (
            "Quantified backlog/RPO/book-to-bill growth produced only 3 target "
            "trades and failed sample/comparator gates. This run adds ARR, "
            "NRR, product revenue, subscription revenue, and large-customer "
            "KPI evidence."
        ),
        "exp-20260615-017": (
            "Raw Companyfacts deferred revenue/RPO acceleration was positive "
            "but rejected on late_strong and accepted-comparator gates. This "
            "run uses filing text KPI provenance, not another Companyfacts "
            "concept sweep."
        ),
        "exp-20260615-022": (
            "Selected Companyfacts demand-obligation taxonomy also failed "
            "late_strong and comparator gates; this run tests richer operating "
            "KPI context rather than retuning demand-liability facts."
        ),
        "exp-20260614-015": (
            "Forward-guidance quality text failed; this run requires reported "
            "operating KPI evidence, not guidance language."
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
        "exp_20260615_026_sec_saas_operating_kpi_text.py"
    ),
}


def _hits(text: str, patterns: tuple[str, ...]) -> list[str]:
    return [pattern for pattern in patterns if re.search(pattern, text, flags=re.IGNORECASE)]


def _extract_saas_operating_kpi_spans(row: dict[str, Any]) -> dict[str, Any]:
    text = base._business_text(row)
    spans: list[dict[str, Any]] = []
    kpi_terms: Counter[str] = Counter()
    rpo_terms: Counter[str] = Counter()
    growth_terms: Counter[str] = Counter()
    magnitude_terms: Counter[str] = Counter()
    quality_terms: Counter[str] = Counter()
    context_terms: Counter[str] = Counter()
    rejected_negative_spans = 0
    rejected_unquantified_spans = 0
    rejected_no_growth_spans = 0
    rejected_no_saas_context_spans = 0

    for sentence in base.SENTENCE_SPLIT_RE.split(text):
        cleaned = re.sub(r"\s+", " ", sentence).strip()
        if len(cleaned) < 35:
            continue
        lowered = cleaned.lower()
        kpi_hits = _hits(lowered, SAAS_KPI_PATTERNS)
        rpo_hits = _hits(lowered, RPO_PATTERNS)
        context_hits = _hits(lowered, SAAS_CONTEXT_PATTERNS)
        if not kpi_hits and not (rpo_hits and context_hits):
            if rpo_hits:
                rejected_no_saas_context_spans += 1
            continue
        magnitude_hits = _hits(cleaned, MAGNITUDE_PATTERNS)
        if not magnitude_hits:
            rejected_unquantified_spans += 1
            continue
        growth_hits = _hits(lowered, GROWTH_PATTERNS)
        quality_hits = _hits(lowered, QUALITY_PATTERNS)
        if not growth_hits and not quality_hits:
            rejected_no_growth_spans += 1
            continue
        if _hits(lowered, NEGATIVE_SPAN_PATTERNS):
            rejected_negative_spans += 1
            continue
        for hit in kpi_hits:
            kpi_terms[hit] += 1
        for hit in rpo_hits:
            rpo_terms[hit] += 1
        for hit in growth_hits:
            growth_terms[hit] += 1
        for hit in magnitude_hits:
            magnitude_terms[hit] += 1
        for hit in quality_hits:
            quality_terms[hit] += 1
        for hit in context_hits:
            context_terms[hit] += 1
        spans.append(
            {
                "text": cleaned[:360],
                "saas_kpi_terms": kpi_hits,
                "rpo_terms": rpo_hits,
                "growth_terms": growth_hits,
                "magnitude_terms": magnitude_hits,
                "quality_terms": quality_hits,
                "saas_context_terms": context_hits,
            }
        )
        if len(spans) >= 5:
            break

    return {
        "span_count": len(spans),
        "spans": spans,
        "ai_terms": dict(sorted(kpi_terms.items())),
        "demand_terms": dict(sorted(growth_terms.items())),
        "saas_kpi_terms": dict(sorted(kpi_terms.items())),
        "rpo_terms": dict(sorted(rpo_terms.items())),
        "growth_terms": dict(sorted(growth_terms.items())),
        "magnitude_terms": dict(sorted(magnitude_terms.items())),
        "quality_terms": dict(sorted(quality_terms.items())),
        "saas_context_terms": dict(sorted(context_terms.items())),
        "rejected_negative_spans": rejected_negative_spans,
        "rejected_unquantified_spans": rejected_unquantified_spans,
        "rejected_no_growth_spans": rejected_no_growth_spans,
        "rejected_no_saas_context_spans": rejected_no_saas_context_spans,
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
        "positive_replay_lead_not_promoted_sec_saas_operating_kpi"
        if gate["passed"]
        else "rejected_sec_saas_operating_kpi_candidate_pool"
    )
    gate["accepted_sec_rs20_comparator"] = ACCEPTED_SEC_RS20_COMPARATOR
    return gate


def _rename_evidence(payload: dict[str, Any]) -> None:
    for bucket_name in ("target_trades_by_window", "filtered_candidates_sample_by_window"):
        for rows in (payload.get(bucket_name) or {}).values():
            for row in rows:
                if "ai_demand_evidence" in row:
                    row["saas_operating_kpi_evidence"] = row.pop("ai_demand_evidence")
                if "order_backlog_demand_evidence" in row:
                    row["saas_operating_kpi_evidence"] = row.pop(
                        "order_backlog_demand_evidence"
                    )
    for scan in (payload.get("scan_by_window") or {}).values():
        reject_counts = scan.get("reject_counts") or {}
        if "no_ai_demand_evidence_span" in reject_counts:
            reject_counts["no_saas_operating_kpi_evidence_span"] = reject_counts.pop(
                "no_ai_demand_evidence_span"
            )
        if "no_order_backlog_demand_evidence_span" in reject_counts:
            reject_counts["no_saas_operating_kpi_evidence_span"] = reject_counts.pop(
                "no_order_backlog_demand_evidence_span"
            )


def _build_payload() -> dict[str, Any]:
    payload = ORIGINAL_PARENT_BUILD_PAYLOAD()
    _rename_evidence(payload)
    passed = bool(payload["gate4"]["passed"])
    aggregate = payload["delta_metrics"]["aggregate"]
    reflection = {
        "why_result_happened": (
            "The SEC SaaS/subscription operating KPI evidence source cleared "
            "the private replay gate, but it remains only a lead because no "
            "shared daily/backtest helper exists."
            if passed
            else (
                "The SEC SaaS/subscription operating KPI evidence source did "
                "not clear Gate 4. The likely reason is that ARR, NRR, product "
                "revenue, subscription revenue, RPO, and large-customer "
                "disclosures are too sparse in this archive, too software-"
                "concentrated, overlap the accepted SEC RS20 support field, or "
                "are already priced by the T+1 confirmation before next-open "
                "execution."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping ARR/NRR/product-revenue/RPO term lists, "
            "numeric regexes, SaaS context words, T+1, ADV/price, top-N, "
            "hold-day, cooldown, or notional thresholds on the same frozen "
            "windows."
        ),
        "new_evidence_required": (
            "A valid retry needs materially richer PIT operating KPI "
            "structure, such as KPI type normalization, magnitude versus prior "
            "period, customer-cohort mix, sector-specific baselines, or closed "
            "forward rows from a shared daily helper."
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
            "change_type": "candidate_pool_private_replay_scout",
            "implementation_mode": "private_replay_scout",
            "mechanism_family": "production_visible_free_sec_text_business_kpi_candidate_pool",
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "nearby_prior_experiments": list(PRE_RUN_QUESTIONS["2_history_check"].keys()),
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "sec_text_saas_operating_kpi_numeric_evidence_span",
            "prediction": PREDICTION,
            "calibration": {
                **payload["calibration"],
                "predicted_success_probability": PREDICTION["success_probability"],
                "brier_score": round(
                    (PREDICTION["success_probability"] - (1.0 if passed else 0.0)) ** 2,
                    6,
                ),
            },
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "accepted_sec_rs20_comparator": ACCEPTED_SEC_RS20_COMPARATOR,
            "post_run_reflection": reflection,
            "next_retry_requires": [
                "normalized operating KPI type",
                "magnitude versus prior-period or prior-year KPI baseline",
                "customer-cohort mix and enterprise-customer concentration",
                "shared helper plus daily snapshot parity for any positive replay",
            ],
            "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
            "total_pnl_delta": aggregate["total_pnl_delta_sum"],
            "interpretation": (
                "The SEC SaaS/subscription operating KPI source passed as a "
                "private replay lead only; no production surface was promoted."
                if passed
                else (
                    "The SEC SaaS/subscription operating KPI source did not "
                    "clear Gate 4 and is not promoted."
                )
            ),
            "rejection_reason": None if passed else "; ".join(payload["gate4"]["failed_reasons"]),
            "related_files": [
                base._repo_rel(Path(__file__)),
                base._repo_rel(OUT_JSON),
                base._repo_rel(LOG_JSON),
                base._repo_rel(TICKET_JSON),
                base._repo_rel(CARD_MD),
                base._repo_rel(MANIFEST_JSON),
                base._repo_rel(EXPERIMENT_LOG),
                base._repo_rel(REGISTRY_JSON),
            ],
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "min_t1_return": MIN_T1_RETURN,
        "min_t1_excess_spy": MIN_T1_EXCESS_SPY,
        "max_t1_return": MAX_T1_RETURN,
        "saas_kpi_patterns": SAAS_KPI_PATTERNS,
        "rpo_patterns": RPO_PATTERNS,
        "saas_context_patterns": SAAS_CONTEXT_PATTERNS,
        "growth_patterns": GROWTH_PATTERNS,
        "magnitude_patterns": MAGNITUDE_PATTERNS,
        "quality_patterns": QUALITY_PATTERNS,
        "negative_span_patterns": NEGATIVE_SPAN_PATTERNS,
    }
    payload["backtest_protocol"]["source"] = (
        "docs/backtesting.md canonical three-window core replay plus replay-only "
        "SEC SaaS/subscription operating KPI evidence-span default-off paper overlay"
    )
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    card = ORIGINAL_PARENT_BUILD_CARD(payload)
    card = card.replace(
        "SEC Order/Backlog Demand Evidence Span",
        "SEC SaaS Operating KPI Evidence Span",
    )
    card = card.replace("order/backlog demand", "SaaS/subscription operating KPI")
    card = card.replace("Order/Backlog", "SaaS Operating KPI")
    return card


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = parent.template.ORIGINAL_BUILD_LOG_RECORD(payload)
    record.update(
        {
            "status": payload["status"],
            "decision": payload["decision"],
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "hypothesis": payload["hypothesis"],
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "post_run_reflection": payload["post_run_reflection"],
            "accepted_sec_rs20_comparator": ACCEPTED_SEC_RS20_COMPARATOR,
            "anti_js": "No JavaScript was used.",
        }
    )
    return record


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            base._repo_rel(Path(__file__)),
            base._repo_rel(OUT_JSON),
            base._repo_rel(CARD_MD),
            base._repo_rel(MANIFEST_JSON),
            base._repo_rel(TICKET_JSON),
            base._repo_rel(LOG_JSON),
            base._repo_rel(EXPERIMENT_LOG),
            base._repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            base._repo_rel(Path(__file__)): base._sha256(Path(__file__)),
            base._repo_rel(OUT_JSON): base._sha256(OUT_JSON),
            base._repo_rel(LOG_JSON): base._sha256(LOG_JSON),
            base._repo_rel(TICKET_JSON): base._sha256(TICKET_JSON),
            base._repo_rel(CARD_MD): base._sha256(CARD_MD),
        },
    }
    base._write_json(MANIFEST_JSON, manifest)


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
    parent.ORDER_BACKLOG_PATTERNS = SAAS_KPI_PATTERNS
    parent.CONTRACT_AWARD_PATTERNS = RPO_PATTERNS
    parent.DEMAND_QUALITY_PATTERNS = QUALITY_PATTERNS
    parent.NEGATIVE_SPAN_PATTERNS = NEGATIVE_SPAN_PATTERNS
    parent.ACCEPTED_SEC_RS20_COMPARATOR = ACCEPTED_SEC_RS20_COMPARATOR
    parent.PREDICTION = PREDICTION
    parent.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    parent.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    parent._extract_order_backlog_spans = _extract_saas_operating_kpi_spans
    parent._gate4 = _gate4
    parent._rename_evidence = _rename_evidence
    parent._build_payload = _build_payload
    parent._build_card = _build_card
    parent._build_log_record = _build_log_record
    parent._write_manifest = _write_manifest


def main() -> None:
    _patch_parent()
    # parent.main delegates final registry/ticket persistence through
    # persist_self_registered_result(), not a direct registry write.
    parent.main()


if __name__ == "__main__":
    main()
