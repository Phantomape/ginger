"""exp-20260626-007: Companyfacts product/service revenue mix shift.

This tests one alpha hypothesis: PIT Companyfacts product/service revenue
mix growth, especially services and subscription-like revenue facts, may
identify durable demand leaders when paired with liquid SPY-relative price
confirmation.

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


EXPERIMENT_ID = "exp-20260626-007"
STEM = "companyfacts_product_service_revenue_mix_shift"
TRIAL_FAMILY = "companyfacts_product_service_revenue_mix_shift_candidate_pool"
TRIAL_VARIANT_ID = "product_service_mix_shift_top1_next_open_10d_v1"
CHANGED_VARIABLE = "companyfacts_product_service_revenue_mix_shift_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-explore"

REPO_ROOT = previous.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260626_007_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

MAX_FACT_AGE_DAYS = 540
MIN_PRIOR_GAP_DAYS = 250
MAX_PRIOR_GAP_DAYS = 500
MIN_SERVICE_REVENUE_GROWTH = 0.08
MIN_SERVICE_MIX_GROWTH = 0.05
MIN_SERVICE_MIX_DELTA = 0.005
MIN_SERVICE_TO_REVENUE = 0.03
MIN_CURRENT_SERVICE_USD = 20_000_000.0

PRODUCT_SERVICE_CONCEPT_GROUPS: dict[str, tuple[str, ...]] = {
    "insurance_services": ("InsuranceServicesRevenue",),
    "sales_services_net": ("SalesRevenueServicesNet",),
    "sales_services_gross": ("SalesRevenueServicesGross",),
    "subscription_revenue": ("SubscriptionRevenue",),
    "technology_services": ("TechnologyServicesRevenue",),
    "license_and_services": ("LicenseAndServicesRevenue",),
}

PREDICTION = {
    "success_probability": 0.14,
    "expected_ev_delta": 0.15,
    "expected_pnl_delta": 2500.0,
    "main_failure_modes": [
        "companyfacts_source_saturation",
        "product_service_tags_stale_or_deprecated",
        "insurance_services_concentration",
        "window_regression",
        "accepted_comparator_not_beaten",
    ],
    "confidence_reason": (
        "exp-20260626-002 surfaced a product_service Companyfacts tag surface "
        "and playbook allows segment revenue/profit mix as a materially new "
        "axis. Confidence is low because the selected tags are mostly stale "
        "or deprecated in the standard windows, the live current coverage is "
        "concentrated in InsuranceServicesRevenue, and broad Companyfacts "
        "candidate-pool scans are saturated."
    ),
    "recorded_at": "2026-06-26T06:20:00+00:00",
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
    "product_service_concepts": PRODUCT_SERVICE_CONCEPT_GROUPS,
    "execution_envelope": {
        **previous.PRODUCTION_IMPACT["execution_envelope"],
        "failure_handling": (
            "missing raw companyfacts product/service revenue tag, stale fact, "
            "missing comparable prior same-concept fact, missing current or "
            "prior annual revenue scaler, missing OHLCV, missing next open, "
            "or missing 10d exit rejects the paper candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production code. A positive result is only "
        "a replay lead until a shared default-off helper and selected "
        "Companyfacts daily surface compute the same product/service revenue "
        "mix gate, liquid SPY-relative confirmation, cooldown, next-open paper "
        "entry, 10-day exit, costs, and concentration controls in both "
        "historical replay and daily production."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: PIT SEC Companyfacts product/service revenue mix "
        "shift, especially rising services or subscription-like revenue share "
        "versus prior comparable filed facts, may identify durable demand "
        "leaders whose next-open 10-day default-off paper continuation beats "
        "accepted OHLCV comparators when paired with liquid SPY-relative "
        "confirmation."
    ),
    "2_history_check": {
        "exp-20260626-002": (
            "Accepted measurement repair inventory surfaced product_service "
            "Companyfacts tags and showed enough all-history coverage for one "
            "fixed PIT tag-surface scout, while also revealing that current "
            "standard-window coverage is likely thin and concentrated."
        ),
        "exp-20260626-003": (
            "Rejected purchase-obligation maturity-ladder facts. This run uses "
            "recognized product/service revenue mix, not supplier/customer "
            "purchase commitments."
        ),
        "exp-20260626-004": (
            "Rejected completed-divestiture facts. This run uses product/"
            "service revenue share growth, not business-sale proceeds or "
            "divestiture completion facts."
        ),
        "exp-20260615-026": (
            "Rejected SEC SaaS/subscription KPI text. This run uses numeric "
            "Companyfacts facts known by filed date, not text regex spans."
        ),
        "novelty_gate": (
            "Reservation required novelty and saturated-source overrides. The "
            "new evidence axis is the exact product_service revenue tag surface "
            "from exp-20260626-002, not inventory, warranty, asset growth, "
            "purchase-obligation, divestiture, segment-count, customer-"
            "concentration, top-N, hold-day, or threshold retuning."
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
        "exp_20260626_007_companyfacts_product_service_revenue_mix_shift.py"
    ),
}


def _prior_same_concept(
    facts: list[dict[str, Any]],
    *,
    asof: str,
    current: dict[str, Any],
) -> dict[str, Any] | None:
    current_end = previous._parse_date(current["end"])
    if current_end is None:
        return None
    candidates: list[dict[str, Any]] = []
    for fact in facts:
        if fact["filed"] > asof or fact["end"] >= current["end"]:
            continue
        if fact.get("concept") != current.get("concept"):
            continue
        gap = (current_end - (previous._parse_date(fact["end"]) or current_end)).days
        if MIN_PRIOR_GAP_DAYS <= gap <= MAX_PRIOR_GAP_DAYS:
            candidates.append(fact)
    if not candidates:
        return None
    return max(candidates, key=lambda fact: (fact["end"], fact["filed"]))


def _service_mix_observation(
    ticker: str,
    asof: str,
    facts: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    revenue = previous._latest_revenue_on_or_before(facts["revenue"], asof)
    if revenue is None or float(revenue["value"]) <= 0:
        return None
    for group in PRODUCT_SERVICE_CONCEPT_GROUPS:
        group_facts = [fact for fact in facts["demand"] if fact.get("concept_group") == group]
        current = previous._latest_on_or_before(group_facts, asof)
        if current is None:
            continue
        if previous._days_between(asof, current["filed"]) > MAX_FACT_AGE_DAYS:
            continue
        prior = _prior_same_concept(group_facts, asof=asof, current=current)
        if prior is None or float(prior["value"]) <= 0:
            continue
        prior_revenue = previous._latest_revenue_on_or_before(facts["revenue"], prior["filed"])
        if prior_revenue is None or float(prior_revenue["value"]) <= 0:
            continue
        current_value = float(current["value"])
        current_revenue = float(revenue["value"])
        prior_value = float(prior["value"])
        prior_revenue_value = float(prior_revenue["value"])
        service_revenue_growth = current_value / prior_value - 1.0
        current_service_mix = current_value / current_revenue
        prior_service_mix = prior_value / prior_revenue_value
        if prior_service_mix <= 0:
            continue
        service_mix_growth = current_service_mix / prior_service_mix - 1.0
        service_mix_delta = current_service_mix - prior_service_mix
        if current_value < MIN_CURRENT_SERVICE_USD:
            continue
        if current_service_mix < MIN_SERVICE_TO_REVENUE:
            continue
        if service_revenue_growth < MIN_SERVICE_REVENUE_GROWTH:
            continue
        if service_mix_growth < MIN_SERVICE_MIX_GROWTH:
            continue
        if service_mix_delta < MIN_SERVICE_MIX_DELTA:
            continue
        row = {
            "demand_group": group,
            "demand_concept": current.get("concept"),
            "current_demand_end": current["end"],
            "prior_demand_end": prior["end"],
            "current_demand_filed": current["filed"],
            "prior_demand_filed": prior["filed"],
            "current_demand_value": previous._round(current_value, 2),
            "prior_demand_value": previous._round(prior_value, 2),
            "demand_growth": previous._round(service_mix_growth, 6),
            "demand_to_revenue": previous._round(current_service_mix, 6),
            "service_revenue_growth": previous._round(service_revenue_growth, 6),
            "service_mix_delta": previous._round(service_mix_delta, 6),
            "prior_service_mix": previous._round(prior_service_mix, 6),
            "prior_revenue_value": previous._round(prior_revenue_value, 2),
            "prior_revenue_filed": prior_revenue["filed"],
            "revenue_value": previous._round(current_revenue, 2),
            "revenue_filed": revenue["filed"],
            "fact_age_days": previous._days_between(asof, current["filed"]),
        }
        if best is None:
            best = row
            continue
        best_score = (
            float(best["demand_growth"] or 0.0)
            + 0.65 * float(best["demand_to_revenue"] or 0.0)
            + 0.35 * float(best["service_revenue_growth"] or 0.0)
        )
        row_score = (
            float(row["demand_growth"] or 0.0)
            + 0.65 * float(row["demand_to_revenue"] or 0.0)
            + 0.35 * float(row["service_revenue_growth"] or 0.0)
        )
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
            quality = _service_mix_observation(ticker, signal_date, quality_index[ticker])
            if quality is None:
                scan["failed_product_service_mix_gate"] += 1
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
                0.95 * min(float(quality["demand_growth"] or 0.0), 2.0)
                + 0.45 * min(float(quality["service_revenue_growth"] or 0.0), 2.0)
                + 0.50 * min(float(quality["demand_to_revenue"] or 0.0), 1.0)
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
                    "source": "COMPANYFACTS_PRODUCT_SERVICE_REVENUE_MIX_PAPER",
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
            -float(row["demand_demand_growth"] or 0.0),
            -float(row["demand_service_revenue_growth"] or 0.0),
            -float(row["demand_demand_to_revenue"] or 0.0),
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
        "min_prior_gap_days": MIN_PRIOR_GAP_DAYS,
        "max_prior_gap_days": MAX_PRIOR_GAP_DAYS,
        "min_service_revenue_growth": MIN_SERVICE_REVENUE_GROWTH,
        "min_service_mix_growth": MIN_SERVICE_MIX_GROWTH,
        "min_service_mix_delta": MIN_SERVICE_MIX_DELTA,
        "min_service_to_revenue": MIN_SERVICE_TO_REVENUE,
        "min_current_service_usd": MIN_CURRENT_SERVICE_USD,
        "product_service_concept_groups": PRODUCT_SERVICE_CONCEPT_GROUPS,
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
        "positive_replay_lead_not_promoted_companyfacts_product_service_mix"
        if gate["passed"]
        else "rejected_companyfacts_product_service_mix_candidate_pool"
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
        "The product/service revenue mix source cleared the numeric "
        "three-window replay screen, but remains only a replay lead because no "
        "shared helper or daily Companyfacts surface was promoted."
        if gate4["passed"]
        else (
            "The product/service revenue mix source did not clear "
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
            "mechanism_family": "production_visible_sec_companyfacts_product_service_mix_candidate_pool",
            "new_evidence_type": "selected_pit_companyfacts_product_service_revenue_mix_tags",
            "nearby_prior_experiments": [
                "exp-20260626-002",
                "exp-20260626-003",
                "exp-20260626-004",
                "exp-20260615-026",
                "exp-20260619-012",
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
        "min_prior_gap_days": MIN_PRIOR_GAP_DAYS,
        "max_prior_gap_days": MAX_PRIOR_GAP_DAYS,
        "min_service_revenue_growth": MIN_SERVICE_REVENUE_GROWTH,
        "min_service_mix_growth": MIN_SERVICE_MIX_GROWTH,
        "min_service_mix_delta": MIN_SERVICE_MIX_DELTA,
        "min_service_to_revenue": MIN_SERVICE_TO_REVENUE,
        "min_current_service_usd": MIN_CURRENT_SERVICE_USD,
        "product_service_concept_groups": PRODUCT_SERVICE_CONCEPT_GROUPS,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["execution_model"] = (
        "Raw SEC Companyfacts product/service revenue facts are known by filed "
        "date (<= signal date). The latest same-concept service, subscription, "
        "technology-service, or license-and-service revenue value is compared "
        "with its prior same-concept fact roughly one fiscal year earlier, then "
        "scaled by current and prior filed annual revenue to require true mix "
        "expansion. Price confirmation uses only signal-date OHLCV. Paper "
        "entry is the next available open with existing entry slippage; exit "
        "is the close 10 trading days after signal with target-side sell "
        "slippage and ROUND_TRIP_COST_PCT."
    )
    payload["gate2"]["runtime_fields"] = [
        "raw SEC companyfacts product/service revenue facts",
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
        "A valid retry needs materially richer current product/service or "
        "segment revenue provenance such as parsed segment/product revenue "
        "and profit mix from filings, current selected-taxonomy coverage, "
        "closed forward replacement-value rows, or a shared daily selected-"
        "Companyfacts surface. Do not sweep product/service tags, mix growth, "
        "service/revenue, current dollars, fact age, prior gap, RS/close/"
        "volume, top-N, hold, cooldown, or notional thresholds."
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
            "Do not retry by sweeping product/service tag lists, service "
            "revenue growth, service/revenue mix, mix delta, current dollars, "
            "fact age, prior gap, RS/close/volume, top-N, hold days, cooldown, "
            "or notional on these frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    card = _ORIGINAL_BUILD_CARD(payload)
    return card.replace(
        "Deferred Revenue Demand Acceleration",
        "Companyfacts Product/Service Revenue Mix Shift",
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
    previous.DEMAND_CONCEPT_GROUPS = PRODUCT_SERVICE_CONCEPT_GROUPS
    previous.MAX_FACT_AGE_DAYS = MAX_FACT_AGE_DAYS
    previous.MIN_PRIOR_GAP_DAYS = MIN_PRIOR_GAP_DAYS
    previous.MAX_PRIOR_GAP_DAYS = MAX_PRIOR_GAP_DAYS
    previous.MIN_DEMAND_GROWTH = MIN_SERVICE_MIX_GROWTH
    previous.MIN_DEMAND_TO_REVENUE = MIN_SERVICE_TO_REVENUE
    previous.MIN_CURRENT_DEMAND_USD = MIN_CURRENT_SERVICE_USD
    previous.PREDICTION = PREDICTION
    previous.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    previous.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    previous._demand_observation = _service_mix_observation
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
