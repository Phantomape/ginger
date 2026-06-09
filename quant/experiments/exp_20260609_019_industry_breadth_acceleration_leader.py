"""exp-20260609-019: industry breadth-acceleration leader candidate pool.

Replay-only alpha search. Space remains observe-only because fresh semantic
ranking needs forward/PIT catalyst data. This tests one alternative
production-visible free-OHLCV relation source: liquid leaders inside industries
where short-horizon peer breadth is accelerating become top-1 next-open
default-off paper candidates with a fixed 10-trading-day hold.

No production code, shared adapter, live/default orders, ranking, sizing, exits,
LLM/news path, watchlist, or run.py behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import math
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any

import exp_20260609_018_industry_pullback_reclaim as previous


framework = previous.framework

EXPERIMENT_ID = "exp-20260609-019"
STEM = "industry_breadth_acceleration_leader"
TRIAL_FAMILY = "industry_breadth_acceleration_leader_candidate_pool"
TRIAL_VARIANT_ID = "industry_breadth_acceleration_leader_top1_next_open_10d_v1"
CHANGED_VARIABLE = "industry_breadth_acceleration_leader_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = previous.REPO_ROOT
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260609_019_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = 4_000.0
HOLD_DAYS = 10
MAX_PAPER_TRADES_PER_DAY = 1
SAME_TICKER_COOLDOWN_DAYS = 12

MIN_PRICE = 10.0
MIN_AVG_DOLLAR_VOLUME_20D = 80_000_000.0
MIN_INDUSTRY_LIQUID_COUNT = 6
MIN_GROUP_MEDIAN_RET5_EXCESS_SPY = 0.010
MIN_GROUP_MEDIAN_RET20_EXCESS_SPY = -0.005
MIN_GROUP_MEDIAN_RET60_EXCESS_SPY = -0.025
MIN_GROUP_RET5_POSITIVE_FRACTION = 0.62
MIN_GROUP_RET20_POSITIVE_FRACTION = 0.42
MIN_GROUP_BREADTH_ACCELERATION = 0.08

MIN_CANDIDATE_RET5_EXCESS_SPY = 0.014
MIN_CANDIDATE_RET5_VS_GROUP = 0.004
MIN_CANDIDATE_RET20_EXCESS_SPY = -0.025
MAX_CANDIDATE_RET20_EXCESS_SPY = 0.170
MIN_CANDIDATE_RET60_EXCESS_SPY = -0.025
MIN_SIGNAL_RETURN = 0.003
MAX_SIGNAL_RETURN = 0.090
MIN_SIGNAL_RELATIVE_VS_SPY = 0.004
MIN_CLOSE_LOCATION = 0.62
MIN_VOLUME_RATIO_20D = 0.65
MAX_VOLUME_RATIO_20D = 2.60
MAX_REALIZED_VOL_20D = 0.090

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

PREDICTION = {
    "success_probability": 0.11,
    "expected_ev_delta": 0.12,
    "expected_pnl_delta": 2500.0,
    "main_failure_modes": [
        "accepted_relation_comparator_not_beaten",
        "window_regression",
        "drawdown_drift",
        "leader_chasing_relabel",
        "old_thin_regression",
    ],
    "confidence_reason": (
        "Space semantic ranking is PIT/forward-data limited, while accepted "
        "relation alphas show some free-OHLCV peer-displacement value. This "
        "tests a materially different breadth-participation field with strict "
        "accepted-comparator guards."
    ),
    "recorded_at": "2026-06-09T16:45:08+00:00",
}

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
        "Replay-only scout. This experiment changes no production code. A "
        "positive result would require a shared default-off adapter that "
        "computes the same sector-known liquid universe, PIT industry grouping, "
        "peer breadth acceleration, leader ranking, same-ticker core-overlap "
        "exclusion, next-open paper entry, 10-trading-day exit, costs, "
        "cooldown, accepted comparator checks, and concentration controls in "
        "both historical replay and daily production before any report queue, "
        "paper ledger, candidate priority, sizing, watchlist, or order surface "
        "could change."
    ),
}

BASE_GATE4 = previous.BASE_GATE4
BASE_BUILD_PAYLOAD = previous.BASE_BUILD_PAYLOAD
ACCEPTED_INDUSTRY_LAGGARD_REPAIR_COMPARATOR = (
    previous.ACCEPTED_INDUSTRY_LAGGARD_REPAIR_COMPARATOR
)
ACCEPTED_ROLLING_CORR_COMPARATOR = previous.ACCEPTED_ROLLING_CORR_COMPARATOR


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _group_summary(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if len(rows) < MIN_INDUSTRY_LIQUID_COUNT:
        return None
    ret5_values = [float(row["ret5_excess_spy"]) for row in rows]
    ret20_values = [float(row["ret20_excess_spy"]) for row in rows]
    ret60_values = [float(row["ret60_excess_spy"]) for row in rows]
    ret5_positive_fraction = sum(value > 0.0 for value in ret5_values) / len(
        ret5_values
    )
    ret20_positive_fraction = sum(value > 0.0 for value in ret20_values) / len(
        ret20_values
    )
    breadth_acceleration = ret5_positive_fraction - ret20_positive_fraction
    summary = {
        "liquid_group_count": len(rows),
        "median_ret5_excess_spy": median(ret5_values),
        "median_ret20_excess_spy": median(ret20_values),
        "median_ret60_excess_spy": median(ret60_values),
        "ret5_positive_fraction": ret5_positive_fraction,
        "ret20_positive_fraction": ret20_positive_fraction,
        "breadth_acceleration": breadth_acceleration,
    }
    if summary["median_ret5_excess_spy"] < MIN_GROUP_MEDIAN_RET5_EXCESS_SPY:
        return None
    if summary["median_ret20_excess_spy"] < MIN_GROUP_MEDIAN_RET20_EXCESS_SPY:
        return None
    if summary["median_ret60_excess_spy"] < MIN_GROUP_MEDIAN_RET60_EXCESS_SPY:
        return None
    if summary["ret5_positive_fraction"] < MIN_GROUP_RET5_POSITIVE_FRACTION:
        return None
    if summary["ret20_positive_fraction"] < MIN_GROUP_RET20_POSITIVE_FRACTION:
        return None
    if summary["breadth_acceleration"] < MIN_GROUP_BREADTH_ACCELERATION:
        return None
    return summary


def _candidate_from_metrics(
    *,
    metrics: dict[str, Any],
    group: dict[str, Any],
) -> dict[str, Any] | None:
    ret5_vs_group = (
        float(metrics["ret5_excess_spy"]) - float(group["median_ret5_excess_spy"])
    )
    if float(metrics["adv20"]) < MIN_AVG_DOLLAR_VOLUME_20D:
        return None
    if float(metrics["ret5_excess_spy"]) < MIN_CANDIDATE_RET5_EXCESS_SPY:
        return None
    if ret5_vs_group < MIN_CANDIDATE_RET5_VS_GROUP:
        return None
    if float(metrics["ret20_excess_spy"]) < MIN_CANDIDATE_RET20_EXCESS_SPY:
        return None
    if float(metrics["ret20_excess_spy"]) > MAX_CANDIDATE_RET20_EXCESS_SPY:
        return None
    if float(metrics["ret60_excess_spy"]) < MIN_CANDIDATE_RET60_EXCESS_SPY:
        return None
    if float(metrics["signal_return"]) < MIN_SIGNAL_RETURN:
        return None
    if float(metrics["signal_return"]) > MAX_SIGNAL_RETURN:
        return None
    if float(metrics["signal_relative_vs_spy"]) < MIN_SIGNAL_RELATIVE_VS_SPY:
        return None
    if float(metrics["close_location"]) < MIN_CLOSE_LOCATION:
        return None
    if float(metrics["volume_ratio_20d"]) < MIN_VOLUME_RATIO_20D:
        return None
    if float(metrics["volume_ratio_20d"]) > MAX_VOLUME_RATIO_20D:
        return None
    if float(metrics["realized_vol_20d"]) > MAX_REALIZED_VOL_20D:
        return None

    group_breadth_score = min(max(float(group["breadth_acceleration"]), 0.0), 0.40)
    leader_score = min(max(ret5_vs_group, 0.0), 0.10)
    liquidity_score = math.log10(max(float(metrics["adv20"]), 1.0) / 1_000_000.0)
    score = (
        1.55 * group_breadth_score
        + 1.20 * float(group["median_ret5_excess_spy"])
        + 1.05 * leader_score
        + 0.75 * float(metrics["signal_relative_vs_spy"])
        + 0.55 * float(metrics["ret20_excess_spy"])
        + 0.35 * float(metrics["close_location"])
        + 0.05 * liquidity_score
        - 0.65 * float(metrics["realized_vol_20d"])
        - 0.05 * abs(float(metrics["volume_ratio_20d"]) - 1.20)
    )
    return {
        "date": metrics["date"],
        "ticker": metrics["ticker"],
        "source": "INDUSTRY_BREADTH_ACCELERATION_LEADER_PAPER",
        "candidate_score": round(score, 6),
        "candidate_group_key": metrics["group_key"],
        "candidate_ret5_vs_group": round(ret5_vs_group, 6),
        "candidate_ret5_excess_spy": round(metrics["ret5_excess_spy"], 6),
        "candidate_ret20_excess_spy": round(metrics["ret20_excess_spy"], 6),
        "candidate_ret60_excess_spy": round(metrics["ret60_excess_spy"], 6),
        "candidate_signal_day_return": round(metrics["signal_return"], 6),
        "candidate_signal_relative_vs_spy": round(
            metrics["signal_relative_vs_spy"], 6
        ),
        "candidate_close_location": round(metrics["close_location"], 6),
        "candidate_volume_ratio_20d": round(metrics["volume_ratio_20d"], 6),
        "candidate_realized_vol_20d": round(metrics["realized_vol_20d"], 6),
        "candidate_avg_dollar_volume_20d": round(metrics["adv20"], 2),
        "industry_context": {
            "group_key": metrics["group_key"],
            "liquid_group_count": group["liquid_group_count"],
            "median_ret5_excess_spy": round(group["median_ret5_excess_spy"], 6),
            "median_ret20_excess_spy": round(group["median_ret20_excess_spy"], 6),
            "median_ret60_excess_spy": round(group["median_ret60_excess_spy"], 6),
            "ret5_positive_fraction": round(group["ret5_positive_fraction"], 6),
            "ret20_positive_fraction": round(group["ret20_positive_fraction"], 6),
            "breadth_acceleration": round(group["breadth_acceleration"], 6),
            "rule_version": RULE_VERSION,
        },
        "sector": metrics.get("sector"),
        "industry": metrics.get("industry"),
        "sector_coverage_status": metrics.get("sector_coverage_status"),
        "rule_version": RULE_VERSION,
        "uses_free_ohlcv_only": True,
        "uses_llm": False,
        "trade_enabled": False,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    entries_by_date = framework.shadow._baseline_entries(before_result)
    indices = {
        ticker: framework.shadow._row_index(framework.shadow._series(snapshot, ticker))
        for ticker in snapshot
    }
    dates = [
        date_value
        for date_value in framework.shadow._trading_dates(snapshot)
        if str(cfg["start"]) <= date_value <= str(cfg["end"])
    ]

    candidates: list[dict[str, Any]] = []
    day_contexts: list[dict[str, Any]] = []
    candidate_tickers: set[str] = set()
    scan = {
        "scanned_trading_days": len(dates),
        "days_with_accelerating_groups": 0,
        "days_with_raw_candidates": 0,
        "accelerating_group_rows": 0,
        "raw_candidate_rows": 0,
        "unique_candidate_tickers": 0,
        "rule_version": RULE_VERSION,
    }

    for signal_date in dates:
        group_members: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for ticker in sorted(sector_entries):
            metrics = previous._ticker_day_metrics(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                ticker=ticker,
                signal_date=signal_date,
            )
            if metrics is None:
                continue
            group_members[metrics["group_key"]].append(metrics)

        group_summaries = {
            group_key: summary
            for group_key, rows in group_members.items()
            if (summary := _group_summary(rows)) is not None
        }
        if not group_summaries:
            continue
        scan["days_with_accelerating_groups"] += 1
        scan["accelerating_group_rows"] += len(group_summaries)

        day_rows: list[dict[str, Any]] = []
        for group_key, rows in group_members.items():
            group = group_summaries.get(group_key)
            if group is None:
                continue
            for metrics in rows:
                row = _candidate_from_metrics(metrics=metrics, group=group)
                if row is None:
                    continue
                ab_entries = entries_by_date.get(signal_date, [])
                row["same_day_ab_entry_count"] = len(ab_entries)
                row["same_day_ab_overlap"] = bool(ab_entries)
                row["same_ticker_ab_overlap"] = any(
                    trade.get("ticker") == row["ticker"] for trade in ab_entries
                )
                day_rows.append(row)
                candidate_tickers.add(str(row["ticker"]))

        if not day_rows:
            continue
        day_rows.sort(
            key=lambda row: (
                -float(row["candidate_score"]),
                -float(row["industry_context"]["breadth_acceleration"]),
                -float(row["candidate_ret5_vs_group"]),
                -float(row["candidate_signal_relative_vs_spy"]),
                -float(row["candidate_avg_dollar_volume_20d"]),
                row["ticker"],
            )
        )
        candidates.extend(day_rows)
        scan["days_with_raw_candidates"] += 1
        scan["raw_candidate_rows"] += len(day_rows)
        top = day_rows[0]
        day_contexts.append(
            {
                "date": signal_date,
                "raw_candidate_count": len(day_rows),
                "accelerating_group_count": len(group_summaries),
                "top_candidate": top["ticker"],
                "top_group_key": top["candidate_group_key"],
                "top_score": top["candidate_score"],
                "top_breadth_acceleration": top["industry_context"][
                    "breadth_acceleration"
                ],
                "top_ret5_vs_group": top["candidate_ret5_vs_group"],
                "top_signal_relative_vs_spy": top[
                    "candidate_signal_relative_vs_spy"
                ],
            }
        )

    candidates.sort(
        key=lambda row: (
            row["date"],
            -float(row["candidate_score"]),
            -float(row["industry_context"]["breadth_acceleration"]),
            -float(row["candidate_ret5_vs_group"]),
            -float(row["candidate_signal_relative_vs_spy"]),
            -float(row["candidate_avg_dollar_volume_20d"]),
            row["ticker"],
        )
    )
    scan.update(
        {
            "unique_candidate_tickers": len(candidate_tickers),
            "min_industry_liquid_count": MIN_INDUSTRY_LIQUID_COUNT,
            "min_group_median_ret5_excess_spy": MIN_GROUP_MEDIAN_RET5_EXCESS_SPY,
            "min_group_median_ret20_excess_spy": MIN_GROUP_MEDIAN_RET20_EXCESS_SPY,
            "min_group_median_ret60_excess_spy": MIN_GROUP_MEDIAN_RET60_EXCESS_SPY,
            "min_group_ret5_positive_fraction": MIN_GROUP_RET5_POSITIVE_FRACTION,
            "min_group_ret20_positive_fraction": MIN_GROUP_RET20_POSITIVE_FRACTION,
            "min_group_breadth_acceleration": MIN_GROUP_BREADTH_ACCELERATION,
            "min_candidate_ret5_excess_spy": MIN_CANDIDATE_RET5_EXCESS_SPY,
            "min_candidate_ret5_vs_group": MIN_CANDIDATE_RET5_VS_GROUP,
            "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
            "max_candidate_ret20_excess_spy": MAX_CANDIDATE_RET20_EXCESS_SPY,
            "min_candidate_ret60_excess_spy": MIN_CANDIDATE_RET60_EXCESS_SPY,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "max_signal_return": MAX_SIGNAL_RETURN,
            "min_signal_relative_vs_spy": MIN_SIGNAL_RELATIVE_VS_SPY,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "max_volume_ratio_20d": MAX_VOLUME_RATIO_20D,
            "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
        }
    )
    return candidates, day_contexts, scan


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = BASE_GATE4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    if aggregate["expected_value_score_delta_sum"] <= (
        ACCEPTED_INDUSTRY_LAGGARD_REPAIR_COMPARATOR["expected_value_score_delta_sum"]
    ):
        gate.setdefault("failed_reasons", []).append(
            "accepted_industry_laggard_repair_ev_not_beaten"
        )
    if aggregate["total_pnl_delta_sum"] <= (
        ACCEPTED_INDUSTRY_LAGGARD_REPAIR_COMPARATOR["total_pnl_delta_sum"]
    ):
        gate.setdefault("failed_reasons", []).append(
            "accepted_industry_laggard_repair_pnl_not_beaten"
        )
    if aggregate["expected_value_score_delta_sum"] <= (
        ACCEPTED_ROLLING_CORR_COMPARATOR["expected_value_score_delta_sum"]
    ):
        gate.setdefault("failed_reasons", []).append(
            "accepted_rolling_corr_ev_not_beaten"
        )
    if aggregate["total_pnl_delta_sum"] <= (
        ACCEPTED_ROLLING_CORR_COMPARATOR["total_pnl_delta_sum"]
    ):
        gate.setdefault("failed_reasons", []).append(
            "accepted_rolling_corr_pnl_not_beaten"
        )
    gate["accepted_comparators"] = {
        "industry_laggard_repair": ACCEPTED_INDUSTRY_LAGGARD_REPAIR_COMPARATOR,
        "rolling_corr_peer_shock": ACCEPTED_ROLLING_CORR_COMPARATOR,
    }
    gate["passed"] = not gate.get("failed_reasons")
    gate["decision"] = (
        "positive_replay_lead_not_promoted_industry_breadth_acceleration_leader"
        if gate["passed"]
        else "rejected_industry_breadth_acceleration_leader_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    aggregate = payload["delta_metrics"]["aggregate"]
    passed = bool(payload["gate4"]["passed"])
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Production-visible industry breadth acceleration may identify "
                "liquid leaders inside groups where peer participation is "
                "improving, giving cleaner replacement value than Space retunes "
                "or generic pullback-reclaim candidates."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
            "new_evidence_type": "free_ohlcv_industry_peer_breadth_acceleration",
            "nearby_prior_experiments": [
                "exp-20260607-008",
                "exp-20260606-025",
                "exp-20260609-014",
                "exp-20260609-018",
                "exp-20260605-012",
            ],
            "prior_trial_count": 5,
            "multiple_testing_risk_bucket": "high",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_comparators": {
                "industry_laggard_repair": ACCEPTED_INDUSTRY_LAGGARD_REPAIR_COMPARATOR,
                "rolling_corr_peer_shock": ACCEPTED_ROLLING_CORR_COMPARATOR,
            },
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that breadth acceleration "
                "plus a leader rank is still generic leader chasing, or the "
                "accepted industry-laggard and rolling-correlation relation "
                "sources already capture the available free-OHLCV peer edge."
            ),
            "next_evidence_needed": (
                "A retry needs materially new PIT evidence such as forward "
                "shared-adapter replacement rows, catalyst provenance, borrow/"
                "options/ownership context, or a true order-flow field. Do not "
                "answer by sweeping group breadth, leader rank, volume, hold-day, "
                "cooldown, or notional thresholds on these frozen windows."
            ),
        }
    )
    payload.setdefault("parameters", {}).update(
        {
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "min_price": MIN_PRICE,
            "min_avg_dollar_volume_20d": MIN_AVG_DOLLAR_VOLUME_20D,
            "min_industry_liquid_count": MIN_INDUSTRY_LIQUID_COUNT,
            "min_group_median_ret5_excess_spy": MIN_GROUP_MEDIAN_RET5_EXCESS_SPY,
            "min_group_median_ret20_excess_spy": MIN_GROUP_MEDIAN_RET20_EXCESS_SPY,
            "min_group_median_ret60_excess_spy": MIN_GROUP_MEDIAN_RET60_EXCESS_SPY,
            "min_group_ret5_positive_fraction": MIN_GROUP_RET5_POSITIVE_FRACTION,
            "min_group_ret20_positive_fraction": MIN_GROUP_RET20_POSITIVE_FRACTION,
            "min_group_breadth_acceleration": MIN_GROUP_BREADTH_ACCELERATION,
            "min_candidate_ret5_excess_spy": MIN_CANDIDATE_RET5_EXCESS_SPY,
            "min_candidate_ret5_vs_group": MIN_CANDIDATE_RET5_VS_GROUP,
            "min_candidate_ret20_excess_spy": MIN_CANDIDATE_RET20_EXCESS_SPY,
            "max_candidate_ret20_excess_spy": MAX_CANDIDATE_RET20_EXCESS_SPY,
            "min_candidate_ret60_excess_spy": MIN_CANDIDATE_RET60_EXCESS_SPY,
            "min_signal_return": MIN_SIGNAL_RETURN,
            "max_signal_return": MAX_SIGNAL_RETURN,
            "min_signal_relative_vs_spy": MIN_SIGNAL_RELATIVE_VS_SPY,
            "min_close_location": MIN_CLOSE_LOCATION,
            "min_volume_ratio_20d": MIN_VOLUME_RATIO_20D,
            "max_volume_ratio_20d": MAX_VOLUME_RATIO_20D,
            "max_realized_vol_20d": MAX_REALIZED_VOL_20D,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: after Space is deferred by forward/PIT "
            "catalyst-data limits, test whether improving peer participation "
            "inside liquid industries identifies leaders with replacement value."
        ),
        "2_history_check": {
            "Space": (
                "exp-20260605-012 found no mature official Space cohort passing "
                "the 10-day same-theme replacement-value gate; exp-20260605-025 "
                "low-thrust absorption failed the accepted Space comparator. "
                "Space price-action/ETF/defense/low-thrust threshold retunes "
                "remain frozen without new forward evidence."
            ),
            "exp-20260607-008": (
                "Industry-relative laggard repair was accepted and is the "
                "nearest industry-relation comparator this run must beat."
            ),
            "exp-20260606-025": (
                "Rolling-correlation peer shock was accepted and remains the "
                "stronger relation comparator this run must beat."
            ),
            "exp-20260609-014": (
                "Multi-peer cluster shock failed; this run uses peer breadth "
                "acceleration, not generic beta clustering."
            ),
            "exp-20260609-018": (
                "Industry pullback reclaim failed aggregate EV/PnL and old_thin. "
                "This run does not retune SMA/reclaim/pullback fields."
            ),
        },
        "3_single_policy_bundle": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Require positive "
            "aggregate EV/PnL, no EV/PnL-regressed window, target sample >=20 "
            "across all 3 windows, survival unchanged, drawdown drift <=0.5pp, "
            "concentration guard pass, and aggregate EV/PnL above accepted "
            "industry-laggard and rolling-corr comparators."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260609_019_industry_breadth_acceleration_leader.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    payload["gate3"]["note"] = (
        "No new core filter or live entry rule was added. The breadth "
        "acceleration source is additive replay-only/default-off paper, so core "
        "signals generated/survived are unchanged from baseline."
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only close-of-day OHLCV available on the signal date plus "
        "prior history needed for industry medians, peer breadth fractions, "
        "ADV, volume ratio, volatility, and SPY-relative returns. Paper entry "
        "is next available open with existing entry slippage; exit is the close "
        "10 trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    payload["decision"] = payload["gate4"]["decision"]
    payload["status"] = "positive_replay_lead_not_promoted" if passed else "rejected"
    payload["interpretation"] = (
        "The industry breadth-acceleration leader source cleared strict Gate 4 "
        "and beat accepted relation comparators, but remains replay-only until "
        "a shared default-off adapter proves historical/daily parity and "
        "forward replacement value."
        if passed
        else (
            "The industry breadth-acceleration leader source did not clear Gate "
            "4 or did not beat accepted relation comparators. Do not promote it "
            "or locally retune breadth, leader, liquidity, hold-day, cooldown, "
            "or notional thresholds on these frozen windows."
        )
    )
    payload["rejection_reason"] = (
        None if passed else "; ".join(payload["gate4"]["failed_reasons"])
    )
    payload["post_run_reflection"] = {
        "result": payload["interpretation"],
        "why_result_happened": (
            "The candidate earned most of its aggregate gain in mid_weak while "
            "late_strong and old_thin both lost EV/PnL, so the breadth field "
            "looks regime-fragile rather than a stable replacement-value source. "
            "Its drawdown drift also shows that leader selection amplified "
            "risk in old_thin, and the accepted rolling-correlation relation "
            "sleeve already captures the stronger peer displacement edge."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by sweeping group breadth fractions, median return "
            "thresholds, leader-rank distance, volume ratio, volatility cap, "
            "top-N, hold-day, cooldown, or notional on the same fixed windows."
        ),
        "new_evidence_required": (
            "Only revisit with a new PIT field outside free-OHLCV leader "
            "selection, such as forward shared-adapter replacement rows tied "
            "to catalyst provenance, borrow/options/ownership context, or a "
            "true order-flow surface."
        ),
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Raw candidates | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {raw} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                raw=payload["raw_candidate_counts"][label],
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Industry Breadth-Acceleration Leader",
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
            "- Industry-laggard comparator EV/PnL: `{}` / `${:,.2f}`".format(
                ACCEPTED_INDUSTRY_LAGGARD_REPAIR_COMPARATOR[
                    "expected_value_score_delta_sum"
                ],
                ACCEPTED_INDUSTRY_LAGGARD_REPAIR_COMPARATOR["total_pnl_delta_sum"],
            ),
            "- Rolling-corr comparator EV/PnL: `{}` / `${:,.2f}`".format(
                ACCEPTED_ROLLING_CORR_COMPARATOR["expected_value_score_delta_sum"],
                ACCEPTED_ROLLING_CORR_COMPARATOR["total_pnl_delta_sum"],
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
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate[
            "expected_value_score_delta_sum"
        ],
        "aggregate_expected_value_delta_pct": aggregate[
            "expected_value_score_delta_pct"
        ],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_comparators": payload["accepted_comparators"],
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_after": payload["after_metrics"][label][
                    "expected_value_score"
                ],
                "expected_value_delta": payload["delta_metrics"]["by_window"][
                    label
                ]["expected_value_score"],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][
                    label
                ]["total_pnl"],
                "raw_candidate_count": payload["raw_candidate_counts"][label],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": {**payload["calibration"]},
        "production_impact": PRODUCTION_IMPACT,
        "negative_reflection": payload["negative_reflection"],
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _update_ticket_and_registry(
    payload: dict[str, Any],
    log_record: dict[str, Any],
) -> None:
    aggregate = payload["delta_metrics"]["aggregate"]
    result = {
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": "alpha-search-space",
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
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
            _repo_rel(Path(__file__)): framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def _patch_framework() -> None:
    framework.EXPERIMENT_ID = EXPERIMENT_ID
    framework.STEM = STEM
    framework.TRIAL_FAMILY = TRIAL_FAMILY
    framework.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    framework.CHANGED_VARIABLE = CHANGED_VARIABLE
    framework.RULE_VERSION = RULE_VERSION
    framework.OUT_DIR = OUT_DIR
    framework.OUT_JSON = OUT_JSON
    framework.LOG_JSON = LOG_JSON
    framework.TICKET_JSON = TICKET_JSON
    framework.CARD_MD = CARD_MD
    framework.MANIFEST_JSON = MANIFEST_JSON
    framework.EXPERIMENT_LOG = EXPERIMENT_LOG
    framework.REGISTRY_JSON = REGISTRY_JSON
    framework.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    framework.HOLD_DAYS = HOLD_DAYS
    framework.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    framework.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    framework.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    framework.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    framework.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    framework.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    framework.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    framework.PREDICTION = PREDICTION
    framework.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._gate4 = _gate4
    framework._build_payload = _build_payload
    framework._build_card = _build_card
    framework._build_log_record = _build_log_record
    framework._update_ticket_and_registry = _update_ticket_and_registry
    framework._write_manifest = _write_manifest


_patch_framework()


def main() -> None:
    framework.main()


if __name__ == "__main__":
    main()
