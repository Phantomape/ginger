"""exp-20260622-001: SEC public non-dilutive funding award scout.

Alpha-search replay scout. The single decision hypothesis is that issuer 8-K
text with explicit public-agency / government funding award provenance,
non-dilutive funding language, a local dollar amount, and financing/dilution
exclusions can expand the candidate pool with capital-efficient demand/support
events that continue after signal-day price absorption.

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


EXPERIMENT_ID = "exp-20260622-001"
STEM = "sec_public_funding_award"
TRIAL_FAMILY = "sec_text_non_dilutive_public_funding_candidate_pool"
TRIAL_VARIANT_ID = "sec_public_funding_award_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_8k_non_dilutive_public_funding_award_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = prev.REPO_ROOT
TEXT_DIR = prev.TEXT_DIR
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260622_001_{STEM}.json"
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

MIN_PUBLIC_FUNDING_VALUE_USD = 5_000_000.0
MAX_PUBLIC_FUNDING_VALUE_USD = 25_000_000_000.0
MIN_TEXT_WORDS = 120
MAX_TEXT_CHARS_SCANNED = 90_000
EVIDENCE_SPAN_CHARS = 650

TRIGGER_RE = re.compile(
    r"\b(awarded?|selected|receiv(?:ed|es?|ing)|granted|contract from|"
    r"contract award|cooperative agreement|direct funding|grant(?:ed)?|"
    r"subsidy|incentive)\b",
    re.IGNORECASE,
)
PUBLIC_COUNTERPARTY_RE = re.compile(
    r"\b(u\.s\. (?:department|army|navy|air force|government|federal|"
    r"department of)|united states (?:department|army|navy|air force|"
    r"government)|federal government|department of (?:energy|defense|"
    r"commerce|transportation|education|agriculture)|army|navy|air force|"
    r"nasa|nih|nsf|darpa|arpa-e|barda|chips and science act|chips act|"
    r"state of [A-Z][a-z]+)\b",
    re.IGNORECASE,
)
FUNDING_NOUN_RE = re.compile(
    r"\b(grant|direct funding|funding award|subsidy|incentive|"
    r"cooperative agreement|contract award|contract from|awarded up to|"
    r"awarding the company up to|chips and science act|chips act)\b",
    re.IGNORECASE,
)
VALUE_RE = re.compile(
    r"\$\s?([0-9][0-9,]*(?:\.[0-9]+)?)\s?"
    r"(billion|bn|million|mm|m)?",
    re.IGNORECASE,
)
EXCLUDE_RE = re.compile(
    r"\b(tax credit investments|consolidated investment entities|\bCIEs\b|"
    r"credit agreement|loan agreement|underwriting agreement|at-the-market|"
    r"atm offering|common stock|preferred stock|warrant|convertible|indenture|"
    r"debt|securities purchase|equity line|private placement|merger agreement|"
    r"settlement agreement|hosting payments|CoreWeave|customer|customers|ARR|"
    r"revenue growth|business update|income taxes|risk factors?)\b",
    re.IGNORECASE,
)

KIND_SCORE = {
    "chips_direct_funding": 1.25,
    "public_contract_award": 1.10,
    "grant_subsidy_incentive": 1.00,
    "public_funding_award": 0.90,
}

PREDICTION = {
    "success_probability": 0.14,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "false_positive_funding_language",
        "window_regression",
        "public_grants_not_incremental",
        "target_concentration_failed",
        "accepted_distribution_comparator_not_beaten",
        "drawdown_drift",
    ],
    "confidence_reason": (
        "Free SEC 8-K text has enough three-window coverage and public/"
        "non-dilutive funding is economically distinct from customer contracts "
        "and generic SEC item metadata, but SEC text parsing remains noisy and "
        "accepted comparators are strong."
    ),
    "recorded_at": "2026-06-22T00:10:57+00:00",
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
            "missing SEC filing text, missing public-agency/funding-award local "
            "evidence span, missing local dollar value, financing/dilution/"
            "private-contract false-positive text, missing OHLCV, missing next "
            "open, or missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper parses the same SEC "
        "8-K filing text fields, public-agency/funding evidence spans, "
        "exclusion rules, same-day OHLCV confirmation, cooldown, next-open "
        "paper entry, 10-day exit, costs, and concentration controls in both "
        "historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: PIT SEC 8-K disclosures that announce explicit "
        "non-dilutive government or public funding awards, grants, subsidies, "
        "incentives, or public-agency contract awards with local dollar-value "
        "evidence may identify capital-efficient demand/support shocks before "
        "next-open 10-day paper exit."
    ),
    "2_history_check": {
        "novelty_gate": (
            "Initial reservation was blocked near generic SEC text/event "
            "families. The override is valid because the evidence axis is PIT "
            "agency/public-counterparty non-dilutive funding award provenance "
            "with financing/dilution exclusions, not customer/supplier "
            "contract economics, raw 8-K metadata, coverage/complexity "
            "metadata, or contract value-to-market-cap threshold sweeps."
        ),
        "exp-20260617-011": (
            "Rejected SEC text contract economics. This run requires public "
            "agency/government funding-award provenance, not generic customer/"
            "supplier contract economics."
        ),
        "exp-20260619-017": (
            "Rejected public counterparty relation. This run tests the issuer "
            "event itself only when the public counterparty is tied to a local "
            "funding/award value and financing false positives are excluded."
        ),
        "exp-20260620-015": (
            "Rejected contract value-to-market-cap materiality. This run does "
            "not use Companyfacts shares outstanding or a contract/market-cap "
            "ratio; it uses public/non-dilutive funding provenance."
        ),
        "exp-20260621-014": (
            "Rejected customer prepayment/capacity commitment. This run is "
            "public funding/agency award provenance, not customer funding."
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
        "exp_20260622_001_sec_public_funding_award.py"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return prev._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return prev._round(value, digits)


def _clean_excerpt(text: str) -> str:
    return " ".join(str(text or "").split())[:360]


def _money_value(match: re.Match[str]) -> float | None:
    try:
        raw = float(match.group(1).replace(",", ""))
    except (TypeError, ValueError):
        return None
    unit = str(match.group(2) or "").lower()
    if unit in {"billion", "bn"}:
        value = raw * 1_000_000_000.0
    elif unit in {"million", "mm", "m"}:
        value = raw * 1_000_000.0
    else:
        value = raw
    if value < MIN_PUBLIC_FUNDING_VALUE_USD or value > MAX_PUBLIC_FUNDING_VALUE_USD:
        return None
    return value


def _nearest_money_value(span: str, trigger: re.Match[str]) -> float | None:
    candidates: list[tuple[int, int, float]] = []
    for value_match in VALUE_RE.finditer(span):
        value = _money_value(value_match)
        if value is None:
            continue
        distance = min(abs(value_match.start() - trigger.end()), abs(trigger.start() - value_match.end()))
        before_penalty = 0 if value_match.start() >= trigger.start() else 1
        candidates.append((distance, before_penalty, value))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1], -item[2]))
    return candidates[0][2]


def _event_kind(span: str) -> str:
    lowered = span.lower()
    if "chips act" in lowered or "chips and science act" in lowered:
        return "chips_direct_funding"
    if "contract award" in lowered or "contract from" in lowered or "air force" in lowered:
        return "public_contract_award"
    if any(term in lowered for term in ("grant", "subsidy", "incentive", "cooperative agreement")):
        return "grant_subsidy_incentive"
    return "public_funding_award"


def _public_funding_event(text: str) -> dict[str, Any] | None:
    if not text or len(text.split()) < MIN_TEXT_WORDS:
        return None
    scanned = text[:MAX_TEXT_CHARS_SCANNED]
    best: dict[str, Any] | None = None
    for trigger in TRIGGER_RE.finditer(scanned):
        start = max(0, trigger.start() - EVIDENCE_SPAN_CHARS)
        end = min(len(scanned), trigger.end() + EVIDENCE_SPAN_CHARS)
        span = scanned[start:end]
        if EXCLUDE_RE.search(span):
            continue
        if not PUBLIC_COUNTERPARTY_RE.search(span) or not FUNDING_NOUN_RE.search(span):
            continue
        value = _nearest_money_value(span, trigger)
        if value is None:
            continue
        kind = _event_kind(span)
        strength = KIND_SCORE[kind] + min(math.log10(value / MIN_PUBLIC_FUNDING_VALUE_USD), 3.0) * 0.15
        event = {
            "public_funding_value_usd": _round(value, 2),
            "public_funding_kind": kind,
            "public_funding_strength": _round(strength, 6),
            "public_funding_evidence_excerpt": _clean_excerpt(span),
            "public_funding_trigger": trigger.group(0),
            "text_word_count_scanned": len(scanned.split()),
        }
        if best is None or float(event["public_funding_strength"] or 0.0) > float(best["public_funding_strength"] or 0.0):
            best = event
    return best


def _load_sec_text_rows(*, max_filed: str, tickers: list[str] | None = None, **_: Any) -> list[dict[str, Any]]:
    allowed = {ticker.upper() for ticker in tickers or []}
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in sorted(TEXT_DIR.glob("sec_filing_text_*.jsonl")):
        with path.open(encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ticker = str(raw.get("ticker") or "").upper()
                if allowed and ticker not in allowed:
                    continue
                if str(raw.get("form_base") or raw.get("form_type") or "").upper() != "8-K":
                    continue
                usable_date = str(raw.get("usable_trade_date") or "")[:10]
                if not usable_date or usable_date > max_filed:
                    continue
                accession = str(raw.get("accession_number") or "")
                key = accession or f"{ticker}:{usable_date}:{raw.get('primary_document')}"
                if key in seen:
                    continue
                seen.add(key)
                event = _public_funding_event(str(raw.get("combined_text") or ""))
                if event is None:
                    continue
                rows.append(
                    {
                        "ticker": ticker,
                        "date": usable_date,
                        "filing_date": str(raw.get("filing_date") or "")[:10],
                        "accepted_at": str(raw.get("accepted_at") or "")[:19],
                        "accession_number": accession,
                        "form_type": raw.get("form_type"),
                        "eight_k_item_codes": raw.get("eight_k_item_codes") or [],
                        "primary_document": raw.get("primary_document"),
                        "text_char_count": raw.get("text_char_count"),
                        "text_word_count": raw.get("text_word_count"),
                        "pit_source": raw.get("pit_source"),
                        "pit_caveat": raw.get("pit_caveat"),
                        **event,
                    }
                )
    return rows


def _build_quality_index(
    text_rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    stats: Counter[str] = Counter()
    kind_counts: Counter[str] = Counter()
    for row in text_rows:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            stats["missing_ticker"] += 1
            continue
        by_ticker[ticker].append(row)
        kind_counts[str(row.get("public_funding_kind") or "unknown")] += 1
        stats["rows_with_public_funding_value"] += 1 if row.get("public_funding_value_usd") else 0
    for rows in by_ticker.values():
        rows.sort(
            key=lambda row: (
                row["date"],
                -float(row.get("public_funding_strength") or 0.0),
                -float(row.get("public_funding_value_usd") or 0.0),
                row.get("accession_number") or "",
            )
        )
    index = {ticker: {"events": rows} for ticker, rows in by_ticker.items()}
    return index, {
        "sec_text_rows_loaded": len(text_rows),
        "tickers_with_public_funding_awards": len(by_ticker),
        "public_funding_kind_counts": dict(kind_counts),
        "text_source": _repo_rel(TEXT_DIR),
        "min_public_funding_value_usd": MIN_PUBLIC_FUNDING_VALUE_USD,
        "max_public_funding_value_usd": MAX_PUBLIC_FUNDING_VALUE_USD,
        "evidence_span_chars": EVIDENCE_SPAN_CHARS,
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
            meta = sector_entries.get(ticker, {})
            value_component = min(
                math.log10(max(float(event.get("public_funding_value_usd") or 1.0), 1.0) / MIN_PUBLIC_FUNDING_VALUE_USD),
                3.0,
            )
            score = (
                0.85 * float(event.get("public_funding_strength") or 0.0)
                + 0.30 * value_component
                + 0.50 * float(confirm["candidate_ret20_excess_spy"])
                + 0.15 * float(confirm["candidate_ret60_excess_spy"])
                + 0.12 * float(confirm["candidate_close_location"])
                + 0.025 * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
            )
            scan["qualified_candidate_rows"] += 1
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "SEC_PUBLIC_FUNDING_AWARD_PAPER",
                    "candidate_score": _round(score, 6),
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
            -float(row.get("text_public_funding_strength") or 0.0),
            -float(row.get("text_public_funding_value_usd") or 0.0),
            -float(row["candidate_ret20_excess_spy"] or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(rows)
    scan["candidate_signal_days"] = len({row["date"] for row in rows})
    scan["candidate_tickers"] = len({row["ticker"] for row in rows})
    return rows, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "min_public_funding_value_usd": MIN_PUBLIC_FUNDING_VALUE_USD,
        "max_public_funding_value_usd": MAX_PUBLIC_FUNDING_VALUE_USD,
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
    gate = prev.base.framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    ev_delta = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if ev_delta <= prev.base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_compression_ev_not_beaten")
    if pnl_delta <= prev.base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_compression_pnl_not_beaten")
    if ev_delta <= prev.base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_distribution_ev_not_beaten")
    if pnl_delta <= prev.base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_distribution_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["accepted_compression_comparator"] = prev.base.COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = prev.base.DISTRIBUTION_COMPARATOR
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_not_promoted_sec_public_funding_award"
        if gate["passed"]
        else "rejected_sec_public_funding_award_candidate_pool"
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
            f"# {EXPERIMENT_ID} SEC Public Funding Award",
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


def _configure_base() -> None:
    prev.base.EXPERIMENT_ID = EXPERIMENT_ID
    prev.base.STEM = STEM
    prev.base.TRIAL_FAMILY = TRIAL_FAMILY
    prev.base.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    prev.base.CHANGED_VARIABLE = CHANGED_VARIABLE
    prev.base.RULE_VERSION = RULE_VERSION
    prev.base.OWNER = OWNER
    prev.base.OUT_DIR = OUT_DIR
    prev.base.OUT_JSON = OUT_JSON
    prev.base.LOG_JSON = LOG_JSON
    prev.base.TICKET_JSON = TICKET_JSON
    prev.base.CARD_MD = CARD_MD
    prev.base.MANIFEST_JSON = MANIFEST_JSON
    prev.base.EXPERIMENT_LOG = EXPERIMENT_LOG
    prev.base.REGISTRY_JSON = REGISTRY_JSON
    prev.base.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    prev.base.HOLD_DAYS = HOLD_DAYS
    prev.base.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    prev.base.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    prev.base.PREDICTION = PREDICTION
    prev.base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    prev.base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    prev.base.load_companyfacts_rows = _load_sec_text_rows
    prev.base._build_quality_index = _build_quality_index
    prev.base._candidate_rows_for_window = _candidate_rows_for_window
    prev.base._gate4 = _gate4
    prev.base._build_card = _build_card


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    if gate4["passed"]:
        interpretation = (
            "The SEC public non-dilutive funding award source cleared the "
            "numeric three-window replay screen, but remains only a replay "
            "lead because no shared daily/backtest parser was promoted."
        )
    else:
        interpretation = (
            "The SEC public non-dilutive funding award source did not clear "
            f"Gate 4 (failed: {', '.join(gate4['failed_reasons']) or 'none'}). "
            "It is not retained or promoted."
        )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
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
            "mechanism_family": "production_visible_sec_text_public_funding_candidate_pool",
            "new_evidence_type": "sec_8k_non_dilutive_government_public_funding_award_text",
            "nearby_prior_experiments": [
                "exp-20260617-011",
                "exp-20260619-017",
                "exp-20260620-015",
                "exp-20260621-014",
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
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": 1 if gate4["passed"] else 0,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
    }
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "min_public_funding_value_usd": MIN_PUBLIC_FUNDING_VALUE_USD,
        "max_public_funding_value_usd": MAX_PUBLIC_FUNDING_VALUE_USD,
        "min_text_words": MIN_TEXT_WORDS,
        "max_text_chars_scanned": MAX_TEXT_CHARS_SCANNED,
        "evidence_span_chars": EVIDENCE_SPAN_CHARS,
        "min_price": prev.base.MIN_PRICE,
        "min_avg_dollar_volume_20d": prev.base.MIN_AVG_DOLLAR_VOLUME_20D,
        "min_ret20_excess_spy": prev.base.MIN_RET20_EXCESS_SPY,
        "min_ret60_excess_spy": prev.base.MIN_RET60_EXCESS_SPY,
        "min_signal_return": prev.base.MIN_SIGNAL_RETURN,
        "max_signal_return": prev.base.MAX_SIGNAL_RETURN,
        "min_close_location": prev.base.MIN_CLOSE_LOCATION,
        "max_realized_vol_20d": prev.base.MAX_REALIZED_VOL_20D,
        "trigger_terms": TRIGGER_RE.pattern,
        "public_counterparty_terms": PUBLIC_COUNTERPARTY_RE.pattern,
        "funding_noun_terms": FUNDING_NOUN_RE.pattern,
        "exclude_terms": EXCLUDE_RE.pattern,
        "kind_score": KIND_SCORE,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"].pop("companyfacts_source", None)
    payload["backtest_protocol"]["sec_filing_text_source"] = _repo_rel(TEXT_DIR)
    payload["backtest_protocol"]["execution_model"] = (
        "8-K SEC filing text is keyed by accepted_at and usable_trade_date. "
        "The parser admits rows only when a local evidence span contains "
        "public-agency/government provenance, funding-award/grant/subsidy/"
        "incentive or public-contract-award semantics, and a local dollar "
        "amount, while equity/debt/ATM/loan/settlement/private-customer/"
        "generic earnings false-positive contexts are excluded. Price "
        "confirmation uses only signal-date OHLCV. Paper entry is next "
        "available open; exit is the close 10 trading days after signal with "
        "existing costs."
    )
    payload["gate2"]["runtime_fields"] = [
        "SEC filing text combined_text",
        "SEC filing accepted_at and usable_trade_date",
        "SEC filing accession_number",
        "local evidence-span public counterparty terms",
        "local evidence-span funding award terms",
        "local evidence-span extracted dollar value",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A valid retry needs materially richer PIT public-funding provenance "
        "such as normalized agency/program identifiers, award type, obligated "
        "versus potential value, non-dilutive grant/accounting treatment, "
        "named program economics, or closed forward replacement-value rows "
        "from a shared daily helper. Do not sweep phrase lists, public-agency "
        "terms, value thresholds, RS/close/volume guards, top-N, hold, "
        "cooldown, or notional on these frozen windows."
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
            "Do not retry by sweeping public funding phrase lists, agency "
            "terms, value thresholds, item codes, RS/close/volume/vol guards, "
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


def main() -> None:
    _configure_base()
    payload = _postprocess_payload(prev.base._build_payload())
    _persist(payload)
    print(json.dumps(prev.base.framework._safe(prev.base._build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
