"""exp-20260605-026: broad Companyfacts profitability inflection + RS.

This alpha search tests one distinct broad-universe, free-data candidate pool:
SEC Companyfacts rows where profitability inflects from non-positive prior-year
profit to positive current profit, confirmed by revenue growth and OHLCV
relative strength.

The runner is replay-only/default-off. It changes no production adapter,
shared policy, live/default orders, ranking, sizing, exits, LLM/news path, or
watchlist behavior. No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

import exp_20260605_011_broad_companyfacts_dual_growth_rs_candidate_pool as base


_ORIGINAL_GATE4 = base._gate4

EXP_ID = "exp-20260605-026"
STEM = "broad_companyfacts_profitability_inflection_rs"
TRIAL_FAMILY = "broad_companyfacts_profitability_inflection_candidate_pool"
CHANGED_VARIABLE = "broad_companyfacts_profitability_inflection_rs_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

MIN_REVENUE_YOY_GROWTH = 0.10
MIN_RET20_EXCESS_SPY = 0.02
MIN_VOLUME_RATIO_20D = 1.00
PROFIT_CURRENT_GT_ZERO = True
PROFIT_PRIOR_LTE_ZERO = True

OUT_DIR = base.REPO_ROOT / "data" / "experiments" / EXP_ID
OUT_JSON = OUT_DIR / f"exp_20260605_026_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = base.REPO_ROOT / "experiments" / "logs" / f"{EXP_ID}.json"
TICKET_JSON = base.REPO_ROOT / "experiments" / "tickets" / f"{EXP_ID}.json"
CARD_MD = base.REPO_ROOT / "experiments" / "cards" / f"{EXP_ID}.md"
ARTIFACT_MD = base.REPO_ROOT / "experiments" / "artifacts" / f"{EXP_ID}_{STEM}.md"

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
        "This runner changes no production code. A positive result would require "
        "a separate shared default-off Companyfacts profitability-inflection "
        "adapter, production exposure of the same PIT filed-date-safe fields, "
        "and focused parity tests before any report queue, paper ledger, "
        "candidate priority, or order surface could change."
    ),
}


def _repo_rel(path: Path | str) -> str:
    return base._repo_rel(path)


def _profitability_inflection_row(
    growth_index: dict[str, dict[str, list[dict[str, Any]]]],
    ticker: str,
    signal_day: str,
) -> dict[str, Any] | None:
    rows = []
    for canonical in ("eps_diluted", "eps_basic", "net_income"):
        row = base._latest_growth_row(growth_index, ticker, canonical, signal_day)
        if row is None:
            continue
        current = row.get("current_value")
        prior = row.get("prior_value")
        if current is None or prior is None:
            continue
        current_f = float(current)
        prior_f = float(prior)
        if current_f > 0.0 and prior_f <= 0.0:
            priority = {"eps_diluted": 3, "eps_basic": 2, "net_income": 1}[canonical]
            if canonical.startswith("eps"):
                scale = max(abs(prior_f), 0.01)
            else:
                scale = max(abs(prior_f), 1_000_000.0)
            rows.append(
                {
                    **row,
                    "inflection_strength": min(2.0, abs(current_f) / scale),
                    "canonical_priority": priority,
                }
            )
    if not rows:
        return None
    return max(
        rows,
        key=lambda row: (
            int(row["canonical_priority"]),
            str(row["asof_date"]),
            float(row["inflection_strength"]),
        ),
    )


def _score_candidate(
    *,
    revenue_growth: float,
    inflection_strength: float,
    ret20_excess_spy: float,
    close_location: float,
    volume_ratio_20d: float,
) -> float:
    return (
        min(max(revenue_growth, -0.5), 1.5)
        + 0.25 * min(max(inflection_strength, 0.0), 2.0)
        + 4.0 * ret20_excess_spy
        + close_location
        + 0.15 * min(volume_ratio_20d, 3.0)
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
    profit = _profitability_inflection_row(growth_index, ticker, signal_day_s)
    if revenue is None or profit is None:
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

    current_profit = float(profit["current_value"])
    prior_profit = float(profit["prior_value"])
    inflection_strength = float(profit["inflection_strength"])
    score = _score_candidate(
        revenue_growth=revenue_growth,
        inflection_strength=inflection_strength,
        ret20_excess_spy=ret20_excess_spy,
        close_location=close_location,
        volume_ratio_20d=volume_ratio_20d,
    )
    metadata = {
        "companyfacts_revenue_yoy_growth": round(revenue_growth, 6),
        "companyfacts_profit_inflection": True,
        "companyfacts_profit_current_value": round(current_profit, 6),
        "companyfacts_profit_prior_value": round(prior_profit, 6),
        "companyfacts_profit_inflection_strength": round(inflection_strength, 6),
        "companyfacts_profit_canonical": profit["canonical"],
        "companyfacts_revenue_asof_date": revenue["asof_date"],
        "companyfacts_profit_asof_date": profit["asof_date"],
        "companyfacts_revenue_asof_age_days": revenue["asof_age_days"],
        "companyfacts_profit_asof_age_days": profit["asof_age_days"],
        "companyfacts_revenue_form": revenue.get("current_form"),
        "companyfacts_profit_form": profit.get("current_form"),
        "ret20": round(ret20, 6),
        "spy_ret20": round(spy_ret20, 6),
        "ret20_excess_spy": round(ret20_excess_spy, 6),
        "close_location": round(close_location, 6),
        "avg_dollar_volume_20d": round(adv20, 2),
        "volume_ratio_20d": round(volume_ratio_20d, 6),
        "candidate_score": round(score, 6),
        "source": "BROAD_COMPANYFACTS_PROFITABILITY_INFLECTION_RS_PAPER",
    }
    return base._candidate_trade(ticker, frame, signal_day, pos, metadata)


def _gate4(
    aggregate_comparison: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
) -> dict[str, Any]:
    gate = _ORIGINAL_GATE4(aggregate_comparison, results, target_summary)
    drawdown_regressed_windows = [
        row["label"]
        for row in results
        if float(row["comparison"]["max_drawdown_delta"]) > base.MAX_DRAWDOWN_WORSE
    ]
    if drawdown_regressed_windows and "window_drawdown_drift_too_high" not in gate["failed_reasons"]:
        gate["failed_reasons"].append("window_drawdown_drift_too_high")
    gate["windows_drawdown_regressed"] = drawdown_regressed_windows
    gate["passed"] = not gate["failed_reasons"]
    gate["status"] = "accepted" if gate["passed"] else "rejected"
    gate["decision"] = (
        "positive_replay_lead_not_promoted_requires_shared_adapter"
        if gate["passed"]
        else "rejected_broad_companyfacts_profitability_inflection_rs_candidate_pool"
    )
    return gate


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
    base.MIN_RET20_EXCESS_SPY = MIN_RET20_EXCESS_SPY
    base.MIN_VOLUME_RATIO_20D = MIN_VOLUME_RATIO_20D
    base._candidate_for_ticker_day = _candidate_for_ticker_day
    base._gate4 = _gate4


def _mutate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    payload["experiment_id"] = EXP_ID
    payload["preflight"] = {
        "alpha_hypothesis": (
            "Broad SEC Companyfacts loss-to-profit inflection, confirmed by "
            "revenue growth and OHLCV relative strength, can add a distinct "
            "default-off paper candidate source beyond dual-positive growth."
        ),
        "category": "entry_candidate_pool",
        "nearby_prior_experiments": [
            "exp-20260605-011",
            "exp-20260605-014",
            "exp-20260605-015",
            "exp-20260605-022",
        ],
        "single_causal_variable": CHANGED_VARIABLE,
        "success_standard": (
            "Canonical three-window before/after aggregate EV and PnL must "
            "improve, no window EV/PnL regression, max drawdown drift <= "
            f"{base.MAX_DRAWDOWN_WORSE}, target trades >= {base.MIN_TARGET_TRADES}, "
            "all three windows represented, concentration within guardrails."
        ),
        "reproducible_if_failed": True,
    }
    payload["parameters"].pop("min_profit_yoy_growth", None)
    payload["parameters"].update(
        {
            "profit_current_gt_zero": PROFIT_CURRENT_GT_ZERO,
            "profit_prior_lte_zero": PROFIT_PRIOR_LTE_ZERO,
            "min_revenue_yoy_growth": MIN_REVENUE_YOY_GROWTH,
            "min_ret20_excess_spy": MIN_RET20_EXCESS_SPY,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "profit_canonical_priority": ["eps_diluted", "eps_basic", "net_income"],
            "daily_selection": "top_1_by_fixed_profit_inflection_rs_score",
        }
    )
    payload["production_impact"] = PRODUCTION_IMPACT
    payload["next_retry_requires"] = [
        "closed forward replacement-value rows",
        "proof that profitability inflection is incremental to ret20 momentum",
        "shared default-off adapter and parity tests before promotion",
        "avoid nearby Companyfacts threshold/scalar retunes on the same frozen sample",
    ]
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(ARTIFACT_MD),
        _repo_rel(TICKET_JSON),
        _repo_rel(base.GROWTH_PATH),
    ]
    return payload


def build_payload() -> dict[str, Any]:
    _patch_base()
    return _mutate_payload(base.build_payload())


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    record = base._experiment_log_record(payload)
    record.update(
        {
            "hypothesis": payload["preflight"]["alpha_hypothesis"],
            "change_summary": (
                "Tested broad SEC Companyfacts loss-to-profit inflection plus "
                "OHLCV confirmation as a replay-only default-off paper "
                "candidate source."
            ),
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": "profitability_inflection_rs_top1_v1",
            "changed_variable": CHANGED_VARIABLE,
            "nearby_prior_experiments": payload["preflight"]["nearby_prior_experiments"],
            "new_evidence_type": "new_production_visible_field",
            "component": _repo_rel(Path(__file__)),
            "parameters": payload["parameters"],
            "production_impact": PRODUCTION_IMPACT,
            "related_files": payload["related_files"],
        }
    )
    return record


def _window_table(results: list[dict[str, Any]]) -> str:
    lines = [
        "| Window | Target trades | Target PnL | EV before | EV after | EV delta | PnL delta | DD delta |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in results:
        lines.append(
            "| {label} | {count} | ${target_pnl:,.2f} | {before_ev:.4f} | {after_ev:.4f} | {ev_delta:+.4f} | ${pnl_delta:+,.2f} | {dd_delta:+.4f} |".format(
                label=row["label"],
                count=row["target_trade_count"],
                target_pnl=float(row["target_trade_pnl_usd"]),
                before_ev=float(row["before"]["expected_value_score"]),
                after_ev=float(row["after"]["expected_value_score"]),
                ev_delta=float(row["comparison"]["expected_value_score_delta"]),
                pnl_delta=float(row["comparison"]["strategy_total_pnl_delta"]),
                dd_delta=float(row["comparison"]["max_drawdown_delta"]),
            )
        )
    return "\n".join(lines)


def _write_artifact(payload: dict[str, Any]) -> None:
    comparison = payload["aggregate"]["comparison"]
    lines = [
        f"# {EXP_ID} Broad Companyfacts Profitability-Inflection RS",
        "",
        f"- Trial family: `{TRIAL_FAMILY}`",
        f"- Changed variable: `{CHANGED_VARIABLE}`",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Aggregate EV delta: {float(comparison['expected_value_score_delta']):+.4f}",
        f"- Aggregate PnL delta: ${float(comparison['strategy_total_pnl_delta']):+,.2f}",
        f"- Target trades: {payload['target_summary']['target_trade_count']}",
        f"- Production impact: `{PRODUCTION_IMPACT['adapter_status']}`",
        "",
        "## Gate 1-4",
        "",
        _window_table(payload["results"]),
        "",
        "## Gate 4",
        "",
    ]
    for key, value in payload["gate4"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Production / Backtest Parity",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "## Reproducibility",
            "",
            (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260605_026_broad_companyfacts_profitability_inflection_rs.py"
            ),
            "",
            "No JavaScript was used.",
        ]
    )
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    _patch_base()
    payload = build_payload()
    record = _experiment_log_record(payload)
    base._write_json(OUT_JSON, payload)
    base._write_json(LOG_JSON, record)
    base._write_json(BEFORE_JSON, payload["aggregate"]["before"])
    base._write_json(AFTER_JSON, payload["aggregate"]["after"])
    _write_artifact(payload)
    base._update_ticket(payload)
    base._update_registry(payload)
    base._append_experiment_log(record)
    print(
        json.dumps(
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
