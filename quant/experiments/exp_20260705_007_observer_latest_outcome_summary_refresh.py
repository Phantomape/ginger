"""exp-20260705-007: refresh observer outcome summaries.

Measurement repair only. exp-20260705-006 fixed observer outcome maturity
semantics in code, but the canonical latest outcome summaries were still stale
generated files. This runner refreshes the prediction-market and entity-theme
observer outcome ledgers/summaries so downstream alpha attribution reads the
repaired future-entry status split.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260705-007"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "observer_latest_outcome_summary_refresh"
DATE_TAG = "20260704"
RUNNER = f"quant/experiments/exp_20260705_007_{SLUG}.py"
RUNNER_WINDOWS = RUNNER.replace("/", "\\")
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_WINDOWS

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for path in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from entity_theme_news_observer import (  # noqa: E402
    persist_entity_theme_news_outcome_ledger,
)
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from prediction_market_event_observer import (  # noqa: E402
    persist_prediction_market_event_outcome_ledger,
)


BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
PREDICTION_SUMMARY = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "prediction_market_event_observer"
    / "latest_outcome_summary.json"
)
ENTITY_SUMMARY = (
    REPO_ROOT
    / "data"
    / "non_ohlcv"
    / "entity_theme_news_observer"
    / "latest_outcome_summary.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260705_007_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Observer alpha outcome summaries remain stale after exp-20260705-006: "
    "canonical prediction-market and entity-theme latest_outcome_summary files "
    "still label future-entry maturity rows as unsettled_no_entry_bar, blocking "
    "reliable RV attribution; refresh/materialize the repaired status semantics "
    "without changing thresholds, candidate maps, horizons, notional, orders, "
    "ranking, sizing, or exits."
)
CHANGED_VARIABLE = "observer_future_entry_status_summary_refresh_v1"
MECHANISM_FAMILY = "observer_forward_outcome_maturity"
TRIAL_FAMILY = "observer_latest_outcome_summary_refresh"
TRIAL_VARIANT_ID = "20260705_future_entry_status_canonical_summary"
NEARBY_PRIORS = ["exp-20260705-006", "exp-20260704-012", "exp-20260703-014"]
CHANGED_FILES = [
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260705_007_{SLUG}.json",
    "data/non_ohlcv/prediction_market_event_observer/latest_outcome_summary.json",
    "data/non_ohlcv/prediction_market_event_observer/outcome_summaries/prediction_market_event_observer_outcome_summary_20260704.json",
    "data/non_ohlcv/prediction_market_event_observer/outcome_ledgers/prediction_market_event_observer_outcomes_20260704.jsonl",
    "data/non_ohlcv/entity_theme_news_observer/latest_outcome_summary.json",
    "data/non_ohlcv/entity_theme_news_observer/outcome_summaries/entity_theme_news_observer_outcome_summary_20260704.json",
    "data/non_ohlcv/entity_theme_news_observer/outcome_ledgers/entity_theme_news_observer_outcomes_20260704.jsonl",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def status_counts(summary: dict[str, Any]) -> dict[str, int]:
    counts = summary.get("status_counts")
    if not isinstance(counts, dict):
        return {}
    return {str(key): int(value or 0) for key, value in counts.items()}


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_PATH, {})
    raw_windows = payload.get("windows") or payload.get("window_results") or []
    windows = list(raw_windows.values()) if isinstance(raw_windows, dict) else list(raw_windows)
    generated = sum(int(w.get("signals_generated") or 0) for w in windows)
    survived = sum(int(w.get("signals_survived") or 0) for w in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_PATH),
        "loaded": BASELINE_PATH.exists(),
        "expected_value_score_sum": round(
            sum(float(w.get("expected_value_score") or 0.0) for w in windows), 4
        ),
        "total_pnl": round(sum(float(w.get("total_pnl") or 0.0) for w in windows), 2),
        "trade_count": sum(int(w.get("trade_count") or 0) for w in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "window_count": len(windows),
    }


def surface_summary(name: str, before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    before_counts = status_counts(before)
    after_counts = status_counts(after)
    return {
        "name": name,
        "before_status_counts": before_counts,
        "after_status_counts": after_counts,
        "candidate_outcome_row_count_before": before.get("candidate_outcome_row_count"),
        "candidate_outcome_row_count_after": after.get("candidate_outcome_row_count"),
        "settled_count_before": before.get("settled_count"),
        "settled_count_after": after.get("settled_count"),
        "unsettled_no_entry_bar_before": before_counts.get("unsettled_no_entry_bar", 0),
        "unsettled_no_entry_bar_after": after_counts.get("unsettled_no_entry_bar", 0),
        "future_entry_session_not_reached_before": before_counts.get(
            "future_entry_session_not_reached", 0
        ),
        "future_entry_session_not_reached_after": after_counts.get(
            "future_entry_session_not_reached", 0
        ),
        "ledger_path": after.get("ledger_path"),
        "summary_path": after.get("summary_path"),
        "latest_summary_path": after.get("latest_summary_path"),
        "warehouse_date_max": (after.get("warehouse") or {}).get("date_max"),
        "trade_enabled": after.get("trade_enabled"),
        "strategy_behavior_changed": after.get("strategy_behavior_changed"),
    }


def build_result() -> dict[str, Any]:
    before_prediction = read_json(PREDICTION_SUMMARY, {})
    before_entity = read_json(ENTITY_SUMMARY, {})

    after_prediction = persist_prediction_market_event_outcome_ledger(DATE_TAG)
    after_entity = persist_entity_theme_news_outcome_ledger(DATE_TAG)

    prediction = surface_summary(
        "prediction_market_event_observer", before_prediction, after_prediction
    )
    entity = surface_summary("entity_theme_news_observer", before_entity, after_entity)
    surfaces = [prediction, entity]

    refreshed = all(
        surface["future_entry_session_not_reached_after"] > 0 for surface in surfaces
    )
    stale_removed = all(
        surface["unsettled_no_entry_bar_after"]
        < surface["unsettled_no_entry_bar_before"]
        for surface in surfaces
    )
    row_counts_stable = all(
        surface["candidate_outcome_row_count_before"]
        == surface["candidate_outcome_row_count_after"]
        for surface in surfaces
    )
    no_strategy_change = all(
        surface["trade_enabled"] is False
        and surface["strategy_behavior_changed"] is False
        for surface in surfaces
    )
    accepted = refreshed and stale_removed and row_counts_stable and no_strategy_change
    decision = (
        "accepted_measurement_repair_observer_latest_outcome_summary_refreshed"
        if accepted
        else "blocked_observer_latest_outcome_summary_refresh_incomplete"
    )
    failed = []
    if not refreshed:
        failed.append("future_entry_status_missing_after_refresh")
    if not stale_removed:
        failed.append("old_no_entry_bucket_not_reduced")
    if not row_counts_stable:
        failed.append("candidate_row_count_changed")
    if not no_strategy_change:
        failed.append("strategy_or_trade_flag_changed")

    baseline = baseline_metrics()
    now = utc_now()
    summary = {
        "prediction_market_future_entry_rows": prediction[
            "future_entry_session_not_reached_after"
        ],
        "prediction_market_no_entry_rows_before": prediction[
            "unsettled_no_entry_bar_before"
        ],
        "prediction_market_no_entry_rows_after": prediction[
            "unsettled_no_entry_bar_after"
        ],
        "entity_theme_future_entry_rows": entity[
            "future_entry_session_not_reached_after"
        ],
        "entity_theme_no_entry_rows_before": entity["unsettled_no_entry_bar_before"],
        "entity_theme_no_entry_rows_after": entity["unsettled_no_entry_bar_after"],
        "row_counts_stable": row_counts_stable,
        "failed_checks": failed,
    }

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": "accepted_measurement_repair" if accepted else "blocked",
        "accepted": accepted,
        "accepted_alpha": False,
        "alpha_ready": False,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": "observer_outcome_summary_materialization_repair",
        "implementation_mode": "canonical_observer_outcome_summary_refresh",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": [
            "prediction_market latest outcome summary refresh",
            "entity_theme latest outcome summary refresh",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "semantic_measurement_defect_materialization",
        "new_evidence_axis": (
            "exp-20260705-006 fixed the observer status branch, but canonical "
            "latest outcome summaries still contained stale generated status "
            "counts; this run materializes that existing semantic repair."
        ),
        "prediction": {
            "success_probability": 0.85,
            "expected_ev_delta": 0.0,
            "expected_pnl_delta": 0.0,
            "main_failure_modes": [
                "refresh helper rewrites with old code",
                "summary consumers require backward-compatible status counts",
                "atomic temp files block canonical writes",
            ],
            "confidence_reason": (
                "exp-20260705-006 already added the status branch; current "
                "canonical summaries are stale generated files."
            ),
            "recorded_at": "2026-07-05T08:11:27+00:00",
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
        },
        "summary": summary,
        "observer_surfaces": surfaces,
        "gate1": {
            "passed": True,
            "baseline_metrics": baseline,
            "note": "Measurement repair only; canonical strategy baseline unchanged.",
        },
        "gate2": {
            "passed": True,
            "fields": [
                "outcome_status",
                "outcome_status_detail",
                "entry_date",
                "replacement_value_vs_cash_usd",
                "replacement_value_vs_spy_usd",
                "replacement_value_vs_qqq_usd",
            ],
            "field_reality": {
                "prediction_market_latest_summary": repo_rel(PREDICTION_SUMMARY),
                "entity_theme_latest_summary": repo_rel(ENTITY_SUMMARY),
                "target_price_relevance": (
                    "not_applicable_observer_fixed_horizon; no orders or exits "
                    "are scheduled by this observer measurement ledger"
                ),
                "entry_date_relevance": (
                    "settled rows retain entry_date; future-entry rows are "
                    "correctly marked before entry_date exists"
                ),
            },
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": baseline["survival_rate"],
            "note": "No executable filter, rank, size, exit, or order policy changed.",
        },
        "gate4": {
            "passed": accepted,
            "mode": "measurement_repair_status_materialization",
            "failed_checks": failed,
            "acceptance_checks": {
                "future_entry_status_present_after_refresh": refreshed,
                "old_no_entry_bucket_reduced": stale_removed,
                "candidate_row_counts_stable": row_counts_stable,
                "strategy_and_trade_flags_unchanged": no_strategy_change,
            },
        },
        "production_impact": {
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "trade_enabled": False,
            "live_ready": False,
            "daily_snapshot_changed": True,
            "parity_note": (
                "Only observer-only outcome ledger and summary files were "
                "regenerated from existing helpers; no production trade path changed."
            ),
        },
        "calibration": {
            "predicted_success_probability": 0.85,
            "actual_success": 1 if accepted else 0,
            "predicted_failure_mode_hit": not accepted,
            "surprise_note": (
                "Canonical summaries were stale as expected; regeneration applied "
                "the exp-20260705-006 status split."
                if accepted
                else "Refresh did not fully materialize the repaired status split."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The code-level semantic repair had not been propagated into "
                "the canonical latest outcome summary files, so downstream "
                "readiness checks still saw the old no-entry bucket."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune prediction-market or entity-theme observer "
                "thresholds, ticker maps, horizons, notional, or source bundles "
                "based only on these current future-entry rows."
            ),
            "new_evidence_required": (
                "Wait for the warehouse to advance beyond the 2026-07-03/2026-07-04 "
                "observer event dates and produce materially more settled cash/SPY/QQQ "
                "replacement rows before observer alpha attribution."
            ),
        },
        "rejection_reason": None if accepted else ";".join(failed),
        "next_retry_requires": [
            "materially more settled observer outcome rows after warehouse date_max advances",
            "or a genuinely different PIT observer source relation",
        ],
        "changed_files": CHANGED_FILES,
        "related_files": [
            repo_rel(PREDICTION_SUMMARY),
            repo_rel(ENTITY_SUMMARY),
            repo_rel(OUT_JSON),
        ],
        "reproduction_commands": [
            f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER_WINDOWS}",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_prediction_market_event_observer.py quant\\test_entity_theme_news_observer.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": None,
    }


def build_log(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "accepted",
        "accepted_alpha",
        "alpha_ready",
        "decision",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "changed_variable",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "causal_components",
        "nearby_prior_experiments",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "summary",
        "observer_surfaces",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "calibration",
        "post_run_reflection",
        "rejection_reason",
        "next_retry_requires",
        "changed_files",
        "related_files",
        "reproduction_commands",
        "lean_quality_passed",
    ]
    return {key: payload.get(key) for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        f"# {EXPERIMENT_ID} - observer outcome summary refresh",
        "",
        f"- status: {payload['status']}",
        f"- decision: {payload['decision']}",
        (
            "- prediction-market no-entry/future-entry: "
            f"{summary['prediction_market_no_entry_rows_before']} -> "
            f"{summary['prediction_market_no_entry_rows_after']} / "
            f"{summary['prediction_market_future_entry_rows']}"
        ),
        (
            "- entity-theme no-entry/future-entry: "
            f"{summary['entity_theme_no_entry_rows_before']} -> "
            f"{summary['entity_theme_no_entry_rows_after']} / "
            f"{summary['entity_theme_future_entry_rows']}"
        ),
        f"- failed checks: {', '.join(summary['failed_checks']) or 'none'}",
        "",
        "No signal generation, ranking, sizing, exits, orders, candidate maps, "
        "horizons, or notional changed.",
        "",
        "## Boundary",
        "",
        payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
        "",
        "## Reproduce",
        "",
        f"- `{RUNNER_COMMAND}`",
        "- `.\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict`",
    ]
    return "\n".join(lines) + "\n"


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "generated_at": payload["timestamp"],
        "runner": RUNNER,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "ticket": repo_rel(TICKET_JSON),
        "files": CHANGED_FILES,
        "reproduction_commands": payload["reproduction_commands"],
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(build_log(payload), allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    ticket = read_json(TICKET_JSON, {})
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": payload["accepted_alpha"],
            "alpha_ready": payload["alpha_ready"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "summary": payload["summary"],
        },
        status=payload["status"],
        fields={
            **{key: value for key, value in ticket.items() if key not in {"result", "status"}},
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "alpha_hypothesis": payload["alpha_hypothesis"],
            "change_type": payload["change_type"],
            "implementation_mode": payload["implementation_mode"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "causal_components": payload["causal_components"],
            "nearby_prior_experiments": payload["nearby_prior_experiments"],
            "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
            "new_evidence_type": payload["new_evidence_type"],
            "new_evidence_axis": payload["new_evidence_axis"],
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "delta_metrics": payload["delta_metrics"],
            "production_impact": payload["production_impact"],
            "calibration": payload["calibration"],
            "post_run_reflection": payload["post_run_reflection"],
            "rejection_reason": payload["rejection_reason"],
            "next_retry_requires": payload["next_retry_requires"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = build_result()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": payload["experiment_id"],
                "status": payload["status"],
                "decision": payload["decision"],
                "summary": payload["summary"],
                "artifact": repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
