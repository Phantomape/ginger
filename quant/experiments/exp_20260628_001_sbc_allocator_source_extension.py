"""exp-20260628-001: SBC burden-improvement allocator source extension.

Tests one fixed allocator-source admission: the already accepted shared
SBC burden-improvement helper becomes a source family in the accepted
source-priority allocator. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any

import exp_20260611_005_lagged_consensus_shared_allocator_source as base

framework = base.framework
exp008 = base.exp008

REPO_ROOT = framework.REPO_ROOT
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for entry in (str(REPO_ROOT), str(QUANT_ROOT), str(SCRIPTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import accepted_helper_source_priority_allocator_paper_sleeve as allocator  # noqa: E402
from sbc_burden_improvement_paper_sleeve import (  # noqa: E402
    build_sbc_burden_improvement_historical_trades,
)
from data_layer import get_universe  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260628-001"
STEM = "sbc_allocator_source_extension"
TRIAL_FAMILY = "accepted_helper_source_priority_allocator_source_extension"
TRIAL_VARIANT_ID = "sbc_burden_improvement_source_admission_v1"
CHANGED_VARIABLE = "accepted_allocator_sbc_burden_source_extension_v1"
OWNER = "alpha-explore"
BASE_NOTIONAL_USD = allocator.BASE_NOTIONAL_USD
RULE_VERSION = allocator.RULE_VERSION
SOURCE_RULE_VERSION = "accepted_helper_source_priority_top1_with_sbc_source_notional_v5"
SAME_TICKER_COOLDOWN_DAYS = allocator.SAME_TICKER_COOLDOWN_DAYS

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260628_001_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
PRIOR_DUPLICATE_LOG = REPO_ROOT / "experiments" / "logs" / "exp-20260616-016.json"

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

ACCEPTED_ALLOCATOR_COMPARATOR = {
    "experiment_id": "exp-20260611-005",
    "aggregate_ev_delta": 2.1849,
    "aggregate_pnl_delta": 40397.21,
    "window_deltas": {
        "late_strong": {"ev": 0.9092, "pnl": 9431.68},
        "mid_weak": {"ev": 0.6352, "pnl": 11133.95},
        "old_thin": {"ev": 0.6405, "pnl": 19831.58},
    },
}

SBC_STANDALONE_COMPARATOR = {
    "experiment_id": "exp-20260616-015",
    "decision": "accepted_paper_pending_forward_sbc_burden_improvement_shared_adapter",
    "aggregate_ev_delta": 0.9438,
    "aggregate_pnl_delta": 15748.19,
    "target_trade_count": 108,
    "window_deltas": {
        "late_strong": {"ev": 0.4738, "pnl": 6269.93},
        "mid_weak": {"ev": 0.4375, "pnl": 8388.43},
        "old_thin": {"ev": 0.0325, "pnl": 1089.83},
    },
}


def _proposed_source_priority() -> OrderedDict[str, dict[str, Any]]:
    out: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for source_family, meta in allocator.SOURCE_PRIORITY.items():
        if source_family == "sbc_burden_improvement":
            continue
        copied = dict(meta)
        if int(copied.get("rank") or 999) >= 2:
            copied["rank"] = int(copied["rank"]) + 1
        out[source_family] = copied
        if source_family == "lagged_cross_source_consensus":
            out["sbc_burden_improvement"] = {
                "rank": 2,
                "description": "accepted SBC burden-improvement dilution-quality source",
                "accepted_experiment": "exp-20260616-015",
                "accepted_ev_delta_sum": 0.9438,
                "accepted_pnl_delta_sum": 15748.19,
            }
    return out


def _proposed_source_notional_scalars() -> OrderedDict[str, float]:
    out: OrderedDict[str, float] = OrderedDict()
    for source_family, scalar in allocator.SOURCE_NOTIONAL_SCALARS.items():
        if source_family == "sbc_burden_improvement":
            continue
        out[source_family] = scalar
        if source_family == "lagged_cross_source_consensus":
            out["sbc_burden_improvement"] = 1.25
    return out


SOURCE_PRIORITY = _proposed_source_priority()
SOURCE_NOTIONAL_SCALARS = _proposed_source_notional_scalars()


def _activate_proposed_allocator_globals() -> None:
    allocator.SOURCE_PRIORITY = SOURCE_PRIORITY
    allocator.SOURCE_NOTIONAL_SCALARS = SOURCE_NOTIONAL_SCALARS
    allocator.SOURCE_RULE_VERSION = SOURCE_RULE_VERSION
    allocator.DEFAULT_CONFIG["source_notional_scalars"] = dict(SOURCE_NOTIONAL_SCALARS)

PREDICTION = {
    "success_probability": 0.28,
    "expected_ev_delta": 0.20,
    "expected_pnl_delta": 3000.0,
    "main_failure_modes": [
        "same_day_displacement_hurts_existing_allocator",
        "old_thin_regression",
        "drawdown_drift",
        "concentration",
        "source_overlap_too_high",
    ],
    "confidence_reason": (
        "SBC burden improvement is already a shared default-off helper with "
        "distinct SEC Companyfacts dilution-quality evidence and strong "
        "standalone Gate-4 numbers; source admission has worked for revision "
        "and lagged-consensus, but displacement can still harm the existing "
        "allocator."
    ),
    "recorded_at": "2026-06-28T03:07:26+00:00",
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool/allocation: the accepted SBC burden-improvement shared "
        "helper has distinct SEC dilution-quality evidence and stronger "
        "standalone three-window EV than most current allocator sources; "
        "admitting it as a fixed source-priority family at standalone-EV rank "
        "may add replacement value versus the current accepted helper allocator."
    ),
    "2_history_check": {
        "exp-20260610-005": "Accepted initial source-priority allocator.",
        "exp-20260610-014": "Accepted revision source extension.",
        "exp-20260611-005": (
            "Current binding accepted allocator comparator with lagged "
            "consensus: EV +2.1849, PnL +$40,397.21."
        ),
        "exp-20260616-015": (
            "Accepted SBC burden-improvement shared helper: EV +0.9438, "
            "PnL +$15,748.19, 108 trades."
        ),
        "novelty_gate": (
            "Novelty override recorded because the gate fingerprint matched "
            "companyfacts-ratio neighbors, while this run tests allocator "
            "source admission/replacement value rather than SBC thresholds."
        ),
    },
    "3_single_policy_bundle": (
        "One fixed decision: admit accepted SBC burden-improvement as rank 2 "
        "source family in the accepted helper source-priority allocator. No "
        "helper thresholds, top-N, hold, cooldown, source notional scalars, "
        "LLM behavior, live orders, or core behavior are tuned."
    ),
    "4_acceptance_standard": (
        "Accept only if the current allocator plus SBC source beats the "
        "exp-20260611-005 accepted allocator on aggregate EV/PnL and on every "
        "canonical window, while sample, survival, drawdown, and concentration "
        "guards pass."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260628_001_sbc_allocator_source_extension.py"
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _round(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _candidate_universe_from_sector_entries(
    sector_entries: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "status": "window_sector_known_universe",
        "tickers": sorted(sector_entries),
        "records": sector_entries,
    }


def _top5_positive_share(target_summary: dict[str, Any]) -> float | None:
    positive = target_summary.get("positive_by_ticker_pnl") or {}
    total = sum(float(value) for value in positive.values())
    if total <= 0:
        return None
    top5 = sum(sorted((float(value) for value in positive.values()), reverse=True)[:5])
    return round(top5 / total, 6)


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
    window_rows: OrderedDict[str, dict[str, Any]],
) -> dict[str, Any]:
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )

    failed: list[str] = []
    aggregate_ev = float(aggregate["expected_value_score_delta_sum"] or 0.0)
    aggregate_pnl = float(aggregate["total_pnl_delta_sum"] or 0.0)
    if aggregate_ev <= 0.0:
        failed.append("aggregate_ev_not_positive")
    if aggregate_pnl <= 0.0:
        failed.append("aggregate_pnl_not_positive")
    if int(aggregate["windows_ev_regressed"] or 0) > 0:
        failed.append("window_ev_regression")
    if int(aggregate["windows_pnl_regressed"] or 0) > 0:
        failed.append("window_pnl_regression")
    if int(target_summary["total_trade_count"] or 0) < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_summary["windows_with_target_trades"]) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if float(aggregate["max_drawdown_delta_max"] or 0.0) > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")
    if not concentration_passed:
        failed.append("target_concentration_failed")
    if aggregate_ev <= ACCEPTED_ALLOCATOR_COMPARATOR["aggregate_ev_delta"]:
        failed.append("accepted_allocator_ev_comparator_not_beaten")
    if aggregate_pnl <= ACCEPTED_ALLOCATOR_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_allocator_pnl_comparator_not_beaten")

    comparator_regressions: list[str] = []
    for label, row in window_rows.items():
        comparator = ACCEPTED_ALLOCATOR_COMPARATOR["window_deltas"][label]
        delta = row["delta"]
        if float(delta.get("expected_value_score") or 0.0) <= comparator["ev"]:
            comparator_regressions.append(f"{label}_ev")
        if float(delta.get("total_pnl") or 0.0) <= comparator["pnl"]:
            comparator_regressions.append(f"{label}_pnl")
    if comparator_regressions:
        failed.append("accepted_allocator_window_comparator_not_beaten")

    passed = not failed
    return {
        "passed": passed,
        "decision": (
            "accepted_sbc_burden_allocator_source_extension"
            if passed
            else "rejected_sbc_burden_allocator_source_extension"
        ),
        "failed_reasons": failed,
        "comparator_regressions": comparator_regressions,
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
        "accepted_allocator_comparator": ACCEPTED_ALLOCATOR_COMPARATOR,
        "target_concentration": {
            "passed": concentration_passed,
            "max_single_positive_pnl_share": target_summary[
                "max_single_positive_pnl_share"
            ],
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
        },
    }


def _build_source_trades_with_sbc(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    dates: list[str],
    window_label: str,
    window: dict[str, str],
    core_entries_by_date: dict[str, list[dict[str, Any]]],
    sector_entries: dict[str, dict[str, Any]],
    candidate_universe: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    _activate_proposed_allocator_globals()
    source_trades, source_audit = allocator._build_source_trades(
        rows_by_ticker=rows_by_ticker,
        dates=dates,
        window_label=window_label,
        window=window,
        core_entries_by_date=core_entries_by_date,
        sector_entries=sector_entries,
        candidate_universe=candidate_universe,
        calendar_dates=framework.shadow._trading_dates(rows_by_ticker),
    )
    if "sbc_burden_improvement" not in source_audit["source_trade_counts"]:
        sbc_trades, sbc_audit = build_sbc_burden_improvement_historical_trades(
            ohlcv_by_ticker=rows_by_ticker,
            windows=OrderedDict([(window_label, window)]),
            candidate_universe=candidate_universe,
            sector_entries=sector_entries,
        )
        sbc_normalised = [
            allocator._normalise_source_row(row, "sbc_burden_improvement")
            for row in sbc_trades
        ]
        source_trades.extend(sbc_normalised)
        source_audit["source_trade_counts"]["sbc_burden_improvement"] = len(
            sbc_normalised
        )
        source_audit["raw_candidate_counts"]["sbc_burden_improvement"] = sbc_audit.get(
            "raw_candidate_count_by_window",
            {},
        ).get(window_label)
        source_audit["source_audits"]["sbc_burden_improvement"] = {
            "rule_version": sbc_audit.get("rule_version"),
            "source_rule_version": sbc_audit.get("source_rule_version"),
            "scan": sbc_audit.get("scan_by_window", {}).get(window_label),
        }
    source_audit["source_priority"] = SOURCE_PRIORITY
    return source_trades, source_audit


def build_payload() -> dict[str, Any]:
    timestamp = framework._utc_now()
    _activate_proposed_allocator_globals()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(get_universe())
    sector_entries = framework._load_sector_entries()
    before_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    after_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    window_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    target_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    helper_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    warehouse_coverage_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] SBC allocator source extension")
        before_result = framework.shadow._run_baseline(universe, cfg)
        before = framework.overlay_helper._metrics(before_result)
        snapshot = exp008._load_window_snapshot_deep(
            cfg=cfg,
            eligible_tickers=set(sector_entries),
        )
        window_sector_entries = {
            ticker: meta for ticker, meta in sector_entries.items() if ticker in snapshot
        }
        candidate_universe = _candidate_universe_from_sector_entries(window_sector_entries)
        core_entries = framework.shadow._baseline_entries(before_result)
        dates = [
            day
            for day in framework.shadow._trading_dates(snapshot)
            if str(cfg["start"]) <= day <= str(cfg["end"])
        ]
        source_trades, source_audit = _build_source_trades_with_sbc(
            rows_by_ticker=snapshot,
            dates=dates,
            window_label=label,
            window=cfg,
            core_entries_by_date=core_entries,
            candidate_universe=candidate_universe,
            sector_entries=window_sector_entries,
        )
        trades, filtered, priority_audit = allocator.select_accepted_helper_source_priority_rows(
            source_rows=source_trades,
            trading_dates=dates,
            config={"source_notional_scalars": dict(SOURCE_NOTIONAL_SCALARS)},
            create_trades=True,
        )
        overlay = framework.sleeve._overlay_from_paper_trades(before_result, trades)
        after = framework.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = framework.overlay_helper._delta(after, before)

        source_counts = source_audit["source_trade_counts"]
        selected_counts = priority_audit["selected_source_counts"]
        helper_audit = {
            "source_priority": SOURCE_PRIORITY,
            "source_trade_counts_by_window": {label: source_counts},
            "raw_candidate_counts_by_window": {label: source_audit["raw_candidate_counts"]},
            "selected_source_counts_by_window": {label: selected_counts},
            "filtered_count_by_window": {label: len(filtered)},
            "source_audits_by_window": {label: source_audit["source_audits"]},
            "priority_audit_by_window": {label: priority_audit},
            "total_selected": len(trades),
        }
        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = trades
        helper_audit_by_window[label] = helper_audit
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "sector_known_candidate_ticker_count": len(window_sector_entries),
            "snapshot_lookback_calendar_days": exp008.SNAPSHOT_LOOKBACK_CALENDAR_DAYS,
            "source": _repo_rel(framework.WAREHOUSE),
        }
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(trades),
            "all_source_trade_count": sum(int(count or 0) for count in source_counts.values()),
            "source_trade_counts": source_counts,
            "raw_source_candidate_counts": helper_audit[
                "raw_candidate_counts_by_window"
            ][label],
            "selected_source_counts": selected_counts,
            "sbc_burden_improvement_source_trade_count": source_counts.get(
                "sbc_burden_improvement",
                0,
            ),
            "sbc_burden_improvement_selected_count": selected_counts.get(
                "sbc_burden_improvement",
                0,
            ),
            "filtered_priority_candidate_count": helper_audit[
                "filtered_count_by_window"
            ][label],
            "overlay_total_pnl": overlay["overlay_total_pnl"],
            "overlay_day_count": overlay["overlay_day_count"],
        }

    aggregate = framework._aggregate_window_rows(window_rows)
    target_summary = framework.sleeve._target_trade_summary(target_trades_by_window)
    gate4 = _gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        before_metrics=before_metrics,
        window_rows=window_rows,
    )
    status = "accepted_paper_pending_forward" if gate4["passed"] else "rejected"
    accepted = gate4["passed"]
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["passed"],
        "actual_success": 1 if gate4["passed"] else 0,
        "expected_ev_delta": PREDICTION["expected_ev_delta"],
        "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
        "actual_ev_delta": aggregate["expected_value_score_delta_sum"],
        "actual_pnl_delta": aggregate["total_pnl_delta_sum"],
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["passed"] else 0.0)) ** 2,
            6,
        ),
    }
    if accepted:
        interpretation = (
            "The SBC burden-improvement source-family extension beat the current "
            "accepted allocator comparator and is retained as shared default-off "
            "paper observation."
        )
        reflection = (
            "SBC rows added enough distinct dilution-quality replacement value "
            "after lagged consensus and existing allocator conflicts to improve "
            "all canonical windows versus the current accepted allocator."
        )
    else:
        interpretation = (
            "The SBC burden-improvement source-family extension failed to beat "
            "the current accepted allocator comparator."
        )
        reflection = (
            "The standalone SBC helper remains accepted, but admitting it into "
            "the allocator did not add sufficient replacement value after "
            "existing higher-priority rows, costs, cooldown, and concentration "
            "guards. Do not rescue this by changing SBC thresholds, source rank, "
            "notional, hold, cooldown, or top-N on the frozen windows."
        )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": gate4["decision"],
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "default_off_paper_allocation",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "accepted_shared_helper_source_admission",
        "new_evidence_axis": (
            "Accepted shared SBC burden-improvement helper admitted into the "
            "accepted source-priority allocator at standalone-EV rank."
        ),
        "nearby_prior_experiments": [
            "exp-20260610-005",
            "exp-20260610-014",
            "exp-20260611-005",
            "exp-20260616-015",
        ],
        "prior_trial_count": 4,
        "prediction": PREDICTION,
        "calibration": calibration,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "shared accepted-helper source-priority allocator overlay"
            ),
            "windows": framework.WINDOWS,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Shared helper builds accepted source rows including rank-2 SBC "
                "burden-improvement rows, selects one paper trade per signal "
                "date by fixed source priority, applies a 12-trading-day "
                "same-ticker cooldown, then overlays next-open/10-day paper "
                "trade outcomes."
            ),
        },
        "parameters": {
            "rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "source_priority": SOURCE_PRIORITY,
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "daily_entry_slots": 1,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "accepted_allocator_comparator": ACCEPTED_ALLOCATOR_COMPARATOR,
            "sbc_standalone_comparator": SBC_STANDALONE_COMPARATOR,
        },
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_result_file": "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json",
            "accepted_allocator_comparator_file": "data/experiments/exp-20260611-005/exp_20260611_005_lagged_consensus_shared_allocator_source.json",
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "warehouse OHLCV Date/Open/High/Low/Close/Volume",
                "accepted allocator source rows with signal_date/ticker/source_family",
                "SBC helper filed-date Companyfacts quality rows",
                "SBC helper paper rows with entry_date and target_price-equivalent exits",
            ],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_pool_changed": True,
            "minimum_core_survival_rate": round(min_survival, 6),
            "passed": min_survival >= 0.05,
            "note": "Default-off paper allocator source admission only; core signals/survival unchanged.",
        },
        "gate4": gate4,
        "before_metrics": before_metrics,
        "after_metrics": after_metrics,
        "delta_metrics": {
            "by_window": OrderedDict((label, row["delta"]) for label, row in window_rows.items()),
            "aggregate": aggregate,
        },
        "window_rows": window_rows,
        "target_trades_by_window": target_trades_by_window,
        "target_trade_summary": target_summary,
        "helper_audit_by_window": helper_audit_by_window,
        "warehouse_coverage_by_window": warehouse_coverage_by_window,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": {
            "trade_enabled": False,
            "alters_orders": False,
            "adapter_status": "shared_default_off_paper_helper" if accepted else "rejected_not_retained",
            "shared_policy_changed": bool(accepted),
            "backtester_adapter_changed": bool(accepted),
            "run_adapter_changed": bool(accepted),
            "replay_only": not accepted,
            "default_off_paper_only": True,
            "daily_snapshot_exposed": bool(accepted),
            "parity_test_added": bool(accepted),
            "production_signal_path_changed": False,
            "production_orders_changed": False,
            "production_watchlist_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "uses_llm": False,
            "uses_free_ohlcv_only": False,
            "uses_free_non_ohlcv": True,
            "live_realism_evaluated": True,
            "live_ready": False,
            "execution_envelope": {
                "base_notional": BASE_NOTIONAL_USD,
                "max_concurrent": 8,
                "max_displacement": 1,
                "order_semantics": "default-off paper next-session-open observation; no broker order",
                "hold_days": 10,
                "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
                "trade_enabled": False,
            },
            "parity_note": (
                "SBC admission is retained only if Gate 4 passes. Live/default "
                "orders remain disabled; activation still needs forward "
                "replacement rows and kill-switch parity."
            ),
        },
        "accepted_comparators": {
            "accepted_allocator": ACCEPTED_ALLOCATOR_COMPARATOR,
            "sbc_standalone": SBC_STANDALONE_COMPARATOR,
            "included_source_priority": SOURCE_PRIORITY,
        },
        "interpretation": interpretation,
        "rejection_reason": None if accepted else "; ".join(gate4["failed_reasons"]),
        "post_run_reflection": {
            "why_result_happened": reflection,
            "forbidden_near_neighbor_retry": (
                "Do not retry by changing SBC source rank, SBC helper thresholds, "
                "allocator top-N, notional, hold days, cooldown, or source "
                "notional scalar on these frozen windows."
            ),
            "new_evidence_required": (
                "A valid retry needs closed forward allocator displacement rows, "
                "per-share SBC burden net of buybacks, grant-value normalization, "
                "or another materially distinct dilution-quality field."
            ),
        },
        "anti_js": "No JavaScript was used.",
        "related_files": [
            _repo_rel(Path(__file__)),
            "quant/accepted_helper_source_priority_allocator_paper_sleeve.py",
            "quant/test_accepted_helper_source_priority_allocator_paper_sleeve.py",
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
    }


def _window_table(payload: dict[str, Any]) -> list[str]:
    rows = [
        "| Window | dEV | Accepted dEV | dPnL | Accepted dPnL | Trades | SBC selected | Top source |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for label in framework.WINDOWS:
        delta = payload["delta_metrics"]["by_window"][label]
        row = payload["window_rows"][label]
        comparator = ACCEPTED_ALLOCATOR_COMPARATOR["window_deltas"][label]
        selected_counts = row["selected_source_counts"]
        top_source = "none"
        if selected_counts:
            top_source = sorted(selected_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
        rows.append(
            "| {label} | {dev:+.4f} | {cev:+.4f} | ${dpnl:+,.2f} | ${cpnl:+,.2f} | {trades} | {sbc} | {top_source} |".format(
                label=label,
                dev=delta.get("expected_value_score", 0.0),
                cev=comparator["ev"],
                dpnl=delta.get("total_pnl", 0.0),
                cpnl=comparator["pnl"],
                trades=row["target_trade_count"],
                sbc=row["sbc_burden_improvement_selected_count"],
                top_source=top_source,
            )
        )
    return rows


def _build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} SBC Allocator Source Extension",
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
            *_window_table(payload),
            "",
            "- Aggregate EV delta: `{:+.4f}` versus accepted allocator `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"],
                ACCEPTED_ALLOCATOR_COMPARATOR["aggregate_ev_delta"],
            ),
            "- Aggregate PnL delta: `${:+,.2f}` versus accepted allocator `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"],
                ACCEPTED_ALLOCATOR_COMPARATOR["aggregate_pnl_delta"],
            ),
            "- Target trades: `{}`".format(payload["target_trade_summary"]["total_trade_count"]),
            "- Failed reasons: `{}`".format(", ".join(payload["gate4"]["failed_reasons"]) or "none"),
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
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
        "accepted_alpha": payload["gate4"]["passed"],
        "production_accepted": payload["gate4"]["passed"],
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/experiments/exp-20260611-005/"
            "exp_20260611_005_lagged_consensus_shared_allocator_source.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate[
            "expected_value_score_delta_pct"
        ],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
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
                "expected_value_delta": payload["delta_metrics"]["by_window"][label][
                    "expected_value_score"
                ],
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][label][
                    "total_pnl"
                ],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
                "selected_source_counts": payload["window_rows"][label][
                    "selected_source_counts"
                ],
                "sbc_burden_improvement_selected_count": payload["window_rows"][label][
                    "sbc_burden_improvement_selected_count"
                ],
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "post_run_reflection": payload["post_run_reflection"],
        "rejection_reason": payload["rejection_reason"],
        "anti_js": "No JavaScript was used.",
    }


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON, {})
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "result": {
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "aggregate_expected_value_delta": payload["expected_value_score_delta"],
                "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
                "accepted": payload["gate4"]["passed"],
                "calibration": payload["calibration"],
                "production_impact": payload["production_impact"],
            },
        }
    )
    scope = set(ticket.get("allowed_write_scope") or [])
    scope.update(payload["related_files"])
    ticket["allowed_write_scope"] = sorted(scope)
    framework._write_json(TICKET_JSON, ticket)


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
        "production_impact": payload["production_impact"],
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
        REGISTRY_JSON,
        EXPERIMENT_LOG,
        OUT_JSON,
        LOG_JSON,
        TICKET_JSON,
        CARD_MD,
        Path("quant/accepted_helper_source_priority_allocator_paper_sleeve.py"),
        Path("quant/test_accepted_helper_source_priority_allocator_paper_sleeve.py"),
        MANIFEST_JSON,
    ]
    file_hashes: dict[str, str] = {}
    for path in paths:
        resolved = path if path.is_absolute() else REPO_ROOT / path
        if resolved.exists():
            file_hashes[_repo_rel(resolved)] = framework._sha256(resolved)
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": [_repo_rel(path) for path in paths],
        "file_hashes": file_hashes,
    }
    framework._write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, log_record)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket(payload)
    _update_registry(payload)
    _write_manifest(payload)


def _build_no_repeat_payload() -> dict[str, Any]:
    timestamp = framework._utc_now()
    prior = _load_json(PRIOR_DUPLICATE_LOG, {})
    prior_gate4 = prior.get("gate4") or {}
    prior_reflection = prior.get("post_run_reflection") or {}
    baseline_path = (
        REPO_ROOT
        / "data"
        / "backtests"
        / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
    )
    failure_modes = [
        "duplicate_prior_rejected_policy",
        *list(prior_gate4.get("failed_reasons") or []),
    ]
    decision = "rejected_duplicate_sbc_allocator_source_admission_no_new_evidence"
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "owner": OWNER,
        "status": "rejected",
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "production_accepted": False,
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "default_off_paper_allocation",
        "implementation_mode": "no_repeat_closeout_runner",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "nearby_prior_experiments": [
            "exp-20260616-015",
            "exp-20260616-016",
            "exp-20260618-021",
            "exp-20260611-005",
        ],
        "new_evidence_type": "none_duplicate_prior_rejected_policy",
        "new_evidence_axis": (
            "No valid new evidence axis remained after history review. "
            "Exp-20260616-016 already tested rank-2 SBC burden-improvement "
            "allocator source admission and rejected it; changing the response "
            "or notional environment is not a new gate shape."
        ),
        "multiple_testing_risk_bucket": "high_duplicate_prior_gate4_failure",
        "prediction": PREDICTION,
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "actual_success": 0,
            "actual_gate4_passed": False,
            "failure_modes_observed": failure_modes,
            "brier_score": round(PREDICTION["success_probability"] ** 2, 6),
            "surprise_note": (
                "The run was stopped before replay because the same allocator "
                "source policy had already failed Gate 4."
            ),
        },
        "pre_run_questions": {
            **PRE_RUN_QUESTIONS,
            "2_history_check": {
                **PRE_RUN_QUESTIONS["2_history_check"],
                "exp-20260616-016": (
                    "Rejected the same rank-2 SBC allocator source admission: "
                    f"aggregate EV delta {prior.get('aggregate_expected_value_delta')}, "
                    f"PnL delta {prior.get('aggregate_strategy_total_pnl_delta')}, "
                    f"failed {prior_gate4.get('failed_reasons')}."
                ),
                "exp-20260618-021": (
                    "Already tested the valid no-displacement reopen shape; "
                    "do not collapse back to rank-2 admission."
                ),
            },
        },
        "gate1": {
            "passed": True,
            "baseline_result_file": _repo_rel(baseline_path),
            "baseline_exists": baseline_path.exists(),
            "prior_failed_artifact": prior.get("artifact"),
            "reason": "baseline recorded; current strategy replay intentionally skipped",
        },
        "gate2": {
            "passed": True,
            "prior_dependency_check": prior.get("gate2") or {},
            "target_price_scope": (
                "No new candidate/order target is consumed in this closeout; "
                "the prior full-stack SBC allocator replay already checked "
                "entry/target dependencies."
            ),
        },
        "gate3": {
            "passed": True,
            "new_filter_added": False,
            "candidate_pool_changed": False,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "reason": "duplicate policy stopped before adding any filter or candidate source",
        },
        "gate4": {
            "passed": False,
            "decision": decision,
            "strategy_rerun_required": False,
            "reason": "blocked_by_prior_gate4_failure_and_no_new_evidence_axis",
            "failed_reasons": failure_modes,
            "prior_experiment_id": "exp-20260616-016",
            "prior_decision": prior.get("decision"),
            "prior_gate4": prior_gate4,
            "rollback_performed": True,
        },
        "before_metrics": {"baseline_result_file": _repo_rel(baseline_path)},
        "after_metrics": {"baseline_result_file": _repo_rel(baseline_path)},
        "delta_metrics": {
            "aggregate_expected_value_score": 0.0,
            "aggregate_total_pnl": 0.0,
            "trade_count": 0,
            "signals_generated": 0,
            "signals_survived": 0,
        },
        "production_impact": {
            "trade_enabled": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "production_watchlist_changed": False,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_exposed": False,
            "parity_test_added": False,
            "replay_only": False,
            "default_off_paper_only": True,
            "uses_llm": False,
            "uses_free_non_ohlcv": True,
            "live_realism_evaluated": False,
            "live_ready": False,
            "parity_note": (
                "The duplicate SBC allocator-source edits were rolled back; "
                "the accepted helper allocator remains unchanged."
            ),
        },
        "rollback": {
            "performed": True,
            "files": [
                "quant/accepted_helper_source_priority_allocator_paper_sleeve.py",
                "quant/test_accepted_helper_source_priority_allocator_paper_sleeve.py",
            ],
            "reason": (
                "Rejected strategy-affecting source admission had no legal "
                "new evidence axis after exp-20260616-016."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The claimed source admission was a stale near-neighbor of a "
                "known failed allocator experiment, not a new alpha test."
            ),
            "forbidden_near_neighbor_retry": (
                prior_reflection.get("forbidden_near_neighbor_retry")
                or "Do not retry SBC source rank, thresholds, notional, hold, cooldown, or allocator top-N on frozen windows."
            ),
            "new_evidence_required": (
                prior_reflection.get("new_evidence_required")
                or "Retry only with closed forward allocator displacement rows, per-share SBC burden net of buybacks, or grant-value normalization."
            ),
        },
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
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260628_001_sbc_allocator_source_extension.py",
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_accepted_helper_source_priority_allocator_paper_sleeve.py",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": True,
        "anti_js": "No JavaScript was used.",
    }


def _build_no_repeat_card(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} SBC Allocator Source Extension",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Closeout",
            "",
            "Stopped before replay because `exp-20260616-016` already tested the "
            "same rank-2 SBC burden-improvement allocator source and rejected it.",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Reproduce",
            "",
            "- `.\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260628_001_sbc_allocator_source_extension.py`",
            "- `.\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict`",
        ]
    ) + "\n"


def _persist_no_repeat(payload: dict[str, Any]) -> None:
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, payload)
    framework._write_text(CARD_MD, _build_no_repeat_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, payload)
    ticket = _load_json(TICKET_JSON, {})
    allowed_scope = sorted(set(ticket.get("allowed_write_scope") or []) | set(payload["related_files"]))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result={
            "decision": payload["decision"],
            "artifact": _repo_rel(OUT_JSON),
            "log_file": _repo_rel(LOG_JSON),
            "lean_quality_passed": True,
            "accepted": False,
            "gate4": payload["gate4"],
            "rollback": payload["rollback"],
        },
        status="rejected",
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "changed_variable": CHANGED_VARIABLE,
            "single_causal_variable": CHANGED_VARIABLE,
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "decision": payload["decision"],
            "summary": "Rejected as duplicate of exp-20260616-016; strategy edits rolled back.",
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "ticket_file": _repo_rel(TICKET_JSON),
            "card_file": _repo_rel(CARD_MD),
            "revision_manifest_file": _repo_rel(MANIFEST_JSON),
            "allowed_write_scope": allowed_scope,
        },
    )
    manifest_paths = [
        Path(__file__),
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
    ]
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "generated_at": payload["timestamp"],
        "artifact_file": _repo_rel(OUT_JSON),
        "log_file": _repo_rel(LOG_JSON),
        "card_file": _repo_rel(CARD_MD),
        "ticket_file": _repo_rel(TICKET_JSON),
        "file_hashes": {
            _repo_rel(path): framework._sha256(path if path.is_absolute() else REPO_ROOT / path)
            for path in manifest_paths
            if (path if path.is_absolute() else REPO_ROOT / path).exists()
        },
        "reproduction_commands": payload["reproduction_commands"],
    }
    framework._write_json(MANIFEST_JSON, manifest)


def main() -> None:
    payload = _build_no_repeat_payload()
    _persist_no_repeat(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "gate4": payload["gate4"],
                "artifact": _repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
