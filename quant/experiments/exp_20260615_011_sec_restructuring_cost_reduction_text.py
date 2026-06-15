"""exp-20260615-011: SEC restructuring/cost-reduction evidence-span scout.

Replay-only alpha search. The single decision hypothesis is that PIT SEC
earnings-release text with concrete restructuring, cost-reduction,
expense-savings, or operating-efficiency evidence, confirmed by a positive T+1
SPY-relative reaction, may identify margin-improvement underreaction candidates
for next-open 10-day continuation.

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
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260614_013_sec_ai_demand_evidence_span as base  # noqa: E402


EXPERIMENT_ID = "exp-20260615-011"
STEM = "sec_restructuring_cost_reduction_text"
TRIAL_FAMILY = "sec_restructuring_cost_reduction_evidence_span_candidate_pool"
TRIAL_VARIANT_ID = "sec_restructuring_cost_reduction_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_restructuring_cost_reduction_text_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260615_011_{STEM}.json"
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

COST_REDUCTION_PATTERNS = (
    r"\bcosts?\b[^.]{0,140}\b(?:reduc(?:e|ed|ing|tion|tions)|cut(?:s|ting)?|savings?|discipline|control|controls|optimization|rationalization|efficienc(?:y|ies))\b",
    r"\b(?:reduc(?:e|ed|ing|tion|tions)|cut(?:s|ting)?|savings?|discipline|control|controls|optimization|rationalization|efficienc(?:y|ies))\b[^.]{0,140}\bcosts?\b",
    r"\bexpenses?\b[^.]{0,140}\b(?:reduc(?:e|ed|ing|tion|tions)|declin(?:e|ed|ing)|cut(?:s|ting)?|savings?|discipline|control|controls|optimization|efficienc(?:y|ies))\b",
    r"\b(?:reduc(?:e|ed|ing|tion|tions)|declin(?:e|ed|ing)|cut(?:s|ting)?|savings?|discipline|control|controls|optimization|efficienc(?:y|ies))\b[^.]{0,140}\bexpenses?\b",
    r"\boperating expenses?\b[^.]{0,140}\b(?:down|lower|declin(?:e|ed|ing)|reduc(?:e|ed|ing|tion|tions)|savings?)\b",
    r"\b(?:annualized|run-rate|run rate)\b[^.]{0,120}\b(?:cost|expense)\b[^.]{0,120}\bsavings?\b",
    r"\b(?:cost|expense)\b[^.]{0,120}\b(?:annualized|run-rate|run rate)\b[^.]{0,120}\bsavings?\b",
)
RESTRUCTURING_PATTERNS = (
    r"\brestructur(?:e|ed|ing|ings)?\b",
    r"\brestructuring plan\b",
    r"\brestructuring program\b",
    r"\breorganization\b",
    r"\bstreamlin(?:e|ed|ing)\b",
    r"\bright-?siz(?:e|ed|ing)\b",
    r"\bworkforce reduction\b",
    r"\bheadcount reduction\b",
    r"\bposition reductions?\b",
    r"\blayoffs?\b",
    r"\bproductivity initiatives?\b",
    r"\boperational efficiency\b",
    r"\befficiency initiatives?\b",
    r"\bprofitability initiatives?\b",
    r"\bmargin expansion\b",
)
IMPROVEMENT_QUALITY_PATTERNS = (
    r"\bsavings?\b",
    r"\bannualized\b",
    r"\brun-rate\b",
    r"\brun rate\b",
    r"\bexpected to save\b",
    r"\bon track\b",
    r"\bcompleted\b",
    r"\bimprov(?:e|ed|ing|ement)\b",
    r"\bmargin\b",
    r"\badjusted ebitda\b",
    r"\bprofitability\b",
    r"\bfree cash flow\b",
    r"\bcash flow\b",
)
QUANTIFIED_CONTEXT_RE = re.compile(
    r"(?:\$[0-9][0-9,.]*|[0-9][0-9,.]*\s*(?:million|billion|mm|bn|%)|basis points?|bps|[0-9][0-9,.]*\s*(?:positions|employees|headcount))",
    re.IGNORECASE,
)
NEGATIVE_SPAN_PATTERNS = (
    r"risk factors?",
    r"cautionary",
    r"uncertaint",
    r"adversely",
    r"may not",
    r"could not",
    r"going concern",
    r"substantial doubt",
    r"bankrupt",
    r"default",
    r"delisting",
    r"material weakness",
    r"covenant violation",
    r"liquidity crisis",
)

ACCEPTED_SEC_RS20_COMPARATOR = {
    "experiment_id": "exp-20260614-004",
    "decision": "accepted_default_off_sec_financial_report_rs20_leader_notional_1.15x",
    "aggregate_expected_value_delta": 0.158184,
    "aggregate_pnl_delta": 3235.38,
}

PREDICTION = {
    "success_probability": 0.13,
    "expected_ev_delta": 0.10,
    "expected_pnl_delta": 1800.0,
    "main_failure_modes": [
        "thin_sample",
        "negative_layoff_semantics",
        "generic_restructuring_language",
        "window_regression",
        "drawdown_drift",
        "accepted_sec_rs20_comparator_not_beaten",
    ],
    "confidence_reason": (
        "SEC text is free, PIT, production-visible, and covers all canonical "
        "windows. The mechanism differs from recent Companyfacts/ownership "
        "retunes by targeting disclosed cost-structure repair, but nearby SEC "
        "semantic scouts were often thin or generic."
    ),
    "recorded_at": "2026-06-15T10:06:58+00:00",
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
        "financial-report text set, restructuring/cost-reduction evidence-span "
        "extractor, T+1 reaction gate, liquidity gate, overlap exclusion, "
        "cooldown, next-open paper entry, 10-day exit, costs, and concentration "
        "controls in both historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: PIT SEC earnings-release text with explicit "
        "restructuring, cost-reduction, expense-savings, or operating-efficiency "
        "evidence, confirmed by T+1 SPY-relative strength, may identify "
        "margin-improvement underreaction candidates for next-open 10d paper "
        "continuation."
    ),
    "2_history_check": {
        "exp-20260504-007": (
            "Older SEC filing text language shadow included restructuring-like "
            "keywords but was not this formal three-window candidate-pool replay."
        ),
        "exp-20260504-008": (
            "Older negative-reaction absorption shadow touched SEC text themes; "
            "this run requires positive T+1 confirmation and a concrete "
            "cost-structure evidence span."
        ),
        "exp-20260529-016": (
            "SEC Item 1.01 positive-reaction pool was a contract/agreement item "
            "family, not restructuring/cost-reduction earnings text."
        ),
        "exp-20260603-012": (
            "SEC customer contract business-win candidate pool was rejected; "
            "this run avoids customer/contract relation parsing."
        ),
        "exp-20260614-013": (
            "Rejected AI/data-center demand evidence span after positive but "
            "thin/concentrated results. This run tests cost-structure repair."
        ),
        "exp-20260614-015": (
            "Rejected forward-guidance quality evidence span; this run is not "
            "a guidance-threshold retry."
        ),
        "exp-20260615-001": (
            "Rejected deleveraging/liquidity repair evidence span; this run "
            "targets operating-cost repair instead of balance-sheet repair."
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
        "exp_20260615_011_sec_restructuring_cost_reduction_text.py"
    ),
}


def _pattern_hits(text: str, patterns: tuple[str, ...]) -> list[str]:
    return [pattern for pattern in patterns if re.search(pattern, text, flags=re.IGNORECASE)]


def _extract_restructuring_cost_spans(row: dict[str, Any]) -> dict[str, Any]:
    text = base._business_text(row)
    spans: list[dict[str, Any]] = []
    cost_terms: Counter[str] = Counter()
    restructuring_terms: Counter[str] = Counter()
    improvement_terms: Counter[str] = Counter()
    rejected_negative_spans = 0
    rejected_unqualified_spans = 0
    for sentence in base.SENTENCE_SPLIT_RE.split(text):
        cleaned = re.sub(r"\s+", " ", sentence).strip()
        if len(cleaned) < 35:
            continue
        lowered = cleaned.lower()
        cost_hits = _pattern_hits(lowered, COST_REDUCTION_PATTERNS)
        restructuring_hits = _pattern_hits(lowered, RESTRUCTURING_PATTERNS)
        improvement_hits = _pattern_hits(lowered, IMPROVEMENT_QUALITY_PATTERNS)
        quantified = bool(QUANTIFIED_CONTEXT_RE.search(cleaned))
        passes_cost = bool(cost_hits) and (bool(improvement_hits) or quantified)
        passes_restructuring = bool(restructuring_hits) and (
            bool(cost_hits) or bool(improvement_hits) or quantified
        )
        if not passes_cost and not passes_restructuring:
            if cost_hits or restructuring_hits or improvement_hits:
                rejected_unqualified_spans += 1
            continue
        if _pattern_hits(lowered, NEGATIVE_SPAN_PATTERNS):
            rejected_negative_spans += 1
            continue
        for hit in cost_hits:
            cost_terms[hit] += 1
        for hit in restructuring_hits:
            restructuring_terms[hit] += 1
        for hit in improvement_hits:
            improvement_terms[hit] += 1
        spans.append(
            {
                "text": cleaned[:300],
                "cost_reduction_terms": cost_hits,
                "restructuring_terms": restructuring_hits,
                "improvement_quality_terms": improvement_hits,
                "has_quantified_context": quantified,
            }
        )
        if len(spans) >= 5:
            break
    return {
        "span_count": len(spans),
        "spans": spans,
        "ai_terms": dict(sorted(cost_terms.items())),
        "demand_terms": dict(sorted(restructuring_terms.items())),
        "cost_reduction_terms": dict(sorted(cost_terms.items())),
        "restructuring_terms": dict(sorted(restructuring_terms.items())),
        "improvement_quality_terms": dict(sorted(improvement_terms.items())),
        "rejected_negative_spans": rejected_negative_spans,
        "rejected_unqualified_spans": rejected_unqualified_spans,
    }


ORIGINAL_GATE4 = base._gate4
ORIGINAL_BUILD_PAYLOAD = base._build_payload
ORIGINAL_BUILD_LOG_RECORD = base._build_log_record


def _gate4(*, aggregate: dict[str, Any], target_summary: dict[str, Any], before_metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    gate = ORIGINAL_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    gate["decision"] = (
        "positive_replay_lead_not_promoted_sec_restructuring_cost_reduction"
        if gate["passed"]
        else "rejected_sec_restructuring_cost_reduction_candidate_pool"
    )
    gate["accepted_sec_rs20_comparator"] = ACCEPTED_SEC_RS20_COMPARATOR
    return gate


def _rename_evidence(payload: dict[str, Any]) -> None:
    for bucket_name in ("target_trades_by_window", "filtered_candidates_sample_by_window"):
        for rows in (payload.get(bucket_name) or {}).values():
            for row in rows:
                if "ai_demand_evidence" in row:
                    row["restructuring_cost_reduction_evidence"] = row.pop(
                        "ai_demand_evidence"
                    )
    for scan in (payload.get("scan_by_window") or {}).values():
        reject_counts = scan.get("reject_counts") or {}
        if "no_ai_demand_evidence_span" in reject_counts:
            reject_counts["no_restructuring_cost_reduction_evidence_span"] = (
                reject_counts.pop("no_ai_demand_evidence_span")
            )


def _build_payload() -> dict[str, Any]:
    payload = ORIGINAL_BUILD_PAYLOAD()
    _rename_evidence(payload)
    if payload.get("gate3"):
        payload["gate3"]["note"] = (
            "No new core filter or entry rule was added. The SEC restructuring/"
            "cost-reduction evidence-span candidate source is additive "
            "default-off paper, so core signals generated/survived are "
            "unchanged from baseline."
        )
    passed = bool(payload["gate4"]["passed"])
    aggregate = payload["delta_metrics"]["aggregate"]
    reflection = {
        "why_result_happened": (
            "The SEC restructuring/cost-reduction evidence-span rule found "
            "enough replacement value to clear the private replay gate, but it "
            "remains only a lead because no shared daily/backtest helper exists."
            if passed
            else (
                "The SEC restructuring/cost-reduction evidence-span rule did "
                "not clear Gate 4. The likely reason is that restructuring and "
                "cost-discipline language is either lagging/internal clean-up "
                "rather than forward demand, already captured by accepted SEC "
                "RS20 support, or too noisy after positive T+1 confirmation, "
                "next-open execution, costs, cooldown, and concentration guards."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping restructuring, workforce-reduction, "
            "cost-savings, T+1, ADV/price, top-N, hold-day, cooldown, or "
            "notional thresholds on the same frozen windows."
        ),
        "new_evidence_required": (
            "A valid retry needs materially richer PIT semantic provenance, "
            "such as quantified cost-savings versus revenue base, recurring "
            "expense run-rate changes, restructuring completion stage, or "
            "forward margin bridge extraction from the filing text."
        ),
    }
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "positive_replay_lead_not_promoted" if passed else "rejected",
            "decision": payload["gate4"]["decision"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "candidate_pool_private_replay_scout",
            "implementation_mode": "private_replay_scout",
            "mechanism_family": "production_visible_free_sec_text_evidence_span_candidate_pool",
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "nearby_prior_experiments": list(PRE_RUN_QUESTIONS["2_history_check"].keys()),
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "sec_text_restructuring_cost_reduction_evidence_span",
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
                "cost-savings versus revenue-base extraction",
                "recurring expense run-rate delta extraction",
                "shared helper plus daily snapshot parity for any positive replay",
            ],
            "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
            "total_pnl_delta": aggregate["total_pnl_delta_sum"],
            "interpretation": (
                "The SEC restructuring/cost-reduction evidence-span source "
                "passed as a private replay lead only; no production surface "
                "was promoted."
                if passed
                else (
                    "The SEC restructuring/cost-reduction evidence-span source "
                    "did not clear Gate 4 and is not promoted."
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
        "cost_reduction_patterns": COST_REDUCTION_PATTERNS,
        "restructuring_patterns": RESTRUCTURING_PATTERNS,
        "improvement_quality_patterns": IMPROVEMENT_QUALITY_PATTERNS,
        "quantified_context_pattern": QUANTIFIED_CONTEXT_RE.pattern,
        "negative_span_patterns": NEGATIVE_SPAN_PATTERNS,
    }
    payload["backtest_protocol"]["source"] = (
        "docs/backtesting.md canonical three-window core replay plus "
        "replay-only SEC restructuring/cost-reduction evidence-span "
        "default-off paper overlay"
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
            f"# {EXPERIMENT_ID} SEC Restructuring/Cost-Reduction Evidence Span",
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
    record = ORIGINAL_BUILD_LOG_RECORD(payload)
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


def _patch_base() -> None:
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
    base.MIN_PRICE = MIN_PRICE
    base.MIN_AVG_DOLLAR_VOLUME_20D = MIN_AVG_DOLLAR_VOLUME_20D
    base.MIN_T1_RETURN = MIN_T1_RETURN
    base.MIN_T1_EXCESS_SPY = MIN_T1_EXCESS_SPY
    base.MAX_T1_RETURN = MAX_T1_RETURN
    base.AI_PATTERNS = COST_REDUCTION_PATTERNS
    base.DEMAND_PATTERNS = RESTRUCTURING_PATTERNS
    base.NEGATIVE_SPAN_PATTERNS = NEGATIVE_SPAN_PATTERNS
    base.ACCEPTED_SEC_RS20_COMPARATOR = ACCEPTED_SEC_RS20_COMPARATOR
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    base._extract_ai_demand_spans = _extract_restructuring_cost_spans
    base._gate4 = _gate4
    base._build_payload = _build_payload
    base._build_card = _build_card
    base._build_log_record = _build_log_record
    base._write_manifest = _write_manifest
    base._configure_sleeve_globals()


def main() -> None:
    _patch_base()
    # base.persist delegates registry/ticket writes to persist_self_registered_result().
    base.main()


if __name__ == "__main__":
    main()
