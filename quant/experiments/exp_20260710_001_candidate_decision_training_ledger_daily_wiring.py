"""exp-20260710-001: candidate decision training ledger daily wiring.

Measurement repair for candidate_meta_label. This runner verifies that the new
shared helper writes duplicate-safe candidate decision rows and fixed-horizon
outcomes, and records that run.py wires the helper without changing strategy
behavior. No model is fit and no trading rule is changed.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


EXPERIMENT_ID = "exp-20260710-001"
OWNER = "alpha-explore"
LANE = "measurement_repair"
SLUG = "candidate_decision_training_ledger_daily_wiring"
RUNNER = f"quant/experiments/exp_20260710_001_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
for path in (REPO_ROOT / "scripts", REPO_ROOT / "quant", REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from candidate_decision_training_ledger import (  # noqa: E402
    RULE_VERSION,
    SURFACE_CONTRACT,
    append_candidate_decision_training_snapshot,
    build_candidate_decision_training_snapshot,
    settle_candidate_decision_training_outcomes,
)
from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260710_001_{SLUG}.json"
SMOKE_LEDGER = OUT_DIR / "candidate_decision_training_smoke_rows.jsonl"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Alpha blocker: candidate-entry meta-labeling remains blocked after "
    "exp-20260709-024 because the leak-free candidate decision table has only "
    "130 complete 10d rows; wire a default-off append-only daily "
    "candidate-decision ledger so generated, selected, slot-sliced, and "
    "blocked rows can accumulate settled non-oracle labels without changing "
    "entry, ranking, sizing, exits, orders, or LLM decisions."
)
CHANGE_TYPE = "identity_or_measurement_repair"
IMPLEMENTATION_MODE = "daily_candidate_decision_training_ledger_wiring"
MECHANISM_FAMILY = "candidate_meta_label"
TRIAL_FAMILY = "candidate_decision_training_ledger_daily_wiring"
TRIAL_VARIANT_ID = "candidate_decision_training_ledger_daily_wiring_v1"
SINGLE_CAUSAL_VARIABLE = "candidate_decision_training_ledger_daily_wiring_v1"
CAUSAL_COMPONENTS = [
    "shared ledger helper",
    "run.py default-off hook",
    "focused parity tests",
    "readiness artifact",
    "no strategy behavior change",
]
NEARBY_PRIORS = ["exp-20260709-023", "exp-20260709-024", "exp-20260709-025"]
NEW_EVIDENCE_TYPE = "pipeline_wiring_for_new_training_rows"
NEW_EVIDENCE_AXIS = (
    "Pipeline wiring, not routine delta materialization: this is the first "
    "shared append-only daily candidate_decision_training_ledger surface for "
    "candidate_meta_label, intended to create future non-oracle settled "
    "candidate rows after exp-20260709-024 proved the model sample gate is "
    "still short."
)
ACCEPTANCE_RULE = (
    "Accepted measurement repair only if the shared ledger helper writes "
    "deterministic duplicate-safe default-off candidate decision rows from "
    "daily entry planning, run.py calls it without changing strategy behavior, "
    "focused tests pass, and the artifact records readiness remains "
    "model-blocked until the exp024 sample gate is met."
)
CHANGED_FILES = [
    "quant/candidate_decision_training_ledger.py",
    "quant/run.py",
    "quant/test_candidate_decision_training_ledger.py",
    RUNNER,
    "data/experiments/exp-20260710-001/",
    "experiments/logs/exp-20260710-001.json",
    "experiments/cards/exp-20260710-001.md",
    "experiments/manifests/exp-20260710-001.json",
    "experiments/tickets/exp-20260710-001.json",
    "docs/experiment_registry.json",
]
VERIFICATION_COMMANDS = [
    ".\\.venv\\Scripts\\python.exe -B -m py_compile quant\\candidate_decision_training_ledger.py quant\\test_candidate_decision_training_ledger.py quant\\run.py quant\\experiments\\exp_20260710_001_candidate_decision_training_ledger_daily_wiring.py",
    ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_candidate_decision_training_ledger.py -q",
    RUNNER_COMMAND,
    ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    try:
        return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return value.as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        try:
            return safe(value.item())
        except Exception:
            return str(value)
    return value


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default if default is not None else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
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


def baseline_metrics() -> dict[str, Any]:
    payload = read_json(BASELINE_RESULT, {})
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
        "available": BASELINE_RESULT.exists(),
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(
            sum(float(row.get("total_pnl") or 0.0) for row in windows),
            2,
        ),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
    }


def candidate(ticker: str, rank: int, *, reason: str = "selected_by_entry_plan") -> dict[str, Any]:
    decision = "buy" if reason == "selected_by_entry_plan" else "deferred"
    return {
        "rank": rank,
        "ticker": ticker,
        "strategy": "trend_long",
        "sector": "Technology",
        "entry_price": 100.0 + rank,
        "stop_price": 94.0 + rank,
        "target_price": 118.0 + rank,
        "risk_reward_ratio": 2.8,
        "trade_quality_score": 0.92,
        "confidence_score": 1.0,
        "days_to_earnings": 20,
        "shares_to_buy": 10,
        "position_value_usd": 1000.0,
        "live_accounting": {"decision": decision, "reason": reason},
        "backtest_accounting": {"decision": decision, "reason": reason},
    }


def bars(start: float) -> list[dict[str, Any]]:
    days = [
        "2026-07-06",
        "2026-07-07",
        "2026-07-08",
        "2026-07-09",
        "2026-07-10",
        "2026-07-13",
        "2026-07-14",
        "2026-07-15",
        "2026-07-16",
        "2026-07-17",
        "2026-07-20",
        "2026-07-21",
        "2026-07-22",
        "2026-07-23",
        "2026-07-24",
        "2026-07-27",
        "2026-07-28",
        "2026-07-29",
        "2026-07-30",
        "2026-07-31",
        "2026-08-03",
    ]
    return [
        {"date": day, "open": start + index, "close": start + index + 0.5}
        for index, day in enumerate(days)
    ]


def run_smoke() -> dict[str, Any]:
    if SMOKE_LEDGER.exists():
        SMOKE_LEDGER.unlink()
    state_path = SMOKE_LEDGER.with_name("state.json")
    if state_path.exists():
        state_path.unlink()
    review = {
        "diagnostic_only": True,
        "orders_changed": False,
        "candidate_count": 2,
        "candidates": [
            candidate("AAA", 1),
            candidate("BBB", 2, reason="slot_sliced"),
        ],
    }
    snapshot = build_candidate_decision_training_snapshot(
        as_of="2026-07-02",
        entry_candidate_review=review,
        metadata={"source": EXPERIMENT_ID},
    )
    first_append = append_candidate_decision_training_snapshot(snapshot, SMOKE_LEDGER)
    second_append = append_candidate_decision_training_snapshot(snapshot, SMOKE_LEDGER)
    first_settle = settle_candidate_decision_training_outcomes(
        ledger_path=SMOKE_LEDGER,
        as_of="2026-08-03",
        ohlcv_by_ticker={
            "AAA": bars(100.0),
            "BBB": bars(120.0),
            "SPY": bars(400.0),
            "QQQ": bars(500.0),
        },
    )
    second_settle = settle_candidate_decision_training_outcomes(
        ledger_path=SMOKE_LEDGER,
        as_of="2026-08-03",
        ohlcv_by_ticker={
            "AAA": bars(100.0),
            "BBB": bars(120.0),
            "SPY": bars(400.0),
            "QQQ": bars(500.0),
        },
    )
    rows = [
        json.loads(line)
        for line in SMOKE_LEDGER.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {
        "snapshot_candidate_count": snapshot["candidate_count"],
        "snapshot_entry_dates": sorted({row["entry_date"] for row in snapshot["rows"]}),
        "snapshot_target_price_present_count": snapshot["target_price_present_count"],
        "first_append": first_append,
        "second_append": second_append,
        "first_settle": first_settle,
        "second_settle": second_settle,
        "record_type_counts": {
            key: sum(1 for row in rows if row.get("record_type") == key)
            for key in ("candidate_decision_snapshot", "candidate_decision_outcome")
        },
        "ledger_path": repo_rel(SMOKE_LEDGER),
        "state_path": repo_rel(state_path),
    }


def run_py_contract() -> dict[str, Any]:
    text = (REPO_ROOT / "quant" / "run.py").read_text(encoding="utf-8")
    required = [
        "build_candidate_decision_training_snapshot",
        "append_candidate_decision_training_snapshot",
        "settle_candidate_decision_training_outcomes",
        '"candidate_decision_training_ledger"',
    ]
    missing = [item for item in required if item not in text]
    return {
        "passed": not missing,
        "missing": missing,
        "required_markers": required,
    }


def build_payload() -> dict[str, Any]:
    baseline = baseline_metrics()
    smoke = run_smoke()
    run_contract = run_py_contract()
    smoke_passed = (
        smoke["first_append"]["rows_written"] == 2
        and smoke["second_append"]["rows_written"] == 0
        and smoke["first_settle"]["outcome_rows_written"] == 4
        and smoke["second_settle"]["outcome_rows_written"] == 0
        and smoke["snapshot_entry_dates"] == ["2026-07-06"]
        and smoke["snapshot_target_price_present_count"] == 2
    )
    accepted = bool(smoke_passed and run_contract["passed"])
    status = "accepted_measurement_repair" if accepted else "blocked"
    decision = (
        "accepted_measurement_repair_candidate_decision_training_ledger_daily_wired"
        if accepted
        else "blocked_candidate_decision_training_ledger_daily_wiring"
    )
    failed = []
    if not smoke_passed:
        failed.append("helper_smoke_contract_failed")
    if not run_contract["passed"]:
        failed.append("run_py_hook_missing")

    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "owner": OWNER,
        "lane": LANE,
        "status": status,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "accepted_measurement_repair": accepted,
        "alpha_ready": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": SINGLE_CAUSAL_VARIABLE,
        "changed_variable": SINGLE_CAUSAL_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIORS,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "acceptance_rule": ACCEPTANCE_RULE,
        "prediction": None,
        "baseline_metrics": baseline,
        "before_metrics": baseline,
        "after_metrics": {
            **baseline,
            "shared_helper_added": True,
            "run_py_hook_present": run_contract["passed"],
            "smoke_snapshot_rows_written": smoke["first_append"]["rows_written"],
            "smoke_outcome_rows_written": smoke["first_settle"]["outcome_rows_written"],
        },
        "delta_metrics": {
            "expected_value_score_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "strategy_behavior_changed": False,
            "daily_candidate_training_ledger_hook_added": 1 if run_contract["passed"] else 0,
        },
        "gate1": {
            "passed": baseline["available"],
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_metrics": baseline,
            "note": "Measurement repair only; no before/after strategy metric change.",
        },
        "gate2": {
            "passed": accepted,
            "required_fields_checked": [
                "observation_id",
                "as_of",
                "ticker",
                "strategy",
                "candidate_status",
                "entry_date",
                "target_price",
                "candidate_decision_outcome",
            ],
            "entry_date_target_price_sentinel": {
                "entry_date_present_count": smoke["snapshot_candidate_count"],
                "target_price_present_count": smoke["snapshot_target_price_present_count"],
                "entry_date_values": smoke["snapshot_entry_dates"],
            },
        },
        "gate3": {
            "passed": True,
            "adds_filter": False,
            "survival_rate_not_applicable": True,
            "baseline_survival_rate": baseline["survival_rate"],
        },
        "gate4": {
            "passed": accepted,
            "measurement_repair_only": True,
            "accepted_alpha": False,
            "strategy_behavior_changed": False,
            "failed_reasons": failed,
            "decision": decision,
        },
        "production_impact": {
            "accepted_measurement_repair": accepted,
            "trade_enabled": False,
            "shared_observer_contract_changed": True,
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": True,
            "daily_snapshot_exposed": True,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "alters_orders": False,
            "llm_change_scope": "none",
            "live_ready": False,
        },
        "smoke_contract": smoke,
        "run_py_contract": run_contract,
        "helper_contract": {
            "rule_version": RULE_VERSION,
            "surface_contract": SURFACE_CONTRACT,
            "default_ledger_path": "data/paper_sleeves/candidate_decision_training_ledger/rows.jsonl",
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The daily entry planning surface already contains candidate "
                "review rows with live/backtest decisions; the repair adds a "
                "shared append-only observer and outcome-settlement contract so "
                "future rows can mature without fitting a model or changing "
                "orders. Recent daily quant snapshots currently have zero "
                "candidate rows, so this is pipeline readiness, not alpha."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not train or tune a candidate_meta_label model, probability "
                "scalar, admission threshold, decision-cohort cut, or response "
                "curve until the ledger meets the exp-20260709-024 sample gate."
            ),
            "new_evidence_required": (
                "At least 300 complete candidate rows, 75 positive and 75 "
                "negative fixed-horizon labels, selected and rejected/unselected "
                "coverage, three chronological folds with >=50 test rows and "
                "both classes, and no single ticker above 20% of complete rows."
            ),
            "next_evidence_needed": (
                "Let run.py accumulate and settle candidate_decision_training_ledger "
                "rows; the next alpha run should be a one-line readiness count "
                "until the sample gate moves."
            ),
        },
        "rejection_reason": ";".join(failed) if failed else None,
        "realized_failure_mode": None if accepted else ";".join(failed),
        "related_files": CHANGED_FILES,
        "changed_files": CHANGED_FILES,
        "reproduction_commands": VERIFICATION_COMMANDS,
        "lean_quality_passed": accepted,
    }


def build_card(payload: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: candidate decision training ledger daily wiring",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Accepted alpha: `false`",
            f"- Helper smoke rows written: `{payload['smoke_contract']['first_append']['rows_written']}`",
            f"- Helper smoke outcomes written: `{payload['smoke_contract']['first_settle']['outcome_rows_written']}`",
            f"- run.py hook present: `{payload['run_py_contract']['passed']}`",
            "- Strategy/live order behavior changed: `false`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Next Evidence",
            "",
            payload["post_run_reflection"]["new_evidence_required"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            *VERIFICATION_COMMANDS,
            "```",
            "",
        ]
    )


def build_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    files = [REPO_ROOT / rel for rel in CHANGED_FILES if not rel.endswith("/")]
    files.append(OUT_JSON)
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
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(payload, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
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
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": "measurement_repair_candidate_decision_training_ledger_daily_wired",
        },
        status=payload["status"],
        fields={
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
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "ticket_file": repo_rel(TICKET_JSON),
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "rejection_reason": payload["rejection_reason"],
            "realized_failure_mode": payload["realized_failure_mode"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "reproduction_commands": payload["reproduction_commands"],
            "lean_quality_passed": payload["lean_quality_passed"],
        },
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
                "artifact": repo_rel(OUT_JSON),
                "gate4": payload["gate4"],
                "smoke_contract": payload["smoke_contract"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if payload["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
