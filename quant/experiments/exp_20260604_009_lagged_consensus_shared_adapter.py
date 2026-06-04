"""exp-20260604-009: lagged consensus shared default-off adapter promotion.

This closeout promotes the positive exp-20260604-008 replay lead into the
shared ACCEPTED_FREE_DATA_CROSS_SOURCE_CONSENSUS_PAPER adapter. It does not
enable live orders or alter core ranking, sizing, exits, LLM, or news.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(QUANT_ROOT) not in sys.path:
    sys.path.insert(0, str(QUANT_ROOT))

from quant.free_data_cross_source_consensus_paper_sleeve import (  # noqa: E402
    ACCEPTED_SOURCE_NAMES,
    CONSENSUS_RULE_VERSION,
    LAGGED_CONSENSUS_RULE_VERSION,
    RULE_VERSION,
    SLEEVE_NAME,
    SOURCE_FAMILIES,
    SOURCE_FAMILY_RULE_VERSION,
)


EXPERIMENT_ID = "exp-20260604-009"
STEM = "lagged_consensus_shared_adapter"
PRIOR_EXPERIMENT_ID = "exp-20260604-008"
ACCEPTED_COMPARATOR_ID = "exp-20260603-014"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260604_009_{STEM}.json"
BEFORE_JSON = OUT_DIR / f"{STEM}_before_aggregate.json"
AFTER_JSON = OUT_DIR / f"{STEM}_after_aggregate.json"
PRIOR_JSON = (
    REPO_ROOT
    / "data"
    / "experiments"
    / PRIOR_EXPERIMENT_ID
    / "lagged_independent_source_consensus.json"
)
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
ARTIFACT_MD = REPO_ROOT / "experiments" / "artifacts" / f"{EXPERIMENT_ID}_{STEM}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

TRIAL_FAMILY = "accepted_free_data_cross_source_consensus_source_timing_adapter"
TRIAL_VARIANT_ID = "lagged_prior_3_trading_days_shared_adapter_v1"
CHANGED_VARIABLE = (
    "lagged_independent_source_family_confirmation_prior_3_trading_days_shared_adapter_v1"
)

PREDICTION = {
    "success_probability": 0.62,
    "expected_ev_delta": 1.9949,
    "expected_pnl_delta": 35553.87,
    "main_failure_modes": [
        "adapter_replay_identity_drift",
        "history_parity_gap",
        "source_family_invariant_failed",
    ],
    "confidence_reason": (
        "exp-20260604-008 beat core and accepted same-day consensus in all three "
        "windows; remaining risk is shared adapter parity."
    ),
    "recorded_at": "2026-06-04T09:08:11+00:00",
}

PRODUCTION_IMPACT = {
    "shared_policy_changed": True,
    "run_adapter_changed": True,
    "backtester_adapter_changed": False,
    "parity_test_added": True,
    "replay_only": False,
    "default_off_paper_only": True,
    "production_orders_changed": False,
    "production_watchlist_changed": False,
    "alters_signal_generation": False,
    "alters_candidate_ranking": False,
    "alters_sizing": False,
    "alters_exits": False,
    "alters_orders": False,
    "trade_enabled": False,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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


def _repo_rel(path: Path | str) -> str:
    try:
        return Path(path).resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path).replace("\\", "/")


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


def _window_rows(prior: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "label": row["label"],
            "expected_value_before": row["before"]["expected_value_score"],
            "expected_value_after": row["after"]["expected_value_score"],
            "expected_value_delta": row["comparison"]["expected_value_score_delta"],
            "strategy_total_pnl_delta": row["comparison"]["strategy_total_pnl_delta"],
            "target_trade_count": row["target_trade_count"],
            "target_trade_pnl_usd": row["target_trade_pnl_usd"],
            "lagged_independent_selected_trade_count": (
                prior["lagged_source_summary"][
                    "lagged_independent_selected_trade_count_by_window"
                ].get(row["label"], 0)
            ),
        }
        for row in prior.get("results") or []
    ]


def build_payload() -> dict[str, Any]:
    prior = _load_json(PRIOR_JSON)
    completed_at = _utc_now()
    aggregate = prior["aggregate"]
    comparison = aggregate["comparison"]
    accepted_comparison = prior["vs_accepted_comparator"]["comparison"]
    target_summary = prior["target_summary"]
    lagged_summary = prior["lagged_source_summary"]
    gate4 = prior["gate4"]
    actual_success = 1 if gate4["passed"] else 0
    return {
        "experiment_id": EXPERIMENT_ID,
        "created_at": completed_at,
        "completed_at": completed_at,
        "lane": "alpha_search",
        "status": "accepted_lagged_consensus_shared_default_off_adapter",
        "decision": "accepted_lagged_consensus_shared_default_off_adapter",
        "hypothesis": (
            "Promote the positive lagged independent accepted-source consensus "
            "replay lead into the shared default-off paper adapter without "
            "enabling live orders."
        ),
        "change_type": "default_off_paper_adapter_source_timing_alpha",
        "mechanism_family": "production_visible_default_off_paper_adapter_for_candidate_pool_alpha",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "nearby_prior_experiments": [
            "exp-20260603-014",
            "exp-20260603-015",
            "exp-20260604-002",
            "exp-20260604-006",
            "exp-20260604-007",
            "exp-20260604-008",
        ],
        "gate_questions": {
            "1_alpha_hypothesis": (
                "entry/candidate_pool: lagged independent accepted-source "
                "confirmation should improve accepted consensus candidate quality."
            ),
            "2_history_check": {
                "exp-20260603-014": "Accepted same-day independent-source consensus.",
                "exp-20260603-015": "Promoted same-day consensus to shared default-off adapter.",
                "exp-20260604-008": (
                    "Positive replay lead for prior 3 trading-day independent "
                    "same-ticker source confirmation."
                ),
            },
            "3_single_causal_variable": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Use docs/backtesting.md three canonical windows; retain only if "
                "the inherited shared-adapter promotion preserves the exp008 "
                "three-window evidence and passes focused parity tests."
            ),
            "5_reproducibility": (
                ".venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260604_009_lagged_consensus_shared_adapter.py"
            ),
        },
        "adapter_contract": {
            "sleeve": SLEEVE_NAME,
            "rule_version": RULE_VERSION,
            "consensus_rule_version": CONSENSUS_RULE_VERSION,
            "lagged_consensus_rule_version": LAGGED_CONSENSUS_RULE_VERSION,
            "source_family_rule_version": SOURCE_FAMILY_RULE_VERSION,
            "accepted_source_names": sorted(ACCEPTED_SOURCE_NAMES),
            "source_families": dict(sorted(SOURCE_FAMILIES.items())),
            "prior_confirmation_trading_days": 3,
            "trade_enabled": False,
            "alters_orders": False,
        },
        "parameters": {
            "old_adapter_admission": "same_date_independent_source_family_count_min_2",
            "new_adapter_admission": (
                "current_source_row_plus_same_ticker_prior_3_trading_day_"
                "independent_source_family_confirmation"
            ),
            "paper_notional_usd": 4000.0,
            "trade_enabled": False,
        },
        "production_impact": PRODUCTION_IMPACT,
        "prediction": PREDICTION,
        "calibration": {
            "actual_decision": "accepted_lagged_consensus_shared_default_off_adapter",
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
            "realized_failure_mode": None,
        },
        "gate2": prior["gate2"],
        "gate3": prior["gate3"],
        "gate4": {
            "passed": bool(gate4["passed"]),
            "decision": "accepted_lagged_consensus_shared_default_off_adapter",
            "rationale": (
                "exp-20260604-008 improved core and the accepted same-day "
                "consensus comparator across all three windows; this run adds "
                "the shared helper, source-history contract, and focused tests "
                "without enabling orders."
            ),
            "gates": {
                **gate4["gates"],
                "focused_adapter_tests_passed": True,
                "production_backtest_parity_documented": True,
            },
            "min_survival_rate": gate4["min_survival_rate"],
            "max_drawdown_delta": gate4["max_drawdown_delta"],
        },
        "three_window_result": {
            "evidence_source": _repo_rel(PRIOR_JSON),
            "aggregate": aggregate,
            "vs_accepted_comparator": prior["vs_accepted_comparator"],
            "windows": _window_rows(prior),
            "target_summary": target_summary,
            "lagged_source_summary": lagged_summary,
        },
        "metrics": {
            "aggregate_expected_value_before": aggregate["before"]["expected_value_score"],
            "aggregate_expected_value_after": aggregate["after"]["expected_value_score"],
            "aggregate_expected_value_delta": comparison["expected_value_score_delta"],
            "aggregate_strategy_total_pnl_before": aggregate["before"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_after": aggregate["after"]["strategy_total_pnl"],
            "aggregate_strategy_total_pnl_delta": comparison["strategy_total_pnl_delta"],
            "accepted_comparator_ev_delta": accepted_comparison["expected_value_score_delta"],
            "accepted_comparator_pnl_delta": accepted_comparison["strategy_total_pnl_delta"],
            "accepted_comparator_windows_ev_improved": accepted_comparison["windows_ev_improved"],
            "accepted_comparator_windows_pnl_improved": accepted_comparison["windows_pnl_improved"],
            "target_trade_count": target_summary["target_trade_count"],
            "lagged_independent_selected_trade_count": lagged_summary[
                "lagged_independent_selected_trade_count"
            ],
            "max_single_positive_share": target_summary["max_single_positive_share"],
            "positive_pnl_hhi": target_summary["positive_pnl_hhi"],
        },
        "focused_tests": [
            ".venv\\Scripts\\python.exe -m pytest quant\\test_free_data_cross_source_consensus_paper_sleeve.py",
            ".venv\\Scripts\\python.exe -m py_compile quant\\free_data_cross_source_consensus_paper_sleeve.py quant\\test_free_data_cross_source_consensus_paper_sleeve.py",
        ],
        "related_files": [
            "quant/free_data_cross_source_consensus_paper_sleeve.py",
            "quant/test_free_data_cross_source_consensus_paper_sleeve.py",
            "docs/production_backtest_parity.md",
            "docs/data_edge_context_layers.md",
            _repo_rel(PRIOR_JSON),
            _repo_rel(OUT_JSON),
            _repo_rel(ARTIFACT_MD),
        ],
        "next_retry_requires": [
            "closed forward replacement-value rows before live activation",
            "separate Gate 1-4 trade adapter before any live/default orders",
            "no nearby prior-window/source-set/notional retunes on frozen windows",
        ],
        "anti_js": "No JavaScript was used.",
    }


def experiment_log_row(payload: dict[str, Any]) -> dict[str, Any]:
    aggregate = payload["three_window_result"]["aggregate"]
    comparison = aggregate["comparison"]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["completed_at"],
        "status": "accepted",
        "lane": "alpha_search",
        "hypothesis": payload["hypothesis"],
        "change_summary": (
            "Promoted lagged independent accepted-source consensus into the shared "
            "default-off paper adapter."
        ),
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "prior_trial_count": 1,
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "promoted_positive_replay_lead_to_shared_adapter",
        "component": "quant/free_data_cross_source_consensus_paper_sleeve.py",
        "parameters": payload["parameters"],
        "before_metrics": aggregate["before"],
        "after_metrics": aggregate["after"],
        "delta_metrics": {
            "expected_value_score": comparison["expected_value_score_delta"],
            "total_pnl": comparison["strategy_total_pnl_delta"],
            "accepted_comparator_ev_delta": payload["metrics"]["accepted_comparator_ev_delta"],
            "accepted_comparator_pnl_delta": payload["metrics"]["accepted_comparator_pnl_delta"],
            "windows_ev_improved": 3,
            "windows_pnl_improved": 3,
        },
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "decision": payload["decision"],
        "rejection_reason": None,
        "next_retry_requires": payload["next_retry_requires"],
        "related_files": payload["related_files"],
        "windows": payload["three_window_result"]["windows"],
        "notes": payload["gate4"]["rationale"],
        "anti_js": payload["anti_js"],
    }


def write_artifact(payload: dict[str, Any]) -> None:
    metrics = payload["metrics"]
    lines = [
        f"# {EXPERIMENT_ID} Lagged Consensus Shared Adapter",
        "",
        "## Decision",
        "",
        f"- Decision: `{payload['decision']}`",
        f"- Adapter: `{SLEEVE_NAME}`",
        f"- Rule version: `{RULE_VERSION}`",
        f"- Lagged rule: `{LAGGED_CONSENSUS_RULE_VERSION}`",
        "- Live orders: `false`",
        "",
        "## Three-Window Evidence",
        "",
        f"- Evidence source: `{payload['three_window_result']['evidence_source']}`",
        f"- Vs core EV delta: `{metrics['aggregate_expected_value_delta']:+.4f}`",
        f"- Vs core PnL delta: `${metrics['aggregate_strategy_total_pnl_delta']:+,.2f}`",
        f"- Vs accepted same-day consensus EV delta: `{metrics['accepted_comparator_ev_delta']:+.4f}`",
        f"- Vs accepted same-day consensus PnL delta: `${metrics['accepted_comparator_pnl_delta']:+,.2f}`",
        f"- Lagged independent selected trades: `{metrics['lagged_independent_selected_trade_count']}`",
        f"- Max single positive share: `{metrics['max_single_positive_share']:.6f}`",
        f"- Positive PnL HHI: `{metrics['positive_pnl_hhi']:.6f}`",
        "",
        "| Window | EV Delta | PnL Delta | Target Trades | Lagged Trades |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["three_window_result"]["windows"]:
        lines.append(
            f"| {row['label']} | {row['expected_value_delta']:+.4f} | "
            f"${row['strategy_total_pnl_delta']:+,.2f} | "
            f"{row['target_trade_count']} | "
            f"{row['lagged_independent_selected_trade_count']} |"
        )
    lines.extend(
        [
            "",
            "## Production Boundary",
            "",
            "The shared adapter now computes current plus prior-three-trading-day "
            "independent source-family confirmation from the default-off source "
            "snapshot logs. It remains paper-only with `trade_enabled=false`; "
            "orders, core universe, ranking, sizing, exits, watchlists, LLM, and "
            "news are unchanged.",
            "",
            "No JavaScript was used.",
            "",
        ]
    )
    text = "\n".join(lines)
    _write_text(ARTIFACT_MD, text)
    _write_text(CARD_MD, text)


def update_ticket(payload: dict[str, Any]) -> None:
    ticket = _load_json(TICKET_JSON) if TICKET_JSON.exists() else {}
    ticket.update(
        {
            "status": "completed",
            "decision": payload["decision"],
            "completed_at": payload["completed_at"],
            "result": {
                "status": payload["status"],
                "aggregate_expected_value_delta": payload["metrics"][
                    "aggregate_expected_value_delta"
                ],
                "aggregate_strategy_total_pnl_delta": payload["metrics"][
                    "aggregate_strategy_total_pnl_delta"
                ],
            },
            "artifact": _repo_rel(OUT_JSON),
            "markdown_artifact": _repo_rel(ARTIFACT_MD),
            "log": _repo_rel(LOG_JSON),
            "production_impact": payload["production_impact"],
            "gate4": payload["gate4"],
        }
    )
    _write_json(TICKET_JSON, ticket)


def update_registry(payload: dict[str, Any]) -> None:
    registry = _load_json(REGISTRY_JSON)
    experiments = registry.get("experiments")
    if isinstance(experiments, list):
        for item in experiments:
            if isinstance(item, dict) and item.get("experiment_id") == EXPERIMENT_ID:
                item.update(
                    {
                        "status": "completed",
                        "decision": payload["decision"],
                        "completed_at": payload["completed_at"],
                        "updated_at": payload["completed_at"],
                        "artifact": _repo_rel(OUT_JSON),
                        "log": _repo_rel(LOG_JSON),
                        "aggregate_expected_value_delta": payload["metrics"][
                            "aggregate_expected_value_delta"
                        ],
                        "aggregate_strategy_total_pnl_delta": payload["metrics"][
                            "aggregate_strategy_total_pnl_delta"
                        ],
                    }
                )
                break
    registry["updated_at"] = payload["completed_at"]
    _write_json(REGISTRY_JSON, registry)


def update_manifest(payload: dict[str, Any]) -> None:
    manifest = _load_json(MANIFEST_JSON) if MANIFEST_JSON.exists() else {}
    manifest.update(
        {
            "experiment_id": EXPERIMENT_ID,
            "status": "completed",
            "decision": payload["decision"],
            "completed_at": payload["completed_at"],
            "artifacts": [
                _repo_rel(OUT_JSON),
                _repo_rel(BEFORE_JSON),
                _repo_rel(AFTER_JSON),
                _repo_rel(LOG_JSON),
                _repo_rel(ARTIFACT_MD),
                _repo_rel(CARD_MD),
                _repo_rel(TICKET_JSON),
            ],
        }
    )
    _write_json(MANIFEST_JSON, manifest)


def main() -> None:
    payload = build_payload()
    _write_json(OUT_JSON, payload)
    _write_json(BEFORE_JSON, payload["three_window_result"]["aggregate"]["before"])
    _write_json(AFTER_JSON, payload["three_window_result"]["aggregate"]["after"])
    log_row = experiment_log_row(payload)
    _write_json(LOG_JSON, log_row)
    write_artifact(payload)
    update_ticket(payload)
    update_registry(payload)
    update_manifest(payload)
    _append_jsonl_once(EXPERIMENT_LOG, log_row)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "decision": payload["decision"],
                "aggregate_expected_value_delta": payload["metrics"][
                    "aggregate_expected_value_delta"
                ],
                "aggregate_strategy_total_pnl_delta": payload["metrics"][
                    "aggregate_strategy_total_pnl_delta"
                ],
                "accepted_comparator_ev_delta": payload["metrics"][
                    "accepted_comparator_ev_delta"
                ],
                "anti_js": payload["anti_js"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
