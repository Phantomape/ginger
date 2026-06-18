"""exp-20260618-017: parsed 13D/A stake-increase absorption scout.

Replay-only alpha search. The single decision hypothesis is that parsed
Schedule 13D/A amendments where the same issuer-holder stake percentage rises
versus the prior point-in-time parsed 13D row identify active accumulation.
Those rows are tested as a default-off paper candidate pool only when the
signal-day price action absorbs the filing versus SPY before next-open entry.

This is not a raw 13D metadata retry, a static classPercent threshold sweep, or
a holder-type/top-N/hold/notional retune. No production code, shared adapter,
live/default orders, ranking, sizing, exits, LLM/news path, or watchlist
behavior is changed. A positive result is only a replay lead until a shared
historical/daily helper reproduces it. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260617_024_s8_employee_equity_registration_absorption_scout as runner

if str(runner.REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(runner.REPO_ROOT))

from quant import sec_13d13g_ingest as ingest


EXPERIMENT_ID = "exp-20260618-017"
STEM = "parsed_13d_stake_increase_absorption"
TRIAL_FAMILY = "parsed_13d_amend_stake_increase_absorption_candidate_pool"
TRIAL_VARIANT_ID = "parsed_13d_stake_increase_absorption_top1_next_open_10d_v1"
CHANGED_VARIABLE = "parsed_13d_amend_stake_increase_absorption_candidate_pool_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-search-automation"

REPO_ROOT = runner.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260618_017_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = runner.BASE_NOTIONAL_USD
HOLD_DAYS = runner.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = runner.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = runner.SAME_TICKER_COOLDOWN_DAYS

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 50_000_000.0
MIN_SIGNAL_RETURN = 0.0
MIN_SIGNAL_EXCESS_SPY = 0.005
MIN_CLOSE_LOCATION = 0.56
MIN_VOLUME_RATIO_20D = 0.75
MAX_REALIZED_VOL_20D = 0.120
MIN_RET20_EXCESS_SPY = -0.050
MAX_EVENT_AGE_TRADING_DAYS = 3

PREDICTION = {
    "success_probability": 0.15,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "thin_sample",
        "old_thin_coverage_gap",
        "priced_before_next_open",
        "accepted_comparator_not_beaten",
        "drawdown_drift",
    ],
    "confidence_reason": (
        "Prior metadata-only 13D/13G runs failed and exp-20260618-016 found no "
        "clean static holder/stake subset, but it explicitly left stake-change "
        "direction as a new evidence axis. The local parsed 13D amendment cache "
        "has adequate rows to test accumulation direction without using LLM or "
        "future information."
    ),
    "recorded_at": "2026-06-18T17:04:48+00:00",
}

PRODUCTION_IMPACT = {
    **runner.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "uses_free_sec_companyfacts": False,
    "uses_free_sec_submissions": True,
    "uses_parsed_sec_13d13g": True,
    "uses_free_ohlcv": True,
    "execution_envelope": {
        **runner.PRODUCTION_IMPACT["execution_envelope"],
        "liquidity_source": "price >= $10 and ADV20 >= $50M from PIT OHLCV",
        "failure_handling": (
            "missing parsed 13D rows, missing prior same issuer-holder parsed "
            "row, non-positive stake change, missing OHLCV, missing next open, "
            "or missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper computes the same PIT "
        "parsed 13D/A stake-change direction, acceptance-time signal date, "
        "price-absorption gate, cooldown, next-open paper entry, 10-day exit, "
        "costs, and concentration controls in both historical replay and daily "
        "production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: parsed 13D/A amendments where the same issuer-holder "
        "stake percentage increases versus the prior PIT parsed 13D row may "
        "identify active accumulation that is stronger than raw 13D metadata. "
        "Same-day liquid SPY-relative price absorption then tests whether demand "
        "accepted the ownership increase before next-open paper entry."
    ),
    "2_history_check": {
        "exp-20260612-015": (
            "Rejected direct SC 13D activist-initiation metadata. Closeout "
            "required parsed 13D documents: stake percent, filer name, purpose, "
            "track record, broader universe, or forward rows."
        ),
        "exp-20260618-014": (
            "Blocked until parsed holder/stake/action rows existed. That parsed "
            "surface now exists from exp-20260618-016."
        ),
        "exp-20260618-016": (
            "Observed-only parsed 13D/13G diagnostic found no clean static "
            "holder/stake subset and explicitly named stake-change direction as "
            "new evidence required before another entry-timing test."
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
        "exp_20260618_017_parsed_13d_stake_increase_absorption.py"
    ),
}

_EVENT_INDEX_CACHE: tuple[dict[str, list[dict[str, Any]]], dict[str, Any]] | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    return runner.base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return runner._round(value, digits)


def _holder_key(row: dict[str, Any]) -> str:
    names: list[str] = []
    for person in row.get("reporting_persons") or []:
        name = str(person.get("reporting_person_name") or "").lower()
        normalized = " ".join(
            name.replace(",", " ").replace(".", " ").replace("&", " and ").split()
        )
        if normalized:
            names.append(normalized)
    return "|".join(sorted(names)) or str(row.get("accession_number") or "")


def _load_13d_stake_increase_events() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    events = ingest.iter_ownership_filings(families=("13D",), include_amendments=True)
    parsed = ingest.build_parsed_rows(events, fetch=False, refresh=False)
    rows = parsed["rows"]
    rows.sort(
        key=lambda row: (
            str(row.get("ticker") or ""),
            _holder_key(row),
            str(row.get("filing_date") or ""),
            str(row.get("accepted_at") or ""),
            str(row.get("accession_number") or ""),
        )
    )

    previous_by_holder: dict[tuple[str, str], dict[str, Any]] = {}
    index: dict[str, list[dict[str, Any]]] = {}
    stats: Counter[str] = Counter()
    stats["enumerated_13d_events"] = len(events)
    stats["parsed_13d_rows"] = len(rows)
    stats.update({f"fetch_status_{key}": value for key, value in parsed["fetch_status"].items()})

    for row in rows:
        ticker = str(row.get("ticker") or "").upper()
        holder = _holder_key(row)
        key = (ticker, holder)
        current_pct = row.get("max_class_percent")
        prior = previous_by_holder.get(key)
        if row.get("is_amendment"):
            stats["parsed_13d_amendment_rows"] += 1
        else:
            stats["parsed_13d_initial_rows"] += 1
        if (
            row.get("is_amendment")
            and ticker
            and current_pct is not None
            and prior
            and prior.get("max_class_percent") is not None
        ):
            delta = float(current_pct) - float(prior["max_class_percent"])
            if delta > 0.0:
                event = {
                    "ticker": ticker,
                    "form": row.get("form"),
                    "family": row.get("family"),
                    "filing_date": row.get("filing_date"),
                    "accepted_after_close": runner._acceptance_after_close(row.get("accepted_at")),
                    "acceptance_datetime": row.get("accepted_at"),
                    "accession_number": row.get("accession_number"),
                    "amendment_no": row.get("amendment_no"),
                    "holder_key": holder,
                    "current_class_percent": _round(current_pct, 4),
                    "prior_class_percent": _round(prior.get("max_class_percent"), 4),
                    "stake_delta_pct_points": _round(delta, 4),
                    "current_aggregate_shares": row.get("reporting_persons", [{}])[0].get(
                        "aggregate_shares"
                    )
                    if row.get("reporting_persons")
                    else None,
                    "prior_accession_number": prior.get("accession_number"),
                    "prior_filing_date": prior.get("filing_date"),
                    "prior_amendment_no": prior.get("amendment_no"),
                    "reporting_person_types": row.get("reporting_person_types") or [],
                    "n_reporting_persons": row.get("n_reporting_persons"),
                    "is_big3": bool(row.get("is_big3")),
                    "issuer_cik": row.get("issuer_cik"),
                    "issuer_name": row.get("issuer_name"),
                    "issuer_cusip": row.get("issuer_cusip"),
                    "source_row_window": row.get("window"),
                }
                index.setdefault(ticker, []).append(event)
                stats["positive_stake_change_events"] += 1
                stats[f"positive_stake_change_{row.get('window')}"] += 1
            elif delta < 0.0:
                stats["negative_stake_change_events"] += 1
            else:
                stats["flat_stake_change_events"] += 1
        if current_pct is not None:
            previous_by_holder[key] = row

    for ticker in index:
        index[ticker].sort(
            key=lambda event: (
                str(event.get("filing_date") or ""),
                str(event.get("acceptance_datetime") or ""),
                str(event.get("accession_number") or ""),
            )
        )
    stats["tickers_with_positive_stake_changes"] = len(index)
    stats["candidate_event_count"] = sum(len(rows_) for rows_ in index.values())
    summary = {
        "parsed_surface": "quant/sec_13d13g_ingest.py build_parsed_rows(fetch=False)",
        "xml_cache": _repo_rel(ingest.XML_CACHE_DIR),
        "candidate_universe_scope": "broad_liquid_warehouse_all_windows_full_liquid",
        "direction_rule": "current parsed 13D/A max_class_percent > prior same issuer-holder parsed 13D max_class_percent",
        "no_js": True,
        **dict(stats),
    }
    return index, summary


def _load_event_index() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    global _EVENT_INDEX_CACHE
    if _EVENT_INDEX_CACHE is None:
        _EVENT_INDEX_CACHE = _load_13d_stake_increase_events()
    return _EVENT_INDEX_CACHE


def _build_quality_index(
    companyfacts_rows: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    index, summary = _load_event_index()
    return index, {
        **summary,
        "selected_companyfacts_rows_ignored": len(companyfacts_rows),
        "field_source": "parsed_sec_13d13g_holder_stake_direction_not_companyfacts",
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indices = {
        ticker: runner.base.framework.shadow._row_index(
            runner.base.framework.shadow._series(snapshot, ticker)
        )
        for ticker in snapshot
    }
    dates = runner.base.framework.shadow._trading_dates(snapshot)
    start = str(cfg["start"])
    end = str(cfg["end"])
    scan: Counter[str] = Counter()
    scan["eligible_event_tickers"] = len(set(quality_index) & set(snapshot))
    scan["positive_stake_change_events_total"] = sum(len(v) for v in quality_index.values())
    candidates: list[dict[str, Any]] = []
    for ticker in sorted(set(quality_index) & set(snapshot)):
        for event in quality_index[ticker]:
            signal_date = runner._signal_date_for_event(event, dates)
            if signal_date is None:
                scan["event_after_last_or_stale"] += 1
                continue
            if not (start <= signal_date <= end):
                scan["event_outside_window"] += 1
                continue
            scan["positive_stake_change_events_in_window"] += 1
            scan[f"source_window_{event.get('source_row_window')}"] += 1
            confirm = runner._absorption_confirmation(
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
            )
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "SEC_13D_AMEND_STAKE_INCREASE_ABSORPTION_PAPER",
                    "candidate_score": _round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "parsed_13d_stake_increase_and_signal_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_submissions": True,
                    "uses_parsed_sec_13d13g": True,
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
                    "sec_13d_current_class_percent": event.get("current_class_percent"),
                    "sec_13d_prior_class_percent": event.get("prior_class_percent"),
                    "sec_13d_stake_delta_pct_points": event.get("stake_delta_pct_points"),
                    "sec_13d_prior_accession_number": event.get("prior_accession_number"),
                    "sec_13d_prior_filing_date": event.get("prior_filing_date"),
                    "sec_13d_reporting_person_types": event.get("reporting_person_types"),
                    "sec_13d_n_reporting_persons": event.get("n_reporting_persons"),
                    "sec_13d_is_big3": event.get("is_big3"),
                    "sec_13d_issuer_cik": event.get("issuer_cik"),
                    "sec_13d_issuer_name": event.get("issuer_name"),
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
        "direction_rule": "current parsed 13D/A max_class_percent > prior same issuer-holder parsed 13D max_class_percent",
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
    gate = runner.base.framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    ev_delta = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if ev_delta <= runner.base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_compression_ev_not_beaten")
    if pnl_delta <= runner.base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_compression_pnl_not_beaten")
    if ev_delta <= runner.base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_distribution_ev_not_beaten")
    if pnl_delta <= runner.base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_distribution_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["accepted_compression_comparator"] = runner.base.COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = runner.base.DISTRIBUTION_COMPARATOR
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_not_promoted_parsed_13d_stake_increase_absorption"
        if gate["passed"]
        else "rejected_parsed_13d_stake_increase_absorption_candidate_pool"
    )
    return gate


def _interpretation(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    if gate4["passed"]:
        return (
            "The parsed 13D/A stake-increase absorption source cleared the "
            "numeric three-window replay screen, but remains only a replay lead "
            "because no shared daily/backtest helper was promoted."
        )
    return (
        "The parsed 13D/A stake-increase absorption source did not clear "
        f"Gate 4 (failed: {', '.join(gate4['failed_reasons']) or 'none'}). "
        "The fixed bundle tested only positive sequential stake-change direction "
        "plus signal-day SPY-relative price absorption. The result is not "
        "retained or promoted."
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
            "mechanism_family": "production_visible_sec_ownership_holder_stake_candidate_pool",
            "new_evidence_type": "parsed_sequential_13d_amend_stake_change_direction",
            "nearby_prior_experiments": [
                "exp-20260612-015",
                "exp-20260618-014",
                "exp-20260618-016",
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
        "direction_rule": (
            "current parsed 13D/A max_class_percent > prior same issuer-holder "
            "parsed 13D max_class_percent"
        ),
        "no_static_class_percent_threshold": True,
        "no_holder_type_filter": True,
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
        "Parsed Schedule 13D/A amendments are read from the local EDGAR "
        "primary_doc.xml cache through quant/sec_13d13g_ingest.py. A row is "
        "eligible only when its current max_class_percent is greater than the "
        "prior same issuer-holder parsed 13D row known earlier in filing/"
        "acceptance order. The signal date is the filing date unless the SEC "
        "acceptance timestamp is after 16:00, in which case it is the next "
        "trading day. Candidates must show signal-day price absorption before "
        "next-open paper entry: non-negative daily return, return minus SPY >= "
        "0.5%, close location >= 0.56, volume ratio >= 0.75, realized vol <= "
        "12%, ret20 excess vs SPY >= -5%, price >= $10, and ADV20 >= $50M. "
        "Paper entry is the next available open with entry slippage; exit is "
        "the close 10 trading days after the signal with target-side sell "
        "slippage and ROUND_TRIP_COST_PCT."
    )
    payload["backtest_protocol"]["parsed_surface"] = "quant/sec_13d13g_ingest.py"
    payload["gate2"]["runtime_fields"] = [
        "parsed 13D/13D-A accession number",
        "parsed 13D/13D-A filing date",
        "parsed 13D/13D-A acceptanceDateTime",
        "parsed reporting-person names",
        "parsed max_class_percent",
        "prior same issuer-holder parsed max_class_percent",
        "warehouse ticker_universe CIK mapping",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for price absorption",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "If this fixed stake-increase direction source fails, do not retry by "
        "sweeping stake-delta thresholds, classPercent thresholds, holder type, "
        "Big-3 exclusions, signal excess, close-location, volume, volatility, "
        "ret20, price/ADV, event-age, top-N, hold days, cooldown, or notional "
        "on these frozen windows. A valid retry needs 13G/A stake-change "
        "direction coverage, 13D Item 4 purpose-text classification, repaired "
        "old_thin structured XML coverage, or closed forward replacement-value "
        "rows."
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
            "A negative result means the parsed 13D/A ownership increase is "
            "still too stale, too sparse, or too issuer-control-heavy after "
            "next-open execution and price absorption. The field is useful as "
            "ownership context, but not sufficient entry timing evidence."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping stake-delta thresholds, classPercent "
            "thresholds, holder type, Big-3 exclusions, signal excess, "
            "close-location, volume, volatility, ret20, price/ADV, event-age, "
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


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Events | Raw | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in runner.base.framework.WINDOWS:
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
                events=scan.get("positive_stake_change_events_in_window", 0),
                raw=scan.get("deduped_candidate_rows", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Parsed 13D/A Stake-Increase Absorption",
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
            _repo_rel(Path(__file__)): runner.base.framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): runner.base.framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): runner.base.framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): runner.base.framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): runner.base.framework._sha256(CARD_MD),
        },
    }
    runner.base.framework._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    log_record = runner.base._build_log_record(payload)
    runner.base.framework._write_json(OUT_JSON, payload)
    runner.base.framework._write_json(LOG_JSON, payload)
    runner.base.framework._write_text(CARD_MD, _build_card(payload))
    runner.base.framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
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
    runner.base.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields=fields,
    )
    _write_manifest(payload)


def _install() -> None:
    runner.EXPERIMENT_ID = EXPERIMENT_ID
    runner.STEM = STEM
    runner.TRIAL_FAMILY = TRIAL_FAMILY
    runner.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    runner.CHANGED_VARIABLE = CHANGED_VARIABLE
    runner.RULE_VERSION = RULE_VERSION
    runner.OWNER = OWNER
    runner.OUT_DIR = OUT_DIR
    runner.OUT_JSON = OUT_JSON
    runner.LOG_JSON = LOG_JSON
    runner.TICKET_JSON = TICKET_JSON
    runner.CARD_MD = CARD_MD
    runner.MANIFEST_JSON = MANIFEST_JSON
    runner.EXPERIMENT_LOG = EXPERIMENT_LOG
    runner.REGISTRY_JSON = REGISTRY_JSON
    runner.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    runner.HOLD_DAYS = HOLD_DAYS
    runner.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    runner.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    runner.MIN_PRICE = MIN_PRICE
    runner.MIN_AVG_DOLLAR_VOLUME_20D = MIN_AVG_DOLLAR_VOLUME_20D
    runner.MIN_SIGNAL_RETURN = MIN_SIGNAL_RETURN
    runner.MIN_SIGNAL_EXCESS_SPY = MIN_SIGNAL_EXCESS_SPY
    runner.MIN_CLOSE_LOCATION = MIN_CLOSE_LOCATION
    runner.MIN_VOLUME_RATIO_20D = MIN_VOLUME_RATIO_20D
    runner.MAX_REALIZED_VOL_20D = MAX_REALIZED_VOL_20D
    runner.MIN_RET20_EXCESS_SPY = MIN_RET20_EXCESS_SPY
    runner.MAX_EVENT_AGE_TRADING_DAYS = MAX_EVENT_AGE_TRADING_DAYS
    runner.PREDICTION = PREDICTION
    runner.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    runner.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    runner._EVENT_INDEX_CACHE = None
    runner._load_event_index = _load_event_index
    runner._build_quality_index = _build_quality_index
    runner._candidate_rows_for_window = _candidate_rows_for_window
    runner._gate4 = _gate4
    runner._postprocess_payload = _postprocess_payload
    runner._build_card = _build_card
    runner._write_manifest = _write_manifest
    runner._persist = _persist


def main() -> None:
    _install()
    runner.main()


if __name__ == "__main__":
    main()
