"""exp-20260612-013: distribution absorption as lagged consensus source.

Replay-only alpha search. Tests one causal variable: add the accepted
distribution-day absorption leadership paper rows as a new independent source
family inside the accepted lagged free-data consensus scout.

No production code, live orders, ranking, sizing, exits, LLM, or news behavior
is changed. No JavaScript is used.
"""

from __future__ import annotations

import copy
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = REPO_ROOT / "quant" / "experiments"
QUANT_DIR = REPO_ROOT / "quant"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for import_path in (REPO_ROOT, EXPERIMENTS_DIR, QUANT_DIR, SCRIPTS_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260603_014_accepted_consensus_independent_source_family as same_day  # noqa: E402
import exp_20260604_008_lagged_independent_source_consensus as lagged  # noqa: E402
import exp_20260608_026_industry_laggard_lagged_consensus_source as template  # noqa: E402
import distribution_day_absorption_leadership_paper_sleeve as distribution  # noqa: E402
from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260612-013"
STEM = "distribution_absorption_lagged_consensus_source"
TRIAL_FAMILY = "accepted_free_data_cross_source_consensus_new_independent_source_family"
TRIAL_VARIANT_ID = "distribution_day_absorption_lagged_consensus_source_family_v1"
CHANGED_VARIABLE = "distribution_day_absorption_source_family_added_to_accepted_lagged_consensus_v1"
RULE_VERSION = "distribution_day_absorption_lagged_consensus_source_family_v1"

DISTRIBUTION_SOURCE_NAME = distribution.SLEEVE_NAME
DISTRIBUTION_SOURCE_FAMILY = "distribution_day_absorption"
DISTRIBUTION_SOURCE_EXPERIMENT_ID = "exp-20260611-007"
DISTRIBUTION_REPLAY_LEAD_ID = "exp-20260611-006"
DISTRIBUTION_SHARED_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / DISTRIBUTION_SOURCE_EXPERIMENT_ID
    / "exp_20260611_007_distribution_day_absorption_shared_adapter.json"
)
DISTRIBUTION_REPLAY_LEAD_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / DISTRIBUTION_REPLAY_LEAD_ID
    / "exp_20260611_006_distribution_day_absorption_leadership.json"
)

ACCEPTED_LAGGED_ADAPTER_ID = "exp-20260604-009"
ACCEPTED_LAGGED_ADAPTER_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / ACCEPTED_LAGGED_ADAPTER_ID
    / "exp_20260604_009_lagged_consensus_shared_adapter.json"
)

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260612_013_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

PREDICTION = {
    "success_probability": 0.28,
    "expected_ev_delta": 0.08,
    "expected_pnl_delta": 1500.0,
    "main_failure_modes": [
        "accepted_lagged_comparator_not_beaten",
        "distribution_rows_redundant_with_existing_sources",
        "window_regression",
        "source_rows_selected_only_as_prior_confirmation",
    ],
    "confidence_reason": (
        "Standalone distribution-day absorption cleared Gate 4, but allocator "
        "insertion already failed an incremental comparator. Lagged consensus "
        "may still improve if distribution pressure absorption acts as "
        "confirmation rather than displacement."
    ),
    "recorded_at": "2026-06-12T09:10:49+00:00",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_consensus_adapter_change",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "default_off_paper_only": True,
    "daily_snapshot_exposed": False,
    "parity_test_added": False,
    "production_watchlist_changed": False,
    "production_orders_changed": False,
    "production_signal_path_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "uses_llm": False,
    "uses_free_ohlcv_only": True,
    "parity_note": (
        "This runner changes no production code. A positive result would still "
        "require the shared free-data consensus adapter to load the accepted "
        "distribution-day absorption paper snapshot as the same source family "
        "in both historical replay and daily default-off production snapshots, "
        "with parity tests before any paper queue, report, priority, notional, "
        "watchlist, or order surface could change."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _repo_rel(path: Path | str) -> str:
    try:
        return Path(path).resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path).replace("\\", "/")


def _load_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any, *, ensure_ascii: bool = True, sort_keys: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=ensure_ascii, indent=2, sort_keys=sort_keys)
        handle.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _upsert_jsonl(path: Path, row: dict[str, Any]) -> None:
    line = json.dumps(row, ensure_ascii=True, sort_keys=True)
    rows: list[str] = []
    if path.exists():
        for existing in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not existing.strip():
                continue
            try:
                payload = json.loads(existing)
            except json.JSONDecodeError:
                rows.append(existing)
                continue
            if payload.get("experiment_id") == EXPERIMENT_ID:
                continue
            rows.append(existing)
    rows.append(line)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _patch_source_family_context() -> None:
    lagged._configure_same_day_modules()
    same_day.SOURCE_FAMILIES[DISTRIBUTION_SOURCE_NAME] = DISTRIBUTION_SOURCE_FAMILY
    same_day.SOURCE_EXPERIMENT_IDS[DISTRIBUTION_SOURCE_NAME] = DISTRIBUTION_SOURCE_EXPERIMENT_ID


def _source_row_from_distribution_trade(
    trade: dict[str, Any],
    *,
    label: str,
) -> dict[str, Any] | None:
    signal_date = str(trade.get("signal_date") or trade.get("date") or "")[:10]
    ticker = str(trade.get("ticker") or "").upper()
    if not signal_date or not ticker:
        return None

    pressure = trade.get("pressure_context") if isinstance(trade.get("pressure_context"), dict) else {}
    return {
        "source_name": DISTRIBUTION_SOURCE_NAME,
        "source_experiment_id": DISTRIBUTION_SOURCE_EXPERIMENT_ID,
        "source_family": DISTRIBUTION_SOURCE_FAMILY,
        "date": signal_date,
        "signal_date": signal_date,
        "ticker": ticker,
        "window_label": label,
        "entry_date": trade.get("entry_date"),
        "paper_pnl": trade.get("paper_pnl", trade.get("pnl")),
        "pnl_usd": trade.get("pnl"),
        "return_pct": trade.get("pnl_pct_net"),
        "paper_notional_usd": trade.get("paper_notional_usd"),
        "candidate_score": trade.get("candidate_score"),
        "candidate_signal_day_return": trade.get("candidate_signal_day_return"),
        "candidate_relative_vs_spy": trade.get("candidate_relative_vs_spy"),
        "candidate_relative_vs_qqq": trade.get("candidate_relative_vs_qqq"),
        "candidate_ret5": trade.get("candidate_ret5"),
        "candidate_ret20": trade.get("candidate_ret20"),
        "candidate_ret20_excess_spy": trade.get("candidate_ret20_excess_spy"),
        "candidate_ret60_excess_spy": trade.get("candidate_ret60_excess_spy"),
        "candidate_close_location": trade.get("candidate_close_location"),
        "candidate_volume_ratio_20d": trade.get("candidate_volume_ratio_20d"),
        "candidate_reclaim_vs_10d_high": trade.get("candidate_reclaim_vs_10d_high"),
        "candidate_realized_vol_20d": trade.get("candidate_realized_vol_20d"),
        "candidate_avg_dollar_volume_20d": trade.get("candidate_avg_dollar_volume_20d"),
        "sector": trade.get("sector"),
        "industry": trade.get("industry"),
        "combined_distribution_event_count": pressure.get("combined_distribution_event_count"),
        "spy_distribution_event_count": pressure.get("spy_distribution_event_count"),
        "qqq_distribution_event_count": pressure.get("qqq_distribution_event_count"),
        "spy_signal_day_return": pressure.get("spy_signal_day_return"),
        "qqq_signal_day_return": pressure.get("qqq_signal_day_return"),
        "spy_ret5": pressure.get("spy_ret5"),
        "qqq_ret5": pressure.get("qqq_ret5"),
        "same_day_ab_entry_count": trade.get("same_day_ab_entry_count"),
        "same_day_ab_overlap": trade.get("same_day_ab_overlap"),
        "same_ticker_ab_overlap": trade.get("same_ticker_ab_overlap"),
        "uses_free_ohlcv_only": trade.get("uses_free_ohlcv_only", True),
        "uses_llm": trade.get("uses_llm", False),
        "helper_rule_version": distribution.RULE_VERSION,
        "helper_source_rule_version": distribution.SOURCE_RULE_VERSION,
        "source_artifact": _repo_rel(DISTRIBUTION_SHARED_ARTIFACT),
        "historical_replay_experiment_id": DISTRIBUTION_REPLAY_LEAD_ID,
        "historical_replay_artifact": _repo_rel(DISTRIBUTION_REPLAY_LEAD_ARTIFACT),
        "rule_version": RULE_VERSION,
        "trade_enabled": False,
        "alters_orders": False,
        "known_at": "after_signal_day_close_before_next_open_paper_entry",
    }


def _distribution_source_rows_by_window() -> tuple[
    dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
    dict[str, Any],
]:
    payload = _load_json(DISTRIBUTION_SHARED_ARTIFACT, {})
    rows_by_window = payload.get("target_trades_by_window") or {}
    out: dict[str, dict[tuple[str, str], list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    diagnostics: dict[str, Any] = {
        "source_path": _repo_rel(DISTRIBUTION_SHARED_ARTIFACT),
        "source_name": DISTRIBUTION_SOURCE_NAME,
        "source_family": DISTRIBUTION_SOURCE_FAMILY,
        "source_experiment_id": DISTRIBUTION_SOURCE_EXPERIMENT_ID,
        "historical_replay_experiment_id": DISTRIBUTION_REPLAY_LEAD_ID,
        "helper_rule_version": distribution.RULE_VERSION,
        "helper_source_rule_version": distribution.SOURCE_RULE_VERSION,
        "selected_trade_count_by_window": {},
        "source_row_count_by_window": {},
        "unique_ticker_count_by_window": {},
        "source_key_count_by_window": {},
        "standalone_gate4": payload.get("gate4", {}),
    }
    for label in same_day.prior.base.WINDOWS:
        trades = [row for row in rows_by_window.get(label, []) if isinstance(row, dict)]
        tickers: set[str] = set()
        for trade in trades:
            source_row = _source_row_from_distribution_trade(trade, label=label)
            if source_row is None:
                continue
            key = (source_row["signal_date"], source_row["ticker"])
            out[label][key].append(source_row)
            tickers.add(source_row["ticker"])
        diagnostics["selected_trade_count_by_window"][label] = len(trades)
        diagnostics["source_row_count_by_window"][label] = sum(len(rows) for rows in out[label].values())
        diagnostics["unique_ticker_count_by_window"][label] = len(tickers)
        diagnostics["source_key_count_by_window"][label] = len(out[label])
    return out, diagnostics


def _source_addition_summary(
    target_trades_by_window: dict[str, list[dict[str, Any]]],
    added_source_rows: dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
) -> dict[str, Any]:
    all_selected = [row for rows in target_trades_by_window.values() for row in rows]
    selected_with_distribution = [
        row for row in all_selected if DISTRIBUTION_SOURCE_NAME in (row.get("source_names") or [])
    ]
    current_distribution = [
        row
        for row in selected_with_distribution
        if DISTRIBUTION_SOURCE_NAME in (row.get("current_source_names") or [])
    ]
    prior_distribution = [
        row
        for row in selected_with_distribution
        if any(
            source_row.get("source_name") == DISTRIBUTION_SOURCE_NAME
            and source_row.get("timing_role") == "prior_confirmation"
            for source_row in row.get("source_rows") or []
        )
    ]
    added_key_counts = {
        label: sum(len(rows) for rows in by_key.values())
        for label, by_key in added_source_rows.items()
    }
    return {
        "added_source_name": DISTRIBUTION_SOURCE_NAME,
        "added_source_family": DISTRIBUTION_SOURCE_FAMILY,
        "added_source_rows_by_window": dict(sorted(added_key_counts.items())),
        "selected_trade_count": len(all_selected),
        "selected_with_distribution_source_count": len(selected_with_distribution),
        "selected_with_current_distribution_count": len(current_distribution),
        "selected_with_prior_distribution_count": len(prior_distribution),
        "selected_with_distribution_pnl_usd": round(
            sum(_safe_float(row.get("pnl")) for row in selected_with_distribution),
            2,
        ),
        "source_combo_counts_selected": dict(
            sorted(Counter("+".join(row.get("source_names") or []) for row in all_selected).items())
        ),
        "family_combo_counts_selected": dict(
            sorted(Counter("+".join(row.get("source_families") or []) for row in all_selected).items())
        ),
    }


def _gate4(
    aggregate_vs_core: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
    vs_lagged: dict[str, Any],
    source_summary: dict[str, Any],
) -> dict[str, Any]:
    base_gate = same_day.prior._gate4_decision(aggregate_vs_core, results, target_summary)
    comp = vs_lagged["comparison"]
    comparator_passed = (
        comp["expected_value_score_delta"] > 0.0
        and comp["strategy_total_pnl_delta"] > 0.0
        and comp["windows_ev_improved"] == 3
        and comp["windows_pnl_improved"] == 3
    )
    source_selected = int(source_summary["selected_with_distribution_source_count"]) > 0
    gates = {
        **base_gate["gates"],
        "beats_current_accepted_lagged_consensus_comparator": comparator_passed,
        "new_source_selected_trade_count_positive": source_selected,
    }
    passed = bool(base_gate["passed"] and comparator_passed and source_selected)
    if passed:
        decision = "positive_replay_lead_requires_distribution_lagged_consensus_shared_adapter"
        rationale = (
            "Adding distribution-day absorption as an independent source family "
            "improved both core and current accepted lagged consensus across all "
            "three windows. Promotion would require shared adapter wiring and "
            "parity tests first."
        )
    elif not source_selected:
        decision = "rejected_distribution_lagged_consensus_no_selected_source_rows"
        rationale = "The distribution-day absorption source produced no selected lagged-consensus trades."
    elif not comparator_passed:
        decision = "rejected_distribution_lagged_consensus_did_not_beat_accepted_lagged_comparator"
        rationale = (
            "The variant did not beat the current accepted lagged consensus "
            "comparator across all three canonical windows."
        )
    else:
        decision = "rejected_distribution_lagged_consensus_gate4_failed"
        rationale = base_gate["rationale"]
    return {
        "passed": passed,
        "decision": decision,
        "gates": gates,
        "rationale": rationale,
        "min_survival_rate": base_gate.get("min_survival_rate"),
        "max_drawdown_delta": base_gate.get("max_drawdown_delta"),
        "requires_parity_before_promotion": True,
        "accepted_comparator": ACCEPTED_LAGGED_ADAPTER_ID,
    }


def _aggregate_after(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "expected_value_score": round(
            sum(_safe_float(row["after"].get("expected_value_score")) for row in results),
            6,
        ),
        "strategy_total_pnl": round(
            sum(_safe_float(row["after"].get("total_pnl")) for row in results),
            2,
        ),
    }


def _window_comparison(
    results: list[dict[str, Any]],
    accepted_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    accepted_by_label = {row["label"]: row for row in accepted_results}
    rows = []
    for row in results:
        accepted = accepted_by_label[row["label"]]
        accepted_delta = same_day.prior.base.overlay_helper._delta(row["after"], accepted["after"])
        rows.append(
            {
                "label": row["label"],
                "expected_value_before_lagged": accepted["after"]["expected_value_score"],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta_vs_lagged": accepted_delta["expected_value_score"],
                "strategy_total_pnl_before_lagged": accepted["after"]["total_pnl"],
                "strategy_total_pnl_after": row["after"]["total_pnl"],
                "strategy_total_pnl_delta_vs_lagged": accepted_delta["total_pnl"],
                "expected_value_delta_vs_core": row["comparison"]["expected_value_score_delta"],
                "strategy_total_pnl_delta_vs_core": row["comparison"]["strategy_total_pnl_delta"],
                "target_trade_count": row["target_trade_count"],
                "raw_lagged_consensus_candidate_count": row["raw_lagged_consensus_candidate_count"],
                "lagged_independent_candidate_count": row["lagged_independent_candidate_count"],
            }
        )
    return rows


def _preflight_payload() -> dict[str, Any]:
    return {
        "alpha_hypothesis": (
            "Accepted distribution-day absorption paper rows may improve the "
            "accepted lagged free-data consensus scout when treated as a new "
            "independent production-visible source family rather than an "
            "allocator rank source."
        ),
        "category": "entry/candidate_pool",
        "playbook_alignment": (
            "Uses a production-visible, default-off, free OHLCV helper with "
            "accepted three-window evidence. It avoids LLM soft-ranking data "
            "limits, SEC text retunes, noisy ticker expansion, and local "
            "allocator threshold sweeps."
        ),
        "nearby_prior_experiments": [
            "exp-20260611-007",
            "exp-20260611-008",
            "exp-20260604-008",
            "exp-20260604-009",
            "exp-20260608-026",
        ],
        "history_check": {
            "exp-20260611-007": (
                "Accepted shared distribution-day absorption adapter: aggregate "
                "EV +0.5286, PnL +$10,432.91, 113 trades, all windows positive."
            ),
            "exp-20260611-008": (
                "Distribution absorption allocator rank-3 insertion was rejected "
                "because it did not beat the accepted allocator in all windows."
            ),
            "exp-20260604-008/009": (
                "Accepted lagged independent-source consensus timing and shared "
                "adapter; this is the comparator to beat."
            ),
            "exp-20260608-026": (
                "Industry laggard-repair as lagged-consensus source was rejected "
                "because it did not beat the accepted lagged comparator."
            ),
        },
        "not_a_near_neighbor_retry": (
            "This tests source-family confirmation inside lagged consensus, not "
            "distribution thresholds, allocator rank, top-N, notional, hold, or "
            "cooldown."
        ),
        "single_causal_variable": CHANGED_VARIABLE,
        "acceptance_criteria": {
            "canonical_windows": list(same_day.prior.base.WINDOWS.keys()),
            "aggregate_expected_value_delta_vs_core": "> 0",
            "aggregate_pnl_delta_vs_core": "> 0",
            "must_beat_current_accepted_lagged_consensus_comparator": True,
            "per_window_delta_vs_accepted_lagged_comparator": "3 of 3 windows > 0",
            "minimum_target_trades": same_day.prior.MIN_TARGET_TRADES,
            "minimum_target_windows": same_day.prior.MIN_TARGET_WINDOWS,
            "max_drawdown_drift": same_day.prior.MAX_DRAWDOWN_WORSE,
            "survival_rate_floor": 0.05,
            "max_single_positive_share": same_day.prior.MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi_max": same_day.prior.MAX_POSITIVE_HHI,
        },
        "reproducibility": (
            ".venv\\Scripts\\python.exe -B "
            "quant\\experiments\\exp_20260612_013_distribution_absorption_lagged_consensus_source.py"
        ),
    }


def _log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate_vs_core"]["comparison"]
    accepted = payload["vs_accepted_lagged_comparator"]["comparison"]
    actual_success = 1 if payload["gate4"]["passed"] else 0
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["completed_at"],
        "lane": "alpha_search",
        "status": "accepted" if payload["gate4"]["passed"] else "rejected",
        "accepted": payload["gate4"]["passed"],
        "accepted_alpha": payload["gate4"]["passed"],
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "change_summary": (
            "Added accepted distribution-day absorption paper rows as a "
            "replay-only independent source family to the lagged consensus scout."
        ),
        "change_type": "default_off_paper_adapter_source_family_alpha",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "prior_trial_count": 6,
        "nearby_prior_experiments": payload["preflight"]["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "accepted_production_visible_distribution_day_absorption_source_family",
        "component": _repo_rel(Path(__file__)),
        "parameters": {
            "added_source_name": DISTRIBUTION_SOURCE_NAME,
            "added_source_family": DISTRIBUTION_SOURCE_FAMILY,
            "helper_rule_version": distribution.RULE_VERSION,
            "helper_source_rule_version": distribution.SOURCE_RULE_VERSION,
            "source_path": _repo_rel(DISTRIBUTION_SHARED_ARTIFACT),
            "accepted_lagged_comparator": ACCEPTED_LAGGED_ADAPTER_ID,
            "trade_enabled": False,
        },
        "before_metrics": payload["accepted_lagged_comparator"]["aggregate_after"],
        "after_metrics": payload["aggregate_vs_core"]["after"],
        "delta_metrics": {
            "expected_value_score": accepted["expected_value_score_delta"],
            "total_pnl": accepted["strategy_total_pnl_delta"],
            "expected_value_score_vs_core": comparison["expected_value_score_delta"],
            "total_pnl_vs_core": comparison["strategy_total_pnl_delta"],
            "windows_ev_improved_vs_lagged": accepted["windows_ev_improved"],
            "windows_pnl_improved_vs_lagged": accepted["windows_pnl_improved"],
        },
        "prediction": PREDICTION,
        "calibration": {
            "actual_decision": payload["gate4"]["decision"],
            "actual_success": actual_success,
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": round((PREDICTION["success_probability"] - actual_success) ** 2, 6),
            "expected_ev_delta": PREDICTION["expected_ev_delta"],
            "actual_ev_delta": accepted["expected_value_score_delta"],
            "ev_prediction_error": round(
                accepted["expected_value_score_delta"] - PREDICTION["expected_ev_delta"],
                6,
            ),
            "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
            "actual_pnl_delta": accepted["strategy_total_pnl_delta"],
            "pnl_prediction_error": round(
                accepted["strategy_total_pnl_delta"] - PREDICTION["expected_pnl_delta"],
                2,
            ),
            "realized_failure_mode": None
            if payload["gate4"]["passed"]
            else payload["gate4"]["decision"],
        },
        "production_impact": PRODUCTION_IMPACT,
        "decision": payload["gate4"]["decision"],
        "rejection_reason": None if payload["gate4"]["passed"] else payload["gate4"]["rationale"],
        "negative_reflection": (
            "If rejected, distribution-day absorption is likely a good standalone "
            "pressure-absorption alpha but not an incremental lagged-consensus "
            "confirmation source. It may confirm rows already covered by accepted "
            "sources or arrive mostly as prior confirmation without improving all "
            "windows. Do not retry distribution thresholds, allocator rank, top-N, "
            "hold, cooldown, or notional sweeps; require closed forward "
            "replacement-value evidence or an orthogonal free-data source."
        ),
        "next_retry_requires": [
            "closed forward replacement-value rows",
            "materially different source relation or genuinely new free-data source",
            "shared production/backtest adapter and parity tests before promotion",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(TICKET_JSON),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(DISTRIBUTION_SHARED_ARTIFACT),
            _repo_rel(ACCEPTED_LAGGED_ADAPTER_ARTIFACT),
        ],
        "windows": payload["window_comparison"],
        "anti_js": "No JavaScript was used.",
    }


def _write_card(payload: dict[str, Any]) -> None:
    core = payload["aggregate_vs_core"]["comparison"]
    accepted = payload["vs_accepted_lagged_comparator"]["comparison"]
    source = payload["source_addition_summary"]
    lines = [
        f"# {EXPERIMENT_ID} Distribution Absorption Lagged Consensus Source",
        "",
        "## Decision",
        "",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Rationale: {payload['gate4']['rationale']}",
        "",
        "## Three-Window Result",
        "",
        f"- Vs core EV delta: `{core['expected_value_score_delta']:+.4f}`",
        f"- Vs core PnL delta: `${core['strategy_total_pnl_delta']:+,.2f}`",
        f"- Vs accepted lagged consensus EV delta: `{accepted['expected_value_score_delta']:+.4f}`",
        f"- Vs accepted lagged consensus PnL delta: `${accepted['strategy_total_pnl_delta']:+,.2f}`",
        f"- Selected trades with distribution source: `{source['selected_with_distribution_source_count']}`",
        "",
        "| Window | EV Delta Vs Lagged | PnL Delta Vs Lagged | EV Delta Vs Core | Target Trades |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["window_comparison"]:
        lines.append(
            f"| {row['label']} | {row['expected_value_delta_vs_lagged']:+.4f} | "
            f"${row['strategy_total_pnl_delta_vs_lagged']:+,.2f} | "
            f"{row['expected_value_delta_vs_core']:+.4f} | "
            f"{row['target_trade_count']} |"
        )
    lines.extend(
        [
            "",
            "## Source Diagnostics",
            "",
            f"- Distribution source rows by window: `{source['added_source_rows_by_window']}`",
            f"- Current distribution confirmations selected: `{source['selected_with_current_distribution_count']}`",
            f"- Prior distribution confirmations selected: `{source['selected_with_prior_distribution_count']}`",
            "",
            "## Production Boundary",
            "",
            PRODUCTION_IMPACT["parity_note"],
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    _write_text(CARD_MD, "\n".join(lines))


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON, {}) or {}
    ticket.update(
        {
            "status": "completed",
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "artifact": _repo_rel(OUT_JSON),
            "card": _repo_rel(CARD_MD),
            "log": _repo_rel(LOG_JSON),
            "production_impact": PRODUCTION_IMPACT,
            "gate4": payload["gate4"],
            "result": {
                "decision": payload["gate4"]["decision"],
                "aggregate_expected_value_delta_vs_lagged": payload[
                    "vs_accepted_lagged_comparator"
                ]["comparison"]["expected_value_score_delta"],
                "aggregate_strategy_total_pnl_delta_vs_lagged": payload[
                    "vs_accepted_lagged_comparator"
                ]["comparison"]["strategy_total_pnl_delta"],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)


def _update_manifest(payload: dict[str, Any]) -> None:
    manifest = _load_json(MANIFEST_JSON, {}) or {}
    manifest.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "completed",
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "artifacts": [
                _repo_rel(OUT_JSON),
                _repo_rel(LOG_JSON),
                _repo_rel(CARD_MD),
                _repo_rel(TICKET_JSON),
            ],
        }
    )
    _write_json(MANIFEST_JSON, manifest, ensure_ascii=False, sort_keys=False)


def _update_registry(payload: dict[str, Any]) -> None:
    comparison = payload["vs_accepted_lagged_comparator"]["comparison"]
    status = "accepted" if payload["gate4"]["passed"] else "rejected"
    result = {
        "decision": payload["gate4"]["decision"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "card": _repo_rel(CARD_MD),
        "aggregate_expected_value_delta": comparison["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": comparison["strategy_total_pnl_delta"],
        "accepted": payload["gate4"]["passed"],
        "gate4": payload["gate4"],
        "calibration": _log_record(payload)["calibration"],
        "production_impact": PRODUCTION_IMPACT,
    }
    fields = {
        "owner": "alpha-search-automation",
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "change_type": "default_off_paper_adapter_source_family_alpha",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": 6,
        "nearby_prior_experiments": payload["preflight"]["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "accepted_production_visible_distribution_day_absorption_source_family",
        "decision": payload["gate4"]["decision"],
        "summary": payload["gate4"]["rationale"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": comparison["expected_value_score_delta"],
        "aggregate_strategy_total_pnl_delta": comparison["strategy_total_pnl_delta"],
        "completed_at": payload["completed_at"],
    }
    try:
        persist_self_registered_result(
            REGISTRY_JSON,
            experiment_id=EXPERIMENT_ID,
            lane="alpha_search",
            prediction=PREDICTION,
            result=result,
            status=status,
            fields=fields,
        )
        return
    except PermissionError as exc:
        fallback = (
            "persist_self_registered_result failed on ticket atomic replace: "
            f"{type(exc).__name__}: {exc}"
        )

    registry = _load_json(REGISTRY_JSON, None)
    if not isinstance(registry, dict):
        return
    experiments = registry.get("experiments")
    if isinstance(experiments, list):
        for item in experiments:
            if isinstance(item, dict) and item.get("experiment_id") == EXPERIMENT_ID:
                item.update(
                    {
                        **fields,
                        "status": status,
                        "result": result,
                        "prediction": PREDICTION,
                        "registry_update_fallback": fallback,
                        "updated_at": payload["completed_at"],
                    }
                )
                break
    registry["updated_at"] = payload["completed_at"]
    _write_json(REGISTRY_JSON, registry, ensure_ascii=False, sort_keys=False)

    ticket = _load_json(TICKET_JSON, {}) or {}
    ticket["registry_update_fallback"] = fallback
    _write_json(TICKET_JSON, ticket)


def main() -> None:
    _patch_source_family_context()
    gate2 = same_day.prior.base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    base_source_rows = same_day.prior._source_rows_by_window()
    distribution_rows, distribution_diagnostics = _distribution_source_rows_by_window()
    extended_source_rows = template._merge_source_rows(base_source_rows, distribution_rows)
    baselines = same_day.prior._load_baselines()

    accepted_results, accepted_target_trades = lagged._run_lagged_windows(
        baselines,
        base_source_rows,
    )
    results, target_trades_by_window = lagged._run_lagged_windows(
        baselines,
        extended_source_rows,
    )

    aggregate_vs_core = same_day.prior._aggregate_results(results)
    target_summary = same_day.prior._target_summary(target_trades_by_window)
    lagged_summary = lagged._lagged_source_summary(target_trades_by_window)
    vs_lagged = template._aggregate_vs_results(results, accepted_results)
    source_summary = _source_addition_summary(target_trades_by_window, distribution_rows)
    gate4 = _gate4(aggregate_vs_core, results, target_summary, vs_lagged, source_summary)
    completed_at = _utc_now()

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": completed_at,
        "completed_at": completed_at,
        "lane": "alpha_search",
        "preflight": _preflight_payload(),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "entry/candidate_pool: accepted distribution-day absorption paper "
                "rows may improve lagged accepted-source consensus quality."
            ),
            "2_history_check": _preflight_payload()["history_check"],
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Use docs/backtesting.md three canonical windows; accept only if "
                "the variant beats core and current accepted lagged consensus in "
                "all three windows with sample, drawdown, survival, and "
                "concentration guards."
            ),
            "5_reproducibility": _preflight_payload()["reproducibility"],
        },
        "source_files": {
            "accepted_lagged_comparator": _repo_rel(ACCEPTED_LAGGED_ADAPTER_ARTIFACT),
            DISTRIBUTION_SOURCE_NAME: _repo_rel(DISTRIBUTION_SHARED_ARTIFACT),
        },
        "rule": {
            "rule_version": RULE_VERSION,
            "added_source_name": DISTRIBUTION_SOURCE_NAME,
            "added_source_family": DISTRIBUTION_SOURCE_FAMILY,
            "helper_rule_version": distribution.RULE_VERSION,
            "helper_source_rule_version": distribution.SOURCE_RULE_VERSION,
            "prior_confirmation_trading_days": lagged.PRIOR_CONFIRMATION_TRADING_DAYS,
            "min_source_family_count": same_day.MIN_SOURCE_FAMILY_COUNT,
            "base_notional_usd": same_day.prior.BASE_NOTIONAL_USD,
            "hold_days": same_day.prior.HOLD_DAYS,
            "max_paper_trades_per_day": same_day.prior.MAX_PAPER_TRADES_PER_DAY,
        },
        "production_impact": PRODUCTION_IMPACT,
        "prediction": PREDICTION,
        "gate2": gate2,
        "gate3": {
            "survival_floor": 0.05,
            "new_core_filter_added": False,
            "candidate_pool_source_family_admission_only": True,
            "min_survival_rate": min(_safe_float(row["before"].get("survival_rate")) for row in results),
        },
        "aggregate_vs_core": aggregate_vs_core,
        "accepted_lagged_comparator": {
            "experiment_id": ACCEPTED_LAGGED_ADAPTER_ID,
            "source_artifact": _repo_rel(ACCEPTED_LAGGED_ADAPTER_ARTIFACT),
            "aggregate_after": _aggregate_after(accepted_results),
            "target_summary": same_day.prior._target_summary(accepted_target_trades),
        },
        "vs_accepted_lagged_comparator": vs_lagged,
        "window_comparison": _window_comparison(results, accepted_results),
        "results": results,
        "target_summary": target_summary,
        "lagged_source_summary": lagged_summary,
        "distribution_source_diagnostics": distribution_diagnostics,
        "source_addition_summary": source_summary,
        "target_trades_by_window": target_trades_by_window,
        "gate4": gate4,
        "anti_js": "No JavaScript was used.",
    }

    log_row = _log_record(payload)
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, log_row)
    _write_card(payload)
    _update_ticket(payload)
    _update_manifest(payload)
    _update_registry(payload)
    _upsert_jsonl(EXPERIMENT_LOG, log_row)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": gate4["decision"],
                "aggregate_vs_core": aggregate_vs_core["comparison"],
                "aggregate_vs_accepted_lagged_consensus": vs_lagged["comparison"],
                "source_addition_summary": source_summary,
                "distribution_source_diagnostics": distribution_diagnostics,
                "anti_js": "No JavaScript was used.",
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
