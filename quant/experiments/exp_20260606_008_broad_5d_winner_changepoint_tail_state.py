"""exp-20260606-008: changepoint/tail-state broad 5-day winner continuation.

Replay-only alpha search. This follows the rejected exp-20260606-005 broad
5-day market-confirmed winner-continuation source, but admits candidates only
when the signal date is not a free-OHLCV changepoint/tail-pressure state:
SPY 20-day realized volatility is not expanded versus 60-day realized
volatility, SPY has no large signal-day shock, and the broad liquid
cross-section has no high down/tail-down fraction.

The only alpha variable is the production-visible changepoint/tail-pressure
state gate. Ticker pool, market confirmation, top-bucket construction,
next-open entry, hold, notional, cooldown, core-overlap controls, LLM/news
behavior, and production code stay unchanged. No JavaScript is used.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import exp_20260606_005_broad_5d_winner_market_confirmed_continuation as previous
import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework


EXPERIMENT_ID = "exp-20260606-008"
STEM = "broad_5d_winner_changepoint_tail_state"
TRIAL_FAMILY = "broad_full_liquid_5d_winner_changepoint_tail_state_candidate_pool"
TRIAL_VARIANT_ID = "no_spy_vol_expansion_no_cross_section_tail_pressure_v1"
CHANGED_VARIABLE = "broad_5d_winner_no_changepoint_tail_pressure_state_v1"
RULE_VERSION = "broad_5d_winner_changepoint_tail_state_v1"

REPO_ROOT = previous.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260606_008_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

SPY_REALIZED_VOL_LOOKBACK = 20
SPY_VOL_BASELINE_LOOKBACK = 60
MAX_SPY_VOL_RATIO_20_TO_60 = 1.15
MAX_SPY_ABS_SIGNAL_DAY_RETURN = 0.025
MAX_CROSS_SECTION_DOWN_FRACTION = 0.62
MAX_CROSS_SECTION_TAIL_DOWN_FRACTION = 0.20
TAIL_DOWN_RETURN = -0.03
MIN_CONTEXT_LIQUID_COUNT = 250

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.80,
    "expected_pnl_delta": 12000.0,
    "main_failure_modes": [
        "drawdown_drift_too_high",
        "window_regression",
        "thin_sample",
        "ohlcv_momentum_relabeling",
    ],
    "confidence_reason": (
        "exp-20260606-005 improved EV/PnL in all three windows but failed "
        "drawdown; the playbook allows another broad 5-day continuation retry "
        "only with a materially new PIT state such as changepoint/tail "
        "persistence, which this tests."
    ),
    "recorded_at": "2026-06-06T07:02:12Z",
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
        "This experiment changes no production code. A positive result is not "
        "production-promoted: it would require a shared default-off adapter "
        "that computes the same broad warehouse full-liquid stock universe, "
        "SPY 5-day market confirmation, candidate 20-day trend state, SPY "
        "20/60 realized-volatility ratio, SPY signal-day shock guard, broad "
        "cross-section down/tail-down fractions, 5-day SPY-relative rank, "
        "next-open paper entry, 10-trading-day exit, costs, cooldown, and "
        "core-overlap controls in both replay and daily production before any "
        "report queue, paper ledger, candidate priority, sizing, watchlist, "
        "or order surface could change."
    ),
}

BASE_CANDIDATE_ROWS = previous._candidate_rows_for_window
BASE_GATE4 = previous._gate4
BASE_BUILD_PAYLOAD = previous._build_payload


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _state_for_day(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    signal_date: str,
) -> dict[str, Any] | None:
    spy_rows = snapshot.get("SPY") or []
    spy_idx = indices.get("SPY", {}).get(signal_date)
    if spy_idx is None:
        return None

    spy_daily = framework._daily_return(spy_rows, spy_idx)
    spy_vol20 = framework._realized_vol(spy_rows, spy_idx, SPY_REALIZED_VOL_LOOKBACK)
    spy_vol60 = framework._realized_vol(spy_rows, spy_idx, SPY_VOL_BASELINE_LOOKBACK)
    if spy_daily is None or spy_vol20 is None or spy_vol60 is None or spy_vol60 <= 0:
        return None

    returns: list[float] = []
    for ticker in sorted(sector_entries):
        rows = snapshot.get(ticker) or []
        idx = indices.get(ticker, {}).get(signal_date)
        if idx is None or idx < SPY_REALIZED_VOL_LOOKBACK:
            continue
        close = framework._value(rows[idx], "Close")
        if close is None or close < framework.MIN_PRICE:
            continue
        adv20 = framework._avg_dollar_volume(rows, idx, SPY_REALIZED_VOL_LOOKBACK)
        if adv20 is None or adv20 < framework.MIN_AVG_DOLLAR_VOLUME_20D:
            continue
        daily_return = framework._daily_return(rows, idx)
        if daily_return is not None:
            returns.append(float(daily_return))

    if len(returns) < MIN_CONTEXT_LIQUID_COUNT:
        return None

    down_fraction = sum(1 for value in returns if value < 0.0) / len(returns)
    tail_down_fraction = sum(1 for value in returns if value <= TAIL_DOWN_RETURN) / len(
        returns
    )
    spy_vol_ratio = spy_vol20 / spy_vol60
    passed = (
        spy_vol_ratio <= MAX_SPY_VOL_RATIO_20_TO_60
        and abs(spy_daily) <= MAX_SPY_ABS_SIGNAL_DAY_RETURN
        and down_fraction <= MAX_CROSS_SECTION_DOWN_FRACTION
        and tail_down_fraction <= MAX_CROSS_SECTION_TAIL_DOWN_FRACTION
    )
    return {
        "date": signal_date,
        "passed": passed,
        "liquid_universe_count": len(returns),
        "spy_signal_day_return": framework._round(spy_daily, 6),
        "spy_abs_signal_day_return": framework._round(abs(spy_daily), 6),
        "spy_realized_vol_20": framework._round(spy_vol20, 6),
        "spy_realized_vol_60": framework._round(spy_vol60, 6),
        "spy_vol_ratio_20_to_60": framework._round(spy_vol_ratio, 6),
        "cross_section_down_fraction": framework._round(down_fraction, 6),
        "cross_section_tail_down_fraction": framework._round(tail_down_fraction, 6),
        "tail_down_return": TAIL_DOWN_RETURN,
        "rule_version": RULE_VERSION,
    }


def _reject_reason_for_state(state: dict[str, Any]) -> str:
    if float(state["spy_vol_ratio_20_to_60"]) > MAX_SPY_VOL_RATIO_20_TO_60:
        return "spy_vol_expansion"
    if float(state["spy_abs_signal_day_return"]) > MAX_SPY_ABS_SIGNAL_DAY_RETURN:
        return "spy_signal_day_shock"
    if float(state["cross_section_tail_down_fraction"]) > MAX_CROSS_SECTION_TAIL_DOWN_FRACTION:
        return "cross_section_tail_pressure"
    if float(state["cross_section_down_fraction"]) > MAX_CROSS_SECTION_DOWN_FRACTION:
        return "cross_section_down_pressure"
    return "changepoint_tail_state_failed"


def _candidate_rows_for_window(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    cfg: dict[str, str],
    before_result: dict[str, Any],
    sector_entries: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidates, contexts, scan = BASE_CANDIDATE_ROWS(
        snapshot=snapshot,
        cfg=cfg,
        before_result=before_result,
        sector_entries=sector_entries,
    )
    indices = {
        ticker: framework.shadow._row_index(rows) for ticker, rows in snapshot.items()
    }
    states_by_date: dict[str, dict[str, Any] | None] = {}
    kept: list[dict[str, Any]] = []
    rejects: Counter[str] = Counter()

    for candidate in candidates:
        signal_date = str(candidate.get("date") or "")
        if signal_date not in states_by_date:
            states_by_date[signal_date] = _state_for_day(
                snapshot=snapshot,
                indices=indices,
                sector_entries=sector_entries,
                signal_date=signal_date,
            )
        state = states_by_date[signal_date]
        if state is None:
            rejects["missing_changepoint_tail_state"] += 1
            continue
        if not state["passed"]:
            rejects[_reject_reason_for_state(state)] += 1
            continue
        row = dict(candidate)
        row.update(
            {
                "source": STEM,
                "strategy": STEM,
                "rule_version": RULE_VERSION,
                "changepoint_tail_state": "no_spy_vol_expansion_no_cross_section_tail_pressure",
                "changepoint_tail_rule_version": RULE_VERSION,
                "spy_realized_vol_20": state["spy_realized_vol_20"],
                "spy_realized_vol_60": state["spy_realized_vol_60"],
                "spy_vol_ratio_20_to_60": state["spy_vol_ratio_20_to_60"],
                "spy_abs_signal_day_return": state["spy_abs_signal_day_return"],
                "cross_section_down_fraction": state["cross_section_down_fraction"],
                "cross_section_tail_down_fraction": state[
                    "cross_section_tail_down_fraction"
                ],
                "liquid_universe_count": state["liquid_universe_count"],
            }
        )
        kept.append(row)

    state_values = [state for state in states_by_date.values() if state is not None]
    passed_states = [state for state in state_values if state["passed"]]
    scan = dict(scan)
    scan["changepoint_tail_state_reject_counts"] = dict(sorted(rejects.items()))
    scan["changepoint_tail_state_kept_candidates"] = len(kept)
    scan["changepoint_tail_state_candidate_count_before_gate"] = len(candidates)
    scan["changepoint_tail_state_eval_day_count"] = len(state_values)
    scan["changepoint_tail_state_pass_day_count"] = len(passed_states)
    scan["changepoint_tail_rule_version"] = RULE_VERSION
    scan["max_spy_vol_ratio_20_to_60"] = MAX_SPY_VOL_RATIO_20_TO_60
    scan["max_spy_abs_signal_day_return"] = MAX_SPY_ABS_SIGNAL_DAY_RETURN
    scan["max_cross_section_down_fraction"] = MAX_CROSS_SECTION_DOWN_FRACTION
    scan["max_cross_section_tail_down_fraction"] = MAX_CROSS_SECTION_TAIL_DOWN_FRACTION
    scan["min_context_liquid_count"] = MIN_CONTEXT_LIQUID_COUNT
    return kept, passed_states, scan


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
    gate["decision"] = (
        "positive_replay_lead_not_promoted_broad_5d_changepoint_tail_state"
        if gate["passed"]
        else "rejected_broad_5d_changepoint_tail_state_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "Broad 5-day market-confirmed winner continuation may become "
                "executable when entries are restricted to non-changepoint, "
                "non-tail-pressure market states computed from free OHLCV "
                "breadth and SPY realized volatility, preserving "
                "exp-20260606-005 upside while reducing drawdown."
            ),
            "change_type": "default_off_candidate_pool_state_gate",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "short_formation_continuation_changepoint_tail_state",
            "new_evidence_type": "materially_new_production_visible_ohlcv_changepoint_tail_state",
            "nearby_prior_experiments": [
                "exp-20260605-033",
                "exp-20260606-004",
                "exp-20260606-005",
                "exp-20260606-006",
                "exp-20260606-007",
            ],
            "prior_trial_count": 5,
            "multiple_testing_risk_bucket": "high",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "anti_js": "No JavaScript was used.",
            "negative_reflection": (
                "If rejected, the likely reason is that exp-20260606-005's "
                "broad OHLCV winner continuation is not made production-worthy "
                "by simple volatility/tail-state avoidance: the drawdown may "
                "come from ordinary extended-winner mean reversion or from a "
                "sample that becomes too thin after state gating. Do not "
                "respond by retuning SPY5, candidate ret20, top-N, hold days, "
                "notional, cooldown, or these volatility/tail thresholds on "
                "the same frozen windows."
            ),
            "next_evidence_needed": (
                "A future retry needs genuinely new PIT evidence such as "
                "forward replacement-value rows, external free breadth data "
                "with production parity, or a non-OHLCV context layer. Broad "
                "5-day continuation threshold retunes should stay frozen."
            ),
        }
    )
    payload.setdefault("parameters", {}).update(
        {
            "changepoint_tail_state": "no_spy_vol_expansion_no_cross_section_tail_pressure",
            "spy_realized_vol_lookback": SPY_REALIZED_VOL_LOOKBACK,
            "spy_vol_baseline_lookback": SPY_VOL_BASELINE_LOOKBACK,
            "max_spy_vol_ratio_20_to_60": MAX_SPY_VOL_RATIO_20_TO_60,
            "max_spy_abs_signal_day_return": MAX_SPY_ABS_SIGNAL_DAY_RETURN,
            "max_cross_section_down_fraction": MAX_CROSS_SECTION_DOWN_FRACTION,
            "max_cross_section_tail_down_fraction": MAX_CROSS_SECTION_TAIL_DOWN_FRACTION,
            "tail_down_return": TAIL_DOWN_RETURN,
            "min_context_liquid_count": MIN_CONTEXT_LIQUID_COUNT,
            "single_causal_variable": CHANGED_VARIABLE,
            "locked_from_exp_20260606_005": [
                "all_windows_full_liquid_common_stock_proxy",
                "formation_days",
                "top_bucket_fraction",
                "top_bucket_ranking",
                "market_confirmation_state",
                "paper_notional_usd",
                "hold_days",
                "max_paper_trades_per_day",
                "same_ticker_cooldown_days",
                "same_ticker_core_overlap_exclusion",
                "min_price",
                "min_avg_dollar_volume_20d",
            ],
        }
    )
    payload["pre_run_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: the exp-20260606-005 broad 5-day "
            "market-confirmed winner source may only be tradable outside "
            "free-OHLCV changepoint/tail-pressure states. This follows the "
            "playbook's requirement for materially new PIT state rather than "
            "another local threshold retune."
        ),
        "2_history_check": {
            "exp-20260606-005": (
                "Rejected: aggregate EV +2.3453 and PnL +$36,495.37 with all "
                "windows positive, but max drawdown worsened +2.97pp."
            ),
            "exp-20260606-004": (
                "Rejected: broad 5-day winner continuation improved aggregate "
                "EV/PnL but regressed old_thin and worsened drawdown +7.63pp."
            ),
            "exp-20260606-006": (
                "Rejected: low-deployment gate reduced but did not remove "
                "old_thin/drawdown risk."
            ),
            "exp-20260606-007": (
                "Rejected SEC credit absorption; SEC item-code near-neighbor "
                "path remains sample-thin and not the best next alpha lane."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_success_failure_criteria": (
            "Use docs/backtesting.md three canonical windows. Accept only if "
            "aggregate EV/PnL improve, no EV/PnL regression window, target "
            "sample >=20 across all 3 windows, survival >=5%, drawdown drift "
            "<=0.5pp, and concentration guard passes."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260606_008_broad_5d_winner_changepoint_tail_state.py"
        ),
    }
    payload["gate_questions"] = payload["pre_run_questions"]
    payload["decision"] = payload["gate4"]["decision"]
    payload["status"] = "accepted" if payload["gate4"]["passed"] else "rejected"
    payload["interpretation"] = (
        "The changepoint/tail-state broad winner-continuation source cleared "
        "Gate 4 as a replay-only/default-off lead, but no production surface "
        "was promoted. A shared parity adapter is required before use."
        if payload["gate4"]["passed"]
        else (
            "The changepoint/tail-state broad winner-continuation source did "
            "not clear Gate 4; do not promote or locally retune this broad "
            "OHLCV momentum family on the frozen windows."
        )
    )
    payload["rejection_reason"] = (
        None if payload["gate4"]["passed"] else "; ".join(payload["gate4"]["failed_reasons"])
    )
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
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | State-pass days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {days} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                dd=delta.get("max_drawdown_pct", 0.0),
                days=scan.get("changepoint_tail_state_pass_day_count", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Broad 5D Winner Changepoint/Tail State",
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
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
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
        "accepted": payload["gate4"]["passed"],
        "mechanism_family": "production_visible_free_ohlcv_candidate_pool",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/experiments/exp-20260602-003/"
            "exp_20260602_003_post_earnings_explicit_continuation.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
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
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "changepoint_tail_state_pass_day_count": payload[
                    "context_scan_by_window"
                ][label].get("changepoint_tail_state_pass_day_count"),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": {**payload["calibration"]},
        "production_impact": PRODUCTION_IMPACT,
        "negative_reflection": payload["negative_reflection"],
        "anti_js": "No JavaScript was used.",
    }


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
    framework.PREDICTION = PREDICTION
    framework.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    framework._candidate_rows_for_window = _candidate_rows_for_window
    framework._gate4 = _gate4
    framework._build_payload = _build_payload
    framework._build_card = _build_card
    framework._build_log_record = _build_log_record


_patch_framework()


def main() -> None:
    framework.main()


if __name__ == "__main__":
    main()
