"""exp-20260611-010: allocator source-pruning scout.

Alpha search experiment. This tests one fixed source-allocation hypothesis:
remove the high-frequency, low-average `industry_laggard_repair` source from
the accepted helper source-priority allocator while leaving all other accepted
source semantics fixed.

No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import OrderedDict
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


EXPERIMENT_ID = "exp-20260611-010"
OWNER = "alpha-search-automation"
STEM = "allocator_prune_industry_laggard"
TRIAL_FAMILY = "accepted_default_off_helper_source_priority_allocation"
TRIAL_VARIANT_ID = "accepted_allocator_prune_industry_laggard_repair_source_v1"
CHANGED_VARIABLE = TRIAL_VARIANT_ID

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260611_010_{STEM}.json"
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

PRUNED_SOURCE_FAMILY = "industry_laggard_repair"

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

SOURCE_ATTRIBUTION_BASELINE = {
    "source": "data/experiments/exp-20260611-005/exp_20260611_005_lagged_consensus_shared_allocator_source.json",
    "industry_laggard_repair": {
        "trade_count": 193,
        "aggregate_pnl": 2023.56,
        "average_pnl": 10.48,
        "windows": {
            "late_strong": {"trade_count": 69, "pnl": -659.17, "average_pnl": -9.55},
            "mid_weak": {"trade_count": 59, "pnl": -419.21, "average_pnl": -7.11},
            "old_thin": {"trade_count": 65, "pnl": 3101.94, "average_pnl": 47.72},
        },
    },
}

PREDICTION = {
    "success_probability": 0.28,
    "expected_ev_delta": 0.25,
    "expected_pnl_delta": 5000.0,
    "main_failure_modes": [
        "old_thin_regression",
        "removes_useful_replacement_rows",
        "no_trade_gap_not_replaced",
        "accepted_allocator_comparator_not_beaten",
    ],
    "confidence_reason": (
        "Source-level attribution from exp-20260611-005 shows "
        "industry_laggard_repair selected 193 of 331 allocator trades with low "
        "aggregate average PnL and negative late/mid window contribution, but "
        "it was positive in old_thin so comparator risk is material."
    ),
    "recorded_at": "2026-06-11T07:06:19+00:00",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "parity_note": (
        "Replay-only source-pruning scout. The shared accepted-helper allocator "
        "and daily production observation path remain at the accepted "
        "exp-20260611-005 source set unless the pruning policy beats the "
        "accepted allocator comparator and is promoted through a shared helper "
        "plus parity test."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool/allocation: pruning the low-average, high-frequency "
        "industry_laggard_repair source from the accepted source-priority "
        "allocator may improve replacement value by avoiding noisy repair rows "
        "while keeping lagged consensus, volatility relief, rolling peer shock, "
        "turn-of-month, revision, compression, and stable core-flow fixed."
    ),
    "2_history_check": {
        "exp-20260611-005": (
            "Current accepted allocator with lagged consensus rank 1: aggregate "
            "EV +2.1849 and PnL +$40,397.21. This is the binding comparator."
        ),
        "exp-20260611-008": (
            "Distribution absorption allocator addition was rejected despite "
            "positive aggregate because it failed the accepted allocator in "
            "late_strong EV and old_thin EV/PnL."
        ),
        "exp-20260611-003": (
            "VBB allocator addition was rejected despite positive aggregate "
            "because it failed the accepted allocator comparator."
        ),
        "exp-20260610-009": (
            "52-week-high allocator extension was positive versus core but "
            "rejected against the accepted allocator."
        ),
        "exp-20260610-016": (
            "Post-earnings allocator extension was positive versus core but "
            "not incremental after higher-priority allocator rows."
        ),
    },
    "3_single_causal_variable": (
        "One fixed policy bundle: remove industry_laggard_repair from the "
        "accepted source-priority allocator. Existing source rules, order of "
        "remaining sources, top-1/day, notional, hold, costs, cooldown, core "
        "behavior, LLM/news, and live/default orders remain fixed."
    ),
    "4_acceptance_standard": (
        "Use docs/backtesting.md three canonical windows. Accept only if "
        "aggregate EV/PnL improve, no EV/PnL window regresses, sample/survival/"
        "drawdown/concentration guards pass, and exp-20260611-005 accepted "
        "allocator aggregate plus every per-window EV/PnL comparator is beaten."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260611_010_allocator_prune_industry_laggard.py"
    ),
}


def _repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return str(value.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def _top5_positive_share(target_summary: dict[str, Any]) -> float | None:
    positive = target_summary.get("positive_by_ticker_pnl") or {}
    total = sum(float(value) for value in positive.values())
    if total <= 0:
        return None
    top5 = sum(sorted((float(value) for value in positive.values()), reverse=True)[:5])
    return round(top5 / total, 6)


def _install_pruned_variant() -> None:
    original_priority: "OrderedDict[str, dict[str, Any]]" = deepcopy(
        allocator_helper.SOURCE_PRIORITY
    )
    original_build_source_trades = allocator_helper._build_source_trades

    proposed_priority: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    next_rank = 1
    for source_family, meta in allocator_helper.SOURCE_PRIORITY.items():
        if source_family == PRUNED_SOURCE_FAMILY:
            continue
        updated = deepcopy(meta)
        updated["rank"] = next_rank
        proposed_priority[source_family] = updated
        next_rank += 1

    allocator_helper.SOURCE_PRIORITY.clear()
    allocator_helper.SOURCE_PRIORITY.update(proposed_priority)
    allocator_helper.RULE_VERSION = (
        "accepted_helper_source_priority_shared_default_off_allocator_v2_prune_industry_laggard_rejected_exp_20260611_010"
    )
    allocator_helper.SOURCE_RULE_VERSION = (
        "accepted_helper_source_priority_top1_without_industry_laggard_repair_v1_rejected"
    )
    base.RULE_VERSION = allocator_helper.RULE_VERSION
    base.SOURCE_RULE_VERSION = allocator_helper.SOURCE_RULE_VERSION

    def _build_source_trades_without_pruned(
        *args: Any,
        **kwargs: Any,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        pruned_priority = deepcopy(allocator_helper.SOURCE_PRIORITY)
        allocator_helper.SOURCE_PRIORITY.clear()
        allocator_helper.SOURCE_PRIORITY.update(original_priority)
        try:
            source_trades, source_audit = original_build_source_trades(*args, **kwargs)
        finally:
            allocator_helper.SOURCE_PRIORITY.clear()
            allocator_helper.SOURCE_PRIORITY.update(pruned_priority)

        pruned_rows = [
            row
            for row in source_trades
            if str(row.get("source_family") or "") == PRUNED_SOURCE_FAMILY
        ]
        filtered_rows = [
            row
            for row in source_trades
            if str(row.get("source_family") or "") != PRUNED_SOURCE_FAMILY
        ]
        source_audit["source_priority"] = deepcopy(allocator_helper.SOURCE_PRIORITY)
        source_audit["pruned_source_family"] = PRUNED_SOURCE_FAMILY
        source_audit["pruned_source_trade_count"] = len(pruned_rows)
        source_audit["source_trade_counts"][PRUNED_SOURCE_FAMILY] = 0
        return filtered_rows, source_audit

    allocator_helper._build_source_trades = _build_source_trades_without_pruned


def _binding_gate4(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    target_summary = payload["target_trade_summary"]
    before_metrics = payload["before_metrics"]
    window_rows = payload["window_rows"]
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
        if float(delta.get("expected_value_score") or 0.0) < comparator["ev"]:
            comparator_regressions.append(f"{label}_ev")
        if float(delta.get("total_pnl") or 0.0) < comparator["pnl"]:
            comparator_regressions.append(f"{label}_pnl")
    if comparator_regressions:
        failed.append("accepted_allocator_window_comparator_regression")

    passed = not failed
    return {
        "passed": passed,
        "decision": (
            "accepted_allocator_prune_industry_laggard_repair_source"
            if passed
            else "rejected_allocator_prune_industry_laggard_repair_source"
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
        "source_attribution_baseline": SOURCE_ATTRIBUTION_BASELINE,
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
        "parity_test_added": False,
        "shared_adapter_module": "runner_local_rejected_variant",
    }


def build_payload() -> dict[str, Any]:
    _install_pruned_variant()
    payload = base.build_payload()
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "lane": "alpha_search",
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "candidate_pool_full_stack",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "source_level_historical_attribution",
            "nearby_prior_experiments": [
                "exp-20260611-005",
                "exp-20260611-008",
                "exp-20260611-003",
                "exp-20260610-009",
                "exp-20260610-016",
            ],
            "prior_trial_count": 1,
            "prediction": PREDICTION,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "production_impact": PRODUCTION_IMPACT,
        }
    )
    payload["parameters"].update(
        {
            "rule_version": allocator_helper.RULE_VERSION,
            "source_rule_version": allocator_helper.SOURCE_RULE_VERSION,
            "source_priority": allocator_helper.SOURCE_PRIORITY,
            "pruned_source_family": PRUNED_SOURCE_FAMILY,
            "source_attribution_baseline": SOURCE_ATTRIBUTION_BASELINE,
            "accepted_allocator_comparator": ACCEPTED_ALLOCATOR_COMPARATOR,
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Experiment runner temporarily removes industry_laggard_repair from "
        "the accepted-helper allocator source set, preserves the remaining "
        "relative source priority, selects one paper trade per signal date, "
        "applies a 12-trading-day same-ticker cooldown, then overlays next-open/"
        "10-day paper outcomes. No shared production/default-off helper changes "
        "are retained unless the comparator passes and a shared parity update is "
        "made."
    )
    payload["gate2"]["runtime_fields"].append(
        "runner-local accepted allocator SOURCE_PRIORITY without industry_laggard_repair"
    )
    payload["gate4"] = _binding_gate4(payload)
    accepted = payload["gate4"]["passed"]
    payload["status"] = "accepted_paper_pending_forward" if accepted else "rejected"
    payload["decision"] = payload["gate4"]["decision"]
    payload["expected_value_score_delta"] = payload["delta_metrics"]["aggregate"][
        "expected_value_score_delta_sum"
    ]
    payload["total_pnl_delta"] = payload["delta_metrics"]["aggregate"][
        "total_pnl_delta_sum"
    ]
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": accepted,
        "failure_modes_observed": payload["gate4"]["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if accepted else 0.0)) ** 2,
            6,
        ),
    }
    payload["interpretation"] = (
        "Pruning industry_laggard_repair beat the accepted allocator comparator "
        "and can be promoted only after shared helper and daily parity updates."
        if accepted
        else "Pruning industry_laggard_repair failed the accepted allocator comparator."
    )
    payload["rejection_reason"] = None if accepted else "; ".join(payload["gate4"]["failed_reasons"])
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The high-frequency repair rows were low-value enough that pruning "
            "improved replacement value even after old_thin risk."
            if accepted
            else (
                "The industry_laggard_repair source looked weak in late/mid "
                "attribution, but removing it eliminated too many useful old_thin "
                "or date-coverage replacement rows and did not beat the accepted "
                "allocator across the binding comparator."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by changing industry_laggard rank, selective pruning "
            "thresholds, allocator top-N, notional, hold days, or cooldown on "
            "the same frozen windows."
        ),
        "new_evidence_required": (
            "Retry only with closed forward source-level displacement rows or a "
            "new PIT quality field that separates useful industry repair rows "
            "from noisy ones before selection."
        ),
    }
    payload["next_retry_requires"] = [
        "closed forward allocator source-level displacement rows",
        "new PIT repair-quality field",
        "no frozen-window industry_laggard rank or threshold retune",
    ]
    payload["accepted_comparators"] = {
        "accepted_allocator": ACCEPTED_ALLOCATOR_COMPARATOR,
        "source_attribution_baseline": SOURCE_ATTRIBUTION_BASELINE,
        "pruned_source_priority": allocator_helper.SOURCE_PRIORITY,
    }
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return payload


def _window_table(payload: dict[str, Any]) -> list[str]:
    rows = [
        "| Window | dEV | Accepted dEV | dPnL | Accepted dPnL | DD d | Trades | Pruned source selected |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        delta = payload["delta_metrics"]["by_window"][label]
        row = payload["window_rows"][label]
        comparator = ACCEPTED_ALLOCATOR_COMPARATOR["window_deltas"][label]
        rows.append(
            "| {label} | {dev:+.4f} | {cev:+.4f} | ${dpnl:+,.2f} | ${cpnl:+,.2f} | {dd:+.4f} | {trades} | {selected} |".format(
                label=label,
                dev=delta.get("expected_value_score", 0.0),
                cev=comparator["ev"],
                dpnl=delta.get("total_pnl", 0.0),
                cpnl=comparator["pnl"],
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=row["target_trade_count"],
                selected=row["selected_source_counts"].get(PRUNED_SOURCE_FAMILY, 0),
            )
        )
    return rows


def _build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Allocator Prune Industry Laggard",
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
        "accepted_alpha": False,
        "production_accepted": False,
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
                "pruned_source_selected_count": payload["window_rows"][label][
                    "selected_source_counts"
                ].get(PRUNED_SOURCE_FAMILY, 0),
            }
            for label in framework.WINDOWS
        ],
        "prediction": PREDICTION,
        "calibration": payload["calibration"],
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "post_run_reflection": payload["post_run_reflection"],
        "negative_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _upsert_current_experiment_jsonl(path: Path, record: dict[str, Any]) -> None:
    line = json.dumps(framework._safe(record), ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                row = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                continue
            rows.append(existing)
    rows.append(line)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON, {})
    ticket.update(
        {
            "status": payload["status"],
            "completed_at": payload["timestamp"],
            "decision": payload["decision"],
            "summary": payload["interpretation"],
            "causal_components": [
                "source-pruning policy",
                "historical replay",
                "runner-local rejected variant",
                "full-stack verdict",
            ],
            "result": {
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "aggregate_expected_value_delta": payload["expected_value_score_delta"],
                "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
                "accepted": payload["gate4"]["passed"],
                "calibration": payload["calibration"],
                "production_impact": PRODUCTION_IMPACT,
            },
        }
    )
    ticket["allowed_write_scope"] = sorted(payload["related_files"])
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
    _upsert_current_experiment_jsonl(EXPERIMENT_LOG, log_record)
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
