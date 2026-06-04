"""exp-20260604-010: lagged consensus rank-priority scout.

Replay-only alpha search. The accepted lagged consensus adapter from
exp-20260604-009 is fixed as comparator. This experiment changes one variable:
when multiple accepted free-data consensus candidates compete for the same
paper top-1 day, rows with lagged independent source-family confirmation rank
ahead of rows supported only by raw same-day source-count strength.

No shared adapter, production path, live orders, source set, source-family map,
notional, hold period, cooldown, ranking outside this paper sleeve, sizing,
exits, LLM, or news behavior is changed. No JavaScript is used.
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


EXPERIMENT_ID = "exp-20260604-010"
STEM = "lagged_consensus_rank_priority"
TRIAL_FAMILY = "accepted_free_data_cross_source_consensus_candidate_ranking"
TRIAL_VARIANT_ID = "lagged_independent_confirmation_rank_priority_v1"
CHANGED_VARIABLE = "lagged_independent_confirmation_rank_priority_v1"
RULE_VERSION = "lagged_independent_confirmation_rank_priority_v1"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260604_010_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
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

PREDICTION = {
    "success_probability": 0.24,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "accepted_adapter_comparator_not_beaten",
        "window_regression",
        "lagged_priority_adds_stale_noise",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Meta research favors default-off adapter alpha; exp-20260604-008/009 "
        "show lagged source timing is strong, but prioritizing it above same-day "
        "source strength is a distinct ranking variable and may overfit."
    ),
    "recorded_at": "2026-06-04T10:07:45+00:00",
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
        "This experiment changes no production code. A retained rank-priority "
        "result would need the shared free-data consensus adapter to apply the "
        "same top-1/day candidate ordering in both daily production and replay "
        "before any report queue, paper ledger, or order surface could change."
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


def _append_jsonl_once(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    experiment_id = row["experiment_id"]
    if path.exists():
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    existing = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if existing.get("experiment_id") == experiment_id:
                    return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")


def _lagged_priority_sort(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = []
    for candidate in candidates:
        row = dict(candidate)
        row["rank_priority_rule_version"] = RULE_VERSION
        row["rank_priority_reason"] = (
            "lagged_independent_confirmation_first"
            if row.get("has_lagged_independent_confirmation")
            else "same_day_consensus_without_lagged_priority"
        )
        ranked.append(row)
    return sorted(
        ranked,
        key=lambda row: (
            str(row["date"]),
            0 if row.get("has_lagged_independent_confirmation") else 1,
            -int(row.get("source_family_count") or 0),
            -int(row.get("current_source_family_count") or 0),
            -int(row.get("source_count") or 0),
            "+".join(row.get("source_families") or []),
            "+".join(row.get("current_source_names") or []),
            str(row["ticker"]),
        ),
    )


def _rank_priority_candidates_for_window(
    label: str,
    snapshot: dict[str, Any],
    cfg: dict[str, str],
    source_rows_by_window: dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
) -> list[dict[str, Any]]:
    baseline_candidates = lagged._lagged_consensus_candidates_for_window(
        label,
        snapshot,
        cfg,
        source_rows_by_window,
    )
    return _lagged_priority_sort(baseline_candidates)


def _run_priority_windows(
    baselines: dict[str, dict[str, Any]],
    source_rows_by_window: dict[str, dict[tuple[str, str], list[dict[str, Any]]]],
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    results: list[dict[str, Any]] = []
    target_trades_by_window: dict[str, list[dict[str, Any]]] = {}
    for label, cfg in lagged.same_day.prior.base.WINDOWS.items():
        snapshot = lagged.same_day.prior.base.shadow._load_snapshot(cfg["snapshot"])
        candidates = _rank_priority_candidates_for_window(
            label,
            snapshot,
            cfg,
            source_rows_by_window,
        )
        target_trades, target_diagnostics = lagged._select_target_trades(snapshot, candidates)
        before_result = baselines[label]["result"]
        before = baselines[label]["metrics"]
        overlay = lagged.same_day.prior.base._overlay_from_paper_trades(
            before_result,
            target_trades,
        )
        after = lagged.same_day.prior.base.overlay_helper._metrics_with_overlay(
            before_result,
            overlay,
        )
        raw_delta = lagged.same_day.prior.base.overlay_helper._delta(after, before)
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
                "target_trade_pnl_usd": sum(
                    _safe_float(row.get("pnl")) for row in target_trades
                ),
                "raw_rank_priority_candidate_count": len(candidates),
                "rank_priority_candidate_count": sum(
                    1 for row in candidates if row.get("has_lagged_independent_confirmation")
                ),
                "rank_priority_selected_trade_count": sum(
                    1 for row in target_trades if row.get("has_lagged_independent_confirmation")
                ),
                "target_diagnostics": target_diagnostics,
            }
        )
        target_trades_by_window[label] = target_trades
    return results, target_trades_by_window


def _rank_priority_summary(target_trades_by_window: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    rows = [row for trades in target_trades_by_window.values() for row in trades]
    lagged_rows = [row for row in rows if row.get("has_lagged_independent_confirmation")]
    priority_reason_counts = Counter(str(row.get("rank_priority_reason") or "missing") for row in rows)
    family_combo_counts = Counter("+".join(row.get("source_families") or []) for row in rows)
    return {
        "rule_version": RULE_VERSION,
        "total_trade_count": len(rows),
        "lagged_priority_selected_trade_count": len(lagged_rows),
        "lagged_priority_selected_trade_count_by_window": {
            label: sum(1 for row in trades if row.get("has_lagged_independent_confirmation"))
            for label, trades in target_trades_by_window.items()
        },
        "lagged_priority_selected_trade_pnl_usd": round(
            sum(_safe_float(row.get("pnl")) for row in lagged_rows),
            2,
        ),
        "priority_reason_counts": dict(sorted(priority_reason_counts.items())),
        "selected_family_combo_counts": dict(sorted(family_combo_counts.items())),
        "trade_enabled": False,
        "alters_orders": False,
    }


def _gate4(
    aggregate: dict[str, Any],
    results: list[dict[str, Any]],
    target_summary: dict[str, Any],
    vs_comparator: dict[str, Any],
    priority_summary: dict[str, Any],
) -> dict[str, Any]:
    base_gate = lagged.same_day.prior._gate4_decision(aggregate, results, target_summary)
    comp = vs_comparator["comparison"]
    comparator_passed = (
        comp["expected_value_score_delta"] > 0.0
        and comp["strategy_total_pnl_delta"] > 0.0
        and comp["windows_ev_improved"] == 3
        and comp["windows_pnl_improved"] == 3
    )
    priority_sample_passed = int(priority_summary["lagged_priority_selected_trade_count"]) > 0
    gates = {
        **base_gate["gates"],
        "beats_current_accepted_lagged_adapter": comparator_passed,
        "lagged_priority_selected_trade_count_positive": priority_sample_passed,
    }
    passed = bool(base_gate["passed"] and comparator_passed and priority_sample_passed)
    if passed:
        decision = "positive_replay_lead_requires_shared_rank_priority_adapter"
        rationale = (
            "Lagged-confirmation rank priority improved core and the current "
            "accepted lagged adapter comparator across all three windows. "
            "Promotion would require shared adapter ordering and parity tests."
        )
    elif not priority_sample_passed:
        decision = "rejected_lagged_rank_priority_no_selected_lagged_rows"
        rationale = "The priority rule selected no lagged-confirmation trades."
    elif not comparator_passed:
        decision = "rejected_lagged_rank_priority_did_not_beat_accepted_adapter"
        rationale = (
            "The rank-priority variant did not beat the current accepted "
            "lagged consensus adapter across all three windows."
        )
    else:
        decision = "rejected_lagged_rank_priority_gate4_failed"
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
            "Accepted free-data consensus candidates with lagged independent "
            "source confirmation may deserve higher same-day top-1 paper priority "
            "than raw current source-count strength."
        ),
        "category": "ranking/candidate_pool",
        "playbook_alignment": (
            "Meta research favors default-off paper adapters and the playbook "
            "allows materially different source-timing constructions. This is "
            "not a source-set, prior-window, notional, hold, or ticker-pool retune."
        ),
        "nearby_prior_experiments": [
            "exp-20260603-014",
            "exp-20260603-015",
            "exp-20260604-008",
            "exp-20260604-009",
        ],
        "prior_difference": (
            "exp-20260604-008/009 admitted lagged independent source-family "
            "confirmation. This run leaves admission unchanged and tests only "
            "whether that timing-quality flag should outrank raw source-count "
            "strength when candidates collide on the same paper entry date."
        ),
        "single_causal_variable": CHANGED_VARIABLE,
        "acceptance_criteria": {
            "canonical_windows": list(lagged.same_day.prior.base.WINDOWS.keys()),
            "aggregate_expected_value_delta_vs_core": "> 0",
            "aggregate_pnl_delta_vs_core": "> 0",
            "per_window_expected_value_delta_vs_core": "3 of 3 windows > 0",
            "per_window_pnl_delta_vs_core": "3 of 3 windows > 0",
            "must_beat_current_accepted_lagged_adapter": True,
            "per_window_delta_vs_accepted_adapter": "3 of 3 windows > 0",
            "minimum_target_trades": lagged.same_day.prior.MIN_TARGET_TRADES,
            "minimum_target_windows": lagged.same_day.prior.MIN_TARGET_WINDOWS,
            "max_drawdown_drift": lagged.same_day.prior.MAX_DRAWDOWN_WORSE,
            "survival_rate_floor": 0.05,
            "max_single_positive_share": lagged.same_day.prior.MAX_SINGLE_POSITIVE_SHARE,
            "positive_pnl_hhi_max": lagged.same_day.prior.MAX_POSITIVE_HHI,
        },
        "reproducibility": (
            ".venv\\Scripts\\python.exe -B "
            "quant\\experiments\\exp_20260604_010_lagged_consensus_rank_priority.py"
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
        "change_type": "default_off_paper_adapter_candidate_ranking_alpha",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "prior_trial_count": 0,
        "nearby_prior_experiments": payload["preflight"]["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "production_visible_source_timing_quality_ranking_field",
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
            "ev_prediction_error": None,
            "expected_pnl_delta": PREDICTION["expected_pnl_delta"],
            "actual_pnl_delta": comparison["strategy_total_pnl_delta"],
            "pnl_prediction_error": None,
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
            "lagged_priority_selected_trade_count": payload["rank_priority_summary"][
                "lagged_priority_selected_trade_count"
            ],
            "lagged_priority_selected_trade_pnl_usd": payload["rank_priority_summary"][
                "lagged_priority_selected_trade_pnl_usd"
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
                "rank_priority_selected_trade_count": row["rank_priority_selected_trade_count"],
            }
            for row in payload["results"]
        ],
        "artifact_path": _repo_rel(OUT_JSON),
        "anti_js": "No JavaScript was used.",
    }


def _write_card(payload: dict[str, Any]) -> None:
    comp = payload["aggregate"]["comparison"]
    accepted = payload["vs_accepted_comparator"]["comparison"]
    priority = payload["rank_priority_summary"]
    lines = [
        f"# {EXPERIMENT_ID} Lagged Consensus Rank Priority",
        "",
        "## Decision",
        "",
        f"- Decision: `{payload['gate4']['decision']}`",
        f"- Rationale: {payload['gate4']['rationale']}",
        "",
        "## Three-Window Result",
        "",
        f"- Vs core: EV `{comp['expected_value_score_delta']:+.4f}`, PnL `${comp['strategy_total_pnl_delta']:+,.2f}`",
        f"- Vs accepted lagged adapter: EV `{accepted['expected_value_score_delta']:+.4f}`, PnL `${accepted['strategy_total_pnl_delta']:+,.2f}`",
        f"- Lagged-priority selected trades: `{priority['lagged_priority_selected_trade_count']}`",
        "",
        "| Window | EV Delta | PnL Delta | Target Trades | Lagged-Priority Trades |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["results"]:
        lines.append(
            f"| {row['label']} | {row['comparison']['expected_value_score_delta']:+.4f} | "
            f"${row['comparison']['strategy_total_pnl_delta']:+,.2f} | "
            f"{row['target_trade_count']} | {row['rank_priority_selected_trade_count']} |"
        )
    lines.extend(
        [
            "",
            "## Production Impact",
            "",
            "- Replay-only; no shared adapter, production order, watchlist, ranking, sizing, exit, LLM, or news behavior changed.",
            "- A positive result would require shared adapter ordering and parity tests before promotion.",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    text = "\n".join(lines)
    _write_text(CARD_MD, text)
    _write_text(ARTIFACT_MD, text)


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
            "markdown_artifact": _repo_rel(ARTIFACT_MD),
            "card": _repo_rel(CARD_MD),
            "log": _repo_rel(LOG_JSON),
            "production_impact": PRODUCTION_IMPACT,
            "gate4": payload["gate4"],
            "result": {
                "aggregate_expected_value_delta": payload["aggregate"]["comparison"][
                    "expected_value_score_delta"
                ],
                "aggregate_strategy_total_pnl_delta": payload["aggregate"]["comparison"][
                    "strategy_total_pnl_delta"
                ],
                "accepted_comparator_ev_delta": payload["vs_accepted_comparator"][
                    "comparison"
                ]["expected_value_score_delta"],
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
                _repo_rel(BEFORE_JSON),
                _repo_rel(AFTER_JSON),
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
    lagged._configure_same_day_modules()
    gate2 = lagged.same_day.prior.base._audit_open_positions()
    if not gate2["passed"]:
        raise RuntimeError(f"Gate 2 failed: {gate2}")

    source_rows = lagged.same_day.prior._source_rows_by_window()
    baselines = lagged.same_day.prior._load_baselines()
    comparator_results, comparator_trades = lagged._run_lagged_windows(baselines, source_rows)
    results, target_trades_by_window = _run_priority_windows(baselines, source_rows)
    aggregate = lagged.same_day.prior._aggregate_results(results)
    comparator_aggregate = lagged.same_day.prior._aggregate_results(comparator_results)
    target_summary = lagged.same_day.prior._target_summary(target_trades_by_window)
    priority_summary = _rank_priority_summary(target_trades_by_window)
    vs_comparator = lagged._aggregate_vs_comparator(results, comparator_results)
    gate4 = _gate4(aggregate, results, target_summary, vs_comparator, priority_summary)
    completed_at = _utc_now()

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "created_at": completed_at,
        "completed_at": completed_at,
        "lane": "alpha_search",
        "preflight": _preflight_payload(),
        "gate_questions": {
            "1_alpha_hypothesis": (
                "ranking/candidate_pool: lagged independent source confirmation "
                "may deserve higher top-1 paper priority than raw current source count."
            ),
            "2_history_check": {
                "exp-20260603-014": "Accepted same-day independent-source consensus.",
                "exp-20260603-015": "Promoted same-day consensus to shared default-off adapter.",
                "exp-20260604-008": "Positive replay lead for lagged independent source timing.",
                "exp-20260604-009": "Promoted lagged timing into shared default-off adapter.",
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Use docs/backtesting.md three fixed windows; accept only if "
                "this ranking variant beats core and exp-20260604-009 in all "
                "windows with concentration, survival, and drawdown guardrails."
            ),
            "5_reproducibility": _preflight_payload()["reproducibility"],
        },
        "rule": {
            "rule_version": RULE_VERSION,
            "changed_sort_order": (
                "date, lagged_independent_confirmation desc, source_family_count desc, "
                "current_source_family_count desc, source_count desc"
            ),
            "unchanged": {
                "accepted_source_names": sorted(lagged.same_day.SOURCE_EXPERIMENT_IDS),
                "min_source_family_count": lagged.same_day.MIN_SOURCE_FAMILY_COUNT,
                "prior_confirmation_trading_days": lagged.PRIOR_CONFIRMATION_TRADING_DAYS,
                "base_notional_usd": lagged.same_day.prior.BASE_NOTIONAL_USD,
                "hold_days": lagged.same_day.prior.HOLD_DAYS,
                "max_paper_trades_per_day": lagged.same_day.prior.MAX_PAPER_TRADES_PER_DAY,
                "same_ticker_cooldown_days": lagged.same_day.prior.SAME_TICKER_COOLDOWN_DAYS,
            },
        },
        "accepted_comparator": {
            "experiment_id": ACCEPTED_COMPARATOR_ID,
            "source_artifact": _repo_rel(ACCEPTED_COMPARATOR_JSON),
            "aggregate": comparator_aggregate,
            "target_summary": lagged.same_day.prior._target_summary(comparator_trades),
        },
        "production_impact": PRODUCTION_IMPACT,
        "prediction": PREDICTION,
        "gate2": gate2,
        "gate3": {
            "survival_floor": 0.05,
            "new_core_filter_added": False,
            "candidate_pool_ranking_only": True,
            "min_survival_rate": min(_safe_float(row["before"].get("survival_rate")) for row in results),
        },
        "aggregate": aggregate,
        "vs_accepted_comparator": vs_comparator,
        "results": results,
        "target_summary": target_summary,
        "rank_priority_summary": priority_summary,
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
    _update_ticket(payload)
    _update_manifest(payload)
    _upsert_registry(payload)
    _append_jsonl_once(EXPERIMENT_LOG, record)

    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": gate4["decision"],
                "aggregate_vs_core": aggregate["comparison"],
                "aggregate_vs_accepted_adapter": vs_comparator["comparison"],
                "rank_priority_summary": priority_summary,
                "anti_js": "No JavaScript was used.",
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
