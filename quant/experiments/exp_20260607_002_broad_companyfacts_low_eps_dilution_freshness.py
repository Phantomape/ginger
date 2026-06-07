"""exp-20260607-002: broad Companyfacts low EPS dilution + freshness.

Replay-only alpha search. This tests one production-visible Companyfacts field
on top of exp-20260606-013: low EPS-dilution broad candidates are admitted only
when the filed-date-safe revenue, basic EPS, and diluted EPS rows are fresh and
come from a close as-of cycle.

No production adapter, shared policy, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

import exp_20260606_013_broad_companyfacts_low_eps_dilution_rs as previous


base = previous.base

EXP_ID = "exp-20260607-002"
STEM = "broad_companyfacts_low_eps_dilution_freshness"
TRIAL_FAMILY = "broad_companyfacts_eps_dilution_freshness_candidate_pool"
TRIAL_VARIANT_ID = "low_eps_dilution_fresh_companyfacts_top1_v1"
CHANGED_VARIABLE = "broad_companyfacts_low_eps_dilution_freshness_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

MAX_FUNDAMENTAL_AGE_DAYS_FRESH = 120
MAX_REVENUE_EPS_ASOF_GAP_DAYS = 45

REPO_ROOT = previous.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"exp_20260607_002_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXP_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "parity_note": (
        "This runner changes no production code. A positive result would "
        "require a separate shared default-off Companyfacts EPS-dilution "
        "freshness adapter, daily production exposure of the same filed-date-safe "
        "revenue/basic EPS/diluted EPS freshness fields, warehouse/snapshot "
        "replay parity, and focused tests before any report queue, paper ledger, "
        "candidate priority, watchlist, sizing, or order surface could change."
    ),
}


def _age(row: dict[str, Any], key: str = "asof_age_days") -> int | None:
    try:
        return int(row[key])
    except (KeyError, TypeError, ValueError):
        return None


def _date_gap_days(left: str | None, right: str | None) -> int | None:
    if not left or not right:
        return None
    try:
        return abs((pd.Timestamp(left) - pd.Timestamp(right)).days)
    except (TypeError, ValueError):
        return None


def _fresh_companyfacts_rows(
    *,
    revenue: dict[str, Any],
    eps_discipline: dict[str, Any],
) -> dict[str, Any] | None:
    basic = eps_discipline["basic"]
    diluted = eps_discipline["diluted"]
    ages = {
        "revenue": _age(revenue),
        "basic_eps": _age(basic),
        "diluted_eps": _age(diluted),
    }
    if any(value is None for value in ages.values()):
        return None
    if any(value > MAX_FUNDAMENTAL_AGE_DAYS_FRESH for value in ages.values() if value is not None):
        return None

    revenue_asof = str(revenue.get("asof_date") or "")
    basic_asof = str(basic.get("asof_date") or "")
    diluted_asof = str(diluted.get("asof_date") or "")
    gaps = [
        _date_gap_days(revenue_asof, basic_asof),
        _date_gap_days(revenue_asof, diluted_asof),
        _date_gap_days(basic_asof, diluted_asof),
    ]
    if any(value is None for value in gaps):
        return None
    if any(value > MAX_REVENUE_EPS_ASOF_GAP_DAYS for value in gaps if value is not None):
        return None

    return {
        "companyfacts_freshness_rule_version": RULE_VERSION,
        "companyfacts_freshness_max_age_days": MAX_FUNDAMENTAL_AGE_DAYS_FRESH,
        "companyfacts_revenue_eps_max_asof_gap_days": MAX_REVENUE_EPS_ASOF_GAP_DAYS,
        "companyfacts_revenue_basic_eps_asof_gap_days": gaps[0],
        "companyfacts_revenue_diluted_eps_asof_gap_days": gaps[1],
        "companyfacts_basic_diluted_eps_asof_gap_days": gaps[2],
        "companyfacts_max_observed_age_days": max(value for value in ages.values() if value is not None),
        "companyfacts_freshness_passed": True,
    }


def _candidate_for_ticker_day(
    *,
    ticker: str,
    frame: pd.DataFrame,
    spy_frame: pd.DataFrame,
    signal_day: pd.Timestamp,
    growth_index: dict[str, dict[str, list[dict[str, Any]]]],
) -> dict[str, Any] | None:
    pos = base._frame_pos(frame, signal_day)
    spy_pos = base._frame_pos(spy_frame, signal_day)
    if pos is None or spy_pos is None or pos < 20 or spy_pos < 20:
        return None

    signal_day_s = str(signal_day.date())
    revenue = base._latest_growth_row(growth_index, ticker, "revenue", signal_day_s)
    eps_discipline = previous._eps_dilution_row(growth_index, ticker, signal_day_s)
    if revenue is None or eps_discipline is None:
        return None
    freshness = _fresh_companyfacts_rows(revenue=revenue, eps_discipline=eps_discipline)
    if freshness is None:
        return None

    revenue_growth = float(revenue["yoy_growth"])
    if revenue_growth < previous.MIN_REVENUE_YOY_GROWTH:
        return None
    if revenue.get("current_value") is None or float(revenue["current_value"]) <= 0.0:
        return None

    close = float(frame["Close"].iloc[pos])
    if close < base.MIN_PRICE:
        return None
    adv20 = base._avg_dollar_volume(frame, pos)
    if adv20 is None or adv20 < base.MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    volume_ratio_20d = base._volume_ratio(frame, pos)
    if volume_ratio_20d is None or volume_ratio_20d < previous.MIN_VOLUME_RATIO_20D:
        return None
    close_location = base._close_location(frame, pos)
    if close_location is None or close_location < base.MIN_CLOSE_LOCATION:
        return None
    ret20 = base._ret(frame, pos, 20)
    spy_ret20 = base._ret(spy_frame, spy_pos, 20)
    if ret20 is None or spy_ret20 is None:
        return None
    ret20_excess_spy = ret20 - spy_ret20
    if ret20_excess_spy < previous.MIN_RET20_EXCESS_SPY:
        return None

    diluted_eps_growth = float(eps_discipline["diluted_yoy_growth"])
    current_ratio = float(eps_discipline["current_diluted_basic_ratio"])
    ratio_delta = float(eps_discipline["diluted_basic_ratio_delta"])
    score = previous._score_candidate(
        revenue_growth=revenue_growth,
        diluted_eps_growth=diluted_eps_growth,
        current_diluted_basic_ratio=current_ratio,
        diluted_basic_ratio_delta=ratio_delta,
        ret20_excess_spy=ret20_excess_spy,
        close_location=close_location,
        volume_ratio_20d=volume_ratio_20d,
    )

    metadata = {
        "companyfacts_revenue_yoy_growth": round(revenue_growth, 6),
        "companyfacts_diluted_eps_yoy_growth": round(diluted_eps_growth, 6),
        "companyfacts_basic_eps_yoy_growth": round(float(eps_discipline["basic_yoy_growth"]), 6),
        "companyfacts_current_diluted_basic_ratio": round(current_ratio, 6),
        "companyfacts_prior_diluted_basic_ratio": round(
            float(eps_discipline["prior_diluted_basic_ratio"]), 6
        ),
        "companyfacts_diluted_basic_ratio_delta": round(ratio_delta, 6),
        "companyfacts_revenue_asof_date": revenue["asof_date"],
        "companyfacts_basic_eps_asof_date": eps_discipline["basic"]["asof_date"],
        "companyfacts_diluted_eps_asof_date": eps_discipline["diluted"]["asof_date"],
        "companyfacts_revenue_asof_age_days": revenue["asof_age_days"],
        "companyfacts_basic_eps_asof_age_days": eps_discipline["basic"]["asof_age_days"],
        "companyfacts_diluted_eps_asof_age_days": eps_discipline["diluted"]["asof_age_days"],
        "companyfacts_eps_period_end": eps_discipline["diluted"].get("current_period_end"),
        "companyfacts_revenue_form": revenue.get("current_form"),
        "companyfacts_diluted_eps_form": eps_discipline["diluted"].get("current_form"),
        "ret20": round(ret20, 6),
        "spy_ret20": round(spy_ret20, 6),
        "ret20_excess_spy": round(ret20_excess_spy, 6),
        "close_location": round(close_location, 6),
        "avg_dollar_volume_20d": round(adv20, 2),
        "volume_ratio_20d": round(volume_ratio_20d, 6),
        "candidate_score": round(score, 6),
        "source": "BROAD_COMPANYFACTS_LOW_EPS_DILUTION_FRESHNESS_PAPER",
        **freshness,
    }
    return base._candidate_trade(ticker, frame, signal_day, pos, metadata)


def _gate4(
    aggregate_comparison: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    gate = previous._BASE_GATE4(aggregate_comparison, results, target_summary)
    gate["decision"] = (
        "positive_replay_lead_not_promoted_requires_eps_dilution_freshness_adapter"
        if gate["passed"]
        else "rejected_broad_companyfacts_low_eps_dilution_freshness_candidate_pool"
    )
    return gate


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = previous._BASE_EXPERIMENT_LOG_RECORD(payload)
    record.update(
        {
            "experiment_id": EXP_ID,
            "hypothesis": (
                "Broad Companyfacts low EPS-dilution candidates may become robust "
                "when revenue, basic EPS, and diluted EPS rows are fresh and from "
                "a close filed-date-safe as-of cycle."
            ),
            "change_summary": (
                "Tested SEC Companyfacts low EPS-dilution plus fundamental "
                "freshness/timeliness as a replay-only broad default-off paper "
                "candidate source."
            ),
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "nearby_prior_experiments": [
                "exp-20260605-011",
                "exp-20260606-009",
                "exp-20260606-013",
                "exp-20260601-027",
            ],
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "new_production_visible_filing_freshness_field",
            "component": base._repo_rel(Path(__file__)),
            "production_impact": PRODUCTION_IMPACT,
            "decision": payload["gate4"]["decision"],
            "rejection_reason": ";".join(payload["gate4"]["failed_reasons"])
            if payload["gate4"]["failed_reasons"]
            else None,
            "next_retry_requires": [
                "closed forward replacement-value rows",
                "proof that Companyfacts freshness is incremental to EPS-dilution and ret20 momentum",
                "shared default-off adapter and parity tests before promotion",
                "avoid nearby Companyfacts freshness or EPS-dilution threshold retunes on this frozen sample",
            ],
        }
    )
    return record


def _patch_modules() -> None:
    previous.EXP_ID = EXP_ID
    previous.STEM = STEM
    previous.TRIAL_FAMILY = TRIAL_FAMILY
    previous.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    previous.CHANGED_VARIABLE = CHANGED_VARIABLE
    previous.RULE_VERSION = RULE_VERSION
    previous.OUT_DIR = OUT_DIR
    previous.OUT_JSON = OUT_JSON
    previous.BEFORE_JSON = BEFORE_JSON
    previous.AFTER_JSON = AFTER_JSON
    previous.LOG_JSON = LOG_JSON
    previous.TICKET_JSON = TICKET_JSON
    previous.CARD_MD = CARD_MD
    previous.ARTIFACT_MD = ARTIFACT_MD
    previous.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    previous._candidate_for_ticker_day = _candidate_for_ticker_day
    previous._gate4 = _gate4
    previous._experiment_log_record = _experiment_log_record

    base.EXP_ID = EXP_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
    base.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    base.CHANGED_VARIABLE = CHANGED_VARIABLE
    base.RULE_VERSION = RULE_VERSION
    base.OUT_DIR = OUT_DIR
    base.OUT_JSON = OUT_JSON
    base.BEFORE_JSON = BEFORE_JSON
    base.AFTER_JSON = AFTER_JSON
    base.LOG_JSON = LOG_JSON
    base.TICKET_JSON = TICKET_JSON
    base.CARD_MD = CARD_MD
    base.ARTIFACT_MD = ARTIFACT_MD
    base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    base._candidate_for_ticker_day = _candidate_for_ticker_day
    base._score_candidate = previous._score_candidate
    base._gate4 = _gate4
    base._experiment_log_record = _experiment_log_record


def main() -> None:
    _patch_modules()
    payload = base.build_payload()
    payload["experiment_id"] = EXP_ID
    payload["preflight"] = {
        "alpha_hypothesis": (
            "Broad Companyfacts low EPS-dilution candidates may keep their "
            "aggregate edge while reducing stale-fundamental old-window tails "
            "when revenue/basic EPS/diluted EPS rows are fresh and close in "
            "as-of date."
        ),
        "category": "entry_candidate_pool",
        "nearby_prior_experiments": [
            "exp-20260605-011",
            "exp-20260606-009",
            "exp-20260606-013",
            "exp-20260601-027",
        ],
        "history_check": (
            "exp-20260606-013 improved aggregate EV/PnL but regressed old_thin; "
            "exp-20260601-027 found Companyfacts filing timeliness useful as "
            "support. This run tests freshness as candidate-source admission, "
            "not a scalar or EPS-dilution threshold retune."
        ),
        "single_causal_variable": CHANGED_VARIABLE,
        "success_standard": (
            "Canonical three-window before/after aggregate EV and PnL must "
            "improve, no window EV/PnL regression, max drawdown drift <= "
            f"{base.MAX_DRAWDOWN_WORSE}, target trades >= {base.MIN_TARGET_TRADES}, "
            "all three windows represented, concentration within guardrails."
        ),
        "reproducible_if_failed": True,
    }
    payload["parameters"].update(
        {
            "max_fundamental_age_days_fresh": MAX_FUNDAMENTAL_AGE_DAYS_FRESH,
            "max_revenue_eps_asof_gap_days": MAX_REVENUE_EPS_ASOF_GAP_DAYS,
            "daily_selection": "top_1_by_fixed_low_eps_dilution_freshness_score",
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["production_impact"] = PRODUCTION_IMPACT
    payload["next_retry_requires"] = [
        "closed forward replacement-value rows",
        "proof that Companyfacts freshness is incremental to EPS-dilution and ret20 momentum",
        "shared default-off adapter and parity tests before promotion",
        "avoid nearby Companyfacts freshness or EPS-dilution threshold retunes on this frozen sample",
    ]
    payload["related_files"] = [
        base._repo_rel(Path(__file__)),
        base._repo_rel(OUT_JSON),
        base._repo_rel(LOG_JSON),
        base._repo_rel(ARTIFACT_MD),
        base._repo_rel(TICKET_JSON),
        base._repo_rel(base.GROWTH_PATH),
    ]

    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, _experiment_log_record(payload))
    base._write_json(BEFORE_JSON, payload["aggregate"]["before"])
    base._write_json(AFTER_JSON, payload["aggregate"]["after"])
    base._write_artifact(payload)
    artifact_text = ARTIFACT_MD.read_text(encoding="utf-8")
    artifact_text = artifact_text.replace(
        f"# {EXP_ID} Broad Companyfacts Dual-Growth RS Candidate Pool",
        f"# {EXP_ID} Broad Companyfacts Low EPS Dilution Freshness Candidate Pool",
    )
    artifact_text = artifact_text.replace(
        (
            ".\\.venv\\Scripts\\python.exe -B "
            "quant\\experiments\\exp_20260605_011_broad_companyfacts_dual_growth_rs_candidate_pool.py"
        ),
        (
            ".\\.venv\\Scripts\\python.exe -B "
            "quant\\experiments\\exp_20260607_002_broad_companyfacts_low_eps_dilution_freshness.py"
        ),
    )
    ARTIFACT_MD.write_text(artifact_text, encoding="utf-8")
    base._update_ticket(payload)
    base._update_registry(payload)
    base._append_experiment_log(_experiment_log_record(payload))
    print(
        base.json.dumps(
            {
                "experiment_id": EXP_ID,
                "decision": payload["gate4"]["decision"],
                "aggregate": payload["aggregate"]["comparison"],
                "target_summary": {
                    "target_trade_count": payload["target_summary"]["target_trade_count"],
                    "target_trade_pnl_usd": payload["target_summary"]["target_trade_pnl_usd"],
                    "max_single_positive_share": payload["target_summary"][
                        "max_single_positive_share"
                    ],
                    "positive_pnl_hhi": payload["target_summary"]["positive_pnl_hhi"],
                },
                "gate4_failed_reasons": payload["gate4"]["failed_reasons"],
                "anti_js": "No JavaScript was used.",
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
