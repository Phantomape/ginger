"""exp-20260708-030: wire the chop-bundle forward observer into run.py.

Measurement repair / pipeline wiring. The two frozen chop bundles
(exp-20260708-023 mean reversion, exp-20260708-025 pairs spread) are
calendar-bound: canonical windows hold only ~33 chop days, so their verdicts
can only come from forward chop-day paper rows. This wiring adds
``quant/chop_forward_observer.py`` (replays the frozen bundles on the frames
run.py already loads; idempotent upsert into
``data/paper_sleeves/chop_forward/rows.jsonl``) and a failure-tolerant run.py
step. After this, daily materialization takes no further experiment IDs
(AGENTS.md routine-materialization rule). No strategy behavior changes.
"""

from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

EXPERIMENT_ID = "exp-20260708-030"
OWNER = "interactive"
LANE = "measurement_repair"
SLUG = "chop_forward_observer_wiring"
RUNNER = f"quant/experiments/exp_20260708_030_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = REPO_ROOT / "quant"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for entry in (REPO_ROOT, QUANT_ROOT, SCRIPTS_ROOT):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)
from filter import WATCHLIST  # noqa: E402

DATA_DIR = REPO_ROOT / "data"
BASELINE_RESULT = (
    DATA_DIR / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
LEDGER_DIR = DATA_DIR / "paper_sleeves" / "chop_forward"

OUT_DIR = DATA_DIR / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"exp_20260708_030_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Pipeline wiring: both frozen chop bundles need forward chop-day paper rows "
    "to ever reach a verdict (canonical windows hold ~33 chop days total); wire "
    "a daily default-off forward observer into run.py that replays the frozen "
    "bundles over a trailing window and idempotently upserts open/closed paper "
    "rows into a forward ledger. One-time wiring; no strategy behavior changes."
)
CHANGED_VARIABLE = "chop_forward_observer_daily_wiring_v1"
MECHANISM_FAMILY = "chop_regime_forward_measurement"
TRIAL_FAMILY = "chop_forward_observer_wiring"
TRIAL_VARIANT_ID = "chop_forward_observer_v1"
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260708-023", "exp-20260708-025", "exp-20260706-010"]
CAUSAL_COMPONENTS = [
    "shared_forward_observer_module",
    "frozen_bundle_replay_reuse",
    "idempotent_row_upsert_ledger",
    "run_py_failure_tolerant_step",
    "no_strategy_behavior_change",
]
PREDICTED_FAILURE_MODES = [
    "frame_lookback_too_short_for_sma200",
    "regime_label_daily_vs_replay_divergence",
    "ledger_upsert_key_collision",
    "run_py_step_ordering_breaks_frames",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: str | Path) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [safe(item) for item in value]
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(safe(payload), indent=2, ensure_ascii=True, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return default if default is not None else {}


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
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "window_count": len(windows),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows), 4
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": sum(int(row.get("trade_count") or 0) for row in windows),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 6) if generated else None,
        "max_drawdown_pct_worst": round(max(drawdowns), 4) if drawdowns else None,
    }


def load_frames() -> dict[str, Any]:
    import pandas as pd

    rows: dict[str, dict[str, tuple]] = {}
    for wh in ("warehouse_main.sqlite", "warehouse_main_hot.sqlite"):
        path = DATA_DIR / "warehouse" / wh
        if not path.exists():
            continue
        con = sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)
        try:
            placeholders = ",".join("?" for _ in WATCHLIST)
            query = (
                "select ticker, date, open, high, low, close from ohlcv "
                f"where ticker in ({placeholders}) and date >= ?"
            )
            for t, d, o, h, l, c in con.execute(query, (*WATCHLIST, "2025-06-01")):
                if c is not None:
                    rows.setdefault(str(t).upper(), {})[str(d)[:10]] = (o or c, h or c, l or c, c)
        finally:
            con.close()
    frames = {}
    for ticker, by_date in rows.items():
        days = sorted(by_date)
        frames[ticker] = pd.DataFrame(
            [
                {"Open": by_date[d][0], "High": by_date[d][1], "Low": by_date[d][2], "Close": by_date[d][3]}
                for d in days
            ],
            index=pd.to_datetime(days),
        )
    return frames


def run_tests() -> dict[str, Any]:
    proc = subprocess.run(
        [
            str(REPO_ROOT / ".venv" / "Scripts" / "python.exe"),
            "-m", "pytest",
            "quant/test_chop_forward_observer.py",
            "quant/test_run_daily_wiring.py",
            "quant/test_chop_mean_reversion_sleeve.py",
            "quant/test_chop_pairs_spread_sleeve.py",
            "-q", "--no-header",
        ],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=1200,
    )
    return {
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "tail": (proc.stdout or "").strip().splitlines()[-3:],
    }


def build_payload() -> dict[str, Any]:
    from chop_forward_observer import persist_chop_forward_observations

    ticket = read_json(TICKET_JSON, {})
    baseline = baseline_metrics()
    today_iso = datetime.now(timezone.utc).date().isoformat()

    frames = load_frames()
    smoke_first = persist_chop_forward_observations(frames, as_of=today_iso)
    smoke_second = persist_chop_forward_observations(frames, as_of=today_iso)
    run_source = (QUANT_ROOT / "run.py").read_text(encoding="utf-8")
    tests = run_tests()

    measurement_blockers: list[str] = []
    if not BASELINE_RESULT.exists() or baseline.get("window_count") != 3:
        measurement_blockers.append("baseline_missing_or_nonstandard")
    if smoke_first.get("status") != "ok":
        measurement_blockers.append(f"observer_smoke_failed:{smoke_first.get('status')}")
    if smoke_second.get("rows_total") != smoke_first.get("rows_total"):
        measurement_blockers.append("observer_not_idempotent")
    if "persist_chop_forward_observations" not in run_source:
        measurement_blockers.append("run_py_wiring_missing")
    if "Chop forward observer unavailable" not in run_source:
        measurement_blockers.append("run_py_failure_guard_missing")
    if not tests["passed"]:
        measurement_blockers.append("test_regression")

    measurement_passed = not measurement_blockers
    status = "accepted_measurement_repair" if measurement_passed else "blocked"
    decision = (
        f"accepted_measurement_repair_{SLUG}" if measurement_passed else f"blocked_{SLUG}"
    )
    strategy_delta = {
        "expected_value_score_sum_delta": 0.0,
        "total_pnl_delta": 0.0,
        "trade_count_delta": 0,
        "signals_generated_delta": 0,
        "signals_survived_delta": 0,
        "strategy_behavior_changed": False,
    }
    delta_metrics = {
        **strategy_delta,
        "observer_status": smoke_first.get("status"),
        "regime_label_asof": smoke_first.get("regime_label_asof"),
        "chop_days_in_trailing_window": smoke_first.get("chop_days_in_window"),
        "ledger_rows_total": smoke_first.get("rows_total"),
        "ledger_rows_closed": smoke_first.get("rows_closed"),
        "idempotent_rerun_rows_delta": (
            (smoke_second.get("rows_total") or 0) - (smoke_first.get("rows_total") or 0)
        ),
        "unit_tests_passed": tests["passed"],
    }
    success_probability = float(
        (ticket.get("prediction") or {}).get("success_probability") or 0.85
    )
    prediction = {
        "recorded_at": ticket.get("claimed_at") or ticket.get("created_at"),
        "success_probability": success_probability,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": PREDICTED_FAILURE_MODES,
        "confidence_reason": (ticket.get("prediction") or {}).get("confidence_reason"),
    }
    calibration = {
        "predicted_success_probability": success_probability,
        "actual_success": 1 if measurement_passed else 0,
        "brier_score": round(
            (success_probability - (1.0 if measurement_passed else 0.0)) ** 2, 6
        ),
        "predicted_failure_modes": PREDICTED_FAILURE_MODES,
        "realized_failure_modes": measurement_blockers,
        "predicted_failure_mode_hit": bool(
            set(measurement_blockers) & set(PREDICTED_FAILURE_MODES)
        ),
    }
    production_impact = {
        "trade_enabled": False,
        "shared_policy_changed": False,
        "backtester_adapter_changed": False,
        "run_adapter_changed": True,
        "daily_snapshot_exposed": False,
        "entry_rules_changed": False,
        "exit_rules_changed": False,
        "ranking_changed": False,
        "sizing_changed": False,
        "orders_changed": False,
        "llm_decision_boundary_changed": False,
        "live_ready": False,
        "live_realism_evaluated": False,
        "scope": "measurement_wiring_forward_chop_bundle_observation_only",
    }
    files = [
        "quant/chop_forward_observer.py",
        "quant/test_chop_forward_observer.py",
        "quant/run.py",
        RUNNER,
        repo_rel(OUT_JSON),
        repo_rel(LOG_JSON),
        repo_rel(CARD_MD),
        repo_rel(MANIFEST_JSON),
        repo_rel(TICKET_JSON),
        repo_rel(REGISTRY_JSON),
        "data/paper_sleeves/chop_forward/rows.jsonl",
        "data/paper_sleeves/chop_forward/summary.json",
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": utc_now(),
        "status": status,
        "lane": LANE,
        "owner": OWNER,
        "decision": decision,
        "accepted": measurement_passed,
        "accepted_alpha": False,
        "accepted_measurement_repair": measurement_passed,
        "alpha_ready": False,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": (
            "None directly; this ledger is the evidence channel through which the two "
            "frozen chop bundles (and the sleeve-scoped chop down-tilt) get their verdicts."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_wiring_forward_observer",
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "pipeline_wiring_for_forward_chop_rows",
        "prediction": prediction,
        "calibration": calibration,
        "pre_run_questions": {
            "1_alpha_hypothesis": "Forward chop-day rows are the only remaining evidence source for the chop lane.",
            "2_history_check": {
                "exp-20260708-023": "Mean reversion in chop rejected on 41 trades; bundle frozen.",
                "exp-20260708-025": "Pairs spread in chop observed_only on 9 trades; bundle frozen.",
                "exp-20260706-010": "Precedent: settlement wiring accepted as measurement repair.",
            },
            "3_single_measurement_bundle": CHANGED_VARIABLE,
            "4_success_failure_standard": (
                "Accept only if the observer smoke-runs ok on real frames, re-run is "
                "idempotent, run.py carries the failure-tolerant step, and all tests pass."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "entry_window_trading_days": 45,
            "ledger": "data/paper_sleeves/chop_forward/rows.jsonl",
            "upsert_key": "bundle|instrument|signal_date",
            "bundles": ["chop_mean_reversion_v1", "chop_pairs_spread_v1"],
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists() and baseline.get("window_count") == 3,
            "baseline_metrics": baseline,
        },
        "gate2": {
            "passed": measurement_passed,
            "dependencies_validated": measurement_passed,
            "fields_checked": [
                "bundle", "row_status", "signal_date", "entry_date", "exit_reason",
                "regime_label_at_signal", "pnl_usd",
            ],
            "entry_date_scope": "Forward paper rows carry entry_date; no production signal objects are created.",
            "target_price_scope": "Not applicable; bundle exits are rule-based (SMA5/z-convergence/timeout).",
        },
        "gate3": {
            "passed": measurement_passed,
            "filter_added": False,
            "signals_generated": None,
            "signals_survived": None,
            "survival_rate": None,
            "note": "Measurement wiring only; no executable filter/entry/rank/size/exit/order rule added.",
        },
        "gate4": {
            "passed": measurement_passed,
            "accepted_alpha": False,
            "alpha_ready": False,
            "decision": decision,
            "measurement_blockers": measurement_blockers,
            "alpha_blockers": [],
            "measurement_repair_only": True,
            "strategy_rerun_required": False,
            "before_after_strategy_delta": strategy_delta,
        },
        "before_metrics": baseline,
        "after_metrics": baseline,
        "delta_metrics": delta_metrics,
        "smoke": {"first": smoke_first, "second": smoke_second},
        "tests": tests,
        "production_impact": production_impact,
        "post_run_reflection": {
            "why_result_happened": (
                "The observer reuses the exact frozen replay functions on frames the "
                "pipeline already loads, so wiring reduced to one failure-tolerant "
                "run.py step plus an idempotent ledger."
                if measurement_passed
                else "The wiring did not satisfy the fixed measurement contract."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not reserve further IDs for daily chop-row materialization; the "
                "run.py step now owns it. Reopen the chop bundles only when the "
                "ledger holds >= 15 closed chop rows for a bundle (mean reversion) "
                "or >= 15 closed spreads (pairs)."
            ),
            "new_evidence_required": (
                "Calendar time: forward chop-labeled days accruing rows in "
                "data/paper_sleeves/chop_forward/rows.jsonl."
            ),
        },
        "next_retry_requires": [
            ">=15 closed forward chop rows per bundle before any verdict reopen",
            "no manual daily materialization IDs (wired into run.py)",
        ],
        "changed_files": files,
        "related_files": [
            "quant/chop_mean_reversion_sleeve.py",
            "quant/chop_pairs_spread_sleeve.py",
            "quant/regime_chop_state.py",
        ],
        "allowed_write_scope": files,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -m pytest quant\\test_chop_forward_observer.py -q",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {"used_javascript": False, "evidence": "Python runner only."},
        "lean_quality_passed": measurement_passed,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "ticket_before": {
            "created_at": ticket.get("created_at"),
            "claimed_at": ticket.get("claimed_at"),
            "hub_identity": ticket.get("hub_identity"),
            "novelty": ticket.get("novelty"),
        },
    }


def build_card(payload: dict[str, Any]) -> str:
    delta = payload["delta_metrics"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: chop forward observer wiring",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Observer smoke: `{delta['observer_status']}`, label asof `{delta['regime_label_asof']}`, chop days in 45d `{delta['chop_days_in_trailing_window']}`",
            f"- Ledger rows: `{delta['ledger_rows_total']}` (idempotent rerun delta `{delta['idempotent_rerun_rows_delta']}`)",
            f"- Tests passed: `{delta['unit_tests_passed']}`",
            "- Strategy behavior changed: `false`",
            "",
            "## Boundary",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            "## Reproduction",
            "",
            "```powershell",
            RUNNER_COMMAND,
            "```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        QUANT_ROOT / "chop_forward_observer.py",
        QUANT_ROOT / "test_chop_forward_observer.py",
        QUANT_ROOT / "run.py",
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
        LEDGER_DIR / "rows.jsonl",
        LEDGER_DIR / "summary.json",
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
            repo_rel(path): {"exists": path.exists(), "sha256": sha256(path)}
            for path in files
        },
        "changed_files": payload["changed_files"],
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
            "alpha_ready": False,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "gate4": payload["gate4"],
            "delta_metrics": payload["delta_metrics"],
            "calibration": payload["calibration"],
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
            "before_metrics": payload["before_metrics"],
            "after_metrics": payload["after_metrics"],
            "delta_metrics": payload["delta_metrics"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "next_retry_requires": payload["next_retry_requires"],
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "calibration": payload["calibration"],
            "hub_identity": payload["ticket_before"].get("hub_identity"),
            "novelty": payload["ticket_before"].get("novelty"),
            "claimed_at": payload["ticket_before"].get("claimed_at"),
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
                "delta_metrics": payload["delta_metrics"],
                "gate4": payload["gate4"],
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
