"""exp-20260614-026: TTM cash-conversion acceleration candidate pool.

Replay-only alpha search. This tests a distinct SEC Companyfacts earnings-
quality field from the rejected annual accruals/cash-conversion variants:
current interim TTM cash conversion must improve versus the comparable prior
year TTM period. The intent is to preserve the gross accruals edge while
avoiding a broad static annual-quality momentum overlay.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260614_020_accruals_cash_conversion_quality as base  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260614-026"
STEM = "ttm_cash_conversion_acceleration"
TRIAL_FAMILY = "ttm_cash_conversion_acceleration_candidate_pool"
TRIAL_VARIANT_ID = "companyfacts_ttm_cash_conversion_acceleration_top1_next_open_10d_v1"
CHANGED_VARIABLE = "ttm_cash_conversion_acceleration_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "codex-alpha-search"
SCRIPT_PATH = Path(__file__)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260614_026_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

INTERIM_DURATION_MIN = 75
INTERIM_DURATION_MAX = 320
ANNUAL_DURATION_MIN = 340
ANNUAL_DURATION_MAX = 380
PRIOR_PERIOD_MIN_LAG_DAYS = 320
PRIOR_PERIOD_MAX_LAG_DAYS = 410
MAX_TTM_FACT_AGE_DAYS = 220
MIN_TTM_CASH_CONVERSION = 0.80
MAX_TTM_ACCRUALS_TO_ASSETS = 0.03
MIN_TTM_CASH_CONVERSION_ACCELERATION = 0.15

PREDICTION = {
    "success_probability": 0.21,
    "expected_ev_delta": 0.35,
    "expected_pnl_delta": 5000.0,
    "main_failure_modes": [
        "drawdown_drift_too_high",
        "window_regression",
        "static_cash_conversion_overlap",
        "thin_acceleration_sample",
        "accepted_comparator_not_beaten",
    ],
    "confidence_reason": (
        "The annual and annual-improvement cash-conversion scouts were "
        "directionally strong but rejected on drawdown/window fragility; "
        "requiring interim TTM cash conversion to accelerate versus the prior "
        "same-period TTM is a distinct PIT Companyfacts field, not a deployment, "
        "stop, threshold, hold, cooldown, or notional retry."
    ),
    "recorded_at": "2026-06-14T21:03:48+00:00",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "private_replay_scout_no_shared_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "uses_llm": False,
    "uses_free_sec_companyfacts": True,
    "uses_free_ohlcv": True,
    "execution_envelope": {
        **base.PRODUCTION_IMPACT["execution_envelope"],
        "failure_handling": (
            "missing interim net_income/operating_cash_flow YTD facts, missing "
            "prior annual or prior comparable YTD facts, missing assets, missing "
            "OHLCV, missing next open, or missing 10d exit rejects the paper "
            "candidate"
        ),
    },
    "parity_note": (
        "This experiment changes no production path. A positive result is only "
        "a replay lead until a shared default-off helper computes the same PIT "
        "interim TTM cash-conversion acceleration gate, liquid SPY-relative "
        "confirmation, cooldown, next-open paper entry, 10-day exit, costs, "
        "and concentration controls in both historical replay and daily "
        "production snapshots."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: interim TTM operating-cash-flow conversion that "
        "improves versus the comparable prior-year TTM should identify "
        "earnings-quality acceleration rather than static quality, improving "
        "next-open 10-day replacement value for liquid leaders."
    ),
    "2_history_check": {
        "exp-20260614-020": (
            "Static annual accruals/cash conversion had EV +0.9921 and PnL "
            "+$21,322.65, positive in all three windows, but failed drawdown "
            "drift at +5.22pp."
        ),
        "exp-20260614-021": (
            "Low-deployment redesign cut sample but still regressed old_thin "
            "and exceeded drawdown drift."
        ),
        "exp-20260614-023": (
            "Daily-close protective stop preserved positive aggregate EV but "
            "regressed two windows and still exceeded drawdown drift."
        ),
        "exp-20260615-018": (
            "Annual current-vs-prior cash-conversion/accrual improvement "
            "improved aggregate EV/PnL but regressed late_strong and old_thin "
            "and worsened drawdown +1.77pp."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Aggregate EV/PnL "
        "must be positive, no window EV/PnL regression, at least 20 paper "
        "trades across all 3 windows, survival >=5%, drawdown drift <=0.5pp, "
        "concentration pass, and accepted compression/distribution "
        "candidate-pool comparators beaten. Replay-only positives are leads "
        "until shared daily/backtest parity exists."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260614_026_ttm_cash_conversion_acceleration.py"
    ),
}

_ORIGINAL_BUILD_QUALITY_INDEX = base._build_quality_index
_ORIGINAL_CANDIDATE_ROWS = base._candidate_rows_for_window
_ORIGINAL_BUILD_PAYLOAD = base._build_payload
_ORIGINAL_BUILD_LOG_RECORD = base._build_log_record


def _period_facts(rows: list[dict[str, Any]], canonical: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for raw in rows:
        if str(raw.get("canonical") or "") != canonical:
            continue
        try:
            duration = int(raw.get("duration_days"))
        except (TypeError, ValueError):
            continue
        if not (INTERIM_DURATION_MIN <= duration <= ANNUAL_DURATION_MAX):
            continue
        filed = str(raw.get("filed") or "")[:10]
        start = str(raw.get("start") or "")[:10]
        end = str(raw.get("end") or "")[:10]
        value = base._float_or_none(raw.get("value"))
        if not filed or not start or not end or value is None:
            continue
        facts.append(
            {
                "filed": filed,
                "start": start,
                "end": end,
                "duration_days": duration,
                "value": value,
                "form": raw.get("form"),
            }
        )
    facts.sort(key=lambda row: (row["filed"], row["end"], row["duration_days"], row["start"]))
    return facts


def _instant_facts(rows: list[dict[str, Any]], canonical: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for raw in rows:
        if str(raw.get("canonical") or "") != canonical:
            continue
        filed = str(raw.get("filed") or "")[:10]
        end = str(raw.get("end") or "")[:10]
        value = base._float_or_none(raw.get("value"))
        if not filed or value is None:
            continue
        facts.append({"filed": filed, "end": end, "value": value})
    facts.sort(key=lambda row: (row["filed"], row["end"]))
    return facts


def _build_quality_index(
    companyfacts_rows: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, list[dict[str, Any]]]], dict[str, Any]]:
    by_ticker: dict[str, list[dict[str, Any]]] = {}
    for raw in companyfacts_rows:
        ticker = str(raw.get("ticker") or "").upper()
        if ticker:
            by_ticker.setdefault(ticker, []).append(raw)
    index: dict[str, dict[str, list[dict[str, Any]]]] = {}
    missing_required = 0
    for ticker, rows in by_ticker.items():
        ni = _period_facts(rows, "net_income")
        ocf = _period_facts(rows, "operating_cash_flow")
        assets = _instant_facts(rows, "assets")
        if not ni or not ocf or not assets:
            missing_required += 1
            continue
        index[ticker] = {
            "net_income": ni,
            "operating_cash_flow": ocf,
            "assets": assets,
        }
    return index, {
        "companyfacts_rows_loaded": len(companyfacts_rows),
        "tickers_seen": len(by_ticker),
        "tickers_missing_required_facts": missing_required,
        "tickers_with_ttm_cash_conversion_facts": len(index),
    }


def _is_annual(fact: dict[str, Any]) -> bool:
    duration = int(fact["duration_days"])
    return ANNUAL_DURATION_MIN <= duration <= ANNUAL_DURATION_MAX


def _is_interim_ytd(
    fact: dict[str, Any],
    prior_annual: dict[str, Any] | None,
) -> bool:
    duration = int(fact["duration_days"])
    if not (INTERIM_DURATION_MIN <= duration <= INTERIM_DURATION_MAX):
        return False
    if duration > 130:
        return True
    if prior_annual is None:
        return False
    # A ~90 day period is valid only when it is fiscal Q1 YTD. Direct Q2/Q3
    # quarterly facts would make the TTM formula wrong, so require the start to
    # immediately follow the prior fiscal year end.
    gap = base._days_between(fact["start"], prior_annual["end"])
    return 1 <= gap <= 10


def _latest_annual_before(
    facts: list[dict[str, Any]], asof: str, period_end: str
) -> dict[str, Any] | None:
    chosen: dict[str, Any] | None = None
    for fact in facts:
        if fact["filed"] <= asof and fact["end"] < period_end and _is_annual(fact):
            chosen = fact
    return chosen


def _latest_asset_on_or_before(
    facts: list[dict[str, Any]], asof: str
) -> dict[str, Any] | None:
    chosen: dict[str, Any] | None = None
    for fact in facts:
        if fact["filed"] <= asof:
            chosen = fact
    return chosen


def _matched_fact(
    facts: list[dict[str, Any]], asof: str, reference: dict[str, Any]
) -> dict[str, Any] | None:
    candidates = [
        fact
        for fact in facts
        if fact["filed"] <= asof
        and fact["end"] == reference["end"]
        and abs(int(fact["duration_days"]) - int(reference["duration_days"])) <= 10
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda fact: (
            -abs(int(fact["duration_days"]) - int(reference["duration_days"])),
            fact["filed"],
        ),
    )


def _prior_same_period_fact(
    facts: list[dict[str, Any]], asof: str, reference: dict[str, Any]
) -> dict[str, Any] | None:
    ref_end = reference["end"]
    ref_duration = int(reference["duration_days"])
    candidates: list[dict[str, Any]] = []
    for fact in facts:
        if fact["filed"] > asof or fact["end"] >= ref_end:
            continue
        lag = base._days_between(ref_end, fact["end"])
        if not (PRIOR_PERIOD_MIN_LAG_DAYS <= lag <= PRIOR_PERIOD_MAX_LAG_DAYS):
            continue
        if abs(int(fact["duration_days"]) - ref_duration) > 20:
            continue
        candidates.append(fact)
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda fact: (
            -abs(base._days_between(ref_end, fact["end"]) - 365),
            -abs(int(fact["duration_days"]) - ref_duration),
            fact["filed"],
        ),
    )


def _ttm_value_for_fact(
    facts: list[dict[str, Any]],
    asof: str,
    current: dict[str, Any],
) -> tuple[float, dict[str, Any]] | None:
    value = float(current["value"])
    if _is_annual(current):
        return value, {
            "method": "annual_as_ttm",
            "current_filed": current["filed"],
            "current_end": current["end"],
            "current_duration_days": current["duration_days"],
        }
    prior_annual = _latest_annual_before(facts, asof, current["end"])
    if not _is_interim_ytd(current, prior_annual) or prior_annual is None:
        return None
    prior_ytd = _prior_same_period_fact(facts, asof, current)
    if prior_ytd is None:
        return None
    prior_annual_for_prior = _latest_annual_before(facts, asof, prior_ytd["end"])
    if not _is_interim_ytd(prior_ytd, prior_annual_for_prior):
        return None
    ttm_value = value + float(prior_annual["value"]) - float(prior_ytd["value"])
    return ttm_value, {
        "method": "interim_ytd_plus_prior_annual_less_prior_ytd",
        "current_filed": current["filed"],
        "current_start": current["start"],
        "current_end": current["end"],
        "current_duration_days": current["duration_days"],
        "prior_annual_filed": prior_annual["filed"],
        "prior_annual_end": prior_annual["end"],
        "prior_same_period_filed": prior_ytd["filed"],
        "prior_same_period_end": prior_ytd["end"],
        "prior_same_period_duration_days": prior_ytd["duration_days"],
    }


def _ttm_pair_for_current(
    ni_facts: list[dict[str, Any]],
    ocf_facts: list[dict[str, Any]],
    asof: str,
    current_ni: dict[str, Any],
) -> dict[str, Any] | None:
    if _is_annual(current_ni):
        return None
    current_ocf = _matched_fact(ocf_facts, asof, current_ni)
    if current_ocf is None:
        return None
    current_ni_ttm = _ttm_value_for_fact(ni_facts, asof, current_ni)
    current_ocf_ttm = _ttm_value_for_fact(ocf_facts, asof, current_ocf)
    if current_ni_ttm is None or current_ocf_ttm is None:
        return None
    prior_ni = _prior_same_period_fact(ni_facts, asof, current_ni)
    if prior_ni is None:
        return None
    prior_ocf = _matched_fact(ocf_facts, asof, prior_ni)
    if prior_ocf is None:
        return None
    prior_ni_ttm = _ttm_value_for_fact(ni_facts, asof, prior_ni)
    prior_ocf_ttm = _ttm_value_for_fact(ocf_facts, asof, prior_ocf)
    if prior_ni_ttm is None or prior_ocf_ttm is None:
        return None
    return {
        "current_ni_ttm": current_ni_ttm[0],
        "current_ocf_ttm": current_ocf_ttm[0],
        "current_ni_components": current_ni_ttm[1],
        "current_ocf_components": current_ocf_ttm[1],
        "prior_ni_ttm": prior_ni_ttm[0],
        "prior_ocf_ttm": prior_ocf_ttm[0],
        "prior_ni_components": prior_ni_ttm[1],
        "prior_ocf_components": prior_ocf_ttm[1],
    }


def _ttm_cash_conversion_quality(
    ticker: str,
    asof: str,
    facts: dict[str, list[dict[str, Any]]],
) -> dict[str, Any] | None:
    ni_facts = facts["net_income"]
    ocf_facts = facts["operating_cash_flow"]
    assets = _latest_asset_on_or_before(facts["assets"], asof)
    if assets is None or assets["value"] <= 0.0:
        return None
    current_candidates = [
        fact
        for fact in ni_facts
        if fact["filed"] <= asof
        and not _is_annual(fact)
        and _is_interim_ytd(fact, _latest_annual_before(ni_facts, asof, fact["end"]))
        and base._days_between(asof, fact["filed"]) <= MAX_TTM_FACT_AGE_DAYS
    ]
    current_candidates.sort(key=lambda fact: (fact["filed"], fact["end"], fact["duration_days"]))
    for current_ni in reversed(current_candidates):
        pair = _ttm_pair_for_current(ni_facts, ocf_facts, asof, current_ni)
        if pair is None:
            continue
        ni_val = float(pair["current_ni_ttm"])
        ocf_val = float(pair["current_ocf_ttm"])
        prior_ni_val = float(pair["prior_ni_ttm"])
        prior_ocf_val = float(pair["prior_ocf_ttm"])
        if ni_val <= 0.0 or ocf_val <= 0.0 or prior_ni_val <= 0.0 or prior_ocf_val <= 0.0:
            continue
        cash_conversion = ocf_val / ni_val
        prior_cash_conversion = prior_ocf_val / prior_ni_val
        acceleration = cash_conversion - prior_cash_conversion
        accruals_to_assets = (ni_val - ocf_val) / float(assets["value"])
        prior_accruals_to_assets = (prior_ni_val - prior_ocf_val) / float(assets["value"])
        accrual_improvement = prior_accruals_to_assets - accruals_to_assets
        if cash_conversion < MIN_TTM_CASH_CONVERSION:
            continue
        if accruals_to_assets > MAX_TTM_ACCRUALS_TO_ASSETS:
            continue
        if acceleration < MIN_TTM_CASH_CONVERSION_ACCELERATION:
            continue
        return {
            "fiscal_year_end": current_ni["end"],
            "net_income_filed": pair["current_ni_components"]["current_filed"],
            "operating_cash_flow_filed": pair["current_ocf_components"]["current_filed"],
            "assets_filed": assets["filed"],
            "net_income": base._round(ni_val, 2),
            "operating_cash_flow": base._round(ocf_val, 2),
            "total_assets": base._round(assets["value"], 2),
            "accruals_to_assets": base._round(accruals_to_assets, 6),
            "cash_conversion_ratio": base._round(cash_conversion, 6),
            "fact_age_days": base._days_between(asof, pair["current_ni_components"]["current_filed"]),
            "ttm_method": pair["current_ni_components"]["method"],
            "ttm_period_end": current_ni["end"],
            "ttm_duration_days": current_ni["duration_days"],
            "prior_ttm_period_end": pair["prior_ni_components"]["current_end"],
            "prior_ttm_cash_conversion_ratio": base._round(prior_cash_conversion, 6),
            "ttm_cash_conversion_acceleration": base._round(acceleration, 6),
            "prior_ttm_accruals_to_assets": base._round(prior_accruals_to_assets, 6),
            "ttm_accruals_to_assets_improvement": base._round(accrual_improvement, 6),
            "prior_ttm_net_income": base._round(prior_ni_val, 2),
            "prior_ttm_operating_cash_flow": base._round(prior_ocf_val, 2),
            "current_ni_components": pair["current_ni_components"],
            "current_ocf_components": pair["current_ocf_components"],
            "prior_ni_components": pair["prior_ni_components"],
            "prior_ocf_components": pair["prior_ocf_components"],
        }
    return None


def _candidate_rows_for_window(*args: Any, **kwargs: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, scan = _ORIGINAL_CANDIDATE_ROWS(*args, **kwargs)
    for row in rows:
        acceleration = float(row.get("quality_ttm_cash_conversion_acceleration") or 0.0)
        accrual_improvement = float(row.get("quality_ttm_accruals_to_assets_improvement") or 0.0)
        score = float(row.get("candidate_score") or 0.0)
        row["source"] = "TTM_CASH_CONVERSION_ACCELERATION_QUALITY_PAPER"
        row["rule_version"] = RULE_VERSION
        row["source_rule_version"] = RULE_VERSION
        row["known_at"] = "interim_ttm_companyfacts_filed_and_signal_close_before_next_open_paper_entry"
        row["candidate_score"] = base._round(
            score
            + 0.90 * min(max(acceleration, 0.0), 1.0)
            + 3.50 * min(max(accrual_improvement, 0.0), 0.10),
            6,
        )
    rows.sort(
        key=lambda row: (
            row["date"],
            -float(row.get("candidate_score") or 0.0),
            -float(row.get("quality_ttm_cash_conversion_acceleration") or 0.0),
            -float(row.get("quality_ttm_accruals_to_assets_improvement") or 0.0),
            float(row.get("quality_accruals_to_assets") or 0.0),
            -float(row.get("candidate_ret20_excess_spy") or 0.0),
            row["ticker"],
        )
    )
    scan = {
        **scan,
        "rule_version": RULE_VERSION,
        "max_ttm_fact_age_days": MAX_TTM_FACT_AGE_DAYS,
        "min_ttm_cash_conversion": MIN_TTM_CASH_CONVERSION,
        "max_ttm_accruals_to_assets": MAX_TTM_ACCRUALS_TO_ASSETS,
        "min_ttm_cash_conversion_acceleration": MIN_TTM_CASH_CONVERSION_ACCELERATION,
        "ttm_acceleration_candidate_rows": len(rows),
        "ttm_acceleration_candidate_tickers": len({row["ticker"] for row in rows}),
    }
    return rows, scan


def _decision_for_gate(passed: bool) -> str:
    if passed:
        return "positive_replay_lead_not_promoted_ttm_cash_conversion_acceleration"
    return "rejected_ttm_cash_conversion_acceleration_candidate_pool"


def _build_payload() -> dict[str, Any]:
    payload = _ORIGINAL_BUILD_PAYLOAD()
    aggregate = payload["delta_metrics"]["aggregate"]
    target_count = payload["target_trade_summary"]["total_trade_count"]
    gate4 = payload["gate4"]
    gate4["decision"] = _decision_for_gate(bool(gate4.get("passed")))
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": (
                "positive_replay_lead_not_promoted"
                if gate4.get("passed")
                else "rejected"
            ),
            "decision": gate4["decision"],
            "hypothesis": (
                "Interim TTM cash conversion that accelerates versus the "
                "comparable prior-year TTM may isolate true earnings-quality "
                "acceleration inside liquid leaders, reducing the broad "
                "drawdown of static annual accruals/cash-conversion quality."
            ),
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "new_evidence_type": "free_sec_companyfacts_interim_ttm_cash_conversion_acceleration_plus_ohlcv",
            "nearby_prior_experiments": [
                "exp-20260614-020",
                "exp-20260614-021",
                "exp-20260614-023",
                "exp-20260615-018",
            ],
            "prior_trial_count": 4,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "production_impact": PRODUCTION_IMPACT,
            "rejection_reason": (
                None if gate4.get("passed") else "; ".join(gate4.get("failed_reasons") or [])
            ),
            "interpretation": (
                "The interim TTM cash-conversion acceleration source cleared "
                "Gate 4 as a replay-only lead; production remains unchanged "
                "until a shared daily/backtest helper reproduces it."
                if gate4.get("passed")
                else (
                    "The interim TTM cash-conversion acceleration source did "
                    "not clear Gate 4. Do not promote it or tune TTM "
                    "acceleration/static quality thresholds on these frozen "
                    "windows."
                )
            ),
            "next_evidence_needed": (
                "A retry needs materially different PIT earnings-quality "
                "evidence such as quarterly cash-flow where directly reported, "
                "analyst breadth/dispersion confirmation, or closed forward "
                "replacement rows; do not sweep TTM acceleration, static "
                "accruals, price-confirmation, top-N, hold, cooldown, or "
                "notional thresholds."
            ),
            "related_files": [
                base._repo_rel(SCRIPT_PATH),
                base._repo_rel(OUT_JSON),
                base._repo_rel(LOG_JSON),
                base._repo_rel(TICKET_JSON),
                base._repo_rel(CARD_MD),
                base._repo_rel(MANIFEST_JSON),
                base._repo_rel(EXPERIMENT_LOG),
                base._repo_rel(REGISTRY_JSON),
            ],
        }
    )
    payload["parameters"].update(
        {
            "max_ttm_fact_age_days": MAX_TTM_FACT_AGE_DAYS,
            "min_ttm_cash_conversion": MIN_TTM_CASH_CONVERSION,
            "max_ttm_accruals_to_assets": MAX_TTM_ACCRUALS_TO_ASSETS,
            "min_ttm_cash_conversion_acceleration": MIN_TTM_CASH_CONVERSION_ACCELERATION,
            "require_interim_ttm": True,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Interim net_income and operating_cash_flow are known by SEC filed date "
        "(<= signal date). Current TTM uses current interim YTD plus prior "
        "annual less prior comparable YTD; prior comparison uses the same "
        "period one fiscal year earlier. Price confirmation uses only "
        "signal-date OHLCV. Paper entry is the next available open with "
        "existing entry slippage; exit is the close 10 trading days after the "
        "signal with target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            (
                "Gate 4 passed: interim TTM cash-conversion acceleration kept "
                "enough of the accruals gross edge while passing drawdown, "
                "concentration, sample, and accepted comparator guards."
            )
            if gate4.get("passed")
            else (
                "Gate 4 failed. The TTM acceleration discriminator either made "
                "the sample too thin or still behaved like a price-confirmed "
                "Companyfacts momentum overlay. Failed reasons: "
                + (", ".join(gate4.get("failed_reasons") or []) or "none")
                + "."
            )
        ),
        "outcome_summary": (
            "Aggregate EV delta {:+.4f}; aggregate PnL delta ${:+,.2f}; "
            "max drawdown drift {:+.4f}; {} paper trades.".format(
                aggregate["expected_value_score_delta_sum"],
                aggregate["total_pnl_delta_sum"],
                float(aggregate["max_drawdown_delta_max"] or 0.0),
                target_count,
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping TTM cash-conversion acceleration, "
            "cash-conversion ratio, accruals/assets, fact freshness, "
            "RS/close/volume/vol guards, top-N, hold days, cooldown, or "
            "notional on these frozen windows."
        ),
        "new_evidence_required": payload["next_evidence_needed"],
    }
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Eligible | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in base.framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {elig} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                elig=scan.get("eligible_quality_tickers", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} TTM Cash-Conversion Acceleration",
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
            "- Target trades: `{}`".format(
                payload["target_trade_summary"]["total_trade_count"]
            ),
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


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = _ORIGINAL_BUILD_LOG_RECORD(payload)
    record.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "decision": payload["decision"],
            "status": payload["status"],
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "hypothesis": payload["hypothesis"],
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "related_files": payload["related_files"],
            "anti_js": "No JavaScript was used.",
        }
    )
    return record


def _persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    base.framework._write_json(OUT_JSON, payload)
    base.framework._write_json(LOG_JSON, payload)
    base.framework._write_text(CARD_MD, _build_card(payload))
    base.framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": base._repo_rel(OUT_JSON),
        "log": base._repo_rel(LOG_JSON),
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
        "artifact": base._repo_rel(OUT_JSON),
        "log": base._repo_rel(LOG_JSON),
        "ticket_file": base._repo_rel(TICKET_JSON),
        "card_file": base._repo_rel(CARD_MD),
        "revision_manifest_file": base._repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": log_record["aggregate_expected_value_delta"],
        "aggregate_strategy_total_pnl_delta": log_record[
            "aggregate_strategy_total_pnl_delta"
        ],
    }
    persist_self_registered_result(
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
            base._repo_rel(SCRIPT_PATH),
            base._repo_rel(OUT_JSON),
            base._repo_rel(CARD_MD),
            base._repo_rel(MANIFEST_JSON),
            base._repo_rel(TICKET_JSON),
            base._repo_rel(LOG_JSON),
            base._repo_rel(EXPERIMENT_LOG),
            base._repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            base._repo_rel(SCRIPT_PATH): base.framework._sha256(SCRIPT_PATH),
            base._repo_rel(OUT_JSON): base.framework._sha256(OUT_JSON),
            base._repo_rel(LOG_JSON): base.framework._sha256(LOG_JSON),
            base._repo_rel(TICKET_JSON): base.framework._sha256(TICKET_JSON),
            base._repo_rel(CARD_MD): base.framework._sha256(CARD_MD),
        },
    }
    base.framework._write_json(MANIFEST_JSON, manifest)


def _patch_base() -> None:
    base.EXPERIMENT_ID = EXPERIMENT_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = RULE_VERSION
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.CARD_MD = CARD_MD
    base.MANIFEST_JSON = MANIFEST_JSON
    base.EXPERIMENT_LOG = EXPERIMENT_LOG
    base.REGISTRY_JSON = REGISTRY_JSON
    base.PREDICTION = PREDICTION
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    base._build_quality_index = _build_quality_index
    base._accruals_quality = _ttm_cash_conversion_quality
    base._candidate_rows_for_window = _candidate_rows_for_window
    base._build_payload = _build_payload
    base._build_log_record = _build_log_record
    base._build_card = _build_card
    base._persist = _persist
    base._write_manifest = _write_manifest


def main() -> None:
    _patch_base()
    payload = _build_payload()
    _persist(payload)
    print(json.dumps(base.framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
