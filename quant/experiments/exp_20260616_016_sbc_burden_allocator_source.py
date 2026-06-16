"""exp-20260616-016: SBC burden-improvement allocator source.

Full-stack alpha search. Tests one attributable policy bundle: admit the
accepted SBC burden-improvement default-off paper rows as a fixed rank-2 source
inside the shared accepted-helper source-priority allocator. No JavaScript is
used.
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
from sbc_burden_improvement_paper_sleeve import (  # noqa: E402
    build_sbc_burden_improvement_historical_trades,
)
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260616-016"
OWNER = "alpha-search-automation"
STEM = "sbc_burden_allocator_source"
TRIAL_FAMILY = "accepted_default_off_helper_source_priority_allocation"
TRIAL_VARIANT_ID = "sbc_burden_improvement_rank2_shared_allocator_source_v1"
CHANGED_VARIABLE = TRIAL_VARIANT_ID
SBC_SOURCE_FAMILY = "sbc_burden_improvement"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260616_016_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
PARITY_MATRIX_MD = REPO_ROOT / "docs" / "production_backtest_parity_matrix.md"

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

ACCEPTED_SBC_COMPARATOR = {
    "experiment_id": "exp-20260616-015",
    "aggregate_ev_delta": 0.9438,
    "aggregate_pnl_delta": 15748.19,
    "target_trade_count": 108,
    "window_deltas": {
        "late_strong": {"ev": 0.4738, "pnl": 6269.93},
        "mid_weak": {"ev": 0.4375, "pnl": 8388.43},
        "old_thin": {"ev": 0.0325, "pnl": 1089.83},
    },
}

PREDICTION = {
    "success_probability": 0.28,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "redundant_with_lagged_consensus",
        "displaces_better_allocator_rows",
        "old_thin_regression",
        "accepted_allocator_comparator_not_beaten",
    ],
    "confidence_reason": (
        "SBC burden improvement just passed shared default-off Gate 4 with a "
        "distinct SEC dilution-quality field, but allocator source extensions "
        "often fail once lagged consensus and volatility relief already occupy "
        "higher-priority rows."
    ),
    "recorded_at": "2026-06-16T15:05:24+00:00",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "rejected_runner_local_allocator_source_replay",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "shared_policy_tested_and_rolled_back": True,
    "production_signal_path_changed": False,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "trade_enabled": False,
    "alters_orders": False,
    "uses_llm": False,
    "uses_free_ohlcv_only": False,
    "uses_free_non_ohlcv": True,
    "live_realism_evaluated": True,
    "live_ready": False,
    "parity_note": (
        "Rejected replay of SBC burden improvement as a rank-2 allocator source. "
        "The runner installs the variant locally for reproducibility, but the "
        "shared allocator helper, daily snapshot path, and live/default orders "
        "are not retained."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool/allocation: accepted SBC burden-improvement rows use raw "
        "SEC Companyfacts to identify improving dilution burden with positive "
        "revenue/gross-profit context. Adding them as fixed rank 2 may expand "
        "the accepted allocator with a free-data quality signal that is distinct "
        "from OHLCV morphology and lagged source consensus."
    ),
    "2_history_check": {
        "exp-20260616-015": (
            "Accepted shared SBC burden-improvement adapter: aggregate EV "
            "+0.9438, PnL +$15,748.19, 108 trades, all three windows positive."
        ),
        "exp-20260616-014": (
            "Positive private replay lead promoted by exp-20260616-015; not a "
            "standalone accepted production-visible result."
        ),
        "exp-20260611-005": (
            "Current binding accepted allocator comparator: aggregate EV "
            "+2.1849 and PnL +$40,397.21, all three canonical windows positive."
        ),
        "exp-20260611-015": (
            "SEC FTD+FINRA allocator source was rejected because source "
            "extensions can be positive versus core while failing the accepted "
            "allocator comparator."
        ),
    },
    "3_single_causal_variable": (
        "One fixed policy bundle: accepted SBC burden-improvement rows enter the "
        "shared accepted-helper allocator as rank 2, after lagged consensus and "
        "before volatility relief. Existing top-1/day, paper notional, hold, "
        "costs, cooldown, core behavior, LLM/news, and live/default orders stay "
        "fixed."
    ),
    "4_acceptance_standard": (
        "Use docs/backtesting.md three canonical windows. Accept only if "
        "aggregate EV/PnL improve, no EV/PnL window regresses, sample/survival/"
        "drawdown/concentration guards pass, and exp-20260611-005 accepted "
        "allocator aggregate plus every per-window EV/PnL comparator is beaten."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260616_016_sbc_burden_allocator_source.py"
    ),
}


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


def _top5_positive_share(target_summary: dict[str, Any]) -> float | None:
    positive = target_summary.get("positive_by_ticker_pnl") or {}
    total = sum(float(value) for value in positive.values())
    if total <= 0:
        return None
    top5 = sum(sorted((float(value) for value in positive.values()), reverse=True)[:5])
    return round(top5 / total, 6)


def _install_replay_variant() -> None:
    proposed_priority: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    for source_family, meta in allocator_helper.SOURCE_PRIORITY.items():
        if source_family == "lagged_cross_source_consensus":
            proposed_priority[source_family] = {**deepcopy(meta), "rank": 1}
            proposed_priority[SBC_SOURCE_FAMILY] = {
                "rank": 2,
                "description": "accepted SBC burden-improvement dilution-quality source",
                "accepted_experiment": "exp-20260616-015",
                "accepted_ev_delta_sum": 0.9438,
                "accepted_pnl_delta_sum": 15748.19,
            }
        elif source_family == "volatility_relief":
            proposed_priority[source_family] = {**deepcopy(meta), "rank": 3}
        elif source_family == "rolling_peer_shock":
            proposed_priority[source_family] = {**deepcopy(meta), "rank": 4}
        elif source_family == "turn_of_month":
            proposed_priority[source_family] = {**deepcopy(meta), "rank": 5}
        elif source_family == "industry_laggard_repair":
            proposed_priority[source_family] = {**deepcopy(meta), "rank": 6}
        elif source_family == "revision_surprise_low_extension":
            proposed_priority[source_family] = {**deepcopy(meta), "rank": 7}
        elif source_family == "compression":
            proposed_priority[source_family] = {**deepcopy(meta), "rank": 8}
        elif source_family == "industry_stable_core_flow":
            proposed_priority[source_family] = {**deepcopy(meta), "rank": 9}
        else:
            proposed_priority[source_family] = deepcopy(meta)

    allocator_helper.SOURCE_PRIORITY.clear()
    allocator_helper.SOURCE_PRIORITY.update(proposed_priority)
    allocator_helper.RULE_VERSION = (
        "accepted_helper_source_priority_shared_default_off_allocator_v3_replay_exp_20260616_016"
    )
    allocator_helper.SOURCE_RULE_VERSION = (
        "accepted_helper_source_priority_top1_with_sbc_burden_allocation_v1_replay"
    )

    original_build_source_trades = allocator_helper._build_source_trades

    def _build_source_trades_with_sbc_burden(
        *,
        rows_by_ticker: dict[str, list[dict[str, Any]]],
        dates: list[str],
        window_label: str,
        window: dict[str, str],
        core_entries_by_date: dict[str, list[dict[str, Any]]],
        sector_entries: dict[str, dict[str, Any]],
        candidate_universe: dict[str, Any] | list[str] | None,
        calendar_dates: list[str] | None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        source_trades, source_audit = original_build_source_trades(
            rows_by_ticker=rows_by_ticker,
            dates=dates,
            window_label=window_label,
            window=window,
            core_entries_by_date=core_entries_by_date,
            sector_entries=sector_entries,
            candidate_universe=candidate_universe,
            calendar_dates=calendar_dates,
        )
        sbc_trades, sbc_audit = build_sbc_burden_improvement_historical_trades(
            ohlcv_by_ticker=rows_by_ticker,
            windows=OrderedDict([(window_label, window)]),
            candidate_universe=candidate_universe,
            sector_entries=sector_entries,
        )
        normalised: list[dict[str, Any]] = []
        for row in sbc_trades:
            normalised.append(
                {
                    **allocator_helper._normalise_source_row(
                        row,
                        SBC_SOURCE_FAMILY,
                    ),
                    "uses_free_ohlcv_only": False,
                    "uses_free_non_ohlcv": True,
                }
            )
        source_trades.extend(normalised)
        source_audit["source_priority"] = allocator_helper.SOURCE_PRIORITY
        source_audit["source_trade_counts"][SBC_SOURCE_FAMILY] = len(normalised)
        source_audit["raw_candidate_counts"][SBC_SOURCE_FAMILY] = sbc_audit.get(
            "raw_candidate_count_by_window",
            {},
        ).get(window_label)
        source_audit["source_audits"][SBC_SOURCE_FAMILY] = {
            "rule_version": sbc_audit.get("rule_version"),
            "source_rule_version": sbc_audit.get("source_rule_version"),
            "quality_index_summary": sbc_audit.get("quality_index_summary"),
            "scan": sbc_audit.get("scan_by_window", {}).get(window_label),
            "source_caveat": (
                "Runner-local replay of rejected rank-2 allocator source; "
                "shared helper and daily path are not retained."
            ),
        }
        return source_trades, source_audit

    allocator_helper._build_source_trades = _build_source_trades_with_sbc_burden
    base.RULE_VERSION = allocator_helper.RULE_VERSION
    base.SOURCE_RULE_VERSION = allocator_helper.SOURCE_RULE_VERSION


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
            "accepted_sbc_burden_rank2_allocator_source_extension"
            if passed
            else "rejected_sbc_burden_rank2_allocator_source_extension"
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
        "accepted_sbc_burden_comparator": ACCEPTED_SBC_COMPARATOR,
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
        "shared_adapter_module": "runner_local_replay_variant",
        "daily_snapshot_source": "not_retained_shared_candidate_was_rolled_back",
    }


def build_payload() -> dict[str, Any]:
    _install_replay_variant()
    payload = base.build_payload()
    gate4 = _binding_gate4(payload)
    accepted = gate4["passed"]
    status = "accepted_paper_pending_forward" if accepted else "rejected"
    decision = gate4["decision"]
    aggregate = payload["delta_metrics"]["aggregate"]

    for label, row in payload["window_rows"].items():
        selected = row.get("selected_source_counts") or {}
        source_counts = row.get("source_trade_counts") or {}
        row["sbc_burden_improvement_selected_count"] = selected.get(SBC_SOURCE_FAMILY, 0)
        row["sbc_burden_improvement_source_trade_count"] = source_counts.get(
            SBC_SOURCE_FAMILY,
            0,
        )

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "lane": "alpha_search",
            "status": status,
            "decision": decision,
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "candidate_pool_full_stack",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": (
                "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
            ),
            "multiple_testing_risk_bucket": "minimal",
            "new_evidence_type": (
                "accepted_raw_companyfacts_sbc_burden_source_priority_allocator_extension"
            ),
            "nearby_prior_experiments": [
                "exp-20260616-015",
                "exp-20260616-014",
                "exp-20260611-005",
                "exp-20260611-015",
                "exp-20260610-014",
            ],
            "prior_trial_count": 5,
            "prediction": PREDICTION,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "production_impact": PRODUCTION_IMPACT,
            "gate4": gate4,
            "expected_value_score_delta": aggregate["expected_value_score_delta_sum"],
            "total_pnl_delta": aggregate["total_pnl_delta_sum"],
            "full_stack_verdict": "paper_pending_forward" if accepted else "reject",
            "interpretation": (
                "SBC burden-improvement rank-2 source is numerically positive but "
                "requires shared helper/daily parity promotion before retention."
                if accepted
                else "SBC burden-improvement rank-2 source failed the accepted "
                "allocator comparator."
            ),
            "rejection_reason": None if accepted else "; ".join(gate4["failed_reasons"]),
        }
    )
    payload["parameters"].update(
        {
            "rule_version": allocator_helper.RULE_VERSION,
            "source_rule_version": allocator_helper.SOURCE_RULE_VERSION,
            "source_priority": allocator_helper.SOURCE_PRIORITY,
            "sbc_source_family": SBC_SOURCE_FAMILY,
            "paper_notional_usd": allocator_helper.BASE_NOTIONAL_USD,
            "daily_entry_slots": 1,
            "same_ticker_cooldown_days": allocator_helper.SAME_TICKER_COOLDOWN_DAYS,
            "accepted_allocator_comparator": ACCEPTED_ALLOCATOR_COMPARATOR,
            "accepted_sbc_burden_comparator": ACCEPTED_SBC_COMPARATOR,
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Experiment runner temporarily installs rank-2 SBC burden-improvement "
        "rows into the accepted-helper allocator module, selects one paper "
        "trade per signal date by fixed source priority, applies a "
        "12-trading-day same-ticker cooldown, then overlays next-open/10-day "
        "paper outcomes. The shared helper and daily snapshot path are not "
        "retained after this rejected replay."
    )
    payload["gate2"]["runtime_fields"].extend(
        [
            "raw SEC Companyfacts annual SBC/revenue/gross-profit facts",
            "SBC burden-improvement source rows with signal_date/ticker/candidate_score",
            "daily sbc_burden_improvement_paper_sleeve snapshot",
            "accepted allocator source_snapshots.sbc_burden_improvement daily parity path",
        ]
    )
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": accepted,
        "actual_retained_as_alpha": accepted,
        "failure_modes_observed": gate4["failed_reasons"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if accepted else 0.0)) ** 2,
            6,
        ),
    }
    if isinstance(payload.get("full_stack"), dict):
        payload["full_stack"]["verdict"] = {
            "verdict": payload["full_stack_verdict"],
            "gate4_passed": accepted,
            "live_ready": False,
            "next_step": (
                "Observe forward allocator displacement rows; live activation "
                "requires forward replacement value and kill-switch parity."
                if accepted
                else "Shared source extension was rolled back; avoid near-neighbor "
                "rank or threshold retunes."
            ),
        }
        payload["full_stack"]["execution_envelope"] = base.EXECUTION_ENVELOPE.to_dict()

    payload["accepted_comparators"] = {
        "accepted_allocator": ACCEPTED_ALLOCATOR_COMPARATOR,
        "accepted_sbc_burden_standalone": ACCEPTED_SBC_COMPARATOR,
        "included_source_priority": allocator_helper.SOURCE_PRIORITY,
    }
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The raw Companyfacts SBC burden signal added distinct dilution-"
            "quality replacement value after lagged consensus without degrading "
            "any canonical window."
            if accepted
            else (
                "The SBC burden source did not add enough incremental allocator "
                "replacement value after lagged consensus. It either overlapped "
                "existing accepted source dates or displaced better lower-rank "
                "allocator rows, especially versus the strong exp-20260611-005 "
                "comparator."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by changing SBC source rank, SBC/revenue thresholds, "
            "revenue/gross-profit floors, fact-age windows, allocator top-N, "
            "notional, hold days, or cooldown on the same frozen windows."
        ),
        "new_evidence_required": (
            "Retry only with closed forward allocator displacement rows, "
            "per-share SBC burden net buybacks, or grant-value normalization "
            "evidence that changes the underlying data edge."
        ),
    }
    payload["next_retry_requires"] = [
        "closed forward allocator displacement rows",
        "per-share SBC burden net buyback adjustment",
        "grant-value normalization evidence",
        "no frozen-window SBC rank or threshold retune",
    ]
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
        "| Window | Before EV | After EV | dEV | Accepted dEV | Before PnL | After PnL | dPnL | Accepted dPnL | DD d | Trades | SBC selected |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        row = payload["window_rows"][label]
        comparator = ACCEPTED_ALLOCATOR_COMPARATOR["window_deltas"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | {cev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | ${cpnl:+,.2f} | {dd:+.4f} | {trades} | {selected} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                cev=comparator["ev"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                cpnl=comparator["pnl"],
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=row["target_trade_count"],
                selected=row["sbc_burden_improvement_selected_count"],
            )
        )
    return rows


def _build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} SBC Burden Allocator Source",
            "",
            f"Status: `{payload['status']}`",
            f"Decision: `{payload['decision']}`",
            f"Full-stack verdict: `{payload['full_stack_verdict']}`",
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
            "## Reflection",
            "",
            payload["post_run_reflection"]["why_result_happened"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    accepted = payload["gate4"]["passed"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": accepted,
        "accepted_alpha": accepted,
        "production_accepted": accepted,
        "full_stack_verdict": payload["full_stack_verdict"],
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
        "full_stack": {
            "verdict": payload["full_stack"]["verdict"],
            "live_readiness": payload["full_stack"]["live_readiness"],
            "execution_envelope": payload["full_stack"]["execution_envelope"],
        },
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
        "production_impact": PRODUCTION_IMPACT,
        "pre_run_questions": PRE_RUN_QUESTIONS,
        "post_run_reflection": payload["post_run_reflection"],
        "anti_js": "No JavaScript was used.",
    }


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
            "result": {
                "decision": payload["decision"],
                "full_stack_verdict": payload["full_stack_verdict"],
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
