"""exp-20260621-001: peer-shock source notional scalar for accepted allocator.

Alpha search. Tests one attributable allocation hypothesis: keep the accepted
helper source-priority allocator selection fixed, keep the accepted exp-032
industry laggard / revision source scalars fixed, and add only a small
default-off paper notional scalar to selected rolling_peer_shock rows.
No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, OrderedDict
from copy import deepcopy
from pathlib import Path
from typing import Any

import exp_20260620_032_accepted_allocator_independent_source_notional as template

framework = template.framework
allocator_helper = template.allocator_helper

REPO_ROOT = framework.REPO_ROOT
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for entry in (str(REPO_ROOT), str(QUANT_ROOT), str(SCRIPTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260621-001"
OWNER = "alpha-search-automation"
STEM = "accepted_allocator_peer_shock_notional"
TRIAL_FAMILY = "accepted_default_off_helper_source_priority_allocation"
TRIAL_VARIANT_ID = "accepted_allocator_peer_shock_independent_source_notional_scalar_v1"
CHANGED_VARIABLE = TRIAL_VARIANT_ID
TARGET_SOURCE = "rolling_peer_shock"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260621_001_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

CURRENT_SCALARS = OrderedDict(
    [
        ("industry_laggard_repair", 1.25),
        ("revision_surprise_low_extension", 1.25),
    ]
)

AFTER_SCALARS = OrderedDict(
    [
        ("industry_laggard_repair", 1.25),
        ("revision_surprise_low_extension", 1.25),
        (TARGET_SOURCE, 1.25),
    ]
)

MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3
MAX_DRAWDOWN_WORSE = 0.005
MAX_SINGLE_POSITIVE_SHARE = 0.50
MAX_POSITIVE_HHI = 0.35

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "peer_shock_sample_too_small",
        "independence_map_in_sample",
        "accepted_allocator_comparator_not_beaten",
        "drawdown_drift",
    ],
    "confidence_reason": (
        "Mechanism is capital allocation to an already selected allocator source "
        "with low corrected cross-sleeve correlation and positive standalone "
        "return. Risk is that peer_shock had only five corrected harness trades, "
        "core-flow inputs under-fire in the harness, and allocator source-notional "
        "experiments are heavily explored."
    ),
    "recorded_at": "2026-06-21T00:04:31+00:00",
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "allocation: selected rolling_peer_shock rows in the accepted helper "
        "allocator should receive a small default-off paper notional scalar "
        "because exp-20260620-033 corrected the sleeve independence map and "
        "showed peer_shock has low cross-sleeve correlation, zero ticker-date "
        "overlap, positive mean return, and was not included in exp-20260620-032."
    ),
    "2_history_check": {
        "novelty_gate": (
            "experiment.py new warned on allocator near-neighbors. The override "
            "is the exp-20260620-033 corrected independence map newly identifying "
            "rolling_peer_shock as a low-correlation positive source; exp-032 "
            "scaled only industry_laggard_repair and revision_surprise_low_extension."
        ),
        "exp-20260620-032": (
            "Accepted 1.25x default-off source-notional scalar for selected "
            "industry_laggard_repair and revision_surprise_low_extension rows. "
            "This run keeps those scalars as the before state and tests only "
            "rolling_peer_shock."
        ),
        "exp-20260620-033": (
            "Corrected accepted-sleeve independence map. peer_shock had mean abs "
            "correlation 0.027, zero ticker-date overlap, n=5 corrected harness "
            "trades, mean net return 2.524%, and total PnL $504.82."
        ),
        "exp-20260611-005": (
            "Current accepted source-priority allocator family; this run does not "
            "alter rank, source selection, daily top-1, hold, costs, or cooldown."
        ),
        "exp-20260613-033": (
            "Allocator crowding/correlation context warned against naive source "
            "stacking; this run only tests notional on a corrected low-overlap "
            "source already selected by the allocator."
        ),
    },
    "3_single_causal_variable": (
        "One fixed policy bundle: add source_notional_scalar=1.25 for selected "
        "rolling_peer_shock allocator rows, while the accepted exp-032 laggard/"
        "revision scalars, source selection, source rank, daily top-1, hold, "
        "costs, cooldown, core behavior, LLM/news, and live/default orders remain fixed."
    ),
    "4_acceptance_standard": (
        "Use docs/backtesting.md canonical three windows. Before is the current "
        "accepted allocator including exp-032 source scalars; after adds only "
        "rolling_peer_shock 1.25x. Accept only if aggregate EV/PnL improve, no "
        "window EV/PnL regression, affected peer_shock sample spans all three "
        "windows with >=20 rows, survival/concentration/drawdown guards pass, "
        "and the after allocator still beats accepted comparators."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260621_001_accepted_allocator_peer_shock_notional.py"
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


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


def _target_trade_summary(
    trades_by_window: OrderedDict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    target_by_window: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    positive_by_ticker: Counter[str] = Counter()
    total_incremental = 0.0
    for label, trades in trades_by_window.items():
        rows: list[dict[str, Any]] = []
        for row in trades:
            if str(row.get("source_family") or "") != TARGET_SOURCE:
                continue
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
        target_by_window[label] = rows

    positive_total = sum(float(value) for value in positive_by_ticker.values())
    hhi = None
    max_share = None
    top5_share = None
    if positive_total > 0:
        shares = [float(value) / positive_total for value in positive_by_ticker.values()]
        hhi = round(sum(share * share for share in shares), 6)
        max_share = round(max(shares), 6)
        top5_share = round(
            sum(sorted((float(value) for value in positive_by_ticker.values()), reverse=True)[:5])
            / positive_total,
            6,
        )

    return {
        "target_source": TARGET_SOURCE,
        "trades_by_window": target_by_window,
        "total_trade_count": sum(len(rows) for rows in target_by_window.values()),
        "windows_with_target_trades": [
            label for label, rows in target_by_window.items() if rows
        ],
        "incremental_pnl_sum": round(total_incremental, 2),
        "positive_by_ticker_pnl": dict(positive_by_ticker),
        "max_single_positive_pnl_share": max_share,
        "positive_pnl_hhi": hhi,
        "top5_positive_share": top5_share,
    }


def _production_impact(accepted: bool) -> dict[str, Any]:
    return {
        "trade_enabled": False,
        "alters_orders": False,
        "adapter_status": (
            "shared_default_off_paper_helper" if accepted else "replay_only_no_shared_change"
        ),
        "shared_policy_changed": accepted,
        "backtester_adapter_changed": accepted,
        "run_adapter_changed": accepted,
        "replay_only": not accepted,
        "default_off_paper_only": True,
        "daily_snapshot_exposed": accepted,
        "parity_test_added": accepted,
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
            "If accepted, historical replay and daily default-off snapshots use "
            "the same shared accepted-helper allocator source_notional_scalars. "
            "If rejected, no shared helper, run adapter, daily snapshot, live "
            "orders, or core behavior changes are retained."
        ),
    }


def _binding_gate4(
    *,
    aggregate: dict[str, Any],
    target_summary: dict[str, Any],
    current_payload: dict[str, Any],
    after_payload: dict[str, Any],
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
    if not after_payload["gate4"]["passed"]:
        failed.append("scaled_allocator_no_longer_beats_accepted_comparators")

    accepted = not failed
    return {
        "passed": accepted,
        "decision": (
            "accepted_allocator_peer_shock_source_notional_scalar"
            if accepted
            else "rejected_allocator_peer_shock_source_notional_scalar"
        ),
        "failed_reasons": failed,
        "aggregate_ev_delta_vs_current_allocator": aggregate[
            "expected_value_score_delta_sum"
        ],
        "aggregate_pnl_delta_vs_current_allocator": aggregate["total_pnl_delta_sum"],
        "current_allocator_core_delta": current_payload["delta_metrics"]["aggregate"],
        "after_allocator_core_delta": after_payload["delta_metrics"]["aggregate"],
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
            "top5_positive_share": target_summary["top5_positive_share"],
        },
    }


def build_payload() -> dict[str, Any]:
    original_scalars = dict(allocator_helper.SOURCE_NOTIONAL_SCALARS)
    try:
        current_payload = template._run_allocator_pass(
            "before_current_exp032", dict(CURRENT_SCALARS)
        )
        after_payload = template._run_allocator_pass(
            "after_peer_shock_scaled", dict(AFTER_SCALARS)
        )
    finally:
        template._set_scalars(original_scalars)

    window_rows: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for label in framework.WINDOWS:
        before = current_payload["after_metrics"][label]
        after = after_payload["after_metrics"][label]
        window_rows[label] = {
            "before": before,
            "after": after,
            "delta": _delta(after, before),
            "current_allocator_core_delta": current_payload["delta_metrics"]["by_window"][
                label
            ],
            "after_allocator_core_delta": after_payload["delta_metrics"]["by_window"][
                label
            ],
            "selected_source_counts": after_payload["window_rows"][label][
                "selected_source_counts"
            ],
        }

    aggregate = _aggregate_incremental(window_rows)
    target_summary = _target_trade_summary(after_payload["target_trades_by_window"])
    gate4 = _binding_gate4(
        aggregate=aggregate,
        target_summary=target_summary,
        current_payload=current_payload,
        after_payload=after_payload,
    )
    accepted = gate4["passed"]
    timestamp = framework._utc_now()
    production_impact = _production_impact(accepted)
    status = "accepted_paper_pending_forward" if accepted else "rejected"
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
        "decision": gate4["decision"],
        "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
        "change_type": "candidate_pool_full_stack",
        "implementation_mode": (
            "shared_paper_first" if accepted else "replay_screen_rejected_before_shared_change"
        ),
        "changed_variable": CHANGED_VARIABLE,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "corrected_accepted_sleeve_independence_map",
        "nearby_prior_experiments": [
            "exp-20260620-032",
            "exp-20260620-033",
            "exp-20260611-005",
            "exp-20260613-033",
        ],
        "prior_trial_count": 5,
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
                "Before: current accepted allocator with exp-032 "
                "industry_laggard_repair and revision_surprise_low_extension "
                "source_notional_scalars. After: same source selection with only "
                "rolling_peer_shock added at 1.25x paper notional. PnL is "
                "recomputed from selected row pnl_pct_net and scaled notional."
            ),
        },
        "parameters": {
            "rule_version": allocator_helper.RULE_VERSION,
            "source_rule_version": allocator_helper.SOURCE_RULE_VERSION,
            "source_priority": allocator_helper.SOURCE_PRIORITY,
            "base_paper_notional_usd": allocator_helper.BASE_NOTIONAL_USD,
            "before_source_notional_scalars": CURRENT_SCALARS,
            "after_source_notional_scalars": AFTER_SCALARS,
            "target_source": TARGET_SOURCE,
            "daily_entry_slots": 1,
            "same_ticker_cooldown_days": allocator_helper.SAME_TICKER_COOLDOWN_DAYS,
        },
        "gate1": {
            "baseline_artifact": "same-run current accepted allocator payload",
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
                "daily snapshot candidate source_notional_scalar if accepted",
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
            "delta_vs_core": after_payload["delta_metrics"]["aggregate"],
            "status": after_payload["status"],
            "decision": after_payload["decision"],
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
        "production_impact": production_impact,
        "full_stack_verdict": (
            "accepted_paper_pending_forward" if accepted else "reject"
        ),
        "interpretation": (
            "Peer-shock source notional improved the current accepted allocator "
            "and should be retained only as shared default-off paper observation."
            if accepted
            else "Peer-shock source notional failed Gate 4 and is not retained."
        ),
        "rejection_reason": None if accepted else "; ".join(gate4["failed_reasons"]),
        "post_run_reflection": {
            "why_result_happened": (
                "The corrected peer_shock independence signal translated into "
                "incremental after-arbitration paper capital without changing "
                "selection."
                if accepted
                else (
                    "The corrected independence map did not provide enough "
                    "after-arbitration replacement value for peer_shock once "
                    "sample, windows, and concentration gates were applied."
                )
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry by sweeping peer_shock scalar, source rank, "
                "allocator top-N, hold days, cooldown, or peer-shock OHLCV "
                "thresholds on the frozen windows."
            ),
            "new_evidence_required": (
                "Closed forward allocator replacement-value rows tagged by "
                "peer_shock source family, or a materially new out-of-sample "
                "source independence surface."
            ),
        },
        "next_retry_requires": [
            "closed forward peer_shock replacement-value rows",
            "out-of-sample source independence map",
            "no frozen-window source scalar sweep",
        ],
        "anti_js": "No JavaScript was used.",
        "related_files": _related_files(accepted),
    }


def _related_files(accepted: bool) -> list[str]:
    files = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    if accepted:
        files.extend(
            [
                "quant/accepted_helper_source_priority_allocator_paper_sleeve.py",
                "quant/test_accepted_helper_source_priority_allocator_paper_sleeve.py",
                "docs/production_backtest_parity_matrix.md",
                "docs/alpha-optimization-playbook.md",
            ]
        )
    return files


def _window_table(payload: dict[str, Any]) -> list[str]:
    rows = [
        "| Window | Current EV | After EV | dEV | Current PnL | After PnL | dPnL | DD d | Peer-shock trades |",
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
            f"# {EXPERIMENT_ID} Accepted Allocator Peer-Shock Notional",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            "",
            "## Hypothesis",
            "",
            payload["hypothesis"],
            "",
            "## Gate 4: Current Allocator vs Peer-Shock Scaled Allocator",
            "",
            *_window_table(payload),
            "",
            "- Aggregate incremental EV: `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"]
            ),
            "- Aggregate incremental PnL: `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"]
            ),
            "- Peer-shock affected trades: `{}` across `{}` windows".format(
                payload["target_trade_summary"]["total_trade_count"],
                len(payload["target_trade_summary"]["windows_with_target_trades"]),
            ),
            "- Failed reasons: `{}`".format(
                ", ".join(payload["gate4"]["failed_reasons"]) or "none"
            ),
            "",
            "## Production Impact",
            "",
            payload["production_impact"]["parity_note"],
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
        "production_impact": payload["production_impact"],
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
        "production_impact": payload["production_impact"],
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
