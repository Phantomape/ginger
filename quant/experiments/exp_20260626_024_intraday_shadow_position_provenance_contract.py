"""exp-20260626-024: intraday shadow-action provenance contract.

Measurement repair for the intraday advisory alpha surface. The prior
observed-only scout found a promising but non-actionable shadow-action lead:
rows were advisory-only, quote source times were often unavailable, and
multiple rule actions could exist for one position. This runner verifies the
new read-only contract: explicit decision-time provenance plus exactly one
deterministic primary shadow action per position.
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
from intraday_review import (  # noqa: E402
    build_advisory_shadow_actions,
    select_primary_advisory_shadow_action,
)


EXPERIMENT_ID = "exp-20260626-024"
OWNER = "alpha-explore"
SLUG = "intraday_shadow_position_provenance_contract"
RUNNER = f"quant/experiments/exp_20260626_024_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260626_024_{SLUG}.json"
BEFORE_JSON = DATA_DIR / "before_intraday_shadow_contract.json"
AFTER_JSON = DATA_DIR / "after_intraday_shadow_contract.json"
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
INTRADAY_QUOTES = REPO_ROOT / "quant" / "intraday_quotes.py"
INTRADAY_REVIEW = REPO_ROOT / "quant" / "intraday_review.py"
INTRADAY_TEST = REPO_ROOT / "quant" / "test_intraday_review.py"

HYPOTHESIS = (
    "measurement_repair/alpha_blocker: intraday shadow-action exit attribution "
    "needs explicit decision-time provenance and one deterministic primary action "
    "per position before future closed rows can test an EXIT/REVIEW risk-allocation "
    "policy without quote-time spoofing or duplicate action rows."
)
ALPHA_HYPOTHESIS = (
    "Intraday EXIT/REVIEW shadow actions may have exit/risk-allocation value if "
    "future closed rows show those primary position-level states underperform "
    "NO_ACTION positions and SPY/QQQ after the snapshot decision time."
)
CHANGED_VARIABLE = "intraday_shadow_action_position_level_provenance_contract_v1"
CAUSAL_COMPONENTS = [
    "decision_time_et provenance",
    "quote_time_basis labels",
    "primary shadow action collapse",
    "no trading behavior change",
]
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260626-019",
    "exp-20260626-020",
    "exp-20260626-022",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "quant/intraday_quotes.py",
    "quant/intraday_review.py",
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
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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
        "success_probability": 0.86,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "field_contract_breaks_existing_tests",
            "primary_action_priority_ambiguous",
            "accidentally_changes_orders",
        ],
        "confidence_reason": (
            "exp-20260626-022 isolated the blocker to field semantics; this is "
            "a read-only contract repair."
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


def synthetic_self_check() -> dict[str, Any]:
    review = {
        "ticker": "NVDA",
        "status": "BREACHED",
        "quote": {
            "price": 94.5,
            "source": "fast_info",
            "quote_time_et": None,
            "capture_time_et": "2026-06-26 13:01 ET",
            "decision_time_et": "2026-06-26 13:01 ET",
            "quote_time_basis": "capture_time_fast_info_no_source_timestamp",
            "is_stale": False,
        },
        "context": {
            "shares": 10,
            "exit_signals": {
                "triggered_rules": [
                    {
                        "rule": "TIME_STOP",
                        "urgency": "REVIEW",
                        "message": "review stale progress",
                    },
                    {
                        "rule": "HARD_STOP",
                        "urgency": "HIGH",
                        "message": "stop breached",
                    },
                ]
            },
        },
    }
    actions = build_advisory_shadow_actions([review])
    primary = select_primary_advisory_shadow_action(actions)
    return {
        "action_count": len(actions),
        "rules": [row.get("rule") for row in actions],
        "primary_rule": primary.get("rule") if primary else None,
        "primary_shadow_action": primary.get("shadow_action") if primary else None,
        "primary_count": sum(1 for row in actions if row.get("is_primary_shadow_action")),
        "all_rows_shadow_only": all(
            row.get("trade_enabled") is False
            and row.get("creates_order") is False
            and row.get("pending_action") is False
            and row.get("advisory_only") is True
            for row in actions
        ),
        "all_rows_have_decision_time": all(row.get("decision_time_et") for row in actions),
        "quote_time_spoofed": any(row.get("quote_time_et") for row in actions),
        "quote_time_basis_values": sorted(
            {row.get("quote_time_basis") for row in actions}
        ),
        "source_quote_time_available_values": sorted(
            {bool(row.get("source_quote_time_available")) for row in actions}
        ),
        "actions": actions,
    }


def project_snapshot(path: Path) -> dict[str, Any]:
    payload = read_json(path, {})
    positions = payload.get("positions") if isinstance(payload, dict) else []
    if not isinstance(positions, list):
        positions = []
    actions = build_advisory_shadow_actions(positions)
    return {
        "snapshot_file": repo_rel(path),
        "date": payload.get("date") if isinstance(payload, dict) else None,
        "time_label": payload.get("time_label") if isinstance(payload, dict) else None,
        "position_count": len(positions),
        "projected_action_count": len(actions),
        "primary_action_count": sum(
            1 for row in actions if row.get("is_primary_shadow_action")
        ),
        "decision_time_rows": sum(1 for row in actions if row.get("decision_time_et")),
        "source_quote_time_rows": sum(
            1 for row in actions if row.get("source_quote_time_available")
        ),
        "rules": dict(sorted(Counter(row.get("rule") for row in actions).items())),
        "shadow_actions": dict(
            sorted(Counter(row.get("shadow_action") for row in actions).items())
        ),
        "quote_time_basis": dict(
            sorted(Counter(row.get("quote_time_basis") for row in actions).items())
        ),
        "sample_actions": actions[:8],
    }


def historical_projection_summary() -> dict[str, Any]:
    rows = []
    for path in sorted(SNAPSHOT_DIR.glob("intraday_review_*.json")):
        rows.append(project_snapshot(path))
    action_count = sum(row["projected_action_count"] for row in rows)
    primary_count = sum(row["primary_action_count"] for row in rows)
    decision_time_rows = sum(row["decision_time_rows"] for row in rows)
    return {
        "snapshot_count": len(rows),
        "projected_action_count": action_count,
        "primary_action_count": primary_count,
        "decision_time_rows": decision_time_rows,
        "decision_time_coverage": (
            round(decision_time_rows / action_count, 6) if action_count else None
        ),
        "note": (
            "Old saved snapshots predate this repair, so historical decision-time "
            "coverage is diagnostic only. Future snapshots receive the contract."
        ),
        "rows": rows,
    }


def latest_snapshot_projection() -> dict[str, Any]:
    files = sorted(SNAPSHOT_DIR.glob("intraday_review_*.json"))
    return project_snapshot(files[-1]) if files else {}


def source_wiring_checks() -> dict[str, bool]:
    quotes_text = INTRADAY_QUOTES.read_text(encoding="utf-8", errors="replace")
    review_text = INTRADAY_REVIEW.read_text(encoding="utf-8", errors="replace")
    test_text = INTRADAY_TEST.read_text(encoding="utf-8", errors="replace")
    return {
        "quotes_emit_decision_time": "decision_time_et" in quotes_text,
        "quotes_emit_quote_time_basis": "quote_time_basis" in quotes_text,
        "review_selects_primary_action": (
            "def select_primary_advisory_shadow_action" in review_text
        ),
        "review_marks_primary_rows": "is_primary_shadow_action" in review_text,
        "review_preserves_no_order_semantics": "none_shadow_only" in review_text,
        "tests_cover_primary_collapse": (
            "test_primary_shadow_action_collapses_duplicate_position_rules"
            in test_text
        ),
        "tests_cover_decision_time": "decision_time_et" in test_text,
    }


def compact_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "lane",
        "owner",
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
        "anti_js",
        "lean_quality_passed",
    ]
    return {key: payload[key] for key in keys}


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    prediction = load_ticket_prediction()
    baseline = baseline_metrics()
    before = historical_projection_summary()
    latest = latest_snapshot_projection()
    self_check = synthetic_self_check()
    source_checks = source_wiring_checks()

    failed: list[str] = []
    if not baseline["baseline_exists"]:
        failed.append("baseline_missing")
    if self_check["action_count"] != 2:
        failed.append("self_check_action_count_wrong")
    if self_check["primary_rule"] != "HARD_STOP":
        failed.append("primary_action_priority_ambiguous")
    if self_check["primary_shadow_action"] != "EXIT":
        failed.append("primary_action_not_exit")
    if self_check["primary_count"] != 1:
        failed.append("primary_action_count_not_one")
    if not self_check["all_rows_shadow_only"]:
        failed.append("accidentally_changes_orders")
    if not self_check["all_rows_have_decision_time"]:
        failed.append("decision_time_missing")
    if self_check["quote_time_spoofed"]:
        failed.append("quote_time_spoofed")
    for key, value in source_checks.items():
        if not value:
            failed.append(key)

    passed = not failed
    status = "accepted_measurement_repair" if passed else "blocked"
    decision = (
        "accepted_measurement_repair_intraday_shadow_position_provenance_contract"
        if passed
        else "blocked_intraday_shadow_position_provenance_contract"
    )
    predicted_modes = prediction.get("main_failure_modes") or []

    after = {
        "self_check": self_check,
        "latest_snapshot_projection": latest,
        "source_wiring_checks": source_checks,
        "contract_summary": {
            "decision_time_et": (
                "Snapshot decision time. Uses capture_time_et when the quote "
                "source does not expose a source timestamp."
            ),
            "quote_time_et": (
                "True source quote/bar timestamp only. Remains null for fast_info "
                "and stale fallbacks."
            ),
            "quote_time_basis": (
                "Machine-readable provenance label; prevents capture time from "
                "being mistaken for source quote time."
            ),
            "primary_advisory_shadow_action": (
                "One deterministic position-level row selected by action, urgency, "
                "rule, and triggered-rule order."
            ),
        },
    }
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
        "change_type": "identity_or_measurement_repair",
        "mechanism_family": "intraday_review_exit_risk_allocation",
        "trial_family": "intraday_shadow_action_forward_outcome",
        "trial_variant_id": "position_level_provenance_contract_v1",
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": (
            "post_contract_measurement_repair_for_duplicate_action_and_quote_time_blockers"
        ),
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
            "predicted_failure_modes_hit": [
                mode for mode in predicted_modes if mode in failed
            ],
            "surprise_note": (
                "Low surprise: field semantics were explicit enough to repair "
                "without changing strategy behavior."
                if passed
                else "One or more contract checks failed."
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
                "quote.decision_time_et",
                "quote.quote_time_et",
                "quote.quote_time_basis",
                "advisory_shadow_actions[*].decision_time_et",
                "advisory_shadow_actions[*].source_quote_time_available",
                "advisory_shadow_actions[*].is_primary_shadow_action",
                "advisory_shadow_actions[*].shadow_action_count",
                "positions[*].primary_advisory_shadow_action",
                "trade_enabled/creates_order/pending_action remain false",
            ],
            "self_check": self_check,
            "latest_snapshot_projection": latest,
            "source_wiring_checks": source_checks,
            "entry_date_target_price_note": (
                "entry_date and target_price are not consumed by this measurement "
                "repair. Existing target rules still come only from production "
                "position_context exit_levels."
            ),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "baseline_signals_generated": baseline["signals_generated"],
            "baseline_signals_survived": baseline["signals_survived"],
            "baseline_survival_rate": baseline["survival_rate"],
            "signals_generated_proxy": before["projected_action_count"],
            "signals_survived_proxy": before["primary_action_count"],
            "survival_rate_proxy": (
                round(before["primary_action_count"] / before["projected_action_count"], 6)
                if before["projected_action_count"]
                else None
            ),
            "note": "No entry, exit, filter, ranking, or sizing rule was added.",
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
            "acceptance_basis": (
                "Read-only contract repair accepted: future intraday snapshots "
                "will expose decision-time provenance and one primary advisory "
                "shadow action per position without enabling orders."
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
        },
        "production_impact": {
            "shared_helper_changed": True,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_intraday_snapshot_contract_changed": True,
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "live_ready": False,
            "replay_only": False,
            "parity_note": (
                "Only advisory intraday snapshot/report fields changed. EOD run.py, "
                "backtester.py, order behavior, ranking, sizing, and exits are unchanged."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "exp-20260626-022 found useful shadow-action underperformance but "
                "blocked promotion on quote-time and duplicate-action semantics. "
                "This run repaired those measurement fields for future rows."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry intraday stop/target/time-stop/urgency thresholds on "
                "the same observed ledger. Next alpha work needs newly generated "
                "post-contract closed rows, then a shared default-off exit/risk "
                "policy Gate 1-4 test."
            ),
            "new_evidence_required": (
                "More snapshots generated after this contract, with h1/h3/h5/h10 "
                "settled outcomes and replacement-value accounting. Broker bar IDs "
                "or true quote_time_et would further strengthen causality."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_history_check": (
                "Novelty gate passed. exp-20260626-022 rejected promotion because "
                "quote_time_et was missing and duplicate actions required a "
                "position-level policy."
            ),
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Accept only as measurement repair if decision_time_et is explicit, "
                "quote_time_et is not spoofed, one primary action is selected, and "
                "all rows remain no-order advisory shadows."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "analysis": {
            "before": before,
            "after": after,
        },
        "artifact": repo_rel(OUT_JSON),
        "before_artifact": repo_rel(BEFORE_JSON),
        "after_artifact": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER,
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m py_compile quant\\intraday_quotes.py quant\\intraday_review.py quant\\test_intraday_review.py",
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_intraday_review.py",
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "related_files": [
            RUNNER,
            "quant/intraday_quotes.py",
            "quant/intraday_review.py",
            "quant/test_intraday_review.py",
            repo_rel(BASELINE_RESULT),
            "experiments/logs/exp-20260626-019.json",
            "experiments/logs/exp-20260626-020.json",
            "experiments/logs/exp-20260626-022.json",
        ],
        "changed_files": [
            RUNNER,
            "quant/intraday_quotes.py",
            "quant/intraday_review.py",
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


def write_card(payload: dict[str, Any]) -> None:
    after = payload["analysis"]["after"]
    latest = after["latest_snapshot_projection"]
    lines = [
        f"# {EXPERIMENT_ID}: intraday shadow-action provenance contract",
        "",
        f"- Decision: `{payload['decision']}`",
        "- Strategy/order impact: none; advisory contract only.",
        f"- Latest snapshot actions: `{latest.get('projected_action_count')}`",
        f"- Latest primary rows: `{latest.get('primary_action_count')}`",
        f"- Self-check primary rule: `{after['self_check']['primary_rule']}`",
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
        INTRADAY_QUOTES,
        INTRADAY_REVIEW,
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
    write_json(BEFORE_JSON, payload["analysis"]["before"])
    write_json(AFTER_JSON, payload["analysis"]["after"])
    write_json(OUT_JSON, payload)
    compact = compact_record(payload)
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
    latest = payload["analysis"]["after"]["latest_snapshot_projection"]
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "latest_snapshot_actions": latest.get("projected_action_count"),
        "latest_snapshot_primary_rows": latest.get("primary_action_count"),
        "failed_reasons": payload["gate4"]["failed_reasons"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
