"""exp-20260614-015: SEC forward-guidance quality evidence-span scout.

Replay-only alpha search. The single decision hypothesis is that SEC
earnings-release text with quantified forward guidance plus operating leverage
or free-cash-flow quality evidence, confirmed by T+1 SPY-relative strength,
may identify business-quality underreaction candidates.

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


EXPERIMENT_ID = "exp-20260614-015"
STEM = "sec_forward_guidance_quality_evidence_span"
TRIAL_FAMILY = "sec_forward_guidance_quality_evidence_span_candidate_pool"
TRIAL_VARIANT_ID = "sec_forward_guidance_quality_evidence_span_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_forward_guidance_quality_evidence_span_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260614_015_{STEM}.json"
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

GUIDANCE_PATTERNS = (
    r"guidance",
    r"outlook",
    r"expect(?:s|ed|ing)?",
    r"forecast",
    r"project(?:s|ed|ion)?",
    r"raise[sd]?",
    r"full[- ]year",
    r"fiscal year",
    r"next quarter",
    r"revenue guidance",
    r"operating income guidance",
    r"adjusted ebitda guidance",
)
ACCELERATION_PATTERNS = (
    r"accelerat(?:e|ed|ing|ion)",
    r"increas(?:e|ed|ing)",
    r"growth",
    r"grew",
    r"record",
    r"expand(?:ed|ing|sion)?",
    r"above (?:our )?forecast",
    r"strong",
)
QUALITY_PATTERNS = (
    r"operating margin",
    r"operating income",
    r"operating leverage",
    r"adjusted ebitda",
    r"free cash flow",
    r"cash flow from operations",
    r"gross margin",
    r"margin expansion",
    r"profitability",
)
NEGATIVE_SPAN_PATTERNS = (
    r"risk factors?",
    r"cautionary",
    r"uncertaint",
    r"adversely",
    r"may not",
    r"could not",
    r"declin(?:e|ed|ing)",
)

ACCEPTED_SEC_RS20_COMPARATOR = {
    "experiment_id": "exp-20260614-004",
    "decision": "accepted_default_off_sec_financial_report_rs20_leader_notional_1.15x",
    "aggregate_expected_value_delta": 0.158184,
    "aggregate_pnl_delta": 3235.38,
}

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "thin_sample",
        "accepted_sec_rs20_comparator_not_beaten",
        "window_regression",
        "concentration_failed",
        "generic_positive_earnings_language",
    ],
    "confidence_reason": (
        "Mechanism: forward guidance plus operating leverage and cash-flow "
        "quality is a richer SEC evidence-span field than generic filing "
        "labels or AI keyword demand. Nearby SEC text and allocator tests "
        "mostly failed, and exp-20260614-013 was thin, so this remains a "
        "private replay scout only."
    ),
    "recorded_at": "2026-06-14T14:06:14+00:00",
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
        "financial-report text set, guidance-quality evidence-span extractor, "
        "T+1 reaction gate, liquidity gate, overlap exclusion, cooldown, "
        "next-open paper entry, 10-day exit, costs, and concentration controls "
        "in both historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: SEC earnings-release text with quantified forward "
        "guidance plus operating leverage or free-cash-flow quality evidence, "
        "confirmed by T+1 SPY-relative strength, may identify business-quality "
        "underreaction candidates for next-open 10d paper continuation."
    ),
    "2_history_check": {
        "exp-20260614-004": (
            "Accepted SEC financial-report RS20 notional support is the "
            "binding SEC comparator; this scout must beat EV +0.158184 and "
            "PnL +$3,235.38 before it matters."
        ),
        "exp-20260614-009": (
            "Rejected SEC financial-report T+1 drift as an allocator source; "
            "this run does not alter the accepted allocator."
        ),
        "exp-20260614-013": (
            "Rejected AI/data-center demand evidence span after positive but "
            "thin and concentrated results. This run tests guidance and "
            "operating-quality spans, not AI topic demand."
        ),
        "exp-20260610-024": (
            "Rejected earnings filing-cadence surprise; this run uses richer "
            "filing text evidence rather than cadence/timing."
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
        "exp_20260614_015_sec_forward_guidance_quality_evidence_span.py"
    ),
}


def _pattern_hits(text: str, patterns: tuple[str, ...]) -> list[str]:
    return [pattern for pattern in patterns if re.search(pattern, text, flags=re.IGNORECASE)]


def _extract_guidance_quality_spans(row: dict[str, Any]) -> dict[str, Any]:
    text = base._business_text(row)
    spans: list[dict[str, Any]] = []
    guidance_terms: Counter[str] = Counter()
    acceleration_terms: Counter[str] = Counter()
    quality_terms: Counter[str] = Counter()
    rejected_negative_spans = 0
    for sentence in base.SENTENCE_SPLIT_RE.split(text):
        cleaned = re.sub(r"\s+", " ", sentence).strip()
        if len(cleaned) < 35:
            continue
        lowered = cleaned.lower()
        guidance_hits = _pattern_hits(lowered, GUIDANCE_PATTERNS)
        acceleration_hits = _pattern_hits(lowered, ACCELERATION_PATTERNS)
        quality_hits = _pattern_hits(lowered, QUALITY_PATTERNS)
        if not guidance_hits or not acceleration_hits or not quality_hits:
            continue
        if _pattern_hits(lowered, NEGATIVE_SPAN_PATTERNS):
            rejected_negative_spans += 1
            continue
        for hit in guidance_hits:
            guidance_terms[hit] += 1
        for hit in acceleration_hits:
            acceleration_terms[hit] += 1
        for hit in quality_hits:
            quality_terms[hit] += 1
        spans.append(
            {
                "text": cleaned[:300],
                "guidance_terms": guidance_hits,
                "acceleration_terms": acceleration_hits,
                "quality_terms": quality_hits,
            }
        )
        if len(spans) >= 5:
            break
    return {
        "span_count": len(spans),
        "spans": spans,
        "ai_terms": dict(sorted(guidance_terms.items())),
        "demand_terms": dict(sorted(quality_terms.items())),
        "guidance_terms": dict(sorted(guidance_terms.items())),
        "acceleration_terms": dict(sorted(acceleration_terms.items())),
        "quality_terms": dict(sorted(quality_terms.items())),
        "rejected_negative_spans": rejected_negative_spans,
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
        "positive_replay_lead_not_promoted_sec_forward_guidance_quality_evidence_span"
        if gate["passed"]
        else "rejected_sec_forward_guidance_quality_evidence_span_candidate_pool"
    )
    gate["accepted_sec_rs20_comparator"] = ACCEPTED_SEC_RS20_COMPARATOR
    return gate


def _build_payload() -> dict[str, Any]:
    payload = ORIGINAL_BUILD_PAYLOAD()
    for bucket_name in ("target_trades_by_window", "filtered_candidates_sample_by_window"):
        for rows in (payload.get(bucket_name) or {}).values():
            for row in rows:
                if "ai_demand_evidence" in row:
                    row["guidance_quality_evidence"] = row.pop("ai_demand_evidence")
    passed = bool(payload["gate4"]["passed"])
    aggregate = payload["delta_metrics"]["aggregate"]
    reflection = {
        "why_result_happened": (
            "The forward-guidance quality evidence-span rule found enough "
            "replacement value to clear the private replay gate, but it remains "
            "only a lead because no shared daily/backtest helper exists."
            if passed
            else (
                "The forward-guidance quality evidence-span rule did not clear "
                "Gate 4. The likely reason is that positive guidance and margin/"
                "cash-flow language is either already captured by the accepted "
                "SEC RS20 support field or too generic after T+1 confirmation, "
                "next-open execution, costs, cooldown, and concentration guards."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping guidance, acceleration, quality, T+1, "
            "ADV/price, top-N, hold-day, cooldown, or notional thresholds on "
            "the same frozen windows."
        ),
        "new_evidence_required": (
            "A valid retry needs materially richer PIT semantic provenance, "
            "such as extracted numeric guidance deltas versus prior guidance, "
            "segment revenue deltas, analyst breadth/dispersion, or closed "
            "forward replacement-value rows from a shared daily helper."
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
            "nearby_prior_experiments": [
                "exp-20260614-004",
                "exp-20260614-009",
                "exp-20260614-013",
                "exp-20260610-024",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "sec_text_forward_guidance_operating_quality_evidence_span",
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
                "numeric guidance deltas versus prior guidance",
                "closed forward replacement-value rows",
                "shared helper plus daily snapshot parity for any positive replay",
            ],
            "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
            "total_pnl_delta": aggregate["total_pnl_delta_sum"],
            "interpretation": (
                "The SEC forward-guidance quality evidence-span source passed "
                "as a private replay lead only; no production surface was "
                "promoted."
                if passed
                else (
                    "The SEC forward-guidance quality evidence-span source did "
                    "not clear Gate 4 and is not promoted."
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
        "guidance_patterns": GUIDANCE_PATTERNS,
        "acceleration_patterns": ACCELERATION_PATTERNS,
        "quality_patterns": QUALITY_PATTERNS,
        "negative_span_patterns": NEGATIVE_SPAN_PATTERNS,
    }
    payload["backtest_protocol"]["source"] = (
        "docs/backtesting.md canonical three-window core replay plus "
        "replay-only SEC forward-guidance quality evidence-span default-off "
        "paper overlay"
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
            f"# {EXPERIMENT_ID} SEC Forward-Guidance Quality Evidence Span",
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
    base.AI_PATTERNS = GUIDANCE_PATTERNS
    base.DEMAND_PATTERNS = QUALITY_PATTERNS
    base.NEGATIVE_SPAN_PATTERNS = NEGATIVE_SPAN_PATTERNS
    base.ACCEPTED_SEC_RS20_COMPARATOR = ACCEPTED_SEC_RS20_COMPARATOR
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    base._extract_ai_demand_spans = _extract_guidance_quality_spans
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
