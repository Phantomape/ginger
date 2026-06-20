"""exp-20260620-017: quarterly inventory turnover duplicate closeout.

This alpha-search closeout records that the proposed quarterly COGS /
inventory turnover acceleration candidate source is not a valid new frozen-window
experiment. The stronger near-neighbor exp-20260616-022 already tested the same
PIT SEC Companyfacts InventoryNet plus quarterly CostOfRevenue turnover/DIO
mechanism and failed Gate 4. No strategy, helper, production adapter, order
path, ranking, sizing, exit, watchlist, LLM, or news behavior is changed.
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
for entry in (str(REPO_ROOT), str(SCRIPTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from experiment_registry import persist_self_registered_result  # noqa: E402


EXPERIMENT_ID = "exp-20260620-017"
SLUG = "quarterly_inventory_turnover_acceleration"
OWNER = "alpha-search-automation"
RUNNER_NAME = (
    "quant/experiments/"
    "exp_20260620_017_quarterly_inventory_turnover_acceleration.py"
)

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
OUT_JSON = DATA_DIR / f"exp_20260620_017_{SLUG}.json"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT_FILE = (
    "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

HYPOTHESIS = (
    "candidate_pool: PIT quarterly inventory turnover acceleration from raw SEC "
    "Companyfacts COGS and average inventory may identify demand sell-through "
    "candidates better than annual inventory/revenue leanness when confirmed by "
    "liquid SPY-relative leadership."
)
CHANGED_VARIABLE = "quarterly_inventory_turnover_acceleration_candidate_source_v1"
TRIAL_FAMILY = "quarterly_inventory_turnover_acceleration_candidate_pool"
TRIAL_VARIANT_ID = "quarterly_inventory_turnover_acceleration_duplicate_closeout_v1"

PREDICTION = {
    "success_probability": 0.22,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "window_regression",
        "drawdown_drift_too_high",
        "accepted_distribution_comparator_not_beaten",
        "inventory_tag_sparse",
        "concentration_failed",
    ],
    "confidence_reason": (
        "Prior annual inventory leanness was high aggregate EV but failed "
        "old_thin/drawdown; playbook explicitly names quarterly inventory "
        "turnover as the valid sharper PIT discriminator, but CCC/DIO neighbors "
        "and old_thin fragility make success unlikely."
    ),
    "recorded_at": "2026-06-20T16:05:23+00:00",
}

CANONICAL_WINDOWS: dict[str, dict[str, Any]] = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
        "expected_value_score": 5.1628,
        "sharpe_daily": 4.41,
        "strategy_total_return_pct": 1.1707,
        "total_pnl": 117072.92,
        "max_drawdown_pct": 0.0665,
        "win_rate": 0.8333,
        "trade_count": 18,
        "signals_generated": 51,
        "signals_survived": 41,
        "survival_rate": 0.8039,
    },
    "mid_weak": {
        "start": "2025-04-23",
        "end": "2025-10-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20250423_20251022.json",
        "expected_value_score": 2.1402,
        "sharpe_daily": 2.74,
        "strategy_total_return_pct": 0.7811,
        "total_pnl": 78110.11,
        "max_drawdown_pct": 0.1119,
        "win_rate": 0.5238,
        "trade_count": 21,
        "signals_generated": 53,
        "signals_survived": 42,
        "survival_rate": 0.7925,
    },
    "old_thin": {
        "start": "2024-10-02",
        "end": "2025-04-22",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20241002_20250422.json",
        "expected_value_score": 0.5911,
        "sharpe_daily": 1.49,
        "strategy_total_return_pct": 0.3967,
        "total_pnl": 39667.96,
        "max_drawdown_pct": 0.1001,
        "win_rate": 0.4091,
        "trade_count": 22,
        "signals_generated": 60,
        "signals_survived": 52,
        "survival_rate": 0.8667,
    },
}

PRIOR_EXP_20260616_022 = {
    "experiment_id": "exp-20260616-022",
    "decision": "rejected_quarterly_inventory_dio_turnover_improvement_candidate_pool",
    "artifact": (
        "data/experiments/exp-20260616-022/"
        "exp_20260616_022_quarterly_inventory_dio_turnover_improvement.json"
    ),
    "mechanism_overlap": (
        "Raw SEC Companyfacts InventoryNet instant facts matched by filed date to "
        "standalone quarterly CostOfRevenue facts, converted into inventory "
        "turnover/DIO improvement, confirmed with liquid SPY-relative leadership, "
        "next-open paper entry, 10 trading-day exit, and top-1/day selection."
    ),
    "aggregate_ev_delta": 0.5185,
    "aggregate_pnl_delta": 5796.59,
    "max_drawdown_drift": 0.0094,
    "target_trade_count": 111,
    "accepted_distribution_comparator_ev": 0.5286,
    "accepted_distribution_comparator_pnl": 10432.91,
    "failed_reasons": [
        "window_ev_regression",
        "window_pnl_regression",
        "drawdown_drift_too_high",
        "target_concentration_failed",
        "accepted_distribution_ev_not_beaten",
        "accepted_distribution_pnl_not_beaten",
    ],
    "windows": {
        "late_strong": {"ev_delta": 0.4005, "pnl_delta": 5200.47, "trades": 29},
        "mid_weak": {"ev_delta": 0.2304, "pnl_delta": 5067.77, "trades": 45},
        "old_thin": {"ev_delta": -0.1124, "pnl_delta": -4471.65, "trades": 37},
    },
    "reopen_condition": (
        "A retry needs materially different PIT inventory-quality evidence such "
        "as finished-goods vs raw-materials decomposition, quarterly inventory "
        "turnover with richer segment detail, or closed forward replacement-value "
        "rows. Do not sweep the inventory/COGS tag list, quarterly DIO threshold, "
        "COGS-growth floor, fact freshness, price guards, top-N, hold, cooldown, "
        "or notional on these frozen windows."
    ),
}


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _repo_rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _upsert_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    replaced = False
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                records.append({"_raw": line})
                continue
            if row.get("experiment_id") == EXPERIMENT_ID:
                records.append(record)
                replaced = True
            else:
                records.append(row)
    if not replaced:
        records.append(record)
    lines = []
    for row in records:
        if isinstance(row, dict) and "_raw" in row:
            lines.append(str(row["_raw"]))
        else:
            lines.append(json.dumps(row, ensure_ascii=True, sort_keys=True))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _aggregate_baseline() -> dict[str, Any]:
    return {
        "aggregate_expected_value_score": round(
            sum(w["expected_value_score"] for w in CANONICAL_WINDOWS.values()), 4
        ),
        "aggregate_total_pnl": round(
            sum(w["total_pnl"] for w in CANONICAL_WINDOWS.values()), 2
        ),
        "max_window_drawdown_pct": max(
            w["max_drawdown_pct"] for w in CANONICAL_WINDOWS.values()
        ),
        "min_survival_rate": min(w["survival_rate"] for w in CANONICAL_WINDOWS.values()),
        "total_trade_count": sum(w["trade_count"] for w in CANONICAL_WINDOWS.values()),
    }


def _window_deltas() -> dict[str, dict[str, float]]:
    return {
        label: {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "max_drawdown_pct": 0.0,
            "trade_count": 0.0,
            "survival_rate": 0.0,
        }
        for label in CANONICAL_WINDOWS
    }


def _build_payload() -> dict[str, Any]:
    now = _now_utc()
    aggregate = _aggregate_baseline()
    gate4 = {
        "passed": False,
        "decision": "blocked_duplicate_frozen_inventory_turnover_prior",
        "target_windows": list(CANONICAL_WINDOWS),
        "window_deltas": _window_deltas(),
        "aggregate_ev_delta": 0.0,
        "aggregate_pnl_delta": 0.0,
        "max_drawdown_worse": 0.0,
        "max_drawdown_worse_guardrail": 0.005,
        "minimum_core_survival_rate": aggregate["min_survival_rate"],
        "survival_guard_passed": True,
        "target_trade_count": 0,
        "target_trade_count_min": 20,
        "failed_reasons": [
            "duplicate_frozen_near_neighbor_exp_20260616_022",
            "no_new_inventory_quality_evidence_axis",
            "strategy_logic_not_started",
        ],
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now,
        "lane": "alpha_search",
        "status": "blocked",
        "decision": "blocked_duplicate_frozen_inventory_turnover_prior",
        "accepted": False,
        "accepted_alpha": False,
        "hypothesis": HYPOTHESIS,
        "change_type": "candidate_pool_full_stack_closeout",
        "mechanism_family": "production_visible_free_sec_companyfacts_inventory_quality_candidate_pool",
        "trial_family": TRIAL_FAMILY,
        "trial_variant_id": TRIAL_VARIANT_ID,
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": [
            "novelty_gate_near_neighbor_review",
            "prior_experiment_gate4_review",
            "canonical_three_window_baseline_disclosure",
            "production_parity_verdict",
        ],
        "nearby_prior_experiments": [
            "exp-20260616-018",
            "exp-20260616-019",
            "exp-20260616-022",
            "exp-20260617-002",
            "exp-20260619-004",
        ],
        "new_evidence_type": "none_duplicate_prior_identified_before_strategy_logic",
        "prediction": PREDICTION,
        "baseline_result_file": BASELINE_RESULT_FILE,
        "gate1_baseline": {
            "status": "passed",
            "source": BASELINE_RESULT_FILE,
            "windows": CANONICAL_WINDOWS,
            "baseline_aggregate": aggregate,
        },
        "gate2_field_availability": {
            "status": "blocked_before_new_field_use",
            "runtime_fields": [
                "operator_inputs/open_positions.json entry_date",
                "operator_inputs/open_positions.json target_price",
            ],
            "blocker": (
                "The proposed COGS/average-inventory turnover acceleration field "
                "is not a new data axis after reviewing exp-20260616-022 and "
                "docs/frozen_families.jsonl."
            ),
            "nearest_frozen_family": "quarterly_inventory_dio_turnover_improvement_candidate_pool",
            "nearest_prior": PRIOR_EXP_20260616_022,
        },
        "gate3_survival": {
            "status": "passed_for_baseline_only",
            "signals_generated": {
                label: w["signals_generated"] for label, w in CANONICAL_WINDOWS.items()
            },
            "signals_survived": {
                label: w["signals_survived"] for label, w in CANONICAL_WINDOWS.items()
            },
            "survival_rate": {
                label: w["survival_rate"] for label, w in CANONICAL_WINDOWS.items()
            },
            "minimum_survival_rate": aggregate["min_survival_rate"],
            "threshold": 0.05,
        },
        "gate4": gate4,
        "before_metrics": CANONICAL_WINDOWS,
        "after_metrics": CANONICAL_WINDOWS,
        "delta_metrics": {
            "aggregate_expected_value_score": 0.0,
            "aggregate_total_pnl": 0.0,
            "max_window_drawdown_pct": 0.0,
            "total_trade_count": 0.0,
            "min_survival_rate": 0.0,
        },
        "production_impact": {
            "replay_only": False,
            "default_off_paper_only": False,
            "shared_policy_changed": False,
            "run_adapter_changed": False,
            "backtester_adapter_changed": False,
            "daily_snapshot_exposed": False,
            "production_orders_changed": False,
            "production_signal_path_changed": False,
            "production_watchlist_changed": False,
            "alters_orders": False,
            "alters_signal_generation": False,
            "alters_candidate_ranking": False,
            "alters_sizing": False,
            "alters_exits": False,
            "trade_enabled": False,
            "live_ready": False,
            "parity_note": (
                "No strategy code or production-visible helper was introduced. "
                "Backtest/production parity is preserved by refusing the duplicate "
                "inventory-turnover experiment before any replay or daily adapter."
            ),
        },
        "calibration": {
            "predicted_success_probability": PREDICTION["success_probability"],
            "realized_failure_mode": "duplicate_frozen_near_neighbor",
            "actual_success": 0,
            "actual_gate4_passed": False,
            "actual_ev_delta": 0.0,
            "actual_pnl_delta": 0.0,
            "surprise": (
                "Low surprise: novelty gate already warned on inventory and "
                "working-capital families; deeper review found the exact stronger "
                "quarterly COGS/inventory turnover prior."
            ),
        },
        "post_run_reflection": {
            "why_blocked": (
                "The proposed quarterly inventory turnover acceleration source "
                "collapses into the rejected exp-20260616-022 PIT quarterly "
                "InventoryNet/CostOfRevenue turnover-DIO family. That prior had "
                "aggregate EV +0.5185 and PnL +$5,796.59, but old_thin regressed "
                "(-0.1124 EV / -$4,471.65), drawdown drift was +0.0094, "
                "concentration failed, and the accepted distribution comparator "
                "was not beaten."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry inventory/COGS tag lists, quarterly turnover or DIO "
                "thresholds, COGS-growth floors, fact freshness, price/RS/volume/"
                "volatility guards, top-N, hold, cooldown, or notional on the "
                "same frozen windows."
            ),
            "new_evidence_required": PRIOR_EXP_20260616_022["reopen_condition"],
            "next_alpha_direction": (
                "Shift away from inventory/Companyfacts working-capital retunes. "
                "The next free-data edge should use a materially different primary "
                "document/economic surface such as SEC offering/prospectus economics, "
                "historical filer-status provenance, or named customer/supplier "
                "contract terms."
            ),
        },
        "changed_files": [
            RUNNER_NAME,
            _repo_rel(OUT_JSON),
            _repo_rel(LOG_JSON),
            _repo_rel(CARD_MD),
            _repo_rel(MANIFEST_JSON),
            _repo_rel(TICKET_JSON),
            _repo_rel(EXPERIMENT_LOG),
            _repo_rel(REGISTRY_JSON),
        ],
        "reproduction": f".venv\\Scripts\\python.exe -B {RUNNER_NAME}",
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": True,
    }


def _build_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": payload["timestamp"],
        "lane": payload["lane"],
        "status": payload["status"],
        "decision": payload["decision"],
        "hypothesis": payload["hypothesis"],
        "change_type": payload["change_type"],
        "single_causal_variable": payload["single_causal_variable"],
        "changed_variable": payload["changed_variable"],
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "baseline_result_file": BASELINE_RESULT_FILE,
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "runner": RUNNER_NAME,
        "gate1_baseline": payload["gate1_baseline"],
        "gate2_field_availability": payload["gate2_field_availability"],
        "gate3_survival": payload["gate3_survival"],
        "gate4": payload["gate4"],
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "prediction": payload["prediction"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
        "changed_files": payload["changed_files"],
        "accepted": False,
        "accepted_alpha": False,
        "lean_quality_passed": True,
        "anti_js": payload["anti_js"],
    }


def _build_card(payload: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: quarterly inventory turnover duplicate closeout",
        "",
        "- Lane: alpha_search",
        "- Status: blocked",
        f"- Decision: {payload['decision']}",
        "- Strategy changes: none",
        "- Production changes: none",
        "",
        "## Hypothesis",
        "",
        HYPOTHESIS,
        "",
        "## Why Blocked",
        "",
        payload["post_run_reflection"]["why_blocked"],
        "",
        "## Canonical Gate 4",
        "",
        "| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, metrics in CANONICAL_WINDOWS.items():
        lines.append(
            f"| {label} | {metrics['expected_value_score']:.4f} | "
            f"{metrics['expected_value_score']:.4f} | 0.0000 | "
            f"${metrics['total_pnl']:,.2f} | ${metrics['total_pnl']:,.2f} | "
            "$0.00 |"
        )
    lines.extend(
        [
            "",
            "## Prior That Blocks This",
            "",
            "- Prior: exp-20260616-022",
            "- Aggregate prior delta: EV +0.5185, PnL +$5,796.59",
            "- Prior failure: old_thin regressed, drawdown drift +0.0094, "
            "concentration failed, accepted distribution comparator not beaten.",
            "",
            "## Reflection",
            "",
            payload["post_run_reflection"]["forbidden_near_neighbor_retry"],
            "",
            payload["post_run_reflection"]["new_evidence_required"],
            "",
        ]
    )
    return "\n".join(lines)


def _persist(payload: dict[str, Any]) -> None:
    _write_json(OUT_JSON, payload)
    _write_json(LOG_JSON, payload)
    _write_text(CARD_MD, _build_card(payload))
    _upsert_jsonl(EXPERIMENT_LOG, _build_log_record(payload))

    result = {
        "decision": payload["decision"],
        "accepted": False,
        "accepted_alpha": False,
        "numeric_gate4_passed": False,
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "gate4": payload["gate4"],
        "calibration": payload["calibration"],
        "production_impact": payload["production_impact"],
        "post_run_reflection": payload["post_run_reflection"],
    }
    fields = {
        "owner": OWNER,
        "hypothesis": HYPOTHESIS,
        "change_type": payload["change_type"],
        "mechanism_family": payload["mechanism_family"],
        "trial_family": payload["trial_family"],
        "trial_variant_id": payload["trial_variant_id"],
        "single_causal_variable": CHANGED_VARIABLE,
        "changed_variable": CHANGED_VARIABLE,
        "causal_components": payload["causal_components"],
        "nearby_prior_experiments": payload["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": payload["new_evidence_type"],
        "baseline_result_file": BASELINE_RESULT_FILE,
        "acceptance_rule": "Blocked because a stronger frozen near-neighbor already tested the same mechanism.",
        "decision": payload["decision"],
        "summary": payload["post_run_reflection"]["why_blocked"],
        "artifact": _repo_rel(OUT_JSON),
        "log": _repo_rel(LOG_JSON),
        "ticket_file": _repo_rel(TICKET_JSON),
        "card_file": _repo_rel(CARD_MD),
        "revision_manifest_file": _repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "gate1_baseline": payload["gate1_baseline"],
        "gate2_field_availability": payload["gate2_field_availability"],
        "gate3_survival": payload["gate3_survival"],
        "gate4": payload["gate4"],
        "post_run_reflection": payload["post_run_reflection"],
        "production_impact": payload["production_impact"],
        "lean_quality_passed": True,
    }
    persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=PREDICTION,
        result=result,
        status="blocked",
        fields=fields,
    )

    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": payload["status"],
        "decision": payload["decision"],
        "created_at": payload["timestamp"],
        "anti_js": payload["anti_js"],
        "allowed_write_scope": payload["changed_files"],
        "file_hashes": {
            RUNNER_NAME: _sha256(REPO_ROOT / RUNNER_NAME),
            _repo_rel(OUT_JSON): _sha256(OUT_JSON),
            _repo_rel(LOG_JSON): _sha256(LOG_JSON),
            _repo_rel(TICKET_JSON): _sha256(TICKET_JSON),
            _repo_rel(CARD_MD): _sha256(CARD_MD),
        },
    }
    _write_json(MANIFEST_JSON, manifest)


def main() -> None:
    payload = _build_payload()
    _persist(payload)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": payload["status"],
                "decision": payload["decision"],
                "aggregate_ev_delta": 0.0,
                "aggregate_pnl_delta": 0.0,
                "blocking_prior": PRIOR_EXP_20260616_022["experiment_id"],
                "anti_js": payload["anti_js"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
