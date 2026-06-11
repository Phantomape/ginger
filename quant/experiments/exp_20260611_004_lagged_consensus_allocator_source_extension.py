"""exp-20260611-004: lagged consensus allocator source-extension scout.

Replay-only alpha search. This tests one fixed candidate-pool/allocation
hypothesis: the accepted lagged cross-source consensus helper may add distinct
multi-source confirmation replacement value when exposed as a rank-1 source
family inside the accepted helper source-priority allocator.

No production code, shared adapter, live/default orders, ranking, sizing,
exits, LLM/news path, or watchlist behavior is changed. A positive result is
only a replay lead until the allocator helper and daily snapshot surface are
updated and parity-tested. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, OrderedDict
from copy import deepcopy
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (QUANT_DIR, EXPERIMENTS_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260610_009_fiftytwo_allocator_source_extension as allocator_base  # noqa: E402


framework = allocator_base.framework

EXPERIMENT_ID = "exp-20260611-004"
STEM = "lagged_consensus_allocator_source_extension"
TRIAL_FAMILY = "accepted_default_off_helper_source_priority_allocation"
TRIAL_VARIANT_ID = (
    "lagged_cross_source_consensus_source_family_added_to_accepted_helper_"
    "source_priority_allocator_v1"
)
CHANGED_VARIABLE = TRIAL_VARIANT_ID
RULE_VERSION = "lagged_consensus_allocator_source_extension_replay_v1"
SOURCE_RULE_VERSION = "accepted_helper_source_priority_top1_with_lagged_consensus_replay_v1"
OWNER = "alpha-search-automation"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260611_004_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
CONSENSUS_SOURCE_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260604-008"
    / "lagged_independent_source_consensus.json"
)

CURRENT_ALLOCATOR_COMPARATOR = {
    "experiment_id": "exp-20260610-014",
    "aggregate_ev_delta": 0.9720,
    "aggregate_pnl_delta": 15197.05,
    "window_deltas": {
        "late_strong": {"ev": 0.5079, "pnl": 4879.33},
        "mid_weak": {"ev": 0.3356, "pnl": 6103.41},
        "old_thin": {"ev": 0.1285, "pnl": 4214.31},
    },
}

ACCEPTED_LAGGED_CONSENSUS_COMPARATOR = {
    "experiment_id": "exp-20260604-009",
    "decision": "accepted_lagged_consensus_shared_default_off_adapter",
    "aggregate_ev_delta": 1.9949,
    "aggregate_pnl_delta": 35553.87,
    "target_trade_count": 64,
    "window_deltas": {
        "late_strong": {"ev": 1.0468, "pnl": 10700.53},
        "mid_weak": {"ev": 0.4887, "pnl": 9517.86},
        "old_thin": {"ev": 0.4594, "pnl": 15335.48},
    },
}

EXECUTION_ENVELOPE = allocator_base.ExecutionEnvelope(
    base_notional=allocator_base.BASE_NOTIONAL_USD,
    max_capital_pct=0.32,
    min_dollar_volume=None,
    slippage_bps=5.0,
    max_displacement=1,
    max_concurrent=8,
    order_semantics="next_open_paper_only",
    kill_switch_drawdown_pct=None,
    sleeve_drawdown_stop_pct=None,
    notes=(
        "Top-1/day accepted-helper allocator, fixed $4,000 paper notional, "
        "8 max active default-off paper positions, 10-trading-day hold, and "
        "12-trading-day same-ticker cooldown. Lagged consensus source rows keep "
        "the accepted prior-3-trading-day independent source-family confirmation "
        "semantics and their underlying helper liquidity gates. This experiment "
        "is not live-ready because the allocator still needs shared source "
        "wiring, daily parity, and a realized-ledger kill switch before any "
        "trade_enabled=true release."
    ),
)

SOURCE_PRIORITY: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
SOURCE_PRIORITY["lagged_cross_source_consensus"] = {
    "rank": 1,
    "description": "accepted lagged cross-source consensus",
    "accepted_experiment": "exp-20260604-009",
    "accepted_ev_delta_sum": ACCEPTED_LAGGED_CONSENSUS_COMPARATOR["aggregate_ev_delta"],
    "accepted_pnl_delta_sum": ACCEPTED_LAGGED_CONSENSUS_COMPARATOR["aggregate_pnl_delta"],
}
for source_name, source_meta in allocator_base.ACCEPTED_SOURCE_PRIORITY.items():
    meta = deepcopy(source_meta)
    meta["rank"] = int(meta["rank"]) + 1
    SOURCE_PRIORITY[source_name] = meta

PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "source_overlap_with_existing_allocator",
        "accepted_allocator_comparator_not_beaten",
        "window_regression",
        "consensus_duplicate_of_underlying_sources",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Lagged consensus is a strong accepted default-off adapter, but recent "
        "allocator source additions usually failed because they displaced better "
        "accepted rows. This tests distinct multi-source confirmation rather "
        "than a new noisy ticker feed."
    ),
    "recorded_at": "2026-06-11T02:10:06+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "private_replay_scout_no_shared_lagged_consensus_allocator_source",
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
    "uses_free_ohlcv_only": False,
    "uses_free_non_ohlcv": True,
    "live_realism_evaluated": True,
    "live_ready": False,
    "execution_envelope": EXECUTION_ENVELOPE.to_dict(),
    "parity_note": (
        "This experiment changes no production code. It reuses accepted lagged "
        "consensus replay rows and applies the accepted allocator overlay in "
        "replay only. A positive result cannot be promoted until the shared "
        "allocator helper, daily snapshots, ledger, and parity tests admit the "
        "same lagged consensus source semantics."
    ),
}

PRE_RUN_QUESTIONS = {
    "1_alpha_hypothesis": (
        "candidate_pool/allocation: accepted lagged cross-source consensus has "
        "the strongest standalone default-off evidence in the current free-data "
        "source set. Admitting it as fixed rank 1 may add multi-source "
        "confirmation replacement value on dates where single-source allocator "
        "rows are less robust."
    ),
    "2_history_check": {
        "exp-20260604-009": (
            "Accepted lagged consensus shared adapter: aggregate EV +1.9949, "
            "PnL +$35,553.87, and all three windows positive."
        ),
        "exp-20260610-014": (
            "Current accepted source-priority allocator with revision source: "
            "aggregate EV +0.9720 and PnL +$15,197.05. This is the binding "
            "comparator."
        ),
        "exp-20260610-016": (
            "Rejected post-earnings allocator extension; accepted standalone "
            "sources can fail after displacement."
        ),
        "exp-20260610-019": (
            "Rejected Fundamental Growth RS allocator extension; positive "
            "aggregate did not beat the current accepted allocator window "
            "comparator."
        ),
        "exp-20260611-003": (
            "Rejected VBB allocator extension; broad accepted source rows did "
            "not add enough incremental replacement value."
        ),
    },
    "3_single_causal_variable": (
        "One fixed policy bundle: accepted lagged cross-source consensus selected "
        "rows added as rank-1 source family inside the accepted helper "
        "source-priority allocator. Existing source rules, next-open entry, "
        "10-day hold, costs, top-1/day, notional, and cooldown remain fixed."
    ),
    "4_acceptance_standard": (
        "Use docs/backtesting.md three canonical windows. Accept only as a "
        "replay lead if aggregate EV/PnL improve, no EV/PnL regression window "
        "appears, target sample >=20 across all three windows, survival >=5%, "
        "drawdown drift <=0.5pp, concentration guard passes, and exp-20260610-014 "
        "accepted allocator aggregate plus per-window EV/PnL comparator is beaten."
    ),
    "5_reproducibility": (
        ".venv\\Scripts\\python.exe -B quant\\experiments\\"
        "exp_20260611_004_lagged_consensus_allocator_source_extension.py"
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


def _consensus_source_score(row: dict[str, Any]) -> float:
    family_count = int(row.get("source_family_count") or 0)
    source_count = int(row.get("source_count") or 0)
    lagged = 1.0 if row.get("has_lagged_independent_confirmation") else 0.0
    prior_families = int(row.get("prior_confirmation_family_count") or 0)
    return family_count * 100.0 + source_count * 10.0 + prior_families + lagged


def _build_lagged_consensus_source_trades(
    *,
    window_label: str,
    dates: list[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    payload = _load_json(CONSENSUS_SOURCE_JSON, {})
    target_by_window = payload.get("target_trades_by_window") or {}
    rows = target_by_window.get(window_label) or []
    date_set = set(dates)
    source_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        signal_date = str(row.get("signal_date") or row.get("date") or "")[:10]
        ticker = str(row.get("ticker") or "").upper()
        if signal_date not in date_set or not ticker:
            continue
        score = _consensus_source_score(row)
        normalised = allocator_base._normalise_source_row(
            {
                **deepcopy(row),
                "date": signal_date,
                "signal_date": signal_date,
                "ticker": ticker,
                "source_family": "lagged_cross_source_consensus",
                "source_score": score,
                "candidate_score": score,
                "paper_notional_usd": allocator_base.BASE_NOTIONAL_USD,
                "source_rule_version": SOURCE_RULE_VERSION,
                "consensus_source_experiment": "exp-20260604-009",
            },
            "lagged_cross_source_consensus",
        )
        normalised.update(
            {
                "uses_free_ohlcv_only": False,
                "uses_free_non_ohlcv": True,
                "source_rule_version": SOURCE_RULE_VERSION,
                "consensus_source_experiment": "exp-20260604-009",
                "consensus_source_artifact": _repo_rel(CONSENSUS_SOURCE_JSON),
            }
        )
        source_rows.append(normalised)

    return source_rows, {
        "rule_version": "accepted_free_data_cross_source_consensus_shared_v1",
        "source_rule_version": SOURCE_RULE_VERSION,
        "source_artifact": _repo_rel(CONSENSUS_SOURCE_JSON),
        "source_trade_count": len(source_rows),
        "raw_candidate_count": (
            (payload.get("target_summary") or {}).get("trades_by_window") or {}
        ).get(window_label, len(source_rows)),
        "unique_source_tickers": len({row["ticker"] for row in source_rows}),
        "selected_source_family_combos": dict(
            Counter("+".join(row.get("source_families") or []) for row in source_rows)
        ),
        "selected_source_name_combos": dict(
            Counter("+".join(row.get("source_names") or []) for row in source_rows)
        ),
        "daily_entry_slots": 1,
    }


def _build_extended_allocator_trades(
    *,
    rows_by_ticker: dict[str, list[dict[str, Any]]],
    dates: list[str],
    window_label: str,
    window: dict[str, str],
    core_entries_by_date: dict[str, list[dict[str, Any]]],
    sector_entries: dict[str, dict[str, Any]],
    candidate_universe: dict[str, Any],
    calendar_dates: list[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_trades, source_audit = allocator_base.build_accepted_allocator_source_trades(
        rows_by_ticker=rows_by_ticker,
        dates=dates,
        window_label=window_label,
        window=window,
        core_entries_by_date=core_entries_by_date,
        sector_entries=sector_entries,
        candidate_universe=candidate_universe,
        calendar_dates=calendar_dates,
    )
    consensus_rows, consensus_audit = _build_lagged_consensus_source_trades(
        window_label=window_label,
        dates=dates,
    )
    source_trades.extend(consensus_rows)
    selected, filtered, priority_audit = allocator_base._select_priority_trades(
        source_trades=source_trades,
        trading_dates=dates,
    )

    source_trade_counts = dict(source_audit["source_trade_counts"])
    raw_candidate_counts = dict(source_audit["raw_candidate_counts"])
    source_audits = dict(source_audit["source_audits"])
    source_trade_counts["lagged_cross_source_consensus"] = len(consensus_rows)
    raw_candidate_counts["lagged_cross_source_consensus"] = consensus_audit[
        "raw_candidate_count"
    ]
    source_audits["lagged_cross_source_consensus"] = consensus_audit
    return selected, {
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "source_priority": SOURCE_PRIORITY,
        "selected_by_window": {window_label: len(selected)},
        "selected_source_counts_by_window": {
            window_label: priority_audit["selected_source_counts"]
        },
        "source_trade_counts_by_window": {window_label: source_trade_counts},
        "raw_candidate_counts_by_window": {window_label: raw_candidate_counts},
        "filtered_count_by_window": {window_label: len(filtered)},
        "source_audits_by_window": {window_label: source_audits},
        "priority_audit_by_window": {window_label: priority_audit},
        "total_selected": len(selected),
    }


ORIGINAL_BINDING_GATE4 = allocator_base._binding_gate4
ORIGINAL_BUILD_PAYLOAD = allocator_base.build_payload


def _binding_gate4(*args: Any, **kwargs: Any) -> dict[str, Any]:
    gate = ORIGINAL_BINDING_GATE4(*args, **kwargs)
    gate["decision"] = (
        "positive_replay_lead_not_promoted_lagged_consensus_allocator_source_extension"
        if gate["passed"]
        else "rejected_lagged_consensus_allocator_source_extension"
    )
    return gate


def _prepare_base() -> None:
    allocator_base.__file__ = str(Path(__file__))
    allocator_base.EXPERIMENT_ID = EXPERIMENT_ID
    allocator_base.STEM = STEM
    allocator_base.TRIAL_FAMILY = TRIAL_FAMILY
    allocator_base.TRIAL_VARIANT_ID = TRIAL_VARIANT_ID
    allocator_base.CHANGED_VARIABLE = CHANGED_VARIABLE
    allocator_base.RULE_VERSION = RULE_VERSION
    allocator_base.SOURCE_RULE_VERSION = SOURCE_RULE_VERSION
    allocator_base.OWNER = OWNER
    allocator_base.OUT_DIR = OUT_DIR
    allocator_base.OUT_JSON = OUT_JSON
    allocator_base.LOG_JSON = LOG_JSON
    allocator_base.TICKET_JSON = TICKET_JSON
    allocator_base.CARD_MD = CARD_MD
    allocator_base.MANIFEST_JSON = MANIFEST_JSON
    allocator_base.EXPERIMENT_LOG = EXPERIMENT_LOG
    allocator_base.REGISTRY_JSON = REGISTRY_JSON
    allocator_base.SOURCE_PRIORITY = SOURCE_PRIORITY
    allocator_base.ACCEPTED_ALLOCATOR_COMPARATOR = CURRENT_ALLOCATOR_COMPARATOR
    allocator_base.PREDICTION = PREDICTION
    allocator_base.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    allocator_base.PRE_RUN_QUESTIONS = PRE_RUN_QUESTIONS
    allocator_base.EXECUTION_ENVELOPE = EXECUTION_ENVELOPE
    allocator_base._build_extended_allocator_trades = _build_extended_allocator_trades
    allocator_base._binding_gate4 = _binding_gate4


def _postprocess_payload(payload: dict[str, Any]) -> dict[str, Any]:
    accepted = bool(payload["gate4"]["passed"])
    if accepted:
        prior_verdict = payload.get("full_stack_verdict")
        verdict_payload = (
            dict(prior_verdict)
            if isinstance(prior_verdict, dict)
            else {"prior_verdict": prior_verdict}
        )
        payload["full_stack_verdict"] = {
            **verdict_payload,
            "verdict": "replay_lead_not_promoted",
            "gate4_passed": True,
            "live_ready": False,
            "next_step": (
                "Promote in a separate shared allocator experiment before any "
                "accepted alpha or daily production observation claim."
            ),
        }
    payload.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "positive_replay_lead_not_promoted" if accepted else "rejected",
            "decision": payload["gate4"]["decision"],
            "hypothesis": PRE_RUN_QUESTIONS["1_alpha_hypothesis"],
            "change_type": "default_off_paper_candidate_pool_replay_scout",
            "changed_variable": CHANGED_VARIABLE,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "mechanism_family": (
                "production_visible_default_off_paper_adapter_for_candidate_pool_alpha"
            ),
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "accepted_lagged_consensus_source_family_added_to_allocator_replay",
            "nearby_prior_experiments": [
                "exp-20260604-009",
                "exp-20260610-014",
                "exp-20260610-016",
                "exp-20260610-019",
                "exp-20260611-003",
            ],
            "prior_trial_count": 5,
            "prediction": PREDICTION,
            "production_impact": PRODUCTION_IMPACT,
            "pre_run_questions": PRE_RUN_QUESTIONS,
            "anti_js": "No JavaScript was used.",
        }
    )
    payload["parameters"] = {
        **payload.get("parameters", {}),
        "rule_version": RULE_VERSION,
        "source_rule_version": SOURCE_RULE_VERSION,
        "source_priority": SOURCE_PRIORITY,
        "accepted_lagged_consensus_comparator": ACCEPTED_LAGGED_CONSENSUS_COMPARATOR,
        "current_accepted_allocator_comparator": CURRENT_ALLOCATOR_COMPARATOR,
        "single_causal_variable": CHANGED_VARIABLE,
    }
    payload["backtest_protocol"]["execution_model"] = (
        "Replay reconstructs accepted source-priority rows plus accepted lagged "
        "cross-source consensus selected source rows from exp-20260604-009, "
        "then selects one paper trade per signal date by fixed source priority "
        "and applies the accepted allocator 12-trading-day same-ticker cooldown."
    )
    payload["gate2"]["runtime_fields"] = [
        "operator_inputs/open_positions.json entry_date",
        "operator_inputs/open_positions.json target_price",
        "warehouse OHLCV Date/Open/High/Low/Close/Volume",
        "accepted lagged consensus target rows with signal_date/ticker/source families",
        "accepted allocator source rows with signal_date/ticker/source_family",
    ]
    for label, row in payload["window_rows"].items():
        source_counts = row.get("source_trade_counts") or {}
        selected_counts = row.get("selected_source_counts") or {}
        row["lagged_cross_source_consensus_source_trade_count"] = source_counts.get(
            "lagged_cross_source_consensus",
            0,
        )
        row["lagged_cross_source_consensus_selected_count"] = selected_counts.get(
            "lagged_cross_source_consensus",
            0,
        )
    payload["accepted_comparators"] = {
        "current_accepted_allocator": CURRENT_ALLOCATOR_COMPARATOR,
        "accepted_lagged_consensus_standalone": ACCEPTED_LAGGED_CONSENSUS_COMPARATOR,
        "included_source_priority": SOURCE_PRIORITY,
    }
    payload["interpretation"] = (
        "The lagged consensus source-family extension beat the current accepted "
        "allocator comparator as a replay-only lead; shared allocator wiring "
        "and daily parity are required before use."
        if accepted
        else (
            "The lagged consensus source-family extension failed to beat the "
            "current accepted allocator comparator."
        )
    )
    payload["post_run_reflection"] = {
        "why_result_happened": (
            "The lagged consensus source added enough multi-source confirmation "
            "rows to beat accepted allocator displacement costs across the "
            "canonical windows. It remains replay-only because shared allocator "
            "wiring was not changed."
            if accepted
            else (
                "The lagged consensus rows likely duplicated the strongest "
                "underlying accepted sources or displaced better higher-priority "
                "allocator rows. Standalone consensus strength did not translate "
                "into incremental top-1/day allocator replacement value."
            )
        ),
        "forbidden_near_neighbor_retry": (
            "Do not retry by changing consensus source rank, source-family map, "
            "prior confirmation window, allocator top-N, notional, hold days, "
            "or cooldown on the same frozen windows."
        ),
        "new_evidence_required": (
            "A retry needs closed forward allocator displacement rows, a truly "
            "new consensus interaction field, or shared-daily replacement-value "
            "evidence."
        ),
    }
    payload["next_retry_requires"] = [
        "closed forward allocator displacement rows",
        "shared allocator daily parity if positive",
        "no frozen-window consensus timing or rank retune",
    ]
    payload["related_files"] = [
        _repo_rel(Path(__file__)),
        _repo_rel(CONSENSUS_SOURCE_JSON),
        _repo_rel(OUT_JSON),
        _repo_rel(LOG_JSON),
        _repo_rel(TICKET_JSON),
        _repo_rel(CARD_MD),
        _repo_rel(MANIFEST_JSON),
        _repo_rel(EXPERIMENT_LOG),
        _repo_rel(REGISTRY_JSON),
    ]
    return payload


def build_payload() -> dict[str, Any]:
    _prepare_base()
    return _postprocess_payload(ORIGINAL_BUILD_PAYLOAD())


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["delta_metrics"]["aggregate"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": "alpha_search",
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": payload["gate4"]["passed"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "backtest_protocol": payload["backtest_protocol"],
        "baseline_result_file": _repo_rel(
            REPO_ROOT
            / "data"
            / "experiments"
            / "exp-20260610-014"
            / "exp_20260610_014_revision_source_priority_allocator_extension.json"
        ),
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_expected_value_delta_pct": aggregate[
            "expected_value_score_delta_pct"
        ],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
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
                "strategy_total_pnl_delta": payload["delta_metrics"]["by_window"][
                    label
                ]["total_pnl"],
                "target_trade_count": len(payload["target_trades_by_window"][label]),
                "lagged_cross_source_consensus_source_trade_count": payload[
                    "window_rows"
                ][label].get("lagged_cross_source_consensus_source_trade_count", 0),
                "lagged_cross_source_consensus_selected_count": payload["window_rows"][
                    label
                ].get("lagged_cross_source_consensus_selected_count", 0),
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


def _build_card(payload: dict[str, Any]) -> str:
    rows = [
        "| Window | Before EV | After EV | dEV | Current allocator dEV | Before PnL | After PnL | dPnL | Current allocator dPnL | DD d | Trades | Consensus selected |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    comparator = CURRENT_ALLOCATOR_COMPARATOR
    for label in framework.WINDOWS:
        before = payload["before_metrics"][label]
        after = payload["after_metrics"][label]
        delta = payload["delta_metrics"]["by_window"][label]
        row = payload["window_rows"][label]
        rows.append(
            "| {label} | {bev:.4f} | {aev:.4f} | {dev:+.4f} | {cev:+.4f} | ${bpnl:,.2f} | ${apnl:,.2f} | ${dpnl:+,.2f} | ${cpnl:+,.2f} | {dd:+.4f} | {trades} | {consensus_selected} |".format(
                label=label,
                bev=before["expected_value_score"],
                aev=after["expected_value_score"],
                dev=delta.get("expected_value_score", 0.0),
                cev=comparator["window_deltas"][label]["ev"],
                bpnl=before["total_pnl"],
                apnl=after["total_pnl"],
                dpnl=delta.get("total_pnl", 0.0),
                cpnl=comparator["window_deltas"][label]["pnl"],
                dd=delta.get("max_drawdown_pct", 0.0),
                trades=len(payload["target_trades_by_window"][label]),
                consensus_selected=row.get(
                    "lagged_cross_source_consensus_selected_count",
                    0,
                ),
            )
        )
    aggregate = payload["delta_metrics"]["aggregate"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Lagged Consensus Allocator Source Extension",
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
            "- Aggregate EV delta: `{:+.4f}` vs current allocator `{:+.4f}`".format(
                aggregate["expected_value_score_delta_sum"],
                comparator["aggregate_ev_delta"],
            ),
            "- Aggregate PnL delta: `${:+,.2f}` vs current allocator `${:+,.2f}`".format(
                aggregate["total_pnl_delta_sum"],
                comparator["aggregate_pnl_delta"],
            ),
            "- Target trades: `{}`".format(
                payload["target_trade_summary"]["total_trade_count"]
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


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON, {})
    aggregate = payload["delta_metrics"]["aggregate"]
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
                "aggregate_expected_value_delta": aggregate[
                    "expected_value_score_delta_sum"
                ],
                "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
                "accepted": False,
                "numeric_gate4_passed": payload["gate4"]["passed"],
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
    aggregate = payload["delta_metrics"]["aggregate"]
    result = {
        "decision": payload["decision"],
        "full_stack_verdict": payload["full_stack_verdict"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
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
        "aggregate_expected_value_delta": aggregate["expected_value_score_delta_sum"],
        "aggregate_strategy_total_pnl_delta": aggregate["total_pnl_delta_sum"],
        "completed_at": payload["timestamp"],
    }
    allocator_base.persist_self_registered_result(
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
