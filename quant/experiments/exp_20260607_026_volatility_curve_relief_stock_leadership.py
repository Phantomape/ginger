"""exp-20260607-026: volatility-curve relief stock-leadership scout.

Replay-only alpha search. This tests one production-visible free-OHLCV
candidate-source variable: on accepted-style VIXY volatility-relief days,
require the short-vol proxy VIXY to compress materially more than medium-term
vol proxy VIXM, then select the same liquid stock leaders for next-open,
10-trading-day default-off paper continuation.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import exp_20260607_018_volatility_relief_stock_leadership as base


framework = base.framework

EXPERIMENT_ID = "exp-20260607-026"
STEM = "volatility_curve_relief_stock_leadership"
TRIAL_FAMILY = "volatility_curve_relief_stock_leadership_candidate_pool"
TRIAL_VARIANT_ID = "vixy_vixm_curve_relief_stock_leadership_top2_10d_v1"
CHANGED_VARIABLE = "volatility_curve_relief_stock_leadership_candidate_source_v1"
RULE_VERSION = CHANGED_VARIABLE

REPO_ROOT = base.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260607_026_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASE_NOTIONAL_USD = base.BASE_NOTIONAL_USD
HOLD_DAYS = base.HOLD_DAYS
MAX_PAPER_TRADES_PER_DAY = base.MAX_PAPER_TRADES_PER_DAY
SAME_TICKER_COOLDOWN_DAYS = base.SAME_TICKER_COOLDOWN_DAYS

MAX_VIXY_RELIEF_RETURN = base.MAX_VIXY_RELIEF_RETURN
MAX_VIXY_CLOSE_LOCATION = base.MAX_VIXY_CLOSE_LOCATION
MIN_SPY_RELIEF_RETURN = base.MIN_SPY_RELIEF_RETURN
MIN_QQQ_RELIEF_RETURN = base.MIN_QQQ_RELIEF_RETURN
MIN_SPY_CLOSE_LOCATION = base.MIN_SPY_CLOSE_LOCATION
MIN_QQQ_CLOSE_LOCATION = base.MIN_QQQ_CLOSE_LOCATION
MAX_VIXM_RELIEF_RETURN = -0.003
MAX_VIXM_CLOSE_LOCATION = 0.55
MIN_FRONT_MINUS_MID_RELIEF = 0.0125

MIN_TARGET_TRADES = base.MIN_TARGET_TRADES
MIN_TARGET_WINDOWS = base.MIN_TARGET_WINDOWS
MAX_DRAWDOWN_WORSE = base.MAX_DRAWDOWN_WORSE
MAX_SINGLE_POSITIVE_SHARE = base.MAX_SINGLE_POSITIVE_SHARE
MAX_POSITIVE_HHI = base.MAX_POSITIVE_HHI

ACCEPTED_VIXY_COMPARATOR = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260607-019"
    / "exp_20260607_019_volatility_relief_stock_leadership_shared_adapter.json"
)

PREDICTION = {
    "success_probability": 0.16,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "accepted_vixy_comparator_not_beaten",
        "window_regression",
        "drawdown_drift",
        "thin_sample",
        "vol_curve_proxy_relabels_vixy",
    ],
    "confidence_reason": (
        "Accepted VIXY relief worked, and VIXM is a free PIT OHLCV "
        "term-structure proxy; this is materially new volatility-structure "
        "evidence but close enough to the accepted VIXY family that it must "
        "beat all three canonical windows and remain a replay lead unless a "
        "shared helper follows."
    ),
    "recorded_at": "2026-06-07T22:05:14+00:00",
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
        "This experiment changes no production code. A positive result would "
        "require a shared default-off adapter exposing the same VIXY/VIXM/"
        "SPY/QQQ volatility-curve relief context, sector-known liquid stock "
        "universe, stock leadership fields, same-ticker core-overlap "
        "exclusion, next-open paper entry, 10-trading-day exit, costs, "
        "cooldown, and concentration controls in both replay and daily "
        "production before any report queue, paper ledger, candidate "
        "priority, sizing, watchlist, or order surface could change."
    ),
}

BASE_LOAD_WINDOW_SNAPSHOT = base.BASE_LOAD_WINDOW_SNAPSHOT
BASE_BUILD_PAYLOAD = base.BASE_BUILD_PAYLOAD
BASE_GATE4 = base.BASE_GATE4
BASE_PERSIST = base.BASE_PERSIST
BASE_CANDIDATE_FOR_TICKER = base.BASE_CANDIDATE_FOR_TICKER


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _accepted_vixy_comparator() -> dict[str, Any]:
    with ACCEPTED_VIXY_COMPARATOR.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    aggregate = data.get("delta_metrics", {}).get("aggregate", {})
    return {
        "experiment_id": "exp-20260607-019",
        "artifact": _repo_rel(ACCEPTED_VIXY_COMPARATOR),
        "decision": data.get("decision"),
        "after_expected_value_score_sum": aggregate.get("after_expected_value_score_sum"),
        "after_total_pnl_sum": aggregate.get("after_total_pnl_sum"),
        "expected_value_score_delta_sum": aggregate.get("expected_value_score_delta_sum"),
        "total_pnl_delta_sum": aggregate.get("total_pnl_delta_sum"),
        "by_window": {
            label: {
                "after_expected_value_score": data.get("after_metrics", {})
                .get(label, {})
                .get("expected_value_score"),
                "expected_value_score_delta": data.get("delta_metrics", {})
                .get("by_window", {})
                .get(label, {})
                .get("expected_value_score"),
                "total_pnl_delta": data.get("delta_metrics", {})
                .get("by_window", {})
                .get(label, {})
                .get("total_pnl"),
                "target_trade_count": len(
                    data.get("target_trades_by_window", {}).get(label, [])
                ),
            }
            for label in framework.WINDOWS
        },
    }


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
    vixy_close_location = base._range_location(vixy_rows[vixy_idx])
    vixm_close_location = base._range_location(vixm_rows[vixm_idx])
    spy_close_location = base._range_location(spy_rows[spy_idx])
    qqq_close_location = base._range_location(qqq_rows[qqq_idx])
    front_minus_mid_relief = None
    if vixy_return is not None and vixm_return is not None:
        front_minus_mid_relief = vixm_return - vixy_return

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
        "front_minus_mid_relief": framework._round(front_minus_mid_relief, 6),
        "max_vixy_relief_return": MAX_VIXY_RELIEF_RETURN,
        "max_vixy_close_location": MAX_VIXY_CLOSE_LOCATION,
        "max_vixm_relief_return": MAX_VIXM_RELIEF_RETURN,
        "max_vixm_close_location": MAX_VIXM_CLOSE_LOCATION,
        "min_front_minus_mid_relief": MIN_FRONT_MINUS_MID_RELIEF,
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
    if (front_minus_mid_relief or 0.0) < MIN_FRONT_MINUS_MID_RELIEF:
        return {
            **context,
            "passed": False,
            "reason": "front_vol_not_compressing_more_than_mid_vol",
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
        "reason": "vixy_vixm_curve_relief_stock_leadership_passed",
    }


def _candidate_for_ticker(
    *,
    snapshot: dict[str, list[dict[str, Any]]],
    indices: dict[str, dict[str, int]],
    sector_entries: dict[str, dict[str, Any]],
    ticker: str,
    signal_date: str,
    context: dict[str, Any],
) -> dict[str, Any] | None:
    row = BASE_CANDIDATE_FOR_TICKER(
        snapshot=snapshot,
        indices=indices,
        sector_entries=sector_entries,
        ticker=ticker,
        signal_date=signal_date,
        context=context,
    )
    if row is None:
        return None
    row["source"] = "VOLATILITY_CURVE_RELIEF_LEADERSHIP_PAPER"
    row["volatility_curve_relief_context"] = row.pop(
        "macro_relief_context",
        context,
    )
    row["rule_version"] = RULE_VERSION
    return row


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    gate = base._gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
    )
    comparator = _accepted_vixy_comparator()
    accepted_after_ev = comparator.get("after_expected_value_score_sum")
    accepted_after_pnl = comparator.get("after_total_pnl_sum")
    failed = list(gate.get("failed_reasons") or [])
    if (
        accepted_after_ev is not None
        and aggregate.get("after_expected_value_score_sum", 0.0) <= accepted_after_ev
    ):
        failed.append("accepted_vixy_comparator_ev_not_beaten")
    if (
        accepted_after_pnl is not None
        and aggregate.get("after_total_pnl_sum", 0.0) <= accepted_after_pnl
    ):
        failed.append("accepted_vixy_comparator_pnl_not_beaten")
    gate["failed_reasons"] = failed
    gate["passed"] = not failed
    gate["accepted_comparator"] = comparator
    gate["decision"] = (
        "positive_replay_lead_not_promoted_volatility_curve_relief_stock_leadership"
        if gate["passed"]
        else "rejected_volatility_curve_relief_stock_leadership_candidate_pool"
    )
    return gate


def _build_payload() -> dict[str, Any]:
    payload = BASE_BUILD_PAYLOAD()
    gate4 = payload["gate4"]
    aggregate = payload["delta_metrics"]["aggregate"]
    accepted = bool(gate4["passed"])
    comparator = gate4.get("accepted_comparator") or _accepted_vixy_comparator()
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "hypothesis": (
                "VIXY/VIXM volatility-curve relief may identify liquid stock "
                "leaders with stronger next-open continuation than plain "
                "VIXY relief because front-end volatility compression versus "
                "medium-term volatility is a cleaner risk-transfer state."
            ),
            "change_type": "default_off_paper_candidate_pool",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_free_ohlcv_cross_asset_candidate_pool",
            "new_evidence_type": "free_ohlcv_vixy_vixm_term_structure_proxy",
            "nearby_prior_experiments": [
                "exp-20260607-018",
                "exp-20260607-019",
                "exp-20260606-019",
                "exp-20260606-027",
            ],
            "prior_trial_count": 0,
            "multiple_testing_risk_bucket": "moderate",
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "anti_js": "No JavaScript was used.",
            "accepted_comparator": comparator,
            "decision": gate4["decision"],
            "status": "positive_replay_lead_not_promoted" if accepted else "rejected",
            "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
            "total_pnl_delta": aggregate["total_pnl_delta_sum"],
            "interpretation": (
                "The volatility-curve relief source cleared Gate 4 and beat "
                "the accepted VIXY comparator as a replay-only/default-off "
                "lead. No production surface was promoted."
                if accepted
                else (
                    "The volatility-curve relief source did not clear Gate 4 "
                    "or failed to beat the accepted VIXY relief comparator. "
                    "Do not promote it or answer by retuning VIXY/VIXM/SPY/"
                    "QQQ thresholds on these frozen windows."
                )
            ),
            "rejection_reason": None if accepted else "; ".join(gate4["failed_reasons"]),
            "negative_reflection": (
                "If rejected, the likely reason is that VIXM adds only a "
                "descriptive curve proxy to the already accepted VIXY relief "
                "state, or the stricter curve-relief subset becomes too thin "
                "or misses the accepted VIXY winners."
            ),
            "post_run_reflection": {
                "why_result_happened": (
                    "The front-vs-mid volatility compression proxy improved "
                    "on the accepted VIXY relief state enough to beat the "
                    "comparator, suggesting term-structure relief added "
                    "distinct risk-transfer information."
                    if accepted
                    else (
                        "VIXM did not add enough independent information "
                        "beyond the accepted VIXY relief state. The stricter "
                        "curve-relief requirement either thinned the sample, "
                        "removed accepted VIXY winners, or merely relabeled "
                        "the same risk-on state without better displacement "
                        "value."
                    )
                ),
                "forbidden_near_neighbor_retry": (
                    "Do not retry by sweeping VIXY return, VIXM return, "
                    "front-minus-mid relief, close-location, SPY/QQQ relief, "
                    "stock leadership, top-N, hold-day, cooldown, or paper "
                    "notional thresholds on the frozen windows."
                ),
                "new_evidence_required": (
                    "A retry requires materially new PIT volatility evidence "
                    "such as VIX futures curve levels, option-volume/flow, "
                    "realized-vs-implied vol compression, or closed forward "
                    "replacement-value rows from the accepted shared adapter."
                ),
            },
            "next_evidence_needed": (
                "A positive replay lead would still need a shared default-off "
                "adapter and parity tests before forward observation; live "
                "activation would require closed forward replacement-value "
                "rows and a separate activation-envelope Gate 1-4."
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
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "hold_days": HOLD_DAYS,
            "max_paper_trades_per_day": MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "max_vixy_relief_return": MAX_VIXY_RELIEF_RETURN,
            "max_vixy_close_location": MAX_VIXY_CLOSE_LOCATION,
            "max_vixm_relief_return": MAX_VIXM_RELIEF_RETURN,
            "max_vixm_close_location": MAX_VIXM_CLOSE_LOCATION,
            "min_front_minus_mid_relief": MIN_FRONT_MINUS_MID_RELIEF,
            "single_causal_variable": CHANGED_VARIABLE,
        }
    )
    payload["backtest_protocol"]["volatility_curve_context_tickers"] = [
        "VIXY",
        "VIXM",
        "SPY",
        "QQQ",
    ]
    payload["backtest_protocol"]["execution_model"] = (
        "Signal uses only close-of-day OHLCV available on the signal date: "
        "VIXY/VIXM term-structure relief, SPY/QQQ confirmation, and stock "
        "leadership/liquidity/volatility fields. Paper entry is next "
        "available open with existing entry slippage; exit is the close 10 "
        "trading days after the signal with target-side sell slippage and "
        "ROUND_TRIP_COST_PCT."
    )
    payload["gate_questions"] = {
        "1_alpha_hypothesis": (
            "entry/candidate_pool: front-end volatility compression versus "
            "medium-term volatility may be a cleaner risk-transfer state than "
            "plain VIXY relief and may improve liquid stock leadership "
            "continuation."
        ),
        "2_history_check": {
            "exp-20260607-018/019": (
                "Plain VIXY relief stock leadership was accepted as a shared "
                "default-off adapter. This must beat that accepted comparator, "
                "not merely improve versus core."
            ),
            "exp-20260606-019/020": (
                "Official macro relief stock leadership accepted; this uses "
                "volatility term structure rather than macro event dates."
            ),
            "exp-20260606-027": (
                "Macro/vol stress resilience failed. This tests relief after "
                "front-end vol compression, not resilience during stress."
            ),
        },
        "3_single_causal_variable": CHANGED_VARIABLE,
        "4_acceptance_standard": (
            "Use docs/backtesting.md three canonical windows. Aggregate EV/"
            "PnL must improve versus core, no EV/PnL regression window, "
            "target sample >=20 across all 3 windows, survival >=5%, "
            "drawdown drift <=0.5pp, concentration guard passes, and after "
            "aggregate EV/PnL must beat accepted exp-20260607-019."
        ),
        "5_reproducibility": (
            ".venv\\Scripts\\python.exe -B quant\\experiments\\"
            "exp_20260607_026_volatility_curve_relief_stock_leadership.py"
        ),
    }
    payload["pre_run_questions"] = payload["gate_questions"]
    runtime_fields = payload.setdefault("gate2", {}).setdefault("runtime_fields", [])
    for field in ("VIXM daily OHLCV", "accepted VIXY comparator artifact"):
        if field not in runtime_fields:
            runtime_fields.append(field)
    payload["gate3"]["note"] = (
        "No new core filter or entry rule was added. The volatility-curve "
        "relief leadership source is additive default-off paper, so core "
        "signals generated/survived are unchanged from baseline."
    )
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_success": 1 if accepted else 0,
        "actual_gate4_passed": accepted,
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if accepted else 0.0)) ** 2,
            6,
        ),
    }
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Curve relief days | Trades |",
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
                days=scan.get("volatility_relief_days", 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    comparator = payload["accepted_comparator"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Volatility Curve Relief Stock Leadership",
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
            "- Aggregate EV delta vs core: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate PnL delta vs core: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Accepted VIXY comparator after EV sum: `{}`".format(
                comparator.get("after_expected_value_score_sum")
            ),
            "- This after EV sum: `{}`".format(
                aggregate.get("after_expected_value_score_sum")
            ),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Production Impact",
            "",
            (
                "Replay-only and default-off paper only. No shared policy, "
                "run adapter, backtester adapter, production watchlist, order "
                "path, core entry, ranking, sizing, or exit behavior changed."
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
            "data/backtests/"
            "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
        ),
        "accepted_comparator": payload["accepted_comparator"],
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
                "curve_relief_day_count": payload["context_scan_by_window"][label].get(
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


def _write_manifest(payload: dict[str, Any]) -> None:
    script_path = Path(__file__)
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [
            _repo_rel(script_path),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "file_hashes": {
            _repo_rel(script_path): framework._sha256(script_path),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    BASE_PERSIST(payload)
    _write_manifest(payload)


def _patch_framework() -> None:
    for module in (base, framework):
        module.EXPERIMENT_ID = EXPERIMENT_ID
        module.STEM = STEM
        module.TRIAL_FAMILY = TRIAL_FAMILY
        module.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
        module.CHANGED_VARIABLE = CHANGED_VARIABLE
        module.RULE_VERSION = RULE_VERSION
        module.BASE_NOTIONAL_USD = BASE_NOTIONAL_USD
        module.HOLD_DAYS = HOLD_DAYS
        module.MAX_PAPER_TRADES_PER_DAY = MAX_PAPER_TRADES_PER_DAY
        module.SAME_TICKER_COOLDOWN_DAYS = SAME_TICKER_COOLDOWN_DAYS
        module.MAX_VIXY_RELIEF_RETURN = MAX_VIXY_RELIEF_RETURN
        module.MAX_VIXY_CLOSE_LOCATION = MAX_VIXY_CLOSE_LOCATION
        module.MIN_SPY_RELIEF_RETURN = MIN_SPY_RELIEF_RETURN
        module.MIN_QQQ_RELIEF_RETURN = MIN_QQQ_RELIEF_RETURN
        module.MIN_SPY_CLOSE_LOCATION = MIN_SPY_CLOSE_LOCATION
        module.MIN_QQQ_CLOSE_LOCATION = MIN_QQQ_CLOSE_LOCATION
        module.MIN_TARGET_TRADES = MIN_TARGET_TRADES
        module.MIN_TARGET_WINDOWS = MIN_TARGET_WINDOWS
        module.MAX_DRAWDOWN_WORSE = MAX_DRAWDOWN_WORSE
        module.MAX_SINGLE_POSITIVE_SHARE = MAX_SINGLE_POSITIVE_SHARE
        module.MAX_POSITIVE_HHI = MAX_POSITIVE_HHI
        module.PREDICTION = PREDICTION
        module.PRODUCTION_IMPACT = PRODUCTION_IMPACT
        module.OUT_DIR = OUT_DIR
        module.OUT_JSON = OUT_JSON
        module.LOG_JSON = LOG_JSON
        module.TICKET_JSON = TICKET_JSON
        module.CARD_MD = CARD_MD
        module.MANIFEST_JSON = MANIFEST_JSON
        module.EXPERIMENT_LOG = EXPERIMENT_LOG
        module.REGISTRY_JSON = REGISTRY_JSON
    base._relief_context_for_day = _relief_context_for_day
    base._candidate_for_ticker = _candidate_for_ticker
    framework._load_window_snapshot = _load_window_snapshot
    framework._candidate_for_ticker = _candidate_for_ticker
    framework._relief_context_for_day = _relief_context_for_day
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
