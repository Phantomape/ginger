"""exp-20260615-012: SEC order/backlog demand evidence-span scout.

Replay-only alpha search. The single decision hypothesis is that PIT SEC
earnings-release text with concrete order backlog, bookings, contract-award,
or remaining-performance-obligation evidence, confirmed by a positive T+1
SPY-relative reaction, may identify demand-confirmation underreaction
candidates for next-open 10-day continuation.

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

import exp_20260615_011_sec_restructuring_cost_reduction_text as template  # noqa: E402


base = template.base

EXPERIMENT_ID = "exp-20260615-012"
STEM = "sec_order_backlog_demand_text"
TRIAL_FAMILY = "sec_order_backlog_demand_evidence_span_candidate_pool"
TRIAL_VARIANT_ID = "sec_order_backlog_demand_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_order_backlog_demand_text_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260615_012_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 10

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_T1_RETURN = 0.0
MIN_T1_EXCESS_SPY = 0.006
MAX_T1_RETURN = 0.16

ORDER_BACKLOG_PATTERNS = (
    r"\border backlog\b",
    r"\bbacklog\b",
    r"\bbookings?\b",
    r"\bbook[- ]to[- ]bill\b",
    r"\border book\b",
    r"\bcustomer orders?\b",
    r"\bpurchase orders?\b",
    r"\bremaining performance obligations?\b",
    r"\brpo\b",
    r"\bcontracted backlog\b",
    r"\bcontracted revenue\b",
)
CONTRACT_AWARD_PATTERNS = (
    r"\bcontract awards?\b",
    r"\bawarded\b[^.]{0,80}\bcontract\b",
    r"\bwon\b[^.]{0,80}\bcontract\b",
    r"\bnew contract\b",
    r"\bmulti[- ]year\b[^.]{0,80}\b(?:contract|agreement|award)\b",
    r"\blong[- ]term\b[^.]{0,80}\b(?:contract|agreement)\b",
    r"\bcustomer wins?\b",
    r"\bnew customer\b",
    r"\bexpanded\b[^.]{0,80}\b(?:contract|agreement|relationship)\b",
)
DEMAND_QUALITY_PATTERNS = (
    r"\brecord\b",
    r"\bincreas(?:e|ed|ing)\b",
    r"\bgrowth\b",
    r"\bgrew\b",
    r"\bstrong\b",
    r"\bvisibility\b",
    r"\bfunded\b",
    r"\bcommitted\b",
    r"\bproduction\b",
    r"\bdeliver(?:y|ies|ed)?\b",
    r"\brevenue visibility\b",
    r"\bdemand\b",
)
QUANTIFIED_CONTEXT_RE = re.compile(
    r"(?:\$[0-9][0-9,.]*|[0-9][0-9,.]*\s*(?:million|billion|mm|bn|%)|"
    r"[0-9]+(?:\.[0-9]+)?x|[0-9][0-9,.]*\s*(?:units|systems|vehicles|orders|customers))",
    re.IGNORECASE,
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
    "success_probability": 0.16,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "thin_sample",
        "generic_contract_language",
        "accepted_sec_rs20_comparator_not_beaten",
        "window_regression",
        "drawdown_drift",
    ],
    "confidence_reason": (
        "Free PIT SEC text can expose concrete demand confirmation that is "
        "distinct from recent Companyfacts quality, cost-reduction, guidance, "
        "and AI-topic text attempts. The main risk is that contract/backlog "
        "language is sparse, already priced by T+1, or fails the accepted SEC "
        "RS20 comparator after next-open execution and costs."
    ),
    "recorded_at": "2026-06-15T11:06:24+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": False,
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
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": {
        "trade_enabled": False,
        "target_notional_per_paper_trade": BASE_NOTIONAL_USD,
        "daily_entry_slots": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "hold_days": HOLD_DAYS,
        "liquidity_source": "price >= $10 and ADV20 >= $50M from PIT OHLCV",
        "order_semantics": "observe-only next-session-open paper entry; no broker order",
        "portfolio_displacement": "none unless a later shared helper and activation gate pass",
        "kill_switch": "trade_enabled remains false; no production adapter changes",
        "failure_handling": "missing SEC text, evidence span, OHLCV, next open, or 10d exit rejects the paper candidate",
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same SEC "
        "financial-report text set, order/backlog demand evidence-span "
        "extractor, T+1 reaction gate, liquidity gate, overlap exclusion, "
        "cooldown, next-open paper entry, 10-day exit, costs, and concentration "
        "controls in both historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: SEC earnings-release text with concrete backlog, "
        "bookings, contract-award, customer-order, or RPO evidence, confirmed "
        "by T+1 SPY-relative strength, may identify demand-confirmation "
        "underreaction candidates for next-open 10d paper continuation."
    ),
    "2_history_check": {
        "exp-20260603-012": (
            "SEC customer contract business-win candidate pool was rejected; "
            "this run requires earnings-release demand evidence plus T+1 "
            "confirmation rather than broad customer-contract item parsing."
        ),
        "exp-20260614-004": (
            "Accepted SEC financial-report RS20 notional support is the "
            "binding SEC comparator; this scout must beat EV +0.158184 and "
            "PnL +$3,235.38 before it matters."
        ),
        "exp-20260614-013": (
            "Rejected AI/data-center demand evidence span after positive but "
            "thin/concentrated results. This run tests orders/backlog demand "
            "evidence, not AI topic demand."
        ),
        "exp-20260614-015": (
            "Rejected forward-guidance quality evidence span; this run is not "
            "a guidance-threshold retry."
        ),
        "exp-20260615-011": (
            "Rejected restructuring/cost-reduction evidence span; this run "
            "targets externally validated demand rather than internal cost "
            "repair language."
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
        "exp_20260615_012_sec_order_backlog_demand_text.py"
    ),
}


def _pattern_hits(text: str, patterns: tuple[str, ...]) -> list[str]:
    return [pattern for pattern in patterns if re.search(pattern, text, flags=re.IGNORECASE)]


def _extract_order_backlog_spans(row: dict[str, Any]) -> dict[str, Any]:
    text = base._business_text(row)
    spans: list[dict[str, Any]] = []
    order_terms: Counter[str] = Counter()
    contract_terms: Counter[str] = Counter()
    quality_terms: Counter[str] = Counter()
    rejected_negative_spans = 0
    rejected_unqualified_spans = 0
    for sentence in base.SENTENCE_SPLIT_RE.split(text):
        cleaned = re.sub(r"\s+", " ", sentence).strip()
        if len(cleaned) < 35:
            continue
        lowered = cleaned.lower()
        order_hits = _pattern_hits(lowered, ORDER_BACKLOG_PATTERNS)
        contract_hits = _pattern_hits(lowered, CONTRACT_AWARD_PATTERNS)
        quality_hits = _pattern_hits(lowered, DEMAND_QUALITY_PATTERNS)
        quantified = bool(QUANTIFIED_CONTEXT_RE.search(cleaned))
        passes_order = bool(order_hits) and (bool(quality_hits) or quantified)
        passes_contract = bool(contract_hits) and (bool(quality_hits) and quantified)
        if not passes_order and not passes_contract:
            if order_hits or contract_hits or quality_hits:
                rejected_unqualified_spans += 1
            continue
        if _pattern_hits(lowered, NEGATIVE_SPAN_PATTERNS):
            rejected_negative_spans += 1
            continue
        for hit in order_hits:
            order_terms[hit] += 1
        for hit in contract_hits:
            contract_terms[hit] += 1
        for hit in quality_hits:
            quality_terms[hit] += 1
        spans.append(
            {
                "text": cleaned[:300],
                "order_backlog_terms": order_hits,
                "contract_award_terms": contract_hits,
                "demand_quality_terms": quality_hits,
                "has_quantified_context": quantified,
            }
        )
        if len(spans) >= 5:
            break
    return {
        "span_count": len(spans),
        "spans": spans,
        "ai_terms": dict(sorted(order_terms.items())),
        "demand_terms": dict(sorted(contract_terms.items())),
        "order_backlog_terms": dict(sorted(order_terms.items())),
        "contract_award_terms": dict(sorted(contract_terms.items())),
        "demand_quality_terms": dict(sorted(quality_terms.items())),
        "rejected_negative_spans": rejected_negative_spans,
        "rejected_unqualified_spans": rejected_unqualified_spans,
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = template.ORIGINAL_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    gate["decision"] = (
        "positive_replay_lead_not_promoted_sec_order_backlog_demand"
        if gate["passed"]
        else "rejected_sec_order_backlog_demand_candidate_pool"
    )
    gate["accepted_sec_rs20_comparator"] = ACCEPTED_SEC_RS20_COMPARATOR
    return gate


def _rename_evidence(payload: dict[str, Any]) -> None:
    for bucket_name in ("target_trades_by_window", "filtered_candidates_sample_by_window"):
        for rows in (payload.get(bucket_name) or {}).values():
            for row in rows:
                if "ai_demand_evidence" in row:
                    row["order_backlog_demand_evidence"] = row.pop("ai_demand_evidence")
    for scan in (payload.get("scan_by_window") or {}).values():
        reject_counts = scan.get("reject_counts") or {}
        if "no_ai_demand_evidence_span" in reject_counts:
            reject_counts["no_order_backlog_demand_evidence_span"] = reject_counts.pop(
                "no_ai_demand_evidence_span"
            )


def _build_payload() -> dict[str, Any]:
    payload = template.ORIGINAL_BUILD_PAYLOAD()
    _rename_evidence(payload)
    passed = bool(payload["gate4"]["passed"])
    aggregate = payload["delta_metrics"]["aggregate"]
    reflection = {
        "why_result_happened": (
            "The SEC order/backlog demand evidence-span rule found enough "
            "replacement value to clear the private replay gate, but it remains "
            "only a lead because no shared daily/backtest helper exists."
            if passed
            else (
                "The SEC order/backlog demand evidence-span rule did not clear "
                "Gate 4. The likely reason is that backlog, bookings, contract "
                "award, and RPO language is either sparse, already reflected in "
                "the T+1 reaction, too generic across earnings releases, or "
                "not incremental to accepted SEC RS20 support after next-open "
                "execution, costs, cooldown, and concentration controls."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping backlog, bookings, contract-award, RPO, "
            "T+1, ADV/price, top-N, hold-day, cooldown, or notional thresholds "
            "on the same frozen windows."
        ),
        "new_evidence_required": (
            "A valid retry needs materially richer PIT semantic provenance, "
            "such as extracted backlog growth rate, book-to-bill magnitude, "
            "contract duration/funding certainty, named customer importance, "
            "or forward replacement-value rows from a shared daily helper."
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
            "mechanism_family": "production_visible_free_sec_text_evidence_span_candidate_pool",
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "nearby_prior_experiments": list(PRE_RUN_QUESTIONS["2_history_check"].keys()),
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "sec_text_order_backlog_demand_evidence_span",
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
                "materially richer PIT semantic provenance",
                "backlog growth or book-to-bill magnitude extraction",
                "contract duration and funding certainty extraction",
                "shared helper plus daily snapshot parity for any positive replay",
            ],
            "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
            "total_pnl_delta": aggregate["total_pnl_delta_sum"],
            "interpretation": (
                "The SEC order/backlog demand evidence-span source passed as a "
                "private replay lead only; no production surface was promoted."
                if passed
                else (
                    "The SEC order/backlog demand evidence-span source did not "
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
    if payload.get("gate3"):
        payload["gate3"]["note"] = (
            "No new core filter or entry rule was added. The SEC order/backlog "
            "demand evidence-span candidate source is additive default-off "
            "paper, so core signals generated/survived are unchanged from "
            "baseline."
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
        "order_backlog_patterns": ORDER_BACKLOG_PATTERNS,
        "contract_award_patterns": CONTRACT_AWARD_PATTERNS,
        "demand_quality_patterns": DEMAND_QUALITY_PATTERNS,
        "quantified_context_pattern": QUANTIFIED_CONTEXT_RE.pattern,
        "negative_span_patterns": NEGATIVE_SPAN_PATTERNS,
    }
    payload["backtest_protocol"]["source"] = (
        "docs/backtesting.md canonical three-window core replay plus "
        "replay-only SEC order/backlog demand evidence-span default-off paper "
        "overlay"
    )
    payload["backtest_protocol"]["execution_model"] = (
        "SEC text and close-of-day OHLCV are known by signal date. Signal date "
        "is the first post-event T+1 close. Paper entry is next available open "
        "with existing entry slippage; exit is the close 10 trading days after "
        "signal with target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Raw candidates | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {raw} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                raw=payload["raw_candidate_counts"][label],
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} SEC Order/Backlog Demand Evidence Span",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## History Check",
            "",
            json.dumps(PRE_RUN_QUESTIONS["2_history_check"], ensure_ascii=True, indent=2),
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Production Impact",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = template.ORIGINAL_BUILD_LOG_RECORD(payload)
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


def _patch_template() -> None:
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
    template.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    template.HOLD_DAYS = HOLD_DAYS
    template.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    template.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    template.MIN_PRICE = MIN_PRICE
    template.MIN_AVG_DOLLAR_VOLUME_20D = MIN_AVG_DOLLAR_VOLUME_20D
    template.MIN_T1_RETURN = MIN_T1_RETURN
    template.MIN_T1_EXCESS_SPY = MIN_T1_EXCESS_SPY
    template.MAX_T1_RETURN = MAX_T1_RETURN
    template.COST_REDUCTION_PATTERNS = ORDER_BACKLOG_PATTERNS
    template.RESTRUCTURING_PATTERNS = CONTRACT_AWARD_PATTERNS
    template.IMPROVEMENT_QUALITY_PATTERNS = DEMAND_QUALITY_PATTERNS
    template.NEGATIVE_SPAN_PATTERNS = NEGATIVE_SPAN_PATTERNS
    template.ACCEPTED_SEC_RS20_COMPARATOR = ACCEPTED_SEC_RS20_COMPARATOR
    template.PREDICTION = PREDICTION
    template.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    template.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    template._extract_restructuring_cost_spans = _extract_order_backlog_spans
    template._gate4 = _gate4
    template._build_payload = _build_payload
    template._build_card = _build_card
    template._build_log_record = _build_log_record
    template._write_manifest = _write_manifest


def main() -> None:
    _patch_template()
    # template.main delegates final registry/ticket persistence through
    # persist_self_registered_result(), not a direct registry write.
    template.main()


if __name__ == "__main__":
    main()
