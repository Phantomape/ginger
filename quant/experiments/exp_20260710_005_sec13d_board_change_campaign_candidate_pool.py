"""exp-20260710-005: concrete SEC 13D Item-4 campaign outcomes.

Alpha search replay scout. This tests one fixed selector on the newly repaired
parsed SEC 13D ownership surface: only concrete campaign outcomes with an
actual board appointment, board-size change, board departure, or nomination
withdrawal are eligible. It intentionally excludes the broad standstill and
generic board-representation rows that made exp-20260629-009 a rejected
governance_terms_present source.

No strategy, live order, ranking, sizing, exit, watchlist, or daily helper
behavior is changed by this replay.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import exp_20260629_009_sec_13d_item4_governance_terms_candidate_pool as base


EXPERIMENT_ID = "exp-20260710-005"
STEM = "sec13d_board_change_campaign_candidate_pool"
TRIAL_FAMILY = "sec13d_concrete_campaign_outcome_candidate_pool"
TRIAL_VARIANT_ID = "fixed_board_change_outcomes_top1_10d_v1"
CHANGED_VARIABLE = "sec13d_concrete_board_change_campaign_candidate_pool_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-explore"

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260710_005_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
CANONICAL_13D_ROWS = REPO_ROOT / "data" / "non_ohlcv" / "sec_13d13g_holdings" / "rows.json"

BASE_NOTIONAL_USD = base.BASE_NOTIONAL_USD
HOLD_DAYS = base.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = base.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = base.SAME_TICKER_COOLDOWN_DAYS

MIN_PRICE = base.MIN_PRICE
MIN_AVG_DOLLAR_VOLUME_20D = base.MIN_AVG_DOLLAR_VOLUME_20D
MIN_SIGNAL_RETURN = base.MIN_SIGNAL_RETURN
MIN_SIGNAL_EXCESS_SPY = base.MIN_SIGNAL_EXCESS_SPY
MIN_CLOSE_LOCATION = base.MIN_CLOSE_LOCATION
MIN_VOLUME_RATIO_20D = base.MIN_VOLUME_RATIO_20D
MAX_REALIZED_VOL_20D = base.MAX_REALIZED_VOL_20D
MIN_RET20_EXCESS_SPY = base.MIN_RET20_EXCESS_SPY
MAX_EVENT_AGE_TRADING_DAYS = base.MAX_EVENT_AGE_TRADING_DAYS

PREDICTION = {
    "success_probability": 0.24,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "thin_sample",
        "old_thin_window_regression",
        "accepted_comparator_not_beaten",
        "target_concentration_failed",
    ],
    "confidence_reason": (
        "Mechanism: actual board appointments, board-size changes, departures, "
        "and nomination withdrawals are more concrete activist campaign "
        "outcomes than the rejected broad governance_terms_present text "
        "surface. Exp-20260710-003 materialized these fields into canonical "
        "13D rows, and exp-20260710-004 repaired novelty accounting so the "
        "true parsed 13D ownership surface is counted separately. Main "
        "disconfirmers are sparse tradeable rows, next-open pricing, "
        "old_thin fragility, and accepted comparator failure."
    ),
    "recorded_at": "2026-07-10T03:13:33+00:00",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "uses_parsed_sec_13d13g": True,
    "uses_structured_item4_governance_terms": True,
    "uses_concrete_campaign_outcomes": True,
    "trade_enabled": False,
    "execution_envelope": {
        **base.PRODUCTION_IMPACT["execution_envelope"],
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "selection_rule": (
            "Only canonical 13D rows with board_appointment_count > 0, "
            "board_size_delta present, board_departure_present, or "
            "nomination_withdrawal_present are eligible."
        ),
    },
    "parity_note": (
        "Replay-only scout. A positive result would still require a shared "
        "default-off helper and daily snapshot before it can be accepted as "
        "paper alpha."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool/full_stack: newly materialized Schedule 13D Item-4 "
        "concrete campaign outcomes, limited to actual board appointments, "
        "board-size changes, board departures, or nomination withdrawals, may "
        "isolate fresher activist catalysts than exp-20260629-009's broad "
        "governance_terms_present source and add next-open 10-session "
        "default-off paper PnL without sweeping governance buckets."
    ),
    "2_history_check": {
        "exp-20260629-009": (
            "Rejected broad item4_governance_terms_present source. This run "
            "does not admit all governance terms and excludes standstill-only "
            "or generic board-representation rows unless a concrete board "
            "change/departure/withdrawal outcome is present."
        ),
        "exp-20260710-003": (
            "Accepted measurement repair materializing canonical Item-4 "
            "campaign fields into data/non_ohlcv/sec_13d13g_holdings/rows.json."
        ),
        "exp-20260710-004": (
            "Accepted measurement repair routing these proposals to "
            "sec13d_ownership rather than saturated generic SEC text/13F cells."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL must "
        "be positive, no window EV/PnL regression, at least two EV-improved "
        "windows, at least 20 paper trades across all 3 windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration pass, and accepted compression/"
        "distribution comparators must be beaten. Replay-only positives are "
        "leads until shared daily/backtest parity exists."
    ),
    "5_reproducibility": (
        ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260710_005_sec13d_board_change_campaign_candidate_pool.py"
    ),
}

_EVENT_INDEX_CACHE: tuple[dict[str, list[dict[str, Any]]], dict[str, Any]] | None = None
_BASE_CANDIDATE_ROWS = base._candidate_rows_for_window
_BASE_GATE4 = base._gate4
_BASE_POSTPROCESS = base._postprocess_payload


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _round(value: Any, digits: int = 6) -> float | None:
    return base._round(value, digits)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}


def _rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    rows = payload.get("rows") if isinstance(payload, Mapping) else payload
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _terms(row: Mapping[str, Any]) -> dict[str, Any]:
    terms = row.get("item4_governance_terms")
    return terms if isinstance(terms, dict) else {}


def _is_concrete_campaign_outcome(row: Mapping[str, Any]) -> bool:
    terms = _terms(row)
    return bool(
        (terms.get("board_appointment_count") or 0) > 0
        or terms.get("board_size_delta") is not None
        or terms.get("board_departure_present")
        or terms.get("nomination_withdrawal_present")
    )


def _outcome_strength(terms: Mapping[str, Any]) -> float:
    strength = 0.0
    strength += min(1.0, 0.25 * float(terms.get("board_appointment_count") or 0.0))
    if terms.get("board_size_delta") is not None:
        strength += 0.75
    if terms.get("board_departure_present"):
        strength += 0.50
    if terms.get("nomination_withdrawal_present"):
        strength += 0.75
    return strength


def _holder_key(row: Mapping[str, Any]) -> str:
    persons = row.get("reporting_persons")
    if not isinstance(persons, list):
        return ""
    names = sorted(
        str(person.get("reporting_person_name") or "").strip().lower()
        for person in persons
        if isinstance(person, dict) and person.get("reporting_person_name")
    )
    return "|".join(names)


def _load_concrete_campaign_events() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    rows = _rows_from_payload(_read_json(CANONICAL_13D_ROWS))
    index: dict[str, list[dict[str, Any]]] = {}
    stats: Counter[str] = Counter()
    stats["canonical_rows"] = len(rows)

    for row in rows:
        if row.get("family") != "13D":
            stats["non_13d_rows_skipped"] += 1
            continue
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            stats["missing_ticker"] += 1
            continue
        if not row.get("item4_text_present"):
            stats["missing_item4_text"] += 1
            continue
        if not _is_concrete_campaign_outcome(row):
            stats["not_concrete_outcome"] += 1
            continue

        terms = _terms(row)
        bucket = str(row.get("item4_governance_terms_bucket") or "unknown")
        stats["concrete_campaign_events"] += 1
        stats[f"concrete_campaign_{row.get('window')}"] += 1
        stats[f"bucket_{bucket}"] += 1
        if (terms.get("board_appointment_count") or 0) > 0:
            stats["outcome_board_appointment"] += 1
        if terms.get("board_size_delta") is not None:
            stats["outcome_board_size_delta"] += 1
        if terms.get("board_departure_present"):
            stats["outcome_board_departure"] += 1
        if terms.get("nomination_withdrawal_present"):
            stats["outcome_nomination_withdrawal"] += 1

        index.setdefault(ticker, []).append(
            {
                "ticker": ticker,
                "form": row.get("form"),
                "family": row.get("family"),
                "filing_date": row.get("filing_date"),
                "accepted_after_close": base.prior.runner._acceptance_after_close(
                    row.get("accepted_at")
                ),
                "acceptance_datetime": row.get("accepted_at"),
                "accession_number": row.get("accession_number"),
                "amendment_no": row.get("amendment_no"),
                "holder_key": _holder_key(row),
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
                "item4_governance_strength": _round(_outcome_strength(terms), 4),
                "item4_board_appointment_count": terms.get("board_appointment_count"),
                "item4_board_size_delta": terms.get("board_size_delta"),
                "item4_board_departure_present": terms.get("board_departure_present"),
                "item4_nomination_withdrawal_present": terms.get(
                    "nomination_withdrawal_present"
                ),
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
    stats["tickers_with_concrete_campaign_events"] = len(index)
    stats["candidate_event_count"] = sum(len(events) for events in index.values())
    summary = {
        "canonical_rows_path": _repo_rel(CANONICAL_13D_ROWS),
        "candidate_universe_scope": "broad_liquid_warehouse_all_windows_full_liquid",
        "concrete_outcome_rule": (
            "board_appointment_count > 0 OR board_size_delta present OR "
            "board_departure_present OR nomination_withdrawal_present"
        ),
        "excluded_broad_governance_rows": (
            "standstill-only, cooperation-only, and generic board-seat/"
            "representation rows without a concrete board/departure/withdrawal outcome"
        ),
        "no_js": True,
        **dict(stats),
    }
    return index, summary


def _load_event_index() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    global _EVENT_INDEX_CACHE
    if _EVENT_INDEX_CACHE is None:
        _EVENT_INDEX_CACHE = _load_concrete_campaign_events()
    return _EVENT_INDEX_CACHE


def _build_quality_index(
    companyfacts_rows: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    index, summary = _load_event_index()
    return index, {
        **summary,
        "selected_companyfacts_rows_ignored": len(companyfacts_rows),
        "field_source": "canonical_sec13d_item4_concrete_campaign_outcomes",
    }


def _candidate_rows_for_window(**kwargs: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, scan = _BASE_CANDIDATE_ROWS(**kwargs)
    for row in rows:
        row["source"] = "SEC_13D_ITEM4_CONCRETE_CAMPAIGN_PAPER"
        row["source_rule_version"] = RULE_VERSION
        row["rule_version"] = RULE_VERSION
        row["known_at"] = (
            "canonical_13d_item4_concrete_campaign_outcome_and_signal_close_"
            "before_next_open_paper_entry"
        )
        row["uses_concrete_campaign_outcomes"] = True
    scan = {
        **scan,
        "rule_version": RULE_VERSION,
        "concrete_outcome_rule": (
            "board appointment, board-size change, board departure, or "
            "nomination withdrawal required"
        ),
        "broad_governance_terms_present_source": "excluded_not_retested",
    }
    return rows, scan


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = _BASE_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    gate["decision"] = (
        "positive_replay_lead_not_promoted_sec13d_concrete_campaign_outcome"
        if gate["passed"]
        else "rejected_sec13d_concrete_campaign_outcome_candidate_pool"
    )
    return gate


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload = _BASE_POSTPROCESS(payload)
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    interpretation = (
        "The concrete 13D Item-4 campaign-outcome source cleared the numeric "
        "replay screen, but remains only a lead because no shared daily helper "
        "or production parity path was promoted."
        if gate4["passed"]
        else (
            "The concrete 13D Item-4 campaign-outcome source did not clear "
            "Gate 4. It is either too sparse, too concentrated, or not "
            "incremental after next-open execution and accepted comparators."
        )
    )
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
            "change_type": "candidate_pool_full_stack",
            "implementation_mode": "private_replay_scout_due_new_surface_shape",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_sec13d_ownership_campaign_candidate_pool",
            "new_evidence_type": "canonical_sec13d_item4_concrete_campaign_outcome_selector",
            "new_evidence_axis": (
                "Newly materialized canonical 13D Item-4 concrete campaign "
                "outcome fields after exp-20260710-003, with fingerprint "
                "coverage repaired by exp-20260710-004. This excludes broad "
                "standstill/generic board-representation rows from exp-20260629-009."
            ),
            "nearby_prior_experiments": [
                "exp-20260629-009",
                "exp-20260710-003",
                "exp-20260710-004",
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
        "surprise_note": (
            "Low base-rate prediction was appropriate because the selector is "
            "narrow and the accepted comparator bar is high."
        ),
    }
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "concrete_outcome_rule": (
            "board_appointment_count > 0 OR board_size_delta present OR "
            "board_departure_present OR nomination_withdrawal_present"
        ),
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
        "Canonical parsed Schedule 13D rows are read from "
        "data/non_ohlcv/sec_13d13g_holdings/rows.json. A row is eligible only "
        "when it has a concrete Item-4 campaign outcome: actual board "
        "appointment, board-size change, board departure, or nomination "
        "withdrawal. Signal date, price absorption, next-open entry, 10-session "
        "exit, costs, cooldown, and liquidity gates match exp-20260629-009."
    )
    payload["gate2"]["runtime_fields"] = [
        "canonical 13D accession number",
        "canonical 13D filing date",
        "canonical 13D accepted_at",
        "item4_governance_terms.board_appointment_count",
        "item4_governance_terms.board_size_delta",
        "item4_governance_terms.board_departure_present",
        "item4_governance_terms.nomination_withdrawal_present",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for price absorption",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "Do not retry by changing concrete outcome lists, adding standstill/"
        "cooperation-only rows, holder-type filters, classPercent thresholds, "
        "price absorption thresholds, top-N, hold, cooldown, notional, or "
        "response shape on the same frozen windows. A legal retry needs "
        "closed forward replacement-value rows from a fixed shared helper, "
        "campaign outcome evidence beyond the current parser, or a genuinely "
        "new ownership/campaign data source."
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
        "forbidden_near_neighbor_retry": (
            "Do not retry by changing concrete outcome lists, adding standstill/"
            "cooperation-only rows, holder types, classPercent, price/ADV, "
            "event age, top-N, hold, cooldown, notional, or response shape on "
            "these frozen windows."
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
    aggregate = payload["delta_metrics"]["aggregate"]
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Raw | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.prior.runner.base.framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {raw} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                raw=scan.get("deduped_candidate_rows", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} SEC 13D Concrete Campaign Outcomes",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
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
            "No JavaScript was used.",
        ]
    ) + "\n"


def _install() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = RULE_VERSION
    base.OWNER = OWNER
    base.REPO_ROOT = REPO_ROOT
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
    base.MIN_SIGNAL_RETURN = MIN_SIGNAL_RETURN
    base.MIN_SIGNAL_EXCESS_SPY = MIN_SIGNAL_EXCESS_SPY
    base.MIN_CLOSE_LOCATION = MIN_CLOSE_LOCATION
    base.MIN_VOLUME_RATIO_20D = MIN_VOLUME_RATIO_20D
    base.MAX_REALIZED_VOL_20D = MAX_REALIZED_VOL_20D
    base.MIN_RET20_EXCESS_SPY = MIN_RET20_EXCESS_SPY
    base.MAX_EVENT_AGE_TRADING_DAYS = MAX_EVENT_AGE_TRADING_DAYS
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    base._EVENT_INDEX_CACHE = None
    base._load_event_index = _load_event_index
    base._build_quality_index = _build_quality_index
    base._candidate_rows_for_window = _candidate_rows_for_window
    base._gate4 = _gate4
    base._postprocess_payload = _postprocess_payload
    base._build_card = _build_card
    base._install()


def main() -> None:
    if str(Path(__file__).resolve().parent) not in sys.path:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
    _install()
    base.prior.runner.main()


if __name__ == "__main__":
    main()
