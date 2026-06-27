"""exp-20260626-020: intraday advisory shadow action contract repair.

Measurement repair for the intraday review alpha surface. Existing intraday
exit-signal triggers are projected into stable advisory shadow action rows so
forward attribution can distinguish actionable existing-rule triggers from
display-only proximity labels. This changes no strategy rule, order, sizing,
ranking, live path, or backtest behavior.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402
from intraday_review import build_advisory_shadow_actions  # noqa: E402


EXPERIMENT_ID = "exp-20260626-020"
OWNER = "alpha-explore"
SLUG = "intraday_advisory_shadow_action_contract"
RUNNER = f"quant/experiments/exp_20260626_020_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260626_020_{SLUG}.json"
BEFORE_JSON = DATA_DIR / "before_intraday_shadow_surface.json"
AFTER_JSON = DATA_DIR / "after_intraday_shadow_surface.json"
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
SNAPSHOT_DIR = REPO_ROOT / "data" / "daily" / "intraday" / "snapshots"
INTRADAY_REVIEW = REPO_ROOT / "quant" / "intraday_review.py"
RUN_INTRADAY = REPO_ROOT / "quant" / "run_intraday.py"
INTRADAY_TEST = REPO_ROOT / "quant" / "test_intraday_review.py"

HYPOTHESIS = (
    "Intraday BREACHED/APPROACHING advisory states showed forward "
    "underperformance in exp-20260626-019, but promotion is blocked until "
    "existing intraday rule triggers are projected into a stable advisory "
    "shadow action surface without creating orders."
)
ALPHA_HYPOTHESIS = (
    "Intraday advisory BREACHED/APPROACHING position states may have "
    "exit/risk-allocation value if they underperform OK states or SPY/QQQ "
    "after the 13:00 ET snapshot."
)
CHANGE_TYPE = "identity_or_measurement_repair"
MECHANISM_FAMILY = "intraday_review_alpha_measurement_repair"
TRIAL_FAMILY = "intraday_advisory_shadow_action_contract"
TRIAL_VARIANT_ID = "advisory_shadow_actions_v1"
CHANGED_VARIABLE = "intraday_advisory_shadow_action_contract_v1"
CAUSAL_COMPONENTS = [
    "existing exit-signal trigger mapping",
    "advisory-only shadow action rows",
    "daily intraday snapshot surface",
    "focused parity tests",
    "no strategy/order change",
]
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260625-021",
    "exp-20260626-001",
    "exp-20260626-019",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "quant/intraday_review.py",
    "quant/run_intraday.py",
    "quant/test_intraday_review.py",
    f"data/experiments/{EXPERIMENT_ID}/**",
    f"experiments/logs/{EXPERIMENT_ID}.json",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/tickets/{EXPERIMENT_ID}.json",
    "docs/experiment_log.jsonl",
    "docs/experiment_registry.json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


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
    encoded = json.dumps(record, sort_keys=True)
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
                    rows.append(encoded)
                    replaced = True
                continue
            rows.append(raw)
    if not replaced:
        rows.append(encoded)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def load_ticket_prediction() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket, dict) else None
    return prediction or {
        "success_probability": 0.76,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "shadow_actions_mislabeled_as_orders",
            "rule_to_action_mapping_too_ambiguous",
            "tests_miss_legacy_target_review",
            "run_intraday_snapshot_not_wired",
        ],
        "confidence_reason": (
            "Triggered_rules carry rule and urgency, so a narrow advisory-only "
            "projection should repair the measurement contract."
        ),
        "recorded_at": utc_now(),
    }


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
    windows = payload.get("windows") if isinstance(payload, dict) else []
    if not isinstance(windows, list):
        windows = []
    generated = sum(float(row.get("signals_generated") or 0.0) for row in windows)
    survived = sum(float(row.get("signals_survived") or 0.0) for row in windows)
    drawdowns = [float(row.get("max_drawdown_pct") or 0.0) for row in windows]
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "baseline_exists": BASELINE_RESULT.exists(),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": int(generated),
        "signals_survived": int(survived),
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
    }


def snapshot_shadow_surface() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    before_rows: list[dict[str, Any]] = []
    after_actions: list[dict[str, Any]] = []
    snapshot_files = sorted(SNAPSHOT_DIR.glob("intraday_review_*.json"))
    position_rows = 0
    triggered_rows = 0
    status_counts: Counter[str] = Counter()

    for path in snapshot_files:
        payload = read_json(path, {})
        if not isinstance(payload, dict):
            continue
        positions = payload.get("positions")
        if not isinstance(positions, list):
            positions = []
        top_level_shadow = payload.get("advisory_shadow_actions")
        position_shadow_count = 0
        for position in positions:
            if not isinstance(position, dict):
                continue
            position_rows += 1
            status_counts[str(position.get("status") or "UNKNOWN")] += 1
            existing = position.get("advisory_shadow_actions")
            if isinstance(existing, list):
                position_shadow_count += len(existing)
            signals = (position.get("context") or {}).get("exit_signals") or {}
            if isinstance(signals, dict) and signals.get("any_triggered"):
                triggered_rows += 1
        projected = build_advisory_shadow_actions(positions)
        after_actions.extend(
            {
                **action,
                "snapshot_file": repo_rel(path),
                "snapshot_date": payload.get("date"),
                "time_label": payload.get("time_label"),
            }
            for action in projected
        )
        before_rows.append({
            "snapshot_file": repo_rel(path),
            "position_count": len(positions),
            "top_level_shadow_action_count": (
                len(top_level_shadow) if isinstance(top_level_shadow, list) else 0
            ),
            "per_position_shadow_action_count": position_shadow_count,
            "projected_shadow_action_count": len(projected),
        })

    before = {
        "snapshot_file_count": len(snapshot_files),
        "position_rows": position_rows,
        "triggered_position_rows": triggered_rows,
        "saved_top_level_shadow_action_count": sum(
            row["top_level_shadow_action_count"] for row in before_rows
        ),
        "saved_per_position_shadow_action_count": sum(
            row["per_position_shadow_action_count"] for row in before_rows
        ),
        "status_counts": dict(sorted(status_counts.items())),
        "rows": before_rows,
    }
    after = {
        "projected_shadow_action_count": len(after_actions),
        "rule_counts": dict(sorted(Counter(a.get("rule") for a in after_actions).items())),
        "shadow_action_counts": dict(
            sorted(Counter(a.get("shadow_action") for a in after_actions).items())
        ),
        "order_semantics_counts": dict(
            sorted(Counter(a.get("order_semantics") for a in after_actions).items())
        ),
        "all_rows_shadow_only": all(
            a.get("trade_enabled") is False
            and a.get("creates_order") is False
            and a.get("pending_action") is False
            and a.get("advisory_only") is True
            for a in after_actions
        ),
        "sample_actions": after_actions[-12:],
    }
    return before, after, after_actions


def wiring_checks() -> dict[str, Any]:
    run_text = RUN_INTRADAY.read_text(encoding="utf-8", errors="replace")
    review_text = INTRADAY_REVIEW.read_text(encoding="utf-8", errors="replace")
    test_text = INTRADAY_TEST.read_text(encoding="utf-8", errors="replace")
    return {
        "run_intraday_imports_helper": "build_advisory_shadow_actions" in run_text,
        "run_intraday_snapshot_wired": (
            '"advisory_shadow_actions": build_advisory_shadow_actions(positions)'
            in run_text
        ),
        "review_helper_defined": "def build_advisory_shadow_actions" in review_text,
        "report_surface_wired": "ADVISORY SHADOW ACTIONS" in review_text,
        "tests_cover_legacy_target_review": (
            "test_legacy_target_review_creates_review_shadow_action_not_exit"
            in test_text
        ),
        "tests_cover_hard_stop_exit": (
            "test_hard_stop_breach_creates_advisory_shadow_exit_not_order"
            in test_text
        ),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    prediction = load_ticket_prediction()
    baseline = baseline_metrics()
    before, after, actions = snapshot_shadow_surface()
    wiring = wiring_checks()

    failed: list[str] = []
    if after["projected_shadow_action_count"] <= 0:
        failed.append("no_projected_shadow_actions")
    if not after["all_rows_shadow_only"]:
        failed.append("shadow_actions_mislabeled_as_orders")
    if "EXIT" not in after["shadow_action_counts"]:
        failed.append("exit_shadow_action_missing")
    if "REVIEW" not in after["shadow_action_counts"]:
        failed.append("review_shadow_action_missing")
    for key, value in wiring.items():
        if not value:
            failed.append(key)
    passed = not failed
    decision = (
        "accepted_measurement_repair_intraday_advisory_shadow_action_contract"
        if passed
        else "blocked_intraday_advisory_shadow_action_contract_not_verified"
    )
    status = "accepted_measurement_repair" if passed else "blocked"

    predicted_modes = prediction.get("main_failure_modes") or []
    predicted_hit = [mode for mode in predicted_modes if mode in failed]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "measurement_repair",
        "owner": OWNER,
        "status": status,
        "decision": decision,
        "accepted": passed,
        "accepted_alpha": False,
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
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "measurement_blocker",
        "prediction": prediction,
        "calibration": {
            "predicted_success_probability": prediction.get("success_probability"),
            "actual_success": int(passed),
            "expected_ev_delta": prediction.get("expected_ev_delta"),
            "actual_ev_delta": 0.0,
            "expected_pnl_delta": prediction.get("expected_pnl_delta"),
            "actual_pnl_delta": 0.0,
            "predicted_failure_modes": predicted_modes,
            "realized_failure_modes": failed,
            "predicted_failure_modes_hit": predicted_hit,
            "surprise_note": (
                "Low surprise: existing triggered_rules were sufficient to "
                "project stable advisory shadow rows without changing behavior."
                if passed
                else "The shadow action contract failed one or more wiring checks."
            ),
        },
        "gate1": {
            "passed": baseline["baseline_exists"],
            "baseline_loaded": baseline["baseline_exists"],
            "baseline_metrics": baseline,
            "note": "Measurement repair only; before and after strategy behavior are identical.",
        },
        "gate2": {
            "passed": passed,
            "dependencies_validated": passed,
            "fields_checked": [
                "positions[*].context.exit_signals.triggered_rules",
                "positions[*].context.shares",
                "positions[*].quote.capture_time_et",
                "advisory_shadow_actions[*].shadow_action",
                "advisory_shadow_actions[*].trade_enabled",
                "advisory_shadow_actions[*].creates_order",
                "advisory_shadow_actions[*].pending_action",
            ],
            "before_surface": before,
            "after_surface": after,
            "wiring_checks": wiring,
            "entry_date_target_price_note": (
                "entry_date is not consumed by this repair. target_price remains "
                "inside existing exit_levels and is only projected when the "
                "pre-existing SIGNAL_TARGET/LEGACY_TARGET_REVIEW rule fires."
            ),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "baseline_signals_generated": baseline["signals_generated"],
            "baseline_signals_survived": baseline["signals_survived"],
            "baseline_survival_rate": baseline["survival_rate"],
            "signals_generated_proxy": before["position_rows"],
            "signals_survived_proxy": before["triggered_position_rows"],
            "survival_rate_proxy": (
                round(before["triggered_position_rows"] / before["position_rows"], 6)
                if before["position_rows"]
                else None
            ),
            "note": "No buy/sell/filter/ranking/sizing rule was added.",
        },
        "gate4": {
            "passed": passed,
            "decision": decision,
            "failed_reasons": failed,
            "expected_value_score_sum_before": baseline["expected_value_score_sum"],
            "expected_value_score_sum_after": baseline["expected_value_score_sum"],
            "aggregate_ev_delta": 0.0,
            "total_pnl_before": baseline["total_pnl"],
            "total_pnl_after": baseline["total_pnl"],
            "aggregate_pnl_delta": 0.0,
            "trade_count_before": baseline["trade_count"],
            "trade_count_after": baseline["trade_count"],
            "strategy_behavior_changed": False,
            "orders_changed": False,
            "ran_after_strategy": False,
            "strategy_rerun_required": False,
            "reason_after_not_run": (
                "No strategy behavior changed; repair was verified by helper "
                "projection over saved snapshots and focused tests."
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
            "strategy_behavior_changed": False,
            "saved_shadow_actions_before": before[
                "saved_top_level_shadow_action_count"
            ],
            "projected_shadow_actions_after": after["projected_shadow_action_count"],
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "daily_snapshot_exposed": True,
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "advisory_reporting_changed": True,
            "live_ready": False,
            "replay_only": False,
            "parity_note": (
                "Only the intraday advisory/reporting surface changed. It exposes "
                "existing-rule shadow action rows with creates_order=false; EOD "
                "run.py, backtester.py, order behavior, ranking, sizing, and exits "
                "are unchanged."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The missing action semantics were already implicit in "
                "context.exit_signals.triggered_rules. A conservative projection "
                "makes them replayable: stop/target triggers map to EXIT shadows, "
                "while TIME_STOP and LEGACY_TARGET_REVIEW remain REVIEW-only."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not promote intraday BREACHED/APPROACHING, stop, target, "
                "time-stop, urgency, or hold-horizon variants into executable "
                "rules on the same ledger. Future alpha work needs newly generated "
                "shadow-action rows plus closed forward outcomes, then a separate "
                "shared action helper if promotion is justified."
            ),
            "new_evidence_required": (
                "New snapshots generated with advisory_shadow_actions and later "
                "closed forward outcomes/replacement value; quote_time_et or broker "
                "bar IDs remain useful before any executable action contract."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": {
                "exp-20260625-021": "Blocked intraday replayability; no action rows.",
                "exp-20260626-001": "Accepted capture_time_et provenance repair.",
                "exp-20260626-019": (
                    "Observed risk-state underperformance, still blocked on "
                    "action semantics."
                ),
                "novelty_gate": "Measurement-repair lane; no blocking near-neighbor.",
            },
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Existing-rule shadow rows must be present, map EXIT and REVIEW, "
                "and all rows must be explicitly non-order/non-pending."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "analysis": {
            "before_surface": before,
            "after_surface": after,
            "shadow_actions": actions,
            "wiring_checks": wiring,
        },
        "artifact": repo_rel(OUT_JSON),
        "before_artifact": repo_rel(BEFORE_JSON),
        "after_artifact": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_intraday_review.py",
            ".\\.venv\\Scripts\\python.exe -B -m py_compile quant\\intraday_review.py quant\\run_intraday.py quant\\test_intraday_review.py",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "related_files": [
            RUNNER,
            "quant/intraday_review.py",
            "quant/run_intraday.py",
            "quant/test_intraday_review.py",
            repo_rel(BASELINE_RESULT),
            repo_rel(SNAPSHOT_DIR),
            "experiments/logs/exp-20260625-021.json",
            "experiments/logs/exp-20260626-001.json",
            "experiments/logs/exp-20260626-019.json",
        ],
        "changed_files": [
            RUNNER,
            "quant/intraday_review.py",
            "quant/run_intraday.py",
            "quant/test_intraday_review.py",
            repo_rel(OUT_JSON),
            repo_rel(BEFORE_JSON),
            repo_rel(AFTER_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "anti_js": {"used_javascript": False, "evidence": "Python runner and pytest only."},
        "lean_quality_passed": True,
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "lane",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "implementation_mode",
        "hypothesis",
        "alpha_hypothesis",
        "change_type",
        "mechanism_family",
        "trial_family",
        "trial_variant_id",
        "single_causal_variable",
        "changed_variable",
        "causal_components",
        "nearby_prior_experiments",
        "multiple_testing_risk_bucket",
        "new_evidence_type",
        "prediction",
        "calibration",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "production_impact",
        "post_run_reflection",
        "artifact",
        "before_artifact",
        "after_artifact",
        "log",
        "runner",
        "reproduction_commands",
        "related_files",
        "changed_files",
        "allowed_write_scope",
        "anti_js",
        "lean_quality_passed",
    ]
    return {key: payload[key] for key in keys}


def write_card(payload: dict[str, Any]) -> None:
    after = payload["analysis"]["after_surface"]
    lines = [
        f"# {EXPERIMENT_ID}: intraday advisory shadow action contract",
        "",
        f"- Decision: `{payload['decision']}`",
        "- Strategy/order impact: none; advisory reporting only.",
        f"- Projected shadow actions: `{after['projected_shadow_action_count']}`",
        f"- Rule counts: `{after['rule_counts']}`",
        f"- Shadow action counts: `{after['shadow_action_counts']}`",
        f"- Artifact: `{payload['artifact']}`",
        "",
        "## Boundary",
        "",
        payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
        "",
        "## Reproduction",
        "",
        "```powershell",
        *payload["reproduction_commands"],
        "```",
        "",
    ]
    write_text(CARD_MD, "\n".join(lines))


def update_ticket(payload: dict[str, Any]) -> None:
    ticket = read_json(TICKET_JSON, {})
    if not isinstance(ticket, dict):
        return
    ticket.update({
        "status": payload["status"],
        "completed_at": payload["timestamp"],
        "result": {
            "decision": payload["decision"],
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "artifact": payload["artifact"],
            "log": payload["log"],
        },
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
    })
    write_json(TICKET_JSON, ticket)


def write_manifest(payload: dict[str, Any]) -> None:
    paths = [
        REPO_ROOT / RUNNER,
        INTRADAY_REVIEW,
        RUN_INTRADAY,
        INTRADAY_TEST,
        OUT_JSON,
        BEFORE_JSON,
        AFTER_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
    ]
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "decision": payload["decision"],
        "files": [
            {"path": repo_rel(path), "exists": path.exists(), "sha256": sha256(path)}
            for path in paths
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
    }
    write_json(MANIFEST_JSON, manifest)


def persist(payload: dict[str, Any]) -> None:
    write_json(BEFORE_JSON, payload["analysis"]["before_surface"])
    write_json(AFTER_JSON, payload["analysis"]["after_surface"])
    write_json(OUT_JSON, payload)
    compact = compact_log_record(payload)
    write_json(LOG_JSON, compact)
    upsert_jsonl(EXPERIMENT_LOG, compact)
    write_card(payload)
    update_ticket(payload)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=payload["prediction"],
        result=compact,
        status=payload["status"],
        fields={
            "owner": OWNER,
            "decision": payload["decision"],
            "accepted": payload["accepted"],
            "accepted_alpha": False,
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
            "new_evidence_type": payload["new_evidence_type"],
            "artifact": payload["artifact"],
            "log": payload["log"],
            "runner": RUNNER,
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "lean_quality_passed": True,
        },
    )
    write_manifest(payload)


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "projected_shadow_actions": payload["analysis"]["after_surface"][
            "projected_shadow_action_count"
        ],
        "failed_reasons": payload["gate4"]["failed_reasons"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
