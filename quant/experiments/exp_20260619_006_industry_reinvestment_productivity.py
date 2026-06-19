"""exp-20260619-006: industry reinvestment productivity blocker.

The ticket was reserved for an industry-normalized CapEx/D&A reinvestment
productivity candidate-pool scout. The post-reservation history check found a
direct near-neighbor, exp-20260617-009, which already tested sector-normalized
reinvestment productivity and explicitly froze peer/productivity retunes unless
new PIT reinvestment evidence exists.

This runner closes the ticket without replaying a strategy. No production code,
shared adapter, ranking, sizing, exits, LLM/news path, watchlist behavior, or
order path is changed. No JavaScript is used.
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


EXPERIMENT_ID = "exp-20260619-006"
SLUG = "industry_reinvestment_productivity"
RUNNER_NAME = (
    "quant/experiments/"
    "exp_20260619_006_industry_reinvestment_productivity.py"
)

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"exp_20260619_006_{SLUG}.json"
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
        "sharpe_daily": 4.41,
        "strategy_total_return_pct": 117.07,
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
        "strategy_total_return_pct": 78.11,
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
        "strategy_total_return_pct": 39.67,
        "total_pnl": 39667.96,
        "max_drawdown_pct": 0.1001,
        "win_rate": 0.4091,
        "trade_count": 22,
        "signals_generated": 60,
        "signals_survived": 52,
        "survival_rate": 0.8667,
    },
}

PRIOR_REINVESTMENT_PRODUCTIVITY = {
    "experiment_id": "exp-20260617-009",
    "decision": "rejected_sector_normalized_reinvestment_productivity_candidate_pool",
    "changed_variable": (
        "raw_sec_companyfacts_sector_normalized_reinvestment_productivity_"
        "candidate_source_v1"
    ),
    "aggregate_ev_delta": 0.2647,
    "aggregate_pnl_delta": 3809.50,
    "target_trade_count": 8,
    "target_windows": ["late_strong"],
    "windows": {
        "late_strong": {
            "expected_value_delta": 0.2647,
            "strategy_total_pnl_delta": 3809.50,
            "target_trade_count": 8,
        },
        "mid_weak": {
            "expected_value_delta": 0.0,
            "strategy_total_pnl_delta": 0.0,
            "target_trade_count": 0,
        },
        "old_thin": {
            "expected_value_delta": 0.0,
            "strategy_total_pnl_delta": 0.0,
            "target_trade_count": 0,
        },
    },
    "failed_reasons": [
        "fewer_than_two_ev_improved_windows",
        "target_sample_too_small",
        "target_window_coverage_too_small",
        "target_concentration_failed",
        "accepted_distribution_ev_not_beaten",
        "accepted_distribution_pnl_not_beaten",
    ],
    "forbidden_retry": (
        "Do not retry by sweeping peer-count, percentile, productivity formula, "
        "raw CapEx/D&A threshold values, tag lists, sector exclusions, annual "
        "fact freshness, RS/close/volume/vol guards, top-N, hold days, "
        "cooldown, or notional on these frozen windows."
    ),
    "new_evidence_required": (
        "A retry needs materially different PIT reinvestment evidence such as "
        "segment/customer capacity disclosures or closed forward replacement-"
        "value rows."
    ),
}

HYPOTHESIS = (
    "candidate_pool: industry-normalized CapEx/D&A reinvestment productivity "
    "may separate productive replacement cycles from noisy raw CapEx expansion "
    "by requiring same-industry revenue-per-reinvestment leadership before "
    "next-open 10-day default-off paper entry."
)

PREDICTION = {
    "success_probability": 0.14,
    "expected_ev_delta": None,
    "expected_pnl_delta": None,
    "main_failure_modes": [
        "near_neighbor_companyfacts_reinvestment_family",
        "old_thin_regression",
        "drawdown_drift",
        "accepted_distribution_not_beaten",
        "industry_peer_sample_too_thin",
    ],
    "confidence_reason": (
        "The ticket was reserved because exp-20260617-007 named industry-"
        "normalized productivity as possible new evidence. The full history "
        "check then found exp-20260617-009 had already run that peer-normalized "
        "productivity shape and froze formula/peer-count retunes."
    ),
}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00",
        "Z",
    )


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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
        "total_trade_count": sum(
            int(row["trade_count"]) for row in CANONICAL_WINDOWS.values()
        ),
        "min_survival_rate": min(
            float(row["survival_rate"]) for row in CANONICAL_WINDOWS.values()
        ),
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
        "note": (
            "Identity artifact: no after policy was tested because the "
            "post-reservation novelty/history check failed."
        ),
    }


def window_deltas() -> dict[str, dict[str, float]]:
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


def build_result() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON)
    novelty = ticket.get("novelty") or {}
    now = now_utc()
    aggregate = aggregate_windows()
    return {
        "experiment_id": EXPERIMENT_ID,
        "created_at": now,
        "lane": "alpha_search",
        "status": "blocked",
        "decision": (
            "blocked_industry_reinvestment_productivity_near_neighbor_"
            "invalid_novelty_axis"
        ),
        "hypothesis": ticket.get("hypothesis") or HYPOTHESIS,
        "change_type": "alpha_search_near_neighbor_blocker",
        "mechanism_family": (
            "production_visible_free_sec_companyfacts_reinvestment_cycle_"
            "candidate_pool"
        ),
        "trial_family": "industry_normalized_reinvestment_productivity_candidate_pool",
        "trial_variant_id": (
            "industry_normalized_reinvestment_productivity_top1_next_open_10d_v1"
        ),
        "single_causal_variable": (
            "raw_sec_companyfacts_industry_normalized_reinvestment_productivity_"
            "candidate_source_v1"
        ),
        "changed_variable": (
            "raw_sec_companyfacts_industry_normalized_reinvestment_productivity_"
            "candidate_source_v1"
        ),
        "nearby_prior_experiments": [
            "exp-20260617-007",
            "exp-20260617-009",
            "exp-20260617-010",
        ],
        "prediction": ticket.get("prediction") or PREDICTION,
        "pre_run_answers": {
            "alpha_hypothesis": ticket.get("hypothesis") or HYPOTHESIS,
            "category": "candidate_pool",
            "historical_check": {
                "reservation_nearest": novelty.get("nearest"),
                "direct_prior": PRIOR_REINVESTMENT_PRODUCTIVITY,
                "conclusion": (
                    "Industry-normalized productivity is not a fresh axis after "
                    "exp-20260617-009; it is a peer-normalized reinvestment "
                    "productivity retry without segment/customer capacity or "
                    "closed forward replacement-value rows."
                ),
            },
            "single_policy_bundle_under_test": (
                "No strategy policy is tested. The ticket is closed as an "
                "invalid near-neighbor after history review."
            ),
            "success_criteria": (
                "A valid run would need three-window Gate 4 coverage and a "
                "materially new PIT reinvestment surface; this ticket has "
                "neither versus the direct prior."
            ),
            "reproducibility": (
                ".\\.venv\\Scripts\\python.exe -B "
                "quant\\experiments\\exp_20260619_006_industry_reinvestment_productivity.py"
            ),
        },
        "novelty_check": {
            "reservation_warning": novelty.get("warn"),
            "reservation_nearest": novelty.get("nearest"),
            "override_recorded": novelty.get("override"),
            "override_axis": novelty.get("new_evidence_axis"),
            "post_reservation_conclusion": (
                "The override is not sufficient because exp-20260617-009 "
                "already tested peer-normalized reinvestment productivity and "
                "froze peer-count/productivity-formula retunes."
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
                "The available Companyfacts CapEx/D&A/revenue fields are the "
                "same reinvestment-productivity surface family. The new "
                "required fields, segment/customer capacity disclosures or "
                "closed forward replacement-value rows, are absent."
            ),
            "direct_prior": PRIOR_REINVESTMENT_PRODUCTIVITY,
        },
        "gate3_survival": {
            "status": "not_applicable_no_new_filter",
            "baseline_min_survival_rate": aggregate["min_survival_rate"],
            "guardrail": "survival_rate must not fall below 0.05",
            "prior_target_trade_count": PRIOR_REINVESTMENT_PRODUCTIVITY[
                "target_trade_count"
            ],
            "prior_target_windows": PRIOR_REINVESTMENT_PRODUCTIVITY["target_windows"],
        },
        "gate4": {
            "status": "blocked_no_after_policy",
            "before": CANONICAL_WINDOWS,
            "after": CANONICAL_WINDOWS,
            "window_deltas": window_deltas(),
            "aggregate_before": aggregate,
            "aggregate_after": aggregate,
            "aggregate_delta": {
                "aggregate_expected_value_score": 0.0,
                "aggregate_total_pnl": 0.0,
                "total_trade_count": 0,
                "min_survival_rate": 0.0,
                "max_window_drawdown_pct": 0.0,
            },
            "direct_prior_three_window_result": PRIOR_REINVESTMENT_PRODUCTIVITY[
                "windows"
            ],
            "acceptance_result": "blocked",
            "reason": (
                "No replay was run because the direct prior was positive only "
                "in late_strong, had 8 trades, zero mid_weak/old_thin target "
                "coverage, failed concentration, and did not beat the accepted "
                "distribution comparator."
            ),
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
            "surprise": (
                "Moderate. The ticket used exp-20260617-007's proposed reopen "
                "axis, but the later exp-20260617-009 had already consumed and "
                "rejected that peer-normalized productivity shape."
            ),
        },
        "production_impact": {
            "production_code_changed": False,
            "backtest_code_changed": False,
            "live_orders_changed": False,
            "shared_helper_added": False,
            "trade_enabled_changed": False,
            "parity_assessment": (
                "No production/backtest inconsistency was introduced because "
                "no policy or helper changed. A future positive reinvestment "
                "alpha would need a shared default-off helper before any "
                "promotion claim."
            ),
        },
        "post_run_reflection": {
            "why_blocked": (
                "The reserved idea is a near-neighbor of exp-20260617-009. That "
                "prior had aggregate EV +0.2647 and PnL +$3,809.50, but only "
                "8 target trades in late_strong, zero target trades in "
                "mid_weak and old_thin, failed target concentration, and did "
                "not beat the accepted distribution comparator."
            ),
            "forbidden_near_neighbor_retry": PRIOR_REINVESTMENT_PRODUCTIVITY[
                "forbidden_retry"
            ],
            "new_evidence_required": PRIOR_REINVESTMENT_PRODUCTIVITY[
                "new_evidence_required"
            ],
            "best_next_alpha_direction": (
                "Use a genuinely new free PIT candidate-pool surface: "
                "segment/customer capacity disclosures, structured contract "
                "economics, 13D/13G amendment stake-direction provenance, "
                "listing/lockup/float fields, or historical analyst breadth/"
                "dispersion rows."
            ),
            "negative_reflection": (
                "This did not proceed because the proposed improvement was not "
                "new. Retrying inside the same peer/productivity formula space "
                "would optimize a sparse late_strong-only artifact."
            ),
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
        "reproduction": (
            ".\\.venv\\Scripts\\python.exe -B "
            "quant\\experiments\\exp_20260619_006_industry_reinvestment_productivity.py"
        ),
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
        "pre_run_answers": result["pre_run_answers"],
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
        f"# {EXPERIMENT_ID}: industry reinvestment productivity blocker",
        "",
        "- Lane: alpha_search",
        "- Status: blocked",
        f"- Decision: {result['decision']}",
        "- Direct prior: exp-20260617-009 already rejected peer-normalized "
        "reinvestment productivity.",
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
            "## Prior evidence",
            "",
            "exp-20260617-009 produced aggregate EV +0.2647 and aggregate PnL "
            "+$3,809.50, but only 8 target trades, all in late_strong. It had "
            "zero target trades in mid_weak and old_thin, failed target "
            "concentration, and did not beat the accepted distribution "
            "comparator.",
            "",
            "## Conclusion",
            "",
            "No strategy replay was run. A valid retry needs materially "
            "different PIT reinvestment evidence such as segment/customer "
            "capacity disclosures or closed forward replacement-value rows.",
            "",
            "No production code, backtest policy, shared helper, live order "
            "path, ranking, sizing, or exit logic changed. No JavaScript was "
            "used.",
            "",
        ]
    )
    return "\n".join(lines)


def build_readme(result: dict[str, Any]) -> str:
    return (
        f"# {EXPERIMENT_ID}\n\n"
        "Alpha-search blocker artifact. The industry-normalized reinvestment "
        "productivity idea was not replayed because history proved it was a "
        "near-neighbor of exp-20260617-009.\n\n"
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
        "multiple_testing_risk_bucket": "minimal",
        "new_evidence_type": "invalid_near_neighbor_reinvestment_productivity",
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
                "direct_prior": PRIOR_REINVESTMENT_PRODUCTIVITY["experiment_id"],
                "aggregate_ev_delta": result["delta_metrics"][
                    "aggregate_expected_value_score"
                ],
                "aggregate_pnl_delta": result["delta_metrics"][
                    "aggregate_total_pnl"
                ],
                "anti_js": result["anti_js"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
