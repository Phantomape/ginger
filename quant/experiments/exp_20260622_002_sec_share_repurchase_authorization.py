"""exp-20260622-002: SEC share-repurchase authorization scout.

Alpha-search replay scout. The single decision hypothesis is that fresh
8-K text disclosing a board-authorized share-repurchase program or expansion,
with a local dollar amount and financing/offering exclusions, can identify
shareholder-yield support shocks that continue after signal-day absorption.

This is deliberately replay-only/default-off. It changes no production
strategy code, shared helper, daily snapshot, live/default orders, ranking,
sizing, exits, watchlist, LLM, or news path. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260622_001_sec_public_funding_award as prior


EXPERIMENT_ID = "exp-20260622-002"
STEM = "sec_share_repurchase_authorization"
TRIAL_FAMILY = "sec_text_share_repurchase_authorization_candidate_pool"
TRIAL_VARIANT_ID = "sec_share_repurchase_authorization_top1_next_open_10d_v1"
CHANGED_VARIABLE = "sec_8k_share_repurchase_authorization_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

base = prior.prev.base
REPO_ROOT = prior.REPO_ROOT
TEXT_DIR = prior.TEXT_DIR
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260622_002_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = prior.BASE_NOTIONAL_USD
HOLD_DAYS = prior.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = prior.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = prior.SAME_TICKER_COOLDOWN_DAYS

MIN_AUTH_VALUE_USD = 50_000_000.0
MAX_AUTH_VALUE_USD = 200_000_000_000.0
MIN_TEXT_WORDS = 120
MAX_TEXT_CHARS_SCANNED = 90_000
EVIDENCE_SPAN_CHARS = 700

REPURCHASE_TRIGGER_RE = re.compile(
    r"\b(authori[sz](?:ed|es?|ation)|approv(?:ed|es?)|announc(?:ed|es?)|"
    r"adopt(?:ed|s)?|expand(?:ed|s)?|increase(?:d|s)?|renew(?:ed|s)?|"
    r"replace(?:d|s)?|new)\b",
    re.IGNORECASE,
)
REPURCHASE_NOUN_RE = re.compile(
    r"\b(share repurchase|stock repurchase|common stock repurchase|"
    r"repurchase program|repurchase plan|buyback|buy-back)\b",
    re.IGNORECASE,
)
BOARD_OR_FRESH_RE = re.compile(
    r"\b(board of directors|board|new share repurchase|new stock repurchase|"
    r"additional|increased|expanded|authorized|approved|program)\b",
    re.IGNORECASE,
)
VALUE_RE = re.compile(
    r"\$\s?([0-9][0-9,]*(?:\.[0-9]+)?)\s?"
    r"(billion|bn|million|mm|m)?",
    re.IGNORECASE,
)
EXCLUDE_RE = re.compile(
    r"\b(repurchase agreement|securities repurchase agreement|repo agreement|"
    r"credit agreement|loan agreement|underwriting agreement|at-the-market|"
    r"atm offering|common stock offering|preferred stock|warrant|convertible|"
    r"indenture|debt securities|securities purchase|equity line|private placement|"
    r"tender offer|merger agreement|settlement agreement|tax withholding|"
    r"shares withheld|withheld to cover|employee benefit plan|risk factors?)\b",
    re.IGNORECASE,
)
HISTORICAL_ONLY_RE = re.compile(
    r"\b(during the (?:three|six|nine|twelve) months|during fiscal|"
    r"for the year ended|repurchased approximately|remaining authorization|"
    r"remaining under|as of .{0,24} remained)\b",
    re.IGNORECASE,
)

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "old_thin_regression",
        "drawdown_drift",
        "authorized_not_executed",
        "accepted_distribution_comparator_not_beaten",
        "thin_sample",
    ],
    "confidence_reason": (
        "Fresh 8-K authorization timing is materially different from the "
        "rejected annual Companyfacts actual-repurchase/OCF ratio, but buyback "
        "and SEC-text families are crowded and authorization may not translate "
        "into near-term executed demand."
    ),
    "recorded_at": "2026-06-22T01:04:44+00:00",
}

PRODUCTION_IMPACT = {
    **prior.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "uses_free_sec_filing_text": True,
    "uses_free_sec_companyfacts": False,
    "uses_raw_companyfacts_cache": False,
    "execution_envelope": {
        **prior.PRODUCTION_IMPACT["execution_envelope"],
        "failure_handling": (
            "missing SEC filing text, missing fresh board/share-repurchase "
            "authorization local evidence span, missing local dollar amount, "
            "financing/offering/repurchase-agreement false-positive text, "
            "missing OHLCV, missing next open, or missing 10d exit rejects the "
            "paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper parses the same SEC "
        "8-K filing text fields, fresh authorization evidence spans, exclusion "
        "rules, same-day OHLCV confirmation, cooldown, next-open paper entry, "
        "10-day exit, costs, and concentration controls in both historical "
        "replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: PIT SEC 8-K disclosures of fresh board-authorized "
        "share-repurchase programs or expansions with explicit dollar-value "
        "evidence may identify shareholder-yield support shocks before a "
        "next-open 10-day default-off paper continuation."
    ),
    "2_history_check": {
        "novelty_gate": (
            "experiment.py new warned on nearby governance/shareholder-yield "
            "families and accepted an override. New evidence axis is fresh SEC "
            "8-K authorization or expansion timestamp with local dollar amount "
            "and financing/offering exclusions, not annual Companyfacts actual "
            "repurchase cash flow, per-share SBC net of buybacks, dividend "
            "signaling, or generic SEC text."
        ),
        "exp-20260616-009": (
            "Rejected actual annual repurchase cash flow covered by OCF. It had "
            "positive aggregate PnL but old_thin and drawdown failed. This run "
            "tests fresh event timing rather than stale annual cash-flow facts."
        ),
        "exp-20260616-017": (
            "Rejected per-share SBC net of buybacks. This run does not combine "
            "SBC, share count, or buyback adjustment ratios."
        ),
        "exp-20260620-019": (
            "Tested dividend-per-share signaling as a distinct cash-return "
            "Companyfacts field. This run uses 8-K repurchase authorization "
            "events, not annual dividend facts."
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
        "exp_20260622_002_sec_share_repurchase_authorization.py"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return prior._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return prior._round(value, digits)


def _clean_excerpt(text: str) -> str:
    return " ".join(str(text or "").split())[:380]


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
    if value < MIN_AUTH_VALUE_USD or value > MAX_AUTH_VALUE_USD:
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


def _repurchase_kind(span: str) -> str:
    lowered = span.lower()
    if any(term in lowered for term in ("increased", "expanded", "additional")):
        return "expanded_authorization"
    if "new" in lowered:
        return "new_authorization"
    return "board_authorization"


def _repurchase_event(text: str) -> dict[str, Any] | None:
    if not text or len(text.split()) < MIN_TEXT_WORDS:
        return None
    scanned = text[:MAX_TEXT_CHARS_SCANNED]
    best: dict[str, Any] | None = None
    for trigger in REPURCHASE_TRIGGER_RE.finditer(scanned):
        start = max(0, trigger.start() - EVIDENCE_SPAN_CHARS)
        end = min(len(scanned), trigger.end() + EVIDENCE_SPAN_CHARS)
        span = scanned[start:end]
        if EXCLUDE_RE.search(span) or HISTORICAL_ONLY_RE.search(span):
            continue
        if not REPURCHASE_NOUN_RE.search(span) or not BOARD_OR_FRESH_RE.search(span):
            continue
        value = _nearest_money_value(span, trigger)
        if value is None:
            continue
        kind = _repurchase_kind(span)
        value_component = min(math.log10(value / MIN_AUTH_VALUE_USD), 3.0)
        fresh_component = 0.25 if kind in {"expanded_authorization", "new_authorization"} else 0.0
        strength = 1.0 + 0.18 * value_component + fresh_component
        event = {
            "repurchase_auth_value_usd": _round(value, 2),
            "repurchase_auth_kind": kind,
            "repurchase_auth_strength": _round(strength, 6),
            "repurchase_auth_evidence_excerpt": _clean_excerpt(span),
            "repurchase_auth_trigger": trigger.group(0),
            "text_word_count_scanned": len(scanned.split()),
        }
        if best is None or float(event["repurchase_auth_strength"] or 0.0) > float(best["repurchase_auth_strength"] or 0.0):
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
                event = _repurchase_event(str(raw.get("combined_text") or ""))
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
    kind_counts: Counter[str] = Counter()
    for row in text_rows:
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        by_ticker[ticker].append(row)
        kind_counts[str(row.get("repurchase_auth_kind") or "unknown")] += 1
    for rows in by_ticker.values():
        rows.sort(
            key=lambda row: (
                row["date"],
                -float(row.get("repurchase_auth_strength") or 0.0),
                -float(row.get("repurchase_auth_value_usd") or 0.0),
                row.get("accession_number") or "",
            )
        )
    index = {ticker: {"events": rows} for ticker, rows in by_ticker.items()}
    return index, {
        "sec_text_rows_loaded": len(text_rows),
        "tickers_with_repurchase_authorizations": len(by_ticker),
        "repurchase_auth_kind_counts": dict(kind_counts),
        "text_source": _repo_rel(TEXT_DIR),
        "min_auth_value_usd": MIN_AUTH_VALUE_USD,
        "max_auth_value_usd": MAX_AUTH_VALUE_USD,
        "evidence_span_chars": EVIDENCE_SPAN_CHARS,
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indices = {
        ticker: base.framework.shadow._row_index(base.framework.shadow._series(snapshot, ticker))
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
            value_component = min(
                math.log10(max(float(event.get("repurchase_auth_value_usd") or 1.0), 1.0) / MIN_AUTH_VALUE_USD),
                3.0,
            )
            score = (
                0.90 * float(event.get("repurchase_auth_strength") or 0.0)
                + 0.35 * value_component
                + 0.55 * float(confirm["candidate_ret20_excess_spy"])
                + 0.16 * float(confirm["candidate_ret60_excess_spy"])
                + 0.12 * float(confirm["candidate_close_location"])
                + 0.025 * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
            )
            scan["qualified_candidate_rows"] += 1
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "SEC_SHARE_REPURCHASE_AUTHORIZATION_PAPER",
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
            -float(row.get("text_repurchase_auth_strength") or 0.0),
            -float(row.get("text_repurchase_auth_value_usd") or 0.0),
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
        "min_auth_value_usd": MIN_AUTH_VALUE_USD,
        "max_auth_value_usd": MAX_AUTH_VALUE_USD,
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
        "positive_replay_lead_not_promoted_sec_share_repurchase_authorization"
        if gate["passed"]
        else "rejected_sec_share_repurchase_authorization_candidate_pool"
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
            f"# {EXPERIMENT_ID} SEC Share Repurchase Authorization",
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
                "adapter, backtester adapter, daily snapshot, production "
                "watchlist, order path, core entry, ranking, sizing, exit, LLM, "
                "or news behavior changed."
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


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    if gate4["passed"]:
        interpretation = (
            "The SEC share-repurchase authorization source cleared the numeric "
            "three-window replay screen, but remains only a replay lead because "
            "no shared daily/backtest parser was promoted."
        )
    else:
        interpretation = (
            "The SEC share-repurchase authorization source did not clear "
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
            "mechanism_family": "production_visible_sec_text_shareholder_yield_candidate_pool",
            "new_evidence_type": "sec_8k_fresh_share_repurchase_authorization_text",
            "nearby_prior_experiments": [
                "exp-20260616-009",
                "exp-20260616-017",
                "exp-20260620-019",
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
        "brier_score": round((PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2, 6),
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
        "min_auth_value_usd": MIN_AUTH_VALUE_USD,
        "max_auth_value_usd": MAX_AUTH_VALUE_USD,
        "min_text_words": MIN_TEXT_WORDS,
        "max_text_chars_scanned": MAX_TEXT_CHARS_SCANNED,
        "evidence_span_chars": EVIDENCE_SPAN_CHARS,
        "min_price": base.MIN_PRICE,
        "min_avg_dollar_volume_20d": base.MIN_AVG_DOLLAR_VOLUME_20D,
        "min_ret20_excess_spy": base.MIN_RET20_EXCESS_SPY,
        "min_ret60_excess_spy": base.MIN_RET60_EXCESS_SPY,
        "min_signal_return": base.MIN_SIGNAL_RETURN,
        "max_signal_return": base.MAX_SIGNAL_RETURN,
        "min_close_location": base.MIN_CLOSE_LOCATION,
        "max_realized_vol_20d": base.MAX_REALIZED_VOL_20D,
        "repurchase_trigger_terms": REPURCHASE_TRIGGER_RE.pattern,
        "repurchase_noun_terms": REPURCHASE_NOUN_RE.pattern,
        "board_or_fresh_terms": BOARD_OR_FRESH_RE.pattern,
        "exclude_terms": EXCLUDE_RE.pattern,
        "historical_only_terms": HISTORICAL_ONLY_RE.pattern,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"].pop("companyfacts_source", None)
    payload["backtest_protocol"]["sec_filing_text_source"] = _repo_rel(TEXT_DIR)
    payload["backtest_protocol"]["execution_model"] = (
        "8-K SEC filing text is keyed by accepted_at and usable_trade_date. "
        "The parser admits rows only when a local evidence span contains a "
        "fresh board/share-repurchase authorization or expansion phrase, a "
        "share-repurchase noun, and a local dollar amount, while financing, "
        "offering, repurchase-agreement, tax-withholding, historical-only, and "
        "generic risk-factor false positives are excluded. Price confirmation "
        "uses only signal-date OHLCV. Paper entry is next available open; exit "
        "is the close 10 trading days after signal with existing costs."
    )
    payload["gate2"]["runtime_fields"] = [
        "SEC filing text combined_text",
        "SEC filing accepted_at and usable_trade_date",
        "SEC filing accession_number",
        "local evidence-span fresh share-repurchase authorization terms",
        "local evidence-span extracted dollar value",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A valid retry needs materially richer PIT repurchase provenance such "
        "as authorization amount normalized by market cap/float, actual "
        "accelerated-repurchase execution terms, Rule 10b5-1 plan execution "
        "context, issuer cash/debt funding state joined at event time, or "
        "closed forward replacement-value rows from a shared daily helper. Do "
        "not sweep phrase lists, dollar thresholds, RS/close/volume guards, "
        "top-N, hold, cooldown, or notional on these frozen windows."
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
            "Do not retry by sweeping share-repurchase phrase lists, dollar "
            "thresholds, item codes, RS/close/volume/vol guards, top-N, hold "
            "days, cooldown, or notional on these frozen windows."
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
            _repo_rel(path): base.framework._sha256(path)
            for path in [runner, OUT_JSON, LOG_JSON, TICKET_JSON, CARD_MD]
            if path.exists()
        },
    }
    base.framework._write_json(MANIFEST_JSON, manifest)


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


def main() -> None:
    _configure_base()
    payload = _postprocess_payload(base._build_payload())
    _persist(payload)
    print(json.dumps(base.framework._safe(base._build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
