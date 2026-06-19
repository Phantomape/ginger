"""exp-20260619-013: issuer 8-K governance resolution text candidate scout.

Replay-only alpha search. The single decision hypothesis is that issuer-filed
8-K text describing a governance settlement, cooperation agreement, or
standstill with a board/proxy outcome can mark activist uncertainty resolution.
Candidates must also show same-day liquid SPY-relative leadership and enter
default-off paper at the next open with a fixed 10-trading-day hold.

No production code, shared adapter, live/default orders, ranking, sizing, exits,
LLM/news path, or watchlist behavior is changed. A positive replay is only a
lead until a shared historical/daily parser reproduces the same PIT text
semantics. No JavaScript is used.
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
import exp_20260617_011_sec_text_contract_economics as template


EXPERIMENT_ID = "exp-20260619-013"
STEM = "issuer_8k_governance_resolution_text"
TRIAL_FAMILY = "issuer_8k_governance_resolution_text_candidate_pool"
TRIAL_VARIANT_ID = "issuer_8k_settlement_outcome_v1"
CHANGED_VARIABLE = "issuer_8k_governance_resolution_text_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = base.REPO_ROOT
TEXT_DIR = REPO_ROOT / "data" / "non_ohlcv"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260619_013_{STEM}.json"
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

MIN_TEXT_WORDS = 250
MAX_TEXT_CHARS_SCANNED = 90_000

RESOLUTION_RE = re.compile(
    r"\b(?:cooperation agreement|settlement agreement|standstill agreement|"
    r"standstill|nomination agreement|shareholder rights plan)\b",
    re.IGNORECASE,
)
OUTCOME_RE = re.compile(
    r"\b(?:board of directors|board seat|director(?:s)?|appoint(?:ed|s|ment)?|"
    r"nominee(?:s)?|nominate(?:d|s|ion)?|proxy contest|annual meeting|"
    r"special meeting|shareholder rights plan|standstill)\b",
    re.IGNORECASE,
)
HOLDER_RE = re.compile(
    r"\b(?:shareholder(?:s)?|stockholder(?:s)?|investor(?:s)?|activist|"
    r"beneficial owner|ownership|voting agreement|13d|13g|proxy)\b",
    re.IGNORECASE,
)
EXCLUDE_RE = re.compile(
    r"\b(?:class action|derivative lawsuit|patent litigation|employment agreement|"
    r"severance agreement|customer settlement|supplier dispute|environmental "
    r"settlement|department of justice|doj|sec investigation|ftc|antitrust|"
    r"merger agreement|tender offer|credit agreement|loan agreement|indenture|"
    r"securities purchase agreement|underwriting agreement|at-the-market|"
    r"atm offering|warrant|convertible)\b",
    re.IGNORECASE,
)

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.30,
    "expected_pnl_delta": 5000.0,
    "main_failure_modes": [
        "sparse_events",
        "generic_litigation_settlement_false_positives",
        "near_neighbor_activist_proxy_family",
        "window_concentration",
    ],
    "confidence_reason": (
        "Daily PIT SEC filing text has rare issuer 8-K settlement/cooperation/"
        "standstill rows. The new evidence axis is an issuer-filed governance "
        "outcome tuple, not raw 13D intent or raw proxy form metadata. Sample "
        "size and false-positive risk remain high."
    ),
    "recorded_at": "2026-06-19T15:08:18+00:00",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "uses_free_sec_filing_text": True,
    "uses_free_sec_companyfacts": False,
    "trade_enabled": False,
    "execution_envelope": {
        **base.PRODUCTION_IMPACT["execution_envelope"],
        "failure_handling": (
            "missing SEC filing text, missing issuer 8-K form, missing "
            "settlement/cooperation/standstill term, missing governance holder "
            "or board/proxy outcome context, excluded litigation/financing/M&A "
            "text, missing OHLCV, missing next open, or missing 10d exit rejects "
            "the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper parses the same SEC "
        "filing text fields, exclusion rules, outcome tuple extraction, same-day "
        "OHLCV confirmation, cooldown, next-open paper entry, 10-day exit, costs, "
        "and concentration controls in both historical replay and daily "
        "production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: issuer-filed 8-K text that contains governance "
        "settlement/cooperation/standstill terms plus board/proxy/shareholder "
        "outcome context may identify activist uncertainty resolution. Requiring "
        "same-day liquid SPY-relative leadership tests whether the market is "
        "starting to absorb the resolution before next-open paper entry."
    ),
    "2_history_check": {
        "exp-20260617-027": (
            "Rejected raw non-management proxy pressure forms. This run uses "
            "issuer-filed 8-K full text and requires governance settlement/"
            "cooperation outcome semantics."
        ),
        "exp-20260618-019": (
            "Rejected parsed 13D Item 4 active intent. This run does not use "
            "ownership-filing Item 4 holder intent; it uses issuer 8-K outcome "
            "text after the agreement is disclosed."
        ),
        "exp-20260612-015": (
            "Rejected 13D activist stake initiation. This run avoids raw stake "
            "initiation and tests an outcome-resolution tuple."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL must "
        "improve versus the accepted core baseline without survival/trade-count "
        "collapse or unacceptable drawdown/concentration drift. Replay-only "
        "positives are leads until shared daily/backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260619_013_issuer_8k_governance_resolution_text.py"
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return base._round(value, digits)


def _unique_matches(pattern: re.Pattern[str], text: str) -> list[str]:
    return sorted({match.group(0).lower() for match in pattern.finditer(text)})


def _resolution_tuple(text: str) -> dict[str, Any] | None:
    if not text or len(text.split()) < MIN_TEXT_WORDS:
        return None
    scanned = text[:MAX_TEXT_CHARS_SCANNED]
    front = scanned[:30_000]
    resolution_terms = _unique_matches(RESOLUTION_RE, front)
    if not resolution_terms:
        return None
    outcome_terms = _unique_matches(OUTCOME_RE, front)
    holder_terms = _unique_matches(HOLDER_RE, front)
    if not outcome_terms or not holder_terms:
        return None
    if EXCLUDE_RE.search(front):
        return None
    has_cooperation = "cooperation agreement" in resolution_terms
    has_settlement = "settlement agreement" in resolution_terms
    has_standstill = any("standstill" in term for term in resolution_terms)
    has_rights_plan = "shareholder rights plan" in resolution_terms or "shareholder rights plan" in outcome_terms
    has_proxy_context = any(term in {"proxy", "proxy contest", "annual meeting", "special meeting"} for term in outcome_terms + holder_terms)
    has_board_context = any("board" in term or "director" in term or "nominee" in term for term in outcome_terms)
    strength = (
        1.00
        + 0.45 * has_cooperation
        + 0.35 * has_settlement
        + 0.30 * has_standstill
        + 0.20 * has_rights_plan
        + 0.20 * has_proxy_context
        + 0.25 * has_board_context
        + min(len(outcome_terms), 5) * 0.08
    )
    return {
        "resolution_terms": resolution_terms,
        "outcome_terms": outcome_terms,
        "holder_terms": holder_terms,
        "has_cooperation_agreement": has_cooperation,
        "has_settlement_agreement": has_settlement,
        "has_standstill": has_standstill,
        "has_shareholder_rights_plan": has_rights_plan,
        "has_proxy_context": has_proxy_context,
        "has_board_context": has_board_context,
        "resolution_strength": _round(strength, 6),
        "text_word_count_scanned": len(scanned.split()),
    }


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
                outcome = _resolution_tuple(str(raw.get("combined_text") or ""))
                if outcome is None:
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
                        **outcome,
                    }
                )
    return rows


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
        stats["rows_with_cooperation_agreement"] += 1 if row.get("has_cooperation_agreement") else 0
        stats["rows_with_settlement_agreement"] += 1 if row.get("has_settlement_agreement") else 0
        stats["rows_with_standstill"] += 1 if row.get("has_standstill") else 0
        stats["rows_with_proxy_context"] += 1 if row.get("has_proxy_context") else 0
        stats["rows_with_board_context"] += 1 if row.get("has_board_context") else 0
    for rows in by_ticker.values():
        rows.sort(
            key=lambda row: (
                row["date"],
                -float(row.get("resolution_strength") or 0.0),
                row.get("accession_number") or "",
            )
        )
    return dict(by_ticker), {
        "sec_text_rows_loaded": len(text_rows),
        "tickers_with_governance_resolution_text": len(by_ticker),
        "text_source": _repo_rel(TEXT_DIR),
        "min_text_words": MIN_TEXT_WORDS,
        "max_text_chars_scanned": MAX_TEXT_CHARS_SCANNED,
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
            strength = float(event.get("resolution_strength") or 0.0)
            score = (
                0.85 * strength
                + 0.55 * float(confirm["candidate_ret20_excess_spy"])
                + 0.18 * float(confirm["candidate_ret60_excess_spy"])
                + 0.16 * float(confirm["candidate_close_location"])
                + 0.025 * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
            )
            scan["qualified_candidate_rows"] += 1
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "ISSUER_8K_GOVERNANCE_RESOLUTION_TEXT_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "sec_filing_text_usable_trade_date_and_signal_close_before_next_open_paper_entry",
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
            -float(row.get("text_resolution_strength") or 0.0),
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
        "min_text_words": MIN_TEXT_WORDS,
        "max_text_chars_scanned": MAX_TEXT_CHARS_SCANNED,
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
        "positive_replay_lead_not_promoted_issuer_8k_governance_resolution_text"
        if gate["passed"]
        else "rejected_issuer_8k_governance_resolution_text_candidate_pool"
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
            f"# {EXPERIMENT_ID} Issuer 8-K Governance Resolution Text",
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
    template.PREDICTION = PREDICTION
    template.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    template.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    template._load_sec_text_rows = _load_sec_text_rows
    template._build_quality_index = _build_quality_index
    template._candidate_rows_for_window = _candidate_rows_for_window
    template._gate4 = _gate4
    template._build_card = _build_card
    template._configure_base()


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    if gate4["passed"]:
        interpretation = (
            "Issuer 8-K governance resolution text cleared the numeric "
            "three-window replay screen, but remains only a replay lead because "
            "no shared daily/backtest parser was promoted."
        )
    else:
        interpretation = (
            "Issuer 8-K governance resolution text did not clear Gate 4 "
            f"(failed: {', '.join(gate4['failed_reasons']) or 'none'}). "
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
            "change_type": "candidate_pool_private_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "sec_text_governance_resolution_candidate_pool",
            "new_evidence_type": "issuer_8k_governance_settlement_cooperation_outcome_text_tuple",
            "nearby_prior_experiments": [
                "exp-20260617-027",
                "exp-20260618-019",
                "exp-20260612-015",
            ],
            "prior_trial_count": 3,
            "multiple_testing_risk_bucket": "high",
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
        "min_text_words": MIN_TEXT_WORDS,
        "max_text_chars_scanned": MAX_TEXT_CHARS_SCANNED,
        "min_price": base.MIN_PRICE,
        "min_avg_dollar_volume_20d": base.MIN_AVG_DOLLAR_VOLUME_20D,
        "min_ret20_excess_spy": base.MIN_RET20_EXCESS_SPY,
        "min_ret60_excess_spy": base.MIN_RET60_EXCESS_SPY,
        "min_signal_return": base.MIN_SIGNAL_RETURN,
        "max_signal_return": base.MAX_SIGNAL_RETURN,
        "min_close_location": base.MIN_CLOSE_LOCATION,
        "max_realized_vol_20d": base.MAX_REALIZED_VOL_20D,
        "resolution_terms": RESOLUTION_RE.pattern,
        "outcome_terms": OUTCOME_RE.pattern,
        "holder_terms": HOLDER_RE.pattern,
        "exclude_terms": EXCLUDE_RE.pattern,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["companyfacts_source"] = None
    payload["backtest_protocol"]["sec_filing_text_source"] = _repo_rel(TEXT_DIR)
    payload["backtest_protocol"]["execution_model"] = (
        "8-K SEC filing text is keyed by accepted_at and usable_trade_date. The "
        "parser admits rows only when issuer 8-K text contains governance "
        "settlement/cooperation/standstill terms, holder context, and board/proxy "
        "outcome context while excluding common litigation, financing, and M&A "
        "false-positive buckets. Price confirmation uses only signal-date OHLCV. "
        "Paper entry is the next available open with existing entry slippage; "
        "exit is the close 10 trading days after the signal with target-side sell "
        "slippage and ROUND_TRIP_COST_PCT."
    )
    payload["gate2"]["runtime_fields"] = [
        "SEC filing text combined_text",
        "SEC filing accepted_at and usable_trade_date",
        "SEC filing accession_number",
        "extracted governance resolution/outcome tuple",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "A retry needs materially richer evidence, such as parsed counterparty/"
        "holder identity, board-seat count, ownership threshold, explicit "
        "standstill duration, evidence spans, or closed forward replacement rows. "
        "Do not sweep phrase lists, item codes, RS/close/volume guards, top-N, "
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
            "Do not retry by sweeping SEC governance settlement phrase lists, "
            "item codes, RS/close/volume/vol guards, top-N, hold days, cooldown, "
            "or notional on these frozen windows."
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
