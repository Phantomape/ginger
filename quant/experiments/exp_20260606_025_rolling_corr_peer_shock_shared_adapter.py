"""exp-20260606-025: promote peer-shock lead to shared adapter.

This alpha experiment retests the positive exp-20260606-024 replay lead through
quant/rolling_corr_peer_shock_paper_sleeve.py. The after replay and the daily
snapshot fixture now share the same helper, which is the minimum parity step
before any forward default-off observation.

No live/default orders, core ranking, sizing, exits, LLM/news path, or watchlist
behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework
from rolling_corr_peer_shock_paper_sleeve import (
    DEFAULT_CONFIG,
    RULE_VERSION,
    SOURCE_RULE_VERSION,
    build_rolling_corr_peer_shock_historical_trades,
)


EXPERIMENT_ID = "exp-20260606-025"
STEM = "rolling_corr_peer_shock_shared_adapter"
TRIAL_FAMILY = "rolling_corr_peer_shock_default_off_shared_adapter"
TRIAL_VARIANT_ID = "rolling_corr_peer_shock_core_flow_shared_adapter_v1"
CHANGED_VARIABLE = RULE_VERSION
SOURCE_LEAD_EXPERIMENT_ID = "exp-20260606-024"

REPO_ROOT = framework.REPO_ROOT
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260606_025_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
PRODUCTION_PARITY_MD = REPO_ROOT / "docs" / "production_backtest_parity.md"
SOURCE_LEAD_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / SOURCE_LEAD_EXPERIMENT_ID
    / "exp_20260606_024_rolling_corr_peer_shock_core_flow_positive.json"
)

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35
MAX_LEAD_REPRO_EV_DRIFT = 0.0002
MAX_LEAD_REPRO_PNL_DRIFT = 1.0

PREDICTION = {
    "success_probability": 0.62,
    "expected_ev_delta": 0.38,
    "expected_pnl_delta": 6100.0,
    "main_failure_modes": [
        "shared_adapter_replay_drift",
        "window_regression",
        "drawdown_drift",
        "parity_fixture_failure",
        "concentration_failed",
    ],
    "confidence_reason": (
        "exp-20260606-024 already cleared Gate 4 as a replay-only lead. This "
        "run changes only implementation boundary: candidate generation moves "
        "into a shared default-off paper helper and must reproduce the same "
        "three-window edge."
    ),
    "recorded_at": "2026-06-06T20:08:00Z",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "shared_default_off_helper_added_not_wired_to_live_orders",
    "shared_policy_changed": True,
    "backtester_adapter_changed": True,
    "run_adapter_changed": False,
    "replay_only": False,
    "default_off_paper_only": True,
    "parity_test_added": True,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "parity_note": (
        "Historical replay calls quant/rolling_corr_peer_shock_paper_sleeve.py, "
        "the same helper covered by daily snapshot tests. The helper remains "
        "default-off and is not wired into quant/run.py, reports, watchlists, "
        "or any live/default order path in this experiment."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _compare_window(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    return {
        "expected_value_score": round(
            float(after.get("expected_value_score") or 0.0)
            - float(before.get("expected_value_score") or 0.0),
            4,
        ),
        "total_pnl": round(
            float(after.get("total_pnl") or 0.0) - float(before.get("total_pnl") or 0.0),
            2,
        ),
        "max_drawdown_pct": round(
            float(after.get("max_drawdown_pct") or 0.0)
            - float(before.get("max_drawdown_pct") or 0.0),
            6,
        ),
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
    lead_reproduction: dict[str, Any],
) -> dict[str, Any]:
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    failed: list[str] = []
    if float(aggregate["expected_value_score_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_ev_not_positive")
    if float(aggregate["total_pnl_delta_sum"] or 0.0) <= 0.0:
        failed.append("aggregate_pnl_not_positive")
    if int(aggregate["windows_ev_regressed"] or 0) > 0:
        failed.append("window_ev_regression")
    if int(aggregate["windows_pnl_regressed"] or 0) > 0:
        failed.append("window_pnl_regression")
    if target_summary["total_trade_count"] < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_summary["windows_with_target_trades"]) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if float(aggregate["max_drawdown_delta_max"] or 0.0) > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")
    if not concentration_passed:
        failed.append("target_concentration_failed")
    if not lead_reproduction.get("passed"):
        failed.append("positive_lead_not_reproduced_by_shared_adapter")
    passed = not failed
    return {
        "passed": passed,
        "decision": (
            "accepted_rolling_corr_peer_shock_shared_default_off_adapter"
            if passed
            else "rejected_rolling_corr_peer_shock_shared_default_off_adapter"
        ),
        "failed_reasons": failed,
        "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
        "windows_ev_improved": aggregate["windows_ev_improved"],
        "windows_ev_regressed": aggregate["windows_ev_regressed"],
        "windows_pnl_improved": aggregate["windows_pnl_improved"],
        "windows_pnl_regressed": aggregate["windows_pnl_regressed"],
        "target_trade_count": target_summary["total_trade_count"],
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_summary["windows_with_target_trades"],
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "max_drawdown_worse": aggregate["max_drawdown_delta_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "minimum_core_survival_rate": round(min_survival, 6),
        "survival_guard_passed": min_survival >= 0.05,
        "target_concentration": {
            "passed": concentration_passed,
            "max_single_positive_pnl_share": target_summary[
                "max_single_positive_pnl_share"
            ],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
        },
        "lead_reproduction": lead_reproduction,
        "parity_test_added": True,
        "shared_adapter_module": "quant/rolling_corr_peer_shock_paper_sleeve.py",
    }


def _lead_reproduction_check(payload: dict[str, Any]) -> dict[str, Any]:
    lead = _load_json(SOURCE_LEAD_JSON, {})
    if not lead:
        return {"passed": False, "reason": "missing_source_lead_artifact"}
    actual_agg = payload["delta_metrics"]["aggregate"]
    lead_agg = (lead.get("delta_metrics") or {}).get("aggregate") or {}
    ev_drift = round(
        float(actual_agg.get("expected_value_score_delta_sum") or 0.0)
        - float(lead_agg.get("expected_value_score_delta_sum") or 0.0),
        6,
    )
    pnl_drift = round(
        float(actual_agg.get("total_pnl_delta_sum") or 0.0)
        - float(lead_agg.get("total_pnl_delta_sum") or 0.0),
        2,
    )
    trade_drift = int(payload["target_trade_summary"]["total_trade_count"]) - int(
        ((lead.get("target_trade_summary") or {}).get("total_trade_count") or 0)
    )
    by_window: dict[str, dict[str, Any]] = {}
    passed = (
        abs(ev_drift) <= MAX_LEAD_REPRO_EV_DRIFT
        and abs(pnl_drift) <= MAX_LEAD_REPRO_PNL_DRIFT
        and trade_drift == 0
    )
    for label in framework.WINDOWS:
        actual = payload["delta_metrics"]["by_window"][label]
        expected = ((lead.get("delta_metrics") or {}).get("by_window") or {}).get(label, {})
        by_window[label] = {
            "expected_value_score_drift": round(
                float(actual.get("expected_value_score") or 0.0)
                - float(expected.get("expected_value_score") or 0.0),
                6,
            ),
            "total_pnl_drift": round(
                float(actual.get("total_pnl") or 0.0) - float(expected.get("total_pnl") or 0.0),
                2,
            ),
            "trade_count": len(payload["target_trades_by_window"][label]),
        }
    return {
        "passed": passed,
        "source_lead_artifact": _repo_rel(SOURCE_LEAD_JSON),
        "aggregate_expected_value_score_delta_drift": ev_drift,
        "aggregate_total_pnl_delta_drift": pnl_drift,
        "trade_count_drift": trade_drift,
        "by_window": by_window,
        "max_ev_drift": MAX_LEAD_REPRO_EV_DRIFT,
        "max_pnl_drift": MAX_LEAD_REPRO_PNL_DRIFT,
    }


def build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    framework._configure_sleeve_globals()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(framework.get_universe())
    sector_entries = framework._load_sector_entries()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    target_audit_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    warehouse_coverage_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] shared peer-shock adapter replay")
        before_result = framework.shadow._run_baseline(universe, cfg)
        before = framework.overlay_helper._metrics(before_result)
        snapshot = framework._load_window_snapshot(
            cfg=cfg,
            eligible_tickers=set(sector_entries),
        )
        window_sector_entries = {
            ticker: meta for ticker, meta in sector_entries.items() if ticker in snapshot
        }
        trades, audit = build_rolling_corr_peer_shock_historical_trades(
            ohlcv_by_ticker=snapshot,
            core_entries_by_date=framework.shadow._baseline_entries(before_result),
            windows={label: cfg},
            sector_entries=window_sector_entries,
            config=DEFAULT_CONFIG,
        )
        overlay = framework.sleeve._overlay_from_paper_trades(before_result, trades)
        after = framework.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = _compare_window(before, after)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = trades
        target_audit_by_window[label] = audit
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "sector_known_candidate_ticker_count": len(window_sector_entries),
            "source": _repo_rel(framework.WAREHOUSE),
        }
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(trades),
            "raw_candidate_count": audit["raw_candidate_count_by_window"].get(label, 0),
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = framework._aggregate_window_rows(window_rows)
    target_summary = framework.sleeve._target_trade_summary(target_trades_by_window)
    payload: dict[str, Any] = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "hypothesis": (
            "The core-flow confirmed rolling-correlation peer-shock lead remains "
            "valuable when candidate generation is moved into a shared "
            "default-off paper adapter used by both historical replay and daily "
            "snapshot tests."
        ),
        "change_type": "default_off_paper_shared_adapter",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_free_ohlcv_relation_alpha",
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "positive_replay_lead_shared_adapter_promotion",
        "nearby_prior_experiments": [
            "exp-20260606-024",
            "exp-20260606-018",
            "exp-20260605-015",
            "exp-20260604-009",
        ],
        "prior_trial_count": 1,
        "prediction": PREDICTION,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "shared default-off paper helper overlay"
            ),
            "windows": framework.WINDOWS,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Signal uses only signal-date close OHLCV and 60 prior trading "
                "day returns, admits only dates with same-day core A/B flow, "
                "paper entry is next available open, and exit is 10 trading "
                "days after signal with the shared fill/cost model."
            ),
        },
        "parameters": {
            "shared_adapter_rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            **{
                key: DEFAULT_CONFIG[key]
                for key in [
                    "paper_notional_usd",
                    "daily_entry_slots",
                    "hold_days",
                    "same_ticker_cooldown_days",
                    "correlation_lookback_days",
                    "min_correlation",
                    "min_peer_signal_return",
                    "min_candidate_signal_return",
                    "max_candidate_signal_return",
                ]
            },
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": (
                "candidate_pool/shared_adapter: exp024's peer-shock alpha is "
                "only usable if the same helper can drive historical replay and "
                "daily default-off paper observation without live-order impact."
            ),
            "2_history_check": {
                "exp-20260606-024": (
                    "Positive replay lead: aggregate EV +0.3845, PnL +$6,107.66, "
                    "48 trades, all three windows positive, no Gate4 failures."
                ),
                "exp-20260606-018": (
                    "Broader rolling-correlation peer-shock lag was rejected; "
                    "core-flow confirmation and positive candidate day reaction "
                    "fixed the old_thin regression in exp024."
                ),
                "exp-20260605-015": (
                    "Prior shared-adapter promotion can fail when replay-only "
                    "logic does not survive production-realistic semantics; this "
                    "run explicitly requires exp024 reproduction."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Use the same three canonical windows. Aggregate EV/PnL must be "
                "positive, no EV/PnL regression window, sample >=20 across all "
                "3 windows, survival >=5%, drawdown drift <=0.5pp, concentration "
                "guard passes, and the shared helper must reproduce exp024."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260606_025_rolling_corr_peer_shock_shared_adapter.py"
            ),
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": f"{_repo_rel(OUT_JSON)}#before_metrics",
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "warehouse ohlcv Date/Open/High/Low/Close/Volume",
                "SPY daily OHLCV",
                "data/reference/broad_market_sector_map.json sector/status",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "same-day baseline A/B entries from current core replay",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": False,
            "minimum_core_survival_rate": round(
                min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values()),
                6,
            ),
            "passed": min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
            >= 0.05,
            "note": (
                "No new core filter is added. The helper is default-off paper; "
                "core signals generated/survived are unchanged from baseline."
            ),
        },
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "target_trades_by_window": target_trades_by_window,
        "target_trade_summary": target_summary,
        "target_audit_by_window": target_audit_by_window,
        "warehouse_coverage_by_window": warehouse_coverage_by_window,
        "production_impact": PRODUCTION_IMPACT,
        "anti_js": "No JavaScript was used.",
        "related_files": [
            _repo_rel(Path(__file__)),
            "quant/rolling_corr_peer_shock_paper_sleeve.py",
            "quant/test_rolling_corr_peer_shock_paper_sleeve.py",
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(PRODUCTION_PARITY_MD),
            _repo_rel(SOURCE_LEAD_JSON),
        ],
    }
    lead_reproduction = _lead_reproduction_check(payload)
    gate4 = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
        lead_reproduction=lead_reproduction,
    )
    payload["gate4"] = gate4
    payload["lead_reproduction"] = lead_reproduction
    payload["status"] = "accepted" if gate4["passed"] else "rejected"
    payload["decision"] = gate4["decision"]
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
    }
    payload["interpretation"] = (
        "The shared adapter reproduced exp024 and cleared Gate 4 as an accepted "
        "default-off helper. It is not wired into live orders; the next step is "
        "daily forward paper observation/report wiring using this same helper."
        if gate4["passed"]
        else (
            "The positive exp024 lead did not survive shared-adapter promotion. "
            "Do not wire this surface forward without new evidence."
        )
    )
    payload["next_evidence_needed"] = (
        "Wire the accepted helper into daily default-off reporting/paper ledger "
        "with trade_enabled=False, then collect closed forward replacement-value "
        "rows before any live trade adapter."
        if gate4["passed"]
        else "Do not retune peer-shock thresholds on the frozen windows."
    )
    return payload


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Before PnL | After PnL | dPnL | DD d | Raw | Trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        audit = payload["target_audit_by_window"][label]
        raw = audit["raw_candidate_count_by_window"].get(label, 0)
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {raw} | {trades} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                dd=delta["max_drawdown_pct"],
                raw=raw,
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Rolling-Correlation Peer-Shock Shared Adapter",
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
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Lead reproduction passed: `{}`".format(payload["lead_reproduction"]["passed"]),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Production Impact",
            "",
            (
                "Shared default-off helper added with parity tests. It is not "
                "wired into run.py, reports, watchlists, or live/default orders."
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
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "lead_reproduction": payload["lead_reproduction"],
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
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "anti_js": "No JavaScript was used.",
    }


def _write_ticket(payload: dict[str, Any]) -> None:
    ticket = {
        "experiment_id": EXPERIMENT_ID,
        "experiment_uid": "expuid-rolling-corr-peer-shock-shared-adapter-v1",
        "status": payload["status"],
        "owner": "alpha-search",
        "lane": "alpha_search",
        "created_at": payload["timestamp"],
        "claimed_at": payload["timestamp"],
        "completed_at": payload["timestamp"],
        "hypothesis": payload["hypothesis"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "prediction": PREDICTION,
        "decision": payload["decision"],
        "summary": payload["interpretation"],
        "result": {
            "accepted": payload["gate4"]["passed"],
            "aggregate_expected_value_delta": payload["delta_metrics"]["aggregate"][
                "expected_value_score_delta_sum"
            ],
            "aggregate_strategy_total_pnl_delta": payload["delta_metrics"]["aggregate"][
                "total_pnl_delta_sum"
            ],
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "decision": payload["decision"],
        },
        "allowed_write_scope": payload["related_files"],
    }
    TICKET_JSON.parent.mkdir(parents=True, exist_ok=True)
    TICKET_JSON.write_text(json.dumps(ticket, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_manifest(payload: dict[str, Any]) -> None:
    script_path = Path(__file__)
    files = [
        script_path,
        REPO_ROOT / "quant" / "rolling_corr_peer_shock_paper_sleeve.py",
        REPO_ROOT / "quant" / "test_rolling_corr_peer_shock_paper_sleeve.py",
        PRODUCTION_PARITY_MD,
        OUT_JSON,
        LOG_JSON,
        TICKET_JSON,
        CARD_MD,
        MANIFEST_JSON,
    ]
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "files": [_repo_rel(path) for path in files],
        "file_hashes": {
            _repo_rel(path): framework._sha256(path) for path in files if path.exists()
        },
    }
    MANIFEST_JSON.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_JSON.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_outputs(payload: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    LOG_JSON.write_text(
        json.dumps(_build_log_record(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    CARD_MD.write_text(_build_card(payload), encoding="utf-8")
    _write_ticket(payload)
    _write_manifest(payload)


def main() -> None:
    payload = build_payload()
    write_outputs(payload)
    aggregate = payload["delta_metrics"]["aggregate"]
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "aggregate_ev_delta": aggregate["expected_value_score_delta_sum"],
                "aggregate_pnl_delta": aggregate["total_pnl_delta_sum"],
                "target_trades": payload["target_trade_summary"]["total_trade_count"],
                "lead_reproduction": payload["lead_reproduction"]["passed"],
                "artifact": _repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
