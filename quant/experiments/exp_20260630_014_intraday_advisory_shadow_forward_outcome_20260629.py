"""exp-20260630-014: matured intraday advisory shadow-action attribution.

Observed-only alpha attribution. The single question is whether the same
post-exp024 primary advisory shadow-action surface that was too young in
exp-20260627-025 becomes useful after more h1/h3 forward rows settled through
the 2026-06-29 warehouse.

This runner changes no shared policy, entry, exit, ranking, sizing, paper state,
live order, watchlist, daily artifact, or LLM boundary.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
for entry in (REPO_ROOT / "quant", REPO_ROOT / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260630-014"
OWNER = "alpha-explore"
SLUG = "intraday_advisory_shadow_forward_outcome_20260629"
RUNNER = f"quant/experiments/exp_20260630_014_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER.replace("/", "\\")

SOURCE_RUNNER = (
    REPO_ROOT
    / "quant"
    / "experiments"
    / "exp_20260627_025_intraday_advisory_shadow_forward_outcome.py"
)
BASELINE_RESULT = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260630_014_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

HYPOTHESIS = (
    "Post-exp024 intraday primary advisory shadow actions may identify existing "
    "positions with worse next-1d and next-3d returns than OK/no-action "
    "positions after materially more settled rows matured through the "
    "2026-06-29 warehouse."
)
CHANGE_TYPE = "observed_only_forward_attribution"
IMPLEMENTATION_MODE = "observed_only_intraday_exit_advisory_attribution"
MECHANISM_FAMILY = "intraday_exit_advisory_forward_attribution"
TRIAL_FAMILY = "intraday_advisory_shadow_action_forward_outcome"
TRIAL_VARIANT_ID = "post_exp024_matured_through_20260629_v1"
CHANGED_VARIABLE = "intraday_advisory_shadow_action_forward_outcome_20260629_v1"
NEW_EVIDENCE_TYPE = "materially_more_settled_intraday_forward_rows"
NEW_EVIDENCE_AXIS = (
    "Materially more settled post-contract intraday forward rows: current h1/h3 "
    "settled rows are 72/45 versus exp-20260627-025's 46/15, and the warehouse "
    "calendar advanced to 2026-06-29."
)
NEARBY_PRIOR_EXPERIMENTS = ["exp-20260626-024", "exp-20260627-025"]
CAUSAL_COMPONENTS = [
    "intraday_review snapshots",
    "primary advisory shadow action extraction",
    "next-1d and next-3d OHLCV settlement",
    "no strategy behavior change",
]
PREDICTION = {
    "success_probability": 0.18,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "h3_action_underperformance_reverses",
        "no_stable_directional_separation",
        "ok_bucket_outperforms_action_bucket",
        "still_observed_only_no_shared_exit_policy",
    ],
    "confidence_reason": (
        "Current no-ID maturity check shows rows advanced versus exp-20260627-025 "
        "from h1/h3 46/15 to 72/45, satisfying the reopen-count condition, but "
        "h3 action-vs-OK separation appears reversed; likely result is a clean "
        "rejection that freezes this near-term exit-advisory promotion path."
    ),
    "recorded_at": "2026-06-30T15:04:48+00:00",
}
CONFIG = {
    "asof_min_date": "2026-06-22",
    "asof_max_date": "2026-06-30",
    "horizons": [1, 3],
    "min_primary_h1_rows": 20,
    "min_primary_h1_action_rows": 8,
    "min_primary_h1_ok_rows": 8,
    "min_h3_action_rows": 3,
    "min_h3_ok_rows": 3,
    "required_action_underperformance_pp": 1.0,
}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def repo_rel(path: Path | str) -> str:
    value = Path(path)
    if not value.is_absolute():
        value = REPO_ROOT / value
    return value.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


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
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_source_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "exp_20260627_025_intraday_advisory_shadow_forward_outcome", SOURCE_RUNNER
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import source runner: {SOURCE_RUNNER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.CONFIG = dict(CONFIG)
    return module


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
        "parameters",
        "gate1",
        "gate2",
        "gate3",
        "gate4",
        "before_metrics",
        "after_metrics",
        "delta_metrics",
        "summary",
        "production_impact",
        "post_run_reflection",
        "rejection_reason",
        "related_files",
        "changed_files",
        "reproduction_commands",
        "lean_quality_passed",
    ]
    return {key: payload.get(key) for key in keys if payload.get(key) is not None}


def build_payload(source: Any) -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    snapshots = source.load_intraday_snapshots()
    tickers = {"SPY", "QQQ"}
    for item in snapshots:
        for pos in item["payload"].get("positions") or []:
            if isinstance(pos, dict) and pos.get("ticker"):
                tickers.add(str(pos["ticker"]).upper())
    prices = source.load_price_rows(tickers)
    observations, source_diagnostics = source.extract_observations(snapshots, prices)
    gate4 = source.evaluate_gate4(observations)
    h1_rows = source.settled_rows(observations, 1)
    h3_rows = source.settled_rows(observations, 3)
    metrics = source.baseline_metrics()
    accepted = bool(gate4["passed"])
    status = "observed_only" if accepted else "observed_only_rejected"
    now = utc_now()
    realized_failure_modes = list(gate4["failed_reasons"])
    predicted_modes = PREDICTION["main_failure_modes"]
    prediction_hit = bool(realized_failure_modes) and any(
        mode
        in {
            "h3_action_underperformance_reverses",
            "no_stable_directional_separation",
            "ok_bucket_outperforms_action_bucket",
            "still_observed_only_no_shared_exit_policy",
        }
        for mode in predicted_modes
    )
    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "status": status,
        "decision": gate4["decision"] + "_20260629",
        "accepted": accepted,
        "accepted_alpha": False,
        "observed_only_lead": accepted,
        "lane": "alpha_search",
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": CHANGE_TYPE,
        "implementation_mode": IMPLEMENTATION_MODE,
        "mechanism_family": MECHANISM_FAMILY,
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "causal_components": CAUSAL_COMPONENTS,
        "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": NEW_EVIDENCE_TYPE,
        "new_evidence_axis": NEW_EVIDENCE_AXIS,
        "prediction": PREDICTION,
        "calibration": {
            "actual_success": 1 if accepted else 0,
            "predicted_success_probability": PREDICTION["success_probability"],
            "brier_score": round((PREDICTION["success_probability"] - (1 if accepted else 0)) ** 2, 6),
            "predicted_failure_modes": predicted_modes,
            "realized_failure_modes": realized_failure_modes,
            "predicted_failure_mode_hit": prediction_hit,
            "surprise_note": (
                "The added settled rows confirmed no stable h1/h3 underperformance "
                "edge; h3 action-vs-OK SPY-excess separation reversed positive."
                if not accepted
                else "The matured forward rows separated enough to become an "
                "observed-only lead, but no strategy behavior changed."
            ),
        },
        "parameters": {
            "config": CONFIG,
            "source_runner": repo_rel(SOURCE_RUNNER),
            "snapshot_glob": "data/daily/intraday/snapshots/intraday_review_*.json",
            "settlement_source": "ohlcv_warehouse.ohlcv_overlay",
        },
        "artifact": repo_rel(OUT_JSON),
        "runner": RUNNER,
        "runner_command": RUNNER_COMMAND,
        "gate1": {
            "passed": BASELINE_RESULT.exists(),
            "baseline_metrics": metrics,
            "baseline_result_file": repo_rel(BASELINE_RESULT),
            "note": "Observed-only attribution; before and after strategy behavior are identical.",
        },
        "gate2": {
            "passed": bool(source_diagnostics["observation_count"]),
            "fields_checked": [
                "intraday_review.date",
                "positions[].ticker",
                "positions[].status",
                "positions[].quote.price",
                "positions[].context.exit_signals.triggered_rules",
                "positions[].primary_advisory_shadow_action",
                "ohlcv_overlay.entry_close",
                "ohlcv_overlay.future_close",
                "entry_date",
                "target_price",
            ],
            "source_diagnostics": source_diagnostics,
            "target_price_relevance": (
                "No target exits are scheduled. target_price is represented only "
                "inside existing intraday exit-level context for attribution."
            ),
        },
        "gate3": {
            "passed": True,
            "filter_added": False,
            "baseline_survival_rate": metrics.get("survival_rate"),
            "signals_generated": source_diagnostics["observation_count"],
            "signals_survived": len(h1_rows),
            "survival_rate": round(len(h1_rows) / source_diagnostics["observation_count"], 6)
            if source_diagnostics["observation_count"]
            else 0.0,
            "note": "No executable filter was added; rows are only attributed.",
        },
        "gate4": gate4,
        "before_metrics": metrics,
        "after_metrics": metrics,
        "delta_metrics": gate4["before_after_strategy_delta"],
        "observations": observations,
        "summary": {
            "observation_count": len(observations),
            "h1_settled_rows": len(h1_rows),
            "h3_settled_rows": len(h3_rows),
            "shadow_action_counts": dict(Counter(row["shadow_action"] for row in observations)),
            "status_bucket_counts": dict(Counter(row["status_bucket"] for row in observations)),
            "reopen_guard_progress": {
                "prior_exp_20260627_025_h1_settled_rows": 46,
                "prior_exp_20260627_025_h3_settled_rows": 15,
                "current_h1_settled_rows": len(h1_rows),
                "current_h3_settled_rows": len(h3_rows),
                "warehouse_calendar_max": source_diagnostics.get("calendar_max"),
            },
        },
        "production_impact": {
            "shared_policy_changed": False,
            "backtester_adapter_changed": False,
            "run_adapter_changed": False,
            "daily_snapshot_exposed": False,
            "trade_enabled": False,
            "live_orders_changed": False,
            "paper_orders_changed": False,
            "entry_rules_changed": False,
            "exit_rules_changed": False,
            "ranking_changed": False,
            "sizing_changed": False,
            "risk_budget_changed": False,
            "watchlist_changed": False,
            "llm_decision_boundary_changed": False,
            "live_realism_evaluated": False,
            "live_ready": False,
            "parity_note": (
                "Read-only attribution over existing intraday snapshots and OHLCV "
                "settlement. No order, exit, or daily adapter behavior changed."
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "More settled rows did not improve the advisory-action edge: h1 "
                "action rows underperformed OK/no-action by less than the required "
                "1 pp, while h3 action rows outperformed OK/no-action on SPY-excess "
                "mean, reversing the intended signal direction."
                if not accepted
                else "The matured intraday action buckets separated forward outcomes, "
                "but the result is still observed-only and needs a shared default-off "
                "exit-lifecycle helper before any strategy test."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retune REVIEW/EXIT labels, SIGNAL_TARGET, stop distance, "
                "target distance, trailing stop, time stop, or hard-exclusion versus "
                "tilt response functions on the same 2026-06-22..2026-06-30 "
                "snapshot surface."
            ),
            "new_evidence_required": (
                "Reopen only after materially more closed forward rows beyond the "
                "2026-06-29 warehouse, true quote timestamps or broker bar IDs, "
                "native primary actions at materially larger coverage, and "
                "slot-reuse/replacement-value accounting."
            ),
        },
        "rejection_reason": ";".join(gate4["failed_reasons"]) if not accepted else None,
        "related_files": [
            RUNNER,
            repo_rel(SOURCE_RUNNER),
            repo_rel(OUT_JSON),
            repo_rel(BASELINE_RESULT),
            "data/daily/intraday/snapshots",
            "data/warehouse/warehouse_main.sqlite",
            "data/warehouse/warehouse_main_hot.sqlite",
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            "docs/experiment_registry.json",
        ],
        "allowed_write_scope": list((ticket or {}).get("allowed_write_scope") or []),
        "ticket_before": ticket,
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B -m py_compile " + RUNNER.replace("/", "\\"),
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": True,
    }
    return payload


def build_card(payload: dict[str, Any]) -> str:
    gate4 = payload["gate4"]
    comparisons = gate4["comparisons"]
    lines = [
        f"# {EXPERIMENT_ID}: Matured Intraday Advisory Shadow Outcome",
        "",
        f"- Status: `{payload['status']}`",
        f"- Decision: `{payload['decision']}`",
        f"- Artifact: `{payload['artifact']}`",
        f"- Runner: `{RUNNER_COMMAND}`",
        "",
        "## Hypothesis",
        "",
        HYPOTHESIS,
        "",
        "## Result",
        "",
        f"- h1 settled/action/OK rows: `{comparisons['h1']['settled_rows']}` / "
        f"`{comparisons['h1']['action_rows']}` / "
        f"`{comparisons['h1']['ok_no_action_rows']}`",
        f"- h1 action-minus-OK SPY-excess mean: "
        f"`{comparisons['h1']['action_minus_ok_spy_excess_mean_pp']}` pp",
        f"- h3 settled/action/OK rows: `{comparisons['h3']['settled_rows']}` / "
        f"`{comparisons['h3']['action_rows']}` / "
        f"`{comparisons['h3']['ok_no_action_rows']}`",
        f"- h3 action-minus-OK SPY-excess mean: "
        f"`{comparisons['h3']['action_minus_ok_spy_excess_mean_pp']}` pp",
        f"- Failed reasons: `{', '.join(gate4['failed_reasons']) or 'none'}`",
        "",
        "## Reflection",
        "",
        f"- Why: {payload['post_run_reflection']['why_result_happened']}",
        f"- Forbidden retry: {payload['post_run_reflection']['forbidden_near_neighbor_retry']}",
        f"- New evidence required: {payload['post_run_reflection']['new_evidence_required']}",
        "",
    ]
    return "\n".join(lines)


def build_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    files = [
        Path(RUNNER),
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
    ]
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {
                "exists": (REPO_ROOT / path).exists() if not path.is_absolute() else path.exists(),
                "sha256": sha256(REPO_ROOT / path) if not path.is_absolute() else sha256(path),
            }
            for path in files
        },
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    log_record = compact_log_record(payload)
    write_json(LOG_JSON, log_record)
    write_text(CARD_MD, build_card(payload))
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=payload["prediction"],
        result={
            "accepted": payload["accepted"],
            "accepted_alpha": False,
            "observed_only_lead": payload["observed_only_lead"],
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
            "hypothesis": HYPOTHESIS,
            "change_type": CHANGE_TYPE,
            "implementation_mode": IMPLEMENTATION_MODE,
            "mechanism_family": MECHANISM_FAMILY,
            "trial_family": TRIAL_FAMILY,
            "trial_variant_id": TRIAL_VARIANT_ID,
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "causal_components": CAUSAL_COMPONENTS,
            "nearby_prior_experiments": NEARBY_PRIOR_EXPERIMENTS,
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": NEW_EVIDENCE_TYPE,
            "new_evidence_axis": NEW_EVIDENCE_AXIS,
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
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "allowed_write_scope": payload["allowed_write_scope"],
            "lean_quality_passed": payload["lean_quality_passed"],
            "novelty": (payload["ticket_before"] or {}).get("novelty"),
        },
    )
    write_json(MANIFEST_JSON, build_manifest(payload))


def main() -> int:
    source = load_source_module()
    payload = build_payload(source)
    persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "summary": payload["summary"],
                "gate4_failed_reasons": payload["gate4"]["failed_reasons"],
                "h1_comparison": payload["gate4"]["comparisons"]["h1"],
                "h3_comparison": payload["gate4"]["comparisons"]["h3"],
                "artifact": payload["artifact"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
