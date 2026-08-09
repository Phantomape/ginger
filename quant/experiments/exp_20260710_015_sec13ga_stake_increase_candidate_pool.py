"""exp-20260710-015: SEC 13G/A non-Big3 stake-increase candidate pool.

Alpha search replay. The single decision hypothesis is that the newly
materialized 13G/A amendment direction fields from exp-20260710-014 identify
ownership-demand events when the computed direction is ``increase`` and the
holder is not one of the Big-3 passive index complexes.

This uses the existing parsed 13D/13G next-open / 10-session paper replay
envelope and accepted-comparator Gate-4 logic. It changes no production code,
orders, ranking, sizing, exits, LLM/news path, watchlist, or daily helper
behavior. A positive result would still require a shared default-off helper
before being retained as paper alpha.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import exp_20260710_005_sec13d_board_change_campaign_candidate_pool as base


EXPERIMENT_ID = "exp-20260710-015"
STEM = "sec13ga_stake_increase_candidate_pool"
TRIAL_FAMILY = "sec13ga_stake_change_direction_candidate_pool"
TRIAL_VARIANT_ID = "fixed_non_big3_increase_top1_10d_v1"
CHANGED_VARIABLE = "sec13ga_non_big3_stake_increase_candidate_pool_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-explore"

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260710_015_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
CANONICAL_13D13G_ROWS = (
    REPO_ROOT / "data" / "non_ohlcv" / "sec_13d13g_holdings" / "rows.json"
)

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
    "success_probability": 0.21,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "thin_sample",
        "old_thin_window_regression",
        "accepted_comparator_not_beaten",
        "target_concentration_failed",
    ],
    "confidence_reason": (
        "Mechanism: a computed 13G/A increase by a non-Big3 holder is more "
        "like ownership demand than mechanical Big3 passive amendment churn "
        "or below-5pct exits. Nearby history rejected broad 13D campaign "
        "outcomes and older static 13G metadata; exp-20260710-014 newly "
        "materialized 2,787 13G/A rows with 161 increase rows and PIT "
        "previous-accession direction fields. Main disconfirmers are sparse "
        "tradeable rows, next-open pricing, old_thin fragility, and accepted "
        "comparator failure."
    ),
    "recorded_at": "2026-07-10T15:05:16+00:00",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "uses_concrete_campaign_outcomes": False,
    "uses_parsed_sec_13d13g": True,
    "uses_sec13ga_direction_fields": True,
    "uses_structured_item4_governance_terms": False,
    "trade_enabled": False,
    "execution_envelope": {
        **base.PRODUCTION_IMPACT["execution_envelope"],
        "failure_handling": (
            "missing canonical 13G/A rows, missing computed direction fields, "
            "missing OHLCV, missing next open, or missing 10d exit rejects the "
            "paper candidate"
        ),
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "selection_rule": (
            "Only canonical 13G/A amendment rows with computed "
            "sec13ga_stake_change_direction == increase and is_big3 == false "
            "are eligible."
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
        "candidate_pool/full_stack: newly materialized SEC 13G/A amendment "
        "stake-change direction rows should isolate non-Big3 stake-increase "
        "demand; a fixed top-1/day default-off paper source using only "
        "computed non-Big3 increase rows may add next-open 10-session "
        "replacement value versus accepted comparators without sweeping holder "
        "types, classPercent, notional, hold, or response shape."
    ),
    "2_history_check": {
        "exp-20260618-016": (
            "Requested parsed 13D/13G holder/stake rows before further "
            "ownership alpha tests."
        ),
        "exp-20260710-014": (
            "Accepted measurement repair materializing 2,787 canonical 13G/A "
            "amendment rows and computed direction fields; no alpha claim."
        ),
        "exp-20260710-005": (
            "Rejected concrete 13D Item-4 campaign outcomes. This run uses "
            "13G/A direction fields, not 13D Item-4 phrase/outcome rows."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL "
        "must be positive, no window EV/PnL regression, at least two "
        "EV-improved windows, at least 20 paper trades across all 3 windows, "
        "survival >=5%, drawdown drift <=0.5pp, concentration pass, and "
        "accepted compression/distribution comparators must be beaten. "
        "Replay-only positives are leads until shared daily/backtest parity "
        "exists."
    ),
    "5_reproducibility": (
        ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260710_015_sec13ga_stake_increase_candidate_pool.py"
    ),
}

_EVENT_INDEX_CACHE: tuple[
    dict[str, list[dict[str, Any]]], dict[str, Any], dict[str, dict[str, Any]]
] | None = None


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


def _load_stake_increase_events() -> tuple[
    dict[str, list[dict[str, Any]]], dict[str, Any], dict[str, dict[str, Any]]
]:
    rows = _rows_from_payload(_read_json(CANONICAL_13D13G_ROWS))
    index: dict[str, list[dict[str, Any]]] = {}
    by_accession: dict[str, dict[str, Any]] = {}
    stats: Counter[str] = Counter()
    stats["canonical_rows"] = len(rows)

    for row in rows:
        if row.get("family") != "13G" or not row.get("is_amendment"):
            stats["non_13ga_rows_skipped"] += 1
            continue
        ticker = str(row.get("ticker") or "").upper()
        direction = row.get("sec13ga_stake_change_direction")
        status = row.get("sec13ga_direction_status")
        stats[f"direction_status_{status}"] += 1
        stats[f"direction_{direction}"] += 1
        if not ticker:
            stats["missing_ticker"] += 1
            continue
        if status != "computed" or direction != "increase":
            stats["not_computed_increase"] += 1
            continue
        if bool(row.get("is_big3")):
            stats["big3_increase_excluded"] += 1
            continue

        event = {
            "ticker": ticker,
            "form": row.get("form"),
            "family": row.get("family"),
            "filing_date": row.get("filing_date"),
            "accepted_after_close": base.base.prior.runner._acceptance_after_close(
                row.get("accepted_at")
            ),
            "acceptance_datetime": row.get("accepted_at"),
            "accession_number": row.get("accession_number"),
            "amendment_no": row.get("amendment_no"),
            "holder_key": _holder_key(row),
            "max_class_percent": _round(row.get("sec13ga_current_max_percent"), 4),
            "reporting_person_types": row.get("reporting_person_types") or [],
            "n_reporting_persons": row.get("n_reporting_persons"),
            "is_big3": bool(row.get("is_big3")),
            "issuer_cik": row.get("issuer_cik"),
            "issuer_name": row.get("issuer_name"),
            "issuer_cusip": row.get("issuer_cusip"),
            "source_row_window": row.get("window"),
            # The base 13D runner uses this as a small tie-break only. Keep it
            # zero so this experiment tests direction, not percent magnitude.
            "item4_governance_terms_bucket": "sec13ga_non_big3_increase",
            "item4_governance_term_hits": ["sec13ga_non_big3_increase"],
            "item4_governance_strength": 0.0,
            "sec13ga_previous_accession": row.get("sec13ga_previous_accession"),
            "sec13ga_current_max_percent": row.get("sec13ga_current_max_percent"),
            "sec13ga_current_max_shares": row.get("sec13ga_current_max_shares"),
            "sec13ga_previous_max_percent": row.get("sec13ga_previous_max_percent"),
            "sec13ga_percent_delta": row.get("sec13ga_percent_delta"),
            "sec13ga_stake_change_direction": direction,
            "sec13ga_direction_status": status,
            "sec13ga_below_5pct": row.get("sec13ga_below_5pct"),
            "sec13ga_item4_person_count": row.get("sec13ga_item4_person_count"),
        }
        index.setdefault(ticker, []).append(event)
        accession = str(row.get("accession_number") or "")
        if accession:
            by_accession[accession] = event
        stats["eligible_non_big3_increase_events"] += 1
        stats[f"eligible_window_{row.get('window')}"] += 1

    for ticker in index:
        index[ticker].sort(
            key=lambda event: (
                str(event.get("filing_date") or ""),
                str(event.get("acceptance_datetime") or ""),
                str(event.get("accession_number") or ""),
            )
        )
    stats["tickers_with_non_big3_increase_events"] = len(index)
    stats["candidate_event_count"] = sum(len(events) for events in index.values())
    summary = {
        "canonical_rows_path": _repo_rel(CANONICAL_13D13G_ROWS),
        "candidate_universe_scope": "broad_liquid_warehouse_all_windows_full_liquid",
        "selector": (
            "family == 13G AND is_amendment == true AND "
            "sec13ga_direction_status == computed AND "
            "sec13ga_stake_change_direction == increase AND is_big3 == false"
        ),
        "excluded_rows": (
            "Big3 passive complexes, below-5pct exits, decreases, unchanged, "
            "unknown-direction rows, 13G initial rows, and 13D Item-4 rows."
        ),
        "fingerprint_caveat": (
            "experiment.py novelty inferred gate_shape=forward_attribution from "
            "replacement-value wording, but the source-saturation block also "
            "reported sec13d_ownership/candidate_pool_top1_10d trials=0."
        ),
        "no_js": True,
        **dict(stats),
    }
    return index, summary, by_accession


def _load_event_index() -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    global _EVENT_INDEX_CACHE
    if _EVENT_INDEX_CACHE is None:
        _EVENT_INDEX_CACHE = _load_stake_increase_events()
    return _EVENT_INDEX_CACHE[0], _EVENT_INDEX_CACHE[1]


def _event_by_accession() -> dict[str, dict[str, Any]]:
    global _EVENT_INDEX_CACHE
    if _EVENT_INDEX_CACHE is None:
        _EVENT_INDEX_CACHE = _load_stake_increase_events()
    return _EVENT_INDEX_CACHE[2]


def _build_quality_index(
    companyfacts_rows: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    index, summary = _load_event_index()
    return index, {
        **summary,
        "selected_companyfacts_rows_ignored": len(companyfacts_rows),
        "field_source": "canonical_sec13ga_amendment_stake_change_direction",
    }


def _candidate_rows_for_window(**kwargs: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, scan = base._BASE_CANDIDATE_ROWS(**kwargs)
    by_accession = _event_by_accession()
    for row in rows:
        accession = str(row.get("sec_13d_accession_number") or "")
        event = by_accession.get(accession, {})
        row["source"] = "SEC_13GA_NON_BIG3_STAKE_INCREASE_PAPER"
        row["source_rule_version"] = RULE_VERSION
        row["rule_version"] = RULE_VERSION
        row["known_at"] = (
            "canonical_13ga_stake_increase_direction_and_signal_close_before_"
            "next_open_paper_entry"
        )
        row["uses_sec13ga_direction_fields"] = True
        row["uses_structured_item4_governance_terms"] = False
        row["sec13ga_accession_number"] = accession
        row["sec13ga_previous_accession"] = event.get("sec13ga_previous_accession")
        row["sec13ga_current_max_percent"] = event.get("sec13ga_current_max_percent")
        row["sec13ga_current_max_shares"] = event.get("sec13ga_current_max_shares")
        row["sec13ga_previous_max_percent"] = event.get("sec13ga_previous_max_percent")
        row["sec13ga_percent_delta"] = event.get("sec13ga_percent_delta")
        row["sec13ga_stake_change_direction"] = event.get(
            "sec13ga_stake_change_direction"
        )
        row["sec13ga_direction_status"] = event.get("sec13ga_direction_status")
        row["sec13ga_below_5pct"] = event.get("sec13ga_below_5pct")
        row["sec13ga_item4_person_count"] = event.get("sec13ga_item4_person_count")
    scan = {
        **scan,
        "rule_version": RULE_VERSION,
        "selector": (
            "computed non-Big3 13G/A stake increase only; no holder type, "
            "classPercent, notional, hold, or response-shape sweep"
        ),
        "excluded_13d_item4_campaign_source": "excluded_not_retested",
    }
    return rows, scan


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = base._BASE_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    gate["decision"] = (
        "positive_replay_lead_not_promoted_sec13ga_non_big3_stake_increase"
        if gate["passed"]
        else "rejected_sec13ga_non_big3_stake_increase_candidate_pool"
    )
    return gate


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload = base._BASE_POSTPROCESS(payload)
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    status = "positive_replay_lead_not_promoted" if gate4["passed"] else "rejected"
    interpretation = (
        "The computed non-Big3 13G/A stake-increase source cleared the numeric "
        "replay screen, but remains only a lead because no shared daily helper "
        "or production parity path was promoted."
        if gate4["passed"]
        else (
            "The computed non-Big3 13G/A stake-increase source did not clear "
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
            "implementation_mode": "private_replay_scout_due_no_shared_helper_retained",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": (
                "production_visible_sec13ga_ownership_stake_change_candidate_pool"
            ),
            "new_evidence_type": (
                "canonical_sec13ga_amendment_stake_change_direction_fields"
            ),
            "new_evidence_axis": (
                "New alpha-enabling canonical 13G/A amendment stake-change "
                "direction fields from exp-20260710-014: previous accession, "
                "current item4 percent/shares, below-5pct flag, and computed "
                "increase/decrease/exit direction across 2,787 amendment rows. "
                "This is not a 13D Item-4 phrase, holder-type/classPercent "
                "threshold, notional, hold, or response-shape retry."
            ),
            "nearby_prior_experiments": [
                "exp-20260618-016",
                "exp-20260710-014",
                "exp-20260710-005",
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
            "Low base-rate prediction was appropriate because SEC ownership "
            "candidate-pool comparators are demanding and 13G/A direction rows "
            "may be sparse after price/liquidity gates."
        ),
    }
    payload["parameters"] = {
        "paper_notional_usd": BASE_NOTIONAL_USD,
        "hold_days": HOLD_DAYS,
        "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "selector": (
            "family == 13G AND is_amendment == true AND "
            "sec13ga_direction_status == computed AND "
            "sec13ga_stake_change_direction == increase AND is_big3 == false"
        ),
        "direction_magnitude_used_for_tiebreak": False,
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
        "Canonical parsed Schedule 13G/A amendment rows are read from "
        "data/non_ohlcv/sec_13d13g_holdings/rows.json. A row is eligible only "
        "when direction_status is computed, stake_change_direction is increase, "
        "and is_big3 is false. Signal date, price absorption, next-open entry, "
        "10-session exit, costs, cooldown, and liquidity gates match the "
        "accepted 13D/G replay envelope used by exp-20260629-009 and "
        "exp-20260710-005."
    )
    payload["gate2"]["runtime_fields"] = [
        "canonical 13G/A accession number",
        "canonical 13G/A filing date",
        "canonical 13G/A accepted_at",
        "sec13ga_previous_accession",
        "sec13ga_current_max_percent",
        "sec13ga_current_max_shares",
        "sec13ga_previous_max_percent",
        "sec13ga_percent_delta",
        "sec13ga_stake_change_direction",
        "sec13ga_direction_status",
        "sec13ga_below_5pct",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for price absorption",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["next_evidence_needed"] = (
        "Do not retry by changing holder-type filters, adding Big3 rows, using "
        "below-5pct exits/decreases as a response curve, changing classPercent "
        "thresholds, signal excess, close-location, volume, volatility, ret20, "
        "price/ADV, event age, top-N, hold, cooldown, notional, or response "
        "shape on these frozen windows. A legal retry needs closed forward "
        "replacement-value rows from a fixed shared 13G/A helper, a genuinely "
        "new ownership/campaign data source, or richer holder intent/economics "
        "provenance beyond the current parser."
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
            "Do not retry by changing holder-type filters, adding Big3 rows, "
            "using below-5pct exits/decreases, classPercent, price/ADV, event "
            "age, top-N, hold, cooldown, notional, or response shape on these "
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


def _build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Raw | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.base.prior.runner.base.framework.WINDOWS:
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
            f"# {EXPERIMENT_ID} SEC 13G/A Stake-Increase Candidate Pool",
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
    base.base.prior.runner.main()


if __name__ == "__main__":
    main()
