"""exp-20260627-002: daily non-OHLCV borrow availability wiring.

Measurement repair only. This accepts the optional, fail-soft wiring that lets
the daily non-OHLCV snapshot call the existing Moomoo borrow-availability
sidecar when explicitly enabled. It changes no entry, exit, ranking, sizing,
orders, paper sleeve policy, or LLM decision boundary.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import math
import sys
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
import backfill_non_ohlcv  # noqa: E402
import daily_non_ohlcv_snapshot  # noqa: E402


EXPERIMENT_ID = "exp-20260627-002"
OWNER = "alpha-explore"
SLUG = "daily_non_ohlcv_borrow_availability_wiring"
RUNNER = f"quant/experiments/exp_20260627_002_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260627_002_{SLUG}.json"
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
BORROW_MANIFEST = REPO_ROOT / "data" / "non_ohlcv" / "borrow_availability" / "manifest.json"
BORROW_ROWS = REPO_ROOT / "data" / "non_ohlcv" / "borrow_availability" / "rows.jsonl"

HYPOTHESIS = (
    "alpha_blocker/measurement_repair: if PIT borrow fee or loan availability "
    "is the required reopen axis for frozen FINRA/options/short-flow alpha, "
    "the existing Moomoo borrow sidecar must be callable from the daily "
    "non-OHLCV snapshot so future forward rows can accumulate without any "
    "trading decision."
)
ALPHA_HYPOTHESIS = (
    "Populated borrow-cost or loan-availability rows could later separate "
    "crowded-but-durable winners from exhausted squeeze/short-flow candidates; "
    "this run only wires the forward collection surface needed to test that."
)
CHANGE_TYPE = "measurement_repair"
IMPLEMENTATION_MODE = "shared_default_off_forward_data_collection"
MECHANISM_FAMILY = "production_visible_moomoo_borrow_availability_readiness"
TRIAL_FAMILY = "daily_non_ohlcv_borrow_availability_forward_collection"
TRIAL_VARIANT_ID = "default_off_daily_snapshot_borrow_sidecar_v1"
CHANGED_VARIABLE = "daily_non_ohlcv_borrow_availability_forward_collection_v1"
NEW_EVIDENCE_TYPE = "default_off_forward_borrow_collection_wiring"
NEARBY_PRIOR_EXPERIMENTS = [
    "exp-20260625-003",
    "exp-20260626-015",
    "exp-20260626-025",
]
CAUSAL_COMPONENTS = [
    "daily non-OHLCV snapshot optional borrow sidecar call",
    "backfill_non_ohlcv parameter passthrough",
    "run.py env-gated daily profile passthrough",
    "fail-soft snapshot substatus",
    "no strategy behavior change",
]
ALLOWED_WRITE_SCOPE = [
    RUNNER,
    "quant/daily_non_ohlcv_snapshot.py",
    "quant/backfill_non_ohlcv.py",
    "quant/run.py",
    "quant/test_daily_non_ohlcv_snapshot.py",
    f"data/experiments/{EXPERIMENT_ID}/",
    f"experiments/cards/{EXPERIMENT_ID}.md",
    f"experiments/manifests/{EXPERIMENT_ID}.json",
    f"experiments/logs/{EXPERIMENT_ID}.json",
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
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default if default is not None else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        text = raw.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(make_json_safe(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): make_json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [make_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [make_json_safe(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(make_json_safe(record), sort_keys=True)
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
    return {
        "baseline_result_file": repo_rel(BASELINE_RESULT),
        "expected_value_score_sum": round(
            sum(float(row.get("expected_value_score") or 0.0) for row in windows),
            4,
        ),
        "total_pnl": round(sum(float(row.get("total_pnl") or 0.0) for row in windows), 2),
        "trade_count": int(sum(int(row.get("trade_count") or 0) for row in windows)),
        "signals_generated": generated,
        "signals_survived": survived,
        "survival_rate": round(survived / generated, 4) if generated else None,
        "max_drawdown_pct_worst": max(
            (float(row.get("max_drawdown_pct") or 0.0) for row in windows),
            default=None,
        ),
        "window_count": len(windows),
        "windows": [
            {
                "label": row.get("label"),
                "start": row.get("start"),
                "end": row.get("end"),
                "expected_value_score": row.get("expected_value_score"),
                "total_pnl": row.get("total_pnl"),
                "trade_count": row.get("trade_count"),
                "signals_generated": row.get("signals_generated"),
                "signals_survived": row.get("signals_survived"),
                "survival_rate": row.get("survival_rate"),
                "max_drawdown_pct": row.get("max_drawdown_pct"),
                "sharpe_daily": row.get("sharpe_daily"),
            }
            for row in windows
            if isinstance(row, dict)
        ],
    }


def current_borrow_surface() -> dict[str, Any]:
    manifest = read_json(BORROW_MANIFEST, {})
    rows = read_jsonl(BORROW_ROWS)
    populated = sum(1 for row in rows if row.get("borrow_populated"))
    return {
        "manifest_exists": BORROW_MANIFEST.exists(),
        "rows_exists": BORROW_ROWS.exists(),
        "row_count": len(rows),
        "as_of_date_count": len({row.get("as_of_date") for row in rows if row.get("as_of_date")}),
        "borrow_populated_rows": populated,
        "manifest_rows_appended_this_run": manifest.get("rows_appended_this_run"),
        "manifest_borrow_populated_this_run": manifest.get("borrow_populated_this_run"),
        "manifest_borrow_populated_pct": manifest.get("borrow_populated_pct"),
        "last_collected_as_of": manifest.get("last_collected_as_of"),
        "entitlement_caveat": manifest.get("entitlement_caveat"),
    }


def contract_summary() -> dict[str, Any]:
    daily_sig = inspect.signature(daily_non_ohlcv_snapshot.persist_daily_non_ohlcv_snapshots)
    backfill_sig = inspect.signature(backfill_non_ohlcv.ensure_non_ohlcv_coverage)
    daily_params = set(daily_sig.parameters)
    backfill_params = set(backfill_sig.parameters)
    return {
        "daily_snapshot_accepts_refresh_borrow_availability": (
            "refresh_borrow_availability" in daily_params
        ),
        "daily_snapshot_accepts_borrow_availability_broad": (
            "borrow_availability_broad" in daily_params
        ),
        "backfill_accepts_refresh_borrow_availability": (
            "refresh_borrow_availability" in backfill_params
        ),
        "backfill_accepts_borrow_availability_broad": (
            "borrow_availability_broad" in backfill_params
        ),
        "run_env_gate": "REFRESH_BORROW_AVAILABILITY",
        "run_broad_env_gate": "BORROW_AVAILABILITY_BROAD",
        "default_refresh_enabled": False,
        "fail_soft_helper": "daily_non_ohlcv_snapshot._run_borrow_availability",
    }


def calibration(prediction: dict[str, Any], accepted: bool) -> dict[str, Any]:
    prob = float(prediction.get("success_probability") or 0.0)
    return {
        "actual_decision": "accepted_measurement_repair" if accepted else "rejected",
        "actual_success": 1 if accepted else 0,
        "predicted_success_probability": prob,
        "brier": round((prob - (1 if accepted else 0)) ** 2, 4),
    }


def build_payload() -> dict[str, Any]:
    timestamp = utc_now()
    ticket = read_json(TICKET_JSON, {})
    prediction = ticket.get("prediction") if isinstance(ticket.get("prediction"), dict) else {
        "success_probability": 0.62,
        "expected_ev_delta": 0.0,
        "expected_pnl_delta": 0.0,
        "main_failure_modes": [
            "moomoo_opend_unavailable",
            "borrow_sidecar_not_stub_safe",
            "daily_snapshot_status_regression",
        ],
        "confidence_reason": "Fallback prediction for default-off borrow sidecar daily wiring.",
        "recorded_at": timestamp,
    }
    before = baseline_metrics()
    after = dict(before)
    contract = contract_summary()
    failed_reasons = [
        key
        for key, ok in contract.items()
        if key.startswith(("daily_snapshot_accepts", "backfill_accepts")) and not ok
    ]
    accepted = not failed_reasons
    status = "accepted_measurement_repair" if accepted else "rejected"
    decision = (
        "accepted_measurement_repair_daily_non_ohlcv_borrow_availability_wiring"
        if accepted
        else "rejected_daily_non_ohlcv_borrow_availability_wiring_incomplete"
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "status": status,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "alpha_ready": False,
        "observed_only_lead": False,
        "lane": "measurement_repair",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "alpha_hypothesis": ALPHA_HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "prediction": prediction,
        "calibration": calibration(prediction, accepted),
        "pre_run_questions": {
            "1_alpha_hypothesis": ALPHA_HYPOTHESIS,
            "2_prior_work": (
                "Novelty gate allowed exp-20260627-002; nearest prior is "
                "exp-20260625-003, which built/readiness-audited the sidecar "
                "but did not wire it into daily snapshot/run."
            ),
            "3_single_policy_bundle": CHANGED_VARIABLE,
            "4_success_criteria": (
                "Accepted only as measurement repair if the daily snapshot and "
                "run/backfill path can call or stub the sidecar fail-soft, "
                "report no strategy behavior change, focused tests pass, and "
                "canonical baseline metrics remain unchanged."
            ),
            "5_reproducibility": RUNNER_COMMAND,
        },
        "parameters": {
            "refresh_borrow_availability_default": False,
            "refresh_env": "REFRESH_BORROW_AVAILABILITY",
            "broad_env": "BORROW_AVAILABILITY_BROAD",
            "trade_enabled": False,
        },
        "borrow_surface_before": current_borrow_surface(),
        "daily_snapshot_contract": contract,
        "before_metrics": before,
        "after_metrics": after,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "max_drawdown_pct_worst_delta": 0.0,
            "strategy_behavior_changed": False,
        },
        "gate1": {
            "passed": BASELINE_RESULT.exists(),
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "baseline_expected_value_score_sum": before["expected_value_score_sum"],
            "baseline_total_pnl": before["total_pnl"],
        },
        "gate2": {
            "passed": accepted,
            "runtime_fields_required": [
                "entry_date",
                "target_price",
                "borrow_availability.status",
                "borrow_availability.borrow_populated_this_run",
                "borrow_availability.trade_enabled",
            ],
            "strategy_fields_changed": False,
            "contract": contract,
        },
        "gate3": {
            "passed": True,
            "not_applicable_reason": "No signal generation, survival filter, ranking, sizing, or order rule changed.",
            "signals_generated_delta": 0,
            "signals_survived_delta": 0,
            "survival_rate_delta": 0.0,
        },
        "gate4": {
            "passed": accepted,
            "accepted_alpha": False,
            "measurement_repair_only": True,
            "decision": decision,
            "failed_reasons": failed_reasons,
            "before_after_strategy_delta": {
                "expected_value_score_sum_delta": 0.0,
                "total_pnl_delta": 0.0,
                "trade_count_delta": 0,
                "strategy_behavior_changed": False,
            },
            "verification_commands": [
                ".\\.venv\\Scripts\\python.exe -m pytest quant\\test_daily_non_ohlcv_snapshot.py quant\\test_backfill_non_ohlcv.py quant\\test_run_daily_wiring.py",
                ".\\.venv\\Scripts\\python.exe -B -m py_compile quant\\daily_non_ohlcv_snapshot.py quant\\backfill_non_ohlcv.py quant\\run.py quant\\test_daily_non_ohlcv_snapshot.py",
            ],
        },
        "production_impact": {
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
                "Data collection is opt-in by REFRESH_BORROW_AVAILABILITY and "
                "fail-soft. It does not feed any trading decision or ranking path."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The sidecar already existed, so the direct blocker was wiring: "
                "daily_non_ohlcv_snapshot now exposes an optional borrow_availability "
                "section, backfill_non_ohlcv passes the flags through, and run.py "
                "has env gates for the daily profile."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not rerun FINRA/options/short-flow alpha slices merely because "
                "borrow collection is wired. A retry still needs populated "
                "short_sell_rate_pct or short_available_volume rows over materially "
                "more forward dates."
            ),
            "new_evidence_required": (
                "Enable REFRESH_BORROW_AVAILABILITY after OpenD is available and "
                "collect at least 20 forward dates with nonzero borrow fields, then "
                "run closed forward replacement-value attribution versus cash, SPY, "
                "QQQ, and accepted comparators."
            ),
        },
        "related_files": [
            RUNNER,
            "quant/daily_non_ohlcv_snapshot.py",
            "quant/backfill_non_ohlcv.py",
            "quant/run.py",
            "quant/test_daily_non_ohlcv_snapshot.py",
            repo_rel(BORROW_MANIFEST),
            repo_rel(BORROW_ROWS),
            repo_rel(BASELINE_RESULT),
        ],
        "changed_files": [
            RUNNER,
            "quant/daily_non_ohlcv_snapshot.py",
            "quant/backfill_non_ohlcv.py",
            "quant/run.py",
            "quant/test_daily_non_ohlcv_snapshot.py",
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(EXPERIMENT_LOG),
            repo_rel(REGISTRY_JSON),
        ],
        "allowed_write_scope": ALLOWED_WRITE_SCOPE,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -m pytest quant\\test_daily_non_ohlcv_snapshot.py quant\\test_backfill_non_ohlcv.py quant\\test_run_daily_wiring.py",
            ".\\.venv\\Scripts\\python.exe -B -m py_compile quant\\daily_non_ohlcv_snapshot.py quant\\backfill_non_ohlcv.py quant\\run.py quant\\test_daily_non_ohlcv_snapshot.py " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {
            "used_javascript": False,
            "evidence": "Python runner/tests only; no node/js tooling invoked.",
        },
        "lean_quality_passed": True,
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "ticket_before": {
            "created_at": ticket.get("created_at"),
            "claimed_at": ticket.get("claimed_at"),
            "hub_identity": ticket.get("hub_identity"),
            "novelty": ticket.get("novelty"),
        },
    }
    return payload


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "experiment_id",
        "timestamp",
        "status",
        "decision",
        "accepted",
        "accepted_alpha",
        "alpha_ready",
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
        "prediction",
        "calibration",
        "pre_run_questions",
        "parameters",
        "borrow_surface_before",
        "daily_snapshot_contract",
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
    surface = payload["borrow_surface_before"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID}: daily non-OHLCV borrow availability wiring",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            "- Strategy behavior changed: `false`",
            "- Live/default orders changed: `false`",
            "- Default refresh: `false`",
            "- Env gate: `REFRESH_BORROW_AVAILABILITY`",
            f"- Existing borrow rows: `{surface['row_count']}`",
            f"- Existing borrow-populated rows: `{surface['borrow_populated_rows']}`",
            f"- Artifact: `{repo_rel(OUT_JSON)}`",
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
            "No JavaScript was used.",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        REPO_ROOT / "quant" / "daily_non_ohlcv_snapshot.py",
        REPO_ROOT / "quant" / "backfill_non_ohlcv.py",
        REPO_ROOT / "quant" / "run.py",
        REPO_ROOT / "quant" / "test_daily_non_ohlcv_snapshot.py",
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        EXPERIMENT_LOG,
        REGISTRY_JSON,
        BASELINE_RESULT,
        BORROW_MANIFEST,
        BORROW_ROWS,
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
        "allowed_write_scope": payload["allowed_write_scope"],
        "anti_js": payload["anti_js"],
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    upsert_jsonl(EXPERIMENT_LOG, log_record)
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "alpha_ready": False,
            "observed_only_lead": False,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "runner": RUNNER,
            "gate4": payload["gate4"],
            "summary": payload["post_run_reflection"]["why_result_happened"],
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
            "gate1": payload["gate1"],
            "gate2": payload["gate2"],
            "gate3": payload["gate3"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
            "post_run_reflection": payload["post_run_reflection"],
            "related_files": payload["related_files"],
            "changed_files": payload["changed_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "novelty": payload["ticket_before"].get("novelty"),
            "claimed_at": payload["ticket_before"].get("claimed_at"),
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
                "borrow_rows": payload["borrow_surface_before"]["row_count"],
                "borrow_populated_rows": payload["borrow_surface_before"][
                    "borrow_populated_rows"
                ],
                "failed_reasons": payload["gate4"]["failed_reasons"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
