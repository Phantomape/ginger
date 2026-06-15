"""exp-20260615-029: SEC named-counterparty contract economics scout.

Replay-only alpha search. The single decision hypothesis is that PIT SEC
earnings-release text with a named public customer, supplier, or platform
partner, concrete contract/revenue/customer-growth economics, issuer T+1
strength, and counterparty strength can isolate relation-backed demand
underreaction better than generic SEC demand text.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive result is
only a replay lead until a shared historical/daily helper reproduces it.
No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter
from datetime import datetime, timezone
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


ORIGINAL_BUILD_PAYLOAD = base._build_payload
ORIGINAL_BUILD_CARD = base._build_card
ORIGINAL_BUILD_LOG_RECORD = base._build_log_record
ORIGINAL_CANDIDATE_FROM_TEXT_ROW = base._candidate_from_text_row
ORIGINAL_GATE4 = base._gate4

EXPERIMENT_ID = "exp-20260615-029"
STEM = "sec_named_counterparty_contract_economics"
TRIAL_FAMILY = "sec_named_counterparty_contract_economics_candidate_pool"
TRIAL_VARIANT_ID = "sec_named_counterparty_contract_economics_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_named_counterparty_contract_economics_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260615_029_{STEM}.json"
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

MIN_COUNTERPARTY_RET20_EXCESS_SPY = 0.0
COUNTERPARTY_LOOKBACK_DAYS = 20
COUNTERPARTY_MA_DAYS = 50

ACCEPTED_SEC_RS20_COMPARATOR = {
    "experiment_id": "exp-20260614-004",
    "decision": "accepted_default_off_sec_financial_report_rs20_leader_notional_1.15x",
    "aggregate_expected_value_delta": 0.158184,
    "aggregate_pnl_delta": 3235.38,
}

COUNTERPARTIES = (
    ("AMZN", "Amazon/AWS", (r"\bamazon\b", r"\baws\b", r"\bamazon web services\b")),
    ("MSFT", "Microsoft/Azure", (r"\bmicrosoft\b", r"\bazure\b")),
    ("GOOG", "Alphabet/Google", (r"\balphabet\b", r"\bgoogle\b", r"\bgoogle cloud\b")),
    ("NVDA", "NVIDIA", (r"\bnvidia\b", r"\bgpu\b", r"\bnvidia ai\b")),
    ("AVGO", "Broadcom", (r"\bbroadcom\b",)),
    ("AAPL", "Apple", (r"\bapple\b", r"\bios\b", r"\bapp store\b")),
    ("META", "Meta", (r"\bmeta\b", r"\bfacebook\b", r"\binstagram\b")),
    ("ORCL", "Oracle", (r"\boracle\b", r"\boci\b", r"\boracle cloud\b")),
    ("CRM", "Salesforce", (r"\bsalesforce\b", r"\bslack\b")),
    ("NOW", "ServiceNow", (r"\bservicenow\b",)),
    ("TSLA", "Tesla", (r"\btesla\b",)),
    ("WMT", "Walmart", (r"\bwalmart\b",)),
    ("TGT", "Target", (r"\btarget\b",)),
    ("JPM", "JPMorgan", (r"\bjpmorgan\b", r"\bjpmorgan chase\b")),
    ("V", "Visa", (r"\bvisa\b",)),
    ("MA", "Mastercard", (r"\bmastercard\b",)),
    ("XOM", "Exxon Mobil", (r"\bexxon\b", r"\bexxonmobil\b")),
    ("CVX", "Chevron", (r"\bchevron\b",)),
    ("BA", "Boeing", (r"\bboeing\b",)),
    ("LMT", "Lockheed Martin", (r"\blockheed\b", r"\blockheed martin\b")),
    ("RTX", "RTX", (r"\brtx\b", r"\braytheon\b", r"\bcollins aerospace\b")),
    ("PLTR", "Palantir", (r"\bpalantir\b",)),
    ("SNOW", "Snowflake", (r"\bsnowflake\b",)),
    ("DDOG", "Datadog", (r"\bdatadog\b",)),
)

RELATION_PATTERNS = (
    r"\bcustomers?\b",
    r"\bpartners?(?:hip)?\b",
    r"\bsuppliers?\b",
    r"\bvendors?\b",
    r"\bagreements?\b",
    r"\bcontracts?\b",
    r"\bcollaboration\b",
    r"\balliance\b",
    r"\bplatform\b",
    r"\bcloud\b",
    r"\bintegrat(?:e|ed|ion)\b",
    r"\bmarketplace\b",
)
ECONOMIC_PATTERNS = (
    r"\brevenue\b",
    r"\bsales\b",
    r"\bdemand\b",
    r"\borders?\b",
    r"\bbookings?\b",
    r"\bbacklog\b",
    r"\bremaining performance obligations?\b",
    r"\brpo\b",
    r"\bsubscription\b",
    r"\bproduct revenue\b",
    r"\bcustomer growth\b",
    r"\blarge customers?\b",
    r"\benterprise customers?\b",
    r"\bdeployment\b",
    r"\badoption\b",
)
QUALITY_PATTERNS = (
    r"\bgrowth\b",
    r"\bgrew\b",
    r"\bincreas(?:e|ed|ing|es)\b",
    r"\bexpanded\b",
    r"\baccelerat(?:e|ed|ion|ing)\b",
    r"\bnew\b",
    r"\bnet new\b",
    r"\brecord\b",
    r"\bmulti[- ]year\b",
    r"\blong[- ]term\b",
    r"\bstrategic\b",
    r"\bfunded\b",
    r"\bcommitted\b",
)
MAGNITUDE_PATTERNS = (
    r"\$[0-9][0-9,.]*\s*(?:million|billion|mm|bn)?",
    r"[0-9]+(?:\.[0-9]+)?\s*%",
    r"[0-9]+(?:\.[0-9]+)?\s*percent",
    r"[0-9]+(?:\.[0-9]+)?x",
    r"[0-9][0-9,.]*\s*(?:million|billion|mm|bn)",
    r"[0-9][0-9,.]*\s*(?:customers|accounts|orders|contracts|units|deployments)",
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
    r"weak(?:er|ness)?",
    r"soft(?:er|ness)?",
    r"churn",
    r"going concern",
    r"substantial doubt",
)

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.12,
    "expected_pnl_delta": 2200.0,
    "main_failure_modes": [
        "thin_sample",
        "named_counterparty_false_positive",
        "already_priced_by_t1",
        "accepted_sec_rs20_comparator_not_beaten",
        "window_regression",
    ],
    "confidence_reason": (
        "Recent SEC demand text and Companyfacts demand-obligation variants "
        "failed because they were generic or sparse. Requiring an explicit "
        "named counterparty plus relation-side strength is a materially "
        "different PIT relation field, but sample risk is high."
    ),
    "recorded_at": "2026-06-15T22:05:04+00:00",
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
        "failure_handling": (
            "missing SEC text, named counterparty evidence, issuer OHLCV, "
            "counterparty OHLCV, next open, or 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same SEC "
        "financial-report text set, named-counterparty evidence extractor, "
        "counterparty OHLCV confirmation, T+1 reaction gate, liquidity gate, "
        "overlap exclusion, cooldown, next-open paper entry, 10-day exit, "
        "costs, and concentration controls in both historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: SEC earnings-release text that names a public customer, "
        "cloud/platform partner, or supplier in a quantified contract/revenue/"
        "customer-growth evidence span, confirmed by both issuer T+1 strength "
        "and counterparty 20d strength versus SPY, may isolate relation-backed "
        "demand underreaction."
    ),
    "2_history_check": {
        "exp-20260603-012": (
            "SEC customer contract business-win candidate pool was rejected; "
            "this run requires a named public counterparty and relation-side "
            "OHLCV strength rather than contract/customer item parsing alone."
        ),
        "exp-20260615-012": "Generic order/backlog/RPO demand text was rejected.",
        "exp-20260615-013": "Quantified backlog/RPO/book-to-bill text was too sparse.",
        "exp-20260615-022": (
            "Selected Companyfacts demand-obligation acceleration failed "
            "late_strong and accepted-comparator gates."
        ),
        "exp-20260615-026": (
            "SaaS/subscription operating KPI text failed with only four event "
            "trades and late_strong regression."
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
        "exp_20260615_029_sec_named_counterparty_contract_economics.py"
    ),
}


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _hits(text: str, patterns: tuple[str, ...]) -> list[str]:
    return [pattern for pattern in patterns if re.search(pattern, text, flags=re.IGNORECASE)]


def _counterparty_hits(text: str) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    for ticker, name, patterns in COUNTERPARTIES:
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns):
            hits.append({"ticker": ticker, "name": name})
    unique: dict[str, dict[str, str]] = {}
    for hit in hits:
        unique.setdefault(hit["ticker"], hit)
    return list(unique.values())


def _extract_named_counterparty_spans(row: dict[str, Any]) -> dict[str, Any]:
    text = base._business_text(row)
    spans: list[dict[str, Any]] = []
    counterparty_terms: Counter[str] = Counter()
    relation_terms: Counter[str] = Counter()
    economic_terms: Counter[str] = Counter()
    quality_terms: Counter[str] = Counter()
    magnitude_terms: Counter[str] = Counter()
    rejected_negative_spans = 0
    rejected_no_economic_terms = 0
    rejected_no_magnitude_or_quality = 0
    for sentence in base.SENTENCE_SPLIT_RE.split(text):
        cleaned = re.sub(r"\s+", " ", sentence).strip()
        if len(cleaned) < 35:
            continue
        lowered = cleaned.lower()
        counterparties = _counterparty_hits(lowered)
        if not counterparties:
            continue
        relation_hits = _hits(lowered, RELATION_PATTERNS)
        economic_hits = _hits(lowered, ECONOMIC_PATTERNS)
        if not relation_hits or not economic_hits:
            rejected_no_economic_terms += 1
            continue
        quality_hits = _hits(lowered, QUALITY_PATTERNS)
        magnitude_hits = _hits(cleaned, MAGNITUDE_PATTERNS)
        if not quality_hits and not magnitude_hits:
            rejected_no_magnitude_or_quality += 1
            continue
        if _hits(lowered, NEGATIVE_SPAN_PATTERNS):
            rejected_negative_spans += 1
            continue
        for counterparty in counterparties:
            counterparty_terms[counterparty["ticker"]] += 1
        for hit in relation_hits:
            relation_terms[hit] += 1
        for hit in economic_hits:
            economic_terms[hit] += 1
        for hit in quality_hits:
            quality_terms[hit] += 1
        for hit in magnitude_hits:
            magnitude_terms[hit] += 1
        spans.append(
            {
                "text": cleaned[:380],
                "counterparties": counterparties,
                "relation_terms": relation_hits,
                "economic_terms": economic_hits,
                "quality_terms": quality_hits,
                "magnitude_terms": magnitude_hits,
            }
        )
        if len(spans) >= 5:
            break
    unique_counterparties: dict[str, dict[str, str]] = {}
    for span in spans:
        for counterparty in span["counterparties"]:
            unique_counterparties.setdefault(counterparty["ticker"], counterparty)
    return {
        "span_count": len(spans),
        "spans": spans,
        "counterparties": list(unique_counterparties.values()),
        "ai_terms": dict(sorted(counterparty_terms.items())),
        "demand_terms": dict(sorted(economic_terms.items())),
        "counterparty_terms": dict(sorted(counterparty_terms.items())),
        "relation_terms": dict(sorted(relation_terms.items())),
        "economic_terms": dict(sorted(economic_terms.items())),
        "quality_terms": dict(sorted(quality_terms.items())),
        "magnitude_terms": dict(sorted(magnitude_terms.items())),
        "rejected_negative_spans": rejected_negative_spans,
        "rejected_no_economic_terms": rejected_no_economic_terms,
        "rejected_no_magnitude_or_quality": rejected_no_magnitude_or_quality,
    }


def _moving_average_close(rows: list[dict[str, Any]], idx: int, lookback: int) -> float | None:
    if idx < lookback - 1:
        return None
    values: list[float] = []
    for row in rows[idx - lookback + 1 : idx + 1]:
        close = base.shadow._value(row, "Close")
        if close is None:
            return None
        values.append(close)
    return sum(values) / len(values)


def _counterparty_confirmation(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    counterparty: dict[str, str],
    issuer_ticker: str,
    signal_date: str,
) -> dict[str, Any]:
    cp_ticker = counterparty["ticker"].upper()
    if cp_ticker == issuer_ticker.upper():
        return {
            "ticker": cp_ticker,
            "name": counterparty["name"],
            "status": "same_as_issuer",
            "passed": False,
        }
    rows = base.shadow._series(snapshot, cp_ticker)
    spy_rows = base.shadow._series(snapshot, "SPY")
    if not rows:
        return {"ticker": cp_ticker, "name": counterparty["name"], "status": "missing_counterparty_ohlcv", "passed": False}
    idx = base._idx_on_or_after(rows, signal_date)
    spy_idx = base._idx_on_or_after(spy_rows, signal_date)
    if idx is None or spy_idx is None:
        return {"ticker": cp_ticker, "name": counterparty["name"], "status": "missing_signal_date", "passed": False}
    if idx < COUNTERPARTY_LOOKBACK_DAYS or spy_idx < COUNTERPARTY_LOOKBACK_DAYS:
        return {"ticker": cp_ticker, "name": counterparty["name"], "status": "insufficient_history", "passed": False}
    cp_ret20 = base._close_to_close_return(rows, idx - COUNTERPARTY_LOOKBACK_DAYS, idx)
    spy_ret20 = base._close_to_close_return(spy_rows, spy_idx - COUNTERPARTY_LOOKBACK_DAYS, spy_idx)
    cp_close = base.shadow._value(rows[idx], "Close")
    cp_ma50 = _moving_average_close(rows, idx, COUNTERPARTY_MA_DAYS)
    if cp_ret20 is None or spy_ret20 is None or cp_close is None or cp_ma50 is None:
        return {"ticker": cp_ticker, "name": counterparty["name"], "status": "missing_strength_inputs", "passed": False}
    ret20_excess = cp_ret20 - spy_ret20
    passed = ret20_excess >= MIN_COUNTERPARTY_RET20_EXCESS_SPY and cp_close >= cp_ma50
    return {
        "ticker": cp_ticker,
        "name": counterparty["name"],
        "status": "covered",
        "passed": bool(passed),
        "date": base.shadow._date(rows[idx]),
        "ret20": base._round(cp_ret20, 6),
        "spy_ret20": base._round(spy_ret20, 6),
        "ret20_excess_vs_spy": base._round(ret20_excess, 6),
        "close": base._round(cp_close, 4),
        "ma50": base._round(cp_ma50, 4),
        "close_above_ma50": bool(cp_close >= cp_ma50),
    }


def _candidate_from_text_row(
    *,
    row: dict[str, Any],
    snapshot: dict[str, list[dict[str, Any]]],
    entries_by_date: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any] | None, str]:
    candidate, reason = ORIGINAL_CANDIDATE_FROM_TEXT_ROW(
        row=row,
        snapshot=snapshot,
        entries_by_date=entries_by_date,
    )
    if candidate is None:
        return None, reason
    evidence = candidate.get("ai_demand_evidence") or {}
    counterparties = evidence.get("counterparties") or []
    if not counterparties:
        return None, "no_named_counterparty"
    confirmations = [
        _counterparty_confirmation(
            snapshot=snapshot,
            counterparty=counterparty,
            issuer_ticker=str(candidate.get("ticker") or ""),
            signal_date=str(candidate.get("date") or ""),
        )
        for counterparty in counterparties
    ]
    passed_confirmations = [row for row in confirmations if row.get("passed")]
    if not passed_confirmations:
        return None, "counterparty_strength_not_confirmed"
    best = max(
        passed_confirmations,
        key=lambda row: float(row.get("ret20_excess_vs_spy") or 0.0),
    )
    bonus = 25.0 * float(best.get("ret20_excess_vs_spy") or 0.0)
    candidate["candidate_score"] = base._round(float(candidate["candidate_score"]) + bonus, 6)
    candidate["counterparty_confirmations"] = confirmations
    candidate["best_counterparty_confirmation"] = best
    candidate["named_counterparty_rule_version"] = RULE_VERSION
    return candidate, "candidate"


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = ORIGINAL_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    gate["decision"] = (
        "positive_replay_lead_not_promoted_sec_named_counterparty_contract_economics"
        if gate["passed"]
        else "rejected_sec_named_counterparty_contract_economics_candidate_pool"
    )
    gate["accepted_sec_rs20_comparator"] = ACCEPTED_SEC_RS20_COMPARATOR
    return gate


def _rename_evidence(payload: dict[str, Any]) -> None:
    for bucket_name in ("target_trades_by_window", "filtered_candidates_sample_by_window"):
        for rows in (payload.get(bucket_name) or {}).values():
            for row in rows:
                if "ai_demand_evidence" in row:
                    row["named_counterparty_contract_economics_evidence"] = row.pop(
                        "ai_demand_evidence"
                    )
    for scan in (payload.get("scan_by_window") or {}).values():
        reject_counts = scan.get("reject_counts") or {}
        if "no_ai_demand_evidence_span" in reject_counts:
            reject_counts["no_named_counterparty_contract_economics_span"] = reject_counts.pop(
                "no_ai_demand_evidence_span"
            )
        scan["evidence_samples"] = [
            {
                **sample,
                "named_counterparty_contract_economics_spans": sample.get("spans", []),
            }
            for sample in scan.get("evidence_samples", [])
        ]


def _build_payload() -> dict[str, Any]:
    payload = ORIGINAL_BUILD_PAYLOAD()
    _rename_evidence(payload)
    passed = bool(payload["gate4"]["passed"])
    aggregate = payload["delta_metrics"]["aggregate"]
    reflection = {
        "why_result_happened": (
            "The named-counterparty SEC relation source cleared the private "
            "replay gate, but it remains only a lead because no shared daily/"
            "backtest helper exists."
            if passed
            else (
                "The named-counterparty SEC relation source did not clear Gate 4. "
                "The likely reason is that explicit customer, supplier, or "
                "platform-partner disclosures are too sparse, too often generic "
                "co-marketing language, or already priced by issuer T+1 and "
                "counterparty strength before next-open execution."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping counterparty name lists, relation terms, "
            "numeric regexes, T+1, counterparty RS20, MA50, ADV/price, top-N, "
            "hold-day, cooldown, or notional thresholds on the same frozen windows."
        ),
        "new_evidence_required": (
            "A valid retry needs materially richer PIT relation provenance, "
            "such as normalized customer/supplier identity from exhibits, "
            "contract duration/funding certainty, revenue exposure by named "
            "counterparty, or closed forward replacement-value rows from a "
            "shared daily helper."
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
            "mechanism_family": "production_visible_free_sec_text_relation_candidate_pool",
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "nearby_prior_experiments": list(PRE_RUN_QUESTIONS["2_history_check"].keys()),
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "sec_text_named_counterparty_relation_plus_ohlcv_confirmation",
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
                "normalized customer/supplier identity",
                "contract duration and funding certainty",
                "named-counterparty revenue exposure",
                "shared helper plus daily snapshot parity for any positive replay",
            ],
            "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
            "total_pnl_delta": aggregate["total_pnl_delta_sum"],
            "interpretation": (
                "The named-counterparty SEC relation source passed as a private "
                "replay lead only; no production surface was promoted."
                if passed
                else (
                    "The named-counterparty SEC relation source did not clear "
                    "Gate 4 and is not promoted."
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
            "No new core filter or entry rule was added. The SEC named-counterparty "
            "relation source is additive default-off paper, so core signals "
            "generated/survived are unchanged from baseline."
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
        "counterparty_lookback_days": COUNTERPARTY_LOOKBACK_DAYS,
        "min_counterparty_ret20_excess_spy": MIN_COUNTERPARTY_RET20_EXCESS_SPY,
        "counterparty_ma_days": COUNTERPARTY_MA_DAYS,
        "counterparties": [
            {"ticker": ticker, "name": name, "patterns": patterns}
            for ticker, name, patterns in COUNTERPARTIES
        ],
        "relation_patterns": RELATION_PATTERNS,
        "economic_patterns": ECONOMIC_PATTERNS,
        "quality_patterns": QUALITY_PATTERNS,
        "magnitude_patterns": MAGNITUDE_PATTERNS,
        "negative_span_patterns": NEGATIVE_SPAN_PATTERNS,
    }
    payload["backtest_protocol"]["source"] = (
        "docs/backtesting.md canonical three-window core replay plus replay-only "
        "SEC named-counterparty relation evidence-span default-off paper overlay"
    )
    payload["backtest_protocol"]["execution_model"] = (
        "SEC text and close-of-day OHLCV are known by signal date. Signal date "
        "is the first post-event T+1 close. Named counterparty confirmation "
        "uses only counterparty OHLCV through signal date. Paper entry is next "
        "available open with existing entry slippage; exit is the close 10 "
        "trading days after signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    card = ORIGINAL_BUILD_CARD(payload)
    card = card.replace(
        "SEC AI Demand Evidence Span",
        "SEC Named Counterparty Contract Economics",
    )
    card = card.replace("AI demand", "named-counterparty relation")
    card = card.replace("SEC AI", "SEC Named Counterparty")
    return card


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = ORIGINAL_BUILD_LOG_RECORD(payload)
    record.update(
        {
            "status": payload["status"],
            "decision": payload["decision"],
            "accepted": False,
            "accepted_alpha": False,
            "mechanism_family": payload["mechanism_family"],
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


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, payload)
    base._write_text(CARD_MD, _build_card(payload))
    base._upsert_jsonl(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "artifact": base._repo_rel(OUT_JSON),
        "log": base._repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "calibration": payload["calibration"],
    }
    base.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "hypothesis": payload["hypothesis"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "completed_at": payload["timestamp"],
            "production_impact": PRODUCTION_IMPACT,
            "post_run_reflection": payload["post_run_reflection"],
        },
        timeout_seconds=120,
    )
    _write_manifest(payload)


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
    base.AI_PATTERNS = tuple(pattern for _, _, patterns in COUNTERPARTIES for pattern in patterns)
    base.DEMAND_PATTERNS = ECONOMIC_PATTERNS
    base.NEGATIVE_SPAN_PATTERNS = NEGATIVE_SPAN_PATTERNS
    base.ACCEPTED_SEC_RS20_COMPARATOR = ACCEPTED_SEC_RS20_COMPARATOR
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    base._extract_ai_demand_spans = _extract_named_counterparty_spans
    base._candidate_from_text_row = _candidate_from_text_row
    base._gate4 = _gate4
    base._build_payload = _build_payload
    base._build_card = _build_card
    base._build_log_record = _build_log_record
    base._write_manifest = _write_manifest
    base._configure_sleeve_globals()


def main() -> None:
    _patch_base()
    payload = _build_payload()
    persist(payload)
    print(json.dumps(base._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
