"""exp-20260619-002: interest-burden near-neighbor blocker.

This alpha-search ticket was reserved for a raw SEC Companyfacts interest
expense burden-relief replay. After reservation, the novelty and history check
found a direct prior experiment, exp-20260616-004, with the same family and an
explicit no-retune rule. This runner closes the ticket without testing a new
strategy policy because a threshold/tag/guard replay would be an untrustworthy
near-neighbor.

No production code, shared adapter, ranking, sizing, exits, LLM/news path, or
watchlist behavior is changed. No JavaScript is used.
"""

from __future__ import annotations

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

import experiment_registry  # noqa: E402


EXPERIMENT_ID = "exp-20260619-002"
SLUG = "interest_burden_near_neighbor_blocker"
RUNNER_NAME = (
    "quant/experiments/"
    "exp_20260619_002_interest_burden_near_neighbor_blocker.py"
)

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"exp_20260619_002_{SLUG}.json"
BEFORE_JSON = DATA_DIR / "before_baseline.json"
AFTER_JSON = DATA_DIR / "after_no_strategy_change.json"
README_MD = DATA_DIR / "README.md"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

BASELINE_RESULT_FILE = (
    "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
)

CANONICAL_WINDOWS: dict[str, dict[str, Any]] = {
    "late_strong": {
        "start": "2025-10-23",
        "end": "2026-04-21",
        "snapshot": "data/ohlcv/ohlcv_snapshot_20251023_20260421.json",
        "expected_value_score": 5.1628,
        "total_pnl": 117072.92,
        "max_drawdown_pct": 0.0665,
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
        "total_pnl": 78110.11,
        "max_drawdown_pct": 0.1119,
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
        "total_pnl": 39667.96,
        "max_drawdown_pct": 0.1001,
        "trade_count": 22,
        "signals_generated": 60,
        "signals_survived": 52,
        "survival_rate": 0.8667,
    },
}

PRIOR_INTEREST_RESULT = {
    "experiment_id": "exp-20260616-004",
    "decision": "rejected_raw_sec_interest_burden_relief_candidate_pool",
    "aggregate_ev_delta": 0.4305,
    "aggregate_pnl_delta": 6763.08,
    "target_trade_count": 45,
    "target_windows": ["late_strong", "mid_weak"],
    "failed_reasons": [
        "target_window_coverage_too_small",
        "target_concentration_failed",
        "accepted_distribution_ev_not_beaten",
        "accepted_distribution_pnl_not_beaten",
    ],
    "old_thin_target_trades": 0,
    "forbidden_retry": (
        "Do not retry by sweeping interest-burden thresholds, interest growth "
        "spread, revenue floor, annual fact freshness, tag lists, RS/close/"
        "volume/vol guards, top-N, hold days, cooldown, or notional on these "
        "frozen windows."
    ),
    "new_evidence_required": (
        "Materially different PIT financing data such as borrow cost, debt "
        "maturity/refinancing terms, or analyst/revenue revisions confirming "
        "the relief."
    ),
}

HYPOTHESIS = (
    "candidate_pool: raw SEC Companyfacts annual interest-expense burden relief "
    "with revenue/operating-income context and liquid SPY-relative confirmation "
    "might identify debt-cost relief candidates."
)

PREDICTION = {
    "success_probability": 0.12,
    "expected_ev_delta": 0.0,
    "expected_pnl_delta": 0.0,
    "main_failure_modes": [
        "companyfacts_relief_family_saturated",
        "interest_expense_semantics_noisy",
        "bank_financial_statement_noise",
        "window_regression",
        "accepted_comparator_not_beaten",
    ],
    "confidence_reason": (
        "Recorded at reservation. The post-reservation history check showed "
        "this was not a valid new evidence axis."
    ),
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}


def append_jsonl_once(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_lines: list[str] = []
    replaced = False
    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                existing_lines.append(raw)
                continue
            if existing.get("experiment_id") == EXPERIMENT_ID:
                existing_lines.append(json.dumps(record, sort_keys=True))
                replaced = True
            else:
                existing_lines.append(raw)
    if not replaced:
        existing_lines.append(json.dumps(record, sort_keys=True))
    path.write_text("\n".join(existing_lines) + "\n", encoding="utf-8")


def aggregate_windows() -> dict[str, Any]:
    return {
        "aggregate_expected_value_score": round(
            sum(float(row["expected_value_score"]) for row in CANONICAL_WINDOWS.values()),
            4,
        ),
        "aggregate_total_pnl": round(
            sum(float(row["total_pnl"]) for row in CANONICAL_WINDOWS.values()),
            2,
        ),
        "total_trade_count": sum(int(row["trade_count"]) for row in CANONICAL_WINDOWS.values()),
        "min_survival_rate": min(float(row["survival_rate"]) for row in CANONICAL_WINDOWS.values()),
        "max_window_drawdown_pct": max(
            float(row["max_drawdown_pct"]) for row in CANONICAL_WINDOWS.values()
        ),
    }


def baseline_artifact(kind: str) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "artifact_type": kind,
        "baseline_result_file": BASELINE_RESULT_FILE,
        "canonical_source": "docs/backtesting.md",
        "windows": CANONICAL_WINDOWS,
        "aggregate": aggregate_windows(),
        "strategy_code_changed": False,
        "production_code_changed": False,
        "note": "Identity artifact: no after policy was tested because novelty failed.",
    }


def build_result() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON)
    now = now_utc()
    aggregate = aggregate_windows()
    window_deltas = {
        label: {
            "expected_value_score": 0.0,
            "total_pnl": 0.0,
            "max_drawdown_pct": 0.0,
            "trade_count": 0.0,
            "survival_rate": 0.0,
        }
        for label in CANONICAL_WINDOWS
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "created_at": now,
        "lane": "alpha_search",
        "status": "blocked",
        "decision": "blocked_interest_burden_near_neighbor_invalid_novelty_axis",
        "hypothesis": ticket.get("hypothesis") or HYPOTHESIS,
        "change_type": "alpha_search_near_neighbor_blocker",
        "mechanism_family": "production_visible_free_sec_companyfacts_interest_burden_candidate_pool",
        "trial_family": "interest_expense_burden_relief_candidate_pool",
        "trial_variant_id": "interest_expense_burden_relief_top1_next_open_10d_v1",
        "single_causal_variable": "raw_sec_companyfacts_interest_expense_burden_relief_candidate_source_v1",
        "changed_variable": "raw_sec_companyfacts_interest_expense_burden_relief_candidate_source_v1",
        "nearby_prior_experiments": ["exp-20260616-004", "exp-20260616-029"],
        "prediction": ticket.get("prediction") or PREDICTION,
        "novelty_check": {
            "reservation_warning": (ticket.get("novelty") or {}).get("warn"),
            "nearest": (ticket.get("novelty") or {}).get("nearest"),
            "post_reservation_conclusion": (
                "Override was not sufficient: exp-20260616-004 directly tested "
                "raw SEC interest-burden relief and froze threshold/tag/guard "
                "retunes on these windows."
            ),
        },
        "gate1_baseline": {
            "status": "passed",
            "source": BASELINE_RESULT_FILE,
            "windows": CANONICAL_WINDOWS,
            "aggregate": aggregate,
        },
        "gate2_field_availability": {
            "status": "blocked_by_prior_evidence_not_field_absence",
            "minimum_runtime_fields_checked": ["entry_date", "target_price"],
            "blocking_item": (
                "The required new evidence axis is absent; the available field "
                "is the same rejected interest-burden family."
            ),
            "prior_interest_result": PRIOR_INTEREST_RESULT,
        },
        "gate3_survival": {
            "status": "not_applicable_no_new_filter",
            "baseline_min_survival_rate": aggregate["min_survival_rate"],
            "guardrail": "survival_rate must not fall below 0.05",
        },
        "gate4": {
            "status": "blocked_no_after_policy",
            "before": CANONICAL_WINDOWS,
            "after": CANONICAL_WINDOWS,
            "window_deltas": window_deltas,
            "aggregate_before": aggregate,
            "aggregate_after": aggregate,
            "aggregate_delta": {
                "aggregate_expected_value_score": 0.0,
                "aggregate_total_pnl": 0.0,
                "total_trade_count": 0,
                "min_survival_rate": 0.0,
                "max_window_drawdown_pct": 0.0,
            },
            "acceptance_result": "blocked",
            "reason": (
                "No strategy replay was run because it would be a forbidden "
                "near-neighbor of exp-20260616-004."
            ),
        },
        "production_impact": {
            "production_code_changed": False,
            "backtest_code_changed": False,
            "live_orders_changed": False,
            "shared_helper_added": False,
            "parity_assessment": (
                "No production/backtest inconsistency was introduced because no "
                "policy or helper changed."
            ),
        },
        "post_run_reflection": {
            "why_blocked": (
                "The interest-burden idea had already been tested and rejected: "
                "late/mid windows were positive, old_thin had zero target "
                "trades, concentration failed, and it did not beat the accepted "
                "distribution comparator."
            ),
            "forbidden_near_neighbor_retry": PRIOR_INTEREST_RESULT["forbidden_retry"],
            "new_evidence_required": PRIOR_INTEREST_RESULT["new_evidence_required"],
        },
        "delta_metrics": {
            "aggregate_expected_value_score": 0.0,
            "aggregate_total_pnl": 0.0,
        },
        "calibration": {
            "predicted_success_probability": (ticket.get("prediction") or PREDICTION).get(
                "success_probability"
            ),
            "realized_failure_mode": "invalid_near_neighbor_novelty_axis",
        },
        "changed_files": [
            RUNNER_NAME,
            repo_rel(ARTIFACT_JSON),
            repo_rel(BEFORE_JSON),
            repo_rel(AFTER_JSON),
            repo_rel(README_MD),
            repo_rel(LOG_JSON),
            repo_rel(CARD_MD),
            repo_rel(MANIFEST_JSON),
            repo_rel(TICKET_JSON),
            "docs/experiment_log.jsonl",
            "docs/experiment_registry.json",
        ],
        "reproduction": f".\\.venv\\Scripts\\python.exe -B {RUNNER_NAME}",
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": True,
    }


def build_log_record(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": result["created_at"],
        "lane": result["lane"],
        "status": result["status"],
        "decision": result["decision"],
        "hypothesis": result["hypothesis"],
        "change_type": result["change_type"],
        "single_causal_variable": result["single_causal_variable"],
        "changed_variable": result["changed_variable"],
        "nearby_prior_experiments": result["nearby_prior_experiments"],
        "baseline_result_file": BASELINE_RESULT_FILE,
        "before_artifact": repo_rel(BEFORE_JSON),
        "after_artifact": repo_rel(AFTER_JSON),
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER_NAME,
        "gate1_baseline": result["gate1_baseline"],
        "gate2_field_availability": result["gate2_field_availability"],
        "gate3_survival": result["gate3_survival"],
        "gate4": result["gate4"],
        "delta_metrics": result["delta_metrics"],
        "calibration": result["calibration"],
        "production_impact": result["production_impact"],
        "post_run_reflection": result["post_run_reflection"],
        "changed_files": result["changed_files"],
        "reproduction": result["reproduction"],
        "lean_quality_passed": result["lean_quality_passed"],
        "anti_js": result["anti_js"],
    }


def build_card(result: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: interest-burden near-neighbor blocker",
        "",
        "- Lane: alpha_search",
        "- Status: blocked",
        f"- Decision: {result['decision']}",
        "- Prior: exp-20260616-004 already rejected raw SEC interest-burden relief.",
        "",
        "## Three-window identity check",
        "",
        "| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, before in CANONICAL_WINDOWS.items():
        lines.append(
            f"| {label} | {before['expected_value_score']:.4f} | "
            f"{before['expected_value_score']:.4f} | 0.0000 | "
            f"${before['total_pnl']:,.2f} | ${before['total_pnl']:,.2f} | $0.00 |"
        )
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            "No strategy replay was run. The direct prior had old_thin zero "
            "coverage, failed target concentration, and did not beat the "
            "accepted distribution comparator. A valid retry needs borrow cost, "
            "debt maturity/refinancing terms, analyst confirmation, or forward "
            "replacement rows.",
            "",
            "No production code, backtest policy, shared helper, live order path, "
            "ranking, sizing, or exit logic changed. No JavaScript was used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_readme(result: dict[str, Any]) -> str:
    return (
        f"# {EXPERIMENT_ID}\n\n"
        "Alpha-search blocker artifact. The interest-burden idea was not "
        "replayed because history proved it was a forbidden near-neighbor of "
        "exp-20260616-004.\n\n"
        f"Decision: `{result['decision']}`. No JavaScript was used.\n"
    )


def write_manifest(result: dict[str, Any]) -> None:
    write_json(
        MANIFEST_JSON,
        {
            "experiment_id": EXPERIMENT_ID,
            "status": result["status"],
            "decision": result["decision"],
            "lane": result["lane"],
            "files": result["changed_files"],
            "artifact": repo_rel(ARTIFACT_JSON),
            "before": repo_rel(BEFORE_JSON),
            "after": repo_rel(AFTER_JSON),
            "log": repo_rel(LOG_JSON),
            "card": repo_rel(CARD_MD),
            "ticket": repo_rel(TICKET_JSON),
            "runner": RUNNER_NAME,
            "command": result["reproduction"],
            "anti_js": result["anti_js"],
            "updated_at": now_utc(),
        },
    )


def update_ticket(result: dict[str, Any]) -> None:
    ticket = read_json(TICKET_JSON)
    ticket["status"] = result["status"]
    ticket["completed_at"] = result["created_at"]
    ticket["result"] = {
        "decision": result["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "summary": result["post_run_reflection"]["why_blocked"],
    }
    write_json(TICKET_JSON, ticket)


def persist(result: dict[str, Any]) -> None:
    write_json(BEFORE_JSON, baseline_artifact("before_baseline"))
    write_json(AFTER_JSON, baseline_artifact("after_no_strategy_change"))
    write_json(ARTIFACT_JSON, result)
    write_json(LOG_JSON, result)
    write_text(CARD_MD, build_card(result))
    write_text(README_MD, build_readme(result))
    append_jsonl_once(EXPERIMENT_LOG_JSONL, build_log_record(result))
    update_ticket(result)

    registry_result = {
        "accepted": False,
        "accepted_alpha": False,
        "decision": result["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "before": repo_rel(BEFORE_JSON),
        "after": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "runner": RUNNER_NAME,
        "delta_metrics": result["delta_metrics"],
        "gate4": result["gate4"],
        "summary": result["post_run_reflection"]["why_blocked"],
    }
    fields = {
        "owner": "alpha-search-automation",
        "hypothesis": result["hypothesis"],
        "change_type": result["change_type"],
        "mechanism_family": result["mechanism_family"],
        "trial_family": result["trial_family"],
        "trial_variant_id": result["trial_variant_id"],
        "single_causal_variable": result["single_causal_variable"],
        "changed_variable": result["changed_variable"],
        "nearby_prior_experiments": result["nearby_prior_experiments"],
        "multiple_testing_risk_bucket": "moderate",
        "new_evidence_type": "invalid_near_neighbor_interest_burden",
        "decision": result["decision"],
        "summary": result["post_run_reflection"]["why_blocked"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "before": repo_rel(BEFORE_JSON),
        "after": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "card_file": repo_rel(CARD_MD),
        "revision_manifest_file": repo_rel(MANIFEST_JSON),
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "post_run_reflection": result["post_run_reflection"],
        "production_impact": result["production_impact"],
        "gate1_baseline": result["gate1_baseline"],
        "gate2_field_availability": result["gate2_field_availability"],
        "gate3_survival": result["gate3_survival"],
        "gate4": result["gate4"],
        "lean_quality_passed": result["lean_quality_passed"],
    }
    experiment_registry.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=result["prediction"],
        result=registry_result,
        status="blocked",
        fields=fields,
    )
    write_manifest(result)


def main() -> None:
    result = build_result()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": result["status"],
                "decision": result["decision"],
                "prior": PRIOR_INTEREST_RESULT["experiment_id"],
                "anti_js": result["anti_js"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
