"""exp-20260605-025: Space low-thrust orderly absorption trend pool.

This alpha search keeps the accepted default-off Space route fixed through the
shared cost/liquidity helper, then tests one additional paper-only candidate
pool: governed Space ``trend_long`` candidates that miss the accepted
high-close/thrust route but show low-thrust orderly absorption on the signal
day.

Core entries, ranking, sizing, exits, heat, LLM/news replay, watchlists, and
live/default orders are unchanged. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import exp_20260602_025_space_cost_liquidity_shared_helper as accepted_shared  # noqa: E402


EXPERIMENT_ID = "exp-20260605-025"
STEM = "exp_20260605_025_space_low_thrust_orderly_absorption_trend_pool"
TRIAL_FAMILY = "governed_space_low_thrust_orderly_absorption_trend_candidate_pool"
CHANGED_VARIABLE = "space_low_thrust_orderly_absorption_trend_candidate_pool_v1"
RULE_VERSION = "space_low_thrust_orderly_absorption_trend_pool_v1"

ACCEPTED_BASELINE_EXPERIMENT_ID = "exp-20260602-025"
TARGET_STRATEGY = "trend_long"
BASE_NOTIONAL_USD = 10_000.0
MIN_SIGNAL_DAY_CLOSE_LOCATION = 0.55
MAX_SIGNAL_DAY_CLOSE_LOCATION = 0.65
MIN_SIGNAL_DAY_OPEN_CLOSE_RETURN = 0.01
MAX_SIGNAL_DAY_OPEN_CLOSE_RETURN = 0.04
MAX_SIGNAL_DAY_RANGE_PCT = 0.06
MIN_SIGNAL_DAY_DOLLAR_VOLUME = 100_000_000.0
MIN_INCREMENTAL_BRANCH_TRADES = 3
MIN_INCREMENTAL_BRANCH_WINDOWS = 2
HARD_MIN_EV_DELTA_VS_ACCEPTED_PCT = 0.10

source = accepted_shared.source
space_base = source.space_base
REPO_ROOT = source.REPO_ROOT
WINDOWS = source.WINDOWS
TARGET_TICKERS = source.TARGET_TICKERS
TARGET_SECTOR_MAP = source.TARGET_SECTOR_MAP
SOURCE_UNIVERSE_STATE = source.SOURCE_UNIVERSE_STATE
SOURCE_OHLCV_EXPERIMENT_ID = source.SOURCE_OHLCV_EXPERIMENT_ID

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
ACCEPTED_BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / ACCEPTED_BASELINE_EXPERIMENT_ID
    / "exp_20260602_025_space_cost_liquidity_shared_helper.json"
)


def _repo_rel(path: Path | str) -> str:
    return space_base._repo_rel(path)


def _to_float(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out


def _low_thrust_absorption_state(
    trade: dict[str, Any],
    market_state: dict[str, Any],
) -> dict[str, Any]:
    ticker = str(trade.get("ticker") or "").upper()
    strategy = str(trade.get("strategy") or "")
    cost_liquidity = market_state.get("space_cost_liquidity_support") or {}
    close_location = _to_float(market_state.get("signal_day_close_location_value"))
    open_close_return = _to_float(
        market_state.get("signal_day_open_close_return_pct")
    )
    range_pct = _to_float(market_state.get("signal_day_range_pct"))
    dollar_volume = _to_float(cost_liquidity.get("signal_day_dollar_volume"))
    base_passed = bool(market_state.get("passed"))

    strategy_passed = strategy == TARGET_STRATEGY
    close_location_passed = (
        close_location is not None
        and MIN_SIGNAL_DAY_CLOSE_LOCATION
        <= close_location
        < MAX_SIGNAL_DAY_CLOSE_LOCATION
    )
    open_close_passed = (
        open_close_return is not None
        and MIN_SIGNAL_DAY_OPEN_CLOSE_RETURN
        <= open_close_return
        < MAX_SIGNAL_DAY_OPEN_CLOSE_RETURN
    )
    range_passed = range_pct is not None and range_pct <= MAX_SIGNAL_DAY_RANGE_PCT
    liquidity_passed = (
        dollar_volume is not None and dollar_volume >= MIN_SIGNAL_DAY_DOLLAR_VOLUME
    )
    branch_passed = (
        strategy_passed
        and close_location_passed
        and open_close_passed
        and range_passed
        and liquidity_passed
    )
    incremental_branch_passed = branch_passed and not base_passed
    if branch_passed:
        reason = "low_thrust_orderly_absorption_trend"
    elif not strategy_passed:
        reason = "not_trend_long"
    elif not close_location_passed:
        reason = "close_location_outside_absorption_band"
    elif not open_close_passed:
        reason = "open_close_return_outside_low_thrust_band"
    elif not range_passed:
        reason = "signal_day_range_above_orderly_ceiling"
    elif not liquidity_passed:
        reason = "signal_day_dollar_volume_below_floor"
    else:
        reason = "not_supported"
    return {
        "rule_version": RULE_VERSION,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
        "uses_existing_signal_strategy_field": True,
        "uses_free_ohlcv_only": True,
        "uses_llm": False,
        "target_strategy": TARGET_STRATEGY,
        "strategy": strategy,
        "ticker": ticker,
        "base_accepted_route_passed": base_passed,
        "branch_passed": branch_passed,
        "incremental_branch_passed": incremental_branch_passed,
        "support_reason": reason,
        "signal_day": market_state.get("signal_day"),
        "signal_day_close_location_value": space_base._round(close_location, 6),
        "min_signal_day_close_location": MIN_SIGNAL_DAY_CLOSE_LOCATION,
        "max_signal_day_close_location": MAX_SIGNAL_DAY_CLOSE_LOCATION,
        "signal_day_open_close_return_pct": space_base._round(
            open_close_return,
            6,
        ),
        "min_signal_day_open_close_return_pct": MIN_SIGNAL_DAY_OPEN_CLOSE_RETURN,
        "max_signal_day_open_close_return_pct": MAX_SIGNAL_DAY_OPEN_CLOSE_RETURN,
        "signal_day_range_pct": space_base._round(range_pct, 6),
        "max_signal_day_range_pct": MAX_SIGNAL_DAY_RANGE_PCT,
        "signal_day_dollar_volume": space_base._round(dollar_volume, 2),
        "min_signal_day_dollar_volume": MIN_SIGNAL_DAY_DOLLAR_VOLUME,
        "strategy_passed": strategy_passed,
        "close_location_passed": close_location_passed,
        "open_close_return_passed": open_close_passed,
        "range_passed": range_passed,
        "liquidity_passed": liquidity_passed,
        "trade_enabled": False,
        "alters_orders": False,
    }


def _strategy_with_low_thrust_absorption_branch(
    snapshot: str,
    trades: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    base_states = source._strategy_high_close_thrust_with_cost_liquidity_support(
        snapshot,
        trades,
    )
    out: dict[str, dict[str, Any]] = {}
    for trade in trades:
        key = f"{trade.get('entry_date')}|{trade.get('ticker')}|{trade.get('exit_date')}"
        state = dict(base_states.get(key) or {})
        branch_state = _low_thrust_absorption_state(trade, state)
        state["space_low_thrust_orderly_absorption_branch"] = branch_state
        state["passed"] = bool(state.get("passed")) or bool(
            branch_state.get("branch_passed")
        )
        out[key] = state
    return out


def _fixed_notional_trade(
    trade: dict[str, Any],
    market_state: dict[str, Any],
) -> dict[str, Any]:
    pnl_pct = float(trade.get("pnl_pct_net") or 0.0)
    cost_liquidity = market_state.get("space_cost_liquidity_support") or {}
    branch = market_state.get("space_low_thrust_orderly_absorption_branch") or {}
    notional = float(cost_liquidity.get("supported_notional_usd") or BASE_NOTIONAL_USD)
    return {
        **trade,
        "core_sized_pnl": space_base._round(trade.get("pnl"), 2),
        "core_sized_shares": trade.get("shares"),
        "base_paper_notional_usd": BASE_NOTIONAL_USD,
        "paper_notional_usd": notional,
        "space_cost_liquidity_support": cost_liquidity,
        "space_low_thrust_orderly_absorption_branch": branch,
        "pnl": round(notional * pnl_pct, 2),
        "pnl_pct_net": space_base._round(pnl_pct, 6),
        "shares": None,
        "market_confirmation": market_state,
    }


def _aggregate_metrics(metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score_sum": space_base._round(
            sum(float(row.get("expected_value_score") or 0.0) for row in metrics.values()),
            4,
        ),
        "total_pnl_sum": space_base._round(
            sum(float(row.get("total_pnl") or 0.0) for row in metrics.values()),
            2,
        ),
        "max_drawdown_pct_max": space_base._round(
            max(float(row.get("max_drawdown_pct") or 0.0) for row in metrics.values()),
            4,
        ),
        "trade_count_sum": sum(int(row.get("trade_count") or 0) for row in metrics.values()),
        "min_survival_rate": space_base._round(
            min(float(row.get("survival_rate") or 0.0) for row in metrics.values()),
            4,
        ),
    }


def _accepted_baseline_comparison(payload: dict[str, Any]) -> dict[str, Any]:
    accepted_payload = json.loads(ACCEPTED_BASELINE_JSON.read_text(encoding="utf-8"))
    accepted_after = accepted_payload["after_metrics"]
    current_after = payload["after_metrics"]
    by_window = {}
    windows_ev_regressed = 0
    windows_pnl_regressed = 0
    for label in WINDOWS:
        ev_delta = space_base._round(
            float(current_after[label]["expected_value_score"])
            - float(accepted_after[label]["expected_value_score"]),
            4,
        )
        pnl_delta = space_base._round(
            float(current_after[label]["total_pnl"])
            - float(accepted_after[label]["total_pnl"]),
            2,
        )
        by_window[label] = {
            "expected_value_score_delta": ev_delta,
            "total_pnl_delta": pnl_delta,
        }
        if ev_delta < 0:
            windows_ev_regressed += 1
        if pnl_delta < 0:
            windows_pnl_regressed += 1
    accepted_aggregate = _aggregate_metrics(accepted_after)
    current_aggregate = _aggregate_metrics(current_after)
    actual_ev_delta = space_base._round(
        current_aggregate["expected_value_score_sum"]
        - accepted_aggregate["expected_value_score_sum"],
        4,
    )
    required_ev_delta = space_base._round(
        accepted_aggregate["expected_value_score_sum"]
        * HARD_MIN_EV_DELTA_VS_ACCEPTED_PCT,
        4,
    )
    return {
        "baseline_experiment_id": ACCEPTED_BASELINE_EXPERIMENT_ID,
        "baseline_artifact": _repo_rel(ACCEPTED_BASELINE_JSON),
        "accepted_after_aggregate": accepted_aggregate,
        "current_after_aggregate": current_aggregate,
        "aggregate_expected_value_score_delta": actual_ev_delta,
        "aggregate_total_pnl_delta": space_base._round(
            current_aggregate["total_pnl_sum"] - accepted_aggregate["total_pnl_sum"],
            2,
        ),
        "hard_min_ev_delta_vs_accepted_pct": HARD_MIN_EV_DELTA_VS_ACCEPTED_PCT,
        "hard_min_ev_delta_vs_accepted": required_ev_delta,
        "hard_min_ev_delta_passed": actual_ev_delta > required_ev_delta,
        "windows_ev_regressed": windows_ev_regressed,
        "windows_pnl_regressed": windows_pnl_regressed,
        "by_window": by_window,
    }


def _incremental_branch_summary(payload: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for label, trades in payload.get("target_trades_by_window", {}).items():
        for trade in trades:
            branch = trade.get("space_low_thrust_orderly_absorption_branch") or {}
            if branch.get("incremental_branch_passed"):
                rows.append({**trade, "window": label})
    return {
        "incremental_trade_count": len(rows),
        "incremental_windows": sorted({row["window"] for row in rows}),
        "incremental_total_pnl": space_base._round(
            sum(float(row.get("pnl") or 0.0) for row in rows),
            2,
        ),
        "incremental_positive_trade_count": sum(
            1 for row in rows if float(row.get("pnl") or 0.0) > 0.0
        ),
        "incremental_win_rate": space_base._round(
            (
                sum(1 for row in rows if float(row.get("pnl") or 0.0) > 0.0)
                / len(rows)
            )
            if rows
            else 0.0,
            4,
        ),
        "incremental_by_window": {
            window: space_base._round(
                sum(float(row.get("pnl") or 0.0) for row in rows if row["window"] == window),
                2,
            )
            for window in sorted({row["window"] for row in rows})
        },
        "incremental_by_ticker": {
            ticker: space_base._round(
                sum(float(row.get("pnl") or 0.0) for row in rows if row.get("ticker") == ticker),
                2,
            )
            for ticker in sorted({str(row.get("ticker") or "") for row in rows})
            if ticker
        },
        "rows": rows,
    }


def _configure_source_runner() -> None:
    source.EXPERIMENT_ID = EXPERIMENT_ID
    source.STEM = STEM
    source.CHANGED_VARIABLE = CHANGED_VARIABLE
    source.RULE_VERSION = (
        accepted_shared.shared.SPACE_CATALYST_COST_LIQUIDITY_SUPPORT_RULE_VERSION
    )
    source.OUT_DIR = OUT_DIR
    source.OUT_JSON = OUT_JSON
    source.LOG_JSON = LOG_JSON
    source.TICKET_JSON = TICKET_JSON
    source.CARD_MD = CARD_MD
    source.EXPERIMENT_LOG = EXPERIMENT_LOG
    source._cost_liquidity_support_state = (
        accepted_shared._shared_cost_liquidity_support_state
    )
    source._configure_space_base()
    space_base.TRIAL_FAMILY = TRIAL_FAMILY
    space_base.CHANGED_VARIABLE = CHANGED_VARIABLE
    space_base._market_confirmation = _strategy_with_low_thrust_absorption_branch
    space_base._fixed_notional_trade = _fixed_notional_trade


def _customize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    accepted_comparison = _accepted_baseline_comparison(payload)
    branch_summary = _incremental_branch_summary(payload)
    base_gate4_passed = bool(payload["gate4"]["passed"])
    soft_current_accepted_improved = (
        accepted_comparison["aggregate_expected_value_score_delta"] > 0
        and accepted_comparison["aggregate_total_pnl_delta"] > 0
        and accepted_comparison["windows_ev_regressed"] == 0
        and accepted_comparison["windows_pnl_regressed"] == 0
    )
    branch_sample_passed = (
        branch_summary["incremental_trade_count"] >= MIN_INCREMENTAL_BRANCH_TRADES
        and len(branch_summary["incremental_windows"]) >= MIN_INCREMENTAL_BRANCH_WINDOWS
        and branch_summary["incremental_total_pnl"] > 0.0
    )
    gate4_passed = (
        base_gate4_passed
        and soft_current_accepted_improved
        and accepted_comparison["hard_min_ev_delta_passed"]
        and branch_sample_passed
    )
    if gate4_passed:
        decision = "accepted_space_low_thrust_orderly_absorption_trend_pool"
    elif branch_sample_passed and not soft_current_accepted_improved:
        decision = "rejected_window_regression_space_low_thrust_absorption_pool"
    elif branch_sample_passed:
        decision = "rejected_positive_below_space_hard_min_low_thrust_absorption_pool"
    else:
        decision = "rejected_space_low_thrust_orderly_absorption_trend_pool"
    aggregate = payload["delta_metrics"]["aggregate"]
    before_metrics = payload["before_metrics"]
    min_survival = min(
        float(row.get("survival_rate") or 0.0) for row in before_metrics.values()
    )
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    predicted_success_probability = 0.16
    actual_success = bool(gate4_passed)
    brier_score = ((1.0 if actual_success else 0.0) - predicted_success_probability) ** 2
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "timestamp": timestamp,
            "lane": "alpha_search",
            "status": decision,
            "decision": decision,
            "change_type": "candidate_pool_paper_sleeve_shadow",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": "low_thrust_orderly_absorption_v1",
            "prior_trial_count": 7,
            "nearby_prior_experiments": [
                "exp-20260528-026",
                "exp-20260529-020",
                "exp-20260531-022",
                "exp-20260602-025",
                "exp-20260604-018",
                "exp-20260604-019",
                "exp-20260605-012",
            ],
            "multiple_testing_risk_bucket": "high",
            "new_evidence_type": (
                "production_visible_free_ohlcv_absorption_field_on_filtered_"
                "governed_space_trend_pool"
            ),
            "hypothesis": (
                "Governed Space trend candidates that miss the accepted "
                "high-close/thrust route may still have additive default-off "
                "paper value when signal-day price action shows low-thrust "
                "orderly absorption with positive open-close return, moderate "
                "close-location, tight range, and institutional dollar volume."
            ),
            "prediction": {
                "success_probability": predicted_success_probability,
                "expected_ev_delta": 0.15,
                "expected_pnl_delta": 3000.0,
                "main_failure_modes": [
                    "thin_sample",
                    "current_accepted_comparator_regression",
                    "price_threshold_overfit",
                    "filtered_pool_negative_base_rate",
                ],
                "confidence_reason": (
                    "Recent Space history rejects nearby support/scalar retunes; "
                    "filtered trend rows have only a small low-thrust positive "
                    "pocket, so prior is low but the field is production-visible "
                    "and orthogonal to LLM data limits."
                ),
                "recorded_at": timestamp,
            },
            "calibration": {
                "actual_success": actual_success,
                "actual_decision": decision,
                "predicted_success_probability": predicted_success_probability,
                "brier_score": space_base._round(brier_score, 4),
                "calibration_direction": (
                    "underconfident" if actual_success else "overconfident"
                ),
                "actual_ev_delta_vs_current_accepted": (
                    accepted_comparison["aggregate_expected_value_score_delta"]
                ),
                "actual_pnl_delta_vs_current_accepted": (
                    accepted_comparison["aggregate_total_pnl_delta"]
                ),
            },
            "parameters": {
                "base_notional_usd": BASE_NOTIONAL_USD,
                "target_strategy": TARGET_STRATEGY,
                "target_tickers": payload["parameters"]["target_tickers"],
                "target_sector_map": TARGET_SECTOR_MAP,
                "accepted_baseline_experiment_id": ACCEPTED_BASELINE_EXPERIMENT_ID,
                "source_universe_state": _repo_rel(SOURCE_UNIVERSE_STATE),
                "source_ohlcv_experiment_id": SOURCE_OHLCV_EXPERIMENT_ID,
                "min_signal_day_close_location": MIN_SIGNAL_DAY_CLOSE_LOCATION,
                "max_signal_day_close_location": MAX_SIGNAL_DAY_CLOSE_LOCATION,
                "min_signal_day_open_close_return": MIN_SIGNAL_DAY_OPEN_CLOSE_RETURN,
                "max_signal_day_open_close_return": MAX_SIGNAL_DAY_OPEN_CLOSE_RETURN,
                "max_signal_day_range_pct": MAX_SIGNAL_DAY_RANGE_PCT,
                "min_signal_day_dollar_volume": MIN_SIGNAL_DAY_DOLLAR_VOLUME,
                "hard_min_ev_delta_vs_accepted_pct": HARD_MIN_EV_DELTA_VS_ACCEPTED_PCT,
                "rule_version": RULE_VERSION,
                "locked_variables": [
                    "core signal rules",
                    "core ranking",
                    "core sizing",
                    "core exits",
                    "portfolio heat",
                    "slot rules",
                    "LLM/news replay",
                    "production watchlists",
                    "live/default orders",
                    "target governed Space ticker list",
                    "accepted high-close/thrust trend branch",
                    "accepted ARKX/UFO breakout complement admission",
                    "accepted Space cost/liquidity support helper",
                ],
                "anti_js": "No JavaScript was used.",
            },
            "gate_questions": {
                "1_alpha_hypothesis": (
                    "entry/candidate_pool: governed Space trend_long candidates "
                    "that miss the current accepted route may still have "
                    "replacement value when signal-day OHLCV shows low-thrust "
                    "orderly absorption."
                ),
                "2_history_check": {
                    "exp-20260528-026": (
                        "Accepted broad Space trend high-close route; this does "
                        "not retune its threshold and only tests non-overlapping "
                        "lower-close-location absorption candidates."
                    ),
                    "exp-20260529-020": (
                        "Accepted intraday-thrust requirement; this tests a "
                        "different low-thrust band and compares against the "
                        "later accepted stack."
                    ),
                    "exp-20260531-022": "Accepted ARKX>UFO breakout complement.",
                    "exp-20260602-025": "Current accepted Space comparator.",
                    "exp-20260604-018": (
                        "Rejected defense-budget branch due zero incremental "
                        "branch trades."
                    ),
                    "exp-20260604-019": (
                        "Rejected satellite-connectivity selected support due "
                        "accepted-comparator regression and hard-min failure."
                    ),
                    "exp-20260605-012": (
                        "Rejected activation readiness: official cohorts still "
                        "lack positive same-theme 10d replacement value."
                    ),
                    "llm_soft_ranking": (
                        "Skipped because replay-safe Space semantic ranking rows "
                        "and closed same-theme replacement outcomes remain sparse."
                    ),
                },
                "3_single_causal_variable": CHANGED_VARIABLE,
                "4_acceptance_standard": (
                    "Same docs/backtesting.md three-window Space replay; compare "
                    "after to accepted exp-20260602-025; state-surface hard "
                    "minimum requires aggregate EV delta greater than 10% of "
                    "accepted EV, no regressed EV/PnL windows, survival above "
                    "5%, and positive incremental branch sample across at least "
                    "two windows."
                ),
                "5_reproducibility": (
                    ".venv\\Scripts\\python.exe quant\\experiments\\"
                    "exp_20260605_025_space_low_thrust_orderly_absorption_trend_pool.py"
                ),
            },
            "accepted_baseline_comparison": accepted_comparison,
            "incremental_branch_summary": branch_summary,
            "gate2": {
                **payload["gate2"],
                "runtime_fields": [
                    "operator_inputs/open_positions.json entry_date",
                    "operator_inputs/open_positions.json target_price",
                    "target OHLCV rows in all three Space replay snapshots",
                    "existing signal strategy field generated before next-open paper entry",
                    "signal-day close/open/high/low/volume fields",
                    "shared Space cost/liquidity dollar-volume field",
                ],
            },
            "gate3": {
                **payload["gate3"],
                "candidate_pool_changed": True,
                "minimum_core_survival_rate": space_base._round(min_survival, 4),
                "note": (
                    "No new core filter or live production filter was added. The "
                    "experiment changes only default-off paper candidate-pool "
                    "membership for governed Space rows."
                ),
            },
            "gate4": {
                **payload["gate4"],
                "acceptance_rule": (
                    "Accepted comparator must be exp-20260602-025; hard-min EV "
                    "delta must exceed 10% of accepted aggregate EV."
                ),
                "passed": gate4_passed,
                "base_gate4_passed": base_gate4_passed,
                "soft_current_accepted_improved": soft_current_accepted_improved,
                "hard_min_ev_delta_passed": accepted_comparison[
                    "hard_min_ev_delta_passed"
                ],
                "incremental_branch_sample_passed": branch_sample_passed,
                "aggregate_expected_value_score_delta": aggregate[
                    "expected_value_score_delta_sum"
                ],
                "aggregate_total_pnl_delta": aggregate["total_pnl_delta_sum"],
            },
            "production_impact": {
                "shared_policy_changed": False,
                "backtester_adapter_changed": False,
                "run_adapter_changed": False,
                "replay_only": True,
                "parity_test_added": False,
                "default_off_paper_only": True,
                "metadata_only": True,
                "production_feature_fields_used": [
                    "signal_day_close_location",
                    "signal_day_open_close_return",
                    "signal_day_range_pct",
                    "signal_day_dollar_volume",
                ],
                "production_watchlist_changed": False,
                "production_orders_changed": False,
                "production_ranking_changed": False,
                "production_sizing_changed": False,
                "production_exits_changed": False,
                "trade_enabled": False,
                "live_space_slots": 0,
            },
            "interpretation": (
                "Accepted: the low-thrust orderly absorption branch cleared the "
                "current accepted Space comparator and the hard-min state-surface "
                "Gate 4. A separate shared-helper/parity promotion would still be "
                "required before any production exposure."
                if gate4_passed
                else (
                    "Rejected: low-thrust orderly absorption did not clear the "
                    "current accepted Space comparator and hard-min Gate 4. Do "
                    "not promote or retune this OHLCV pocket on the frozen windows."
                )
            ),
            "next_evidence_needed": (
                "Stop optimizing low-thrust Space price-action pockets on these "
                "windows; collect forward replacement-value rows by official "
                "catalyst/source bucket or add a genuinely new production-visible "
                "catalyst-quality field."
            ),
            "related_files": [
                _repo_rel(Path(__file__)),
                _repo_rel(OUT_JSON),
                _repo_rel(LOG_JSON),
                _repo_rel(TICKET_JSON),
                _repo_rel(CARD_MD),
                _repo_rel(MANIFEST_JSON),
                _repo_rel(EXPERIMENT_LOG),
                _repo_rel(REGISTRY_JSON),
                _repo_rel(ACCEPTED_BASELINE_JSON),
            ],
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["rejection_reason"] = None if gate4_passed else (
        "failed_current_accepted_comparator_or_space_hard_min"
    )
    return payload


def _build_report(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | Survival | Target trades | Filtered |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {surv:.4f} | {trades} | {filtered} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                surv=after["survival_rate"],
                trades=len(payload["target_trades_by_window"][label]),
                filtered=len(payload["filtered_out_target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    accepted_delta = payload["accepted_baseline_comparison"]
    branch = payload["incremental_branch_summary"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Space Low-Thrust Orderly Absorption Trend Pool",
            "",
            f"Decision: `{payload['decision']}`.",
            "",
            "Single variable: admit only governed Space `trend_long` rows that miss the accepted route and show low-thrust orderly absorption on signal-day OHLCV.",
            "",
            "## Three-Window Result",
            "",
            *rows,
            "",
            "## Aggregate Versus Core",
            "",
            f"- EV delta: `{aggregate['expected_value_score_delta_sum']}` (`{aggregate['expected_value_score_delta_pct']}`)",
            f"- PnL delta: `${aggregate['total_pnl_delta_sum']}` (`{aggregate['total_pnl_delta_pct']}`)",
            f"- target trades: `{payload['target_trade_summary']['total_trade_count']}` across `{len(payload['target_trade_summary']['windows_with_target_trades'])}` windows",
            "",
            "## Incremental Versus Accepted Space Route",
            "",
            f"- baseline: `{accepted_delta['baseline_experiment_id']}`",
            f"- EV delta: `{accepted_delta['aggregate_expected_value_score_delta']}`",
            f"- required EV delta: `{accepted_delta['hard_min_ev_delta_vs_accepted']}`",
            f"- PnL delta: `${accepted_delta['aggregate_total_pnl_delta']}`",
            f"- EV-regressed windows: `{accepted_delta['windows_ev_regressed']}`",
            f"- PnL-regressed windows: `{accepted_delta['windows_pnl_regressed']}`",
            f"- incremental branch trades: `{branch['incremental_trade_count']}`",
            f"- incremental branch windows: `{', '.join(branch['incremental_windows'])}`",
            f"- incremental branch PnL: `${branch['incremental_total_pnl']}`",
            f"- incremental branch win rate: `{branch['incremental_win_rate']}`",
            "",
            "## Gate 4",
            "",
            "```json",
            json.dumps(payload["gate4"], indent=2, sort_keys=True),
            "```",
            "",
            "## Production Impact",
            "",
            "Replay-only and default-off paper only. No live orders, ranking, sizing, exits, watchlists, shared production helpers, or Space slots changed.",
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _update_ticket_and_registry(payload: dict[str, Any]) -> None:
    ticket = {}
    if TICKET_JSON.exists():
        ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
    ticket.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "lane": "alpha_search",
            "owner": "alpha-search-space",
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "mechanism_family": "production_visible_default_off_space_candidate_pool_alpha",
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "prior_trial_count": payload["prior_trial_count"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "prediction": payload["prediction"],
            "calibration": payload["calibration"],
            "completed_at": payload["timestamp"],
            "result": {
                "artifact": _repo_rel(CARD_MD),
                "decision": payload["decision"],
                "expected_value_score_delta": payload["expected_value_score_delta"],
                "json": _repo_rel(OUT_JSON),
                "summary": payload["interpretation"],
                "total_pnl_delta": payload["total_pnl_delta"],
            },
        }
    )
    space_base._write_json(TICKET_JSON, ticket)

    if REGISTRY_JSON.exists():
        registry = json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))
        entry = {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "lane": "alpha_search",
            "owner": "alpha-search-space",
            "hypothesis": payload["hypothesis"],
            "ticket_file": f"experiments/tickets/{EXPERIMENT_ID}.json",
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        experiments = registry.setdefault("experiments", [])
        for index, existing in enumerate(experiments):
            if existing.get("experiment_id") == EXPERIMENT_ID:
                experiments[index] = {**existing, **entry}
                break
        else:
            experiments.append(entry)
        REGISTRY_JSON.write_text(
            json.dumps(registry, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )


def _update_manifest(payload: dict[str, Any]) -> None:
    manifest = {}
    if MANIFEST_JSON.exists():
        manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
    manifest.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "files": {
                **(manifest.get("files") or {}),
                "runner": {"path": f"quant/experiments/{STEM}.py", "exists": True},
                "data": {"path": _repo_rel(OUT_JSON), "exists": OUT_JSON.exists()},
                "log": {"path": _repo_rel(LOG_JSON), "exists": LOG_JSON.exists()},
                "card": {"path": _repo_rel(CARD_MD), "exists": CARD_MD.exists()},
                "ticket": {"path": _repo_rel(TICKET_JSON), "exists": TICKET_JSON.exists()},
            },
            "result": {
                "decision": payload["decision"],
                "json": _repo_rel(OUT_JSON),
                "card": _repo_rel(CARD_MD),
            },
        }
    )
    space_base._write_json(MANIFEST_JSON, manifest)


def _persist(payload: dict[str, Any]) -> None:
    space_base._write_json(OUT_JSON, payload)
    space_base._write_json(LOG_JSON, payload)
    space_base._write_text(CARD_MD, _build_report(payload))
    space_base._upsert_jsonl(EXPERIMENT_LOG, payload)
    _update_ticket_and_registry(payload)
    _update_manifest(payload)


def main() -> int:
    _configure_source_runner()
    payload = _customize_payload(space_base._build_payload())
    _persist(payload)
    print(
        json.dumps(
            space_base._safe(
                {
                    "experiment_id": payload["experiment_id"],
                    "decision": payload["decision"],
                    "expected_value_score_delta": payload["expected_value_score_delta"],
                    "total_pnl_delta": payload["total_pnl_delta"],
                    "accepted_baseline_comparison": payload[
                        "accepted_baseline_comparison"
                    ],
                    "incremental_branch_summary": payload["incremental_branch_summary"],
                    "gate4": payload["gate4"],
                    "card": _repo_rel(CARD_MD),
                    "anti_js": payload["anti_js"],
                }
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
