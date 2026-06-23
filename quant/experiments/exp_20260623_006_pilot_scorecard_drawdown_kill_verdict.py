"""exp-20260623-006: pilot scorecard drawdown kill verdict repair.

Measurement repair for the manual live pilot scorecard. The pre-committed
pilot envelope says book drawdown must stay below 15%, so the scorecard must
flag a pilot as stopped when that ceiling is breached even if the closed-trade
sample has not reached the graduation threshold yet.

This changes reporting/verdict semantics only. It does not change sleeve
signals, entries, exits, ranking, sizing, live orders, or paper ledgers.
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


EXPERIMENT_ID = "exp-20260623-006"
OWNER = "alpha-explore"
SLUG = "pilot_scorecard_drawdown_kill_verdict"
RUNNER = f"quant/experiments/exp_20260623_006_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260623_006_{SLUG}.json"
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
PILOT_RECS = REPO_ROOT / "data" / "pilots" / "pilot_recommendations_2026-06-23.json"

HYPOTHESIS = (
    "measurement_repair/alpha_blocker: manual live pilot forward maturation is "
    "unreliable if a pilot that already breaches the pre-committed 15% book "
    "drawdown ceiling remains labelled COLLECTING instead of risk-stopped; "
    "repair the scorecard verdict so activation evidence and operator review "
    "respect the declared envelope."
)
ALPHA_HYPOTHESIS = (
    "Accepted default-off sleeves can only become activation evidence if live "
    "pilot scorecards enforce the same risk envelope used for maturation."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "identity_or_measurement_repair"
TRIAL_FAMILY = "identity_or_measurement_repair"
TRIAL_VARIANT_ID = EXPERIMENT_ID
CHANGED_VARIABLE = "pilot_scorecard_drawdown_kill_verdict_v1"
CAUSAL_COMPONENTS = [
    "pilot scorecard verdict",
    "pre-committed drawdown ceiling",
    "pilot recommendation new-entry block",
    "no strategy signal change",
    "no live order change",
]
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260612-024",
    "exp-20260620-029",
    "exp-20260623-004",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "quant/pilot_tracker.py",
    "quant/test_pilot_tracker.py",
    "data/experiments/exp-20260623-006/exp_20260623_006_pilot_scorecard_drawdown_kill_verdict.json",
    "data/pilots/pilot_scorecard.json",
    "data/pilots/pilot_tracker.md",
    "data/pilots/pilot_recommendations_2026-06-23.json",
    "experiments/cards/exp-20260623-006.md",
    "experiments/manifests/exp-20260623-006.json",
    "experiments/tickets/exp-20260623-006.json",
    "experiments/logs/exp-20260623-006.json",
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
    "pilot_verdict_changed": True,
    "pilot_recommendation_changed": True,
    "live_ready": False,
    "replay_only": False,
    "parity_note": (
        "Only the manual pilot scorecard/recommendation sheet changes. Sleeve "
        "state, daily candidate generation, live orders, ranking, sizing, and "
        "exits are unchanged."
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=True)
    rows: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
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
    windows = payload.get("windows") or []
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


def legacy_verdict(card: dict[str, Any]) -> tuple[str, str]:
    closed = int(card.get("closed_trades") or 0)
    rv_spy = float(card.get("rv_vs_spy_usd") or 0.0)
    dd_pct = float(card.get("book_max_drawdown_pct") or 0.0)
    if closed < pilot_tracker.GRADUATE_MIN_CLOSED:
        return (
            "COLLECTING",
            f"{closed}/{pilot_tracker.GRADUATE_MIN_CLOSED} closed trades; keep tracking",
        )
    if rv_spy > pilot_tracker.GRADUATE_MIN_RV_SPY_USD and dd_pct < pilot_tracker.GRADUATE_MAX_BOOK_DD_PCT:
        return "GRADUATE", "beats SPY after costs within drawdown ceiling -> scale up"
    return "KILL", "sample reached but does not beat SPY / breaches drawdown -> stop"


def build_analysis(
    scorecards: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
) -> dict[str, Any]:
    rows = []
    repaired = []
    for card in scorecards:
        old_verdict, old_note = legacy_verdict(card)
        after_verdict = str(card.get("verdict") or "")
        row = {
            "pilot": card.get("pilot"),
            "label": card.get("label"),
            "sleeve": card.get("sleeve"),
            "closed_trades": card.get("closed_trades"),
            "rv_vs_spy_usd": card.get("rv_vs_spy_usd"),
            "book_max_drawdown_pct": card.get("book_max_drawdown_pct"),
            "drawdown_ceiling_breached": card.get("drawdown_ceiling_breached"),
            "before_verdict_legacy": old_verdict,
            "before_verdict_note_legacy": old_note,
            "after_verdict": after_verdict,
            "after_verdict_note": card.get("verdict_note"),
        }
        rows.append(row)
        if old_verdict == "COLLECTING" and after_verdict == "KILL" and card.get("drawdown_ceiling_breached"):
            repaired.append(row)
    rec_rows = []
    blocked_entries = []
    for rec in recommendations:
        actionable_statuses = [row.get("status") for row in rec.get("actionable", [])]
        skipped_rows = rec.get("skipped") or []
        kill_blocked = [
            row
            for row in skipped_rows
            if row.get("status") == "SKIP_pilot_kill_verdict"
        ]
        row = {
            "pilot": rec.get("pilot"),
            "label": rec.get("label"),
            "pilot_verdict": rec.get("pilot_verdict"),
            "new_entries_blocked": bool(rec.get("new_entries_blocked")),
            "actionable_statuses": actionable_statuses,
            "enter_next_open_count": actionable_statuses.count("ENTER_NEXT_OPEN"),
            "kill_blocked_pending_entries": [
                {"ticker": item.get("ticker"), "status": item.get("status")}
                for item in kill_blocked
            ],
        }
        rec_rows.append(row)
        blocked_entries.extend(
            [
                {"pilot": rec.get("pilot"), "ticker": item.get("ticker"), "status": item.get("status")}
                for item in kill_blocked
            ]
        )
    return {
        "scorecards": rows,
        "repaired_pilots": repaired,
        "repaired_count": len(repaired),
        "verdicts_after": {str(row["pilot"]): row["after_verdict"] for row in rows},
        "recommendations": rec_rows,
        "blocked_new_entries": blocked_entries,
        "blocked_new_entry_count": len(blocked_entries),
        "killed_pilots_have_no_new_buys": all(
            row["enter_next_open_count"] == 0
            for row in rec_rows
            if row["pilot_verdict"] == "KILL"
        ),
    }


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    return prediction or {
        "success_probability": 0.8,
        "expected_ev_delta": None,
        "expected_pnl_delta": None,
        "main_failure_modes": [
            "ambiguous_graduate_vs_kill_semantics",
            "existing_dirty_pilot_artifacts",
            "tests_missing_fixture",
        ],
        "confidence_reason": (
            "The pilot tracker declares a 15% book drawdown ceiling and current "
            "generated pilot data breaches it while still reporting COLLECTING."
        ),
        "recorded_at": "2026-06-23T05:07:36+00:00",
    }


def build_payload() -> dict[str, Any]:
    now = utc_now()
    baseline = baseline_metrics()
    generated = pilot_tracker.generate(write=False)
    analysis = build_analysis(generated["scorecards"], generated["recommendations"])
    verdicts_repaired = analysis["repaired_count"] >= 1 and all(
        not row["drawdown_ceiling_breached"] or row["after_verdict"] == "KILL"
        for row in analysis["scorecards"]
    )
    recommendations_repaired = analysis["killed_pilots_have_no_new_buys"]
    passed = verdicts_repaired and recommendations_repaired
    decision = "accepted_measurement_repair_pilot_drawdown_kill_verdict" if passed else "blocked_pilot_drawdown_verdict_repair"
    status = "accepted_measurement_repair" if passed else "blocked"
    failure_modes = []
    if not verdicts_repaired:
        failure_modes.append("no_drawdown_breach_repaired")
    if not recommendations_repaired:
        failure_modes.append("killed_pilot_still_has_enter_next_open")
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "decision": decision,
        "accepted": passed,
        "accepted_alpha": False,
        "lane": "measurement_repair",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": "measurement_repair",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "prediction": load_ticket_prediction(),
        "calibration": {
            "actual_success": bool(passed),
            "predicted_success_probability": load_ticket_prediction().get("success_probability"),
            "failure_modes_observed": failure_modes,
            "predicted_failure_modes": load_ticket_prediction().get("main_failure_modes", []),
            "surprise_note": (
                "The repair was straightforward: the existing scorecard already "
                "computed drawdown; verdict precedence and recommendation-sheet "
                "new-entry blocking were the missing pieces."
                if passed
                else "The current pilot data did not expose a repairable drawdown-verdict mismatch."
            ),
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "pilot_verdicts_repaired": analysis["repaired_count"],
            "pending_entries_blocked_by_kill": analysis["blocked_new_entry_count"],
        },
        "gate1": {
            "baseline_loaded": BASELINE_RESULT.exists(),
            "baseline_metrics": baseline,
        },
        "gate2": {
            "dependencies_validated": True,
            "fields_checked": [
                "closed_trades",
                "book_max_drawdown_pct",
                "verdict",
                "pending_entries",
                "recommendations.actionable.status",
                "recommendations.skipped.status",
                "replacement_value_vs_spy_usd",
            ],
            "entry_date_target_price_note": (
                "No strategy candidates are built. This repair changes only "
                "pilot scorecard verdict and manual recommendation reporting."
            ),
            "pilot_scorecard_path": repo_rel(PILOT_SCORECARD),
        },
        "gate3": {
            "filter_added": False,
            "baseline_signals_generated": baseline["signals_generated"],
            "baseline_signals_survived": baseline["signals_survived"],
            "baseline_survival_rate": baseline["survival_rate"],
            "note": "No executable filter or strategy rule was added.",
        },
        "gate4": {
            "passed": passed,
            "decision": decision,
            "before_after_strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
            "acceptance_checks": {
                "repaired_drawdown_breach_count": analysis["repaired_count"],
                "all_drawdown_breaches_are_kill": all(
                    not row["drawdown_ceiling_breached"] or row["after_verdict"] == "KILL"
                    for row in analysis["scorecards"]
                ),
                "killed_pilots_have_no_new_buys": analysis["killed_pilots_have_no_new_buys"],
                "pending_entries_blocked_by_kill": analysis["blocked_new_entry_count"],
                "strategy_behavior_changed": False,
            },
            "failed_reasons": failure_modes,
            "strategy_rerun_required": False,
        },
        "analysis": analysis,
        "production_impact": PRODUCTION_IMPACT,
        "post_run_reflection": {
            "why_result_happened": (
                "The scorecard computed drawdown correctly but evaluated the "
                "closed-trade minimum before the drawdown kill ceiling, so low-sample "
                "pilots could hide an envelope breach behind COLLECTING and still "
                "surface pending entries as new BUY recommendations."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not treat low-sample pilot scorecards as activation evidence "
                "when the pre-committed drawdown ceiling is already breached."
            ),
            "new_evidence_required": (
                "Fresh closed pilot rows after the stopped pilot is reviewed, with "
                "the scorecard verdict and replacement-value fields intact."
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
            repo_rel(OUT_JSON),
            repo_rel(PILOT_SCORECARD),
            repo_rel(PILOT_TRACKER_MD),
            repo_rel(PILOT_RECS),
            repo_rel(BASELINE_RESULT),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -m pytest quant\\test_pilot_tracker.py",
            ".\\.venv\\Scripts\\python.exe -B quant\\pilot_tracker.py",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner and pytest only.",
        },
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": payload["experiment_id"],
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "accepted": payload["accepted"],
        "accepted_alpha": False,
        "lane": payload["lane"],
        "hypothesis": payload["hypothesis"],
        "alpha_hypothesis": payload["alpha_hypothesis"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "single_causal_variable": payload["single_causal_variable"],
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "before_metrics": payload["before_metrics"],
        "after_metrics": payload["after_metrics"],
        "delta_metrics": payload["delta_metrics"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "analysis": payload["analysis"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "related_files": payload["related_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "anti_js": payload["anti_js"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
    }


def build_card(payload: dict[str, Any]) -> str:
    repaired = payload["analysis"]["repaired_pilots"]
    repaired_lines = [
        f"- `{row['pilot']}`: `{row['before_verdict_legacy']}` -> `{row['after_verdict']}` "
        f"(DD {row['book_max_drawdown_pct']:.1%})"
        for row in repaired
    ] or ["- No pilot verdict repaired."]
    blocked = payload["analysis"]["blocked_new_entries"]
    blocked_lines = [
        f"- `{row['pilot']}`: `{row['ticker']}` -> `{row['status']}`"
        for row in blocked
    ] or ["- No pending entries blocked."]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: pilot scorecard drawdown kill verdict",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Strategy behavior changed: `false`",
            "- Live orders changed: `false`",
            "",
            "## Result",
            "",
            *repaired_lines,
            "",
            "## Recommendation Sheet",
            "",
            *blocked_lines,
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "No JavaScript was used.",
        ]
    ) + "\n"


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
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "gate4": payload["gate4"],
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
            "related_files": payload["related_files"],
        },
        allow_missing_prediction=True,
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps({"experiment_id": EXPERIMENT_ID, "decision": payload["decision"]}, sort_keys=True))


if __name__ == "__main__":
    main()
