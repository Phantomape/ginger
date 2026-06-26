"""exp-20260625-019: moomoo short-volume clean-flow gate.

Full-stack candidate-pool experiment for the exp-20260625-018 observed-only
lead. The single policy hypothesis is a negative quality gate over the already
accepted source-priority allocator: keep accepted allocator rows unless their
PIT per-ticker moomoo daily ``short_volume_ratio`` percentile is in toxic Q5.

The binding before/after comparison is the current ungated accepted allocator
versus the same allocator after the clean-flow gate. Core baseline context is
reported separately. No live/default orders are changed.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260605_033_cross_section_pressure_resilience_candidate_pool as framework  # noqa: E402
from accepted_helper_source_priority_allocator_paper_sleeve import (  # noqa: E402
    BASE_NOTIONAL_USD,
    EXECUTION_ENVELOPE,
    RULE_VERSION as ALLOCATOR_RULE_VERSION,
    SAME_TICKER_COOLDOWN_DAYS,
    SOURCE_PRIORITY,
    SOURCE_RULE_VERSION,
    build_accepted_helper_source_priority_allocator_historical_trades,
)
from data_layer import get_universe  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402
from short_volume_clean_flow_gate import (  # noqa: E402
    DEFAULT_SHORT_VOLUME_ROWS,
    DEFAULT_TOXIC_QUINTILE_INDEX,
    RULE_VERSION as CLEAN_FLOW_RULE_VERSION,
    apply_clean_flow_gate,
    build_short_volume_percentile_index,
    load_short_volume_ratio_history,
)


EXPERIMENT_ID = "exp-20260625-019"
OWNER = "alpha-explore"
SLUG = "moomoo_short_volume_clean_flow_gate"
RUNNER = f"quant/experiments/exp_20260625_019_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260625_019_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

MIN_CHANGED_TRADES = 9
MIN_CHANGED_WINDOWS = 2
MIN_EV_IMPROVED_WINDOWS = 2
MAX_EV_REGRESSED_WINDOWS = 0
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

HYPOTHESIS = (
    "A shared clean-flow quality gate that skips accepted source-priority "
    "allocator paper rows only when their PIT per-ticker moomoo daily "
    "short_volume_ratio percentile is in the toxic highest quintile should "
    "improve replacement value by avoiding names with informed short-sale "
    "pressure."
)
CHANGED_VARIABLE = "moomoo_daily_short_volume_clean_flow_gate_over_accepted_allocator_v1"
TRIAL_FAMILY = "moomoo_daily_short_volume_clean_flow_quality_gate"
TRIAL_VARIANT_ID = "toxic_q5_gate_over_accepted_allocator_v1"
NEW_EVIDENCE_AXIS = (
    "new PIT data source and gate shape from exp-20260625-018: "
    "moomoo_daily_short_volume short_volume_ratio expanding per-ticker "
    "percentile used as a negative clean-flow quality gate over allocator "
    "rows, not a source-priority, top-N, capacity, notional, or hold-day retune"
)
PREDICTION = {
    "success_probability": 0.32,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "accepted_allocator_overlap_too_thin",
        "filter_removes_winners",
        "bull_window_washout",
        "accepted_comparator_not_beaten",
    ],
    "confidence_reason": (
        "exp-20260625-018 found point-in-time per-ticker short_volume_ratio "
        "percentiles were sign-correct as an avoidance signal across the broad "
        "archive, with toxic Q5 underperforming clean Q1 in all three windows "
        "and about 19 percent of accepted paper-sleeve selections landing in "
        "Q5. The main risk is that filtering a long-only accepted allocator "
        "captures too little replacement value or removes too many winners."
    ),
    "recorded_at": "2026-06-25T17:05:33+00:00",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(framework.sleeve._safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    kept: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if not line.strip():
                continue
            try:
                existing = json.loads(line)
            except json.JSONDecodeError:
                kept.append(line)
                continue
            if existing.get("experiment_id") != record["experiment_id"]:
                kept.append(json.dumps(existing, sort_keys=True))
    kept.append(json.dumps(record, sort_keys=True))
    path.write_text("\n".join(kept) + "\n", encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _round(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round(number, digits) if math.isfinite(number) else None


def candidate_universe_from_sector_entries(
    sector_entries: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "status": "window_sector_known_universe",
        "tickers": sorted(sector_entries),
        "records": sector_entries,
    }


def gate4(
    *,
    aggregate: dict[str, Any],
    core_aggregate: dict[str, Any],
    skipped_summary: dict[str, Any],
    gated_summary: dict[str, Any],
    ungated_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    changed_windows = skipped_summary["windows_with_target_trades"]
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    gated_single_share = gated_summary["max_single_positive_pnl_share"]
    gated_hhi = gated_summary["positive_pnl_hhi"]
    ungated_single_share = ungated_summary["max_single_positive_pnl_share"]
    ungated_hhi = ungated_summary["positive_pnl_hhi"]

    failed: list[str] = []
    if float(aggregate["expected_value_score_delta_sum"] or 0.0) <= 0.0:
        failed.append("gate_ev_delta_not_positive_vs_ungated_allocator")
    if float(aggregate["total_pnl_delta_sum"] or 0.0) <= 0.0:
        failed.append("gate_pnl_delta_not_positive_vs_ungated_allocator")
    if int(aggregate["windows_ev_improved"] or 0) < MIN_EV_IMPROVED_WINDOWS:
        failed.append("fewer_than_two_ev_improved_windows_vs_ungated")
    if int(aggregate["windows_ev_regressed"] or 0) > MAX_EV_REGRESSED_WINDOWS:
        failed.append("window_ev_regression_vs_ungated")
    if skipped_summary["total_trade_count"] < MIN_CHANGED_TRADES:
        failed.append("changed_sample_too_small")
    if len(changed_windows) < MIN_CHANGED_WINDOWS:
        failed.append("changed_window_coverage_too_small")
    if float(aggregate["max_drawdown_delta_max"] or 0.0) > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high_vs_ungated")
    if float(core_aggregate["expected_value_score_delta_sum"] or 0.0) <= 0.0:
        failed.append("gated_overlay_not_positive_ev_vs_core")
    if float(core_aggregate["total_pnl_delta_sum"] or 0.0) <= 0.0:
        failed.append("gated_overlay_not_positive_pnl_vs_core")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")

    concentration_cap_passed = (
        gated_single_share is not None
        and gated_single_share <= MAX_SINGLE_POSITIVE_SHARE
        and gated_hhi is not None
        and gated_hhi <= MAX_POSITIVE_HHI
    )
    concentration_not_worse = (
        gated_single_share is not None
        and ungated_single_share is not None
        and gated_single_share <= ungated_single_share + 1e-12
        and gated_hhi is not None
        and ungated_hhi is not None
        and gated_hhi <= ungated_hhi + 1e-12
    )
    if not concentration_cap_passed:
        failed.append("gated_target_concentration_failed")
    if not concentration_not_worse:
        failed.append("gated_target_concentration_worse_than_ungated")

    passed = not failed
    return {
        "passed": passed,
        "decision": (
            "accepted_paper_pending_forward_moomoo_short_volume_clean_flow_gate"
            if passed
            else "rejected_moomoo_short_volume_clean_flow_gate"
        ),
        "failed_reasons": failed,
        "aggregate_ev_delta_vs_ungated": aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta_vs_ungated": aggregate["total_pnl_delta_sum"],
        "aggregate_ev_delta_vs_core": core_aggregate["expected_value_score_delta_sum"],
        "aggregate_pnl_delta_vs_core": core_aggregate["total_pnl_delta_sum"],
        "windows_ev_improved_vs_ungated": aggregate["windows_ev_improved"],
        "windows_ev_regressed_vs_ungated": aggregate["windows_ev_regressed"],
        "windows_pnl_improved_vs_ungated": aggregate["windows_pnl_improved"],
        "windows_pnl_regressed_vs_ungated": aggregate["windows_pnl_regressed"],
        "changed_trade_count": skipped_summary["total_trade_count"],
        "changed_trade_count_min": MIN_CHANGED_TRADES,
        "changed_windows": changed_windows,
        "changed_window_count_min": MIN_CHANGED_WINDOWS,
        "max_drawdown_worse_vs_ungated": aggregate["max_drawdown_delta_max"],
        "max_drawdown_worse_guardrail": MAX_DRAWDOWN_WORSE,
        "minimum_core_survival_rate": round(min_survival, 6),
        "survival_guard_passed": min_survival >= 0.05,
        "target_concentration": {
            "passed": concentration_cap_passed and concentration_not_worse,
            "cap_passed": concentration_cap_passed,
            "not_worse_than_ungated": concentration_not_worse,
            "gated_max_single_positive_pnl_share": gated_single_share,
            "ungated_max_single_positive_pnl_share": ungated_single_share,
            "max_single_positive_pnl_share_guardrail": MAX_SINGLE_POSITIVE_SHARE,
            "gated_positive_pnl_hhi": gated_hhi,
            "ungated_positive_pnl_hhi": ungated_hhi,
            "positive_pnl_hhi_guardrail": MAX_POSITIVE_HHI,
        },
        "acceptance_rule": (
            "Binding Gate 4 compares gated allocator after-metrics against the "
            "current ungated accepted allocator. The gate must improve aggregate "
            "EV and PnL, improve EV in at least two canonical windows with zero "
            "EV regressions, affect at least nine trades over at least two "
            "windows, keep drawdown drift <=0.5pp, remain positive versus the "
            "core baseline, and not worsen target concentration."
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    short_volume_history, short_volume_audit = load_short_volume_ratio_history()
    percentile_index = build_short_volume_percentile_index(short_volume_history)

    universe = sorted(get_universe())
    sector_entries = framework._load_sector_entries()
    before_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    ungated_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    gated_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    delta_vs_ungated_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    delta_vs_core_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    ungated_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    gated_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    skipped_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    helper_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    clean_flow_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    window_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] moomoo short-volume clean-flow gate")
        before_result = framework.shadow._run_baseline(universe, cfg)
        core = framework.overlay_helper._metrics(before_result)
        snapshot = framework._load_window_snapshot(
            cfg=cfg,
            eligible_tickers=set(sector_entries),
        )
        window_sector_entries = {
            ticker: meta for ticker, meta in sector_entries.items() if ticker in snapshot
        }
        candidate_universe = candidate_universe_from_sector_entries(window_sector_entries)
        core_entries = framework.shadow._baseline_entries(before_result)
        ungated_trades, helper_audit = (
            build_accepted_helper_source_priority_allocator_historical_trades(
                ohlcv_by_ticker=snapshot,
                core_entries_by_date=core_entries,
                windows=OrderedDict([(label, cfg)]),
                candidate_universe=candidate_universe,
                sector_entries=window_sector_entries,
                calendar_dates=framework.shadow._trading_dates(snapshot),
            )
        )
        gated_trades, skipped_trades, clean_flow_audit = apply_clean_flow_gate(
            ungated_trades,
            percentile_index,
        )
        ungated_overlay = framework.sleeve._overlay_from_paper_trades(
            before_result,
            ungated_trades,
        )
        gated_overlay = framework.sleeve._overlay_from_paper_trades(
            before_result,
            gated_trades,
        )
        ungated = framework.overlay_helper._metrics_with_overlay(before_result, ungated_overlay)
        gated = framework.overlay_helper._metrics_with_overlay(before_result, gated_overlay)
        delta_vs_ungated = framework.overlay_helper._delta(gated, ungated)
        delta_vs_core = framework.overlay_helper._delta(gated, core)

        before_metrics[label] = core
        ungated_metrics[label] = ungated
        gated_metrics[label] = gated
        delta_vs_ungated_rows[label] = {
            "before": ungated,
            "after": gated,
            "delta": delta_vs_ungated,
            "target_trade_count": len(skipped_trades),
        }
        delta_vs_core_rows[label] = {
            "before": core,
            "after": gated,
            "delta": delta_vs_core,
            "target_trade_count": len(gated_trades),
        }
        ungated_trades_by_window[label] = ungated_trades
        gated_trades_by_window[label] = gated_trades
        skipped_trades_by_window[label] = skipped_trades
        helper_audit_by_window[label] = helper_audit
        clean_flow_audit_by_window[label] = clean_flow_audit
        window_rows[label] = {
            "core_baseline": core,
            "ungated_allocator": ungated,
            "gated_allocator": gated,
            "delta_vs_ungated": delta_vs_ungated,
            "delta_vs_core": delta_vs_core,
            "ungated_trade_count": len(ungated_trades),
            "gated_trade_count": len(gated_trades),
            "skipped_toxic_trade_count": len(skipped_trades),
            "clean_flow_audit": clean_flow_audit,
            "selected_source_counts": helper_audit["selected_source_counts_by_window"][label],
        }

    aggregate_vs_ungated = framework._aggregate_window_rows(delta_vs_ungated_rows)
    aggregate_vs_core = framework._aggregate_window_rows(delta_vs_core_rows)
    skipped_summary = framework.sleeve._target_trade_summary(skipped_trades_by_window)
    gated_summary = framework.sleeve._target_trade_summary(gated_trades_by_window)
    ungated_summary = framework.sleeve._target_trade_summary(ungated_trades_by_window)
    gate = gate4(
        aggregate=aggregate_vs_ungated,
        core_aggregate=aggregate_vs_core,
        skipped_summary=skipped_summary,
        gated_summary=gated_summary,
        ungated_summary=ungated_summary,
        before_metrics=before_metrics,
    )
    status = "accepted" if gate["passed"] else "rejected"
    decision = gate["decision"]
    production_impact = {
        "shared_policy_changed": True,
        "shared_policy_note": (
            "new reusable clean-flow quality gate helper only; existing accepted "
            "allocator default behavior and live orders are unchanged unless a "
            "future run explicitly enables this rejected/accepted policy"
        ),
        "backtester_adapter_changed": True,
        "run_adapter_changed": False,
        "replay_only": False,
        "default_off_paper_only": True,
        "daily_snapshot_exposed": False,
        "parity_test_added": True,
        "trade_enabled": False,
        "alters_orders": False,
        "production_orders_changed": False,
        "production_signal_path_changed": False,
        "production_watchlist_changed": False,
        "alters_signal_generation": False,
        "alters_candidate_ranking": False,
        "alters_sizing": False,
        "alters_exits": False,
        "uses_llm": False,
        "uses_free_non_ohlcv": True,
        "live_realism_evaluated": True,
        "live_ready": False,
        "execution_envelope": {
            "base_notional_usd": BASE_NOTIONAL_USD,
            "source_notional_scalars": "same as accepted allocator",
            "max_concurrent_positions": EXECUTION_ENVELOPE["max_concurrent_positions"],
            "capital_cap": EXECUTION_ENVELOPE["bucket_notional_usd"],
            "min_avg_dollar_volume_20d": EXECUTION_ENVELOPE["min_avg_dollar_volume_20d"],
            "slippage_model": EXECUTION_ENVELOPE["slippage_model"],
            "order_semantics": EXECUTION_ENVELOPE["order_semantics"],
            "kill_switch": EXECUTION_ENVELOPE["kill_switch_drawdown_pct"],
            "portfolio_displacement": EXECUTION_ENVELOPE["core_displacement"],
            "trade_enabled": False,
        },
    }
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_success": 1.0 if gate["passed"] else 0.0,
        "actual_gate4_passed": gate["passed"],
        "failure_modes_observed": gate["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate["passed"] else 0.0)) ** 2,
            6,
        ),
        "surprise_note": (
            "The observed-only universe edge translated into an allocator gate."
            if gate["passed"]
            else "The broad observed-only edge did not translate into a robust accepted-allocator gate."
        ),
    }
    post_run_reflection = {
        "why_result_happened": (
            "The clean-flow gate improved the accepted allocator enough to pass "
            "the incremental Gate 4."
            if gate["passed"]
            else (
                "The clean-flow gate did not produce robust incremental value "
                "over the already accepted allocator after next-open execution, "
                "costs, window checks, drawdown, and concentration controls."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not sweep short_volume_ratio quintile cutoffs, percentile "
            "lookback length, allocator source rank, daily slot count, notional, "
            "hold days, or cooldown on these frozen windows."
        ),
        "new_evidence_required": (
            "A retry needs materially more closed forward accepted-allocator "
            "rows tagged with entry-time short_volume_ratio percentile, true PIT "
            "borrow fee/utilization/loan-availability economics, or a materially "
            "different non-OHLCV flow field."
        ),
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "owner": OWNER,
        "status": status,
        "decision": decision,
        "accepted": gate["passed"],
        "accepted_alpha": gate["passed"],
        "hypothesis": HYPOTHESIS,
        "change_type": "candidate_pool_full_stack",
        "implementation_mode": "shared_paper_first_clean_flow_quality_gate",
        "mechanism_family": "production_visible_moomoo_daily_short_volume_quality_gate",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": [
            "shared short-volume percentile helper",
            "historical allocator replay filter",
            "daily snapshot quality gate semantics",
            "parity test",
            "execution envelope",
            "full-stack verdict",
        ],
        "nearby_prior_experiments": [
            "exp-20260625-018",
            "exp-20260622-010",
            "exp-20260623-008",
        ],
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "multiple_testing_risk_bucket": "moderate_allocator_near_neighbor_override",
        "prediction": PREDICTION,
        "calibration": calibration,
        "pre_run_questions": {
            "1_alpha_hypothesis": HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": (
                    "experiment.py new initially blocked as an allocator "
                    "near-neighbor; override recorded on the ticket using the "
                    "new moomoo daily short-volume data source and negative "
                    "quality-gate axis from exp-20260625-018."
                ),
                "exp-20260625-018": "positive observed-only informed-flow avoidance lead",
                "exp-20260622-010": "rejected wrong-sign high-short-volume absorption entry",
                "exp-20260623-008": "built broad moomoo daily short-volume archive",
            },
            "3_single_decision_hypothesis": CHANGED_VARIABLE,
            "4_acceptance_standard": gate["acceptance_rule"],
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "allocator_rule_version": ALLOCATOR_RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "clean_flow_rule_version": CLEAN_FLOW_RULE_VERSION,
            "short_volume_source": repo_rel(DEFAULT_SHORT_VOLUME_ROWS),
            "toxic_quintile_index": DEFAULT_TOXIC_QUINTILE_INDEX,
            "toxic_quintile_label": f"Q{DEFAULT_TOXIC_QUINTILE_INDEX + 1}",
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "source_priority": SOURCE_PRIORITY,
            "pit_rule": (
                "Historical rows use the latest formed activity percentile "
                "strictly before entry_date. Daily candidate semantics may use "
                "signal-date activity after the close for next-session paper "
                "entry. Missing percentiles are kept, not failed closed."
            ),
        },
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "accepted allocator overlay with and without clean-flow gate"
            ),
            "windows": framework.WINDOWS,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "candidate_ohlcv_source": repo_rel(framework.WAREHOUSE),
            "short_volume_source": repo_rel(DEFAULT_SHORT_VOLUME_ROWS),
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists(),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "core_baseline_metrics": before_metrics,
            "before_policy": "ungated accepted_helper_source_priority_allocator",
            "after_policy": "same allocator after toxic-Q5 short-volume clean-flow gate",
        },
        "gate2": {
            "passed": bool(short_volume_history) and bool(percentile_index) and gate2_open_positions["passed"],
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "entry_date",
                "target_price",
                "allocator candidate ticker/signal_date/entry_date",
                "moomoo activity_date",
                "moomoo short_volume_ratio",
                "PIT expanding per-ticker percentile",
            ],
            "short_volume_audit": short_volume_audit,
        },
        "gate3": {
            "new_core_filter_added": False,
            "strategy_filter_added": True,
            "signals_generated": sum(len(rows) for rows in ungated_trades_by_window.values()),
            "signals_survived": sum(len(rows) for rows in gated_trades_by_window.values()),
            "survival_rate": _round(
                sum(len(rows) for rows in gated_trades_by_window.values())
                / max(1, sum(len(rows) for rows in ungated_trades_by_window.values())),
                6,
            ),
            "minimum_core_survival_rate": gate["minimum_core_survival_rate"],
            "passed": gate["minimum_core_survival_rate"] >= 0.05,
        },
        "gate4": gate,
        "before_metrics": ungated_metrics,
        "after_metrics": gated_metrics,
        "core_baseline_metrics": before_metrics,
        "delta_metrics": {
            "by_window_vs_ungated": OrderedDict(
                (label, row["delta"]) for label, row in delta_vs_ungated_rows.items()
            ),
            "aggregate_vs_ungated": aggregate_vs_ungated,
            "by_window_vs_core": OrderedDict(
                (label, row["delta"]) for label, row in delta_vs_core_rows.items()
            ),
            "aggregate_vs_core": aggregate_vs_core,
        },
        "window_rows": window_rows,
        "target_trade_summary": {
            "skipped_toxic_rows": skipped_summary,
            "gated_rows": gated_summary,
            "ungated_rows": ungated_summary,
        },
        "clean_flow_audit_by_window": clean_flow_audit_by_window,
        "helper_audit_by_window": helper_audit_by_window,
        "sample_trades": {
            "skipped_toxic_rows": {
                label: rows[:10] for label, rows in skipped_trades_by_window.items()
            },
            "gated_rows": {label: rows[:10] for label, rows in gated_trades_by_window.items()},
        },
        "production_impact": production_impact,
        "post_run_reflection": post_run_reflection,
        "related_files": [
            RUNNER,
            "quant/short_volume_clean_flow_gate.py",
            "quant/test_short_volume_clean_flow_gate.py",
            "quant/accepted_helper_source_priority_allocator_paper_sleeve.py",
            repo_rel(DEFAULT_SHORT_VOLUME_ROWS),
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_short_volume_clean_flow_gate.py",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": "No JavaScript was used.",
    }


def build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    gate = payload["gate4"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "owner": OWNER,
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "numeric_gate4_passed": gate["passed"],
        "hypothesis": HYPOTHESIS,
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": "new_pit_data_source_and_negative_quality_gate",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "pre_run_questions": payload["pre_run_questions"],
        "backtest_protocol": payload["backtest_protocol"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": gate,
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "aggregate_expected_value_delta": gate["aggregate_ev_delta_vs_ungated"],
        "aggregate_strategy_total_pnl_delta": gate["aggregate_pnl_delta_vs_ungated"],
        "aggregate_ev_delta_vs_core": gate["aggregate_ev_delta_vs_core"],
        "aggregate_pnl_delta_vs_core": gate["aggregate_pnl_delta_vs_core"],
        "target_trade_summary": payload["target_trade_summary"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "changed_files": payload["related_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "anti_js": payload["anti_js"],
    }


def build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Ungated EV | Gated EV | dEV | Ungated PnL | Gated PnL | dPnL | skipped |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, row in payload["window_rows"].items():
        ungated = row["ungated_allocator"]
        gated = row["gated_allocator"]
        delta = row["delta_vs_ungated"]
        rows.append(
            "| {label} | {uev:.4f} | {gev:.4f} | {dev:+.4f} | ${upnl:,.2f} | ${gpnl:,.2f} | ${dpnl:+,.2f} | {skipped} |".format(
                label=label,
                uev=ungated["expected_value_score"],
                gev=gated["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                upnl=ungated["total_pnl"],
                gpnl=gated["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                skipped=row["skipped_toxic_trade_count"],
            )
        )
    gate = payload["gate4"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: moomoo short-volume clean-flow gate",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Production orders changed: `false`",
            f"- Runner: `{RUNNER_COMMAND}`",
            "",
            "## Hypothesis",
            "",
            HYPOTHESIS,
            "",
            "## Gate 4: gated allocator vs current ungated allocator",
            "",
            *rows,
            "",
            f"- Aggregate EV delta vs ungated: `{gate['aggregate_ev_delta_vs_ungated']:+.4f}`",
            f"- Aggregate PnL delta vs ungated: `${gate['aggregate_pnl_delta_vs_ungated']:+,.2f}`",
            f"- Changed trades: `{gate['changed_trade_count']}`",
            f"- Failed reasons: `{', '.join(gate['failed_reasons']) or 'none'}`",
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def update_ticket_and_registry(payload: dict[str, Any], log_record: dict[str, Any]) -> None:
    result = {
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": payload["accepted_alpha"],
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "aggregate_expected_value_delta": payload["gate4"]["aggregate_ev_delta_vs_ungated"],
        "aggregate_strategy_total_pnl_delta": payload["gate4"]["aggregate_pnl_delta_vs_ungated"],
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": payload["gate4"]["aggregate_ev_delta_vs_ungated"],
            "aggregate_strategy_total_pnl_delta": payload["gate4"]["aggregate_pnl_delta_vs_ungated"],
        },
    )
    ticket = {}
    if TICKET_JSON.exists():
        ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8-sig"))
    allowed = list(ticket.get("allowed_write_scope") or [])
    for path in ("quant/short_volume_clean_flow_gate.py", "quant/test_short_volume_clean_flow_gate.py"):
        if path not in allowed:
            allowed.append(path)
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "updated_at": payload["timestamp"],
            "owner": OWNER,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "new_evidence_type": "new_pit_data_source_and_negative_quality_gate",
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "allowed_write_scope": allowed,
            "decision": payload["decision"],
            "result": result,
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
        }
    )
    write_json(TICKET_JSON, ticket)


def write_manifest(payload: dict[str, Any]) -> None:
    paths = [
        REPO_ROOT / RUNNER,
        REPO_ROOT / "quant" / "short_volume_clean_flow_gate.py",
        REPO_ROOT / "quant" / "test_short_volume_clean_flow_gate.py",
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        TICKET_JSON,
        MANIFEST_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        DEFAULT_SHORT_VOLUME_ROWS,
    ]
    write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": payload["status"],
            "decision": payload["decision"],
            "created_at": payload["timestamp"],
            "runner": RUNNER,
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card": repo_rel(CARD_MD),
            "files": {repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)} for path in paths},
            "reproduction_commands": payload["reproduction_commands"],
            "anti_js": "No JavaScript was used.",
        },
    )


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = build_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)
    update_ticket_and_registry(payload, log_record)
    write_manifest(payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "aggregate_ev_delta_vs_ungated": payload["gate4"][
                    "aggregate_ev_delta_vs_ungated"
                ],
                "aggregate_pnl_delta_vs_ungated": payload["gate4"][
                    "aggregate_pnl_delta_vs_ungated"
                ],
                "changed_trade_count": payload["gate4"]["changed_trade_count"],
                "failed_reasons": payload["gate4"]["failed_reasons"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
