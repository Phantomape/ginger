"""exp-20260711-019: chronological SEC 13F manager-skill candidate scout.

This private replay scout keeps the accepted SEC13F manager-conviction price,
liquidity, ranking, entry, exit, cost, cooldown, and core-overlap rules fixed.
The only decision change is an admission gate: a new conviction holder must
have a positive, chronologically observable median SPY-excess return across at
least five additions disclosed in the preceding 13F window.

No production/shared helper, order, ranking, sizing, exit, LLM, or live path is
changed.  A positive result is only a replay lead.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

import exp_20260621_019_sec13f_manager_conviction as prior
from ohlcv_warehouse import DEFAULT_WAREHOUSE_PATH, load_warehouse_ohlcv_frames


EXPERIMENT_ID = "exp-20260711-019"
STEM = "sec13f_chronological_manager_skill"
TRIAL_FAMILY = "sec13f_manager_skill_candidate_pool"
TRIAL_VARIANT_ID = "sec13f_prior_skill_new_conviction_liquid_leadership_top1_10d_v1"
CHANGED_VARIABLE = "sec13f_chronological_manager_skill_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE
OWNER = "alpha-explore-automation"

ROOT = prior.ROOT
OUT_DIR = ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260711_019_{STEM}.json"
LOG_JSON = ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
DERIVED_CACHE_DIR = OUT_DIR / "derived_sec13f"

MIN_MANAGER_TRAIN_ADDITIONS = 5
MIN_MANAGER_MEDIAN_SPY_EXCESS = 0.0
MIN_SKILLED_NEW_CONVICTION_MANAGERS = 1

NEW_EVIDENCE_AXIS = (
    "New gate shape: chronological manager-level alpha attribution. Manager "
    "quality is selected only from a prior disclosed-addition cohort and "
    "realized SPY-excess returns known by the current 13F availability date, "
    "then applied to the next quarter's new-conviction candidates."
)

PREDICTION = {
    "success_probability": 0.12,
    "expected_ev_delta": 0.10,
    "expected_pnl_delta": 1500.0,
    "main_failure_modes": [
        "quarterly_disclosure_staleness",
        "manager_skill_nonpersistent",
        "sample_starvation",
        "window_regression",
        "accepted_comparator_not_beaten",
    ],
    "confidence_reason": (
        "The exact prior 13F closeouts requested independent manager alpha "
        "attribution, and local raw manager-level zips support a strict "
        "chronological test. Quarterly disclosure delay keeps confidence low."
    ),
    "recorded_at": "2026-07-11T16:11:14+00:00",
}

PRODUCTION_IMPACT = {
    **prior.PRODUCTION_IMPACT,
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "private_replay_scout_no_live_adapter",
    "implementation_mode": "private_replay_scout",
    "private_replay_scout_escape_reason": (
        "Manager-skill persistence and coverage are unproven. A positive "
        "result is lead-only until one shared helper computes identical PIT "
        "manager attribution in historical replay and daily default-off state."
    ),
    "live_realism_evaluated": False,
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool: SEC 13F managers whose prior disclosed additions "
        "earned positive median SPY-excess returns may carry persistent skill; "
        "admit only unchanged new-conviction leadership candidates backed by "
        "at least one chronologically prequalified manager."
    ),
    "2_history_check": {
        "exp-20260621-019": (
            "Rejected static new-manager portfolio-weight conviction; requested "
            "materially richer manager identity or quality."
        ),
        "exp-20260622-007": (
            "Rejected same-manager co-accumulation peer graph; explicitly "
            "requested manager-level alpha attribution."
        ),
        "exp-20260622-018": (
            "Rejected active-manager concentration attribution; explicitly "
            "requested independent manager quality or manager alpha attribution."
        ),
        "difference": NEW_EVIDENCE_AXIS,
    },
    "3_single_causal_variable": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical windows. Aggregate EV/PnL must "
        "improve with no regressing window, >=20 trades across all 3 windows, "
        "survival >=5%, drawdown drift <=0.5pp, concentration passing, and the "
        "accepted allocator comparator respected. Positive remains lead-only."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260711_019_sec13f_chronological_manager_skill.py"
    ),
}

_prior_load_13f_history = prior._load_13f_history
_prior_candidate_for_ticker = prior._candidate_for_ticker
_prior_candidate_sort_key = prior._candidate_sort_key
_prior_build_payload = prior._build_payload
_prior_build_card = prior._build_card
_prior_build_log_record = prior._build_log_record


def _price_return(frame: pd.DataFrame | None, start: str, end: str) -> float | None:
    if frame is None or frame.empty:
        return None
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    closes = frame.loc[(frame.index >= start_ts) & (frame.index <= end_ts), "Close"]
    if len(closes) < 2:
        return None
    first = float(closes.iloc[0])
    last = float(closes.iloc[-1])
    if first <= 0:
        return None
    return last / first - 1.0


def _manager_skill_scores(
    *,
    training_latest: dict[str, Any],
    training_prior: dict[str, Any],
    frames: dict[str, pd.DataFrame],
    scoring_end: str,
) -> tuple[dict[str, float], dict[str, Any]]:
    start = str(training_latest["known_after"])
    spy_return = _price_return(frames.get("SPY"), start, scoring_end)
    if spy_return is None:
        return {}, {
            "status": "missing_spy_training_return",
            "training_start": start,
            "training_end": scoring_end,
        }

    manager_excess: dict[str, list[float]] = defaultdict(list)
    prior_holdings = training_prior.get("holdings_by_ticker") or {}
    for ticker, latest_row in (training_latest.get("holdings_by_ticker") or {}).items():
        ticker_return = _price_return(frames.get(ticker), start, scoring_end)
        if ticker_return is None:
            continue
        prior_values = dict((prior_holdings.get(ticker) or {}).get("manager_values_usd") or {})
        latest_values = dict(latest_row.get("manager_values_usd") or {})
        for manager, latest_value in latest_values.items():
            if float(latest_value or 0.0) <= float(prior_values.get(manager) or 0.0):
                continue
            manager_excess[str(manager)].append(ticker_return - spy_return)

    scores: dict[str, float] = {}
    for manager, values in manager_excess.items():
        if len(values) < MIN_MANAGER_TRAIN_ADDITIONS:
            continue
        median_excess = float(statistics.median(values))
        if median_excess > MIN_MANAGER_MEDIAN_SPY_EXCESS:
            scores[manager] = round(median_excess, 8)
    return scores, {
        "status": "ok",
        "training_start": start,
        "training_end": scoring_end,
        "spy_return": round(spy_return, 8),
        "managers_with_any_addition_return": len(manager_excess),
        "qualified_manager_count": len(scores),
        "min_training_additions": MIN_MANAGER_TRAIN_ADDITIONS,
        "min_median_spy_excess": MIN_MANAGER_MEDIAN_SPY_EXCESS,
    }


def _load_13f_history(universe: set[str]) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    by_label, summary = _prior_load_13f_history(universe)
    ordered = sorted(by_label.values(), key=lambda row: (row["known_after"], row["window_end"]))
    frames = load_warehouse_ohlcv_frames(
        DEFAULT_WAREHOUSE_PATH,
        set(universe) | {"SPY"},
        "2024-06-01",
        "2026-04-21",
    )
    skill_windows: list[dict[str, Any]] = []
    for idx, current in enumerate(ordered):
        if idx < 2:
            current["skilled_manager_scores"] = {}
            current["manager_skill_training"] = {"status": "insufficient_prior_windows"}
        else:
            scores, audit = _manager_skill_scores(
                training_latest=ordered[idx - 1],
                training_prior=ordered[idx - 2],
                frames=frames,
                scoring_end=str(current["known_after"]),
            )
            current["skilled_manager_scores"] = scores
            current["manager_skill_training"] = audit
        skill_windows.append(
            {
                "window_label": current["window_label"],
                "known_after": current["known_after"],
                **current["manager_skill_training"],
            }
        )
    summary.update(
        {
            "chronological_manager_skill_rule_version": RULE_VERSION,
            "manager_skill_windows": skill_windows,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
        }
    )
    return by_label, summary


def _candidate_for_ticker(**kwargs: Any) -> dict[str, Any] | None:
    if str(kwargs["signal_date"]) < str(kwargs["latest_13f"]["known_after"]):
        return None
    row = _prior_candidate_for_ticker(**kwargs)
    if row is None:
        return None
    ticker = str(kwargs["ticker"])
    latest = kwargs["latest_13f"]["holdings_by_ticker"].get(ticker) or {}
    previous = kwargs["prior_13f"]["holdings_by_ticker"].get(ticker) or {}
    skilled_scores = dict(kwargs["latest_13f"].get("skilled_manager_scores") or {})
    latest_values = dict(latest.get("manager_values_usd") or {})
    prior_values = dict(previous.get("manager_values_usd") or {})
    conviction = dict(latest.get("conviction_manager_values_usd") or {})
    skilled_new = sorted(
        manager
        for manager in (set(latest_values) - set(prior_values))
        if manager in conviction and manager in skilled_scores
    )
    if len(skilled_new) < MIN_SKILLED_NEW_CONVICTION_MANAGERS:
        return None
    score_values = [float(skilled_scores[manager]) for manager in skilled_new]
    row.update(
        {
            "source": "SEC13F_CHRONOLOGICAL_MANAGER_SKILL_LIQUID_LEADERSHIP_PAPER",
            "rule_version": RULE_VERSION,
            "sec13f_skilled_new_conviction_manager_count": len(skilled_new),
            "sec13f_skilled_manager_median_prior_spy_excess": round(
                float(statistics.median(score_values)), 8
            ),
            "sec13f_skilled_manager_max_prior_spy_excess": round(max(score_values), 8),
            "sec13f_manager_skill_training_end": kwargs["latest_13f"]["known_after"],
            "sec13f_manager_skill_min_training_additions": MIN_MANAGER_TRAIN_ADDITIONS,
        }
    )
    return row


def _candidate_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return _prior_candidate_sort_key(row)


def _build_payload() -> dict[str, Any]:
    payload = _prior_build_payload()
    passed = bool(payload.get("gate4", {}).get("passed"))
    decision = (
        "positive_replay_lead_not_promoted_sec13f_chronological_manager_skill"
        if passed
        else "rejected_sec13f_chronological_manager_skill_candidate_pool"
    )
    aggregate = payload["delta_metrics"]["aggregate"]
    why = (
        "Chronologically trained manager quality retained a robust replay lead, "
        "but no shared daily helper or forward replacement ledger exists."
        if passed
        else (
            "Prior-quarter manager alpha did not persist strongly enough after "
            "the 13F disclosure delay and unchanged next-open execution rules."
        )
    )
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "positive_replay_lead_not_promoted" if passed else "rejected",
            "decision": decision,
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_sec_13f_candidate_pool",
            "nearby_prior_experiments": [
                "exp-20260621-019",
                "exp-20260622-007",
                "exp-20260622-018",
            ],
            "prior_trial_count": 11,
            "multiple_testing_risk_bucket": "high",
            "new_evidence_type": "chronological_manager_level_alpha_attribution",
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "gate_questions": PRE_RUN_QUESTIONS,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "production_impact": PRODUCTION_IMPACT,
            "interpretation": why,
            "rejection_reason": None if passed else "; ".join(payload["gate4"]["failed_reasons"]),
            "next_evidence_needed": (
                "This candidate-pool/source cell reaches 12 dry trials and is "
                "parked. Reopen only with non-quarterly manager flow, a genuinely "
                "new manager-quality source, or materially settled forward rows; "
                "do not retune training length, skill cutoff, conviction, price, "
                "top-N, hold, cooldown, notional, or response shape."
            ),
            "post_run_reflection": {
                "why_result_happened": why,
                "forbidden_near_neighbor_retry": (
                    "Do not retry 13F manager skill by changing training sample "
                    "count, median cutoff, return horizon, manager buckets, "
                    "conviction thresholds, leadership gates, top-N, hold, "
                    "cooldown, notional, or response shape."
                ),
                "new_evidence_required": (
                    "Non-quarterly manager flow, a genuinely new manager-quality "
                    "source, or materially settled forward replacement rows."
                ),
            },
        }
    )
    payload["gate4"]["decision"] = decision
    payload["prediction"] = {
        **PREDICTION,
        "actual_success": 1 if passed else 0,
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
        "brier_score": round((PREDICTION["success_probability"] - float(passed)) ** 2, 6),
    }
    payload["calibration"].update(
        {
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": payload["prediction"]["brier_score"],
        }
    )
    payload["backtest_protocol"]["source"] = (
        "docs/backtesting.md canonical three-window core replay plus "
        "experiment-local chronological SEC 13F manager-skill paper overlay"
    )
    payload["backtest_protocol"]["sec13f_provenance"] = (
        "Local SEC structured Form 13F filing-window source-cache zip files. "
        "For each current window, manager quality uses only additions from the "
        "previous two disclosed windows and ticker/SPY returns ending at the "
        "current window's known_after date. The resulting manager set is then "
        "applied to new-conviction candidates after that date."
    )
    payload["parameters"].update(
        {
            "min_manager_train_additions": MIN_MANAGER_TRAIN_ADDITIONS,
            "min_manager_median_spy_excess": MIN_MANAGER_MEDIAN_SPY_EXCESS,
            "min_skilled_new_conviction_managers": MIN_SKILLED_NEW_CONVICTION_MANAGERS,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["related_files"] = [
        prior._repo_rel(Path(__file__)),
        prior._repo_rel(OUT_JSON),
        prior._repo_rel(LOG_JSON),
        prior._repo_rel(TICKET_JSON),
        prior._repo_rel(CARD_MD),
        prior._repo_rel(MANIFEST_JSON),
        prior._repo_rel(prior.base.EXPERIMENT_LOG),
        prior._repo_rel(prior.base.REGISTRY_JSON),
    ]
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    return _prior_build_card(payload).replace(
        f"# {EXPERIMENT_ID} SEC 13F Manager Conviction",
        f"# {EXPERIMENT_ID} SEC 13F Chronological Manager Skill",
    )


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = _prior_build_log_record(payload)
    record.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "change_type": "experiment_local_replay_candidate_pool",
            "implementation_mode": "private_replay_scout",
            "causal_components": [
                "prior-quarter manager addition attribution",
                "chronological manager-skill admission",
                "unchanged manager-conviction leadership selector",
                "top1 next-open 10d costed paper execution",
            ],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "negative_reflection": None
            if payload["gate4"]["passed"]
            else payload["post_run_reflection"]["why_result_happened"],
            "anti_js": "No JavaScript was used.",
        }
    )
    return record


def _configure_prior() -> None:
    prior.__file__ = __file__
    prior.EXPERIMENT_ID = EXPERIMENT_ID
    prior.STEM = STEM
    prior.TRIAL_FAMILY = TRIAL_FAMILY
    prior.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    prior.CHANGED_VARIABLE = CHANGED_VARIABLE
    prior.RULE_VERSION = RULE_VERSION
    prior.OWNER = OWNER
    prior.OUT_DIR = OUT_DIR
    prior.OUT_JSON = OUT_JSON
    prior.LOG_JSON = LOG_JSON
    prior.TICKET_JSON = TICKET_JSON
    prior.CARD_MD = CARD_MD
    prior.MANIFEST_JSON = MANIFEST_JSON
    prior.DERIVED_CACHE_DIR = DERIVED_CACHE_DIR
    prior.PREDICTION = PREDICTION
    prior.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    prior.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    prior._load_13f_history = _load_13f_history
    prior._candidate_for_ticker = _candidate_for_ticker
    prior._candidate_sort_key = _candidate_sort_key
    prior._build_payload = _build_payload
    prior._build_card = _build_card
    prior._build_log_record = _build_log_record
    prior._configure_base()


def main() -> None:
    _configure_prior()
    prior.base.main()


if __name__ == "__main__":
    main()
