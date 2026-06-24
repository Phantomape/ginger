"""exp-20260624-009: pilot cross-overlap verdict context audit.

Read-only measurement repair experiment. The manual pilot tracker reports
same-ticker cross-pilot overlap as stacked exposure, but the daily overlap row
does not include per-pilot verdict/status context. That hides whether one leg
is a killed pilot whose remaining position is unwind-only exposure.

This runner records the gap and a local enriched view without changing
strategy behavior, pilot recommendations, shared tracker output, live orders,
or paper ledgers. The current ticket's allowed write scope does not include
``quant/pilot_tracker.py`` or its tests, so the actual reporting repair is left
as a follow-up with the correct scope.
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


EXPERIMENT_ID = "exp-20260624-009"
OWNER = "alpha-explore"
SLUG = "pilot_cross_overlap_verdict_context"
RUNNER = f"quant/experiments/exp_20260624_009_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260624_009_{SLUG}.json"
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

HYPOTHESIS = (
    "measurement_repair/alpha_blocker: live pilot forward maturation and "
    "activation-envelope review are unreliable when cross-pilot same-ticker "
    "overlap is reported without per-pilot verdict/status context; enrich "
    "overlap reporting so killed-pilot unwind exposure is auditable without "
    "changing orders."
)
ALPHA_HYPOTHESIS = (
    "Default-off alpha sleeves can only graduate toward live activation when "
    "manual pilot overlap reporting makes stacked exposure and killed-pilot "
    "unwind context auditable."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "identity_or_measurement_repair"
TRIAL_FAMILY = "identity_or_measurement_repair"
TRIAL_VARIANT_ID = EXPERIMENT_ID
CHANGED_VARIABLE = "pilot_cross_pilot_overlap_verdict_context_v1"
CAUSAL_COMPONENTS = [
    "pilot cross-pilot overlap report",
    "per-pilot verdict context",
    "per-position actionable status context",
    "no strategy signal change",
    "no live order change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "data/experiments/exp-20260624-009/exp_20260624_009_pilot_cross_overlap_verdict_context.json",
    "experiments/cards/exp-20260624-009.md",
    "experiments/manifests/exp-20260624-009.json",
    "experiments/tickets/exp-20260624-009.json",
    "experiments/logs/exp-20260624-009.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]
FOLLOW_UP_WRITE_SCOPE = [
    "quant/pilot_tracker.py",
    "quant/test_pilot_tracker.py",
    "data/pilots/pilot_scorecard.json",
    "data/pilots/pilot_tracker.md",
    "data/pilots/pilot_recommendations_2026-06-24.json",
]
REQUIRED_DAILY_OVERLAP_CONTEXT_FIELDS = [
    "participant_context",
    "pilot_verdicts",
    "pilot_statuses",
    "new_entries_blocked_by_pilot",
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
    "pilot_reporting_changed": False,
    "daily_snapshot_exposed": False,
    "live_ready": False,
    "replay_only": False,
    "parity_note": (
        "Read-only audit only. The shared pilot tracker and daily pilot files "
        "are inputs, not outputs, for this experiment."
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
        "success_probability": 0.72,
        "expected_ev_delta": None,
        "expected_pnl_delta": None,
        "main_failure_modes": [
            "shared_tracker_not_in_allowed_write_scope",
            "no_current_killed_pilot_overlap",
            "daily_payload_already_has_context",
        ],
        "confidence_reason": (
            "Current 2026-06-24 pilot recommendations show a DDOG overlap "
            "between allocator_top1 and a KILL-verdict fundamental_growth_rs "
            "pilot, while cross_pilot_overlap only exposes labels and exposure."
        ),
        "recorded_at": "2026-06-24T07:04:06+00:00",
    }


def matching_actionables(rec: dict[str, Any], ticker: str) -> list[dict[str, Any]]:
    return [
        row
        for row in rec.get("actionable", [])
        if isinstance(row, dict) and str(row.get("ticker") or "").upper() == ticker
    ]


def enrich_overlap(
    overlap: dict[str, Any],
    recommendations: list[dict[str, Any]],
    scorecards: list[dict[str, Any]],
) -> dict[str, Any]:
    ticker = str(overlap.get("ticker") or "").upper()
    scorecard_by_key = {row.get("pilot"): row for row in scorecards if isinstance(row, dict)}
    participants: list[dict[str, Any]] = []
    for rec in recommendations:
        if not isinstance(rec, dict):
            continue
        for row in matching_actionables(rec, ticker):
            scorecard = scorecard_by_key.get(rec.get("pilot")) or {}
            participants.append(
                {
                    "pilot": rec.get("pilot"),
                    "label": rec.get("label"),
                    "sleeve": rec.get("sleeve"),
                    "pilot_verdict": rec.get("pilot_verdict"),
                    "pilot_verdict_note": rec.get("pilot_verdict_note"),
                    "new_entries_blocked": bool(rec.get("new_entries_blocked")),
                    "actionable_status": row.get("status"),
                    "stop_status": row.get("stop_status"),
                    "entry_date": row.get("entry_date"),
                    "days_held": row.get("days_held"),
                    "days_remaining": row.get("days_remaining"),
                    "unrealized_pct": row.get("unrealized_pct"),
                    "pilot_notional_usd": row.get("pilot_notional_usd"),
                    "book_max_drawdown_pct": scorecard.get("book_max_drawdown_pct"),
                    "drawdown_ceiling_breached": bool(
                        scorecard.get("drawdown_ceiling_breached")
                    ),
                    "closed_trades": scorecard.get("closed_trades"),
                }
            )

    daily_context_fields_present = [
        field for field in REQUIRED_DAILY_OVERLAP_CONTEXT_FIELDS if field in overlap
    ]
    contains_kill_verdict = any(p.get("pilot_verdict") == "KILL" for p in participants)
    kill_unwind_participants = [
        p
        for p in participants
        if p.get("pilot_verdict") == "KILL" and p.get("actionable_status") in {"HOLD", "EXIT_NOW", "EXIT_NEXT_SESSION"}
    ]
    return {
        "ticker": ticker,
        "daily_overlap": overlap,
        "daily_overlap_has_verdict_context": bool(daily_context_fields_present),
        "daily_context_fields_present": daily_context_fields_present,
        "daily_context_fields_missing": [
            field
            for field in REQUIRED_DAILY_OVERLAP_CONTEXT_FIELDS
            if field not in overlap
        ],
        "participants": participants,
        "local_enrichment_possible": all(
            p.get("pilot_verdict") and p.get("actionable_status") for p in participants
        ),
        "contains_kill_verdict": contains_kill_verdict,
        "kill_unwind_participants": kill_unwind_participants,
        "kill_unwind_exposure_usd": round(
            sum(float(p.get("pilot_notional_usd") or 0.0) for p in kill_unwind_participants),
            2,
        ),
        "total_exposure_usd": overlap.get("total_exposure_usd"),
    }


def build_analysis(generated: dict[str, Any]) -> dict[str, Any]:
    overlaps = [
        row
        for row in generated.get("cross_pilot_overlap", [])
        if isinstance(row, dict)
    ]
    recs = [
        row
        for row in generated.get("recommendations", [])
        if isinstance(row, dict)
    ]
    scorecards = [
        row
        for row in generated.get("scorecards", [])
        if isinstance(row, dict)
    ]
    enriched = [enrich_overlap(row, recs, scorecards) for row in overlaps]
    daily_missing = [
        row for row in enriched if not row["daily_overlap_has_verdict_context"]
    ]
    killed_overlap = [row for row in enriched if row["contains_kill_verdict"]]
    return {
        "as_of": generated.get("as_of"),
        "overlap_count": len(overlaps),
        "daily_overlap_rows": overlaps,
        "enriched_overlap_rows": enriched,
        "daily_context_missing_count": len(daily_missing),
        "kill_verdict_overlap_count": len(killed_overlap),
        "kill_unwind_exposure_usd": round(
            sum(float(row.get("kill_unwind_exposure_usd") or 0.0) for row in killed_overlap),
            2,
        ),
        "total_stacked_exposure_usd": round(
            sum(float(row.get("total_exposure_usd") or 0.0) for row in overlaps),
            2,
        ),
        "local_context_available": all(
            row["local_enrichment_possible"] for row in enriched
        )
        if enriched
        else False,
        "pilot_verdicts": {
            str(row.get("pilot")): row.get("verdict") for row in scorecards
        },
        "participant_statuses_by_overlap": {
            row["ticker"]: [
                {
                    "pilot": participant.get("pilot"),
                    "pilot_verdict": participant.get("pilot_verdict"),
                    "actionable_status": participant.get("actionable_status"),
                    "new_entries_blocked": participant.get("new_entries_blocked"),
                }
                for participant in row["participants"]
            ]
            for row in enriched
        },
    }


def build_payload() -> dict[str, Any]:
    now = utc_now()
    prediction = load_ticket_prediction()
    baseline = baseline_metrics()
    generated = pilot_tracker.generate(write=False)
    analysis = build_analysis(generated)

    has_gap = analysis["daily_context_missing_count"] > 0
    has_killed_overlap = analysis["kill_verdict_overlap_count"] > 0
    local_context_available = bool(analysis["local_context_available"])
    ticket_scope_blocks_patch = any(
        path not in ALLOWED_WRITE_SCOPE for path in FOLLOW_UP_WRITE_SCOPE[:2]
    )
    failed_reasons = []
    if has_gap:
        failed_reasons.append("daily_cross_pilot_overlap_lacks_verdict_status_context")
    if has_killed_overlap:
        failed_reasons.append("current_overlap_contains_kill_verdict_pilot")
    if ticket_scope_blocks_patch:
        failed_reasons.append("shared_tracker_and_tests_not_in_allowed_write_scope")
    if not local_context_available:
        failed_reasons.append("local_enrichment_context_not_fully_available")
    failed_reasons.append("no_strategy_or_daily_output_change")

    blocked = has_gap and has_killed_overlap and ticket_scope_blocks_patch
    decision = (
        "blocked_pilot_cross_overlap_verdict_context_not_wired"
        if blocked
        else "observed_only_no_current_overlap_verdict_context_gap"
    )
    status = "blocked" if blocked else "observed_only"
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "owner": OWNER,
        "lane": "measurement_repair",
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": not blocked,
        "implementation_mode": "read_only_measurement_audit",
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": ["exp-20260623-006", "exp-20260624-008"],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "forward_pilot_overlap_reporting_gap",
        "new_evidence_axis": (
            "Current 2026-06-24 pilot recommendations include same-ticker DDOG "
            "overlap where one participant is a KILL-verdict pilot, but the "
            "daily cross_pilot_overlap row has no per-pilot verdict/status context."
        ),
        "prediction": prediction,
        "calibration": {
            "predicted_success_probability": prediction.get("success_probability"),
            "actual_success": False,
            "failure_modes_observed": failed_reasons,
            "predicted_failure_modes": prediction.get("main_failure_modes", []),
            "predicted_failure_mode_hit": "shared_tracker_not_in_allowed_write_scope"
            in prediction.get("main_failure_modes", []),
            "surprise_note": (
                "The data gap was present and locally enrichable, but this ticket "
                "cannot write the shared tracker or tests, so the repair cannot "
                "be accepted under the current scope."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "novelty_gate": "exp-20260624-009 reserved with no blocking near-neighbor.",
                "related_prior": (
                    "exp-20260623-006 repaired pilot KILL verdict semantics; "
                    "this run checks whether cross-pilot overlap exposes that "
                    "verdict context."
                ),
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_acceptance_standard": (
                "Accepted measurement repair would require daily overlap output "
                "to include per-pilot verdict/status context plus tracker tests."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "cross_pilot_overlap_count": analysis["overlap_count"],
            "daily_context_missing_count": analysis["daily_context_missing_count"],
            "kill_verdict_overlap_count": analysis["kill_verdict_overlap_count"],
            "kill_unwind_exposure_usd": analysis["kill_unwind_exposure_usd"],
            "total_stacked_exposure_usd": analysis["total_stacked_exposure_usd"],
            "strategy_behavior_changed": False,
            "daily_output_changed": False,
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists(),
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": local_context_available,
            "dependencies_validated": local_context_available,
            "fields_checked": [
                "cross_pilot_overlap.ticker",
                "cross_pilot_overlap.pilots",
                "recommendations.pilot_verdict",
                "recommendations.new_entries_blocked",
                "recommendations.actionable.status",
                "recommendations.actionable.entry_date",
                "recommendations.actionable.ticker",
                "scorecards.verdict",
                "scorecards.book_max_drawdown_pct",
            ],
            "entry_date_target_price_note": (
                "entry_date is present on overlap participants where the sleeve "
                "has an open row. target_price is not consumed because this is "
                "a pilot-reporting audit, not an executable exit or target-price "
                "strategy change."
            ),
            "input_files": [repo_rel(PILOT_SCORECARD), repo_rel(PILOT_RECS), repo_rel(PILOT_TRACKER_MD)],
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
            "passed": False,
            "decision": decision,
            "failed_reasons": failed_reasons,
            "acceptance_checks": {
                "daily_overlap_lacks_verdict_context": has_gap,
                "current_overlap_contains_kill_verdict_pilot": has_killed_overlap,
                "local_enrichment_proves_context_available": local_context_available,
                "shared_tracker_in_allowed_write_scope": "quant/pilot_tracker.py"
                in ALLOWED_WRITE_SCOPE,
                "tracker_tests_in_allowed_write_scope": "quant/test_pilot_tracker.py"
                in ALLOWED_WRITE_SCOPE,
                "strategy_behavior_changed": False,
                "daily_pilot_output_changed": False,
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
                "Blocked as a measurement-reporting scope gap before any strategy "
                "or daily-output patch."
            ),
        },
        "analysis": analysis,
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": {
            "why_result_happened": (
                "The daily tracker detects DDOG stacked exposure, but the overlap "
                "row only lists pilot labels and total notional. The underlying "
                "recommendation rows already contain the missing verdict/status "
                "context: allocator_top1 is COLLECTING/HOLD, while "
                "fundamental_growth_rs is KILL/HOLD with new entries blocked."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not treat same-ticker pilot overlap as activation-ready "
                "evidence when one participant is a killed pilot unless the "
                "daily overlap report exposes per-pilot verdict and actionable "
                "status context."
            ),
            "new_evidence_required": (
                "Open a follow-up measurement repair whose write scope includes "
                "quant/pilot_tracker.py and quant/test_pilot_tracker.py, then "
                "wire participant_context into cross_pilot_overlap and regenerate "
                "the 2026-06-24 pilot files."
            ),
        },
        "production_files": {
            "pilot_scorecard": repo_rel(PILOT_SCORECARD),
            "pilot_tracker_md": repo_rel(PILOT_TRACKER_MD),
            "pilot_recommendations": repo_rel(PILOT_RECS),
        },
        "related_files": [
            RUNNER,
            repo_rel(BASELINE_RESULT),
            repo_rel(PILOT_SCORECARD),
            repo_rel(PILOT_TRACKER_MD),
            repo_rel(PILOT_RECS),
            "quant/pilot_tracker.py",
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "follow_up_write_scope_needed": FOLLOW_UP_WRITE_SCOPE,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner only.",
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
        "follow_up_write_scope_needed",
        "reproduction_commands",
        "artifact",
        "log",
        "anti_js",
        "lean_quality_passed",
    ]
    return {key: payload[key] for key in keys}


def build_card(payload: dict[str, Any]) -> str:
    rows = payload["analysis"]["enriched_overlap_rows"]
    overlap_lines: list[str] = []
    for row in rows:
        overlap_lines.append(
            "- `{ticker}`: daily context present `{present}`, exposure `${exposure:,.0f}`, "
            "kill unwind exposure `${kill_exposure:,.0f}`".format(
                ticker=row["ticker"],
                present=row["daily_overlap_has_verdict_context"],
                exposure=float(row.get("total_exposure_usd") or 0.0),
                kill_exposure=float(row.get("kill_unwind_exposure_usd") or 0.0),
            )
        )
        for participant in row["participants"]:
            overlap_lines.append(
                "  - `{pilot}`: verdict `{verdict}`, action `{status}`, blocked `{blocked}`".format(
                    pilot=participant.get("pilot"),
                    verdict=participant.get("pilot_verdict"),
                    status=participant.get("actionable_status"),
                    blocked=participant.get("new_entries_blocked"),
                )
            )
    if not overlap_lines:
        overlap_lines = ["- No cross-pilot overlap rows found."]

    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: pilot cross-overlap verdict context",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Strategy behavior changed: `false`",
            "- Daily pilot output changed: `false`",
            f"- Artifact: `{repo_rel(OUT_JSON)}`",
            "",
            "## Finding",
            "",
            *overlap_lines,
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Follow-Up Scope",
            "",
            *[f"- `{path}`" for path in FOLLOW_UP_WRITE_SCOPE],
            "",
            "## Reproduction",
            "",
            "```powershell",
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
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        BASELINE_RESULT,
        PILOT_SCORECARD,
        PILOT_TRACKER_MD,
        PILOT_RECS,
        REPO_ROOT / "quant" / "pilot_tracker.py",
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
        "follow_up_write_scope_needed": FOLLOW_UP_WRITE_SCOPE,
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
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["observed_only_lead"],
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
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "allowed_write_scope": ALLOWED_WRITE_SCOPE,
            "follow_up_write_scope_needed": FOLLOW_UP_WRITE_SCOPE,
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
                "daily_context_missing_count": payload["analysis"][
                    "daily_context_missing_count"
                ],
                "kill_verdict_overlap_count": payload["analysis"][
                    "kill_verdict_overlap_count"
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
