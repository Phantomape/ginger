"""exp-20260621-014: SEC customer prepayment / capacity commitment scout.

Alpha-search replay scout. The single decision hypothesis is that issuer 8-K
text with customer prepayment, deposit, capacity-reservation, take-or-pay, or
minimum-commitment language tied to customer/supply/capacity agreements may
identify harder-to-cancel demand commitments than generic contract news.

The runner reuses the prior SEC-text replay framework so Gate 1-4 math,
next-open entry, 10-day paper exit, costs, and accepted comparators remain
consistent with nearby SEC contract experiments. It changes no production
strategy code, shared helper, daily snapshot, live/default orders, ranking,
sizing, exits, watchlist, LLM, or news path. No JavaScript is used.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260620_015_sec_contract_value_market_cap_materiality as prev


EXPERIMENT_ID = "exp-20260621-014"
STEM = "sec_customer_prepayment_capacity_commitment"
TRIAL_FAMILY = "sec_customer_prepayment_capacity_commitment_candidate_pool"
TRIAL_VARIANT_ID = "sec_customer_prepayment_capacity_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_text_customer_prepayment_capacity_commitment_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "codex-alpha-search"

REPO_ROOT = prev.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260621_014_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = prev.BASE_NOTIONAL_USD
HOLD_DAYS = prev.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = prev.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = prev.SAME_TICKER_COOLDOWN_DAYS

MIN_CONTRACT_VALUE_USD = 1_000_000.0
MAX_CONTRACT_VALUE_USD = 75_000_000_000.0
MIN_CONTRACT_VALUE_TO_MARKET_CAP = 0.005
MAX_CONTRACT_VALUE_TO_MARKET_CAP = 1.25
MIN_TEXT_WORDS = 180
MAX_TEXT_CHARS_SCANNED = 100_000
EVIDENCE_SPAN_CHARS = 900

COMMITMENT_RE = re.compile(
    r"\b(pre[-\s]?payment|advance payment|customer deposit|customer advances?|"
    r"capacity reservation|capacity commitment|reservation payment|take[-\s]?or[-\s]?pay|"
    r"minimum (?:purchase |revenue |volume )?commitment|contractual minimum|"
    r"non[-\s]?cancel(?:able|lable)|firm commitment)\b",
    re.IGNORECASE,
)
RELATION_RE = re.compile(
    r"\b(customer|client|hyperscaler|supply|supplier|capacity|contract|agreement|"
    r"purchase|reservation|hosting|data center|datacenter|HPC|GPU|take[-\s]?or[-\s]?pay)\b",
    re.IGNORECASE,
)
CAPACITY_RE = re.compile(
    r"\b([0-9][0-9,.]*)\s?(MW|megawatts|GW|gigawatts|GPU(?:s)?|megawatt-hours?)\b",
    re.IGNORECASE,
)
EXCLUDE_RE = re.compile(
    r"\b(prepaid expenses?|security deposit|lease deposit|operating lease|"
    r"credit agreement|loan agreement|revolving credit|term loan|indenture|"
    r"convertible|warrants?|preferred stock|common stock|at[-\s]?the[-\s]?market|"
    r"ATM offering|underwriting agreement|securities purchase agreement|"
    r"tender offer|merger agreement|employment agreement|equity incentive|"
    r"tax receivable|income taxes|interest expense|bankruptcy|going concern)\b",
    re.IGNORECASE,
)

PREDICTION = {
    "success_probability": 0.14,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "generic_earnings_text_noise",
        "window_regression",
        "target_concentration_failed",
        "accepted_distribution_comparator_not_beaten",
        "drawdown_drift",
    ],
    "confidence_reason": (
        "Prior generic SEC contract-value and raw Companyfacts contract-asset "
        "signals failed on thin sample, concentration, or window fragility. "
        "The new evidence axis is explicit text-level customer prepayment/"
        "deposit/capacity-reservation/take-or-pay/minimum-commitment provenance, "
        "which should separate durable demand funding from ordinary contract or "
        "earnings-release numerics, but parser noise and accepted-comparator "
        "weakness remain substantial."
    ),
    "recorded_at": "2026-06-21T15:05:45+00:00",
}

PRODUCTION_IMPACT = {
    **prev.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "uses_free_sec_filing_text": True,
    "uses_free_sec_companyfacts": True,
    "uses_raw_companyfacts_cache": True,
    "execution_envelope": {
        **prev.PRODUCTION_IMPACT["execution_envelope"],
        "failure_handling": (
            "missing SEC filing text, missing commitment/relation language, "
            "excluded financing/equity/legal/deposit-only context, missing "
            "numeric value, missing PIT shares outstanding, missing OHLCV, "
            "missing next open, or missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper parses the same SEC "
        "commitment evidence spans, PIT shares-outstanding market-cap "
        "denominator, same-day OHLCV confirmation, cooldown, next-open paper "
        "entry, 10-day exit, costs, and concentration controls in both "
        "historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: SEC 8-K text with explicit customer prepayment, "
        "deposit, capacity reservation, take-or-pay, or minimum-commitment "
        "language tied to customer/supply/capacity agreements may identify "
        "harder-to-cancel demand commitments after liquid SPY-relative "
        "confirmation."
    ),
    "2_history_check": {
        "novelty_gate": (
            "Reservation warned on nearby SEC backlog/contract families. The "
            "override is valid because the evidence axis is explicit customer "
            "prepayment/deposit/capacity-reservation/take-or-pay/minimum-"
            "commitment provenance, not a generic contract-dollar, backlog, "
            "Companyfacts contract-asset, no-covenant debt, or supplier-"
            "financing threshold retry."
        ),
        "exp-20260620-010": (
            "Raw Companyfacts contract-asset/unbilled-revenue was rejected on "
            "window regression, drawdown drift, target concentration, and "
            "accepted comparators. This run uses source-document payment/"
            "capacity commitment language, not balance-sheet tag growth."
        ),
        "exp-20260620-015": (
            "SEC contract value / market-cap materiality was rejected with only "
            "six target trades and concentration failure. This run requires "
            "prepayment/capacity-commitment provenance before the same materiality "
            "and price-confirmation replay can admit rows."
        ),
        "exp-20260620-005": (
            "Supplier-financing plus debt-relief Companyfacts was rejected on "
            "drawdown drift and then accepted only as a very specific 4k shared "
            "adapter in exp-20260620-009. This run uses customer commitment text, "
            "not supplier-payment or notional retuning."
        ),
        "exp-20260621-012": (
            "No-covenant credit-facility text had zero target events. This run "
            "uses a non-debt demand/payment-commitment tuple with nonzero "
            "pre-scan coverage."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL must "
        "be positive, no window EV/PnL regression, at least two EV-improved "
        "windows, at least 20 paper trades across all 3 windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration pass, and accepted compression/"
        "distribution candidate-pool comparators must be beaten. Replay-only "
        "positives are leads until shared daily/backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260621_014_sec_customer_prepayment_capacity_commitment.py"
    ),
}

_ORIGINAL_GATE4 = prev._gate4


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return prev._repo_rel(path)


def _commitment_economics(text: str) -> dict[str, Any] | None:
    if not text or len(text.split()) < MIN_TEXT_WORDS:
        return None
    scanned = text[:MAX_TEXT_CHARS_SCANNED]
    matches = list(COMMITMENT_RE.finditer(scanned))
    if not matches:
        return None

    values: list[float] = []
    duration: float | None = None
    evidence_spans = 0
    commitment_terms: set[str] = set()
    relation_terms: set[str] = set()
    capacity_units: set[str] = set()
    first_excerpt = ""
    for match in matches:
        start = max(0, match.start() - EVIDENCE_SPAN_CHARS)
        end = min(len(scanned), match.end() + EVIDENCE_SPAN_CHARS)
        span = scanned[start:end]
        if EXCLUDE_RE.search(span) or not RELATION_RE.search(span):
            continue
        span_values = [prev._money_value(value_match) for value_match in prev.VALUE_RE.finditer(span)]
        span_values = [value for value in span_values if value is not None]
        if not span_values:
            continue
        span_duration = prev._duration_years(span)
        values.extend(span_values)
        if span_duration is not None:
            duration = span_duration if duration is None else max(duration, span_duration)
        evidence_spans += 1
        commitment_terms.update(term.group(0).upper() for term in COMMITMENT_RE.finditer(span))
        relation_terms.update(term.group(0).upper() for term in RELATION_RE.finditer(span))
        capacity_units.update(term.group(0).upper() for term in CAPACITY_RE.finditer(span))
        if not first_excerpt:
            first_excerpt = re.sub(r"\s+", " ", span).strip()[:900]

    if not values:
        return None
    return {
        "contract_value_usd": prev._round(max(values), 2),
        "contract_duration_years": prev._round(duration, 2) if duration is not None else None,
        "contract_value_count": len(values),
        "has_contract_value": True,
        "has_contract_duration": duration is not None,
        "contract_evidence_span_count": evidence_spans,
        "text_word_count_scanned": len(scanned.split()),
        "commitment_terms": sorted(commitment_terms)[:12],
        "relation_terms": sorted(relation_terms)[:12],
        "capacity_units": sorted(capacity_units)[:12],
        "commitment_excerpt": first_excerpt,
    }


def _gate4(*, aggregate: dict[str, Any], target_summary: dict[str, Any], before_metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    gate = _ORIGINAL_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    gate["decision"] = (
        "positive_replay_lead_not_promoted_sec_customer_prepayment_capacity_commitment"
        if gate["passed"]
        else "rejected_sec_customer_prepayment_capacity_commitment_candidate_pool"
    )
    return gate


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Text Events | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in prev.base.framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | "
            "${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {events} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                events=scan.get("event_rows_in_window", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} SEC Customer Prepayment / Capacity Commitment",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4",
            "",
            *rows,
            "",
            "- Aggregate EV delta: `{:+.4f}`".format(aggregate["expected_value_score_delta_sum"]),
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Accepted compression comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                prev.base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"],
                prev.base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Accepted distribution comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                prev.base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"],
                prev.base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Production Impact",
            "",
            (
                "Replay-only and default-off paper only. No shared policy, run "
                "adapter, backtester adapter, daily snapshot, production "
                "watchlist, order path, core entry, ranking, sizing, exit, LLM, "
                "or news behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _write_manifest(payload: dict[str, Any]) -> None:
    runner = Path(__file__)
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(runner),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(runner): prev.base.framework._sha256(runner),
            _repo_rel(OUT_JSON): prev.base.framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): prev.base.framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): prev.base.framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): prev.base.framework._sha256(CARD_MD),
        },
    }
    prev.base.framework._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    log_record = prev.base._build_log_record(payload)
    prev.base.framework._write_json(OUT_JSON, payload)
    prev.base.framework._write_json(LOG_JSON, payload)
    prev.base.framework._write_text(CARD_MD, _build_card(payload))
    prev.base.framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
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
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
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
        "aggregate_strategy_total_pnl_delta": log_record["aggregate_strategy_total_pnl_delta"],
    }
    prev.base.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )
    _write_manifest(payload)


def _configure_prev() -> None:
    prev.EXPERIMENT_ID = EXPERIMENT_ID
    prev.STEM = STEM
    prev.TRIAL_FAMILY = TRIAL_FAMILY
    prev.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    prev.CHANGED_VARIABLE = CHANGED_VARIABLE
    prev.RULE_VERSION = RULE_VERSION
    prev.OWNER = OWNER
    prev.OUT_DIR = OUT_DIR
    prev.OUT_JSON = OUT_JSON
    prev.LOG_JSON = LOG_JSON
    prev.TICKET_JSON = TICKET_JSON
    prev.CARD_MD = CARD_MD
    prev.MANIFEST_JSON = MANIFEST_JSON
    prev.EXPERIMENT_LOG = EXPERIMENT_LOG
    prev.REGISTRY_JSON = REGISTRY_JSON
    prev.MIN_CONTRACT_VALUE_USD = MIN_CONTRACT_VALUE_USD
    prev.MAX_CONTRACT_VALUE_USD = MAX_CONTRACT_VALUE_USD
    prev.MIN_CONTRACT_VALUE_TO_MARKET_CAP = MIN_CONTRACT_VALUE_TO_MARKET_CAP
    prev.MAX_CONTRACT_VALUE_TO_MARKET_CAP = MAX_CONTRACT_VALUE_TO_MARKET_CAP
    prev.MIN_TEXT_WORDS = MIN_TEXT_WORDS
    prev.MAX_TEXT_CHARS_SCANNED = MAX_TEXT_CHARS_SCANNED
    prev.EVIDENCE_SPAN_CHARS = EVIDENCE_SPAN_CHARS
    prev.PREDICTION = PREDICTION
    prev.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    prev.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    prev._contract_economics = _commitment_economics
    prev._gate4 = _gate4
    prev._build_card = _build_card
    prev._write_manifest = _write_manifest
    prev._configure_base()


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload = prev._postprocess_payload(payload)
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    if gate4["passed"]:
        interpretation = (
            "The SEC customer prepayment / capacity-commitment source cleared "
            "the numeric replay screen, but remains only a replay lead because "
            "no shared daily/backtest parser was promoted."
        )
    else:
        interpretation = (
            "The SEC customer prepayment / capacity-commitment source did not "
            f"clear Gate 4 (failed: {', '.join(gate4['failed_reasons']) or 'none'}). "
            "It is not retained or promoted."
        )
    payload.update(
        {
            "timestamp": _utc_now(),
            "status": "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected",
            "decision": gate4["decision"],
            "accepted": False,
            "accepted_alpha": False,
            "numeric_gate4_passed": gate4["passed"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "default_off_paper_candidate_pool_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_sec_text_customer_commitment_candidate_pool",
            "new_evidence_type": "sec_text_customer_prepayment_capacity_commitment_tuple",
            "nearby_prior_experiments": [
                "exp-20260620-010",
                "exp-20260620-015",
                "exp-20260620-005",
                "exp-20260621-012",
            ],
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "interpretation": interpretation,
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["parameters"].update(
        {
            "min_contract_value_usd": MIN_CONTRACT_VALUE_USD,
            "max_contract_value_usd": MAX_CONTRACT_VALUE_USD,
            "min_contract_value_to_market_cap": MIN_CONTRACT_VALUE_TO_MARKET_CAP,
            "max_contract_value_to_market_cap": MAX_CONTRACT_VALUE_TO_MARKET_CAP,
            "min_text_words": MIN_TEXT_WORDS,
            "max_text_chars_scanned": MAX_TEXT_CHARS_SCANNED,
            "evidence_span_chars": EVIDENCE_SPAN_CHARS,
            "commitment_terms": COMMITMENT_RE.pattern,
            "relation_terms": RELATION_RE.pattern,
            "capacity_terms": CAPACITY_RE.pattern,
            "exclude_terms": EXCLUDE_RE.pattern,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "8-K SEC filing text is keyed by accepted_at and usable_trade_date. The "
        "parser admits rows only when a local evidence span contains customer "
        "prepayment, deposit, capacity-reservation, take-or-pay, or minimum-"
        "commitment language, relation terms tying it to customer/supply/capacity "
        "agreements, a numeric dollar value, and no financing/equity/legal/"
        "generic prepaid-expense exclusion. Raw SEC Companyfacts shares "
        "outstanding facts are joined by filed date to signal-date close to "
        "compute a PIT market-cap denominator. Price confirmation uses only "
        "signal-date OHLCV. Paper entry is next available open; exit is the "
        "close 10 trading days after signal with existing costs."
    )
    payload["gate2"]["runtime_fields"] = [
        "SEC filing text combined_text",
        "SEC filing accepted_at and usable_trade_date",
        "SEC filing accession_number",
        "local evidence-span commitment language",
        "local evidence-span numeric commitment value",
        "raw SEC Companyfacts dei.EntityCommonStockSharesOutstanding filed date",
        "signal-date OHLCV close for PIT market-cap denominator",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A valid retry needs materially richer PIT relation provenance such as "
        "normalized named customer identity, non-cancelable revenue exposure by "
        "counterparty, contract duration/funding certainty extracted from source "
        "documents, or closed forward replacement-value rows from a shared daily "
        "helper. Do not sweep commitment phrase lists, value/market-cap thresholds, "
        "RS/close/volume guards, top-N, hold, cooldown, or notional on these "
        "frozen windows."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": interpretation,
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; "
            "max drawdown drift {:+.4f}; {} paper trades.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
                float(aggregate["max_drawdown_delta_max"] or 0.0),
                payload["target_trade_summary"]["total_trade_count"],
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping SEC commitment phrase lists, value/"
            "market-cap thresholds, item codes, RS/close/volume/vol guards, "
            "top-N, hold days, cooldown, or notional on these frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return payload


def main() -> None:
    _configure_prev()
    payload = _postprocess_payload(prev.base._build_payload())
    _persist(payload)
    print(json.dumps(prev.base.framework._safe(prev.base._build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
