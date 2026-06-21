"""exp-20260621-023: SEC cyber incident containment scout.

Alpha-search replay scout. The single decision hypothesis is that issuer 8-K
text with explicit cybersecurity incident/update language plus containment,
remediation, restoration, or no-material-impact evidence may identify
overreaction recovery / continuation candidates when paired with liquid
SPY-relative leadership.

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


EXPERIMENT_ID = "exp-20260621-023"
STEM = "sec_cyber_incident_containment"
TRIAL_FAMILY = "sec_text_cyber_incident_containment_candidate_pool"
TRIAL_VARIANT_ID = "sec_cyber_incident_containment_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_text_cyber_incident_containment_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = prev.REPO_ROOT
TEXT_DIR = prev.TEXT_DIR
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260621_023_{STEM}.json"
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

MIN_TEXT_WORDS = 120
MAX_TEXT_CHARS_SCANNED = 110_000
EVIDENCE_SPAN_CHARS = 850

CYBER_EVENT_RE = re.compile(
    r"\b(cybersecurity|cyber security|cyber incident|cybersecurity incident|"
    r"cyber attack|cyberattack|ransomware|malware|data breach|security breach|"
    r"security incident|information security incident|data security incident|"
    r"unauthorized access|network intrusion|computer intrusion|systems? intrusion)\b",
    re.IGNORECASE,
)
NO_MATERIAL_IMPACT_RE = re.compile(
    r"\b(no|not|does not|do not|did not|has not|have not|is not|are not|"
    r"isn't|aren't)\b.{0,90}\b(material|materially|significant)\b.{0,90}"
    r"\b(impact|impacted|affect|affected|adverse|disruption|interruption|loss|"
    r"result|effect)\b|"
    r"\b(material|materially|significant)\b.{0,90}\b(impact|impacted|affect|"
    r"affected|adverse|disruption|interruption|loss|effect)\b.{0,90}"
    r"\b(no|not|does not|do not|did not|has not|have not|is not|are not|"
    r"isn't|aren't)\b|"
    r"\bnot expected\b.{0,90}\b(material|materially|significant)\b.{0,90}"
    r"\b(impact|affect|adverse|disruption|loss|effect)\b",
    re.IGNORECASE | re.DOTALL,
)
CONTAINMENT_RE = re.compile(
    r"\b(contained|containment|isolated|remediated|remediation|mitigated|"
    r"mitigation|secured|blocked|eradicated|neutralized|resolved|completed its "
    r"investigation|substantially completed)\b",
    re.IGNORECASE,
)
RESTORATION_RE = re.compile(
    r"\b(restored|resumed|operational|fully operational|back online|systems? "
    r"restored|services? restored|operations? restored|normal operations)\b",
    re.IGNORECASE,
)
ACTIVE_NEGATIVE_RE = re.compile(
    r"\b(material adverse|material impact|materially impacted|significant "
    r"disruption|significantly disrupted|unable to determine|has not yet "
    r"determined|cannot determine|ongoing disruption|ransom demand|encrypted "
    r"systems|exfiltrat(?:ed|ion)|shutdown|ceased operations)\b",
    re.IGNORECASE,
)
BAD_CONTEXT_RE = re.compile(
    r"\b(risk factors?|safe harbor|forward[-\s]?looking|could differ|may "
    r"differ|privacy policy|terms of use|material breach of this agreement|"
    r"breach of contract|credit agreement|loan agreement|indenture|employment "
    r"agreement|settlement agreement|insurance policy)\b",
    re.IGNORECASE,
)

KIND_SCORE = {
    "no_material_impact": 1.25,
    "contained_remediated": 1.05,
    "restored_operations": 0.95,
}

PREDICTION = {
    "success_probability": 0.12,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "thin_sample",
        "cyber_events_are_negative_tail",
        "window_regression",
        "target_concentration_failed",
        "accepted_distribution_comparator_not_beaten",
        "drawdown_drift",
    ],
    "confidence_reason": (
        "SEC cyber containment/no-material-impact evidence is distinct from "
        "the rejected static cybersecurity basket and recent SEC contract/"
        "divestiture text families. SEC text parsers remain noisy and cyber "
        "events may be fundamentally negative, so the prior success "
        "probability is deliberately low."
    ),
    "recorded_at": "2026-06-21T23:08:01+00:00",
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
        "missing SEC filing text, missing cybersecurity event/update language, "
        "missing local containment/remediation/restoration/no-material-impact "
        "evidence, excluded risk-factor/forward-looking/contract-breach "
        "context, missing OHLCV, missing next open, or missing 10d exit "
        "rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper parses the same SEC "
        "filing text fields, cyber evidence spans, exclusion rules, same-day "
        "OHLCV confirmation, cooldown, next-open paper entry, 10-day exit, "
        "costs, and concentration controls in both historical replay and "
        "daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: PIT SEC 8-K text with explicit cybersecurity incident/"
        "update language plus containment, remediation, restoration, or "
        "no-material-impact evidence, paired with liquid SPY-relative "
        "leadership, may identify overreaction recovery / continuation "
        "candidates before next-open 10-day paper exit."
    ),
    "2_history_check": {
        "novelty_gate": (
            "Reservation warned on nearby SEC text candidate families. The "
            "override is valid because the evidence axis is PIT cyber incident/"
            "update containment, remediation, restoration, or no-material-"
            "impact language, not issuer continuation text, contract value, "
            "customer commitment, or generic SEC item/form absorption."
        ),
        "exp-20260505-033": (
            "Rejected a static CHKP/CRWD cybersecurity infrastructure basket. "
            "This run trades issuer incident containment disclosure, not "
            "security-vendor exposure."
        ),
        "exp-20260620-018": (
            "SEC price-alignment issuer-continuation text was rejected. This "
            "run requires a cyber incident/update object plus mitigation or "
            "no-material-impact evidence, not generic continuation language."
        ),
        "exp-20260621-014": (
            "SEC customer commitment text had zero target trades. This run "
            "uses cyber operational-risk mitigation provenance, not demand "
            "funding."
        ),
        "exp-20260621-022": (
            "SEC divestiture/spin-off completion text was rejected. This run "
            "uses a different 8-K event object and different local evidence "
            "terms."
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
        "exp_20260621_023_sec_cyber_incident_containment.py"
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
    for match in CYBER_EVENT_RE.finditer(scanned):
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
    if not CYBER_EVENT_RE.search(span):
        return None
    no_material = NO_MATERIAL_IMPACT_RE.search(span) is not None
    contained = CONTAINMENT_RE.search(span) is not None
    restored = RESTORATION_RE.search(span) is not None
    if not (no_material or contained or restored):
        return None
    if BAD_CONTEXT_RE.search(span) and not no_material:
        return None
    if ACTIVE_NEGATIVE_RE.search(span) and not (no_material or contained or restored):
        return None
    if no_material:
        return "no_material_impact"
    if contained:
        return "contained_remediated"
    if restored:
        return "restored_operations"
    return None


def _cyber_event(text: str) -> dict[str, Any] | None:
    if not text or len(text.split()) < MIN_TEXT_WORDS:
        return None
    scanned = text[:MAX_TEXT_CHARS_SCANNED]

    kinds: set[str] = set()
    cyber_terms: set[str] = set()
    no_material_terms: set[str] = set()
    containment_terms: set[str] = set()
    restoration_terms: set[str] = set()
    first_excerpt = ""
    evidence_spans = 0

    for span in _local_spans(scanned):
        kind = _kind_for_span(span)
        if kind is None:
            continue
        evidence_spans += 1
        kinds.add(kind)
        cyber_terms.update(term.group(0).upper() for term in CYBER_EVENT_RE.finditer(span))
        no_material_terms.update(term.group(0).upper() for term in NO_MATERIAL_IMPACT_RE.finditer(span))
        containment_terms.update(term.group(0).upper() for term in CONTAINMENT_RE.finditer(span))
        restoration_terms.update(term.group(0).upper() for term in RESTORATION_RE.finditer(span))
        if not first_excerpt:
            first_excerpt = _clean_excerpt(span)

    if not kinds:
        return None
    primary_kind = max(kinds, key=lambda kind: KIND_SCORE[kind])
    return {
        "incident_kind": primary_kind,
        "incident_kinds": sorted(kinds),
        "cyber_evidence_span_count": evidence_spans,
        "cyber_terms": sorted(cyber_terms)[:16],
        "no_material_impact_terms": sorted(no_material_terms)[:8],
        "containment_terms": sorted(containment_terms)[:12],
        "restoration_terms": sorted(restoration_terms)[:12],
        "cyber_excerpt": first_excerpt,
        "contract_value_usd": None,
        "contract_duration_years": None,
        "contract_value_count": 0,
        "has_contract_value": False,
        "has_contract_duration": False,
        "contract_evidence_span_count": 0,
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
        stats[f"kind_{row.get('incident_kind') or 'unknown'}"] += 1
        stats["rows_with_no_material_impact_terms"] += 1 if row.get("no_material_impact_terms") else 0
        stats["rows_with_containment_terms"] += 1 if row.get("containment_terms") else 0
        stats["rows_with_restoration_terms"] += 1 if row.get("restoration_terms") else 0
    for rows in by_ticker.values():
        rows.sort(
            key=lambda row: (
                row["date"],
                -float(KIND_SCORE.get(str(row.get("incident_kind")), 0.0)),
                -float(row.get("cyber_evidence_span_count") or 0.0),
                row.get("accession_number") or "",
            )
        )
    index = {ticker: {"events": rows} for ticker, rows in by_ticker.items()}
    return index, {
        "sec_text_rows_loaded": len(text_rows),
        "tickers_with_cyber_events": len(by_ticker),
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
            kind = str(event.get("incident_kind") or "")
            kind_score = KIND_SCORE.get(kind, 0.0)
            if kind_score <= 0.0:
                scan["missing_incident_kind"] += 1
                continue
            span_component = min(float(event.get("cyber_evidence_span_count") or 0.0), 4.0) / 4.0
            score = (
                kind_score
                + 0.16 * span_component
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
                    "source": "SEC_TEXT_CYBER_CONTAINMENT_PAPER",
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
                    "text_cyber_score_kind": kind_score,
                    "text_cyber_span_component": prev._round(span_component, 6),
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
            -float(row.get("text_cyber_score_kind") or 0.0),
            -float(row.get("text_cyber_span_component") or 0.0),
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
        "positive_replay_lead_not_promoted_sec_cyber_incident_containment"
        if gate["passed"]
        else "rejected_sec_cyber_incident_containment_candidate_pool"
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
            f"# {EXPERIMENT_ID} SEC Cyber Incident Containment",
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
    prev.MIN_CONTRACT_VALUE_USD = 0.0
    prev.MAX_CONTRACT_VALUE_USD = 0.0
    prev.MIN_TEXT_WORDS = MIN_TEXT_WORDS
    prev.MAX_TEXT_CHARS_SCANNED = MAX_TEXT_CHARS_SCANNED
    prev.EVIDENCE_SPAN_CHARS = EVIDENCE_SPAN_CHARS
    prev.PREDICTION = PREDICTION
    prev.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    prev.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    prev._contract_economics = _cyber_event
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
            "The SEC cyber incident containment source cleared the numeric "
            "replay screen, but remains only a replay lead because no shared "
            "daily/backtest parser was promoted."
        )
    else:
        interpretation = (
            "The SEC cyber incident containment source did not clear "
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
            "mechanism_family": "production_visible_sec_text_cyber_incident_candidate_pool",
            "new_evidence_type": "sec_8k_cyber_incident_containment_no_material_impact_text",
            "nearby_prior_experiments": [
                "exp-20260505-033",
                "exp-20260620-018",
                "exp-20260621-014",
                "exp-20260621-022",
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
            "min_text_words": MIN_TEXT_WORDS,
            "max_text_chars_scanned": MAX_TEXT_CHARS_SCANNED,
            "evidence_span_chars": EVIDENCE_SPAN_CHARS,
            "cyber_event_terms": CYBER_EVENT_RE.pattern,
            "no_material_impact_terms": NO_MATERIAL_IMPACT_RE.pattern,
            "containment_terms": CONTAINMENT_RE.pattern,
            "restoration_terms": RESTORATION_RE.pattern,
            "active_negative_terms": ACTIVE_NEGATIVE_RE.pattern,
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
        "cybersecurity incident/update language plus containment, remediation, "
        "restoration, or no-material-impact evidence, while generic risk-"
        "factor, forward-looking, policy, contract-breach, and financing/legal "
        "contexts are excluded. Price confirmation uses only signal-date OHLCV. "
        "Paper entry is next available open; exit is the close 10 trading days "
        "after signal with existing costs."
    )
    payload["gate2"]["runtime_fields"] = [
        "SEC filing text combined_text",
        "SEC filing accepted_at and usable_trade_date",
        "SEC filing accession_number",
        "local evidence-span cybersecurity incident/update terms",
        "local evidence-span containment/remediation/restoration terms",
        "local evidence-span no-material-impact terms",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A valid retry needs materially richer PIT cyber provenance such as "
        "incident category, quantified business interruption, exfiltration/"
        "ransomware status, insurance/recovery evidence, customer churn or "
        "regulatory exposure, or closed forward replacement rows from a shared "
        "daily helper. Do not sweep cyber phrase lists, Item 1.05/8.01 item "
        "codes, RS/close/volume guards, top-N, hold, cooldown, or notional on "
        "these frozen windows."
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
            "Do not retry by sweeping cyber phrase lists, Item 1.05/8.01 item "
            "codes, no-material-impact/containment wording, RS/close/volume/"
            "vol guards, top-N, hold days, cooldown, or notional on these "
            "frozen windows."
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
