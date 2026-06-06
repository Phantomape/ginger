"""exp-20260606-013: broad Companyfacts low EPS dilution + RS.

Replay-only alpha search. This tests whether SEC Companyfacts candidates with
positive realized growth and low/non-worsening diluted-vs-basic EPS erosion
create a cleaner broad default-off paper candidate pool than static growth
alone.

No production adapter, shared policy, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

import exp_20260605_011_broad_companyfacts_dual_growth_rs_candidate_pool as base


_BASE_GATE4 = base._gate4
_BASE_EXPERIMENT_LOG_RECORD = base._experiment_log_record

EXP_ID = "exp-20260606-013"
STEM = "broad_companyfacts_low_eps_dilution_rs"
TRIAL_FAMILY = "broad_companyfacts_eps_dilution_candidate_pool"
TRIAL_VARIANT_ID = "low_eps_dilution_rs_top1_v1"
CHANGED_VARIABLE = "broad_companyfacts_low_eps_dilution_rs_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

MIN_REVENUE_YOY_GROWTH = 0.10
MIN_DILUTED_EPS_YOY_GROWTH = 0.10
MIN_CURRENT_DILUTED_BASIC_RATIO = 0.98
MAX_CURRENT_DILUTED_BASIC_RATIO = 1.05
MIN_DILUTION_RATIO_DELTA = -0.01
MIN_RET20_EXCESS_SPY = 0.02
MIN_VOLUME_RATIO_20D = 1.00

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"exp_20260606_013_{STEM}.json"
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
        "adapter, daily production exposure of the same filed-date-safe "
        "basic/diluted EPS fields, warehouse/snapshot replay parity, and "
        "focused tests before any report queue, paper ledger, candidate "
        "priority, watchlist, sizing, or order surface could change."
    ),
}


def _same_eps_period(basic: dict[str, Any], diluted: dict[str, Any]) -> bool:
    basic_period = basic.get("current_period_end")
    diluted_period = diluted.get("current_period_end")
    if basic_period and diluted_period:
        return str(basic_period) == str(diluted_period)
    return str(basic.get("asof_date") or "") == str(diluted.get("asof_date") or "")


def _eps_dilution_row(
    growth_index: dict[str, dict[str, list[dict[str, Any]]]],
    ticker: str,
    signal_day: str,
) -> dict[str, Any] | None:
    basic = base._latest_growth_row(growth_index, ticker, "eps_basic", signal_day)
    diluted = base._latest_growth_row(growth_index, ticker, "eps_diluted", signal_day)
    if basic is None or diluted is None:
        return None
    if not _same_eps_period(basic, diluted):
        return None

    try:
        basic_current = float(basic["current_value"])
        basic_prior = float(basic["prior_value"])
        basic_growth = float(basic["yoy_growth"])
        diluted_current = float(diluted["current_value"])
        diluted_prior = float(diluted["prior_value"])
        diluted_growth = float(diluted["yoy_growth"])
    except (TypeError, ValueError):
        return None

    if min(basic_current, basic_prior, diluted_current, diluted_prior) <= 0.0:
        return None

    current_ratio = diluted_current / basic_current
    prior_ratio = diluted_prior / basic_prior
    ratio_delta = current_ratio - prior_ratio
    if current_ratio < MIN_CURRENT_DILUTED_BASIC_RATIO:
        return None
    if current_ratio > MAX_CURRENT_DILUTED_BASIC_RATIO:
        return None
    if ratio_delta < MIN_DILUTION_RATIO_DELTA:
        return None
    if diluted_growth < MIN_DILUTED_EPS_YOY_GROWTH:
        return None

    return {
        "basic": basic,
        "diluted": diluted,
        "basic_yoy_growth": basic_growth,
        "diluted_yoy_growth": diluted_growth,
        "current_diluted_basic_ratio": current_ratio,
        "prior_diluted_basic_ratio": prior_ratio,
        "diluted_basic_ratio_delta": ratio_delta,
    }


def _score_candidate(
    *,
    revenue_growth: float,
    diluted_eps_growth: float,
    current_diluted_basic_ratio: float,
    diluted_basic_ratio_delta: float,
    ret20_excess_spy: float,
    close_location: float,
    volume_ratio_20d: float,
) -> float:
    return (
        min(max(revenue_growth, -1.0), 1.5)
        + min(max(diluted_eps_growth, -1.0), 1.5)
        + 4.0 * ret20_excess_spy
        + close_location
        + 0.15 * min(volume_ratio_20d, 3.0)
        + 0.50 * min(max(current_diluted_basic_ratio - 0.95, 0.0), 0.10)
        + 0.20 * min(max(diluted_basic_ratio_delta, 0.0), 0.10)
    )


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
    eps_discipline = _eps_dilution_row(growth_index, ticker, signal_day_s)
    if revenue is None or eps_discipline is None:
        return None

    revenue_growth = float(revenue["yoy_growth"])
    if revenue_growth < MIN_REVENUE_YOY_GROWTH:
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
    if volume_ratio_20d is None or volume_ratio_20d < MIN_VOLUME_RATIO_20D:
        return None
    close_location = base._close_location(frame, pos)
    if close_location is None or close_location < base.MIN_CLOSE_LOCATION:
        return None
    ret20 = base._ret(frame, pos, 20)
    spy_ret20 = base._ret(spy_frame, spy_pos, 20)
    if ret20 is None or spy_ret20 is None:
        return None
    ret20_excess_spy = ret20 - spy_ret20
    if ret20_excess_spy < MIN_RET20_EXCESS_SPY:
        return None

    diluted_eps_growth = float(eps_discipline["diluted_yoy_growth"])
    current_ratio = float(eps_discipline["current_diluted_basic_ratio"])
    ratio_delta = float(eps_discipline["diluted_basic_ratio_delta"])
    score = _score_candidate(
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
        "source": "BROAD_COMPANYFACTS_LOW_EPS_DILUTION_RS_PAPER",
    }
    return base._candidate_trade(ticker, frame, signal_day, pos, metadata)


def _gate4(
    aggregate_comparison: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    gate = _BASE_GATE4(aggregate_comparison, results, target_summary)
    gate["decision"] = (
        "positive_replay_lead_not_promoted_requires_eps_dilution_shared_adapter"
        if gate["passed"]
        else "rejected_broad_companyfacts_low_eps_dilution_rs_candidate_pool"
    )
    return gate


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = _BASE_EXPERIMENT_LOG_RECORD(payload)
    record.update(
        {
            "experiment_id": EXP_ID,
            "hypothesis": (
                "Broad Companyfacts dual-growth candidates with low and "
                "non-worsening EPS dilution may identify cleaner default-off "
                "paper entries than static growth alone."
            ),
            "change_summary": (
                "Tested SEC Companyfacts low diluted-vs-basic EPS erosion plus "
                "revenue/EPS growth and OHLCV relative strength as a replay-only "
                "default-off broad candidate source."
            ),
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "nearby_prior_experiments": [
                "exp-20260605-011",
                "exp-20260605-026",
                "exp-20260606-009",
            ],
            "multiple_testing_risk_bucket": "minimal",
            "new_evidence_type": "new_production_visible_field",
            "component": base._repo_rel(Path(__file__)),
            "production_impact": PRODUCTION_IMPACT,
            "decision": payload["gate4"]["decision"],
            "rejection_reason": ";".join(payload["gate4"]["failed_reasons"])
            if payload["gate4"]["failed_reasons"]
            else None,
            "next_retry_requires": [
                "closed forward replacement-value rows",
                "proof that low EPS dilution is incremental to static Companyfacts growth and ret20 momentum",
                "shared default-off adapter and parity tests before promotion",
                "avoid nearby Companyfacts EPS-dilution threshold/scalar retunes on this frozen sample",
            ],
        }
    )
    return record


def _patch_base() -> None:
    base.EXP_ID = EXP_ID
    base.STEM = STEM
    base.TRIAL_FAMILY = TRIAL_FAMILY
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
    base.MIN_REVENUE_YOY_GROWTH = MIN_REVENUE_YOY_GROWTH
    base.MIN_PROFIT_YOY_GROWTH = MIN_DILUTED_EPS_YOY_GROWTH
    base.MIN_RET20_EXCESS_SPY = MIN_RET20_EXCESS_SPY
    base.MIN_VOLUME_RATIO_20D = MIN_VOLUME_RATIO_20D
    base._candidate_for_ticker_day = _candidate_for_ticker_day
    base._score_candidate = _score_candidate
    base._gate4 = _gate4
    base._experiment_log_record = _experiment_log_record


def main() -> None:
    _patch_base()
    payload = base.build_payload()
    payload["preflight"] = {
        "alpha_hypothesis": (
            "Broad Companyfacts dual-growth candidates with low and non-worsening "
            "EPS dilution may identify cleaner default-off paper entries than "
            "static growth alone."
        ),
        "category": "entry_candidate_pool",
        "nearby_prior_experiments": [
            "exp-20260605-011",
            "exp-20260605-026",
            "exp-20260606-009",
        ],
        "history_check": (
            "Recent broad Companyfacts dual-growth, profitability inflection, "
            "and growth acceleration sources failed Gate 4. No prior broad "
            "Companyfacts experiment was found that isolates the basic-vs-diluted "
            "EPS erosion field."
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
            "min_revenue_yoy_growth": MIN_REVENUE_YOY_GROWTH,
            "min_diluted_eps_yoy_growth": MIN_DILUTED_EPS_YOY_GROWTH,
            "min_current_diluted_basic_ratio": MIN_CURRENT_DILUTED_BASIC_RATIO,
            "max_current_diluted_basic_ratio": MAX_CURRENT_DILUTED_BASIC_RATIO,
            "min_dilution_ratio_delta": MIN_DILUTION_RATIO_DELTA,
            "daily_selection": "top_1_by_fixed_low_eps_dilution_rs_score",
            "eps_pair_period_match_required": True,
        }
    )
    payload["next_retry_requires"] = [
        "closed forward replacement-value rows",
        "proof that low EPS dilution is incremental to static Companyfacts growth and ret20 momentum",
        "shared default-off adapter and parity tests before promotion",
        "avoid nearby Companyfacts EPS-dilution threshold/scalar retunes on this frozen sample",
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
        f"# {EXP_ID} Broad Companyfacts Low EPS Dilution RS Candidate Pool",
    )
    artifact_text = artifact_text.replace(
        (
            ".\\.venv\\Scripts\\python.exe -B "
            "quant\\experiments\\exp_20260605_011_broad_companyfacts_dual_growth_rs_candidate_pool.py"
        ),
        (
            ".\\.venv\\Scripts\\python.exe -B "
            "quant\\experiments\\exp_20260606_013_broad_companyfacts_low_eps_dilution_rs.py"
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
