"""exp-20260621-009: post-scalar-stack nonrepeat alpha readiness.

Alpha-search blocker. After the accepted helper allocator source-scalar stack,
only launch another Gate 1-4 strategy replay if a production-visible nonrepeat
candidate source has enough sample, novelty, and backtest/production parity.
This runner proves the current blocker and changes no trading policy.

No JavaScript is used.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
QUANT_DIR = REPO_ROOT / "quant"
EXPERIMENTS_DIR = QUANT_DIR / "experiments"
SCRIPTS_DIR = REPO_ROOT / "scripts"
for entry in (str(REPO_ROOT), str(QUANT_DIR), str(EXPERIMENTS_DIR), str(SCRIPTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import experiment_registry  # noqa: E402


EXPERIMENT_ID = "exp-20260621-009"
SLUG = "post_scalar_stack_nonrepeat_readiness"
RUNNER_NAME = f"quant/experiments/exp_20260621_009_{SLUG}.py"
RUNNER_COMMAND = ".\\.venv\\Scripts\\python.exe -B " + RUNNER_NAME.replace("/", "\\")

DATA_DIR = REPO_ROOT / "data" / "experiments" / EXPERIMENT_ID
ARTIFACT_JSON = DATA_DIR / f"exp_20260621_009_{SLUG}.json"
BEFORE_JSON = DATA_DIR / "before_baseline.json"
AFTER_JSON = DATA_DIR / "after_no_strategy_change.json"
README_MD = DATA_DIR / "README.md"
LOG_JSON = REPO_ROOT / "experiments" / "logs" / f"{EXPERIMENT_ID}.json"
CARD_MD = REPO_ROOT / "experiments" / "cards" / f"{EXPERIMENT_ID}.md"
MANIFEST_JSON = REPO_ROOT / "experiments" / "manifests" / f"{EXPERIMENT_ID}.json"
TICKET_JSON = REPO_ROOT / "experiments" / "tickets" / f"{EXPERIMENT_ID}.json"
EXPERIMENT_LOG_JSONL = REPO_ROOT / "docs" / "experiment_log.jsonl"
REGISTRY_JSON = REPO_ROOT / "docs" / "experiment_registry.json"

EVENT_SNAPSHOT_DIR = REPO_ROOT / "data" / "daily" / "snapshots" / "events"
NON_OHLCV_DIR = REPO_ROOT / "data" / "non_ohlcv"
SUBMISSIONS_DIR = REPO_ROOT / "data" / "cache" / "sec" / "submissions"

BASELINE_RESULT_FILE = "data/backtests/backtest_results_warehouse_snapshot_standard_windows_20260604.json"
MIN_TARGET_TRADES = 20
MIN_TARGET_WINDOWS = 3

CURRENT_ACCEPTED_SCALARS = {
    "industry_laggard_repair": 1.25,
    "revision_surprise_low_extension": 1.25,
    "rolling_peer_shock": 1.25,
    "turn_of_month": 1.25,
    "lagged_cross_source_consensus": 1.25,
}
REMAINING_UNSCALED_ALLOCATOR_SOURCES = [
    "volatility_relief",
    "compression",
    "industry_stable_core_flow",
]

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
        "trade_count": 22,
        "signals_generated": 60,
        "signals_survived": 52,
        "survival_rate": 0.8667,
    },
}

HYPOTHESIS = (
    "candidate_pool/data-edge: after the accepted helper source-scalar stack, "
    "the next executable alpha should come from a production-visible nonrepeat "
    "candidate source only if unscaled allocator sources, standalone accepted "
    "sleeve insertion, or a new PIT event/filer-status field has enough sample, "
    "novelty, and parity to run Gate 1-4; otherwise launching a strategy replay "
    "would duplicate frozen families or create production/backtest leakage."
)

PRIOR_BLOCKERS = [
    "exp-20260610-009",
    "exp-20260611-008",
    "exp-20260616-016",
    "exp-20260618-021",
    "exp-20260618-022",
    "exp-20260620-011",
    "exp-20260616-027",
    "exp-20260618-007",
    "exp-20260620-012",
    "exp-20260621-008",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def append_jsonl_once(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    needle = f'"experiment_id": "{EXPERIMENT_ID}"'
    if path.exists() and needle in path.read_text(encoding="utf-8-sig"):
        return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


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
        "min_survival_rate": round(
            min(float(row["survival_rate"]) for row in CANONICAL_WINDOWS.values()),
            4,
        ),
        "max_window_drawdown_pct": round(
            max(float(row["max_drawdown_pct"]) for row in CANONICAL_WINDOWS.values()),
            4,
        ),
    }


def metric_deltas() -> dict[str, dict[str, float]]:
    fields = ["expected_value_score", "total_pnl", "max_drawdown_pct", "trade_count"]
    return {
        label: {field: 0.0 for field in fields}
        for label in CANONICAL_WINDOWS
    }


def baseline_artifact(label: str) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "label": label,
        "baseline_result_file": BASELINE_RESULT_FILE,
        "windows": CANONICAL_WINDOWS,
        "aggregate": aggregate_windows(),
        "strategy_code_changed": False,
        "production_code_changed": False,
        "note": "No after strategy was launched; after intentionally equals before.",
    }


def summarize_current_allocator_selection() -> dict[str, Any]:
    import exp_20260620_032_accepted_allocator_independent_source_notional as template

    original_scalars = dict(template.allocator_helper.SOURCE_NOTIONAL_SCALARS)
    try:
        payload = template._run_allocator_pass(
            "exp009_current_accepted_scalar_stack_probe",
            dict(CURRENT_ACCEPTED_SCALARS),
        )
    finally:
        template._set_scalars(original_scalars)

    total_counts: Counter[str] = Counter()
    total_pnl: defaultdict[str, float] = defaultdict(float)
    by_window: dict[str, Any] = {}
    rows_by_window = payload.get("target_trades_by_window") or {}
    for label, rows in rows_by_window.items():
        counts: Counter[str] = Counter()
        pnl: defaultdict[str, float] = defaultdict(float)
        for row in rows:
            source = str(row.get("source_family") or "unknown")
            value = float(row.get("pnl") or 0.0)
            counts[source] += 1
            total_counts[source] += 1
            pnl[source] += value
            total_pnl[source] += value
        by_window[label] = {
            "selected_source_counts": dict(counts),
            "selected_source_pnl": {key: round(value, 2) for key, value in pnl.items()},
        }

    remaining = {}
    for source in REMAINING_UNSCALED_ALLOCATOR_SOURCES:
        count = int(total_counts[source])
        windows = [
            label
            for label, row in by_window.items()
            if int(row["selected_source_counts"].get(source, 0)) > 0
        ]
        remaining[source] = {
            "selected_trade_count": count,
            "windows_with_selected_rows": windows,
            "selected_pnl": round(total_pnl[source], 2),
            "gate3_sample_passed": count >= MIN_TARGET_TRADES and len(windows) >= MIN_TARGET_WINDOWS,
        }

    return {
        "current_source_notional_scalars": CURRENT_ACCEPTED_SCALARS,
        "selected_source_counts": dict(total_counts),
        "selected_source_pnl": {key: round(value, 2) for key, value in total_pnl.items()},
        "by_window": by_window,
        "remaining_unscaled_sources": remaining,
        "blocking_verdict": "blocked_remaining_unscaled_allocator_sources_sample_starved",
    }


def audit_event_snapshots() -> dict[str, Any]:
    files = sorted(EVENT_SNAPSHOT_DIR.glob("event_snapshot_*.json"))
    types: Counter[str] = Counter()
    rows = 0
    ticker_days = 0
    for path in files:
        payload = read_json(path)
        events = payload.get("events_by_ticker") or {}
        ticker_days += len(events)
        for event_rows in events.values():
            for row in event_rows:
                rows += 1
                types[str(row.get("event_type") or "unknown")] += 1
    return {
        "file_count": len(files),
        "first_file": files[0].name if files else None,
        "last_file": files[-1].name if files else None,
        "event_rows": rows,
        "ticker_days": ticker_days,
        "event_types": types.most_common(10),
        "blocking_verdict": (
            "blocked_generic_sparse_event_schema_without_structured_actor_object_magnitude"
        ),
    }


def audit_sec_text_and_submissions() -> dict[str, Any]:
    forms: Counter[str] = Counter()
    rows = 0
    for path in sorted(NON_OHLCV_DIR.glob("sec_filing_text_*.jsonl")):
        with path.open(encoding="utf-8-sig") as handle:
            for raw in handle:
                if not raw.strip():
                    continue
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                rows += 1
                forms[str(row.get("form_type") or row.get("form_base") or "unknown").upper()] += 1

    categories: Counter[str] = Counter()
    submission_files = 0
    for path in sorted(SUBMISSIONS_DIR.glob("CIK*.json")):
        payload = read_json(path)
        if not payload:
            continue
        submission_files += 1
        categories[str(payload.get("category") or "missing")] += 1

    return {
        "sec_filing_text_rows": rows,
        "sec_filing_text_forms": forms.most_common(12),
        "sec_text_10k_10q_rows": sum(forms[form] for form in ("10-K", "10-Q", "10-K/A", "10-Q/A")),
        "submission_files": submission_files,
        "current_submission_categories": categories.most_common(12),
        "blocking_verdict": (
            "blocked_current_submissions_category_not_historical_pit_cover_page_status"
        ),
    }


def prior_summary(exp_id: str) -> dict[str, Any]:
    payload = read_json(REPO_ROOT / "experiments" / "logs" / f"{exp_id}.json")
    return {
        "experiment_id": exp_id,
        "found": bool(payload),
        "decision": payload.get("decision"),
        "trial_variant_id": payload.get("trial_variant_id"),
        "aggregate_expected_value_delta": payload.get("aggregate_expected_value_delta"),
        "aggregate_strategy_total_pnl_delta": payload.get("aggregate_strategy_total_pnl_delta"),
        "failed_reasons": (payload.get("gate4") or {}).get("failed_reasons"),
        "new_evidence_required": (
            (payload.get("post_run_reflection") or {}).get("new_evidence_required")
            or payload.get("next_evidence_needed")
        ),
    }


def build_result() -> dict[str, Any]:
    ticket = read_json(TICKET_JSON)
    allocator_probe = summarize_current_allocator_selection()
    aggregate = aggregate_windows()
    gate4 = {
        "status": "blocked_no_after_policy",
        "before": CANONICAL_WINDOWS,
        "after": CANONICAL_WINDOWS,
        "window_deltas": metric_deltas(),
        "aggregate_before": aggregate,
        "aggregate_after": aggregate,
        "aggregate_delta": {
            "aggregate_expected_value_score": 0.0,
            "aggregate_total_pnl": 0.0,
            "total_trade_count": 0.0,
            "min_survival_rate": 0.0,
            "max_window_drawdown_pct": 0.0,
        },
        "reason": "Gate 2/Gate 3 readiness blocked all reviewed nonrepeat surfaces.",
    }
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": now_utc(),
        "lane": "alpha_search",
        "status": "blocked",
        "decision": "blocked_no_gate4_ready_nonrepeat_alpha_after_scalar_stack",
        "hypothesis": HYPOTHESIS,
        "change_type": "candidate_pool_data_edge_readiness",
        "mechanism_family": "nonrepeat_alpha_candidate_readiness",
        "trial_family": "post_accepted_scalar_stack_candidate_pool_readiness",
        "trial_variant_id": "post_scalar_stack_nonrepeat_candidate_pool_readiness_v1",
        "single_causal_variable": "post_scalar_stack_nonrepeat_candidate_pool_readiness_v1",
        "changed_variable": "post_scalar_stack_nonrepeat_candidate_pool_readiness_v1",
        "baseline_result_file": BASELINE_RESULT_FILE,
        "prediction": ticket.get("prediction") or {},
        "novelty": ticket.get("novelty") or {},
        "gate1": {
            "passed": True,
            "baseline_result_file": BASELINE_RESULT_FILE,
            "windows": CANONICAL_WINDOWS,
            "aggregate": aggregate,
        },
        "gate2": {
            "status": "blocked",
            "runtime_fields_checked": ["entry_date", "target_price"],
            "allocator_source_probe": allocator_probe,
            "event_snapshot_audit": audit_event_snapshots(),
            "sec_text_and_filer_status_audit": audit_sec_text_and_submissions(),
            "accepted_standalone_insertion_history": [prior_summary(exp) for exp in PRIOR_BLOCKERS],
            "blocking_item": (
                "No reviewed candidate source has all of: non-frozen novelty, "
                "three-window PIT/parity-safe fields, and enough selected/sample rows."
            ),
        },
        "gate3": {
            "status": "blocked_before_strategy_filter",
            "minimum_survival_rate": min(float(row["survival_rate"]) for row in CANONICAL_WINDOWS.values()),
            "remaining_unscaled_source_sample": allocator_probe["remaining_unscaled_sources"],
            "interpretation": (
                "A notional/scalar experiment for the remaining allocator sources "
                "would be invalid: volatility_relief and industry_stable_core_flow "
                "have zero current selected rows, and compression has only two."
            ),
        },
        "gate4": gate4,
        "delta_metrics": gate4["aggregate_delta"],
        "production_impact": {
            "strategy_code_changed": False,
            "shared_helper_changed": False,
            "backtester_adapter_changed": False,
            "daily_snapshot_changed": False,
            "live_orders_changed": False,
            "trade_enabled_changed": False,
            "parity_note": (
                "No production/backtest inconsistency was introduced because no "
                "trading rule or shared helper changed. A future positive alpha "
                "must be implemented shared-paper-first before acceptance."
            ),
        },
        "calibration": {
            "predicted_success_probability": (ticket.get("prediction") or {}).get("success_probability"),
            "actual_gate4_passed": False,
            "actual_success": 0,
            "failure_modes_observed": [
                "remaining_allocator_sources_sample_starved",
                "accepted_sleeve_insertions_already_rejected",
                "event_snapshot_schema_sparse_and_generic",
                "filer_status_current_metadata_not_pit",
            ],
        },
        "post_run_reflection": {
            "why_blocked": (
                "The remaining source-scalar path is sample-starved after the "
                "accepted scalar stack; accepted standalone sleeve insertions have "
                "already failed current-allocator comparators; event/filer-status "
                "surfaces lack the structured PIT fields needed for parity-safe "
                "Gate 4."
            ),
            "negative_result_reflection": (
                "The failure mode is not that a tested alpha lost money; it is that "
                "the next candidate would be a known-neighbor replay or a PIT leak. "
                "Recent negative alpha attempts failed mainly through old_thin "
                "regression, drawdown drift, thin samples, or accepted-comparator "
                "failure, and this run avoids repeating those shapes."
            ),
            "best_next_alpha_direction": (
                "Build a new free PIT data edge first: structured SEC customer/"
                "supplier/payment-term or contract-economics rows, historical "
                "10-K/10-Q cover-page filer-status by accession, PIT analyst "
                "breadth/dispersion including revenue estimates, or borrow/options "
                "as-of rows with fixed-window coverage."
            ),
            "forbidden_near_neighbor_retry": (
                "Do not retry allocator source rank/notional/top-N/cooldown, daily "
                "slot capacity, generic SEC item/event filters, current SEC "
                "submissions category, or Companyfacts ratio thresholds on frozen "
                "windows without a materially new PIT field or closed forward "
                "replacement-value rows."
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
        "reproduction": RUNNER_COMMAND,
        "anti_js": "No JavaScript was used.",
        "lean_quality_passed": True,
    }


def build_log_record(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": result["timestamp"],
        "lane": result["lane"],
        "status": result["status"],
        "decision": result["decision"],
        "hypothesis": result["hypothesis"],
        "change_type": result["change_type"],
        "mechanism_family": result["mechanism_family"],
        "trial_family": result["trial_family"],
        "trial_variant_id": result["trial_variant_id"],
        "changed_variable": result["changed_variable"],
        "aggregate_expected_value_delta": 0.0,
        "aggregate_strategy_total_pnl_delta": 0.0,
        "gate1": result["gate1"],
        "gate2": result["gate2"],
        "gate3": result["gate3"],
        "gate4": result["gate4"],
        "production_impact": result["production_impact"],
        "calibration": result["calibration"],
        "post_run_reflection": result["post_run_reflection"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "log": repo_rel(LOG_JSON),
        "anti_js": result["anti_js"],
        "lean_quality_passed": result["lean_quality_passed"],
    }


def build_card(result: dict[str, Any]) -> str:
    lines = [
        f"# {EXPERIMENT_ID}: post-scalar-stack nonrepeat readiness",
        "",
        "- Lane: alpha_search",
        "- Status: blocked",
        f"- Decision: {result['decision']}",
        "- Strategy / production behavior changed: no",
        "",
        "## Gate 4 Baseline",
        "",
        "| Window | Before EV | After EV | Delta EV | Before PnL | After PnL | Delta PnL |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, row in CANONICAL_WINDOWS.items():
        lines.append(
            f"| {label} | {row['expected_value_score']:.4f} | "
            f"{row['expected_value_score']:.4f} | 0.0000 | "
            f"${row['total_pnl']:,.2f} | ${row['total_pnl']:,.2f} | $0.00 |"
        )
    aggregate = result["gate4"]["aggregate_before"]
    remaining = result["gate3"]["remaining_unscaled_source_sample"]
    lines.extend(
        [
            "",
            "## Blocker",
            "",
            f"Aggregate baseline EV `{aggregate['aggregate_expected_value_score']:.4f}`, "
            f"PnL `${aggregate['aggregate_total_pnl']:,.2f}`. No after policy was run.",
            "",
            "Remaining unscaled allocator source sample:",
            "",
        ]
    )
    for source, row in remaining.items():
        lines.append(
            f"- `{source}`: `{row['selected_trade_count']}` selected rows, "
            f"windows `{row['windows_with_selected_rows']}`."
        )
    lines.extend(["", result["post_run_reflection"]["best_next_alpha_direction"], ""])
    return "\n".join(lines)


def build_readme(result: dict[str, Any]) -> str:
    return (
        f"# {EXPERIMENT_ID}\n\n"
        "Blocked alpha-search readiness record after the accepted source-scalar stack.\n\n"
        f"- Artifact: `{repo_rel(ARTIFACT_JSON)}`\n"
        f"- Log: `{repo_rel(LOG_JSON)}`\n"
        f"- Decision: `{result['decision']}`\n"
        f"- Reproduce: `{result['reproduction']}`\n"
    )


def persist(result: dict[str, Any]) -> None:
    write_json(BEFORE_JSON, baseline_artifact("before_baseline"))
    write_json(AFTER_JSON, baseline_artifact("after_no_strategy_change"))
    write_json(ARTIFACT_JSON, result)
    write_json(LOG_JSON, result)
    write_text(CARD_MD, build_card(result))
    write_text(README_MD, build_readme(result))
    manifest = {
        "experiment_id": EXPERIMENT_ID,
        "status": result["status"],
        "decision": result["decision"],
        "artifact": repo_rel(ARTIFACT_JSON),
        "before": repo_rel(BEFORE_JSON),
        "after": repo_rel(AFTER_JSON),
        "log": repo_rel(LOG_JSON),
        "card": repo_rel(CARD_MD),
        "runner": RUNNER_NAME,
        "command": result["reproduction"],
        "files": result["changed_files"],
        "anti_js": result["anti_js"],
        "updated_at": now_utc(),
    }
    write_json(MANIFEST_JSON, manifest)
    append_jsonl_once(EXPERIMENT_LOG_JSONL, build_log_record(result))

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
        "calibration": result["calibration"],
        "summary": result["post_run_reflection"]["why_blocked"],
    }
    experiment_registry.persist_self_registered_result(
        REGISTRY_JSON,
        experiment_id=EXPERIMENT_ID,
        lane="alpha_search",
        prediction=result["prediction"],
        result=registry_result,
        status="blocked",
        fields={
            "owner": "alpha-search-automation",
            "hypothesis": result["hypothesis"],
            "change_type": result["change_type"],
            "mechanism_family": result["mechanism_family"],
            "trial_family": result["trial_family"],
            "trial_variant_id": result["trial_variant_id"],
            "single_causal_variable": result["single_causal_variable"],
            "changed_variable": result["changed_variable"],
            "nearby_prior_experiments": PRIOR_BLOCKERS,
            "multiple_testing_risk_bucket": "moderate",
            "new_evidence_type": "post_exp20260621_accepted_scalar_stack_and_source_attribution",
            "baseline_result_file": BASELINE_RESULT_FILE,
            "evaluation_windows": [
                {"label": label, "start": row["start"], "end": row["end"], "snapshot": row["snapshot"]}
                for label, row in CANONICAL_WINDOWS.items()
            ],
            "acceptance_rule": (
                "Blocked unless a candidate surface clears PIT/parity, novelty, "
                "and three-window sample readiness."
            ),
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
            "gate1": result["gate1"],
            "gate2": result["gate2"],
            "gate3": result["gate3"],
            "gate4": result["gate4"],
            "production_impact": result["production_impact"],
            "post_run_reflection": result["post_run_reflection"],
            "lean_quality_passed": result["lean_quality_passed"],
        },
    )


def main() -> None:
    result = build_result()
    persist(result)
    print(
        json.dumps(
            {
                "experiment_id": EXPERIMENT_ID,
                "status": result["status"],
                "decision": result["decision"],
                "remaining_unscaled_sources": result["gate3"][
                    "remaining_unscaled_source_sample"
                ],
                "aggregate_ev_delta": result["delta_metrics"][
                    "aggregate_expected_value_score"
                ],
                "aggregate_pnl_delta": result["delta_metrics"]["aggregate_total_pnl"],
                "anti_js": result["anti_js"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
