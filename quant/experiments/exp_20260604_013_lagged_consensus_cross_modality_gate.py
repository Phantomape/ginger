"""exp-20260604-013: lagged consensus cross-modality gate scout.

Replay-only alpha search. The accepted lagged free-data consensus adapter from
exp-20260604-009 is fixed as comparator. This experiment changes one variable:
selected paper trades must have current and prior independent source families
from disjoint information modalities.

No shared adapter, production path, live orders, source set, family map, lag
window, cooldown, notional, ranking, hold period, exits, LLM, or news behavior
is changed. No JavaScript is used.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENTS_DIR = REPO_ROOT / "quant" / "experiments"
QUANT_DIR = REPO_ROOT / "quant"
for import_path in (REPO_ROOT, EXPERIMENTS_DIR, QUANT_DIR):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import exp_20260604_008_lagged_independent_source_consensus as lagged  # noqa: E402


EXPERIMENT_ID = "exp-20260604-013"
STEM = "lagged_consensus_cross_modality_gate"
TRIAL_FAMILY = "accepted_free_data_cross_source_consensus_source_timing_quality_gate"
TRIAL_VARIANT_ID = "lagged_cross_modality_current_prior_gate_v1"
CHANGED_VARIABLE = "lagged_consensus_cross_modality_source_timing_gate_v1"
RULE_VERSION = "accepted_lagged_consensus_cross_modality_gate_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260604_013_{STEM}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

ACCEPTED_COMPARATOR_ID = "exp-20260604-009"
ACCEPTED_COMPARATOR_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / ACCEPTED_COMPARATOR_ID
    / "exp_20260604_009_lagged_consensus_shared_adapter.json"
)

SOURCE_FAMILY_MODALITIES = {
    "alpha_score_market_regime": "cross_sectional_ohlcv_ranking",
    "companyfacts_growth_quality": "fundamental_companyfacts",
    "finra_short_pressure": "short_interest_pressure",
    "volume_breadth_breakout": "ohlcv_breadth_breakout",
}

PREDICTION = {
    "success_probability": 0.28,
    "expected_ev_delta": 0.10,
    "expected_pnl_delta": 1500.0,
    "main_failure_modes": [
        "accepted_adapter_comparator_not_beaten",
        "thin_sample",
        "window_regression",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Recent lagged timing was strong, but nearby rank and support retunes "
        "failed. Cross-modality is a distinct source-timing relation using "
        "only existing production-visible accepted source families."
    ),
    "recorded_at": "2026-06-04T13:06:50+00:00",
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
        "require the shared free-data consensus adapter to compute the same "
        "cross-modality source-timing gate in daily production and historical "
        "replay, with parity tests, before any paper queue or order surface "
        "could change."
    ),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _repo_rel(path: Path | str) -> str:
    try:
        return Path(path).resolve().relative_to(REPO_ROOT).as_posix()
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


def _modalities(families: list[str] | tuple[str, ...]) -> set[str]:
    return {SOURCE_FAMILY_MODALITIES.get(str(family), str(family)) for family in families}


def _cross_modality_context(trade: dict[str, Any]) -> dict[str, Any]:
    current_families = sorted(str(value) for value in trade.get("current_source_families") or [])
    prior_families = sorted(str(value) for value in trade.get("prior_confirmation_source_families") or [])
    current_modalities = sorted(_modalities(current_families))
    prior_modalities = sorted(_modalities(prior_families))
    passed = bool(current_modalities and prior_modalities and set(current_modalities).isdisjoint(prior_modalities))
    return {
        "cross_modality_rule_version": RULE_VERSION,
        "cross_modality_known_at": "current signal date after close, from bounded prior source snapshot history",
        "cross_modality_trade_enabled": False,
        "cross_modality_alters_orders": False,
        "cross_modality_gate_pass_v1": passed,
        "cross_modality_status": "passed" if passed else "failed",
        "current_source_families": current_families,
        "prior_confirmation_source_families": prior_families,
        "current_source_modalities": current_modalities,
        "prior_confirmation_source_modalities": prior_modalities,
    }


def _filter_cross_modality_trades(
    comparator_trades: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    filtered: dict[str, list[dict[str, Any]]] = {}
    diagnostics: dict[str, Any] = {
        "source_trade_count_by_window": {},
        "target_trade_count_by_window": {},
        "status_counts_by_window": {},
        "family_pair_counts": {},
        "modality_pair_counts": {},
        "sample_trades_by_window": {},
    }
    family_pairs: Counter[str] = Counter()
    modality_pairs: Counter[str] = Counter()

    for label, trades in comparator_trades.items():
        selected: list[dict[str, Any]] = []
        status_counts: Counter[str] = Counter()
        samples: list[dict[str, Any]] = []
        for trade in trades:
            context = _cross_modality_context(trade)
            status_counts[str(context["cross_modality_status"])] += 1
            family_pairs[
                "+".join(context["current_source_families"])
                + " <= "
                + "+".join(context["prior_confirmation_source_families"])
            ] += 1
            modality_pairs[
                "+".join(context["current_source_modalities"])
                + " <= "
                + "+".join(context["prior_confirmation_source_modalities"])
            ] += 1
            if context["cross_modality_gate_pass_v1"]:
                row = {
                    **trade,
                    **context,
                    "strategy": "lagged_free_data_consensus_cross_modality_gate",
                    "rule_version": RULE_VERSION,
                    "trade_enabled": False,
                    "alters_orders": False,
                }
                selected.append(row)
                if len(samples) < 20:
                    samples.append(row)
        filtered[label] = selected
        diagnostics["source_trade_count_by_window"][label] = len(trades)
        diagnostics["target_trade_count_by_window"][label] = len(selected)
        diagnostics["status_counts_by_window"][label] = dict(sorted(status_counts.items()))
        diagnostics["sample_trades_by_window"][label] = samples

    source_count = sum(diagnostics["source_trade_count_by_window"].values())
    target_count = sum(diagnostics["target_trade_count_by_window"].values())
    diagnostics["source_trade_count"] = source_count
    diagnostics["target_trade_count"] = target_count
    diagnostics["target_source_share"] = round(target_count / source_count, 6) if source_count else None
    diagnostics["family_pair_counts"] = dict(sorted(family_pairs.items()))
    diagnostics["modality_pair_counts"] = dict(sorted(modality_pairs.items()))
    return filtered, diagnostics


def _results_from_trades(
    baselines: dict[str, dict[str, Any]],
    target_trades_by_window: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for label, cfg in lagged.same_day.prior.base.WINDOWS.items():
        before_result = baselines[label]["result"]
        before = baselines[label]["metrics"]
        target_trades = target_trades_by_window.get(label, [])
        overlay = lagged.same_day.prior.base._overlay_from_paper_trades(before_result, target_trades)
        after = lagged.same_day.prior.base.overlay_helper._metrics_with_overlay(before_result, overlay)
        raw_delta = lagged.same_day.prior.base.overlay_helper._delta(after, before)
        results.append(
            {
                "label": label,
                "start": cfg["start"],
                "end": cfg["end"],
                "snapshot": cfg["snapshot"],
                "before": before,
                "after": after,
                "comparison": {
                    "expected_value_score_delta": raw_delta["expected_value_score"],
                    "strategy_total_pnl_delta": raw_delta["total_pnl"],
                    "total_pnl_delta": raw_delta["total_pnl"],
                    "max_drawdown_delta": raw_delta["max_drawdown_pct"],
                    "raw_delta": raw_delta,
                },
                "target_trade_count": len(target_trades),
                "target_trade_pnl_usd": round(sum(_safe_float(row.get("pnl")) for row in target_trades), 2),
            }
        )
    return results


def _aggregate_vs_comparator(
    after_results: list[dict[str, Any]],
    comparator_results: list[dict[str, Any]],
) -> dict[str, Any]:
    comparator_by_label = {row["label"]: row for row in comparator_results}
    rows = []
    for row in after_results:
        comparator = comparator_by_label[row["label"]]
        delta = lagged.same_day.prior.base.overlay_helper._delta(row["after"], comparator["after"])
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
    comparator_ev = sum(_safe_float(row["after"].get("expected_value_score")) for row in comparator_results)
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


def _gate4(
    aggregate: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
    vs_comparator: dict[str, Any],
    diagnostics: dict[str, Any],
) -> dict[str, Any]:
    base_gate = lagged.same_day.prior._gate4_decision(aggregate, results, target_summary)
    comp = vs_comparator["comparison"]
    comparator_passed = (
        comp["expected_value_score_delta"] > 0.0
        and comp["strategy_total_pnl_delta"] > 0.0
        and comp["windows_ev_improved"] == 3
        and comp["windows_pnl_improved"] == 3
    )
    sample_passed = int(diagnostics["target_trade_count"]) >= lagged.same_day.prior.MIN_TARGET_TRADES
    gates = {
        **base_gate["gates"],
        "beats_current_accepted_lagged_adapter": comparator_passed,
        "cross_modality_target_trade_count_passed": sample_passed,
    }
    passed = bool(base_gate["passed"] and comparator_passed and sample_passed)
    if passed:
        decision = "positive_replay_lead_requires_shared_cross_modality_adapter"
        rationale = (
            "The cross-modality source-timing gate beat the current accepted "
            "lagged consensus adapter across all three canonical windows. "
            "Promotion would require shared adapter parity first."
        )
    elif not comparator_passed:
        decision = "rejected_cross_modality_gate_underperformed_accepted_lagged_adapter"
        rationale = (
            "The cross-modality gate did not beat the current accepted "
            "exp-20260604-009 lagged consensus adapter across all three windows."
        )
    elif not sample_passed:
        decision = "rejected_cross_modality_gate_thin_sample"
        rationale = "The cross-modality gate did not clear the target trade-count floor."
    elif not base_gate["gates"].get("concentration_guard_passed", False):
        decision = "rejected_cross_modality_gate_concentration_failed"
        rationale = (
            "The cross-modality gate improved, but incremental positive PnL "
            "was too concentrated."
        )
    else:
        decision = "rejected_cross_modality_gate_gate4_failed"
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
            "Accepted lagged free-data consensus candidates should be cleaner "
            "when current and prior independent source families come from "
            "different information modalities."
        ),
        "category": "entry/candidate_pool",
        "playbook_alignment": (
            "The playbook prioritizes production-visible default-off paper "
            "adapters and allows materially different source-timing "
            "constructions. This avoids LLM soft-ranking, unavailable 13F/options "
            "coverage, source-family additions already rejected, and notional "
            "retunes around exp-20260604-009."
        ),
        "nearby_prior_experiments": [
            "exp-20260604-008",
            "exp-20260604-009",
            "exp-20260604-010",
            "exp-20260604-011",
            "exp-20260604-012",
        ],
        "prior_difference": (
            "exp-20260604-009 accepted lagged timing; exp-20260604-010 "
            "rejected rank priority; exp-20260604-011 and exp-20260604-012 "
            "rejected support layers due concentration. This run tests a "
            "different relation field: current/prior modality disjointness."
        ),
        "single_causal_variable": CHANGED_VARIABLE,
        "acceptance_criteria": {
            "canonical_windows": list(lagged.same_day.prior.base.WINDOWS.keys()),
            "before_comparator": ACCEPTED_COMPARATOR_ID,
            "aggregate_expected_value_delta_vs_accepted_adapter": "> 0",
            "aggregate_pnl_delta_vs_accepted_adapter": "> 0",
            "per_window_expected_value_delta_vs_accepted_adapter": "3 of 3 windows > 0",
            "per_window_pnl_delta_vs_accepted_adapter": "3 of 3 windows > 0",
            "minimum_target_trades": lagged.same_day.prior.MIN_TARGET_TRADES,
            "minimum_target_windows": lagged.same_day.prior.MIN_TARGET_WINDOWS,
            "max_drawdown_drift": lagged.same_day.prior.MAX_DRAWDOWN_WORSE,
            "survival_rate_floor": 0.05,
            "max_single_positive_share": lagged.same_day.prior.MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi_max": lagged.same_day.prior.MAX_POSITIVE_HHI,
        },
        "reproducibility": (
            ".venv\\Scripts\\python.exe -B "
            "quant\\experiments\\exp_20260604_013_lagged_consensus_cross_modality_gate.py"
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
        "hypothesis": payload["preflight"]["alpha_hypothesis"],
        "change_summary": "Tested a cross-modality source-timing gate on the accepted lagged free-data consensus adapter.",
        "change_type": "default_off_paper_candidate_pool_quality",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "prior_trial_count": 5,
        "nearby_prior_experiments": payload["preflight"]["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "production_visible_source_timing_relation_on_accepted_free_data_sources",
        "component": "quant/experiments/exp_20260604_013_lagged_consensus_cross_modality_gate.py",
        "parameters": {
            "source_family_modalities": SOURCE_FAMILY_MODALITIES,
            "gate": "current_source_modalities disjoint from prior_confirmation_source_modalities",
            "trade_enabled": False,
        },
        "before_metrics": payload["accepted_comparator"]["aggregate"]["after"],
        "after_metrics": payload["aggregate"]["after"],
        "delta_metrics": {
            "expected_value_score": accepted["expected_value_score_delta"],
            "total_pnl": accepted["strategy_total_pnl_delta"],
            "windows_ev_improved": accepted["windows_ev_improved"],
            "windows_pnl_improved": accepted["windows_pnl_improved"],
            "vs_core_expected_value_score": comparison["expected_value_score_delta"],
            "vs_core_total_pnl": comparison["strategy_total_pnl_delta"],
        },
        "prediction": PREDICTION,
        "calibration": {
            "actual_decision": payload["gate4"]["decision"],
            "actual_success": actual_success,
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": round((PREDICTION["success_probability"] - actual_success) ** 2, 6),
            "expected_ev_delta": PREDICTION["expected_ev_delta"],
            "actual_ev_delta": accepted["expected_value_score_delta"],
            "ev_prediction_error": round(accepted["expected_value_score_delta"] - PREDICTION["expected_ev_delta"], 6),
            "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
            "actual_pnl_delta": accepted["strategy_total_pnl_delta"],
            "pnl_prediction_error": round(accepted["strategy_total_pnl_delta"] - PREDICTION["expected_pnl_delta"], 2),
            "realized_failure_mode": None if payload["gate4"]["passed"] else payload["gate4"]["decision"],
        },
        "production_impact": PRODUCTION_IMPACT,
        "decision": payload["gate4"]["decision"],
        "rejection_reason": None if payload["gate4"]["passed"] else payload["gate4"]["rationale"],
        "next_retry_requires": [
            "new forward replacement-value rows",
            "materially different source relation beyond current/prior modality disjointness",
            "shared production/backtest adapter parity before any promotion",
        ],
        "related_files": [
            _repo_rel(Path(__file__)),
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(CARD_MD),
        ],
        "windows": [
            {
                "label": row["label"],
                "expected_value_before": payload["accepted_comparator"]["aggregate"]["after_by_window"][row["label"]][
                    "expected_value_score"
                ],
                "expected_value_after": row["after"]["expected_value_score"],
                "expected_value_delta": next(
                    item["expected_value_score_delta"]
                    for item in accepted["per_window"]
                    if item["label"] == row["label"]
                ),
                "strategy_total_pnl_delta": next(
                    item["strategy_total_pnl_delta"]
                    for item in accepted["per_window"]
                    if item["label"] == row["label"]
                ),
                "target_trade_count": row["target_trade_count"],
                "target_trade_pnl_usd": row["target_trade_pnl_usd"],
            }
            for row in payload["results"]
        ],
        "anti_js": "No JavaScript was used.",
    }


def _write_card(payload: dict[str, Any]) -> None:
    comp = payload["aggregate"]["comparison"]
    accepted = payload["vs_accepted_comparator"]["comparison"]
    diag = payload["cross_modality_diagnostics"]
    lines = [
        f"# {EXPERIMENT_ID} Lagged Consensus Cross-Modality Gate",
        "",
        "## Decision",
        "",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Rationale: {payload['gate4']['rationale']}",
        "",
        "## Three-Window Result",
        "",
        f"- Vs core EV/PnL: `{comp['expected_value_score_delta']:+.4f}` / `${comp['strategy_total_pnl_delta']:+,.2f}`",
        f"- Vs accepted lagged adapter EV/PnL: `{accepted['expected_value_score_delta']:+.4f}` / `${accepted['strategy_total_pnl_delta']:+,.2f}`",
        f"- Cross-modality trades: `{diag['target_trade_count']}` / `{diag['source_trade_count']}` "
        f"({diag['target_source_share']})",
        "",
        "| Window | EV Delta vs Accepted | PnL Delta vs Accepted | Target Trades |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in accepted["per_window"]:
        label = row["label"]
        lines.append(
            f"| {label} | {row['expected_value_score_delta']:+.4f} | "
            f"${row['strategy_total_pnl_delta']:+,.2f} | "
            f"{diag['target_trade_count_by_window'].get(label, 0)} |"
        )
    lines.extend(
        [
            "",
            "## Production Impact",
            "",
            "- Replay-only; no shared policy, run adapter, backtester adapter, orders, watchlists, core ranking, sizing, exits, LLM, or news behavior changed.",
            "- A positive result would require shared adapter parity before promotion.",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    _write_text(CARD_MD, "\n".join(lines))


def _update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "id": EXPERIMENT_ID,
            "experiment_id": EXPERIMENT_ID,
            "status": "completed",
            "decision": payload["gate4"]["decision"],
            "completed_at": payload["completed_at"],
            "artifact": _repo_rel(OUT_JSON),
            "card": _repo_rel(CARD_MD),
            "log": _repo_rel(LOG_JSON),
            "production_impact": PRODUCTION_IMPACT,
            "gate4": payload["gate4"],
            "result": {
                "aggregate_expected_value_delta_vs_accepted_adapter": payload["vs_accepted_comparator"]["comparison"][
                    "expected_value_score_delta"
                ],
                "aggregate_strategy_total_pnl_delta_vs_accepted_adapter": payload["vs_accepted_comparator"][
                    "comparison"
                ]["strategy_total_pnl_delta"],
                "decision": payload["gate4"]["decision"],
            },
        }
    )
    _write_json(TICKET_JSON, ticket)


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
                _repo_rel(TICKET_JSON),
            ],
        }
    )
    _write_json(MANIFEST_JSON, manifest)


def _update_registry(payload: dict[str, Any]) -> None:
    if not REGISTRY_JSON.exists():
        return
    registry = _load_json(REGISTRY_JSON)
    experiments = registry.get("experiments")
    if isinstance(experiments, list):
        for item in experiments:
            if isinstance(item, dict) and item.get("experiment_id") == EXPERIMENT_ID:
                item["status"] = "completed"
                item["decision"] = payload["gate4"]["decision"]
                item["completed_at"] = payload["completed_at"]
                item["updated_at"] = payload["completed_at"]
                item["artifact"] = _repo_rel(OUT_JSON)
                item["log"] = _repo_rel(LOG_JSON)
                item["aggregate_expected_value_delta"] = payload["vs_accepted_comparator"]["comparison"][
                    "expected_value_score_delta"
                ]
                item["aggregate_strategy_total_pnl_delta"] = payload["vs_accepted_comparator"]["comparison"][
                    "strategy_total_pnl_delta"
                ]
                break
    registry["updated_at"] = payload["completed_at"]
    _write_json(REGISTRY_JSON, registry)


def main() -> None:
    lagged._configure_same_day_modules()
    gate2 = lagged.same_day.prior.base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    source_rows = lagged.same_day.prior._source_rows_by_window()
    baselines = lagged.same_day.prior._load_baselines()
    comparator_results, comparator_trades = lagged._run_lagged_windows(baselines, source_rows)
    target_trades_by_window, diagnostics = _filter_cross_modality_trades(comparator_trades)
    results = _results_from_trades(baselines, target_trades_by_window)
    aggregate = lagged.same_day.prior._aggregate_results(results)
    target_summary = lagged.same_day.prior._target_summary(target_trades_by_window)
    accepted_aggregate = lagged.same_day.prior._aggregate_results(comparator_results)
    accepted_aggregate["after_by_window"] = {
        row["label"]: row["after"] for row in comparator_results
    }
    vs_comparator = _aggregate_vs_comparator(results, comparator_results)
    gate4 = _gate4(aggregate, results, target_summary, vs_comparator, diagnostics)
    completed_at = _utc_now()
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": completed_at,
        "completed_at": completed_at,
        "lane": "alpha_search",
        "preflight": _preflight_payload(),
        "gate_questions": {
            "1_alpha_hypothesis": _preflight_payload()["alpha_hypothesis"],
            "2_history_check": {
                "exp-20260604-008": "Positive replay lead for lagged independent source timing.",
                "exp-20260604-009": "Accepted lagged timing as shared default-off adapter.",
                "exp-20260604-010": "Rejected rank priority over source strength.",
                "exp-20260604-011": "Rejected cost/liquidity support due concentration.",
                "exp-20260604-012": "Rejected prior Companyfacts support due concentration.",
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Use docs/backtesting.md three canonical windows. Before is "
                "the current accepted exp-20260604-009 lagged adapter. Accept "
                "only if all windows improve vs accepted adapter with survival, "
                "drawdown, trade-count, and concentration guards."
            ),
            "5_reproducibility": _preflight_payload()["reproducibility"],
        },
        "rule": {
            "rule_version": RULE_VERSION,
            "changed_variable": CHANGED_VARIABLE,
            "source_family_modalities": SOURCE_FAMILY_MODALITIES,
            "gate_definition": "current_source_modalities are disjoint from prior_confirmation_source_modalities",
            "unchanged": {
                "accepted_source_names": sorted(lagged.same_day.SOURCE_EXPERIMENT_IDS),
                "source_families": dict(sorted(lagged.same_day.SOURCE_FAMILIES.items())),
                "prior_confirmation_trading_days": lagged.PRIOR_CONFIRMATION_TRADING_DAYS,
                "base_notional_usd": lagged.same_day.prior.BASE_NOTIONAL_USD,
                "hold_days": lagged.same_day.prior.HOLD_DAYS,
                "max_paper_trades_per_day": lagged.same_day.prior.MAX_PAPER_TRADES_PER_DAY,
                "same_ticker_cooldown_days": lagged.same_day.prior.SAME_TICKER_COOLDOWN_DAYS,
            },
        },
        "production_impact": PRODUCTION_IMPACT,
        "prediction": PREDICTION,
        "gate2": gate2,
        "gate3": {
            "survival_floor": 0.05,
            "new_core_filter_added": False,
            "paper_candidate_quality_gate_only": True,
            "min_survival_rate": min(_safe_float(row["before"].get("survival_rate")) for row in results),
        },
        "accepted_comparator": {
            "experiment_id": ACCEPTED_COMPARATOR_ID,
            "source_artifact": _repo_rel(ACCEPTED_COMPARATOR_JSON),
            "aggregate": accepted_aggregate,
            "target_summary": lagged.same_day.prior._target_summary(comparator_trades),
        },
        "aggregate": aggregate,
        "results": results,
        "vs_accepted_comparator": vs_comparator,
        "target_summary": target_summary,
        "target_trades_by_window": target_trades_by_window,
        "cross_modality_diagnostics": diagnostics,
        "gate4": gate4,
        "anti_js": "No JavaScript was used.",
    }

    _write_json(OUT_JSON, payload)
    record = _experiment_log_record(payload)
    _write_json(LOG_JSON, record)
    _write_card(payload)
    _update_ticket(payload)
    _update_manifest(payload)
    _update_registry(payload)
    lagged.same_day.prior.base._upsert_jsonl(EXPERIMENT_LOG, record)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": gate4["decision"],
                "aggregate_vs_core": aggregate["comparison"],
                "aggregate_vs_accepted_lagged_adapter": vs_comparator["comparison"],
                "cross_modality_diagnostics": {
                    "source_trade_count": diagnostics["source_trade_count"],
                    "target_trade_count": diagnostics["target_trade_count"],
                    "target_source_share": diagnostics["target_source_share"],
                },
                "anti_js": "No JavaScript was used.",
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
