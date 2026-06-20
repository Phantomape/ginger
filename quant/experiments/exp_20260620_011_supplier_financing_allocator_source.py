"""exp-20260620-011: supplier-financing allocator source.

Replay-only alpha search. Tests one attributable policy bundle: insert the
accepted supplier-financing/debt-relief default-off paper rows as a fixed rank-3
source in the accepted-helper source-priority allocator. No production code or
live order path is changed by this runner. No JavaScript is used.
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
import supplier_financing_debt_relief_paper_sleeve as supplier_helper  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260620-011"
OWNER = "alpha-search-automation"
STEM = "supplier_financing_allocator_source"
TRIAL_FAMILY = "accepted_default_off_helper_source_priority_allocation"
TRIAL_VARIANT_ID = "supplier_financing_debt_relief_rank3_allocator_source_v1"
CHANGED_VARIABLE = TRIAL_VARIANT_ID
SOURCE_FAMILY = "supplier_financing_debt_relief"

SOURCE_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260620-009"
    / "exp_20260620_009_supplier_financing_debt_relief_shared_4k_risk_scaled_adapter.json"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260620_011_{STEM}.json"
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

ACCEPTED_SUPPLIER_COMPARATOR = {
    "experiment_id": "exp-20260620-009",
    "decision": "accepted_supplier_financing_debt_relief_shared_4k_risk_scaled_adapter",
    "aggregate_ev_delta": 0.6801,
    "aggregate_pnl_delta": 12355.48,
    "target_trade_count": 88,
    "window_deltas": {
        "late_strong": {"ev": 0.2776, "pnl": 3554.83},
        "mid_weak": {"ev": 0.3567, "pnl": 7109.00},
        "old_thin": {"ev": 0.0458, "pnl": 1691.65},
    },
}

PREDICTION = {
    "success_probability": 0.28,
    "expected_ev_delta": 0.20,
    "expected_pnl_delta": 5000.0,
    "main_failure_modes": [
        "redundant_with_lagged_consensus",
        "displaces_better_allocator_rows",
        "old_thin_regression",
        "accepted_allocator_comparator_not_beaten",
    ],
    "confidence_reason": (
        "exp-20260620-009 accepted this helper standalone across all windows, "
        "but prior accepted-helper source insertion often fails the binding "
        "allocator comparator; this tests allocator replacement value without "
        "changing DPO, debt, risk, ADV, notional, hold, or cooldown thresholds."
    ),
    "recorded_at": "2026-06-20T10:07:32+00:00",
}

PRODUCTION_IMPACT = {
    **base.PRODUCTION_IMPACT,
    "adapter_status": "replay_only_runner_local_allocator_source_scout",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "production_accepted": False,
    "trade_enabled": False,
    "alters_orders": False,
    "default_off_paper_only": True,
    "uses_llm": False,
    "uses_free_ohlcv_only": False,
    "uses_free_non_ohlcv": True,
    "uses_free_sec_companyfacts": True,
    "live_ready": False,
    "parity_note": (
        "Replay-only allocator source scout. The shared accepted-helper "
        "allocator, daily production observation path, live ranking, sizing, "
        "exits, and orders remain unchanged unless this source is separately "
        "promoted through a shared helper and parity tests."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool/allocation: the newly accepted supplier-financing/"
        "debt-relief helper may add distinct replacement value inside the "
        "accepted-helper source-priority allocator because it combines supplier "
        "credit funding pressure with deleveraging, which is orthogonal to the "
        "current OHLCV, consensus, revision, and seasonal source stack."
    ),
    "2_history_check": {
        "novelty_gate": (
            "Blocked as a near-neighbor of accepted allocator-source work; "
            "override was recorded because the genuinely new evidence axis is "
            "exp-20260620-009 becoming an accepted shared default-off supplier "
            "source family, not a DPO/debt threshold or risk/notional retune."
        ),
        "exp-20260620-009": (
            "Accepted supplier-financing/debt-relief helper: aggregate EV "
            "+0.6801, PnL +$12,355.48, 88 trades, all three windows positive."
        ),
        "exp-20260611-005": (
            "Current binding accepted allocator: aggregate EV +2.1849 and PnL "
            "+$40,397.21. This experiment must beat it aggregate and per-window."
        ),
        "exp-20260616-016": (
            "SBC burden allocator-source insertion was rejected; useful warning "
            "that standalone accepted helpers can still fail allocator replacement."
        ),
        "exp-20260611-015": (
            "SEC FTD+FINRA rank-3 allocator source was rejected against the "
            "accepted allocator comparator."
        ),
    },
    "3_single_causal_variable": (
        "One fixed policy bundle: accepted supplier-financing/debt-relief rows "
        "enter the accepted-helper allocator as rank 3, after lagged consensus "
        "and volatility relief and before rolling peer shock. Existing top-1/day, "
        "paper notional, hold, costs, cooldown, core behavior, LLM/news, and "
        "live/default orders remain fixed."
    ),
    "4_acceptance_standard": (
        "Use docs/backtesting.md three canonical windows. Accept only if "
        "aggregate EV/PnL improve, no EV/PnL window regresses, sample/survival/"
        "drawdown/concentration guards pass, and exp-20260611-005 accepted "
        "allocator aggregate plus every per-window EV/PnL comparator is beaten. "
        "A positive replay-only result is not retained without shared helper/"
        "daily parity promotion."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260620_011_supplier_financing_allocator_source.py"
    ),
}

_INSTALLED = False


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


def _supplier_source_trades(
    *,
    dates: list[str],
    window_label: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = _load_json(SOURCE_ARTIFACT, {})
    date_set = set(dates)
    rows = (payload.get("target_trades_by_window") or {}).get(window_label, [])
    source_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        signal_date = str(row.get("signal_date") or row.get("date") or "")[:10]
        ticker = str(row.get("ticker") or "").upper()
        if signal_date not in date_set or not ticker:
            continue
        source_score = row.get("candidate_score")
        normalised = allocator_helper._normalise_source_row(
            {
                **deepcopy(row),
                "date": signal_date,
                "signal_date": signal_date,
                "ticker": ticker,
                "source_family": SOURCE_FAMILY,
                "source_score": source_score,
                "candidate_score": source_score,
                "source_artifact": _repo_rel(SOURCE_ARTIFACT),
                "helper_rule_version": supplier_helper.RULE_VERSION,
                "helper_source_rule_version": supplier_helper.SOURCE_RULE_VERSION,
                "helper_risk_rule_version": supplier_helper.RISK_RULE_VERSION,
                "standalone_accepted_experiment_id": "exp-20260620-009",
                "supplier_standalone_paper_notional_usd": row.get("paper_notional_usd"),
                "uses_free_sec_companyfacts": True,
                "uses_raw_sec_companyfacts_cache": True,
                "uses_llm": False,
                "trade_enabled": False,
                "known_at": (
                    "raw_sec_companyfacts_filed_and_signal_close_before_next_open_paper_entry"
                ),
            },
            SOURCE_FAMILY,
        )
        normalised["uses_free_ohlcv_only"] = False
        normalised["uses_free_non_ohlcv"] = True
        normalised["uses_free_sec_companyfacts"] = True
        normalised["uses_raw_sec_companyfacts_cache"] = True
        source_rows.append(normalised)

    target_summary = payload.get("target_trade_summary") or {}
    trades_by_window = target_summary.get("trades_by_window") or {}
    return source_rows, {
        "rule_version": supplier_helper.RULE_VERSION,
        "source_rule_version": supplier_helper.SOURCE_RULE_VERSION,
        "risk_rule_version": supplier_helper.RISK_RULE_VERSION,
        "source_artifact": _repo_rel(SOURCE_ARTIFACT),
        "source_trade_count": len(source_rows),
        "raw_candidate_count": trades_by_window.get(window_label, len(source_rows)),
        "unique_source_tickers": len({row["ticker"] for row in source_rows}),
        "known_at": "after raw SEC Companyfacts filing before signal-close cut",
        "daily_entry_slots": 1,
    }


def _install_replay_variant() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    proposed_priority: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
    for source_family, meta in allocator_helper.SOURCE_PRIORITY.items():
        if source_family == "lagged_cross_source_consensus":
            proposed_priority[source_family] = {**deepcopy(meta), "rank": 1}
        elif source_family == "volatility_relief":
            proposed_priority[source_family] = {**deepcopy(meta), "rank": 2}
            proposed_priority[SOURCE_FAMILY] = {
                "rank": 3,
                "description": "accepted supplier financing plus debt relief",
                "accepted_experiment": "exp-20260620-009",
                "accepted_ev_delta_sum": 0.6801,
                "accepted_pnl_delta_sum": 12355.48,
            }
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
        "accepted_helper_source_priority_shared_default_off_allocator_v2_replay_exp_20260620_011"
    )
    allocator_helper.SOURCE_RULE_VERSION = (
        "accepted_helper_source_priority_top1_with_supplier_financing_debt_relief_allocation_v1_replay"
    )

    original_build_source_trades = allocator_helper._build_source_trades

    def _build_source_trades_with_supplier(
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
        supplier_trades, supplier_audit = _supplier_source_trades(
            dates=dates,
            window_label=window_label,
        )
        source_trades.extend(supplier_trades)
        source_audit["source_priority"] = allocator_helper.SOURCE_PRIORITY
        source_audit["source_trade_counts"][SOURCE_FAMILY] = len(supplier_trades)
        source_audit["raw_candidate_counts"][SOURCE_FAMILY] = supplier_audit[
            "raw_candidate_count"
        ]
        source_audit["source_audits"][SOURCE_FAMILY] = supplier_audit
        return source_trades, source_audit

    allocator_helper._build_source_trades = _build_source_trades_with_supplier
    base.RULE_VERSION = allocator_helper.RULE_VERSION
    base.SOURCE_RULE_VERSION = allocator_helper.SOURCE_RULE_VERSION
    _INSTALLED = True


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

    numeric_passed = not failed
    return {
        "passed": numeric_passed,
        "decision": (
            "positive_replay_lead_supplier_financing_rank3_allocator_source_requires_shared_promotion"
            if numeric_passed
            else "rejected_supplier_financing_rank3_allocator_source"
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
        "accepted_supplier_comparator": ACCEPTED_SUPPLIER_COMPARATOR,
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
        "shared_adapter_module": "runner_local_replay_variant",
    }


def build_payload() -> dict[str, Any]:
    _install_replay_variant()
    payload = base.build_payload()
    gate4 = _binding_gate4(payload)
    numeric_passed = gate4["passed"]
    retained = False

    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "lane": "alpha_search",
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "candidate_pool_full_stack",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": (
                "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
            ),
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": (
                "accepted_supplier_financing_debt_relief_source_priority_allocator_extension"
            ),
            "nearby_prior_experiments": [
                "exp-20260620-009",
                "exp-20260611-005",
                "exp-20260616-016",
                "exp-20260611-015",
            ],
            "prior_trial_count": 4,
            "prediction": PREDICTION,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "production_impact": PRODUCTION_IMPACT,
            "gate4": gate4,
            "status": (
                "positive_replay_lead_requires_shared_promotion"
                if numeric_passed
                else "rejected"
            ),
            "decision": gate4["decision"],
        }
    )
    payload["parameters"].update(
        {
            "rule_version": allocator_helper.RULE_VERSION,
            "source_rule_version": allocator_helper.SOURCE_RULE_VERSION,
            "source_priority": allocator_helper.SOURCE_PRIORITY,
            "paper_notional_usd": allocator_helper.BASE_NOTIONAL_USD,
            "daily_entry_slots": 1,
            "same_ticker_cooldown_days": allocator_helper.SAME_TICKER_COOLDOWN_DAYS,
            "source_artifact": _repo_rel(SOURCE_ARTIFACT),
            "accepted_allocator_comparator": ACCEPTED_ALLOCATOR_COMPARATOR,
            "accepted_supplier_comparator": ACCEPTED_SUPPLIER_COMPARATOR,
        }
    )
    payload["backtest_protocol"]["execution_model"] = (
        "Experiment runner temporarily installs rank-3 supplier-financing/"
        "debt-relief rows into the accepted-helper allocator module, selects "
        "one paper trade per signal date by fixed source priority, applies a "
        "12-trading-day same-ticker cooldown, then overlays next-open/10-day "
        "paper outcomes. No shared production/default-off helper changes are "
        "retained by this replay-only scout."
    )
    payload["gate2"]["runtime_fields"].append(
        "accepted supplier_financing_debt_relief replay rows with signal_date/ticker"
    )
    payload["expected_value_score_delta"] = payload["delta_metrics"]["aggregate"][
        "expected_value_score_delta_sum"
    ]
    payload["total_pnl_delta"] = payload["delta_metrics"]["aggregate"][
        "total_pnl_delta_sum"
    ]
    payload["calibration"] = {
        "predicted_success_probability": PREDICTION["success_probability"],
        "actual_gate4_passed": numeric_passed,
        "actual_retained_as_alpha": retained,
        "failure_modes_observed": gate4["failed_reasons"]
        or ["numeric_positive_but_requires_shared_promotion"],
        "brier_score": round(
            (PREDICTION["success_probability"] - (1.0 if numeric_passed else 0.0)) ** 2,
            6,
        ),
    }
    payload["full_stack_verdict"] = "reject"
    if isinstance(payload.get("full_stack"), dict) and isinstance(
        payload["full_stack"].get("verdict"),
        dict,
    ):
        payload["full_stack"]["verdict"].update(
            {
                "verdict": "reject",
                "gate4_passed": numeric_passed,
                "next_step": (
                    "Promote through a shared allocator/daily parity change before "
                    "retaining alpha."
                    if numeric_passed
                    else "Log the failure and avoid near-neighbor retunes."
                ),
            }
        )
    payload["interpretation"] = (
        "Supplier-financing/debt-relief rank-3 source is numerically positive "
        "but not retained because this run did not promote shared allocator/"
        "daily parity."
        if numeric_passed
        else (
            "Supplier-financing/debt-relief rank-3 source failed the accepted "
            "allocator comparator."
        )
    )
    payload["rejection_reason"] = (
        "numeric_positive_requires_shared_allocator_daily_parity_promotion"
        if numeric_passed
        else "; ".join(gate4["failed_reasons"])
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The supplier financing and deleveraging rows added enough allocator "
            "replacement value numerically, but retaining it would require a "
            "shared allocator source plus daily snapshot parity."
            if numeric_passed
            else (
                "The supplier financing and deleveraging rows did not add enough "
                "incremental replacement value after lagged consensus and "
                "volatility relief. The source likely overlaps broad momentum/"
                "quality rows or displaces better lower-rank allocator candidates."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by changing supplier source rank, DPO extension, debt "
            "relief, ADV, volatility target, allocator top-N, notional, hold days, "
            "or cooldown on the same frozen windows."
        ),
        "new_evidence_required": (
            "Retry only with closed forward allocator displacement rows, supplier/"
            "payment-term provenance, covenant/refinancing context, or a materially "
            "different PIT free-data supply/catalyst source."
        ),
    }
    payload["next_retry_requires"] = [
        "closed forward allocator displacement rows",
        "supplier payment-term or covenant/refinancing provenance",
        "shared helper and parity tests before any positive result is retained",
        "no frozen-window supplier financing threshold or rank retune",
    ]
    payload["accepted_comparators"] = {
        "accepted_allocator": ACCEPTED_ALLOCATOR_COMPARATOR,
        "accepted_supplier_financing_standalone": ACCEPTED_SUPPLIER_COMPARATOR,
        "included_source_priority": allocator_helper.SOURCE_PRIORITY,
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
        "| Window | Before EV | After EV | dEV | Accepted dEV | Before PnL | After PnL | dPnL | Accepted dPnL | DD d | Trades | Supplier selected |",
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
                selected=row["selected_source_counts"].get(SOURCE_FAMILY, 0),
            )
        )
    return rows


def _build_card(payload: dict[str, Any]) -> str:
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Supplier Financing Allocator Source",
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
    retained = False
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": retained,
        "accepted_alpha": retained,
        "production_accepted": retained,
        "numeric_gate4_passed": payload["gate4"]["passed"],
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
                "supplier_financing_selected_count": payload["window_rows"][label][
                    "selected_source_counts"
                ].get(SOURCE_FAMILY, 0),
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
            "causal_components": [
                "accepted_supplier_financing_artifact_source_rows",
                "rank3_source_priority_allocator_overlay",
                "Gate1-4_three_window_comparator",
                "no_live_order_change",
            ],
            "result": {
                "decision": payload["decision"],
                "artifact": _repo_rel(OUT_JSON),
                "log": _repo_rel(LOG_JSON),
                "aggregate_expected_value_delta": payload["expected_value_score_delta"],
                "aggregate_strategy_total_pnl_delta": payload["total_pnl_delta"],
                "accepted": False,
                "numeric_gate4_passed": payload["gate4"]["passed"],
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
        "accepted": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
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
