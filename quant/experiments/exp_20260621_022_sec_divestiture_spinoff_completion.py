"""exp-20260621-022: SEC divestiture / spin-off completion scout.

Alpha-search replay scout. The single decision hypothesis is that issuer 8-K
text with explicit completed divestiture, asset-sale, spin-off, or separation
transaction provenance may identify structure-simplification and capital
redeployment catalysts when paired with liquid SPY-relative leadership.

The runner reuses the prior SEC-text replay framework so Gate 1-4 math,
next-open entry, 10-day paper exit, costs, and accepted comparators remain
consistent with nearby SEC text experiments. It changes no production strategy
code, shared helper, daily snapshot, live/default orders, ranking, sizing,
exits, watchlist, LLM, or news path. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260620_015_sec_contract_value_market_cap_materiality as prev


EXPERIMENT_ID = "exp-20260621-022"
STEM = "sec_divestiture_spinoff_completion"
TRIAL_FAMILY = "sec_divestiture_spinoff_completion_text_candidate_pool"
TRIAL_VARIANT_ID = "sec_divestiture_spinoff_completion_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_text_divestiture_spinoff_completion_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = prev.REPO_ROOT
TEXT_DIR = prev.TEXT_DIR
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260621_022_{STEM}.json"
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

MIN_OPTIONAL_TRANSACTION_VALUE_USD = 1_000_000.0
MAX_OPTIONAL_TRANSACTION_VALUE_USD = 75_000_000_000.0
MIN_TEXT_WORDS = 160
MAX_TEXT_CHARS_SCANNED = 110_000
EVIDENCE_SPAN_CHARS = 900

STRUCTURE_KEYWORD_RE = re.compile(
    r"\b(divestiture|divestment|divested|sold|sale|sell|disposed of|"
    r"disposition|asset sale|spin[-\s]?off|spinoff|split[-\s]?off|"
    r"separation|separated|standalone public company|separate public company)\b",
    re.IGNORECASE,
)
CONCRETE_ACTION_RE = re.compile(
    r"\b(sold|sale|sell|divestiture|divestment|divested|disposed of|"
    r"spin[-\s]?off|spinoff|split[-\s]?off|separation|separated)\b",
    re.IGNORECASE,
)
COMPLETION_RE = re.compile(
    r"\b(completed|closed|consummated|completed the previously announced|"
    r"closed the previously announced|successfully completed|effective)\b",
    re.IGNORECASE,
)
DEFINITIVE_RE = re.compile(
    r"\b(entered into|signed|executed|announced)\b.{0,90}"
    r"\b(definitive|purchase|sale|separation|transaction)\b.{0,90}"
    r"\bagreement\b|\bagreement\b.{0,90}\b(to sell|for the sale of|"
    r"to divest|to separate)\b",
    re.IGNORECASE | re.DOTALL,
)
SALE_RE = re.compile(
    r"\b(sold|sale|sell|divestiture|divestment|divested|disposed of|"
    r"disposition)\b",
    re.IGNORECASE,
)
SPIN_RE = re.compile(
    r"\b(spin[-\s]?off|spinoff|split[-\s]?off|separation|separated|"
    r"standalone public company|separate public company|tax[-\s]?free distribution)\b",
    re.IGNORECASE,
)
ASSET_OBJECT_RE = re.compile(
    r"\b(business|businesses|assets?|subsidiar(?:y|ies)|division|unit|"
    r"operations|portfolio|brand|product line|facility|facilities|segment|"
    r"ownership interest|majority interest|minority interest|equity interest)\b",
    re.IGNORECASE,
)
BAD_CONTEXT_RE = re.compile(
    r"\b(common stock|preferred stock|warrants?|convertible|indenture|"
    r"notes? due|senior notes?|at[-\s]?the[-\s]?market|ATM offering|"
    r"underwriting agreement|securities purchase agreement|registered direct|"
    r"private placement|tender offer|merger agreement|employment agreement|"
    r"equity incentive|lease agreement|credit agreement|loan agreement|"
    r"revolving credit|term loan|severance|revocation period|risk factors?|"
    r"safe harbor|forward[-\s]?looking|could differ|may differ|expects to|"
    r"anticipated benefits|excluding divestitures|foreign currency|"
    r"discontinued operations adjustment|purchase price allocation)\b",
    re.IGNORECASE,
)
GENERIC_ITEM_RE = re.compile(
    r"item\s+2\.01\s+completion\s+of\s+acquisition\s+or\s+disposition\s+of\s+assets",
    re.IGNORECASE,
)

KIND_SCORE = {
    "completed_spinoff": 1.25,
    "completed_sale": 1.05,
    "definitive_sale": 0.75,
}

PREDICTION = {
    "success_probability": 0.14,
    "expected_ev_delta": 0.12,
    "expected_pnl_delta": 2000.0,
    "main_failure_modes": [
        "generic_earnings_text_noise",
        "window_regression",
        "target_concentration_failed",
        "accepted_distribution_comparator_not_beaten",
        "drawdown_drift",
    ],
    "confidence_reason": (
        "Segment-count reduction failed but explicitly named divestiture/"
        "spin-off provenance as valid new evidence. Local SEC text has "
        "nonzero three-window sample after stricter parser, but SEC text "
        "families remain noisy and comparator failure risk is high."
    ),
    "recorded_at": "2026-06-21T22:09:43+00:00",
}

PRODUCTION_IMPACT = {
    **prev.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "uses_free_sec_filing_text": True,
    "uses_free_sec_companyfacts": False,
    "uses_raw_companyfacts_cache": False,
    "execution_envelope": {
        **prev.PRODUCTION_IMPACT["execution_envelope"],
        "failure_handling": (
            "missing SEC filing text, missing completed divestiture/asset-sale/"
            "spin-off/separation provenance, excluded financing/equity/legal/"
            "risk context, missing OHLCV, missing next open, or missing 10d "
            "exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper parses the same SEC "
        "filing text fields, evidence spans, exclusion rules, same-day OHLCV "
        "confirmation, cooldown, next-open paper entry, 10-day exit, costs, and "
        "concentration controls in both historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: PIT SEC 8-K text with explicit completed divestiture, "
        "asset-sale, spin-off, or separation transaction provenance, paired "
        "with liquid SPY-relative leadership, may identify structure-"
        "simplification and capital-redeployment catalysts before next-open "
        "10-day continuation."
    ),
    "2_history_check": {
        "novelty_gate": (
            "Reservation warned on nearby SEC text candidate families. The "
            "override is valid because the evidence axis is completed "
            "divestiture/asset-sale/spin-off/separation transaction provenance, "
            "not raw reportable segment count, generic SEC complexity text, "
            "contract value, customer commitment, or Companyfacts asset-growth "
            "ratios."
        ),
        "exp-20260619-012": (
            "Rejected raw NumberOfReportableSegments reduction, but its "
            "reflection explicitly required segment-level revenue/profit, "
            "divestiture completion events, IPO/spin-off linkage, or closed "
            "forward rows for a valid retry."
        ),
        "exp-20260620-018": (
            "SEC price-alignment issuer-continuation text was rejected. This "
            "run requires a structure-simplification transaction object, not "
            "generic issuer continuation language."
        ),
        "exp-20260621-014": (
            "SEC customer commitment text had zero target trades. This run uses "
            "corporate portfolio simplification provenance, not demand funding."
        ),
        "exp-20260615-011": (
            "Generic SEC complexity text did not create durable edge. This run "
            "uses concrete transaction completion language."
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
        "exp_20260621_022_sec_divestiture_spinoff_completion.py"
    ),
}

_ORIGINAL_GATE4 = prev._gate4


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return prev._repo_rel(path)


def _clean_excerpt(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()[:1000]


def _local_spans(scanned: str) -> list[str]:
    spans: list[str] = []
    seen: set[str] = set()
    for match in STRUCTURE_KEYWORD_RE.finditer(scanned):
        start = max(0, match.start() - EVIDENCE_SPAN_CHARS)
        end = min(len(scanned), match.end() + EVIDENCE_SPAN_CHARS)
        span = scanned[start:end]
        key = _clean_excerpt(span[:350]).lower()
        if key in seen:
            continue
        seen.add(key)
        spans.append(span)
    return spans


def _kind_for_span(span: str) -> str | None:
    if BAD_CONTEXT_RE.search(span):
        return None
    if not CONCRETE_ACTION_RE.search(span):
        return None
    generic_item_only = GENERIC_ITEM_RE.search(span) and not re.search(
        r"\b(sold|sale|sell|divestiture|divestment|divested|disposed of|"
        r"spin[-\s]?off|spinoff|split[-\s]?off|separation|separated)\b",
        span,
        re.IGNORECASE,
    )
    if generic_item_only:
        return None

    has_sale = SALE_RE.search(span) is not None
    has_spin = SPIN_RE.search(span) is not None
    has_object = ASSET_OBJECT_RE.search(span) is not None
    has_completion = COMPLETION_RE.search(span) is not None
    has_definitive = DEFINITIVE_RE.search(span) is not None
    sold_as_past_action = re.search(r"\b(sold|divested|disposed of)\b", span, re.IGNORECASE) is not None

    if has_spin and (has_completion or sold_as_past_action):
        return "completed_spinoff"
    if has_sale and has_object and (has_completion or sold_as_past_action):
        return "completed_sale"
    if has_sale and has_object and has_definitive:
        return "definitive_sale"
    return None


def _structure_event(text: str) -> dict[str, Any] | None:
    if not text or len(text.split()) < MIN_TEXT_WORDS:
        return None
    scanned = text[:MAX_TEXT_CHARS_SCANNED]

    values: list[float] = []
    kinds: set[str] = set()
    completion_terms: set[str] = set()
    structure_terms: set[str] = set()
    object_terms: set[str] = set()
    first_excerpt = ""
    evidence_spans = 0

    for span in _local_spans(scanned):
        kind = _kind_for_span(span)
        if kind is None:
            continue
        evidence_spans += 1
        kinds.add(kind)
        completion_terms.update(term.group(0).upper() for term in COMPLETION_RE.finditer(span))
        structure_terms.update(term.group(0).upper() for term in STRUCTURE_KEYWORD_RE.finditer(span))
        object_terms.update(term.group(0).upper() for term in ASSET_OBJECT_RE.finditer(span))
        span_values = [prev._money_value(value_match) for value_match in prev.VALUE_RE.finditer(span)]
        values.extend(value for value in span_values if value is not None)
        if not first_excerpt:
            first_excerpt = _clean_excerpt(span)

    if not kinds:
        return None
    primary_kind = max(kinds, key=lambda kind: KIND_SCORE[kind])
    max_value = max(values) if values else None
    return {
        "transaction_kind": primary_kind,
        "transaction_kinds": sorted(kinds),
        "structure_evidence_span_count": evidence_spans,
        "structure_terms": sorted(structure_terms)[:16],
        "completion_terms": sorted(completion_terms)[:12],
        "asset_object_terms": sorted(object_terms)[:12],
        "structure_excerpt": first_excerpt,
        "optional_transaction_value_usd": prev._round(max_value, 2) if max_value else None,
        "optional_transaction_value_count": len(values),
        "has_optional_transaction_value": bool(values),
        "contract_value_usd": prev._round(max_value, 2) if max_value else None,
        "contract_duration_years": None,
        "contract_value_count": len(values),
        "has_contract_value": bool(values),
        "has_contract_duration": False,
        "contract_evidence_span_count": evidence_spans,
        "text_word_count_scanned": len(scanned.split()),
    }


def _build_quality_index(
    text_rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    stats: Counter[str] = Counter()
    for row in text_rows:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            stats["missing_ticker"] += 1
            continue
        by_ticker[ticker].append(row)
        stats[f"kind_{row.get('transaction_kind') or 'unknown'}"] += 1
        stats["rows_with_optional_value"] += 1 if row.get("has_optional_transaction_value") else 0
    for rows in by_ticker.values():
        rows.sort(
            key=lambda row: (
                row["date"],
                -float(KIND_SCORE.get(str(row.get("transaction_kind")), 0.0)),
                -float(row.get("optional_transaction_value_usd") or 0.0),
                row.get("accession_number") or "",
            )
        )
    index = {ticker: {"events": rows} for ticker, rows in by_ticker.items()}
    return index, {
        "sec_text_rows_loaded": len(text_rows),
        "tickers_with_structure_events": len(by_ticker),
        "text_source": _repo_rel(TEXT_DIR),
        "min_text_words": MIN_TEXT_WORDS,
        "max_text_chars_scanned": MAX_TEXT_CHARS_SCANNED,
        "evidence_span_chars": EVIDENCE_SPAN_CHARS,
        "uses_market_cap_denominator": False,
        **dict(stats),
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indices = {
        ticker: prev.base.framework.shadow._row_index(prev.base.framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    scan: Counter[str] = Counter()
    candidates: list[dict[str, Any]] = []
    for ticker in sorted(set(quality_index) & set(snapshot)):
        for event in list(quality_index[ticker].get("events") or []):
            signal_date = str(event.get("date") or "")[:10]
            if not (str(cfg["start"]) <= signal_date <= str(cfg["end"])):
                continue
            scan["event_rows_in_window"] += 1
            confirm = prev.base._price_confirmation(
                snapshot=snapshot,
                indices=indices,
                ticker=ticker,
                signal_date=signal_date,
            )
            if confirm is None:
                scan["failed_price_confirmation"] += 1
                continue
            kind = str(event.get("transaction_kind") or "")
            kind_score = KIND_SCORE.get(kind, 0.0)
            if kind_score <= 0.0:
                scan["missing_transaction_kind"] += 1
                continue
            value = float(event.get("optional_transaction_value_usd") or 0.0)
            value_component = min(math.log10(max(value, 1.0) / 1_000_000.0), 4.0) / 4.0 if value else 0.0
            span_component = min(float(event.get("structure_evidence_span_count") or 0.0), 4.0) / 4.0
            score = (
                kind_score
                + 0.25 * value_component
                + 0.12 * span_component
                + 0.50 * float(confirm["candidate_ret20_excess_spy"])
                + 0.15 * float(confirm["candidate_ret60_excess_spy"])
                + 0.12 * float(confirm["candidate_close_location"])
                + 0.025
                * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
            )
            meta = sector_entries.get(ticker, {})
            scan["qualified_candidate_rows"] += 1
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "SEC_TEXT_STRUCTURE_SIMPLIFICATION_PAPER",
                    "candidate_score": prev._round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "sec_filing_text_usable_trade_date_and_signal_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_filing_text": True,
                    "uses_free_sec_companyfacts": False,
                    "uses_raw_companyfacts_cache": False,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    "text_structure_score_kind": kind_score,
                    "text_structure_value_component": prev._round(value_component, 6),
                    "text_structure_span_component": prev._round(span_component, 6),
                    **{f"text_{key}": value for key, value in event.items() if key not in {"ticker", "date"}},
                    **confirm,
                }
            )

    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in candidates:
        key = (row["date"], row["ticker"])
        existing = deduped.get(key)
        if existing is None or float(row["candidate_score"]) > float(existing["candidate_score"]):
            deduped[key] = row
    rows = list(deduped.values())
    rows.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"] or 0.0),
            -float(row.get("text_structure_score_kind") or 0.0),
            -float(row.get("text_optional_transaction_value_usd") or 0.0),
            -float(row.get("candidate_ret20_excess_spy") or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(rows)
    scan["candidate_signal_days"] = len({row["date"] for row in rows})
    scan["candidate_tickers"] = len({row["ticker"] for row in rows})
    return rows, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "min_optional_transaction_value_usd": MIN_OPTIONAL_TRANSACTION_VALUE_USD,
        "max_optional_transaction_value_usd": MAX_OPTIONAL_TRANSACTION_VALUE_USD,
        "min_text_words": MIN_TEXT_WORDS,
        "max_text_chars_scanned": MAX_TEXT_CHARS_SCANNED,
        "evidence_span_chars": EVIDENCE_SPAN_CHARS,
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = _ORIGINAL_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    gate["decision"] = (
        "positive_replay_lead_not_promoted_sec_divestiture_spinoff_completion"
        if gate["passed"]
        else "rejected_sec_divestiture_spinoff_completion_candidate_pool"
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
            f"# {EXPERIMENT_ID} SEC Divestiture / Spin-Off Completion",
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
    prev.MIN_CONTRACT_VALUE_USD = MIN_OPTIONAL_TRANSACTION_VALUE_USD
    prev.MAX_CONTRACT_VALUE_USD = MAX_OPTIONAL_TRANSACTION_VALUE_USD
    prev.MIN_TEXT_WORDS = MIN_TEXT_WORDS
    prev.MAX_TEXT_CHARS_SCANNED = MAX_TEXT_CHARS_SCANNED
    prev.EVIDENCE_SPAN_CHARS = EVIDENCE_SPAN_CHARS
    prev.PREDICTION = PREDICTION
    prev.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    prev.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    prev._contract_economics = _structure_event
    prev._build_quality_index = _build_quality_index
    prev._candidate_rows_for_window = _candidate_rows_for_window
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
            "The SEC divestiture / spin-off completion source cleared the "
            "numeric replay screen, but remains only a replay lead because no "
            "shared daily/backtest parser was promoted."
        )
    else:
        interpretation = (
            "The SEC divestiture / spin-off completion source did not clear "
            f"Gate 4 (failed: {', '.join(gate4['failed_reasons']) or 'none'}). "
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
            "mechanism_family": "production_visible_sec_text_structure_simplification_candidate_pool",
            "new_evidence_type": "sec_text_completed_divestiture_spinoff_provenance",
            "nearby_prior_experiments": [
                "exp-20260619-012",
                "exp-20260620-018",
                "exp-20260621-014",
                "exp-20260615-011",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "interpretation": interpretation,
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["parameters"].pop("min_contract_value_to_market_cap", None)
    payload["parameters"].pop("max_contract_value_to_market_cap", None)
    payload["parameters"].pop("max_shares_outstanding_fact_age_days", None)
    payload["parameters"].update(
        {
            "min_optional_transaction_value_usd": MIN_OPTIONAL_TRANSACTION_VALUE_USD,
            "max_optional_transaction_value_usd": MAX_OPTIONAL_TRANSACTION_VALUE_USD,
            "min_text_words": MIN_TEXT_WORDS,
            "max_text_chars_scanned": MAX_TEXT_CHARS_SCANNED,
            "evidence_span_chars": EVIDENCE_SPAN_CHARS,
            "structure_terms": STRUCTURE_KEYWORD_RE.pattern,
            "completion_terms": COMPLETION_RE.pattern,
            "definitive_terms": DEFINITIVE_RE.pattern,
            "asset_object_terms": ASSET_OBJECT_RE.pattern,
            "exclude_terms": BAD_CONTEXT_RE.pattern,
            "kind_score": KIND_SCORE,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["backtest_protocol"].pop("companyfacts_source", None)
    payload["backtest_protocol"]["sec_filing_text_source"] = _repo_rel(TEXT_DIR)
    payload["backtest_protocol"]["execution_model"] = (
        "8-K SEC filing text is keyed by accepted_at and usable_trade_date. "
        "The parser admits rows only when a local evidence span contains "
        "concrete divestiture, asset-sale, spin-off, or separation transaction "
        "language plus completion or definitive-sale provenance, and no "
        "financing/equity/legal/risk/forward-looking exclusion. Optional "
        "dollar proceeds are used only for ranking, not as an admission gate. "
        "Price confirmation uses only signal-date OHLCV. Paper entry is next "
        "available open; exit is the close 10 trading days after signal with "
        "existing costs."
    )
    payload["gate2"]["runtime_fields"] = [
        "SEC filing text combined_text",
        "SEC filing accepted_at and usable_trade_date",
        "SEC filing accession_number",
        "local evidence-span completed divestiture/asset-sale/spin-off/separation terms",
        "local evidence-span transaction object terms",
        "optional local evidence-span dollar proceeds/value",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A valid retry needs materially richer PIT transaction provenance such "
        "as normalized business/segment identity, segment revenue or profit "
        "mix, buyer/counterparty identity, proceeds/use-of-proceeds, completion "
        "status labels from a shared daily helper, or closed forward "
        "replacement rows. Do not sweep SEC divestiture/spin-off phrase lists, "
        "item codes, optional value thresholds, RS/close/volume guards, top-N, "
        "hold, cooldown, or notional on these frozen windows."
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
            "Do not retry by sweeping SEC divestiture/spin-off phrase lists, "
            "item codes, optional dollar-value thresholds, RS/close/volume/vol "
            "guards, top-N, hold days, cooldown, or notional on these frozen "
            "windows."
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
