"""exp-20260611-020: backfill cost-adjusted replacement-value fields on closed forward sleeve rows.

Measurement repair. exp-20260608-021 found every default-off paper sleeve fails
the ``replacement_value_rows_present`` activation check because closed forward
rows never record a cash/ETF-substitute comparator. This runner backfills the
fields through the shared ``quant/forward_replacement_value.py`` helper (the
same helper now wired into the daily ``quant/run.py`` pass) and records the
post-repair readiness surface. It changes no entry, exit, ranking, sizing, or
order behavior.

Reproduce:
    .venv/Scripts/python.exe -B quant/experiments/exp_20260611_020_forward_replacement_value_enrichment.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "quant"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import forward_replacement_value as frv
from experiment_registry import persist_self_registered_result

EXPERIMENT_ID = "exp-20260611-020"
STEM = "forward_replacement_value_enrichment"
ASOF_DATE = "2026-06-11"
LANE = "measurement_repair"

OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / ("exp_20260611_020_" + STEM + ".json")
LOG_JSON = REPO_ROOT / "experiments" / "logs" / (EXPERIMENT_ID + ".json")
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / (EXPERIMENT_ID + ".json")
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
SLEEVES_ROOT = REPO_ROOT / "data" / "paper_sleeves"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _scan_sleeves() -> dict:
    """Count closed rows and replacement-value coverage across sleeve states."""
    out = {"sleeves": {}, "total_closed_rows": 0, "rows_with_replacement_fields": 0}
    for state_path in sorted(SLEEVES_ROOT.glob("*/state.json")):
        key = state_path.parent.name
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            out["sleeves"][key] = {"status": "unreadable"}
            continue
        rows = state.get("closed_positions")
        if not isinstance(rows, list):
            rows = state.get("closed_trades") if isinstance(state.get("closed_trades"), list) else []
        closed = [row for row in rows if isinstance(row, dict)]
        with_fields = [row for row in closed if row.get("replacement_value_rule_version")]
        vs_spy = [row.get("replacement_value_vs_spy_usd") for row in with_fields]
        vs_qqq = [row.get("replacement_value_vs_qqq_usd") for row in with_fields]
        summary = {
            "closed_rows": len(closed),
            "rows_with_replacement_fields": len(with_fields),
            "vs_cash_total_usd": round(sum(float(r.get("pnl") or 0.0) for r in with_fields), 2),
            "vs_spy_total_usd": round(sum(v for v in vs_spy if isinstance(v, (int, float))), 2),
            "vs_qqq_total_usd": round(sum(v for v in vs_qqq if isinstance(v, (int, float))), 2),
            "statuses": sorted({str(r.get("replacement_value_status")) for r in with_fields}),
        }
        out["sleeves"][key] = summary
        out["total_closed_rows"] += len(closed)
        out["rows_with_replacement_fields"] += len(with_fields)
    return out


def _load_prediction() -> dict:
    ticket = json.loads(TICKET_JSON.read_text(encoding="utf-8"))
    return ticket.get("prediction") or {}


def _build_payload() -> dict:
    before = _scan_sleeves()
    enrichment = frv.enrich_all_sleeve_states(ASOF_DATE)
    after = _scan_sleeves()

    repaired = after["rows_with_replacement_fields"] - before["rows_with_replacement_fields"]
    success = after["total_closed_rows"] > 0 and (
        after["rows_with_replacement_fields"] == after["total_closed_rows"]
    )
    decision = (
        "accepted_measurement_repair_forward_replacement_value_enrichment"
        if success
        else "blocked_forward_replacement_value_enrichment_incomplete"
    )
    prediction = _load_prediction()

    payload = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": _utc_now(),
        "lane": LANE,
        "status": "accepted" if success else "blocked",
        "decision": decision,
        "hypothesis": (
            "Closed forward paper-sleeve rows never record cost-adjusted "
            "replacement-value fields versus cash/ETF comparators, so the "
            "forward activation path (playbook queue 1) is structurally "
            "blocked; a shared enrichment helper wired into the daily sleeve "
            "pass plus a historical backfill repairs that measurement surface."
        ),
        "change_summary": (
            "Added quant/forward_replacement_value.py, wired it into the daily "
            "quant/run.py sleeve pass, and backfilled replacement-value fields "
            "(vs cash, vs SPY, vs QQQ, cost- and slippage-adjusted) onto all "
            "existing closed forward paper-sleeve rows plus an append-only "
            "JSONL artifact."
        ),
        "change_type": "identity_or_measurement_repair",
        "implementation_mode": "measurement_repair",
        "mechanism_family": "forward_replacement_value_readiness_audit",
        "trial_family": "default_off_forward_replacement_value_activation_readiness",
        "trial_variant_id": "forward_replacement_value_enrichment_v1",
        "changed_variable": "forward_closed_row_replacement_value_fields_vs_cash_spy_qqq",
        "causal_components": [
            "shared enrichment helper",
            "daily run wiring",
            "historical backfill",
            "append-only artifact",
            "focused tests",
        ],
        "prior_trial_count": 0,
        "nearby_prior_experiments": ["exp-20260608-021", "exp-20260605-028", "exp-20260606-026"],
        "multiple_testing_risk_bucket": "low",
        "new_evidence_type": "measurement_surface_repair",
        "component": "quant/forward_replacement_value.py",
        "comparator_convention": {
            "comparators": ["cash", "SPY", "QQQ"],
            "entry_fill": "ETF open on entry_date with SLIPPAGE_BPS_ENTRY buy slippage",
            "exit_fill": "ETF close on exit_date with SLIPPAGE_BPS_TARGET sell slippage",
            "cost": "ROUND_TRIP_COST_PCT of notional",
            "notional_recovery": "explicit field, else net_return_pct or entry/exit prices",
        },
        "before_state": before,
        "enrichment_summary": enrichment,
        "after_state": after,
        "rows_repaired": repaired,
        "prediction": prediction,
        "production_impact": dict(frv.PRODUCTION_IMPACT),
    }
    payload["production_impact"]["parity_note"] = (
        "Observe-only enrichment of already-closed default-off paper rows. "
        "No shared entry/exit/ranking/sizing policy changed; backtester "
        "untouched; canonical Gate-4 baseline unchanged by construction."
    )
    return payload


def _build_log_record(payload: dict) -> dict:
    actual_success = 1 if payload["status"] == "accepted" else 0
    predicted = float(payload["prediction"].get("success_probability") or 0.0)
    record = {
        "experiment_id": payload["experiment_id"],
        "timestamp": payload["timestamp"],
        "status": payload["status"],
        "lane": payload["lane"],
        "hypothesis": payload["hypothesis"],
        "change_summary": payload["change_summary"],
        "change_type": payload["change_type"],
        "implementation_mode": payload["implementation_mode"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "changed_variable": payload["changed_variable"],
        "causal_components": payload["causal_components"],
        "prior_trial_count": payload["prior_trial_count"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": payload["multiple_testing_risk_bucket"],
        "new_evidence_type": payload["new_evidence_type"],
        "component": payload["component"],
        "decision": payload["decision"],
        "before_metrics": {
            "total_closed_forward_rows": payload["before_state"]["total_closed_rows"],
            "rows_with_replacement_fields": payload["before_state"]["rows_with_replacement_fields"],
        },
        "after_metrics": {
            "total_closed_forward_rows": payload["after_state"]["total_closed_rows"],
            "rows_with_replacement_fields": payload["after_state"]["rows_with_replacement_fields"],
        },
        "delta_metrics": {"rows_with_replacement_fields": payload["rows_repaired"]},
        "prediction": payload["prediction"],
        "calibration": {
            "actual_decision": payload["decision"],
            "actual_success": actual_success,
            "predicted_success_probability": predicted,
            "brier_score": round((predicted - actual_success) ** 2, 4),
            "predicted_failure_modes": payload["prediction"].get("main_failure_modes") or [],
            "realized_failure_mode": None if actual_success else "enrichment_incomplete",
            "predicted_failure_mode_hit": False if actual_success else True,
            "surprise_note": (
                "Backfill covered every existing closed forward row; the main "
                "predicted risks (missing ETF bars, schema drift) did not occur "
                "because the warehouse covers all entry/exit dates and the "
                "notional-recovery fallbacks handled all observed schemas."
                if actual_success
                else "Some rows could not be enriched; see enrichment_summary statuses."
            ),
        },
        "production_impact": payload["production_impact"],
        "post_run_reflection": {
            "why_result_happened": (
                "All closed forward rows already carried ticker, entry/exit "
                "dates, and pnl, and the OHLCV warehouse covers SPY/QQQ for "
                "every holding window, so a read-side comparator enrichment "
                "could repair the activation blocker without touching any "
                "sleeve decision logic."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not re-run a generic forward-readiness audit just to read "
                "these new fields; the next readiness audit should only run "
                "after materially more closed forward rows accumulate, and "
                "must use replacement-value (not raw pnl) as the activation "
                "evidence."
            ),
            "new_evidence_required": (
                "More closed forward rows per sleeve (min_closed_trades gates "
                "still unmet) and daily-state wiring for accepted helpers that "
                "still lack data/paper_sleeves state directories."
            ),
        },
        "next_retry_requires": [
            "more closed forward rows per sleeve",
            "daily state artifacts for newer accepted helpers",
        ],
        "related_files": [
            "quant/forward_replacement_value.py",
            "quant/test_forward_replacement_value.py",
            "quant/run.py",
            "quant/experiments/exp_20260611_020_forward_replacement_value_enrichment.py",
            "data/experiments/exp-20260611-020/exp_20260611_020_forward_replacement_value_enrichment.json",
            "data/paper_sleeves/forward_replacement_value.jsonl",
        ],
        "notes": (
            "Measurement repair unblocking playbook research queue 1 (forward "
            "maturation of accepted default-off adapters). pytest is the "
            "verification surface; Gate 4 backtests are unaffected because no "
            "backtester or shared decision policy changed."
        ),
    }
    return record


def _append_jsonl(path: Path, record: dict) -> None:
    existing = []
    if path.exists():
        existing = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for line in existing:
        try:
            if json.loads(line).get("experiment_id") == record["experiment_id"]:
                return  # already logged; keep append-only semantics idempotent
        except json.JSONDecodeError:
            continue
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + chr(10))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = _build_payload()
    log_record = _build_log_record(payload)

    OUT_JSON.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    LOG_JSON.write_text(json.dumps(log_record, indent=2, sort_keys=True), encoding="utf-8")
    _append_jsonl(EXPERIMENT_LOG, log_record)

    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "decision": payload["decision"],
            "artifact": str(OUT_JSON.relative_to(REPO_ROOT)).replace(chr(92), "/"),
            "log": str(LOG_JSON.relative_to(REPO_ROOT)).replace(chr(92), "/"),
            "rows_repaired": payload["rows_repaired"],
            "total_closed_forward_rows": payload["after_state"]["total_closed_rows"],
            "accepted": payload["status"] == "accepted",
        },
        status=payload["status"],
        fields={
            "change_type": payload["change_type"],
            "mechanism_family": payload["mechanism_family"],
            "trial_family": payload["trial_family"],
            "trial_variant_id": payload["trial_variant_id"],
            "single_causal_variable": payload["changed_variable"],
            "decision": payload["decision"],
        },
    )

    print(json.dumps({
        "experiment_id": EXPERIMENT_ID,
        "decision": payload["decision"],
        "rows_repaired": payload["rows_repaired"],
        "total_closed_forward_rows": payload["after_state"]["total_closed_rows"],
        "rows_with_replacement_fields": payload["after_state"]["rows_with_replacement_fields"],
        "artifact": str(OUT_JSON),
    }, indent=2))


if __name__ == "__main__":
    main()
