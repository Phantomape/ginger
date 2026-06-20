"""exp-20260620-006: SEC refinancing/covenant relief text scout.

Replay-only alpha search. The single decision hypothesis is a free PIT SEC
8-K/exhibit text candidate source: issuer filings that explicitly report
refinancing, credit facility amendments, maturity extensions, covenant relief,
waivers, or upsized liquidity may identify balance-sheet de-risking events
before next-open 10-trading-day continuation, when paired with liquid
SPY-relative confirmation.

This is private replay first because deterministic financing-text extraction is
noisy and has no shared daily/backtest contract yet. A positive replay is only
a lead until a shared default-off helper reproduces the same PIT filing-text
semantics in historical replay and daily production. No production code, run
adapter, backtester adapter, ranking, sizing, exits, orders, LLM/news path, or
watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260614_020_accruals_cash_conversion_quality as base
import exp_20260617_021_intraindustry_liquidity_leader_lead_lag_scout as broad_static


EXPERIMENT_ID = "exp-20260620-006"
STEM = "sec_refinancing_covenant_relief_text"
TRIAL_FAMILY = "sec_refinancing_covenant_relief_text_candidate_pool"
TRIAL_VARIANT_ID = "sec_refinancing_covenant_relief_text_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_refinancing_covenant_relief_text_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
TEXT_DIR = REPO_ROOT / "data" / "non_ohlcv"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260620_006_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = base.BASE_NOTIONAL_USD
HOLD_DAYS = base.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = base.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = base.SAME_TICKER_COOLDOWN_DAYS

MIN_TEXT_WORDS = 120
MAX_TEXT_CHARS_SCANNED = 80_000
MATCH_CONTEXT_CHARS = 900

TERM_PATTERNS: tuple[tuple[str, re.Pattern[str], float], ...] = (
    (
        "refinancing",
        re.compile(r"\b(REFINANC(?:E|ED|ING)|REFINANCED DEBT|REFINANCING TRANSACTION)\b", re.IGNORECASE),
        1.45,
    ),
    (
        "credit_facility",
        re.compile(
            r"\b(REVOLVING CREDIT FACILITY|CREDIT FACILITY|CREDIT AGREEMENT|"
            r"TERM LOAN|SENIOR SECURED CREDIT|ASSET[-\s]?BASED LENDING|ABL FACILITY)\b",
            re.IGNORECASE,
        ),
        1.20,
    ),
    (
        "maturity_extension",
        re.compile(
            r"\b(MATURIT(?:Y|IES).{0,140}(?:EXTEND|EXTENDED|EXTENSION)|"
            r"(?:EXTEND|EXTENDED|EXTENSION).{0,140}MATURIT(?:Y|IES)|"
            r"EXTENDED THE TERM|EXTENDED ITS TERM)\b",
            re.IGNORECASE,
        ),
        1.35,
    ),
    (
        "covenant_relief",
        re.compile(
            r"\b(COVENANT RELIEF|COVENANT WAIVER|WAIVER OF.{0,80}COVENANT|"
            r"AMEND(?:ED|MENT).{0,120}COVENANT|FINANCIAL COVENANT)\b",
            re.IGNORECASE,
        ),
        1.30,
    ),
    (
        "liquidity_upsize",
        re.compile(
            r"\b(UPSIZ(?:E|ED|ING)|INCREASED.{0,90}COMMITMENTS?|"
            r"AVAILABLE BORROWING|UNDRAWN|LIQUIDITY|BORROWING CAPACITY|"
            r"TOTAL COMMITMENTS? OF)\b",
            re.IGNORECASE,
        ),
        1.10,
    ),
)
ACTION_RE = re.compile(
    r"\b(ENTERED INTO|AMENDED|AMENDMENT|CLOSED|COMPLETED|SECURED|OBTAINED|"
    r"INCREASED|UPSIZED|EXTENDED|REFINANCED|REPAID|REDEEMED|REPLACED|"
    r"WAIVED|WAIVER|COMMITMENT|AVAILABILITY|PROCEEDS|MATURITY EXTENSION)\b",
    re.IGNORECASE,
)
NUMERIC_EVIDENCE_RE = re.compile(
    r"(?:\$[0-9][0-9,.]*(?:\.\d+)?\s?(?:BILLION|MILLION|BN|MM|M)?|"
    r"\b[0-9]{4}\b|[0-9][0-9,.]*\s?(?:%|PERCENT|BPS|BASIS POINTS?))",
    re.IGNORECASE,
)
NEGATIVE_RE = re.compile(
    r"\b(DEFAULT|GOING CONCERN|SUBSTANTIAL DOUBT|BANKRUPT|BANKRUPTCY|"
    r"COVENANT VIOLATION|BREACH|NON[-\s]?COMPLIANCE|ACCELERATION OF DEBT)\b",
    re.IGNORECASE,
)
EQUITY_DILUTION_RE = re.compile(
    r"\b(COMMON STOCK|AT[-\s]?THE[-\s]?MARKET|ATM OFFERING|REGISTERED DIRECT|"
    r"EQUITY LINE|UNDERWRITING AGREEMENT|WARRANTS?|PREFERRED STOCK|UNITS?)\b",
    re.IGNORECASE,
)
NORMALIZE_RE = re.compile(r"[^A-Z0-9%$]+")

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.25,
    "expected_pnl_delta": 3500.0,
    "main_failure_modes": [
        "sample_too_thin",
        "generic_financing_text_noise",
        "offering_dilution_mixed",
        "old_thin_coverage_gap",
        "accepted_sec_or_distribution_comparator_not_beaten",
        "drawdown_drift",
    ],
    "confidence_reason": (
        "The playbook explicitly calls for parsed debt maturity, covenant, and "
        "refinancing terms as a new evidence axis after raw Companyfacts debt "
        "and DPO/debt intersections failed. This run tests SEC primary text "
        "financing-term provenance, not another raw leverage ratio or broad "
        "OHLCV continuation retune. Failure risk is high because financing "
        "language can mix constructive liquidity repair with dilution or "
        "distress."
    ),
    "recorded_at": "2026-06-20T06:10:03Z",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "uses_free_sec_filing_text": True,
    "uses_free_sec_companyfacts": False,
    "uses_free_ohlcv": True,
    "uses_llm": False,
    "trade_enabled": False,
    "execution_envelope": {
        **base.PRODUCTION_IMPACT["execution_envelope"],
        "candidate_universe": "broad liquid warehouse names with PIT issuer SEC 8-K/exhibit text",
        "failure_handling": (
            "missing SEC filing text, missing usable_trade_date, missing "
            "refinancing/credit/covenant/liquidity term, missing action or "
            "numeric evidence, distress/dilution false-positive context, "
            "missing OHLCV, missing next open, or missing 10d exit rejects the "
            "paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper parses the same PIT "
        "SEC 8-K/exhibit text fields, financing-term category rules, numeric/"
        "action/negative/exclusion evidence, same-day OHLCV confirmation, "
        "cooldown, next-open paper entry, 10-day exit, costs, and concentration "
        "controls in both historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: issuer SEC 8-K or exhibit text with explicit "
        "refinancing, credit-facility amendment, maturity extension, covenant "
        "relief, waiver, or upsized liquidity terms, paired with liquid "
        "SPY-relative confirmation, may surface balance-sheet de-risking "
        "underreaction candidates before a 10-trading-day continuation leg."
    ),
    "2_history_check": {
        "novelty_gate": (
            "Experiment reservation warned near broad OHLCV continuation "
            "families, but override was used because the evidence axis is SEC "
            "primary-text financing-term provenance. A direct novelty probe "
            "with data_source=sec_text produced no blocking near-neighbor."
        ),
        "exp-20260615-001": (
            "Rejected SEC earnings-release deleveraging/liquidity repair text; "
            "that run used broader balance-sheet repair language. This run "
            "requires explicit refinancing, covenant, maturity, waiver, or "
            "facility terms from primary filing text."
        ),
        "exp-20260616-029": (
            "Rejected raw Companyfacts principal debt burden relief. This run "
            "uses primary-text financing-term events rather than balance-sheet "
            "debt ratios."
        ),
        "exp-20260619-002": (
            "Interest-burden relief near-neighbor was blocked; this run uses "
            "non-Companyfacts contractual financing terms."
        ),
        "exp-20260620-005": (
            "Supplier-financing plus debt-relief intersection was rejected due "
            "to drawdown drift. This run does not retune DPO or raw debt relief."
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
        "exp_20260620_006_sec_refinancing_covenant_relief_text.py"
    ),
}

_TEXT_REFINANCING_CACHE: tuple[list[dict[str, Any]], dict[str, Any]] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return base._round(value, digits)


def _normalized_excerpt(text: str, limit: int = 360) -> str:
    return NORMALIZE_RE.sub(" ", str(text or "").upper()).strip()[:limit]


def _context_features(context: str, category: str, category_weight: float) -> dict[str, Any] | None:
    action_terms = sorted({match.group(0).upper() for match in ACTION_RE.finditer(context)})
    numeric_terms = sorted({match.group(0).upper() for match in NUMERIC_EVIDENCE_RE.finditer(context)})
    negative_terms = sorted({match.group(0).upper() for match in NEGATIVE_RE.finditer(context)})
    equity_terms = sorted({match.group(0).upper() for match in EQUITY_DILUTION_RE.finditer(context)})
    if not action_terms and not numeric_terms:
        return None
    has_relief_term = bool(re.search(r"\b(WAIVER|RELIEF|REFINANC|EXTENDED|UPSIZED)\b", context, re.IGNORECASE))
    if negative_terms and not has_relief_term:
        return None
    if equity_terms and category not in {"refinancing", "maturity_extension"}:
        return None
    strength = (
        category_weight
        + 0.070 * min(len(action_terms), 8)
        + 0.055 * min(len(numeric_terms), 8)
        - 0.120 * min(len(negative_terms), 5)
        - 0.090 * min(len(equity_terms), 5)
    )
    if category in {"refinancing", "maturity_extension", "covenant_relief"}:
        strength += 0.10
    if any("WAIVER" in term or "EXTENDED" in term or "UPSIZED" in term for term in action_terms):
        strength += 0.08
    return {
        "financing_category": category,
        "financing_strength": _round(strength, 6),
        "action_terms": action_terms[:10],
        "numeric_evidence_terms": numeric_terms[:10],
        "negative_terms": negative_terms[:10],
        "equity_dilution_terms": equity_terms[:10],
        "context_excerpt_normalized": _normalized_excerpt(context),
    }


def _extract_refinancing_row(raw: dict[str, Any]) -> dict[str, Any] | None:
    ticker = str(raw.get("ticker") or "").upper()
    if str(raw.get("form_base") or raw.get("form_type") or "").upper() != "8-K":
        return None
    usable_date = str(raw.get("usable_trade_date") or "")[:10]
    if not ticker or not usable_date:
        return None
    text = str(raw.get("combined_text") or "")
    if len(text.split()) < MIN_TEXT_WORDS:
        return None
    scanned = text[:MAX_TEXT_CHARS_SCANNED]
    best: dict[str, Any] | None = None
    for category, regex, weight in TERM_PATTERNS:
        for match in regex.finditer(scanned):
            left = max(0, match.start() - MATCH_CONTEXT_CHARS)
            right = min(len(scanned), match.end() + MATCH_CONTEXT_CHARS)
            context = scanned[left:right]
            features = _context_features(context, category, weight)
            if features is None:
                continue
            row = {
                "ticker": ticker,
                "date": usable_date,
                "filing_date": str(raw.get("filing_date") or "")[:10],
                "accepted_at": str(raw.get("accepted_at") or "")[:19],
                "accession_number": str(raw.get("accession_number") or ""),
                "form_type": raw.get("form_type"),
                "eight_k_item_codes": raw.get("eight_k_item_codes") or [],
                "primary_document": raw.get("primary_document"),
                "text_char_count": raw.get("text_char_count"),
                "text_word_count": raw.get("text_word_count"),
                "pit_source": raw.get("pit_source"),
                "pit_caveat": raw.get("pit_caveat"),
                "matched_financing_term": match.group(0).upper(),
                **features,
            }
            if best is None or float(row["financing_strength"] or 0.0) > float(
                best["financing_strength"] or 0.0
            ):
                best = row
    return best


def _load_sec_text_rows(*, max_filed: str, tickers: list[str] | None = None, **_: Any) -> list[dict[str, Any]]:
    del tickers
    global _TEXT_REFINANCING_CACHE
    if _TEXT_REFINANCING_CACHE is None:
        rows: list[dict[str, Any]] = []
        scan: Counter[str] = Counter()
        seen: set[str] = set()
        for path in sorted(TEXT_DIR.glob("sec_filing_text_*.jsonl")):
            with path.open(encoding="utf-8", errors="ignore") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    try:
                        raw = json.loads(line)
                    except json.JSONDecodeError:
                        scan["json_decode_errors"] += 1
                        continue
                    scan["raw_text_rows"] += 1
                    if str(raw.get("form_base") or raw.get("form_type") or "").upper() != "8-K":
                        scan["non_8k_rows"] += 1
                        continue
                    accession = str(raw.get("accession_number") or "")
                    key = accession or f"{raw.get('ticker')}:{raw.get('usable_trade_date')}:{raw.get('primary_document')}"
                    if key in seen:
                        scan["duplicate_accession"] += 1
                        continue
                    seen.add(key)
                    row = _extract_refinancing_row(raw)
                    if row is None:
                        scan["8k_rows_without_refinancing_covenant_relief_text"] += 1
                        continue
                    rows.append(row)
                    scan[f"category_{row['financing_category']}"] += 1
        rows.sort(
            key=lambda row: (
                row["date"],
                row["ticker"],
                -(float(row.get("financing_strength") or 0.0)),
                row.get("accession_number") or "",
            )
        )
        _TEXT_REFINANCING_CACHE = (rows, dict(scan))
    rows, _scan = _TEXT_REFINANCING_CACHE
    return [row for row in rows if str(row.get("date") or "")[:10] <= max_filed]


def _build_quality_index(
    text_rows: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    stats: Counter[str] = Counter()
    for row in text_rows:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            stats["missing_ticker"] += 1
            continue
        by_ticker[ticker].append(row)
        stats[f"category_{row.get('financing_category') or 'unknown'}"] += 1
    for rows in by_ticker.values():
        rows.sort(
            key=lambda row: (
                row["date"],
                -(float(row.get("financing_strength") or 0.0)),
                row.get("accession_number") or "",
            )
        )
    _all_rows, raw_scan = _TEXT_REFINANCING_CACHE or ([], {})
    return dict(by_ticker), {
        "sec_text_rows_loaded": len(text_rows),
        "tickers_with_refinancing_covenant_relief_text": len(by_ticker),
        "text_source": _repo_rel(TEXT_DIR),
        "min_text_words": MIN_TEXT_WORDS,
        "max_text_chars_scanned": MAX_TEXT_CHARS_SCANNED,
        "match_context_chars": MATCH_CONTEXT_CHARS,
        "raw_text_scan": raw_scan,
        **dict(stats),
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indices = {
        ticker: base.framework.shadow._row_index(base.framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    scan: Counter[str] = Counter()
    candidates: list[dict[str, Any]] = []
    for ticker in sorted(set(quality_index) & set(snapshot)):
        for event in quality_index[ticker]:
            signal_date = str(event.get("date") or "")[:10]
            if not (str(cfg["start"]) <= signal_date <= str(cfg["end"])):
                continue
            scan["event_rows_in_window"] += 1
            confirm = base._price_confirmation(
                snapshot=snapshot,
                indices=indices,
                ticker=ticker,
                signal_date=signal_date,
            )
            if confirm is None:
                scan["failed_price_confirmation"] += 1
                continue
            meta = sector_entries.get(ticker, {})
            event_strength = float(event.get("financing_strength") or 0.0)
            score = (
                event_strength
                + 0.45 * float(confirm["candidate_ret20_excess_spy"])
                + 0.14 * float(confirm["candidate_ret60_excess_spy"])
                + 0.12 * float(confirm["candidate_close_location"])
                + 0.025
                * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
            )
            scan["qualified_candidate_rows"] += 1
            scan[f"qualified_{event.get('financing_category') or 'unknown'}"] += 1
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "SEC_REFINANCING_COVENANT_RELIEF_TEXT_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "sec_8k_text_usable_trade_date_and_signal_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_filing_text": True,
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
            -float(row.get("text_financing_strength") or 0.0),
            -float(row["candidate_ret20_excess_spy"] or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(rows)
    scan["candidate_signal_days"] = len({row["date"] for row in rows})
    scan["candidate_tickers"] = len({row["ticker"] for row in rows})
    scan["eligible_quality_tickers"] = len(quality_index)
    return rows, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "min_text_words": MIN_TEXT_WORDS,
        "max_text_chars_scanned": MAX_TEXT_CHARS_SCANNED,
        "match_context_chars": MATCH_CONTEXT_CHARS,
        "candidate_universe": "broad_liquid_warehouse_all_windows_full_liquid",
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = base.framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    ev_delta = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if ev_delta <= base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_compression_ev_not_beaten")
    if pnl_delta <= base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_compression_pnl_not_beaten")
    if ev_delta <= base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_distribution_ev_not_beaten")
    if pnl_delta <= base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_distribution_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["accepted_compression_comparator"] = base.COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = base.DISTRIBUTION_COMPARATOR
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_not_promoted_sec_refinancing_covenant_relief_text"
        if gate["passed"]
        else "rejected_sec_refinancing_covenant_relief_text_candidate_pool"
    )
    return gate


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Text Events | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {events} | {trades} |".format(
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
            f"# {EXPERIMENT_ID} SEC Refinancing/Covenant Relief Text",
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
                base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"],
                base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Accepted distribution comparator: EV `{:+.4f}`, PnL `${:+,.2f}`".format(
                base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"],
                base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Production Impact",
            "",
            (
                "Replay-only and default-off paper only. No shared policy, run "
                "adapter, backtester adapter, production watchlist, order path, "
                "core entry, ranking, sizing, or exit behavior changed."
            ),
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _configure_base() -> None:
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
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    base.load_companyfacts_rows = _load_sec_text_rows
    base._build_quality_index = _build_quality_index
    base._candidate_rows_for_window = _candidate_rows_for_window
    base._gate4 = _gate4
    base._build_card = _build_card
    base._load_window_snapshot = broad_static._broad_load_window_snapshot


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    total_events = sum(
        int(scan.get("event_rows_in_window") or 0)
        for scan in payload["context_scan_by_window"].values()
    )
    total_trades = int(payload["target_trade_summary"]["total_trade_count"] or 0)
    if gate4["passed"]:
        interpretation = (
            "SEC refinancing/covenant relief text cleared the numeric "
            "three-window replay screen, but remains only a replay lead because "
            "no shared daily/backtest parser was promoted."
        )
    elif total_trades == 0:
        interpretation = (
            "SEC refinancing/covenant relief text did not clear Gate 4 "
            f"(failed: {', '.join(gate4['failed_reasons']) or 'none'}). The "
            f"parser found {total_events} in-window financing events, but none "
            "survived liquidity/price confirmation and next-open/10d execution."
        )
    else:
        interpretation = (
            "SEC refinancing/covenant relief text did not clear Gate 4 "
            f"(failed: {', '.join(gate4['failed_reasons']) or 'none'}). The "
            f"source produced {total_trades} paper trades from {total_events} "
            "in-window financing events, but the bundle did not beat the "
            "canonical three-window EV/PnL/risk/comparator screen."
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
            "mechanism_family": "production_visible_free_sec_text_refinancing_covenant_relief_candidate_pool",
            "new_evidence_type": "sec_primary_text_refinancing_covenant_maturity_liquidity_terms",
            "nearby_prior_experiments": [
                "exp-20260615-001",
                "exp-20260616-029",
                "exp-20260619-002",
                "exp-20260620-005",
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
        "candidate_universe": "broad_liquid_warehouse_all_windows_full_liquid",
        "min_text_words": MIN_TEXT_WORDS,
        "max_text_chars_scanned": MAX_TEXT_CHARS_SCANNED,
        "match_context_chars": MATCH_CONTEXT_CHARS,
        "min_price": base.MIN_PRICE,
        "min_avg_dollar_volume_20d": base.MIN_AVG_DOLLAR_VOLUME_20D,
        "min_ret20_excess_spy": base.MIN_RET20_EXCESS_SPY,
        "min_ret60_excess_spy": base.MIN_RET60_EXCESS_SPY,
        "min_signal_return": base.MIN_SIGNAL_RETURN,
        "max_signal_return": base.MAX_SIGNAL_RETURN,
        "min_close_location": base.MIN_CLOSE_LOCATION,
        "max_realized_vol_20d": base.MAX_REALIZED_VOL_20D,
        "financing_categories": [label for label, _regex, _weight in TERM_PATTERNS],
        "action_terms": ACTION_RE.pattern,
        "numeric_evidence": NUMERIC_EVIDENCE_RE.pattern,
        "negative_terms": NEGATIVE_RE.pattern,
        "equity_dilution_terms": EQUITY_DILUTION_RE.pattern,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["companyfacts_source"] = None
    payload["backtest_protocol"]["sec_filing_text_source"] = _repo_rel(TEXT_DIR)
    payload["backtest_protocol"]["candidate_ohlcv_source"] = _repo_rel(base.framework.WAREHOUSE)
    payload["backtest_protocol"]["execution_model"] = (
        "Issuer SEC 8-K/exhibit filing text is keyed by accepted_at and "
        "usable_trade_date. The parser requires a refinancing, credit facility, "
        "maturity extension, covenant relief, waiver, or liquidity-upsize term "
        "inside local context plus action or numeric evidence, while distress "
        "and equity-dilution false positives are rejected or penalized. The "
        "candidate is the filing issuer. Price confirmation uses only "
        "signal-date OHLCV and SPY relative strength. Paper entry is the next "
        "available open with existing entry slippage; exit is the close 10 "
        "trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT. The core baseline remains the canonical core "
        "replay; only the default-off paper candidate snapshot uses the broad "
        "liquid universe."
    )
    payload["gate2"]["runtime_fields"] = [
        "SEC filing text combined_text",
        "SEC filing accepted_at and usable_trade_date",
        "SEC filing accession_number",
        "extracted financing category, action terms, numeric evidence terms, negative terms, and dilution terms",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume for issuer ticker",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A retry needs materially cleaner structured debt-event tuples, such as "
        "maturity ladder before/after, covenant headroom, facility availability "
        "versus market cap, dilution-adjusted financing terms, or closed "
        "forward replacement rows. Do not sweep financing phrase lists, "
        "RS/close/volume/vol guards, top-N, hold, cooldown, or notional on "
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
                total_trades,
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping refinancing/covenant phrase lists, "
            "numeric/action/equity filters, item codes, RS/close/volume/vol "
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


def _persist(payload: dict[str, Any]) -> None:
    log_record = base._build_log_record(payload)
    base.framework._write_json(OUT_JSON, payload)
    base.framework._write_json(LOG_JSON, payload)
    base.framework._write_text(CARD_MD, _build_card(payload))
    base.framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
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
    base.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )
    _write_manifest(payload)


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(Path(__file__)): base.framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): base.framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): base.framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): base.framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): base.framework._sha256(CARD_MD),
        },
    }
    base.framework._write_json(MANIFEST_JSON, manifest)


def main() -> None:
    _configure_base()
    payload = _postprocess_payload(base._build_payload())
    _persist(payload)
    print(json.dumps(base.framework._safe(base._build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
