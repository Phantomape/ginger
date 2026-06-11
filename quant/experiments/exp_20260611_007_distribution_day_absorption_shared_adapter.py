"""exp-20260611-007: shared distribution-day absorption adapter.

This alpha experiment promotes the positive exp-20260611-006 replay lead into
quant/distribution_day_absorption_leadership_paper_sleeve.py. Historical replay
and daily default-off snapshots now share one helper. No live/default orders,
core ranking, sizing, exits, LLM/news path, or watchlist behavior is changed.

No JavaScript was used.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework
from distribution_day_absorption_leadership_paper_sleeve import (
    DEFAULT_CONFIG,
    RULE_VERSION,
    SOURCE_RULE_VERSION,
    build_distribution_day_absorption_leadership_historical_trades,
)


EXPERIMENT_ID = "exp-20260611-007"
OWNER = "alpha-search"
STEM = "distribution_day_absorption_shared_adapter"
TRIAL_FAMILY = "distribution_day_absorption_leadership_shared_default_off_adapter"
TRIAL_VARIANT_ID = RULE_VERSION
CHANGED_VARIABLE = "distribution_day_absorption_leadership_shared_default_off_candidate_source_v1"
SOURCE_LEAD_EXPERIMENT_ID = "exp-20260611-006"

REPO_ROOT = framework.REPO_ROOT
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (SCRIPTS_DIR,):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from experiment_registry import persist_self_registered_result  # noqa: E402


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260611_007_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
PRODUCTION_PARITY_MATRIX_MD = REPO_ROOT / "docs" / "production_backtest_parity_matrix.md"
SOURCE_LEAD_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / SOURCE_LEAD_EXPERIMENT_ID
    / "exp_20260611_006_distribution_day_absorption_leadership.json"
)

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35
MAX_LEAD_REPRO_EV_DRIFT = 0.0002
MAX_LEAD_REPRO_PNL_DRIFT = 1.0

ACCEPTED_COMPRESSION_COMPARATOR = {
    "experiment_id": "exp-20260608-013",
    "decision": "accepted_narrow_range_compression_breakout_shared_default_off_adapter",
    "expected_value_score_delta_sum": 0.1608,
    "total_pnl_delta_sum": 2248.98,
    "target_trade_count": 44,
}

PREDICTION = {
    "success_probability": 0.62,
    "expected_ev_delta": 0.5286,
    "expected_pnl_delta": 10432.91,
    "main_failure_modes": [
        "shared_helper_drift_from_replay",
        "daily_snapshot_wiring_gap",
        "accepted_comparator_not_reproduced",
        "forward_rows_immature",
    ],
    "confidence_reason": (
        "The immediate prior replay lead exp-20260611-006 used only "
        "point-in-time OHLCV, improved all three canonical windows, produced "
        "113 target trades, passed drawdown and concentration, and beat the "
        "accepted compression comparator. The main risk is implementation "
        "drift when moving the fixed rule into a shared daily/backtest helper "
        "plus the fact that it remains default-off until forward replacement "
        "rows mature."
    ),
    "recorded_at": "2026-06-11T05:03:47+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "shared_default_off_helper_with_daily_snapshot",
    "shared_policy_changed": True,
    "backtester_adapter_changed": True,
    "run_adapter_changed": True,
    "replay_only": False,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": True,
    "parity_test_added": True,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "live_realism_evaluated": True,
    "live_ready": False,
    "uses_llm": False,
    "uses_free_ohlcv_only": True,
    "activation_envelope": {
        "intended_notional": "default-off paper only at fixed $4,000 notional",
        "capital_cap": "max 8 default-off paper positions; no live capital",
        "liquidity_slippage_model": (
            "price >= $10, ADV20 >= $50M, next-open entry, target-side sell "
            "slippage, and round-trip cost"
        ),
        "portfolio_displacement": (
            "paper overlay versus core/cash baseline only; no live slot or "
            "capital displacement"
        ),
        "exposure_limits": "top-1/day, 10-trading-day same-ticker cooldown, concentration gate",
        "kill_switch": (
            "future activation requires closed forward replacement-value gate "
            "and drawdown/concentration kill switch"
        ),
        "order_semantics": "no orders emitted; pending/open/closed paper ledger only",
        "failure_handling": "snapshot fails closed to empty default-off payload",
    },
    "parity_note": (
        "Historical replay and daily observation share "
        "quant/distribution_day_absorption_leadership_paper_sleeve.py. The "
        "helper is default-off and cannot alter orders, core ranking, sizing, "
        "exits, watchlists, LLM, or news behavior."
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
                float(actual.get("total_pnl") or 0.0)
                - float(expected.get("total_pnl") or 0.0),
                2,
            ),
            "target_trade_count": len(payload["target_trades_by_window"][label]),
        }
    passed = (
        abs(ev_drift) <= MAX_LEAD_REPRO_EV_DRIFT
        and abs(pnl_drift) <= MAX_LEAD_REPRO_PNL_DRIFT
        and trade_drift == 0
    )
    return {
        "passed": passed,
        "source_lead_experiment_id": SOURCE_LEAD_EXPERIMENT_ID,
        "source_lead_artifact": _repo_rel(SOURCE_LEAD_JSON),
        "aggregate_expected_value_score_delta_drift": ev_drift,
        "aggregate_total_pnl_delta_drift": pnl_drift,
        "trade_count_drift": trade_drift,
        "by_window": by_window,
        "max_ev_drift": MAX_LEAD_REPRO_EV_DRIFT,
        "max_pnl_drift": MAX_LEAD_REPRO_PNL_DRIFT,
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
    if (
        float(aggregate["expected_value_score_delta_sum"] or 0.0)
        <= ACCEPTED_COMPRESSION_COMPARATOR["expected_value_score_delta_sum"]
    ):
        failed.append("accepted_compression_ev_not_beaten")
    if (
        float(aggregate["total_pnl_delta_sum"] or 0.0)
        <= ACCEPTED_COMPRESSION_COMPARATOR["total_pnl_delta_sum"]
    ):
        failed.append("accepted_compression_pnl_not_beaten")
    passed = not failed
    return {
        "passed": passed,
        "decision": (
            "accepted_paper_pending_forward_distribution_day_absorption_leadership_shared_adapter"
            if passed
            else "rejected_distribution_day_absorption_leadership_shared_adapter"
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
            "max_single_positive_pnl_share": target_summary["max_single_positive_pnl_share"],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
        },
        "lead_reproduction": lead_reproduction,
        "accepted_compression_comparator": ACCEPTED_COMPRESSION_COMPARATOR,
        "parity_test_added": True,
        "shared_adapter_module": "quant/distribution_day_absorption_leadership_paper_sleeve.py",
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
        print(f"[{label}] shared distribution-day absorption leadership adapter replay")
        before_result = framework.shadow._run_baseline(universe, cfg)
        before = framework.overlay_helper._metrics(before_result)
        snapshot = framework._load_window_snapshot(
            cfg=cfg,
            eligible_tickers=set(sector_entries),
        )
        window_sector_entries = {
            ticker: meta for ticker, meta in sector_entries.items() if ticker in snapshot
        }
        trades, audit = build_distribution_day_absorption_leadership_historical_trades(
            ohlcv_by_ticker=snapshot,
            core_entries_by_date=framework.shadow._baseline_entries(before_result),
            windows={label: cfg},
            sector_entries=window_sector_entries,
            config=DEFAULT_CONFIG,
        )
        overlay = framework.sleeve._overlay_from_paper_trades(before_result, trades)
        after = framework.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = framework.overlay_helper._delta(after, before)

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
            "Distribution-day absorption leadership may identify liquid stocks "
            "where institutional demand absorbs recent SPY/QQQ high-volume "
            "selloff pressure and produces next-open 10-day replacement value. "
            "The alpha is only acceptable if the fixed exp006 policy bundle "
            "reproduces through one shared historical and daily helper."
        ),
        "change_type": "candidate_pool_full_stack",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_free_ohlcv_tail_state_candidate_pool",
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "positive_replay_lead_shared_adapter_promotion",
        "nearby_prior_experiments": [
            "exp-20260611-006",
            "exp-20260608-013",
            "exp-20260609-001",
            "exp-20260528-010",
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
                "Signal uses only signal-date close OHLCV, recent SPY/QQQ "
                "distribution-pressure context, candidate absorption/reclaim "
                "fields, next-open paper entry, and 10-trading-day close exit "
                "through the shared fill/cost model."
            ),
        },
        "parameters": {
            "changed_variable": CHANGED_VARIABLE,
            "shared_adapter_rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            **{
                key: DEFAULT_CONFIG[key]
                for key in [
                    "paper_notional_usd",
                    "daily_entry_slots",
                    "hold_days",
                    "same_ticker_cooldown_days",
                    "min_price",
                    "min_avg_dollar_volume_20d",
                    "pressure_lookback_days",
                    "min_combined_distribution_events",
                    "max_index_signal_return",
                    "min_index_signal_return",
                    "max_recent_spy_qqq_ret5",
                    "min_recent_spy_qqq_ret5",
                    "max_index_close_location_on_distribution",
                    "max_index_distribution_return",
                    "min_index_distribution_volume_ratio",
                    "prior_high_lookback_days",
                    "min_candidate_signal_return",
                    "min_candidate_relative_vs_spy",
                    "min_candidate_relative_vs_qqq",
                    "min_candidate_close_location",
                    "min_candidate_volume_ratio_20d",
                    "min_candidate_ret5",
                    "max_candidate_ret5",
                    "max_candidate_ret20",
                    "min_candidate_ret20_excess_spy",
                    "min_candidate_ret60_excess_spy",
                    "min_candidate_reclaim_vs_10d_high",
                    "max_candidate_reclaim_vs_10d_high",
                    "max_candidate_realized_vol_20",
                ]
            },
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": (
                "candidate_pool/shared_adapter: stocks that absorb recent "
                "SPY/QQQ distribution pressure and reclaim highs may show "
                "institutional demand before next-open continuation."
            ),
            "2_history_check": {
                "exp-20260611-006": (
                    "Positive replay lead: aggregate EV +0.5286, PnL "
                    "+$10,432.91, 113 target trades, all three windows positive."
                ),
                "exp-20260608-013": (
                    "Accepted narrow-range compression is the closest free "
                    "OHLCV comparator and must still be beaten."
                ),
                "exp-20260609-001": (
                    "Market-pullback resilient reclaim failed old_thin and "
                    "aggregate PnL; this is distribution-pressure absorption, "
                    "not a pullback reclaim retune."
                ),
                "exp-20260528-010": (
                    "Kova distribution-day context was observed-only and did "
                    "not justify VCP gating; this tests a default-off candidate "
                    "source with shared daily replay semantics."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Use the same three canonical windows. Aggregate EV/PnL must "
                "be positive, no EV/PnL regression window, sample >=20 across "
                "all 3 windows, survival >=5%, drawdown drift <=0.5pp, "
                "concentration guard passes, accepted compression comparator "
                "is beaten, and the shared helper reproduces exp006."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260611_007_distribution_day_absorption_shared_adapter.py"
            ),
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": (
                "data/experiments/exp-20260602-003/"
                "exp_20260602_003_post_earnings_explicit_continuation.json"
            ),
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "warehouse ohlcv Date/Open/High/Low/Close/Volume",
                "SPY daily OHLCV",
                "QQQ daily OHLCV",
                "data/reference/broad_market_sector_map.json sector/industry/status",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "same-day core A/B ticker for same-ticker overlap exclusion",
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
            "passed": min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values()) >= 0.05,
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
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "anti_js": "No JavaScript was used.",
    }
    lead_reproduction = _lead_reproduction_check(payload)
    gate4 = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
        lead_reproduction=lead_reproduction,
    )
    payload["gate4"] = gate4
    payload["status"] = "accepted" if gate4["passed"] else "rejected"
    payload["decision"] = gate4["decision"]
    payload["expected_value_score_delta"] = aggregate["expected_value_score_delta_sum"]
    payload["total_pnl_delta"] = aggregate["total_pnl_delta_sum"]
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
        "surprise_note": (
            "Shared helper reproduced the positive replay lead."
            if gate4["passed"]
            else "Shared helper failed reproduction or Gate 4."
        ),
    }
    payload["interpretation"] = (
        "Accepted for shared default-off paper observation only. The positive "
        "distribution-day absorption replay lead reproduced through a shared "
        "daily/backtest helper, but live activation remains blocked by forward "
        "replacement-value maturation."
        if gate4["passed"]
        else (
            "The distribution-day absorption lead failed shared-helper "
            "promotion; do not retain the helper as accepted alpha."
        )
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The shared helper reproduced the private replay lead because it "
            "kept the exact distribution-pressure context, absorption/reclaim "
            "candidate fields, SPY/QQQ relative leadership, next-open entry, "
            "10-day exit, cost, top-1, cooldown, and same-ticker core-overlap "
            "semantics while adding a daily pending/open/closed state surface."
            if gate4["passed"]
            else (
                "The helper failed reproduction or Gate 4, indicating the "
                "private lead depended on implementation details or remained "
                "too fragile after shared daily semantics."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not sweep distribution-day count, index volume ratio, index "
            "return thresholds, reclaim distance, candidate ret5/ret20, "
            "close-location, volume, top-N, hold-day, cooldown, or paper "
            "notional on the frozen windows."
        ),
        "new_evidence_required": (
            "Next useful evidence is closed forward replacement-value rows "
            "from the shared default-off ledger or an orthogonal PIT flow/"
            "catalyst provenance layer. Live activation requires a separate "
            "activation-envelope Gate 1-4 if the execution envelope changes."
        ),
    }
    payload["next_retry_requires"] = [
        "closed forward replacement-value rows",
        "independent PIT flow or catalyst provenance",
        "no frozen-window parameter retune",
    ]
    payload["related_files"] = [
        "quant/distribution_day_absorption_leadership_paper_sleeve.py",
        "quant/test_distribution_day_absorption_leadership_paper_sleeve.py",
        "quant/run.py",
        "docs/production_backtest_parity_matrix.md",
        "docs/experiment_registry.json",
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(TICKET_JSON),
        _repo_rel(MANIFEST_JSON),
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
        audit = payload["target_audit_by_window"][label]
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
                raw=audit["raw_candidate_count_by_window"].get(label, 0),
                trades=len(payload["target_trades_by_window"][label]),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    lead_repro = payload["gate4"]["lead_reproduction"]
    comparator = payload["gate4"]["accepted_compression_comparator"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Distribution-Day Absorption Shared Adapter",
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
            "- Aggregate EV delta: `{:+.4f}`".format(aggregate["expected_value_score_delta_sum"]),
            "- Aggregate PnL delta: `${:+,.2f}`".format(aggregate["total_pnl_delta_sum"]),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "- Lead reproduction EV drift: `{:+.6f}`".format(
                lead_repro.get("aggregate_expected_value_score_delta_drift", 0.0)
            ),
            "- Lead reproduction PnL drift: `${:+,.2f}`".format(
                lead_repro.get("aggregate_total_pnl_delta_drift", 0.0)
            ),
            "- Accepted compression comparator EV/PnL: `{}` / `${:,.2f}`".format(
                comparator["expected_value_score_delta_sum"],
                comparator["total_pnl_delta_sum"],
            ),
            "",
            "## Production Impact",
            "",
            (
                "Shared default-off paper helper and daily snapshot only. "
                "`trade_enabled=false`; live/default orders, ranking, sizing, "
                "exits, LLM/news, and watchlists are unchanged."
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
        "mechanism_family": "production_visible_free_ohlcv_tail_state_candidate_pool",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": payload["gate1"]["baseline_artifact"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate["expected_value_score_delta_pct"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "gate4": payload["gate4"],
        "windows": [
            {
                "label": label,
                "expected_value_before": payload["before_metrics"][label]["expected_value_score"],
                "expected_value_after": payload["after_metrics"][label]["expected_value_score"],
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "raw_candidate_count": payload["target_audit_by_window"][label][
                    "raw_candidate_count_by_window"
                ].get(label, 0),
                "target_trade_count": len(payload["target_trades_by_window"][label]),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": {**payload["calibration"]},
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _update_registry(payload: dict[str, Any]) -> None:
    result = {
        "decision": payload["decision"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "accepted": payload["gate4"]["passed"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
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
        "aggregate_expected_value_delta": payload["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
        "allowed_write_scope": sorted(set(payload["related_files"] + [_repo_rel(EXPERIMENT_LOG)])),
        "completed_at": payload["timestamp"],
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
    paths = [
        Path(__file__),
        QUANT_ROOT / "distribution_day_absorption_leadership_paper_sleeve.py",
        QUANT_ROOT / "test_distribution_day_absorption_leadership_paper_sleeve.py",
        QUANT_ROOT / "run.py",
        PRODUCTION_PARITY_MATRIX_MD,
        REGISTRY_JSON,
        EXPERIMENT_LOG,
        OUT_JSON,
        LOG_JSON,
        TICKET_JSON,
        CARD_MD,
    ]
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [_repo_rel(path) for path in paths],
        "file_hashes": {
            _repo_rel(path): framework._sha256(path)
            for path in paths
            if path.exists()
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, payload)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, _build_log_record(payload))
    _update_registry(payload)
    _write_manifest(payload)


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps(framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
