from __future__ import annotations

import hashlib
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260628-009"
LANE = "alpha_search"
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.experiment_registry import (  # noqa: E402
    persist_self_registered_result,
    save_experiment_log_entry,
)


RUNNER = "quant/experiments/exp_20260628_009_allocator_top1_current_concurrency_attribution.py"
RUNNER_COMMAND = (
    ".\\.venv\\Scripts\\python.exe -B "
    "quant\\experiments\\exp_20260628_009_allocator_top1_current_concurrency_attribution.py"
)
RECOMMENDATIONS_JSON = REPO_ROOT / "data/pilots/pilot_recommendations_2026-06-28.json"
BASELINE_JSON = (
    REPO_ROOT / "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
OUT_DIR = REPO_ROOT / "data/experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "allocator_top1_current_concurrency_attribution.json"
LOG_JSON = REPO_ROOT / "experiments/logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments/cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments/manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments/tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs/experiment_registry.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def safe(value: Any) -> Any:
    if isinstance(value, Path):
        return repo_rel(value)
    if isinstance(value, dict):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [safe(v) for v in value]
    if isinstance(value, tuple):
        return [safe(v) for v in value]
    return value


def numeric(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 6) if values else None


def median(values: list[float]) -> float | None:
    return round(float(statistics.median(values)), 6) if values else None


def recommendation_surface(payload: dict[str, Any]) -> dict[str, Any]:
    for row in payload.get("recommendations", []):
        if row.get("pilot") == "allocator_top1":
            return row
    raise RuntimeError("allocator_top1 recommendation surface not found")


def flatten_rows(surface: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bucket, label in (("actionable", "selected"), ("skipped", "skipped")):
        for row in surface.get(bucket, []) or []:
            unrealized = numeric(row.get("unrealized_pct"))
            notional = numeric(row.get("pilot_notional_usd")) or 0.0
            rows.append(
                {
                    "allocation_bucket": label,
                    "status": row.get("status"),
                    "ticker": row.get("ticker"),
                    "signal_date": row.get("signal_date"),
                    "entry_date": row.get("entry_date"),
                    "entry_price": row.get("entry_price"),
                    "last_price": row.get("last_price"),
                    "unrealized_pct": unrealized,
                    "current_mark_pnl_usd": (
                        round(unrealized * notional, 2) if unrealized is not None else None
                    ),
                    "stop_status": row.get("stop_status"),
                    "days_held": row.get("days_held"),
                    "days_remaining": row.get("days_remaining"),
                    "hold_days": row.get("hold_days"),
                    "pilot_notional_usd": row.get("pilot_notional_usd"),
                    "source": row.get("source"),
                    "source_priority_rank": row.get("source_priority_rank"),
                    "candidate_score": row.get("candidate_score"),
                    "target_price": row.get("target_price"),
                }
            )
    return rows


def mark_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    selected = [r for r in rows if r["allocation_bucket"] == "selected"]
    skipped = [r for r in rows if r["allocation_bucket"] == "skipped"]
    selected_marks = [
        float(r["unrealized_pct"]) for r in selected if r.get("unrealized_pct") is not None
    ]
    skipped_marks = [
        float(r["unrealized_pct"]) for r in skipped if r.get("unrealized_pct") is not None
    ]
    selected_mean = mean(selected_marks)
    skipped_mean = mean(skipped_marks)
    selected_median = median(selected_marks)
    skipped_median = median(skipped_marks)
    notional = numeric(selected[0].get("pilot_notional_usd")) if selected else None
    avg_delta = (
        round(selected_mean - skipped_mean, 6)
        if selected_mean is not None and skipped_mean is not None
        else None
    )
    median_delta = (
        round(selected_median - skipped_median, 6)
        if selected_median is not None and skipped_median is not None
        else None
    )
    return {
        "selected_count": len(selected),
        "skipped_count": len(skipped),
        "total_candidate_rows": len(rows),
        "selected_markable_count": len(selected_marks),
        "skipped_markable_count": len(skipped_marks),
        "rows_without_current_mark": [
            {
                "allocation_bucket": r["allocation_bucket"],
                "ticker": r["ticker"],
                "status": r["status"],
                "stop_status": r["stop_status"],
            }
            for r in rows
            if r.get("unrealized_pct") is None
        ],
        "selected_mean_unrealized_pct": selected_mean,
        "skipped_mean_unrealized_pct": skipped_mean,
        "selected_minus_skipped_mean_pct": avg_delta,
        "selected_median_unrealized_pct": selected_median,
        "skipped_median_unrealized_pct": skipped_median,
        "selected_minus_skipped_median_pct": median_delta,
        "selected_positive_count": sum(1 for v in selected_marks if v > 0),
        "selected_negative_count": sum(1 for v in selected_marks if v < 0),
        "skipped_positive_count": sum(1 for v in skipped_marks if v > 0),
        "skipped_negative_count": sum(1 for v in skipped_marks if v < 0),
        "selected_worst_unrealized_pct": min(selected_marks) if selected_marks else None,
        "skipped_worst_unrealized_pct": min(skipped_marks) if skipped_marks else None,
        "equal_notional_usd": notional,
        "selected_vs_skipped_average_current_mark_delta_usd": (
            round(avg_delta * notional, 2)
            if avg_delta is not None and notional is not None
            else None
        ),
        "selected_vs_skipped_median_current_mark_delta_usd": (
            round(median_delta * notional, 2)
            if median_delta is not None and notional is not None
            else None
        ),
    }


def field_coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    required = ["entry_date", "target_price"]
    coverage = {}
    for field in required:
        present = sum(1 for row in rows if row.get(field) is not None)
        coverage[field] = {
            "present": present,
            "total": len(rows),
            "coverage_rate": round(present / len(rows), 4) if rows else 0.0,
        }
    return coverage


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON)
    recommendations = read_json(RECOMMENDATIONS_JSON)
    baseline_exists = BASELINE_JSON.exists()
    baseline_payload = read_json(BASELINE_JSON) if baseline_exists else {}
    surface = recommendation_surface(recommendations)
    rows = flatten_rows(surface)
    metrics = mark_metrics(rows)
    coverage = field_coverage(rows)
    target_price_present = coverage["target_price"]["present"]
    entry_date_present = coverage["entry_date"]["present"]
    survival_rate = (
        round(metrics["selected_count"] / metrics["total_candidate_rows"], 4)
        if metrics["total_candidate_rows"]
        else 0.0
    )

    gate1 = {
        "passed": baseline_exists,
        "baseline_result_file": repo_rel(BASELINE_JSON),
        "baseline_schema_keys": sorted(baseline_payload.keys())[:20]
        if isinstance(baseline_payload, dict)
        else [],
        "note": "Baseline exists for protocol anchoring; this run does not alter or replay strategy policy.",
    }
    gate2 = {
        "passed": False,
        "entry_date_present": entry_date_present,
        "target_price_present": target_price_present,
        "field_coverage": coverage,
        "runtime_fields_checked": [
            "ticker",
            "status",
            "signal_date",
            "entry_date",
            "entry_price",
            "last_price",
            "unrealized_pct",
            "target_price",
        ],
        "why_partial": (
            "The recommendation surface supports current-mark attribution, but target_price "
            "is absent for all rows and one skipped candidate has no entry/current price."
        ),
    }
    gate3 = {
        "passed": survival_rate >= 0.05 and metrics["selected_count"] > 0,
        "signals_generated": metrics["total_candidate_rows"],
        "signals_survived": metrics["selected_count"],
        "survival_rate": survival_rate,
        "note": "This is an allocation-cap surface, so skipped rows are deferred by capacity rather than filtered out as invalid signals.",
    }
    gate4 = {
        "passed": False,
        "before_artifact": repo_rel(BASELINE_JSON),
        "after_artifact": repo_rel(OUT_JSON),
        "observed_only": True,
        "why_no_full_gate4": (
            "No strategy behavior changed and the rows are open/unsettled; current marks cannot be "
            "treated as a closed before/after replay."
        ),
        "current_mark_result": {
            "selected_minus_skipped_mean_pct": metrics["selected_minus_skipped_mean_pct"],
            "selected_vs_skipped_average_current_mark_delta_usd": metrics[
                "selected_vs_skipped_average_current_mark_delta_usd"
            ],
            "skipped_negative_count": metrics["skipped_negative_count"],
            "skipped_markable_count": metrics["skipped_markable_count"],
        },
    }

    decision = "observed_only_lead_not_allocation_ready"
    status = "observed_only"
    post_run_reflection = {
        "why_result_happened": (
            "The latest allocator_top1 marks favor the existing cap because DDOG is positive "
            "while five of six markable skipped rows are negative, but every row remains open "
            "and the surface lacks target_price, so the evidence is not allocation-ready."
        ),
        "forbidden_near_neighbor_retry": (
            "Do not rerun adjacent allocator selected-vs-skipped slices on the same 2026-06-28 "
            "open rows or only swap rank/score buckets."
        ),
        "new_evidence_required": (
            "Wait for materially more closed allocator_top1 replacement-value rows, or add a "
            "daily target_price/closed-outcome ledger that makes Gate 2 and Gate 4 executable."
        ),
    }
    calibration = {
        "pre_run_success_probability": ticket["prediction"]["success_probability"],
        "actual_success": False,
        "prediction_error": ticket["prediction"]["success_probability"],
        "surprise_level": "low",
        "realized_failure_modes": [
            "open_rows_not_settled",
            "target_price_missing_for_gate2",
            "small_sample",
            "skipped_rows_no_price",
        ],
        "surprise_note": (
            "The prior assigned low acceptance odds because the surface was open and incomplete; "
            "that was correct even though the current marks were directionally favorable."
        ),
    }

    payload = {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "generated_at": utc_now(),
        "owner": ticket.get("owner"),
        "lane": LANE,
        "status": status,
        "decision": decision,
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": True,
        "hypothesis": ticket["hypothesis"],
        "change_type": ticket["change_type"],
        "implementation_mode": "read_only_observed_forward_attribution",
        "mechanism_family": ticket.get("mechanism_family"),
        "trial_family": ticket.get("trial_family"),
        "trial_variant_id": ticket.get("trial_variant_id"),
        "single_causal_variable": ticket.get("single_causal_variable"),
        "changed_variable": ticket.get("changed_variable"),
        "causal_components": ticket.get("causal_components", []),
        "nearby_prior_experiments": ticket.get("nearby_prior_experiments", []),
        "multiple_testing_risk_bucket": ticket.get("multiple_testing_risk_bucket"),
        "new_evidence_type": ticket.get("new_evidence_type"),
        "novelty": ticket.get("novelty"),
        "prediction": ticket["prediction"],
        "parameters": {
            "pilot_key": "allocator_top1",
            "recommendation_file": repo_rel(RECOMMENDATIONS_JSON),
            "as_of": surface.get("as_of"),
            "max_concurrent": surface.get("max_concurrent"),
            "pilot_verdict": surface.get("pilot_verdict"),
            "new_entries_blocked": surface.get("new_entries_blocked"),
        },
        "pre_run_questions": {
            "alpha_hypothesis": ticket["hypothesis"],
            "prior_near_neighbors": ticket.get("novelty", {}).get("nearest", [])[:5],
            "single_policy_bundle": ticket.get("single_causal_variable"),
            "success_criteria": (
                "Only a closed-row Gate 4 acceptance can preserve behavior; current marks can "
                "produce an observed-only lead but not an accepted allocation change."
            ),
            "reproducibility": "Runner uses a fixed 2026-06-28 recommendation artifact and writes a deterministic JSON/card/log shard.",
        },
        "input_files": {
            "recommendations": repo_rel(RECOMMENDATIONS_JSON),
            "baseline": repo_rel(BASELINE_JSON),
            "ticket": repo_rel(TICKET_JSON),
        },
        "allocator_surface": {
            "as_of": surface.get("as_of"),
            "label": surface.get("label"),
            "sleeve": surface.get("sleeve"),
            "pilot_verdict": surface.get("pilot_verdict"),
            "pilot_verdict_note": surface.get("pilot_verdict_note"),
            "max_concurrent": surface.get("max_concurrent"),
            "new_entries_blocked": surface.get("new_entries_blocked"),
        },
        "rows": rows,
        "metrics": metrics,
        "gate1": gate1,
        "gate2": gate2,
        "gate3": gate3,
        "gate4": gate4,
        "production_impact": {
            "trade_enabled": False,
            "alters_orders": False,
            "live_orders_changed": False,
            "default_off_only": True,
            "notes": (
                "This runner reads daily pilot recommendation artifacts only; it does not alter "
                "ranking, sizing, exits, live orders, or paper sleeve state."
            ),
        },
        "decision_basis": {
            "directional_supports_current_cap": (
                metrics["selected_minus_skipped_mean_pct"] is not None
                and metrics["selected_minus_skipped_mean_pct"] > 0
            ),
            "not_allocation_ready_reasons": [
                "all rows are open/unsettled",
                "target_price absent on every row",
                "only one selected row",
                "one skipped candidate has no current mark",
            ],
        },
        "rejection_reason": (
            "Not rejected as a lead, but rejected for acceptance: current open marks are not a "
            "settled Gate 4 replay and Gate 2 target_price coverage is zero."
        ),
        "next_retry_requires": post_run_reflection["new_evidence_required"],
        "post_run_reflection": post_run_reflection,
        "calibration": calibration,
        "related_files": [
            repo_rel(RECOMMENDATIONS_JSON),
            repo_rel(BASELINE_JSON),
            repo_rel(TICKET_JSON),
        ],
        "changed_files": [
            RUNNER,
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            repo_rel(REGISTRY_JSON),
        ],
        "reproduction_commands": [
            RUNNER_COMMAND,
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "anti_js": {
            "do_not_claim": "Do not claim allocator_top1 capacity retunes from this current-mark-only surface.",
            "reopen_condition": post_run_reflection["new_evidence_required"],
        },
    }
    return payload


def compact_log(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "lane": payload["lane"],
        "status": payload["status"],
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "changed_variable": payload["changed_variable"],
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "prediction": payload["prediction"],
        "metrics": payload["metrics"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "decision_basis": payload["decision_basis"],
        "calibration": payload["calibration"],
        "post_run_reflection": payload["post_run_reflection"],
        "rejection_reason": payload["rejection_reason"],
        "next_retry_requires": payload["next_retry_requires"],
        "artifact": repo_rel(OUT_JSON),
        "runner": RUNNER,
        "reproduction_commands": payload["reproduction_commands"],
        "updated_at": payload["generated_at"],
    }


def build_card(payload: dict[str, Any]) -> str:
    metrics = payload["metrics"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} allocator_top1 current concurrency attribution",
            "",
            f"- Status: `{payload['status']}`",
            f"- Decision: `{payload['decision']}`",
            f"- Hypothesis: {payload['hypothesis']}",
            "- Result: current marks directionally support the existing top-1 cap, but the "
            "surface is open/unsettled and not Gate-4-ready.",
            f"- Selected vs skipped mean: {metrics['selected_mean_unrealized_pct']} vs "
            f"{metrics['skipped_mean_unrealized_pct']} "
            f"({metrics['selected_minus_skipped_mean_pct']} delta).",
            f"- Equal-notional current mark delta: "
            f"{metrics['selected_vs_skipped_average_current_mark_delta_usd']} USD.",
            f"- Gate 2: target_price present on "
            f"{payload['gate2']['target_price_present']}/{metrics['total_candidate_rows']} rows.",
            "",
            "## Next Evidence",
            "",
            payload["next_retry_requires"],
            "",
            "## Reproduce",
            "",
            "```powershell",
            RUNNER_COMMAND,
            "```",
            "",
        ]
    )


def build_manifest(payload: dict[str, Any], log_row: dict[str, Any]) -> dict[str, Any]:
    files = [
        REPO_ROOT / RUNNER,
        OUT_JSON,
        LOG_JSON,
        CARD_MD,
        MANIFEST_JSON,
        TICKET_JSON,
        REGISTRY_JSON,
    ]
    return {
        "schema_version": 1,
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER,
        "command": RUNNER_COMMAND,
        "files": {
            repo_rel(path): {"exists": path.exists(), "sha256": sha256_file(path)}
            for path in files
        },
        "log_row_sha256": hashlib.sha256(
            json.dumps(safe(log_row), sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "updated_at": utc_now(),
    }


def persist(payload: dict[str, Any]) -> None:
    log_row = compact_log(payload)
    write_json(OUT_JSON, payload)
    save_experiment_log_entry(log_row, allow_duplicate=True)
    write_text(CARD_MD, build_card(payload))
    result = {
        "accepted": False,
        "accepted_alpha": False,
        "observed_only_lead": payload["observed_only_lead"],
        "gate4_passed": payload["gate4"]["passed"],
        "decision": payload["decision"],
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "metrics": payload["metrics"],
        "calibration": payload["calibration"],
        "summary": payload["post_run_reflection"]["why_result_happened"],
    }
    fields = {
        key: payload[key]
        for key in [
            "owner",
            "hypothesis",
            "change_type",
            "implementation_mode",
            "mechanism_family",
            "trial_family",
            "trial_variant_id",
            "single_causal_variable",
            "changed_variable",
            "causal_components",
            "nearby_prior_experiments",
            "multiple_testing_risk_bucket",
            "new_evidence_type",
            "parameters",
            "pre_run_questions",
            "gate1",
            "gate2",
            "gate3",
            "gate4",
            "production_impact",
            "post_run_reflection",
            "rejection_reason",
            "next_retry_requires",
            "related_files",
            "changed_files",
            "reproduction_commands",
            "anti_js",
        ]
        if key in payload
    }
    fields.update(
        {
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
        }
    )
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result=result,
        status=payload["status"],
        fields=fields,
    )
    write_json(MANIFEST_JSON, build_manifest(payload, log_row))


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps(safe(compact_log(payload)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
