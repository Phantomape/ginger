"""exp-20260629-009: 13D Item-4 governance terms candidate-pool scout.

Alpha search. The single decision hypothesis is that the structured
Schedule 13D Item-4 governance-term surface accepted in exp-20260629-006
(board-seat/representation, cooperation or settlement agreements, nomination
withdrawal, board departure, and standstill terms) is a richer activist
catalyst than the rejected generic Item-4 phrase gate.

This runner keeps the existing 13D next-open/10d paper replay envelope and
price-absorption checks, but swaps the source evidence to the fixed shared
governance-term fields. It changes no production code, orders, ranking,
sizing, exits, LLM/news path, or watchlist behavior. A positive result would
remain a replay lead until a shared daily/backtest helper is promoted.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260618_019_parsed_13d_item4_active_intent_absorption as prior

if str(prior.REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(prior.REPO_ROOT))

from quant import sec_13d13g_ingest as ingest  # noqa: E402


EXPERIMENT_ID = "exp-20260629-009"
STEM = "sec_13d_item4_governance_terms_candidate_pool"
TRIAL_FAMILY = "sec_13d_item4_governance_terms_candidate_pool"
TRIAL_VARIANT_ID = "fixed_governance_terms_top1_10d_v1"
CHANGED_VARIABLE = "sec_13d_item4_governance_terms_candidate_pool_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-explore"

REPO_ROOT = prior.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260629_009_{STEM}.json"
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

MIN_PRICE = prior.MIN_PRICE
MIN_AVG_DOLLAR_VOLUME_20D = prior.MIN_AVG_DOLLAR_VOLUME_20D
MIN_SIGNAL_RETURN = prior.MIN_SIGNAL_RETURN
MIN_SIGNAL_EXCESS_SPY = prior.MIN_SIGNAL_EXCESS_SPY
MIN_CLOSE_LOCATION = prior.MIN_CLOSE_LOCATION
MIN_VOLUME_RATIO_20D = prior.MIN_VOLUME_RATIO_20D
MAX_REALIZED_VOL_20D = prior.MAX_REALIZED_VOL_20D
MIN_RET20_EXCESS_SPY = prior.MIN_RET20_EXCESS_SPY
MAX_EVENT_AGE_TRADING_DAYS = prior.MAX_EVENT_AGE_TRADING_DAYS

PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "thin_sample",
        "source_saturation_reject",
        "priced_at_next_open",
        "old_thin_coverage_gap",
        "accepted_comparator_not_beaten",
    ],
    "confidence_reason": (
        "Mechanism: board-seat and standstill outcomes are concrete activist "
        "governance economics, not generic text tone. Nearby history rejected "
        "simple 13D active phrase gates but exp-20260629-006 exposed "
        "deterministic governance-term fields as a new structured provenance "
        "surface. Main disconfirmers are thin tradeable coverage, next-open "
        "pricing, and source-saturation if the gate classifies this as old SEC "
        "text."
    ),
    "recorded_at": "2026-06-29T12:04:45+00:00",
}

PRODUCTION_IMPACT = {
    **prior.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "uses_free_sec_companyfacts": False,
    "uses_free_sec_submissions": True,
    "uses_parsed_sec_13d13g": True,
    "uses_structured_item4_governance_terms": True,
    "uses_free_ohlcv": True,
    "execution_envelope": {
        **prior.PRODUCTION_IMPACT["execution_envelope"],
        "liquidity_source": "price >= $10 and ADV20 >= $50M from PIT OHLCV",
        "failure_handling": (
            "missing parsed 13D rows, missing cached primary_doc.xml, no "
            "shared governance-term field hit, missing OHLCV, missing next "
            "open, or missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same PIT "
        "13D Item-4 governance-term parser output, acceptance-time signal date, "
        "price-absorption gate, cooldown, next-open paper entry, 10-day exit, "
        "costs, and concentration controls in both historical replay and daily "
        "production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: structured Schedule 13D Item-4 governance terms such "
        "as board-seat, cooperation/settlement, nomination-withdrawal, and "
        "standstill outcomes may identify a stronger activist catalyst than "
        "the rejected generic Item-4 phrase gate. A fixed top-1/day default-off "
        "paper source from the shared sec_13d13g governance-terms surface "
        "should add next-open 10d replacement value across canonical windows."
    ),
    "2_history_check": {
        "exp-20260618-019": (
            "Rejected generic active Item-4 phrase gate plus price absorption. "
            "This run does not sweep phrases; it uses the new structured "
            "governance-term fields from exp-20260629-006."
        ),
        "exp-20260619-014": (
            "Built 13G/A direction surface but found weak/static ownership "
            "direction. This run tests 13D Item-4 governance outcomes."
        ),
        "exp-20260629-006": (
            "Accepted measurement repair exposing deterministic Item-4 "
            "governance-term fields; closeout allowed a fixed Gate 1-4 use of "
            "these new fields."
        ),
        "novelty_saturation_gate": (
            "Reservation required novelty and saturated-source overrides "
            "because the tool fingerprints the source as sec_text_event. The "
            "declared new axis is the shared structured Item-4 governance-term "
            "surface, not another phrase/threshold scan."
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
        ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260629_009_sec_13d_item4_governance_terms_candidate_pool.py"
    ),
}

_EVENT_INDEX_CACHE: tuple[dict[str, list[dict[str, Any]]], dict[str, Any]] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return prior.runner.base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return prior._round(value, digits)


def _governance_strength(terms: dict[str, Any]) -> float:
    strength = 0.0
    if terms.get("cooperation_or_settlement_agreement_present"):
        strength += 1.0
    if terms.get("board_terms_present"):
        strength += 1.0
    if terms.get("standstill_terms_present"):
        strength += 0.75
    if terms.get("nomination_withdrawal_present"):
        strength += 0.75
    if terms.get("board_departure_present"):
        strength += 0.50
    strength += min(1.0, 0.25 * float(terms.get("board_appointment_count") or 0.0))
    return strength


def _load_governance_term_events() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    events = ingest.iter_ownership_filings(families=("13D",), include_amendments=True)
    parsed = ingest.build_parsed_rows(events, fetch=False, refresh=False)
    rows = parsed["rows"]
    index: dict[str, list[dict[str, Any]]] = {}
    stats: Counter[str] = Counter()
    stats["enumerated_13d_events"] = len(events)
    stats["parsed_13d_rows"] = len(rows)
    stats.update({f"fetch_status_{key}": value for key, value in parsed["fetch_status"].items()})

    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        terms = row.get("item4_governance_terms") or {}
        if not ticker:
            stats["missing_ticker"] += 1
            continue
        if not row.get("item4_text_present"):
            stats["missing_item4_text"] += 1
            continue
        stats["rows_with_item4_text"] += 1
        if not row.get("item4_governance_terms_present"):
            stats["rows_without_governance_terms"] += 1
            continue
        bucket = str(row.get("item4_governance_terms_bucket") or "unknown")
        strength = _governance_strength(terms)
        stats["governance_term_events"] += 1
        stats[f"governance_term_{row.get('window')}"] += 1
        stats[f"governance_bucket_{bucket}"] += 1
        index.setdefault(ticker, []).append(
            {
                "ticker": ticker,
                "form": row.get("form"),
                "family": row.get("family"),
                "filing_date": row.get("filing_date"),
                "accepted_after_close": prior.runner._acceptance_after_close(row.get("accepted_at")),
                "acceptance_datetime": row.get("accepted_at"),
                "accession_number": row.get("accession_number"),
                "amendment_no": row.get("amendment_no"),
                "holder_key": prior._holder_key(row),
                "max_class_percent": _round(row.get("max_class_percent"), 4),
                "reporting_person_types": row.get("reporting_person_types") or [],
                "n_reporting_persons": row.get("n_reporting_persons"),
                "is_big3": bool(row.get("is_big3")),
                "issuer_cik": row.get("issuer_cik"),
                "issuer_name": row.get("issuer_name"),
                "issuer_cusip": row.get("issuer_cusip"),
                "source_row_window": row.get("window"),
                "item4_governance_terms_bucket": bucket,
                "item4_governance_term_hits": terms.get("governance_term_hits") or [],
                "item4_governance_strength": _round(strength, 4),
                "item4_board_appointment_count": terms.get("board_appointment_count"),
                "item4_board_size_delta": terms.get("board_size_delta"),
                "item4_standstill_duration_days": terms.get("standstill_duration_days"),
                "item4_standstill_until_date": terms.get("standstill_until_date"),
                "item4_excerpt": terms.get("item4_excerpt"),
            }
        )

    for ticker in index:
        index[ticker].sort(
            key=lambda event: (
                str(event.get("filing_date") or ""),
                str(event.get("acceptance_datetime") or ""),
                str(event.get("accession_number") or ""),
            )
        )
    stats["tickers_with_governance_term_events"] = len(index)
    stats["candidate_event_count"] = sum(len(rows_) for rows_ in index.values())
    summary = {
        "parsed_surface": "quant/sec_13d13g_ingest.py build_parsed_rows(fetch=False)",
        "xml_cache": _repo_rel(ingest.XML_CACHE_DIR),
        "candidate_universe_scope": "broad_liquid_warehouse_all_windows_full_liquid",
        "governance_rule": (
            "fixed exp-20260629-006 item4_governance_terms_present field; no "
            "phrase-list, holder-type, classPercent, top-N, hold, cooldown, or "
            "notional sweep"
        ),
        "no_js": True,
        **dict(stats),
    }
    return index, summary


def _load_event_index() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    global _EVENT_INDEX_CACHE
    if _EVENT_INDEX_CACHE is None:
        _EVENT_INDEX_CACHE = _load_governance_term_events()
    return _EVENT_INDEX_CACHE


def _build_quality_index(
    companyfacts_rows: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    index, summary = _load_event_index()
    return index, {
        **summary,
        "selected_companyfacts_rows_ignored": len(companyfacts_rows),
        "field_source": "structured_sec_13d_item4_governance_terms_not_companyfacts",
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indices = {
        ticker: prior.runner.base.framework.shadow._row_index(
            prior.runner.base.framework.shadow._series(snapshot, ticker)
        )
        for ticker in snapshot
    }
    dates = prior.runner.base.framework.shadow._trading_dates(snapshot)
    start = str(cfg["start"])
    end = str(cfg["end"])
    scan: Counter[str] = Counter()
    scan["eligible_event_tickers"] = len(set(quality_index) & set(snapshot))
    scan["governance_term_events_total"] = sum(len(v) for v in quality_index.values())
    candidates: list[dict[str, Any]] = []

    for ticker in sorted(set(quality_index) & set(snapshot)):
        for event in quality_index[ticker]:
            signal_date = prior.runner._signal_date_for_event(event, dates)
            if signal_date is None:
                scan["event_after_last_or_stale"] += 1
                continue
            if not (start <= signal_date <= end):
                scan["event_outside_window"] += 1
                continue
            scan["governance_term_events_in_window"] += 1
            scan[f"source_window_{event.get('source_row_window')}"] += 1
            bucket = str(event.get("item4_governance_terms_bucket") or "unknown")
            scan[f"bucket_{bucket}"] += 1
            confirm = prior.runner._absorption_confirmation(
                snapshot=snapshot,
                indices=indices,
                ticker=ticker,
                signal_date=signal_date,
            )
            if confirm is None:
                scan["failed_absorption_or_liquidity_gate"] += 1
                continue
            scan["qualified_candidate_rows"] += 1
            meta = sector_entries.get(ticker, {})
            score = (
                1.60 * float(confirm["candidate_signal_excess_spy"])
                + 0.40 * float(confirm["candidate_close_location"])
                + 0.25 * max(0.0, float(confirm["candidate_ret20_excess_spy"]))
                + 0.08
                * math.log10(
                    max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0)
                    / 1_000_000.0
                )
                + min(0.30, 0.08 * float(event.get("item4_governance_strength") or 0.0))
            )
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "SEC_13D_ITEM4_GOVERNANCE_TERMS_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "parsed_13d_item4_governance_terms_and_signal_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_submissions": True,
                    "uses_parsed_sec_13d13g": True,
                    "uses_structured_item4_governance_terms": True,
                    "uses_free_sec_companyfacts": False,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    "sec_13d_form": event.get("form"),
                    "sec_13d_filing_date": event.get("filing_date"),
                    "sec_13d_accepted_after_close": event.get("accepted_after_close"),
                    "sec_13d_acceptance_datetime": event.get("acceptance_datetime"),
                    "sec_13d_accession_number": event.get("accession_number"),
                    "sec_13d_amendment_no": event.get("amendment_no"),
                    "sec_13d_holder_key": event.get("holder_key"),
                    "sec_13d_max_class_percent": event.get("max_class_percent"),
                    "sec_13d_reporting_person_types": event.get("reporting_person_types"),
                    "sec_13d_n_reporting_persons": event.get("n_reporting_persons"),
                    "sec_13d_is_big3": event.get("is_big3"),
                    "sec_13d_issuer_cik": event.get("issuer_cik"),
                    "sec_13d_issuer_name": event.get("issuer_name"),
                    "sec_13d_item4_governance_terms_bucket": bucket,
                    "sec_13d_item4_governance_term_hits": event.get(
                        "item4_governance_term_hits"
                    ),
                    "sec_13d_item4_governance_strength": event.get(
                        "item4_governance_strength"
                    ),
                    "sec_13d_item4_board_appointment_count": event.get(
                        "item4_board_appointment_count"
                    ),
                    "sec_13d_item4_board_size_delta": event.get("item4_board_size_delta"),
                    "sec_13d_item4_standstill_duration_days": event.get(
                        "item4_standstill_duration_days"
                    ),
                    "sec_13d_item4_standstill_until_date": event.get(
                        "item4_standstill_until_date"
                    ),
                    "sec_13d_item4_excerpt": event.get("item4_excerpt"),
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
            -float(row["candidate_signal_excess_spy"] or 0.0),
            -float(row["candidate_close_location"] or 0.0),
            -float(row.get("candidate_avg_dollar_volume_20d") or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(rows)
    scan["candidate_signal_days"] = len({row["date"] for row in rows})
    scan["candidate_tickers"] = len({row["ticker"] for row in rows})
    scan["eligible_quality_tickers"] = scan["eligible_event_tickers"]
    return rows, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "governance_rule": "fixed exp-20260629-006 item4_governance_terms_present field",
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "min_signal_return": MIN_SIGNAL_RETURN,
        "min_signal_excess_spy": MIN_SIGNAL_EXCESS_SPY,
        "min_close_location": MIN_CLOSE_LOCATION,
        "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
        "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
        "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
        "max_event_age_trading_days": MAX_EVENT_AGE_TRADING_DAYS,
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = prior.runner.base.framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    ev_delta = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if ev_delta <= prior.runner.base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_compression_ev_not_beaten")
    if pnl_delta <= prior.runner.base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_compression_pnl_not_beaten")
    if ev_delta <= prior.runner.base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_distribution_ev_not_beaten")
    if pnl_delta <= prior.runner.base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_distribution_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["accepted_compression_comparator"] = prior.runner.base.COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = prior.runner.base.DISTRIBUTION_COMPARATOR
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_not_promoted_sec_13d_item4_governance_terms_candidate_pool"
        if gate["passed"]
        else "rejected_sec_13d_item4_governance_terms_candidate_pool"
    )
    return gate


def _interpretation(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    if gate4["passed"]:
        return (
            "The structured 13D Item-4 governance-term source cleared the "
            "numeric three-window replay screen, but remains only a replay lead "
            "because no shared daily/backtest helper was promoted."
        )
    return (
        "The structured 13D Item-4 governance-term source did not clear Gate 4 "
        f"(failed: {', '.join(gate4['failed_reasons']) or 'none'}). The fixed "
        "bundle tested only exp-20260629-006 governance-term rows plus the "
        "existing signal-day SPY-relative price-absorption replay envelope. The "
        "result is not retained or promoted."
    )


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    interpretation = _interpretation(payload)
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": _utc_now(),
            "status": status,
            "decision": gate4["decision"],
            "accepted": False,
            "accepted_alpha": False,
            "numeric_gate4_passed": gate4["passed"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "default_off_paper_candidate_pool_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_sec_ownership_item4_governance_terms",
            "new_evidence_type": "structured_sec_13d_item4_governance_terms_surface",
            "new_evidence_axis": (
                "Shared structured Schedule 13D Item-4 governance-term fields "
                "from quant/sec_13d13g_ingest.py after exp-20260629-006; fixed "
                "provenance bucket only, no phrase/threshold/top-N/hold/notional "
                "sweep."
            ),
            "nearby_prior_experiments": [
                "exp-20260618-019",
                "exp-20260619-014",
                "exp-20260629-006",
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
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0))
            ** 2,
            6,
        ),
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
        "predicted_failure_modes": PREDICTION["main_failure_modes"],
        "predicted_failure_mode_hit": bool(
            set(PREDICTION["main_failure_modes"]) & set(gate4["failed_reasons"])
        ),
    }
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "governance_rule": "fixed exp-20260629-006 item4_governance_terms_present field",
        "governance_strength_for_tie_break_only": True,
        "min_price": MIN_PRICE,
        "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
        "min_signal_return": MIN_SIGNAL_RETURN,
        "min_signal_excess_spy": MIN_SIGNAL_EXCESS_SPY,
        "min_close_location": MIN_CLOSE_LOCATION,
        "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
        "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
        "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
        "max_event_age_trading_days": MAX_EVENT_AGE_TRADING_DAYS,
        "candidate_universe": "broad_liquid_warehouse_all_windows_full_liquid",
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["execution_model"] = (
        "Parsed Schedule 13D Item-4 governance-term rows are read from the "
        "local cached EDGAR primary_doc.xml files through "
        "quant/sec_13d13g_ingest.py. A row is eligible only when the shared "
        "exp-20260629-006 item4_governance_terms_present field is true. The "
        "signal date is the filing date unless SEC acceptance timestamp is "
        "after 16:00, in which case it is the next trading day. Candidates must "
        "show signal-day price absorption before next-open paper entry: "
        "non-negative daily return, return minus SPY >= 0.5%, close location >= "
        "0.56, volume ratio >= 0.75, realized vol <= 12%, ret20 excess vs SPY "
        ">= -5%, price >= $10, and ADV20 >= $50M. Paper entry is the next "
        "available open with entry slippage; exit is the close 10 trading days "
        "after the signal with target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["backtest_protocol"]["parsed_surface"] = "quant/sec_13d13g_ingest.py"
    payload["gate2"]["runtime_fields"] = [
        "parsed 13D accession number",
        "parsed 13D filing date",
        "parsed 13D acceptanceDateTime",
        "cached 13D primary_doc.xml",
        "item4_governance_terms_present",
        "item4_governance_terms_bucket",
        "item4_governance_term_hits",
        "item4_board_appointment_count",
        "item4_standstill_duration_days",
        "warehouse ticker_universe CIK mapping",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for price absorption",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "If this fixed governance-term source fails, do not retry by sweeping "
        "governance bucket lists, phrase lists, holder types, classPercent, "
        "signal excess, close-location, volume, volatility, ret20, price/ADV, "
        "event age, top-N, hold, cooldown, notional, or response shape on these "
        "frozen windows. A valid retry needs campaign/board-seat outcome "
        "evidence beyond regex provenance, repaired old_thin structured XML "
        "coverage, or closed forward replacement-value rows."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": interpretation,
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; max "
            "drawdown drift {:+.4f}; {} paper trades.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
                float(aggregate["max_drawdown_delta_max"] or 0.0),
                payload["target_trade_summary"]["total_trade_count"],
            )
        ),
        "negative_reflection": (
            "A negative result means deterministic Item-4 governance terms are "
            "still too sparse, too stale, or too transaction-control-heavy after "
            "next-open execution and price absorption. Keep the surface as "
            "ownership/governance context unless stronger forward replacement "
            "rows appear."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping governance buckets, phrase lists, holder "
            "types, classPercent, signal excess, close-location, volume, "
            "volatility, ret20, price/ADV, event age, top-N, hold, cooldown, "
            "notional, or response shape on these frozen windows."
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


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Events | Raw | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in prior.runner.base.framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {events} | {raw} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                events=scan.get("governance_term_events_in_window", 0),
                raw=scan.get("deduped_candidate_rows", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} SEC 13D Item-4 Governance Terms Candidate Pool",
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
            "- Aggregate EV delta: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
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


def _install() -> None:
    prior.EXPERIMENT_ID = EXPERIMENT_ID
    prior.STEM = STEM
    prior.TRIAL_FAMILY = TRIAL_FAMILY
    prior.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    prior.CHANGED_VARIABLE = CHANGED_VARIABLE
    prior.RULE_VERSION = RULE_VERSION
    prior.OWNER = OWNER
    prior.REPO_ROOT = REPO_ROOT
    prior.OUT_DIR = OUT_DIR
    prior.OUT_JSON = OUT_JSON
    prior.LOG_JSON = LOG_JSON
    prior.TICKET_JSON = TICKET_JSON
    prior.CARD_MD = CARD_MD
    prior.MANIFEST_JSON = MANIFEST_JSON
    prior.EXPERIMENT_LOG = EXPERIMENT_LOG
    prior.REGISTRY_JSON = REGISTRY_JSON
    prior.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    prior.HOLD_DAYS = HOLD_DAYS
    prior.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    prior.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    prior.MIN_PRICE = MIN_PRICE
    prior.MIN_AVG_DOLLAR_VOLUME_20D = MIN_AVG_DOLLAR_VOLUME_20D
    prior.MIN_SIGNAL_RETURN = MIN_SIGNAL_RETURN
    prior.MIN_SIGNAL_EXCESS_SPY = MIN_SIGNAL_EXCESS_SPY
    prior.MIN_CLOSE_LOCATION = MIN_CLOSE_LOCATION
    prior.MIN_VOLUME_RATIO_20D = MIN_VOLUME_RATIO_20D
    prior.MAX_REALIZED_VOL_20D = MAX_REALIZED_VOL_20D
    prior.MIN_RET20_EXCESS_SPY = MIN_RET20_EXCESS_SPY
    prior.MAX_EVENT_AGE_TRADING_DAYS = MAX_EVENT_AGE_TRADING_DAYS
    prior.PREDICTION = PREDICTION
    prior.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    prior.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    prior._EVENT_INDEX_CACHE = None
    prior._load_event_index = _load_event_index
    prior._build_quality_index = _build_quality_index
    prior._candidate_rows_for_window = _candidate_rows_for_window
    prior._gate4 = _gate4
    prior._postprocess_payload = _postprocess_payload
    prior._build_card = _build_card
    prior._install()


def main() -> None:
    _install()
    prior.runner.main()


if __name__ == "__main__":
    main()
