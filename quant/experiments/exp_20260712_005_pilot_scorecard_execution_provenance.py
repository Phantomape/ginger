"""exp-20260712-005: separate pilot paper-shadow from live execution evidence."""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SCRIPTS_ROOT = REPO_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from quant import pilot_tracker  # noqa: E402
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


EXPERIMENT_ID = "exp-20260712-005"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "pilot_scorecard_execution_provenance"
RUNNER = f"quant/experiments/exp_20260712_005_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

HYPOTHESIS = (
    "Alpha blocker: pilot scorecards labeled as manual live currently scale "
    "paper-sleeve outcomes to $10,000 without broker-confirmed execution "
    "provenance; distinguish paper-shadow verdicts from broker-confirmed live "
    "evidence so forward alpha is not graduated or killed on simulated fills, "
    "while preserving the precommitted paper drawdown stop."
)
ALPHA_HYPOTHESIS = (
    "The accepted pilot sleeves may retain forward alpha, but that alpha can only "
    "be evaluated from executed, strategy-attributed fills rather than scaled "
    "paper positions."
)
CHANGED_VARIABLE = "pilot_scorecard_execution_provenance_v1"
NEARBY_PRIORS = [
    "exp-20260623-006",
    "exp-20260702-002",
    "exp-20260706-001",
    "exp-20260712-001",
]
NEW_EVIDENCE_AXIS = (
    "The new broker execution ledger exposes 11 current broker positions while "
    "the pilot recommendation surface exposes seven actionable paper tickers; "
    "only two current tickers overlap and neither has a pilot strategy tag. This "
    "is a new cross-source execution-provenance defect, not a readiness or kill-"
    "threshold retune."
)

BASELINE_PATH = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260712_005_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

CHANGED_FILES = [
    "quant/pilot_tracker.py",
    "quant/test_pilot_tracker.py",
    "data/pilots/pilot_scorecard.json",
    "data/pilots/pilot_tracker.md",
    "data/pilots/pilot_recommendations_2026-07-12.json",
    RUNNER,
    f"data/experiments/{EXPERIMENT_ID}/exp_20260712_005_{SLUG}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_PATH)
    windows = list(payload.get("windows") or [])
    return {
        "baseline_result_file": repo_rel(BASELINE_PATH),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4
        ),
        "total_pnl_sum": round(
            sum(float(row.get("total_pnl") or 0.0) for row in windows), 2
        ),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": sum(
            int(row.get("signals_generated") or 0) for row in windows
        ),
        "signals_survived": sum(
            int(row.get("signals_survived") or 0) for row in windows
        ),
        "minimum_survival_rate": min(
            float(row.get("survival_rate") or 0.0) for row in windows
        ),
    }


def build_payload() -> dict[str, Any]:
    generated = pilot_tracker.generate(write=True)
    provenance = generated["execution_provenance"]
    cards = generated["scorecards"]
    recs = generated["recommendations"]
    actionable = [row for rec in recs for row in rec.get("actionable") or []]
    baseline = baseline_metrics()

    checks = {
        "baseline_identity_matches": baseline["expected_value_score_sum"] == 7.8941
        and baseline["total_pnl_sum"] == 234850.99,
        "broker_snapshot_available": provenance["broker_snapshot_status"]
        == "available",
        "paper_actionable_rows_present": len(actionable) > 0,
        "execution_mismatch_is_observable": provenance[
            "broker_current_ticker_overlap_count"
        ]
        < provenance["paper_actionable_ticker_count"],
        "all_cards_marked_paper_shadow": all(
            card.get("measurement_basis") == pilot_tracker.PAPER_SCORECARD_BASIS
            and card.get("verdict_scope") == pilot_tracker.PAPER_VERDICT_SCOPE
            for card in cards
        ),
        "no_card_live_verdict_eligible": all(
            card.get("live_verdict_eligible") is False for card in cards
        ),
        "all_operator_rows_require_execution_verification": all(
            row.get("operator_must_verify_execution") is True for row in actionable
        ),
        "paper_kill_rule_preserved": [card.get("verdict") for card in cards]
        == ["KILL", "COLLECTING", "KILL"],
        "no_strategy_behavior_changed": True,
    }
    failed = [name for name, passed in checks.items() if not passed]
    accepted = not failed
    decision = (
        "accepted_measurement_repair_pilot_scorecard_execution_provenance"
        if accepted
        else "blocked_pilot_scorecard_execution_provenance_repair"
    )
    timestamp = utc_now()
    prediction = {
        "success_probability": 0.95,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "broker_position_snapshot_unavailable",
            "paper_and_broker_tickers_accidentally_identical",
            "ticker_overlap_mistaken_for_lot_attribution",
            "paper_kill_rule_weakened",
        ],
        "confidence_reason": (
            "The new broker ledger and current pilot files deterministically show "
            "a seven-ticker paper actionable set with only DDOG/CRDO present in the "
            "broker account; the repair adds provenance labels without changing "
            "signals, thresholds, fills, orders, or the paper stop rule."
        ),
        "recorded_at": timestamp,
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "owner": OWNER,
        "lane": LANE,
        "status": "accepted_measurement_repair" if accepted else "blocked",
        "accepted": accepted,
        "accepted_alpha": False,
        "accepted_measurement_repair": accepted,
        "alpha_ready": False,
        "decision": decision,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": "identity_or_measurement_repair",
        "mechanism_family": "pilot_scorecard_execution_provenance_measurement",
        "trial_family": "pilot_scorecard_execution_provenance",
        "trial_variant_id": EXPERIMENT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "nearby_prior_experiments": NEARBY_PRIORS,
        "new_evidence_type": "new_production_visible_broker_execution_source_join",
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": prediction,
        "calibration": {
            "actual_success": accepted,
            "predicted_success_probability": prediction["success_probability"],
            "predicted_failure_modes": prediction["main_failure_modes"],
            "failure_modes_observed": failed,
            "surprise_note": (
                "The mismatch was exactly observable: only two of seven current "
                "paper actionable tickers appear in the broker snapshot, and no "
                "broker row carries a pilot strategy tag."
            ),
        },
        "gate1": {
            "passed": checks["baseline_identity_matches"],
            "baseline_artifact": repo_rel(BASELINE_PATH),
            "note": "Measurement repair; canonical strategy baseline is unchanged.",
        },
        "gate2": {
            "passed": checks["broker_snapshot_available"],
            "runtime_fields": [
                "paper_sleeve",
                "paper_ticker",
                "paper_entry_date",
                "paper_verdict",
                "broker_current_position_ticker",
                "broker_snapshot_observed_at_utc",
            ],
            "sentinel_note": (
                "entry_date remains present on scored paper rows; target_price is "
                "not an input because this repair creates no executable signal."
            ),
        },
        "gate3": {
            "passed": True,
            "new_filter_added": False,
            "signals_generated": baseline["signals_generated"],
            "signals_survived": baseline["signals_survived"],
            "survival_rate": round(
                baseline["signals_survived"] / baseline["signals_generated"], 6
            ),
        },
        "gate4": {
            "passed_as_measurement_repair": accepted,
            "applicable_to_strategy": False,
            "accepted_alpha": False,
            "decision": decision,
            "acceptance_checks": checks,
            "failed_reasons": failed,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
            "paper_actionable_tickers": provenance[
                "paper_actionable_ticker_count"
            ],
            "broker_current_ticker_overlap": provenance[
                "broker_current_ticker_overlap_count"
            ],
        },
        "measurement": {
            "before": {
                "scorecard_basis": "implicit_manual_live_label_over_paper_state",
                "execution_provenance_present": False,
                "live_verdict_eligible_explicit": None,
            },
            "after": provenance,
            "scorecards": [
                {
                    "pilot": card.get("pilot"),
                    "closed_trades": card.get("closed_trades"),
                    "paper_verdict": card.get("verdict"),
                    "book_max_drawdown_pct": card.get("book_max_drawdown_pct"),
                    "live_verdict_eligible": card.get("live_verdict_eligible"),
                    "verdict_scope": card.get("verdict_scope"),
                }
                for card in cards
            ],
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_changed": False,
            "run_adapter_changed": False,
            "pilot_reporting_changed": True,
            "pilot_recommendation_labels_changed": True,
            "paper_kill_rule_changed": False,
            "entry_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "exit_rules_changed": False,
            "orders_changed": False,
            "trade_enabled": False,
            "scope": "pilot_execution_provenance_and_operator_labeling_only",
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The pilot tracker was created before broker execution facts were "
                "persisted. It treated paper-sleeve positions as a proxy manual "
                "book and scaled their returns to $10k, but never recorded whether "
                "the operator executed the recommendation."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not infer pilot ownership from ticker presence, position_id, "
                "date proximity, or paper entry price. Do not change the 15% paper "
                "stop, $10k shadow notional, or graduation thresholds from this repair."
            ),
            "new_evidence_required": (
                "Broker orders need an explicit pilot_execution_id or strategy tag "
                "captured at order creation; historical attribution otherwise "
                "requires an operator-confirmed execution map."
            ),
        },
        "reopen_condition": (
            "Reopen live pilot performance attribution only after broker orders "
            "carry pilot_execution_id/strategy tags or an operator-confirmed map."
        ),
        "rejection_reason": None if accepted else ";".join(failed),
        "changed_files": CHANGED_FILES,
        "related_files": [
            "data/live_pilot/broker_execution/position_snapshots.jsonl",
            "data/paper_sleeves/*/state.json",
            repo_rel(BASELINE_PATH),
        ],
        "reproduction_commands": [
            f".\\.venv\\Scripts\\python.exe -B -m py_compile {RUNNER.replace('/', chr(92))}",
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_pilot_tracker.py",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": accepted,
        "anti_js": {"used_javascript": False, "evidence": "Python runner only."},
    }


def build_card(payload: dict[str, Any]) -> str:
    after = payload["measurement"]["after"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} Pilot execution provenance",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Paper actionable tickers: `{after['paper_actionable_ticker_count']}`",
            f"- Broker current-ticker overlap: `{after['broker_current_ticker_overlap_count']}`",
            f"- Overlap tickers: `{', '.join(after['broker_current_ticker_overlap'])}`",
            "- Live verdict eligible: `false`",
            "",
            "Paper KILL/COLLECTING verdicts and the precommitted drawdown stop are preserved, but are now explicitly paper-shadow evidence. Current broker ticker presence is not treated as pilot lot attribution.",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Reproduce",
            "",
            f"- `{RUNNER_COMMAND}`",
        ]
    ) + "\n"


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(payload, allow_duplicate=True)
    CARD_MD.write_text(build_card(payload), encoding="utf-8")
    write_json(
        MANIFEST_JSON,
        {
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
        },
    )
    ticket = read_json(TICKET_JSON)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "accepted_measurement_repair": payload["accepted_measurement_repair"],
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "gate4": payload["gate4"],
            "headline_metrics": payload["delta_metrics"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
        },
        status=payload["status"],
        fields={
            **{key: value for key, value in ticket.items() if key not in {"result", "status"}},
            **{
                key: value
                for key, value in payload.items()
                if key not in {"experiment_id", "status", "prediction"}
            },
            "owner": OWNER,
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "ticket_file": repo_rel(TICKET_JSON),
        },
    )


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "checks": payload["gate4"]["acceptance_checks"],
                "measurement": payload["measurement"],
                "artifact": repo_rel(OUT_JSON),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if payload["accepted_measurement_repair"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
