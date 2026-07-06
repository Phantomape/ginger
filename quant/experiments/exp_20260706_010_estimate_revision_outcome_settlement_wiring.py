"""exp-20260706-010: estimate-revision outcome settlement wiring.

Measurement repair only. The estimate-revision candidate-match alpha cannot be
evaluated credibly while fixed-horizon replacement outcomes are materialized one
horizon at a time by experiment runners. This experiment factors the settlement
into a shared helper and wires it after the post-quant candidate-match refresh.
No strategy behavior is changed.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from estimate_revision_outcomes import persist_estimate_revision_outcomes  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


EXPERIMENT_ID = "exp-20260706-010"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "estimate_revision_outcome_settlement_wiring"
RUNNER = f"quant/experiments/exp_20260706_010_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

AS_OF_DATE = "2026-06-29"
BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
REVISION_LEDGER = REPO_ROOT / "data" / "non_ohlcv" / "estimate_revision_ledger_20260629.jsonl"
REVISION_SUMMARY = (
    REPO_ROOT / "data" / "non_ohlcv" / "estimate_revision_ledger_summary_20260629.json"
)
HOT_WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main_hot.sqlite"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260706_010_{SLUG}.json"
OUTCOME_LEDGER = OUT_DIR / "estimate_revision_outcomes_20260629.jsonl"
OUTCOME_SUMMARY = OUT_DIR / "estimate_revision_outcome_summary_20260629.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Alpha-enabling repair: estimate-revision candidate-match alpha cannot be "
    "evaluated credibly while H0/H1/H3/H5/H10 replacement outcomes are manually "
    "materialized one horizon at a time; wire the fixed matched-row outcome "
    "settlement into the shared run path so newly mature 2026-06-29 H3 rows and "
    "future rows are produced without threshold, ranking, sizing, exit, or order "
    "changes."
)
ALPHA_HYPOTHESIS = (
    "Estimate-revision direction may have replacement value when it overlaps "
    "same-day production-visible candidate rows, but the alpha remains blocked "
    "until matched rows have shared, repeatable H3/H5/H10 outcomes."
)
CHANGED_VARIABLE = "estimate_revision_candidate_match_outcome_settlement_daily_wiring_v1"
CHANGE_TYPE = "alpha_enabling_forward_outcome_settlement_wiring"
MECHANISM_FAMILY = "production_visible_estimate_revision_candidate_match_attribution"
TRIAL_FAMILY = "estimate_revision_candidate_match_outcome_ledger_daily_wiring"
TRIAL_VARIANT_ID = "estimate_revision_outcome_settlement_horizons_h0_h1_h3_h5_h10_v1"
NEW_EVIDENCE_AXIS = (
    "One-time routine-materialization wiring for estimate-revision matched "
    "candidate outcome settlement plus newly settled H3 cash/SPY/QQQ rows for "
    "the 2026-06-29 cohort because the hot warehouse now reaches 2026-07-02; "
    "no thresholds, response functions, ranks, notional, hold days, or "
    "condition slices change."
)
NEARBY_PRIORS = ["exp-20260630-022", "exp-20260701-006", "exp-20260703-010"]
CHANGED_FILES = [
    "quant/estimate_revision_outcomes.py",
    "quant/run.py",
    "quant/test_estimate_revision_outcomes.py",
    "quant/test_run_daily_wiring.py",
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260706_010_{SLUG}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: str | Path) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8-sig", errors="replace") as handle:
        for raw in handle:
            text = raw.strip()
            if text:
                payload = json.loads(text)
                if isinstance(payload, dict):
                    rows.append(payload)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_PATH, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(int(row.get("signals_generated") or 0) for row in windows)
    survived = sum(int(row.get("signals_survived") or 0) for row in windows)
    drawdowns = [
        float(row.get("max_drawdown_pct"))
        for row in windows
        if row.get("max_drawdown_pct") is not None
    ]
    return {
        "baseline_result_file": repo_rel(BASELINE_PATH),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
        "windows": windows,
    }


def _prediction(ticket: dict[str, Any]) -> dict[str, Any]:
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    if isinstance(prediction, dict) and prediction:
        return prediction
    return {
        "success_probability": 0.74,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "helper_scope_mismatch",
            "hot_warehouse_missing_comparator_bars",
            "run_py_hook_breaks_quant_signal_payload",
            "audit_flags_manual_materialization",
        ],
        "confidence_reason": (
            "Prior manual H0/H1 refreshes proved the calculation; the remaining "
            "repair is shared settlement plus daily wiring."
        ),
    }


def _calibration(
    prediction: dict[str, Any],
    measurement_passed: bool,
    realized_failure_modes: list[str],
) -> dict[str, Any]:
    probability = float(prediction.get("success_probability") or 0.0)
    actual = 1.0 if measurement_passed else 0.0
    predicted_failures = prediction.get("main_failure_modes") or []
    return {
        "actual_decision": "accepted_measurement_repair" if measurement_passed else "blocked",
        "actual_success": actual,
        "predicted_success_probability": probability,
        "brier_score": round((probability - actual) ** 2, 4),
        "predicted_failure_modes": predicted_failures,
        "realized_failure_modes": realized_failure_modes,
        "predicted_failure_mode_hit": bool(set(predicted_failures) & set(realized_failure_modes)),
    }


def build_result() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    prediction = _prediction(ticket)
    baseline = baseline_metrics()
    outcome_summary = persist_estimate_revision_outcomes(
        as_of=AS_OF_DATE,
        data_dir=REPO_ROOT / "data",
        output_dir=OUT_DIR,
        ledger_path=REVISION_LEDGER,
        source_summary_path=REVISION_SUMMARY,
        warehouse_path=HOT_WAREHOUSE,
        generated_at=datetime.now(timezone.utc),
        run_adapter_changed=False,
    )
    outcome_rows = read_jsonl(OUTCOME_LEDGER)

    matched_rows = int(outcome_summary.get("matched_candidate_rows") or 0)
    h3_closed = int((outcome_summary.get("closed_rows_by_horizon") or {}).get("h3") or 0)
    h3_comparator_complete = int(
        (outcome_summary.get("comparator_complete_rows_by_horizon") or {}).get("h3") or 0
    )
    measurement_blockers: list[str] = []
    if baseline.get("window_count") != 3:
        measurement_blockers.append("baseline_standard_windows_missing")
    if not REVISION_LEDGER.exists():
        measurement_blockers.append("revision_ledger_missing")
    if not HOT_WAREHOUSE.exists():
        measurement_blockers.append("hot_warehouse_missing")
    if outcome_summary.get("status") != "ok":
        measurement_blockers.append(f"outcome_summary_status_{outcome_summary.get('status')}")
    if matched_rows < 5:
        measurement_blockers.append("predeclared_20260629_matched_rows_below_5")
    if h3_closed < matched_rows:
        measurement_blockers.append("h3_outcomes_not_fully_settled")
    if h3_comparator_complete < matched_rows:
        measurement_blockers.append("h3_spy_qqq_comparators_missing")
    if not OUTCOME_LEDGER.exists() or not OUTCOME_SUMMARY.exists():
        measurement_blockers.append("experiment_outcome_files_missing")

    alpha_blockers = []
    if int(outcome_summary.get("nonflat_usable_matched_candidate_rows") or 0) < 20:
        alpha_blockers.append("matched_nonflat_sample_too_thin")
    for horizon in ("h5", "h10"):
        if int((outcome_summary.get("closed_rows_by_horizon") or {}).get(horizon) or 0) < 20:
            alpha_blockers.append(f"{horizon}_outcomes_not_mature")

    measurement_passed = not measurement_blockers
    status = "accepted_measurement_repair" if measurement_passed else "blocked"
    decision = (
        "accepted_measurement_repair_estimate_revision_outcome_settlement_wiring"
        if measurement_passed
        else "blocked_estimate_revision_outcome_settlement_wiring"
    )
    realized_failure_modes = [*measurement_blockers, *alpha_blockers]
    strategy_delta = {
        "expected_value_score_sum_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "signals_generated_delta": 0,
        "signals_survived_delta": 0,
        "strategy_behavior_changed": False,
    }
    production_impact = {
        "trade_enabled": False,
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": True,
        "daily_snapshot_exposed": True,
        "entry_rules_changed": False,
        "exit_rules_changed": False,
        "ranking_changed": False,
        "sizing_changed": False,
        "live_orders_changed": False,
        "paper_orders_changed": False,
        "watchlist_changed": False,
        "llm_decision_boundary_changed": False,
        "live_ready": False,
        "live_realism_evaluated": False,
        "parity_note": (
            "The daily run now writes a default-off outcome-settlement summary "
            "after the post-quant estimate-revision candidate match. It does "
            "not feed entry, exit, ranking, sizing, LLM, or order logic."
        ),
    }
    result = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "accepted": measurement_passed,
        "accepted_alpha": False,
        "alpha_ready": False,
        "observed_only_lead": False,
        "lane": LANE,
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "shared_helper_plus_daily_outcome_settlement_wiring",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": [
            "shared fixed-horizon outcome helper",
            "run.py post-quant candidate-match settlement hook",
            "hot warehouse cash/SPY/QQQ replacement values",
            "no strategy behavior change",
        ],
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "routine_materialization_wiring_plus_new_h3_settled_rows",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": _calibration(prediction, measurement_passed, realized_failure_modes),
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260630-022": "Manual H0/H1/H3/H5/H10-shaped outcome ledger; only H0 mature then.",
                "exp-20260701-006": "Manual H1 refresh for the same estimate-revision matched rows.",
                "exp-20260703-010": "Post-quant estimate-revision ledger timing repair.",
                "novelty_gate": ticket.get("novelty"),
            },
            "3_single_policy_bundle": (
                "One measurement bundle: shared outcome settlement plus daily "
                "default-off wiring. No thresholds, rank, hold, notional, exit, "
                "or order policy changed."
            ),
            "4_success_failure_standard": (
                "Accept only if 2026-06-29 matched candidate rows close H3 "
                "cash/SPY/QQQ outcomes, run wiring is testable, and baseline "
                "strategy metrics remain unchanged."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "as_of_date": AS_OF_DATE,
            "horizons": outcome_summary.get("horizons"),
            "proxy_notional_usd": outcome_summary.get("proxy_notional_usd"),
            "baseline_result_file": repo_rel(BASELINE_PATH),
            "revision_ledger": repo_rel(REVISION_LEDGER),
            "revision_summary": repo_rel(REVISION_SUMMARY),
            "hot_warehouse": repo_rel(HOT_WAREHOUSE),
            "outcome_ledger": repo_rel(OUTCOME_LEDGER),
            "outcome_summary": repo_rel(OUTCOME_SUMMARY),
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            **strategy_delta,
            "matched_candidate_rows": matched_rows,
            "h3_closed_rows": h3_closed,
            "h3_comparator_complete_rows": h3_comparator_complete,
            "h5_closed_rows": int(
                (outcome_summary.get("closed_rows_by_horizon") or {}).get("h5") or 0
            ),
            "h10_closed_rows": int(
                (outcome_summary.get("closed_rows_by_horizon") or {}).get("h10") or 0
            ),
            "nonflat_usable_matched_candidate_rows": int(
                outcome_summary.get("nonflat_usable_matched_candidate_rows") or 0
            ),
        },
        "gate1": {
            "passed": BASELINE_PATH.exists() and baseline.get("window_count") == 3,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": REVISION_LEDGER.exists()
            and HOT_WAREHOUSE.exists()
            and matched_rows >= 5
            and h3_comparator_complete >= matched_rows,
            "dependencies_validated": REVISION_LEDGER.exists() and HOT_WAREHOUSE.exists(),
            "fields_checked": [
                "ticker",
                "as_of_date",
                "estimate_revision_usable",
                "matched_candidate_today",
                "entry_date",
                "target_price",
                "h3_replacement_value_vs_cash_usd",
                "h3_replacement_value_vs_spy_usd",
                "h3_replacement_value_vs_qqq_usd",
            ],
            "entry_date_rows": sum(1 for row in outcome_rows if row.get("entry_date")),
            "target_price_scope": (
                "Not applicable: fixed-horizon replacement attribution only; "
                "no target exits or orders are scheduled."
            ),
            "source_metadata": {
                "revision_ledger": repo_rel(REVISION_LEDGER),
                "revision_summary": repo_rel(REVISION_SUMMARY),
                "hot_warehouse": repo_rel(HOT_WAREHOUSE),
                "warehouse_date_range": outcome_summary.get("warehouse_date_range"),
                "matched_candidate_tickers": outcome_summary.get("matched_candidate_tickers"),
                "warehouse_missing_matched_tickers": outcome_summary.get(
                    "warehouse_missing_matched_tickers"
                ),
            },
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "signals_generated": baseline.get("signals_generated"),
            "signals_survived": baseline.get("signals_survived"),
            "survival_rate": baseline.get("survival_rate"),
            "note": "No executable entry, exit, filter, ranking, or sizing rule was added.",
        },
        "gate4": {
            "passed": measurement_passed,
            "accepted_alpha": False,
            "alpha_ready": False,
            "decision": decision,
            "measurement_blockers": measurement_blockers,
            "alpha_blockers": alpha_blockers,
            "measurement_repair_only": True,
            "strategy_rerun_required": False,
            "before_after_strategy_delta": strategy_delta,
            "summary": (
                "Accepted measurement repair: shared outcome settlement now "
                "closes the 2026-06-29 H3 matched candidate rows."
                if measurement_passed
                else "Blocked: estimate-revision outcome settlement did not meet the H3 contract."
            ),
        },
        "outcome_summary": outcome_summary,
        "matched_outcome_rows": outcome_rows,
        "production_impact": production_impact,
        "post_run_reflection": {
            "why_result_happened": (
                "The hot warehouse now reaches 2026-07-02, so the 2026-06-29 "
                "matched estimate-revision cohort has mature H3 bars for each "
                "matched ticker plus SPY/QQQ comparators. Moving settlement into "
                "a shared helper prevents another manual horizon-refresh ID."
                if measurement_passed
                else "The shared helper or warehouse coverage did not satisfy the H3 settlement contract."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune revision direction thresholds, response curves, "
                "notional, rank, hold, or condition slices from this tiny cohort."
            ),
            "new_evidence_required": (
                "Next alpha-compliant revision work needs H5/H10 settlement and "
                "materially more matched/non-flat rows, another settled production "
                "revision cohort, or a distinct unsaturated PIT expectation source."
            ),
        },
        "routine_materialization_guard": {
            "pipeline_wiring": True,
            "manual_materialization_replaced": True,
            "canonical_non_ohlcv_written_by_runner": False,
        },
        "changed_files": CHANGED_FILES,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "manifest": repo_rel(MANIFEST_JSON),
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant/test_estimate_revision_outcomes.py quant/test_run_daily_wiring.py -q",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
    }
    return result


def compact_log_record(result: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in result.items()
        if key not in {"matched_outcome_rows"}
    }


def build_card(result: dict[str, Any]) -> str:
    gate4 = result["gate4"]
    delta = result["delta_metrics"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} - Estimate Revision Outcome Settlement Wiring",
            "",
            f"- Status: `{result['status']}`",
            f"- Decision: `{result['decision']}`",
            f"- Lane: `{LANE}`",
            f"- H3 closed rows: {delta['h3_closed_rows']} / {delta['matched_candidate_rows']}",
            f"- H3 comparator-complete rows: {delta['h3_comparator_complete_rows']}",
            f"- Strategy delta: {result['delta_metrics']['strategy_behavior_changed']}",
            "",
            "## Hypothesis",
            HYPOTHESIS,
            "",
            "## Gate 4",
            gate4["summary"],
            "",
            "## Next Evidence",
            result["post_run_reflection"]["new_evidence_required"],
            "",
            "## Reproduce",
            "```powershell",
            *result["reproduction_commands"],
            "```",
            "",
        ]
    )


def write_manifest(result: dict[str, Any]) -> None:
    write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": result["status"],
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log": result["log"],
            "runner": RUNNER,
            "generated_at": result["timestamp"],
            "changed_files": CHANGED_FILES,
            "reproduction_commands": result["reproduction_commands"],
        },
    )


def update_ticket(result: dict[str, Any]) -> None:
    ticket = read_json(TICKET_JSON, {})
    ticket.update(
        {
            "status": result["status"],
            "completed_at": result["timestamp"],
            "decision": result["decision"],
            "result": {
                "accepted": result["accepted"],
                "accepted_alpha": False,
                "alpha_ready": False,
                "decision": result["decision"],
                "artifact": result["artifact"],
                "log": result["log"],
                "runner": RUNNER,
                "gate4": result["gate4"],
                "summary": result["gate4"]["summary"],
            },
            "gate1": result["gate1"],
            "gate2": result["gate2"],
            "gate3": result["gate3"],
            "gate4": result["gate4"],
            "production_impact": result["production_impact"],
            "post_run_reflection": result["post_run_reflection"],
            "next_retry_requires": result["post_run_reflection"]["new_evidence_required"],
        }
    )
    write_json(TICKET_JSON, ticket)


def main() -> int:
    result = build_result()
    write_json(OUT_JSON, result)
    save_experiment_log_entry(compact_log_record(result), allow_duplicate=True)
    write_text(CARD_MD, build_card(result))
    write_manifest(result)
    update_ticket(result)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=result["prediction"],
        result={
            "accepted": result["accepted"],
            "accepted_alpha": False,
            "alpha_ready": False,
            "observed_only_lead": False,
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log": result["log"],
            "runner": RUNNER,
            "gate4": result["gate4"],
            "summary": result["gate4"]["summary"],
        },
        status=result["status"],
        fields={
            "owner": OWNER,
            "hypothesis": HYPOTHESIS,
            "alpha_hypothesis": ALPHA_HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": result["implementation_mode"],
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": result["causal_components"],
            "nearby_prior_experiments": NEARBY_PRIORS,
            "multiple_testing_risk_bucket": "low",
            "new_evidence_type": result["new_evidence_type"],
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
            "decision": result["decision"],
            "artifact": result["artifact"],
            "log_file": result["log"],
            "card_file": repo_rel(CARD_MD),
            "gate1": result["gate1"],
            "gate2": result["gate2"],
            "gate3": result["gate3"],
            "gate4": result["gate4"],
            "production_impact": result["production_impact"],
            "post_run_reflection": result["post_run_reflection"],
            "next_retry_requires": result["post_run_reflection"]["new_evidence_required"],
            "changed_files": CHANGED_FILES,
            "reproduction_commands": result["reproduction_commands"],
        },
    )
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": result["status"],
                "decision": result["decision"],
                "h3_closed_rows": result["delta_metrics"]["h3_closed_rows"],
                "matched_candidate_rows": result["delta_metrics"]["matched_candidate_rows"],
                "artifact": result["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
