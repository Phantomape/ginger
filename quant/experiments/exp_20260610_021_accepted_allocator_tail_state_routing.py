"""exp-20260610-021: accepted allocator tail-state routing scout.

Alpha search for one fixed policy bundle: keep the accepted helper source set,
but route same-day allocator conflicts away from the observed weak
``extended_momentum`` tail-state bucket when another same-day source candidate
is available.

This runner is intentionally replay-only until the numeric evidence justifies a
shared helper update. It changes no live/default orders, core ranking, sizing,
exits, watchlists, LLM/news behavior, or enabled trading behavior. No
JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter, OrderedDict
from copy import deepcopy
from pathlib import Path
from typing import Any

import exp_20260610_014_revision_source_priority_allocator_extension as base
import exp_20260610_020_accepted_allocator_tail_state_attribution as tail_state
from accepted_helper_source_priority_allocator_paper_sleeve import (
    BASE_NOTIONAL_USD,
    RULE_VERSION as ACCEPTED_ALLOCATOR_RULE_VERSION,
    SAME_TICKER_COOLDOWN_DAYS,
    SOURCE_PRIORITY as ACCEPTED_SOURCE_PRIORITY,
    SOURCE_RULE_VERSION as ACCEPTED_ALLOCATOR_SOURCE_RULE_VERSION,
)
from data_layer import get_universe


framework = base.framework

EXPERIMENT_ID = "exp-20260610-021"
STEM = "accepted_allocator_tail_state_routing"
TRIAL_FAMILY = "accepted_helper_source_priority_allocator_tail_state_routing"
TRIAL_VARIANT_ID = "accepted_allocator_tail_state_aware_same_day_routing_v1"
CHANGED_VARIABLE = TRIAL_VARIANT_ID
OWNER = "codex-alpha-search"

RULE_VERSION = ACCEPTED_ALLOCATOR_RULE_VERSION
SOURCE_RULE_VERSION = ACCEPTED_ALLOCATOR_SOURCE_RULE_VERSION
SOURCE_PRIORITY: "OrderedDict[str, dict[str, Any]]" = deepcopy(ACCEPTED_SOURCE_PRIORITY)

REPO_ROOT = framework.REPO_ROOT
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiment_registry import persist_self_registered_result  # noqa: E402


OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260610_021_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

TAIL_STATE_POLICY = {
    "rule_version": CHANGED_VARIABLE,
    "demoted_bucket": "extended_momentum",
    "missing_return_path_penalty": True,
    "description": (
        "Within each signal date, non-extended tail-state candidates route "
        "ahead of extended_momentum rows; source priority remains the tiebreak "
        "inside each tail-state route group."
    ),
}

ACCEPTED_ALLOCATOR_COMPARATOR = {
    "experiment_id": "exp-20260610-014",
    "aggregate_ev_delta": 0.9720,
    "aggregate_pnl_delta": 15197.05,
    "window_deltas": {
        "late_strong": {"ev": 0.5079, "pnl": 4879.33},
        "mid_weak": {"ev": 0.3356, "pnl": 6103.41},
        "old_thin": {"ev": 0.1285, "pnl": 4214.31},
    },
}

PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "diagnostic_overfit",
        "source_family_confounding",
        "accepted_allocator_window_comparator_regression",
        "drawdown_drift",
    ],
    "confidence_reason": (
        "Observed-only exp-20260610-020 showed stable tail-state separation on "
        "accepted allocator rows, but using it for routing risks same-window "
        "overfit and source-family confounding; success requires improving "
        "every canonical window versus the current accepted allocator without "
        "changing live orders."
    ),
    "recorded_at": "2026-06-10T19:04:21+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_tail_state_routing_scout",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "uses_llm": False,
    "uses_free_ohlcv_only": True,
    "uses_free_non_ohlcv": False,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": {
        "trade_enabled": False,
        "target_notional_per_paper_trade": BASE_NOTIONAL_USD,
        "daily_entry_slots": 1,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "hold_days": 10,
        "max_active_positions": 8,
        "liquidity_source": "underlying accepted helper source liquidity gates",
        "order_semantics": "observe-only next-session-open paper entry; no broker order",
        "portfolio_displacement": (
            "same-day accepted allocator paper candidate routing only; no live "
            "portfolio displacement"
        ),
        "kill_switch": (
            "not live; any positive replay must be promoted through shared "
            "helper parity and forward replacement-value gates"
        ),
    },
    "parity_note": (
        "This experiment changes no production path. The tail-state route uses "
        "free OHLCV fields and warehouse fallback for replay coverage; a "
        "positive result is not accepted unless the same field is implemented "
        "inside the shared allocator helper and daily snapshot path."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate-pool/ranking alpha: accepted source-priority allocator rows "
        "may improve if same-day conflict routing demotes the observed weak "
        "extended_momentum bucket while keeping the source set fixed."
    ),
    "2_history_check": {
        "exp-20260610-014": (
            "Current accepted allocator with revision source; aggregate EV "
            "+0.9720 and PnL +$15,197.05. This is the binding comparator."
        ),
        "exp-20260610-020": (
            "Observed-only tail-state attribution: pullback_repair best and "
            "extended_momentum worst across accepted allocator selected rows; "
            "not a strategy result."
        ),
        "exp-20260610-019": (
            "Rejected adding Fundamental Growth RS to the allocator because it "
            "regressed late_strong versus the accepted allocator comparator."
        ),
        "exp-20260609-007": (
            "Rejected broad tail-state winner continuation; tail-state must "
            "beat accepted allocator rows, not generic momentum."
        ),
    },
    "3_single_decision_hypothesis": CHANGED_VARIABLE,
    "4_acceptance_standard": (
        "docs/backtesting.md canonical three windows. Numeric pass requires "
        "positive aggregate EV/PnL, no core-window regressions, sample/survival/"
        "drawdown/concentration guards, and beating exp-20260610-014 aggregate "
        "and per-window EV/PnL. Acceptance also requires shared helper parity; "
        "this replay-only runner cannot accept production alpha by itself."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260610_021_accepted_allocator_tail_state_routing.py"
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _round(value: Any, digits: int = 6) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return round(number, digits)


def _decision_id(row: dict[str, Any]) -> str:
    signal_date = str(row.get("signal_date") or row.get("date") or "")[:10]
    ticker = str(row.get("ticker") or "").upper()
    source_family = str(row.get("source_family") or "unknown")
    return f"ACCEPTED_ALLOCATOR_TAIL_STATE_ROUTE:{CHANGED_VARIABLE}:{signal_date}:{ticker}:{source_family}"


def _source_score(row: dict[str, Any]) -> float:
    for key in (
        "source_priority_score",
        "candidate_score",
        "paper_candidate_score",
        "peer_shock_score",
        "compression_score",
        "source_score",
        "score",
        "rank_score",
    ):
        if row.get(key) is not None:
            return _float(row.get(key))
    return 0.0


def _tail_route_penalty(row: dict[str, Any]) -> int:
    bucket = str(row.get("tail_state_bucket") or "missing_return_path")
    if bucket == "extended_momentum":
        return 1
    if bucket == "missing_return_path" and TAIL_STATE_POLICY["missing_return_path_penalty"]:
        return 1
    return 0


def _annotate_source_rows(
    *,
    label: str,
    source_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    features_by_window = tail_state._warehouse_tail_state_features({label: source_rows})
    annotated_by_window = tail_state._annotate_rows(
        {label: source_rows},
        features_by_window,
    )
    out: list[dict[str, Any]] = []
    for row in annotated_by_window.get(label, []):
        penalty = _tail_route_penalty(row)
        out.append(
            {
                **row,
                "tail_state_route_penalty": penalty,
                "tail_state_routing_rule_version": CHANGED_VARIABLE,
            }
        )
    return out


def _select_tail_state_routed_rows(
    *,
    source_rows: list[dict[str, Any]],
    trading_dates: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidates = [
        deepcopy(row)
        for row in source_rows
        if str(row.get("source_family") or "") in SOURCE_PRIORITY
    ]
    candidates.sort(
        key=lambda row: (
            str(row.get("signal_date") or row.get("date") or "")[:10],
            _tail_route_penalty(row),
            int(row.get("source_priority_rank") or 999),
            -_source_score(row),
            str(row.get("ticker") or ""),
        )
    )
    date_position = {date_value: idx for idx, date_value in enumerate(trading_dates)}
    used_date_counts: Counter[str] = Counter()
    next_allowed_pos_by_ticker: dict[str, int] = {}
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for row in candidates:
        signal_date = str(row.get("signal_date") or row.get("date") or "")[:10]
        ticker = str(row.get("ticker") or "").upper()
        pos = date_position.get(signal_date)
        if pos is None:
            rejected.append({**row, "filter_reason": "missing_signal_date_position"})
            continue
        if used_date_counts[signal_date] >= 1:
            rejected.append({**row, "filter_reason": "daily_top1_tail_state_route_limit"})
            continue
        if pos < next_allowed_pos_by_ticker.get(ticker, -1):
            rejected.append({**row, "filter_reason": "same_ticker_cooldown"})
            continue
        out = {
            **deepcopy(row),
            "source": "ACCEPTED_HELPER_SOURCE_PRIORITY_TOP1_PAPER",
            "sleeve": "ACCEPTED_HELPER_SOURCE_PRIORITY_TOP1_PAPER",
            "rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "tail_state_routing_rule_version": CHANGED_VARIABLE,
            "decision_id": _decision_id(row),
            "candidate_score": _round(1000.0 / max(1, int(row.get("source_priority_rank") or 999)) + _source_score(row)),
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "notional_usd": BASE_NOTIONAL_USD,
            "paper_status": "closed",
            "trade_enabled": False,
            "alters_orders": False,
        }
        selected.append(out)
        used_date_counts[signal_date] += 1
        next_allowed_pos_by_ticker[ticker] = pos + SAME_TICKER_COOLDOWN_DAYS
    audit = {
        "source_candidate_count": len(candidates),
        "selected_priority_trade_count": len(selected),
        "filtered_priority_candidate_count": len(rejected),
        "source_candidate_counts": dict(
            Counter(str(row.get("source_family") or "unknown") for row in candidates)
        ),
        "selected_source_counts": dict(
            Counter(str(row.get("source_family") or "unknown") for row in selected)
        ),
        "candidate_tail_state_counts": dict(
            Counter(str(row.get("tail_state_bucket") or "missing_return_path") for row in candidates)
        ),
        "selected_tail_state_counts": dict(
            Counter(str(row.get("tail_state_bucket") or "missing_return_path") for row in selected)
        ),
        "daily_entry_slots": 1,
        "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
        "tail_state_policy": TAIL_STATE_POLICY,
    }
    return selected, rejected, audit


def _candidate_universe_from_sector_entries(
    sector_entries: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "status": "window_sector_known_universe",
        "tickers": sorted(sector_entries),
        "records": sector_entries,
    }


def _selection_delta(
    baseline_rows: list[dict[str, Any]],
    routed_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    baseline_by_date = {
        str(row.get("signal_date") or row.get("date") or "")[:10]: row
        for row in baseline_rows
    }
    routed_by_date = {
        str(row.get("signal_date") or row.get("date") or "")[:10]: row
        for row in routed_rows
    }
    changed: list[dict[str, Any]] = []
    for signal_date in sorted(set(baseline_by_date) | set(routed_by_date)):
        before = baseline_by_date.get(signal_date)
        after = routed_by_date.get(signal_date)
        if not before or not after:
            changed.append(
                {
                    "signal_date": signal_date,
                    "baseline_ticker": str((before or {}).get("ticker") or ""),
                    "routed_ticker": str((after or {}).get("ticker") or ""),
                    "reason": "date_presence_changed",
                }
            )
            continue
        before_key = (
            str(before.get("ticker") or ""),
            str(before.get("source_family") or ""),
        )
        after_key = (
            str(after.get("ticker") or ""),
            str(after.get("source_family") or ""),
        )
        if before_key != after_key:
            changed.append(
                {
                    "signal_date": signal_date,
                    "baseline_ticker": before_key[0],
                    "baseline_source": before_key[1],
                    "baseline_tail_state": before.get("tail_state_bucket"),
                    "routed_ticker": after_key[0],
                    "routed_source": after_key[1],
                    "routed_tail_state": after.get("tail_state_bucket"),
                }
            )
    return {
        "changed_selection_count": len(changed),
        "changed_selection_sample": changed[:50],
    }


def _gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    before_metrics: dict[str, dict[str, Any]],
    window_rows: OrderedDict[str, dict[str, Any]],
    shared_helper_promoted: bool,
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
    if aggregate_ev <= ACCEPTED_ALLOCATOR_COMPARATOR["aggregate_ev_delta"]:
        failed.append("accepted_allocator_ev_comparator_not_beaten")
    if aggregate_pnl <= ACCEPTED_ALLOCATOR_COMPARATOR["aggregate_pnl_delta"]:
        failed.append("accepted_allocator_pnl_comparator_not_beaten")

    comparator_regressions: list[str] = []
    for label, row in window_rows.items():
        comparator = ACCEPTED_ALLOCATOR_COMPARATOR["window_deltas"][label]
        delta = row["delta"]
        if float(delta.get("expected_value_score") or 0.0) < comparator["ev"]:
            comparator_regressions.append(f"{label}_ev")
        if float(delta.get("total_pnl") or 0.0) < comparator["pnl"]:
            comparator_regressions.append(f"{label}_pnl")
    if comparator_regressions:
        failed.append("accepted_allocator_window_comparator_regression")

    numeric_passed = not failed
    acceptance_blockers: list[str] = []
    if numeric_passed and not shared_helper_promoted:
        acceptance_blockers.append("shared_helper_not_promoted")
    passed = numeric_passed and not acceptance_blockers
    if acceptance_blockers:
        failed.extend(acceptance_blockers)
    if passed:
        decision = "accepted_shared_default_off_tail_state_allocator_routing"
    elif numeric_passed:
        decision = "positive_replay_lead_not_promoted_tail_state_allocator_routing"
    else:
        decision = "rejected_tail_state_allocator_routing"
    return {
        "passed": passed,
        "numeric_passed": numeric_passed,
        "decision": decision,
        "failed_reasons": failed,
        "acceptance_blockers": acceptance_blockers,
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


def _build_payload() -> dict[str, Any]:
    timestamp = framework._utc_now()
    gate2_open_positions = framework.sleeve._audit_open_positions()
    if not gate2_open_positions["passed"]:
        raise RuntimeError(f"Gate 2 open-position field check failed: {gate2_open_positions}")

    universe = sorted(get_universe())
    sector_entries = framework._load_sector_entries()
    before_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    after_metrics: OrderedDict[str, dict[str, Any]] = OrderedDict()
    window_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    target_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    baseline_trades_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    filtered_candidates_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    source_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    priority_audit_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    selection_delta_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()
    warehouse_coverage_by_window: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for label, cfg in framework.WINDOWS.items():
        print(f"[{label}] accepted allocator tail-state routing")
        before_result = framework.shadow._run_baseline(universe, cfg)
        before = framework.overlay_helper._metrics(before_result)
        snapshot = framework._load_window_snapshot(
            cfg=cfg,
            eligible_tickers=set(sector_entries),
        )
        dates = [
            day
            for day in framework.shadow._trading_dates(snapshot)
            if str(cfg["start"]) <= day <= str(cfg["end"])
        ]
        window_sector_entries = {
            ticker: meta for ticker, meta in sector_entries.items() if ticker in snapshot
        }
        candidate_universe = _candidate_universe_from_sector_entries(window_sector_entries)
        core_entries = framework.shadow._baseline_entries(before_result)
        source_trades, source_audit = base._build_extended_source_trades(
            snapshot=snapshot,
            dates=dates,
            label=label,
            cfg=cfg,
            core_entries_by_date=core_entries,
            sector_entries=window_sector_entries,
            candidate_universe=candidate_universe,
        )
        annotated_source_trades = _annotate_source_rows(
            label=label,
            source_rows=source_trades,
        )
        baseline_selected, _baseline_filtered, baseline_audit = base._select_priority_trades(
            source_trades=annotated_source_trades,
            trading_dates=dates,
        )
        selected, filtered, priority_audit = _select_tail_state_routed_rows(
            source_rows=annotated_source_trades,
            trading_dates=dates,
        )
        overlay = framework.sleeve._overlay_from_paper_trades(before_result, selected)
        after = framework.overlay_helper._metrics_with_overlay(before_result, overlay)
        delta = framework.overlay_helper._delta(after, before)
        selection_delta = _selection_delta(baseline_selected, selected)

        before_metrics[label] = before
        after_metrics[label] = after
        target_trades_by_window[label] = selected
        baseline_trades_by_window[label] = baseline_selected
        filtered_candidates_by_window[label] = filtered[:100]
        source_audit_by_window[label] = source_audit
        priority_audit_by_window[label] = {
            **priority_audit,
            "baseline_selected_source_counts": baseline_audit["selected_source_counts"],
            "selection_delta": selection_delta,
        }
        selection_delta_by_window[label] = selection_delta
        warehouse_coverage_by_window[label] = {
            "loaded_ticker_count": len(snapshot),
            "sector_known_candidate_ticker_count": len(window_sector_entries),
            "source": _repo_rel(framework.WAREHOUSE),
        }
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": delta,
            "target_trade_count": len(selected),
            "baseline_target_trade_count": len(baseline_selected),
            "all_source_trade_count": len(source_trades),
            "source_trade_counts": source_audit["source_trade_counts"],
            "raw_source_candidate_counts": source_audit["raw_candidate_counts"],
            "selected_source_counts": priority_audit["selected_source_counts"],
            "selected_tail_state_counts": priority_audit["selected_tail_state_counts"],
            "candidate_tail_state_counts": priority_audit["candidate_tail_state_counts"],
            "filtered_priority_candidate_count": len(filtered),
            "changed_selection_count": selection_delta["changed_selection_count"],
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
        shared_helper_promoted=False,
    )
    status = "accepted" if gate4["passed"] else "rejected"
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": gate4["numeric_passed"],
        "actual_success": 1 if gate4["numeric_passed"] else 0,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if gate4["numeric_passed"] else 0.0)) ** 2,
            6,
        ),
    }
    if gate4["passed"]:
        interpretation = (
            "Tail-state routing beat the accepted allocator comparator and was "
            "retained through a shared default-off helper."
        )
        reflection = (
            "The fixed route demoted crowded extended_momentum rows while "
            "preserving accepted source evidence and all three-window risk "
            "guards."
        )
    elif gate4["numeric_passed"]:
        interpretation = (
            "Tail-state routing numerically passed but remains a replay lead "
            "because the shared daily allocator helper was not promoted."
        )
        reflection = (
            "The route may separate crowded extension from cleaner source rows, "
            "but accepting it now would create a backtest/production mismatch. "
            "It needs a shared helper field, parity tests, and forward rows."
        )
    else:
        interpretation = (
            "Tail-state routing failed to beat the accepted allocator comparator."
        )
        reflection = (
            "The observed-only tail-state separation did not translate into a "
            "robust same-day routing policy. The likely failure is diagnostic "
            "overfit and source-family confounding: lower-priority non-extended "
            "rows did not consistently beat the accepted highest-priority row "
            "after costs, cooldown, and next-open execution."
        )

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": gate4["decision"],
        "accepted": gate4["passed"],
        "accepted_alpha": gate4["passed"],
        "production_accepted": gate4["passed"],
        "hypothesis": (
            "Accepted helper source-priority allocator rows may improve "
            "replacement value if same-day routing prefers non-extended "
            "tail-state candidates over extended-momentum candidates, reducing "
            "crowded continuation risk without adding a new source family."
        ),
        "change_type": "candidate_pool_full_stack",
        "implementation_mode": "private_replay_scout",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "diagnostic_to_routing_policy_test",
        "nearby_prior_experiments": [
            "exp-20260610-020",
            "exp-20260610-014",
            "exp-20260610-019",
            "exp-20260609-007",
        ],
        "prior_trial_count": 1,
        "prediction": PREDICTION,
        "calibration": calibration,
        "backtest_protocol": {
            "source": (
                "docs/backtesting.md canonical three-window core replay plus "
                "replay-only tail-state-aware routing over the accepted helper "
                "source-priority allocator source rows"
            ),
            "windows": framework.WINDOWS,
            "candidate_ohlcv_source": _repo_rel(framework.WAREHOUSE),
            "replay_llm": False,
            "replay_news": False,
            "REGIME_AWARE_EXIT": True,
            "execution_model": (
                "Existing accepted allocator source rows are rebuilt through "
                "the accepted helper. Rows are annotated with the exp020 "
                "tail-state bucket using signal-date OHLCV only; within each "
                "date non-extended rows sort before extended_momentum rows, "
                "then original source priority applies. Entry remains next open "
                "and exit remains 10 trading days at fixed $4,000 paper notional."
            ),
        },
        "parameters": {
            "rule_version": RULE_VERSION,
            "source_rule_version": SOURCE_RULE_VERSION,
            "source_priority": SOURCE_PRIORITY,
            "tail_state_policy": TAIL_STATE_POLICY,
            "paper_notional_usd": BASE_NOTIONAL_USD,
            "max_paper_trades_per_day": 1,
            "same_ticker_cooldown_days": SAME_TICKER_COOLDOWN_DAYS,
            "accepted_allocator_comparator": ACCEPTED_ALLOCATOR_COMPARATOR,
        },
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "gate1": {
            "baseline_metrics": before_metrics,
            "baseline_artifact": (
                "docs/backtesting.md current canonical baseline and same-run "
                "before_metrics inside this artifact"
            ),
            "passed": True,
        },
        "gate2": {
            "open_positions": gate2_open_positions,
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "warehouse ohlcv Date/Open/High/Low/Close/Volume",
                "accepted helper source rows with signal_date/ticker/source_family",
                "tail-state ret5/ret20/ret60/realized-vol fields from signal-date history",
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
                "No core filter or live candidate ranking changed. This is a "
                "default-off paper routing replay over accepted helper rows."
            ),
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
        "baseline_trades_by_window": baseline_trades_by_window,
        "target_trade_summary": target_summary,
        "filtered_priority_candidates_by_window": filtered_candidates_by_window,
        "source_audit_by_window": source_audit_by_window,
        "priority_audit_by_window": priority_audit_by_window,
        "selection_delta_by_window": selection_delta_by_window,
        "warehouse_coverage_by_window": warehouse_coverage_by_window,
        "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
        "total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "llm_metrics": {"used_llm": False, "llm_change_scope": "none"},
        "production_impact": PRODUCTION_IMPACT,
        "accepted_comparators": {
            "accepted_allocator": ACCEPTED_ALLOCATOR_COMPARATOR,
            "observed_tail_state_attribution": {
                "experiment_id": "exp-20260610-020",
                "best_bucket": "pullback_repair",
                "worst_bucket": "extended_momentum",
                "avg_pnl_edge": 120.36,
            },
            "included_source_priority": SOURCE_PRIORITY,
        },
        "interpretation": interpretation,
        "rejection_reason": None if gate4["passed"] else "; ".join(gate4["failed_reasons"]),
        "post_run_reflection": {
            "why_result_happened": reflection,
            "forbidden_near_neighbor_retry": (
                "Do not retry by retuning tail-state bucket thresholds, source "
                "rank, top-N, notional, hold days, or cooldown on the same "
                "frozen windows."
            ),
            "new_evidence_required": (
                "A retry needs closed forward allocator replacement rows, a "
                "shared daily tail-state field collected before routing, or a "
                "materially different PIT displacement field."
            ),
        },
        "anti_js": "No JavaScript was used.",
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


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Accepted dEV | Before PnL | After PnL | dPnL | Accepted dPnL | Trades | Changed route | Tail states |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        row = payload["window_rows"][label]
        comparator = ACCEPTED_ALLOCATOR_COMPARATOR["window_deltas"][label]
        tail_counts = ", ".join(
            f"{name}:{count}"
            for name, count in sorted(row["selected_tail_state_counts"].items())
        )
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | {cev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | ${cpnl:+,.2f} | {trades} | {changed} | {tail_counts} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                cev=comparator["ev"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                cpnl=comparator["pnl"],
                trades=row["target_trade_count"],
                changed=row["changed_selection_count"],
                tail_counts=tail_counts or "none",
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Accepted Allocator Tail-State Routing",
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
            "## Production Impact",
            "",
            PRODUCTION_IMPACT["parity_note"],
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
        "numeric_gate4_passed": payload["gate4"]["numeric_passed"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": (
            "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
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
                "source_trade_count": payload["window_rows"][label]["all_source_trade_count"],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
                "changed_selection_count": payload["window_rows"][label][
                    "changed_selection_count"
                ],
                "selected_source_counts": payload["window_rows"][label][
                    "selected_source_counts"
                ],
                "selected_tail_state_counts": payload["window_rows"][label][
                    "selected_tail_state_counts"
                ],
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": PRE_RUN_QUESTIONS,
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
        "accepted_alpha": payload["gate4"]["passed"],
        "production_accepted": payload["gate4"]["passed"],
        "numeric_gate4_passed": payload["gate4"]["numeric_passed"],
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
        "owner": OWNER,
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
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

    ticket = {}
    if TICKET_JSON.exists():
        ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "updated_at": payload["timestamp"],
            "decision": payload["decision"],
            "result": result,
            "artifact": _repo_rel(OUT_JSON),
            "log": _repo_rel(LOG_JSON),
            "card_file": _repo_rel(CARD_MD),
            "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        }
    )
    scope = set(ticket.get("allowed_write_scope") or [])
    scope.update(payload["related_files"])
    ticket["allowed_write_scope"] = sorted(scope)
    framework._write_json(TICKET_JSON, ticket)


def _write_manifest(payload: dict[str, Any]) -> None:
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": "No JavaScript was used.",
        "allowed_write_scope": payload["related_files"],
        "file_hashes": {
            _repo_rel(Path(__file__)): framework._sha256(Path(__file__)),
            _repo_rel(OUT_JSON): framework._sha256(OUT_JSON),
            _repo_rel(LOG_JSON): framework._sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): framework._sha256(TICKET_JSON),
            _repo_rel(CARD_MD): framework._sha256(CARD_MD),
        },
    }
    framework._write_json(MANIFEST_JSON, manifest)


def main() -> None:
    payload = _build_payload()
    log_record = _build_log_record(payload)
    framework._write_json(OUT_JSON, payload)
    framework._write_json(LOG_JSON, log_record)
    framework._write_text(CARD_MD, _build_card(payload))
    framework._upsert_jsonl(EXPERIMENT_LOG, log_record)
    _update_ticket_and_registry(payload, log_record)
    _write_manifest(payload)
    print(
        "completed {experiment_id}: {decision} | dEV={ev:+.4f} | dPnL=${pnl:+,.2f}".format(
            experiment_id=EXPERIMENT_ID,
            decision=payload["decision"],
            ev=payload["delta_metrics"]["aggregate"]["expected_value_score_delta_sum"],
            pnl=payload["delta_metrics"]["aggregate"]["total_pnl_delta_sum"],
        )
    )


if __name__ == "__main__":
    main()
