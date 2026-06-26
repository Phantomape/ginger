"""exp-20260626-004: Companyfacts completed-divestiture segment simplification.

This tests one alpha hypothesis: PIT Companyfacts facts for completed
business divestitures or business-unit sales may identify portfolio
simplification events with short-horizon continuation when paired with liquid
SPY-relative price confirmation.

The run is default-off paper and replay-only. No live/default orders, ranking,
sizing, exits, LLM/news, watchlist, or production adapter behavior changes.
The novelty and saturation overrides are recorded on the ticket; this file
keeps the policy bundle fixed and does not sweep nearby Companyfacts fields.

No JavaScript was used.
"""

from __future__ import annotations

import math
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

import exp_20260615_017_deferred_revenue_demand_acceleration as previous


EXPERIMENT_ID = "exp-20260626-004"
STEM = "companyfacts_completed_divestiture_segment_simplification"
TRIAL_FAMILY = "companyfacts_completed_divestiture_segment_simplification_candidate_pool"
TRIAL_VARIANT_ID = "completed_divestiture_top1_next_open_10d_v1"
CHANGED_VARIABLE = "companyfacts_completed_divestiture_segment_simplification_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-explore"

REPO_ROOT = previous.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260626_004_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

MAX_FACT_AGE_DAYS = 150
MIN_DIVESTITURE_TO_REVENUE = 0.01
MIN_CURRENT_DIVESTITURE_USD = 15_000_000.0

DIVESTITURE_CONCEPT_GROUPS: dict[str, tuple[str, ...]] = {
    "divestiture_proceeds": (
        "ProceedsFromDivestitureOfBusinesses",
        "ProceedsFromDivestitureOfBusinessesAndInterestsInAffiliates",
    ),
    "business_sale_net_proceeds": (
        "PaymentsForProceedsFromBusinessesAndInterestInAffiliates",
    ),
    "sale_related_goodwill_writeoff": (
        "GoodwillWrittenOffRelatedToSaleOfBusinessUnit",
    ),
}

PREDICTION = {
    "success_probability": 0.15,
    "expected_ev_delta": 0.20,
    "expected_pnl_delta": 3000.0,
    "main_failure_modes": [
        "companyfacts_source_saturation",
        "window_regression",
        "drawdown_drift",
        "accepted_comparator_not_beaten",
        "divestiture_event_staleness_or_concentration",
    ],
    "confidence_reason": (
        "exp-20260626-002 surfaced segment/divestiture Companyfacts tags with "
        "broad cross-window coverage and playbook specifically allows "
        "materially different divestiture completion evidence; confidence "
        "remains low because Companyfacts scan-shape sources are saturated "
        "and accepted OHLCV comparators are strong."
    ),
    "recorded_at": "2026-06-26T03:05:28+00:00",
}

PRODUCTION_IMPACT = {
    **deepcopy(previous.PRODUCTION_IMPACT),
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "uses_free_sec_companyfacts": True,
    "uses_raw_companyfacts_cache": True,
    "uses_free_ohlcv": True,
    "divestiture_concepts": DIVESTITURE_CONCEPT_GROUPS,
    "execution_envelope": {
        **previous.PRODUCTION_IMPACT["execution_envelope"],
        "failure_handling": (
            "missing raw companyfacts completed-divestiture tag, stale fact, "
            "missing annual revenue scaler, missing OHLCV, missing next open, "
            "or missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper and selected "
        "Companyfacts daily surface compute the same completed-divestiture "
        "event gate, liquid SPY-relative confirmation, cooldown, next-open "
        "paper entry, 10-day exit, costs, and concentration controls in both "
        "historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: PIT SEC Companyfacts completed business divestiture "
        "facts, such as divestiture proceeds and goodwill written off on "
        "business-unit sale, may identify portfolio simplification events that "
        "can create next-open 10-day continuation when paired with liquid "
        "SPY-relative price confirmation."
    ),
    "2_history_check": {
        "exp-20260626-002": (
            "Accepted measurement repair inventory surfaced segment/customer/"
            "counterparty Companyfacts tags and explicitly listed divestiture "
            "completion evidence as a valid non-threshold segment axis."
        ),
        "exp-20260626-003": (
            "Rejected purchase-obligation maturity-ladder facts. This run uses "
            "completed divestiture/business-unit-sale facts, not supplier "
            "purchase commitments."
        ),
        "exp-20260622-003": (
            "Rejected SEC text divestiture/spin-off phrase variants. This run "
            "uses filed numeric Companyfacts completion facts, not SEC text "
            "phrase lists or optional value regexes."
        ),
        "novelty_gate": (
            "Reservation required novelty and saturated-source overrides. The "
            "new evidence axis is exact completed-divestiture Companyfacts "
            "tags surfaced by exp-20260626-002, not RPO/deferred revenue, "
            "purchase obligations, segment-count thresholds, capex, or SEC "
            "text retuning."
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
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260626_004_companyfacts_completed_divestiture_segment_simplification.py"
    ),
}


def _divestiture_observation(
    ticker: str,
    asof: str,
    facts: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    revenue = previous._latest_revenue_on_or_before(facts["revenue"], asof)
    if revenue is None or float(revenue["value"]) <= 0:
        return None
    for group in DIVESTITURE_CONCEPT_GROUPS:
        group_facts = [fact for fact in facts["demand"] if fact.get("concept_group") == group]
        current = previous._latest_on_or_before(group_facts, asof)
        if current is None:
            continue
        fact_age = previous._days_between(asof, current["filed"])
        if fact_age > MAX_FACT_AGE_DAYS:
            continue
        current_value = float(current["value"])
        divestiture_to_revenue = current_value / float(revenue["value"])
        if current_value < MIN_CURRENT_DIVESTITURE_USD:
            continue
        if divestiture_to_revenue < MIN_DIVESTITURE_TO_REVENUE:
            continue
        recency_score = max(0.0, (MAX_FACT_AGE_DAYS - fact_age) / MAX_FACT_AGE_DAYS)
        row = {
            "demand_group": group,
            "demand_concept": current.get("concept"),
            "current_demand_end": current["end"],
            "prior_demand_end": None,
            "current_demand_filed": current["filed"],
            "prior_demand_filed": None,
            "current_demand_value": previous._round(current_value, 2),
            "prior_demand_value": None,
            "demand_growth": previous._round(recency_score, 6),
            "demand_to_revenue": previous._round(divestiture_to_revenue, 6),
            "revenue_value": previous._round(revenue["value"], 2),
            "revenue_filed": revenue["filed"],
            "fact_age_days": fact_age,
        }
        if best is None:
            best = row
            continue
        best_score = float(best["demand_to_revenue"] or 0.0) + 0.35 * float(best["demand_growth"] or 0.0)
        row_score = float(row["demand_to_revenue"] or 0.0) + 0.35 * float(row["demand_growth"] or 0.0)
        if row_score > best_score:
            best = row
    return best


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    sector_entries: dict[str, dict[str, Any]],
    quality_index: dict[str, dict[str, list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    indices = {
        ticker: previous.base.framework.shadow._row_index(
            previous.base.framework.shadow._series(snapshot, ticker)
        )
        for ticker in snapshot
    }
    dates = previous.base.framework.shadow._trading_dates(snapshot)
    window_dates = [day for day in dates if str(cfg["start"]) <= day <= str(cfg["end"])]
    eligible = sorted(set(quality_index) & set(snapshot))
    scan: Counter[str] = Counter()
    scan["scanned_trading_days"] = len(window_dates)
    scan["eligible_quality_tickers"] = len(eligible)
    candidates: list[dict[str, Any]] = []
    for signal_date in window_dates:
        for ticker in eligible:
            scan["ticker_day_evaluations"] += 1
            quality = _divestiture_observation(ticker, signal_date, quality_index[ticker])
            if quality is None:
                scan["failed_completed_divestiture_gate"] += 1
                continue
            confirm = previous.base._price_confirmation(
                snapshot=snapshot,
                indices=indices,
                ticker=ticker,
                signal_date=signal_date,
            )
            if confirm is None:
                scan["failed_price_confirmation"] += 1
                continue
            scan["qualified_candidate_rows"] += 1
            meta = sector_entries.get(ticker, {})
            score = (
                0.80 * min(float(quality["demand_to_revenue"] or 0.0), 0.75)
                + 0.25 * float(quality["demand_growth"] or 0.0)
                + 0.45 * float(confirm["candidate_ret20_excess_spy"])
                + 0.12 * float(confirm["candidate_ret60_excess_spy"])
                + 0.10 * float(confirm["candidate_close_location"])
                + 0.035
                * math.log10(max(float(confirm["candidate_avg_dollar_volume_20d"]), 1.0) / 1_000_000.0)
            )
            candidates.append(
                {
                    "date": signal_date,
                    "ticker": ticker,
                    "source": "COMPANYFACTS_COMPLETED_DIVESTITURE_SEGMENT_PAPER",
                    "candidate_score": previous._round(score, 6),
                    "rule_version": RULE_VERSION,
                    "source_rule_version": RULE_VERSION,
                    "known_at": "raw_companyfacts_filed_and_signal_close_before_next_open_paper_entry",
                    "sector": meta.get("sector"),
                    "industry": meta.get("industry"),
                    "uses_free_sec_companyfacts": True,
                    "uses_raw_companyfacts_cache": True,
                    "uses_free_ohlcv": True,
                    "uses_llm": False,
                    "trade_enabled": False,
                    **{f"demand_{key}": value for key, value in quality.items()},
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
            -float(row["demand_demand_to_revenue"] or 0.0),
            -float(row["demand_demand_growth"] or 0.0),
            -float(row["candidate_ret20_excess_spy"] or 0.0),
            -float(row["candidate_avg_dollar_volume_20d"] or 0.0),
            row["ticker"],
        )
    )
    scan["deduped_candidate_rows"] = len(rows)
    scan["candidate_signal_days"] = len({row["date"] for row in rows})
    scan["candidate_tickers"] = len({row["ticker"] for row in rows})
    return rows, {
        **dict(scan),
        "rule_version": RULE_VERSION,
        "max_fact_age_days": MAX_FACT_AGE_DAYS,
        "min_divestiture_to_revenue": MIN_DIVESTITURE_TO_REVENUE,
        "min_current_divestiture_usd": MIN_CURRENT_DIVESTITURE_USD,
        "divestiture_concept_groups": DIVESTITURE_CONCEPT_GROUPS,
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = previous.base.framework._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    failed = list(gate.get("failed_reasons") or [])
    ev_delta = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    pnl_delta = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if ev_delta <= previous.base.COMPRESSION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_compression_ev_not_beaten")
    if pnl_delta <= previous.base.COMPRESSION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_compression_pnl_not_beaten")
    if ev_delta <= previous.base.DISTRIBUTION_COMPARATOR["aggregate_expected_value_delta"]:
        failed.append("accepted_distribution_ev_not_beaten")
    if pnl_delta <= previous.base.DISTRIBUTION_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_distribution_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["accepted_compression_comparator"] = previous.base.COMPRESSION_COMPARATOR
    gate["accepted_distribution_comparator"] = previous.base.DISTRIBUTION_COMPARATOR
    gate["passed"] = not failed
    gate["decision"] = (
        "positive_replay_lead_not_promoted_companyfacts_completed_divestiture"
        if gate["passed"]
        else "rejected_companyfacts_completed_divestiture_candidate_pool"
    )
    return gate


_ORIGINAL_PATCH_PAYLOAD = previous._patch_payload
_ORIGINAL_BUILD_CARD = previous._build_card


def _patch_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload = _ORIGINAL_PATCH_PAYLOAD(payload)
    aggregate = payload["delta_metrics"]["aggregate"]
    gate4 = payload["gate4"]
    failed = ", ".join(gate4.get("failed_reasons") or [])
    interpretation = (
        "The completed-divestiture Companyfacts source cleared the numeric "
        "three-window replay screen, but remains only a replay lead because no "
        "shared helper or daily Companyfacts surface was promoted."
        if gate4["passed"]
        else (
            "The completed-divestiture Companyfacts source did not clear "
            f"Gate 4 (failed: {failed or 'none'}). It is not retained or promoted."
        )
    )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "candidate_pool_full_stack",
            "implementation_mode": "private_replay_scout_due_saturated_source_shape",
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_sec_companyfacts_segment_divestiture_candidate_pool",
            "new_evidence_type": "selected_pit_companyfacts_completed_divestiture_segment_tags",
            "nearby_prior_experiments": [
                "exp-20260626-002",
                "exp-20260626-003",
                "exp-20260622-003",
            ],
            "multiple_testing_risk_bucket": "high",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "interpretation": interpretation,
            "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
        }
    )
    payload["parameters"] = {
        **payload.get("parameters", {}),
        "max_fact_age_days": MAX_FACT_AGE_DAYS,
        "min_divestiture_to_revenue": MIN_DIVESTITURE_TO_REVENUE,
        "min_current_divestiture_usd": MIN_CURRENT_DIVESTITURE_USD,
        "divestiture_concept_groups": DIVESTITURE_CONCEPT_GROUPS,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["execution_model"] = (
        "Raw SEC Companyfacts completed-divestiture facts are known by filed "
        "date (<= signal date). The latest divestiture-proceeds or "
        "business-unit-sale goodwill writeoff fact is scaled by latest filed "
        "annual revenue and used only for a fixed default-off paper candidate "
        "source. Price confirmation uses only signal-date OHLCV. Paper entry "
        "is the next available open with existing entry slippage; exit is the "
        "close 10 trading days after signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    payload["gate2"]["runtime_fields"] = [
        "raw SEC companyfacts completed-divestiture / business-unit-sale facts",
        "raw SEC companyfacts annual revenue facts",
        "SEC companyfacts filed date and period end",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "SPY OHLCV for relative strength",
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
    ]
    payload["calibration"] = {
        **payload["calibration"],
        "predicted_success_probability": PREDICTION["success_probability"],
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
    }
    payload["next_evidence_needed"] = (
        "A valid retry needs materially richer divestiture provenance such as "
        "normalized sold business/segment identity, divestiture completion "
        "status, proceeds use, segment revenue/profit mix, closed forward "
        "replacement-value rows, or a shared daily selected-Companyfacts "
        "surface. Do not sweep divestiture/revenue, fact age, tag list, "
        "RS/close/volume, top-N, hold, cooldown, or notional thresholds."
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
            "Do not retry by sweeping completed-divestiture tag lists, "
            "divestiture/revenue, minimum dollars, fact age, RS/close/volume, "
            "top-N, hold days, cooldown, or notional on these frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    card = _ORIGINAL_BUILD_CARD(payload)
    return card.replace(
        "Deferred Revenue Demand Acceleration",
        "Companyfacts Completed Divestiture Segment Simplification",
    ).replace(
        "Replay-only and default-off paper only.",
        "Replay-only default-off paper scout under a saturated-source override.",
    )


def _apply_overrides() -> None:
    previous.__file__ = __file__
    previous.EXPERIMENT_ID = EXPERIMENT_ID
    previous.STEM = STEM
    previous.TRIAL_FAMILY = TRIAL_FAMILY
    previous.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    previous.CHANGED_VARIABLE = CHANGED_VARIABLE
    previous.RULE_VERSION = RULE_VERSION
    previous.OWNER = OWNER
    previous.OUT_DIR = OUT_DIR
    previous.OUT_JSON = OUT_JSON
    previous.LOG_JSON = LOG_JSON
    previous.TICKET_JSON = TICKET_JSON
    previous.CARD_MD = CARD_MD
    previous.MANIFEST_JSON = MANIFEST_JSON
    previous.EXPERIMENT_LOG = EXPERIMENT_LOG
    previous.REGISTRY_JSON = REGISTRY_JSON
    previous.DEMAND_CONCEPT_GROUPS = DIVESTITURE_CONCEPT_GROUPS
    previous.MAX_FACT_AGE_DAYS = MAX_FACT_AGE_DAYS
    previous.PREDICTION = PREDICTION
    previous.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    previous.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    previous._demand_observation = _divestiture_observation
    previous._candidate_rows_for_window = _candidate_rows_for_window
    previous._gate4 = _gate4
    previous._patch_payload = _patch_payload
    previous._build_card = _build_card
    previous._RAW_ROWS_CACHE.clear()


def main() -> None:
    _apply_overrides()
    previous.main()


if __name__ == "__main__":
    main()
