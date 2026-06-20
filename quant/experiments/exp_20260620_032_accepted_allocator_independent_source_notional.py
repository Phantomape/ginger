"""exp-20260620-032: independent-source notional scalar for accepted allocator.

Full-stack alpha search. Tests one attributable allocation hypothesis: keep the
accepted helper source-priority allocator's selected rows unchanged, but apply a
small default-off paper notional scalar to selected rows from low-overlap
positive sources identified by exp-20260620-029 and corrected by exp-20260620-031.
No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, OrderedDict
from copy import deepcopy
from pathlib import Path
from typing import Any

import exp_20260611_005_lagged_consensus_shared_allocator_source as base

framework = base.framework

REPO_ROOT = framework.REPO_ROOT
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for entry in (str(REPO_ROOT), str(QUANT_ROOT), str(SCRIPTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import accepted_helper_source_priority_allocator_paper_sleeve as allocator_helper  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260620-032"
OWNER = "alpha-search-automation"
STEM = "accepted_allocator_independent_source_notional"
TRIAL_FAMILY = "accepted_default_off_helper_source_priority_allocation"
TRIAL_VARIANT_ID = "accepted_allocator_independent_source_notional_scalar_v1"
CHANGED_VARIABLE = TRIAL_VARIANT_ID

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260620_032_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
PARITY_MATRIX_MD = REPO_ROOT / "docs" / "production_backtest_parity_matrix.md"
PLAYBOOK_MD = REPO_ROOT / "docs" / "alpha-optimization-playbook.md"

SCALARS = OrderedDict(
    [
        ("industry_laggard_repair", 1.25),
        ("revision_surprise_low_extension", 1.25),
    ]
)

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

PREDICTION = {
    "success_probability": 0.24,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "independence_map_in_sample",
        "too_few_scaled_selected_rows",
        "accepted_allocator_comparator_not_beaten",
        "drawdown_drift",
    ],
    "confidence_reason": (
        "Mechanism is capital allocation toward selected sources with low overlap "
        "and positive standalone sleeve returns from exp-20260620-029, corrected "
        "for zero-fire harness issues by exp-20260620-031. It keeps source "
        "selection fixed and only tests a small default-off paper notional scalar, "
        "but allocator scalar/routing families are heavily explored and the "
        "evidence is in-sample."
    ),
    "recorded_at": "2026-06-20T23:05:33+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "shared_default_off_paper_helper",
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
    "uses_llm": False,
    "uses_free_ohlcv_only": False,
    "uses_free_non_ohlcv": True,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": allocator_helper.EXECUTION_ENVELOPE,
    "parity_note": (
        "Historical replay and daily default-off snapshots use the same shared "
        "accepted-helper allocator helper and source_notional_scalars. The change "
        "does not alter source priority, daily top-1 selection, cooldown, exits, "
        "core trading, LLM/news, watchlists, or live/default orders."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "allocation: selected accepted-helper allocator rows from independent, "
        "positive source families should carry slightly more default-off paper "
        "notional because exp-20260620-029 showed low return/ticker-date overlap "
        "for industry_laggard_repair and revision_surprise_low_extension, and "
        "exp-20260620-031 corrected the zero-fire harness caveat."
    ),
    "2_history_check": {
        "novelty_gate": (
            "The novelty gate warned on nearby revision/allocator history. The "
            "override is the exp-20260620-029 sleeve independence map plus "
            "exp-20260620-031 zero-fire correction, not a rank/top-N/hold/"
            "cooldown or raw source-threshold retry."
        ),
        "exp-20260620-029": (
            "Built accepted-sleeve return independence map. industry_laggard_repair "
            "had mean abs corr 0.021 and positive total PnL; revision_surprise had "
            "mean abs corr 0.039 and positive total PnL."
        ),
        "exp-20260620-031": (
            "Corrected zero-fire harness artifacts and showed core-flow sleeves "
            "need proper core entries/VIXY/companyfacts wiring for attribution."
        ),
        "exp-20260611-005": (
            "Current accepted shared allocator with lagged consensus; this run "
            "keeps selection fixed and compares scaled after versus unscaled "
            "current allocator."
        ),
        "exp-20260613-033": (
            "Allocator crowding/correlation context warned against naive source "
            "stacking; this run only changes notional on low-overlap selected rows."
        ),
    },
    "3_single_causal_variable": (
        "One fixed policy bundle: source_notional_scalar=1.25 for selected "
        "industry_laggard_repair and revision_surprise_low_extension allocator "
        "rows; all source selection, priority rank, daily top-1, hold, costs, "
        "cooldown, core behavior, LLM/news, and live/default orders remain fixed."
    ),
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Before is the current "
        "unscaled accepted allocator; after is the shared helper with the fixed "
        "source scalars. Accept only if aggregate EV/PnL improve, no window EV/"
        "PnL regression, affected sample spans all three windows with >=20 rows, "
        "survival/concentration/drawdown guards pass, and after still beats the "
        "accepted allocator comparator."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260620_032_accepted_allocator_independent_source_notional.py"
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _set_scalars(scalars: dict[str, float]) -> None:
    allocator_helper.SOURCE_NOTIONAL_SCALARS.clear()
    allocator_helper.SOURCE_NOTIONAL_SCALARS.update(scalars)
    allocator_helper.DEFAULT_CONFIG["source_notional_scalars"] = dict(scalars)


def _run_allocator_pass(name: str, scalars: dict[str, float]) -> dict[str, Any]:
    print(f"[{name}] allocator replay with source_notional_scalars={dict(scalars)}")
    _set_scalars(scalars)
    return base.build_payload()


def _delta(after: dict[str, Any], before: dict[str, Any]) -> dict[str, Any]:
    return framework.overlay_helper._delta(after, before)


def _aggregate_incremental(window_rows: OrderedDict[str, dict[str, Any]]) -> dict[str, Any]:
    before_ev = sum(float(row["before"]["expected_value_score"]) for row in window_rows.values())
    after_ev = sum(float(row["after"]["expected_value_score"]) for row in window_rows.values())
    before_pnl = sum(float(row["before"]["total_pnl"]) for row in window_rows.values())
    after_pnl = sum(float(row["after"]["total_pnl"]) for row in window_rows.values())
    deltas = [row["delta"] for row in window_rows.values()]
    ev_delta = after_ev - before_ev
    pnl_delta = after_pnl - before_pnl
    return {
        "baseline_expected_value_score_sum": round(before_ev, 4),
        "after_expected_value_score_sum": round(after_ev, 4),
        "expected_value_score_delta_sum": round(ev_delta, 4),
        "expected_value_score_delta_pct": round(ev_delta / before_ev, 6) if before_ev else None,
        "baseline_total_pnl_sum": round(before_pnl, 2),
        "after_total_pnl_sum": round(after_pnl, 2),
        "total_pnl_delta_sum": round(pnl_delta, 2),
        "total_pnl_delta_pct": round(pnl_delta / before_pnl, 6) if before_pnl else None,
        "windows_ev_improved": sum(1 for row in deltas if float(row["expected_value_score"]) > 0),
        "windows_ev_regressed": sum(1 for row in deltas if float(row["expected_value_score"]) < 0),
        "windows_pnl_improved": sum(1 for row in deltas if float(row["total_pnl"]) > 0),
        "windows_pnl_regressed": sum(1 for row in deltas if float(row["total_pnl"]) < 0),
        "max_drawdown_delta_max": max(float(row["max_drawdown_pct"]) for row in deltas),
    }


def _affected_trade_summary(
    trades_by_window: OrderedDict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    affected_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    positive_by_ticker: Counter[str] = Counter()
    total_incremental = 0.0
    for label, trades in trades_by_window.items():
        rows: list[dict[str, Any]] = []
        for row in trades:
            scalar = float(row.get("source_notional_scalar") or 1.0)
            if scalar <= 1.0:
                continue
            pnl = float(row.get("pnl") or 0.0)
            incremental = round(pnl - pnl / scalar, 2)
            out = {**row, "incremental_pnl": incremental}
            rows.append(out)
            total_incremental += incremental
            if incremental > 0:
                positive_by_ticker[str(row.get("ticker") or "UNKNOWN")] += incremental
        affected_by_window[label] = rows
    positive_total = sum(float(v) for v in positive_by_ticker.values())
    hhi = None
    max_share = None
    if positive_total > 0:
        shares = [float(v) / positive_total for v in positive_by_ticker.values()]
        hhi = round(sum(share * share for share in shares), 6)
        max_share = round(max(shares), 6)
    return {
        "trades_by_window": affected_by_window,
        "total_trade_count": sum(len(rows) for rows in affected_by_window.values()),
        "windows_with_target_trades": [
            label for label, rows in affected_by_window.items() if rows
        ],
        "incremental_pnl_sum": round(total_incremental, 2),
        "positive_by_ticker_pnl": dict(positive_by_ticker),
        "max_single_positive_pnl_share": max_share,
        "positive_pnl_hhi": hhi,
        "source_counts": dict(
            Counter(
                str(row.get("source_family") or "unknown")
                for rows in affected_by_window.values()
                for row in rows
            )
        ),
    }


def _top5_positive_share(target_summary: dict[str, Any]) -> float | None:
    positive = target_summary.get("positive_by_ticker_pnl") or {}
    total = sum(float(value) for value in positive.values())
    if total <= 0:
        return None
    top5 = sum(sorted((float(value) for value in positive.values()), reverse=True)[:5])
    return round(top5 / total, 6)


def _binding_gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    current_payload: dict[str, Any],
    scaled_payload: dict[str, Any],
) -> dict[str, Any]:
    before_metrics = current_payload["before_metrics"]
    min_survival = min(float(row.get("survival_rate") or 0.0) for row in before_metrics.values())
    concentration_passed = (
        target_summary["max_single_positive_pnl_share"] is not None
        and target_summary["max_single_positive_pnl_share"] <= MAX_SINGLE_POSITIVE_SHARE
        and target_summary["positive_pnl_hhi"] is not None
        and target_summary["positive_pnl_hhi"] <= MAX_POSITIVE_HHI
    )
    failed: list[str] = []
    if float(aggregate["expected_value_score_delta_sum"]) <= 0:
        failed.append("incremental_ev_not_positive")
    if float(aggregate["total_pnl_delta_sum"]) <= 0:
        failed.append("incremental_pnl_not_positive")
    if int(aggregate["windows_ev_regressed"]) > 0:
        failed.append("window_ev_regression_vs_current_allocator")
    if int(aggregate["windows_pnl_regressed"]) > 0:
        failed.append("window_pnl_regression_vs_current_allocator")
    if int(target_summary["total_trade_count"]) < MIN_TARGET_TRADES:
        failed.append("target_sample_too_small")
    if len(target_summary["windows_with_target_trades"]) < MIN_TARGET_WINDOWS:
        failed.append("target_window_coverage_too_small")
    if float(aggregate["max_drawdown_delta_max"]) > MAX_DRAWDOWN_WORSE:
        failed.append("drawdown_drift_too_high")
    if min_survival < 0.05:
        failed.append("core_survival_rate_below_5pct")
    if not concentration_passed:
        failed.append("target_concentration_failed")
    if not scaled_payload["gate4"]["passed"]:
        failed.append("scaled_allocator_no_longer_beats_accepted_comparators")

    return {
        "passed": not failed,
        "decision": (
            "accepted_allocator_independent_source_notional_scalar"
            if not failed
            else "rejected_allocator_independent_source_notional_scalar"
        ),
        "failed_reasons": failed,
        "aggregate_ev_delta_vs_current_allocator": aggregate[
            "expected_value_score_delta_sum"
        ],
        "aggregate_pnl_delta_vs_current_allocator": aggregate["total_pnl_delta_sum"],
        "current_allocator_core_delta": current_payload["delta_metrics"]["aggregate"],
        "scaled_allocator_core_delta": scaled_payload["delta_metrics"]["aggregate"],
        "target_trade_count": target_summary["total_trade_count"],
        "target_trade_count_min": MIN_TARGET_TRADES,
        "target_windows": target_summary["windows_with_target_trades"],
        "target_window_count_min": MIN_TARGET_WINDOWS,
        "max_drawdown_worse_vs_current": aggregate["max_drawdown_delta_max"],
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
            "top5_positive_share": _top5_positive_share(target_summary),
        },
    }


def build_payload() -> dict[str, Any]:
    original_scalars = dict(allocator_helper.SOURCE_NOTIONAL_SCALARS)
    try:
        current_payload = _run_allocator_pass("before_unscaled_current", {})
        scaled_payload = _run_allocator_pass("after_scaled_shared", dict(SCALARS))
    finally:
        _set_scalars(original_scalars)

    window_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label in framework.WINDOWS:
        before = current_payload["after_metrics"][label]
        after = scaled_payload["after_metrics"][label]
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": _delta(after, before),
            "current_allocator_core_delta": current_payload["delta_metrics"]["by_window"][
                label
            ],
            "scaled_allocator_core_delta": scaled_payload["delta_metrics"]["by_window"][
                label
            ],
            "selected_source_counts": scaled_payload["window_rows"][label][
                "selected_source_counts"
            ],
        }

    aggregate = _aggregate_incremental(window_rows)
    target_summary = _affected_trade_summary(scaled_payload["target_trades_by_window"])
    gate4 = _binding_gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        current_payload=current_payload,
        scaled_payload=scaled_payload,
    )
    accepted = gate4["passed"]
    timestamp = framework._utc_now()
    status = "accepted_paper_pending_forward" if accepted else "rejected"
    decision = gate4["decision"]
    calibration = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": accepted,
        "actual_success": 1 if accepted else 0,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if accepted else 0.0)) ** 2,
            6,
        ),
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "alpha_search",
        "status": status,
        "decision": decision,
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "candidate_pool_full_stack",
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "accepted_sleeve_return_independence_map",
        "nearby_prior_experiments": [
            "exp-20260620-029",
            "exp-20260620-031",
            "exp-20260611-005",
            "exp-20260613-033",
        ],
        "prior_trial_count": 4,
        "prediction": PREDICTION,
        "calibration": calibration,
        "pre_run_questions": PRE_RUN_QUESTIONS,
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
                "Before: current shared allocator with source_notional_scalars={}. "
                "After: same shared allocator source selection with fixed 1.25x "
                "paper notional on industry_laggard_repair and "
                "revision_surprise_low_extension rows. PnL is recomputed from "
                "the selected row pnl_pct_net and scaled notional."
            ),
        },
        "parameters": {
            "rule_version": allocator_helper.RULE_VERSION,
            "source_rule_version": allocator_helper.SOURCE_RULE_VERSION,
            "source_priority": allocator_helper.SOURCE_PRIORITY,
            "base_paper_notional_usd": allocator_helper.BASE_NOTIONAL_USD,
            "source_notional_scalars": SCALARS,
            "daily_entry_slots": 1,
            "same_ticker_cooldown_days": allocator_helper.SAME_TICKER_COOLDOWN_DAYS,
        },
        "gate1": {
            "baseline_artifact": "same-run before_unscaled_current payload",
            "baseline_metrics": {
                label: current_payload["after_metrics"][label]
                for label in framework.WINDOWS
            },
            "passed": True,
        },
        "gate2": {
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
                "accepted allocator source row source_family",
                "accepted allocator source row pnl_pct_net/pnl",
                "accepted allocator selected row paper_notional_usd",
                "daily snapshot candidate source_notional_scalar",
            ],
            "open_positions": current_payload["gate2"]["open_positions"],
            "passed": True,
        },
        "gate3": {
            "new_core_filter_added": False,
            "candidate_selection_changed": False,
            "minimum_core_survival_rate": gate4["minimum_core_survival_rate"],
            "passed": gate4["survival_guard_passed"],
            "note": "Default-off paper notional only; core signals/survival unchanged.",
        },
        "gate4": gate4,
        "before_payload_summary": {
            "delta_vs_core": current_payload["delta_metrics"]["aggregate"],
            "status": current_payload["status"],
            "decision": current_payload["decision"],
        },
        "after_payload_summary": {
            "delta_vs_core": scaled_payload["delta_metrics"]["aggregate"],
            "status": scaled_payload["status"],
            "decision": scaled_payload["decision"],
        },
        "before_metrics": {
            label: window_rows[label]["before"] for label in framework.WINDOWS
        },
        "after_metrics": {
            label: window_rows[label]["after"] for label in framework.WINDOWS
        },
        "delta_metrics": {
            "by_window": OrderedDict(
                (label, row["delta"]) for label, row in window_rows.items()
            ),
            "aggregate": aggregate,
        },
        "window_rows": window_rows,
        "target_trade_summary": target_summary,
        "affected_trades_by_window": target_summary["trades_by_window"],
        "production_impact": PRODUCTION_IMPACT,
        "full_stack_verdict": (
            "accepted_paper_pending_forward" if accepted else "reject"
        ),
        "interpretation": (
            "The low-overlap source notional scalar improved the current accepted "
            "allocator across the canonical windows and is retained as shared "
            "default-off paper observation only."
            if accepted
            else "The low-overlap source notional scalar failed Gate 4 and is not retained."
        ),
        "rejection_reason": None if accepted else "; ".join(gate4["failed_reasons"]),
        "post_run_reflection": {
            "why_result_happened": (
                "The selected industry laggard repair and revision rows were "
                "sufficiently positive after current allocator arbitration, so "
                "source-aware paper capital improved without changing selection."
                if accepted
                else (
                    "The independence map did not translate into enough incremental "
                    "after-arbitration replacement value once source selection stayed fixed."
                )
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry by sweeping the 1.25 scalar, source rank, allocator "
                "top-N, hold days, cooldown, or adding adjacent revision/laggard "
                "thresholds on the frozen windows."
            ),
            "new_evidence_required": (
                "Closed forward allocator replacement-value rows tagged by source "
                "family and realized overlap, or a materially new out-of-sample "
                "independence surface."
            ),
        },
        "next_retry_requires": [
            "closed forward source-family replacement-value rows",
            "out-of-sample source independence map",
            "no frozen-window scalar sweep",
        ],
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
            _repo_rel(PARITY_MATRIX_MD),
            _repo_rel(PLAYBOOK_MD),
        ],
    }


def _window_table(payload: dict[str, Any]) -> list[str]:
    rows = [
        "| Window | Current EV | Scaled EV | dEV | Current PnL | Scaled PnL | dPnL | DD d | Affected trades |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        affected = len(payload["affected_trades_by_window"][label])
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | {dd:+.4f} | {affected} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta["expected_value_score"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta["total_pnl"],
                dd=delta["max_drawdown_pct"],
                affected=affected,
            )
        )
    return rows


def _build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Accepted Allocator Independent Source Notional",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4: Current Allocator vs Scaled Allocator",
            "",
            *_window_table(payload),
            "",
            "- Aggregate incremental EV: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate incremental PnL: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Affected trades: `{}` across `{}` windows".format(
                payload["target_trade_summary"]["total_trade_count"],
                len(payload["target_trade_summary"]["windows_with_target_trades"]),
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Production Impact",
            "",
            PRODUCTION_IMPACT["parity_note"],
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
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
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
                "affected_trade_count": len(payload["affected_trades_by_window"][label]),
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
                "full_stack_verdict": payload["full_stack_verdict"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "aggregate_expected_value_delta": payload["delta_metrics"]["aggregate"][
                    "expected_value_score_delta_sum"
                ],
                "aggregate_strategy_total_pnl_delta": payload["delta_metrics"][
                    "aggregate"
                ]["total_pnl_delta_sum"],
                "accepted": payload["gate4"]["passed"],
                "calibration": payload["calibration"],
                "production_impact": PRODUCTION_IMPACT,
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
        "full_stack_verdict": payload["full_stack_verdict"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": payload["delta_metrics"]["aggregate"][
            "expected_value_score_delta_sum"
        ],
        "aggregate_strategy_total_pnl_delta": payload["delta_metrics"]["aggregate"][
            "total_pnl_delta_sum"
        ],
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
    paths = [Path(path) for path in payload["related_files"]]
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


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            framework._safe(_build_log_record(payload)),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
