"""exp-20260603-023: AI optical source-family consensus scout.

Replay-only alpha search. This tests one variable: whether the accepted
AI optical IWM-confirmed paper sleeve contributes an independent same-date
source family to the accepted free-data cross-source consensus.

No shared adapter, production orders, watchlists, ranking, sizing, exits, LLM,
news, or default trade surfaces are changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENT_DIR = QUANT_DIR / "experiments"
LEGACY_DIR = EXPERIMENT_DIR / "legacy"
for path in (QUANT_DIR, EXPERIMENT_DIR, LEGACY_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import exp_20260426_041_opening_range_continuation_shadow as opening_shadow
import exp_20260603_014_accepted_consensus_independent_source_family as consensus


EXPERIMENT_ID = "exp-20260603-023"
STEM = "ai_optical_consensus_source_family"
TRIAL_FAMILY = "accepted_free_data_cross_source_consensus_new_independent_source_family"
CHANGED_VARIABLE = "ai_optical_iwm_confirmed_source_family_presence_added_to_independent_consensus_v1"
RULE_VERSION = "independent_source_family_with_ai_optical_iwm_confirmed_v1"

ROOT = consensus.ROOT
OUT_DIR = Path("data/experiments") / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260603_023_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = Path("experiments/logs") / f"{EXPERIMENT_ID}.json"
TICKET_JSON = Path("experiments/tickets") / f"{EXPERIMENT_ID}.json"
CARD_MD = Path("experiments/cards") / f"{EXPERIMENT_ID}.md"
EXPERIMENT_LOG = Path("docs/experiment_log.jsonl")
REGISTRY_JSON = Path("docs/experiment_registry.json")

AI_OPTICAL_SOURCE = "AI_OPTICAL_IWM_CONFIRMED_PAPER"
AI_OPTICAL_SOURCE_EXPERIMENT_ID = "exp-20260525-003"
AI_OPTICAL_SOURCE_ARTIFACT = Path(
    "data/experiments/exp-20260525-003/ai_optical_iwm_confirmed_fixed_notional_sleeve.json"
)
CURRENT_ACCEPTED_CONSENSUS_ARTIFACT = Path(
    "data/experiments/exp-20260603-014/accepted_consensus_independent_source_family.json"
)

SOURCE_FILES = {
    **consensus.SOURCE_FILES,
    AI_OPTICAL_SOURCE: AI_OPTICAL_SOURCE_ARTIFACT,
}
SOURCE_EXPERIMENT_IDS = {
    **consensus.SOURCE_EXPERIMENT_IDS,
    AI_OPTICAL_SOURCE: AI_OPTICAL_SOURCE_EXPERIMENT_ID,
}
SOURCE_FAMILIES = {
    **consensus.SOURCE_FAMILIES,
    AI_OPTICAL_SOURCE: "ai_optical_iwm_confirmed",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_uses_existing_default_off_source_artifact",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_watchlist_changed": False,
    "production_orders_changed": False,
    "parity_note": (
        "This experiment changes no production code. A retained lead would need "
        "the same AI optical source-family row reconstruction wired through the "
        "shared default-off consensus adapter and daily run path before any "
        "candidate queue or order surface could change."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _configure_consensus_module() -> None:
    consensus.EXPERIMENT_ID = EXPERIMENT_ID
    consensus.STEM = STEM
    consensus.TRIAL_FAMILY = TRIAL_FAMILY
    consensus.CHANGED_VARIABLE = CHANGED_VARIABLE
    consensus.RULE_VERSION = RULE_VERSION
    consensus.SOURCE_FILES = SOURCE_FILES
    consensus.SOURCE_EXPERIMENT_IDS = SOURCE_EXPERIMENT_IDS
    consensus.SOURCE_FAMILIES = SOURCE_FAMILIES
    consensus.OUT_DIR = OUT_DIR
    consensus.OUT_JSON = OUT_JSON
    consensus.BEFORE_JSON = BEFORE_JSON
    consensus.AFTER_JSON = AFTER_JSON
    consensus.LOG_JSON = LOG_JSON
    consensus.TICKET_JSON = TICKET_JSON
    consensus.CARD_MD = CARD_MD
    consensus.EXPERIMENT_LOG = EXPERIMENT_LOG
    consensus.REGISTRY_JSON = REGISTRY_JSON
    consensus.PRODUCTION_IMPACT = PRODUCTION_IMPACT
    consensus._configure_prior_module()
    consensus.prior._configure_base_module()
    consensus.prior.base.shadow = opening_shadow


def _ai_optical_source_row(trade: dict[str, Any]) -> dict[str, Any]:
    market_confirmation = trade.get("market_confirmation") or {}
    signal_date = market_confirmation.get("market_state_as_of") or trade.get("entry_date")
    return {
        "source_name": AI_OPTICAL_SOURCE,
        "source_experiment_id": AI_OPTICAL_SOURCE_EXPERIMENT_ID,
        "date": signal_date,
        "signal_date": signal_date,
        "entry_date": trade.get("entry_date"),
        "exit_date": trade.get("exit_date"),
        "ticker": str(trade.get("ticker") or "").upper(),
        "paper_pnl": trade.get("pnl"),
        "pnl_usd": trade.get("pnl"),
        "return_pct": trade.get("pnl_pct_net"),
        "paper_notional_usd": trade.get("paper_notional_usd"),
        "ai_optical_market_state_as_of": market_confirmation.get("market_state_as_of"),
        "ai_optical_iwm_momentum20": market_confirmation.get("iwm_momentum20"),
        "ai_optical_spy_momentum20": market_confirmation.get("spy_momentum20"),
        "ai_optical_iwm_spy_momentum_spread": market_confirmation.get(
            "iwm_spy_momentum_spread"
        ),
        "ai_optical_min_iwm_spy_momentum_spread": market_confirmation.get(
            "min_iwm_spy_momentum_spread"
        ),
        "known_at": f"{signal_date}T21:00:00Z" if signal_date else None,
        "trade_enabled": False,
        "alters_orders": False,
    }


def _ai_optical_source_audit(
    source_payload: dict[str, Any],
    rows_by_window: dict[str, list[dict[str, Any]]],
    existing_keys_by_window: dict[str, set[tuple[str, str]]],
) -> dict[str, Any]:
    return {
        "source": AI_OPTICAL_SOURCE,
        "source_experiment_id": AI_OPTICAL_SOURCE_EXPERIMENT_ID,
        "source_artifact": str(AI_OPTICAL_SOURCE_ARTIFACT).replace("\\", "/"),
        "source_decision": source_payload.get("decision"),
        "source_gate4_passed": bool((source_payload.get("gate4") or {}).get("passed")),
        "source_target_summary": source_payload.get("target_trade_summary"),
        "windows": {
            label: {
                "selected_trade_count": len(trades),
                "selected_trade_pnl_usd": round(
                    sum(float(row.get("pnl") or 0.0) for row in trades), 2
                ),
                "same_date_ticker_overlap_with_existing_consensus_sources": sum(
                    (
                        (
                            str((row.get("market_confirmation") or {}).get("market_state_as_of") or row.get("entry_date") or ""),
                            str(row.get("ticker") or "").upper(),
                        )
                        in existing_keys_by_window.get(label, set())
                    )
                    for row in trades
                ),
                "tickers": sorted({str(row.get("ticker") or "").upper() for row in trades}),
            }
            for label, trades in sorted(rows_by_window.items())
        },
    }


def _source_rows_by_window_with_ai_optical() -> tuple[
    dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
    dict[str, Any],
]:
    combined = consensus.prior._source_rows_by_window()
    existing_keys_by_window = {label: set(rows) for label, rows in combined.items()}
    source_payload = consensus.prior._load_json(ROOT / AI_OPTICAL_SOURCE_ARTIFACT)
    ai_rows_by_window = source_payload.get("target_trades_by_window") or {}
    if not isinstance(ai_rows_by_window, dict):
        raise RuntimeError("AI optical artifact missing target_trades_by_window")

    normalized_rows_by_window: dict[str, list[dict[str, Any]]] = {}
    for label, trades in ai_rows_by_window.items():
        if not isinstance(trades, list):
            continue
        normalized_rows_by_window[str(label)] = [row for row in trades if isinstance(row, dict)]
        for trade in normalized_rows_by_window[str(label)]:
            source_row = _ai_optical_source_row(trade)
            signal_date = str(source_row.get("signal_date") or source_row.get("date") or "")
            ticker = str(source_row.get("ticker") or "").upper()
            if not signal_date or not ticker:
                continue
            combined[str(label)][(signal_date, ticker)].append(source_row)

    return combined, _ai_optical_source_audit(
        source_payload,
        normalized_rows_by_window,
        existing_keys_by_window,
    )


def _preflight_payload() -> dict[str, Any]:
    return {
        "alpha_hypothesis": (
            "A same-date ticker confirmed by the accepted AI optical IWM-confirmed sleeve and at "
            "least one other accepted free-data source family may have better replacement value "
            "than the current accepted independent-source consensus alone."
        ),
        "category": "entry/candidate_pool",
        "playbook_alignment": (
            "Uses a broad, free, production-visible default-off paper source family. It avoids "
            "LLM soft-ranking, direct ticker-noise expansion, state-surface tuning, and retuning "
            "source-count thresholds."
        ),
        "nearby_prior_experiments": [
            "exp-20260525-003",
            "exp-20260525-005",
            "exp-20260603-014",
            "exp-20260603-015",
            "exp-20260603-016",
            "exp-20260603-017",
        ],
        "prior_difference": (
            "The AI optical sleeve was previously accepted as a standalone default-off paper "
            "adapter. This run only tests whether that accepted sleeve adds independent "
            "same-date confirmation to the current accepted source-family consensus."
        ),
        "single_causal_variable": CHANGED_VARIABLE,
        "acceptance_criteria": {
            "canonical_windows": list(consensus.prior.base.WINDOWS.keys()),
            "aggregate_expected_value_delta": "> 0",
            "aggregate_pnl_delta": "> 0",
            "per_window_expected_value_delta": "3 of 3 windows > 0",
            "per_window_pnl_delta": "3 of 3 windows > 0",
            "beats_current_accepted_consensus": "required for source-family expansion retention",
            "minimum_target_trades": consensus.prior.MIN_TARGET_TRADES,
            "minimum_target_windows": consensus.prior.MIN_TARGET_WINDOWS,
            "max_drawdown_drift": consensus.prior.MAX_DRAWDOWN_WORSE,
            "survival_rate_floor": 0.05,
            "max_single_positive_share": consensus.prior.MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi_max": consensus.prior.MAX_POSITIVE_HHI,
            "source_family_min_count": consensus.MIN_SOURCE_FAMILY_COUNT,
        },
        "reproducibility": (
            "The runner persists source-family mapping, source artifact audit, canonical "
            "before/after metrics, target trades, and current-accepted comparator diagnostics."
        ),
    }


def _current_accepted_consensus_comparison(
    aggregate: dict[str, Any],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    source = consensus.prior._load_json(ROOT / CURRENT_ACCEPTED_CONSENSUS_ARTIFACT)
    source_results = {str(row["label"]): row for row in source.get("results", [])}
    window_rows: list[dict[str, Any]] = []
    windows_ev_regressed: list[str] = []
    windows_pnl_regressed: list[str] = []
    for row in results:
        label = str(row["label"])
        source_row = source_results[label]
        candidate_after_ev = float(row["after"]["expected_value_score"])
        source_after_ev = float(source_row["after"]["expected_value_score"])
        candidate_after_pnl = float(row["after"]["total_pnl"])
        source_after_pnl = float(source_row["after"]["total_pnl"])
        ev_delta = round(candidate_after_ev - source_after_ev, 6)
        pnl_delta = round(candidate_after_pnl - source_after_pnl, 2)
        if ev_delta < 0:
            windows_ev_regressed.append(label)
        if pnl_delta < 0:
            windows_pnl_regressed.append(label)
        window_rows.append(
            {
                "label": label,
                "candidate_after_expected_value": candidate_after_ev,
                "current_accepted_after_expected_value": source_after_ev,
                "after_expected_value_delta_vs_current_accepted": ev_delta,
                "candidate_after_total_pnl": candidate_after_pnl,
                "current_accepted_after_total_pnl": source_after_pnl,
                "after_total_pnl_delta_vs_current_accepted": pnl_delta,
                "candidate_target_trade_count": row["target_trade_count"],
                "current_accepted_target_trade_count": source_row["target_trade_count"],
            }
        )
    aggregate_ev_delta = round(
        float(aggregate["after"]["expected_value_score"])
        - float(source["aggregate"]["after"]["expected_value_score"]),
        6,
    )
    aggregate_pnl_delta = round(
        float(aggregate["after"]["strategy_total_pnl"])
        - float(source["aggregate"]["after"]["strategy_total_pnl"]),
        2,
    )
    return {
        "comparison_artifact": str(CURRENT_ACCEPTED_CONSENSUS_ARTIFACT).replace("\\", "/"),
        "current_accepted_experiment_id": str(source.get("experiment_id")),
        "candidate_after_expected_value": aggregate["after"]["expected_value_score"],
        "current_accepted_after_expected_value": source["aggregate"]["after"]["expected_value_score"],
        "after_expected_value_delta_vs_current_accepted": aggregate_ev_delta,
        "candidate_after_strategy_total_pnl": aggregate["after"]["strategy_total_pnl"],
        "current_accepted_after_strategy_total_pnl": source["aggregate"]["after"][
            "strategy_total_pnl"
        ],
        "after_strategy_total_pnl_delta_vs_current_accepted": aggregate_pnl_delta,
        "beats_current_accepted_ev": aggregate_ev_delta > 0,
        "beats_current_accepted_pnl": aggregate_pnl_delta > 0,
        "windows_ev_regressed_vs_current_accepted": windows_ev_regressed,
        "windows_pnl_regressed_vs_current_accepted": windows_pnl_regressed,
        "by_window": window_rows,
    }


def _apply_current_accepted_guard(
    gate4: dict[str, Any],
    current_comparison: dict[str, Any],
) -> dict[str, Any]:
    gate4["gates"]["beats_current_accepted_consensus_ev"] = bool(
        current_comparison["beats_current_accepted_ev"]
    )
    gate4["gates"]["beats_current_accepted_consensus_pnl"] = bool(
        current_comparison["beats_current_accepted_pnl"]
    )
    gate4["gates"]["no_window_ev_regression_vs_current_accepted_consensus"] = not bool(
        current_comparison["windows_ev_regressed_vs_current_accepted"]
    )
    gate4["gates"]["no_window_pnl_regression_vs_current_accepted_consensus"] = not bool(
        current_comparison["windows_pnl_regressed_vs_current_accepted"]
    )
    if not all(gate4["gates"].values()):
        gate4["passed"] = False
        gate4["decision"] = (
            "rejected_ai_optical_source_family_underperforms_current_accepted_consensus"
        )
        gate4["rationale"] = (
            "The AI optical-expanded consensus failed the stricter current accepted consensus "
            "guard. Source-family expansions must beat the accepted comparator before retention "
            "or adapter promotion."
        )
        gate4["requires_parity_before_promotion"] = False
    return gate4


def _added_source_selected_summary(
    target_trades_by_window: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    selected: dict[str, list[dict[str, Any]]] = {}
    for label, trades in target_trades_by_window.items():
        selected[label] = [
            trade
            for trade in trades
            if AI_OPTICAL_SOURCE in set(str(row) for row in (trade.get("source_names") or []))
        ]
    total = sum(len(rows) for rows in selected.values())
    return {
        "added_source": AI_OPTICAL_SOURCE,
        "added_source_family": SOURCE_FAMILIES[AI_OPTICAL_SOURCE],
        "selected_trade_count": total,
        "selected_trade_count_by_window": {label: len(rows) for label, rows in selected.items()},
        "selected_trade_pnl_by_window": {
            label: round(sum(float(row.get("pnl") or 0.0) for row in rows), 2)
            for label, rows in selected.items()
        },
        "selected_tickers": sorted(
            {
                str(row.get("ticker") or "").upper()
                for rows in selected.values()
                for row in rows
            }
        ),
    }


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate"]["comparison"]
    prediction = {
        "success_probability": 0.25,
        "expected_ev_delta": 0.2,
        "expected_pnl_delta": 3500.0,
        "main_failure_modes": [
            "underperforms_current_accepted_consensus",
            "thin_same_date_overlap",
            "window_regression",
            "concentration_failed",
        ],
        "confidence_reason": (
            "AI optical is an accepted default-off paper source family, but recent source-family "
            "expansions failed unless they beat the current accepted independent consensus."
        ),
        "recorded_at": "2026-06-03T20:20:00+00:00",
    }
    actual_success = 1 if payload["gate4"]["passed"] else 0
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["completed_at"],
        "lane": "alpha_search",
        "status": "accepted" if payload["gate4"]["passed"] else "rejected",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "ai_optical_iwm_confirmed_source_family_added_to_consensus_v1",
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "change_type": "default_off_paper_candidate_pool_source_family_scout",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "prior_trial_count": 10,
        "nearby_prior_experiments": payload["preflight"]["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "accepted_ai_optical_default_off_source_family_consensus_overlap",
        "decision": payload["gate4"]["decision"],
        "accepted": bool(payload["gate4"]["passed"]),
        "rejection_reason": None if payload["gate4"]["passed"] else payload["gate4"]["rationale"],
        "prediction": prediction,
        "calibration": {
            "actual_decision": payload["gate4"]["decision"],
            "actual_success": actual_success,
            "predicted_success_probability": prediction["success_probability"],
            "brier_score": round((prediction["success_probability"] - actual_success) ** 2, 6),
            "expected_ev_delta": prediction["expected_ev_delta"],
            "actual_ev_delta": comparison["expected_value_score_delta"],
            "ev_prediction_error": round(
                comparison["expected_value_score_delta"] - prediction["expected_ev_delta"], 6
            ),
            "expected_pnl_delta": prediction["expected_pnl_delta"],
            "actual_pnl_delta": comparison["strategy_total_pnl_delta"],
            "pnl_prediction_error": round(
                comparison["strategy_total_pnl_delta"] - prediction["expected_pnl_delta"], 2
            ),
            "realized_failure_mode": None
            if payload["gate4"]["passed"]
            else payload["gate4"].get("realized_failure_mode")
            or "ai_optical_source_family_current_comparator_guard_failed",
        },
        "production_impact": PRODUCTION_IMPACT,
        "requires_parity_before_promotion": bool(payload["gate4"]["requires_parity_before_promotion"]),
        "metrics": {
            "aggregate_expected_value_before": payload["aggregate"]["before"]["expected_value_score"],
            "aggregate_expected_value_after": payload["aggregate"]["after"]["expected_value_score"],
            "aggregate_expected_value_delta": comparison["expected_value_score_delta"],
            "aggregate_strategy_total_pnl_before": payload["aggregate"]["before"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_after": payload["aggregate"]["after"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_delta": comparison["strategy_total_pnl_delta"],
            "target_trade_count": payload["target_summary"]["target_trade_count"],
            "target_trade_pnl_usd": payload["target_summary"]["target_trade_pnl_usd"],
            "max_drawdown_delta": payload["gate4"]["max_drawdown_delta"],
            "max_single_positive_share": payload["target_summary"]["max_single_positive_share"],
            "positive_pnl_hhi": payload["target_summary"]["positive_pnl_hhi"],
            "ai_optical_source_trade_count": sum(
                int(row["selected_trade_count"])
                for row in payload["ai_optical_source_audit"]["windows"].values()
            ),
            "ai_optical_consensus_selected_trade_count": payload[
                "added_source_selected_summary"
            ]["selected_trade_count"],
            "after_ev_delta_vs_current_accepted_consensus": payload[
                "current_accepted_consensus_comparison"
            ]["after_expected_value_delta_vs_current_accepted"],
            "after_pnl_delta_vs_current_accepted_consensus": payload[
                "current_accepted_consensus_comparison"
            ]["after_strategy_total_pnl_delta_vs_current_accepted"],
        },
        "windows": [
            {
                "label": row["label"],
                "expected_value_before": row["before"]["expected_value_score"],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta": row["comparison"]["expected_value_score_delta"],
                "strategy_total_pnl_delta": row["comparison"]["strategy_total_pnl_delta"],
                "target_trade_count": row["target_trade_count"],
                "target_trade_pnl_usd": row["target_trade_pnl_usd"],
            }
            for row in payload["results"]
        ],
        "artifact_path": str(OUT_JSON).replace("\\", "/"),
        "anti_js": "No JavaScript was used.",
    }


def _write_ticket(payload: dict[str, Any]) -> None:
    ticket = consensus.prior._load_json(TICKET_JSON) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "id": EXPERIMENT_ID,
            "experiment_id": EXPERIMENT_ID,
            "status": "completed",
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "artifact": str(OUT_JSON).replace("\\", "/"),
            "markdown_artifact": str(CARD_MD).replace("\\", "/"),
            "log": str(LOG_JSON).replace("\\", "/"),
            "production_impact": PRODUCTION_IMPACT,
            "gate4": payload["gate4"],
        }
    )
    consensus.prior._write_json(TICKET_JSON, ticket)


def main() -> None:
    _configure_consensus_module()
    gate2 = consensus.prior.base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    source_rows, ai_optical_source_audit = _source_rows_by_window_with_ai_optical()
    _configure_consensus_module()
    baselines = consensus.prior._load_baselines()
    results, target_trades_by_window = consensus._run_windows(baselines, source_rows)
    aggregate = consensus.prior._aggregate_results(results)
    target_summary = consensus.prior._target_summary(target_trades_by_window)
    source_family_summary = consensus._source_family_summary(target_trades_by_window)
    gate4 = consensus.prior._gate4_decision(aggregate, results, target_summary)
    current_accepted_consensus_comparison = _current_accepted_consensus_comparison(aggregate, results)
    added_source_selected_summary = _added_source_selected_summary(target_trades_by_window)
    if not source_family_summary["all_selected_have_min_family_count"]:
        gate4["gates"]["source_family_min_count_passed"] = False
        gate4["passed"] = False
        gate4["decision"] = "rejected_ai_optical_source_family_invariant_failed"
        gate4["rationale"] = "At least one selected trade failed the source-family count invariant."
    else:
        gate4["gates"]["source_family_min_count_passed"] = True
    gate4 = _apply_current_accepted_guard(gate4, current_accepted_consensus_comparison)
    gate4["gates"]["added_source_family_selected_trade_count_positive"] = (
        added_source_selected_summary["selected_trade_count"] > 0
    )
    if added_source_selected_summary["selected_trade_count"] <= 0:
        gate4["passed"] = False
        gate4["decision"] = "rejected_ai_optical_source_family_no_selected_consensus_overlap"
        gate4["rationale"] = (
            "The accepted AI optical source rows had no same-date ticker overlap that survived the "
            "independent consensus selector, so the observed after metrics are not attributable to "
            "the tested source-family addition."
        )
        gate4["realized_failure_mode"] = "zero_selected_same_date_consensus_overlap"
        gate4["requires_parity_before_promotion"] = False
    completed_at = _utc_now()

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": completed_at,
        "completed_at": completed_at,
        "lane": "alpha_search",
        "preflight": _preflight_payload(),
        "source_files": {name: str(path).replace("\\", "/") for name, path in SOURCE_FILES.items()},
        "rule": {
            "rule_version": RULE_VERSION,
            "min_source_family_count": consensus.MIN_SOURCE_FAMILY_COUNT,
            "source_families": SOURCE_FAMILIES,
            "added_source_family": SOURCE_FAMILIES[AI_OPTICAL_SOURCE],
            "added_source": AI_OPTICAL_SOURCE,
            "base_notional_usd": consensus.prior.BASE_NOTIONAL_USD,
            "hold_days": consensus.prior.HOLD_DAYS,
            "max_paper_trades_per_day": consensus.prior.MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": consensus.prior.SAME_TICKER_COOLDOWN_DAYS,
        },
        "production_impact": PRODUCTION_IMPACT,
        "gate2": gate2,
        "gate3": {
            "survival_floor": 0.05,
            "new_core_filter_added": False,
            "candidate_pool_source_family_admission_only": True,
        },
        "ai_optical_source_audit": ai_optical_source_audit,
        "added_source_selected_summary": added_source_selected_summary,
        "aggregate": aggregate,
        "current_accepted_consensus_comparison": current_accepted_consensus_comparison,
        "results": results,
        "target_summary": target_summary,
        "target_trades_by_window": target_trades_by_window,
        "source_family_summary": source_family_summary,
        "gate4": gate4,
        "anti_js": "No JavaScript was used.",
    }

    consensus.prior._write_json(OUT_JSON, payload)
    consensus.prior._write_json(BEFORE_JSON, aggregate["before"])
    consensus.prior._write_json(AFTER_JSON, aggregate["after"])
    record = _experiment_log_record(payload)
    consensus.prior._write_json(LOG_JSON, record)
    consensus.prior._write_card(payload)
    _write_ticket(payload)
    consensus._upsert_registry(payload)
    consensus.prior.base._upsert_jsonl(EXPERIMENT_LOG, record)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": gate4["decision"],
                "aggregate": aggregate["comparison"],
                "current_accepted_consensus_comparison": current_accepted_consensus_comparison,
                "source_family_summary": source_family_summary,
                "ai_optical_source_audit": ai_optical_source_audit,
                "anti_js": payload["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
