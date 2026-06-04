"""exp-20260604-008: lagged independent accepted-source consensus scout.

Replay-only alpha search. The current accepted same-date independent-source
consensus is fixed as comparator, then this experiment tests one timing change:
a current accepted source row may be confirmed by another independent accepted
source family from the same ticker in the prior three trading days.

No production code, shared adapter, live orders, ranking, sizing, exits, source
artifacts, source-family map, notional, hold period, or cooldown is changed.
No JavaScript is used.
"""

from __future__ import annotations

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
for import_path in (REPO_ROOT, EXPERIMENTS_DIR, QUANT_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260603_014_accepted_consensus_independent_source_family as same_day  # noqa: E402


EXPERIMENT_ID = "exp-20260604-008"
STEM = "lagged_independent_source_consensus"
TRIAL_FAMILY = "accepted_free_data_cross_source_consensus_source_timing"
TRIAL_VARIANT_ID = "lagged_prior_3_trading_days_v1"
CHANGED_VARIABLE = "lagged_independent_source_family_confirmation_prior_3_trading_days"
RULE_VERSION = "lagged_independent_source_family_confirmation_prior_3d_v1"
PRIOR_CONFIRMATION_TRADING_DAYS = 3

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

ACCEPTED_COMPARATOR_ID = "exp-20260603-014"
ACCEPTED_COMPARATOR_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / ACCEPTED_COMPARATOR_ID
    / "accepted_consensus_independent_source_family.json"
)

PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.25,
    "expected_pnl_delta": 4500.0,
    "main_failure_modes": [
        "window_regression",
        "accepted_comparator_not_beaten",
        "lagged_confirmation_adds_stale_noise",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Playbook permits a materially different source-timing construction "
        "after same-date source-family consensus. This uses only already "
        "accepted source families and tests whether recent independent "
        "confirmation is useful."
    ),
    "recorded_at": "2026-06-04T08:11:41+00:00",
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
        "This experiment changes no production code. A retained result would "
        "require the shared accepted free-data consensus adapter to implement "
        "the same lagged source-family timing rule in historical replay and "
        "daily production, with parity tests, before any report queue, paper "
        "notional, candidate priority, or order surface could change."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    try:
        return str(Path(path).resolve().relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=True, indent=2, sort_keys=True)
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


def _configure_same_day_modules() -> None:
    same_day._configure_prior_module()


def _date_order(snapshot: dict[str, Any], start: str, end: str) -> list[str]:
    return [
        date
        for date in same_day.prior.base.shadow._trading_dates(snapshot)
        if start <= date <= end
    ]


def _lagged_rows_for_ticker(
    *,
    label: str,
    ticker: str,
    current_date: str,
    date_idx: int,
    dates: list[str],
    rows_by_key: dict[tuple[str, str], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    first_idx = max(0, date_idx - PRIOR_CONFIRMATION_TRADING_DAYS)
    for source_date in dates[first_idx : date_idx + 1]:
        for row in rows_by_key.get((source_date, ticker), []):
            row_copy = dict(row)
            row_copy["timing_role"] = "current" if source_date == current_date else "prior_confirmation"
            row_copy["confirmation_lag_trading_days"] = date_idx - dates.index(source_date)
            row_copy["lagged_consensus_window_label"] = label
            rows.append(row_copy)
    return rows


def _source_family(source_name: str) -> str:
    return same_day.SOURCE_FAMILIES.get(source_name, source_name)


def _source_family_map(source_names: list[str]) -> dict[str, list[str]]:
    family_map: dict[str, list[str]] = {}
    for source_name in source_names:
        family_map.setdefault(_source_family(source_name), []).append(source_name)
    return {family: sorted(names) for family, names in sorted(family_map.items())}


def _lagged_consensus_candidates_for_window(
    label: str,
    snapshot: dict[str, Any],
    cfg: dict[str, str],
    source_rows_by_window: dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
) -> list[dict[str, Any]]:
    rows_by_key = source_rows_by_window.get(label, {})
    dates = _date_order(snapshot, cfg["start"], cfg["end"])
    date_to_idx = {date: idx for idx, date in enumerate(dates)}
    candidates: list[dict[str, Any]] = []

    for (current_date, ticker), current_rows in sorted(rows_by_key.items()):
        date_idx = date_to_idx.get(current_date)
        if date_idx is None or not current_rows:
            continue
        source_rows = _lagged_rows_for_ticker(
            label=label,
            ticker=ticker,
            current_date=current_date,
            date_idx=date_idx,
            dates=dates,
            rows_by_key=rows_by_key,
        )
        source_names = sorted({str(row["source_name"]) for row in source_rows})
        source_families = sorted({_source_family(source_name) for source_name in source_names})
        current_source_names = sorted({str(row["source_name"]) for row in current_rows})
        current_families = sorted({_source_family(source_name) for source_name in current_source_names})
        prior_rows = [row for row in source_rows if row.get("timing_role") == "prior_confirmation"]
        prior_families = sorted({_source_family(str(row["source_name"])) for row in prior_rows})
        has_lagged_independent_confirmation = any(
            family not in set(current_families) for family in prior_families
        )
        if len(source_families) < same_day.MIN_SOURCE_FAMILY_COUNT:
            continue

        candidates.append(
            {
                "date": current_date,
                "ticker": ticker,
                "source_count": len(source_names),
                "source_family_count": len(source_families),
                "current_source_count": len(current_source_names),
                "current_source_family_count": len(current_families),
                "prior_confirmation_source_count": len({str(row["source_name"]) for row in prior_rows}),
                "prior_confirmation_family_count": len(prior_families),
                "has_lagged_independent_confirmation": has_lagged_independent_confirmation,
                "source_names": source_names,
                "source_families": source_families,
                "current_source_names": current_source_names,
                "current_source_families": current_families,
                "prior_confirmation_source_families": prior_families,
                "source_family_map": _source_family_map(source_names),
                "source_experiment_ids": {
                    source_name: same_day.SOURCE_EXPERIMENT_IDS[source_name]
                    for source_name in source_names
                },
                "source_rows": sorted(
                    source_rows,
                    key=lambda row: (
                        int(row.get("confirmation_lag_trading_days") or 0),
                        str(row.get("source_name") or ""),
                    ),
                ),
                "fundamental_growth_rs_score": same_day.prior._extract_source_numeric(
                    source_rows, "fundamental_growth_rs_score"
                ),
                "alpha_score": same_day.prior._extract_source_numeric(source_rows, "alpha_score"),
                "volume_breadth_breakout_score": same_day.prior._extract_source_numeric(
                    source_rows, "volume_breadth_breakout_score"
                ),
                "finra_candidate_selection_score": same_day.prior._extract_source_numeric(
                    source_rows, "candidate_selection_score"
                ),
                "source_agreement_rule": (
                    "current_ticker_selected_by_one_accepted_source_and_confirmed_by_"
                    "another_independent_accepted_source_family_within_prior_3_trading_days"
                ),
                "known_at": f"{current_date}T21:00:00Z",
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
            -int(row["current_source_family_count"]),
            -int(row["source_count"]),
            0 if row["has_lagged_independent_confirmation"] else 1,
            "+".join(row["source_families"]),
            "+".join(row["current_source_names"]),
            str(row["ticker"]),
        ),
    )


def _select_target_trades(
    snapshot: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selected, diagnostics = same_day.prior._select_target_trades(snapshot, candidates)
    diagnostics["lagged_independent_selected_count"] = sum(
        1 for row in selected if row.get("has_lagged_independent_confirmation")
    )
    diagnostics["source_family_combo_counts_selected"] = dict(
        sorted(Counter("+".join(row.get("source_families") or []) for row in selected).items())
    )
    return selected, diagnostics


def _run_lagged_windows(
    baselines: dict[str, dict[str, Any]],
    source_rows_by_window: dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    results: list[dict[str, Any]] = []
    target_trades_by_window: dict[str, list[dict[str, Any]]] = {}
    for label, cfg in same_day.prior.base.WINDOWS.items():
        snapshot = same_day.prior.base.shadow._load_snapshot(cfg["snapshot"])
        candidates = _lagged_consensus_candidates_for_window(
            label,
            snapshot,
            cfg,
            source_rows_by_window,
        )
        target_trades, target_diagnostics = _select_target_trades(snapshot, candidates)
        before_result = baselines[label]["result"]
        before = baselines[label]["metrics"]
        overlay = same_day.prior.base._overlay_from_paper_trades(before_result, target_trades)
        after = same_day.prior.base.overlay_helper._metrics_with_overlay(before_result, overlay)
        raw_delta = same_day.prior.base.overlay_helper._delta(after, before)
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
                "target_trade_pnl_usd": sum(_safe_float(row.get("pnl")) for row in target_trades),
                "raw_lagged_consensus_candidate_count": len(candidates),
                "lagged_independent_candidate_count": sum(
                    1 for row in candidates if row.get("has_lagged_independent_confirmation")
                ),
                "target_diagnostics": target_diagnostics,
            }
        )
        target_trades_by_window[label] = target_trades
    return results, target_trades_by_window


def _aggregate_vs_comparator(
    after_results: list[dict[str, Any]],
    comparator_results: list[dict[str, Any]],
) -> dict[str, Any]:
    comparator_by_label = {row["label"]: row for row in comparator_results}
    rows = []
    for row in after_results:
        comparator = comparator_by_label[row["label"]]
        delta = same_day.prior.base.overlay_helper._delta(row["after"], comparator["after"])
        rows.append(
            {
                "label": row["label"],
                "expected_value_score_delta": delta["expected_value_score"],
                "strategy_total_pnl_delta": delta["total_pnl"],
                "total_pnl_delta": delta["total_pnl"],
                "max_drawdown_delta": delta["max_drawdown_pct"],
            }
        )

    after_ev = sum(_safe_float(row["after"].get("expected_value_score")) for row in after_results)
    comparator_ev = sum(
        _safe_float(row["after"].get("expected_value_score")) for row in comparator_results
    )
    after_pnl = sum(_safe_float(row["after"].get("total_pnl")) for row in after_results)
    comparator_pnl = sum(_safe_float(row["after"].get("total_pnl")) for row in comparator_results)
    return {
        "comparison": {
            "expected_value_score_delta": round(after_ev - comparator_ev, 6),
            "strategy_total_pnl_delta": round(after_pnl - comparator_pnl, 2),
            "total_pnl_delta": round(after_pnl - comparator_pnl, 2),
            "windows_ev_improved": sum(1 for row in rows if row["expected_value_score_delta"] > 0.0),
            "windows_ev_regressed": sum(1 for row in rows if row["expected_value_score_delta"] < 0.0),
            "windows_pnl_improved": sum(1 for row in rows if row["strategy_total_pnl_delta"] > 0.0),
            "windows_pnl_regressed": sum(1 for row in rows if row["strategy_total_pnl_delta"] < 0.0),
            "per_window": rows,
        }
    }


def _lagged_source_summary(target_trades_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    rows = [row for trades in target_trades_by_window.values() for row in trades]
    lagged_rows = [row for row in rows if row.get("has_lagged_independent_confirmation")]
    family_combo_counts = Counter("+".join(row.get("source_families") or []) for row in rows)
    raw_combo_counts = Counter("+".join(row.get("source_names") or []) for row in rows)
    return {
        "prior_confirmation_trading_days": PRIOR_CONFIRMATION_TRADING_DAYS,
        "total_trade_count": len(rows),
        "lagged_independent_selected_trade_count": len(lagged_rows),
        "lagged_independent_selected_trade_count_by_window": {
            label: sum(1 for row in trades if row.get("has_lagged_independent_confirmation"))
            for label, trades in target_trades_by_window.items()
        },
        "lagged_independent_selected_trade_pnl_usd": round(
            sum(_safe_float(row.get("pnl")) for row in lagged_rows),
            2,
        ),
        "selected_family_combo_counts": dict(sorted(family_combo_counts.items())),
        "selected_raw_source_combo_counts": dict(sorted(raw_combo_counts.items())),
        "all_selected_have_min_family_count": all(
            len(row.get("source_families") or []) >= same_day.MIN_SOURCE_FAMILY_COUNT
            for row in rows
        ),
    }


def _gate4(
    aggregate: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
    vs_comparator: dict[str, Any],
    lagged_summary: dict[str, Any],
) -> dict[str, Any]:
    base_gate = same_day.prior._gate4_decision(aggregate, results, target_summary)
    comp = vs_comparator["comparison"]
    comparator_passed = (
        comp["expected_value_score_delta"] > 0.0
        and comp["strategy_total_pnl_delta"] > 0.0
        and comp["windows_ev_improved"] == 3
        and comp["windows_pnl_improved"] == 3
    )
    lagged_sample_passed = int(lagged_summary["lagged_independent_selected_trade_count"]) > 0
    source_family_passed = bool(lagged_summary["all_selected_have_min_family_count"])
    gates = {
        **base_gate["gates"],
        "beats_current_accepted_same_day_consensus_comparator": comparator_passed,
        "lagged_independent_selected_trade_count_positive": lagged_sample_passed,
        "source_family_min_count_passed": source_family_passed,
    }
    passed = bool(base_gate["passed"] and comparator_passed and lagged_sample_passed and source_family_passed)
    if passed:
        decision = "positive_replay_lead_requires_lagged_consensus_shared_adapter"
        rationale = (
            "Lagged independent-source timing improved core and the current "
            "accepted same-date consensus comparator across all three windows. "
            "Promotion would require a shared production/backtest adapter first."
        )
    elif not lagged_sample_passed:
        decision = "rejected_lagged_consensus_no_lagged_selected_rows"
        rationale = "The lagged timing rule produced no selected lagged-confirmation trades."
    elif not comparator_passed:
        decision = "rejected_lagged_consensus_did_not_beat_accepted_same_day_comparator"
        rationale = (
            "The lagged timing variant did not beat the current accepted "
            "same-date independent-source consensus comparator across all "
            "three windows."
        )
    elif not source_family_passed:
        decision = "rejected_lagged_consensus_source_family_invariant_failed"
        rationale = "At least one selected trade failed the independent source-family invariant."
    else:
        decision = "rejected_lagged_consensus_gate4_failed"
        rationale = base_gate["rationale"]
    return {
        "passed": passed,
        "decision": decision,
        "gates": gates,
        "rationale": rationale,
        "min_survival_rate": base_gate.get("min_survival_rate"),
        "max_drawdown_delta": base_gate.get("max_drawdown_delta"),
        "requires_parity_before_promotion": True,
        "accepted_comparator": ACCEPTED_COMPARATOR_ID,
    }


def _preflight_payload() -> dict[str, Any]:
    return {
        "alpha_hypothesis": (
            "A current accepted free-data source row may be stronger when the "
            "same ticker had another independent accepted source-family row in "
            "the prior three trading days. This tests source timing, not a new "
            "source count or source set."
        ),
        "category": "entry/candidate_pool",
        "playbook_alignment": (
            "The playbook rejects nearby source-family additions but explicitly "
            "allows a materially different source-timing construction after the "
            "accepted same-date independent-source consensus."
        ),
        "nearby_prior_experiments": [
            "exp-20260603-014",
            "exp-20260603-015",
            "exp-20260604-002",
            "exp-20260604-006",
            "exp-20260604-007",
        ],
        "prior_difference": (
            "exp-20260603-014/015 accepted same-date independent-source "
            "consensus. exp-20260604-007 tested broad-market prior lead as a "
            "new source and had zero selected overlap. This run keeps the "
            "accepted source families fixed and changes only the timing relation "
            "among accepted same-ticker source rows."
        ),
        "single_causal_variable": CHANGED_VARIABLE,
        "acceptance_criteria": {
            "canonical_windows": list(same_day.prior.base.WINDOWS.keys()),
            "aggregate_expected_value_delta_vs_core": "> 0",
            "aggregate_pnl_delta_vs_core": "> 0",
            "per_window_expected_value_delta_vs_core": "3 of 3 windows > 0",
            "per_window_pnl_delta_vs_core": "3 of 3 windows > 0",
            "must_beat_current_accepted_same_day_consensus_comparator": True,
            "per_window_delta_vs_accepted_comparator": "3 of 3 windows > 0",
            "minimum_target_trades": same_day.prior.MIN_TARGET_TRADES,
            "minimum_target_windows": same_day.prior.MIN_TARGET_WINDOWS,
            "max_drawdown_drift": same_day.prior.MAX_DRAWDOWN_WORSE,
            "survival_rate_floor": 0.05,
            "max_single_positive_share": same_day.prior.MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi_max": same_day.prior.MAX_POSITIVE_HHI,
            "source_family_min_count": same_day.MIN_SOURCE_FAMILY_COUNT,
        },
        "reproducibility": (
            ".venv\\Scripts\\python.exe -B "
            "quant\\experiments\\exp_20260604_008_lagged_independent_source_consensus.py"
        ),
    }


def _experiment_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    comparison = payload["aggregate"]["comparison"]
    accepted = payload["vs_accepted_comparator"]["comparison"]
    actual_success = 1 if payload["gate4"]["passed"] else 0
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["completed_at"],
        "lane": "alpha_search",
        "status": "accepted" if payload["gate4"]["passed"] else "rejected",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "change_type": "default_off_paper_adapter_source_timing_alpha",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "prior_trial_count": 8,
        "nearby_prior_experiments": payload["preflight"]["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": "high",
        "new_evidence_type": "materially_different_source_timing_construction",
        "decision": payload["gate4"]["decision"],
        "accepted": bool(payload["gate4"]["passed"]),
        "rejection_reason": None if payload["gate4"]["passed"] else payload["gate4"]["rationale"],
        "prediction": PREDICTION,
        "calibration": {
            "actual_decision": payload["gate4"]["decision"],
            "actual_success": actual_success,
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": round((PREDICTION["success_probability"] - actual_success) ** 2, 6),
            "expected_ev_delta": PREDICTION["expected_ev_delta"],
            "actual_ev_delta": comparison["expected_value_score_delta"],
            "ev_prediction_error": round(
                comparison["expected_value_score_delta"] - PREDICTION["expected_ev_delta"],
                6,
            ),
            "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
            "actual_pnl_delta": comparison["strategy_total_pnl_delta"],
            "pnl_prediction_error": round(
                comparison["strategy_total_pnl_delta"] - PREDICTION["expected_pnl_delta"],
                2,
            ),
            "realized_failure_mode": None if payload["gate4"]["passed"] else payload["gate4"]["decision"],
        },
        "production_impact": PRODUCTION_IMPACT,
        "requires_parity_before_promotion": True,
        "metrics": {
            "aggregate_expected_value_before": payload["aggregate"]["before"]["expected_value_score"],
            "aggregate_expected_value_after": payload["aggregate"]["after"]["expected_value_score"],
            "aggregate_expected_value_delta": comparison["expected_value_score_delta"],
            "aggregate_strategy_total_pnl_before": payload["aggregate"]["before"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_after": payload["aggregate"]["after"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_delta": comparison["strategy_total_pnl_delta"],
            "accepted_comparator_ev_delta": accepted["expected_value_score_delta"],
            "accepted_comparator_pnl_delta": accepted["strategy_total_pnl_delta"],
            "accepted_comparator_windows_ev_improved": accepted["windows_ev_improved"],
            "accepted_comparator_windows_pnl_improved": accepted["windows_pnl_improved"],
            "target_trade_count": payload["target_summary"]["target_trade_count"],
            "target_trade_pnl_usd": payload["target_summary"]["target_trade_pnl_usd"],
            "lagged_independent_selected_trade_count": payload["lagged_source_summary"][
                "lagged_independent_selected_trade_count"
            ],
            "lagged_independent_selected_trade_pnl_usd": payload["lagged_source_summary"][
                "lagged_independent_selected_trade_pnl_usd"
            ],
            "max_drawdown_delta": payload["gate4"]["max_drawdown_delta"],
            "max_single_positive_share": payload["target_summary"]["max_single_positive_share"],
            "positive_pnl_hhi": payload["target_summary"]["positive_pnl_hhi"],
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
                "lagged_independent_selected_trade_count": payload["lagged_source_summary"][
                    "lagged_independent_selected_trade_count_by_window"
                ].get(row["label"], 0),
            }
            for row in payload["results"]
        ],
        "artifact_path": _repo_rel(OUT_JSON),
        "anti_js": "No JavaScript was used.",
    }


def _write_card(payload: dict[str, Any]) -> None:
    comp = payload["aggregate"]["comparison"]
    accepted = payload["vs_accepted_comparator"]["comparison"]
    lagged = payload["lagged_source_summary"]
    lines = [
        f"# {EXPERIMENT_ID} Lagged independent-source consensus",
        "",
        "## Decision",
        "",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Rationale: {payload['gate4']['rationale']}",
        "",
        "## Three-window result",
        "",
        f"- Vs core: EV `{comp['expected_value_score_delta']:+.4f}`, PnL `${comp['strategy_total_pnl_delta']:+,.2f}`",
        f"- Vs accepted same-date consensus: EV `{accepted['expected_value_score_delta']:+.4f}`, PnL `${accepted['strategy_total_pnl_delta']:+,.2f}`",
        f"- Lagged independent selected trades: `{lagged['lagged_independent_selected_trade_count']}`",
        "",
        "## Production impact",
        "",
        "- Replay-only; no production code or live/default order behavior changed.",
        "- Positive retention would require a shared lagged-consensus adapter and parity tests first.",
        "",
        "No JavaScript was used.",
        "",
    ]
    _write_text(CARD_MD, "\n".join(lines))
    _write_text(ARTIFACT_MD, "\n".join(lines))


def _update_ticket(path: Path, payload: dict[str, Any]) -> None:
    ticket = _load_json(path) if path.exists() else {}
    ticket.update(
        {
            "id": EXPERIMENT_ID,
            "experiment_id": EXPERIMENT_ID,
            "status": "completed",
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "artifact": _repo_rel(OUT_JSON),
            "markdown_artifact": _repo_rel(ARTIFACT_MD),
            "card": _repo_rel(CARD_MD),
            "log": _repo_rel(LOG_JSON),
            "production_impact": PRODUCTION_IMPACT,
            "gate4": payload["gate4"],
        }
    )
    _write_json(path, ticket)


def _update_manifest(payload: dict[str, Any]) -> None:
    manifest = _load_json(MANIFEST_JSON) if MANIFEST_JSON.exists() else {}
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
                _repo_rel(ARTIFACT_MD),
                _repo_rel(TICKET_JSON),
            ],
        }
    )
    _write_json(MANIFEST_JSON, manifest)


def _upsert_registry(payload: dict[str, Any]) -> None:
    if not REGISTRY_JSON.exists():
        return
    registry = _load_json(REGISTRY_JSON)
    experiments = registry.get("experiments")
    if not isinstance(experiments, list):
        return
    for item in experiments:
        if isinstance(item, dict) and item.get("experiment_id") == EXPERIMENT_ID:
            item["status"] = "completed"
            item["decision"] = payload["gate4"]["decision"]
            item["completed_at"] = payload["completed_at"]
            item["artifact"] = _repo_rel(OUT_JSON)
            item["log"] = _repo_rel(LOG_JSON)
            item["aggregate_expected_value_delta"] = payload["aggregate"]["comparison"][
                "expected_value_score_delta"
            ]
            item["aggregate_strategy_total_pnl_delta"] = payload["aggregate"]["comparison"][
                "strategy_total_pnl_delta"
            ]
            item["updated_at"] = payload["completed_at"]
            break
    registry["updated_at"] = payload["completed_at"]
    _write_json(REGISTRY_JSON, registry)


def main() -> None:
    _configure_same_day_modules()
    gate2 = same_day.prior.base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    source_rows = same_day.prior._source_rows_by_window()
    baselines = same_day.prior._load_baselines()
    accepted_results, accepted_trades = same_day._run_windows(baselines, source_rows)
    accepted_aggregate = same_day.prior._aggregate_results(accepted_results)
    results, target_trades_by_window = _run_lagged_windows(baselines, source_rows)
    aggregate = same_day.prior._aggregate_results(results)
    target_summary = same_day.prior._target_summary(target_trades_by_window)
    lagged_summary = _lagged_source_summary(target_trades_by_window)
    vs_comparator = _aggregate_vs_comparator(results, accepted_results)
    gate4 = _gate4(aggregate, results, target_summary, vs_comparator, lagged_summary)
    completed_at = _utc_now()

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": completed_at,
        "completed_at": completed_at,
        "lane": "alpha_search",
        "preflight": _preflight_payload(),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "entry/candidate_pool: lagged independent accepted-source "
                "confirmation may improve same-ticker consensus timing."
            ),
            "2_history_check": {
                "exp-20260603-014": "Accepted same-date independent-source consensus.",
                "exp-20260603-015": "Promoted same-date consensus to shared default-off paper adapter.",
                "exp-20260604-002": "Broad-market source-family addition had zero selected overlap.",
                "exp-20260604-007": "Broad-market prior-lead source timing had zero selected trades.",
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Use docs/backtesting.md three fixed windows; accept only if "
                "the variant beats core and current same-date accepted consensus "
                "in all windows, with concentration and survival guardrails."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260604_008_lagged_independent_source_consensus.py"
            ),
        },
        "source_files": {
            name: _repo_rel(REPO_ROOT / path) for name, path in same_day.SOURCE_FILES.items()
        },
        "rule": {
            "rule_version": RULE_VERSION,
            "prior_confirmation_trading_days": PRIOR_CONFIRMATION_TRADING_DAYS,
            "min_source_family_count": same_day.MIN_SOURCE_FAMILY_COUNT,
            "source_families": same_day.SOURCE_FAMILIES,
            "base_notional_usd": same_day.prior.BASE_NOTIONAL_USD,
            "hold_days": same_day.prior.HOLD_DAYS,
            "max_paper_trades_per_day": same_day.prior.MAX_PAPER_TRADES_PER_DAY,
            "same_ticker_cooldown_days": same_day.prior.SAME_TICKER_COOLDOWN_DAYS,
        },
        "production_impact": PRODUCTION_IMPACT,
        "prediction": PREDICTION,
        "gate2": gate2,
        "gate3": {
            "survival_floor": 0.05,
            "new_core_filter_added": False,
            "candidate_pool_source_timing_admission_only": True,
            "min_survival_rate": min(_safe_float(row["before"].get("survival_rate")) for row in results),
        },
        "aggregate": aggregate,
        "accepted_comparator": {
            "experiment_id": ACCEPTED_COMPARATOR_ID,
            "source_artifact": _repo_rel(ACCEPTED_COMPARATOR_JSON),
            "aggregate": accepted_aggregate,
            "target_summary": same_day.prior._target_summary(accepted_trades),
        },
        "vs_accepted_comparator": vs_comparator,
        "results": results,
        "target_summary": target_summary,
        "lagged_source_summary": lagged_summary,
        "target_trades_by_window": target_trades_by_window,
        "gate4": gate4,
        "anti_js": "No JavaScript was used.",
    }

    _write_json(OUT_JSON, payload)
    _write_json(BEFORE_JSON, aggregate["before"])
    _write_json(AFTER_JSON, aggregate["after"])
    record = _experiment_log_record(payload)
    _write_json(LOG_JSON, record)
    _write_card(payload)
    _update_ticket(TICKET_JSON, payload)
    _update_manifest(payload)
    _upsert_registry(payload)
    same_day.prior.base._upsert_jsonl(EXPERIMENT_LOG, record)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": gate4["decision"],
                "aggregate_vs_core": aggregate["comparison"],
                "aggregate_vs_accepted_same_day_consensus": vs_comparator["comparison"],
                "lagged_source_summary": lagged_summary,
                "anti_js": "No JavaScript was used.",
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
