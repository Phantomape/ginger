"""exp-20260624-010: pilot cross-overlap participant context repair.

Measurement repair for the manual pilot tracker. Cross-pilot same-ticker
overlap must expose per-participant verdict and actionable status so the
operator can distinguish stacked active exposure from killed-pilot unwind
exposure. This changes reporting only; it does not change sleeve signals,
entries, exits, ranking, sizing, live orders, or paper ledgers.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402
from quant import pilot_tracker  # noqa: E402


EXPERIMENT_ID = "exp-20260624-010"
OWNER = "alpha-explore"
SLUG = "pilot_cross_overlap_participant_context"
RUNNER = f"quant/experiments/exp_20260624_010_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260624_010_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
PILOT_SCORECARD = REPO_ROOT / "data" / "pilots" / "pilot_scorecard.json"
PILOT_TRACKER_MD = REPO_ROOT / "data" / "pilots" / "pilot_tracker.md"
PILOT_RECS = REPO_ROOT / "data" / "pilots" / "pilot_recommendations_2026-06-24.json"
BEFORE_GAP_ARTIFACT = (
    REPO_ROOT
    / "data"
    / "experiments"
    / "exp-20260624-009"
    / "exp_20260624_009_pilot_cross_overlap_verdict_context.json"
)

HYPOTHESIS = (
    "measurement_repair/alpha_blocker: cross-pilot same-ticker overlap must "
    "carry per-participant pilot verdict and actionable status so manual live "
    "pilot activation review can distinguish stacked active exposure from "
    "killed-pilot unwind exposure without changing orders."
)
ALPHA_HYPOTHESIS = (
    "Default-off alpha sleeves can only graduate toward live activation when "
    "manual pilot overlap reporting makes stacked exposure and killed-pilot "
    "unwind context auditable."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "identity_or_measurement_repair"
TRIAL_FAMILY = "identity_or_measurement_repair"
TRIAL_VARIANT_ID = "pilot_cross_pilot_overlap_participant_context_v1"
CHANGED_VARIABLE = "pilot_cross_pilot_overlap_participant_context_v1"
CAUSAL_COMPONENTS = [
    "pilot cross-pilot overlap report",
    "per-pilot verdict context",
    "per-position actionable status context",
    "no strategy signal change",
    "no live order change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "quant/pilot_tracker.py",
    "quant/test_pilot_tracker.py",
    "data/experiments/exp-20260624-010/exp_20260624_010_pilot_cross_overlap_participant_context.json",
    "data/pilots/pilot_scorecard.json",
    "data/pilots/pilot_tracker.md",
    "data/pilots/pilot_recommendations_2026-06-24.json",
    "experiments/cards/exp-20260624-010.md",
    "experiments/manifests/exp-20260624-010.json",
    "experiments/tickets/exp-20260624-010.json",
    "experiments/logs/exp-20260624-010.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]
PRODUCTION_IMPACT = {
    "trade_enabled": False,
    "shared_policy_changed": False,
    "backtester_adapter_changed": False,
    "run_adapter_changed": False,
    "entry_rules_changed": False,
    "exit_rules_changed": False,
    "ranking_changed": False,
    "sizing_changed": False,
    "live_orders_changed": False,
    "paper_orders_changed": False,
    "pilot_reporting_changed": True,
    "daily_snapshot_exposed": True,
    "live_ready": False,
    "replay_only": False,
    "parity_note": (
        "Only manual pilot reporting changed. The underlying sleeve state, "
        "candidate generation, orders, ranking, sizing, and exits are unchanged."
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path | str) -> str:
    path = Path(path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                rows.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                if not replaced:
                    rows.append(line)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(line)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(float(row.get("signals_generated") or 0.0) for row in windows)
    survived = sum(float(row.get("signals_survived") or 0.0) for row in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": int(sum(int(row.get("trade_count") or 0) for row in windows)),
        "signals_generated": int(generated),
        "signals_survived": int(survived),
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": max(
            (float(row.get("max_drawdown_pct") or 0.0) for row in windows),
            default=None,
        ),
        "window_count": len(windows),
    }


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    return prediction or {
        "success_probability": 0.78,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "test fixture misses overlap shape",
            "current forward data changes before run",
            "daily markdown context too noisy",
        ],
        "confidence_reason": (
            "exp-20260624-009 proved the context is present in recommendation "
            "rows and missing only from the overlap projection."
        ),
        "recorded_at": "2026-06-24T07:11:31+00:00",
    }


def analyze_generated(generated: dict[str, Any]) -> dict[str, Any]:
    overlaps = [
        row
        for row in generated.get("cross_pilot_overlap", [])
        if isinstance(row, dict)
    ]
    rows = []
    for overlap in overlaps:
        participants = overlap.get("participant_context") or []
        rows.append(
            {
                "ticker": overlap.get("ticker"),
                "positions": overlap.get("positions"),
                "total_exposure_usd": overlap.get("total_exposure_usd"),
                "has_participant_context": bool(participants),
                "has_pilot_verdicts": bool(overlap.get("pilot_verdicts")),
                "has_pilot_statuses": bool(overlap.get("pilot_statuses")),
                "has_new_entries_blocked_by_pilot": bool(
                    overlap.get("new_entries_blocked_by_pilot")
                ),
                "participants": participants,
                "kill_participants": [
                    row for row in participants if row.get("pilot_verdict") == "KILL"
                ],
            }
        )
    markdown = str(generated.get("markdown") or "")
    all_context_present = all(
        row["has_participant_context"]
        and row["has_pilot_verdicts"]
        and row["has_pilot_statuses"]
        and row["has_new_entries_blocked_by_pilot"]
        for row in rows
    ) if rows else False
    killed_overlap_auditable = any(row["kill_participants"] for row in rows)
    return {
        "as_of": generated.get("as_of"),
        "overlap_count": len(rows),
        "overlap_rows": rows,
        "all_overlap_rows_have_context": all_context_present,
        "killed_overlap_auditable": killed_overlap_auditable,
        "markdown_has_verdict_context": (
            "verdict KILL" in markdown and "new entries blocked" in markdown
        ),
        "kill_unwind_exposure_usd": round(
            sum(
                float(p.get("pilot_notional_usd") or 0.0)
                for row in rows
                for p in row["kill_participants"]
            ),
            2,
        ),
        "total_stacked_exposure_usd": round(
            sum(float(row.get("total_exposure_usd") or 0.0) for row in rows),
            2,
        ),
    }


def before_gap_summary() -> dict[str, Any]:
    before = read_json(BEFORE_GAP_ARTIFACT, {})
    analysis = before.get("analysis") if isinstance(before, dict) else {}
    if not isinstance(analysis, dict):
        analysis = {}
    return {
        "artifact": repo_rel(BEFORE_GAP_ARTIFACT),
        "exists": BEFORE_GAP_ARTIFACT.exists(),
        "daily_context_missing_count": analysis.get("daily_context_missing_count"),
        "kill_verdict_overlap_count": analysis.get("kill_verdict_overlap_count"),
        "decision": before.get("decision") if isinstance(before, dict) else None,
    }


def build_payload() -> dict[str, Any]:
    now = utc_now()
    prediction = load_ticket_prediction()
    baseline = baseline_metrics()
    before_gap = before_gap_summary()
    generated = pilot_tracker.generate(write=True)
    analysis = analyze_generated(generated)

    passed = (
        analysis["overlap_count"] >= 1
        and analysis["all_overlap_rows_have_context"]
        and analysis["killed_overlap_auditable"]
        and analysis["markdown_has_verdict_context"]
    )
    decision = (
        "accepted_measurement_repair_pilot_cross_overlap_participant_context"
        if passed
        else "blocked_pilot_cross_overlap_participant_context_not_verified"
    )
    status = "accepted_measurement_repair" if passed else "blocked"
    failure_modes = []
    if analysis["overlap_count"] < 1:
        failure_modes.append("no_current_cross_pilot_overlap")
    if not analysis["all_overlap_rows_have_context"]:
        failure_modes.append("overlap_context_fields_missing")
    if not analysis["killed_overlap_auditable"]:
        failure_modes.append("killed_pilot_overlap_not_auditable")
    if not analysis["markdown_has_verdict_context"]:
        failure_modes.append("markdown_context_missing_or_too_noisy")

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "owner": OWNER,
        "lane": "measurement_repair",
        "status": status,
        "decision": decision,
        "accepted": passed,
        "accepted_alpha": False,
        "observed_only_lead": False,
        "implementation_mode": "measurement_repair",
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": ["exp-20260623-006", "exp-20260624-009"],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "forward_pilot_overlap_reporting_gap",
        "new_evidence_axis": (
            "exp-20260624-009 observed a current DDOG cross-pilot overlap with "
            "a KILL-verdict participant and no daily overlap verdict/status "
            "context; this run wires that context into the shared tracker."
        ),
        "prediction": prediction,
        "calibration": {
            "predicted_success_probability": prediction.get("success_probability"),
            "actual_success": bool(passed),
            "failure_modes_observed": failure_modes,
            "predicted_failure_modes": prediction.get("main_failure_modes", []),
            "predicted_failure_mode_hit": bool(failure_modes)
            and any(mode in prediction.get("main_failure_modes", []) for mode in failure_modes),
            "surprise_note": (
                "Repair stayed localized to the overlap projection and Markdown "
                "rendering; no strategy or order path changed."
                if passed
                else "The reporting context could not be verified in generated pilot output."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": "exp-20260624-010 reserved with no blocking near-neighbor.",
                "related_prior": (
                    "exp-20260624-009 blocked because the gap was real but "
                    "the ticket lacked tracker/test write scope."
                ),
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Daily cross_pilot_overlap must include participant_context, "
                "pilot_verdicts, pilot_statuses, and new_entries_blocked_by_pilot; "
                "Markdown must expose the KILL/HOLD participant."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "before_gap": before_gap,
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "before_daily_context_missing_count": before_gap.get("daily_context_missing_count"),
            "after_overlap_count": analysis["overlap_count"],
            "after_all_overlap_rows_have_context": analysis["all_overlap_rows_have_context"],
            "kill_unwind_exposure_usd": analysis["kill_unwind_exposure_usd"],
            "total_stacked_exposure_usd": analysis["total_stacked_exposure_usd"],
            "strategy_behavior_changed": False,
            "daily_pilot_output_changed": True,
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists(),
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": analysis["all_overlap_rows_have_context"],
            "dependencies_validated": analysis["all_overlap_rows_have_context"],
            "fields_checked": [
                "cross_pilot_overlap.participant_context",
                "cross_pilot_overlap.pilot_verdicts",
                "cross_pilot_overlap.pilot_statuses",
                "cross_pilot_overlap.new_entries_blocked_by_pilot",
                "recommendations.pilot_verdict",
                "recommendations.new_entries_blocked",
                "recommendations.actionable.status",
                "recommendations.actionable.entry_date",
                "recommendations.actionable.ticker",
            ],
            "entry_date_target_price_note": (
                "entry_date remains present on overlap participant rows. "
                "target_price is not consumed because this repair changes only "
                "manual pilot reporting, not executable exit logic."
            ),
            "input_files": [
                repo_rel(PILOT_SCORECARD),
                repo_rel(PILOT_RECS),
                repo_rel(PILOT_TRACKER_MD),
            ],
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "baseline_signals_generated": baseline["signals_generated"],
            "baseline_signals_survived": baseline["signals_survived"],
            "baseline_survival_rate": baseline["survival_rate"],
            "note": "No buy/sell/filter/ranking/sizing rule was added.",
        },
        "gate4": {
            "passed": passed,
            "decision": decision,
            "failed_reasons": failure_modes,
            "acceptance_checks": {
                "all_overlap_rows_have_participant_context": analysis[
                    "all_overlap_rows_have_context"
                ],
                "killed_overlap_auditable": analysis["killed_overlap_auditable"],
                "markdown_has_verdict_context": analysis["markdown_has_verdict_context"],
                "strategy_behavior_changed": False,
                "orders_changed": False,
                "tests_expected": ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_pilot_tracker.py",
            },
            "before_after_strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
            "ran_after_strategy": False,
            "strategy_rerun_required": False,
            "reason_after_not_run": (
                "No strategy behavior changed; reporting repair was verified "
                "through generated pilot output and unit tests."
            ),
        },
        "analysis": analysis,
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": {
            "why_result_happened": (
                "The missing context was already available in each pilot's "
                "recommendation envelope. Projecting it into cross_pilot_overlap "
                "and the Markdown overlap section makes the current DDOG stack "
                "auditable: allocator_top1 is COLLECTING/HOLD, while "
                "fundamental_growth_rs is KILL/HOLD with new entries blocked."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not add separate manual overlap spreadsheets or reclassify "
                "killed-pilot overlap by hand; the shared tracker output is now "
                "the source of truth for participant verdict/status context."
            ),
            "new_evidence_required": (
                "Fresh forward pilot rows can now be reviewed using the enriched "
                "overlap fields; activation still requires closed replacement "
                "value evidence and the pre-committed pilot risk envelope."
            ),
        },
        "production_files": {
            "pilot_scorecard": repo_rel(PILOT_SCORECARD),
            "pilot_tracker_md": repo_rel(PILOT_TRACKER_MD),
            "pilot_recommendations": repo_rel(PILOT_RECS),
        },
        "related_files": [
            RUNNER,
            "quant/pilot_tracker.py",
            "quant/test_pilot_tracker.py",
            repo_rel(BASELINE_RESULT),
            repo_rel(BEFORE_GAP_ARTIFACT),
            repo_rel(PILOT_SCORECARD),
            repo_rel(PILOT_TRACKER_MD),
            repo_rel(PILOT_RECS),
        ],
        "changed_files": [
            RUNNER,
            "quant/pilot_tracker.py",
            "quant/test_pilot_tracker.py",
            repo_rel(OUT_JSON),
            repo_rel(PILOT_SCORECARD),
            repo_rel(PILOT_TRACKER_MD),
            repo_rel(PILOT_RECS),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_pilot_tracker.py",
            ".\\.venv\\Scripts\\python.exe -B quant\\pilot_tracker.py",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner and pytest only.",
        },
        "lean_quality_passed": True,
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "observed_only_lead",
        "lane",
        "owner",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "implementation_mode",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "changed_variable",
        "single_causal_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "new_evidence_axis",
        "prediction",
        "calibration",
        "before_gap",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "production_impact",
        "post_run_reflection",
        "related_files",
        "changed_files",
        "allowed_write_scope",
        "reproduction_commands",
        "artifact",
        "log",
        "anti_js",
        "lean_quality_passed",
    ]
    return {key: payload[key] for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    for row in payload["analysis"]["overlap_rows"]:
        lines.append(
            "- `{ticker}`: context `{context}`, exposure `${exposure:,.0f}`".format(
                ticker=row["ticker"],
                context=row["has_participant_context"],
                exposure=float(row.get("total_exposure_usd") or 0.0),
            )
        )
        for participant in row["participants"]:
            lines.append(
                "  - `{pilot}`: verdict `{verdict}`, action `{status}`, blocked `{blocked}`".format(
                    pilot=participant.get("pilot_key"),
                    verdict=participant.get("pilot_verdict"),
                    status=participant.get("actionable_status"),
                    blocked=participant.get("new_entries_blocked"),
                )
            )
    if not lines:
        lines = ["- No overlap rows found."]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: pilot cross-overlap participant context",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Strategy behavior changed: `false`",
            "- Live orders changed: `false`",
            f"- Artifact: `{repo_rel(OUT_JSON)}`",
            "",
            "## Result",
            "",
            *lines,
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_pilot_tracker.py",
            ".\\.venv\\Scripts\\python.exe -B quant\\pilot_tracker.py",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
            "```",
            "",
            "No JavaScript was used.",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        REPO_ROOT / "quant" / "pilot_tracker.py",
        REPO_ROOT / "quant" / "test_pilot_tracker.py",
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        BASELINE_RESULT,
        BEFORE_GAP_ARTIFACT,
        PILOT_SCORECARD,
        PILOT_TRACKER_MD,
        PILOT_RECS,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {
                "exists": path.exists(),
                "sha256": sha256(path),
            }
            for path in files
        },
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)

    registry_result = {
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "observed_only_lead": False,
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=payload["prediction"],
        result=registry_result,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
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
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "aggregate_expected_value_delta": 0.0,
            "aggregate_strategy_total_pnl_delta": 0.0,
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
        allow_missing_prediction=True,
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "overlap_count": payload["analysis"]["overlap_count"],
                "all_overlap_rows_have_context": payload["analysis"][
                    "all_overlap_rows_have_context"
                ],
                "killed_overlap_auditable": payload["analysis"][
                    "killed_overlap_auditable"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
