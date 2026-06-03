"""exp-20260603-014: accepted consensus independent source-family count.

Replay-only alpha search. This tests whether the newly accepted FINRA
borrow-pressure source can improve accepted free-data consensus only when
confirmed by at least one non-FINRA source family.

Unlike exp-20260603-011, FINRA_IWM_CONFIRMED_PAPER and
FINRA_BORROW_PRESSURE_PAPER are collapsed into one source family before
admission. No shared adapter, production path, live orders, ranking, sizing,
exits, thresholds, or hold periods are changed. No JavaScript is used.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import exp_20260531_030_accepted_free_data_cross_source_consensus as prior


EXPERIMENT_ID = "exp-20260603-014"
STEM = "accepted_consensus_independent_source_family"
TRIAL_FAMILY = "accepted_free_data_cross_source_consensus_source_family_count"
CHANGED_VARIABLE = "independent_source_family_count_min_2_with_finra_family_collapsed"
RULE_VERSION = "independent_source_family_count_v1"

ROOT = prior.ROOT
OUT_DIR = Path("data/experiments") / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = Path("experiments/logs") / f"{EXPERIMENT_ID}.json"
TICKET_JSON = Path("experiments/tickets") / f"{EXPERIMENT_ID}.json"
DOC_TICKET_JSON = Path("docs/experiments/tickets") / f"{EXPERIMENT_ID}.json"
CARD_MD = Path("experiments/cards") / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = Path("experiments/artifacts") / f"{EXPERIMENT_ID}_{STEM}.md"
EXPERIMENT_LOG = Path("docs/experiment_log.jsonl")
REGISTRY_JSON = Path("docs/experiment_registry.json")

FINRA_BASE_SOURCE = "FINRA_IWM_CONFIRMED_PAPER"
FINRA_BORROW_SOURCE = "FINRA_BORROW_PRESSURE_PAPER"
MIN_SOURCE_FAMILY_COUNT = 2

SOURCE_FILES = {
    **prior.SOURCE_FILES,
    FINRA_BORROW_SOURCE: Path(
        "data/experiments/exp-20260603-006/exp_20260603_006_finra_borrow_pressure_candidate_pool.json"
    ),
}
SOURCE_EXPERIMENT_IDS = {
    **prior.SOURCE_EXPERIMENT_IDS,
    FINRA_BORROW_SOURCE: "exp-20260603-006",
}
SOURCE_FAMILIES = {
    "FUNDAMENTAL_GROWTH_RS_PAPER": "companyfacts_growth_quality",
    "VOLUME_BREADTH_BREAKOUT_PAPER": "volume_breadth_breakout",
    FINRA_BASE_SOURCE: "finra_short_pressure",
    FINRA_BORROW_SOURCE: "finra_short_pressure",
    "ALPHA_SCORE_MARKET_REGIME_PAPER": "alpha_score_market_regime",
}

PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "alters_orders": False,
    "adapter_status": "replay_only_no_live_adapter",
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "replay_only": True,
    "parity_test_added": False,
    "production_watchlist_changed": False,
    "production_orders_changed": False,
    "parity_note": (
        "This experiment changes no production code. A retained result would need "
        "a shared default-off adapter that uses the same source-family mapping and "
        "parity tests before any daily report, candidate queue, or order surface "
        "could change."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _configure_prior_module() -> None:
    prior.EXPERIMENT_ID = EXPERIMENT_ID
    prior.STEM = STEM
    prior.TRIAL_FAMILY = TRIAL_FAMILY
    prior.CHANGED_VARIABLE = CHANGED_VARIABLE
    prior.RULE_VERSION = RULE_VERSION
    prior.SOURCE_FILES = SOURCE_FILES
    prior.SOURCE_EXPERIMENT_IDS = SOURCE_EXPERIMENT_IDS
    prior.OUT_DIR = OUT_DIR
    prior.OUT_JSON = OUT_JSON
    prior.BEFORE_JSON = BEFORE_JSON
    prior.AFTER_JSON = AFTER_JSON
    prior.LOG_JSON = LOG_JSON
    prior.TICKET_JSON = TICKET_JSON
    prior.CARD_MD = CARD_MD
    prior.EXPERIMENT_LOG = EXPERIMENT_LOG
    prior.REGISTRY_JSON = REGISTRY_JSON
    prior.PRODUCTION_IMPACT = PRODUCTION_IMPACT


def _source_family(source_name: str) -> str:
    return SOURCE_FAMILIES.get(source_name, source_name)


def _consensus_candidates_for_window(
    label: str,
    source_rows_by_window: dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for (signal_date, ticker), source_rows in source_rows_by_window.get(label, {}).items():
        source_names = sorted({str(row["source_name"]) for row in source_rows})
        source_families = sorted({_source_family(source_name) for source_name in source_names})
        if len(source_families) < MIN_SOURCE_FAMILY_COUNT:
            continue
        source_family_map: dict[str, list[str]] = {}
        for source_name in source_names:
            source_family_map.setdefault(_source_family(source_name), []).append(source_name)
        candidates.append(
            {
                "date": signal_date,
                "ticker": ticker,
                "source_count": len(source_names),
                "source_family_count": len(source_families),
                "source_names": source_names,
                "source_families": source_families,
                "source_family_map": {
                    family: sorted(names) for family, names in sorted(source_family_map.items())
                },
                "source_experiment_ids": {
                    source_name: SOURCE_EXPERIMENT_IDS[source_name] for source_name in source_names
                },
                "source_rows": sorted(source_rows, key=lambda row: str(row.get("source_name") or "")),
                "fundamental_growth_rs_score": prior._extract_source_numeric(
                    source_rows, "fundamental_growth_rs_score"
                ),
                "alpha_score": prior._extract_source_numeric(source_rows, "alpha_score"),
                "volume_breadth_breakout_score": prior._extract_source_numeric(
                    source_rows, "volume_breadth_breakout_score"
                ),
                "finra_candidate_selection_score": prior._extract_source_numeric(
                    source_rows, "candidate_selection_score"
                ),
                "source_agreement_rule": (
                    "same_date_ticker_selected_by_at_least_two_independent_accepted_free_data_source_families"
                ),
                "known_at": f"{signal_date}T21:00:00Z",
                "trade_enabled": False,
                "alters_orders": False,
                "rule_version": RULE_VERSION,
                "strategy": "paper_candidate_pool_default_off",
            }
        )
    return sorted(
        candidates,
        key=lambda row: (
            str(row["date"]),
            -int(row["source_family_count"]),
            -int(row["source_count"]),
            "+".join(row["source_families"]),
            "+".join(row["source_names"]),
            str(row["ticker"]),
        ),
    )


def _select_target_trades(
    snapshot: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selected, diagnostics = prior._select_target_trades(snapshot, candidates)
    family_combos = Counter("+".join(trade.get("source_families") or []) for trade in selected)
    diagnostics["source_family_combo_counts_selected"] = dict(
        sorted(family_combos.items(), key=lambda item: (-item[1], item[0]))
    )
    return selected, diagnostics


def _source_family_summary(target_trades_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    all_trades = [trade for rows in target_trades_by_window.values() for trade in rows]
    family_combo_counts = Counter("+".join(trade.get("source_families") or []) for trade in all_trades)
    raw_combo_counts = Counter("+".join(trade.get("source_names") or []) for trade in all_trades)
    finra_with_non_finra = [
        trade
        for trade in all_trades
        if "finra_short_pressure" in (trade.get("source_families") or [])
        and len(trade.get("source_families") or []) >= 2
    ]
    finra_only = [
        trade
        for trade in all_trades
        if set(trade.get("source_families") or []) == {"finra_short_pressure"}
    ]
    return {
        "min_source_family_count": MIN_SOURCE_FAMILY_COUNT,
        "source_families": SOURCE_FAMILIES,
        "selected_family_combo_counts": dict(sorted(family_combo_counts.items())),
        "selected_raw_source_combo_counts": dict(sorted(raw_combo_counts.items())),
        "finra_with_non_finra_trade_count": len(finra_with_non_finra),
        "finra_only_trade_count": len(finra_only),
        "total_trade_count": len(all_trades),
        "all_selected_have_min_family_count": all(
            len(trade.get("source_families") or []) >= MIN_SOURCE_FAMILY_COUNT for trade in all_trades
        ),
    }


def _run_windows(
    baselines: dict[str, dict[str, Any]],
    source_rows_by_window: dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    results: list[dict[str, Any]] = []
    target_trades_by_window: dict[str, list[dict[str, Any]]] = {}
    for label, cfg in prior.base.WINDOWS.items():
        snapshot = prior.base.shadow._load_snapshot(cfg["snapshot"])
        candidates = _consensus_candidates_for_window(label, source_rows_by_window)
        target_trades, target_diagnostics = _select_target_trades(snapshot, candidates)
        before_result = baselines[label]["result"]
        before = baselines[label]["metrics"]
        overlay = prior.base._overlay_from_paper_trades(before_result, target_trades)
        after = prior.base.overlay_helper._metrics_with_overlay(before_result, overlay)
        raw_delta = prior.base.overlay_helper._delta(after, before)
        comparison = {
            "expected_value_score_delta": raw_delta["expected_value_score"],
            "strategy_total_pnl_delta": raw_delta["total_pnl"],
            "total_pnl_delta": raw_delta["total_pnl"],
            "max_drawdown_delta": raw_delta["max_drawdown_pct"],
            "raw_delta": raw_delta,
        }
        results.append(
            {
                "label": label,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "before": before,
                "after": after,
                "comparison": comparison,
                "target_trade_count": len(target_trades),
                "target_trade_pnl_usd": sum(float(row.get("pnl", 0.0)) for row in target_trades),
                "raw_consensus_candidate_count": len(candidates),
                "target_diagnostics": target_diagnostics,
            }
        )
        target_trades_by_window[label] = target_trades
    return results, target_trades_by_window


def _preflight_payload() -> dict[str, Any]:
    return {
        "alpha_hypothesis": (
            "Accepted free-data consensus should count independent source families rather than raw "
            "source names. FINRA borrow-pressure evidence can improve the consensus sleeve only when "
            "it is confirmed by at least one non-FINRA family."
        ),
        "category": "entry/candidate_pool",
        "playbook_alignment": (
            "Meta research ranks default-off paper adapters highest. This avoids a raw source-count "
            "retune by making source-family independence the tested candidate-pool variable."
        ),
        "nearby_prior_experiments": [
            "exp-20260531-030",
            "exp-20260601-001",
            "exp-20260601-028",
            "exp-20260603-006",
            "exp-20260603-007",
            "exp-20260603-011",
        ],
        "prior_difference": (
            "exp-20260603-011 cleared numeric gates but failed because FINRA/IWM plus FINRA borrow "
            "pressure was not an independent cross-source confirmation. This run collapses those "
            "sources before candidate admission."
        ),
        "single_causal_variable": CHANGED_VARIABLE,
        "acceptance_criteria": {
            "canonical_windows": list(prior.base.WINDOWS.keys()),
            "aggregate_expected_value_delta": "> 0",
            "aggregate_pnl_delta": "> 0",
            "per_window_expected_value_delta": "3 of 3 windows > 0",
            "per_window_pnl_delta": "3 of 3 windows > 0",
            "minimum_target_trades": prior.MIN_TARGET_TRADES,
            "minimum_target_windows": prior.MIN_TARGET_WINDOWS,
            "max_drawdown_drift": prior.MAX_DRAWDOWN_WORSE,
            "survival_rate_floor": 0.05,
            "max_single_positive_share": prior.MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi_max": prior.MAX_POSITIVE_HHI,
            "source_family_min_count": MIN_SOURCE_FAMILY_COUNT,
        },
        "reproducibility": (
            "All source artifact paths, source-family mapping, canonical window metrics, target "
            "trades, and rejection checks are persisted under this experiment ID."
        ),
    }


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate"]["comparison"]
    prediction = {
        "success_probability": 0.22,
        "expected_ev_delta": 0.4,
        "expected_pnl_delta": 6000.0,
        "main_failure_modes": [
            "source_family_count_removes_too_many_trades",
            "window_regression",
            "concentration_failed",
            "nearby_consensus_overfit",
        ],
        "confidence_reason": (
            "exp-20260603-011 cleared all numeric gates but failed source-family independence; "
            "collapsing FINRA into one family directly tests the remaining independent confirmations."
        ),
        "recorded_at": "2026-06-03T13:07:05+00:00",
    }
    actual_success = 1 if payload["gate4"]["passed"] else 0
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["completed_at"],
        "lane": "alpha_search",
        "status": "accepted" if payload["gate4"]["passed"] else "rejected",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": "independent_finra_family_count_v1",
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "change_type": "default_off_paper_candidate_pool_source_family_count",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "prior_trial_count": 7,
        "nearby_prior_experiments": payload["preflight"]["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "new_source_family_independence_guard_from_exp_20260603_011",
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
            else "source_family_count_or_gate4_failed",
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
            "finra_only_trade_count": payload["source_family_summary"]["finra_only_trade_count"],
            "finra_with_non_finra_trade_count": payload["source_family_summary"][
                "finra_with_non_finra_trade_count"
            ],
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


def _write_artifact(payload: dict[str, Any]) -> None:
    prior._write_card(payload)
    source_family = payload["source_family_summary"]
    lines = [
        CARD_MD.read_text(encoding="utf-8"),
        "",
        "## Independent Source-Family Admission",
        "",
        f"- Min source families: `{MIN_SOURCE_FAMILY_COUNT}`",
        f"- FINRA-only selected trades: `{source_family['finra_only_trade_count']}`",
        f"- FINRA with non-FINRA selected trades: `{source_family['finra_with_non_finra_trade_count']}`",
        f"- All selected trades pass family count: `{source_family['all_selected_have_min_family_count']}`",
        "",
        "```json",
        json.dumps(source_family, indent=2, sort_keys=True),
        "```",
        "",
        "No JavaScript was used.",
        "",
    ]
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_MD.write_text("\n".join(lines), encoding="utf-8")


def _update_ticket(path: Path, payload: dict[str, Any]) -> None:
    ticket = prior._load_json(path) if path.exists() else {}
    ticket.update(
        {
            "id": EXPERIMENT_ID,
            "experiment_id": EXPERIMENT_ID,
            "status": "completed",
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "artifact": str(OUT_JSON).replace("\\", "/"),
            "markdown_artifact": str(ARTIFACT_MD).replace("\\", "/"),
            "log": str(LOG_JSON).replace("\\", "/"),
            "production_impact": PRODUCTION_IMPACT,
            "gate4": payload["gate4"],
        }
    )
    prior._write_json(path, ticket)


def _upsert_registry(payload: dict[str, Any]) -> None:
    if not REGISTRY_JSON.exists():
        return
    registry = prior._load_json(REGISTRY_JSON)
    experiments = registry.get("experiments")
    if not isinstance(experiments, list):
        return
    for item in experiments:
        if isinstance(item, dict) and item.get("experiment_id") == EXPERIMENT_ID:
            item["status"] = "completed"
            item["decision"] = payload["gate4"]["decision"]
            item["completed_at"] = payload["completed_at"]
            item["artifact"] = str(OUT_JSON).replace("\\", "/")
            item["log"] = str(LOG_JSON).replace("\\", "/")
            item["aggregate_expected_value_delta"] = payload["aggregate"]["comparison"][
                "expected_value_score_delta"
            ]
            item["aggregate_strategy_total_pnl_delta"] = payload["aggregate"]["comparison"][
                "strategy_total_pnl_delta"
            ]
            break
    prior._write_json(REGISTRY_JSON, registry)


def main() -> None:
    _configure_prior_module()
    gate2 = prior.base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    source_rows = prior._source_rows_by_window()
    baselines = prior._load_baselines()
    results, target_trades_by_window = _run_windows(baselines, source_rows)
    aggregate = prior._aggregate_results(results)
    target_summary = prior._target_summary(target_trades_by_window)
    source_family_summary = _source_family_summary(target_trades_by_window)
    gate4 = prior._gate4_decision(aggregate, results, target_summary)
    if not source_family_summary["all_selected_have_min_family_count"]:
        gate4["gates"]["source_family_min_count_passed"] = False
        gate4["passed"] = False
        gate4["decision"] = "rejected_independent_source_family_count_invariant_failed"
        gate4["rationale"] = "At least one selected trade failed the independent source-family count invariant."
    else:
        gate4["gates"]["source_family_min_count_passed"] = True
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
            "min_source_family_count": MIN_SOURCE_FAMILY_COUNT,
            "source_families": SOURCE_FAMILIES,
            "base_notional_usd": prior.BASE_NOTIONAL_USD,
            "hold_days": prior.HOLD_DAYS,
            "max_paper_trades_per_day": prior.MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": prior.SAME_TICKER_COOLDOWN_DAYS,
        },
        "production_impact": PRODUCTION_IMPACT,
        "gate2": gate2,
        "gate3": {
            "survival_floor": 0.05,
            "new_core_filter_added": False,
            "candidate_pool_source_family_admission_only": True,
        },
        "aggregate": aggregate,
        "results": results,
        "target_summary": target_summary,
        "target_trades_by_window": target_trades_by_window,
        "source_family_summary": source_family_summary,
        "gate4": gate4,
        "anti_js": "No JavaScript was used.",
    }

    prior._write_json(OUT_JSON, payload)
    prior._write_json(BEFORE_JSON, aggregate["before"])
    prior._write_json(AFTER_JSON, aggregate["after"])
    record = _experiment_log_record(payload)
    prior._write_json(LOG_JSON, record)
    _write_artifact(payload)
    _update_ticket(TICKET_JSON, payload)
    _update_ticket(DOC_TICKET_JSON, payload)
    _upsert_registry(payload)
    prior.base._upsert_jsonl(EXPERIMENT_LOG, record)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": gate4["decision"],
                "aggregate": aggregate["comparison"],
                "source_family_summary": source_family_summary,
                "anti_js": payload["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
