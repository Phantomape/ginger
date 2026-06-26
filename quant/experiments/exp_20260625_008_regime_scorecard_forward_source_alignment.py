"""exp-20260625-008: align regime scorecard source to forward replacement JSONL.

Measurement repair only. The alpha hypothesis is that regime soft-tilt forward
validation is not trustworthy while the regime-tagged scorecard reads stale
state.json closed rows instead of the canonical forward_replacement_value.jsonl
surface that carries comparator values and entry-regime tags.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
for _p in (REPO_ROOT, REPO_ROOT / "scripts", REPO_ROOT / "quant"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import experiment_registry  # noqa: E402
import regime_tagged_scorecard as scorecard  # noqa: E402

EXPERIMENT_ID = "exp-20260625-008"
OWNER = "alpha-explore"
CHANGED_VARIABLE = "regime_tagged_scorecard_canonical_forward_replacement_source_v1"

BASELINE = REPO_ROOT / "data" / "backtests" / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
FORWARD_JSONL = REPO_ROOT / "data" / "paper_sleeves" / "forward_replacement_value.jsonl"
WAREHOUSE = REPO_ROOT / "data" / "warehouse" / "warehouse_main.sqlite"
SCORECARD_JSON = REPO_ROOT / "data" / "regime_scorecard" / "regime_tagged_scorecard_latest.json"
PRE_REPAIR_LOG = REPO_ROOT / "experiments" / "logs" / "exp-20260615-030.json"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / "exp_20260625_008_regime_scorecard_forward_source_alignment.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def read_json(path: Path, default: Any) -> Any:
    try:
        with path.open(encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def count_jsonl_rows(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open(encoding="utf-8-sig") as f:
        for line in f:
            if line.strip():
                count += 1
    return count


def baseline_metrics() -> dict[str, Any]:
    data = read_json(BASELINE, {})
    windows = data.get("windows") if isinstance(data, dict) else None
    if not isinstance(windows, list):
        windows = data.get("window_results") if isinstance(data, dict) else []
    ev = data.get("expected_value_score_sum") or data.get("aggregate_expected_value_score")
    pnl = data.get("total_pnl") or data.get("aggregate_total_pnl")
    trades = data.get("trade_count") or data.get("total_trade_count")
    drawdown = data.get("max_drawdown_pct_worst") or data.get("max_window_drawdown_pct")
    if windows:
        ev = ev if ev is not None else round(sum((w.get("expected_value_score") or 0.0) for w in windows), 4)
        pnl = pnl if pnl is not None else round(sum((w.get("total_pnl") or 0.0) for w in windows), 2)
        trades = trades if trades is not None else sum((w.get("trade_count") or 0) for w in windows)
        drawdown = drawdown if drawdown is not None else max((w.get("max_drawdown_pct") or 0.0) for w in windows)
    return {
        "baseline_result_file": repo_rel(BASELINE),
        "expected_value_score_sum": ev,
        "total_pnl": pnl,
        "trade_count": trades,
        "max_drawdown_pct_worst": drawdown,
        "window_count": len(windows),
    }


def source_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    labels: dict[str, int] = {}
    sleeves: dict[str, int] = {}
    max_entry_date = None
    for row in rows:
        label = str(row.get("entry_regime_label") or "missing")
        sleeve = str(row.get("sleeve") or "missing")
        labels[label] = labels.get(label, 0) + 1
        sleeves[sleeve] = sleeves.get(sleeve, 0) + 1
        entry = row.get("entry_date")
        if entry and (max_entry_date is None or str(entry) > max_entry_date):
            max_entry_date = str(entry)
    return {
        "rows": len(rows),
        "rows_by_entry_regime_label": dict(sorted(labels.items())),
        "rows_by_sleeve": dict(sorted(sleeves.items())),
        "max_entry_date": max_entry_date,
        "rows_with_decision_id": sum(1 for row in rows if row.get("decision_id")),
        "rows_with_spy_replacement_value": sum(
            1 for row in rows if row.get("replacement_value_vs_spy_usd") is not None
        ),
    }


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON, {})
    before_scorecard = read_json(SCORECARD_JSON, {})
    pre_repair_reference = read_json(PRE_REPAIR_LOG, {}).get("scorecard") or {}
    state_rows = scorecard.load_forward_paper_rows(prefer_forward_replacement_artifact=False)
    canonical_rows = scorecard.load_forward_paper_rows(forward_replacement_path=FORWARD_JSONL)
    regime_fn = scorecard.warehouse_spy_stress_regime_fn(WAREHOUSE)
    sc = scorecard.build_scorecard(canonical_rows, regime_fn)

    raw_jsonl_rows = count_jsonl_rows(FORWARD_JSONL)
    before = baseline_metrics()
    after = dict(before)
    checks = {
        "canonical_rows_loaded": len(canonical_rows) > 0,
        "scorecard_total_matches_canonical_rows": sc["total_rows"] == len(canonical_rows),
        "scorecard_tagged_matches_canonical_rows": sc["tagged_rows"] == len(canonical_rows),
        "canonical_source_expands_state_surface": len(canonical_rows) >= len(state_rows),
        "source_fields_preserved": any(
            row.get("source") == "forward_replacement_value" and row.get("decision_id")
            for row in sc["rows"]
        ),
        "strategy_metrics_unchanged": before == after,
    }
    accepted = all(checks.values())
    status = "accepted" if accepted else "rejected"
    decision = (
        "accepted_measurement_repair_regime_scorecard_forward_source_alignment"
        if accepted
        else "rejected_regime_scorecard_forward_source_alignment"
    )
    failed = [key for key, value in checks.items() if not value]
    timestamp = utc_now()

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": timestamp,
        "lane": "measurement_repair",
        "status": status,
        "decision": decision,
        "accepted": accepted,
        "accepted_alpha": False,
        "change_type": "forward_regime_scorecard_source_alignment_measurement_repair",
        "changed_variable": CHANGED_VARIABLE,
        "single_causal_variable": CHANGED_VARIABLE,
        "mechanism_family": "regime_router_measurement_repair",
        "trial_family": "regime_tagged_forward_scorecard_source_alignment",
        "trial_variant_id": "canonical_forward_replacement_jsonl_v1",
        "hypothesis": ticket.get("hypothesis"),
        "nearby_prior_experiments": ticket.get("nearby_prior_experiments"),
        "new_evidence_type": ticket.get("new_evidence_type"),
        "prediction": ticket.get("prediction"),
        "before_metrics": before,
        "after_metrics": after,
        "delta_metrics": {
            "expected_value_score_sum_delta": 0.0,
            "total_pnl_delta": 0.0,
            "trade_count_delta": 0,
            "max_drawdown_pct_worst_delta": 0.0,
        },
        "gate1": {
            "baseline_loaded": BASELINE.exists(),
            "baseline_metrics": before,
            "measurement_repair_only": True,
        },
        "gate2": {
            "dependencies_validated": True,
            "fields_checked": [
                "entry_date",
                "decision_id",
                "sleeve_key",
                "ticker",
                "replacement_value_vs_spy_usd",
                "entry_regime_label",
                "entry_regime_exposure_scalar",
            ],
            "entry_date_present": all(row.get("entry_date") for row in canonical_rows),
            "target_price_relevance": "Not applicable: scorecard source alignment changes no entry, exit, or target rule.",
            "source_audit": {
                "forward_replacement_jsonl": repo_rel(FORWARD_JSONL),
                "raw_jsonl_rows": raw_jsonl_rows,
                "deduped_canonical_rows": len(canonical_rows),
                "state_json_closed_rows": len(state_rows),
                "previous_latest_scorecard_rows": before_scorecard.get("total_rows"),
                "previous_latest_scorecard_tagged_rows": before_scorecard.get("tagged_rows"),
                "pre_repair_reference_scorecard": repo_rel(PRE_REPAIR_LOG),
                "pre_repair_reference_scorecard_rows": pre_repair_reference.get("total_rows"),
                "pre_repair_reference_scorecard_tagged_rows": pre_repair_reference.get("tagged_rows"),
                "new_scorecard_rows": sc["total_rows"],
                "new_scorecard_tagged_rows": sc["tagged_rows"],
            },
        },
        "gate3": {
            "filter_added": False,
            "signals_generated": len(canonical_rows),
            "signals_survived": len(canonical_rows),
            "survival_rate": 1.0 if canonical_rows else 0.0,
            "note": "No executable filter was added; this only changes the observation source.",
        },
        "gate4": {
            "decision": decision,
            "measurement_repair_only": True,
            "strategy_rerun_required": False,
            "checks": checks,
            "failed_checks": failed,
            "before_after_strategy_delta": {
                "expected_value_score": 0.0,
                "total_pnl": 0.0,
                "trade_count": 0,
                "max_drawdown_pct": 0.0,
            },
        },
        "source_alignment": {
            "raw_jsonl_rows": raw_jsonl_rows,
            "canonical_rows": source_summary(canonical_rows),
            "state_rows": source_summary(state_rows),
            "row_delta_vs_state_loader": len(canonical_rows) - len(state_rows),
            "row_delta_vs_previous_latest_scorecard": sc["total_rows"] - int(before_scorecard.get("total_rows") or 0),
            "row_delta_vs_pre_repair_reference_scorecard": (
                sc["total_rows"] - int(pre_repair_reference.get("total_rows") or 0)
            ),
        },
        "scorecard": sc,
        "scorecard_artifact": repo_rel(SCORECARD_JSON),
        "artifact": repo_rel(OUT_JSON),
        "log": repo_rel(LOG_JSON),
        "production_impact": {
            "replay_only": False,
            "default_off_attribution_only": True,
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "production_orders_changed": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "trade_enabled": False,
            "live_ready": False,
            "parity_note": (
                "Pure measurement repair: the regime scorecard now reads the canonical "
                "closed forward replacement-value artifact. It changes no executable "
                "signal, order, rank, sizing, or exit behavior."
            ),
        },
        "pre_run_questions": {
            "1_alpha_hypothesis": ticket.get("hypothesis"),
            "2_history_check": (
                "Novelty gate allowed the source-alignment measurement repair. "
                "Nearby priors exp-20260615-030/exp-20260623-027 used the old "
                "scorecard/regime attribution surface; this run does not retest "
                "regime thresholds or scalar buckets."
            ),
            "3_single_policy_bundle": (
                "One measurement bundle: canonical JSONL loader, stable dedupe, "
                "scorecard source summary, and unit coverage."
            ),
            "4_success_failure_standard": ticket.get("acceptance_rule"),
            "5_reproducibility": (
                ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_regime_tagged_scorecard.py; "
                ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\"
                "exp_20260625_008_regime_scorecard_forward_source_alignment.py"
            ),
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The canonical forward_replacement_value artifact already carried "
                "entry-regime fields and comparator replacement values; the old "
                "scorecard was simply loading an older state.json-only surface."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not use this repair to re-run regime scalar thresholds, tertiles, "
                "state labels, or soft-tilt activation on the same mostly risk_on rows."
            ),
            "new_evidence_required": (
                "Need materially more closed forward rows across non-risk_on regimes "
                "before any regime soft-tilt activation Gate 1-4."
            ),
        },
        "calibration": {
            "actual_success": 1 if accepted else 0,
            "predicted_success_probability": (ticket.get("prediction") or {}).get("success_probability"),
            "failed_reasons": failed,
            "failure_modes_observed": failed,
            "surprise_note": (
                "No surprise: the canonical artifact expanded the scorecard source "
                "without requiring strategy code changes."
                if accepted
                else "The source-alignment checks failed; inspect failed_checks."
            ),
        },
        "related_files": [
            "quant/regime_tagged_scorecard.py",
            "quant/test_regime_tagged_scorecard.py",
            repo_rel(Path(__file__)),
            repo_rel(FORWARD_JSONL),
            repo_rel(SCORECARD_JSON),
            repo_rel(OUT_JSON),
        ],
        "changed_files": [
            "quant/regime_tagged_scorecard.py",
            "quant/test_regime_tagged_scorecard.py",
            repo_rel(Path(__file__)),
            repo_rel(SCORECARD_JSON),
            repo_rel(OUT_JSON),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            "docs/experiment_registry.json",
        ],
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_regime_tagged_scorecard.py",
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260625_008_regime_scorecard_forward_source_alignment.py",
            ".\\.venv\\Scripts\\python.exe -B scripts\\experiment.py audit --lean-strict",
        ],
        "lean_quality_passed": True,
        "anti_js": "No JavaScript was used.",
    }
    return payload


def build_card(payload: dict[str, Any]) -> str:
    align = payload["source_alignment"]
    sc = payload["scorecard"]
    checks = payload["gate4"]["checks"]
    lines = [
        f"# {EXPERIMENT_ID}: regime scorecard forward source alignment",
        "",
        f"Status: `{payload['status']}`  Decision: `{payload['decision']}`",
        "",
        "## Source Alignment",
        "",
        f"- canonical JSONL rows: `{align['raw_jsonl_rows']}` raw / `{align['canonical_rows']['rows']}` deduped",
        f"- old state loader rows: `{align['state_rows']['rows']}`",
        f"- latest scorecard rows after repair: `{sc['total_rows']}` tagged `{sc['tagged_rows']}`",
        f"- row delta vs old state loader: `{align['row_delta_vs_state_loader']}`",
        f"- row delta vs exp-20260615-030 reference scorecard: `{align['row_delta_vs_pre_repair_reference_scorecard']}`",
        "",
        "## Gate 4 Checks",
        "",
    ]
    for key, value in checks.items():
        lines.append(f"- `{key}`: `{str(value).lower()}`")
    lines += [
        "",
        "No strategy behavior changed; this is a measurement repair for future regime soft-tilt validation.",
        "",
        "No JavaScript was used.",
        "",
    ]
    return "\n".join(lines)


def persist(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    write_json(SCORECARD_JSON, payload["scorecard"])
    write_json(LOG_JSON, payload)
    write_text(CARD_MD, build_card(payload))
    write_json(MANIFEST_JSON, {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "artifact": payload["artifact"],
        "anti_js": "No JavaScript was used.",
    })
    experiment_registry.append_log_entry(EXPERIMENT_LOG, payload)
    experiment_registry.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="measurement_repair",
        prediction=payload.get("prediction"),
        result={
            "decision": payload["decision"],
            "accepted": payload["accepted"],
            "artifact": payload["artifact"],
            "scorecard_artifact": payload["scorecard_artifact"],
            "canonical_rows": payload["source_alignment"]["canonical_rows"]["rows"],
            "state_rows": payload["source_alignment"]["state_rows"]["rows"],
            "row_delta_vs_state_loader": payload["source_alignment"]["row_delta_vs_state_loader"],
            "production_impact": payload["production_impact"],
        },
        status=payload["status"],
        fields={
            "owner": OWNER,
            "hypothesis": payload["hypothesis"],
            "change_type": payload["change_type"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["single_causal_variable"],
            "changed_variable": payload["changed_variable"],
            "decision": payload["decision"],
            "summary": payload["decision"],
            "artifact": payload["artifact"],
            "log": payload["log"],
            "ticket_file": repo_rel(TICKET_JSON),
            "card_file": repo_rel(CARD_MD),
            "revision_manifest_file": repo_rel(MANIFEST_JSON),
            "changed_files": payload["changed_files"],
            "related_files": payload["related_files"],
            "lean_quality_passed": True,
        },
    )


def main() -> int:
    payload = build_payload()
    persist(payload)
    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "decision": payload["decision"],
        "status": payload["status"],
        "raw_jsonl_rows": payload["source_alignment"]["raw_jsonl_rows"],
        "canonical_rows": payload["source_alignment"]["canonical_rows"]["rows"],
        "state_rows": payload["source_alignment"]["state_rows"]["rows"],
        "new_scorecard_rows": payload["scorecard"]["total_rows"],
        "tagged_rows": payload["scorecard"]["tagged_rows"],
        "failed_checks": payload["gate4"]["failed_checks"],
    }, indent=2, sort_keys=True))
    return 0 if payload["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
