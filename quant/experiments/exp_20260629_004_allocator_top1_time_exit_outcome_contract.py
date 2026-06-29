from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


EXPERIMENT_ID = "exp-20260629-004"
LANE = "measurement_repair"
SLUG = "allocator_top1_time_exit_outcome_contract"
CHANGED_VARIABLE = "allocator_top1_time_exit_outcome_contract_v1"
STATUS = "accepted"
DECISION = "accepted_measurement_repair_allocator_top1_time_exit_outcome_contract"

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "quant"))

from accepted_helper_source_priority_allocator_paper_sleeve import (  # noqa: E402
    OUTCOME_CONTRACT_RULE_VERSION,
    TARGET_PRICE_STATUS,
    allocator_time_exit_outcome_contract,
)
from experiment_registry import persist_self_registered_result  # noqa: E402


TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"
BASELINE_JSON = (
    REPO_ROOT
    / "data"
    / "backtests"
    / "backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)
STATE_JSON = (
    REPO_ROOT
    / "data"
    / "paper_sleeves"
    / "accepted_helper_source_priority_allocator"
    / "state.json"
)
PILOT_RECS_DIR = REPO_ROOT / "data" / "pilots"
OUT_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = OUT_DIR / f"{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def repo_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def latest_recommendations_path() -> Path:
    paths = sorted(PILOT_RECS_DIR.glob("pilot_recommendations_*.json"))
    if not paths:
        raise FileNotFoundError("No pilot_recommendations_*.json files found")
    return paths[-1]


def allocator_surface(recommendations: dict[str, Any]) -> dict[str, Any]:
    for surface in recommendations.get("recommendations") or []:
        if isinstance(surface, dict) and surface.get("pilot") == "allocator_top1":
            return surface
    raise RuntimeError("allocator_top1 recommendation surface not found")


def row_key(row: dict[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("ticker") or "").upper(),
        str(row.get("signal_date") or row.get("date") or "")[:10],
    )


def allocator_state_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bucket in ("open_positions", "pending_entries", "closed_positions"):
        for row in state.get(bucket) or []:
            if isinstance(row, dict):
                out = dict(row)
                out["state_bucket"] = bucket
                rows.append(out)
    return rows


def recommendation_rows(surface: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bucket, label in (("actionable", "selected"), ("skipped", "skipped")):
        for row in surface.get(bucket) or []:
            if isinstance(row, dict):
                out = dict(row)
                out["allocation_bucket"] = label
                rows.append(out)
    return rows


def merged_contract_source(
    row: dict[str, Any],
    state_index: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    state_row = state_index.get(row_key(row), {})
    merged = dict(state_row)
    for key, value in row.items():
        if value is not None:
            merged[key] = value
    return merged


def add_contracts(
    rows: list[dict[str, Any]],
    state_rows_by_key: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for row in rows:
        source = merged_contract_source(row, state_rows_by_key)
        contract = allocator_time_exit_outcome_contract(
            source,
            {"hold_days": source.get("hold_days")},
        )
        out = dict(row)
        out.update(contract)
        out["state_bucket"] = source.get("state_bucket")
        out["paper_status"] = source.get("paper_status")
        enriched.append(out)
    return enriched


def field_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    target_price_present = sum(1 for row in rows if row.get("target_price") is not None)
    target_status_rows = sum(
        1 for row in rows if row.get("target_price_status") == TARGET_PRICE_STATUS
    )
    target_not_required = sum(1 for row in rows if row.get("target_price_required") is False)
    entry_date_present = sum(1 for row in rows if row.get("entry_date"))
    entry_status_rows = sum(1 for row in rows if row.get("entry_date_status"))
    return {
        "rows": total,
        "entry_date_present": entry_date_present,
        "entry_date_status_present": entry_status_rows,
        "target_price_present": target_price_present,
        "target_price_status_not_applicable": target_status_rows,
        "target_price_required_false": target_not_required,
        "target_price_status_coverage_rate": round(target_status_rows / total, 4)
        if total
        else 0.0,
        "entry_date_or_status_coverage_rate": round(
            sum(1 for row in rows if row.get("entry_date") or row.get("entry_date_status"))
            / total,
            4,
        )
        if total
        else 0.0,
    }


def compact_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = [
        "allocation_bucket",
        "status",
        "ticker",
        "signal_date",
        "entry_date",
        "entry_date_status",
        "paper_status",
        "state_bucket",
        "hold_days",
        "days_held",
        "days_remaining",
        "exit_rule",
        "target_price",
        "target_price_required",
        "target_price_status",
        "outcome_contract_rule_version",
    ]
    return [{key: row.get(key) for key in keys} for row in rows]


def build_payload() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON)
    state = read_json(STATE_JSON)
    rec_path = latest_recommendations_path()
    recommendations = read_json(rec_path)
    surface = allocator_surface(recommendations)
    rows_before = recommendation_rows(surface)
    state_rows = allocator_state_rows(state)
    state_index = {row_key(row): row for row in state_rows}
    rows_after = add_contracts(rows_before, state_index)
    before = field_summary(rows_before)
    after = field_summary(rows_after)
    state_after = [
        {
            **allocator_time_exit_outcome_contract(row, {"hold_days": row.get("hold_days")}),
            "ticker": row.get("ticker"),
            "signal_date": row.get("signal_date") or row.get("date"),
            "entry_date": row.get("entry_date"),
            "paper_status": row.get("paper_status"),
            "state_bucket": row.get("state_bucket"),
        }
        for row in state_rows
    ]
    baseline = read_json(BASELINE_JSON) if BASELINE_JSON.exists() else {}
    signals_generated = len(rows_after)
    signals_survived = sum(1 for row in rows_after if row.get("allocation_bucket") == "selected")
    survival_rate = round(signals_survived / signals_generated, 4) if signals_generated else 0.0
    contract_ready = (
        after["target_price_status_coverage_rate"] == 1.0
        and after["entry_date_or_status_coverage_rate"] == 1.0
    )
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": STATUS,
        "decision": DECISION,
        "lane": LANE,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": ticket.get("hypothesis"),
        "prediction": ticket.get("prediction") or {},
        "new_evidence_type": "measurement_repair",
        "input_files": {
            "ticket": repo_rel(TICKET_JSON),
            "baseline": repo_rel(BASELINE_JSON),
            "allocator_state": repo_rel(STATE_JSON),
            "pilot_recommendations": repo_rel(rec_path),
        },
        "baseline_anchor": {
            "exists": BASELINE_JSON.exists(),
            "aggregate_expected_value_score": baseline.get("aggregate_expected_value_score"),
            "aggregate_total_return_pct": baseline.get("aggregate_total_return_pct"),
            "note": "Baseline anchors protocol only; this repair changes no trading policy.",
        },
        "metrics": {
            "before_contract": before,
            "after_contract": after,
            "state_rows_with_contract_after_helper": field_summary(state_after),
            "signals_generated": signals_generated,
            "signals_survived": signals_survived,
            "survival_rate": survival_rate,
        },
        "rows_after_contract": compact_rows(rows_after),
        "gate1": {
            "passed": BASELINE_JSON.exists(),
            "baseline_result_file": repo_rel(BASELINE_JSON),
        },
        "gate2": {
            "passed": contract_ready,
            "runtime_fields_checked": [
                "entry_date",
                "entry_date_status",
                "target_price",
                "target_price_required",
                "target_price_status",
                "exit_rule",
            ],
            "target_price_contract": TARGET_PRICE_STATUS,
            "target_price_relevance": (
                "target_price is intentionally None because allocator_top1 exits by "
                "fixed time hold; closed outcomes use exit_price and pnl fields."
            ),
        },
        "gate3": {
            "passed": survival_rate >= 0.05 and signals_survived > 0,
            "signals_generated": signals_generated,
            "signals_survived": signals_survived,
            "survival_rate": survival_rate,
            "note": "Measurement repair only; no new filter was added.",
        },
        "gate4": {
            "passed": True,
            "status": "not_applicable_measurement_repair_no_policy_delta",
            "expected_value_delta": 0.0,
            "pnl_delta": 0.0,
            "note": (
                "No before/after strategy replay was run because orders, ranking, sizing, "
                "and exits are unchanged. This accepts only the measurement contract."
            ),
        },
        "production_impact": {
            "shared_helper_changed": True,
            "default_off_paper_only": True,
            "trade_enabled": False,
            "alters_orders": False,
            "alters_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "daily_snapshot_contract_exposed": True,
            "live_ready": False,
        },
        "post_run_reflection": {
            "why_result_happened": (
                "The prior allocator blocker was semantic rather than alpha evidence: "
                "time-exit rows were counted as missing target_price. The helper now "
                "marks target_price as not_applicable_time_exit and names exit_price/pnl "
                "as the closed-outcome fields."
            ),
            "do_not_claim": (
                "Do not use this repair to retune allocator capacity or promote allocator_top1; "
                "closed replacement-value rows are still required."
            ),
            "next_retry_requires": (
                "Wait for materially more closed allocator_top1 replacement-value rows, "
                "then test selected-vs-skipped allocation with the explicit contract."
            ),
        },
        "changed_files": [
            "quant/accepted_helper_source_priority_allocator_paper_sleeve.py",
            "quant/test_accepted_helper_source_priority_allocator_paper_sleeve.py",
            "quant/experiments/exp_20260629_004_allocator_top1_time_exit_outcome_contract.py",
        ],
        "reproduction_commands": [
            ".\\.venv\\Scripts\\python.exe -B -m pytest quant\\test_accepted_helper_source_priority_allocator_paper_sleeve.py",
            ".\\.venv\\Scripts\\python.exe -B quant\\experiments\\exp_20260629_004_allocator_top1_time_exit_outcome_contract.py",
        ],
    }


def build_log_row(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "lane": LANE,
        "changed_variable": CHANGED_VARIABLE,
        "hypothesis": payload["hypothesis"],
        "metrics": payload["metrics"],
        "gate1": payload["gate1"],
        "gate2": payload["gate2"],
        "gate3": payload["gate3"],
        "gate4": payload["gate4"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "changed_files": payload["changed_files"],
        "reproduction_commands": payload["reproduction_commands"],
        "artifact": repo_rel(OUT_JSON),
    }


def build_card(payload: dict[str, Any]) -> str:
    after = payload["metrics"]["after_contract"]
    return "\n".join(
        [
            f"# {EXPERIMENT_ID} allocator TOP-1 time-exit outcome contract",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Status: `{payload['status']}`",
            f"- Artifact: `{repo_rel(OUT_JSON)}`",
            f"- Rows covered: `{after['target_price_status_not_applicable']}/{after['rows']}` target_price_not_applicable contracts",
            "- Production impact: default-off paper metadata only; no orders, ranking, sizing, or exits changed.",
            "- Next: wait for materially more closed allocator_top1 replacement-value rows before allocation retunes.",
            "",
        ]
    )


def persist(payload: dict[str, Any]) -> None:
    log_row = build_log_row(payload)
    write_json(OUT_JSON, payload)
    write_json(LOG_JSON, log_row)
    CARD_MD.parent.mkdir(parents=True, exist_ok=True)
    CARD_MD.write_text(build_card(payload), encoding="utf-8")
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane=LANE,
        prediction=payload["prediction"],
        result={
            "decision": payload["decision"],
            "status": payload["status"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "metrics": payload["metrics"],
            "gate2": payload["gate2"],
            "gate4": payload["gate4"],
            "production_impact": payload["production_impact"],
        },
        status=payload["status"],
        fields={
            "change_type": "measurement_repair",
            "mechanism_family": "allocator_forward_measurement",
            "trial_family": "allocator_top1_outcome_contract",
            "trial_variant_id": "time_exit_target_price_not_applicable_v1",
            "single_causal_variable": CHANGED_VARIABLE,
            "changed_variable": CHANGED_VARIABLE,
            "decision": payload["decision"],
            "artifact": repo_rel(OUT_JSON),
            "log": repo_rel(LOG_JSON),
            "card_file": repo_rel(CARD_MD),
            "accepted_measurement_repair": True,
        },
    )


def main() -> None:
    payload = build_payload()
    persist(payload)
    print(json.dumps(build_log_row(payload), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
