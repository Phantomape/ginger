"""exp-20260616-015: shared SBC burden-improvement adapter.

Promotes the positive exp-20260616-014 replay lead into
quant/sbc_burden_improvement_paper_sleeve.py. Historical replay and daily
default-off snapshots now share one helper. No live/default orders, core
ranking, sizing, exits, LLM/news path, or watchlist behavior is changed.

No JavaScript was used.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT_BOOT = Path(__file__).resolve().parents[2]
QUANT_ROOT_BOOT = REPO_ROOT_BOOT / "quant"
for import_path in (REPO_ROOT_BOOT, QUANT_ROOT_BOOT, REPO_ROOT_BOOT / "scripts"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework
from full_stack_candidate_pool import (
    ExecutionEnvelope,
    evaluate_live_readiness,
    full_stack_verdict,
)
from sbc_burden_improvement_paper_sleeve import (
    DEFAULT_CONFIG,
    GROSS_PROFIT_TAGS,
    REVENUE_TAGS,
    RULE_VERSION,
    SBC_TAGS,
    SOURCE_RULE_VERSION,
    build_sbc_burden_improvement_historical_trades,
    load_sbc_burden_companyfacts_index,
)


EXPERIMENT_ID = "exp-20260616-015"
OWNER = "alpha-search-automation"
STEM = "sbc_burden_improvement_shared_adapter"
TRIAL_FAMILY = "sbc_burden_improvement_shared_default_off_adapter"
TRIAL_VARIANT_ID = RULE_VERSION
CHANGED_VARIABLE = "stock_based_compensation_burden_improvement_shared_default_off_candidate_source_v1"
SOURCE_LEAD_EXPERIMENT_ID = "exp-20260616-014"

REPO_ROOT = framework.REPO_ROOT
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260616_015_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
PRODUCTION_PARITY_MATRIX_MD = REPO_ROOT / "docs" / "production_backtest_parity_matrix.md"
SOURCE_LEAD_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / SOURCE_LEAD_EXPERIMENT_ID
    / "exp_20260616_014_stock_based_compensation_burden_improvement.json"
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
ACCEPTED_DISTRIBUTION_COMPARATOR = {
    "experiment_id": "exp-20260611-007",
    "decision": "accepted_paper_pending_forward_distribution_day_absorption_leadership_shared_adapter",
    "expected_value_score_delta_sum": 0.5286,
    "total_pnl_delta_sum": 10432.91,
    "target_trade_count": 113,
}

PREDICTION = {
    "success_probability": 0.62,
    "expected_ev_delta": 0.9438,
    "expected_pnl_delta": 15748.19,
    "main_failure_modes": [
        "shared_helper_reproduction_drift",
        "daily_snapshot_parity_gap",
        "drawdown_guard_regression",
        "accepted_comparator_not_beaten",
    ],
    "confidence_reason": (
        "exp-20260616-014 already passed numeric Gate 4 across all three "
        "canonical windows with 108 trades and no concentration failure. This "
        "run changes only the production/backtest boundary by moving the fixed "
        "policy into one shared helper, so the main risk is reproduction or "
        "parity drift rather than new alpha quality."
    ),
    "recorded_at": "2026-06-16T13:04:42+00:00",
}

EXECUTION_ENVELOPE = ExecutionEnvelope(
    base_notional=4_000.0,
    max_capital_pct=0.40,
    min_dollar_volume=50_000_000.0,
    slippage_bps=5.0,
    max_displacement=1,
    max_concurrent=10,
    order_semantics="default-off paper next-session-open observation; no broker order",
    kill_switch_drawdown_pct=0.08,
    sleeve_drawdown_stop_pct=0.05,
    notes=(
        "Top-1/day, 10 trading-day hold, 10 trading-day same-ticker cooldown. "
        "Trade-enabled remains false until forward closed paper rows, "
        "replacement value, and kill-switch parity pass."
    ),
)

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
    "uses_free_sec_companyfacts": True,
    "uses_raw_companyfacts_cache": True,
    "uses_free_ohlcv": True,
    "activation_envelope": EXECUTION_ENVELOPE.to_dict(),
    "parity_note": (
        "Historical replay and daily observation share "
        "quant/sbc_burden_improvement_paper_sleeve.py. The helper is "
        "default-off and cannot alter orders, core ranking, sizing, exits, "
        "watchlists, LLM, or news behavior."
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
    if int(aggregate["windows_ev_improved"] or 0) < 2:
        failed.append("fewer_than_two_ev_improved_windows")
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
    if (
        float(aggregate["expected_value_score_delta_sum"] or 0.0)
        <= ACCEPTED_DISTRIBUTION_COMPARATOR["expected_value_score_delta_sum"]
    ):
        failed.append("accepted_distribution_ev_not_beaten")
    if (
        float(aggregate["total_pnl_delta_sum"] or 0.0)
        <= ACCEPTED_DISTRIBUTION_COMPARATOR["total_pnl_delta_sum"]
    ):
        failed.append("accepted_distribution_pnl_not_beaten")
    passed = not failed
    return {
        "passed": passed,
        "decision": (
            "accepted_paper_pending_forward_sbc_burden_improvement_shared_adapter"
            if passed
            else "rejected_sbc_burden_improvement_shared_adapter"
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
        "accepted_distribution_comparator": ACCEPTED_DISTRIBUTION_COMPARATOR,
        "parity_test_added": True,
        "shared_adapter_module": "quant/sbc_burden_improvement_paper_sleeve.py",
    }


def build_payload() -> dict[str, Any]:
    timestamp = _utc_now()
    framework._configure_sleeve_globals()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(framework.get_universe())
    sector_entries = framework._load_sector_entries()
    quality_index, quality_summary = load_sbc_burden_companyfacts_index()
    before_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    after_metrics: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    target_trades_by_window: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    target_audit_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    warehouse_coverage_by_window: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    window_rows: "OrderedDict[str, dict[str, Any]]" = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] shared SBC burden-improvement adapter replay")
        before_result = framework.shadow._run_baseline(universe, cfg)
        before = framework.overlay_helper._metrics(before_result)
        snapshot = framework._load_window_snapshot(cfg=cfg, eligible_tickers=set(universe))
        window_sector_entries = {
            ticker: meta for ticker, meta in sector_entries.items() if ticker in snapshot
        }
        trades, audit = build_sbc_burden_improvement_historical_trades(
            ohlcv_by_ticker=snapshot,
            windows={label: cfg},
            quality_index=quality_index,
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
            "candidate_pool/shared_adapter: raw SEC Companyfacts annual stock-based "
            "compensation burden falling versus revenue, with positive revenue/"
            "gross-profit context and liquid SPY-relative leadership, may identify "
            "growth-quality candidates whose shareholder dilution cost is improving "
            "before a 10-trading-day continuation leg."
        ),
        "change_type": "candidate_pool_full_stack",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_free_sec_companyfacts_dilution_quality_candidate_pool",
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "positive_sbc_burden_replay_lead_shared_adapter_promotion",
        "nearby_prior_experiments": [
            "exp-20260616-014",
            "exp-20260616-010",
            "exp-20260616-009",
            "exp-20260615-016",
            "exp-20260614-029",
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
            "companyfacts_source": "data/cache/sec/companyfacts raw filed-date SEC Companyfacts",
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Annual stock-based compensation, revenue, and gross-profit facts "
                "are read from raw SEC Companyfacts tags and known only by filed "
                "date (<= signal date). The current SBC/revenue ratio is compared "
                "with the prior annual period using the same SBC tag. Price "
                "confirmation uses signal-date OHLCV only. Paper entry is next "
                "available open with entry slippage; exit is the close 10 trading "
                "days after the signal with target-side sell slippage and "
                "ROUND_TRIP_COST_PCT."
            ),
        },
        "parameters": {
            "changed_variable": CHANGED_VARIABLE,
            "shared_adapter_rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "sbc_tags": list(SBC_TAGS),
            "revenue_tags": list(REVENUE_TAGS),
            "gross_profit_tags": list(GROSS_PROFIT_TAGS),
            **{
                key: DEFAULT_CONFIG[key]
                for key in [
                    "paper_notional_usd",
                    "daily_entry_slots",
                    "hold_days",
                    "same_ticker_cooldown_days",
                    "max_active_positions",
                ]
            },
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": (
                "candidate_pool: SBC/revenue burden falling YoY is a dilution-cost "
                "quality improvement; if liquid SPY-relative price action confirms "
                "demand, the name may continue over the next 10 trading days."
            ),
            "2_history_check": {
                "exp-20260616-014": (
                    "Positive replay lead: aggregate EV +0.9438, PnL +$15,748.19, "
                    "108 target trades, all three canonical windows positive. This "
                    "run promotes that fixed bundle to a shared helper."
                ),
                "exp-20260614-029": (
                    "Rejected diluted-share-count contraction; this run is explicit "
                    "SBC burden versus revenue, not share-count contraction."
                ),
                "exp-20260616-010": (
                    "Rejected SGA/operating-expense leverage; this is a distinct "
                    "shareholder-compensation dilution-cost field."
                ),
                "exp-20260616-009": (
                    "Rejected buyback source; this tests compensation dilution cost, "
                    "not cash-funded repurchase activity."
                ),
                "exp-20260615-016": (
                    "Rejected operating leverage acceleration; this tests one input "
                    "cost burden rather than operating-income outcome."
                ),
            },
            "3_single_decision_hypothesis": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Use the same three canonical windows. Aggregate EV/PnL must be "
                "positive, no EV/PnL regression window, sample >=20 across all 3 "
                "windows, survival >=5%, drawdown drift <=0.5pp, concentration "
                "guard passes, accepted compression and distribution comparators "
                "are beaten, and the shared helper reproduces exp-20260616-014."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260616_015_sbc_burden_improvement_shared_adapter.py"
            ),
        },
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "raw SEC companyfacts annual stock-based compensation facts",
                "raw SEC companyfacts annual revenue facts",
                "raw SEC companyfacts annual gross-profit facts",
                "raw SEC companyfacts filed date and period end",
                "warehouse ticker_universe CIK mapping",
                "warehouse OHLCV Date/Open/High/Low/Close/Volume",
                "SPY OHLCV for relative strength",
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
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
                "No new core filter is added. The helper is default-off paper; core "
                "signals generated/survived are unchanged from baseline."
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
        "quality_index_summary": quality_summary,
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
    live_readiness = evaluate_live_readiness(
        envelope=EXECUTION_ENVELOPE,
        closed_forward_trades=0,
        forward_pnl=None,
        replacement_value_passed=False,
        kill_switch_parity_passed=False,
    )
    fs_verdict = full_stack_verdict(
        gate4=gate4,
        live_readiness=live_readiness,
        envelope=EXECUTION_ENVELOPE,
    )
    payload["gate4"] = gate4
    payload["full_stack_verdict"] = fs_verdict
    payload["status"] = "accepted" if gate4["passed"] else "rejected"
    payload["decision"] = gate4["decision"]
    payload["accepted"] = bool(gate4["passed"])
    payload["accepted_alpha"] = bool(gate4["passed"])
    payload["numeric_gate4_passed"] = bool(gate4["passed"])
    payload["expected_value_score_delta"] = aggregate["expected_value_score_delta_sum"]
    payload["total_pnl_delta"] = aggregate["total_pnl_delta_sum"]
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": 1 if gate4["passed"] else 0,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
        "surprise_note": (
            "Shared helper reproduced the positive SBC burden-improvement replay lead."
            if gate4["passed"]
            else "Shared helper failed reproduction or Gate 4."
        ),
    }
    payload["interpretation"] = (
        "Accepted for shared default-off paper observation only. The SBC burden "
        "improvement replay lead reproduced through a shared daily/backtest helper, "
        "but live activation remains blocked by forward replacement-value rows and "
        "kill-switch parity."
        if gate4["passed"]
        else (
            "The SBC burden-improvement lead failed shared-helper promotion. Do not "
            "retain this helper as accepted alpha or tune nearby SBC thresholds on "
            "the frozen windows."
        )
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The shared helper reproduced the private replay lead because it kept "
            "the exact filed-date raw Companyfacts SBC/revenue/gross-profit gates, "
            "SPY-relative price confirmation, top-1/day selection, 10-day cooldown, "
            "next-open paper entry, 10-day exit, costs, and concentration semantics "
            "while adding a daily pending/open/closed state surface."
            if gate4["passed"]
            else (
                "The helper failed reproduction or Gate 4, indicating the private "
                "lead depended on implementation details or remained too fragile "
                "after shared daily semantics."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not sweep SBC tag lists, SBC/revenue thresholds, revenue or "
            "gross-profit floors, annual fact freshness, RS/close/volume/vol guards, "
            "top-N, hold days, cooldown, or notional on these frozen windows."
        ),
        "new_evidence_required": (
            "Next useful evidence is closed forward replacement-value rows from the "
            "shared default-off ledger, per-share SBC burden net of buybacks, or "
            "grant-value normalization. Live activation requires forward paper "
            "maturation and kill-switch parity, not a new threshold search."
        ),
    }
    payload["next_retry_requires"] = [
        "closed forward replacement-value rows",
        "per-share SBC burden net of buybacks",
        "grant-value normalization",
        "no frozen-window parameter retune",
    ]
    payload["related_files"] = [
        "quant/sbc_burden_improvement_paper_sleeve.py",
        "quant/test_sbc_burden_improvement_paper_sleeve.py",
        "quant/run.py",
        "docs/production_backtest_parity_matrix.md",
        "docs/experiment_registry.json",
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(ARTIFACT_MD),
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
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} SBC Burden Improvement Shared Adapter",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            f"Full-stack verdict: `{payload['full_stack_verdict']['verdict']}`",
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
            "- Accepted compression comparator EV/PnL: `{:+.4f}` / `${:+,.2f}`".format(
                ACCEPTED_COMPRESSION_COMPARATOR["expected_value_score_delta_sum"],
                ACCEPTED_COMPRESSION_COMPARATOR["total_pnl_delta_sum"],
            ),
            "- Accepted distribution comparator EV/PnL: `{:+.4f}` / `${:+,.2f}`".format(
                ACCEPTED_DISTRIBUTION_COMPARATOR["expected_value_score_delta_sum"],
                ACCEPTED_DISTRIBUTION_COMPARATOR["total_pnl_delta_sum"],
            ),
            "",
            "## Production Impact",
            "",
            (
                "Shared default-off paper helper and daily snapshot only. "
                "`trade_enabled=false`; live/default orders, ranking, sizing, exits, "
                "LLM/news, and watchlists are unchanged."
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
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "numeric_gate4_passed": payload["numeric_gate4_passed"],
        "mechanism_family": payload["mechanism_family"],
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
        "full_stack_verdict": payload["full_stack_verdict"],
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
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "gate4": payload["gate4"],
        "full_stack_verdict": payload["full_stack_verdict"],
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
        QUANT_ROOT / "sbc_burden_improvement_paper_sleeve.py",
        QUANT_ROOT / "test_sbc_burden_improvement_paper_sleeve.py",
        QUANT_ROOT / "run.py",
        PRODUCTION_PARITY_MATRIX_MD,
        REGISTRY_JSON,
        EXPERIMENT_LOG,
        OUT_JSON,
        LOG_JSON,
        TICKET_JSON,
        CARD_MD,
        ARTIFACT_MD,
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
    card = _build_card(payload)
    framework._write_text(CARD_MD, card)
    framework._write_text(ARTIFACT_MD, card)
    framework._upsert_jsonl(EXPERIMENT_LOG, _build_log_record(payload))
    _update_registry(payload)
    _write_manifest(payload)


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps(framework._safe(_build_log_record(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
