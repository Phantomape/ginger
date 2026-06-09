"""exp-20260609-022: VIXY/VIXM term-relief stock leadership scout.

Replay-only alpha search. This tests one production-visible free-OHLCV
candidate-source variable: accepted VIXY volatility-relief stock leadership is
admitted only when front-end VIXY declines materially more than VIXM, proxying
term-structure normalization rather than generic risk-on beta.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import exp_20260607_018_volatility_relief_stock_leadership as previous


framework = previous.framework
macro_base = previous.previous

EXPERIMENT_ID = "exp-20260609-022"
STEM = "vixy_vixm_term_relief_leadership"
TRIAL_FAMILY = "volatility_term_structure_relief_candidate_pool"
TRIAL_VARIANT_ID = "vixy_vixm_front_end_vol_crush_top2_10d_v1"
CHANGED_VARIABLE = "vixy_vixm_front_end_vol_crush_stock_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = previous.REPO_ROOT
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260609_022_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = previous.BASE_NOTIONAL_USD
HOLD_DAYS = previous.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = previous.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = previous.SAME_TICKER_COOLDOWN_DAYS

MAX_VIXY_RELIEF_RETURN = previous.MAX_VIXY_RELIEF_RETURN
MAX_VIXY_CLOSE_LOCATION = previous.MAX_VIXY_CLOSE_LOCATION
MAX_VIXM_RELIEF_RETURN = -0.005
MAX_VIXM_CLOSE_LOCATION = 0.60
MIN_VIXY_UNDERPERFORMANCE_VS_VIXM = 0.015
MIN_SPY_RELIEF_RETURN = previous.MIN_SPY_RELIEF_RETURN
MIN_QQQ_RELIEF_RETURN = previous.MIN_QQQ_RELIEF_RETURN
MIN_SPY_CLOSE_LOCATION = previous.MIN_SPY_CLOSE_LOCATION
MIN_QQQ_CLOSE_LOCATION = previous.MIN_QQQ_CLOSE_LOCATION
MIN_PRICE = previous.MIN_PRICE
MIN_AVG_DOLLAR_VOLUME_20D = previous.MIN_AVG_DOLLAR_VOLUME_20D
MIN_SIGNAL_RETURN = previous.MIN_SIGNAL_RETURN
MIN_RELATIVE_VS_SPY = previous.MIN_RELATIVE_VS_SPY
MIN_RELATIVE_VS_QQQ = previous.MIN_RELATIVE_VS_QQQ
MIN_CLOSE_LOCATION = previous.MIN_CLOSE_LOCATION
MIN_VOLUME_RATIO_20D = previous.MIN_VOLUME_RATIO_20D
MIN_RET20_EXCESS_SPY = previous.MIN_RET20_EXCESS_SPY
MIN_RET60_EXCESS_SPY = previous.MIN_RET60_EXCESS_SPY
MIN_RET5 = previous.MIN_RET5
MAX_RET5 = previous.MAX_RET5
MAX_REALIZED_VOL_20D = previous.MAX_REALIZED_VOL_20D

MIN_TARGET_TRADES = previous.MIN_TARGET_TRADES
MIN_TARGET_WINDOWS = previous.MIN_TARGET_WINDOWS
MAX_DRAWDOWN_WORSE = previous.MAX_DRAWDOWN_WORSE
MAX_SINGLE_POSITIVE_SHARE = previous.MAX_SINGLE_POSITIVE_SHARE
MAX_POSITIVE_HHI = previous.MAX_POSITIVE_HHI

ACCEPTED_VOL_RELIEF_COMPARATOR = {
    "experiment_id": "exp-20260607-019",
    "decision": "accepted_volatility_relief_stock_leadership_shared_default_off_adapter",
    "expected_value_score_delta_sum": 0.5732,
    "total_pnl_delta_sum": 11934.79,
    "target_trade_count": 88,
    "by_window": {
        "late_strong": {"expected_value_score_delta": 0.2388, "total_pnl_delta": 2165.40},
        "mid_weak": {"expected_value_score_delta": 0.2173, "total_pnl_delta": 4898.38},
        "old_thin": {"expected_value_score_delta": 0.1171, "total_pnl_delta": 4871.01},
    },
}

PREDICTION = {
    "success_probability": 0.12,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "accepted_volatility_relief_comparator_not_beaten",
        "thin_sample",
        "window_regression",
        "drawdown_drift",
        "broad_beta_relabel",
    ],
    "confidence_reason": (
        "Accepted VIXY-only relief leadership worked, but recent extra "
        "confirmations failed; VIXM adds a distinct free OHLCV term-structure "
        "field, so probability is low and comparator discipline is strict."
    ),
    "recorded_at": "2026-06-09T18:05:57+00:00",
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
        "positive result would require a shared default-off adapter computing "
        "the same VIXY/VIXM/SPY/QQQ term-relief context, liquid stock "
        "leadership fields, same-ticker core-overlap exclusion, next-open "
        "paper entry, 10-trading-day exit, costs, cooldown, accepted "
        "volatility-relief comparator checks, and concentration controls in "
        "both historical replay and daily production before any report queue, "
        "paper ledger, candidate priority, sizing, watchlist, or order surface "
        "could change."
    ),
}

BASE_LOAD_WINDOW_SNAPSHOT = previous.BASE_LOAD_WINDOW_SNAPSHOT
BASE_GATE4 = previous.BASE_GATE4
BASE_PERSIST = previous.BASE_PERSIST
BASE_PREVIOUS_BUILD_PAYLOAD = previous._build_payload


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _load_window_snapshot(
    *,
    cfg: dict[str, str],
    eligible_tickers: set[str],
) -> dict[str, list[dict[str, Any]]]:
    return BASE_LOAD_WINDOW_SNAPSHOT(
        cfg=cfg,
        eligible_tickers=set(eligible_tickers) | {"VIXY", "VIXM"},
    )


def _relief_context_for_day(
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    signal_date: str,
) -> dict[str, Any] | None:
    vixy_rows = snapshot.get("VIXY") or []
    vixm_rows = snapshot.get("VIXM") or []
    spy_rows = snapshot.get("SPY") or []
    qqq_rows = snapshot.get("QQQ") or []
    vixy_idx = indices.get("VIXY", {}).get(signal_date)
    vixm_idx = indices.get("VIXM", {}).get(signal_date)
    spy_idx = indices.get("SPY", {}).get(signal_date)
    qqq_idx = indices.get("QQQ", {}).get(signal_date)
    if vixy_idx is None or vixm_idx is None or spy_idx is None or qqq_idx is None:
        return None

    vixy_return = framework._daily_return(vixy_rows, vixy_idx)
    vixm_return = framework._daily_return(vixm_rows, vixm_idx)
    spy_return = framework._daily_return(spy_rows, spy_idx)
    qqq_return = framework._daily_return(qqq_rows, qqq_idx)
    vixy_close_location = previous._range_location(vixy_rows[vixy_idx])
    vixm_close_location = previous._range_location(vixm_rows[vixm_idx])
    spy_close_location = previous._range_location(spy_rows[spy_idx])
    qqq_close_location = previous._range_location(qqq_rows[qqq_idx])
    vixy_underperformance_vs_vixm = None
    if vixy_return is not None and vixm_return is not None:
        vixy_underperformance_vs_vixm = vixm_return - vixy_return
    context = {
        "date": signal_date,
        "vixy_return": framework._round(vixy_return, 6),
        "vixm_return": framework._round(vixm_return, 6),
        "spy_return": framework._round(spy_return, 6),
        "qqq_return": framework._round(qqq_return, 6),
        "vixy_close_location": framework._round(vixy_close_location, 6),
        "vixm_close_location": framework._round(vixm_close_location, 6),
        "spy_close_location": framework._round(spy_close_location, 6),
        "qqq_close_location": framework._round(qqq_close_location, 6),
        "vixy_underperformance_vs_vixm": framework._round(
            vixy_underperformance_vs_vixm,
            6,
        ),
        "max_vixy_relief_return": MAX_VIXY_RELIEF_RETURN,
        "max_vixy_close_location": MAX_VIXY_CLOSE_LOCATION,
        "max_vixm_relief_return": MAX_VIXM_RELIEF_RETURN,
        "max_vixm_close_location": MAX_VIXM_CLOSE_LOCATION,
        "min_vixy_underperformance_vs_vixm": MIN_VIXY_UNDERPERFORMANCE_VS_VIXM,
        "min_spy_relief_return": MIN_SPY_RELIEF_RETURN,
        "min_qqq_relief_return": MIN_QQQ_RELIEF_RETURN,
        "min_spy_close_location": MIN_SPY_CLOSE_LOCATION,
        "min_qqq_close_location": MIN_QQQ_CLOSE_LOCATION,
        "rule_version": RULE_VERSION,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }
    if (
        vixy_return is None
        or vixm_return is None
        or spy_return is None
        or qqq_return is None
    ):
        return {**context, "passed": False, "reason": "missing_daily_return"}
    if (
        vixy_close_location is None
        or vixm_close_location is None
        or spy_close_location is None
        or qqq_close_location is None
    ):
        return {**context, "passed": False, "reason": "missing_close_location"}
    if vixy_return > MAX_VIXY_RELIEF_RETURN:
        return {**context, "passed": False, "reason": "vixy_decline_too_small"}
    if vixy_close_location > MAX_VIXY_CLOSE_LOCATION:
        return {**context, "passed": False, "reason": "vixy_close_not_weak_enough"}
    if vixm_return > MAX_VIXM_RELIEF_RETURN:
        return {**context, "passed": False, "reason": "vixm_decline_too_small"}
    if vixm_close_location > MAX_VIXM_CLOSE_LOCATION:
        return {**context, "passed": False, "reason": "vixm_close_not_weak_enough"}
    if vixy_underperformance_vs_vixm < MIN_VIXY_UNDERPERFORMANCE_VS_VIXM:
        return {
            **context,
            "passed": False,
            "reason": "front_end_vol_crush_not_distinct_enough",
        }
    if spy_return < MIN_SPY_RELIEF_RETURN:
        return {**context, "passed": False, "reason": "spy_relief_return_too_low"}
    if qqq_return < MIN_QQQ_RELIEF_RETURN:
        return {**context, "passed": False, "reason": "qqq_relief_return_too_low"}
    if spy_close_location < MIN_SPY_CLOSE_LOCATION:
        return {**context, "passed": False, "reason": "spy_close_location_too_low"}
    if qqq_close_location < MIN_QQQ_CLOSE_LOCATION:
        return {**context, "passed": False, "reason": "qqq_close_location_too_low"}
    return {
        **context,
        "passed": True,
        "reason": "vixy_vixm_front_end_vol_crush_relief_passed",
    }


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
    failed = list(gate.get("failed_reasons") or [])
    if aggregate["expected_value_score_delta_sum"] <= ACCEPTED_VOL_RELIEF_COMPARATOR[
        "expected_value_score_delta_sum"
    ]:
        failed.append("accepted_volatility_relief_ev_not_beaten")
    if aggregate["total_pnl_delta_sum"] <= ACCEPTED_VOL_RELIEF_COMPARATOR[
        "total_pnl_delta_sum"
    ]:
        failed.append("accepted_volatility_relief_pnl_not_beaten")
    window_deltas = aggregate.get("by_window") or {}
    for label, comparator in ACCEPTED_VOL_RELIEF_COMPARATOR["by_window"].items():
        current = window_deltas.get(label) or {}
        if current.get("expected_value_score", 0.0) <= comparator[
            "expected_value_score_delta"
        ]:
            failed.append(f"accepted_volatility_relief_{label}_ev_not_beaten")
        if current.get("total_pnl", 0.0) <= comparator["total_pnl_delta"]:
            failed.append(f"accepted_volatility_relief_{label}_pnl_not_beaten")
    gate["failed_reasons"] = sorted(set(failed))
    gate["passed"] = not gate["failed_reasons"]
    gate["decision"] = (
        "positive_replay_lead_not_promoted_vixy_vixm_term_relief_leadership"
        if gate["passed"]
        else "rejected_vixy_vixm_term_relief_leadership_candidate_pool"
    )
    gate["accepted_volatility_relief_comparator"] = ACCEPTED_VOL_RELIEF_COMPARATOR
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_PREVIOUS_BUILD_PAYLOAD()
    passed = bool(payload["gate4"]["passed"])
    aggregate = payload["delta_metrics"]["aggregate"]
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "VIXY volatility-relief stock leadership may be cleaner when "
                "front-end VIXY declines materially more than VIXM, indicating "
                "term-structure normalization rather than generic risk-on beta."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_cross_asset_candidate_pool",
            "new_evidence_type": "production_visible_vixm_term_structure_context",
            "nearby_prior_experiments": [
                "exp-20260607-019",
                "exp-20260607-026",
                "exp-20260609-010",
            ],
            "prior_trial_count": 3,
            "multiple_testing_risk_bucket": "minimal",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "accepted_volatility_relief_comparator": ACCEPTED_VOL_RELIEF_COMPARATOR,
            "anti_js": "No JavaScript was used.",
            "decision": payload["gate4"]["decision"],
            "status": "positive_replay_lead_not_promoted" if passed else "rejected",
            "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
            "total_pnl_delta": aggregate["total_pnl_delta_sum"],
            "interpretation": (
                "The VIXY/VIXM term-relief stock-leadership source cleared "
                "Gate 4 and beat the accepted VIXY relief comparator as a "
                "replay-only/default-off lead, but no production surface was "
                "promoted."
                if passed
                else (
                    "The VIXY/VIXM term-relief stock-leadership source did "
                    "not clear Gate 4 or did not beat the accepted VIXY relief "
                    "comparator. Do not promote it or retune VIXY/VIXM/SPY/QQQ "
                    "thresholds on these frozen windows."
                )
            ),
            "rejection_reason": None
            if passed
            else "; ".join(payload["gate4"]["failed_reasons"]),
            "negative_reflection": (
                "If rejected, the likely reason is that the VIXM term-structure "
                "confirmation either thinned the accepted VIXY relief sample or "
                "still described generic risk-on beta rather than a stronger "
                "single-stock replacement edge after next-open execution costs."
            ),
            "post_run_reflection": {
                "why_result_happened": (
                    "The VIXM term-structure field isolated front-end vol "
                    "normalization that improved stock-leadership replacement "
                    "value beyond the accepted VIXY relief comparator."
                    if passed
                    else (
                        "The VIXM term-structure field did not add enough "
                        "incremental information beyond accepted VIXY relief. "
                        "It either removed useful VIXY-only winners or kept "
                        "the same broad risk-on beta without stronger "
                        "per-window replacement value."
                    )
                ),
                "forbidden_near_neighbor_retry": (
                    "Do not retry by sweeping VIXY return, VIXM return, "
                    "VIXY-minus-VIXM spread, VIXY/VIXM close-location, SPY/QQQ "
                    "relief, stock close-location, volume, ret20/ret60, "
                    "top-N, hold-day, cooldown, or notional thresholds on the "
                    "frozen windows."
                ),
                "new_evidence_required": (
                    "A retry requires materially new PIT volatility evidence, "
                    "such as actual VIX futures term structure, options flow, "
                    "realized-vol compression, or closed forward replacement "
                    "rows from an accepted shared adapter."
                ),
            },
            "next_evidence_needed": (
                "If this had passed, the next step would be a shared default-off "
                "adapter plus parity tests. Since it did not, only new PIT "
                "volatility evidence or forward replacement rows justify "
                "another volatility-relief variant."
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
            ],
        }
    )
    payload.setdefault("parameters", {}).update(
        {
            "max_vixm_relief_return": MAX_VIXM_RELIEF_RETURN,
            "max_vixm_close_location": MAX_VIXM_CLOSE_LOCATION,
            "min_vixy_underperformance_vs_vixm": MIN_VIXY_UNDERPERFORMANCE_VS_VIXM,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only close-of-day OHLCV available on the signal date: "
        "VIXY/VIXM/SPY/QQQ daily return/range context plus stock leadership, "
        "liquidity, close-location, volume, ret5/ret20/ret60, and realized-vol "
        "fields. Paper entry is next available open with existing entry "
        "slippage; exit is the close 10 trading days after the signal with "
        "target-side sell slippage and ROUND_TRIP_COST_PCT."
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: front-end volatility-premium compression "
            "relative to VIXM may identify more durable single-stock "
            "leadership continuation than generic VIXY relief."
        ),
        "2_history_check": {
            "exp-20260607-019": (
                "Accepted VIXY-only volatility-relief stock leadership. This "
                "experiment must beat it, not merely improve versus core."
            ),
            "exp-20260607-026": (
                "VIXY/VIXM curve relief variants were nearby and not enough "
                "without a stricter accepted-comparator rule."
            ),
            "exp-20260609-010": (
                "Volatility-relief plus industry-laggard repair failed to beat "
                "the accepted VIXY comparator, warning that extra confirmation "
                "often thins the useful source."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Aggregate EV/PnL "
            "must improve, no window may regress, target sample must be >=20 "
            "across all 3 windows, survival must stay >=5%, drawdown drift "
            "<=0.5pp, concentration guard must pass, and aggregate plus each "
            "window must beat accepted exp-20260607-019 VIXY relief deltas."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260609_022_vixy_vixm_term_relief_leadership.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    runtime_fields = payload.setdefault("gate2", {}).setdefault("runtime_fields", [])
    if "VIXM daily OHLCV" not in runtime_fields:
        runtime_fields.insert(4, "VIXM daily OHLCV")
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Accepted dEV | Before PnL | After PnL | dPnL | Accepted dPnL | Term relief days | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        scan = payload["context_scan_by_window"][label]
        accepted = ACCEPTED_VOL_RELIEF_COMPARATOR["by_window"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | {adev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | ${adpnl:+,.2f} | {days} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                adev=accepted["expected_value_score_delta"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                adpnl=accepted["total_pnl_delta"],
                days=scan.get("volatility_relief_days", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} VIXY/VIXM Term Relief Leadership",
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
            "- Aggregate EV delta: `{:+.4f}` versus accepted `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"],
                ACCEPTED_VOL_RELIEF_COMPARATOR["expected_value_score_delta_sum"],
            ),
            "- Aggregate PnL delta: `${:+,.2f}` versus accepted `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"],
                ACCEPTED_VOL_RELIEF_COMPARATOR["total_pnl_delta_sum"],
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
        "mechanism_family": "production_visible_free_ohlcv_cross_asset_candidate_pool",
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
        "accepted_volatility_relief_comparator": ACCEPTED_VOL_RELIEF_COMPARATOR,
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
                "accepted_expected_value_delta": ACCEPTED_VOL_RELIEF_COMPARATOR[
                    "by_window"
                ][label]["expected_value_score_delta"],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "accepted_total_pnl_delta": ACCEPTED_VOL_RELIEF_COMPARATOR["by_window"][
                    label
                ]["total_pnl_delta"],
                "term_relief_day_count": payload["context_scan_by_window"][label].get(
                    "volatility_relief_days"
                ),
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
        "accepted": payload["gate4"]["passed"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "accepted_volatility_relief_comparator": ACCEPTED_VOL_RELIEF_COMPARATOR,
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": "alpha-search-automation",
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
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
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


def persist(payload: dict[str, Any]) -> None:
    BASE_PERSIST(payload)
    _update_ticket_and_registry(payload, _build_log_record(payload))
    _write_manifest(payload)


def _patch_module(module: Any) -> None:
    module.EXPERIMENT_ID = EXPERIMENT_ID
    module.STEM = STEM
    module.TRIAL_FAMILY = TRIAL_FAMILY
    module.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    module.CHANGED_VARIABLE = CHANGED_VARIABLE
    module.RULE_VERSION = RULE_VERSION
    module.OUT_DIR = OUT_DIR
    module.OUT_JSON = OUT_JSON
    module.LOG_JSON = LOG_JSON
    module.TICKET_JSON = TICKET_JSON
    module.CARD_MD = CARD_MD
    module.MANIFEST_JSON = MANIFEST_JSON
    module.EXPERIMENT_LOG = EXPERIMENT_LOG
    module.REGISTRY_JSON = REGISTRY_JSON
    module.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
    module.HOLD_DAYS = HOLD_DAYS
    module.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
    module.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
    module.MIN_TARGET_TRADES = MIN_TARGET_TRADES
    module.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
    module.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
    module.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
    module.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
    module.PREDICTION = PREDICTION
    module.PRODUCTION_IMPACT = PRODUCTION_IMPACT


def _patch_framework() -> None:
    _patch_module(previous)
    _patch_module(macro_base)
    _patch_module(framework)
    previous.MAX_VIXY_RELIEF_RETURN = MAX_VIXY_RELIEF_RETURN
    previous.MAX_VIXY_CLOSE_LOCATION = MAX_VIXY_CLOSE_LOCATION
    previous.MIN_SPY_RELIEF_RETURN = MIN_SPY_RELIEF_RETURN
    previous.MIN_QQQ_RELIEF_RETURN = MIN_QQQ_RELIEF_RETURN
    previous.MIN_SPY_CLOSE_LOCATION = MIN_SPY_CLOSE_LOCATION
    previous.MIN_QQQ_CLOSE_LOCATION = MIN_QQQ_CLOSE_LOCATION
    previous.MIN_PRICE = MIN_PRICE
    previous.MIN_AVG_DOLLAR_VOLUME_20D = MIN_AVG_DOLLAR_VOLUME_20D
    previous.MIN_SIGNAL_RETURN = MIN_SIGNAL_RETURN
    previous.MIN_RELATIVE_VS_SPY = MIN_RELATIVE_VS_SPY
    previous.MIN_RELATIVE_VS_QQQ = MIN_RELATIVE_VS_QQQ
    previous.MIN_CLOSE_LOCATION = MIN_CLOSE_LOCATION
    previous.MIN_VOLUME_RATIO_20D = MIN_VOLUME_RATIO_20D
    previous.MIN_RET20_EXCESS_SPY = MIN_RET20_EXCESS_SPY
    previous.MIN_RET60_EXCESS_SPY = MIN_RET60_EXCESS_SPY
    previous.MIN_RET5 = MIN_RET5
    previous.MAX_RET5 = MAX_RET5
    previous.MAX_REALIZED_VOL_20D = MAX_REALIZED_VOL_20D
    previous.OUT_DIR = OUT_DIR
    previous.OUT_JSON = OUT_JSON
    previous.LOG_JSON = LOG_JSON
    previous.TICKET_JSON = TICKET_JSON
    previous.CARD_MD = CARD_MD
    previous.MANIFEST_JSON = MANIFEST_JSON
    previous.EXPERIMENT_LOG = EXPERIMENT_LOG
    previous.REGISTRY_JSON = REGISTRY_JSON
    previous._relief_context_for_day = _relief_context_for_day
    previous._load_window_snapshot = _load_window_snapshot
    previous._gate4 = _gate4
    previous._build_payload = _build_payload
    previous._build_card = _build_card
    previous._build_log_record = _build_log_record
    previous._write_manifest = _write_manifest
    previous.persist = persist

    framework._load_window_snapshot = _load_window_snapshot
    framework._candidate_rows_for_window = previous._candidate_rows_for_window
    framework._gate4 = _gate4
    framework._build_payload = _build_payload
    framework._build_card = _build_card
    framework._build_log_record = _build_log_record
    framework._write_manifest = _write_manifest
    framework.persist = persist


_patch_framework()


def main() -> None:
    framework.main()


if __name__ == "__main__":
    main()
